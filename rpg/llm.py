"""Talking to a local model, off the main thread.

A turn on a local 12B can take two minutes, so every request runs in a worker
and the game loop polls a queue. The room keeps breathing while he thinks.
"""

import json
import os
import queue
import re
import ssl
import threading
import time
import urllib.error
import urllib.request

from case import CASE, SUSPECTS_BY_ID
from settings import asset

# Where the address of the shared model server is published. Editing that file
# in the repository repoints every copy of the game already in players' hands -
# no rebuild, no reinstall, no new download.
DIRECTORY_URL = "https://raw.githubusercontent.com/Dekpunpun/Robot-project/main/server.json"
LOCAL_URL = "http://localhost:1234/v1"

BASE_URL = (os.environ.get("LLM_URL") or LOCAL_URL).rstrip("/")
API_KEY = os.environ.get("LLM_KEY", "lm-studio")
# A turn against the shared server is a queued turn - several other players'
# turns may be batched ahead of it, on top of the minute-plus one turn already
# costs. Anything below that just fails requests the server is still working on.
TIMEOUT = 240
PROBE_TIMEOUT = 20


class ServerBusy(Exception):
    """Every slot on the shared server is already in use.

    Carried as its own type so the wait is reported to the player as a queue -
    something that clears on its own - rather than as a connection failure,
    which reads like the game is broken.
    """


def _ssl_context():
    """Trust roots for HTTPS.

    A frozen build ships no CA bundle of its own, and CPython's compiled-in
    default path points inside the *developer's* Python installation - a path
    that does not exist on anyone else's machine, so certificate verification
    fails there for every https request while working perfectly here. The
    bundled certifi file is what makes the shared server reachable off this
    machine at all; falling back to the system default keeps running from
    source, where that path does resolve, exactly as it was.
    """
    bundled = asset("cacert.pem")
    if os.path.exists(bundled):
        return ssl.create_default_context(cafile=bundled)
    return ssl.create_default_context()


SSL_CTX = _ssl_context()

# The directory lookup is deliberately slow to repeat: main.py retries the
# connection every ~4s for as long as it is down, and that loop must not become
# one request per tick against GitHub.
DIRECTORY_TTL = 60
_directory = {"at": 0.0, "message": ""}


def _resolve_base_url():
    """Point BASE_URL at the shared server, if there is one to point at.

    Returns a message to show the player *instead* of connecting (the operator
    has taken the server down deliberately), or "" to go ahead. LLM_URL always
    wins, so a developer aimed at their own backend is never redirected. If the
    directory cannot be read the last known address stands, and failing that
    localhost - so a player running their own LM Studio still works with no
    internet at all.

    The gateway's token travels with the address for the same reason the
    address is not compiled in: it can be rotated without anyone reinstalling.
    Publishing it in a public file loses nothing that shipping it inside a
    downloadable binary had not already lost - its job is to turn away scanners
    that stumble onto the tunnel hostname, not to keep out anyone holding a
    copy of the game.
    """
    global BASE_URL, API_KEY
    if os.environ.get("LLM_URL"):
        return ""
    now = time.monotonic()
    if _directory["at"] and now - _directory["at"] < DIRECTORY_TTL:
        return _directory["message"]
    # Set before the fetch, not after: a directory that is failing must back
    # off on exactly the same cadence as one that is working.
    _directory["at"] = now
    try:
        # raw.githubusercontent serves max-age=300, so without busting the
        # cache an address change stays invisible for five minutes - long
        # enough that moving the server would look like an outage.
        req = urllib.request.Request(
            f"{DIRECTORY_URL}?t={int(now)}",
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
            entry = json.load(r)
    except Exception:  # noqa: BLE001 - unreachable directory just means "keep what we have"
        return _directory["message"]
    if not entry.get("enabled", True):
        _directory["message"] = entry.get("message") or "The case server is offline right now."
        return _directory["message"]
    url = (entry.get("url") or "").strip()
    if url:
        BASE_URL = url.rstrip("/")
    token = (entry.get("token") or "").strip()
    # LLM_KEY stays authoritative: a developer pointed at their own backend
    # must not have its credential replaced by the shared server's.
    if token and not os.environ.get("LLM_KEY"):
        API_KEY = token
    _directory["message"] = ""
    return ""

# The whole control block, loosely — individual key=value pairs are pulled
# out of it separately so a model that omits a field (or a case that doesn't
# need one) never breaks parsing.
TELL_BLOCK = re.compile(r"\[\[TELL(.*?)\]\]", re.I | re.S)
TELL_FIELD = re.compile(r"(\w+)\s*=\s*([^\s\]]+)")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# A transcript-style "Name: words" line. The format example in the system
# prompt has to show both sides of an exchange to be readable, and a weaker
# local model sometimes copies that shape whole - labelling its own line, or
# writing the detective's question for them and answering it. Both read to
# the player as the suspect talking like the detective.
SPEAKER_LINE = re.compile(r"^[ \t]*([A-Za-z][\w.'\-]*(?:[ \t]+[A-Za-z][\w.'\-]*){0,4})[ \t]*:[ \t]*(.*)$")
DETECTIVE_LABEL = re.compile(r"^(the\s+)?det(ective)?\.?$", re.I)
# The same fabricated line, but punctuated as prose rather than as a
# transcript entry: `Detective "You are lying."` with no colon at all.
DETECTIVE_QUOTED = re.compile(r"^[ \t]*(the[ \t]+)?det(ective)?\.?[ \t]*[\"\u201c]", re.I)

# Hybrid-reasoning models (Qwen3 and friends) think in a hidden <think>...
# </think> block before actually answering, by default, regardless of what
# the system prompt asks for. Left unstripped this either leaks the whole
# internal monologue onto the player's screen as "dialogue" (reads exactly
# like hallucination) or - if it runs past max_tokens before closing the
# tag - eats the entire token budget on a reply the player never sees at
# all, forcing the expensive empty-content retry. `chat_template_kwargs`
# below asks the server to turn thinking off outright; stripping here is
# the backstop for servers/models that ignore that request.
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.I | re.S)


def _strip_think(text):
    text = THINK_BLOCK.sub("", text)
    # An opened-but-never-closed tag means the whole visible budget was
    # spent mid-thought - nothing after it is a real answer.
    text = re.split(r"<think>", text, maxsplit=1, flags=re.I)[0]
    return text.strip()

# A hard backstop on top of RULES' own "1-4 sentences" - a model that just
# won't stop can turn a short in-character answer into a wall of invented,
# off-script rambling spanning many dialogue-box pages. This clamps the
# *symptom* regardless of why the model overran. Matches the RULES text
# exactly (4, not some looser buffer) - long run-on "sentences" still get a
# second, character-based cut below.
MAX_SPOKEN_SENTENCES = 4
MAX_SPOKEN_CHARS = 320


def _dedupe_repeats(sentences):
    """Collapse "Yes I do. Yes I do. Yes I do." down to one - a degenerate
    repetition loop a weak or unlucky local model can fall into regardless
    of sampling settings. Only consecutive repeats collapse, so a phrase the
    character genuinely says twice at different points in a longer answer is
    left alone."""
    out = []
    for sent in sentences:
        if out and sent.strip().lower() == out[-1].strip().lower():
            continue
        out.append(sent)
    return out


def _post(path, payload):
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # The gateway refuses immediately once every slot is busy rather than
        # letting the turn queue silently until it times out - a wait the
        # player can be told about beats four minutes of a frozen screen.
        if e.code == 503:
            raise ServerBusy(
                "Someone else is being questioned right now. Give it a moment, then ask again."
            ) from None
        raise


def _get(path):
    req = urllib.request.Request(BASE_URL + path, headers={"Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT, context=SSL_CTX) as r:
        return json.load(r)


def _is_chat_model(mid):
    """Embedding and rerank models will 400 a chat request."""
    return not re.search(r"embed|embedding|rerank", mid, re.I)


class Client:
    def __init__(self):
        self.model = None
        self.results = queue.Queue()
        self.busy = False
        self.status = "unknown"  # unknown | ok | down
        self.error = ""
        self.generation = 0
        self.checking = False

    # --- connection ------------------------------------------------------

    def check(self):
        """Re-checkable at any time, including while `status == "down"` - the
        game calls this periodically so starting LM Studio after the game
        launches recovers on its own instead of requiring a restart."""
        if self.checking:
            return
        self.checking = True
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            self._probe()
        finally:
            self.checking = False

    def _probe(self):
        """The actual connectivity check, with no `checking`-flag bookkeeping
        of its own - `_check()` above owns that flag on behalf of the
        background thread `check()` starts. `_ask()` below also calls this
        directly (synchronously, on its own worker thread) when no model id
        is known yet; it must not go through `_check()` for that, since
        clearing `checking` on a turn that never set it could stomp on an
        unrelated check already in flight from `check()`."""
        try:
            offline = _resolve_base_url()
            if offline:
                self.status, self.error = "down", offline
                return
            data = _get("/models")
            ids = [m["id"] for m in data.get("data", []) if _is_chat_model(m.get("id", ""))]
            if not ids:
                self.status, self.error = "down", "The case server has no chat model loaded."
                return
            self.model = self.model or ids[0]
            self.status, self.error = "ok", ""
        except Exception as e:  # noqa: BLE001 - any failure means "not reachable"
            self.status = "down"
            # Deliberately without the URL. This string is shown to the player,
            # and the shared server's address is not theirs to be handed - the
            # exception type is the part that helps diagnose it anyway.
            self.error = f"The case server is not answering ({e.__class__.__name__})."

    # --- one turn --------------------------------------------------------

    def ask(self, messages):
        """Fire a request. The answer arrives via `poll()`."""
        self.generation += 1
        gen = self.generation
        self.busy = True
        threading.Thread(target=self._ask, args=(messages, gen), daemon=True).start()

    def cancel(self):
        """Abandon the in-flight turn. There is no way to kill the worker
        thread from here, so it keeps running to completion - but its result
        is tagged with the generation it started under, and `poll()` silently
        discards anything that doesn't match the current one. Bumping the
        generation here is also what lets a fresh `ask()` proceed immediately
        instead of being blocked by the stale turn's own `finally` clause."""
        self.generation += 1
        self.busy = False

    def _once(self, messages, temperature, max_tokens):
        data = _post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                # Nudges a local model away from the degenerate "yes I do.
                # yes I do. yes I do." loop a repetition-blind sampler can
                # fall into - standard OpenAI-compatible fields, honoured
                # by llama.cpp's server too. _dedupe_repeats below is the
                # backstop for whatever gets through anyway.
                "frequency_penalty": 0.4,
                "presence_penalty": 0.4,
                # A reply that runs on into the detective's next line is the
                # single most common way a weaker model breaks character.
                # Cutting generation at the label costs nothing when it never
                # appears, and saves the wasted tokens when it does. Anchored
                # to a line start, and to the colon/quote that makes it a
                # speaker label, so prose like "Detective work is your job"
                # is left alone. strip_speaker_labels stays the backstop for
                # servers that ignore `stop` and for casings not listed here.
                "stop": ["\nDetective:", "\nDETECTIVE:", "\nDet:", "\nDetective \""],
                # Qwen3's server-side switch for its default thinking mode.
                # Silently ignored by any backend/model that doesn't
                # recognise it, so this is safe to send unconditionally.
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("The model server returned no choices - check that a chat model is loaded.")
        message = choices[0].get("message") or {}
        content = _strip_think((message.get("content") or "").strip())
        return content, choices[0].get("finish_reason")

    def _ask(self, messages, gen):
        try:
            if not self.model:
                self._probe()
                if self.status != "ok":
                    raise RuntimeError(self.error)

            # Sized for a shared server: several turns are generated at once,
            # so a shorter cap clears the queue faster for everyone. RULES asks
            # for 1-4 sentences, which fits inside this comfortably.
            content, finish = self._once(messages, 0.7, 300)

            # A reasoning model that ran out of room emits nothing but its
            # scratchpad. More tokens would only buy a longer spiral, so the
            # retry leans on a blunt instruction instead.
            if not content and finish == "length":
                nudge = {
                    "role": "system",
                    "content": (
                        "STOP DELIBERATING. Your previous attempt produced no visible reply. "
                        "Output the character's spoken words (1-4 sentences) and the control "
                        "line. Nothing else."
                    ),
                }
                content, _ = self._once(messages + [nudge], 0.6, 3500)

            if not content:
                raise RuntimeError(
                    "The model spent its whole budget thinking and never spoke. Try a "
                    "smaller or non-reasoning model in LM Studio."
                )
            self.results.put((gen, "ok", content))
        except Exception as e:  # noqa: BLE001
            self.results.put((gen, "err", str(e)))
        finally:
            # Only clear `busy` if nothing has cancelled or superseded this
            # turn since it started - otherwise a stale, just-finished
            # request could stomp on a newer one already in flight.
            if gen == self.generation:
                self.busy = False

    def poll(self):
        """The next result for the *current* generation, or None. A result
        from a turn that was cancelled or superseded carries an old
        generation number and is dropped here rather than ever reaching the
        game - `ask()`/`cancel()` already moved past it."""
        while True:
            try:
                gen, kind, payload = self.results.get_nowait()
            except queue.Empty:
                return None
            if gen == self.generation:
                return kind, payload


# --- prompt -----------------------------------------------------------------


def strip_speaker_labels(text, speaker=None):
    """Drop transcript-style name labels, and any line written as the detective.

    Runs before whitespace is collapsed, while the line breaks the model
    actually emitted are still there to split on. A line the model wrote for
    the detective is the player's own words put back in their mouth, so it is
    dropped outright; the suspect's own label is merely redundant - the
    dialogue box already draws their name - so only the label comes off.
    """
    surname = speaker.split()[-1].lower() if speaker else None
    out = []
    for line in text.splitlines():
        if DETECTIVE_QUOTED.match(line):
            continue
        m = SPEAKER_LINE.match(line)
        if not m:
            out.append(line)
            continue
        label, rest = m.group(1).strip(), m.group(2)
        if DETECTIVE_LABEL.match(label):
            continue
        # A speaker label ends on the name: "Doss", "Cpl. Doss", "Corporal
        # Wyatt Doss". Testing the last word rather than the whole label keeps
        # a real sentence that happens to name them - "Sergeant Thorne told
        # me: he was home" - from being read as a label and having everything
        # before the colon deleted.
        words = label.lower().replace(",", " ").split()
        if surname and words and words[-1].strip(".") == surname:
            out.append(rest)
            continue
        out.append(line)
    text = "\n".join(out).strip()
    # The example shows spoken words in quotes, so a model copying it wraps
    # the whole reply. Only unwrap when the pair really is the outer shell -
    # a reply that quotes something mid-sentence keeps its quotes.
    for open_q, close_q in (('"', '"'), ("\u201c", "\u201d")):
        if len(text) > 1 and text[0] == open_q and text[-1] == close_q:
            inner = text[1:-1]
            if open_q not in inner and close_q not in inner:
                text = inner.strip()
            break
    return text


def parse_tell(raw, speaker=None):
    """Pull the hidden control line out.

    Returns (spoken, composure, delta, asked, concepts). `asked` is only ever
    meaningful for the two evidence_plus_question suspects, and `concepts` is
    only ever meaningful for Bricker - both default to a false/empty value the
    rest of the time, which every other suspect's stance logic ignores.
    """
    block = TELL_BLOCK.search(raw)
    composure, delta, asked, concepts = None, 0, False, []
    if block:
        # Field *names* are lowercased before lookup - TELL_BLOCK itself is
        # case-insensitive on "TELL", but a model that also uppercases a
        # field name (COMPOSURE=...) must not silently lose that field.
        fields = {k.lower(): v for k, v in TELL_FIELD.findall(block.group(1))}
        if "composure" in fields:
            composure = fields["composure"].lower()
        if "pressure" in fields:
            try:
                delta = int(fields["pressure"])
            except ValueError:
                delta = 0
        asked = fields.get("asked", "no").lower() in ("yes", "true", "1")
        concepts = [c for c in fields.get("concepts", "").lower().split(",") if c]
        spoken = TELL_BLOCK.sub("", raw).strip()
    else:
        # No complete [[TELL ... ]] block matched - either there never was
        # one, or the model got cut off mid-block. Either way, a stray,
        # unterminated "[[TELL" must never leak onto the player's screen as
        # if it were dialogue.
        spoken = re.split(r"\[\[TELL", raw, maxsplit=1, flags=re.I)[0].strip()
    spoken = strip_speaker_labels(spoken, speaker)
    spoken = re.sub(r"\s{2,}", " ", spoken)
    sentences = _dedupe_repeats(SENTENCE_SPLIT.split(spoken))
    spoken = " ".join(sentences)
    if len(sentences) > MAX_SPOKEN_SENTENCES:
        spoken = " ".join(sentences[:MAX_SPOKEN_SENTENCES])
    if len(spoken) > MAX_SPOKEN_CHARS:
        # A model that writes a handful of very long run-on "sentences"
        # slips past the count-based cap above - fall back to cutting at
        # the last sentence boundary inside the character budget, or if
        # there isn't one, the last space, so this never hacks off mid-word.
        cut = spoken[:MAX_SPOKEN_CHARS]
        boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        spoken = cut[: boundary + 1] if boundary != -1 else cut[: cut.rfind(" ")]
        spoken = spoken.strip()
    return spoken, composure, delta, asked, concepts


def _stance(s, state):
    """The STANCE block and the extra control-line instruction, dispatched on
    this suspect's break mechanic. Returns (stance_text, control_line_help)."""
    brk = s["break"]

    if brk["type"] == "threshold_any":
        hit = [e for e in brk["pool"] if e in state["presented"]]
        if len(hit) >= brk["count"]:
            stance = (
                "STANCE: You are cornered. They have laid out real evidence: "
                + ", ".join(hit) + ". Stop lying. Break - quietly, not theatrically - and "
                f"give up the truth in pieces as they press. You may admit {s['concession']}, "
                "because that is true."
            )
        elif state["pressure"] >= 55:
            stance = (
                "STANCE: You are badly rattled. You concede small things to buy room, but you "
                f"protect {s['protects']} at all costs."
            )
        elif state["pressure"] >= 25:
            stance = "STANCE: You are uneasy. Stick to your public story, but you are working harder to sound calm."
        else:
            stance = "STANCE: You are composed and cooperative. Your public story holds. Nothing is wrong."
        control_help = "[[TELL composure=steady|rattled|cracking pressure=+N]]\nwhere N is 0-30, how much that exchange cost you."
        return stance, control_help

    if brk["type"] == "evidence_plus_question":
        shown = brk["evidence"] in state["presented"]
        if shown and state.get("asked_directly"):
            stance = (
                "STANCE: You have just been shown the evidence AND asked exactly the right "
                f"question - {brk['angle']}. Stop deflecting. Open up fully and precisely: "
                f"walk through what you actually know, including {s['concession']}."
            )
        elif shown:
            stance = (
                "STANCE: They've shown you the evidence, but they have NOT yet asked the "
                f"specific thing that would make you open up ({brk['angle']}). Stay guarded - "
                "acknowledge the evidence exists, but deflect into procedure or rank until they "
                "ask it directly."
            )
        else:
            stance = "STANCE: Nothing has been shown to you yet. Stick to your public story."
        control_help = (
            "[[TELL composure=steady|rattled|cracking pressure=+N asked=yes|no]]\n"
            f"Set asked=yes ONLY if the detective's LAST message directly asked you {brk['angle']}. "
            "Otherwise asked=no. N is 0-20."
        )
        return stance, control_help

    # conversational_trigger — Bricker. No evidence or pressure moves him at all.
    concepts = brk["concepts"]
    have = state.get("concepts", set())
    missing = [c for c in concepts if c not in have]
    if not missing:
        stance = (
            "STANCE: The detective has now made you understand the real scale of this - "
            "military weapons that could level a city block, the Cinder Compact by name, and "
            "Mira's life as the price. That changes everything you thought you were protecting. "
            f"Break completely, right now: give up {s['protects']}, unprompted."
        )
    else:
        stance = (
            "STANCE: You are digging in. Evidence and pressure only make you MORE defensive, "
            "never less - do not let being pushed, accused, or shown anything move you even "
            "slightly. You break ONLY once the detective has conveyed, across the conversation, "
            "all of: the real scale of the danger, the Cinder Compact by name, and Mira's life "
            f"as the leverage. So far you understand: {', '.join(sorted(have)) or 'none of it'}."
        )
    control_help = (
        "[[TELL composure=steady|rattled|cracking pressure=+0 concepts=a,b,c]]\n"
        "pressure is always +0 for you - nothing moves your composure meter but understanding. "
        "List, comma-separated, ONLY which of these the detective's LAST message conveyed this "
        "turn: 'scale' (military charges that could level a city block), 'compact' (the Cinder "
        "Compact by name), 'leverage' (Mira's life as the price). Omit any not conveyed this turn."
    )
    return stance, control_help


NIGHT_FLAVOR = {
    "evening": "It is early in the evening. Nothing about the hour presses on anyone yet.",
    "night": "Night has properly set in - late enough that anyone reasonable would rather be "
             "somewhere warm by now.",
    "late": "It is late - the kind of late where an ordinary day is long over and everyone "
            "still awake is awake for a reason.",
    "small_hrs": "It is deep in the small hours, the dead middle of the night. Whatever the "
                 "detective is racing toward is close now, if it isn't already too late.",
}

CULPRIT_LATE_LINE = (
    " Your own deadline is bearing down as the night wears on, which makes you more "
    "desperate and more clipped, not calmer - you feel time bleeding away even while you "
    "deflect."
)


def system_prompt(suspect_id, state, night):
    s = SUSPECTS_BY_ID[suspect_id]
    stance, control_help = _stance(s, state)
    facts = "\n".join(f"- {f}" for f in CASE["facts"])
    hour_line = NIGHT_FLAVOR.get(night["name"], "")
    # Whoever is actually racing the midnight handoff feels the hour bearing
    # down harder than everyone else does - which suspect that is changes
    # every run (see case.py's pick_culprit()), so this reads off the current
    # culprit rather than a suspect id baked in at authoring time.
    if suspect_id == CASE["conviction"]["culprit"] and night["name"] in ("late", "small_hrs"):
        hour_line += CULPRIT_LATE_LINE
    if state.get("warned"):
        hour_line += (
            " You already told the detective you're on limited time here, and you feel that "
            "clock pressing on you now more than anything else in the room."
        )
    leave_line = (
        "You are standing in the street and can end this conversation any time you like - "
        "nobody is making you stay."
        if s["id"] == "bricker"
        else "You are standing where the detective found you and are free to walk away, but a "
        "reasonable person in your position keeps talking rather than making that scene."
    )
    return f"""ANSWER IMMEDIATELY. Do not deliberate, plan, draft alternatives, second-guess yourself, or check your answer against these rules before writing. Speak the first thing the character would say. Your entire output is your spoken words plus one control line - a local model that spends its budget thinking produces nothing the player can see.

You are {s['name']}. {s['role']}
You are being questioned by a detective investigating the theft of five VSP-5 demolition charges from Fort Callow, and the disappearance of {CASE['victim']['name']} ({CASE['victim']['detail']}).

PERSONALITY: {s['personality']}

YOUR PUBLIC STORY: {s['publicAlibi']}

THE TRUTH, WHICH YOU WILL NOT VOLUNTEER: {s['hiddenTruth']}

WHAT YOU ARE REALLY PROTECTING: {s['motive']}

CASE FACTS - these are established and you cannot contradict them:
{facts}

THE HOUR: {hour_line} You may let this colour your tone and patience, and may reference how late it's gotten in your own words, but you do not know an exact time and must never state one.

{stance}

RULES:
1. Default to your public story. Deflect, minimise, redirect.
2. You may lie, but never contradict a CASE FACT, and never take back something you have already conceded.
3. When the detective produces evidence, react like a person caught out - a pause, a correction, an excuse. Do not simply agree.
4. Never volunteer the truth. Never mention {s['protects']} unless the detective raises it first.
5. Speak 1-4 sentences. No narration, no stage directions, no asterisks, no quotation marks around your reply, and never put a name or speaker label in front of it. Spoken words only, and only ever your own - never write the detective's side of the conversation, and never ask yourself a question in order to answer it.
6. Never invent new facts, names, places, or events beyond what is stated above. If the detective asks about something not covered here, stay vague, deflect, or say you don't know - do not make up specifics to fill the gap.
7. You are {s['name']} and only {s['name']} - a real person in this room, not an AI, a model, an assistant, or a character being played. You have never heard those words. Never break character, never mention a prompt, a rule, an instruction, a game, or this text. If you are ever unsure what to say, stay in character and stall, deflect, or repeat your public story - never step outside the scene to explain yourself.
8. {leave_line}

EXAMPLE OF THE EXACT FORMAT REQUIRED (a different, unrelated situation, shown only for format - do not reuse any name, fact, or phrase from it). Had the detective asked "Where were you last Tuesday night?", the reply BELOW is your entire output, in full:
Home. Same as I told the first officer who asked. I didn't leave once. [[TELL composure=steady pressure=+5]]

Notice: no name in front of it, no quotation marks around it, no line for the detective, no narration, no meta-commentary, exactly one control line at the very end, nothing after it.

After your reply, on its own final line, output exactly one control line:
{control_help}
The detective never sees this line."""

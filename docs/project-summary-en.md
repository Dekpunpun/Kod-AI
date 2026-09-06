# The Vesper Manifest — Project Summary

A first-semester capstone project. This summary covers the project end to end
across the seven sections requested, in plain English, checked against the
actual repository (`file:line` references are given so any claim here can be
verified directly in the code).

---

## Abstract

*The Vesper Manifest* is a single-player detective RPG built in Python with
pygame. The player investigates the theft of five military demolition charges
and the disappearance of a sergeant's wife, exploring an open city, collecting
seven pieces of physical evidence, and interrogating four suspects before
naming a culprit.

The project's central technical contribution is that **every suspect's
dialogue is generated live by a local large language model**, rather than
written in advance — the player can ask anything, in their own words, and get
a genuine, in-character reply, with no repeated playthrough producing an
identical conversation. At the same time, the mystery's **solvability is
guaranteed by deterministic code**, never by the language model's behavior: a
hidden "pressure floor" mechanism ensures that presenting the correct evidence
always produces enough proof to win, regardless of how well or poorly the
model responds. The guilty suspect is chosen at random at the start of each
game, so no two playthroughs share the same solution, yet the case remains
internally consistent and always fair.

The system is 11 modules and roughly 6,800 lines of Python, tested through a
custom headless self-test suite (no display or audio hardware required),
verified with continuous integration on both Windows and macOS, and
distributed as installable builds through GitHub Releases.

---

## Introduction

### The problem

Most detective and mystery games rely on fully scripted dialogue: every
question the player can ask, and every answer a character can give, is
written in advance. This has two consequences. First, the player's
investigation is bounded by what the writer anticipated — asking anything
outside the script produces a generic non-answer. Second, a second playthrough
is identical to the first; there is nothing left to discover once the fixed
dialogue tree has been exhausted.

### The objective

This project asks whether a **local language model** can replace scripted
dialogue for interrogation scenes specifically, while preserving the one
property a mystery game cannot give up: **the case must remain solvable**,
regardless of how the language model happens to respond on a given run. A
detective game that occasionally becomes unsolvable because the AI had an off
night is not an acceptable trade for more natural conversation.

### Scope

The game implements one complete case: four suspects, seven pieces of
evidence, three possible endings, and one city map to explore. Guilt is
randomized per playthrough among three of the four suspects, so the same
world supports multiple distinct solutions without additional content being
authored. Explicitly out of scope: save/load, multiple cases, and any online
or cloud-hosted model — the language model runs entirely on the player's own
machine.

---

## Background / Theoretical Framework

### Local language model serving

The game talks to a language model running locally through
[LM Studio](https://lmstudio.ai/), which exposes an OpenAI-compatible HTTP API
(`/v1/chat/completions`) on `localhost` (`rpg/llm.py:16-17`). No cloud API, no
API key, no per-call cost, and no conversation data ever leaves the player's
machine. This was chosen specifically so a mystery game's dialogue — which
must stay consistent with hidden facts the model is trusted with — never
depends on a third-party service being available or affordable to keep
running long-term.

### Why not an existing AI-NPC platform

Commercial and research platforms for AI-driven non-player characters (e.g.
Inworld- and Convai-class tooling, and NVIDIA ACE) optimize for **believable,
natural conversation**. None of them attempt to *guarantee* that a mystery
built around their output stays solvable — that guarantee has to be
engineered separately, in the surrounding game logic, and is this project's
actual contribution. See Related Work below for direct comparisons.

### The control-line protocol

To let the model both perform dialogue *and* report a small amount of
structured state back to the game in a single response, the game defines a
lightweight inline protocol: the model appends one hidden line to its reply,
of the form

```
[[TELL composure=steady|rattled|cracking pressure=+N asked=yes|no concepts=a,b,c]]
```

which the game parses out and strips before anything is shown to the player
(`rpg/llm.py:242` `parse_tell()`). This line is never trusted blindly — see
Methods, "the pressure floor," below.

### Related work

| Work | Type | Relationship to this project |
|---|---|---|
| Park et al., "Generative Agents: Interactive Simulacra of Human Behavior" (2023) | Academic | Established that LLM-driven agents can sustain believable, persistent behavior over long interactions — the general feasibility case this project builds an interrogation-specific application on top of. |
| Inworld AI / Convai (commercial NPC middleware) | Industry | Provide LLM-backed NPC dialogue as a hosted service, optimized for natural conversation and character consistency. Neither publishes a mechanism for guaranteeing a scripted objective (e.g. "the mystery is solvable") independent of the model's output — the gap this project's pressure floor fills. |
| *Ace Attorney* series, *Her Story*, *Return of the Obra Dinn* | Genre baseline | Deduction/interrogation games with entirely scripted, pre-written dialogue and evidence logic. The honest control group: consistent and always solvable by construction, but with a fixed, exhaustible dialogue tree and no replay variation. |

The axis this project sits on relative to all three: **dialogue is generated,
not authored, and the game runs entirely offline on local hardware, while
still guaranteeing — in code, not in the prompt — that the mystery cannot
become unsolvable.**

---

## Methods

### Architecture

The game is organized into 11 modules (`rpg/`, ~6,800 lines total): a main
game-state module, world/map handling, UI drawing, sound, the game clock, the
language-model client, procedurally generated art and audio, the case data
file, and entity definitions. All visual art and sound effects are generated
in code at startup rather than loaded from binary asset files — the only
external asset in the entire project is one font file.

### The interrogation loop

1. The player types a question, or selects a piece of evidence to present.
2. The request is sent to the local model **on a background thread**
   (`rpg/llm.py:4`), so the game keeps rendering and responding to input while
   waiting — a reply from a larger local model can take up to roughly two
   minutes.
3. The model's reply is parsed: the spoken portion is separated from the
   hidden control line (`parse_tell()`), and a set of text-safety passes
   trims run-on replies, collapses repeated sentences, and (added this
   session — see Results) removes any line where the model incorrectly wrote
   the detective's side of the conversation instead of its own.
4. The suspect's pressure, composure, and evidence-presented state are
   updated, and the **cleaned** reply — not the raw model output — is the
   version saved into that suspect's conversation history, so a one-off
   mistake is never re-shown to the model as an example of its own past
   behavior on a later turn.

### Per-suspect isolation and prompt construction

Each suspect keeps an entirely separate conversation record: their own
pressure score, evidence-presented list, turn count, and message history.
Nothing from one suspect's conversation is ever visible to another. Before
every single reply, the game builds a **brand-new system prompt from
scratch** (`rpg/llm.py:386` `system_prompt()`), assembled from: the suspect's
fixed identity and backstory (from the case file), a "stance" paragraph
recomputed live from that suspect's current pressure/evidence/state, the
current in-game time of night, and a fixed rulebook (stay in character, never
invent facts beyond what's given, keep replies short, never break the fourth
wall). Only the stance and time-of-night sections change between turns — the
character's core identity is constant, but how they are currently *acting* is
recalculated every time based on the live state of that specific
conversation. This is the mechanism behind suspects becoming visibly more
rattled or breaking under sustained pressure, without any dialogue being
hand-edited.

### The pressure floor — guaranteed solvability

The single most important design decision in the project: pressure is never
trusted to the model alone. After the model reports its own pressure change,
the game computes a floor equal to the sum of the pressure values of whatever
real evidence has actually been presented to that suspect, and takes whichever
is higher (`rpg/main.py:657`):

```python
floor = min(95.0, float(sum(EVIDENCE_BY_ID[e]["pressure"] for e in c["presented"])))
c["pressure"] = max(c["pressure"], floor)
```

Two specific pieces of evidence (25 + 30 pressure) sum to exactly 55, the
threshold required for the strongest ending — meaning presenting the correct
evidence guarantees a winnable case **even if the model's replies are
unhelpful in every single exchange.**

### Randomized guilt

At the start of every game, one suspect is chosen at random from a pool of
three as the true culprit (`rpg/case.py`, `pick_culprit()`); a fourth suspect
can never be guilty. Each suspect carries a `guiltVariant` data block that is
merged over their base data only if chosen, and the base data is restored
first on every call so no leftover state survives between games. Each
suspect's "break" mechanic (how they eventually crack under pressure) is a
property of the *character*, never of guilt, so an innocent suspect breaks
identically to a guilty one — the player cannot identify the culprit simply by
watching who cracks first.

### Guilt determination and grading

Verdict computation is pure code, run only when the player accuses someone,
with zero language-model involvement (`rpg/main.py:718` `resolve()`):

1. **Identity check** — a direct comparison against the hidden, stored
   culprit value. The wrong suspect ends the game immediately, regardless of
   evidence quality.
2. **Strength check** — if correct, whether enough of the right evidence was
   presented and the pressure threshold was met, producing a "strong" or
   "thin" correct ending.
3. **Efficiency grade (S/A/B/C)** — for the strongest outcome only, based on
   how many turns (questions/evidence-presentations) it took, tracked
   per-suspect and rolled back automatically if a turn errors or is cancelled.

### Testing strategy

Because model output is inherently non-deterministic, testing focuses on
everything **except** the model's exact wording:

- **Headless self-test** (`--selftest`) boots the entire game under dummy
  SDL video/audio drivers — no display or sound hardware required — and
  asserts on deterministic internals: the control-line parser, the culprit
  pool, that every suspect and prop resolves correctly, and that the map,
  fonts, and audio all initialize without error.
- **`FORCE_CULPRIT`** environment variable pins a specific suspect as guilty
  for reproducible manual testing of one branch at a time.
- **Property-style edge-case tables** for the control-line parser cover
  malformed input directly: case-mismatched field names, an unterminated
  block, and (added this session) a model writing both sides of a
  conversation or wrapping its reply in quotes.
- Rendering every screen headlessly and inspecting the output is also how the
  project's 20 report screenshots were produced, and is how three UI overflow
  bugs were originally found.

---

## Results

### What was built

A complete, playable case: 4 suspects, 7 pieces of evidence, 3 possible
endings, one explorable city map, running at 384×240 internal resolution
scaled to 1152×720 at 60 FPS. The project spans 40 commits and roughly 6,800
lines of Python across 11 modules.

### Delivery

- **Continuous integration** runs the headless self-test automatically on
  both `windows-latest` and `macos-latest` GitHub Actions runners on every
  push.
- **Installable builds** are published automatically to GitHub Releases for
  both platforms.
- **Documentation**: 7 architecture/sequence diagrams, 20 real in-game
  screenshots, a full presentation run-sheet with offline-fallback
  contingency planning, and a self-contained prompt document for regenerating
  the project's defense slide deck independently of any specific file access.

### Defects found and fixed

Beyond the three UI overflow bugs found via headless screenshot inspection
during documentation work, and prior review-driven fixes (a race condition
between a background connectivity check and an in-flight request; several
gaps in the culprit-randomization swap logic), this session's active testing
of the interrogation system surfaced and fixed one additional real defect
class:

- **Role confusion under pressure.** Weaker local models occasionally
  answered "as the detective" instead of the suspect — most commonly by
  copying the two-speaker shape of the system prompt's own formatting
  example. Traced to three compounding causes and fixed at each: the
  prompt's example no longer demonstrates a two-speaker exchange; a text
  filter strips any fabricated detective line or redundant speaker label
  before display; the model is now given `stop` sequences so the fabricated
  line is never generated at all; and — the defect with the widest impact —
  a raw, broken reply was previously being saved into that suspect's
  conversation history verbatim, meaning one bad reply taught the model to
  repeat the mistake on every subsequent turn instead of remaining a one-off.
  All four fixes are verified by the headless self-test's `parse_tell` edge
  cases and pushed to the repository.

### Numbers worth citing directly

| Fact | Value |
|---|---|
| Suspects / evidence items | 4 / 7 |
| Possible endings | 3 |
| Strong-ending requirement | 2 qualifying evidence items **and** pressure ≥ 55 |
| The two key exhibits | 25 + 30 pressure = exactly 55 |
| Fastest grade (S) | ≤ 10 turns |
| Modules / lines of code | 11 / ~6,800 |
| Commits | 40 |
| CI platforms | Windows + macOS |
| External binary assets | 1 (a single font file) — all art/audio generated in code |

---

## Discussion

### What the pressure-floor design actually proves

The project's central claim — that a language-model-driven mystery can remain
guaranteed-solvable — rests entirely on the pressure floor and the
code-only verdict logic, not on prompting the model well. This is a
deliberate and, in this project's view, necessary design stance: prompting
can *reduce* the frequency of bad model behavior, but cannot *eliminate* it,
so the game's fairness guarantee was built at the layer the model can never
override.

### The limits of prompting alone

The role-confusion defect found and fixed this session is direct evidence for
that stance. Multiple layers of prompt instruction already told the model
"never write the detective's lines" — and a weaker local model still did it
regularly, because it was pattern-matching a formatting example rather than
parsing an instruction. The fix that actually mattered most was not better
wording, but a **structural, code-level backstop** (stop sequences and output
filtering) that does not depend on the model understanding or obeying
anything. This generalizes: for any property this project truly needs to
hold, code enforcement was more reliable than prompt instruction alone.

### Model quality is a real, honest limitation

Character consistency, natural-sounding dialogue, and how quickly a reply
arrives all depend directly on the capability and size of whatever model the
player happens to be running locally. This is not fully solvable in code —
a better local model will always drift out of character less often and reply
faster than a smaller one, and the game can only mitigate the failure modes
it can detect, not eliminate the underlying variance. This is stated plainly
rather than minimized, since it is the most likely question to come up in a
defense.

### Why local-only, and what that costs

Running entirely on local hardware removes cost, internet dependency, and any
data-privacy concern — no conversation ever leaves the player's machine. The
cost is hardware: a capable chat model needs enough memory to run alongside
the game itself, which is why the development machine's spec (24 GB unified
memory) is directly relevant to whether this approach is currently practical
for an average player's computer, not just the developer's.

---

## Conclusions

This project demonstrates that a local, on-device language model can
generate genuinely dynamic, in-character interrogation dialogue for a
detective game, while the mystery's fairness and solvability are guaranteed
independently, in deterministic game logic that never depends on — and is
never undermined by — the model's behavior on a given run. The three-layer
separation this required — a fixed evidence and case-fact layer the model
cannot read into existence, a code-computed pressure floor beneath whatever
the model reports, and a verdict function with zero model involvement — is
the project's central technical contribution, and is what distinguishes it
from existing AI-NPC middleware, which optimizes for conversational realism
without attempting this guarantee.

Real defects were found through active testing of this specific claim,
including one — the interrogation system's role-confusion bug — found and
fixed during the writing of this very summary, which is itself a small piece
of evidence that the project's testing approach (exercising the actual live
system rather than only reasoning about it) works as intended.

### Limitations

No save/load; a single case; requires a machine capable of hosting a
moderately sized language model locally; dialogue quality and reply latency
both scale with the capability of whatever model the player has available.

### Future work

Additional cases reusing the same engine and pressure-floor mechanism;
save/load support; and exploring whether the same "code-guaranteed, model-
generated" separation generalizes to other genres where an LLM's unreliability
would otherwise be a blocking risk rather than a stylistic choice.

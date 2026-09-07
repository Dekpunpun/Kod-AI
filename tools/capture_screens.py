"""Render every screen of Kod AI to a PNG, headlessly.

Same technique as `rpg/main.py --selftest` (which already does
`pygame.image.save(g.screen, out)`) - boot a real `Game` under the dummy SDL
drivers, drive its actual `draw()`, and save the real screen surface. Nothing
in `rpg/` is imported for its side effects only; every seed below just sets
fields on this script's own `Game` instance, exactly like `selftest()` does.

Run:  python3 tools/capture_screens.py
Output: docs/screenshots/NN-name.png (20 files)
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Deterministic run, so every screenshot (and the case-file/ending pages
# built from it) is reproducible across runs rather than depending on
# pick_culprit()'s random roll.
os.environ["FORCE_CULPRIT"] = "doss"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RPG = os.path.join(REPO, "rpg")
OUT = os.path.join(REPO, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, RPG)

import pygame  # noqa: E402

import main as m  # noqa: E402
import case  # noqa: E402

g = m.Game()
n = 0


def snap(name):
    """Settle a couple of frames (so animated elements land on a readable
    pose, same warmup selftest() already does), draw, and save."""
    global n
    n += 1
    for _ in range(3):
        g.update(1 / 60)
    g.draw()
    path = os.path.join(OUT, f"{n:02d}-{name}.png")
    pygame.image.save(g.screen, path)
    print("wrote", path)


# --- 01: title screen -------------------------------------------------------
g.state = m.TITLE_SCREEN
snap("title")

# --- 02: world, interact prompt, minimap ------------------------------------
g.state = m.PLAYING
spot = g.world.npc_spots["bricker"]  # standing outdoors, easy to read
g.player.x, g.player.y = spot["x"], spot["y"] + 26
g._reveal_minimap()
snap("world-interact-prompt")

# --- 03: dialogue box, read mode --------------------------------------------
g.state = m.TALKING
g.active_suspect = "doss"
g.talk_mode = "read"
g.say_suspect("doss", case.SUSPECTS_BY_ID["doss"]["opener"])
g.box.shown = 9999  # skip the type-on animation for a clean capture
snap("dialogue-read")

# --- 04: question input mode -------------------------------------------------
g.talk_mode = "input"
g.typed = "What does the pattern in that ledger actually mean?"
snap("dialogue-input")

# --- 05: evidence picker -----------------------------------------------------
g.found = ["vault-ledger", "gate-camera", "matchbook"]
g.talk_mode = "evidence"
g.ev_index = 0
snap("dialogue-evidence-picker")

# --- 06: waiting on the model ------------------------------------------------
g.talk_mode = "read"
g.ai.busy = True
g.waiting_since = pygame.time.get_ticks() - 6000
snap("dialogue-waiting")
g.ai.busy = False

# --- 07: accuse list ---------------------------------------------------------
g.open_accuse(m.PLAYING)
snap("accuse-list")

# --- 08: accuse confirm -------------------------------------------------------
g.accuse_confirm = "doss"
snap("accuse-confirm")
g.accuse_confirm = None
g.state = m.PLAYING

# --- 09: pause menu -----------------------------------------------------------
g.open_pause()
snap("pause-menu")

# --- 10: controls page ---------------------------------------------------------
g.pause_showing_controls = True
snap("pause-controls")
g.pause_showing_controls = False
g.state = m.PLAYING

# --- case file: seed transcripts + a statement page, then walk every page ----
c = g.convo["doss"]
c["log"] = [
    ("you", "Walk me through the ledger."),
    ("doss", "I signed off same as always. Every checkout, every night."),
    ("you", "What does the override code pattern actually mean?"),
    ("doss", "It means... someone used the Colonel's old code. All five times."),
]
c["broken"] = True  # unlocks a "statement" page for an evidence_plus_question suspect

g.state = m.CASEFILE
labels = ["briefing", "scene", "timeline", "facts", "victim-suspects"]
for i, label in enumerate(labels):
    g.casefile_page = i
    snap(f"casefile-{label}")

exhibit_index = g.CASEFILE_INTRO_PAGES  # first found exhibit
g.casefile_page = exhibit_index
snap("casefile-exhibit")

transcript_index = g.CASEFILE_INTRO_PAGES + len(g.found)
g.casefile_page = transcript_index
snap("casefile-transcript")

statement_index = transcript_index + len(g._transcript_pages())
g.casefile_page = statement_index
snap("casefile-statement")

# --- endings: build a strong case against the (forced) culprit --------------
c["presented"] = ["vault-ledger", "gate-camera"]
c["pressure"] = 60.0
c["turns"] = 2
g.resolve("doss")
g.ending_page = 0
snap("ending-disposition")
g.ending_page = 1
snap("ending-solution")

print(f"\n{n} screenshots written to {OUT}")

# Kod AI

A pixel-art detective RPG. Five military demolition charges are missing from
Fort Callow, a sergeant's wife has vanished, and you have one night in
Harrow's Reach to work out which of four soldiers is lying — by walking the
city, finding evidence, and interrogating each suspect in free text against a
local LLM.

Everything is drawn in code — no image or audio assets. The world, sprites,
weather, lighting and the amber police-terminal UI are all procedural pixel
art; sound is synthesised square waves.

## Running it

The game needs an OpenAI-compatible chat model reachable over HTTP. It
defaults to LM Studio on `localhost:1234`.

1. Start your local server and load a chat model.
2. Then:

```bash
python3 -m pip install -r requirements.txt
python3 rpg/main.py
```

To point at a different backend:

```bash
LLM_URL=http://localhost:8000 python3 rpg/main.py
```

The model is auto-detected from `/v1/models` (embedding models are skipped).
If the model isn't reachable, the game still runs — you can walk the city and
collect evidence — but talking to a suspect will say so rather than hang.

## How it plays

Walk Harrow's Reach and Fort Callow with WASD/arrows (hold Shift to run).
Press **E** near a person or object to look or talk, **Tab** for the case
file, **Esc** to back out of a conversation.

**Case File** holds what's established and can never be contradicted.
Talking to a suspect is free-text chat: **Enter** asks a question, **Tab**
opens what evidence you're carrying to present. Evidence that contradicts a
suspect's story forces a retreat — a correction, a new partial lie — and
raises their **Pressure**. Each suspect has their own breaking condition:
some need a pile of contradicting evidence, some need one specific item *and*
the right question asked directly, one needs nothing but to understand what's
actually at stake.

**A** opens Accuse. A correct verdict only holds up if you back it with real
evidence and pressure — naming the right suspect on a thin case still closes
it, just worse. The ending screen grades a strong conviction from **S** down
to **C** on how few questions it took.

## Building a standalone app

```bash
./build.sh          # macOS / Linux
build.bat            # Windows
```

Produces `dist/Kod AI.app` (macOS) or `dist/KodAI/`
(Windows/Linux) via PyInstaller, and runs `--selftest` against the built
binary to confirm the font, world, and NPCs actually loaded. Windows and
macOS builds are also produced automatically by
[`.github/workflows/build.yml`](.github/workflows/build.yml) on every push —
useful if you don't own a Windows machine.

## Swapping in a new case

Everything scenario-specific lives in [`rpg/case.py`](rpg/case.py) — victim,
scene, timeline, established facts, every suspect's personality/alibi/hidden
truth/breaking condition, the evidence list, and what a conviction requires.
Rewrite that one file and the rest of the game adapts; `world.py` reads
`CASE["suspects"]` to place NPCs and `art.py` reads suspect `sprite` keys to
draw them.

## How the AI works

Each turn, [`rpg/llm.py`](rpg/llm.py)'s `system_prompt()` builds a fresh
system prompt from the suspect's personality, public story, hidden truth, the
established case facts, and a stance line derived from that suspect's
specific breaking condition and how close the conversation has gotten to it.
The model only ever speaks as the character.

The character also appends a hidden control line, e.g.:

```
[[TELL composure=rattled pressure=+12]]
```

This is stripped before display and drives the composure meter and portrait.
Presented evidence sets a floor on pressure gain, so a stubborn model can't
stall the case.

Local reasoning models can spend their whole token budget deliberating and
return nothing visible; the prompt forbids that outright, and a turn that
still comes back empty gets one retry with a blunter instruction and a lower
temperature. A turn on a local 12B model can take 30s–2min — the "THINKING"
indicator counts elapsed seconds so a slow turn never looks hung, and a
failed turn is rolled back (the question, and any evidence you presented,
return so you can retry).

## Files

| File | Purpose |
|---|---|
| `rpg/main.py` | Game loop, states, input, rendering, HUD |
| `rpg/case.py` | The case — swap this to make a new one |
| `rpg/world.py` | Map layout, zones, collision, NPC placement |
| `rpg/art.py` | All pixel art: sprites, portraits, props, tiles, weather |
| `rpg/ui.py` | Panels, text, the police-terminal look |
| `rpg/llm.py` | LLM client and system prompt builder |
| `rpg/sfx.py` | Synthesised square-wave sound effects |
| `rpg/entities.py` | Player/NPC entity classes |
| `rpg/settings.py` | Screen size, palette, asset path helper |
| `KodAI.spec`, `build.sh`, `build.bat` | PyInstaller packaging |

## Design references

[`docs/art-theme-brief.md`](docs/art-theme-brief.md) covers the visual
mood and per-character/per-location intent;
[`docs/map-asset-inventory.md`](docs/map-asset-inventory.md) is a generated
inventory of every building, sprite, evidence item and prop currently in the
game.

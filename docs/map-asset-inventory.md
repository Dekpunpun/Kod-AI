# Kod AI — Map Asset Inventory

Pulled directly from the game's code (`rpg/art.py`, `rpg/world.py`,
`rpg/case.py`), not reconstructed from memory — this is the exact current
state of the map.

## Buildings (7)

| Zone | Card (title / subtitle) | Roof/wall style | Rooms |
|---|---|---|---|
| `vault` | FORT CALLOW / SPECIAL WEAPONS VAULT | military | 1 |
| `command` | FORT CALLOW / COMMAND OFFICE | military | 1 |
| `motorpool` | FORT CALLOW / MOTOR POOL | military | 1 |
| `precinct` | THIRD PRECINCT / HOME BASE | civic | 1 |
| `milner` | 14 MILNER STREET / THE THORNE HOUSE | house | 2 (kitchen + garage) |
| `saltrow` | SALT ROW, DOCK 4 / THE FISHING CABIN | cabin | 1 |
| `lab` | HARROW'S REACH P.D. / FORENSICS | lab | 1 |

Each style (`military` / `civic` / `house` / `cabin` / `lab`) has its own roof
shingle colors, wall siding course (block / brick / board), door type, and
window type — see "Exterior kit" below.

## Characters

| Sprite key | Who | Build |
|---|---|---|
| (player) | The detective | Long coat, fedora — the only unique body |
| `thorne` | Staff Sgt. Elias Thorne | Broad, patrol cap, sergeant's chevrons |
| `doss` | Cpl. Wyatt Doss | Lean, garrison cap, wrench on belt |
| `ashworth` | Col. Margaret Ashworth | Upright, peaked officer's cap, gold shoulder star |
| `bricker` | L. Cpl. Sam Bricker | Hunched, beanie, grease smudge |

Each NPC has a calm pose and a broken/cracking pose, plus a 48×48 portrait bust
with 3 expressions (steady / rattled / cracking).

## Evidence (7 total — 6 found in the world, 1 unlocked by dialogue)

| id | Name | Where found |
|---|---|---|
| `vault-ledger` | Vault Checkout Ledger | Vault checkout terminal |
| `gate-camera` | Motor Pool Gate Camera Footage | Gate camera terminal (motor pool) |
| `matchbook` | Cinder Compact Matchbook | Dropped in the gravel, Harborview Square |
| `struggle-kitchen` | Signs of a Struggle | The kitchen, 14 Milner Street |
| `burner-phone` | The Burner Phone | Behind the paint shelf, garage |
| `proof-of-life-photo` | Proof-of-Life Photo | Face down, garage |
| `bricker-account` | Bricker's Account | Unlocked by conversation, not placed in world |

## Other lookables placed in the world (no evidence attached)

- The arms rack (vault)
- The forensics bench (lab)
- A 2.5-ton in the end bay (motor pool truck)
- Wall map of Harrow's Reach (command office)
- The case board (precinct corkboard)

## Exterior kit (per building style)

- `door_military`, `door_civic`, `door_house`, `door_cabin`, `door_lab` —
  panelled timber (house/cabin/civic) or steel with a wired vision panel
  (military/lab)
- `window_military`, `window_civic`, `window_house`, `window_cabin`,
  `window_lab` — lit window facades
- `chimney` — house and cabin roofs
- `roof_vent` — military roofs
- `roof_sign` — civic (precinct) roof

## Furniture & props (full list, `art.objects()`)

**General furniture:** `desk`, `table`, `chair`, `chair_up`, `shelf`,
`cabinet`, `bench`, `cooler`, `sink`, `bunk`, `stove`

**Armory / military:** `steel_shelf`, `gun_locker`, `ammo_crate`, `sandbags`,
`munitions_crate`, `weapon_rack`, `vault_terminal`, `camera_console`

**Forensics lab:** `lab_bench`, `microscope`, `specimen_cabinet`, `fume_hood`

**Motor pool:** `truck`, `oil_drum`, `workbench`

**Precinct:** `corkboard`, `banner`

**Command office:** `wallmap`

**Evidence props:** `burner_phone`, `photo_facedown`, `matchbook`,
`kitchen_mess`

**Street furniture:** `pole` (utility pole, wires drawn separately), `bin`,
`drain`, `hydrant`, `bollard`, `lamp`, `sconce`

**Grounds / decoration:** `tree`, `bush`, `flowers`, `plant`, `fountain`,
`stanchion`, `crate`, `pallet`, `debris`

**Museum-leftover decorative set** (still in the registry, not currently
placed on this map): `plinth`, `plinth_empty`, `painting`, `painting_wide`,
`painting_empty`, `corot`, `easel`, `case`, `rack`, `mirror`, `dumpster`,
`outline`, `marker1`–`marker5`

**Doors (generic):** `door`, `door_open` (older/unstyled — superseded by the
per-building `door_*` set above for building entrances)

## Ground tiles (`art.build_tiles()`)

| Tile | Variants | Used for |
|---|---|---|
| `grass` | 4 | Open grounds |
| `path` | 4 | Streets, Harborview Square |
| `marble` / `marble_d` | 3 / 3 | `marble_d` is the garage floor at 14 Milner Street; plain `marble` is unused on this map |
| `wood` | 4 | Precinct, house, cabin floors |
| `carpet` | 3 | Command office |
| `concrete` | 4 | Vault, motor pool floors |
| `labfloor` | 3 | Forensics lab floor |
| `wall` / `wall_top` / `wainscot` | 3 / 3 / 3 | Interior walls |
| `hedge` | 3 | Grounds boundary |
| `water` | 3 | Fountain |
| `void` | 1 | Unused/off-map |

## Weather & atmosphere assets

- `dust_sprite` — motes drifting through lamp light
- `fog_blob` — soft drifting fog bank
- Rain drawn as procedural streaks (no sprite, generated per-frame)
- Chimney smoke — procedural puffs above house/cabin roofs when unroofed
- Overhead wires — drawn as sagging lines between `pole` props

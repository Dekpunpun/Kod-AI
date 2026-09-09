# Diagrams and Data Dictionary — Kod AI

Every diagram below is drawn from the actual source in `rpg/`, not from the
original design intent — file:line references are given so any diagram can be
checked against the code it describes. Each has a Mermaid version (renders on
GitHub and in most Markdown viewers) and a plain-ASCII twin (for the `.txt`
report and anywhere Mermaid isn't available).

## Symbol legend

Used consistently across every diagram below:

| Symbol | Meaning |
|---|---|
| Rectangle | A process / function / module |
| Diamond | A decision point |
| Rounded rectangle | A start/end state |
| Cylinder | A data store (in this project: always an in-memory dict, never a database) |
| Solid arrow `→` | Synchronous call / direct data flow, same thread |
| Dashed arrow `-->` | Asynchronous / cross-thread communication |

---

## 1. System architecture

```mermaid
graph TD
    subgraph "rpg/ (single process)"
        MAIN["main.py<br/>Game (controller + state machine)"]
        UI["ui.py<br/>DialogBox, Toast, panels"]
        ENT["entities.py<br/>Player, NPC"]
        WORLD["world.py<br/>World, Building, floors"]
        ART["art.py<br/>procedural sprites/tiles"]
        SFX["sfx.py<br/>procedural audio"]
        CLOCK["clock.py<br/>Clock, night phases"]
        CASE["case.py<br/>CASE / SUSPECTS_BY_ID / EVIDENCE_BY_ID<br/>pick_culprit()"]
        LLM["llm.py<br/>Client, prompt builder"]
        SET["settings.py<br/>constants"]
    end
    EXT[("LLM server<br/>hosted gateway over a tunnel,<br/>or LM Studio on localhost:1234")]

    MAIN --> UI
    MAIN --> ENT
    MAIN --> WORLD
    MAIN --> CASE
    MAIN --> LLM
    MAIN --> CLOCK
    WORLD --> ART
    WORLD --> CASE
    ENT --> ART
    MAIN --> SFX
    LLM --> CASE
    MAIN -.HTTP.-> EXT
    LLM -.HTTP.-> EXT
```

```
ASCII:

  +-------------------------------------------------------------+
  |                     rpg/ (single process)                   |
  |                                                               |
  |   main.py (Game: controller + state machine)                 |
  |     |     |      |        |         |         |              |
  |     v     v      v        v         v         v              |
  |    ui.py entities world.py case.py  llm.py   clock.py         |
  |          .py       |         ^        |                       |
  |                     v         |        |                      |
  |                   art.py -----+        |                      |
  |                                        |                      |
  +----------------------------------------|----------------------+
                                            | HTTPS (urllib, threaded)
                                            v
                          +----------------------------------+
                          |  serve_llm.py gateway             |
                          |  (5 slots, token, caps)           |
                          |  reached over a Cloudflare tunnel |
                          +----------------------------------+
                                            |
                                            v
                          +----------------------------------+
                          |  LM Studio, localhost:1234        |
                          +----------------------------------+

  The address is not compiled in: llm.py reads server.json from the repo, so
  the server can move without players reinstalling. LLM_URL overrides it, and
  localhost:1234 is the fallback when the directory cannot be reached.
```

Reference: imports at `main.py:9-25`; `llm.py:15,17` for the external
dependency.

---

## 2. State machine

```mermaid
stateDiagram-v2
    [*] --> TITLE_SCREEN
    TITLE_SCREEN --> PLAYING: Enter
    PLAYING --> TALKING: E on a suspect (begin_interview)
    PLAYING --> CASEFILE: TAB
    PLAYING --> PAUSED: Esc
    TALKING --> PLAYING: Esc
    TALKING --> ACCUSE: A
    CASEFILE --> PLAYING: TAB / Esc
    CASEFILE --> ACCUSE: A
    ACCUSE --> PLAYING: Esc (from world)
    ACCUSE --> TALKING: Esc (from a conversation)
    ACCUSE --> CASEFILE: Esc (from case file)
    ACCUSE --> ENDING: Y (confirm accusation)
    PAUSED --> PLAYING: Resume
    ENDING --> TITLE_SCREEN: Enter (reset_run + re-roll culprit)
```

```
ASCII:

   [TITLE_SCREEN] --Enter--> [PLAYING] <--Esc-- [PAUSED]
                                 |  ^              ^
                          E on   |  | Esc          | Esc
                        a suspect| TAB/Esc          |
                                 v  |               |
                            [TALKING]           [CASEFILE]
                                 |                   |
                              A |                 A  |
                                 v                   v
                              [ACCUSE] <---Esc-------+
                                 |
                              Y (confirm)
                                 v
                             [ENDING] --Enter--> [TITLE_SCREEN]
                                              (reset_run: re-rolls culprit)
```

`ACCUSE`'s return state is tracked in `self.accuse_return` (`main.py:193,
835-839`) so Esc goes back to whichever screen opened it. Reference:
`main.py:27` for the 7 states, `on_key()` (`main.py:757-833`) for every
transition.

---

## 3. Main loop

```mermaid
flowchart TD
    Start([Frame start, 60 FPS cap]) --> Input[Poll pygame events<br/>KEYDOWN -> on_key<br/>TEXTINPUT -> on_text]
    Input --> Update[Game.update dt]
    Update --> Poll{ai.poll returned<br/>a result?}
    Poll -->|yes| Receive[receive kind, payload]
    Poll -->|no| Weather
    Receive --> Weather[Update weather<br/>if state visible]
    Weather --> TickDecide{state in PLAYING/PAUSED/<br/>CASEFILE/ACCUSE, or<br/>TALKING and not ai.busy?}
    TickDecide -->|yes| Tick[clock.tick dt<br/>night advances]
    TickDecide -->|no, request in flight| Skip[clock frozen this frame]
    Tick --> Departures
    Skip --> Departures[if PLAYING: check suspect departures]
    Departures --> Draw[Game.draw]
    Draw --> Flip([pygame.display.flip])
    Flip --> Start
```

```
ASCII:

  +----------------------------------------------------------+
  |  loop (60 FPS):                                           |
  |    read input (keyboard)                                  |
  |    update(dt):                                             |
  |      poll AI worker thread for a finished reply            |
  |      update weather (cosmetic)                             |
  |      IF state in {PLAYING, PAUSED, CASEFILE, ACCUSE}        |
  |         OR (TALKING and no request in flight):              |
  |          tick the night clock forward                       |
  |      ELSE: clock frozen (a reply is in flight)               |
  |      if PLAYING: check suspect departure schedules           |
  |    draw()                                                    |
  |    flip to screen                                            |
  +----------------------------------------------------------+
```

Reference: `main.py:979-1039` (`update`), `main.py:1741-1752` (`_run`). The
clock-tick condition at `main.py:1012` is the game's core pacing rule — it is
what stops a slow model reply from silently spending the player's night for
them (see `docs/diagrams.md` §4 below for why a reply can take so long).

---

## 4. LLM request pipeline

```mermaid
sequenceDiagram
    participant Player
    participant Game as Game (main thread)
    participant Client as llm.Client
    participant Worker as worker thread
    participant Queue as queue.Queue
    participant Server as Local LLM server

    Player->>Game: types a question / presents evidence
    Game->>Game: send() - advance clock, build system_prompt()
    Game->>Client: ask(messages)
    Client->>Client: generation += 1 (tags this turn)
    Client-->>Worker: start _ask(messages, gen)
    Note over Game: main thread returns immediately,<br/>game keeps rendering
    Worker->>Server: POST /chat/completions
    alt model replies but ran out of tokens mid-thought
        Server-->>Worker: empty content, finish_reason=length
        Worker->>Server: retry once with "STOP DELIBERATING" nudge
    end
    Server-->>Worker: reply text
    Worker->>Worker: strip <think> block, put (gen, "ok", text) on Queue
    loop every frame
        Game->>Client: poll()
        Client->>Queue: get_nowait()
        alt gen matches current generation
            Queue-->>Game: (kind, payload)
        else stale (cancelled/superseded)
            Queue-->>Client: discarded silently
        end
    end
    Game->>Game: receive() - parse_tell(), update pressure/composure
    Game->>Player: suspect's line shown in DialogBox
```

```
ASCII:

  Player types Q          Game (main thread)         Worker thread        LLM server
       |                        |                          |                  |
       |--question------------>|                          |                  |
       |                        |--send(): build prompt--->|                  |
       |                        |--ask(): gen+=1, spawn---->|                  |
       |                        |  (returns immediately,    |--POST----------->|
       |                        |   game keeps rendering)   |                  |
       |                        |                           |<--reply----------|
       |                        |                           | (retry once if   |
       |                        |                           |  empty+length)   |
       |                        |                           |--strip <think>-->|
       |                        |                           |--queue.put(gen,--+
       |                        |                           |   "ok", text)    |
       |                        |<--poll() each frame-------|                  |
       |                        |  (drops stale generation) |                  |
       |                        |--receive(): parse_tell,   |                  |
       |                        |  update pressure/mood     |                  |
       |<--dialogue box updates-|                            |                  |
```

Reference: `main.py:564-583` (`send`), `llm.py:130-135` (`ask`), `llm.py:176-
212` (`_ask`), `llm.py:214-225` (`poll`), `main.py:620-716` (`receive`). The
generation-tag discard (`llm.py:224`) is what makes `cancel()` (`main.py:938`)
safe even though the worker thread itself cannot actually be killed.

---

## 5. Culprit randomization

```mermaid
flowchart TD
    Start([reset_run called<br/>new game or ENTER NEW CASE]) --> PickCulprit[pick_culprit]
    PickCulprit --> Restore[Restore ALL of Thorne/Doss/Ashworth<br/>to their innocent base fields<br/>+ gate-camera evidence text<br/>+ CASE.solution + ending prose]
    Restore --> ForceCheck{FORCE_CULPRIT<br/>env var set?}
    ForceCheck -->|yes, valid pool id| UseForced[culprit = forced value]
    ForceCheck -->|yes, invalid| Raise([raise ValueError])
    ForceCheck -->|no| Random[culprit = random.choice pool]
    UseForced --> Merge
    Random --> Merge[Merge that suspect's guiltVariant over:<br/>hiddenTruth, motive, protects, concession,<br/>gate-camera text, endings, solution]
    Merge --> SetKey[CASE.conviction.culprit = culprit]
    SetKey --> Done([resolve and system_prompt<br/>now read the new culprit generically])
```

```
ASCII:

  reset_run() (new game, or "ENTER NEW CASE" from ending screen)
       |
       v
  pick_culprit():
    1. restore Thorne, Doss, AND Ashworth to their innocent text
       (so last run's guilty text can never leak forward)
    2. FORCE_CULPRIT env var set and valid?  -> use it
       FORCE_CULPRIT set but invalid?        -> raise (fail loud, not silent)
       otherwise                             -> random.choice(pool)
    3. merge the picked suspect's guiltVariant over the shared data:
         hiddenTruth, motive, protects, concession,
         gate-camera evidence text, both ending proses, the solution
    4. CASE["conviction"]["culprit"] = <picked id>
       -> resolve() and system_prompt() both read this key generically,
          with zero changes needed elsewhere in the codebase
```

Reference: `case.py:672-704`. Bricker is excluded from the pool
(`case.py:584`) because his own `publicAlibi` states as fact that he has no
vault access.

---

## 6. Resolution decision tree

```mermaid
flowchart TD
    Accuse([Player accuses a suspect]) --> Match{accused == the<br/>actual culprit?}
    Match -->|no| Wrong[[wrong_suspect ending<br/>caption: THE WRONG NAME]]
    Match -->|yes| Strong{"hit >= 2 of the 5-item<br/>strong pool AND<br/>pressure >= 55?"}
    Strong -->|no| Thin[[correct_thin ending<br/>caption: RIGHT NAME, THIN CASE]]
    Strong -->|yes| Grade{turns spent with<br/>the culprit}
    Grade -->|"<= 10"| S([Grade S - SURGICAL])
    Grade -->|"11-16"| A([Grade A - SOLID POLICE WORK])
    Grade -->|"17-24"| B([Grade B - GOT THERE IN THE END])
    Grade -->|"> 24"| C([Grade C - A LONG NIGHT])
```

```
ASCII:

  Player accuses suspect X
       |
       v
  Is X the actual culprit? ----no----> "wrong_suspect" ending
       | yes
       v
  >=2 of {vault-ledger, gate-camera, burner-phone,        ----no----> "correct_thin" ending
  proof-of-life-photo, bricker-account} shown to X
  AND pressure(X) >= 55 ?
       | yes
       v
  turns spent with X:
     <= 10   -> Grade S  "SURGICAL"
     11-16   -> Grade A  "SOLID POLICE WORK"
     17-24   -> Grade B  "GOT THERE IN THE END"
     > 24    -> Grade C  "A LONG NIGHT"
```

Reference: `main.py:718-753` (`resolve`). This function reads
`CASE["conviction"]["culprit"]` generically and needed **no changes** to
support culprit randomization.

---

## 7. Data model

```mermaid
erDiagram
    CASE ||--o{ SUSPECT : "has 4"
    CASE ||--o{ EVIDENCE : "has 7"
    CASE ||--|| CONVICTION : "has 1"
    CASE ||--o{ ENDING : "has 3 shapes"
    SUSPECT ||--o| GUILT_VARIANT : "3 of 4 have"
    SUSPECT ||--o| BREAK : "exactly 1"
    SUSPECT ||--o| SCHEDULE : "3 of 4 have"
    CONVICTION ||--o{ SUSPECT : "culprit_pool references 3"
    GAME ||--o{ RUNTIME_STATE : "one per suspect, in memory only"
    RUNTIME_STATE }o--o{ EVIDENCE : "presented references"

    CASE {
        string id
        dict meta
        dict victim
        string scene
        list timeline
        list facts
        string solution
    }
    SUSPECT {
        string id
        string name
        string personality
        string publicAlibi
        string hiddenTruth "swapped by pick_culprit()"
        string motive "swapped"
        string protects "swapped"
        string concession "swapped"
        string opener "never swapped"
    }
    EVIDENCE {
        string id
        string name
        string summary
        string detail
        string contradicts
        int pressure
        string requires "optional prerequisite id"
    }
    RUNTIME_STATE {
        float pressure
        string composure
        int turns
        list presented
        list history
        list log
        set concepts
        bool asked_directly
        set warned
        bool departed
        bool broken
    }
```

```
ASCII:

  CASE (module-level dict, rpg/case.py)
    |-- meta, victim, scene, timeline, facts, solution
    |-- suspects[4]  --------------------> SUSPECT
    |                                        |-- break (1 of 3 mechanic types)
    |                                        |-- schedule (3 of 4 suspects)
    |                                        |-- guiltVariant (3 of 4 suspects)
    |-- evidence[7]  --------------------> EVIDENCE
    |-- conviction { culprit_pool, culprit (runtime), strong{...} }
    |-- endings { correct_strong, correct_thin, wrong_suspect }

  Game.convo[suspect_id]  (RUNTIME STATE - in memory only, never saved)
    pressure, composure, turns, presented[], history[], log[],
    concepts{}, asked_directly, warned{}, departed, last_typed, broken
```

Reference: `case.py:13-643` (`CASE` literal), `main.py:166-182`
(`Game.convo` construction in `reset_run`).

---

## Data Dictionary

### CASE (top level) — `rpg/case.py:13`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | str | yes | Case identifier, `"kod-ai"` |
| `title` | str | yes | Display title |
| `meta` | dict | yes | `title_lines`, `subtitle`, `opening` text, `spawn` tile coords |
| `victim` | dict | yes | `name`, `detail` |
| `scene` | str | yes | The crime-scene description shown in the case file |
| `timeline` | list[tuple(str,str)] | yes | (`when`, `what`) pairs |
| `facts` | list[str] | yes | Facts no suspect may contradict; injected into every system prompt |
| `suspects` | list[dict] | yes | 4 suspect records (see below) |
| `evidence` | list[dict] | yes | 7 evidence records (see below) |
| `conviction` | dict | yes | `culprit_pool`, `culprit` (runtime-only key), `strong` (pool/requires_count/minPressure) |
| `endings` | dict | yes | `correct_strong`, `correct_thin`, `wrong_suspect`, each with `caption`/`prose` |
| `solution` | str | yes | Full reveal text; overwritten per-culprit by `pick_culprit()` |

### Suspect record — one entry of `CASE["suspects"]`

| Field | Type | Required | Swapped by `pick_culprit()`? |
|---|---|---|---|
| `id`, `name`, `sprite`, `role` | str | yes | no |
| `personality`, `publicAlibi`, `opener` | str | yes | no |
| `hiddenTruth`, `motive`, `protects`, `concession` | str | yes | **yes** — base (innocent) value, or the picked culprit's `guiltVariant` value |
| `break` | dict | yes | no — mechanic never changes with guilt |
| `break.type` | str enum | yes | `threshold_any` \| `evidence_plus_question` \| `conversational_trigger` |
| `schedule` | dict | 3 of 4 | `leaves_at` (minute), `warnings` (list of (minute, text)), `vacated` (text) |
| `guiltVariant` | dict | 3 of 4 (not Bricker) | The alternate hiddenTruth/motive/protects/concession/gate_camera_text/endings/reveal_text/solution used only if this suspect is picked guilty |

### Evidence record — one entry of `CASE["evidence"]`

| Field | Type | Required | Description |
|---|---|---|---|
| `id`, `name` | str | yes | Identifier and display name |
| `summary` | str | yes | Short line sent to the model when presented (`main.py:600`) |
| `detail` | str | yes | Long text shown in the case file |
| `contradicts` | str | yes | What this exhibit disproves |
| `found_text` | str | yes | Text shown on pickup |
| `pressure` | int | yes | Weight toward the deterministic pressure floor |
| `requires` | str | optional | Prerequisite evidence id (e.g. `gate-camera` requires `vault-ledger`) |
| `locked_text` | str | only if `requires` set | Shown if examined before the prerequisite is found |
| `sourced` | str | optional | `"dialogue"` for the one evidence item unlocked by conversation, not the world |

### Runtime state — `Game.convo[suspect_id]`, in memory only

| Field | Type | Description |
|---|---|---|
| `pressure` | float 0-100 | Drives composure and the strong-ending threshold |
| `composure` | str enum | `steady` \| `rattled` \| `cracking` |
| `turns` | int | Count of questions/presents; grades S/A/B/C |
| `presented` | list[str] | Evidence ids shown to this suspect |
| `history` | list[dict] | Full chat messages; only the last 16 are re-sent to the model |
| `log` | list[tuple] | Full transcript for the case-file view |
| `concepts` | set[str] | Bricker only — which of 3 ideas have landed |
| `asked_directly` | bool | Doss/Ashworth only — was the exact right question asked |
| `warned` | set | Schedule-warning thresholds already delivered |
| `departed` | bool | Left the map per schedule |
| `last_typed` | str | Last real player-typed text (never a synthesized evidence string) |
| `broken` | bool | Doss/Ashworth only — statement page unlocked |

This entire structure is rebuilt from scratch by `reset_run()` (`main.py:166`)
and is never written to disk — see the project summary's Chapter 3 note on
save/load.

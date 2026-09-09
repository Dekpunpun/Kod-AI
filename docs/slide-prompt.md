# Slide-rebuild prompt — Kod AI

A self-contained prompt for regenerating the project-defence deck with an AI
slide generator. Nothing here requires the AI to see the repository: every
number, name, and citation it needs is written into the prompt itself.

**Which block to use:**

| Tool | Use | Why |
|---|---|---|
| **Gamma** (`Paste in text`) | Block B | Accepts long input; best results of the three |
| **Tome** | Block B | Accepts long input |
| **Canva Magic Design** | Block A, then edit | Its prompt box caps at roughly 500 characters |
| ChatGPT / Claude | Block B | Ask for a slide-by-slide outline, then build it yourself |

Adjust the deck by editing the `CONFIG` lines at the top of Block B — nothing
else needs to change.

---

## Block A — short brief (Canva Magic Design)

```text
สร้างสไลด์นำเสนอโครงงานนักศึกษา 10 หน้า ภาษาไทย หัวข้อ "Kod AI —
เกมสืบสวนที่ผู้ต้องสงสัยตอบคำถามด้วย AI ที่รันบนเครื่องผู้เล่นเอง" ธีมมืดแนว
film noir สีหลักน้ำเงินเข้ม เน้นสีเหลืองอำพัน ฟอนต์ Sarabun โครงสไลด์: ปก /
บทคัดย่อ / ที่มาและวัตถุประสงค์ / เทคโนโลยีและทฤษฎี / งานวิจัยที่เกี่ยวข้อง /
สถาปัตยกรรมระบบ / กลไกรับประกันว่าคดีแก้ได้ / ผลการดำเนินงาน / อภิปรายผล /
สรุปผล แต่ละหน้าไม่เกิน 5 บรรทัด เว้นที่ว่างสำหรับใส่ภาพหน้าจอเกม
```

---

## Block B — full prompt (Gamma / Tome / a chat model)

Copy everything inside the fence.

````text
=== CONFIG — change these three lines, leave the rest alone ===
SLIDE_COUNT: 10
THEME: dark film-noir — deep navy-black background, amber accent, muted teal secondary
TONE: academic but plain-spoken; a third-year lecturer should follow it without the code
=== END CONFIG ===

You are designing a university capstone project-defence deck.

OUTPUT LANGUAGE: **Thai**, with technical terms left in English where a Thai
audience would normally keep them (LLM, prompt, pressure floor, thread, headless,
CI/CD, FPS). Do not translate those into Thai. All narrative text is Thai.

FONT: Sarabun (or any Thai-capable font the tool offers).

HARD RULES
1. Use only the facts in the FACT BANK below. Do not invent statistics, dates,
   citations, or features. If something is not in the bank, leave it out.
2. Every slide must carry a visual element — a diagram, an icon row, a comparison
   table, or a placeholder box captioned "ใส่ภาพหน้าจอเกมตรงนี้".
3. Body text: maximum 5 short lines per slide. Put the detail in speaker notes,
   not on the slide.
4. Write speaker notes for every slide, in Thai, as sentences the presenter can
   actually say out loud — not a restatement of the bullets. End each note with a
   suggested duration, e.g. [~1 นาที 30 วินาที].
5. Keep the bullets short and factual so the presenter can rewrite the wording in
   their own voice without breaking the layout.
6. Do not use decorative accent bars, stripes, or underlines beneath titles.

REQUIRED STRUCTURE
The deck must cover these seven sections, in this order, whatever SLIDE_COUNT is:
Abstract → Introduction → Background/Theoretical Framework → Methods → Results →
Discussion → Conclusions.

Scale to SLIDE_COUNT like this:
- 8 slides: title, abstract, introduction, background+related work merged,
  methods (architecture + the guarantee mechanism), results, discussion, conclusions
- 10 slides: as above, but split background from related work, and give the
  guarantee mechanism its own slide
- 15 slides: split introduction into problem and objectives; split methods into
  architecture, interview loop, guarantee mechanism, randomization, testing;
  split results into screens, numbers, and test results
- 20 slides: additionally split discussion into findings and limitations, give
  each technology group its own slide, and add an agenda slide after the title

Whatever the count, the slide on the guarantee mechanism (pressure floor) gets a
full slide to itself and the most visual weight. It is the project's contribution.

Add a Thai title slide with these fields left blank for the presenter to fill:
ผู้จัดทำ, รหัสนักศึกษา, อาจารย์ที่ปรึกษา, ชื่อวิชา, คณะ/สาขา, มหาวิทยาลัย.

=== FACT BANK — the only facts you may use ===

WHAT IT IS
- Title: Kod AI. A single-player detective RPG.
- The player is a detective with one night to solve a theft of five weapons cases
  from a military vault, and must name the culprit before the night ends.
- The distinguishing feature: the four suspects' dialogue is generated live by a
  large language model running on the player's own machine. The player types any
  question they like instead of picking from written options.
- Built with Python 3.14.2 and pygame 2.6.1. 11 modules.
- All graphics and audio are generated in code. The only external asset file is
  one font. Map is 88x70 tiles; the game renders at 384x240 internally, scaled x3
  to 1152x720, at 60 FPS.
- One case: 4 suspects, 7 pieces of evidence, 3 endings. A session runs 30-60 minutes.

THE PROBLEM IT SOLVES
- Conventional detective games (Ace Attorney, Her Story, Return of the Obra Dinn)
  write every line of dialogue in advance. The designer controls exactly what the
  player learns and when, which keeps the puzzle solvable — but the player can
  only ask what the writer anticipated, and a replay gives identical dialogue.
- Using an LLM gives the player freedom to ask anything, but the model's output is
  not controllable. If the model is unhelpful, the case can become unsolvable.
- The research question: how do you get the freedom of an LLM together with the
  guaranteed solvability of an authored game?

THE ANSWER — pressure floor (this is the project's contribution)
- Each suspect has a "pressure" value. The program sets it to:
  pressure = max(the value the model reported, the sum of evidence actually presented)
- So presenting real evidence always advances the case, no matter what the model says.
- The verdict is computed by the program from the evidence the player presented.
  The model is never asked who is guilty.
- Concrete numbers: the vault checkout ledger is worth 25 pressure, the gate camera
  footage 30. Together 55, which is exactly the minimum the best ending requires
  (which also requires 2 items from the strong-evidence pool). So presenting those
  two exhibits guarantees the best ending even if every model reply is unhelpful.
- The gate camera requires the ledger first, so order matters.
- Grades by number of turns used: S is 10 or fewer, A is 16 or fewer, B is 24 or
  fewer, C is more than 24.

HOW A QUESTION BECOMES AN ANSWER
1. Player types a question, or presses TAB to present a piece of evidence.
2. The game combines that suspect's system prompt with the conversation history
   and sends it to the model on a background thread, so the game keeps drawing at
   60 FPS instead of freezing. Pressing ESC cancels a question and rolls the turn back.
3. The model replies. Internal reasoning wrapped in <think> tags is stripped out.
4. The model is required to append a machine-readable control line —
   [[TELL composure=... pressure=+N asked=yes|no concepts=a,b,c]] — which the game
   parses and then removes before showing the text to the player.
5. The game updates pressure and mood, then applies the floor described above.

RANDOMIZED CULPRIT
- The guilty party is chosen at random from three possible suspects on every new game.
- The routine restores the original text first, picks a culprit, then merges that
  culprit's variant text over the base — so nothing from a previous run survives.
- The case stays coherent because each suspect's "break" condition is a property of
  their personality, not of guilt. The three types are: breaking at a pressure
  threshold, breaking only when shown evidence AND asked directly, and breaking when
  the conversation reaches a particular topic. An innocent suspect breaks the same
  way, so the player cannot identify the culprit by watching who cracks first.
- An environment variable can pin the culprit, which makes a demo reproducible.

RELATED WORK (cite exactly as written; do not add others)
- Park et al., "Generative Agents: Interactive Simulacra of Human Behavior", UIST 2023
  — 25 agents with memory, reflection and daily planning in a Sims-like sandbox.
  Optimises for believable behaviour; has no win condition to protect.
- "Exploring Presence in Interactions with LLM-Driven NPCs", VRST 2024 — a murder
  mystery game where players interrogate LLM-driven NPCs, comparing speech input
  against a dialogue box. The closest comparable to this project.
- "Symbolically Scaffolded Play: Designing Role-Sensitive Prompts for Generative NPC
  Dialogue", arXiv 2510.25820 — a detective role-play probe where the player
  interrogates two suspect NPCs.
- "Tricking LLM-Based NPCs into Spilling Secrets", ProvSec 2025, arXiv 2508.19288 —
  shows prompt injection can make LLM NPCs disclose in-game secrets. This is why
  break conditions here are never tied to guilt and the verdict is computed in code.
- NVIDIA ACE, Convai, Inworld AI — commercial AI-NPC toolkits. They target latency,
  inference cost and response safety. None of them attempts to guarantee a mystery
  stays solvable.
- Comparison table to include, four columns
  (System / Dialogue / Runs where / Always solvable?):
  Generative Agents (UIST 2023) | generated | cloud API | no win condition
  LLM murder-mystery study (VRST 2024) | generated | cloud API | not stated
  The Interview (arXiv 2510.25820) | generated | cloud API | not stated
  NVIDIA ACE / Convai / Inworld | generated | cloud or on-device | not a design goal
  Ace Attorney / Her Story / Obra Dinn | authored | local | yes, by authoring
  Kod AI (this project) | generated | self-hosted, local-capable | yes, by mechanism
  Highlight the last row. The claim it supports: of the systems surveyed, this is
  the only one combining generated dialogue, operation with no commercial cloud AI
  service, and a guarantee that the case remains solvable. Say "self-hosted, and it
  runs fully offline against a local model" rather than "fully local" — the shared
  server that makes the download playable is on the project's own hardware, not a
  third party's, and that is the defensible version of the claim.

TECHNOLOGY
- Python 3.14.2, pygame 2.6.1, numpy (audio synthesis), Pillow (icon generation).
- LM Studio, or any server implementing the OpenAI chat-completions API. Qwen 3.5 9B
  was the model used in testing.
- Two ways to reach it: a shared instance self-hosted by the project (so a downloaded
  build works with nothing to install), or the player's own local server, which runs
  fully offline and is used automatically when the shared one is unreachable.
- PyInstaller packages the game into a .exe and a .app.
- GitHub Actions builds and self-tests on windows-latest and macos-latest; installers
  are published on GitHub Releases.
- No commercial cloud AI service is called and there is no per-call cost. Running a
  local model keeps every conversation on the player's own machine.

THEORY TO NAME
- LLM and prompt engineering: per-suspect system prompts define personality,
  background and knowledge limits, plus the control-line protocol.
- Finite state machine: the game has 7 states, and each keypress is interpreted
  according to the current one.
- Client-server and REST API: the game is an HTTP client to a local model server.
- Concurrency: model calls run on a background thread with a queue, so the game
  never blocks.

TESTING AND RESULTS
- Four levels, all passing:
  Unit — the control-line parser and the culprit-pool validation.
  Integration — boots and renders the whole game headlessly under dummy display
  drivers; asserts props=140, npcs=4, font=True, audio=True.
  System — builds and self-tests the packaged binary on both windows-latest and
  macos-latest via GitHub Actions.
  Acceptance — full manual playthrough against a running model; 30-60 minutes.
- 8 defects were found and fixed. The notable ones: the model leaking its internal
  <think> reasoning to the player; three UI text-overflow bugs found by rendering
  every screen headlessly to image files; evidence text contradicting itself when
  the culprit was randomized; the in-game clock freezing while the case file was open.
- Headless rendering was the single most effective testing technique, and the same
  method produced the 20 screenshots used in the written report.
- Development ran 10 August to 5 September 2026, 36 commits.
- Development machine: MacBook Pro, Apple M5, 10-core CPU, 10-core GPU, 24 GB
  unified memory. The unified memory is what lets one machine host both the game
  and a 9-billion-parameter model at once.

FINDINGS FOR THE DISCUSSION SECTION
- Let the model speak, but let the program decide. Moving the win condition out of
  the model and into code is what made the system testable and predictable.
- Every point that depends on the model's judgement has a deterministic backstop
  in code, for the case where the model does not report state back.
- Headless rendering is the best UI testing tool available here: it finds text
  overflow immediately and produces report figures as a side effect.
- The one-sentence takeaway: an AI system becomes trustworthy not by making the
  model better, but by designing the system to stay correct when the model is wrong.

LIMITATIONS (state these plainly; do not soften them)
- The player must install a model server themselves; it is not click-and-play.
- It needs a machine with enough memory to host a 9B model.
- There is no save/load; the session must be finished in one sitting.
- There is only one case, though the culprit is randomized.
- Output quality depends on the model used, and models were not compared systematically.

FUTURE WORK
- Save and load. A second case, to test whether the case data structure is really
  reusable. A systematic comparison across models. Support for smaller models so
  lower-spec machines can run it.
=== END FACT BANK ===
````

---

## Theme options

Replace the `THEME:` line in CONFIG with one of these to change the look.

| Theme | THEME line to paste |
|---|---|
| Film noir (current) | `dark film-noir — deep navy-black background, amber accent, muted teal secondary` |
| Terminal green | `dark technical — near-black background, phosphor-green accent, cool grey secondary` |
| Academic light | `light academic — white background, deep navy headings, single crimson accent` |
| Warm editorial | `warm editorial — cream background, dark brown text, burnt-orange accent` |
| Cold forensic | `cold forensic — slate grey background, ice-blue accent, white text, one red highlight` |

## After the tool generates the deck

1. **Check the numbers.** These generators paraphrase, and paraphrasing breaks
   arithmetic. The three that must survive intact: 25 + 30 = 55, four test levels
   all passing, and 8 defects fixed.
2. **Drop in the screenshots.** `docs/screenshots/` holds 20 captures. The three
   worth using are `02-world-interact-prompt.png`, `04-dialogue-input.png`, and
   `20-ending-solution.png`.
3. **Rewrite the bullets in your own words.** The prompt deliberately keeps them
   short so you can, without the layout breaking.
4. **Check the citations survived.** Generators like to trim author names and years.
5. If Thai text renders with broken vowel marks, switch the font to Sarabun,
   Noto Sans Thai, or Tahoma.

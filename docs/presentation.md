# Presentation pack — Kod AI

Run sheet, contingency plan, slide outline, and likely questions for the
project defence. Everything here is checked against the actual code; the
`file:line` references are there so any claim can be verified on the spot.

---

## 0. Before you leave the house

| # | Check | How |
|---|---|---|
| 1 | LM Studio installed on the presenting laptop, with the chat model downloaded | Open LM Studio, confirm the model appears under *My Models* |
| 2 | Server running and serving on the default port | LM Studio → *Developer* / *Local Server* → **Start** |
| 3 | *Max Concurrent Predictions* set to 5 | LM Studio → *Developer* → server settings. Anything less queues the audience |
| 4 | Gateway and tunnel up, address published | `LLM_TOKEN=… ./tools/start_server.sh --push` |
| 5 | Game launches and shows a **green dot + `MODEL OK`** on the title screen | Launch the game; the badge is at the top-right (`main.py:1590`) |
| 6 | Rehearse the run sheet below once, end to end, with a timer | — |
| 7 | `docs/screenshots/` present on the laptop (20 PNGs) | Fallback material — see §2 |
| 8 | Laptop on mains power, **lid open**, sleep disabled, notifications off | `sudo pmset -a disablesleep 1`; `caffeinate` does not survive a lid close on Apple silicon, and a sleep drops every connected player at once |

The model has to be **loaded**, not just downloaded. If nothing is loaded, the
game reports `No chat model is loaded in LM Studio.` (`llm.py:131`).

---

## 1. Demo run sheet (~7 minutes)

### Make it reproducible first

The culprit is picked at random on every new game (`pick_culprit()` in
`case.py`). For a rehearsed demo, pin it:

```bash
FORCE_CULPRIT=doss python3 rpg/main.py
```

Doss is the right choice for a short demo: he stands **inside the vault**
(tile 40, 8 — `world.py:695`), in the same room as both of the two exhibits you
need. Nothing else in the game is changed by this variable.

**Say this out loud when you use it** — it is a strength, not a cheat:
*"ผมล็อกคนร้ายไว้เพื่อให้การสาธิตคงที่ ปกติเกมจะสุ่มคนร้ายใหม่ทุกครั้งที่เริ่มเกม"*
("I've pinned the culprit so the demo is reproducible; normally the game
randomizes it every new game.") If the professor asks you to prove it,
quit and relaunch **without** the variable and show the case file naming a
different suspect.

### Controls you will actually use

| Key | Does |
|---|---|
| `WASD` / arrows | Move (`SHIFT` to run) |
| `E` | Examine a prop, or start talking to a suspect |
| `ENTER` | In conversation: open the type-a-question box |
| `TAB` | In conversation: open the evidence picker — this is how you *present* evidence |
| `A` | Accuse (works from inside a conversation) |
| `ESC` | Back / cancel / pause |
| `F11` | Fullscreen — **use this**, the room needs to see it |

### The route

You start inside the Third Precinct (bottom-left of the Civic district). The
vault is in **Fort Callow**, the military district at the top right.

| Step | Action | You should see |
|---|---|---|
| 1 | Press `F11`, then `ENTER` at the title | The city, player in the precinct |
| 2 | Leave the precinct by the corridor at the **top** of the room | Street |
| 3 | Head **north-east** across the map to Fort Callow | Three military buildings; the **Special Weapons Vault** is the left one of the top row |
| 4 | Enter through its door on the **south** side | Concrete room, crates, two terminals, Corporal Doss standing near the right wall |
| 5 | Walk to the **vault checkout terminal** (right side of the room), press `E` | *"Five checkouts over twelve nights, all on one long-dormant override code…"* — **Vault Checkout Ledger added** |
| 6 | Walk to the **gate camera console** (upper-left of the same room), press `E` | *"…out after hours, every time. The last clip: he meets a masked figure roadside…"* — **Gate Camera Footage added** |
| 7 | Walk up to **Doss**, press `E` | Dialogue box, his opening line |
| 8 | Press `TAB`, select **Vault Checkout Ledger**, press `ENTER` | He answers; his composure drops |
| 9 | Press `TAB`, select **Gate Camera Footage**, press `ENTER` | He answers again; pressure now at least 55 |
| 10 | Press `ENTER` and type one direct question, e.g. `Did you sign that override yourself?` | A generated reply — this is the moment to point out nothing here was pre-written |
| 11 | Press `A`, choose **Doss**, confirm | Ending screen: **disposition**, then `→` for **what actually happened** |

**Why exactly those two exhibits:** the ledger is worth 25 pressure and the
gate camera 30. They sum to **55**, which is exactly the `minPressure` the
strong ending requires, and they are 2 items from the strong pool, which meets
`requires_count: 2` (`case.py`, `conviction.strong`). The gate camera also
**requires** the ledger, so you must examine them in that order.

Because the deterministic floor at `main.py:657` sets pressure to at least the
sum of the presented evidence, those two exhibits guarantee the strong ending
**even if the language model says something unhelpful in every reply.** That is
the single most defensible line in your whole demo.

With ~4 turns used, you land grade **S — SURGICAL** (grade S is `turns <= 10`,
`main.py:734`).

### If a suspect's reply is slow

The model runs on a background thread; the game keeps rendering and shows a
waiting state. Say so rather than standing in silence: *"ตอนนี้โมเดลกำลังคิดอยู่
ตัวเกมไม่ได้ค้าง — มันเรียกโมเดลบนเธรดแยก"*. Press `ESC` to cancel a question if
it takes too long; the turn is rolled back (`main.py:939`), so nothing is lost.

---

## 2. If the model will not connect

This is the one failure the room can see. Handle it in this order.

**Level 1 — the game already handles it.** If the server is down, the game does
not crash. Talking to a suspect shows:

> "They look at you and say nothing. The case server is not answering (…). The
> game keeps trying to reconnect on its own - carry on gathering evidence and
> try again in a moment."

(`main.py:449`.) The title screen shows a **red dot + `MODEL OFFLINE`**, and the
client retries by itself every 4 seconds (`main.py:994`). **Turn this into a
point:** the network layer degrades gracefully instead of crashing, and it
recovers on its own once the server returns.

**Level 2 — fix it live.** In order of likelihood: LM Studio's server stopped
or its model unloaded; the tunnel died (restart `./tools/start_server.sh`, which
republishes the new address); or `server.json` still points at a stale address.
Keep going while it comes back — walking the city, examining evidence, and the
whole case file work with no model at all.

**Level 2b — fall back to a local model.** `LLM_URL` overrides the hosted
lookup entirely, so a laptop with LM Studio running can bypass the network
completely:

```bash
LLM_URL=http://localhost:1234/v1 python3 rpg/main.py
```

This is the strongest fallback: it removes the tunnel, the directory, and the
venue's wifi from the demo in one command.

**Level 3 — present from the captures.** `docs/screenshots/` holds 20 PNGs of
every screen in the game, rendered from the real program, including the
evidence picker, a live transcript, a broken suspect's statement, and **both**
ending pages. Walk the class through those instead. Say plainly that you are
showing captures because the local model server will not start — do not pretend
the screenshots are live.

**Do not** try to install, download, or reconfigure anything during your slot.

---

## 3. Slide outline

Eleven slides, each reusing an asset that already exists in the repo.

| # | Slide | Say | Show |
|---|---|---|---|
| 1 | Title | Name, project, one line: *a detective RPG where every suspect answers you live* | `docs/screenshots/01-title.png` |
| 2 | Problem | Detective games have fixed dialogue: you can only ask what the writer anticipated, and a replay is identical | — |
| 3 | What it is | Open city, four suspects, seven exhibits, one night, three endings | `02-world-interact-prompt.png` |
| 4 | Architecture | 11 modules, all art and audio generated in code, one external service (a local model server) | Diagram 1, `docs/diagrams.md` |
| 5 | One question, end to end | Player types → background thread → model → control line parsed → pressure updated → reply drawn | Diagram 4 (sequence) |
| 6 | **The key idea** | Evidence pressure is computed by the program, not the model — so the case is always solvable | Diagram 6 + `main.py:657` |
| 7 | Randomized culprit | The guilty party changes every new game; the same exhibits stay valid because break conditions are never tied to guilt | Diagram 5 |
| 8 | Live demo | Run sheet, §1 | The game |
| 9 | Testing | 4 test levels, 8 real defects found and fixed | Ch.5 §3 table + defect log |
| 10 | Delivery | CI on Windows + macOS, installers published on GitHub Releases | `build.yml`, the Releases page |
| 11 | Limits + future | No save/load, one case, needs a machine that can host a ~9B model | Ch.6 §2 |

If the slot is short, slides 6 and 9 are the two that carry the most credit.
Cut 3 and 10 first.

---

## 4. Likely questions

**"ถ้าโมเดลไม่ยอมให้ข้อมูล ผู้เล่นจะแก้คดีไม่ได้ใช่ไหม"**
*Doesn't the game break if the model refuses to cooperate?*
No. Pressure is set to at least the sum of the evidence actually presented
(`main.py:657`), and the verdict is computed by `resolve()` from what the player
presented — never from the model's text. The two key exhibits sum to exactly the
55 needed for the strong ending, so the case is winnable regardless of what the
model says.

**"สุ่มคนร้ายแล้วคดีจะยังสมเหตุสมผลอยู่ไหม"**
*If the culprit is random, is the case still consistent?*
Yes. Each suspect carries a `guiltVariant` block; `pick_culprit()` restores the
base text first, then merges the guilty variant over it, so no leftovers from a
previous run survive. Crucially, the three break mechanics (`threshold_any`,
`evidence_plus_question`, `conversational_trigger`) are properties of the
*character*, not of guilt — an innocent suspect still breaks the same way, so
you cannot identify the culprit by watching who cracks.

**"ต้องต่ออินเทอร์เน็ตไหม"**
*Does it need internet?*
No. The model runs on the player's own machine through any OpenAI-compatible
server (LM Studio was used here). No cloud service, no API key, no per-call
cost, and no conversation data leaves the machine.

**"จะทดสอบยังไงในเมื่อคำตอบไม่เหมือนกันทุกครั้ง"**
*How do you test something whose output is non-deterministic?*
By testing everything except the model's wording. `--selftest` boots the game
headlessly under dummy SDL drivers and asserts on the parts that *are*
deterministic: the control-line parser, the culprit pool, that every suspect id
resolves, that props/NPCs/font/audio all initialise. `FORCE_CULPRIT` makes a run
reproducible. Three UI overflow bugs were found this way — by rendering every
screen headlessly and looking at the output — which is also how the 20
screenshots in the report were produced.

**"ทำไมถึงเลือกทำเอง แทนที่จะใช้ NVIDIA ACE หรือ Convai"**
*Why build this rather than use an existing AI-NPC platform?*
Those platforms optimise for believable conversation; none of them try to
guarantee that a mystery stays solvable. That guarantee is this project's
contribution, and it lives in program code, not in a prompt. See Ch.2 §3 for the
full comparison.

---

## 5. Cheat sheet — numbers worth having memorised

| Fact | Value |
|---|---|
| Internal resolution / window | 384×240, scaled ×3 → 1152×720 |
| Frame rate | 60 FPS |
| Suspects / exhibits | 4 / 7 |
| Strong ending needs | 2 exhibits from the pool **and** pressure ≥ 55 |
| Vault ledger + gate camera | 25 + 30 = **55** |
| Grade S | ≤ 10 turns |
| Endings | 3 (`wrong_suspect`, `correct_thin`, `correct_strong`) |
| Session length | ~30–60 minutes |
| Commits / test levels / defects fixed | 36 / 4 / 8 |
| External asset files | 1 (`PressStart2P.ttf`) — everything else is generated in code |

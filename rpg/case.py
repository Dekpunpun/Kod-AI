"""The case. Everything the game knows about the scenario lives here.

Four suspects instead of one, each cracking under a different mechanic (see
each suspect's "break" dict): Thorne needs a pile of evidence, Doss and
Ashworth need one specific piece of evidence *plus* the right question, and
Bricker needs no evidence at all — only for the detective to have explained,
in conversation, what is actually at stake.
"""

import os
import random

CASE = {
    "id": "kod-ai",
    "title": "Kod AI",
    "meta": {
        "title_lines": ("KOD", "AI"),
        "subtitle": "A CITY ON THE CLOCK",
        "opening": (
            "00:12. Five VSP-5 demolition charges are missing from the Special "
            "Weapons vault at Fort Callow - together, enough to level a city "
            "block. No ransom note. No group has claimed them. You have until "
            "someone else's deadline to find out who took them, why, and where "
            "they are - though nobody has told you that part yet. Third "
            "Precinct is yours to leave whenever you're ready."
        ),
        # Inside the Third Precinct bullpen — the opening line hands the
        # detective their own home base to leave when they're ready, so the
        # run starts there rather than out in the open.
        "spawn": (11, 24),
    },
    "victim": {
        "name": "Mira Thorne",
        "detail": "31. Wife of Staff Sgt. Elias Thorne. Taken four days before the first theft.",
    },
    "scene": (
        "Fort Callow Special Weapons Vault, Harrow's Reach. A surprise ordnance audit this "
        "morning turned up five missing VSP-5 'Vesper' demolition charges - man-portable, "
        "built to drop a reinforced bridge span in a single blast, and together enough to "
        "level several city blocks. No forced entry. The vault's two-signature rule was "
        "satisfied on every checkout. Nothing on the surface points at anyone."
    ),
    "timeline": [
        ("-12d", "Mira Thorne is taken by the Cinder Compact. No one reports it yet."),
        ("-12n", "First of five vault checkouts begins, spread over twelve nights."),
        ("06:40", "The duty officer's incident report is filed, off an anonymous tip."),
        ("00:12", "Tonight. The deadline nobody has told the detective about yet."),
    ],
    "facts": [
        "Five VSP-5 cases are missing from Fort Callow's Special Weapons vault.",
        "The vault requires two-person sign-off; no one badge alone can check out a case.",
        "Vesper charges are inert without a separate detonator train, which is fully accounted for.",
        "The motor pool gate camera logs every vehicle in and out, timestamped, for the past week.",
        "A group calling itself the Cinder Compact is tied to two prior small bombings nearby.",
        "The audit was ordered off the back of an anonymous tip called in overnight.",
        "A welfare-check review was opened on Sgt. Thorne after his last deployment. It was "
        "never completed or filed.",
    ],
    "suspects": [
        {
            "id": "thorne",
            "name": "Staff Sergeant Elias Thorne",
            "sprite": "thorne",
            "role": "Special Weapons vault rotation, Fort Callow",
            "personality": (
                "Not hardened, not defiant - exhausted past the point of fear, holding on to "
                "one plan that has narrowed to a single option. Protective of Mira above "
                "literally everything else, including himself. Flat and quiet; answers get "
                "shorter the closer they get to her name."
            ),
            "publicAlibi": (
                "He says nothing is wrong. He hasn't slept, that's all. He was never home to "
                "ask because he's been at the vault, on the road, or here. He wants the "
                "detective to leave before it gets late."
            ),
            # Base = the version of him who did NOT take the charges. He is
            # still Mira's husband and still the emotional centre of the case
            # either way; what changes is whether his own hands are dirty.
            "hiddenTruth": (
                "The Cinder Compact took Mira four days before the first theft and has been "
                "issuing instructions since: one case at a time, or she doesn't come home. He "
                "could not get at the vault himself without burning the only person who could, "
                "so he did the one thing left - he told someone, and that someone has been "
                "paying the ransom for him, one case at a time. He has made himself not ask how. "
                "Four are already gone. The fifth changes hands at midnight, at his own family's "
                "cabin on Salt Row - he came here to wait for word, because he could not stand "
                "one more night not knowing, even though the carrying was never his to do."
            ),
            "motive": (
                "Not greed - Mira. He let someone else break the law on his behalf because it "
                "was the only currency the Cinder Compact would take, and refusing meant "
                "burying his wife."
            ),
            "protects": "who is actually doing this for him, how much he was told, and the fact that he let it happen",
            "concession": "that he knows more than he has said, and that someone close to him is taking the real risk to save her",
            "opener": "You shouldn't be here. Not tonight, not now. Please - just go. I don't have anything to say to you.",
            "break": {
                "type": "threshold_any",
                "pool": ["vault-ledger", "gate-camera", "burner-phone", "proof-of-life-photo", "bricker-account"],
                "count": 2,
            },
            # Guilty variant: verbatim the text this case shipped with.
            "guiltVariant": {
                "hiddenTruth": (
                    "He stole all five VSP-5 cases from the vault over twelve nights, using Colonel "
                    "Ashworth's long-dormant override code to satisfy the two-signature rule without "
                    "her knowledge, because the Cinder Compact took Mira four days before the first "
                    "theft and has been issuing instructions since: one case at a time, or she "
                    "doesn't come home. He drove each case home after hours and handed it off at a "
                    "rotating roadside meeting point. Four are already gone. The fifth is with him "
                    "now, at the family's fishing cabin on Salt Row, due at midnight."
                ),
                "motive": (
                    "Not greed - Mira. He is paying a ransom in stolen ordnance because it's the "
                    "only currency the Cinder Compact would take."
                ),
                "protects": "the vault thefts, the override code, the burner phone, and where Mira and the fifth case are",
                "concession": "that he is terrified and out of options, and that this was never about money",
                "gate_camera_text": {
                    "summary": "Thorne's truck out after-hours all five nights; a masked handoff on the last.",
                    "detail": (
                        "A cracked monitor cycling through a week of grainy footage. On all five nights "
                        "matching the ledger, one truck logs out after hours: registered to Staff "
                        "Sergeant Elias Thorne. On the most recent night, it catches him stopped roadside "
                        "half a mile out, meeting a masked figure who takes something from his truck bed."
                    ),
                    "contradicts": "His claim that he's been at the vault, on the road, or home - nothing else.",
                    "found_text": (
                        "The ledger's five nights, cross-checked against the gate log. Thorne's truck, out "
                        "after hours, every time. The last clip: he meets a masked figure roadside, hands "
                        "something over, and drives on - not toward home."
                    ),
                },
                "endings": {
                    "correct_strong": (
                        "Grim relief, not triumph. Confronted with the evidence, Thorne gives up the "
                        "cabin and the midnight handoff before you have to ask twice. Officers move on "
                        "Salt Row in time; the fifth case is recovered, and - just barely - so is Mira, "
                        "traced through the courier caught at the drop. Thorne is arrested, but the "
                        "report on his desk starts with 'coerced' instead of 'sold,' and Ashworth is "
                        "already fighting to keep it that way."
                    ),
                    "correct_thin": (
                        "Right name, thin case. You name Thorne but can't back it with much, and the "
                        "confrontation goes differently - he shuts down instead of breaking, gives up the "
                        "case but not the cabin, not the deadline, not Mira. The fifth charge turns up "
                        "days later in a raid, empty-handed on everything else. It's filed as a "
                        "straightforward theft. Nobody finds out why, and nobody goes looking for her."
                    ),
                },
                "reveal_text": (
                    " Thorne is picked up two days later, ruined and alone - Mira is never found in "
                    "time, and he stops talking about her entirely."
                ),
                "solution": (
                    "Staff Sergeant Elias Thorne stole all five VSP-5 cases from Fort Callow's vault over "
                    "twelve nights, using Colonel Ashworth's long-dormant override code to satisfy the "
                    "two-signature rule without her knowledge - Cpl. Doss, trusting him, countersigned every "
                    "one. He was paying a ransom in stolen ordnance: the Cinder Compact took his wife Mira "
                    "four days before the first theft and has been trading her life for one case at a time "
                    "ever since. The fifth case, and the final handoff for Mira, waited at the family's "
                    "fishing cabin on Salt Row, due at midnight."
                ),
            },
        },
        {
            "id": "doss",
            "name": "Corporal Wyatt Doss",
            "sprite": "doss",
            "role": "Vault NCO, Fort Callow Special Weapons Depot",
            "personality": (
                "By-the-book to the point of anxiety, now visibly unraveling because the book "
                "let him down. Not devious - someone who trusted rank over instinct and is "
                "starting to understand the cost. Overexplains procedure when nervous, which is "
                "most of the time now. Clipped military phrasing, 'sir' and 'ma'am' on reflex."
            ),
            "publicAlibi": (
                "He was on duty exactly as logged, every night in question. He signed off same "
                "as always, following procedure to the letter - which, he keeps pointing out, is "
                "exactly the problem."
            ),
            "hiddenTruth": (
                "He countersigned all five checkouts now missing, every night Thorne told him it "
                "was 'already cleared with the Colonel' using her old override code. He didn't "
                "check. He's spent the morning quietly re-reading the log himself, terrified of "
                "what it means. He knows nothing about any blackmail or Mira - genuinely no idea "
                "why, only that his name is on all of it."
            ),
            "motive": "Fear of losing his rating and being blamed for a pattern he only now understands.",
            "protects": "very little - he wants someone to walk through the pattern with him and confirm what it means",
            "concession": "that he never once called to confirm the override, all five times",
            "opener": "You're here about the audit. I already gave my statement, but - go ahead, ask. I signed off. Same as always.",
            "guiltVariant": {
                "hiddenTruth": (
                    "He took all five cases himself. Elias came to him two weeks ago with the Cinder "
                    "Compact's terms and nowhere left to go, and Doss - who has never once broken a "
                    "regulation in his life - worked out that Colonel Ashworth's old adjutant override "
                    "had never been retired, and that his own countersignature would close the loop. "
                    "He ran every checkout himself, on his own shifts, and drove each case out in his "
                    "own car to a rotating roadside handoff. He kept Elias away from all of it on "
                    "purpose, so that when it came apart only one of them would be finished. Four are "
                    "gone. The fifth goes tonight at midnight, off Salt Row."
                ),
                "motive": (
                    "Loyalty, and a debt he has never talked about. Not money - he has calculated "
                    "exactly what this costs him and decided a friend's wife is worth more than his "
                    "own career."
                ),
                "protects": "that he ran the checkouts himself, the override he dug up, and where the last case goes tonight",
                "concession": "that he broke the one rule he has built his whole career on, deliberately, and would do it again",
                "gate_camera_text": {
                    "summary": "Doss's car out after-hours all five nights; a masked handoff on the last.",
                    "detail": (
                        "A cracked monitor cycling through a week of grainy footage. On all five nights "
                        "matching the ledger, one car logs out after hours: registered to Corporal Wyatt "
                        "Doss. On the most recent night, it catches him stopped roadside half a mile out, "
                        "meeting a masked figure who takes something from his back seat."
                    ),
                    "contradicts": "His claim that he was on duty exactly as logged, every night in question, and nothing more.",
                    "found_text": (
                        "The ledger's five nights, cross-checked against the gate log. Doss's car, out "
                        "after hours, every time - on the same nights he signed off on. The last clip: he "
                        "meets a masked figure roadside, hands something over, and drives on."
                    ),
                },
                "endings": {
                    "correct_strong": (
                        "Grim relief, not triumph. Confronted with the log and his own car on the gate "
                        "camera, Doss stops explaining procedure and tells you the rest of it - the "
                        "handoff, the hour, the stretch of Salt Row. Officers move in time; the fifth case "
                        "is recovered, and - just barely - so is Mira, traced through the courier caught "
                        "at the drop. Doss is arrested without a word of protest, and Thorne, who was "
                        "never told the how of it, cannot stop telling anyone who will listen that the "
                        "man did it for him."
                    ),
                    "correct_thin": (
                        "Right name, thin case. You name Doss but can't back it with much, and he retreats "
                        "into the regulations he knows better than anyone - concedes the signatures, "
                        "concedes nothing else, not the handoff, not the hour, not Mira. The fifth charge "
                        "turns up days later in a raid, empty-handed on everything else. It's filed as an "
                        "inside theft by a corporal with a clean record and no explanation. Nobody finds "
                        "out why, and nobody goes looking for her."
                    ),
                },
                "reveal_text": (
                    " Doss is picked up two days later, still filing his paperwork on time - Mira is "
                    "never found, and he never once says her husband's name."
                ),
                "solution": (
                    "Corporal Wyatt Doss stole all five VSP-5 cases from Fort Callow's vault over twelve "
                    "nights. Elias Thorne had come to him with the Cinder Compact's terms and no way to "
                    "meet them, and Doss - the most procedural man on the post - found that Colonel "
                    "Ashworth's long-dormant adjutant override had never been retired, and that his own "
                    "countersignature would satisfy the two-signature rule. He ran every checkout on his "
                    "own shift and drove each case out himself, deliberately keeping Thorne clear of it. "
                    "The fifth case, and the final handoff for Mira, was due off Salt Row at midnight."
                ),
            },
            "break": {
                "type": "evidence_plus_question",
                "evidence": "vault-ledger",
                "angle": "asking him plainly, directly, what the ledger pattern actually means",
                # Deterministic backstop: a model that never self-reports
                # asked=yes (weak model, or just an inconsistent judgment
                # call) can't stall a player who plainly asked the right
                # thing. Matches a topic word AND a question word anywhere
                # in the player's own text (never the model's reply) rather
                # than an exact phrase, since real phrasing reorders freely
                # ("what does the pattern in that ledger actually mean?").
                "angle_keywords": {
                    "topic": ["pattern", "ledger", "log", "checkout", "override", "signature"],
                    "ask": ["mean", "means", "explain", "going on", "happened", "why", "walk me through"],
                },
            },
            "schedule": {
                "leaves_at": 170,
                "warnings": [
                    (110, "I'm off shift in about an hour, for what it's worth."),
                    (150, "Twenty minutes and I'm off the clock. Whatever you need, ask it now."),
                ],
                "vacated": (
                    "Doss's post at the vault terminal sits empty, his log signed out at 22:30. "
                    "Whatever he understood about that ledger, he took it home with him."
                ),
            },
        },
        {
            "id": "ashworth",
            "name": "Colonel Margaret Ashworth",
            "sprite": "ashworth",
            "role": "Battalion Commander, Fort Callow",
            "personality": (
                "Composed, precise, carries command like a second skin - and is using every bit "
                "of that composure right now to not fall apart. Fiercely protective of the "
                "people under her, which is exactly what's compromising her. Guilt-driven rather "
                "than self-interested. Formal, economical sentences; deflects with rank."
            ),
            "publicAlibi": (
                "She was off-base at a command dinner for most of the week in question - easily "
                "confirmed. Whatever the detective needs, she says, ask it once, and ask it like "
                "they intend to use the answer."
            ),
            "hiddenTruth": (
                "The override code on all five unauthorized checkouts is hers - issued to her "
                "years ago as a junior officer's adjutant, never formally retired. She had no "
                "idea it still worked until the audit. Separately, she has been sitting on an "
                "unfiled welfare-check flag for Thorne after his last deployment, delayed "
                "because she believed in him and didn't want one instinct to end his career."
            ),
            "motive": "Loyalty and guilt, not cover-up - but both facts together look exactly like she saw this coming.",
            "protects": "her record, and the fact that she sat on a concern about Thorne instead of filing it",
            "concession": "that she should have filed the flag months ago, and that not filing it may have cost time they didn't have",
            "opener": "I've already spoken to the Provost Marshal. Whatever you need from me, ask it once, and ask it like you intend to use the answer.",
            "guiltVariant": {
                "hiddenTruth": (
                    "She sat on Thorne's unfiled welfare-check flag for months, believing in him, and "
                    "when the Cinder Compact's terms reached her through him two weeks ago she decided "
                    "she owed him more than a form she'd let gather dust. The override code on all five "
                    "checkouts is hers, issued years ago as a junior officer's adjutant - she knew "
                    "exactly that it still worked, and used it herself rather than let Doss's routine "
                    "countersignature ever be questioned. The command dinners were real; a colonel can "
                    "step out of one for an hour without a soul remarking on it, and the five nights on "
                    "the ledger are five nights she found the excuse to leave early. Four cases are "
                    "already gone. The fifth changes hands at midnight, off Salt Row."
                ),
                "motive": (
                    "Guilt, not cover-up - the flag she never filed, turned into the one thing she could "
                    "still do about it herself, in secret, on her own authority."
                ),
                "protects": "that the override was used knowingly, that she drove the checkouts herself, and where the last handoff is",
                "concession": "that she chose to break the law herself rather than let the system fail one of her own soldiers twice",
                "gate_camera_text": {
                    "summary": "Ashworth's staff car out after-hours all five nights; a masked handoff on the last.",
                    "detail": (
                        "A cracked monitor cycling through a week of grainy footage. On all five nights "
                        "matching the ledger, one staff car logs out after hours: registered to the "
                        "battalion commander's office. On the most recent night, it catches Colonel "
                        "Ashworth stopped roadside half a mile out, meeting a masked figure who takes "
                        "something from the trunk."
                    ),
                    "contradicts": "Her claim that she was off-base at command dinners the whole week, with nothing else to account for.",
                    "found_text": (
                        "The ledger's five nights, cross-checked against the gate log. The battalion "
                        "commander's staff car, out after hours, every one of them. The last clip: "
                        "Ashworth herself meets a masked figure roadside, hands something over, and "
                        "drives on."
                    ),
                },
                "endings": {
                    "correct_strong": (
                        "Grim relief, not triumph. Confronted with her own car on the gate camera, "
                        "Ashworth drops the rank she's been hiding behind and gives you the rest of it "
                        "herself - the handoff, the hour, the stretch of Salt Row. Officers move in time; "
                        "the fifth case is recovered, and - just barely - so is Mira, traced through the "
                        "courier caught at the drop. Ashworth surrenders her command without a fight, and "
                        "Doss, who signed off on every checkout without ever knowing why, is the one now "
                        "fighting to keep her file from reading worse than it is."
                    ),
                    "correct_thin": (
                        "Right name, thin case. You name Ashworth but can't back it with much, and she "
                        "retreats into rank instead of breaking - concedes the override was hers, concedes "
                        "nothing else, not the handoff, not the hour, not Mira. The fifth charge turns up "
                        "days later in a raid, empty-handed on everything else. It's filed as a security "
                        "failure at the command level. Nobody finds out why, and nobody goes looking for "
                        "her."
                    ),
                },
                "reveal_text": (
                    " Ashworth is relieved of command two days later, composed to the last - Mira is "
                    "never found, and the flag she never filed is the only part of the file anyone ever "
                    "finishes reading."
                ),
                "solution": (
                    "Colonel Margaret Ashworth stole all five VSP-5 cases from Fort Callow's vault over "
                    "twelve nights, using her own long-dormant adjutant override code so that Cpl. Doss's "
                    "routine countersignature would never need to be questioned. She had sat for months on "
                    "an unfiled welfare-check flag for Sgt. Thorne after his last deployment, and when the "
                    "Cinder Compact reached him with an impossible demand, she chose to act herself rather "
                    "than let the system fail him a second time - trading his wife Mira's life for one "
                    "case at a time. The fifth case, and the final handoff for Mira, waited off Salt Row, "
                    "due at midnight."
                ),
            },
            "break": {
                "type": "evidence_plus_question",
                "evidence": "vault-ledger",
                "angle": "showing her the log and asking specifically why she never filed the welfare-check flag on Thorne",
                "angle_keywords": {
                    "topic": ["welfare", "flag", "flagged"],
                    "ask": ["why", "file", "filed", "filing", "report", "sat on", "sit on"],
                },
            },
            "schedule": {
                "leaves_at": 230,
                "warnings": [
                    (170, "I have a car waiting within the hour. Say what you came to say."),
                    (210, "Twenty minutes, detective. Then I'm back on-post whether we're finished or not."),
                ],
                "vacated": (
                    "The command office's lamp is off and the wall map is dark. Ashworth signed "
                    "out at 23:30 - whatever she was sitting on, she took the decision with her."
                ),
            },
        },
        {
            "id": "bricker",
            "name": "Lance Corporal Sam Bricker",
            "sprite": "bricker",
            "role": "Motor Pool Mechanic, Fort Callow - Thorne's oldest friend",
            "personality": (
                "Loyal to a fault, protective, running on two days of bad sleep. Defensive and a "
                "little combative at first - sees the detective as a threat to his friend, not "
                "help. Underneath it he's scared and ashamed he hasn't done more. Informal, "
                "quick to deflect with sarcasm or irritation."
            ),
            "publicAlibi": (
                "He hasn't seen Elias either, if this is about him. Something's off with him "
                "lately, sure, but that's not a crime. He has no vault access and was never on "
                "the checkout log."
            ),
            "hiddenTruth": (
                "Two nights ago Elias showed up wrecked and told him, in pieces, that 'they have "
                "her' and that he was 'almost done.' Bricker assumed something bad but "
                "survivable - debt, maybe worse - and has NO idea it involves stolen military "
                "ordnance or any terrorist group. He is lying purely to protect Elias from what "
                "he thinks is smaller, more ordinary trouble."
            ),
            "motive": "Protecting his best friend from what he wrongly assumes is a smaller kind of trouble.",
            "protects": "the visit two nights ago, the phrase 'they have her', Mira's absence, and the fishing cabin on Salt Row",
            "concession": "none, until he understands the real scale - pressure and evidence only make him dig in further",
            "opener": "Look, if this is about Elias, I haven't seen him either, alright? Something's off with him lately, sure. That's not a crime, last I checked.",
            "break": {
                "type": "conversational_trigger",
                "concepts": ["scale", "compact", "leverage"],
                "keyword_backstop": {
                    "scale": ["level a city block", "level several city block", "vsp-5", "vesper",
                              "demolition charge", "five case", "military ordnance", "weapons"],
                    "compact": ["cinder compact"],
                    "leverage": ["mira", "his wife", "her life", "hostage", "ransom"],
                },
            },
            "schedule": {
                "leaves_at": 200,
                "warnings": [
                    (140, "I'm not standing out here all night, you know."),
                    (180, "I'm going inside in twenty minutes whether you're done or not."),
                ],
                "vacated": (
                    "Bricker's gone in for the night, the motor pool bay shut at 23:00. Whatever "
                    "he was holding back, he's holding it behind a closed door now."
                ),
            },
        },
    ],
    "evidence": [
        {
            "id": "vault-ledger",
            "name": "Vault Checkout Ledger",
            "summary": "Five checkouts, one dormant override code, all countersigned by Doss.",
            "detail": (
                "A terminal bolted to the vault's outer wall, logging every checkout by badge, "
                "time, and countersignature. Five entries over the last twelve nights stand out: "
                "the same override code on every one, issued to 'M. ASHWORTH, ADJT' years ago. "
                "Cpl. Doss countersigned all five."
            ),
            "contradicts": "The idea that nobody knew which code would still work, or who was on duty to sign off on it.",
            "pressure": 25,
            "found_text": (
                "A terminal bolted to the vault wall. Five checkouts over twelve nights, all on "
                "one long-dormant override code - issued to Colonel Ashworth years ago - and all "
                "countersigned by the same corporal."
            ),
        },
        {
            "id": "gate-camera",
            "name": "Motor Pool Gate Camera Footage",
            "summary": "Thorne's truck out after-hours all five nights; a masked handoff on the last.",
            "detail": (
                "A cracked monitor cycling through a week of grainy footage. On all five nights "
                "matching the ledger, one truck logs out after hours: registered to Staff "
                "Sergeant Elias Thorne. On the most recent night, it catches him stopped roadside "
                "half a mile out, meeting a masked figure who takes something from his truck bed."
            ),
            "contradicts": "His claim that he's been at the vault, on the road, or home - nothing else.",
            "pressure": 30,
            "requires": "vault-ledger",
            "locked_text": "Hours of grainy timestamped footage. Without knowing which five nights to look at, it's just traffic.",
            "found_text": (
                "The ledger's five nights, cross-checked against the gate log. Thorne's truck, out "
                "after hours, every time. The last clip: he meets a masked figure roadside, hands "
                "something over, and drives on - not toward home."
            ),
        },
        {
            "id": "matchbook",
            "name": "Cinder Compact Matchbook",
            "summary": "Dropped at the roadside meeting point. Half-legible note: Salt Row, Dock 4.",
            "detail": (
                "Plain black cover, no name, a single stamped mark near the corner - already "
                "linked to the Cinder Compact's last two jobs. Inside the flap, in ballpoint, "
                "half rubbed away by rain: 'SALT ROW - DOCK 4.'"
            ),
            "contradicts": "The idea that this theft has nothing to do with the Cinder Compact.",
            "pressure": 15,
            "found_text": (
                "A matchbook in the gravel where the gate camera caught the handoff. The mark "
                "matches the Cinder Compact's last two bombings. Inside the flap: 'SALT ROW - "
                "DOCK 4,' half washed out by rain."
            ),
        },
        {
            "id": "struggle-kitchen",
            "name": "Signs of a Struggle",
            "summary": "A shattered mug, a shoved-back chair, nothing packed. She didn't walk out.",
            "detail": (
                "Two mugs in the Thorne kitchen - one full and cold, one shattered on the floor "
                "and never swept up. A chair pushed back hard enough to scuff the tile. Nothing "
                "missing that a woman packing a bag would take - no coat, no keys, no shoes."
            ),
            "contradicts": "Any suggestion that Mira Thorne left on her own.",
            "pressure": 15,
            "found_text": (
                "The kitchen. A shattered mug never cleaned up, a chair shoved back hard, and "
                "nothing missing that anyone leaving willingly would have taken."
            ),
        },
        {
            "id": "burner-phone",
            "name": "The Burner Phone",
            "summary": "Hidden behind a garage shelf. One contact, a thread naming a countdown.",
            "detail": (
                "A prepaid phone tucked behind a paint shelf in the garage, screen cracked, one "
                "saved contact with no name. The thread underneath: a countdown, an address "
                "changed twice, and one line that doesn't need explaining."
            ),
            "contradicts": "Any claim that he isn't being pressured by anyone, or that he has something to sell rather than a debt to pay.",
            "pressure": 25,
            "found_text": (
                "Behind the paint shelf in the garage, a phone, screen cracked. One contact, no "
                "name. A thread of threats - a countdown, an address changed twice, and 'her for "
                "the last one, tonight, or you'll wish it was you.'"
            ),
        },
        {
            "id": "proof-of-life-photo",
            "name": "Proof-of-Life Photo",
            "summary": "Mira, holding a dated newspaper, four days ago.",
            "detail": (
                "Wedged in the same gap as the phone, face down. A woman on a folding chair "
                "against bare concrete, holding a folded newspaper. On the back, in pencil, a "
                "date - four days ago."
            ),
            "contradicts": "Any doubt that this is real, current, and ongoing.",
            "pressure": 20,
            "requires": "burner-phone",
            "locked_text": "There's a gap behind this shelf, but nothing to see until you know to look for it.",
            "found_text": (
                "A photo, face down behind the shelf. Mira Thorne, on a folding chair against bare "
                "concrete, holding up a dated newspaper. Proof she was alive four days ago - and "
                "proof someone wanted that fact kept close at hand."
            ),
        },
        {
            "id": "bricker-account",
            "name": "Bricker's Account",
            "summary": "What Elias told him, two nights ago, once he finally says it.",
            "detail": (
                "Sam Bricker's account, once he understood what he was actually protecting: that "
                "Elias came to him wrecked, said 'they have her,' and that it would 'be over "
                "soon' - and that the two of them know a fishing cabin on Salt Row nobody else "
                "would think to check."
            ),
            "contradicts": "Every version of events where Thorne is acting alone, for money, or by choice.",
            "pressure": 25,
            "sourced": "dialogue",
        },
    ],
    "conviction": {
        # "culprit" is set at runtime by pick_culprit() below, once per run -
        # this is the pool it draws from. Bricker is deliberately never in it:
        # his own publicAlibi states as fact that he has no vault access and
        # was never on the checkout log, and the theft mechanism (badge +
        # override code + routine countersignature) only makes sense for
        # someone already inside that access chain. Thorne (rotation access),
        # Doss (does the countersigning) and Ashworth (owns the override code)
        # all already sit inside it.
        "culprit_pool": ["thorne", "doss", "ashworth"],
        "strong": {
            "pool": ["vault-ledger", "gate-camera", "burner-phone", "proof-of-life-photo", "bricker-account"],
            "requires_count": 2,
            "minPressure": 55,
        },
    },
    # The prose below is the default/fallback (Thorne's variant) so the module
    # is well-formed at import time; pick_culprit() overwrites all of it - see
    # the resolver at the bottom of this file. "wrong_suspect" is split so its
    # who-really-did-it reveal can vary with the culprit without duplicating
    # the shared setup sentence.
    "endings": {
        "correct_strong": {
            "caption": "COERCED, NOT SOLD",
            "prose": (
                "Grim relief, not triumph. Confronted with the evidence, Thorne gives up the "
                "cabin and the midnight handoff before you have to ask twice. Officers move on "
                "Salt Row in time; the fifth case is recovered, and - just barely - so is Mira, "
                "traced through the courier caught at the drop. Thorne is arrested, but the "
                "report on his desk starts with 'coerced' instead of 'sold,' and Ashworth is "
                "already fighting to keep it that way."
            ),
        },
        "wrong_suspect": {
            "caption": "THE WRONG NAME",
            "prose_prefix": (
                "Not a game over, but a costly one. Whoever you named is cleared within hours, "
                "and every one of those hours mattered. Midnight comes and goes with no one "
                "moving on Salt Row. The fifth case changes hands on schedule."
            ),
            "prose": (
                "Not a game over, but a costly one. Whoever you named is cleared within hours, "
                "and every one of those hours mattered. Midnight comes and goes with no one "
                "moving on Salt Row. The fifth case changes hands on schedule. Thorne is picked "
                "up two days later, ruined and alone - Mira is never found in time, and he stops "
                "talking about her entirely."
            ),
        },
        "correct_thin": {
            "caption": "RIGHT NAME, THIN CASE",
            "prose": (
                "Right name, thin case. You name Thorne but can't back it with much, and the "
                "confrontation goes differently - he shuts down instead of breaking, gives up the "
                "case but not the cabin, not the deadline, not Mira. The fifth charge turns up "
                "days later in a raid, empty-handed on everything else. It's filed as a "
                "straightforward theft. Nobody finds out why, and nobody goes looking for her."
            ),
        },
    },
    "solution": (
        "Staff Sergeant Elias Thorne stole all five VSP-5 cases from Fort Callow's vault over "
        "twelve nights, using Colonel Ashworth's long-dormant override code to satisfy the "
        "two-signature rule without her knowledge - Cpl. Doss, trusting him, countersigned every "
        "one. He was paying a ransom in stolen ordnance: the Cinder Compact took his wife Mira "
        "four days before the first theft and has been trading her life for one case at a time "
        "ever since. The fifth case, and the final handoff for Mira, waited at the family's "
        "fishing cabin on Salt Row, due at midnight."
    ),
}

SUSPECTS_BY_ID = {s["id"]: s for s in CASE["suspects"]}
EVIDENCE_BY_ID = {e["id"]: e for e in CASE["evidence"]}

# --- culprit selection -------------------------------------------------------

# Fields that differ between "innocent this run" and "guilty this run" - the
# base (innocent) values live on the suspect dict itself; pick_culprit() below
# swaps in each candidate's "guiltVariant" for whichever one gets picked, and
# restores everyone else first. publicAlibi and opener are deliberately never
# swapped: a suspect's surface story to the detective reads the same either
# way, since it's what they'd say regardless of whether they did it.
_CULPRIT_SWAP_FIELDS = ("hiddenTruth", "motive", "protects", "concession")

# Snapshotted once at import, before anything mutates these dicts, so a
# suspect who was guilty last run can be restored exactly before the next
# pick - reset_run() can call pick_culprit() many times in one process (e.g.
# "ENTER NEW CASE" from the ending screen), and without this a suspect's
# guilty text would otherwise leak into a run where they're innocent.
_BASE_SUSPECT_FIELDS = {
    sid: {k: s[k] for k in _CULPRIT_SWAP_FIELDS} for sid, s in SUSPECTS_BY_ID.items()
}
_BASE_GATE_CAMERA = {k: EVIDENCE_BY_ID["gate-camera"][k] for k in ("summary", "detail", "contradicts", "found_text")}
_BASE_SOLUTION = CASE["solution"]
_BASE_ENDING_PROSE = {shape: CASE["endings"][shape]["prose"] for shape in ("correct_strong", "correct_thin")}
_BASE_WRONG_SUSPECT_PREFIX = CASE["endings"]["wrong_suspect"]["prose_prefix"]


def pick_culprit(rng=random):
    """Roll who's actually guilty this run and merge their `guiltVariant` over
    the shared CASE/SUSPECTS_BY_ID/EVIDENCE_BY_ID dicts in place. Every reader
    in the rest of the codebase (main.py's resolve(), llm.py's system_prompt())
    keeps reading CASE["conviction"]["culprit"] and CASE["endings"][...]
    exactly as before - this only changes what those reads resolve to.

    Set FORCE_CULPRIT in the environment to pin a specific suspect id instead
    of rolling, for testing one branch by hand. A value set but not in the
    pool raises rather than silently rolling anyway - a verification run
    built around one suspect must not pass by accident against a different,
    randomly-chosen one.
    """
    for sid, base in _BASE_SUSPECT_FIELDS.items():
        SUSPECTS_BY_ID[sid].update(base)
    EVIDENCE_BY_ID["gate-camera"].update(_BASE_GATE_CAMERA)
    CASE["solution"] = _BASE_SOLUTION
    CASE["endings"]["correct_strong"]["prose"] = _BASE_ENDING_PROSE["correct_strong"]
    CASE["endings"]["correct_thin"]["prose"] = _BASE_ENDING_PROSE["correct_thin"]
    CASE["endings"]["wrong_suspect"]["prose_prefix"] = _BASE_WRONG_SUSPECT_PREFIX

    pool = CASE["conviction"]["culprit_pool"]
    forced = os.environ.get("FORCE_CULPRIT")
    if forced:
        if forced not in pool:
            raise ValueError(f"FORCE_CULPRIT={forced!r} is not in the culprit pool {pool!r}")
        culprit = forced
    else:
        culprit = rng.choice(pool)

    variant = SUSPECTS_BY_ID[culprit]["guiltVariant"]
    SUSPECTS_BY_ID[culprit].update({k: variant[k] for k in _CULPRIT_SWAP_FIELDS})
    if "gate_camera_text" in variant:
        EVIDENCE_BY_ID["gate-camera"].update(variant["gate_camera_text"])

    CASE["conviction"]["culprit"] = culprit
    CASE["solution"] = variant["solution"]
    CASE["endings"]["correct_strong"]["prose"] = variant["endings"]["correct_strong"]
    CASE["endings"]["correct_thin"]["prose"] = variant["endings"]["correct_thin"]
    CASE["endings"]["wrong_suspect"]["prose"] = _BASE_WRONG_SUSPECT_PREFIX + variant["reveal_text"]
    return culprit


def validate_culprit_pool():
    """Non-mutating selftest check: every pool member has a complete
    guiltVariant, so CI coverage of Doss's and Ashworth's branches isn't a
    coin flip against whichever one a random pick() happened to land on."""
    problems = []
    required = ("hiddenTruth", "motive", "protects", "concession", "endings", "reveal_text", "solution")
    for cid in CASE["conviction"]["culprit_pool"]:
        if cid not in SUSPECTS_BY_ID:
            problems.append(f"culprit_pool id {cid!r} is not a real suspect id")
            continue
        variant = SUSPECTS_BY_ID[cid].get("guiltVariant")
        if not variant:
            problems.append(f"{cid} is in culprit_pool but has no guiltVariant")
            continue
        for k in required:
            if k not in variant:
                problems.append(f"{cid} guiltVariant missing {k!r}")
        for shape in ("correct_strong", "correct_thin"):
            if shape not in variant.get("endings", {}):
                problems.append(f"{cid} guiltVariant.endings missing {shape!r}")
    return problems

"""Kod AI — a walking detective RPG.

    python3 rpg/main.py

Move with WASD or the arrow keys, E to look at things, TAB for the case file.
Four people know something. Only one of them did it.
"""

import math
import os
import random
import sys
import traceback

import pygame

import art
import clock as clockmod
import llm
import sfx
import ui
from case import CASE, EVIDENCE_BY_ID, SUSPECTS_BY_ID, pick_culprit, validate_culprit_pool
from entities import NPC, Player
from settings import *
from world import MAP_H, MAP_W, World

TITLE_SCREEN, PLAYING, CASEFILE, TALKING, ACCUSE, ENDING, PAUSED = range(7)

# Set LE_DEBUG=1 to have the game dump frames and a log of what it did.
# There is no way to see the player's real screen from here, so when
# something only shows up on a real display, the game has to report on
# itself instead of being screenshotted.
DEBUG = os.environ.get("LE_DEBUG") == "1"
DEBUG_DIR = os.environ.get("LE_DEBUG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug"))


def _debug_log(msg):
    if not DEBUG:
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)
    with open(os.path.join(DEBUG_DIR, "debug.log"), "a") as f:
        f.write(msg + "\n")


class Game:
    def __init__(self):
        pygame.init()
        sfx.init()
        self.screen = pygame.display.set_mode((SCREEN_W * SCALE, SCREEN_H * SCALE))
        pygame.display.set_caption(TITLE)
        self.scene = pygame.Surface((SCREEN_W, SCREEN_H))
        self.fps_clock = pygame.time.Clock()
        self.tick = 0
        self.fullscreen = False

        self.world = World()
        self.player = self._spawn_player()
        self.minimap_base = self._build_minimap_base()
        self.minimap_fog = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        self.minimap_fog.fill((6, 6, 16, 255))
        # Reveal radius scales with the map, so a bigger city doesn't mean a
        # proportionally slower-clearing fog.
        self.minimap_reveal = self._build_minimap_reveal_mask(max(6, MAP_W // 11))
        self.minimap_size = self._minimap_size()
        self._reveal_minimap()
        self.dust_sprite = pygame.Surface((3, 3), pygame.SRCALPHA)
        pygame.draw.circle(self.dust_sprite, (255, 226, 168, 150), (1, 1), 1)

        self.zone_id = self.world.zone_at(self.player.x, self.player.y)
        self.transition = None

        # Weather. One condition at a time, re-rolled every few minutes with a
        # crossfade so it never snaps. Drops and fog banks are laid out once
        # here and animated by clock, which keeps the per-frame cost to blits.
        wr = random.Random(7)
        self.weather = "clear"
        self.weather_next = None
        self.weather_fade = 1.0
        self.weather_timer = wr.uniform(*self.WEATHER_EVERY)
        self.raindrops = [
            (wr.randrange(-60, SCREEN_W + 60), wr.randrange(0, SCREEN_H),
             wr.uniform(300.0, 460.0), wr.randrange(4, 10))
            for _ in range(110)
        ]
        self.fogbanks = [
            (wr.randrange(0, SCREEN_W), wr.randrange(30, SCREEN_H - 20), wr.uniform(6.0, 15.0))
            for _ in range(5)
        ]
        self.fog_blob = art.make_light(84, colour=(170, 174, 194), strength=120)

        self.npcs = {}
        # One persistent interactable dict per suspect, built once and reused
        # for their whole lifetime - floor switches and departures toggle its
        # membership in world.interactables and mutate its fields in place,
        # but never replace it. That's what lets a departure be found and
        # repurposed regardless of which floor is currently live, and stops
        # a floor-return or a run reset from ever creating a second, stale
        # duplicate of it.
        self.npc_interactable = {}
        for sid, spot in self.world.npc_spots.items():
            calm, broken = art.NPC_ART[SUSPECTS_BY_ID[sid]["sprite"]]
            self.npcs[sid] = NPC(sid, spot["x"], spot["y"], calm, broken)
            self.world.blockers.append(spot["blocker"])
            interactable = {
                "rect": spot["rect"],
                "title": SUSPECTS_BY_ID[sid]["name"],
                "body": None,
                "evidence": None,
                "npc": True,
                "suspect_id": sid,
            }
            self.world.interactables.append(interactable)
            self.npc_interactable[sid] = interactable

        self.box = ui.DialogBox()
        self.toast = ui.Toast()
        self.lights = {}

        self.ai = llm.Client()
        self.ai.check()

        if DEBUG:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            drivers = {
                k: os.environ.get(k)
                for k in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "SDL_RENDER_DRIVER")
            }
            _debug_log(
                f"--- start --- window={self.screen.get_size()} "
                f"internal={self.scene.get_size()} scale={SCALE} drivers={drivers} "
                f"pygame={pygame.version.ver} sdl={pygame.version.SDL}"
            )

        self.scanlines = self.build_scanlines()
        self.vignette = self.build_vignette()
        self.state = TITLE_SCREEN
        self.reset_run()

    def _spawn_player(self):
        tx, ty = CASE["meta"]["spawn"]
        return Player((tx + 0.5) * TILE, ty * TILE)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        names = {TITLE_SCREEN: "TITLE_SCREEN", PLAYING: "PLAYING", CASEFILE: "CASEFILE",
                  TALKING: "TALKING", ACCUSE: "ACCUSE", ENDING: "ENDING"}
        if DEBUG and getattr(self, "_state", None) != value:
            _debug_log(f"[{self.tick}] state -> {names.get(value, value)}")
        self._state = value

    # -- run state -----------------------------------------------------------

    def reset_run(self):
        # Rolled fresh every run, including a replay from the ending screen -
        # pick_culprit() restores whoever was guilty last time before picking
        # again, so their guilty text never leaks into a run where they're
        # innocent.
        pick_culprit()
        self.clock = clockmod.Clock()
        self.world.reset_floors()
        self.found = []  # evidence ids picked up in the world (or unlocked by dialogue)
        self.convo = {
            sid: {
                "presented": [],       # evidence ids put to this suspect
                "pressure": 0.0,
                "composure": "steady",
                "turns": 0,
                "history": [],         # chat messages for the model
                "log": [],             # (speaker, text) - first-time-talking marker
                "concepts": set(),     # Bricker only: which of the 3 ideas have landed
                "asked_directly": False,  # Doss/Ashworth only: was the right question ever asked
                "warned": set(),       # schedule warning thresholds already delivered
                "departed": False,     # left the map per their schedule, if they have one
                "last_typed": "",      # last real question the player typed (never a synthesized evidence string)
                "broken": False,       # evidence_plus_question only: has their durable statement page unlocked
            }
            for sid in SUSPECTS_BY_ID
        }
        self.active_suspect = None
        self.talk_mode = "read"  # read | input | evidence
        self.typed = ""
        self.ev_index = 0
        self.waiting_since = None
        self._pending_evidence_id = None
        self.ending = None
        self.casefile_page = 0
        self.accuse_index = 0
        self.accuse_confirm = None
        self.accuse_return = PLAYING
        self.pause_index = 0
        self.pause_showing_controls = False
        # A previous run may have repurposed a departed suspect's interactable
        # into their vacated-post text - put every one back to its talkable,
        # pristine state before the floor sync below decides who's live.
        for sid, it in self.npc_interactable.items():
            it["npc"] = True
            it["suspect_id"] = sid
            it["body"] = None
            it["evidence"] = None
        for zone, floor_name in self.world.floor_default.items():
            self._sync_floor_npcs(zone, floor_name)
        for npc in self.npcs.values():
            npc.mood = "steady"
            npc.shake = 0.0

    # -- helpers -------------------------------------------------------------

    @property
    def camera(self):
        cx = int(self.player.x) - SCREEN_W // 2
        cy = int(self.player.y) - SCREEN_H // 2
        cx = max(0, min(cx, MAP_W * TILE - SCREEN_W))
        cy = max(0, min(cy, MAP_H * TILE - SCREEN_H))
        return cx, cy

    @property
    def player_zone(self):
        """Which building the player is standing in, or None for outdoors.
        Read fresh rather than from `zone_id`, which only tracks movement so
        it can fire the entry cutscene."""
        return self.world.zone_at(self.player.x, self.player.y)

    def light(self, radius):
        if radius not in self.lights:
            self.lights[radius] = art.make_light(radius)
        return self.lights[radius]

    def _build_minimap_base(self):
        """One pixel per tile, coloured by ground kind. Built once — the map
        itself never changes, only how much of it the fog still hides."""
        colours = {
            "grass": GRASS, "hedge": HEDGE, "path": STONE_L, "wood": WOOD,
            "marble_d": MARBLE_D, "carpet": CARPET, "wall": WALL_D, "void": NIGHT,
        }
        surf = pygame.Surface((MAP_W, MAP_H))
        grid = self.world.grid
        for y in range(MAP_H):
            row = grid[y]
            for x in range(MAP_W):
                surf.set_at((x, y), colours.get(row[x], NIGHT))
        return surf

    def _build_minimap_reveal_mask(self, radius):
        """`art.make_light`'s falloff is tuned for room-sized lamps — at a
        radius this small it never reaches full alpha at its own centre, so
        the minimap here gets its own mask, solid through the middle with a
        soft rim, guaranteed to fully clear the fog at the point stood on."""
        size = radius * 2
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            for x in range(size):
                d = ((x - radius + 0.5) ** 2 + (y - radius + 0.5) ** 2) ** 0.5
                if d > radius:
                    continue
                t = max(0.0, (d - radius * 0.55) / (radius * 0.45))
                s.set_at((x, y), (0, 0, 0, int(255 * (1 - min(1.0, t)))))
        return s

    def _reveal_minimap(self):
        """Punch a permanent hole in the fog around wherever the player is
        standing right now. Subtracting alpha only ever removes fog, so
        ground once seen stays visible — ordinary fog-of-war."""
        r = self.minimap_reveal.get_width() // 2
        mx = int(self.player.x / TILE)
        my = int(self.player.y / TILE)
        self.minimap_fog.blit(self.minimap_reveal, (mx - r, my - r), special_flags=pygame.BLEND_RGBA_SUB)

    # The most screen the minimap may ever take, in scene pixels. Drawing it
    # one pixel per tile instead ties a HUD element's size to the size of the
    # city, so redrawing the map silently grows the thing covering the view.
    MINIMAP_MAX = (72, 56)

    def _minimap_size(self):
        fit = min(1.0, self.MINIMAP_MAX[0] / MAP_W, self.MINIMAP_MAX[1] / MAP_H)
        return max(1, int(MAP_W * fit)), max(1, int(MAP_H * fit))

    def draw_minimap(self):
        composite = self.minimap_base.copy()
        composite.blit(self.minimap_fog, (0, 0))
        mw, mh = self.minimap_size
        if (mw, mh) != (MAP_W, MAP_H):
            composite = pygame.transform.scale(composite, (mw, mh))
        # Markers go on after the scale, so shrinking can never erase a dot.
        sx, sy = mw / MAP_W, mh / MAP_H
        for npc in self.npcs.values():
            mx, my = int(npc.x / TILE), int(npc.y / TILE)
            if 0 <= mx < MAP_W and 0 <= my < MAP_H and self.minimap_fog.get_at((mx, my))[3] < 120:
                composite.fill(DANGER, (int(mx * sx), int(my * sy), 2, 2))
        px, py = int(self.player.x / TILE), int(self.player.y / TILE)
        if 0 <= px < MAP_W and 0 <= py < MAP_H:
            composite.fill(ACCENT, (int(px * sx), int(py * sy), 2, 2))
        ui.panel(self.scene, (6, 6, mw + 6, mh + 6), UI_BG, UI_LINE)
        self.scene.blit(composite, (9, 9))

    # -- weather -----------------------------------------------------------

    WEATHER_EVERY = (300.0, 600.0)  # seconds between rolls: 5 to 10 minutes
    WEATHER_FADE = 3.0

    def _update_weather(self, dt):
        if self.weather_next is None:
            self.weather_timer -= dt
            if self.weather_timer <= 0:
                # Late-night phases lean the roll toward rain/fog — never a
                # guarantee, just a thumb on the scale, so a clear midnight
                # still happens sometimes.
                options = [w for w in ("clear", "rain", "fog") if w != self.weather]
                bias = self.clock.phase["weather_bias"]
                weights = [max(0.15, 1.0 - bias) if w == "clear" else 1.0 + bias for w in options]
                self.weather_next = random.choices(options, weights=weights)[0]
            elif self.weather_fade < 1.0:
                self.weather_fade = min(1.0, self.weather_fade + dt / self.WEATHER_FADE)
            return
        # Fading the old condition out; the swap happens at the bottom of the dip.
        self.weather_fade -= dt / self.WEATHER_FADE
        if self.weather_fade <= 0.0:
            self.weather_fade = 0.0
            self.weather = self.weather_next
            self.weather_next = None
            self.weather_timer = random.uniform(*self.WEATHER_EVERY)

    def draw_weather(self):
        if self.weather == "clear" or self.weather_fade <= 0.02:
            return
        strength = self.weather_fade
        # Indoors you only catch it through the windows.
        if self.world.zone_at(self.player.x, self.player.y) is not None:
            strength *= 0.22
        layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        t = self.tick / 60.0

        if self.weather == "rain":
            span = SCREEN_H + 24
            colour = (168, 196, 224, int(150 * strength))
            for x0, y0, speed, length in self.raindrops:
                y = (y0 + t * speed) % span - 12
                x = (x0 + t * speed * 0.22) % (SCREEN_W + 80) - 40
                pygame.draw.line(layer, colour, (x, y), (x - 2, y - length))
        else:  # fog
            # A flat haze carries the condition; the banks give it movement.
            layer.fill((152, 158, 178, int(54 * strength)))
            self.fog_blob.set_alpha(int(255 * strength))
            r = self.fog_blob.get_width() // 2
            for x0, y0, speed in self.fogbanks:
                x = (x0 + t * speed) % (SCREEN_W + 2 * r) - r
                y = y0 + math.sin(t * 0.12 + x0) * 6
                layer.blit(self.fog_blob, (int(x) - r, int(y) - r))
        self.scene.blit(layer, (0, 0))

    # -- entering a building ---------------------------------------------

    TRANSITION_DURATIONS = {"out": 0.35, "hold": 1.1, "in": 0.35}

    def start_transition(self, zone_id):
        self.transition = {"zone": zone_id, "phase": "out", "t": 0.0}
        self.clock.advance(clockmod.COST_ENTER_BUILDING)
        sfx.play("open")

    def _update_transition(self, dt):
        tr = self.transition
        tr["t"] += dt
        if tr["t"] < self.TRANSITION_DURATIONS[tr["phase"]]:
            return
        tr["t"] = 0.0
        nxt = {"out": "hold", "hold": "in", "in": None}[tr["phase"]]
        if nxt is None:
            self.transition = None
        else:
            tr["phase"] = nxt

    def draw_transition(self):
        tr = self.transition
        dur = self.TRANSITION_DURATIONS[tr["phase"]]
        frac = min(1.0, tr["t"] / dur)
        if tr["phase"] == "out":
            alpha = int(255 * frac)
        elif tr["phase"] == "hold":
            alpha = 255
        else:
            alpha = int(255 * (1 - frac))
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((6, 6, 14, alpha))
        self.scene.blit(overlay, (0, 0))
        if alpha > 160:
            name, subtitle = self.world.zone_names[tr["zone"]]
            big = ui.font(14)
            w = big.size(name)[0]
            y = SCREEN_H // 2 - 14
            self.scene.blit(big.render(name, False, INK), (SCREEN_W // 2 - w // 2 + 2, y + 2))
            self.scene.blit(big.render(name, False, ACCENT), (SCREEN_W // 2 - w // 2, y))
            sw = ui.text_w(subtitle)
            ui.text(self.scene, subtitle, SCREEN_W // 2 - sw // 2, y + 20, UI_DIM)

    def available_evidence(self):
        return [EVIDENCE_BY_ID[e] for e in self.found]

    # -- interaction ---------------------------------------------------------

    def interact(self):
        target = self.world.interactable_near((self.player.x, self.player.y - 8), self.player_zone)
        if not target:
            return
        if target.get("npc"):
            self.begin_interview(target["suspect_id"])
            return

        if target.get("stairs"):
            # Costs what a doorway costs: a flight of stairs is traversal, and
            # the clock is the run's whole source of pressure - no other way
            # of moving through the city is free.
            self.clock.advance(clockmod.COST_ENTER_BUILDING)
            self.world.switch_floor(target["zone"], target["to_floor"])
            self._sync_floor_npcs(target["zone"], target["to_floor"])
            sfx.play("open")
            self.toast.show(target["title"].upper())
            return

        self.clock.advance(clockmod.COST_EXAMINE)
        eid = target.get("evidence")
        if eid and eid not in self.found:
            ev = EVIDENCE_BY_ID[eid]
            need = ev.get("requires")
            if need and need not in self.found:
                sfx.play("close")
                self.box.open(ev["locked_text"], target["title"])
                return
            self.found.append(eid)
            sfx.play("pickup")
            self.box.open(
                ev["found_text"],
                target["title"],
                on_close=lambda n=ev["name"]: self.toast.show(f"ADDED: {n.upper()}"),
            )
            return

        sfx.play("open")
        body = target["body"] or "Nothing more here."
        if eid:
            body = f"{EVIDENCE_BY_ID[eid]['name']} - already in your file."
        self.box.open(body, target["title"])

    # -- the interview -------------------------------------------------------

    def begin_interview(self, sid):
        if self.ai.status == "down":
            sfx.play("error")
            self.box.open(
                "They look at you and say nothing. " + self.ai.error +
                " Start LM Studio and load a chat model - the game keeps trying to "
                "reconnect on its own, so just try again once it's up.",
                "No connection",
            )
            return
        sfx.play("open")
        self.state = TALKING
        self.active_suspect = sid
        self.talk_mode = "read"
        c = self.convo[sid]
        lines = []
        if not c["log"]:
            lines.append(SUSPECTS_BY_ID[sid]["opener"])
        warning = self._due_warning(sid)
        if warning:
            lines.append(warning)
        if lines:
            self.say_suspect(sid, " ".join(lines))

    def _due_warning(self, sid):
        """The most urgent not-yet-delivered countdown line for a suspect on
        a schedule, or None. Phrased as a countdown rather than a time, so it
        stays useful to a player with no clock on screen. Marks every
        threshold up to and including the one returned as delivered, so a
        player who skips a visit never gets a stale earlier warning."""
        sched = SUSPECTS_BY_ID[sid].get("schedule")
        if not sched:
            return None
        c = self.convo[sid]
        warned = c.setdefault("warned", set())
        due = [(t, text) for t, text in sched["warnings"] if self.clock.minutes >= t and t not in warned]
        if not due:
            return None
        due.sort()
        for t, _ in due:
            warned.add(t)
        return due[-1][1]

    def _sync_floor_npcs(self, zone, floor_name):
        """A suspect confined to one floor of `zone` (via npc_spots'
        zone/home_floor) must vanish - sprite, blocker, and interactable -
        the instant the player is on any other floor of that building, and
        reappear on returning. Suspects with no zone (single-floor
        buildings) are untouched.

        The interactable's *presence* in the live list is floor-only: it
        stays scoped to the suspect's home floor even after they've departed
        and it's been repurposed into a vacated-post reveal, so that reveal
        doesn't leak onto every other floor of the building. The sprite and
        blocker additionally require they haven't departed - a gone suspect
        leaves no body behind, just the empty post."""
        for sid, spot in self.world.npc_spots.items():
            if spot.get("zone") != zone:
                continue
            on_home_floor = spot.get("home_floor") == floor_name
            it = self.npc_interactable[sid]
            it_live = it in self.world.interactables
            if on_home_floor and not it_live:
                self.world.interactables.append(it)
            elif not on_home_floor and it_live:
                World._drop(self.world.interactables, [it])

            should_show_sprite = on_home_floor and not self.convo[sid].get("departed")
            present = sid in self.npcs
            if should_show_sprite and not present:
                calm, broken = art.NPC_ART[SUSPECTS_BY_ID[sid]["sprite"]]
                self.npcs[sid] = NPC(sid, spot["x"], spot["y"], calm, broken)
                self.world.blockers.append(spot["blocker"])
            elif not should_show_sprite and present:
                self.npcs.pop(sid, None)
                if spot["blocker"] in self.world.blockers:
                    self.world.blockers.remove(spot["blocker"])

    def _update_departures(self):
        """Suspects on a schedule leave the map once their time comes, with
        an empty, examinable post left behind as the only explanation. Only
        checked while PLAYING (never mid-conversation) so a suspect can't be
        pulled out from under an interview in progress.

        This fires regardless of which floor the player is currently on -
        `_sync_floor_npcs` reads the fields set here through the same
        persistent interactable dict, so the vacated post shows up whenever
        the player is next on the suspect's home floor, never before and
        never on any other floor."""
        for sid, sched in ((s["id"], s.get("schedule")) for s in CASE["suspects"]):
            if not sched or self.convo[sid].get("departed"):
                continue
            if self.clock.minutes < sched["leaves_at"]:
                continue
            self.convo[sid]["departed"] = True
            spot = self.world.npc_spots[sid]
            self.npcs.pop(sid, None)
            if spot["blocker"] in self.world.blockers:
                self.world.blockers.remove(spot["blocker"])
            it = self.npc_interactable[sid]
            it["npc"] = False
            it["suspect_id"] = None
            it["body"] = sched["vacated"]
            it["evidence"] = None
            self.toast.show(f"{SUSPECTS_BY_ID[sid]['name'].upper()} HAS LEFT")

    def say_suspect(self, sid, line):
        self.convo[sid]["log"].append(("suspect", line))
        self.box.open(line, SUSPECTS_BY_ID[sid]["name"])

    # How much of the conversation is actually sent to the model each turn.
    # c["history"] itself is kept in full (the transcript view reads all of
    # it) - this only bounds what gets re-sent alongside the ~1000-token
    # system prompt, so a long interview doesn't grow the request forever.
    HISTORY_WINDOW = 16

    def send(self, user_text, evidence=None):
        sid = self.active_suspect
        c = self.convo[sid]
        c["turns"] += 1
        # Tracked so a turn that never gets an answer (error, or the player
        # cancels) can be unwound exactly - see _rollback_pending_turn.
        self._pending_evidence_id = evidence["id"] if evidence else None
        if evidence is None:
            # What the keyword backstops in `receive` scan. On an evidence
            # turn `user_text` below is a synthesized [EVIDENCE PRESENTED...]
            # string, not anything the player wrote - last_typed is left
            # untouched then, so a backstop always sees the last thing the
            # player actually said, never manufactured text.
            c["last_typed"] = user_text
        self.clock.advance(clockmod.COST_PRESENT if evidence else clockmod.COST_QUESTION)
        c["history"].append({"role": "user", "content": user_text})
        c["log"].append(("you", user_text))
        messages = [{"role": "system", "content": llm.system_prompt(sid, c, self.clock.phase)}]
        messages += c["history"][-self.HISTORY_WINDOW:]
        self.ai.ask(messages)
        self.waiting_since = pygame.time.get_ticks()
        self.talk_mode = "read"
        self.box.active = False
        if evidence:
            sfx.play("present")
        else:
            sfx.play("select")

    def present(self, ev):
        c = self.convo[self.active_suspect]
        if ev["id"] in c["presented"]:
            self.toast.show("ALREADY PRESENTED")
            sfx.play("error")
            return
        c["presented"].append(ev["id"])
        self.send(
            f"[EVIDENCE PRESENTED: {ev['name']}] {ev['summary']} "
            f"This contradicts: {ev['contradicts']}",
            evidence=ev,
        )

    def _rollback_pending_turn(self, sid):
        """Undo the bookkeeping `send()` did for a turn that will never get
        an answer - the model errored, or the player cancelled it. Puts the
        question, and any evidence presented with it, back exactly as if it
        had never been asked, so the player can just try again."""
        c = self.convo[sid]
        c["history"].pop()
        c["turns"] -= 1
        if self._pending_evidence_id:
            try:
                c["presented"].remove(self._pending_evidence_id)
            except ValueError:
                pass
        self._pending_evidence_id = None

    def receive(self, kind, payload):
        sid = self.active_suspect
        c = self.convo[sid]
        self.waiting_since = None
        if kind == "err":
            sfx.play("error")
            self._rollback_pending_turn(sid)
            c["log"].append(("system", payload))
            self.box.open(payload, "Connection")
            return

        s_name = SUSPECTS_BY_ID[sid]["name"]
        spoken, composure, delta, asked, concepts = llm.parse_tell(payload, s_name)
        if not spoken:
            # The model produced only a control line (or nothing at all) -
            # rendering that as an empty dialogue box left the player
            # staring at a blank panel with no explanation. Unwind the turn
            # exactly like a network error, rather than silently spending
            # it and the assistant's empty reply on nothing.
            sfx.play("error")
            self._rollback_pending_turn(sid)
            c["log"].append(("system", "The model gave a control line but no actual words."))
            self.box.open("They start to answer, then... nothing comes out. Try asking again.", "Connection")
            return
        self._pending_evidence_id = None
        # Store the cleaned reply, not the raw payload. A payload that broke
        # character - a fabricated detective line, a name label - would
        # otherwise sit in the history and be shown back to the model as its
        # own past behaviour on every later turn, teaching it the bad shape
        # and making the drift compound instead of staying a one-off. The
        # control line is deliberately left in: seeing its own past ones is
        # part of what keeps it emitting them.
        c["history"].append(
            {"role": "assistant", "content": llm.strip_speaker_labels(payload, s_name)}
        )

        s = SUSPECTS_BY_ID[sid]
        brk = s["break"]
        npc = self.npcs[sid]

        before = c["pressure"]
        # Late-night damping only slows what talk alone can earn - it never
        # touches the floor below, so a player who did the legwork is never
        # blocked by the hour, only one trying to talk their way there late.
        damped_delta = delta * self.clock.phase["damp"] if delta > 0 else delta
        c["pressure"] = max(0.0, min(100.0, c["pressure"] + damped_delta))
        # Hard evidence guarantees progress even if the model undersells it.
        floor = min(95.0, float(sum(EVIDENCE_BY_ID[e]["pressure"] for e in c["presented"])))
        c["pressure"] = max(c["pressure"], floor)

        if brk["type"] == "evidence_plus_question":
            if asked:
                c["asked_directly"] = True
            elif brk.get("angle_keywords"):
                # Deterministic backstop, same idea as Bricker's below: the
                # model's own asked=yes/no judgment is the only signal this
                # had before, and a model that never sets it to yes stalls
                # the suspect forever no matter how plainly the player asks.
                # A topic word plus a question word, anywhere in the text,
                # rather than an exact phrase - real phrasing reorders freely.
                # Scans only what the player actually typed - never the
                # synthesized [EVIDENCE PRESENTED...] string a present() turn
                # puts in history, which would otherwise grant this for free.
                user_text = c["last_typed"].lower()
                kw = brk["angle_keywords"]
                if any(t in user_text for t in kw["topic"]) and any(a in user_text for a in kw["ask"]):
                    c["asked_directly"] = True
            # Doss and Ashworth's break otherwise only changes their stance
            # text - resolve() never looks at it, so without this it pays out
            # nothing durable. First time both conditions hold, their
            # concession becomes a permanent case-file statement page.
            if not c["broken"] and brk["evidence"] in c["presented"] and c["asked_directly"]:
                c["broken"] = True
                self.toast.show(f"{s['name'].upper()} - STATEMENT ADDED TO CASE FILE")

        if brk["type"] == "conversational_trigger":
            c["concepts"] |= set(concepts)
            # Deterministic backstop: also scan what the PLAYER just typed, so
            # a model that forgets to self-report a concept it clearly heard
            # can't stall a deserving turn. Never the model's own reply, and
            # never a synthesized [EVIDENCE PRESENTED...] string either - a
            # present() turn must not silently hand him concepts he's
            # written to resist just because an exhibit's name/summary
            # happens to contain one of the backstop keywords.
            user_text = c["last_typed"].lower()
            for concept, keywords in brk["keyword_backstop"].items():
                if any(k in user_text for k in keywords):
                    c["concepts"].add(concept)
            complete = c["concepts"] >= set(brk["concepts"])
            if complete and "bricker-account" not in self.found:
                self.found.append("bricker-account")
                self.toast.show("ADDED: BRICKER'S ACCOUNT")
            have = len(c["concepts"] & set(brk["concepts"]))
            npc.mood = c["composure"] = (
                "cracking" if complete else "rattled" if have > 0 else "steady"
            )
        else:
            if composure in ("steady", "rattled", "cracking"):
                c["composure"] = composure
            else:
                c["composure"] = "cracking" if c["pressure"] >= 70 else "rattled" if c["pressure"] >= 35 else "steady"
            npc.mood = c["composure"]

        if c["pressure"] > before:
            npc.hit()
            sfx.play("hurt")
        self.say_suspect(sid, spoken)

    def resolve(self, accused_id):
        culprit = CASE["conviction"]["culprit"]
        strong = CASE["conviction"]["strong"]
        c = self.convo[culprit]

        if accused_id != culprit:
            shape = "wrong_suspect"
        else:
            hit = sum(1 for e in strong["pool"] if e in c["presented"])
            strong_case = hit >= strong["requires_count"] and c["pressure"] >= strong["minPressure"]
            shape = "correct_strong" if strong_case else "correct_thin"

        grade = caption = None
        if shape == "correct_strong":
            turns = c["turns"]
            if turns <= 10:
                grade, caption = "S", "SURGICAL"
            elif turns <= 16:
                grade, caption = "A", "SOLID POLICE WORK"
            elif turns <= 24:
                grade, caption = "B", "GOT THERE IN THE END"
            else:
                grade, caption = "C", "A LONG NIGHT"

        ending_def = CASE["endings"][shape]
        self.ending = {
            "shape": shape,
            "accused": accused_id,
            "grade": grade,
            "caption": caption or ending_def["caption"],
            "prose": ending_def["prose"],
            "closed_at": self.clock.hhmm,
        }
        self.ending_page = 0
        self.state = ENDING
        sfx.play("win" if shape == "correct_strong" else "lose")

    # -- input ---------------------------------------------------------------

    def on_key(self, e):
        if e.key == pygame.K_F11 or (e.key == pygame.K_RETURN and e.mod & pygame.KMOD_ALT):
            self.toggle_fullscreen()
            return
        if e.key == pygame.K_m:
            if self.state != TALKING or self.talk_mode != "input":
                self.toast.show("SOUND OFF" if sfx.toggle() else "SOUND ON")
                return

        if self.state == TITLE_SCREEN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                sfx.play("start")
                self.state = PLAYING
                self.box.open(CASE["meta"]["opening"], "Detective")
            elif e.key == pygame.K_ESCAPE:
                self.quit()
            return

        if self.state == ENDING:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.reset_run()
                self.player = self._spawn_player()
                self.zone_id = self.world.zone_at(self.player.x, self.player.y)
                self.transition = None
                self.state = TITLE_SCREEN
            elif e.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
                self.ending_page = 1 - self.ending_page
                sfx.play("move")
            elif e.key == pygame.K_ESCAPE:
                self.quit()
            return

        if self.state == ACCUSE:
            self.on_key_accuse(e)
            return

        if self.state == CASEFILE:
            if e.key in (pygame.K_TAB, pygame.K_ESCAPE):
                sfx.play("close")
                self.state = PLAYING
            elif e.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT):
                last = (
                    len(self.found) + self.CASEFILE_INTRO_PAGES
                    + len(self._transcript_pages()) + len(self._statement_pages()) - 1
                )
                self.casefile_page = min(last, self.casefile_page + 1)
                sfx.play("move")
            elif e.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT):
                self.casefile_page = max(0, self.casefile_page - 1)
                sfx.play("move")
            elif e.key == pygame.K_a:
                self.open_accuse(CASEFILE)
            return

        if self.state == TALKING:
            self.on_key_talking(e)
            return

        if self.state == PAUSED:
            self.on_key_paused(e)
            return

        # -- walking around
        if self.transition:
            return
        if self.box.active:
            if e.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.box.advance()
            return
        if e.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.interact()
        elif e.key == pygame.K_TAB:
            sfx.play("open")
            self.casefile_page = 0
            self.state = CASEFILE
        elif e.key == pygame.K_ESCAPE:
            self.open_pause()

    def open_accuse(self, return_to):
        self.accuse_index = 0
        self.accuse_confirm = None
        self.accuse_return = return_to
        self.state = ACCUSE
        sfx.play("select")

    def on_key_accuse(self, e):
        suspects = CASE["suspects"]
        if self.accuse_confirm is None:
            if e.key in (pygame.K_DOWN, pygame.K_s):
                self.accuse_index = (self.accuse_index + 1) % len(suspects)
                sfx.play("move")
            elif e.key in (pygame.K_UP, pygame.K_w):
                self.accuse_index = (self.accuse_index - 1) % len(suspects)
                sfx.play("move")
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.accuse_confirm = suspects[self.accuse_index]["id"]
                sfx.play("select")
            elif e.key in (pygame.K_TAB, pygame.K_ESCAPE):
                sfx.play("close")
                self.state = self.accuse_return
            return

        if e.key == pygame.K_y:
            self.resolve(self.accuse_confirm)
        elif e.key in (pygame.K_n, pygame.K_ESCAPE):
            self.accuse_confirm = None
            sfx.play("close")

    PAUSE_OPTIONS = ("RESUME", "CONTROLS", "QUIT")

    def open_pause(self):
        # Deliberately does NOT touch the clock - see the PAUSED note in
        # update(). Pausing only stops input, never the night.
        self.pause_index = 0
        self.pause_showing_controls = False
        self.state = PAUSED
        sfx.play("open")

    def on_key_paused(self, e):
        if self.pause_showing_controls:
            if e.key in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.pause_showing_controls = False
                sfx.play("close")
            return

        if e.key in (pygame.K_DOWN, pygame.K_s):
            self.pause_index = (self.pause_index + 1) % len(self.PAUSE_OPTIONS)
            sfx.play("move")
        elif e.key in (pygame.K_UP, pygame.K_w):
            self.pause_index = (self.pause_index - 1) % len(self.PAUSE_OPTIONS)
            sfx.play("move")
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            choice = self.PAUSE_OPTIONS[self.pause_index]
            if choice == "RESUME":
                self.state = PLAYING
                sfx.play("close")
            elif choice == "CONTROLS":
                self.pause_showing_controls = True
                sfx.play("open")
            else:  # QUIT
                self.quit()
        elif e.key == pygame.K_ESCAPE:
            self.state = PLAYING
            sfx.play("close")

    def on_key_talking(self, e):
        if self.talk_mode == "input":
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                q = self.typed.strip()
                if q and not self.ai.busy:
                    self.typed = ""
                    self.send(q)
                return
            if e.key == pygame.K_BACKSPACE:
                self.typed = self.typed[:-1]
                return
            if e.key == pygame.K_ESCAPE:
                self.talk_mode = "read"
                sfx.play("close")
            return

        if self.talk_mode == "evidence":
            items = self.available_evidence()
            if e.key in (pygame.K_DOWN, pygame.K_s):
                self.ev_index = (self.ev_index + 1) % max(1, len(items))
                sfx.play("move")
            elif e.key in (pygame.K_UP, pygame.K_w):
                self.ev_index = (self.ev_index - 1) % max(1, len(items))
                sfx.play("move")
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and items and not self.ai.busy:
                self.present(items[self.ev_index])
            elif e.key in (pygame.K_TAB, pygame.K_ESCAPE):
                self.talk_mode = "read"
                sfx.play("close")
            return

        # read mode
        if self.box.active and self.box.advance():
            return
        if self.ai.busy:
            if e.key == pygame.K_ESCAPE:
                self.ai.cancel()
                self._rollback_pending_turn(self.active_suspect)
                self.waiting_since = None
                self.toast.show("QUESTION CANCELLED")
                sfx.play("close")
            return
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e, pygame.K_SPACE):
            self.talk_mode = "input"
            sfx.play("open")
        elif e.key == pygame.K_TAB:
            if self.found:
                self.ev_index = min(self.ev_index, len(self.found) - 1)
                self.talk_mode = "evidence"
                sfx.play("open")
            else:
                self.toast.show("NOTHING IN THE FILE YET")
                sfx.play("error")
        elif e.key == pygame.K_a:
            self.open_accuse(TALKING)
        elif e.key == pygame.K_ESCAPE:
            self.state = PLAYING
            self.box.active = False
            sfx.play("close")

    def on_text(self, e):
        if self.state == TALKING and self.talk_mode == "input" and len(self.typed) < 90:
            self.typed += e.text

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN | pygame.SCALED if self.fullscreen else 0
        self.screen = pygame.display.set_mode((SCREEN_W * SCALE, SCREEN_H * SCALE), flags)
        self.scanlines = self.build_scanlines()
        self.vignette = self.build_vignette()

    def quit(self):
        pygame.quit()
        sys.exit(0)

    # -- update --------------------------------------------------------------

    def update(self, dt):
        self.tick += 1
        self.box.update(dt)
        self.toast.update(dt)
        for npc in self.npcs.values():
            npc.update(dt)

        result = self.ai.poll()
        if result:
            self.receive(*result)

        # Keep trying to reach the model in the background whenever it isn't
        # reachable, so starting LM Studio after the game launches recovers
        # on its own instead of requiring a restart. check() no-ops while a
        # check is already in flight, so this is safe to call every ~4s.
        if self.ai.status != "ok" and self.tick % (FPS * 4) == 0:
            self.ai.check()

        # Weather is cosmetic and runs wherever the world is visible.
        if self.state in (PLAYING, TALKING, PAUSED):
            self._update_weather(dt)

        # The clock is mechanical, so it's gated more carefully. PAUSED,
        # CASEFILE and ACCUSE all deliberately keep ticking - none of them
        # may be a way to buy free thinking time against the night clock,
        # and the case file in particular is exactly where a player plans
        # their next move. TALKING ticks too, but only while the player is
        # the one taking the time: reading a reply, typing the next
        # question, browsing evidence. It stops dead while a request is in
        # flight, because a local model can take anywhere from five seconds
        # to two minutes to answer and none of that is the player's doing -
        # charging for it made how much night you had left a function of
        # your hardware.
        if self.state in (PLAYING, PAUSED, CASEFILE, ACCUSE) or (self.state == TALKING and not self.ai.busy):
            self.clock.tick(dt)

        if self.state == PLAYING:
            self._update_departures()

        if self.transition:
            self._update_transition(dt)
            self.player.moving = False
            return

        if self.state != PLAYING or self.box.active:
            self.player.moving = False
            return

        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        running = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        was = int(self.player.frame)
        self.player.update(dt, dx, dy, self.world, running)
        if self.player.moving and int(self.player.frame) != was and int(self.player.frame) % 2 == 1:
            sfx.play("step")
        if self.player.moving:
            self._reveal_minimap()
            new_zone = self.world.zone_at(self.player.x, self.player.y)
            if new_zone != self.zone_id:
                if new_zone is not None:
                    self.start_transition(new_zone)
                self.zone_id = new_zone

    # -- draw ----------------------------------------------------------------

    def draw_world(self):
        cam = self.camera
        s = self.scene
        s.blit(self.world.floor, (-cam[0], -cam[1]))

        view = pygame.Rect(cam[0] - 64, cam[1] - 64, SCREEN_W + 128, SCREEN_H + 128)
        drawables = [
            (sort_y, surf, x, y)
            for surf, x, y, sort_y in self.world.objects
            if view.collidepoint(x + surf.get_width() // 2, y + surf.get_height() // 2)
        ]
        drawables.sort(key=lambda d: d[0])

        entities = [(self.player.sort_y, "player", None)]
        entities += [(npc.sort_y, "npc", npc) for npc in self.npcs.values()]
        merged = sorted(
            [(d[0], "obj", d) for d in drawables] + entities,
            key=lambda m: m[0],
        )
        for _, kind, data in merged:
            if kind == "obj":
                _, surf, x, y = data
                s.blit(surf, (x - cam[0], y - cam[1]))
            elif kind == "player":
                self.player.draw(s, cam)
            else:
                data.draw(s, cam, self.tick)

        # Roofs go on last, over the room and anyone standing in it — every
        # building except the one the player is inside.
        t = self.tick / 60.0
        here = self.player_zone
        roofed = [z for z in self.world.roofs if z != here]
        for zone in roofed:
            roof, wx, wy = self.world.roofs[zone]
            s.blit(roof, (wx - cam[0], wy - cam[1]))

        # Overhead wires, drawn above the roofs because that is where they run.
        # Each span sags in the middle, which is the whole character of them.
        for (ax, ay), (bx, by) in self.world.wires:
            x1, y1 = ax - cam[0], ay - cam[1]
            x2, y2 = bx - cam[0], by - cam[1]
            if max(x1, x2) < -20 or min(x1, x2) > SCREEN_W + 20:
                continue
            pts = []
            for i in range(7):
                f = i / 6
                sag = math.sin(f * math.pi) * 5
                pts.append((x1 + (x2 - x1) * f, y1 + (y2 - y1) * f + sag))
            pygame.draw.lines(s, (26, 24, 32), False, pts, 1)

        # Smoke, only from the chimneys of buildings currently wearing a roof.
        for cx, cy, zone in self.world.chimneys:
            if zone == here:
                continue
            for i in range(4):
                age = (t * 0.55 + i * 0.25) % 1.0
                puff = int(2 + age * 4)
                sx = cx - cam[0] + int(math.sin(age * 5 + i) * 4)
                sy = cy - cam[1] - int(age * 26)
                smoke = pygame.Surface((puff * 2, puff * 2), pygame.SRCALPHA)
                pygame.draw.circle(smoke, (188, 184, 180, int(120 * (1 - age))),
                                   (puff, puff), puff)
                s.blit(smoke, (sx - puff, sy - puff))

        # Standing at the foot of a building, a 23px sprite reaches up into the
        # roof above it and vanishes. Anyone outdoors who overlaps a roof this
        # way gets redrawn on top of the shingles: they are in front of the
        # building, not inside it.
        def _under_roof(cx, cy, half_w=8, height=24):
            for tx in range(int(cx - half_w) // TILE, int(cx + half_w) // TILE + 1):
                for ty in range(int(cy - height) // TILE, int(cy) // TILE + 1):
                    for zone in roofed:
                        if (tx, ty) in self.world.zone_tiles[zone]:
                            return True
            return False

        if here is None and _under_roof(self.player.x, self.player.y, 8, self.player.H):
            self.player.draw(s, cam)
        for npc in self.npcs.values():
            if self.world.zone_at(npc.x, npc.y) is None and _under_roof(npc.x, npc.y):
                npc.draw(s, cam, self.tick)

        # Night, punched through by every lamp in range. How dark it gets,
        # and how many lamps still work, both come from the clock's phase —
        # the only way the player ever reads the hour is by feel.
        night = self.clock.phase
        dark = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dark.fill((*night["tint"], night["dark_alpha"]))
        for lx, ly, r in self.world.lights:
            # A lamp's survival is hashed from its position, not rolled per
            # frame, so a dead lamp stays dead instead of strobing.
            if (int(lx) * 92821 + int(ly) * 68917) % 100 >= night["lamp_frac"] * 100:
                continue
            # A lamp under a roof you are not standing under stays hidden,
            # otherwise its pool glows through the shingles.
            lz = self.world.zone_at(lx, ly)
            if lz is not None and lz != here:
                continue
            if abs(lx - cam[0] - SCREEN_W // 2) > SCREEN_W // 2 + r:
                continue
            if abs(ly - cam[1] - SCREEN_H // 2) > SCREEN_H // 2 + r:
                continue
            # A gentle, never-quite-steady flicker — each lamp gets its own
            # phase from its position, so a whole street doesn't pulse in
            # lockstep like one broken bulb.
            phase = ((lx * 7 + ly * 13) % 97) / 97.0 * math.tau
            wobble = math.sin(self.tick * 0.05 + phase) + 0.4 * math.sin(self.tick * 0.11 + phase * 2)
            rr = r + (2 if wobble > 0.5 else -2 if wobble < -0.5 else 0)
            dark.blit(self.light(rr), (lx - rr - cam[0], ly - rr - cam[1]), special_flags=pygame.BLEND_RGBA_SUB)

            # Dust, backlit by the lamp, drifting up out of its pool of light.
            rng = random.Random(int(lx) * 92821 + int(ly))
            for _ in range(4):
                mphase = rng.uniform(0, math.tau)
                speed = rng.uniform(5, 10)
                cycle = r * 1.1
                y_off = r * 0.5 - (t * speed + mphase * 6) % cycle
                x_off = rng.uniform(-r * 0.45, r * 0.45) + math.sin(t * 0.7 + mphase) * 3
                dark.blit(
                    self.dust_sprite,
                    (int(lx + x_off - cam[0]) - 1, int(ly + y_off - cam[1]) - 1),
                    special_flags=pygame.BLEND_RGBA_ADD,
                )
        dark.blit(
            self.light(40),
            (int(self.player.x) - 40 - cam[0], int(self.player.y) - 48 - cam[1]),
            special_flags=pygame.BLEND_RGBA_SUB,
        )
        s.blit(dark, (0, 0))
        self.draw_weather()

    def draw_hud(self):
        s = self.scene
        self.draw_minimap()

        if self.state == PLAYING and not self.box.active:
            t = self.world.interactable_near((self.player.x, self.player.y - 8), self.player_zone)
            if t:
                cam = self.camera
                # Stairs get their own verb: pressing E there moves the player
                # to another floor, which "LOOK" gives no warning of - and the
                # prompt is the only thing advertising that a second floor is
                # down there at all.
                verb = "E  TALK" if t.get("npc") else "E  STAIRS" if t.get("stairs") else "E  LOOK"
                ui.prompt(s, verb,
                          int(t["rect"].centerx) - cam[0], int(t["rect"].top) - cam[1] - 18)
            ui.text(s, "TAB  CASE FILE", 6, SCREEN_H - 12, UI_FAINT)

    def draw_talk(self):
        s = self.scene
        sid = self.active_suspect
        suspect = SUSPECTS_BY_ID[sid]
        c = self.convo[sid]
        name = suspect["name"].upper()
        label = {"steady": "CALM", "rattled": "RATTLED", "cracking": "CRACKING"}[c["composure"]]
        col = {"steady": UI_DIM, "rattled": ACCENT, "cracking": DANGER}[c["composure"]]
        if c["composure"] == "cracking" and (self.tick // 16) % 2 == 0:
            col = UI_TEXT

        # Header: name on the left, a progress read-out on the right. The
        # name is clipped to whatever that leaves, so a long rank never runs
        # under it. Bricker's own pressure is pinned at +0 by design (nothing
        # moves him but understanding, see llm.py's conversational_trigger
        # stance) - showing that percentage would just read as a broken
        # meter, so he gets a concepts-held count instead.
        ui.panel(s, (6, 6, SCREEN_W - 12, 20), UI_BG, UI_LINE)
        ui.text(s, name[: (SCREEN_W - 162) // 8], 12, 10, UI_TEXT)
        brk = suspect["break"]
        if brk["type"] == "conversational_trigger":
            total = len(brk["concepts"])
            have = len(c["concepts"] & set(brk["concepts"]))
            ui.meter(s, SCREEN_W - 128, 9, have / total * 100 if total else 0)
            ui.text(s, f"{have}/{total}", SCREEN_W - 40, 10, UI_DIM)
        else:
            ui.meter(s, SCREEN_W - 128, 9, c["pressure"])
            ui.text(s, f"{int(c['pressure']):3d}%", SCREEN_W - 40, 10, UI_DIM)

        # Portrait, reacting to composure. It borrows the world sprite's shake
        # so a landed piece of evidence hits the face as well as the body.
        portrait = art.PORTRAITS[sid][c["composure"]]
        ox = (1 if (self.tick // 2) % 2 else -1) if self.npcs[sid].shake > 0 else 0
        ui.panel(s, (8, 30, 68, 76), UI_BG, UI_LINE)
        s.blit(portrait, (18 + ox, 34))
        ui.text(s, label, 8 + (68 - ui.text_w(label)) // 2, 90, col)

        if self.ai.busy:
            secs = (pygame.time.get_ticks() - (self.waiting_since or 0)) // 1000
            dots = "." * (1 + (self.tick // 24) % 3)
            ui.panel(s, (12, SCREEN_H - 66, SCREEN_W - 24, 58))
            ui.text(s, f"THINKING{dots}", 20, SCREEN_H - 46, UI_DIM)
            ui.text(s, f"{secs}s", 20, SCREEN_H - 32, UI_FAINT)
            return

        if self.talk_mode == "evidence":
            items = self.available_evidence()
            # Capped rather than growing with the exhibit count (a case with
            # more items would otherwise push this panel up through the
            # portrait), and scrolled to keep the selection in view. The
            # panel is bottom-anchored (ui.panel's y is SCREEN_H - h - 8), so
            # a fixed block reserved below the list - for the "contradicts"
            # preview - sits at the same absolute position regardless of how
            # many rows are visible; only the top edge moves.
            MAX_VISIBLE = 4
            PREVIEW_BLOCK = 40
            start = 0
            if len(items) > MAX_VISIBLE:
                start = max(0, min(self.ev_index - MAX_VISIBLE // 2, len(items) - MAX_VISIBLE))
            visible = items[start:start + MAX_VISIBLE]
            list_h = len(visible) * 12
            h = 22 + list_h + PREVIEW_BLOCK
            top = SCREEN_H - h - 8
            ui.panel(s, (12, top, SCREEN_W - 24, h))
            ui.text(s, "PRESENT WHAT?", 20, top + 8, ACCENT)
            for i, ev in enumerate(visible):
                real_i = start + i
                y = top + 24 + i * 12
                sel = real_i == self.ev_index
                done = ev["id"] in c["presented"]
                if sel:
                    pygame.draw.rect(s, UI_BG_2, (16, y - 2, SCREEN_W - 32, 12))
                    ui.text(s, ">", 18, y, ACCENT)
                ui.text(s, ev["name"][:34], 28, y, UI_FAINT if done else (UI_TEXT if sel else UI_DIM))
            # The thing a player actually needs mid-argument - previously
            # visible only in the case file, which meant leaving the
            # interrogation entirely to go re-read what an exhibit contradicts.
            py = top + 24 + list_h + 4
            for line in ui.wrap(items[self.ev_index]["contradicts"], SCREEN_W - 40)[:2]:
                ui.text(s, line, 20, py, ACCENT)
                py += 10
            ui.text(s, "ENTER PRESENT   TAB BACK", 20, SCREEN_H - 14, UI_FAINT)
            return

        if self.talk_mode == "input":
            ui.panel(s, (12, SCREEN_H - 40, SCREEN_W - 24, 32))
            shown = "> " + self.typed[-40:]
            ui.text(s, shown, 20, SCREEN_H - 32, UI_TEXT)
            ui.caret(s, 20 + ui.text_w(shown) + 1, SCREEN_H - 32, self.tick)
            ui.text(s, "ENTER ASK    ESC BACK", 20, SCREEN_H - 18, UI_FAINT)
            return

        self.box.draw(s, self.tick)
        if not self.box.active:
            ui.panel(s, (12, SCREEN_H - 30, SCREEN_W - 24, 22))
            hint = "ENTER ASK   TAB PRESENT   A ACCUSE   ESC LEAVE"
            ui.text(s, hint, 20, SCREEN_H - 23, UI_FAINT)

    def draw_accuse(self):
        s = self.scene
        suspects = CASE["suspects"]

        if self.accuse_confirm is None:
            ui.terminal_frame(s, "HRPD // FILE CHARGES", self.tick, "ENTER ACCUSE   TAB BACK")
            y = self._section("NAME ONE", 28)
            for i, sp in enumerate(suspects):
                sel = i == self.accuse_index
                # Was `[0]` (first wrapped line only) at a fixed 26px box
                # height - silently dropped the tail of any role too long
                # for one line (Doss's "...Depot", Bricker's "...oldest
                # friend"). The box grows to fit however many lines wrap.
                role_lines = ui.wrap(sp["role"], SCREEN_W - 40)
                box_h = 16 + len(role_lines) * 10
                if sel:
                    pygame.draw.rect(s, UI_BG_2, (12, y - 3, SCREEN_W - 24, box_h))
                    pygame.draw.rect(s, UI_LINE, (12, y - 3, SCREEN_W - 24, box_h), 1)
                    ui.text(s, ">", 16, y + 2, ACCENT)
                ui.text(s, sp["name"], 26, y, UI_TEXT if sel else UI_DIM)
                ry = y + 11
                for line in role_lines:
                    ui.text(s, line, 26, ry, UI_FAINT)
                    ry += 10
                y += box_h + 4
            return

        accused = SUSPECTS_BY_ID[self.accuse_confirm]
        ui.terminal_frame(s, "HRPD // CONFIRM", self.tick, "Y  ACCUSE      N  NOT YET")
        ui.header(s, f"ACCUSE {accused['name'].upper()}?", 14, 30, DANGER)
        y = 52
        for line in ui.wrap(
            "This is your one shot. Once you name someone, the case closes tonight, "
            "for better or worse.",
            SCREEN_W - 40,
        ):
            ui.text(s, line, 18, y, UI_DIM)
            y += 11
        # Committing here is irreversible with nothing else on screen to
        # decide from - a bare minimum of the state that actually matters.
        y += 6
        shown = len(self.convo[self.accuse_confirm]["presented"])
        ui.text(s, f"EXHIBITS FOUND: {len(self.found)}/{len(CASE['evidence'])}", 18, y, UI_FAINT)
        y += 11
        ui.text(s, f"SHOWN TO {accused['name'].upper()}: {shown}", 18, y, UI_FAINT)

    def draw_paused(self):
        s = self.scene

        if self.pause_showing_controls:
            ui.terminal_frame(s, "HRPD // CONTROLS", self.tick, "ENTER / TAB / ESC   BACK")
            y = self._section("HOW TO PLAY", 28)
            lines = [
                ("WASD / ARROWS", "MOVE"),
                ("SHIFT", "RUN"),
                ("E / SPACE / ENTER", "LOOK, TALK, ADVANCE TEXT"),
                ("TAB", "CASE FILE   (PRESENT EVIDENCE, MID-TALK)"),
                ("A", "ACCUSE"),
                ("ESC", "BACK, CANCEL A QUESTION, OR PAUSE"),
                ("F11", "FULLSCREEN"),
                ("M", "SOUND"),
            ]
            # Column start was 110px - narrower than "E / SPACE / ENTER"
            # itself (136px), so the longest keys ran straight into their
            # own description text ("ARROWS" into "MOVE", "ENTER" into
            # "LOOK..."). DESC_X clears the widest key in this list; the
            # description wraps rather than assuming one line, since the
            # longest ones (e.g. TAB's) ran off the right edge otherwise.
            DESC_X = 164
            for key, what in lines:
                ui.text(s, key, 20, y, ACCENT)
                wrapped = ui.wrap(what, SCREEN_W - DESC_X - 14)
                for i, line in enumerate(wrapped):
                    ui.text(s, line, DESC_X, y + i * 10, UI_DIM)
                y += max(12, len(wrapped) * 10) + 2
            return

        ui.terminal_frame(s, "HRPD // STAND BY", self.tick, "ENTER SELECT   ESC RESUME")
        y = self._section("PAUSED", 28)
        ui.text(s, "The night keeps moving. Nobody waits for you.", 14, y, UI_FAINT)
        y += 20
        for i, label in enumerate(self.PAUSE_OPTIONS):
            sel = i == self.pause_index
            if sel:
                pygame.draw.rect(s, UI_BG_2, (12, y - 3, SCREEN_W - 24, 18))
                pygame.draw.rect(s, UI_LINE, (12, y - 3, SCREEN_W - 24, 18), 1)
                ui.text(s, ">", 16, y + 1, ACCENT)
            ui.text(s, label, 26, y + 1, UI_TEXT if sel else UI_DIM)
            y += 22

    def _draw_wrapped(self, lines, x, y, colour=UI_TEXT):
        """Draw wrapped lines one per row, clamped to whatever space remains
        above the footer rule. draw_ending already did this by hand for the
        one place a long case-authored string was known to risk overflow;
        case.py is the file the README advertises as swappable for a new
        case, so every wrap loop reading from it gets the same guarantee -
        a longer fact or exhibit silently loses its tail instead of
        spilling text through the footer chrome."""
        room = max(0, (SCREEN_H - 26 - y) // 10)
        for line in lines[:room]:
            ui.text(self.scene, line, x, y, colour)
            y += 10
        return y

    def _section(self, label, y):
        """An amber section header with a rule running out to the margin."""
        s = self.scene
        ui.text(s, label, 14, y, ACCENT)
        pygame.draw.line(s, UI_LINE, (18 + ui.text_w(label), y + 4), (SCREEN_W - 15, y + 4))
        return y + 12

    # Pages before the exhibits: briefing (the opening, re-readable), the
    # scene, the timeline, established facts, then the existing
    # victim/suspects roster. Everything here was already written in
    # case.py and fed to the model - none of it reached the player before.
    CASEFILE_INTRO_PAGES = 5

    # How many transcript lines fit between the header and footer chrome.
    LOG_LINES_PER_PAGE = 18

    def _transcript_pages(self):
        """Every suspect who's been talked to gets their full exchange log
        flattened and chunked into fixed-size pages, in suspect order - a
        long interview simply spans more pages rather than being silently
        clamped (main.py used to write c["log"] and never read it back).
        Recomputed on demand: conversations are short, and this only runs
        while the case file is open."""
        pages = []
        for sp in CASE["suspects"]:
            sid = sp["id"]
            log = [entry for entry in self.convo[sid]["log"] if entry[0] != "system"]
            if not log:
                continue
            # Every element here is exactly one on-screen row - a tag gets
            # its own row rather than sharing one with the first wrapped
            # line, so chunking by row count below can never under-count
            # what the draw loop actually renders.
            lines = []
            for speaker, text_ in log:
                tag = "YOU" if speaker == "you" else sp["name"].upper()
                lines.append(("tag", tag))
                for line in ui.wrap(text_, SCREEN_W - 40) or [""]:
                    lines.append(("text", line))
            chunks = [lines[i:i + self.LOG_LINES_PER_PAGE] for i in range(0, len(lines), self.LOG_LINES_PER_PAGE)]
            for i, chunk in enumerate(chunks):
                pages.append({"sid": sid, "part": i + 1, "total": len(chunks), "lines": chunk})
        return pages

    def _statement_pages(self):
        """sids whose evidence_plus_question break has been earned - see the
        `c["broken"]` note in receive(). Doss and Ashworth only; Thorne's
        confession is the ending itself, and Bricker already yields evidence."""
        return [
            sp["id"] for sp in CASE["suspects"]
            if sp["break"]["type"] == "evidence_plus_question" and self.convo[sp["id"]]["broken"]
        ]

    def draw_casefile(self):
        s = self.scene
        tpages = self._transcript_pages()
        spages = self._statement_pages()
        total = len(self.found) + self.CASEFILE_INTRO_PAGES + len(tpages) + len(spages)
        footer = f"{self.casefile_page + 1}/{total}   ARROWS PAGE   A ACCUSE   TAB CLOSE"
        page = self.casefile_page

        if page == 0:
            ui.terminal_frame(s, "HRPD // BRIEFING", self.tick, footer)
            y = self._section("00:12 - THE CALL", 28)
            self._draw_wrapped(ui.wrap(CASE["meta"]["opening"], SCREEN_W - 40), 18, y)
            return

        if page == 1:
            ui.terminal_frame(s, "HRPD // THE SCENE", self.tick, footer)
            y = self._section("SCENE", 28)
            self._draw_wrapped(ui.wrap(CASE["scene"], SCREEN_W - 40), 18, y)
            return

        if page == 2:
            ui.terminal_frame(s, "HRPD // TIMELINE", self.tick, footer)
            y = self._section("TIMELINE", 28)
            for when, what in CASE["timeline"]:
                if y > SCREEN_H - 30:
                    break
                ui.text(s, when, 18, y, ACCENT)
                y += 10
                y = self._draw_wrapped(ui.wrap(what, SCREEN_W - 44), 24, y, UI_DIM)
                y += 3
            return

        if page == 3:
            ui.terminal_frame(s, "HRPD // ESTABLISHED FACTS", self.tick, footer)
            y = self._section("WHAT'S KNOWN - CAN'T BE CONTRADICTED", 28)
            for fact in CASE["facts"]:
                if y > SCREEN_H - 30:
                    break
                y = self._draw_wrapped(ui.wrap(f"- {fact}", SCREEN_W - 40), 18, y)
            return

        if page == 4:
            ui.terminal_frame(s, "HRPD // CASE FILE 44-C", self.tick, footer)
            y = self._section("VICTIM", 28)
            y = self._draw_wrapped(
                ui.wrap(f"{CASE['victim']['name']}. {CASE['victim']['detail']}", SCREEN_W - 40), 18, y
            )
            y = self._section("SUSPECTS", y + 6)
            for sp in CASE["suspects"]:
                if y > SCREEN_H - 30:
                    break
                ui.text(s, sp["name"], 18, y, UI_TEXT)
                y += 10
                # Was `[0]` (first wrapped line only), which silently
                # dropped the tail of any role too long for one line - e.g.
                # Bricker's "- Thorne's oldest friend" never showed at all.
                y = self._draw_wrapped(ui.wrap(sp["role"], SCREEN_W - 34), 18, y, UI_FAINT)
                y += 2
            return

        exhibit_end = self.CASEFILE_INTRO_PAGES + len(self.found)
        if page < exhibit_end:
            exhibit_num = page - self.CASEFILE_INTRO_PAGES + 1
            ev = EVIDENCE_BY_ID[self.found[page - self.CASEFILE_INTRO_PAGES]]
            ui.terminal_frame(s, f"HRPD // EXHIBIT {exhibit_num}", self.tick, footer)
            ui.text(s, ev["name"].upper()[:36], 14, 28, UI_TEXT)
            y = self._draw_wrapped(ui.wrap(ev["detail"], SCREEN_W - 40), 18, 44)
            y = self._section("CONTRADICTS", y + 6)
            self._draw_wrapped(ui.wrap(ev["contradicts"], SCREEN_W - 40), 18, y, ACCENT)
            if any(ev["id"] in c["presented"] for c in self.convo.values()):
                ui.text(s, "[ PRESENTED ]", 14, SCREEN_H - 34, GREEN)
            return

        transcript_end = exhibit_end + len(tpages)
        if page < transcript_end:
            # Transcript pages - what a suspect actually said, the thing the
            # player is asked to catch contradicting itself and previously had
            # no way to check back against once a line scrolled off the box.
            tp = tpages[page - exhibit_end]
            name = SUSPECTS_BY_ID[tp["sid"]]["name"].upper()
            prefix = "HRPD // TRANSCRIPT - "
            suffix = f" ({tp['part']}/{tp['total']})" if tp["total"] > 1 else ""
            # A long full rank+name (Thorne's, worst case) can outrun the
            # title bar and run past the frame's edge - trim the name, never
            # the (part/total) suffix, since that's what matters most for
            # paging through a multi-part transcript.
            room = SCREEN_W - 40 - ui.text_w(prefix) - ui.text_w(suffix)
            full_name = name
            while name and ui.text_w(name) > room:
                name = name[:-1]
            if name != full_name and " " in name:
                name = name.rsplit(" ", 1)[0]  # back up to a whole word
            ui.terminal_frame(s, prefix + name + suffix, self.tick, footer)
            y = 28
            for kind, value in tp["lines"]:
                if kind == "tag":
                    ui.text(s, value, 14, y, ACCENT if value == "YOU" else UI_TEXT)
                else:
                    ui.text(s, value, 20, y, UI_DIM)
                y += 10
            return

        # Statement pages - Doss/Ashworth's evidence_plus_question break
        # otherwise changes only their stance text and pays out nothing
        # resolve() or the player ever sees. See the "broken" note in
        # receive(). Deliberately not part of any conviction math.
        sid = spages[page - transcript_end]
        sp = SUSPECTS_BY_ID[sid]
        ui.terminal_frame(s, f"HRPD // STATEMENT - {sp['name'].upper()}", self.tick, footer)
        y = self._section("WHAT THEY ADMITTED", 28)
        for line in ui.wrap(sp["concession"], SCREEN_W - 40):
            ui.text(s, line, 18, y)
            y += 10

    def draw_title(self):
        s = self.scene
        s.fill(UI_BG)
        for y in range(0, SCREEN_H, 2):
            pygame.draw.line(s, (27, 21, 18), (0, y), (SCREEN_W, y))
        boot = "HARROW'S REACH P.D.  //  CASE 44-C"
        ui.text(s, boot, (SCREEN_W - ui.text_w(boot)) // 2, 12, UI_FAINT)
        big = ui.font(20)
        for i, word in enumerate(CASE["meta"]["title_lines"]):
            w = big.size(word)[0]
            x = (SCREEN_W - w) // 2
            y = 26 + i * 26
            s.blit(big.render(word, False, INK), (x + 3, y + 3))
            s.blit(big.render(word, False, ACCENT if i else UI_TEXT), (x, y))
        subtitle = CASE["meta"]["subtitle"]
        ui.text(s, subtitle, (SCREEN_W - ui.text_w(subtitle)) // 2, 84, UI_FAINT)

        frame = self.player.frames["down"][(self.tick // 14) % 4]
        big_sprite = pygame.transform.scale(frame, (frame.get_width() * 3, frame.get_height() * 3))
        s.blit(big_sprite, ((SCREEN_W - big_sprite.get_width()) // 2, 100))

        if (self.tick // 22) % 3 != 2:
            msg = "PRESS ENTER TO BEGIN"
            ui.text(s, msg, (SCREEN_W - ui.text_w(msg)) // 2, 186, ACCENT)
        foot = "WASD MOVE   E LOOK   TAB FILE   M SOUND"
        ui.text(s, foot, (SCREEN_W - ui.text_w(foot)) // 2, SCREEN_H - 18, UI_FAINT)

        dot = GREEN if self.ai.status == "ok" else DANGER if self.ai.status == "down" else ACCENT
        pygame.draw.rect(s, dot, (SCREEN_W - 14, 10, 5, 5))
        status_label = {"ok": "MODEL OK", "down": "MODEL OFFLINE", "unknown": "CHECKING"}[self.ai.status]
        ui.text(s, status_label, SCREEN_W - 8 - ui.text_w(status_label), 18, UI_FAINT)

    def draw_ending(self):
        s = self.scene
        e = self.ending

        if self.ending_page == 1:
            # The full solution is written (case.py's CASE["solution"]) but
            # was never shown anywhere - most pointedly after wrong_suspect,
            # where the player learns only that they were wrong and never
            # who did it or why.
            ui.terminal_frame(s, "HRPD // WHAT ACTUALLY HAPPENED", self.tick, "TAB DISPOSITION   ENTER NEW CASE")
            y = self._section("THE TRUTH OF IT", 28)
            room = (SCREEN_H - 26 - y) // 10
            for line in ui.wrap(CASE["solution"], SCREEN_W - 34)[:room]:
                ui.text(s, line, 14, y, UI_DIM)
                y += 10
            return

        ui.terminal_frame(s, "HRPD // DISPOSITION", self.tick, "ENTER NEW CASE   TAB WHAT HAPPENED")
        heads = {
            "correct_strong": ("CASE CLOSED", GREEN),
            "wrong_suspect": ("CASE GONE COLD", DANGER),
            "correct_thin": ("CASE CLOSED - HOLLOW", ACCENT),
        }
        head, head_col = heads[e["shape"]]
        big = ui.font(16)
        w = big.size(head)[0]
        s.blit(big.render(head, False, INK), ((SCREEN_W - w) // 2 + 2, 30))
        s.blit(big.render(head, False, head_col), ((SCREEN_W - w) // 2, 28))

        # The grade sits as a badge beside the caption rather than as a hero
        # panel: the prose is the payoff here, and it needs the vertical room.
        y = 50
        cx = 14
        if e["grade"]:
            gf = ui.font(16)
            gw = gf.size(e["grade"])[0]
            ui.panel(s, (14, y, gw + 16, 22), UI_BG_2, UI_HI)
            s.blit(gf.render(e["grade"], False, ACCENT), (22, y + 3))
            cx = 14 + gw + 26
        ui.text(s, e["caption"], cx, y + 7, UI_TEXT)
        y += 28

        turns = sum(c["turns"] for c in self.convo.values())
        stat = (
            f"{turns} QUESTIONS   {len(self.found)}/{len(CASE['evidence'])} FOUND   "
            f"CASE CLOSED {e['closed_at']}"
        )
        ui.text(s, stat, 14, y, UI_DIM)
        y += 16

        # Clamped to the space above the footer so a long ending can never
        # spill over the chrome.
        room = (SCREEN_H - 26 - y) // 10
        for line in ui.wrap(e["prose"], SCREEN_W - 34)[:room]:
            ui.text(s, line, 14, y, UI_DIM)
            y += 10

    def draw(self):
        if self.state == TITLE_SCREEN:
            self.draw_title()
        elif self.state == CASEFILE:
            self.draw_casefile()
        elif self.state == ACCUSE:
            self.draw_accuse()
        elif self.state == ENDING:
            self.draw_ending()
        elif self.state == PAUSED:
            self.draw_paused()
        else:
            self.draw_world()
            if self.state == TALKING:
                self.draw_talk()
            else:
                self.draw_hud()
                self.box.draw(self.scene, self.tick)
            self.toast.draw(self.scene)
            if self.transition:
                self.draw_transition()

        # `scene` inherits the real display's pixel format, which on this
        # Mac's window includes a genuine per-pixel alpha byte. Blitting any
        # SRCALPHA surface onto it (the darkness overlay, the title screen's
        # scaled-up sprite, anything drawn with `from_art`) leaves that alpha
        # near-zero across the blitted rect instead of the destination
        # staying opaque — a dummy/offscreen driver never composites the
        # window against anything so this was invisible in every headless
        # test, but a real macOS window honours that alpha for compositing,
        # so those areas turned see-through to whatever was behind the
        # window. Normalizing once here, right before the scene ever reaches
        # the screen, fixes every draw call that could hit this rather than
        # chasing it call site by call site. MAX is a plain per-channel
        # maximum, not alpha-blend math, so it reliably forces opacity back
        # to 255 without touching any RGB colour.
        self.scene.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MAX)

        if DEBUG and self.tick % 60 == 0:
            # Both surfaces, so a black window with a correct internal scene
            # points at the upscale/flip step rather than at drawing itself.
            pygame.image.save(self.scene, os.path.join(DEBUG_DIR, f"{self.tick:06d}_scene.png"))

        pygame.transform.scale(self.scene, self.screen.get_size(), self.screen)
        # Scanlines go on after the upscale, so they stay one screen pixel
        # thick however far the window is blown up.
        self.screen.blit(self.scanlines, (0, 0))
        self.screen.blit(self.vignette, (0, 0))

        if DEBUG and self.tick % 60 == 0:
            pygame.image.save(self.screen, os.path.join(DEBUG_DIR, f"{self.tick:06d}_screen.png"))
            _debug_log(f"[{self.tick}] dumped frame, state={self._state}")

        pygame.display.flip()

    def build_scanlines(self):
        w, h = self.screen.get_size()
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 3):
            pygame.draw.line(s, (0, 0, 0, 46), (0, y), (w, y))
        return s

    def build_vignette(self):
        """A soft noir frame around the edges. Built small and scaled up —
        walking the full screen resolution pixel-by-pixel in Python would be
        far too slow for something drawn once at startup."""
        w, h = self.screen.get_size()
        sw, sh = max(64, w // 6), max(40, h // 6)
        small = pygame.Surface((sw, sh), pygame.SRCALPHA)
        cx, cy = sw / 2, sh / 2
        for y in range(sh):
            ny = (y - cy) / cy
            for x in range(sw):
                nx = (x - cx) / cx
                d = (nx * nx + ny * ny) ** 0.5
                a = int((d - 0.55) * 220)
                if a > 0:
                    small.set_at((x, y), (6, 6, 16, min(160, a)))
        return pygame.transform.smoothscale(small, (w, h))

    # -- loop ----------------------------------------------------------------

    def run(self):
        try:
            self._run()
        except Exception:
            # A crash mid-frame otherwise just vanishes when the game is
            # launched from Finder rather than a terminal.
            _debug_log(f"[{self.tick}] CRASH:\n{traceback.format_exc()}")
            raise

    def _run(self):
        while True:
            dt = min(self.fps_clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit()
                elif e.type == pygame.KEYDOWN:
                    self.on_key(e)
                elif e.type == pygame.TEXTINPUT:
                    self.on_text(e)
            self.update(dt)
            self.draw()


def _selftest_parse_tell():
    """Edge cases that have each broken this once: case-sensitive field
    names losing an uppercasing model's composure, an unterminated control
    block leaking raw [[TELL syntax onto the player's screen, and a model
    copying the format example's two-speaker shape so the suspect answers
    in the detective's voice."""
    problems = []
    name = "Staff Sergeant Elias Thorne"
    cases = [
        ("Hello there.", None, ("Hello there.", None, 0, False, [])),
        ("[[TELL composure=rattled pressure=+12]]", None, ("", "rattled", 12, False, [])),
        ("Fine. [[tell COMPOSURE=Cracking pressure=30 ASKED=yes]]", None, ("Fine.", "cracking", 30, True, [])),
        ("Look, [[TELL composure=steady pressure=+5", None, ("Look,", None, 0, False, [])),
        # The model wrote both sides of the exchange.
        ('Detective: "Where were you?"\nThorne: "Home. All night."', name,
         ("Home. All night.", None, 0, False, [])),
        # Just its own label, and the example's quotes around the reply.
        ('Staff Sergeant Elias Thorne: "Home. All night."', name,
         ("Home. All night.", None, 0, False, [])),
        # A colon that is ordinary speech, not a label, survives intact.
        ("Look: I already told you.", name, ("Look: I already told you.", None, 0, False, [])),
        # A mid-sentence quotation is not an outer wrapper - keep it.
        ('He said "wait" and I waited.', name, ('He said "wait" and I waited.', None, 0, False, [])),
        # Naming themselves mid-sentence is not a speaker label - the words
        # before the colon must survive.
        ("Sergeant Thorne told me: he was home.", name,
         ("Sergeant Thorne told me: he was home.", None, 0, False, [])),
        # Curly quotes wrap a reply just as straight ones do.
        ("\u201cHome. All night.\u201d", name, ("Home. All night.", None, 0, False, [])),
    ]
    for raw, speaker, expected in cases:
        got = llm.parse_tell(raw, speaker)
        if got != expected:
            problems.append(f"parse_tell({raw!r}, {speaker!r}) = {got!r}, expected {expected!r}")
    return problems


def _selftest_winnable():
    """The strong ending must stay reachable from world evidence alone, even
    if the model never contributes a pressure delta - receive()'s pressure
    floor is the deliberate backstop for that. Encodes the same arithmetic
    the case-content audit checked by hand, so a future edit to evidence
    pressures or conviction thresholds can't silently take that away."""
    problems = []
    conv = CASE["conviction"]
    strong = conv["strong"]
    pool_by_pressure = sorted((EVIDENCE_BY_ID[e]["pressure"] for e in strong["pool"]), reverse=True)
    best_floor = sum(pool_by_pressure[: strong["requires_count"]])
    if best_floor < strong["minPressure"]:
        problems.append(
            f"even the {strong['requires_count']} highest-pressure pool items only floor to "
            f"{best_floor}, short of minPressure {strong['minPressure']} - the strong ending "
            "would be unreachable without the model contributing a delta"
        )
    # This run's own pick, from Game()'s reset_run() -> pick_culprit() - a
    # cheap sanity check that the runtime key actually got set, independent of
    # validate_culprit_pool() below which checks every pool member instead.
    if conv.get("culprit") not in SUSPECTS_BY_ID:
        problems.append(f"conviction culprit {conv.get('culprit')!r} is not a real suspect id")
    # Game()'s own reset_run() already rolled a random culprit before this
    # ever runs, so checking only that one would make CI's coverage of Doss's
    # and Ashworth's guiltVariant text a coin flip. validate_culprit_pool()
    # checks every pool member's variant is complete, unconditionally.
    problems += validate_culprit_pool()
    return problems


def selftest():
    """Prove a packaged build works: boot, render, and check the font loaded.

    Frozen builds fail quietly — a missing data file falls back to a default
    font instead of crashing — so the check has to be explicit.
    """
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    g = Game()
    for _ in range(8):
        g.update(1 / 60)
        g.draw()
    g.state = PLAYING
    g.box.active = False
    for _ in range(4):
        g.update(1 / 60)
        g.draw()
    problems = []
    if not ui.pixel_font_loaded:
        problems.append(f"pixel font not found at {ui.FONT_PATH}")
    if len(g.world.objects) < 100:
        problems.append(f"world looks empty ({len(g.world.objects)} props)")
    if len(g.npcs) != len(CASE["suspects"]):
        problems.append(f"expected {len(CASE['suspects'])} suspects, found {len(g.npcs)}")
    if not sfx.ok:
        problems.append("audio device unavailable (harmless under a dummy driver)")
    llm_problems = _selftest_parse_tell() + _selftest_winnable()
    problems += llm_problems
    out = sys.argv[sys.argv.index("--selftest") + 1] if len(sys.argv) > 2 else None
    if out:
        pygame.image.save(g.screen, out)
        print("wrote", out)
    print(f"props={len(g.world.objects)} npcs={len(g.npcs)} font={ui.pixel_font_loaded} audio={sfx.ok}")
    for p in problems:
        print("PROBLEM:", p)
    fail = any("font" in p or "empty" in p or "suspects" in p for p in problems) or llm_problems
    return 1 if fail else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    Game().run()

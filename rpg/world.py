"""Harrow's Reach, the night the vault came up five cases short.

The map is carved rather than typed. Rooms and corridors are cut into a field
of void, then anything still void that touches an interior tile becomes wall.
That way the city's five buildings are always sealed and the layout can be
moved around without recounting a single row of ASCII.
"""

import pygame

import art
from case import CASE, EVIDENCE_BY_ID
from settings import *

MAP_W, MAP_H = 88, 70

# Floors you can stand on. Everything else stops you.
WALKABLE = {"marble_d", "wood", "carpet", "path", "grass", "concrete", "labfloor"}
INTERIOR = {"marble_d", "wood", "carpet", "concrete", "labfloor"}


class Building:
    """One structure on the map, described in a single place.

    Give it its rooms and the corridor that pokes out to the street, and
    everything downstream is derived: the zone tag that lifts the roof when
    you walk in, the wall shell the sealing pass builds around it, the door
    punched back through that shell, the title card the entry cutscene
    shows, and the approach lane that furniture is forbidden to block.

    Before this existed all five of those lived in separate hand-typed
    lists, which is how a tree ended up parked inside the vault doorway and
    sealed the building shut.
    """

    def __init__(self, zone, title, subtitle, rooms, corridor, style="military",
                 door=None, window=None):
        self.zone = zone
        self.title = title
        self.subtitle = subtitle
        self.rooms = rooms  # [(x, y, w, h, floor)]
        self.corridor = corridor  # (x, y, w, h, floor)
        self.style = style  # which roof material this building wears
        # Most buildings just wear their style's shared door/window. A few
        # (the vault's blast door, the motor pool's bay shutter, the
        # precinct's awning) are distinctive enough to earn their own prop
        # key instead — None means "use door_{style}"/"window_{style}" as
        # every building did before this existed.
        self.door_key = door
        self.window_key = window

    @property
    def _exits_south(self):
        """True when the corridor leaves from the bottom of the building."""
        cx, cy, cw, ch, _ = self.corridor
        return cy >= max(y + h for _, y, _, h, _ in self.rooms)

    @property
    def door_row(self):
        """The row the sealing pass walls shut and the door punches back open:
        one tile past the far end of the corridor."""
        _, cy, _, ch, _ = self.corridor
        return cy + ch if self._exits_south else cy - 1

    @property
    def door_tiles(self):
        cx, _, cw, _, _ = self.corridor
        return [(x, self.door_row) for x in range(cx, cx + cw)]

    @property
    def approach(self):
        """Every tile that has to stay walkable for the building to be usable:
        the corridor, its door, and the step of street just outside it."""
        cx, cy, cw, ch, _ = self.corridor
        tiles = [(x, y) for x in range(cx, cx + cw) for y in range(cy, cy + ch)]
        tiles += self.door_tiles
        outside = self.door_row + 1 if self._exits_south else self.door_row - 1
        tiles += [(x, outside) for x in range(cx, cx + cw)]
        return tiles


# Harrow's Reach reorganised into four districts on an enlarged map: Military
# (Fort Callow) top-right, Civic (the P.D.) top-left, Rural (the Thorne house)
# bottom-left, Coastal (Salt Row) bottom-right, with Harborview Square at the
# crossroads between all four. Each building keeps its original room/corridor
# shape exactly - only its position moved - so the roofs-can't-touch and
# approach-lane invariants below carry over unchanged from the layout that
# already shipped.
BUILDINGS = [
    # --- Military district (top-right): Vault + Command in a row, Motor
    # Pool below them - the same relative arrangement and spacing as before,
    # the whole cluster just shifted right and down to its new district.
    Building("vault", "FORT CALLOW", "SPECIAL WEAPONS VAULT",
             rooms=[(28, 5, 16, 9, "concrete")], corridor=(34, 14, 3, 1, "concrete"),
             style="military", door="door_vault", window="window_vault"),
    Building("command", "FORT CALLOW", "COMMAND OFFICE",
             rooms=[(68, 5, 16, 9, "carpet")], corridor=(74, 14, 3, 1, "carpet"),
             style="military"),
    # Wider and flatter than the other Fort Callow buildings - a long shed
    # rather than a square room, matching a motor pool's actual shape. Can't
    # go wider than this and still leave both neighbours clear: the map only
    # gives Fort Callow so much east-west room.
    Building("motorpool", "FORT CALLOW", "MOTOR POOL",
             rooms=[(48, 5, 16, 7, "concrete")], corridor=(55, 12, 3, 3, "concrete"),
             style="military", door="door_motorpool"),
    # --- Civic district (top-left): Third Precinct + Forensics, clustered.
    # The entrance faces south, like every other building: the door, awning
    # and sign are painted on the south wall, and when the corridor left from
    # the north the front of the building was a blank roof with a fake door
    # round the back. The street that meets it is the "precinct road" below.
    Building("precinct", "THIRD PRECINCT", "HOME BASE",
             rooms=[(6, 20, 16, 8, "wood")], corridor=(12, 28, 3, 1, "wood"),
             style="civic", door="door_precinct"),
    # A real room now, not a closet - big enough for the full bench/
    # microscope/cabinet/fume-hood set.
    Building("lab", "HARROW'S REACH P.D.", "FORENSICS",
             rooms=[(10, 3, 10, 6, "labfloor")], corridor=(14, 9, 3, 1, "labfloor"),
             style="lab"),
    # --- Rural district (bottom-left): the Thorne house, alone. Held well
    # clear of the bottom edge: the hedge border eats the last three rows,
    # and a door whose outside step lands on hedge seals the building shut.
    # Two rooms, kitchen and garage, with a wall of their own between them:
    # the garage starts a tile further along so the sealing pass walls the
    # gap, and the 1x2 room at x=17 cuts a doorway back through that wall.
    Building("milner", "14 MILNER STREET", "THE THORNE HOUSE",
             rooms=[(8, 44, 9, 11, "wood"), (18, 44, 7, 11, "concrete"),
                    (17, 49, 1, 2, "concrete")],
             corridor=(11, 55, 3, 2, "wood"), style="house"),
    # --- Coastal district (bottom-right): the fishing cabin, alone.
    Building("saltrow", "SALT ROW, DOCK 4", "THE FISHING CABIN",
             rooms=[(67, 46, 14, 10, "wood")], corridor=(72, 56, 3, 1, "wood"),
             style="cabin"),
]


class World:
    def __init__(self):
        self.grid = [["void"] * MAP_W for _ in range(MAP_H)]
        self.tiles = art.build_tiles()
        self.objects = []  # (surface, x, y, sort_y)
        self.blockers = []  # pygame.Rect, world space
        self.interactables = []
        self.floor_layers = {}  # zone -> {floor_name: captured content}
        self.floor_state = {}  # zone -> currently-live floor_name
        self.floor_default = {}  # zone -> floor a fresh run starts on
        self.lights = []
        self.npc_spots = {}  # sid -> {"x", "y", "rect", "blocker"}
        self._build()
        self._furnish()
        self.floor = self._bake_floor()
        self.roofs = self._bake_roofs()

    # --- carving -------------------------------------------------------------

    def _fill(self, x, y, w, h, kind, over=None):
        """Paint a rectangle. `over` limits which tile kinds may be replaced,
        which is how the grass flows around walls and the paths sit on the
        grass without eating either."""
        for ty in range(y, y + h):
            for tx in range(x, x + w):
                if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
                    if over is not None and self.grid[ty][tx] not in over:
                        continue
                    self.grid[ty][tx] = kind

    def _build(self):
        self.zone_grid = [[None] * MAP_W for _ in range(MAP_H)]
        self.zone_names = {b.zone: (b.title, b.subtitle) for b in BUILDINGS}

        def zone_fill(x, y, w, h, kind, zone, over=None):
            self._fill(x, y, w, h, kind, over)
            for ty in range(y, y + h):
                for tx in range(x, x + w):
                    if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
                        self.zone_grid[ty][tx] = zone

        # Every building carves itself: rooms first, then the corridor that
        # takes it out to the street.
        for b in BUILDINGS:
            for x, y, w, h, floor in b.rooms:
                zone_fill(x, y, w, h, floor, b.zone)
            cx, cy, cw, ch, floor = b.corridor
            zone_fill(cx, cy, cw, ch, floor, b.zone)

        # Seal the city: any void touching a floor becomes wall.
        walls = []
        for y in range(MAP_H):
            for x in range(MAP_W):
                if self.grid[y][x] != "void":
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < MAP_W and 0 <= ny < MAP_H and self.grid[ny][nx] in INTERIOR:
                            walls.append((x, y))
                            break
                    else:
                        continue
                    break
        for x, y in walls:
            self.grid[y][x] = "wall"

        # Grounds. Fills only what is still void, so it flows around the walls.
        self._fill(1, 1, MAP_W - 2, MAP_H - 2, "grass", over={"void"})

        # Paths, laid over the grass — never over a wall, or the shell would
        # develop holes the auto-walling has already finished checking for.
        # A wide spine across the top, linking the civic district to Fort
        # Callow...
        self._fill(8, 16, 74, 3, "path", over={"grass"})
        # ...a spine down the middle to the bottom of the map...
        self._fill(42, 16, 4, 45, "path", over={"grass"})
        # ...a spine along the bottom, linking Milner Street to Salt Row...
        self._fill(10, 58, 72, 3, "path", over={"grass"})
        # ...and one connector for the lab, the only building set back far
        # enough from a spine to need one. Every other corridor is cut so its
        # door's outside step lands on a spine directly: a connector drawn
        # across corridor and wall tiles paints nothing at all, because the
        # over={"grass"} guard skips them, and the door ends up opening onto
        # bare ground.
        self._fill(14, 11, 3, 5, "path", over={"grass"})   # lab
        # ...and the precinct road, from the precinct's front door east to
        # Harborview Square.
        self._fill(12, 30, 22, 3, "path", over={"grass"})
        # Harborview Square: the plaza at the crossroads where all four
        # districts meet.
        self._fill(34, 30, 20, 12, "path", over={"grass"})

        # A hedge along the boundary so the grounds have an edge.
        for y in range(MAP_H):
            for x in range(MAP_W):
                if self.grid[y][x] == "grass" and (x <= 2 or y <= 2 or x >= MAP_W - 3 or y >= MAP_H - 3):
                    self.grid[y][x] = "hedge"

        # Doors. Each corridor ends one row short of the path network, so the
        # sealing pass above walls that row shut — punch exactly that row back
        # open. The row is derived from the corridor, so moving a building
        # moves its door with it.
        for b in BUILDINGS:
            for tx, ty in b.door_tiles:
                self.grid[ty][tx] = "path"

        # The lanes furniture may never stand in. Anything with a collision box
        # that lands here would seal a building shut from the outside, which is
        # exactly how a decorative tree once locked the vault.
        self._keep_clear = [
            pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
            for b in BUILDINGS
            for tx, ty in b.approach
        ]

    def _bake_floor(self):
        """Draw the whole map once. It never changes, so it never redraws."""
        surf = pygame.Surface((MAP_W * TILE, MAP_H * TILE))
        for y in range(MAP_H):
            for x in range(MAP_W):
                kind = self.grid[y][x]
                if kind == "wall":
                    below = self.grid[y + 1][x] if y + 1 < MAP_H else "void"
                    if below in ("wall", "void"):
                        variants = self.tiles["wall_top"]
                    elif below == "carpet":
                        variants = self.tiles["wainscot"]
                    else:
                        variants = self.tiles["wall"]
                else:
                    variants = self.tiles.get(kind, self.tiles["void"])
                surf.blit(variants[(x * 7 + y * 3) % len(variants)], (x * TILE, y * TILE))

        # Kerbs. A road with no edge reads as a grey shape painted on grass;
        # a raised lip along every ground-facing side turns the same tiles
        # into a street.
        for y in range(MAP_H):
            for x in range(MAP_W):
                if self.grid[y][x] != "path":
                    continue
                px, py = x * TILE, y * TILE
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < MAP_W and 0 <= ny < MAP_H):
                        continue
                    if self.grid[ny][nx] not in ("grass", "hedge"):
                        continue
                    if dy:  # horizontal kerb, lit on top and shadowed beneath
                        ky = py if dy < 0 else py + TILE - 3
                        pygame.draw.rect(surf, STONE_L, (px, ky, TILE, 2))
                        pygame.draw.rect(surf, STONE_D, (px, ky + 2, TILE, 1))
                    else:
                        kx = px if dx < 0 else px + TILE - 3
                        pygame.draw.rect(surf, STONE_L, (kx, py, 2, TILE))
                        pygame.draw.rect(surf, STONE_D, (kx + 2, py, 1, TILE))
        return surf

    def _bake_roofs(self):
        """One roof surface per building, baked once.

        A building's roof covers its own tiles plus the wall shell around them,
        so from outside you see a closed structure rather than a lit room with
        no lid. `main` draws every roof except the one the player is standing
        under, which is what makes walking through a door feel like entering.
        """
        members = {}
        for y in range(MAP_H):
            for x in range(MAP_W):
                z = self.zone_grid[y][x]
                if z:
                    members.setdefault(z, set()).add((x, y))
        for tiles in members.values():
            shell = set()
            for x, y in tiles:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < MAP_W and 0 <= ny < MAP_H and self.grid[ny][nx] == "wall":
                            shell.add((nx, ny))
            tiles |= shell
        self.zone_tiles = members

        # Two roofs that touch read as one long slab rather than as separate
        # buildings, so they are kept a tile apart.
        zones = list(members)
        for i, a in enumerate(zones):
            for b in zones[i + 1:]:
                touching = {(x + dx, y + dy) for x, y in members[a]
                            for dx in (-1, 0, 1) for dy in (-1, 0, 1)} & members[b]
                if touching:
                    raise ValueError(
                        f"roofs of {a!r} and {b!r} touch at {sorted(touching)[0]} — "
                        f"leave a tile of ground between them"
                    )

        by_zone = {b.zone: b for b in BUILDINGS}
        roofs = {}
        self.chimneys = []
        for zone, tiles in members.items():
            roofs[zone] = self._bake_exterior(by_zone[zone], tiles)
        return roofs

    # Overhang below the eave, where the roof throws a shadow onto the ground.
    EAVE_DROP = 5
    # How many rows at the bottom of a building are wall rather than roof.
    FACADE_ROWS = 2

    def _dress_facade(self, building, surf, tx, px, wall_top, wall_bottom, door_cols):
        """One door at the middle of the entrance, windows along the rest.

        Every door column getting a door gave the house three front doors in
        a row, so the door goes on the centre column only and the flanking
        ones stay blank wall rather than falling through to a window.
        """
        props = art.objects()
        if tx in door_cols:
            cols = sorted(door_cols)
            if tx == cols[len(cols) // 2]:
                door = building.door_key or f"door_{building.style}"
                surf.blit(props[door], (px, wall_bottom - 26))
            elif art.ROOF_STYLES[building.style].get("flank"):
                # Whatever hangs either side of the door: a lantern and an
                # address plate on the house, a blue lamp each side on the
                # precinct. (prop key, height above the foot of the wall)
                left, right = art.ROOF_STYLES[building.style]["flank"]
                if tx == cols[0]:
                    surf.blit(props[left[0]], (px, wall_bottom - left[1]))
                elif tx == cols[-1]:
                    surf.blit(props[right[0]], (px, wall_bottom - right[1]))
        elif tx % 3 == 1 and min(door_cols) - 1 <= tx <= max(door_cols) + 1:
            pass  # the wall beside the door stays blank, so the door has room
        elif tx % 3 == 1:
            window = props[building.window_key or f"window_{building.style}"]
            # Normally 8px down the wall, but never so low that it hangs off
            # the foot of a thin wall band (the precinct's is one tile high).
            y = min(wall_top + 8, wall_bottom - window.get_height())
            surf.blit(window, (px + (TILE - window.get_width()) // 2, y))

    def _bake_exterior(self, building, tiles):
        """Draw one building as a pitched structure rather than a flat lid.

        Each column of the footprint gets its own ridge, halfway down that
        column, so an L-shaped building with a corridor still reads as a roof
        rather than as a rectangle. The back slope sits in shadow, the ridge
        catches the light, the front slope runs down to a dark eave, and the
        whole thing drops a shadow onto the ground below it.
        """
        pal = art.ROOF_STYLES[building.style]
        shingles = art.build_roof_tiles(building.style)
        self._facade = [art.facade_tile(building.style, i) for i in range(3)]
        x0 = min(t[0] for t in tiles)
        y0 = min(t[1] for t in tiles)
        w = max(t[0] for t in tiles) - x0 + 1
        h = max(t[1] for t in tiles) - y0 + 1
        surf = pygame.Surface((w * TILE, h * TILE + self.EAVE_DROP), pygame.SRCALPHA)

        cols = {}
        for x, y in tiles:
            cols.setdefault(x, []).append(y)

        # Ground shadow first, so the roof lands on top of it.
        shadow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for x, ys in cols.items():
            px = (x - x0) * TILE
            shadow.fill((0, 0, 0, 96), (px + 2, (max(ys) - y0 + 1) * TILE, TILE, self.EAVE_DROP))
        surf.blit(shadow, (0, 0))

        door_cols = {x for x, _ in building.door_tiles}
        facade_rows = pal.get("facade_rows", self.FACADE_ROWS)
        for x, ys in cols.items():
            top, bottom = min(ys), max(ys)
            # The bottom rows of every column are wall, not roof — that front
            # face is what stops the building reading as paper on the ground.
            # How many rows depends on style: military/lab want most of the
            # structure to read as flat-roofed wall, civic wants the opposite
            # (mostly steep roof, a thin wall band).
            wall_from = max(top + 1, bottom - facade_rows + 1)
            roof_rows = [y for y in ys if y < wall_from]
            ridge = (top + max(roof_rows)) // 2 if roof_rows else top
            px = (x - x0) * TILE
            reach = max(1, (max(roof_rows) - top) / 2) if roof_rows else 1

            for y in roof_rows:
                py = (y - y0) * TILE
                slope = "back" if y <= ridge else "front"
                bank = shingles[slope]
                surf.blit(bank[(x * 7 + y * 3) % len(bank)], (px, py))
                # Both slopes fall away from the ridge. Without this the two
                # halves read as flat two-tone bands rather than a pitch.
                fall = abs(y - ridge) / reach
                dim = int((48 if slope == "back" else 34) * fall)
                if dim:
                    shade = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                    shade.fill((8, 8, 14, dim))
                    surf.blit(shade, (px, py))
            if roof_rows:
                ry = (ridge - y0) * TILE
                pygame.draw.rect(surf, pal["cap"], (px, ry, TILE, 3))
                pygame.draw.rect(surf, pal["trim"], (px, ry + 3, TILE, 1))

            # The wall itself, then the eave shadow the roof throws across it.
            for y in range(wall_from, bottom + 1):
                surf.blit(self._facade[(x * 5 + y) % len(self._facade)],
                          (px, (y - y0) * TILE))
            wy = (wall_from - y0) * TILE
            pygame.draw.rect(surf, pal["eave"], (px, wy - 3, TILE, 5))
            shade = pygame.Surface((TILE, 6), pygame.SRCALPHA)
            shade.fill((8, 8, 14, 90))
            surf.blit(shade, (px, wy + 2))
            by = (bottom - y0 + 1) * TILE
            pygame.draw.rect(surf, pal["wall_d"], (px, by - 2, TILE, 2))  # footing

            self._dress_facade(building, surf, x, px, wy, by, door_cols)

        # Gable trim down the outside edges of every column run.
        for x, ys in cols.items():
            px = (x - x0) * TILE
            for edge, ex in (((x - 1) not in cols, px), ((x + 1) not in cols, px + TILE - 1)):
                if edge:
                    for y in ys:
                        py = (y - y0) * TILE
                        pygame.draw.rect(surf, pal["trim"], (ex, py, 1, TILE))

        self._fit_roof(building, surf, cols, x0, y0, pal)
        return surf, x0 * TILE, y0 * TILE

    def _fit_roof(self, building, surf, cols, x0, y0, pal):
        """Chimneys, vents and signage — what tells one roof from another."""
        props = art.objects()
        rx, ry, rw, rh, _ = building.rooms[0]

        if pal.get("chimney"):
            cx, cy = rx + 1, ry + 1
            px, py = (cx - x0) * TILE, (cy - y0) * TILE
            surf.blit(props["chimney"], (px, py - 4))
            # Remembered in world pixels so the smoke can animate above it.
            self.chimneys.append((cx * TILE + 5, cy * TILE - 4, building.zone))

        if pal.get("vents"):
            for i in range(1, 4):
                vx = rx + (rw * i) // 4
                if vx in cols:
                    surf.blit(props["roof_vent"], ((vx - x0) * TILE + 2, (ry + 1 - y0) * TILE))

        if pal.get("mast"):
            # On the far slope, off to one side so it never lines up with the
            # sign over the door.
            mast = props["mast"]
            mx = rx + rw - 4
            if mx in cols:
                surf.blit(mast, ((mx - x0) * TILE + 2, (ry + 4 - y0) * TILE + 6 - mast.get_height()))

        if pal.get("sign"):
            # Centred over the door and clear of it: the door leaf stands 26px
            # above the foot of the wall, and a sign hung any lower covers half
            # of it. The wall band is always the bottom of the column.
            cx, _, cw, _, _ = building.corridor
            sign = props["roof_sign"]
            row = max(cols[cx + cw // 2])
            surf.blit(sign, ((cx + cw // 2 - x0) * TILE + (TILE - sign.get_width()) // 2,
                             (row - y0) * TILE - 12 - sign.get_height()))

    # --- furniture -----------------------------------------------------------

    def _obj(self, key, tx, ty, ox=0, oy=0, solid=None, sort_pad=0):
        """Place a prop. `solid` is a rect in pixels relative to its top-left."""
        surf = self.props[key] if isinstance(key, str) else key
        x, y = tx * TILE + ox, ty * TILE + oy
        self.objects.append((surf, x, y, y + surf.get_height() + sort_pad))
        if solid is True:
            solid = (0, surf.get_height() // 2, surf.get_width(), surf.get_height() // 2)
        if solid:
            dx, dy, w, h = solid
            box = pygame.Rect(x + dx, y + dy, w, h)
            if box.collidelist(self._keep_clear) != -1:
                raise ValueError(
                    f"prop {key!r} at tile ({tx},{ty}) blocks a building "
                    f"approach lane — move it clear of the doorway"
                )
            self.blockers.append(box)
        return pygame.Rect(x, y, surf.get_width(), surf.get_height())

    def _look(self, rect, title, body, evidence=None):
        """Register something the player can press E on.

        Two lookable props whose reach overlaps are a silent trap: the game
        returns whichever centre is nearer, so one of them becomes
        unreachable and its evidence uncollectable. That is what an arms
        rack once did to the gate camera, so it is refused outright here.
        """
        reach = rect.inflate(12, 12)
        for other in self.interactables:
            if reach.colliderect(other["rect"]):
                raise ValueError(
                    f"interactable {title!r} overlaps {other['title']!r} — "
                    f"one of them would be unreachable"
                )
        self.interactables.append(
            {"rect": reach, "title": title, "body": body, "evidence": evidence}
        )

    def _npc_spot(self, sid, tx, ty, ox=8, oy=20, zone=None, home_floor=None):
        """Reserve a standing spot for one of the four suspects. `main.py`
        builds the NPC instance and its interactable from this.

        `zone`/`home_floor` mark a suspect confined to one floor of a
        multi-floor building (e.g. Doss only ever stands in the vault's
        main level, never the basement) - `Game` uses them to keep the
        suspect off every other floor of that zone."""
        x, y = tx * TILE + ox, ty * TILE + oy
        self.npc_spots[sid] = {
            "x": x,
            "y": y,
            "rect": pygame.Rect(x - 12, y - 26, 24, 26).inflate(16, 16),
            "blocker": pygame.Rect(x - 7, y - 10, 14, 10),
            "zone": zone,
            "home_floor": home_floor,
        }

    def _stairs(self, rect, zone, to_floor, label):
        """A staircase between two floors of the same building. Lives in
        `self.interactables` like any other lookable, but flagged so
        `Game.interact` swaps floors instead of opening a body of text."""
        reach = rect.inflate(12, 12)
        for other in self.interactables:
            # Every floor of a building puts its stairway on the same tile, so
            # the other floor's hatch is expected to sit exactly here. Skipping
            # it keeps this check independent of the order floors are
            # registered in — only one of them is ever live at a time.
            if other.get("stairs") and other.get("zone") == zone:
                continue
            if reach.colliderect(other["rect"]):
                raise ValueError(
                    f"stairs {label!r} overlap {other['title']!r} — one of "
                    f"them would be unreachable"
                )
        self.interactables.append(
            {"rect": reach, "title": label, "body": None, "evidence": None,
             "stairs": True, "zone": zone, "to_floor": to_floor}
        )

    # --- multi-floor buildings -------------------------------------------

    def _capture(self, fn):
        """Call `fn` (which appends new props/blockers/interactables/lights
        for one floor) and return exactly what it added, by slicing each
        live list at its pre-call length — so a later floor swap can remove
        or restore precisely that set."""
        o0, b0, i0, l0 = len(self.objects), len(self.blockers), len(self.interactables), len(self.lights)
        fn()
        return {
            "objects": self.objects[o0:],
            "blockers": self.blockers[b0:],
            "interactables": self.interactables[i0:],
            "lights": self.lights[l0:],
        }

    @staticmethod
    def _drop(live, items):
        """Remove `items` from `live` by identity.

        `list.remove` matches with `==`, and both of the things stored here
        compare by value rather than identity: pygame.Rect is value-equal, and
        a prop tuple holds a Surface shared out of art.objects()'s cache. Two
        floors placing the same prop on the same tile would therefore produce
        equal-but-distinct entries, and `remove` would silently drop whichever
        came first — possibly a permanent blocker rather than the floor's."""
        doomed = {id(i) for i in items}
        live[:] = [x for x in live if id(x) not in doomed]

    def _remove_floor_content(self, content):
        self._drop(self.objects, content["objects"])
        self._drop(self.blockers, content["blockers"])
        self._drop(self.interactables, content["interactables"])
        self._drop(self.lights, content["lights"])

    def _register_floor(self, zone, floor_name, fn, active):
        """Furnish one floor of a multi-floor building. Every floor gets
        built (so its props exist and its stairs prop is captured), but only
        the `active` floor's content stays live until `switch_floor` is
        called."""
        content = self._capture(fn)
        # A solid prop sitting on this floor's own stairway would close over
        # the player the moment they arrive here, with no way back out: the
        # hatch is exactly where they are standing when the swap happens.
        for st in (i for i in content["interactables"] if i.get("stairs")):
            # Where the player's feet actually land — Player.FOOT, centred on
            # the hatch — not the whole prop, which is wider than they are.
            cx, cy = st["rect"].center
            landing = pygame.Rect(cx - 5, cy - 3, 10, 6)
            for b in content["blockers"]:
                if b.colliderect(landing):
                    raise ValueError(
                        f"{zone}/{floor_name}: a prop at {b.topleft} blocks "
                        f"this floor's stairway — the player would arrive "
                        f"inside it and be trapped"
                    )
        self.floor_layers.setdefault(zone, {})[floor_name] = content
        if active:
            # Remembered so a new run can put every building back on the floor
            # it started on — floor state outlives reset_run otherwise.
            self.floor_default[zone] = floor_name
            self.floor_state[zone] = floor_name
        else:
            self._remove_floor_content(content)

    def switch_floor(self, zone, floor_name):
        """Swap which floor of a building is furnished into the live world.
        The zone tag never changes, so roofing, lighting, and the entry
        cutscene are untouched — only the room's contents swap."""
        layers = self.floor_layers[zone]
        current = self.floor_state[zone]
        if current == floor_name:
            return
        self._remove_floor_content(layers[current])
        for o in layers[floor_name]["objects"]:
            self.objects.append(o)
        for b in layers[floor_name]["blockers"]:
            self.blockers.append(b)
        for i in layers[floor_name]["interactables"]:
            self.interactables.append(i)
        for l in layers[floor_name]["lights"]:
            self.lights.append(l)
        self.floor_state[zone] = floor_name

    def reset_floors(self):
        """Put every multi-floor building back on its starting floor. Floor
        state lives on the World, which outlives a run, so without this a new
        case would begin wherever the last one happened to leave off — with
        the vault's checkout terminal still stowed away downstairs."""
        for zone, floor_name in self.floor_default.items():
            self.switch_floor(zone, floor_name)

    def _furnish(self):
        self.props = art.objects()

        def put(key, tx, ty, ox=0, oy=0, solid=None, pad=0):
            return self._obj(key, tx, ty, ox, oy, solid, pad)

        def lamp(tx, ty, r=64, ox=8, oy=18):
            self.lights.append((tx * TILE + ox, ty * TILE + oy, r))

        def row(key, txs, ty, **kw):
            for tx in txs:
                put(key, tx, ty, **kw)

        # ---- Fort Callow: Special Weapons Vault ------------------------------
        # An armoury, not a study: steel racking and locked cabinets, no
        # bookshelves and no reading lamps. Two floors — the working floor,
        # and a storage sub-level down the hatch.
        def furnish_vault_main():
            put("steel_shelf", 29, 6, solid=True)
            put("steel_shelf", 29, 9, solid=True)
            put("gun_locker", 42, 6, solid=True)
            put("gun_locker", 42, 9, solid=True)
            put("ammo_crate", 30, 12, solid=True)
            put("ammo_crate", 32, 12, solid=True)
            put("sandbags", 40, 12, solid=(2, 4, 16, 7))
            for tx in (31, 36, 41):
                put("sconce", tx, 5, oy=6)
                lamp(tx, 6, 70)

            put("munitions_crate", 36, 12, solid=True)
            put("munitions_crate", 38, 6, solid=True)
            # Kept clear of the camera console: two lookable props whose
            # rects overlap and the nearer one silently swallows the other.
            rack = put("weapon_rack", 35, 6, solid=True)
            self._look(rack, "The arms rack",
                       "Serial-stencilled slots, every one of them signed for. Two stand "
                       "empty tonight, and the dust in them is a different age.")

            terminal = put("vault_terminal", 39, 10, solid=True)
            self._look(terminal, "Vault checkout terminal", EVIDENCE_BY_ID["vault-ledger"]["found_text"], evidence="vault-ledger")

            camera = put("camera_console", 32, 7, solid=True)
            self._look(camera, "Gate camera terminal", EVIDENCE_BY_ID["gate-camera"]["found_text"], evidence="gate-camera")

            hatch = put("stairs", 34, 10, pad=-4)
            self._stairs(hatch, "vault", "basement", "Down to the sub-level")

        def furnish_vault_basement():
            put("munitions_crate", 30, 7, solid=True)
            put("munitions_crate", 30, 11, solid=True)
            put("ammo_crate", 36, 7, solid=True)
            put("sandbags", 40, 6, solid=(2, 4, 16, 7))
            put("sandbags", 40, 11, solid=(2, 4, 16, 7))
            put("steel_shelf", 36, 11, solid=True)
            for tx in (32, 41):
                put("sconce", tx, 5, oy=6)
                lamp(tx, 6, 50)
            hatch = put("stairs", 34, 10, pad=-4)
            self._stairs(hatch, "vault", "main", "Up to the vault floor")

        self._register_floor("vault", "main", furnish_vault_main, active=True)
        self._register_floor("vault", "basement", furnish_vault_basement, active=False)
        # At his post by the checkout terminal, not blocking the doorway.
        self._npc_spot("doss", 40, 8, zone="vault", home_floor="main")

        # ---- Harrow's Reach P.D.: Forensics -----------------------------------
        # A real room now, big enough for the full bench/microscope/cabinet/
        # fume-hood set instead of three fittings crammed into a closet.
        bench = put("lab_bench", 11, 4, solid=True)
        self._look(bench, "The forensics bench",
                   "Someone has been working the matchbook mark against the Compact's "
                   "last two jobs. The comparison is pinned up half-finished, and the "
                   "burner is still lit.")
        put("microscope", 12, 6, pad=-4)
        put("specimen_cabinet", 17, 4, solid=True)
        put("fume_hood", 15, 7, solid=True)
        put("sconce", 14, 3, oy=4)
        lamp(14, 4, 62)

        # ---- Fort Callow: Motor Pool ------------------------------------------
        # Bricker's shop, and where the truck from the gate footage is parked.
        # Wide and flat rather than square - a long shed, not a garage bay.
        truck = put("truck", 52, 6, solid=(2, 20, 22, 18))
        self._look(truck, "A 2.5-ton in the end bay",
                   "Motor pool log says it has not moved in a week. The odometer says "
                   "otherwise, and someone has wiped the bed out with solvent - it is "
                   "the only clean thing in the building.")
        put("workbench", 49, 11, solid=True)
        # Steel racking, not a wooden bookshelf - nobody stores books in a
        # vehicle bay - one at each end so the long walls are not bare.
        put("steel_shelf", 48, 6, solid=True)
        put("steel_shelf", 62, 6, solid=True)
        for tx in (51, 53, 59):
            put("oil_drum", tx, 11, solid=(1, 8, 10, 7))
        put("crate", 60, 11, solid=True)
        put("pallet", 50, 6, solid=True)
        for tx in (48, 55, 60):
            put("sconce", tx, 5, oy=6)
            lamp(tx, 6, 70)

        # ---- Fort Callow: Command Office --------------------------------------
        # Two floors — the office itself, and a briefing room upstairs.
        def furnish_command_main():
            put("desk", 75, 8, solid=True)
            put("chair", 76, 10, solid=(3, 10, 10, 6))
            put("cabinet", 70, 7, solid=True)
            personnel_cabinet = put("cabinet", 70, 10, solid=True)
            self._look(personnel_cabinet, "A personnel file, left half-open",
                       "Thorne's file, pulled and re-filed more than once. A welfare-check "
                       "flag sits in it, dated months ago and never sent up the chain - no "
                       "signature, no date filed. Someone kept meaning to.")
            put("plant", 81, 11, solid=True)
            put("cooler", 81, 7, solid=True)
            for tx in (71, 75, 80):
                put("sconce", tx, 5, oy=6)
                lamp(tx, 6, 70)
            put("banner", 69, 6, oy=-2)
            put("banner", 82, 6, oy=-2)
            wallmap = put("wallmap", 77, 5, oy=4)
            self._look(wallmap, "Wall map of Harrow's Reach",
                       "The whole district under glass. Someone has pushed a single red pin "
                       "into Salt Row, down by the water, and left it there.")
            hatch = put("stairs", 73, 11, pad=-4)
            self._stairs(hatch, "command", "upper", "Up to the briefing room")

        def furnish_command_upper():
            put("table", 73, 8, solid=True)
            put("chair", 75, 10, solid=(3, 10, 10, 6))
            put("chair", 78, 10, solid=(3, 10, 10, 6))
            for tx in (72, 81):
                put("sconce", tx, 5, oy=6)
                lamp(tx, 6, 60)
            hatch = put("stairs", 73, 11, pad=-4)
            self._stairs(hatch, "command", "main", "Down to the office")

        self._register_floor("command", "main", furnish_command_main, active=True)
        self._register_floor("command", "upper", furnish_command_upper, active=False)
        # Behind her own desk — a battalion commander receives you, she doesn't
        # meet you at the door.
        self._npc_spot("ashworth", 76, 7, zone="command", home_floor="main")

        # ---- Third Precinct (home base) --------------------------------------
        put("desk", 13, 23, solid=True)
        put("chair_up", 14, 25, solid=(3, 10, 10, 6))
        put("desk", 17, 26, solid=True)
        row("bench", (8, 17), 25, solid=True)
        put("shelf", 7, 22, solid=True)
        # The holding cell, in the north-east corner where the east
        # bookshelf used to stand.
        put("jail_cell", 19, 21, solid=(0, 10, 48, 38))
        put("cabinet", 16, 21, solid=True)
        put("cooler", 6, 26, solid=True)
        put("banner", 18, 21, oy=4)
        board = put("corkboard", 8, 21, oy=4)
        self._look(board, "The case board",
                   "Five photographs, a duty roster, and a torn-off map corner, strung "
                   "together in red. Your own handwriting on most of it. None of it "
                   "yet says who.")
        for tx in (9, 13, 18):
            put("sconce", tx, 21, oy=8)
            lamp(tx, 22, 74)
        # Outside the front door: the blue lamps' glow, a patrol car parked at
        # the kerb of the precinct road, and a bush either side of the steps.
        for tx in (12, 14):
            lamp(tx, 27, 44, oy=13)
        put("patrol_car", 17, 32, oy=-2, solid=(2, 8, 40, 12))
        for tx in (9, 10, 16, 18):
            put("bush", tx, 29, solid=(2, 6, 12, 8))

        # ---- 14 Milner Street: the Thorne house --------------------------------
        # Kitchen.
        mess = put("kitchen_mess", 10, 50, solid=True)
        self._look(mess, "The kitchen", EVIDENCE_BY_ID["struggle-kitchen"]["found_text"], evidence="struggle-kitchen")
        put("shelf", 8, 46, solid=True)
        put("cooler", 14, 46, solid=True)
        put("stove", 12, 46, solid=True)
        put("table", 9, 53, solid=True)
        put("chair", 13, 52, solid=(3, 10, 10, 6))
        put("sconce", 12, 44, oy=6)
        lamp(12, 45, 64)

        # Garage. A working one: a bench with the tools on it, and the paint
        # shelf the burner phone is tucked behind (its `found_text` says so).
        put("doorway", 17, 49, pad=-32)  # the door from the kitchen
        put("workbench", 18, 46, solid=True)
        put("crate", 20, 46, solid=True)
        put("crate", 22, 46, solid=True)
        put("steel_shelf", 23, 46, solid=True)
        put("oil_drum", 24, 52, ox=2, solid=True)
        put("pallet", 20, 52, solid=True)
        phone = put("burner_phone", 23, 48, pad=-4)
        self._look(phone, "Behind the paint shelf", EVIDENCE_BY_ID["burner-phone"]["found_text"], evidence="burner-phone")
        photo = put("photo_facedown", 23, 50, pad=-4)
        self._look(photo, "A photo, face down", EVIDENCE_BY_ID["proof-of-life-photo"]["found_text"], evidence="proof-of-life-photo")
        put("lamp", 18, 52, solid=(2, 24, 12, 6))
        lamp(18, 52, 68, oy=26)

        # Planting either side of the front step, on the grass beside the
        # doorway (the approach lane itself stays clear).
        put("bush", 9, 56, solid=(2, 6, 12, 8))
        put("flowers", 10, 57, ox=-2)
        put("bush", 15, 56, solid=(2, 6, 12, 8))
        put("flowers", 14, 57, ox=2)

        # Out on the street rather than in the hallway — he is not in this house,
        # he is hanging around outside it.
        self._npc_spot("bricker", 17, 61)

        # ---- Salt Row, Dock 4: the fishing cabin -------------------------------
        put("table", 69, 49, solid=True)
        put("chair", 71, 51, solid=(3, 10, 10, 6))
        put("bunk", 68, 46, solid=True)
        put("stove", 74, 47, solid=True)
        lamp(74, 48, 52, oy=12)
        put("crate", 79, 53, solid=True)
        put("pallet", 76, 54, solid=True)
        put("lamp", 69, 48, solid=(2, 24, 12, 6))
        lamp(69, 48, 74, oy=26)
        put("lamp", 79, 48, solid=(2, 24, 12, 6))
        lamp(79, 48, 74, oy=26)
        # The dock itself, out front of the cabin, on the water side of the road.
        for tx in (68, 71, 77, 80):
            put("bollard", tx, 62, solid=(3, 8, 6, 6))

        # Deep in the cabin, backed into the far corner away from the door.
        self._npc_spot("thorne", 77, 51)

        # ---- Harborview Square (the roads between everything) ------------------
        # The plaza itself is the path fill at (34,30,20,12) - everything
        # below has to actually sit inside that rectangle, not on the road
        # feeding into it.
        put("fountain", 41, 33, solid=(4, 18, 40, 20))
        row("bench", (38, 48), 39, solid=True)
        for tx, ty in ((37, 32), (51, 32), (37, 39), (51, 39)):
            put("plant", tx, ty, solid=True)
        for tx in (39, 45, 51):
            put("sconce", tx, 31, oy=8)
            lamp(tx, 32, 80)

        # The matchbook, dropped roadside where the gate footage caught the
        # handoff — between the vault and the square, not inside either.
        matchbook = put("matchbook", 32, 25, pad=-4)
        self._look(matchbook, "A matchbook in the gravel", EVIDENCE_BY_ID["matchbook"]["found_text"], evidence="matchbook")

        # ---- The grounds -----------------------------------------------------
        for tx, ty in (
            (5, 5), (58, 26), (84, 26), (5, 35), (80, 35),
            (30, 45), (60, 45), (30, 64), (45, 64), (60, 64),
            (38, 26), (30, 55), (62, 55), (20, 40),
        ):
            put("tree", tx, ty, solid=(6, 26, 14, 10))
        for tx, ty in (
            (24, 8), (64, 42), (28, 44), (24, 33), (58, 50), (30, 50),
        ):
            put("bush", tx, ty, solid=(2, 6, 12, 8))
        for tx, ty in ((36, 44), (50, 44), (20, 65), (64, 65)):
            put("flowers", tx, ty)

        # ---- the street itself ------------------------------------------------
        # Utility poles down the top and bottom spines, with the wires strung
        # between them. Kept off the roadway so nothing blocks a crossing.
        # `pole_row`, not `row` — that name is the helper defined at the top of
        # this method, and binding it to an int here would break any later call.
        self.wires = []
        for pole_row, xs in ((20, (26, 32, 40, 50, 62, 80)), (62, (20, 30, 45, 60, 70))):
            last = None
            for tx in xs:
                put("pole", tx, pole_row, solid=(3, 30, 4, 5))
                top = (tx * TILE + 5, pole_row * TILE + 8)
                if last:
                    self.wires.append((last, top))
                last = top

        for tx, ty in ((18, 18), (64, 18), (18, 59), (56, 59)):
            put("bin", tx, ty, solid=(1, 8, 10, 6))
        for tx, ty in ((30, 32), (50, 32), (44, 20)):
            put("drain", tx, ty)
        for tx, ty in ((20, 18), (70, 18)):
            put("hydrant", tx, ty, solid=(1, 8, 6, 5))
        for tx, ty in ((5, 64), (83, 64)):
            put("lamp", tx, ty, solid=(2, 24, 12, 6))
            lamp(tx, ty, 74, oy=26)

    # --- queries -------------------------------------------------------------

    def zone_at(self, x, y):
        """Which building (if any) this world point falls inside — used to
        fire the "entering a building" cutscene at the right doorway."""
        tx, ty = int(x) // TILE, int(y) // TILE
        if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
            return self.zone_grid[ty][tx]
        return None

    def solid_at(self, rect):
        """True if this world rect overlaps a wall or a blocking prop."""
        x0, y0 = rect.left // TILE, rect.top // TILE
        x1, y1 = (rect.right - 1) // TILE, (rect.bottom - 1) // TILE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
                    return True
                if self.grid[ty][tx] not in WALKABLE:
                    return True
        return rect.collidelist(self.blockers) != -1

    def interactable_near(self, point, zone=None):
        """The closest thing worth pressing E on, or None.

        Only things sharing the player's building count: with roofs on, a
        terminal you cannot see through a wall should not be reachable either.
        """
        best, best_d = None, INTERACT_RANGE**2
        for it in self.interactables:
            if self.zone_at(it["rect"].centerx, it["rect"].centery) != zone:
                continue
            if it["rect"].collidepoint(point):
                return it
            cx = max(it["rect"].left, min(point[0], it["rect"].right))
            cy = max(it["rect"].top, min(point[1], it["rect"].bottom))
            d = (cx - point[0]) ** 2 + (cy - point[1]) ** 2
            if d < best_d:
                best, best_d = it, d
        return best

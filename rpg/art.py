"""Every pixel in the game is made here.

There are no image files. Characters are hand-authored as string art — one
character per pixel, read against a legend — because shape is what sells a
16-pixel sprite. Tiles and furniture are generated with seeded noise so a floor
has texture without a hundred variants being drawn by hand.
"""

import math
import random

import pygame

from settings import *


# --- string art --------------------------------------------------------------


def from_art(rows, legend):
    """Turn rows of legend characters into a surface. '.' is transparent."""
    h = len(rows)
    w = len(rows[0])
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        assert len(row) == w, f"row {y} is {len(row)} wide, expected {w}"
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            surf.set_at((x, y), legend[ch])
    return surf


def stack(*parts):
    """Compose sprites top to bottom into one surface."""
    w = max(p.get_width() for p in parts)
    h = sum(p.get_height() for p in parts)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    y = 0
    for p in parts:
        out.blit(p, ((w - p.get_width()) // 2, y))
        y += p.get_height()
    return out


# --- the detective -----------------------------------------------------------

COAT = (66, 74, 118)
COAT_D = (42, 48, 84)
COAT_L = (96, 106, 156)

DET = {
    "_": INK,
    "H": (48, 44, 68),
    "h": (70, 66, 94),
    "b": (30, 28, 46),
    "s": (216, 162, 120),
    "S": (172, 122, 88),
    "e": (30, 24, 36),
    "c": COAT,
    "C": COAT_D,
    "k": COAT_L,
    "t": (203, 202, 190),
    "p": (56, 54, 78),
    "o": (42, 36, 44),
}

# Twenty rows of body; the last three rows are swapped out per walk frame.
DET_DOWN = [
    "................",
    ".....______.....",
    "...._HHhhHH_....",
    "...._HhhhhH_....",
    "...._HHHHHH_....",
    ".._HHHHHHHHHH_..",
    ".._bbbbbbbbbb_..",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    ".._cccccccccc_..",
    ".._ccckttkcck_..",
    ".._ccckttkcck_..",
    ".._ccckttkcck_..",
    ".._CcckttkccC_..",
    ".._CCCCCCCCCC_..",
]

DET_UP = [
    "................",
    ".....______.....",
    "...._HHhhHH_....",
    "...._HhhhhH_....",
    "...._HHHHHH_....",
    ".._HHHHHHHHHH_..",
    ".._bbbbbbbbbb_..",
    "...._bbbbbb_....",
    "...._HHHHHH_....",
    "...._HHHHHH_....",
    "...._HHHHHH_....",
    "...._SHHHHS_....",
    "....._ssss_.....",
    "....._cccc_.....",
    ".._cccccccccc_..",
    ".._ccccCCccck_..",
    ".._ccccCCccck_..",
    ".._ccccCCccck_..",
    ".._CcccCCcccC_..",
    ".._CCCCCCCCCC_..",
]

# Profile, facing right. Mirrored at build time for the left-facing set.
DET_SIDE = [
    "................",
    ".....?????......",
    "...._HHHHH_.....",
    "...._HhhhH_.....",
    "...._HHHHH_.....",
    "..._HHHHHHHHH_..",
    "..._bbbbbbbbb_..",
    "...._SSSSS_.....",
    "...._sssss_.....",
    "...._ssess_.....",
    "...._sssss_.....",
    "...._sSSss_.....",
    "....._sss_......",
    "....._ttt_......",
    "..._ccccccc_....",
    "..._Ckccccc_....",
    "..._Ckccccc_....",
    "..._Ckccccc_....",
    "..._CCcccck_....",
    "..._CCCCCCC_....",
]
DET_SIDE = [r.replace("?", "_") for r in DET_SIDE]

# Walk cycle: stand, left foot, stand, right foot.
LEGS_FRONT = [
    ["....ppp..ppp....", "....ppp..ppp....", "....ooo..ooo...."],
    ["....ppp..ppp....", "...ppp....pp....", "...ooo....oo...."],
    ["....ppp..ppp....", "....ppp..ppp....", "....ooo..ooo...."],
    ["....ppp..ppp....", "....pp....ppp...", "....oo....ooo..."],
]

LEGS_SIDE = [
    ["....ppppp.......", "....ppppp.......", "...oooooo......."],
    ["...pp..ppp......", "..ppp....pp.....", "..ooo....ooo...."],
    ["....ppppp.......", "....ppppp.......", "...oooooo......."],
    ["...ppp.ppp......", "...pp....ppp....", "...oo....ooo...."],
]


def build_actor(body_down, body_up, body_side, legs_front, legs_side, legend):
    """Assemble a four-direction, four-frame walk cycle."""
    out = {}
    for name, body, legs in (
        ("down", body_down, legs_front),
        ("up", body_up, legs_front),
        ("right", body_side, legs_side),
    ):
        out[name] = [from_art(body + frame, legend) for frame in legs]
    out["left"] = [pygame.transform.flip(f, True, False) for f in out["right"]]
    return out


# --- Elias, seated -----------------------------------------------------------

ELIAS = {
    "_": INK,
    "n": (43, 34, 51),
    "s": (208, 168, 134),
    "S": (168, 126, 98),
    "e": (30, 24, 36),
    "a": (198, 196, 182),
    "A": (158, 156, 146),
    "w": (104, 108, 138),
    "p": (60, 58, 74),
}

ELIAS_SEATED = [
    "................",
    "....._nnnn_.....",
    "...._nnnnnn_....",
    "...._nnnnnn_....",
    "...._nssssn_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._SssS_.....",
    "..._wwaaaaww_...",
    "..._wwaaaaww_...",
    "..._wwaaaaww_...",
    "..._wwaaaaww_...",
    "..._sAaaaaAs_...",
    "..._AAAAAAAA_...",
    "..._pppppppp_...",
    "..._pppppppp_...",
]

# The same man, slumped — used once his composure is gone.
ELIAS_BROKEN = [
    "................",
    "................",
    "....._nnnn_.....",
    "...._nnnnnn_....",
    "...._nnnnnn_....",
    "...._nssssn_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "...._ssssss_....",
    "....._SSSS_.....",
    "....._SssS_.....",
    "..._wwaaaaww_...",
    "..._wwaaaaww_...",
    "..._wwaaaaww_...",
    "..._sAaaaaAs_...",
    "..._AAAAAAAA_...",
    "..._pppppppp_...",
    "..._pppppppp_...",
    "................",
]


# --- the four suspects, standing --------------------------------------------
#
# All four reuse the detective's own proven body geometry (DET_DOWN for a
# normal, composed stance; DET_UP - head tucked down and away - for the
# "broken" reaction) so there is zero risk of a row-width mismatch. What makes
# each character read as a different person is the legend: uniform colour,
# skin tone, cap. None of the four ever walk, so there is no per-direction
# walk cycle - just one calm pose and one broken pose apiece, standing on the
# same static leg frame the detective uses at rest.

_STAND_LEGS = LEGS_FRONT[0]


def _standing(body, legend):
    return from_art(body + _STAND_LEGS, legend)


# Each suspect gets their own build and headgear rather than a recolour of the
# detective: a patrol cap over heavy shoulders reads as a different man from a
# garrison cap over a narrow frame, even at sixteen pixels. Every body is 20
# rows of 16 so it drops onto the same standing legs.

THORNE_BODY = [
    "................",
    "...._______.....",
    "..._HHhhhhHH_...",
    "..._HhhhhhhH_...",
    "..._HHHHHHHH_...",
    ".._bbbbbbbbbb_..",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    "._cccccccccccc_.",
    "._ccckttkccccc_.",
    "._ccckttkccccc_.",
    "._ccckttkccccc_.",
    "._ccckttkccccc_.",
    "._CcckttkcccCC_.",
    "._CCCCCCCCCCCC_.",
]
THORNE_SLUMP = [
    "................",
    "................",
    "...._______.....",
    "..._HHhhhhHH_...",
    "..._HhhhhhhH_...",
    "..._HHHHHHHH_...",
    ".._bbbbbbbbbb_..",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    "._cccccccccccc_.",
    "._ccckttkccccc_.",
    "._ccckttkccccc_.",
    "._ccckttkccccc_.",
    "._CcckttkcccCC_.",
    "._CCCCCCCCCCCC_.",
    "................",
    "................",
]

DOSS_BODY = [
    "................",
    "................",
    "....._HHHH_.....",
    "...._HhhhhH_....",
    "..._HHHHHHHH_...",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._ssss_.....",
    "....._tttt_.....",
    "..._cccccccc_...",
    "..._ckttkccc_...",
    "..._ckttkccc_...",
    "..._ckttkccc_...",
    "..._ckttkccc_...",
    "..._CkttkccC_...",
    "..._CCCCCCCC_...",
]
DOSS_SLUMP = [
    "................",
    "................",
    "................",
    "....._HHHH_.....",
    "...._HhhhhH_....",
    "..._HHHHHHHH_...",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    "..._cccccccc_...",
    "..._ckttkccc_...",
    "..._ckttkccc_...",
    "..._ckttkccc_...",
    "..._CkttkccC_...",
    "..._CCCCCCCC_...",
    "................",
    "................",
    "................",
]

ASHWORTH_BODY = [
    "................",
    "...._______.....",
    "...._HHHHHH_....",
    "...._HhhhhH_....",
    "..._HHHHHHHH_...",
    ".._bbbbbbbbbb_..",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    ".._cccccccccc_..",
    ".._cckcccckcc_..",
    ".._cckcccckcc_..",
    ".._cckcccckcc_..",
    ".._cckcccckcc_..",
    ".._CckcccckcC_..",
    ".._CCCCCCCCCC_..",
]
ASHWORTH_SLUMP = [
    "................",
    "................",
    "...._______.....",
    "...._HHHHHH_....",
    "...._HhhhhH_....",
    "..._HHHHHHHH_...",
    ".._bbbbbbbbbb_..",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    ".._cccccccccc_..",
    ".._cckcccckcc_..",
    ".._cckcccckcc_..",
    ".._cckcccckcc_..",
    ".._CckcccckcC_..",
    ".._CCCCCCCCCC_..",
    "................",
    "................",
]

# Bricker stands hunched: short neck, shoulders riding high, hands in pockets.
BRICKER_BODY = [
    "................",
    "................",
    "....._HHHH_.....",
    "...._HHHHHH_....",
    "...._hhhhhh_....",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sesses_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    ".._cccccccccc_..",
    ".._cccccccccc_..",
    ".._cCCccccCCc_..",
    ".._cCCccccCCc_..",
    ".._cccccccccc_..",
    ".._cccccccccc_..",
    ".._CccccccccC_..",
    ".._CCCCCCCCCC_..",
]
BRICKER_SLUMP = [
    "................",
    "................",
    "................",
    "....._HHHH_.....",
    "...._HHHHHH_....",
    "...._hhhhhh_....",
    "...._SSSSSS_....",
    "...._ssssss_....",
    "...._sSSSSs_....",
    "....._ssss_.....",
    "....._tttt_.....",
    ".._cccccccccc_..",
    ".._cCCccccCCc_..",
    ".._cCCccccCCc_..",
    ".._cccccccccc_..",
    ".._cccccccccc_..",
    ".._CccccccccC_..",
    ".._CCCCCCCCCC_..",
    "................",
    "................",
]


# Every legend below is the character's actual uniform, not a colour swap:
# 'c/C/k' is the garment, 't' the collar, 'p/o' the trousers and boots. Where a
# uniform is a single piece of cloth the trousers share the jacket's colour,
# which is what makes coveralls read as coveralls and not as a shirt.

# Staff Sergeant, off duty at the cabin: olive field uniform, matching trousers.
THORNE = {
    "_": INK, "H": (52, 58, 44), "h": (74, 86, 58), "b": (30, 28, 46),
    "s": (208, 168, 134), "S": (172, 122, 88), "e": (30, 24, 36),
    "c": (74, 86, 58), "C": (54, 64, 42), "k": (100, 114, 80),
    "t": (60, 70, 50), "p": (58, 66, 46), "o": (34, 38, 30),
}
THORNE_STANDING = _standing(THORNE_BODY, THORNE)
THORNE_BROKEN = _standing(THORNE_SLUMP, THORNE)

# Corporal on vault duty: tan working fatigues, trousers to match, dark boots.
DOSS = {
    "_": INK, "H": (86, 78, 54), "h": (138, 126, 90), "b": (30, 28, 46),
    "s": (216, 172, 132), "S": (176, 128, 92), "e": (30, 24, 36),
    "c": (132, 118, 84), "C": (98, 86, 58), "k": (162, 148, 112),
    "t": (98, 86, 58), "p": (118, 106, 74), "o": (46, 40, 28),
}
DOSS_STANDING = _standing(DOSS_BODY, DOSS)
DOSS_OPEN = _standing(DOSS_SLUMP, DOSS)

# Battalion Commander: army service dress, not navy blue. Deep olive with the
# brass showing — 'k' runs as the double-breasted button rows on her body.
ASHWORTH = {
    "_": INK, "H": (48, 54, 42), "h": (70, 78, 58), "b": (26, 30, 24),
    "s": (196, 158, 128), "S": (158, 118, 92), "e": (30, 24, 36),
    "c": (64, 72, 54), "C": (44, 50, 38), "k": (198, 158, 76),
    "t": (206, 202, 186), "p": (52, 58, 44), "o": (28, 30, 24),
}
ASHWORTH_STANDING = _standing(ASHWORTH_BODY, ASHWORTH)
ASHWORTH_OPEN = _standing(ASHWORTH_SLUMP, ASHWORTH)

# Motor pool mechanic: one-piece coveralls, so the trousers are the same cloth
# as the chest — that continuity is the whole silhouette.
BRICKER = {
    "_": INK, "H": (40, 40, 46), "h": (60, 60, 68), "b": (26, 26, 32),
    "s": (212, 166, 126), "S": (170, 120, 86), "e": (30, 24, 36),
    "c": (58, 68, 84), "C": (40, 48, 62), "k": (84, 96, 114),
    "t": (58, 68, 84), "p": (58, 68, 84), "o": (30, 28, 26),
}
BRICKER_STANDING = _standing(BRICKER_BODY, BRICKER)
BRICKER_SHAKEN = _standing(BRICKER_SLUMP, BRICKER)

def _mark(surf, pixels):
    """Stamp a few extra pixels onto a built sprite — small insignia and
    wear that make four recolours of the same body read as four people."""
    for x, y, colour in pixels:
        surf.set_at((x, y), colour)
    return surf


# Insignia sit on the sleeve of each body, so the coordinates below are per
# build rather than shared — a mark placed for one silhouette lands off the
# edge of a narrower one.

# Sergeant's chevrons, on the broad sleeve.
_mark(THORNE_STANDING, [
    (3, 15, (196, 190, 150)), (4, 16, (196, 190, 150)), (3, 17, (196, 190, 150)),
])
_mark(THORNE_BROKEN, [
    (3, 14, (196, 190, 150)), (4, 15, (196, 190, 150)), (3, 16, (196, 190, 150)),
])

# A wrench on the belt — the vault NCO who signs for the tools.
_mark(DOSS_STANDING, [
    (10, 17, (176, 176, 184)), (10, 18, (176, 176, 184)), (9, 18, (140, 140, 148)),
])
_mark(DOSS_OPEN, [
    (10, 15, (176, 176, 184)), (10, 16, (176, 176, 184)), (9, 16, (140, 140, 148)),
])

# A colonel's shoulder star — gold, unmissable next to two corporals.
_mark(ASHWORTH_STANDING, [
    (10, 14, BRASS), (11, 14, BRASS), (10, 15, BRASS_D),
])
_mark(ASHWORTH_OPEN, [
    (10, 13, BRASS), (11, 13, BRASS), (10, 14, BRASS_D),
])

# Grease on the coat — a motor pool mechanic never quite gets clean.
_mark(BRICKER_STANDING, [
    (7, 17, (64, 46, 28)), (8, 18, (64, 46, 28)), (6, 18, (82, 60, 36)),
])
_mark(BRICKER_SHAKEN, [
    (7, 15, (64, 46, 28)), (8, 16, (64, 46, 28)), (6, 16, (82, 60, 36)),
])

NPC_ART = {
    "thorne": (THORNE_STANDING, THORNE_BROKEN),
    "doss": (DOSS_STANDING, DOSS_OPEN),
    "ashworth": (ASHWORTH_STANDING, ASHWORTH_OPEN),
    "bricker": (BRICKER_STANDING, BRICKER_SHAKEN),
}


# --- tiles -------------------------------------------------------------------


def _speckle(surf, rng, colours, count):
    for _ in range(count):
        x, y = rng.randrange(TILE), rng.randrange(TILE)
        surf.set_at((x, y), rng.choice(colours))


def tile_grass(seed):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(GRASS)
    _speckle(s, rng, [GRASS_D, GRASS_L], 34)
    # A few upright blades so the ground has a direction.
    for _ in range(rng.randrange(2, 5)):
        x, y = rng.randrange(1, TILE - 1), rng.randrange(2, TILE - 2)
        pygame.draw.line(s, GRASS_L, (x, y), (x, y - 2))
        s.set_at((x, y + 1), GRASS_D)
    return s


def tile_stone_path(seed):
    """Irregular cobbles — the mortar is what reads at this size."""
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(STONE_D)
    y = 0
    row = 0
    while y < TILE:
        h = rng.choice((5, 6))
        x = -rng.randrange(0, 6) if row % 2 else 0
        while x < TILE:
            w = rng.choice((5, 6, 7))
            pygame.draw.rect(s, rng.choice((STONE, STONE, STONE_L)), (x + 1, y + 1, w - 1, h - 1))
            x += w
        y += h
        row += 1
    _speckle(s, rng, [STONE_D, STONE_L], 8)
    return s


def tile_marble(seed, dark=False):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(MARBLE_D if dark else MARBLE)
    # Veining: a short drunken walk across the slab.
    vein = MARBLE_L if dark else MARBLE_D
    x, y = rng.randrange(TILE), rng.randrange(TILE)
    for _ in range(rng.randrange(5, 11)):
        s.set_at((x % TILE, y % TILE), vein)
        x += rng.choice((0, 1, 1))
        y += rng.choice((-1, 0, 1))
    # Grout on two edges only, so slabs read as a grid rather than as boxes.
    pygame.draw.line(s, STONE_D, (0, 0), (TILE - 1, 0))
    pygame.draw.line(s, STONE_D, (0, 0), (0, TILE - 1))
    return s


def tile_wood(seed):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(WOOD)
    for y in range(0, TILE, 4):
        pygame.draw.line(s, WOOD_D, (0, y), (TILE - 1, y))
        for _ in range(3):
            gx = rng.randrange(TILE)
            pygame.draw.line(s, WOOD_L, (gx, y + 2), (min(TILE - 1, gx + rng.randrange(2, 5)), y + 2))
    # Butt joints between boards.
    for y in range(0, TILE, 4):
        if rng.random() < 0.4:
            jx = rng.randrange(TILE)
            pygame.draw.line(s, WOOD_D, (jx, y), (jx, y + 3))
    return s


def tile_carpet(seed, border=None):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(CARPET)
    _speckle(s, rng, [CARPET_D, CARPET_L], 40)
    if border:
        for edge in border:
            if edge == "n":
                pygame.draw.rect(s, BRASS_D, (0, 0, TILE, 2))
            elif edge == "s":
                pygame.draw.rect(s, BRASS_D, (0, TILE - 2, TILE, 2))
            elif edge == "w":
                pygame.draw.rect(s, BRASS_D, (0, 0, 2, TILE))
            elif edge == "e":
                pygame.draw.rect(s, BRASS_D, (TILE - 2, 0, 2, TILE))
    return s


def tile_wall_face(seed):
    """The side of a wall you actually look at, in three-quarter view."""
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(WALL_D)
    for i, y in enumerate(range(0, TILE, 8)):
        off = 0 if i % 2 == 0 else -4
        x = off
        while x < TILE:
            pygame.draw.rect(s, WALL, (x + 1, y + 1, 7, 6))
            pygame.draw.line(s, WALL_L, (x + 1, y + 1), (x + 7, y + 1))
            x += 8
    _speckle(s, rng, [WALL_D, WALL_L], 6)
    return s


def tile_wall_top(seed):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(WALL_L)
    _speckle(s, rng, [WALL, (120, 118, 146)], 20)
    pygame.draw.line(s, WALL, (0, TILE - 1), (TILE - 1, TILE - 1))
    return s


def tile_wainscot(seed):
    """Panelled dado — the gallery walls, so they don't read as a dungeon."""
    s = tile_wall_face(seed)
    pygame.draw.rect(s, WOOD_D, (0, 6, TILE, TILE - 6))
    pygame.draw.rect(s, WOOD, (1, 8, TILE - 2, TILE - 10))
    pygame.draw.line(s, WOOD_L, (1, 8), (TILE - 2, 8))
    pygame.draw.rect(s, BRASS_D, (0, 5, TILE, 1))
    return s


# --- building exteriors ------------------------------------------------------
#
# A building seen from outside is a roof, and a flat rectangle of shingles
# reads as a lid rather than a structure. Each one is built as a pitched roof
# instead: a back slope in shadow, a ridge cap catching the light, a front
# slope, and a dark eave overhanging the wall below. Materials differ per
# building so the fort, the precinct and a fisherman's cabin are told apart
# from across the map.

ROOF_STYLES = {
    # Cooler grey-blue concrete and a flat, near-parapet cap - facade_rows is
    # high so most of the structure reads as wall, only a thin flat lid on
    # top, the way an actual bunker roofline would.
    "military": dict(
        back=(36, 39, 44), front=(52, 55, 59), cap=(59, 62, 66),
        eave=(26, 29, 34), trim=(40, 43, 48), vents=True,
        wall=(74, 77, 82), wall_d=(48, 50, 53), wall_l=(94, 98, 104),
        course="block", facade_rows=4),
    # A steep, dramatic true gable - facade_rows is low so most of the
    # structure reads as roof.
    "civic": dict(
        back=(50, 36, 31), front=(66, 52, 46), cap=(73, 59, 53),
        eave=(40, 26, 21), trim=(54, 40, 35), sign=True,
        wall=(90, 63, 54), wall_d=(59, 41, 35), wall_l=(114, 80, 69),
        course="brick", facade_rows=1),
    # A painted family home, so it doesn't read as the fishing cabin's twin:
    # brick-red tiles over pale clapboard, with a lit porch (`porch`).
    "house": dict(
        back=(58, 30, 28), front=(84, 46, 40), cap=(96, 56, 48),
        eave=(38, 18, 16), trim=(70, 40, 34), chimney=True, porch=True,
        wall=(128, 116, 98), wall_d=(88, 78, 64), wall_l=(158, 146, 124),
        course="board"),
    "cabin": dict(
        back=(28, 21, 14), front=(44, 37, 29), cap=(51, 44, 36),
        eave=(18, 11, 4), trim=(32, 25, 18), chimney=True,
        wall=(70, 60, 46), wall_d=(46, 39, 30), wall_l=(89, 76, 58),
        course="board"),
    # Institutional: pale rendered walls, a low flat roof with vents - the
    # same bunker-flat proportions as military.
    "lab": dict(
        back=(50, 54, 59), front=(66, 70, 74), cap=(73, 77, 81),
        eave=(40, 44, 49), trim=(54, 58, 63), vents=True,
        wall=(122, 128, 136), wall_d=(79, 83, 88), wall_l=(155, 163, 173),
        course="block", facade_rows=4),
}


def facade_tile(style, seed):
    """One tile of the front wall a building shows the camera. A roof alone
    reads as paper laid on the ground; the wall under it is what gives the
    building a front."""
    p = ROOF_STYLES[style]
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(p["wall"])
    if p["course"] == "brick":
        for i, y in enumerate(range(0, TILE, 4)):
            x = 0 if i % 2 == 0 else -4
            while x < TILE:
                pygame.draw.rect(s, p["wall_l"], (x + 1, y + 1, 6, 2))
                x += 8
    elif p["course"] == "block":
        for y in range(0, TILE, 6):
            pygame.draw.line(s, p["wall_d"], (0, y), (TILE - 1, y))
        for x in range(0, TILE, 8):
            pygame.draw.line(s, p["wall_d"], (x, 0), (x, TILE - 1))
    else:  # board — horizontal siding
        for y in range(0, TILE, 3):
            pygame.draw.line(s, p["wall_d"], (0, y + 2), (TILE - 1, y + 2))
            pygame.draw.line(s, p["wall_l"], (0, y), (TILE - 1, y))
    _speckle(s, rng, [p["wall_d"], p["wall_l"]], 6)
    return s


def obj_facade_window(style):
    """A lit window. Every one of these is somebody still awake at 2am."""
    p = ROOF_STYLES[style]
    s = _surf(12, 12)
    _box(s, (0, 0, 12, 12), (46, 40, 36), p["wall_l"], INK)
    pygame.draw.rect(s, LAMP, (2, 2, 8, 8))
    pygame.draw.rect(s, GLOW, (2, 2, 8, 3))
    pygame.draw.line(s, (58, 48, 34), (6, 2), (6, 9))
    pygame.draw.line(s, (58, 48, 34), (2, 6), (9, 6))
    return s


def obj_house_window():
    """The Thorne house's window: a lit pane between two painted shutters,
    with a sill under it. A full tile wide, so the facade centres it."""
    p = ROOF_STYLES["house"]
    shutter, shutter_d = (52, 92, 76), (32, 62, 50)
    s = _surf(16, 14)
    for x in (0, 13):
        _box(s, (x, 0, 3, 12), shutter, None, shutter_d)
        for y in (3, 6, 9):  # louvre slats
            pygame.draw.line(s, shutter_d, (x, y), (x + 2, y))
    _box(s, (3, 0, 10, 12), (46, 40, 36), p["wall_l"], INK)
    pygame.draw.rect(s, LAMP, (5, 2, 6, 8))
    pygame.draw.rect(s, GLOW, (5, 2, 6, 3))
    pygame.draw.line(s, (58, 48, 34), (8, 2), (8, 9))
    pygame.draw.line(s, (58, 48, 34), (5, 6), (10, 6))
    pygame.draw.rect(s, p["wall_l"], (2, 12, 12, 2))  # sill
    pygame.draw.rect(s, INK, (2, 13, 12, 1))
    return s


def obj_doorway():
    """The door between the Thorne kitchen and garage, seen from above: a
    timber jamb at each end of the gap in the wall, a worn threshold across
    the floor, and the leaf standing open into the garage. 32x32, two tiles
    tall, to fill the 1x2 opening the wall is cut with."""
    s = _surf(32, 32)
    for y in (0, 29):  # jambs
        _box(s, (0, y, 16, 3), WOOD, WOOD_L, WOOD_D)
    _box(s, (6, 3, 4, 26), WOOD_D, None, None, None)  # threshold
    pygame.draw.line(s, WOOD, (7, 3), (7, 28))
    # The leaf, hinged at the top jamb and swung open into the garage.
    _box(s, (2, 1, 27, 4), (116, 78, 50), (146, 104, 68), (74, 50, 32))
    pygame.draw.rect(s, BRASS, (25, 2, 2, 2))  # knob
    pygame.draw.rect(s, BRASS_D, (2, 0, 3, 2))  # hinge
    return s


def obj_porch_lamp():
    """A lantern by the front door, the only lamp on the house left burning."""
    s = _surf(16, 14)
    _box(s, (6, 0, 4, 2), BRASS_D, BRASS, INK)
    _box(s, (5, 2, 6, 8), LAMP, GLOW, LAMP_D)
    pygame.draw.rect(s, BRASS_D, (5, 10, 6, 2))
    pygame.draw.rect(s, INK, (5, 10, 6, 2), 1)
    return s


def obj_house_number():
    """A brass plate reading 14, drawn pixel by pixel: the address of the
    house the whole case starts from."""
    s = _surf(16, 10)
    _box(s, (3, 0, 10, 9), BRASS_D, BRASS, INK)
    ink = (34, 26, 12)
    for x, y, w, h in ((5, 2, 1, 5), (4, 3, 1, 1), (4, 6, 3, 1),          # 1
                       (8, 2, 1, 3), (10, 2, 1, 5), (8, 4, 3, 1)):         # 4
        pygame.draw.rect(s, ink, (x, y, w, h))
    return s


def obj_facade_door(style):
    """The way in. A panelled timber door on the houses and the precinct, a
    steel one with a wired vision panel on the fort and the lab — the same
    rustic door on a concrete armoury never looked right."""
    p = ROOF_STYLES[style]
    s = _surf(16, 24)
    # Frame and lintel, cut into the wall.
    pygame.draw.rect(s, p["wall_d"], (0, 0, 16, 24))
    pygame.draw.rect(s, p["wall_l"], (0, 0, 16, 2))
    pygame.draw.rect(s, INK, (0, 0, 16, 24), 1)

    if style in ("military", "lab"):
        leaf, dark, light = (108, 114, 118), (72, 78, 82), (150, 156, 158)
        pygame.draw.rect(s, leaf, (2, 3, 12, 20))
        pygame.draw.rect(s, light, (2, 3, 12, 1))
        pygame.draw.rect(s, dark, (2, 21, 12, 2))
        pygame.draw.rect(s, dark, (7, 3, 1, 20))  # leaf seam
        pygame.draw.rect(s, (52, 64, 68), (3, 6, 10, 6))  # vision panel
        pygame.draw.rect(s, (124, 154, 160), (4, 7, 8, 4))
        for gx in range(5, 12, 2):  # wired glass
            pygame.draw.rect(s, (72, 92, 96), (gx, 7, 1, 4))
        pygame.draw.rect(s, INK, (3, 6, 10, 6), 1)
        pygame.draw.rect(s, (178, 182, 184), (3, 15, 10, 2))  # push bar
        pygame.draw.rect(s, (86, 90, 92), (3, 17, 10, 1))
    else:
        leaf, dark, light = (116, 78, 50), (74, 50, 32), (146, 104, 68)
        if style == "house":  # a painted front door, not bare timber
            leaf, dark, light = (52, 92, 76), (32, 62, 50), (78, 128, 106)
        pygame.draw.rect(s, leaf, (2, 3, 12, 20))
        pygame.draw.rect(s, light, (2, 3, 12, 1))
        for y in (5, 14):  # two raised panels
            pygame.draw.rect(s, dark, (4, y, 8, 6))
            pygame.draw.rect(s, light, (4, y + 5, 8, 1))
            pygame.draw.rect(s, INK, (4, y, 8, 6), 1)
        pygame.draw.rect(s, BRASS, (11, 12, 2, 2))  # knob
        pygame.draw.rect(s, BRASS_D, (11, 14, 2, 1))
    # Threshold, so the door meets the ground instead of floating on the wall.
    pygame.draw.rect(s, p["wall_l"], (0, 23, 16, 1))
    return s


def obj_door_vault():
    """The vault's own door - thicker steel, a lockwheel instead of a knob,
    twin heavy hinges. Built to keep five tons of ordnance in, not to keep
    an office private."""
    p = ROOF_STYLES["military"]
    s = _surf(16, 24)
    pygame.draw.rect(s, p["wall_d"], (0, 0, 16, 24))
    pygame.draw.rect(s, p["wall_l"], (0, 0, 16, 2))
    pygame.draw.rect(s, INK, (0, 0, 16, 24), 1)
    leaf, dark, light = (70, 74, 78), (46, 50, 54), (112, 116, 120)
    pygame.draw.rect(s, leaf, (1, 2, 14, 21))
    pygame.draw.rect(s, light, (1, 2, 14, 1))
    pygame.draw.rect(s, dark, (1, 21, 14, 2))
    for hy in (5, 17):  # heavy hinge barrels down one edge
        pygame.draw.rect(s, dark, (1, hy, 3, 4))
        pygame.draw.rect(s, light, (1, hy, 3, 1))
    pygame.draw.circle(s, dark, (9, 12), 5)
    pygame.draw.circle(s, light, (9, 12), 5, 1)
    for ang in range(0, 360, 60):
        rad = math.radians(ang)
        pygame.draw.line(s, dark, (9, 12), (9 + int(4 * math.cos(rad)), 12 + int(4 * math.sin(rad))))
    pygame.draw.circle(s, (32, 34, 36), (9, 12), 2)  # the wheel's hub
    pygame.draw.rect(s, p["wall_l"], (0, 23, 16, 1))
    return s


def obj_door_motorpool():
    """A wide bay shutter, corrugated top to bottom - reads as roll-up even
    though it sits in the same door slot as everything else."""
    p = ROOF_STYLES["military"]
    s = _surf(16, 24)
    pygame.draw.rect(s, p["wall_d"], (0, 0, 16, 24))
    pygame.draw.rect(s, p["wall_l"], (0, 0, 16, 2))
    pygame.draw.rect(s, INK, (0, 0, 16, 24), 1)
    leaf, dark, light = (96, 100, 104), (64, 68, 72), (134, 138, 140)
    pygame.draw.rect(s, leaf, (1, 2, 14, 21))
    for y in range(3, 22, 3):  # corrugated ribs
        pygame.draw.line(s, dark, (1, y), (14, y))
        pygame.draw.line(s, light, (1, y + 1), (14, y + 1))
    pygame.draw.rect(s, dark, (1, 21, 14, 2))
    pygame.draw.rect(s, (178, 182, 184), (6, 11, 4, 2))  # pull handle
    pygame.draw.rect(s, p["wall_l"], (0, 23, 16, 1))
    return s


def obj_door_precinct():
    """The precinct's timber door under a canvas awning - the one entrance in
    the city that announces itself before you reach it."""
    p = ROOF_STYLES["civic"]
    s = _surf(16, 24)
    awning, awning_d = (138, 88, 46), (94, 58, 28)
    pygame.draw.polygon(s, awning, [(0, 3), (16, 3), (13, 0), (3, 0)])
    pygame.draw.polygon(s, awning_d, [(0, 3), (16, 3), (13, 0), (3, 0)], 1)
    for x in range(2, 15, 4):
        pygame.draw.line(s, awning_d, (x, 0), (x - 1, 3))
    pygame.draw.rect(s, INK, (0, 3, 16, 21), 1)
    leaf, dark, light = (116, 78, 50), (74, 50, 32), (146, 104, 68)
    pygame.draw.rect(s, leaf, (2, 5, 12, 18))
    pygame.draw.rect(s, light, (2, 5, 12, 1))
    for y in (7, 15):
        pygame.draw.rect(s, dark, (4, y, 8, 6))
        pygame.draw.rect(s, light, (4, y + 5, 8, 1))
        pygame.draw.rect(s, INK, (4, y, 8, 6), 1)
    pygame.draw.rect(s, BRASS, (11, 12, 2, 2))
    pygame.draw.rect(s, BRASS_D, (11, 14, 2, 1))
    pygame.draw.rect(s, p["wall_l"], (0, 23, 16, 1))
    return s


def obj_window_vault():
    """A narrow observation slit rather than a proper window - nobody looks
    out of a vault to enjoy the view."""
    p = ROOF_STYLES["military"]
    s = _surf(12, 12)
    _box(s, (0, 0, 12, 12), (46, 40, 36), p["wall_l"], INK)
    pygame.draw.rect(s, LAMP, (5, 2, 2, 8))
    pygame.draw.rect(s, GLOW, (5, 2, 2, 3))
    return s


def obj_stairs():
    """A stairwell, drawn top-down so it reads as an opening in the floor
    rather than a door - used both ways, up and down, between a building's
    two floors."""
    s = _surf(24, 24)
    _box(s, (2, 2, 20, 20), (28, 26, 24), (44, 40, 36), INK)
    for i, y in enumerate(range(5, 20, 3)):
        shade = 24 + i * 6
        pygame.draw.rect(s, (shade, shade - 2, shade - 4), (4, y, 16, 2))
    return s


def roof_tile(base, light, seed):
    """One tile of shingle course in a given shade."""
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(base)
    for i, y in enumerate(range(0, TILE, 5)):
        x = 0 if i % 2 == 0 else -3
        while x < TILE:
            pygame.draw.rect(s, light, (x + 1, y, 5, 4))
            pygame.draw.line(s, base, (x + 1, y + 3), (x + 5, y + 3))
            x += 6
    _speckle(s, rng, [base, light], 7)
    return s


def build_roof_tiles(style):
    """Shingle courses for one material: shadowed back slope, lit front slope."""
    p = ROOF_STYLES[style]
    return {
        "back": [roof_tile(p["back"], p["trim"], i) for i in range(3)],
        "front": [roof_tile(p["front"], p["cap"], i + 7) for i in range(3)],
    }


def obj_steel_shelf():
    """Industrial racking. The armoury's version of a bookshelf, which is to
    say: no books, no wood, and everything on it is in a box with a number."""
    s = _surf(16, 26)
    _box(s, (0, 0, 16, 26), (72, 76, 78), (98, 102, 104), INK)
    for shelf_y in (2, 10, 18):
        pygame.draw.rect(s, (56, 60, 62), (1, shelf_y, 14, 6))
        x = 2
        while x < 14:
            bw = 3 if x % 2 else 4
            pygame.draw.rect(s, (86, 88, 78), (x, shelf_y + 1, bw, 5))
            pygame.draw.rect(s, (140, 142, 128), (x, shelf_y + 2, bw, 1))
            x += bw + 1
        pygame.draw.rect(s, (108, 112, 114), (1, shelf_y + 6, 14, 1))
    for x in (0, 15):  # uprights
        pygame.draw.rect(s, (52, 56, 58), (x, 0, 1, 26))
    return s


def obj_gun_locker():
    """A locked steel cabinet, chained and signed for."""
    s = _surf(14, 26)
    _box(s, (0, 0, 14, 26), (66, 70, 74), (94, 98, 102), INK)
    pygame.draw.rect(s, (52, 56, 60), (1, 2, 5, 22))
    pygame.draw.rect(s, (52, 56, 60), (8, 2, 5, 22))
    pygame.draw.rect(s, (120, 124, 128), (6, 2, 2, 22))  # centre seam
    pygame.draw.rect(s, (156, 148, 96), (5, 12, 4, 3))  # hasp
    pygame.draw.rect(s, (36, 38, 40), (6, 15, 2, 3))  # padlock
    for y in (5, 20):
        pygame.draw.rect(s, (172, 168, 150), (2, y, 3, 1))  # stencilled number
    return s


def obj_ammo_crate():
    """Stacked ammunition boxes, stencilled and banded."""
    s = _surf(18, 16)
    _box(s, (0, 7, 18, 9), (78, 72, 50), (100, 94, 66), (44, 40, 28))
    _box(s, (2, 0, 14, 8), (86, 80, 56), (108, 102, 72), (44, 40, 28))
    for bx in (5, 11):
        pygame.draw.rect(s, (52, 48, 34), (bx, 0, 1, 8))
        pygame.draw.rect(s, (52, 48, 34), (bx - 1, 7, 1, 9))
    pygame.draw.rect(s, (188, 182, 150), (4, 3, 8, 2))  # stencil block
    pygame.draw.rect(s, (188, 182, 150), (3, 10, 6, 1))
    return s


def obj_sandbags():
    s = _surf(20, 12)
    rng = random.Random(41)
    for row, y in enumerate((5, 0)):
        x = 0 if row % 2 == 0 else 4
        while x < 20:
            c = rng.choice(((122, 112, 84), (108, 98, 72), (134, 124, 94)))
            pygame.draw.ellipse(s, c, (x, y, 9, 7))
            pygame.draw.ellipse(s, (66, 60, 44), (x, y, 9, 7), 1)
            x += 8
    return s


def obj_lab_bench():
    """A forensics bench: black top, glassware, a burner, a specimen tray."""
    s = _surf(32, 20)
    _box(s, (0, 4, 32, 10), (48, 52, 56), (78, 84, 88), INK)
    pygame.draw.rect(s, (206, 212, 210), (0, 12, 32, 2))  # enamel apron
    pygame.draw.rect(s, (150, 158, 156), (2, 14, 6, 6))
    pygame.draw.rect(s, (150, 158, 156), (24, 14, 6, 6))
    for gx, col in ((4, (176, 206, 200)), (9, (196, 214, 180)), (14, (188, 168, 206))):
        pygame.draw.rect(s, col, (gx, 0, 3, 5))  # flasks
        pygame.draw.rect(s, INK, (gx, 0, 3, 5), 1)
        pygame.draw.rect(s, (226, 232, 230), (gx, 0, 3, 1))
    pygame.draw.rect(s, (62, 66, 70), (21, 1, 5, 4))  # burner
    pygame.draw.rect(s, (108, 168, 214), (22, 0, 3, 2))  # flame
    return s


def obj_microscope():
    s = _surf(12, 18)
    _box(s, (2, 12, 8, 6), (58, 62, 66), (88, 92, 96), INK)
    pygame.draw.rect(s, (72, 76, 80), (5, 3, 3, 10))
    pygame.draw.rect(s, (96, 100, 104), (3, 1, 6, 3))  # eyepiece
    pygame.draw.rect(s, (188, 214, 216), (3, 10, 6, 1))  # slide
    return s


def obj_specimen_cabinet():
    """Glass-fronted, everything inside bagged and tagged."""
    s = _surf(16, 26)
    _box(s, (0, 0, 16, 26), (196, 200, 198), (222, 226, 222), INK)
    pygame.draw.rect(s, (130, 156, 158), (2, 2, 12, 22))
    rng = random.Random(43)
    for y in (3, 11, 19):
        pygame.draw.rect(s, (168, 186, 186), (2, y + 6, 12, 1))
        x = 3
        while x < 13:
            w = rng.choice((2, 3))
            pygame.draw.rect(s, (214, 210, 190), (x, y, w, 6))
            pygame.draw.rect(s, (176, 60, 56), (x, y, w, 1))  # evidence seal
            x += w + 1
    pygame.draw.rect(s, (150, 154, 152), (7, 2, 1, 22))
    return s


def obj_fume_hood():
    s = _surf(24, 24)
    _box(s, (0, 0, 24, 24), (188, 192, 190), (216, 220, 216), INK)
    pygame.draw.rect(s, (58, 66, 70), (2, 4, 20, 14))
    pygame.draw.rect(s, (120, 150, 156), (3, 5, 18, 8))  # sash glass
    pygame.draw.rect(s, (162, 190, 194), (3, 5, 18, 2))
    pygame.draw.rect(s, (146, 150, 148), (2, 2, 20, 2))
    pygame.draw.rect(s, (92, 96, 94), (10, 18, 4, 6))
    return s


def obj_pole():
    """A utility pole. Nothing says city street after dark like a line of
    these marching off into the fog with the wires sagging between them."""
    s = _surf(10, 36)
    _box(s, (3, 6, 4, 30), (86, 62, 42), (112, 84, 58), (48, 34, 22))
    for y in range(10, 34, 6):
        pygame.draw.line(s, (58, 42, 28), (3, y), (6, y))
    pygame.draw.rect(s, (72, 52, 36), (0, 6, 10, 2))  # crossarm
    pygame.draw.rect(s, INK, (0, 6, 10, 2), 1)
    for x in (1, 8):  # glass insulators
        pygame.draw.rect(s, (104, 150, 152), (x, 3, 2, 3))
    pygame.draw.rect(s, (40, 30, 22), (2, 34, 6, 2))  # base
    return s


def obj_bin():
    s = _surf(12, 15)
    _box(s, (1, 3, 10, 12), (68, 72, 68), (92, 98, 90), INK)
    pygame.draw.rect(s, (54, 58, 54), (0, 1, 12, 3))
    pygame.draw.rect(s, INK, (0, 1, 12, 3), 1)
    pygame.draw.rect(s, (46, 50, 46), (5, 0, 2, 2))  # handle
    return s


def obj_drain():
    """A storm grate. Flat to the ground — nothing walks around it."""
    s = _surf(14, 8)
    _box(s, (0, 0, 14, 8), (52, 54, 58), (78, 80, 86), (30, 32, 36))
    for x in range(2, 13, 3):
        pygame.draw.rect(s, (22, 24, 28), (x, 2, 1, 5))
    return s


def obj_hydrant():
    s = _surf(8, 14)
    _box(s, (1, 3, 6, 11), (146, 52, 46), (180, 76, 64), INK)
    pygame.draw.rect(s, (180, 76, 64), (0, 5, 8, 2))
    pygame.draw.rect(s, (110, 38, 34), (2, 0, 4, 3))
    return s


def obj_chimney():
    s = _surf(10, 14)
    _box(s, (0, 2, 10, 12), (92, 62, 52), (118, 82, 66), INK)
    for y in (5, 9):
        pygame.draw.line(s, (62, 40, 34), (1, y), (8, y))
    pygame.draw.rect(s, (120, 86, 70), (0, 0, 10, 3))
    pygame.draw.rect(s, (24, 20, 20), (2, 1, 6, 2))  # the flue opening
    pygame.draw.rect(s, INK, (0, 0, 10, 3), 1)
    return s


def obj_roof_vent():
    s = _surf(12, 9)
    _box(s, (0, 2, 12, 7), (62, 68, 62), (88, 96, 86), INK)
    pygame.draw.rect(s, (86, 94, 84), (0, 0, 12, 3))
    for x in range(2, 11, 3):
        pygame.draw.rect(s, (34, 38, 34), (x, 4, 1, 4))
    return s


def obj_roof_sign(label_seed=0):
    """A precinct sign board hung off the eave. The lettering is suggested,
    not spelled — real glyphs at this size turn to mush."""
    s = _surf(26, 11)
    _box(s, (0, 0, 26, 9), (34, 30, 38), (58, 52, 62), INK)
    rng = random.Random(label_seed)
    x = 3
    while x < 23:
        w = rng.choice((2, 3))
        pygame.draw.rect(s, ACCENT, (x, 3, w, 3))
        x += w + 2
    for bx in (3, 22):  # the brackets it hangs from
        pygame.draw.rect(s, (72, 66, 78), (bx, 9, 1, 2))
    return s


def tile_concrete(seed):
    """Poured slab — an armoury and a motor pool have floors you can drop a
    crate on, not marble."""
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill((98, 96, 92))
    _speckle(s, rng, [(86, 84, 80), (114, 112, 106)], 34)
    pygame.draw.line(s, (82, 80, 76), (0, 0), (TILE - 1, 0))
    pygame.draw.line(s, (82, 80, 76), (0, 0), (0, TILE - 1))
    if rng.random() < 0.3:  # oil, ground in and never coming out
        ox, oy = rng.randrange(2, 10), rng.randrange(2, 10)
        pygame.draw.ellipse(s, (74, 72, 70), (ox, oy, 5, 4))
    return s


def tile_labfloor(seed):
    """Small sealed tile, the kind you can hose down."""
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill((150, 162, 158))
    for y in (0, 8):
        for x in (0, 8):
            pygame.draw.rect(s, (176, 188, 182), (x + 1, y + 1, 6, 6))
            pygame.draw.line(s, (196, 206, 200), (x + 1, y + 1), (x + 6, y + 1))
    _speckle(s, rng, [(164, 176, 170)], 5)
    return s


def tile_void():
    s = pygame.Surface((TILE, TILE))
    s.fill(NIGHT)
    return s


def tile_hedge(seed):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill(HEDGE)
    for _ in range(26):
        x, y = rng.randrange(TILE), rng.randrange(TILE)
        pygame.draw.rect(s, rng.choice((HEDGE_L, HEDGE, (28, 56, 40))), (x, y, 2, 2))
    return s


def tile_water(seed):
    rng = random.Random(seed)
    s = pygame.Surface((TILE, TILE))
    s.fill((44, 74, 122))
    for y in range(0, TILE, 3):
        pygame.draw.line(s, (60, 98, 152), (rng.randrange(0, 6), y), (rng.randrange(9, TILE), y))
    _speckle(s, rng, [(96, 140, 190)], 6)
    return s


def build_tiles():
    """Four variants per ground type; the map picks one from the coordinates."""
    t = {}
    t["grass"] = [tile_grass(i) for i in range(4)]
    t["path"] = [tile_stone_path(i) for i in range(4)]
    t["marble"] = [tile_marble(i, dark=False) for i in range(3)]
    t["marble_d"] = [tile_marble(i + 10, dark=True) for i in range(3)]
    t["wood"] = [tile_wood(i) for i in range(4)]
    t["carpet"] = [tile_carpet(i) for i in range(3)]
    t["wall"] = [tile_wall_face(i) for i in range(3)]
    t["wall_top"] = [tile_wall_top(i) for i in range(3)]
    t["wainscot"] = [tile_wainscot(i) for i in range(3)]
    t["concrete"] = [tile_concrete(i) for i in range(4)]
    t["labfloor"] = [tile_labfloor(i) for i in range(3)]
    t["hedge"] = [tile_hedge(i) for i in range(3)]
    t["water"] = [tile_water(i) for i in range(3)]
    t["void"] = [tile_void()]
    return t


# --- furniture and props -----------------------------------------------------
#
# Drawn with rectangles rather than string art: at this size a chair is four
# boxes, and the code stays shorter than the picture would be.


def _surf(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _box(s, rect, fill, top=None, shade=None, outline=INK):
    x, y, w, h = rect
    pygame.draw.rect(s, fill, rect)
    if top:
        pygame.draw.rect(s, top, (x, y, w, 1))
    if shade:
        pygame.draw.rect(s, shade, (x, y + h - 2, w, 2))
        pygame.draw.rect(s, shade, (x + w - 1, y, 1, h))
    if outline:
        pygame.draw.rect(s, outline, rect, 1)


def obj_plinth():
    """Marble pedestal with a small bust. One of these is missing its base."""
    s = _surf(16, 28)
    _box(s, (3, 12, 10, 15), MARBLE_D, MARBLE_L, STONE_D)
    _box(s, (1, 24, 14, 4), MARBLE, MARBLE_L, STONE_D)
    _box(s, (2, 10, 12, 3), MARBLE, MARBLE_L, STONE_D)
    # bust
    _box(s, (5, 4, 6, 7), (188, 178, 156), (216, 208, 188), (144, 134, 116))
    pygame.draw.rect(s, (144, 134, 116), (6, 6, 1, 2))
    pygame.draw.rect(s, (144, 134, 116), (9, 6, 1, 2))
    _box(s, (6, 1, 4, 4), (198, 188, 166), (222, 214, 196), (144, 134, 116))
    return s


def obj_plinth_empty():
    """The plinth the murder weapon came off. Its marble base is gone."""
    s = _surf(16, 28)
    _box(s, (3, 12, 10, 15), MARBLE, MARBLE_L, STONE_D)
    _box(s, (2, 10, 12, 3), MARBLE_L, (240, 236, 226), STONE_D)
    # The gap where the base was torn off, and the tape around it.
    pygame.draw.rect(s, INK, (4, 24, 8, 4))
    pygame.draw.rect(s, SHADOW, (5, 25, 6, 2))
    pygame.draw.rect(s, TAPE, (2, 15, 12, 1))
    return s


def obj_painting(w=32, empty=False, canvas=None):
    s = _surf(w, 18)
    _box(s, (0, 0, w, 18), BRASS_D, BRASS, (96, 68, 28))
    inner = (2, 2, w - 4, 14)
    if empty:
        pygame.draw.rect(s, (36, 32, 44), inner)
        pygame.draw.rect(s, (24, 20, 30), (3, 3, w - 6, 12))
        return s
    rng = random.Random(w + (1 if canvas else 0))
    sky, land = canvas or ((132, 150, 168), (86, 104, 68))
    pygame.draw.rect(s, sky, inner)
    pygame.draw.rect(s, land, (2, 10, w - 4, 6))
    for _ in range(w // 3):
        x = rng.randrange(3, w - 4)
        pygame.draw.line(s, (58, 74, 48), (x, 10), (x, 8 - rng.randrange(2)))
    pygame.draw.rect(s, (168, 176, 186), (w - 9, 4, 4, 2))
    return s


def obj_desk():
    s = _surf(32, 20)
    _box(s, (0, 4, 32, 8), WOOD, WOOD_L, WOOD_D)
    _box(s, (1, 12, 8, 8), WOOD_D, None, None)
    _box(s, (23, 12, 8, 8), WOOD_D, None, None)
    pygame.draw.rect(s, BRASS, (3, 15, 4, 1))
    pygame.draw.rect(s, BRASS, (25, 15, 4, 1))
    # papers and a desk lamp
    pygame.draw.rect(s, PAPER, (12, 2, 8, 4))
    pygame.draw.rect(s, PAPER_D, (13, 5, 7, 1))
    pygame.draw.rect(s, INK, (12, 2, 8, 4), 1)
    return s


def obj_table():
    s = _surf(48, 22)
    _box(s, (0, 2, 48, 10), WOOD_L, (176, 132, 92), WOOD_D)
    _box(s, (3, 12, 5, 10), WOOD_D, None, None)
    _box(s, (40, 12, 5, 10), WOOD_D, None, None)
    return s


def obj_chair(facing="down"):
    s = _surf(16, 20)
    if facing == "down":
        _box(s, (3, 8, 10, 6), WOOD, WOOD_L, WOOD_D)
        _box(s, (3, 1, 10, 8), WOOD_D, WOOD, None)
    else:
        _box(s, (3, 4, 10, 6), WOOD, WOOD_L, WOOD_D)
        _box(s, (3, 10, 10, 6), WOOD_D, None, None)
    pygame.draw.rect(s, WOOD_D, (4, 14, 2, 6))
    pygame.draw.rect(s, WOOD_D, (10, 14, 2, 6))
    return s


def obj_shelf():
    s = _surf(16, 26)
    _box(s, (0, 0, 16, 26), WOOD_D, WOOD, INK)
    rng = random.Random(7)
    for shelf_y in (3, 11, 19):
        pygame.draw.rect(s, (52, 34, 24), (1, shelf_y, 14, 6))
        x = 2
        while x < 14:
            bw = rng.choice((1, 2, 2))
            bh = rng.choice((4, 5, 6))
            col = rng.choice(((142, 58, 52), (60, 92, 128), (150, 128, 66), (86, 108, 70)))
            pygame.draw.rect(s, col, (x, shelf_y + 6 - bh, bw, bh))
            x += bw + 1
        pygame.draw.rect(s, WOOD, (1, shelf_y + 6, 14, 1))
    return s


def obj_cabinet():
    s = _surf(16, 24)
    _box(s, (0, 0, 16, 24), STONE_D, STONE, INK)
    for y in (3, 10, 17):
        pygame.draw.rect(s, STONE, (2, y, 12, 5))
        pygame.draw.rect(s, INK, (2, y, 12, 5), 1)
        pygame.draw.rect(s, BRASS, (7, y + 2, 3, 1))
    return s


def obj_plant():
    s = _surf(16, 24)
    _box(s, (4, 16, 8, 8), (146, 84, 58), (176, 108, 74), (96, 52, 34))
    rng = random.Random(3)
    for _ in range(16):
        x = rng.randrange(2, 14)
        y = rng.randrange(2, 16)
        pygame.draw.rect(s, rng.choice((HEDGE, HEDGE_L, (30, 60, 42))), (x, y, 3, 3))
    return s


def obj_lamp(lit=True):
    s = _surf(16, 30)
    pygame.draw.rect(s, (52, 50, 66), (7, 10, 2, 18))
    _box(s, (4, 27, 8, 3), (52, 50, 66), None, INK)
    shade = LAMP if lit else (96, 92, 104)
    _box(s, (2, 2, 12, 9), shade, GLOW if lit else (120, 116, 128), LAMP_D if lit else (70, 66, 80))
    return s


def obj_sconce():
    s = _surf(16, 12)
    _box(s, (5, 6, 6, 5), BRASS_D, BRASS, INK)
    _box(s, (4, 1, 8, 6), LAMP, GLOW, LAMP_D)
    return s


def obj_dumpster():
    s = _surf(32, 22)
    _box(s, (0, 6, 32, 16), (58, 84, 68), (78, 108, 86), (34, 52, 42))
    _box(s, (0, 2, 32, 5), (46, 68, 56), (72, 98, 78), (34, 52, 42))
    pygame.draw.rect(s, (34, 52, 42), (10, 7, 1, 14))
    pygame.draw.rect(s, (34, 52, 42), (21, 7, 1, 14))
    return s


def obj_door(open_=False):
    s = _surf(16, 16)
    if open_:
        pygame.draw.rect(s, (12, 10, 18), (2, 0, 12, 16))
        pygame.draw.rect(s, WOOD_D, (0, 0, 2, 16))
        pygame.draw.rect(s, WOOD_D, (14, 0, 2, 16))
        return s
    _box(s, (1, 0, 14, 16), WOOD, WOOD_L, WOOD_D)
    pygame.draw.rect(s, WOOD_D, (3, 2, 10, 5))
    pygame.draw.rect(s, WOOD_D, (3, 9, 10, 5))
    pygame.draw.rect(s, BRASS, (12, 8, 2, 2))
    return s


def obj_body_outline():
    """Tape on the floor where Marguerite was found — head, arms, legs."""
    s = _surf(30, 40)
    pygame.draw.circle(s, TAPE, (15, 6), 5, 1)
    pts = [
        (11, 10), (7, 14), (2, 22), (5, 24), (9, 17),  # left arm, flung out
        (9, 26), (7, 38), (11, 38), (14, 27),          # left leg
        (17, 27), (21, 38), (25, 37), (22, 25),        # right leg
        (22, 16), (27, 21), (29, 18), (23, 11),        # right arm
        (19, 10),
    ]
    pygame.draw.lines(s, TAPE, True, pts, 1)
    # The stain, under the head where the blow landed.
    pygame.draw.ellipse(s, (74, 22, 26), (8, 1, 12, 9))
    pygame.draw.ellipse(s, BLOOD, (10, 2, 8, 6))
    return s


def obj_tree():
    """Museum grounds. Two greens and a hard rim is all a canopy needs."""
    s = _surf(26, 36)
    pygame.draw.rect(s, (72, 46, 32), (11, 24, 4, 12))
    pygame.draw.rect(s, (52, 32, 22), (11, 24, 1, 12))
    rng = random.Random(11)
    pygame.draw.circle(s, (30, 58, 40), (13, 15), 13)
    for _ in range(90):
        a = rng.random() * math.tau
        r = rng.random() ** 0.5 * 11
        x = int(13 + r * math.cos(a))
        y = int(15 + r * math.sin(a))
        pygame.draw.rect(s, rng.choice((HEDGE, HEDGE_L, (46, 84, 54))), (x, y, 2, 2))
    pygame.draw.circle(s, (22, 44, 32), (13, 15), 13, 1)
    return s


def obj_bush():
    s = _surf(16, 14)
    rng = random.Random(5)
    pygame.draw.ellipse(s, HEDGE, (0, 2, 16, 12))
    for _ in range(24):
        x, y = rng.randrange(1, 14), rng.randrange(3, 12)
        pygame.draw.rect(s, rng.choice((HEDGE_L, HEDGE)), (x, y, 2, 2))
    return s


def obj_flowers():
    s = _surf(16, 10)
    rng = random.Random(9)
    pygame.draw.ellipse(s, (46, 84, 54), (0, 3, 16, 7))
    for _ in range(7):
        x, y = rng.randrange(2, 14), rng.randrange(3, 8)
        s.set_at((x, y), rng.choice(((214, 92, 108), (238, 206, 96), (176, 132, 214))))
    return s


def obj_crate():
    s = _surf(16, 15)
    _box(s, (0, 2, 16, 13), WOOD, WOOD_L, WOOD_D)
    pygame.draw.line(s, WOOD_D, (1, 3), (14, 13))
    pygame.draw.line(s, WOOD_D, (14, 3), (1, 13))
    pygame.draw.rect(s, WOOD_D, (0, 6, 16, 1))
    return s


def obj_pallet():
    s = _surf(22, 10)
    _box(s, (0, 2, 22, 8), WOOD_D, WOOD, INK)
    for x in range(1, 21, 4):
        pygame.draw.rect(s, WOOD, (x, 3, 3, 6))
    return s


def obj_stanchion():
    """Rope barrier. The rope is what tells you not to touch the art."""
    s = _surf(24, 20)
    for x in (2, 20):
        pygame.draw.rect(s, BRASS_D, (x, 6, 2, 12))
        pygame.draw.rect(s, BRASS, (x - 1, 4, 4, 3))
        pygame.draw.rect(s, BRASS_D, (x - 2, 18, 6, 2))
    pygame.draw.line(s, (86, 34, 40), (3, 7), (11, 10))
    pygame.draw.line(s, (86, 34, 40), (11, 10), (20, 7))
    pygame.draw.line(s, (128, 52, 58), (3, 6), (11, 9))
    pygame.draw.line(s, (128, 52, 58), (11, 9), (20, 6))
    return s


def obj_case():
    """Glass display case with something small and gold inside."""
    s = _surf(32, 22)
    _box(s, (0, 14, 32, 8), WOOD_D, WOOD, INK)
    pygame.draw.rect(s, (168, 198, 210), (2, 2, 28, 13))
    pygame.draw.rect(s, (196, 220, 230), (2, 2, 28, 2))
    pygame.draw.rect(s, INK, (2, 2, 28, 13), 1)
    pygame.draw.rect(s, BRASS, (12, 8, 8, 5))
    pygame.draw.rect(s, BRASS_D, (12, 12, 8, 1))
    for x in (10, 21):
        pygame.draw.line(s, (206, 228, 236), (x, 3), (x - 3, 14))
    return s


def obj_workbench():
    """A conservator's bench: jars, brushes, a lamp clamped to the edge."""
    s = _surf(32, 20)
    _box(s, (0, 4, 32, 9), WOOD_L, (180, 138, 96), WOOD_D)
    pygame.draw.rect(s, WOOD_D, (2, 13, 4, 7))
    pygame.draw.rect(s, WOOD_D, (26, 13, 4, 7))
    for x, col in ((4, (168, 176, 186)), (8, (196, 168, 96)), (12, (140, 96, 168))):
        pygame.draw.rect(s, col, (x, 0, 3, 5))
        pygame.draw.rect(s, INK, (x, 0, 3, 5), 1)
    for i, x in enumerate((20, 23, 26)):
        pygame.draw.line(s, WOOD_D, (x, 4), (x + 1, 1 - i % 2))
        s.set_at((x, 0), (60, 50, 44))
    return s


def obj_rack():
    """Drying rack — canvases stacked on edge."""
    s = _surf(16, 26)
    _box(s, (0, 0, 16, 26), (58, 44, 36), None, INK)
    rng = random.Random(13)
    for i, y in enumerate((2, 10, 18)):
        pygame.draw.rect(s, (46, 34, 28), (1, y, 14, 7))
        for x in range(2, 14, 3):
            pygame.draw.rect(
                s, rng.choice(((176, 168, 142), (150, 158, 138), (188, 176, 156))), (x, y + 1, 2, 5)
            )
    return s


def obj_sink():
    s = _surf(16, 16)
    _box(s, (0, 4, 16, 12), STONE, STONE_L, STONE_D)
    pygame.draw.rect(s, (52, 64, 84), (3, 7, 10, 6))
    pygame.draw.rect(s, INK, (3, 7, 10, 6), 1)
    pygame.draw.rect(s, BRASS, (7, 2, 2, 5))
    pygame.draw.rect(s, BRASS, (7, 2, 4, 2))
    return s


def obj_debris():
    """Pulled drawers and scattered paper — the room was turned over."""
    s = _surf(20, 14)
    rng = random.Random(17)
    for _ in range(7):
        x, y = rng.randrange(0, 14), rng.randrange(2, 11)
        pygame.draw.rect(s, PAPER, (x, y, 5, 3))
        pygame.draw.rect(s, PAPER_D, (x, y + 2, 5, 1))
    _box(s, (2, 6, 11, 7), WOOD_D, WOOD, INK)
    pygame.draw.rect(s, BRASS, (6, 9, 3, 1))
    return s


def obj_mirror():
    """The observation glass. You can see yourself in it, which is the point."""
    s = _surf(32, 16)
    _box(s, (0, 0, 32, 16), (44, 52, 74), (72, 84, 116), INK)
    pygame.draw.rect(s, (58, 70, 100), (2, 2, 28, 12))
    for x in range(4, 30, 9):
        pygame.draw.line(s, (86, 100, 136), (x, 3), (x - 2, 13))
    return s


def obj_cooler():
    s = _surf(12, 22)
    _box(s, (1, 8, 10, 14), (206, 208, 212), (232, 234, 238), STONE_D)
    _box(s, (2, 0, 8, 8), (110, 160, 190), (150, 196, 216), (60, 100, 130))
    pygame.draw.rect(s, (60, 70, 90), (4, 13, 4, 2))
    return s


def obj_banner():
    """A hanging exhibition banner. Colour where the walls have none."""
    s = _surf(14, 30)
    pygame.draw.rect(s, BRASS_D, (0, 0, 14, 2))
    _box(s, (1, 2, 12, 26), CARPET, CARPET_L, CARPET_D)
    pygame.draw.rect(s, BRASS, (3, 6, 8, 1))
    pygame.draw.rect(s, PAPER_D, (3, 10, 8, 2))
    pygame.draw.rect(s, PAPER_D, (4, 14, 6, 1))
    pygame.draw.polygon(s, CARPET_D, [(1, 28), (7, 24), (13, 28)])
    return s


def obj_marker(n):
    """A numbered evidence tent. The number is drawn, not typed."""
    s = _surf(10, 12)
    pygame.draw.polygon(s, TAPE, [(1, 11), (5, 2), (9, 11)])
    pygame.draw.polygon(s, (168, 138, 30), [(1, 11), (5, 2), (9, 11)], 1)
    digits = {
        1: [(5, 6), (5, 7), (5, 8), (5, 9), (4, 7)],
        2: [(4, 6), (5, 6), (6, 7), (5, 8), (4, 9), (5, 9), (6, 9)],
        3: [(4, 6), (5, 6), (6, 7), (5, 7), (6, 8), (5, 9), (4, 9)],
        4: [(4, 6), (4, 7), (5, 7), (6, 6), (6, 7), (6, 8), (6, 9)],
        5: [(6, 6), (5, 6), (4, 6), (4, 7), (5, 7), (6, 8), (5, 9), (4, 9)],
    }
    for px, py in digits.get(n, []):
        s.set_at((px, py), INK)
    return s


def obj_easel():
    s = _surf(16, 26)
    pygame.draw.line(s, WOOD_D, (3, 25), (7, 8))
    pygame.draw.line(s, WOOD_D, (12, 25), (8, 8))
    pygame.draw.line(s, WOOD_D, (8, 25), (8, 14))
    _box(s, (1, 6, 14, 11), (222, 216, 198), None, WOOD_D)
    pygame.draw.rect(s, (150, 160, 176), (3, 8, 10, 4))
    pygame.draw.rect(s, (96, 116, 78), (3, 12, 10, 3))
    return s


def obj_bench():
    s = _surf(32, 14)
    _box(s, (0, 2, 32, 6), WOOD, WOOD_L, WOOD_D)
    pygame.draw.rect(s, WOOD_D, (3, 8, 3, 6))
    pygame.draw.rect(s, WOOD_D, (26, 8, 3, 6))
    return s


def obj_fountain():
    s = _surf(48, 40)
    pygame.draw.ellipse(s, STONE_D, (0, 8, 48, 32))
    pygame.draw.ellipse(s, STONE, (2, 10, 44, 28))
    pygame.draw.ellipse(s, (44, 74, 122), (5, 13, 38, 22))
    pygame.draw.ellipse(s, (60, 98, 152), (9, 16, 30, 16))
    _box(s, (20, 4, 8, 20), STONE, STONE_L, STONE_D)
    _box(s, (17, 0, 14, 5), STONE_L, MARBLE_L, STONE_D)
    return s


def obj_vault_terminal():
    """A checkout terminal bolted to the vault wall — the ledger evidence."""
    s = _surf(16, 22)
    _box(s, (0, 4, 16, 18), STONE_D, STONE, INK)
    _box(s, (2, 6, 12, 8), (24, 40, 30), (34, 56, 42), INK)
    rng = random.Random(21)
    for y in range(8, 13, 2):
        w = rng.randrange(5, 10)
        pygame.draw.line(s, (86, 196, 128), (4, y), (4 + w, y))
    for x, y in ((3, 16), (6, 16), (9, 16), (12, 16), (3, 19), (6, 19), (9, 19), (12, 19)):
        pygame.draw.rect(s, STONE_D, (x, y, 2, 2))
    return s


def obj_camera_console():
    """Motor pool gate camera monitor, cycling grainy footage."""
    s = _surf(22, 18)
    _box(s, (0, 0, 22, 18), WOOD_D, WOOD, INK)
    _box(s, (2, 2, 18, 12), (30, 30, 36), (44, 44, 52), INK)
    rng = random.Random(22)
    for y in range(3, 13, 2):
        shade = rng.choice(((70, 70, 78), (54, 54, 62), (86, 86, 94)))
        pygame.draw.line(s, shade, (3, y), (19, y))
    pygame.draw.circle(s, DANGER, (18, 4), 1)
    pygame.draw.rect(s, STONE_D, (8, 14, 6, 3))
    return s


def obj_burner_phone():
    """A cheap prepaid handset, hidden behind a shelf."""
    s = _surf(10, 16)
    _box(s, (1, 1, 8, 14), (34, 34, 40), (48, 48, 56), INK)
    pygame.draw.rect(s, (60, 92, 78), (2, 3, 6, 6))
    pygame.draw.line(s, INK, (2, 6), (8, 4))  # the cracked screen
    for y in (11, 12, 13):
        pygame.draw.rect(s, (24, 24, 30), (3, y, 4, 1))
    return s


def obj_photo_facedown():
    """A printed photo, left face down. All you see is the back."""
    s = _surf(14, 10)
    _box(s, (0, 0, 14, 10), PAPER_D, PAPER, (150, 142, 118))
    pygame.draw.line(s, (150, 142, 118), (2, 8), (5, 6))
    return s


def obj_matchbook():
    """Dropped at the roadside handoff — the Cinder Compact's mark."""
    s = _surf(10, 8)
    _box(s, (0, 0, 10, 8), (24, 22, 28), (40, 38, 46), INK)
    pygame.draw.rect(s, (206, 60, 54), (7, 1, 2, 2))
    pygame.draw.line(s, PAPER_D, (1, 6), (5, 5))
    return s


def obj_kitchen_mess():
    """The Thorne kitchen: a shattered mug, a full one, a chair shoved back."""
    s = _surf(28, 18)
    _box(s, (2, 6, 24, 8), WOOD_L, (176, 132, 92), WOOD_D)
    pygame.draw.rect(s, (216, 220, 224), (4, 3, 5, 5))  # the full mug, cold
    pygame.draw.rect(s, INK, (4, 3, 5, 5), 1)
    rng = random.Random(23)
    for _ in range(6):  # the shattered one, never swept up
        x = 16 + rng.randrange(0, 8)
        y = 15 + rng.randrange(0, 2)
        pygame.draw.rect(s, (206, 210, 214), (x, y, 2, 1))
    _box(s, (20, 1, 6, 6), WOOD_D, WOOD, None)  # the chair, pushed back hard
    return s


def obj_corkboard():
    """The precinct's board: photos, pins, and red string between them. The
    string is the point — it's the one prop that says 'investigation'."""
    s = _surf(46, 26)
    _box(s, (0, 0, 46, 26), (146, 108, 62), (176, 136, 84), (78, 54, 30))
    rng = random.Random(31)
    cards = []
    for cx, cy, w, h in ((4, 4, 9, 7), (18, 3, 10, 8), (33, 5, 9, 7),
                         (7, 15, 10, 7), (24, 16, 12, 6)):
        pygame.draw.rect(s, PAPER, (cx, cy, w, h))
        pygame.draw.rect(s, PAPER_D, (cx, cy + h - 2, w, 2))
        pygame.draw.rect(s, INK, (cx, cy, w, h), 1)
        for _ in range(2):  # a scrawled line or two per card
            ly = cy + 2 + rng.randrange(0, max(1, h - 3))
            pygame.draw.line(s, (128, 122, 108), (cx + 2, ly), (cx + w - 3, ly))
        cards.append((cx + w // 2, cy + h // 2))
    for a, b in zip(cards, cards[1:]):
        pygame.draw.line(s, (168, 46, 44), a, b)
    pygame.draw.line(s, (168, 46, 44), cards[0], cards[-1])
    for px, py in cards:
        s.set_at((px, py), (232, 208, 96))  # brass pin head
    return s


def obj_wallmap():
    """Ashworth's wall map of Harrow's Reach — coastline, roads, a pinned site."""
    s = _surf(40, 28)
    _box(s, (0, 0, 40, 28), (206, 196, 168), (228, 220, 196), (72, 60, 44))
    pygame.draw.rect(s, (156, 176, 158), (2, 2, 36, 24))
    # Water along the bottom, land above it.
    pygame.draw.rect(s, (86, 122, 156), (2, 20, 36, 6))
    pygame.draw.line(s, (66, 98, 130), (2, 20), (38, 20))
    rng = random.Random(37)
    for _ in range(9):  # blocks
        bx, by = rng.randrange(3, 34), rng.randrange(3, 17)
        pygame.draw.rect(s, (132, 152, 136), (bx, by, rng.randrange(3, 6), rng.randrange(2, 4)))
    for x in (11, 22, 31):  # roads
        pygame.draw.line(s, (198, 190, 166), (x, 3), (x, 19))
    pygame.draw.line(s, (198, 190, 166), (3, 12), (37, 12))
    pygame.draw.rect(s, DANGER, (29, 21, 3, 3))  # the pin on Salt Row
    return s


def obj_bollard():
    """A dock bollard with rope looped over it."""
    s = _surf(12, 16)
    _box(s, (3, 4, 6, 12), (62, 58, 66), (94, 90, 100), INK)
    _box(s, (2, 1, 8, 4), (78, 74, 84), (110, 106, 118), INK)
    pygame.draw.arc(s, (156, 132, 88), (0, 7, 12, 8), 3.4, 6.0, 2)
    return s


def obj_munitions_crate():
    """A stencilled weapons case — the shape five of these left behind."""
    s = _surf(20, 15)
    _box(s, (0, 2, 20, 13), (76, 84, 62), (98, 108, 78), (44, 50, 36))
    pygame.draw.rect(s, (44, 50, 36), (0, 6, 20, 1))
    pygame.draw.rect(s, (44, 50, 36), (0, 11, 20, 1))
    for x in (3, 15):  # latches
        pygame.draw.rect(s, (152, 148, 132), (x, 7, 2, 3))
    # Stencil block, unreadable at this size but unmistakably a marking.
    for i, x in enumerate(range(6, 15, 3)):
        pygame.draw.rect(s, (198, 192, 160), (x, 3, 2, 2))
    return s


def obj_weapon_rack():
    """An arms rack. The empty slots are the story: five of them."""
    s = _surf(30, 22)
    _box(s, (0, 0, 30, 22), (64, 58, 46), (88, 80, 62), (36, 32, 24))
    pygame.draw.rect(s, (36, 32, 24), (0, 9, 30, 1))
    for i, x in enumerate(range(3, 28, 5)):
        if i in (1, 3):  # two slots stand empty
            pygame.draw.rect(s, (28, 26, 20), (x, 2, 3, 17))
            continue
        pygame.draw.rect(s, (48, 44, 36), (x, 2, 3, 17))  # barrel
        pygame.draw.rect(s, (92, 62, 40), (x, 12, 3, 6))  # stock
        pygame.draw.rect(s, (120, 116, 104), (x + 1, 3, 1, 8))
    return s


def obj_bunk():
    """A single cot. Slept in, not made."""
    s = _surf(20, 30)
    _box(s, (0, 2, 20, 28), WOOD_D, WOOD, INK)
    pygame.draw.rect(s, (188, 180, 158), (2, 5, 16, 10))  # pillow end
    pygame.draw.rect(s, (152, 144, 124), (2, 13, 16, 2))
    pygame.draw.rect(s, (86, 74, 68), (2, 15, 16, 13))  # blanket, thrown back
    pygame.draw.rect(s, (108, 94, 86), (2, 15, 16, 2))
    pygame.draw.rect(s, INK, (2, 5, 16, 23), 1)
    return s


def obj_stove():
    """A cast-iron stove with the fire still in it."""
    s = _surf(16, 24)
    _box(s, (1, 4, 14, 20), (52, 50, 54), (76, 74, 80), INK)
    pygame.draw.rect(s, (34, 32, 36), (3, 10, 10, 8))
    pygame.draw.rect(s, (198, 96, 40), (4, 13, 8, 4))  # firebox glow
    pygame.draw.rect(s, (240, 176, 72), (5, 14, 6, 2))
    pygame.draw.rect(s, (40, 38, 42), (6, 0, 4, 5))  # flue
    pygame.draw.rect(s, BRASS_D, (3, 20, 10, 1))
    return s


def obj_truck():
    """A two-and-a-half ton in its bay — the truck the gate camera caught
    logging out after hours on all five nights."""
    s = _surf(26, 40)
    _box(s, (2, 12, 22, 26), (62, 70, 50), (84, 94, 66), (34, 38, 28))  # bed
    for y in range(17, 36, 5):
        pygame.draw.line(s, (44, 50, 36), (4, y), (21, y))  # slats
    _box(s, (3, 0, 20, 13), (74, 84, 58), (98, 110, 76), (34, 38, 28))  # cab
    pygame.draw.rect(s, (96, 122, 130), (6, 2, 14, 5))  # windshield
    pygame.draw.rect(s, (132, 158, 164), (6, 2, 14, 1))
    for wy in (7, 22, 30):
        pygame.draw.rect(s, (28, 26, 26), (0, wy, 3, 6))
        pygame.draw.rect(s, (28, 26, 26), (23, wy, 3, 6))
    return s


def obj_oil_drum():
    s = _surf(12, 18)
    _box(s, (1, 3, 10, 15), (104, 72, 44), (134, 96, 62), (52, 36, 22))
    for y in (7, 12):
        pygame.draw.rect(s, (52, 36, 22), (1, y, 10, 1))
    pygame.draw.ellipse(s, (134, 96, 62), (1, 1, 10, 4))
    pygame.draw.ellipse(s, (52, 36, 22), (1, 1, 10, 4), 1)
    return s


def build_objects():
    return {
        "plinth": obj_plinth(),
        "plinth_empty": obj_plinth_empty(),
        "painting": obj_painting(32),
        "painting_wide": obj_painting(48),
        "painting_empty": obj_painting(32, empty=True),
        "corot": obj_painting(48, canvas=((156, 168, 148), (96, 106, 62))),
        "desk": obj_desk(),
        "table": obj_table(),
        "chair": obj_chair("down"),
        "chair_up": obj_chair("up"),
        "shelf": obj_shelf(),
        "cabinet": obj_cabinet(),
        "plant": obj_plant(),
        "lamp": obj_lamp(True),
        "sconce": obj_sconce(),
        "dumpster": obj_dumpster(),
        "door": obj_door(),
        "door_open": obj_door(True),
        "outline": obj_body_outline(),
        "easel": obj_easel(),
        "bench": obj_bench(),
        "fountain": obj_fountain(),
        "tree": obj_tree(),
        "bush": obj_bush(),
        "flowers": obj_flowers(),
        "crate": obj_crate(),
        "pallet": obj_pallet(),
        "stanchion": obj_stanchion(),
        "case": obj_case(),
        "workbench": obj_workbench(),
        "rack": obj_rack(),
        "sink": obj_sink(),
        "debris": obj_debris(),
        "mirror": obj_mirror(),
        "cooler": obj_cooler(),
        "banner": obj_banner(),
        "vault_terminal": obj_vault_terminal(),
        "camera_console": obj_camera_console(),
        "burner_phone": obj_burner_phone(),
        "photo_facedown": obj_photo_facedown(),
        "matchbook": obj_matchbook(),
        "kitchen_mess": obj_kitchen_mess(),
        "corkboard": obj_corkboard(),
        "wallmap": obj_wallmap(),
        "bollard": obj_bollard(),
        "munitions_crate": obj_munitions_crate(),
        "weapon_rack": obj_weapon_rack(),
        "truck": obj_truck(),
        "oil_drum": obj_oil_drum(),
        "chimney": obj_chimney(),
        "steel_shelf": obj_steel_shelf(),
        "gun_locker": obj_gun_locker(),
        "ammo_crate": obj_ammo_crate(),
        "sandbags": obj_sandbags(),
        "lab_bench": obj_lab_bench(),
        "microscope": obj_microscope(),
        "specimen_cabinet": obj_specimen_cabinet(),
        "fume_hood": obj_fume_hood(),
        "pole": obj_pole(),
        "bin": obj_bin(),
        "drain": obj_drain(),
        "hydrant": obj_hydrant(),
        **{f"window_{s}": obj_facade_window(s) for s in ROOF_STYLES},
        **{f"door_{s}": obj_facade_door(s) for s in ROOF_STYLES},
        "window_house": obj_house_window(),
        "doorway": obj_doorway(),
        "porch_lamp": obj_porch_lamp(),
        "house_number": obj_house_number(),
        "door_vault": obj_door_vault(),
        "door_motorpool": obj_door_motorpool(),
        "door_precinct": obj_door_precinct(),
        "window_vault": obj_window_vault(),
        "stairs": obj_stairs(),
        "roof_vent": obj_roof_vent(),
        "roof_sign": obj_roof_sign(),
        "bunk": obj_bunk(),
        "stove": obj_stove(),
        **{f"marker{i}": obj_marker(i) for i in range(1, 6)},
    }


_cache = None


def objects():
    """Built once. Every prop is a plain surface, so they can all be shared."""
    global _cache
    if _cache is None:
        _cache = build_objects()
    return _cache


# --- lighting ----------------------------------------------------------------


def make_light(radius, colour=(255, 226, 168), strength=190):
    """A round pool of light. Enough bands that the falloff reads as a falloff
    and not as a set of rings — seven looked like a dartboard."""
    size = radius * 2
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    bands = max(12, radius // 2)
    for i in range(bands, 0, -1):
        r = int(radius * i / bands)
        a = int(strength * (1 - (i - 1) / bands) ** 1.7)
        pygame.draw.circle(s, (*colour, a), (radius, radius), r)
    return s


# --- interview portraits -----------------------------------------------------
#
# A 48x48 bust per suspect, in three states. These are drawn rather than
# authored as string art: at this size the head is a handful of rectangles, and
# what actually carries a performance is the eyes, brows and mouth — those get
# placed by hand, pixel by pixel, below. Each character shares one skull and is
# told apart by legend colours plus their own headwear.

EYE_L, EYE_R = 20, 28  # eye centres
BROW_Y, EYE_Y, MOUTH_Y = 15, 18, 26


def _bust_base(lg):
    s = _surf(48, 48)
    skin, skin_d, coat, coat_d, coat_l = lg["s"], lg["S"], lg["c"], lg["C"], lg["k"]

    # Shoulders and collar.
    pygame.draw.rect(s, coat, (3, 35, 42, 13))
    pygame.draw.rect(s, coat_d, (3, 44, 42, 4))
    pygame.draw.rect(s, coat_l, (3, 35, 42, 1))
    pygame.draw.rect(s, INK, (3, 34, 42, 1))
    # Collar notch, so the neck reads as sitting inside a shirt.
    pygame.draw.polygon(s, coat_d, [(18, 35), (24, 42), (30, 35)])
    pygame.draw.polygon(s, INK, [(18, 35), (24, 42), (30, 35)], 1)

    # Neck.
    pygame.draw.rect(s, skin_d, (20, 29, 8, 7))
    pygame.draw.rect(s, INK, (19, 29, 1, 7))
    pygame.draw.rect(s, INK, (28, 29, 1, 7))

    # Skull: a rect with the corners knocked off rather than a true oval —
    # ovals at 24px go lumpy, and the flat planes read better under lamplight.
    pygame.draw.rect(s, skin, (14, 7, 20, 24))
    pygame.draw.rect(s, skin, (13, 11, 22, 15))
    pygame.draw.rect(s, skin_d, (14, 27, 20, 4))  # jaw in shadow
    pygame.draw.rect(s, skin_d, (30, 11, 4, 18))  # lit from the left
    for x, y in ((14, 7), (33, 7), (14, 30), (33, 30)):
        s.set_at((x, y), (0, 0, 0, 0))
    # Ears.
    pygame.draw.rect(s, skin_d, (12, 17, 2, 5))
    pygame.draw.rect(s, skin_d, (34, 17, 2, 5))
    # Outline down both cheeks.
    pygame.draw.rect(s, INK, (12, 8, 1, 23))
    pygame.draw.rect(s, INK, (35, 8, 1, 23))
    pygame.draw.rect(s, INK, (14, 31, 20, 1))

    # Nose.
    pygame.draw.rect(s, skin_d, (23, 20, 2, 4))
    pygame.draw.rect(s, INK, (23, 24, 3, 1))
    return s


def _face(s, lg, mood):
    """Brows, eyes and mouth — the whole performance lives in nine rows."""
    ink, white = INK, (236, 232, 226)
    if mood == "steady":
        for x in (EYE_L - 2, EYE_R - 2):
            pygame.draw.rect(s, ink, (x, BROW_Y, 5, 1))
        for x in (EYE_L - 1, EYE_R - 1):
            pygame.draw.rect(s, white, (x, EYE_Y, 3, 2))
            pygame.draw.rect(s, ink, (x + 1, EYE_Y, 1, 2))
        pygame.draw.rect(s, ink, (21, MOUTH_Y, 7, 1))
    elif mood == "rattled":
        # Inner brows lift; the mouth tightens and pulls down at one corner.
        pygame.draw.rect(s, ink, (EYE_L - 2, BROW_Y + 1, 3, 1))
        pygame.draw.rect(s, ink, (EYE_L + 1, BROW_Y, 2, 1))
        pygame.draw.rect(s, ink, (EYE_R - 1, BROW_Y, 2, 1))
        pygame.draw.rect(s, ink, (EYE_R + 1, BROW_Y + 1, 3, 1))
        for x in (EYE_L - 1, EYE_R - 1):
            pygame.draw.rect(s, white, (x, EYE_Y, 3, 3))
            pygame.draw.rect(s, ink, (x + 1, EYE_Y + 1, 1, 2))
        pygame.draw.rect(s, ink, (21, MOUTH_Y, 6, 1))
        s.set_at((27, MOUTH_Y + 1), ink)
    else:  # cracking
        pygame.draw.rect(s, ink, (EYE_L - 2, BROW_Y + 2, 4, 1))
        pygame.draw.rect(s, ink, (EYE_L + 2, BROW_Y, 2, 1))
        pygame.draw.rect(s, ink, (EYE_R - 2, BROW_Y, 2, 1))
        pygame.draw.rect(s, ink, (EYE_R, BROW_Y + 2, 4, 1))
        for x in (EYE_L - 1, EYE_R - 1):
            pygame.draw.rect(s, white, (x, EYE_Y - 1, 4, 4))
            pygame.draw.rect(s, ink, (x + 1, EYE_Y, 2, 2))
        # Mouth open, jaw slack.
        pygame.draw.rect(s, (58, 30, 34), (21, MOUTH_Y, 7, 3))
        pygame.draw.rect(s, ink, (21, MOUTH_Y, 7, 1))
        # Sweat, running off the temple.
        pygame.draw.rect(s, (150, 205, 226), (36, 14, 1, 3))
        s.set_at((36, 17), (198, 232, 244))
    return s


def _headwear(s, lg, kind):
    band = lg["H"]
    lit = lg["h"]
    if kind == "patrol":  # Thorne — flat field cap, short bill
        pygame.draw.rect(s, band, (13, 2, 22, 8))
        pygame.draw.rect(s, lit, (13, 2, 22, 1))
        pygame.draw.rect(s, INK, (13, 1, 22, 1))
        pygame.draw.rect(s, band, (11, 9, 26, 2))
        pygame.draw.rect(s, INK, (11, 11, 26, 1))
    elif kind == "garrison":  # Doss — folded side cap, no bill
        pygame.draw.polygon(s, band, [(13, 10), (18, 2), (30, 2), (35, 10)])
        pygame.draw.polygon(s, INK, [(13, 10), (18, 2), (30, 2), (35, 10)], 1)
        pygame.draw.line(s, lit, (19, 4), (29, 4))
    elif kind == "peaked":  # Ashworth — officer's cap, badge and wide bill
        dark = lg["C"]
        pygame.draw.rect(s, band, (12, 1, 24, 7))
        pygame.draw.rect(s, lit, (12, 1, 24, 1))
        pygame.draw.rect(s, dark, (12, 8, 24, 3))  # cap band
        pygame.draw.rect(s, BRASS, (23, 3, 3, 3))  # badge
        pygame.draw.rect(s, BRASS_D, (23, 6, 3, 1))
        # Band and bill come from her own uniform, not a fixed colour, so the
        # cap can never drift out of step with the coat. The bill still has to
        # stay lighter than the terminal background or it reads as a gap.
        pygame.draw.rect(s, dark, (9, 11, 30, 2))  # bill
        pygame.draw.rect(s, band, (9, 11, 30, 1))
        pygame.draw.rect(s, INK, (9, 13, 30, 1))
    else:  # bricker — knit beanie, ribbed brim
        pygame.draw.rect(s, band, (13, 3, 22, 8))
        pygame.draw.rect(s, band, (15, 1, 18, 3))
        pygame.draw.rect(s, lit, (15, 1, 18, 1))
        pygame.draw.rect(s, INK, (15, 0, 18, 1))
        pygame.draw.rect(s, lit, (12, 9, 24, 3))  # rolled brim
        pygame.draw.rect(s, INK, (12, 12, 24, 1))
        for x in range(13, 36, 3):
            pygame.draw.rect(s, band, (x, 9, 1, 3))
    return s


def build_portrait(legend, hat, mood):
    s = _bust_base(legend)
    _face(s, legend, mood)
    # Sideburns, under the hat brim — without them every head reads as shaved.
    hair = legend["H"]
    for x in (13, 34):
        pygame.draw.rect(s, hair, (x, 13, 2, 5))
    _headwear(s, legend, hat)
    return s


PORTRAIT_HATS = {
    "thorne": "patrol",
    "doss": "garrison",
    "ashworth": "peaked",
    "bricker": "beanie",
}
_PORTRAIT_LEGENDS = {
    "thorne": THORNE,
    "doss": DOSS,
    "ashworth": ASHWORTH,
    "bricker": BRICKER,
}

PORTRAITS = {
    sid: {m: build_portrait(_PORTRAIT_LEGENDS[sid], PORTRAIT_HATS[sid], m)
          for m in ("steady", "rattled", "cracking")}
    for sid in _PORTRAIT_LEGENDS
}

"""Chiptune sound, synthesised at startup.

No audio files. Square and triangle waves with a hard attack and an exponential
decay, which is most of what a 1985 sound chip could do and all this game needs.
"""

import numpy as np
import pygame

RATE = 22050
_sounds = {}
muted = False
ok = False


def _wave(freq, dur, kind="square", vol=0.28, to=None, duty=0.5):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    if to:
        # Linear frequency slide: phase is the integral of the sweep.
        f = np.linspace(freq, to, n)
        phase = np.cumsum(f) / RATE
    else:
        phase = freq * t
    frac = phase % 1.0
    if kind == "square":
        w = np.where(frac < duty, 1.0, -1.0)
    elif kind == "triangle":
        w = 4 * np.abs(frac - 0.5) - 1
    elif kind == "saw":
        w = 2 * frac - 1
    else:  # noise, held in short steps so it reads as pitched hiss
        rng = np.random.default_rng(int(freq))
        step = max(1, int(RATE / max(freq, 1)))
        w = np.repeat(rng.uniform(-1, 1, n // step + 1), step)[:n]
    env = np.exp(-np.linspace(0, 5.0, n))
    env[: int(RATE * 0.002)] *= np.linspace(0, 1, int(RATE * 0.002))
    return w * env * vol


def _snd(*parts):
    """Mix layers of equal or unequal length into one Sound."""
    n = max(len(p) for p in parts)
    buf = np.zeros(n)
    for p in parts:
        buf[: len(p)] += p
    buf = np.clip(buf, -1, 1)
    samples = (buf * 32767).astype(np.int16)
    if _channels > 1:  # the mixer decides; duplicate rather than assume mono
        samples = np.repeat(samples[:, None], _channels, axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray(samples))


_channels = 1


def init():
    """Take over the mixer at our own rate, whatever pygame.init() opened."""
    global ok, RATE, _channels
    ok = False
    try:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        # allowedchanges=0: SDL converts to our mono 16-bit rather than opening
        # the device's own layout (6 or 8 channels on some Windows sound cards).
        pygame.mixer.init(RATE, -16, 1, 512, allowedchanges=0)
        got = pygame.mixer.get_init()
        if not got:
            raise pygame.error("mixer did not open")
        RATE, _, _channels = got[0], got[1], abs(got[2])
        _sounds.update(_build())
    except (pygame.error, ValueError, TypeError):
        # No sound is better than no game.
        _sounds.clear()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        return
    ok = True


def _build():
    return {
        "blip": _snd(_wave(760, 0.035, "square", 0.13, duty=0.25)),
        "blip2": _snd(_wave(680, 0.035, "square", 0.13, duty=0.25)),
        "step": _snd(_wave(150, 0.05, "noise", 0.07)),
        "step2": _snd(_wave(190, 0.05, "noise", 0.06)),
        "select": _snd(_wave(880, 0.05, "square", 0.2)),
        "move": _snd(_wave(520, 0.035, "square", 0.14)),
        "open": _snd(_wave(300, 0.09, "square", 0.18, to=620)),
        "close": _snd(_wave(620, 0.09, "square", 0.16, to=300)),
        "pickup": _snd(
            _wave(784, 0.07, "square", 0.2),
            np.concatenate([np.zeros(int(RATE * 0.07)), _wave(1046, 0.07, "square", 0.2)]),
            np.concatenate([np.zeros(int(RATE * 0.14)), _wave(1568, 0.16, "square", 0.2)]),
        ),
        "hurt": _snd(_wave(220, 0.22, "square", 0.24, to=70), _wave(90, 0.22, "triangle", 0.2)),
        "present": _snd(
            _wave(180, 0.16, "triangle", 0.3, to=70),
            _wave(900, 0.1, "square", 0.14, to=1300),
        ),
        "error": _snd(_wave(200, 0.16, "square", 0.2, to=120)),
        "start": _snd(
            _wave(523, 0.09, "square", 0.22),
            np.concatenate([np.zeros(int(RATE * 0.09)), _wave(659, 0.09, "square", 0.22)]),
            np.concatenate([np.zeros(int(RATE * 0.18)), _wave(784, 0.09, "square", 0.22)]),
            np.concatenate([np.zeros(int(RATE * 0.27)), _wave(1046, 0.3, "square", 0.24)]),
        ),
        "win": _snd(
            _wave(659, 0.11, "square", 0.24),
            np.concatenate([np.zeros(int(RATE * 0.11)), _wave(784, 0.11, "square", 0.24)]),
            np.concatenate([np.zeros(int(RATE * 0.22)), _wave(988, 0.11, "square", 0.24)]),
            np.concatenate([np.zeros(int(RATE * 0.33)), _wave(1318, 0.42, "square", 0.26)]),
        ),
        "lose": _snd(
            _wave(392, 0.16, "square", 0.22),
            np.concatenate([np.zeros(int(RATE * 0.16)), _wave(311, 0.16, "square", 0.22)]),
            np.concatenate([np.zeros(int(RATE * 0.32)), _wave(233, 0.5, "square", 0.24, to=180)]),
        ),
    }


_alt = {"blip": False, "step": False}


def play(name):
    if muted or not ok:
        return
    if name in ("blip", "step"):
        _alt[name] = not _alt[name]
        name = name + ("2" if _alt[name] else "")
    s = _sounds.get(name)
    if s:
        s.play()


def toggle():
    global muted
    muted = not muted
    return muted

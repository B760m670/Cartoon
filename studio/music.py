"""Процедурная фоновая музыка: укулеле-переборы (Karplus-Strong), маримба, бас, шейкер.

Генерируется под длину эпизода, бесплатно и без файлов. Стиль задаётся в episode.yaml:
    music: {style: cheerful, bpm: 104, key: C, volume: 0.22, seed: 1}
"""

import numpy as np

from . import config

SR = config.AUDIO_RATE
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

PROGRESSIONS = {
    "cheerful": [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")],      # I–V–vi–IV
    "gentle": [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")],        # I–vi–IV–V
    "wonder": [(5, "maj"), (7, "maj"), (4, "min"), (9, "min")],        # IV–V–iii–vi
    "sad": [(9, "min"), (5, "maj"), (0, "maj"), (7, "maj")],
}


def hz(semi_from_a4):
    return 440.0 * 2 ** (semi_from_a4 / 12)


def pluck(freq, dur, bright=0.5, rng=None):
    n = int(SR * dur)
    period = max(2, int(SR / freq))
    rng = rng or np.random.default_rng(0)
    buf = rng.uniform(-1, 1, period)
    out = np.empty(n)
    decay = 0.996
    for i in range(n):
        out[i] = buf[i % period]
        nxt = buf[(i + 1) % period]
        buf[i % period] = decay * (bright * buf[i % period] + (1 - bright) * 0.5 * (buf[i % period] + nxt))
    env = np.exp(-np.arange(n) / SR * 2.2)
    return out * env


def marimba(freq, dur):
    t = np.arange(int(SR * dur)) / SR
    s = np.sin(2 * np.pi * freq * t) * np.exp(-t * 5) + 0.35 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 14)
    att = np.minimum(1, t / 0.004)
    return s * att


def bass(freq, dur):
    t = np.arange(int(SR * dur)) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
    env = np.minimum(1, t / 0.01) * np.exp(-t * 1.6)
    return s * env


def shaker(dur, rng):
    n = int(SR * dur)
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)  # высокие частоты
    env = np.exp(-np.arange(n) / SR * 60)
    return noise * env * 0.25


def chord_notes(root, kind):
    third = 4 if kind == "maj" else 3
    return [root, root + third, root + 7]


def generate(duration: float, style="cheerful", bpm=104, key="C", seed=1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    total = int(SR * (duration + 2))
    out = np.zeros(total)
    prog = PROGRESSIONS.get(style, PROGRESSIONS["cheerful"])
    k = NOTES.get(key, 0) - 9  # относительно A4 → C4 = -9
    bar = beat * 4
    n_bars = int(np.ceil(duration / bar)) + 1
    # мелодия — простые мотивы из ступеней аккорда, повторяются по 2 такта
    motif = [rng.choice([0, 1, 2, 3, 4]) for _ in range(8)]
    rhythm = [rng.choice([0.5, 0.5, 1.0]) for _ in range(8)]

    def add(sig, start, gain):
        i = int(start * SR)
        if i >= total:
            return
        j = min(total, i + len(sig))
        out[i:j] += sig[: j - i] * gain

    for b in range(n_bars):
        root, kind = prog[b % len(prog)]
        notes = chord_notes(k + root, kind)
        t0 = b * bar
        # бас: 1 и 3 доли
        add(bass(hz(notes[0] - 24), beat * 1.8), t0, 0.32)
        add(bass(hz(notes[0] - 24 + 7), beat * 1.8), t0 + 2 * beat, 0.22)
        # перебор укулеле восьмыми
        pattern = [0, 1, 2, 1, 0, 2, 1, 2]
        for i, idx in enumerate(pattern):
            f = hz(notes[idx] + (12 if idx == 2 and i % 4 == 3 else 0))
            add(pluck(f, beat * 1.5, 0.45, rng), t0 + i * beat / 2, 0.16)
        # шейкер
        for i in range(8):
            add(shaker(0.08, rng), t0 + i * beat / 2 + 0.01, 0.18 if i % 2 else 0.1)
        # мелодия (маримба) — с 3-го такта, чтобы вступление было мягким
        if b >= 2:
            tt = t0
            scale = [0, 2, 4, 7, 9, 12]
            for m, r in zip(motif, rhythm):
                if tt >= t0 + bar:
                    break
                deg = scale[(m + (b // 2) % 2) % len(scale)]
                add(marimba(hz(k + root + deg + 12) if kind == "maj" else hz(k + root + deg + 12 - (1 if deg == 4 else 0)), r * beat + 0.4), tt, 0.13)
                tt += r * beat
    # плавные вход/выход
    fade_in = int(SR * 1.5)
    out[:fade_in] *= np.linspace(0, 1, fade_in)
    end = int(SR * duration)
    fade = int(SR * 2.5)
    out[max(0, end - fade):end] *= np.linspace(1, 0, min(fade, end))
    out[end:] = 0
    # мягкая «комната»: простое эхо
    d = int(SR * 0.18)
    wet = np.zeros_like(out)
    wet[d:] = out[:-d] * 0.25
    out = out + wet
    peak = np.max(np.abs(out)) or 1
    return (out / peak * 0.8)[: int(SR * duration)]


def duck(music: np.ndarray, voice: np.ndarray, amount=0.55, attack=0.05, release=0.4) -> np.ndarray:
    """Приглушает музыку, пока звучат голоса."""
    n = min(len(music), len(voice))
    win = int(SR * 0.02)
    env = np.sqrt(np.convolve(voice[:n] ** 2, np.ones(win) / win, mode="same"))
    active = (env > 0.01).astype(float)
    g = np.ones(n)
    a = 1 / (attack * SR)
    r = 1 / (release * SR)
    level = 0.0
    for i in range(0, n, 64):
        target = active[i]
        level += (target - level) * (a * 64 if target > level else r * 64)
        level = min(1, max(0, level))
        g[i:i + 64] = 1 - amount * level
    out = music.copy()
    out[:n] *= g
    return out

"""Синтез звуковых эффектов (без внешних файлов) и запись звуковой дорожки сцены.

События сцены — список словарей {t, kind, ...}:
  blip  — «голос» персонажа (короткий писк), параметр pitch
  boing — прыжок
  pop   — появление / щелчок
  chime — заставка (мягкий аккорд)
  whoosh — быстрое движение
"""

import wave

import numpy as np

from . import config

RATE = config.AUDIO_RATE


def _env(n, attack=0.005, release=0.05):
    t = np.arange(n) / RATE
    dur = n / RATE
    env = np.minimum(1, t / max(attack, 1e-4)) * np.minimum(1, (dur - t) / max(release, 1e-4))
    return np.clip(env, 0, 1)


def blip(pitch=440.0, dur=0.07):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    wave_ = np.sign(np.sin(2 * np.pi * pitch * t)) * 0.35 + np.sin(2 * np.pi * pitch * 2 * t) * 0.15
    return wave_ * _env(n, 0.004, 0.03) * 0.5


def boing(dur=0.45):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    freq = 180 + 520 * (t / dur) + 30 * np.sin(2 * np.pi * 14 * t)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase) * _env(n, 0.01, 0.15) * 0.45


def pop(dur=0.08):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    freq = 900 - 700 * (t / dur)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase) * _env(n, 0.002, 0.05) * 0.5


def chime(dur=1.6):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for i, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
        start = int(i * 0.09 * RATE)
        tt = t[: n - start]
        out[start:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.5) * 0.18
    return out * _env(n, 0.005, 0.3)


def whoosh(dur=0.35):
    n = int(RATE * dur)
    rng = np.random.default_rng(1)
    noise = rng.standard_normal(n)
    kernel = np.ones(30) / 30
    noise = np.convolve(noise, kernel, mode="same")
    shape = np.sin(np.pi * np.arange(n) / n) ** 2
    return noise * shape * 0.6


def rain(dur=8.0):
    """Шум дождя: мягкий «розовый» шум + редкие капли."""
    n = int(RATE * dur)
    rng = np.random.default_rng(5)
    noise = rng.standard_normal(n)
    noise = np.convolve(noise, np.ones(6) / 6, mode="same") - np.convolve(noise, np.ones(120) / 120, mode="same")
    drops = np.zeros(n)
    for i in rng.integers(0, max(1, n - 800), int(dur * 30)):
        k = np.arange(600)
        drops[i:i + 600] += np.sin(k * rng.uniform(0.12, 0.3)) * np.exp(-k / 90) * rng.uniform(0.1, 0.35)
    edge = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (RATE * 0.6))
    return (noise * 0.35 + drops) * edge


def splash(dur=0.5):
    n = int(RATE * dur)
    rng = np.random.default_rng(9)
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(40) / 40, mode="same")
    k = np.arange(n)
    blub = np.sin(2 * np.pi * (300 - 180 * k / n) * k / RATE) * np.exp(-k / (RATE * 0.06))
    return (noise * np.exp(-k / (RATE * 0.12)) * 0.7 + blub * 0.5)


SYNTHS = {"blip": blip, "boing": boing, "pop": pop, "chime": chime, "whoosh": whoosh, "rain": rain, "splash": splash}


def render_track(events: list[dict], duration: float) -> np.ndarray:
    total = int(round(duration * RATE))
    buf = np.zeros(total)
    for ev in events:
        params = {k: v for k, v in ev.items() if k not in ("t", "kind", "volume")}
        sound = SYNTHS[ev["kind"]](**params) * float(ev.get("volume", 1.0))
        start = int(ev["t"] * RATE)
        if start >= total:
            continue
        end = min(total, start + len(sound))
        buf[start:end] += sound[: end - start]
    peak = np.max(np.abs(buf)) if total else 0
    if peak > 0.95:
        buf *= 0.95 / peak
    return buf


def write_wav(path, samples: np.ndarray):
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())

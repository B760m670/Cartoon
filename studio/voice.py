"""Озвучка реплик через Kokoro (бесплатная нейросеть TTS, работает на CPU).

Голос персонажа — в character.yaml:  voice: {kokoro: am_puck, pitch: 1.12, speed: 1.0}
Готовые реплики кэшируются в output/<эпизод>/voice/, повторно не синтезируются.
"""

import hashlib
import subprocess
import urllib.request
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import config


def ensure_models():
    for path in (config.KOKORO_MODEL, config.KOKORO_VOICES):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"  ↓ скачиваю {path.name} (один раз)…")
            urllib.request.urlretrieve(config.KOKORO_URL + path.name, path)


@lru_cache(maxsize=1)
def _kokoro():
    from kokoro_onnx import Kokoro

    ensure_models()
    return Kokoro(str(config.KOKORO_MODEL), str(config.KOKORO_VOICES))


def _read_wav_mono(path: Path) -> np.ndarray:
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    assert sr == config.AUDIO_RATE, sr
    return data


def synth(text: str, voice: dict, cache_dir: Path) -> np.ndarray:
    """Возвращает моно-сэмплы 44.1 кГц."""
    import soundfile as sf

    name = voice.get("kokoro", "af_heart")
    pitch = float(voice.get("pitch", 1.0))
    speed = float(voice.get("speed", 1.0))
    key = hashlib.sha1(f"{name}|{pitch}|{speed}|{text}".encode()).hexdigest()[:16]
    out = cache_dir / f"{key}.wav"
    if not out.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        lang = "en-gb" if name.startswith("b") else "en-us"
        samples, sr = _kokoro().create(text, voice=name, speed=speed, lang=lang)
        raw = out.with_suffix(".raw.wav")
        sf.write(str(raw), samples, sr)
        af = f"asetrate={int(sr * pitch)},aresample={config.AUDIO_RATE},atempo={1 / pitch:.5f}" if pitch != 1 else f"aresample={config.AUDIO_RATE}"
        af += ",highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", af, "-ac", "1", str(out)], check=True)
        raw.unlink()
    return _read_wav_mono(out)


def mouth_envelope(samples: np.ndarray, fps: int) -> np.ndarray:
    """Открытие рта 0..1 на каждый кадр по громкости (с лёгким сглаживанием)."""
    hop = config.AUDIO_RATE // fps
    n = int(np.ceil(len(samples) / hop))
    env = np.zeros(n)
    for i in range(n):
        seg = samples[i * hop:(i + 1) * hop]
        env[i] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
    if env.max() > 0:
        env = env / (np.percentile(env, 95) + 1e-6)
    env = np.clip((env - 0.12) * 1.25, 0, 1)
    # чтобы рот «щёлкал» по слогам, а не дрожал
    sm = np.convolve(env, [0.25, 0.5, 0.25], mode="same")
    return np.clip(sm, 0, 1)

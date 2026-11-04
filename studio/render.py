"""Рендер эпизода: сцены параллельно → склейка → общий звук (голоса + эффекты + музыка)."""

import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from cartoon import encoder
from cartoon.audio import write_wav
from . import config, music
from .scene import Scene


def resolve_episode(name: str) -> Path:
    p = Path(name)
    if (p / "episode.yaml").exists():
        return p.resolve()
    p = config.EPISODES_DIR / name
    if (p / "episode.yaml").exists():
        return p
    raise FileNotFoundError(f"Эпизод не найден: {name}")


def load_episode(name):
    d = resolve_episode(name)
    spec = yaml.safe_load((d / "episode.yaml").read_text(encoding="utf-8"))
    files = [d / "scenes" / s for s in spec["scenes"]] if spec.get("scenes") else sorted((d / "scenes").glob("*.yaml"))
    return d, spec, files


def size_for(preview):
    return (config.W // 2, config.H // 2) if preview else (config.W, config.H)


def build_scene(ep_dir: Path, spec: dict, path: Path, preview: bool) -> Scene:
    w, h = size_for(preview)
    cache = config.OUTPUT_DIR / ep_dir.name / "voice"
    return Scene(path.stem, yaml.safe_load(path.read_text(encoding="utf-8")), spec, w, h, cache)


def render_scene(ep_name, scene_path, out_dir, preview):
    ep_dir, spec, _ = load_episode(ep_name)
    scene = build_scene(ep_dir, spec, Path(scene_path), preview)
    fps = spec.get("fps", config.FPS)
    out = Path(out_dir) / f"{scene.id}.mp4"
    frames = int(round(scene.duration * fps))
    t0 = time.time()
    w = encoder.VideoWriter(out, scene.W, scene.H, fps, None, crf=24 if preview else 17)
    try:
        for i in range(frames):
            w.write_array(scene.frame(i / fps))
    finally:
        w.close()
    mix, voice = scene.audio()
    n = int(round(frames / fps * config.AUDIO_RATE))
    mix = np.pad(mix, (0, max(0, n - len(mix))))[:n]
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    np.save(Path(out_dir) / f"{scene.id}.mix.npy", mix)
    np.save(Path(out_dir) / f"{scene.id}.voice.npy", voice)
    return str(out), frames, time.time() - t0


def render_episode(name, only=None, preview=False, jobs=None):
    ep_dir, spec, files = load_episode(name)
    if only:
        files = [f for f in files if f.stem in only]
    out_root = config.OUTPUT_DIR / ep_dir.name
    scenes_dir = out_root / ("preview" if preview else "scenes")
    scenes_dir.mkdir(parents=True, exist_ok=True)
    jobs = jobs or min(len(files), os.cpu_count() or 1)
    title = spec.get("title", ep_dir.name)
    print(f"▶ {title}: {len(files)} сцен, {'превью' if preview else 'Full HD'}, потоков {jobs}")
    started = time.time()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futs = [pool.submit(render_scene, str(ep_dir), str(f), str(scenes_dir), preview) for f in files]
        parts = []
        for f in futs:
            out, frames, secs = f.result()
            parts.append(Path(out))
            print(f"  ✓ {Path(out).name}: {frames} кадров за {secs:.1f} с")

    silent = out_root / "_video.mp4"
    encoder.concat(parts, silent)
    mix = np.concatenate([np.load(p.with_suffix(".mix.npy")) for p in parts])
    voice = np.concatenate([np.load(p.with_suffix(".voice.npy")) for p in parts])
    mspec = spec.get("music")
    if mspec:
        bed = music.generate(len(mix) / config.AUDIO_RATE, mspec.get("style", "cheerful"), mspec.get("bpm", 104),
                             mspec.get("key", "C"), mspec.get("seed", 1))
        bed = music.duck(bed, voice, amount=mspec.get("duck", 0.6))
        mix = mix + bed[: len(mix)] * float(mspec.get("volume", 0.22))
    peak = np.max(np.abs(mix)) or 1
    mix = mix / max(peak, 1.0) * 0.97
    wav = out_root / "_audio.wav"
    write_wav(wav, mix)
    suffix = "_preview" if preview else ""
    final = out_root / f"{ep_dir.name}{suffix}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest", "-movflags", "+faststart", str(final)],
                   check=True)
    silent.unlink()
    wav.unlink()
    print(f"✔ {final}  ({time.time() - started:.0f} с)\n  {encoder.probe(final)}")
    return final


def render_still(name, scene_id, t, preview=False):
    ep_dir, spec, files = load_episode(name)
    match = [f for f in files if f.stem == scene_id]
    if not match:
        raise ValueError(f"Нет сцены {scene_id}. Есть: {', '.join(f.stem for f in files)}")
    scene = build_scene(ep_dir, spec, match[0], preview)
    fps = spec.get("fps", config.FPS)
    # прогоняем кадры до t, чтобы пружины/состояния были честными
    last = int(t * fps)
    for i in range(last):
        for a in scene.actors:
            a.pose(i / fps)
    arr = scene.frame(last / fps)
    from PIL import Image
    out = config.OUTPUT_DIR / ep_dir.name / "stills" / f"{scene_id}_{t:.2f}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out)
    print(f"✔ {out}")
    return out

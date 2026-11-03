"""Оркестратор рендера: эпизод → сцены → кадры → MP4."""

import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import audio, encoder
from .loader import Episode, load_characters, load_episode, read_yaml
from .scene import Scene


def _size(ep: Episode, preview: bool) -> tuple[int, int]:
    if preview:
        return ep.width // 2 // 2 * 2, ep.height // 2 // 2 * 2
    return ep.width, ep.height


def build_scene(ep: Episode, path: Path, preview: bool = False) -> Scene:
    w, h = _size(ep, preview)
    chars = load_characters(ep.dir / "characters")
    return Scene(path.stem, read_yaml(path), chars, w, h)


def render_scene(ep_name: str, scene_path: str, out_dir: str, preview: bool) -> tuple[str, float, int]:
    ep = load_episode(ep_name)
    scene = build_scene(ep, Path(scene_path), preview)
    out = Path(out_dir) / f"{scene.id}.mp4"
    wav = Path(out_dir) / f"{scene.id}.wav"
    frames = int(round(scene.duration * ep.fps))
    audio.write_wav(wav, audio.render_track(scene.sound_events(), frames / ep.fps))
    writer = encoder.VideoWriter(out, scene.width, scene.height, ep.fps, wav, crf=26 if preview else 18)
    started = time.time()
    try:
        for i in range(frames):
            writer.write(scene.frame(i / ep.fps))
    finally:
        writer.close()
        wav.unlink(missing_ok=True)
    return str(out), time.time() - started, frames


def render_episode(name: str, only: list[str] | None = None, preview: bool = False, jobs: int | None = None) -> Path:
    ep = load_episode(name)
    files = [f for f in ep.scene_files if not only or f.stem in only]
    if not files:
        raise ValueError(f"Нет сцен для рендера (фильтр: {only})")
    scenes_dir = ep.output_dir / ("preview" if preview else "scenes")
    scenes_dir.mkdir(parents=True, exist_ok=True)
    jobs = jobs or min(len(files), os.cpu_count() or 1)

    print(f"▶ {ep.title}: {len(files)} сцен, {ep.fps} fps, {'превью' if preview else 'финал'}, потоков: {jobs}")
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(render_scene, str(ep.dir), str(f), str(scenes_dir), preview) for f in files]
        parts = []
        for f in futures:
            out, secs, frames = f.result()
            parts.append(Path(out))
            print(f"  ✓ {Path(out).name}: {frames} кадров за {secs:.1f} с")

    suffix = "_preview" if preview else ""
    final = ep.output_dir / f"{ep.id}{suffix}.mp4"
    if only and len(parts) == 1:
        shutil.copyfile(parts[0], final.with_name(f"{ep.id}_{parts[0].stem}{suffix}.mp4"))
        final = final.with_name(f"{ep.id}_{parts[0].stem}{suffix}.mp4")
    else:
        encoder.concat(parts, final)
    if ep.music and ep.music.exists():
        tmp = final.with_suffix(".music.mp4")
        encoder.add_music(final, ep.music, tmp, ep.music_volume)
        tmp.replace(final)
    print(f"✔ Готово: {final}\n  {encoder.probe(final)}")
    return final


def render_still(name: str, scene_id: str, t: float, out: Path | None = None) -> Path:
    """Один кадр в PNG — чтобы быстро посмотреть, как выглядит сцена."""
    ep = load_episode(name)
    match = [f for f in ep.scene_files if f.stem == scene_id]
    if not match:
        raise ValueError(f"Сцена '{scene_id}' не найдена. Есть: {', '.join(f.stem for f in ep.scene_files)}")
    scene = build_scene(ep, match[0])
    out = out or ep.output_dir / "stills" / f"{scene_id}_{t:.2f}s.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.frame(t).save(out)
    print(f"✔ Кадр: {out}")
    return out

"""Загрузка эпизодов, сцен и персонажей из YAML."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config
from .characters import Character


def read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_characters(extra_dir: Path | None = None) -> dict[str, Character]:
    """Все персонажи из characters/ (и, если есть, из <эпизод>/characters/)."""
    chars = {}
    for base in filter(None, [config.CHARACTERS_DIR, extra_dir]):
        for path in sorted(Path(base).glob("*/character.yaml")):
            cid = path.parent.name
            chars[cid] = Character(cid, read_yaml(path))
    return chars


@dataclass
class Episode:
    id: str
    dir: Path
    title: str
    fps: int
    width: int
    height: int
    scene_files: list[Path]
    music: Path | None = None
    music_volume: float = 0.3
    spec: dict = field(default_factory=dict)

    @property
    def output_dir(self) -> Path:
        return config.OUTPUT_DIR / self.id


def resolve_episode(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if (p / "episode.yaml").exists():
        return p.resolve()
    candidate = config.EPISODES_DIR / name_or_path
    if (candidate / "episode.yaml").exists():
        return candidate
    raise FileNotFoundError(f"Эпизод не найден: {name_or_path} (ожидается папка с episode.yaml)")


def load_episode(name_or_path: str) -> Episode:
    d = resolve_episode(name_or_path)
    spec = read_yaml(d / "episode.yaml")
    if spec.get("scenes"):
        files = [d / "scenes" / s for s in spec["scenes"]]
    else:
        files = sorted((d / "scenes").glob("*.yaml"))
    missing = [f for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"Нет файлов сцен: {', '.join(map(str, missing))}")
    music = spec.get("music")
    return Episode(
        id=d.name,
        dir=d,
        title=spec.get("title", d.name),
        fps=int(spec.get("fps", config.DEFAULT_FPS)),
        width=int(spec.get("width", config.DEFAULT_WIDTH)),
        height=int(spec.get("height", config.DEFAULT_HEIGHT)),
        scene_files=files,
        music=(config.ASSETS_DIR / "audio" / music) if music else None,
        music_volume=float(spec.get("music_volume", 0.3)),
        spec=spec,
    )

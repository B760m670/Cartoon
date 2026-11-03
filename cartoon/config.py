"""Пути проекта и настройки по умолчанию."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = ROOT / "characters"
EPISODES_DIR = ROOT / "episodes"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"
TEMPLATES_DIR = ROOT / "templates"

# Логический холст: все координаты в сценах задаются в этой системе,
# а при рендере масштабируются под реальное разрешение эпизода.
LOGICAL_WIDTH = 1280
LOGICAL_HEIGHT = 720

DEFAULT_FPS = 24
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720

# Во сколько раз рисуем крупнее перед уменьшением (сглаживание краёв).
SUPERSAMPLE = 2

AUDIO_RATE = 44100

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

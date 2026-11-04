"""Настройки движка studio."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = ROOT / "characters"
LOCATIONS_DIR = ROOT / "locations"
EPISODES_DIR = ROOT / "episodes"
OUTPUT_DIR = ROOT / "output"
MODELS_DIR = ROOT / "models"            # большие модели (голоса) — не в git

W, H = 1920, 1080                       # логический холст; рендер может быть меньше (превью)
FPS = 24
LAYER_QUALITY = 1.0                     # во сколько раз детальнее растрить слои фона
AUDIO_RATE = 44100

KOKORO_MODEL = MODELS_DIR / "kokoro" / "kokoro-v1.0.onnx"
KOKORO_VOICES = MODELS_DIR / "kokoro" / "voices-v1.0.bin"
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"

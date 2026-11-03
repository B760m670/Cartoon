"""Всё, что касается ffmpeg: кодирование кадров, склейка сцен, музыка."""

import shutil
import subprocess
from pathlib import Path


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg не найден. Установите его: sudo apt install ffmpeg / brew install ffmpeg")
    return exe


class VideoWriter:
    """Принимает кадры (PIL.Image RGB) и пишет MP4 (H.264 + AAC)."""

    def __init__(self, path: Path, width: int, height: int, fps: int, audio: Path | None, crf: int = 18):
        cmd = [
            require_ffmpeg(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        ]
        if audio:
            cmd += ["-i", str(audio)]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
        cmd += ["-movflags", "+faststart", str(path)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, img):
        self.proc.stdin.write(img.tobytes())

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg завершился с ошибкой при кодировании")


def concat(parts: list[Path], out: Path):
    """Склейка готовых сцен (одинаковые параметры) без перекодирования."""
    list_file = out.with_suffix(".concat.txt")
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(out)],
        check=True,
    )
    list_file.unlink()


def add_music(video: Path, music: Path, out: Path, volume: float = 0.3):
    """Подмешивает музыку (зацикленную) к звуковой дорожке видео."""
    subprocess.run(
        [require_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-stream_loop", "-1", "-i", str(music),
         "-filter_complex", f"[1:a]volume={volume}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(out)],
        check=True,
    )


def probe(path: Path) -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        return ""
    res = subprocess.run(
        [exe, "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate",
         "-of", "compact", str(path)],
        capture_output=True, text=True,
    )
    return res.stdout.strip()

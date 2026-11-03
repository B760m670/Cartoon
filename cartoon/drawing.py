"""Холст с логическими координатами и общие помощники рисования."""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config


def hex_to_rgb(value, alpha: int | None = None):
    if isinstance(value, (tuple, list)):
        rgb = tuple(int(c) for c in value[:3])
    else:
        v = str(value).lstrip("#")
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        rgb = tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))
    return rgb + (alpha,) if alpha is not None else rgb


def mix(a, b, p: float):
    a, b = hex_to_rgb(a), hex_to_rgb(b)
    return tuple(int(x + (y - x) * p) for x, y in zip(a, b))


@lru_cache(maxsize=None)
def font(size: int) -> ImageFont.FreeTypeFont:
    """Шрифт с кириллицей: сначала assets/fonts, потом системные."""
    candidates = sorted(Path(config.ASSETS_DIR / "fonts").glob("*.[to]tf"))
    candidates += [Path(p) for p in config.FONT_CANDIDATES]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


class Canvas:
    """Рисование в логической системе 1280x720 на холсте любого размера."""

    def __init__(self, width: int, height: int, color="#000000"):
        self.k = width / config.LOGICAL_WIDTH
        self.img = Image.new("RGB", (width, height), hex_to_rgb(color))
        self.draw = ImageDraw.Draw(self.img, "RGBA")

    def _pts(self, points):
        return [(x * self.k, y * self.k) for x, y in points]

    def _w(self, width):
        return max(1, round(width * self.k)) if width else 0

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=0):
        box = [(cx - rx) * self.k, (cy - ry) * self.k, (cx + rx) * self.k, (cy + ry) * self.k]
        self.draw.ellipse(box, fill=fill, outline=outline, width=self._w(width))

    def rounded_rect(self, x0, y0, x1, y1, radius, fill=None, outline=None, width=0):
        box = [x0 * self.k, y0 * self.k, x1 * self.k, y1 * self.k]
        self.draw.rounded_rectangle(
            box, radius=radius * self.k, fill=fill, outline=outline, width=self._w(width)
        )

    def rect(self, x0, y0, x1, y1, fill):
        self.draw.rectangle([x0 * self.k, y0 * self.k, x1 * self.k, y1 * self.k], fill=fill)

    def polygon(self, points, fill=None, outline=None, width=0):
        self.draw.polygon(self._pts(points), fill=fill, outline=outline, width=self._w(width))

    def line(self, points, fill, width=1):
        self.draw.line(self._pts(points), fill=fill, width=self._w(width), joint="curve")

    def arc(self, cx, cy, rx, ry, start, end, fill, width=1):
        box = [(cx - rx) * self.k, (cy - ry) * self.k, (cx + rx) * self.k, (cy + ry) * self.k]
        self.draw.arc(box, start, end, fill=fill, width=self._w(width))

    def pieslice(self, cx, cy, rx, ry, start, end, fill=None, outline=None, width=0):
        box = [(cx - rx) * self.k, (cy - ry) * self.k, (cx + rx) * self.k, (cy + ry) * self.k]
        self.draw.pieslice(box, start, end, fill=fill, outline=outline, width=self._w(width))

    def text_size(self, text, size):
        f = font(max(1, round(size * self.k)))
        l, t, r, b = self.draw.multiline_textbbox((0, 0), text, font=f, spacing=4 * self.k)
        return (r - l) / self.k, (b - t) / self.k

    def text(self, x, y, text, size, fill, anchor="la", stroke=0, stroke_fill=None):
        f = font(max(1, round(size * self.k)))
        self.draw.multiline_text(
            (x * self.k, y * self.k), text, font=f, fill=fill, anchor=anchor,
            spacing=4 * self.k, align="center",
            stroke_width=self._w(stroke), stroke_fill=stroke_fill,
        )


def wrap_text(text: str, max_chars: int) -> str:
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


def speech_bubble(cv: Canvas, tip_x, tip_y, text, size=30, max_chars=22):
    """Облачко с репликой; хвостик указывает в точку (tip_x, tip_y)."""
    if not text:
        return
    wrapped = wrap_text(text, max_chars)
    tw, th = cv.text_size(wrapped, size)
    pad = 18
    w, h = tw + pad * 2, th + pad * 2
    x0 = min(max(tip_x - w / 2, 20), config.LOGICAL_WIDTH - 20 - w)
    y1 = tip_y - 26
    y0 = y1 - h
    ink = (40, 30, 30)
    cv.polygon([(tip_x - 14, y1 - 4), (tip_x + 14, y1 - 4), (tip_x, tip_y)], fill="white", outline=ink, width=3)
    cv.rounded_rect(x0, y0, x0 + w, y1, 22, fill="white", outline=ink, width=3)
    cv.polygon([(tip_x - 11, y1 - 5), (tip_x + 11, y1 - 5), (tip_x, tip_y - 5)], fill="white")
    cv.text(x0 + w / 2, y0 + h / 2, wrapped, size, ink, anchor="mm")

"""Тонкая обёртка над Skia: цвета, кисти, формы, cel-shading."""

import math
from functools import lru_cache

import numpy as np
import skia


def rgb(value, a: float = 1.0) -> int:
    """'#RRGGBB' | (r,g,b) → skia Color4 int с альфой a (0..1)."""
    if isinstance(value, int):
        return value
    if isinstance(value, (tuple, list)):
        r, g, b = (int(c) for c in value[:3])
    else:
        r, g, b = to_tuple(value)
    return skia.Color(r, g, b, int(max(0, min(1, a)) * 255))


def to_tuple(value):
    if isinstance(value, (tuple, list)):
        return tuple(int(c) for c in value[:3])
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def shade(color, k: float):
    """k<0 — темнее (с уходом в холодный оттенок, как в аниме), k>0 — светлее (в тёплый)."""
    r, g, b = to_tuple(color)
    if k < 0:
        k = -k
        tr, tg, tb = r * 0.55, g * 0.5, min(255, b * 0.75 + 40)  # тень холоднее
        return (int(r + (tr - r) * k), int(g + (tg - g) * k), int(b + (tb - b) * k))
    return (int(r + (255 - r) * k), int(g + (250 - g) * k), int(b + (235 - b) * k))


def mix(a, b, p):
    a, b = to_tuple(a), to_tuple(b)
    return tuple(int(x + (y - x) * p) for x, y in zip(a, b))


def fill(color, a=1.0, blur=0.0, shader=None, blend=None):
    p = skia.Paint(AntiAlias=True, Color=rgb(color, a))
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if shader is not None:
        p.setShader(shader)
        p.setAlphaf(a)
    if blend is not None:
        p.setBlendMode(blend)
    return p


def stroke(color, width, a=1.0, cap=skia.Paint.kRound_Cap, blur=0.0):
    p = skia.Paint(AntiAlias=True, Color=rgb(color, a), Style=skia.Paint.kStroke_Style,
                   StrokeWidth=width, StrokeCap=cap, StrokeJoin=skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p


def linear(p0, p1, colors, stops=None, alphas=None):
    cols = [rgb(c, alphas[i] if alphas else 1) for i, c in enumerate(colors)]
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], cols, stops)


def radial(center, r, colors, stops=None, alphas=None):
    cols = [rgb(c, alphas[i] if alphas else 1) for i, c in enumerate(colors)]
    return skia.GradientShader.MakeRadial(skia.Point(*center), r, cols, stops)


# ---------- формы ----------

def oval(cx, cy, rx, ry) -> skia.Path:
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


def smooth_closed(points, tension=1.0) -> skia.Path:
    """Гладкая замкнутая кривая через точки (Catmull-Rom → кубические Безье)."""
    n = len(points)
    p = skia.Path()
    p.moveTo(*points[0])
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        p.cubicTo(*c1, *c2, *p2)
    p.close()
    return p


def smooth_open(points, tension=1.0) -> skia.Path:
    p = skia.Path()
    p.moveTo(*points[0])
    pts = [points[0]] + list(points) + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        p.cubicTo(*c1, *c2, *p2)
    return p


def blob(cx, cy, rx, ry, top=1.0, bottom=1.0, waist=1.0, n=16) -> skia.Path:
    """Мягкая «груша»: top/bottom — ширина верха/низа, waist — сужение в середине."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s, c = math.sin(a), math.cos(a)
        w = top if c < 0 else bottom
        w = 1 + (w - 1) * abs(c)
        w *= 1 - (1 - waist) * (1 - abs(c)) ** 2
        pts.append((cx + s * rx * w, cy + c * ry))
    return smooth_closed(pts)


def capsule(x0, y0, x1, y1, r0, r1) -> skia.Path:
    """Конечность: суживающаяся «сосиска» от (x0,y0) радиуса r0 до (x1,y1) радиуса r1."""
    ang = math.atan2(y1 - y0, x1 - x0)
    nx, ny = -math.sin(ang), math.cos(ang)
    p = skia.Path()
    p.moveTo(x0 + nx * r0, y0 + ny * r0)
    p.lineTo(x1 + nx * r1, y1 + ny * r1)
    p.arcTo(skia.Rect.MakeLTRB(x1 - r1, y1 - r1, x1 + r1, y1 + r1), math.degrees(ang) + 90, -180, False)
    p.lineTo(x0 - nx * r0, y0 - ny * r0)
    p.arcTo(skia.Rect.MakeLTRB(x0 - r0, y0 - r0, x0 + r0, y0 + r0), math.degrees(ang) - 90, -180, False)
    p.close()
    return p


def union(*paths) -> skia.Path:
    out = paths[0]
    for p in paths[1:]:
        out = skia.Op(out, p, skia.PathOp.kUnion_PathOp)
    return out


def moved(path: skia.Path, dx, dy) -> skia.Path:
    p = skia.Path(path)
    p.offset(dx, dy)
    return p


# ---------- аниме-заливка ----------

class Light:
    """Направление света (откуда падает) и сила теней — общее на сцену."""

    def __init__(self, dx=-0.6, dy=-0.8, shadow=0.42, rim="#FFF4D6", rim_a=0.55):
        n = math.hypot(dx, dy) or 1
        self.dx, self.dy = dx / n, dy / n
        self.shadow, self.rim, self.rim_a = shadow, rim, rim_a


def cel(canvas: skia.Canvas, path: skia.Path, base, light: Light, size: float, outline=True,
        shadow_k=None, highlight=True, line_w=None):
    """Заливка в стиле аниме: основной цвет, жёсткая тень, блик, цветной контур."""
    shadow_k = light.shadow if shadow_k is None else shadow_k
    canvas.drawPath(path, fill(shade(base, -shadow_k)))
    canvas.save()
    canvas.clipPath(path, doAntiAlias=True)
    off = size * 0.22
    canvas.drawPath(moved(path, light.dx * off, light.dy * off), fill(base))
    if highlight:
        hp = moved(path, light.dx * size * 0.55, light.dy * size * 0.55)
        canvas.save()
        canvas.clipPath(hp, doAntiAlias=True)
        canvas.drawPath(moved(path, -light.dx * size * 0.35, -light.dy * size * 0.35),
                        fill(shade(base, 0.22), 0.0))
        canvas.restore()
        # мягкий блик сверху у источника света
        b = path.getBounds()
        cx = b.centerX() + light.dx * b.width() * 0.22
        cy = b.centerY() + light.dy * b.height() * 0.25
        canvas.drawOval(skia.Rect.MakeXYWH(cx - b.width() * 0.22, cy - b.height() * 0.14,
                                           b.width() * 0.44, b.height() * 0.28),
                        fill(shade(base, 0.35), 0.35, blur=size * 0.08))
    # отражённый свет (rim) с теневой стороны
    canvas.drawPath(path, stroke(light.rim, size * 0.05, light.rim_a * 0.0))
    canvas.restore()
    if outline:
        w = line_w if line_w is not None else max(2.0, size * 0.035)
        canvas.drawPath(path, stroke(shade(base, -0.85), w))


@lru_cache(maxsize=None)
def typeface(bold=True):
    style = skia.FontStyle.Bold() if bold else skia.FontStyle.Normal()
    for fam in ("DejaVu Sans", "Liberation Sans", "Arial"):
        tf = skia.FontMgr().matchFamilyStyle(fam, style)
        if tf:
            return tf
    return skia.Typeface.MakeDefault()


def text(canvas, s, x, y, size, color="#FFFFFF", outline="#20152B", outline_w=0.0, align="center", a=1.0, bold=True):
    font = skia.Font(typeface(bold), size)
    w = font.measureText(s)
    if align == "center":
        x -= w / 2
    blob_ = skia.TextBlob.MakeFromString(s, font)
    if outline_w:
        canvas.drawTextBlob(blob_, x, y, stroke(outline, outline_w, a))
    canvas.drawTextBlob(blob_, x, y, fill(color, a))
    return w


def text_width(s, size, bold=True):
    return skia.Font(typeface(bold), size).measureText(s)


def surface_to_rgb(surface: skia.Surface) -> np.ndarray:
    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return arr[:, :, :3]


_SCRATCH = {}


def blend_upscaled(canvas, small_img, W, H, mode=skia.BlendMode.kScreen, alpha=1.0):
    """Растянуть маленькую картинку на весь кадр и смешать режимом mode.

    Напрямую (растяжение + Screen) Skia на CPU делает медленно, поэтому сначала
    растягиваем обычным наложением во временную поверхность, потом смешиваем 1:1.
    """
    key = (W, H)
    if key not in _SCRATCH:
        _SCRATCH[key] = skia.Surface(W, H)
    scratch = _SCRATCH[key]
    sc = scratch.getCanvas()
    sc.clear(skia.ColorTRANSPARENT)
    sc.drawImageRect(small_img, skia.Rect(0, 0, W, H), skia.SamplingOptions(skia.FilterMode.kLinear))
    p = skia.Paint(BlendMode=mode)
    p.setAlphaf(alpha)
    canvas.drawImage(scratch.makeImageSnapshot(), 0, 0, skia.SamplingOptions(), p)

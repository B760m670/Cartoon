"""Локации: многослойные фоны с параллаксом.

Локация — папка locations/<id>/ с файлом location.py, где описан список слоёв:

    LAYERS = [
        {"name": "sky", "parallax": 0.0, "draw": draw_sky},
        {"name": "hills", "parallax": 0.3, "draw": draw_hills, "blur": 1.5},
        ...
    ]
    ANCHORS = {"apple_branch": (1350, 360)}   # полезные точки для сцен
    def dynamic(c, layer, t, rnd): ...        # необязательно: облака, трава на ветру

parallax: 0 — неподвижно (небо), 1 — плоскость персонажей, >1 — передний план.
Каждый статичный слой рисуется один раз в картинку, а на кадре только сдвигается.
"""

import importlib.util
import math
import random

import skia

from . import config, skx

MARGIN_X, MARGIN_Y = 520, 260


def load(location_id: str, light: skx.Light):
    path = config.LOCATIONS_DIR / location_id / "location.py"
    if not path.exists():
        raise FileNotFoundError(f"Нет локации {location_id}: ожидается {path}")
    spec = importlib.util.spec_from_file_location(f"location_{location_id}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return Location(location_id, mod, light)


class Camera:
    def __init__(self, x=960, y=540, zoom=1.0, shake=0.0):
        self.x, self.y, self.zoom, self.shake = x, y, zoom, shake

    def matrix(self, parallax: float, W=config.W, H=config.H) -> skia.Matrix:
        cx = W / 2 + (self.x - W / 2) * parallax
        cy = H / 2 + (self.y - H / 2) * parallax
        z = 1 + (self.zoom - 1) * parallax
        m = skia.Matrix()
        m.setTranslate(W / 2, H / 2)
        m.preScale(z, z)
        m.preTranslate(-cx, -cy)
        return m


class Location:
    def __init__(self, lid, mod, light):
        self.id = lid
        self.mod = mod
        self.light = light
        self.anchors = getattr(mod, "ANCHORS", {})
        self.ground_y = getattr(mod, "GROUND_Y", 940)
        self.layers = []
        q = config.LAYER_QUALITY
        for spec in mod.LAYERS:
            w = int((config.W + 2 * MARGIN_X) * q)
            h = int((config.H + 2 * MARGIN_Y) * q)
            surf = skia.Surface(w, h)
            c = surf.getCanvas()
            c.scale(q, q)
            c.translate(MARGIN_X, MARGIN_Y)
            spec["draw"](c, light)
            img = surf.makeImageSnapshot()
            if spec.get("blur"):
                b = spec["blur"] * q
                s2 = skia.Surface(w, h)
                p = skia.Paint(ImageFilter=skia.ImageFilters.Blur(b, b))
                s2.getCanvas().drawImage(img, 0, 0, skia.SamplingOptions(), p)
                img = s2.makeImageSnapshot()
            self.layers.append({**spec, "image": img})

    def draw_layers(self, c: skia.Canvas, cam: Camera, t: float, which: str):
        """which: 'back' — слои с parallax ≤ 1, 'front' — передний план (> 1)."""
        q = config.LAYER_QUALITY
        mip = skia.MipmapMode.kLinear if c.getTotalMatrix().getScaleX() < 0.9 else skia.MipmapMode.kNone
        sampling = skia.SamplingOptions(skia.FilterMode.kLinear, mip)
        for layer in self.layers:
            p = layer["parallax"]
            if (which == "back") != (p <= 1.0):
                continue
            c.save()
            c.concat(cam.matrix(p))
            c.save()
            c.translate(-MARGIN_X, -MARGIN_Y)
            c.scale(1 / q, 1 / q)
            c.drawImage(layer["image"], 0, 0, sampling)
            c.restore()
            dyn = getattr(self.mod, "dynamic", None)
            if dyn:
                dyn(c, layer["name"], t, self.light)
            c.restore()

    def screen_effects(self, c, t):
        fx = getattr(self.mod, "screen_effects", None)
        if fx:
            fx(c, t, self.light)


_RAY_CACHE = {}


def light_rays(c, t, origin, color="#FFF3C4", n=6, alpha=0.12, seed=1, W=config.W, H=config.H):
    """Солнечные лучи: каждый луч растрится один раз в 1/4 разрешения, на кадре только «дышит» прозрачностью."""
    key = (origin, color, n, alpha, seed)
    if key not in _RAY_CACHE:
        rnd = random.Random(seed)
        ox, oy = origin
        rays = []
        q = 0.25
        for i in range(n):
            a0 = rnd.uniform(0.25, 1.35) * math.pi / 2
            w = rnd.uniform(0.03, 0.08)
            surf = skia.Surface(int(W * q), int(H * q))
            sc = surf.getCanvas()
            sc.scale(q, q)
            L = 2600
            p = skia.Path()
            p.moveTo(ox, oy)
            p.lineTo(ox - math.cos(a0 - w) * L, oy + math.sin(a0 - w) * L)
            p.lineTo(ox - math.cos(a0 + w) * L, oy + math.sin(a0 + w) * L)
            p.close()
            shader = skx.radial((ox, oy), 1400, [color, color], [0, 1], [alpha, 0])
            sc.drawPath(p, skx.fill("#000", shader=shader, blur=14))
            rays.append((surf.makeImageSnapshot(), rnd.uniform(0.4, 0.9), i))
        _RAY_CACHE[key] = rays
    lin = skia.SamplingOptions(skia.FilterMode.kLinear)
    rays = _RAY_CACHE[key]
    small = _RAY_CACHE.setdefault(("surf", key), skia.Surface(rays[0][0].width(), rays[0][0].height()))
    sc = small.getCanvas()
    sc.clear(skia.ColorTRANSPARENT)
    for img, sp, i in rays:
        paint = skia.Paint(BlendMode=skia.BlendMode.kPlus)
        paint.setAlphaf(0.6 + 0.4 * math.sin(t * sp + i))
        sc.drawImage(img, 0, 0, lin, paint)
    m = c.getTotalMatrix()
    c.save()
    c.resetMatrix()
    k = m.getScaleX()
    skx.blend_upscaled(c, small.makeImageSnapshot(), int(W * k), int(H * k), skia.BlendMode.kScreen)
    c.restore()


def motes(c, t, n=30, seed=4, color="#FFF6C8", W=config.W, H=config.H):
    """Парящие пылинки/пыльца со свечением."""
    rnd = random.Random(seed)
    for _ in range(n):
        x0, y0 = rnd.uniform(0, W), rnd.uniform(0, H)
        sp = rnd.uniform(8, 25)
        ph = rnd.uniform(0, 6.28)
        x = (x0 + t * sp) % W
        y = (y0 - t * sp * 0.6 + math.sin(t * 0.8 + ph) * 18) % H
        r = rnd.uniform(1.5, 4.0)
        a = 0.35 + 0.35 * math.sin(t * 2 + ph)
        c.drawCircle(x, y, r * 3, skx.fill(color, a * 0.25, blur=r * 2))
        c.drawCircle(x, y, r, skx.fill(color, a))

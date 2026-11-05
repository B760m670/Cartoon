"""Постобработка кадра: свечение (bloom), виньетка, цветокоррекция, затемнения."""

import skia

from . import skx


class Post:
    def __init__(self, W, H, spec: dict | None = None):
        spec = spec or {}
        self.W, self.H = W, H
        self.bloom = float(spec.get("bloom", 0.28))
        self.vignette = float(spec.get("vignette", 0.32))
        self.saturation = float(spec.get("saturation", 1.08))
        self.warmth = float(spec.get("warmth", 0.03))
        self.small = skia.Surface(W // 4, H // 4)
        self._vig = skx.fill("#000", shader=skx.radial((W / 2, H / 2), (W * W + H * H) ** 0.5 / 2,
                                                       ["#000000", "#000000", "#0A0614"], [0, 0.62, 1], [0, 0, 1]))
        s = self.saturation
        lr, lg, lb = 0.2126 * (1 - s), 0.7152 * (1 - s), 0.0722 * (1 - s)
        w = self.warmth
        self._grade = skia.ColorFilters.Matrix([
            lr + s + w, lg, lb, 0, 0,
            lr, lg + s, lb, 0, 0,
            lr, lg, lb + s - w, 0, 0,
            0, 0, 0, 1, 0,
        ])

    def begin(self, c: skia.Canvas):
        """Цветокоррекция через слой: всё, что нарисовано до end(), пройдёт через фильтр."""
        c.saveLayer(None, skia.Paint(ColorFilter=self._grade))

    def end(self, c: skia.Canvas):
        c.restore()

    def apply(self, surface: skia.Surface, fade: float = 1.0):
        c = surface.getCanvas()
        lin = skia.SamplingOptions(skia.FilterMode.kLinear)
        # bloom: уменьшенная копия → порог яркости → размытие (всё в 1/4) → «экраном» поверх
        if self.bloom > 0:
            img = surface.makeImageSnapshot()
            sw, sh = self.W // 4, self.H // 4
            sc = self.small.getCanvas()
            thresh = skia.ColorFilters.Matrix([
                1.6, 0, 0, 0, -0.55,
                0, 1.6, 0, 0, -0.55,
                0, 0, 1.6, 0, -0.55,
                0, 0, 0, 1, 0,
            ])
            sc.clear(skia.ColorBLACK)
            sc.drawImageRect(img, skia.Rect(0, 0, sw, sh), lin,
                             skia.Paint(ImageFilter=skia.ImageFilters.Blur(6, 6, skia.TileMode.kClamp, skia.ImageFilters.ColorFilter(thresh))))
            small = self.small.makeImageSnapshot()
            skx.blend_upscaled(c, small, self.W, self.H, skia.BlendMode.kScreen, self.bloom)
        if self.vignette > 0:
            p = skia.Paint(self._vig)
            p.setAlphaf(self.vignette)
            c.drawRect(skia.Rect(0, 0, self.W, self.H), p)
        if fade < 1:
            c.drawRect(skia.Rect(0, 0, self.W, self.H), skx.fill("#000000", 1 - max(0, fade)))

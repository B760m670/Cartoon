"""Фоны сцен. Каждый фон — функция-«рисовальщик», зарегистрированная по типу.

Статичная часть фона рисуется один раз на сцену, а анимированная
(облака, звёзды и т.п.) — поверх неё на каждом кадре.
"""

import math
import random

from PIL import Image

from . import config
from .drawing import Canvas, hex_to_rgb, mix

W, H = config.LOGICAL_WIDTH, config.LOGICAL_HEIGHT


class Background:
    def __init__(self, spec: dict, width: int, height: int):
        self.spec = spec
        self.width, self.height = width, height
        self.static = Canvas(width, height)
        self.draw_static(self.static, spec)

    def draw_static(self, cv: Canvas, spec: dict):
        cv.rect(0, 0, W, H, hex_to_rgb(spec.get("color", "#FFFFFF")))

    def draw_dynamic(self, cv: Canvas, spec: dict, t: float):
        pass

    def frame(self, t: float) -> Canvas:
        cv = Canvas(self.width, self.height)
        cv.img.paste(self.static.img)
        self.draw_dynamic(cv, self.spec, t)
        return cv


def vertical_gradient(cv: Canvas, top, bottom, y0=0, y1=H, steps=120):
    for i in range(steps):
        p = i / (steps - 1)
        cv.rect(0, y0 + (y1 - y0) * i / steps, W, y0 + (y1 - y0) * (i + 1) / steps + 1, mix(top, bottom, p))


def cloud(cv: Canvas, x, y, s, color=(255, 255, 255, 235)):
    for dx, dy, r in ((0, 0, 38), (-40, 10, 28), (40, 10, 30), (-18, -18, 30), (22, -16, 28)):
        cv.ellipse(x + dx * s, y + dy * s, r * s, r * s, fill=color)


class Solid(Background):
    pass


class Meadow(Background):
    """Небо, солнце, холмы, трава, плывущие облака."""

    def draw_static(self, cv, spec):
        sky_top = spec.get("sky_top", "#6EC6FF")
        sky_bottom = spec.get("sky_bottom", "#D8F1FF")
        ground = spec.get("ground", "#78C850")
        horizon = spec.get("horizon", 470)
        vertical_gradient(cv, sky_top, sky_bottom, 0, horizon + 40)
        if spec.get("sun", True):
            sx, sy = spec.get("sun_x", 1080), spec.get("sun_y", 120)
            cv.ellipse(sx, sy, 90, 90, fill=(255, 236, 140, 70))
            cv.ellipse(sx, sy, 62, 62, fill=hex_to_rgb("#FFE066"))
        hill_far = mix(ground, "#4E8F3A", 0.35)
        cv.ellipse(250, horizon + 60, 420, 140, fill=hill_far)
        cv.ellipse(1000, horizon + 70, 480, 150, fill=hill_far)
        cv.rect(0, horizon, W, H, hex_to_rgb(ground))
        rnd = random.Random(spec.get("seed", 7))
        blade = mix(ground, "#2F6E22", 0.4)
        for _ in range(140):
            x = rnd.uniform(0, W)
            y = rnd.uniform(horizon + 20, H)
            cv.line([(x, y), (x + rnd.uniform(-4, 4), y - rnd.uniform(8, 16))], fill=blade, width=2)
        for _ in range(spec.get("flowers", 18)):
            x, y = rnd.uniform(0, W), rnd.uniform(horizon + 30, H - 10)
            petal = rnd.choice(["#FF6B9A", "#FFFFFF", "#FFD23F", "#B388FF"])
            for a in range(5):
                ang = a * 2 * math.pi / 5
                cv.ellipse(x + 6 * math.cos(ang), y + 6 * math.sin(ang), 5, 5, fill=hex_to_rgb(petal))
            cv.ellipse(x, y, 4, 4, fill=hex_to_rgb("#FFB000"))

    def draw_dynamic(self, cv, spec, t):
        speed = spec.get("cloud_speed", 18)
        rnd = random.Random(spec.get("seed", 7) + 1)
        for _ in range(spec.get("clouds", 4)):
            x0, y, s = rnd.uniform(0, W), rnd.uniform(60, 250), rnd.uniform(0.8, 1.5)
            x = (x0 + t * speed * s) % (W + 300) - 150
            cloud(cv, x, y, s)


class Night(Background):
    """Ночное небо с мерцающими звёздами и луной."""

    def draw_static(self, cv, spec):
        horizon = spec.get("horizon", 470)
        vertical_gradient(cv, spec.get("sky_top", "#0B1033"), spec.get("sky_bottom", "#2B3A74"), 0, horizon + 40)
        cv.ellipse(spec.get("moon_x", 1050), spec.get("moon_y", 130), 55, 55, fill=hex_to_rgb("#F4F1C9"))
        cv.ellipse(spec.get("moon_x", 1050) + 22, spec.get("moon_y", 130) - 12, 48, 48, fill=mix("#0B1033", "#2B3A74", 0.2))
        cv.rect(0, horizon, W, H, hex_to_rgb(spec.get("ground", "#1F3B2B")))

    def draw_dynamic(self, cv, spec, t):
        rnd = random.Random(spec.get("seed", 3))
        for _ in range(spec.get("stars", 70)):
            x, y = rnd.uniform(0, W), rnd.uniform(0, spec.get("horizon", 470) - 20)
            phase = rnd.uniform(0, 6.28)
            a = int(140 + 115 * (0.5 + 0.5 * math.sin(t * 3 + phase)))
            r = rnd.uniform(1.2, 2.6)
            cv.ellipse(x, y, r, r, fill=(255, 255, 230, a))


class ImageBg(Background):
    """Готовая картинка из assets/backgrounds (spec: {type: image, file: forest.png})."""

    def draw_static(self, cv, spec):
        path = config.ASSETS_DIR / "backgrounds" / spec["file"]
        img = Image.open(path).convert("RGB").resize(cv.img.size, Image.LANCZOS)
        cv.img.paste(img)


TYPES = {"solid": Solid, "meadow": Meadow, "night": Night, "image": ImageBg}


def create(spec: dict | None, width: int, height: int) -> Background:
    spec = spec or {"type": "solid"}
    kind = spec.get("type", "solid")
    if kind not in TYPES:
        raise ValueError(f"Неизвестный фон '{kind}'. Доступны: {', '.join(TYPES)}")
    return TYPES[kind](spec, width, height)

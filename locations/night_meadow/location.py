"""Тот же луг ночью: луна, мерцающие звёзды, туман у холмов, силуэт яблони."""

import math
import random

import skia

from studio import scenery as sc, skx
from studio.skx import fill

GROUND_Y = 940
MOON = (520, 190)
ANCHORS = {"moon": MOON}


def draw_sky(c, L):
    sc.sky(c, -600, -300, 2520, 1400, "#0B1030", "#24306A", "#5A4E8C")
    mx, my = MOON
    c.drawCircle(mx, my, 420, fill("#000", shader=skx.radial((mx, my), 420, ["#B9C8FF", "#B9C8FF"], [0, 1], [0.28, 0])))
    c.drawCircle(mx, my, 78, fill("#FFF8E1"))
    for dx, dy, r in ((-22, -14, 12), (18, 20, 9), (26, -26, 6)):  # кратеры
        c.drawCircle(mx + dx, my + dy, r, fill("#E8DDB8", 0.8))


def draw_far(c, L):
    sc.ridge(c, -600, 2520, 610, 90, "#3A4C86", 11, haze="#4A5590", waves=2.2)
    c.drawRect(skia.Rect.MakeLTRB(-600, 600, 2520, 760), fill("#8E9BD6", 0.16, blur=40))  # туман


def draw_hills(c, L):
    pts = sc.ridge(c, -600, 2520, 700, 50, "#25456A", 12, haze="#2C4A6E", waves=3)
    sc.treeline(c, pts, "#173253", 13, size=58)
    c.drawRect(skia.Rect.MakeLTRB(-600, 720, 2520, 820), fill("#8EA3E0", 0.14, blur=30))


def draw_ground(c, L):
    sc.meadow_ground(c, -600, 2520, 790, 600, "#2E5C55", L, 14, flowers=40, tufts=420)
    sc.big_tree(c, 1420, 860, 1.0, L, seed=3, leaves="#234E4A", trunk="#4A3A44")


def draw_front(c, L):
    rnd = random.Random(21)
    for x0 in (-500, 1720):
        for _ in range(60):
            x, y = x0 + rnd.uniform(0, 700), rnd.uniform(1010, 1180)
            sc.grass_tuft(c, x, y, rnd.uniform(2.2, 3.4), rnd.choice(["#16312E", "#1C3B37", "#122826"]), rnd)


LAYERS = [
    {"name": "sky", "parallax": 0.0, "draw": draw_sky},
    {"name": "far", "parallax": 0.15, "draw": draw_far, "blur": 2.0},
    {"name": "hills", "parallax": 0.4, "draw": draw_hills, "blur": 1.0},
    {"name": "ground", "parallax": 1.0, "draw": draw_ground},
    {"name": "front", "parallax": 1.35, "draw": draw_front, "blur": 5.0},
]

_STARS = [(random.Random(i).uniform(-500, 2400), random.Random(i * 7 + 1).uniform(-250, 560),
           random.Random(i * 13 + 2).uniform(1.0, 3.2), random.Random(i * 3 + 5).uniform(0, 6.28)) for i in range(160)]


def dynamic(c, layer, t, L):
    if layer == "sky":
        for x, y, r, ph in _STARS:
            if math.hypot(x - MOON[0], y - MOON[1]) < 140:
                continue
            a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.4 + ph))
            c.drawCircle(x, y, r * 2.6, fill("#CFE0FF", a * 0.18, blur=r * 1.5))
            c.drawCircle(x, y, r * 0.6, fill("#FFFFFF", a))
    elif layer == "far":
        # медленно плывущая дымка
        x = (t * 12) % 1200
        c.drawOval(skia.Rect.MakeXYWH(-600 + x, 640, 1400, 110), fill("#A9B6EA", 0.10, blur=40))
        c.drawOval(skia.Rect.MakeXYWH(700 + x * 0.6, 660, 1500, 90), fill("#A9B6EA", 0.08, blur=40))


def screen_effects(c, t, L):
    pass

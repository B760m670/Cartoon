"""Тот же луг в дождь: низкие серые тучи, мокрая трава, лужи. ENV: rain 0..1 — сила дождя, clear 0..1 — небо светлеет."""

import random

import skia

from studio import location, scenery as sc, skx
from studio.skx import fill

GROUND_Y = 940
ANCHORS = {"puddle": (980, 990)}


def draw_sky(c, L):
    sc.sky(c, -600, -300, 2520, 1400, "#5D6B84", "#8D9AB0", "#C3CAD4")


def draw_far(c, L):
    sc.ridge(c, -600, 2520, 610, 90, "#8A9AB2", 11, haze="#A9B4C4", waves=2.2)
    c.drawRect(skia.Rect.MakeLTRB(-600, 560, 2520, 760), fill("#C9D1DC", 0.22, blur=40))


def draw_hills(c, L):
    pts = sc.ridge(c, -600, 2520, 700, 50, "#5E8A5E", 12, haze="#7D9C82", waves=3)
    sc.treeline(c, pts, "#3F6A48", 13, size=58)
    c.drawRect(skia.Rect.MakeLTRB(-600, 700, 2520, 820), fill("#C3CCD8", 0.16, blur=30))


def draw_ground(c, L):
    sc.meadow_ground(c, -600, 2520, 790, 600, "#4F8A47", L, 14, flowers=50, tufts=420)
    sc.big_tree(c, 1420, 860, 1.0, L, seed=3, leaves="#3C7A3A", trunk="#6A4A36")
    for x, y, w in ((300, 1030, 130), (1750, 1000, 110), (-200, 980, 90)):  # дальние лужи
        c.drawOval(skia.Rect.MakeXYWH(x - w, y - w * 0.18, w * 2, w * 0.36), fill("#8FA3BF", 0.8))
        c.drawOval(skia.Rect.MakeXYWH(x - w * 0.5, y - w * 0.1, w * 0.5, w * 0.08), fill("#FFFFFF", 0.35))


def draw_front(c, L):
    rnd = random.Random(21)
    for x0 in (-500, 1720):
        for _ in range(60):
            x, y = x0 + rnd.uniform(0, 700), rnd.uniform(1010, 1180)
            sc.grass_tuft(c, x, y, rnd.uniform(2.2, 3.4), rnd.choice(["#2E5E2A", "#376B31", "#264F22"]), rnd)


LAYERS = [
    {"name": "sky", "parallax": 0.0, "draw": draw_sky},
    {"name": "far", "parallax": 0.15, "draw": draw_far, "blur": 2.0},
    {"name": "hills", "parallax": 0.4, "draw": draw_hills, "blur": 1.0},
    {"name": "ground", "parallax": 1.0, "draw": draw_ground},
    {"name": "front", "parallax": 1.35, "draw": draw_front, "blur": 5.0},
]
ENV = {}


def dynamic(c, layer, t, L):
    if layer == "sky":
        clear = float(ENV.get("clear", 0) or 0)
        if clear > 0:
            c.drawRect(skia.Rect.MakeLTRB(-600, -300, 2520, 1400), fill("#9DD2F6", clear * 0.6))
        for i, (x, y, s, v) in enumerate([(200, 160, 1.6, 7), (900, 90, 1.3, 5), (1500, 230, 1.2, 9), (-300, 260, 1.4, 6), (1200, 380, 1.0, 8)]):
            xx = (x + t * v * (1 + clear * 3) + 700) % 3000 - 700
            sc.cloud(c, xx, y - clear * 160, s, i + 10, L, base=skx.mix("#8E99AD", "#FFFFFF", clear), shadow=skx.mix("#5E6A80", "#B9CCEB", clear))


def screen_effects(c, t, L):
    location.rain(c, t, float(ENV.get("rain", 1.0) or 0))

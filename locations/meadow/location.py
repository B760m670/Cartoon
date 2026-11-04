"""Солнечный луг с большой яблоней. Мир: 1920x1080 (+ запас по краям для панорам).

Слои (от дальнего к ближнему): небо → дальние горы → холмы с лесом → луг с яблоней → трава переднего плана.
"""

import random

from studio import location, scenery as sc
from studio.skx import oval, fill

GROUND_Y = 940
TREE_X, TREE_BASE = 1420, 860
ANCHORS = {
    "apple_high": (1400, 228),   # то самое яблоко — высоко на ветке
    "apple_2": (1560, 380),
    "tree_trunk": (TREE_X, TREE_BASE),
}
SUN = (1600, 150)


def draw_sky(c, L):
    sc.sky(c, -600, -300, 2520, 1400, "#3E8EE0", "#9DD2F6", "#FBEBD0", sun=(*SUN, 64))


def draw_far(c, L):
    sc.ridge(c, -600, 2520, 610, 90, "#A7C3E3", 11, haze="#D9E6F0", waves=2.2)


def draw_hills(c, L):
    pts = sc.ridge(c, -600, 2520, 700, 50, "#86BE6A", 12, haze="#B5D79C", waves=3)
    sc.treeline(c, pts, "#5B9B4E", 13, size=58)


def draw_ground(c, L):
    sc.meadow_ground(c, -600, 2520, 790, 600, "#7CC555", L, 14, flowers=90, tufts=420)
    sc.big_tree(c, TREE_X, TREE_BASE, 1.0, L, seed=3)
    sc.apple(c, *ANCHORS["apple_2"], 24, L)
    sc.apple(c, 1640, 250, 22, L)
    sc.apple(c, 1200, 420, 22, L)


def draw_front(c, L):
    rnd = random.Random(21)
    for x0 in (-500, 1720):
        for _ in range(60):
            x, y = x0 + rnd.uniform(0, 700), rnd.uniform(1010, 1180)
            sc.grass_tuft(c, x, y, rnd.uniform(2.2, 3.4), rnd.choice(["#3F8A33", "#4E9C3B", "#2F7428"]), rnd)
        for _ in range(6):
            sc.flower(c, x0 + rnd.uniform(0, 700), rnd.uniform(1030, 1120), rnd.uniform(14, 20), rnd.choice(["#FFFFFF", "#FFD93D", "#FF8FB1"]), L)


LAYERS = [
    {"name": "sky", "parallax": 0.0, "draw": draw_sky},
    {"name": "far", "parallax": 0.15, "draw": draw_far, "blur": 2.0},
    {"name": "hills", "parallax": 0.4, "draw": draw_hills, "blur": 1.0},
    {"name": "ground", "parallax": 1.0, "draw": draw_ground},
    {"name": "front", "parallax": 1.35, "draw": draw_front, "blur": 5.0},
]


def dynamic(c, layer, t, L):
    if layer == "sky":
        for i, (x, y, s, v) in enumerate([(200, 210, 1.1, 9), (900, 120, 0.8, 6), (1300, 300, 0.65, 11), (-400, 170, 0.9, 8)]):
            xx = (x + t * v + 700) % 3000 - 700
            sc.cloud(c, xx, y, s, i, L)


def screen_effects(c, t, L):
    location.light_rays(c, t, SUN, alpha=0.10)
    location.motes(c, t, n=26)

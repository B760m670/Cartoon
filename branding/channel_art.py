"""Оформление канала Little Story Meadow: аватарка 800x800 и баннер 2560x1440.

    python branding/channel_art.py   → output/branding/avatar.png, banner.png

Баннер: на телефоне и компьютере видна только центральная полоса 1546x423 (y 508–931),
поэтому название и главное — там; по краям просто продолжается луг.
"""

import random
import sys
from pathlib import Path

import skia
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, scenery as sc, skx  # noqa: E402
from studio.skx import Light, fill  # noqa: E402

OUT = config.OUTPUT_DIR / "branding"
L = Light()


def save(surf, name, size=None):
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(skx.surface_to_rgb(surf))
    if size:
        img = img.resize(size, Image.LANCZOS)
    p = OUT / name
    img.save(p, optimize=True)
    print(f"✔ {p} ({p.stat().st_size // 1024} КБ)")


def meadow(c, w, h, sun, tree_x=None, seed=5):
    """Луг в мировых координатах шириной w (высота мира 1080)."""
    sc.sky(c, -50, -50, w + 50, h + 50, "#3E8EE0", "#9DD2F6", "#FBEBD0", sun=sun)
    for i, (x, y, s) in enumerate([(w * 0.12, 170, 0.9), (w * 0.46, 110, 0.7), (w * 0.8, 230, 0.8), (w * 0.62, 300, 0.5)]):
        sc.cloud(c, x, y, s, i + seed, L)
    sc.ridge(c, -50, w + 50, 640, 80, "#A7C3E3", 11, haze="#D9E6F0", waves=2.2)
    pts = sc.ridge(c, -50, w + 50, 740, 50, "#86BE6A", 12, haze="#B5D79C", waves=3)
    sc.treeline(c, pts, "#5B9B4E", 13, size=54)
    sc.meadow_ground(c, -50, w + 50, 840, 400, "#7CC555", L, 14, flowers=int(w / 14), tufts=int(w / 4))
    if tree_x:
        sc.big_tree(c, tree_x, 900, 0.9, L, seed=3)


def banner():
    W, H = 2560, 1440
    k = H / 1080
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.scale(k, k)
    w = W / k
    meadow(c, w, 1080, sun=(w * 0.5, 470, 54), tree_x=w * 0.94)
    # мягкие лучи от солнца за названием
    c.drawCircle(w * 0.5, 470, 520, fill("#000", shader=skx.radial((w * 0.5, 470), 520, ["#FFF3C4", "#FFF3C4"], [0, 1], [0.45, 0])))
    rnd = random.Random(2)
    for _ in range(40):  # пыльца
        x, y = rnd.uniform(0, w), rnd.uniform(380, 900)
        c.drawCircle(x, y, 4, fill("#FFF6C8", 0.7))
        c.drawCircle(x, y, 10, fill("#FFF6C8", 0.2, blur=6))
    c.resetMatrix()
    # название в безопасной зоне (центр 1546x423)
    cy = 508 + 423 / 2
    title = "Little Story Meadow"
    size = 132
    font = skia.Font(skx.typeface(True), size)
    tw = font.measureText(title)
    blob = skia.TextBlob.MakeFromString(title, font)
    x0 = W / 2 - tw / 2
    c.drawTextBlob(blob, x0 + 6, cy + 30, fill("#1B3A5C", 0.35, blur=8))
    c.drawTextBlob(blob, x0, cy + 20, skx.stroke("#2A4A7A", 22))
    c.drawTextBlob(blob, x0, cy + 20, fill("#000", shader=skx.linear((0, cy - 80), (0, cy + 20), ["#FFFFFF", "#FFF2B8"])))
    sub = "gentle little cartoons"
    skx.text(c, sub, W / 2, cy + 110, 56, "#FFFFFF", "#2A4A7A", 10)
    save(surf, "banner.png")


def avatar():
    S = 1600  # рисуем крупно, потом уменьшаем до 800
    surf = skia.Surface(S, S)
    c = surf.getCanvas()
    k = S / 1080
    c.scale(k, k)
    w = 1080
    sc.sky(c, -50, -50, w + 50, 1130, "#3E8EE0", "#9DD2F6", "#FBEBD0", sun=(760, 300, 60))
    sc.cloud(c, 260, 230, 0.8, 4, L)
    sc.ridge(c, -50, w + 50, 700, 70, "#A7C3E3", 11, haze="#D9E6F0", waves=1.6)
    # круглый холм с деревом — простой силуэт, читается даже в 48 пикселях
    hill = skx.blob(540, 1000, 760, 260)
    skx.cel(c, hill, "#7CC555", L, 500, line_w=0, shadow_k=0.25, highlight=False)
    sc.big_tree(c, 540, 880, 0.7, L, seed=7)
    rnd = random.Random(9)
    for _ in range(26):
        x, y = rnd.uniform(140, 940), rnd.uniform(900, 1060)
        sc.flower(c, x, y, rnd.uniform(9, 14), rnd.choice(["#FFFFFF", "#FFD93D", "#FF8FB1", "#B79CFF"]), L)
    save(surf, "avatar.png", (800, 800))


if __name__ == "__main__":
    avatar()
    banner()

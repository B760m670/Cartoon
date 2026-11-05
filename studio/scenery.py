"""Кисти для фонов: небо, облака, холмы, деревья, трава, цветы — в аниме-стиле."""

import math
import random

import skia

from . import skx
from .skx import Light, cel, fill, oval, shade, stroke


def sky(c, x0, y0, x1, y1, top, mid, bottom, sun=None, sun_color="#FFF6D8"):
    c.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1),
               fill("#000", shader=skx.linear((0, y0), (0, y1), [top, mid, bottom], [0, 0.6, 1])))
    if sun:
        sx, sy, r = sun
        c.drawCircle(sx, sy, r * 6, fill("#000", shader=skx.radial((sx, sy), r * 6, [sun_color, sun_color], [0, 1], [0.55, 0])))
        c.drawCircle(sx, sy, r * 2.2, fill("#000", shader=skx.radial((sx, sy), r * 2.2, ["#FFFFFF", sun_color], [0, 1], [0.9, 0])))
        c.drawCircle(sx, sy, r, fill("#FFFDF2"))


def cloud_path(x, y, s, seed):
    rnd = random.Random(seed)
    parts = []
    n = rnd.randint(5, 8)
    for i in range(n):
        px = x + (i - n / 2) * 46 * s + rnd.uniform(-10, 10) * s
        r = rnd.uniform(38, 70) * s * (1 - abs(i - n / 2) / n * 0.9)
        parts.append(oval(px, y - r * 0.4, r, r * 0.9))
    parts.append(skx.blob(x, y + 10 * s, n * 26 * s, 26 * s))
    return skx.union(*parts)


def cloud(c, x, y, s, seed, light: Light, base="#FFFFFF", shadow="#B9CCEB"):
    p = cloud_path(x, y, s, seed)
    c.drawPath(p, fill(shadow))
    c.save()
    c.clipPath(p, doAntiAlias=True)
    c.drawPath(skx.moved(p, light.dx * 26 * s, light.dy * 26 * s), fill(base))
    c.drawPath(skx.moved(p, light.dx * 70 * s, light.dy * 70 * s), fill("#FFFFFF", 0.0))
    c.restore()
    c.drawPath(p, fill("#FFFFFF", 0.18, blur=6 * s))


def ridge(c, x0, x1, base_y, amp, color, seed, bottom=None, haze=None, waves=3, bumps=0.0):
    rnd = random.Random(seed)
    phases = [rnd.uniform(0, 6.28) for _ in range(4)]
    pts = []
    steps = 48
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i / steps
        u = i / steps
        y = base_y - amp * (0.55 * math.sin(u * waves * math.pi + phases[0]) + 0.3 * math.sin(u * waves * 2.3 * math.pi + phases[1])
                            + bumps * math.sin(u * 37 + phases[2]))
        pts.append((x, y))
    p = skx.smooth_open(pts)
    p.lineTo(x1, (bottom or base_y + 2000))
    p.lineTo(x0, (bottom or base_y + 2000))
    p.close()
    top_col = color
    bot_col = haze or shade(color, -0.25)
    c.drawPath(p, fill("#000", shader=skx.linear((0, base_y - amp), (0, base_y + 260), [shade(top_col, 0.08), bot_col])))
    c.drawPath(skx.smooth_open(pts), stroke(shade(color, 0.3), 3, 0.5))
    return pts


def treeline(c, pts, color, seed, size=60, density=1.0):
    """Ряд круглых крон вдоль линии холма (силуэтом, с подсветкой сверху)."""
    rnd = random.Random(seed)
    crowns = []
    for i, (x, y) in enumerate(pts):
        if rnd.random() > 0.55 * density:
            continue
        r = rnd.uniform(0.6, 1.2) * size
        crowns.append(oval(x + rnd.uniform(-20, 20), y - r * 0.5, r, r * 1.05))
    if not crowns:
        return
    p = skx.union(*crowns)
    cel(c, p, color, Light(), size * 1.4, line_w=2.0, shadow_k=0.35, highlight=False)


def leaf_cluster(c, x, y, r, base, light, seed):
    rnd = random.Random(seed)
    parts = [oval(x, y, r, r * 0.92)]
    for _ in range(7):
        a = rnd.uniform(0, 6.28)
        parts.append(oval(x + math.cos(a) * r * 0.72, y + math.sin(a) * r * 0.62, r * rnd.uniform(0.38, 0.55), r * rnd.uniform(0.35, 0.5)))
    p = skx.union(*parts)
    cel(c, p, base, light, r * 1.6, line_w=3, shadow_k=0.5)
    return p


def big_tree(c, x, y, s, light, seed=3, leaves="#4FA83D", trunk="#8A5A36"):
    """Большое дерево у которого основание ствола в (x, y)."""
    rnd = random.Random(seed)
    # ствол с ветвями
    tw = 58 * s
    trunk_p = skx.smooth_closed([(x - tw, y), (x - tw * 0.7, y - 160 * s), (x - tw * 0.55, y - 330 * s), (x - tw * 1.6, y - 470 * s),
                                 (x - tw * 0.2, y - 400 * s), (x + tw * 0.1, y - 520 * s), (x + tw * 0.5, y - 400 * s),
                                 (x + tw * 1.7, y - 455 * s), (x + tw * 0.6, y - 310 * s), (x + tw * 0.75, y - 150 * s),
                                 (x + tw * 1.25, y)], tension=0.9)
    roots = skx.smooth_closed([(x - tw * 2.2, y + 6), (x - tw * 0.8, y - 40 * s), (x + tw * 0.9, y - 40 * s), (x + tw * 2.4, y + 6)])
    cel(c, skx.union(trunk_p, roots), trunk, light, 140 * s)
    c.save()
    c.clipPath(trunk_p, doAntiAlias=True)
    for i in range(9):
        yy = y - rnd.uniform(20, 380) * s
        xx = x + rnd.uniform(-tw * 0.6, tw * 0.6)
        c.drawPath(skx.smooth_open([(xx, yy), (xx + 4 * s, yy - 30 * s), (xx - 2 * s, yy - 60 * s)]), stroke(shade(trunk, -0.6), 3 * s, 0.6))
    c.restore()
    # крона из кластеров: тёмные сзади, светлые спереди
    cy = y - 560 * s
    clusters = []
    for i in range(16):
        a = rnd.uniform(0, 6.28)
        d = rnd.uniform(0, 1) ** 0.6
        clusters.append((x + math.cos(a) * 290 * s * d, cy + math.sin(a) * 170 * s * d - 20 * s, rnd.uniform(85, 125) * s))
    clusters.sort(key=lambda q: q[1])
    for i, (px, py, r) in enumerate(clusters):
        k = i / len(clusters)
        leaf_cluster(c, px, py, r, skx.mix(shade(leaves, -0.25), leaves, 0.4 + 0.6 * k), light, seed * 100 + i)
    # искорки-листья
    for _ in range(40):
        a = rnd.uniform(0, 6.28)
        d = rnd.uniform(0.2, 1.0)
        px, py = x + math.cos(a) * 320 * s * d, cy + math.sin(a) * 190 * s * d
        c.drawOval(skia.Rect.MakeXYWH(px, py, 12 * s, 7 * s), fill(shade(leaves, 0.45), 0.8))
    return {"crown": (x, cy, 330 * s, 210 * s)}


def apple(c, x, y, r, light, color="#E5383B"):
    body = skx.union(oval(x - r * 0.42, y, r * 0.72, r * 0.9), oval(x + r * 0.42, y, r * 0.72, r * 0.9))
    cel(c, body, color, light, r * 2.2)
    c.drawOval(skia.Rect.MakeXYWH(x - r * 0.55, y - r * 0.6, r * 0.32, r * 0.45), fill("#FFFFFF", 0.85))
    c.drawPath(skx.smooth_open([(x, y - r * 0.7), (x + r * 0.08, y - r * 1.15), (x + r * 0.2, y - r * 1.35)]), stroke("#5A3A22", r * 0.13))
    leaf = skx.smooth_closed([(x + r * 0.1, y - r * 1.1), (x + r * 0.55, y - r * 1.45), (x + r * 0.95, y - r * 1.25), (x + r * 0.5, y - r * 0.98)])
    cel(c, leaf, "#5DB447", light, r, line_w=2)


def meadow_ground(c, x0, x1, y, depth, color, light, seed, flowers=60, tufts=260):
    rnd = random.Random(seed)
    p = skx.smooth_open([(x0, y + 10), ((x0 + x1) * 0.3, y - 14), ((x0 + x1) * 0.7, y + 6), (x1, y - 8)])
    p.lineTo(x1, y + depth)
    p.lineTo(x0, y + depth)
    p.close()
    c.drawPath(p, fill("#000", shader=skx.linear((0, y - 20), (0, y + depth), [shade(color, 0.12), color, shade(color, -0.2)], [0, 0.35, 1])))
    # пятна света/тени на траве
    for _ in range(14):
        px, py = rnd.uniform(x0, x1), rnd.uniform(y + 40, y + depth)
        w = rnd.uniform(120, 360)
        c.drawOval(skia.Rect.MakeXYWH(px - w, py - w * 0.12, w * 2, w * 0.24), fill(shade(color, rnd.choice([-0.18, 0.15])), 0.35, blur=18))
    for _ in range(tufts):
        px, py = rnd.uniform(x0, x1), rnd.uniform(y + 10, y + depth)
        k = (py - y) / depth
        grass_tuft(c, px, py, 0.5 + k * 0.9, shade(color, rnd.uniform(-0.35, -0.1)), rnd)
    for _ in range(flowers):
        px, py = rnd.uniform(x0, x1), rnd.uniform(y + 20, y + depth)
        k = 0.5 + (py - y) / depth
        flower(c, px, py, 7 * k, rnd.choice(["#FFFFFF", "#FFD93D", "#FF8FB1", "#B79CFF"]), light)


def grass_tuft(c, x, y, s, color, rnd, sway=0.0):
    for i in range(5):
        a = (i - 2) * 0.28 + rnd.uniform(-0.1, 0.1) + sway
        h = rnd.uniform(14, 28) * s
        tip = (x + math.sin(a) * h, y - math.cos(a) * h)
        blade = skx.smooth_closed([(x - 2.5 * s, y), ((x + tip[0]) / 2 - 1 * s, (y + tip[1]) / 2), tip,
                                   ((x + tip[0]) / 2 + 2 * s, (y + tip[1]) / 2), (x + 2.5 * s, y)], tension=0.6)
        c.drawPath(blade, fill(color))


def flower(c, x, y, r, color, light):
    for k in range(5):
        a = k * 2 * math.pi / 5
        c.drawOval(skia.Rect.MakeXYWH(x + math.cos(a) * r - r * 0.7, y + math.sin(a) * r * 0.7 - r * 0.55, r * 1.4, r * 1.1), fill(color))
    c.drawCircle(x, y, r * 0.55, fill("#FFB000"))
    c.drawCircle(x - r * 0.15, y - r * 0.15, r * 0.2, fill("#FFFFFF", 0.7))

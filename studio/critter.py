"""Риг персонажа-зверька в аниме-стиле.

Один риг на всех: вид (медведь, заяц, лиса…) задаётся параметрами из
characters/<id>/character.yaml — форма ушей, мордочки, хвоста, палитра.

Объём головы: черты лица лежат на «сфере» и проецируются с учётом
поворота головы (turn) — так голова поворачивается как в 3D.
"""

import math
from dataclasses import dataclass, field

import skia

from . import skx
from .skx import cel, fill, oval, shade, stroke


@dataclass
class Pose:
    x: float = 960
    y: float = 900                  # земля под ногами
    lift: float = 0.0               # подъём над землёй (прыжок)
    scale: float = 1.0
    facing: int = 1                 # 1 — вправо, -1 — влево (зеркалим)
    turn: float = 0.25              # поворот головы −1..1 (0 — анфас)
    tilt: float = 0.0               # наклон головы, градусы
    lean: float = 0.0               # наклон корпуса, градусы
    squash: float = 0.0             # >0 сплющен, <0 вытянут
    look_x: float = 0.0             # взгляд −1..1
    look_y: float = 0.0
    blink: float = 0.0              # 0 — открыты, 1 — закрыты
    mood: str = "happy"             # happy | neutral | sad | surprised | angry | excited
    mouth: float = 0.0              # открытие рта 0..1 (липсинк)
    arm_l: tuple = (20.0, 10.0)     # (плечо, локоть) градусы; 0 — вниз
    arm_r: tuple = (20.0, 10.0)
    leg_l: tuple = (0.0, 0.0)       # (бедро, колено)
    leg_r: tuple = (0.0, 0.0)
    ear_l: float = 0.0              # отклонение ушей (пружины), градусы
    ear_r: float = 0.0
    tail: float = 0.0
    breath: float = 0.0             # дыхание −1..1
    blush: float = 0.0              # румянец 0..1 сверх обычного
    stretch: float = 0.0            # мультяшное вытягивание рук 0..1 (тянется за чем-то)


@dataclass
class Look:
    """Внешность из YAML."""

    name: str = "?"
    fur: str = "#C8814A"
    fur2: str = "#F2D2A9"          # животик, мордочка, внутренность ушей
    inner_ear: str | None = None
    eye: str = "#5A3A22"            # радужка
    eye2: str = "#C98A45"           # низ радужки (градиент)
    nose: str = "#3B2416"
    cheek: str = "#FF8FA0"
    ears: str = "round"             # round | long | pointy
    snout: str = "bear"             # bear | bunny | fox
    tail: str = "stub"              # stub | puff | fluffy
    head_r: float = 112
    body_w: float = 92
    body_h: float = 98
    accessory: dict = field(default_factory=dict)  # {type: scarf|bow, color: ...}
    voice: dict = field(default_factory=dict)

    @classmethod
    def from_spec(cls, spec: dict):
        known = {k: v for k, v in spec.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def _rot(px, py, deg):
    a = math.radians(deg)
    return px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)


class Critter:
    def __init__(self, cid: str, spec: dict, light: skx.Light):
        self.id = cid
        self.look = Look.from_spec(spec)
        self.light = light

    # точки для облачков/камеры
    def head_center(self, pose: Pose):
        lk = self.look
        hy = -(lk.body_h * 2 + 60 + lk.head_r * 0.82) * (1 - pose.squash * 0.3)
        return pose.x, pose.y - pose.lift + hy * pose.scale

    def draw(self, c: skia.Canvas, pose: Pose):
        lk, L = self.look, self.light
        s = pose.scale
        c.save()
        # контактная тень на земле
        sh = 1 / (1 + pose.lift / 160)
        c.drawOval(skia.Rect.MakeXYWH(pose.x - 115 * s * sh, pose.y - 16 * s * sh, 230 * s * sh, 32 * s * sh),
                   fill("#1B2A3A", 0.33 * sh, blur=10 * s))
        c.translate(pose.x, pose.y - pose.lift)
        c.scale(s * pose.facing, s)
        # дальше всё в локальных координатах; +x — «вперёд» персонажа
        sq = pose.squash
        c.scale(1 + sq * 0.25, 1 - sq * 0.3)

        hip_y = -62
        body_cy = -(lk.body_h + 26)
        neck_y = body_cy - lk.body_h * 0.92
        b = 1 + pose.breath * 0.012

        # ---- дальние конечности (за телом) ----
        self._leg(c, -30, hip_y, pose.leg_l, far=True)
        self._leg(c, 32, hip_y, pose.leg_r)
        self._arm(c, -lk.body_w * 0.78, neck_y + 40, pose.arm_l, far=True, stretch=pose.stretch)
        self._tail(c, body_cy, pose)

        # ---- тело ----
        c.save()
        c.translate(0, hip_y + 20)
        c.rotate(pose.lean)
        c.translate(0, -(hip_y + 20))
        body = skx.blob(4, body_cy, lk.body_w * b, lk.body_h * b, top=0.78, bottom=1.08, waist=0.97)
        cel(c, body, lk.fur, L, lk.body_w * 2)
        c.save()
        c.clipPath(body, doAntiAlias=True)
        belly = skx.blob(14, body_cy + lk.body_h * 0.22, lk.body_w * 0.62, lk.body_h * 0.62, top=0.8, bottom=1.0)
        cel(c, belly, lk.fur2, L, lk.body_w, outline=False, shadow_k=0.25)
        c.restore()
        if lk.accessory.get("type") == "scarf":
            self._scarf(c, neck_y + 8, lk.accessory.get("color", "#2F6FE0"), pose)

        # ---- голова ----
        c.save()
        c.translate(6, neck_y)
        c.rotate(pose.tilt)
        self._head(c, pose)
        c.restore()
        self._arm(c, lk.body_w * 0.72, neck_y + 40, pose.arm_r, stretch=pose.stretch)
        c.restore()
        c.restore()

    # ------------------------------------------------------------------
    def _limb(self, c, x, y, angles, length, r0, r1, color, far=False, paw=None):
        a1, a2 = angles
        ex, ey = _rot(0, length, -a1)
        ex, ey = x + ex, y + ey
        hx, hy = _rot(0, length * 0.95, -(a1 + a2))  # предплечье
        hx, hy = ex + hx, ey + hy
        col = shade(color, -0.18) if far else color
        p = skx.union(skx.capsule(x, y, ex, ey, r0, (r0 + r1) / 2), skx.capsule(ex, ey, hx, hy, (r0 + r1) / 2, r1))
        cel(c, p, col, self.light, r0 * 2.4)
        return hx, hy

    def _arm(self, c, x, y, ang, far=False, stretch=0.0):
        lk = self.look
        hx, hy = self._limb(c, x, y, ang, 46 * (1 + 0.9 * stretch), 21, 18, lk.fur, far)
        paw = oval(hx, hy, 22, 21)
        cel(c, paw, shade(lk.fur, -0.18) if far else lk.fur, self.light, 40)
        if not far:
            c.drawPath(oval(hx + 3, hy + 5, 10, 8), fill(lk.fur2, 0.9))

    def _leg(self, c, x, y, ang, far=False):
        lk = self.look
        hx, hy = self._limb(c, x, y, ang, 26, 28, 25, lk.fur, far)
        foot = skx.blob(hx + 10, hy + 4, 40, 24, top=0.9, bottom=1.05)
        col = shade(lk.fur, -0.18) if far else lk.fur
        cel(c, foot, col, self.light, 50)
        if not far:
            c.drawPath(oval(hx + 28, hy + 6, 11, 14), fill(lk.fur2))

    def _tail(self, c, body_cy, pose):
        lk = self.look
        c.save()
        c.translate(-lk.body_w * 0.92, body_cy + lk.body_h * 0.45)
        c.rotate(-pose.tail)
        if lk.tail == "puff":
            for dx, dy, r in ((0, 0, 30), (-14, -10, 22), (-10, 14, 20), (8, -16, 18)):
                cel(c, oval(dx, dy, r, r), lk.fur2, self.light, 60, outline=False)
            c.drawPath(skx.union(oval(0, 0, 30, 30), oval(-14, -10, 22, 22), oval(-10, 14, 20, 20), oval(8, -16, 18, 18)),
                       stroke(shade(lk.fur2, -0.8), 3))
        elif lk.tail == "fluffy":
            p = skx.smooth_closed([(0, -16), (-60, -60), (-110, -40), (-125, 10), (-70, 30), (0, 16)])
            cel(c, p, lk.fur, self.light, 120)
            tip = skx.smooth_closed([(-95, -48), (-125, -30), (-128, 12), (-98, 22), (-88, -10)])
            cel(c, tip, lk.fur2, self.light, 50)
        else:
            cel(c, oval(0, 0, 20, 18), lk.fur, self.light, 40)
        c.restore()

    def _scarf(self, c, y, color, pose):
        lk = self.look
        w = lk.body_w * 0.92
        band = skx.smooth_closed([(-w, y - 6), (0, y - 20), (w + 8, y - 6), (w + 4, y + 18), (0, y + 26), (-w + 4, y + 18)])
        cel(c, band, color, self.light, 80)
        tail = skx.smooth_closed([(w * 0.35, y + 10), (w * 0.62, y + 70 + pose.ear_r * 0.4), (w * 0.3, y + 78), (w * 0.12, y + 16)])
        cel(c, tail, shade(color, -0.1), self.light, 50)
        for i in range(3):
            c.drawLine(w * 0.3 + i * 8, y + 72, w * 0.33 + i * 8, y + 82, stroke(shade(color, -0.6), 3))

    # ------------------------------------------------------------------
    def _proj(self, lon, lat, turn, R, ry=None):
        """Точка на сфере головы → экран. Возвращает (x, y, видимость/сжатие)."""
        ry = ry or R
        a = lon + turn * 0.75
        x = R * math.sin(a) * math.cos(lat)
        y = -ry * math.sin(lat)
        return x, y, math.cos(a)

    def _head(self, c, pose: Pose):
        lk, L = self.look, self.light
        R = lk.head_r
        hcy = -R * 0.82
        turn = pose.turn
        c.save()
        c.translate(0, hcy)
        rx, ry = R * (1 - abs(turn) * 0.04), R * 0.9

        # уши — за головой
        self._ears(c, pose, R, ry)

        head = skx.blob(0, 0, rx, ry, top=0.96, bottom=1.04, waist=1.0)
        if lk.snout == "fox":
            # щёчки-пушок по бокам
            fluff = skx.smooth_closed([(-rx * 0.98, ry * 0.05), (-rx * 1.18, ry * 0.45), (-rx * 0.7, ry * 0.75),
                                       (rx * 0.7, ry * 0.75), (rx * 1.18, ry * 0.45), (rx * 0.98, ry * 0.05)])
            head = skx.union(head, fluff)
        # хохолок на макушке — сливается с контуром головы
        tx, ty, _ = self._proj(0.12, 0.93, turn, rx, ry)
        tuft = skx.smooth_closed([(tx - 30, ty + 18), (tx - 14, ty - 14), (tx - 2, ty - 30), (tx + 4, ty - 8),
                                  (tx + 20, ty - 22), (tx + 34, ty - 26), (tx + 24, ty - 2), (tx + 30, ty + 18)], tension=0.8)
        head = skx.union(head, tuft)
        cel(c, head, lk.fur, L, R * 2)
        c.save()
        c.clipPath(head, doAntiAlias=True)
        # мордочка (светлое пятно), сдвигается при повороте
        sx, sy, vis = self._proj(0, -0.38, turn, rx * 0.98, ry)
        mw = R * (0.5 if lk.snout != "bunny" else 0.42) * (0.75 + 0.25 * vis)
        muzzle = skx.blob(sx, sy + 6, mw, R * 0.36, top=0.85, bottom=1.1)
        cel(c, muzzle, lk.fur2, L, R * 0.8, outline=False, shadow_k=0.2)
        if lk.snout == "fox":
            for side in (-1, 1):
                px, py, v = self._proj(side * 0.85, -0.25, turn, rx, ry)
                c.drawPath(skx.blob(px, py + 10, R * 0.32 * max(v, 0.2), R * 0.36), fill(lk.fur2))
        # румянец
        for side in (-1, 1):
            px, py, v = self._proj(side * 0.62, -0.18, turn, rx, ry)
            if v > 0.05:
                a = 0.45 + 0.4 * pose.blush
                c.drawOval(skia.Rect.MakeXYWH(px - R * 0.17 * v, py - R * 0.07, R * 0.34 * v, R * 0.14),
                           fill(lk.cheek, a, blur=R * 0.04))
                for k in range(3):
                    hx = px - R * 0.08 * v + k * R * 0.07 * v
                    c.drawLine(hx, py - R * 0.035, hx - R * 0.03, py + R * 0.035, stroke(shade(lk.cheek, -0.3), 2.2, a))
        c.restore()

        # глаза, брови
        for side in (-1, 1):
            self._eye(c, pose, side, rx, ry, R)
        # нос и рот
        nx, ny, nv = self._proj(0, -0.22, turn, rx * 1.02, ry)
        if lk.snout == "bunny":
            nose = skx.smooth_closed([(nx - 11, ny - 4), (nx + 11, ny - 4), (nx, ny + 8)])
        else:
            nose = skx.blob(nx, ny, R * 0.13 * (0.7 + 0.3 * nv), R * 0.085, top=1.15, bottom=0.75)
        c.drawPath(nose, fill(lk.nose))
        c.drawOval(skia.Rect.MakeXYWH(nx - R * 0.07, ny - R * 0.06, R * 0.06, R * 0.035), fill("#FFFFFF", 0.85))
        self._mouth(c, pose, nx, ny + R * 0.1, R)
        c.restore()

    def _ears(self, c, pose, R, ry):
        lk, L = self.look, self.light
        inner = lk.inner_ear or lk.fur2
        for side in (-1, 1):
            spring = pose.ear_l if side < 0 else pose.ear_r
            px, py, v = self._proj(side * 0.62, 0.72, pose.turn, R, ry)
            c.save()
            c.translate(px, py)
            c.rotate(side * 8 + spring)
            if lk.ears == "long":
                w = 30 * (0.6 + 0.4 * max(v, 0.3))
                ear = skx.smooth_closed([(-w, 10), (-w * 1.05, -80), (-w * 0.4, -168), (w * 0.4, -168), (w * 1.05, -80), (w, 10)])
                cel(c, ear, lk.fur, L, 120)
                inn = skx.smooth_closed([(-w * 0.45, 0), (-w * 0.55, -80), (0, -150), (w * 0.55, -80), (w * 0.45, 0)])
                c.drawPath(inn, fill(inner))
                c.drawPath(inn, fill(shade(inner, -0.25), 0.5, blur=3))
            elif lk.ears == "pointy":
                w = 46 * (0.6 + 0.4 * max(v, 0.3))
                ear = skx.smooth_closed([(-w, 12), (-w * 0.5, -40), (0, -92), (w * 0.5, -40), (w, 12)], tension=0.6)
                cel(c, ear, lk.fur, L, 90)
                c.drawPath(skx.smooth_closed([(-w * 0.5, 4), (0, -64), (w * 0.5, 4)], tension=0.6), fill(inner))
                c.drawPath(skx.smooth_closed([(-w * 0.32, -40), (0, -92), (w * 0.32, -40)], tension=0.6), fill(shade(lk.fur, -0.6)))
            else:
                r = 38 * (0.7 + 0.3 * max(v, 0.3))
                cel(c, oval(0, -8, r, 38), lk.fur, L, 76)
                c.drawPath(oval(0, -4, r * 0.55, 21), fill(inner))
            c.restore()
        if lk.accessory.get("type") == "bow":
            px, py, _ = self._proj(0.62, 0.62, pose.turn, R, ry)
            self._bow(c, px + 6, py + 6, lk.accessory.get("color", "#FF5C8A"))

    def _bow(self, c, x, y, color):
        L = self.light
        for side in (-1, 1):
            p = skx.smooth_closed([(x, y), (x + side * 44, y - 28), (x + side * 50, y + 6), (x + side * 40, y + 30)], tension=0.8)
            cel(c, p, color, L, 60)
        cel(c, oval(x, y, 13, 12), shade(color, -0.1), L, 26)

    def _eye(self, c, pose, side, rx, ry, R):
        lk = self.look
        ex, ey, v = self._proj(side * 0.36, 0.02, pose.turn, rx, ry)
        if v < 0.08:
            return
        w = R * 0.2 * (0.55 + 0.45 * v)
        h = R * 0.26
        if pose.mood == "surprised":
            h *= 1.1
        if pose.mood == "excited" and pose.blink < 0.5:
            # счастливые глаза-дуги ^^
            arc = skx.smooth_open([(ex - w, ey + h * 0.15), (ex, ey - h * 0.5), (ex + w, ey + h * 0.15)])
            c.drawPath(arc, stroke(shade(lk.fur, -0.9), R * 0.055))
            self._brow(c, pose, ex, ey, w, h, R, side)
            return
        if pose.blink >= 0.85:
            # закрытые глаза: мягкая дуга вниз с ресничкой
            arc = skx.smooth_open([(ex - w * 1.05, ey + h * 0.05), (ex, ey + h * 0.42), (ex + w * 1.05, ey + h * 0.05)])
            c.drawPath(arc, stroke("#24151A", R * 0.045))
            c.drawPath(skx.smooth_open([(ex + side * w * 0.95, ey + h * 0.12), (ex + side * w * 1.35, ey - h * 0.02)]), stroke("#24151A", R * 0.03))
            self._brow(c, pose, ex, ey, w, h, R, side)
            return
        eye = oval(ex, ey, w, h)
        c.drawPath(eye, fill("#FFFFFF"))
        c.save()
        c.clipPath(eye, doAntiAlias=True)
        # радужка с градиентом и зрачком
        ix = ex + pose.look_x * w * 0.35 + (pose.turn * w * 0.25)
        iy = ey + pose.look_y * h * 0.25 + h * 0.08
        iw, ih = w * 0.82, h * 0.8
        c.drawOval(skia.Rect.MakeXYWH(ix - iw, iy - ih, iw * 2, ih * 2),
                   fill("#000", shader=skx.linear((0, iy - ih), (0, iy + ih), [shade(lk.eye, -0.5), lk.eye, lk.eye2], [0, 0.5, 1])))
        c.drawOval(skia.Rect.MakeXYWH(ix - iw * 0.48, iy - ih * 0.5, iw * 0.96, ih), fill("#140C10", 0.92))
        # тень от века
        c.drawOval(skia.Rect.MakeXYWH(ex - w * 1.3, ey - h * 1.45, w * 2.6, h * 0.95), fill(shade(lk.eye, -0.7), 0.35, blur=3))
        # блики
        c.drawOval(skia.Rect.MakeXYWH(ix - iw * 0.62, iy - ih * 0.72, iw * 0.62, ih * 0.52), fill("#FFFFFF"))
        c.drawOval(skia.Rect.MakeXYWH(ix + iw * 0.25, iy + ih * 0.3, iw * 0.3, ih * 0.24), fill("#FFFFFF", 0.9))
        # моргание: веко сверху
        if pose.blink > 0.02:
            lid_h = h * 2.1 * pose.blink
            c.drawRect(skia.Rect.MakeLTRB(ex - w * 1.5, ey - h * 1.2, ex + w * 1.5, ey - h + lid_h), fill(lk.fur))
        if pose.mood == "sad":
            c.drawPath(skx.smooth_closed([(ex - w * 1.4, ey - h * 1.2), (ex + w * 1.4, ey - h * 1.2), (ex + side * w * 1.2, ey - h * 0.25)]),
                       fill(lk.fur))
        c.restore()
        # ресницы / контур века
        top = skx.smooth_open([(ex - w * 1.05, ey - h * 0.15 + (h * 1.9 * pose.blink if pose.blink > 0.02 else 0)),
                               (ex - w * 0.3, ey - h * 1.03 + h * 1.95 * pose.blink),
                               (ex + w * 0.55, ey - h * 0.98 + h * 1.9 * pose.blink),
                               (ex + w * 1.08, ey - h * 0.35 + h * 1.5 * pose.blink)])
        c.drawPath(top, stroke("#24151A", R * 0.045))
        c.drawPath(eye, stroke("#24151A", R * 0.016, 0.6))
        self._brow(c, pose, ex, ey, w, h, R, side)

    def _brow(self, c, pose, ex, ey, w, h, R, side):
        mood = pose.mood
        y = ey - h * 1.38
        inner, outer = 0.0, 0.0
        if mood == "sad":
            inner, outer = -12, 6
        elif mood == "angry":
            inner, outer = 10, -8
        elif mood == "surprised":
            inner = outer = -12
        elif mood in ("happy", "excited"):
            inner = outer = -4
        # side: −1 — левый (на экране), внутренняя сторона ближе к центру
        x_in, x_out = ex - side * w * 0.7, ex + side * w * 0.9
        path = skx.smooth_open([(x_in, y + inner), (ex, y - 6 + (inner + outer) / 2), (x_out, y + outer)])
        c.drawPath(path, stroke(shade(self.look.fur, -0.75), R * 0.04))

    def _mouth(self, c, pose, mx, my, R):
        lk = self.look
        ink = "#3A1F24"
        o = pose.mouth
        if lk.snout != "bunny":
            c.drawLine(mx, my - R * 0.09, mx, my - R * 0.02, stroke(ink, R * 0.025))
        if o > 0.06 or pose.mood in ("surprised", "excited"):
            o = max(o, 0.45 if pose.mood in ("surprised", "excited") else 0)
            w = R * (0.13 + 0.05 * o) * (1.15 if pose.mood == "excited" else 1)
            h = R * (0.05 + 0.19 * o)
            if pose.mood == "surprised" and pose.mouth < 0.1:
                w = h * 0.8
            m = skx.smooth_closed([(mx - w, my), (mx, my - h * 0.25), (mx + w, my), (mx + w * 0.6, my + h), (mx, my + h * 1.2),
                                   (mx - w * 0.6, my + h)])
            c.drawPath(m, fill("#7A1E2C"))
            c.save()
            c.clipPath(m, doAntiAlias=True)
            c.drawOval(skia.Rect.MakeXYWH(mx - w * 0.6, my + h * 0.45, w * 1.2, h * 1.0), fill("#F07A8A"))
            if lk.snout == "bunny":
                c.drawRect(skia.Rect.MakeXYWH(mx - w * 0.3, my - h, w * 0.6, h * 0.8), fill("#FFFFFF"))
            c.restore()
            c.drawPath(m, stroke(ink, R * 0.022))
        else:
            if pose.mood == "sad":
                curve = [(mx - R * 0.12, my + R * 0.05), (mx, my - R * 0.01), (mx + R * 0.12, my + R * 0.05)]
            elif pose.mood in ("neutral", "angry"):
                curve = [(mx - R * 0.1, my + R * 0.02), (mx, my + R * 0.02), (mx + R * 0.1, my + R * 0.02)]
            else:
                curve = [(mx - R * 0.15, my - R * 0.01), (mx - R * 0.07, my + R * 0.05), (mx, my + R * 0.01),
                         (mx + R * 0.07, my + R * 0.05), (mx + R * 0.15, my - R * 0.01)]
            c.drawPath(skx.smooth_open(curve), stroke(ink, R * 0.026))

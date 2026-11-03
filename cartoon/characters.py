"""Отрисовка персонажей. Внешность описывается в characters/<id>/character.yaml."""

import math
import zlib
from dataclasses import dataclass

from .drawing import Canvas, hex_to_rgb, mix

MOODS = ("happy", "neutral", "sad", "surprised", "angry")


@dataclass
class Pose:
    """Состояние персонажа на конкретном кадре (вычисляет scene.py)."""

    x: float
    y: float                 # точка опоры (земля под ногами)
    lift: float = 0.0        # высота над землёй (прыжок, подскок при ходьбе)
    scale: float = 1.0
    facing: int = 1          # 1 — вправо, -1 — влево
    squash: float = 0.0      # >0 — сплющен, <0 — вытянут
    mood: str = "happy"
    mouth_open: float = 0.0  # 0..1, во время речи
    blink: bool = False
    walk_phase: float = 0.0
    walk: float = 0.0        # 0..1 — насколько активно шагает
    wave: float = 0.0        # 0..1 — машет рукой


class Character:
    def __init__(self, cid: str, spec: dict):
        self.id = cid
        self.spec = spec
        self.name = spec.get("name", cid)
        self.shape = spec.get("shape", "circle")
        self.size = float(spec.get("size", 70))
        self.color = hex_to_rgb(spec.get("color", "#FF8A3D"))
        self.outline = hex_to_rgb(spec.get("outline", "#3A2A20"))
        self.belly = spec.get("belly")
        self.cheeks = spec.get("cheeks", "#FF7A9A")
        self.limbs = hex_to_rgb(spec.get("limbs", spec.get("outline", "#3A2A20")))
        self.eye_size = float(spec.get("eye_size", 0.26))
        self.hat = spec.get("hat")
        self.voice_pitch = float(spec.get("voice_pitch", 440))
        self._blink_offset = (zlib.crc32(cid.encode()) % 1000) / 1000 * 3.0

    def is_blinking(self, t: float) -> bool:
        period = 3.2
        return ((t + self._blink_offset) % period) < 0.12

    def draw(self, cv: Canvas, pose: Pose):
        s = pose.scale
        r = self.size * s
        sx = 1 + pose.squash * 0.35
        sy = 1 - pose.squash * 0.35
        rx, ry = r * sx, r * sy
        x, floor = pose.x, pose.y
        ground = floor - pose.lift
        feet_h = 14 * s
        cy = ground - feet_h - ry
        f = pose.facing
        ow = 4 * s

        # тень
        shrink = 1 / (1 + pose.lift / 120)
        cv.ellipse(x, floor + 4 * s, rx * 0.9 * shrink, 10 * s * shrink, fill=(0, 0, 0, int(55 * shrink)))

        # ноги — шагают при ходьбе
        for side in (-1, 1):
            step = math.sin(pose.walk_phase + (0 if side < 0 else math.pi)) * 10 * s * pose.walk
            fx = x + side * rx * 0.45 + step
            cv.line([(x + side * rx * 0.35, cy + ry * 0.8), (fx, ground - 6 * s)], self.limbs, 5 * s)
            cv.ellipse(fx + f * 6 * s, ground - 4 * s, 14 * s, 7 * s, fill=self.limbs)

        # руки
        for side in (-1, 1):
            sh = (x + side * rx * 0.92, cy + ry * 0.1)
            if side == f and pose.wave > 0:
                a = 0.6 + 0.35 * math.sin(pose.wave * math.pi * 6)  # угол от вертикали
                hand = (sh[0] + side * math.sin(a) * 42 * s, sh[1] - math.cos(a) * 42 * s)
            else:
                swing = math.sin(pose.walk_phase + (math.pi if side < 0 else 0)) * 10 * s * pose.walk
                hand = (sh[0] + side * 22 * s + swing, sh[1] + 28 * s)
            cv.line([sh, hand], self.limbs, 5 * s)
            cv.ellipse(hand[0], hand[1], 7 * s, 7 * s, fill=self.limbs)

        # тело
        if self.shape == "square":
            cv.rounded_rect(x - rx, cy - ry, x + rx, cy + ry, r * 0.3, fill=self.color, outline=self.outline, width=ow)
        elif self.shape == "triangle":
            cv.polygon([(x, cy - ry * 1.15), (x + rx * 1.1, cy + ry), (x - rx * 1.1, cy + ry)],
                       fill=self.color, outline=self.outline, width=ow)
        else:
            cv.ellipse(x, cy, rx, ry, fill=self.color, outline=self.outline, width=ow)
        if self.belly:
            cv.ellipse(x + f * rx * 0.08, cy + ry * 0.38, rx * 0.55, ry * 0.4, fill=hex_to_rgb(self.belly))

        self._draw_face(cv, pose, x + f * rx * 0.18, cy - ry * 0.12, rx, ry, s)
        if self.hat:
            self._draw_hat(cv, x, cy - ry, rx, s)

    def _draw_face(self, cv, pose, fx, fy, rx, ry, s):
        f = pose.facing
        ink = self.outline
        er = self.size * self.eye_size * s
        gap = rx * 0.36
        for side in (-1, 1):
            ex = fx + side * gap
            ey = fy - ry * 0.12
            if pose.blink:
                cv.line([(ex - er, ey), (ex + er, ey)], ink, 4 * s)
            else:
                cv.ellipse(ex, ey, er * 0.85, er, fill="white", outline=ink, width=3 * s)
                pr = er * (0.62 if pose.mood == "surprised" else 0.5)
                cv.ellipse(ex + f * er * 0.3, ey + er * 0.08, pr, pr, fill=(25, 20, 30))
                cv.ellipse(ex + f * er * 0.3 + pr * 0.35, ey - pr * 0.3, pr * 0.3, pr * 0.3, fill="white")
            # брови
            by = ey - er * 1.35
            if pose.mood == "angry":
                cv.line([(ex - side * er, by - 6 * s), (ex + side * er * 0.6, by + 4 * s)], ink, 4 * s)
            elif pose.mood == "sad":
                cv.line([(ex - side * er, by + 4 * s), (ex + side * er * 0.6, by - 4 * s)], ink, 4 * s)
            elif pose.mood == "surprised":
                cv.arc(ex, by, er * 0.8, er * 0.5, 200, 340, ink, 4 * s)

        if self.cheeks:
            for side in (-1, 1):
                cv.ellipse(fx + side * gap * 1.55, fy + ry * 0.2, er * 0.7, er * 0.4,
                           fill=hex_to_rgb(self.cheeks, 120))

        mx, my = fx, fy + ry * 0.32
        mw = rx * 0.32
        if pose.mouth_open > 0.05:
            h = mw * (0.25 + 0.6 * pose.mouth_open)
            cv.ellipse(mx, my, mw * 0.7, h, fill=(110, 30, 40), outline=ink, width=3 * s)
            cv.ellipse(mx, my + h * 0.45, mw * 0.4, h * 0.35, fill=(240, 110, 120))
        elif pose.mood == "surprised":
            cv.ellipse(mx, my, mw * 0.35, mw * 0.45, fill=(110, 30, 40), outline=ink, width=3 * s)
        elif pose.mood == "sad":
            cv.arc(mx, my + mw * 0.5, mw, mw * 0.5, 200, 340, ink, 4 * s)
        elif pose.mood in ("neutral", "angry"):
            cv.line([(mx - mw * 0.6, my), (mx + mw * 0.6, my)], ink, 4 * s)
        else:
            cv.arc(mx, my - mw * 0.4, mw, mw * 0.7, 20, 160, ink, 4 * s)

    def _draw_hat(self, cv, x, top, rx, s):
        color = hex_to_rgb(self.hat.get("color", "#3D5AFE"))
        kind = self.hat.get("type", "cap")
        if kind == "bow":
            cv.polygon([(x, top + 6 * s), (x - 30 * s, top - 14 * s), (x - 30 * s, top + 22 * s)], fill=color, outline=self.outline, width=3 * s)
            cv.polygon([(x, top + 6 * s), (x + 30 * s, top - 14 * s), (x + 30 * s, top + 22 * s)], fill=color, outline=self.outline, width=3 * s)
            cv.ellipse(x, top + 6 * s, 9 * s, 9 * s, fill=color, outline=self.outline, width=3 * s)
        elif kind == "party":
            cv.polygon([(x - 28 * s, top + 10 * s), (x + 28 * s, top + 10 * s), (x, top - 60 * s)], fill=color, outline=self.outline, width=3 * s)
            cv.ellipse(x, top - 60 * s, 9 * s, 9 * s, fill=hex_to_rgb("#FFEB3B"))
        else:  # cap
            cv.pieslice(x, top + 16 * s, rx * 0.72, 34 * s, 180, 360, fill=color, outline=self.outline, width=3 * s)
            cv.rounded_rect(x - rx * 0.1, top + 8 * s, x + rx * 0.95, top + 20 * s, 6 * s,
                            fill=mix(color, "#000000", 0.25), outline=self.outline, width=3 * s)

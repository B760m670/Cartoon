"""Актёр сцены: ключевые кадры + действия → поза на каждом кадре.

Автоматически: дыхание, моргание, походка (walk/hop) по скорости,
пружинные уши и хвост, липсинк по голосу, мелкая жестикуляция при речи.
"""

import math
import random

from . import voice as voice_mod
from .critter import Critter, Pose
from .timeline import Track

POSE_DEFAULTS = {
    "x": 960.0, "y": 940.0, "lift": 0.0, "scale": 1.0, "turn": 0.3, "tilt": 0.0, "lean": 0.0,
    "look_x": 0.0, "look_y": 0.0, "blush": 0.0, "facing": 1, "mood": "happy",
    "arm_l": (18.0, 12.0), "arm_r": (18.0, 12.0), "z": 0, "squash": 0.0,
}


class Actor:
    def __init__(self, spec: dict, critter: Critter, char_spec: dict, fps: int, voice_cache, light):
        self.spec = spec
        self.c = critter
        self.char = char_spec
        self.id = spec.get("id", critter.id)
        self.fps = fps
        self.gait = char_spec.get("gait", "walk")
        start = dict(POSE_DEFAULTS)
        start.update({k: (tuple(v) if isinstance(v, list) else v) for k, v in spec.get("start", {}).items()})
        self.track = Track(spec.get("keys", []), start)
        self.actions = sorted(spec.get("actions", []), key=lambda a: float(a["t"]))
        self.rnd = random.Random(self.id)
        self.lines = []  # (start, end, text, samples, envelope)
        for a in self.actions:
            if a["do"] == "say":
                samples = voice_mod.synth(a["text"], char_spec.get("voice", {}), voice_cache)
                env = voice_mod.mouth_envelope(samples, fps)
                dur = len(samples) / 44100
                a["duration"] = dur
                self.lines.append((float(a["t"]), float(a["t"]) + dur, a["text"], samples, env))
        # пружины
        self.ear = [0.0, 0.0]
        self.ear_v = [0.0, 0.0]
        self.tail = 0.0
        self.prev_head_y = None
        self.prev_tilt = 0.0
        self.blink_times = []
        t = self.rnd.uniform(0.6, 2.0)
        while t < 600:
            self.blink_times.append(t)
            t += self.rnd.uniform(2.2, 4.5)

    def _active(self, kind, t):
        for a in self.actions:
            d = float(a["duration"]) if "duration" in a else (float(a["until"]) - a["t"] if "until" in a else 1.0)
            if a["do"] == kind and a["t"] <= t < a["t"] + d:
                yield a, (t - a["t"]) / d, d

    def pose(self, t: float) -> Pose:
        st = self.track.state(t)
        dt = 1 / self.fps
        x = float(st["x"])
        vx = (float(self.track.value("x", t + dt)) - float(self.track.value("x", t - dt))) / (2 * dt)
        facing = int(st["facing"])
        if not self.track.has("facing") and abs(vx) > 8:
            facing = 1 if vx > 0 else -1
            self._last_facing = facing
        elif not self.track.has("facing"):
            facing = getattr(self, "_last_facing", facing)

        p = Pose(x=x, y=float(st["y"]), lift=float(st["lift"]), scale=float(st["scale"]), facing=facing,
                 turn=float(st["turn"]), tilt=float(st["tilt"]), lean=float(st["lean"]),
                 look_x=float(st["look_x"]), look_y=float(st["look_y"]), blush=float(st["blush"]),
                 mood=st["mood"], arm_l=tuple(st["arm_l"]), arm_r=tuple(st["arm_r"]), squash=float(st["squash"]))
        for a in self.actions:
            if a["do"] == "mood" and a["t"] <= t:
                p.mood = a["mood"]

        # дыхание
        p.breath = math.sin(t * 2 * math.pi / 3.2 + self.rnd.random())
        p.lift += 0.0

        # походка
        speed = abs(vx)
        if speed > 10:
            k = min(1.0, speed / 260)
            if self.gait == "hop":
                ph = (x / 140) * math.pi
                hop = abs(math.sin(ph))
                p.lift += hop * 46 * k
                p.squash = (0.12 if hop < 0.15 else -0.08) * k
                p.leg_l = p.leg_r = (-25 * hop * k, 35 * hop * k)
                p.arm_l = (p.arm_l[0] + 30 * hop * k, p.arm_l[1])
                p.arm_r = (p.arm_r[0] + 30 * hop * k, p.arm_r[1])
            else:
                ph = (x / 55)
                sw = math.sin(ph)
                p.leg_l = (sw * 34 * k, max(0, -sw) * 30 * k)
                p.leg_r = (-sw * 34 * k, max(0, sw) * 30 * k)
                p.lift += abs(math.cos(ph)) * 9 * k
                p.arm_l = (p.arm_l[0] - sw * 26 * k, p.arm_l[1] + 10 * k)
                p.arm_r = (p.arm_r[0] + sw * 26 * k, p.arm_r[1] + 10 * k)
                p.lean += 5 * k
                p.tilt += math.sin(ph * 2) * 1.5 * k

        # прыжок: подготовка → полёт → приземление
        for a, u, d in self._active("jump", t):
            h = float(a.get("height", 150))
            if u < 0.18:
                q = u / 0.18
                p.squash += 0.28 * math.sin(q * math.pi / 2)
                p.arm_l = (p.arm_l[0] - 10, p.arm_l[1])
                p.arm_r = (p.arm_r[0] - 10, p.arm_r[1])
            elif u < 0.88:
                q = (u - 0.18) / 0.7
                p.lift += h * 4 * q * (1 - q)
                p.squash += -0.16 * (1 - abs(2 * q - 1))
                up = 120 * math.sin(q * math.pi)
                p.arm_l = (p.arm_l[0] + up, p.arm_l[1] - 10)
                p.arm_r = (p.arm_r[0] + up, p.arm_r[1] - 10)
                p.leg_l = (-15, 30)
                p.leg_r = (10, 20)
            else:
                q = (u - 0.88) / 0.12
                p.squash += 0.22 * math.sin(q * math.pi)

        # помахать
        for a, u, d in self._active("wave", t):
            env = min(1, u * 6, (1 - u) * 6)
            sw = math.sin(t * 2 * math.pi * 2.2)
            side = a.get("arm", "r")
            val = (150 * env + sw * 18 * env, -20 * env + sw * 25 * env)
            if side == "l":
                p.arm_l = (p.arm_l[0] + val[0], p.arm_l[1] + val[1])
            else:
                p.arm_r = (p.arm_r[0] + val[0], p.arm_r[1] + val[1])

        # тянуться вверх (лапы и тело вытянуты)
        for a, u, d in self._active("reach", t):
            env = min(1, u * 5, (1 - u) * 5)
            p.arm_l = (p.arm_l[0] + 120 * env, p.arm_l[1] - 12 * env)
            p.arm_r = (p.arm_r[0] + 125 * env, p.arm_r[1] - 12 * env)
            p.stretch = env
            p.squash -= 0.1 * env
            p.look_y = -0.8 * env + p.look_y * (1 - env)
            p.tilt += -6 * env

        # речь: липсинк + кивки
        for start, end, text, samples, env in self.lines:
            if start <= t < end:
                i = int((t - start) * self.fps)
                p.mouth = float(env[min(i, len(env) - 1)])
                p.tilt += math.sin((t - start) * 5.1) * 3.0
                p.lift += p.mouth * 3

        # моргание
        for bt in self.blink_times:
            if bt <= t < bt + 0.16:
                u = (t - bt) / 0.16
                p.blink = math.sin(u * math.pi)
                break
        for a, u, d in self._active("close_eyes", t):
            p.blink = max(p.blink, min(1, u * 8, (1 - u) * 8))

        # пружины ушей и хвоста (вторичная анимация)
        hy = p.lift
        dy = 0 if self.prev_head_y is None else hy - self.prev_head_y
        dtilt = p.tilt - self.prev_tilt
        self.prev_head_y, self.prev_tilt = hy, p.tilt
        for i, side in enumerate((-1, 1)):
            force = -dy * 1.4 * side - dtilt * 2.0 + (-6 if p.mood == "sad" else 0) * side
            self.ear_v[i] += force - self.ear[i] * 0.18
            self.ear_v[i] *= 0.78
            self.ear[i] += self.ear_v[i]
        p.ear_l, p.ear_r = max(-35, min(35, self.ear[0])), max(-35, min(35, self.ear[1]))
        self.tail += (math.sin(t * 6) * 10 * (1 if p.mood in ("happy", "excited") else 0.2) - self.tail) * 0.3
        p.tail = self.tail
        return p

    def subtitles(self, t):
        for start, end, text, _, _ in self.lines:
            if start <= t < end + 0.25:
                return text
        return None

    def audio_events(self):
        events = []
        for a in self.actions:
            if a["do"] == "jump":
                events.append({"t": a["t"] + float(a.get("duration", 1.0)) * 0.18, "kind": "boing", "volume": 0.5})
            elif a["do"] == "sfx":
                events.append({"t": a["t"], "kind": a["kind"], "volume": a.get("volume", 0.7)})
        return events

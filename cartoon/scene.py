"""Сцена: фон + актёры + действия + камера. Считает кадр для момента времени t."""

import math
import random

from PIL import Image

from . import backgrounds, config, easing
from .characters import Character, Pose
from .drawing import Canvas, hex_to_rgb, speech_bubble
from .timeline import Track

CHARS_PER_SECOND = 20  # скорость «печати» реплик


class Actor:
    def __init__(self, spec: dict, character: Character):
        self.spec = spec
        self.character = character
        self.id = spec.get("id", character.id)
        start = {"x": 640, "y": 600, "scale": 1.0, "mood": spec.get("mood", "happy")}
        start.update(spec.get("start", {}))
        self.track = Track(spec.get("keyframes", []), start)
        self.actions = sorted(spec.get("actions", []), key=lambda a: float(a["t"]))
        for a in self.actions:
            if a["type"] == "say":
                a.setdefault("duration", round(len(a["text"]) / CHARS_PER_SECOND + 1.4, 2))
        self.facing = int(spec.get("facing", 1))

    def _active(self, kind, t):
        for a in self.actions:
            if a["type"] == kind and a["t"] <= t < a["t"] + a.get("duration", 0):
                yield a

    def pose(self, t: float) -> tuple[Pose, str | None]:
        st = self.track.state(t)
        x, y = float(st["x"]), float(st["y"])
        dt = 0.04
        vx = (float(self.track.value("x", t + dt)) - float(self.track.value("x", t - dt))) / (2 * dt)
        if st.get("facing") is not None:
            self.facing = int(st["facing"])
        elif abs(vx) > 5:
            self.facing = 1 if vx > 0 else -1

        walk = min(1.0, abs(vx) / 120)
        phase = x / 22
        squash, lift = 0.0, 0.0
        if walk > 0.05:
            lift += abs(math.sin(phase)) * 10 * walk
            squash = -0.06 * walk * abs(math.sin(phase))

        mood = st.get("mood", "happy")
        for a in self.actions:
            if a["type"] == "mood" and a["t"] <= t:
                mood = a["mood"]

        for a in self._active("jump", t):
            p = (t - a["t"]) / a["duration"]
            lift += a.get("height", 120) * 4 * p * (1 - p)
            squash = 0.35 if p < 0.08 or p > 0.92 else -0.2

        wave = 0.0
        for a in self._active("wave", t):
            wave = (t - a["t"]) / a["duration"] + 1e-3

        text, mouth = None, 0.0
        for a in self._active("say", t):
            shown = int((t - a["t"]) * CHARS_PER_SECOND)
            text = a["text"][: max(1, shown)]
            if shown < len(a["text"]):
                mouth = 0.5 + 0.5 * math.sin(t * 22)

        pose = Pose(
            x=x, y=y, lift=lift, scale=float(st["scale"]), facing=self.facing, squash=squash,
            mood=mood, mouth_open=mouth, blink=self.character.is_blinking(t),
            walk_phase=phase, walk=walk, wave=wave,
        )
        return pose, text

    def head_top(self, pose: Pose) -> float:
        return pose.y - pose.lift - (14 + 2 * self.character.size) * pose.scale - (40 if self.character.hat else 6)

    def sound_events(self) -> list[dict]:
        events = []
        rnd = random.Random(self.id)
        pitch = self.character.voice_pitch
        for a in self.actions:
            if a["type"] == "say":
                letters = [c for c in a["text"] if c.isalpha()]
                for i in range(0, len(letters), 2):
                    events.append({"t": a["t"] + i / CHARS_PER_SECOND, "kind": "blip",
                                   "pitch": pitch * rnd.uniform(0.85, 1.25), "volume": 0.6})
            elif a["type"] == "jump":
                events.append({"t": a["t"], "kind": "boing"})
            elif a["type"] == "wave":
                events.append({"t": a["t"], "kind": "pop", "volume": 0.6})
        return events


class Scene:
    def __init__(self, sid: str, spec: dict, characters: dict, width: int, height: int):
        self.id = sid
        self.spec = spec
        self.kind = spec.get("type", "scene")
        self.duration = float(spec["duration"])
        self.width, self.height = width, height
        ss = config.SUPERSAMPLE
        self.bg = backgrounds.create(spec.get("background"), width * ss, height * ss)
        self.actors = []
        for a in spec.get("actors", []):
            cid = a["character"]
            if cid not in characters:
                raise ValueError(f"Сцена {sid}: нет персонажа '{cid}'. Есть: {', '.join(characters)}")
            self.actors.append(Actor(a, characters[cid]))
        self.camera = Track(spec.get("camera", []), {"zoom": 1.0, "x": 640, "y": 360})
        self.fade_in = float(spec.get("fade_in", 0.4))
        self.fade_out = float(spec.get("fade_out", 0.4))

    def frame(self, t: float) -> Image.Image:
        cv = self.bg.frame(t)
        if self.kind == "title":
            self._draw_title(cv, t)
        else:
            posed = [(actor, *actor.pose(t)) for actor in self.actors]
            posed.sort(key=lambda item: item[1].y)
            for actor, pose, _ in posed:
                actor.character.draw(cv, pose)
            tint = self.spec.get("tint")  # {color: "#0B1033", opacity: 0.3} — общий светофильтр
            if tint:
                alpha = int(255 * float(tint.get("opacity", 0.3)))
                cv.rect(0, 0, config.LOGICAL_WIDTH, config.LOGICAL_HEIGHT, hex_to_rgb(tint["color"], alpha))
            for actor, pose, text in posed:
                if text:
                    speech_bubble(cv, pose.x, self.head_top(actor, pose), text)
            for cap in self.spec.get("captions", []):
                if cap["t"] <= t < cap["t"] + cap.get("duration", 2):
                    cv.text(640, 680, cap["text"], 32, "white", anchor="mm", stroke=3, stroke_fill=(0, 0, 0))
        img = self._apply_camera(cv.img, t)
        return self._apply_fade(img, t)

    @staticmethod
    def head_top(actor, pose):
        return actor.head_top(pose)

    def _draw_title(self, cv: Canvas, t: float):
        p = easing.back_out(min(1.0, t / 0.8))
        size = max(1, 84 * p)
        color = hex_to_rgb(self.spec.get("text_color", "#FFFFFF"))
        cv.text(640, 320, self.spec.get("text", ""), size, color, anchor="mm", stroke=5, stroke_fill=(40, 30, 60))
        sub = self.spec.get("subtitle")
        if sub and t > 0.6:
            a = int(255 * min(1.0, (t - 0.6) / 0.6))
            cv.text(640, 420, sub, 40, color + (a,), anchor="mm", stroke=3, stroke_fill=(40, 30, 60, a))

    def _apply_camera(self, img: Image.Image, t: float) -> Image.Image:
        zoom = max(1.0, float(self.camera.value("zoom", t)))
        target = (self.width, self.height)
        if zoom == 1.0:
            return img.resize(target, Image.LANCZOS)
        k = img.width / config.LOGICAL_WIDTH
        cw, ch = img.width / zoom, img.height / zoom
        cx = min(max(float(self.camera.value("x", t)) * k, cw / 2), img.width - cw / 2)
        cy = min(max(float(self.camera.value("y", t)) * k, ch / 2), img.height - ch / 2)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        return img.resize(target, Image.LANCZOS, box=box)

    def _apply_fade(self, img: Image.Image, t: float) -> Image.Image:
        k = 1.0
        if self.fade_in > 0 and t < self.fade_in:
            k = t / self.fade_in
        if self.fade_out > 0 and t > self.duration - self.fade_out:
            k = min(k, (self.duration - t) / self.fade_out)
        if k >= 1:
            return img
        return Image.blend(Image.new("RGB", img.size), img, max(0.0, k))

    def sound_events(self) -> list[dict]:
        events = list(self.spec.get("sounds", []))
        if self.kind == "title":
            events.append({"t": 0.1, "kind": "chime"})
        for actor in self.actors:
            events.extend(actor.sound_events())
        return events

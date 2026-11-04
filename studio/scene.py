"""Сцена: локация + актёры + реквизит + камера + субтитры + постобработка."""

import math
import random

import numpy as np
import skia
import yaml

from cartoon import audio as sfx
from . import config, location, skx
from .actor import Actor
from .critter import Critter
from .post import Post
from .scenery import apple
from .timeline import Track

def _apple(c, st, L, t):
    apple(c, 0, 0, 26, L)
    if st.get("sparkle"):
        # мерцающая звёздочка — «то самое» яблоко
        a = 0.5 + 0.5 * math.sin(t * 5)
        r = 16 + 6 * a
        star = skia.Path()
        for i in range(8):
            ang = i * math.pi / 4
            rr = r if i % 2 == 0 else r * 0.28
            pt = (-14 + math.cos(ang) * rr, -14 + math.sin(ang) * rr)
            star.moveTo(*pt) if i == 0 else star.lineTo(*pt)
        star.close()
        c.drawPath(star, skx.fill("#FFFFFF", 0.4 + 0.6 * a))
        c.drawCircle(-14, -14, r * 1.4, skx.fill("#FFF6C8", 0.35 * a, blur=10))


def _fireflies(c, st, L, t):
    """Рой светлячков вокруг (x, y): amount 0..1 — сколько их, radius — размер роя, rise — улетают вверх."""
    amount = float(st.get("amount", 1.0))
    if amount <= 0.01:
        return
    radius = float(st.get("radius", 260))
    rise = float(st.get("rise", 0.0))
    n = int(40 * amount)
    rnd = random.Random(7)
    for i in range(40):
        ph, sp, rr = rnd.uniform(0, 6.28), rnd.uniform(0.3, 0.9), rnd.uniform(0.2, 1.0)
        if i >= n:
            continue
        x = math.cos(t * sp + ph) * radius * rr + math.sin(t * 1.7 + ph * 2) * 30
        y = math.sin(t * sp * 1.3 + ph) * radius * 0.55 * rr - rise * (0.5 + rr) * 600
        blink = 0.55 + 0.45 * math.sin(t * rnd.uniform(3, 6) + ph)
        c.drawCircle(x, y, 30, skx.fill("#C8F040", 0.35 * blink, blur=16, blend=skia.BlendMode.kPlus))
        c.drawCircle(x, y, 5, skx.fill("#E8F870", 0.9 * blink, blend=skia.BlendMode.kPlus))


PROPS = {"apple": _apple, "fireflies": _fireflies}


def load_character(cid):
    path = config.CHARACTERS_DIR / cid / "character.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Нет персонажа {cid}: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Prop:
    def __init__(self, spec):
        self.id = spec.get("id", spec["type"])
        self.type = spec["type"]
        start = {"x": 960, "y": 540, "rot": 0.0, "scale": 1.0, "visible": 1, "z": 0, "sparkle": 0,
                 "amount": 1.0, "radius": 260, "rise": 0.0}
        start.update(spec.get("start", {}))
        self.track = Track(spec.get("keys", []), start)
        self.events = spec.get("sounds", [])

    def draw(self, c, t, L):
        st = self.track.state(t)
        if not st["visible"]:
            return
        c.save()
        c.translate(float(st["x"]), float(st["y"]))
        c.rotate(float(st["rot"]))
        c.scale(float(st["scale"]), float(st["scale"]))
        PROPS[self.type](c, st, L, t)
        c.restore()


class Scene:
    def __init__(self, sid, spec, episode, width, height, voice_cache):
        self.id = sid
        self.spec = spec
        self.kind = spec.get("type", "scene")
        self.fps = episode.get("fps", config.FPS)
        self.W, self.H = width, height
        self.k = width / config.W
        lspec = spec.get("light", {})
        self.light = skx.Light(**lspec) if lspec else skx.Light()
        self.loc = location.load(spec["location"], self.light) if spec.get("location") else None
        self.actors = []
        for a in spec.get("actors", []):
            cs = load_character(a["character"])
            self.actors.append(Actor(a, Critter(a["character"], cs, self.light), cs, self.fps, voice_cache, self.light))
        self.props = [Prop(p) for p in spec.get("props", [])]
        self.camera = Track(spec.get("camera", []), {"x": 960, "y": 540, "zoom": 1.0, "shake": 0.0})
        self.post = Post(width, height, spec.get("post", episode.get("post")))
        self.fade_in = float(spec.get("fade_in", 0.35))
        self.fade_out = float(spec.get("fade_out", 0.35))
        last_line = max([end for a in self.actors for (_, end, *_r) in a.lines] + [0])
        self.duration = float(spec.get("duration", last_line + 1.0))
        self.surface = skia.Surface(width, height)
        tint = spec.get("actor_tint")  # {color: "#6A7BC8", alpha: 0.45} — освещение сцены на героях (ночь, закат)
        self.tint = skx.rgb(skx.mix("#FFFFFF", tint["color"], float(tint.get("alpha", 0.4)))) if tint else None

    def frame(self, t: float) -> np.ndarray:
        c = self.surface.getCanvas()
        c.clear(skia.ColorBLACK)
        self.post.begin(c)
        c.save()
        c.scale(self.k, self.k)
        st = self.camera.state(t)
        sh = float(st["shake"])
        cam = location.Camera(float(st["x"]) + math.sin(t * 47) * sh, float(st["y"]) + math.cos(t * 53) * sh, float(st["zoom"]))
        if self.loc:
            self.loc.draw_layers(c, cam, t, "back")
        poses = [(a, a.pose(t)) for a in self.actors]
        c.save()
        c.concat(cam.matrix(1.0))
        drawables = [((float(a.track.value("z", t) or 0), p.y), "actor", (a, p)) for a, p in poses]
        drawables += [((float(pr.track.value("z", t) or 0), float(pr.track.value("y", t))), "prop", pr) for pr in self.props]
        for _, kind, obj in sorted(drawables, key=lambda d: d[0]):
            if kind == "actor":
                if self.tint is not None:
                    c.saveLayer(None, None)
                    obj[0].c.draw(c, obj[1])
                    c.drawPaint(skia.Paint(Color=self.tint, BlendMode=skia.BlendMode.kModulate))
                    c.restore()
                else:
                    obj[0].c.draw(c, obj[1])
            else:
                obj.draw(c, t, self.light)
        c.restore()
        if self.loc:
            self.loc.draw_layers(c, cam, t, "front")
            self.loc.screen_effects(c, t)
        if self.kind == "title":
            self._title(c, t)
        if self.spec.get("subtitles", True):
            for a, _ in poses:
                txt = a.subtitles(t)
                if txt:
                    self._subtitle(c, txt, a.c.look.name)
        c.restore()
        self.post.end(c)
        fade = 1.0
        if self.fade_in and t < self.fade_in:
            fade = t / self.fade_in
        if self.fade_out and t > self.duration - self.fade_out:
            fade = min(fade, (self.duration - t) / self.fade_out)
        self.post.apply(self.surface, fade)
        return skx.surface_to_rgb(self.surface)

    def _subtitle(self, c, text, who):
        size = 46
        w = skx.text_width(text, size)
        x, y = config.W / 2, config.H - 70
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - w / 2 - 28, y - 52, w + 56, 74), 22, 22), skx.fill("#0E0A1A", 0.45))
        skx.text(c, text, x, y, size, "#FFFFFF", "#1A1030", 7)

    def _title(self, c, t):
        title = self.spec.get("text", "")
        sub = self.spec.get("subtitle", "")
        from cartoon import easing
        p = easing.back_out(min(1.0, max(0.0, (t - 0.3) / 0.9)))
        size = 150 * max(p, 0.01)
        c.drawRect(skia.Rect(0, 0, config.W, config.H), skx.fill("#120A2A", 0.25))
        y = config.H * 0.42
        glow = skx.fill("#FFD36E", 0.55, blur=28)
        font = skia.Font(skx.typeface(True), size)
        w = font.measureText(title)
        c.drawTextBlob(skia.TextBlob.MakeFromString(title, font), config.W / 2 - w / 2, y, glow)
        skx.text(c, title, config.W / 2, y, size, "#FFFFFF", "#3A1B5C", 16)
        if sub and t > 1.0:
            a = min(1.0, (t - 1.0) / 0.6)
            skx.text(c, sub, config.W / 2, y + 120, 64, "#FFE9A8", "#3A1B5C", 10, a=a)

    def audio(self) -> np.ndarray:
        n = int(round(self.duration * config.AUDIO_RATE))
        track = np.zeros(n)
        voice = np.zeros(n)
        for a in self.actors:
            for start, end, text, samples, _ in a.lines:
                i = int(start * config.AUDIO_RATE)
                j = min(n, i + len(samples))
                if i < n:
                    voice[i:j] += samples[: j - i] * 0.95
        events = list(self.spec.get("sounds", []))
        for a in self.actors:
            events += a.audio_events()
        if self.kind == "title":
            events.append({"t": 0.3, "kind": "chime", "volume": 0.7})
        rendered = sfx.render_track(events, self.duration) if events else np.zeros(n)
        track[: len(rendered)] += rendered[:n] * 0.6
        return track + voice, voice

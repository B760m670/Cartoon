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


def _puddle(c, st, L, t):
    """Лужа: голубое отражение неба, блик; splash 0..1 — брызги разлетаются дугами."""
    w, h = 170, 34
    c.drawOval(skia.Rect.MakeXYWH(-w - 8, -h - 4, 2 * w + 16, 2 * h + 8), skx.fill("#3D5A3A", 0.5, blur=4))
    c.drawOval(skia.Rect.MakeXYWH(-w, -h, 2 * w, 2 * h),
               skx.fill("#000", shader=skx.linear((0, -h), (0, h), [st.get("sky", "#9DB4D6"), "#5F7FA8"])))
    c.drawOval(skia.Rect.MakeXYWH(-w * 0.6, -h * 0.6, w * 0.7, h * 0.35), skx.fill("#FFFFFF", 0.45))
    # круги на воде
    for k in range(3):
        ph = (t * 0.8 + k / 3) % 1
        rx = 20 + ph * 120
        c.drawOval(skia.Rect.MakeXYWH(-rx + (k - 1) * 50, -rx * 0.2, rx * 2, rx * 0.4), skx.stroke("#FFFFFF", 2, 0.35 * (1 - ph)))
    sp = float(st.get("splash", 0))
    if 0.01 < sp < 0.99:
        rnd = random.Random(3)
        for i in range(22):
            a = math.pi * rnd.uniform(0.08, 0.92)
            v = rnd.uniform(260, 520)
            x = math.cos(a) * v * sp * 1.1
            y = -math.sin(a) * v * sp + 900 * sp * sp * 0.9
            r = rnd.uniform(6, 13) * (1 - sp * 0.6)
            c.drawCircle(x, y - 10, r, skx.fill("#CFE3FF", 0.85))
            c.drawCircle(x - r * 0.3, y - 10 - r * 0.3, r * 0.35, skx.fill("#FFFFFF", 0.9))
        ring = sp * 220
        c.drawOval(skia.Rect.MakeXYWH(-ring, -ring * 0.22, ring * 2, ring * 0.44), skx.stroke("#FFFFFF", 4, 0.7 * (1 - sp)))


def _leaf(c, st, L, t):
    """Большой лист-зонтик: держится над головой (рисуется с центром в черенке)."""
    from .skx import cel
    sway = math.sin(t * 2.2) * 3
    c.rotate(sway)
    stem = skx.smooth_open([(0, 0), (6, -90), (0, -190)])
    c.drawPath(stem, skx.stroke("#3E6B2A", 9))
    leaf = skx.smooth_closed([(-230, -150), (-120, -235), (0, -260), (130, -235), (240, -150), (120, -175), (0, -170), (-120, -178)],
                             tension=0.85)
    cel(c, leaf, "#4FA83D", L, 260, line_w=4)
    for x in (-150, -75, 75, 150):
        c.drawPath(skx.smooth_open([(0, -200), (x * 0.6, -215), (x, -195)]), skx.stroke("#2F7A2A", 3, 0.7))
    c.drawPath(skx.smooth_open([(-200, -165), (0, -205), (200, -165)]), skx.stroke("#2F7A2A", 4, 0.8))


PROPS = {"apple": _apple, "fireflies": _fireflies, "puddle": _puddle, "leaf": _leaf}


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
        self.follow = spec.get("follow")  # id персонажа: тогда x, y — смещение от его ног (с учётом прыжка)

    def draw(self, c, t, L, base=(0.0, 0.0)):
        st = self.track.state(t)
        if not st["visible"]:
            return
        c.save()
        c.translate(float(st["x"]) + base[0], float(st["y"]) + base[1])
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
        # вертикальный кадр (Shorts 9:16): мир масштабируется по высоте, видна центральная полоса
        self.vertical = height > width
        self.k = height / config.H if self.vertical else width / config.W
        self.view_w = width / self.k          # видимая ширина в единицах мира
        self.off_x = (self.view_w - config.W) / 2
        vspec = spec.get("vertical", {})
        self.v_camera = Track(vspec["camera"], {"x": 960, "y": 540, "zoom": 1.0, "shake": 0.0}) if vspec.get("camera") else None
        self.v_zoom = float(vspec.get("zoom", 0.82))
        lspec = spec.get("light", {})
        self.light = skx.Light(**lspec) if lspec else skx.Light()
        self.loc = location.load(spec["location"], self.light) if spec.get("location") else None
        self.actors = []
        for a in spec.get("actors", []):
            cs = load_character(a["character"])
            self.actors.append(Actor(a, Critter(a["character"], cs, self.light), cs, self.fps, voice_cache, self.light))
        self.props = [Prop(p) for p in spec.get("props", [])]
        env = spec.get("env", {})  # {start: {rain: 1}, keys: [{t: 5, rain: 0}]} — состояние локации (дождь, радуга)
        self.env = Track(env.get("keys", []), env.get("start", {}))
        self.camera = Track(spec.get("camera", []), {"x": 960, "y": 540, "zoom": 1.0, "shake": 0.0})
        self.post = Post(width, height, spec.get("post", episode.get("post")))
        self.fade_in = float(spec.get("fade_in", 0.35))
        self.fade_out = float(spec.get("fade_out", 0.35))
        last_line = max([end for a in self.actors for (_, end, *_r) in a.lines] + [0])
        self.duration = float(spec.get("duration", last_line + 1.0))
        self.surface = skia.Surface(width, height)
        self.hook = None
        tint = spec.get("actor_tint")  # {color: "#6A7BC8", alpha: 0.45} — освещение сцены на героях (ночь, закат)
        self.tint = skx.rgb(skx.mix("#FFFFFF", tint["color"], float(tint.get("alpha", 0.4)))) if tint else None

    def frame(self, t: float) -> np.ndarray:
        c = self.surface.getCanvas()
        c.clear(skia.ColorBLACK)
        self.post.begin(c)
        c.save()
        c.scale(self.k, self.k)
        c.translate(self.off_x, 0)
        st = self.camera.state(t)
        sh = float(st["shake"])
        cx, cy, cz = float(st["x"]), float(st["y"]), float(st["zoom"])
        if self.vertical:
            if self.v_camera:
                vs = self.v_camera.state(t)
                cx, cy, cz = float(vs["x"]), float(vs["y"]), float(vs["zoom"])
            else:
                # держим героев в узком кадре: середина между ними + чуть отъезжаем
                xs = [float(a.track.value("x", t)) for a in self.actors]
                if xs:
                    cx = 0.35 * cx + 0.65 * (min(xs) + max(xs)) / 2
                cz = cz * self.v_zoom
                cy = 0.4 * cy + 0.6 * 660   # герои в нижней трети, но выше панели YouTube
        cam = location.Camera(cx + math.sin(t * 47) * sh, cy + math.cos(t * 53) * sh, cz)
        if self.loc:
            self.loc.env = {k: self.env.value(k, t) for k in set(self.env.props) | set(self.env.defaults)}
            self.loc.draw_layers(c, cam, t, "back")
        poses = [(a, a.pose(t)) for a in self.actors]
        anchor = {a.id: (p.x, p.y - p.lift) for a, p in poses}
        c.save()
        c.concat(cam.matrix(1.0))
        drawables = [((float(a.track.value("z", t) or 0), p.y), "actor", (a, p)) for a, p in poses]
        def _py(pr):
            return float(pr.track.value("y", t)) + (anchor.get(pr.follow, (0, 0))[1] if pr.follow else 0)
        drawables += [((float(pr.track.value("z", t) or 0), _py(pr)), "prop", pr) for pr in self.props]
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
                obj.draw(c, t, self.light, anchor.get(obj.follow, (0.0, 0.0)) if obj.follow else (0.0, 0.0))
        c.restore()
        if self.loc:
            self.loc.draw_layers(c, cam, t, "front")
            self.loc.screen_effects(c, t)
        if self.kind == "title":
            self._title(c, t)
        if self.hook and t < 3.0:
            self._hook(c, t)
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
        x = config.W / 2
        if not self.vertical:
            size = 46
            lines = [text]
            y0 = config.H - 70
        else:
            # Shorts: крупнее, переносим по словам, выше нижней панели YouTube
            size = 40
            maxw = self.view_w * 0.86
            lines, cur = [], ""
            for word in text.split():
                trial = (cur + " " + word).strip()
                if cur and skx.text_width(trial, size) > maxw:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
            y0 = config.H * 0.24
        for i, line in enumerate(lines):
            y = y0 + i * size * (1.62 if self.vertical else 1.2)
            w = skx.text_width(line, size)
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - w / 2 - 24, y - size * 1.12, w + 48, size * 1.6), 20, 20),
                        skx.fill("#0E0A1A", 0.45))
            skx.text(c, line, x, y, size, "#FFFFFF", "#1A1030", 7)

    def _hook(self, c, t):
        from cartoon import easing
        p = easing.back_out(min(1.0, t / 0.35)) if t < 0.35 else 1.0
        a = min(1.0, (3.0 - t) / 0.4)
        size = min(76, 76 * self.view_w * 0.88 / max(1, skx.text_width(self.hook, 76))) * max(p, 0.01)
        skx.text(c, self.hook, config.W / 2, config.H * 0.13, size, "#FFE14D", "#1B0E33", 12, a=a)

    def _title(self, c, t):
        title = self.spec.get("text", "")
        sub = self.spec.get("subtitle", "")
        from cartoon import easing
        p = easing.back_out(min(1.0, max(0.0, (t - 0.3) / 0.9)))
        base = min(150, 150 * self.view_w * 0.9 / max(1, skx.text_width(title, 150)))
        size = base * max(p, 0.01)
        c.drawRect(skia.Rect(-self.off_x, 0, config.W + self.off_x, config.H), skx.fill("#120A2A", 0.25))
        y = config.H * 0.42
        glow = skx.fill("#FFD36E", 0.55, blur=28)
        font = skia.Font(skx.typeface(True), size)
        w = font.measureText(title)
        c.drawTextBlob(skia.TextBlob.MakeFromString(title, font), config.W / 2 - w / 2, y, glow)
        skx.text(c, title, config.W / 2, y, size, "#FFFFFF", "#3A1B5C", 16)
        if sub and t > 1.0:
            a = min(1.0, (t - 1.0) / 0.6)
            ss = min(64, 64 * self.view_w * 0.9 / max(1, skx.text_width(sub, 64)))
            skx.text(c, sub, config.W / 2, y + base * 0.8, ss, "#FFE9A8", "#3A1B5C", 10, a=a)

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

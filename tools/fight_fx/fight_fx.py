"""Anime / cinema style impact effects for a fight clip.

Free tools only: OpenCV, NumPy, SciPy, Pillow, ffmpeg.

Usage:
    python tools/fight_fx/fight_fx.py hits.json input.mp4 output.mp4 [--preview N]

hits.json describes the source video layout and every hit:
    {
      "band": [y0, y1],            # rows of the real picture inside a 9:16 source
      "hits": [{"f": 152, "x": 230, "y": 150, "s": 3, "word": "WHAM!"}, ...]
    }
x, y are pixel coordinates inside the band (band width = source width);
s is the strength 1..3 (controls slow motion, freeze, waves, particles).
"""
import json
import math
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal

OUT_W, OUT_H = 1080, 1920
FPS = 30
SR = 44100
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf"

# per-strength timing: pre-ramp length, speed at hit, freeze frames, post slow length, post speed
PROFILE = {
    1: dict(P=0, vpre=1.0, Z=2, Q=0, vmin=1.0),
    2: dict(P=5, vpre=0.55, Z=4, Q=9, vmin=0.4),
    3: dict(P=8, vpre=0.4, Z=6, Q=16, vmin=0.25),
}


# ---------------------------------------------------------------- input
def read_frames(path, y0, y1):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f[y0:y1])
    return frames


def detect_cuts(frames):
    cuts = set()
    prev = None
    for i, f in enumerate(frames):
        s = cv2.resize(f, (96, 96)).astype(np.float32)
        if prev is not None and np.abs(s - prev).mean() > 33:
            cuts.add(i)
        prev = s
    return cuts


# ---------------------------------------------------------------- timeline
def speed_at(pos, hits):
    v = 1.0
    for h in hits:
        p = PROFILE[h["s"]]
        d = pos - h["f"]
        if p["P"] and -p["P"] <= d < 0:
            k = (d + p["P"]) / p["P"]
            v = min(v, 1 + (p["vpre"] - 1) * k * k)
        elif p["Q"] and 0 <= d < p["Q"]:
            k = d / p["Q"]
            if k < 0.6:
                v = min(v, p["vmin"])
            else:
                kk = (k - 0.6) / 0.4
                v = min(v, p["vmin"] + (1 - p["vmin"]) * kk * kk)
    return v


def build_timeline(n, hits, extra_slow=()):
    """Return list of (src_pos, freeze_flag) and the output index of each hit."""
    out = []
    hit_out = {}
    pos = 0.0
    pending = sorted(hits, key=lambda h: h["f"])
    hi = 0
    while pos <= n - 1:
        v = speed_at(pos, hits)
        for a, b, sp in extra_slow:
            if a <= pos < b:
                v = min(v, sp)
        if hi < len(pending) and pos + 1e-6 >= pending[hi]["f"]:
            h = pending[hi]
            hit_out[hi] = len(out)
            for _ in range(PROFILE[h["s"]]["Z"]):
                out.append((float(h["f"]), True))
            pos = float(h["f"]) + 0.15
            hi += 1
            continue
        out.append((pos, False))
        nxt = pos + v
        if hi < len(pending) and nxt > pending[hi]["f"] > pos:
            nxt = float(pending[hi]["f"])
        pos = nxt
    return out, [hit_out[i] for i in range(len(pending))], pending


# ---------------------------------------------------------------- interpolation
class Interp:
    def __init__(self, frames, cuts):
        self.frames = frames
        self.cuts = cuts
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        self.cache = {}
        h, w = frames[0].shape[:2]
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        self.grid = (gx, gy)

    def flow(self, a):
        if a not in self.cache:
            if len(self.cache) > 6:
                self.cache.pop(next(iter(self.cache)))
            ga = cv2.cvtColor(self.frames[a], cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(self.frames[a + 1], cv2.COLOR_BGR2GRAY)
            self.cache[a] = self.dis.calc(ga, gb, None)
        return self.cache[a]

    def get(self, pos):
        a = int(math.floor(pos))
        t = pos - a
        if t < 0.04 or a + 1 >= len(self.frames):
            return self.frames[min(a, len(self.frames) - 1)].copy()
        if t > 0.96:
            return self.frames[a + 1].copy()
        if (a + 1) in self.cuts:
            return self.frames[a].copy()
        f = self.flow(a)
        gx, gy = self.grid
        A = cv2.remap(self.frames[a], gx - t * f[..., 0], gy - t * f[..., 1],
                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        B = cv2.remap(self.frames[a + 1], gx + (1 - t) * f[..., 0], gy + (1 - t) * f[..., 1],
                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return cv2.addWeighted(A, 1 - t, B, t, 0)


# ---------------------------------------------------------------- look
def grade(img, slow):
    f = img.astype(np.float32) / 255.0
    f = f * f * (3 - 2 * f) * 0.35 + f * 0.65          # S-curve contrast
    lum = f.mean(axis=2, keepdims=True)
    sat = 1.15 - 0.45 * slow
    f = lum + (f - lum) * sat
    # teal shadows / warm highlights; cooler in slow motion
    f[..., 0] += (0.04 + 0.05 * slow) * (1 - lum[..., 0])
    f[..., 2] += 0.035 * lum[..., 0] - 0.03 * slow
    return np.clip(f * 255, 0, 255).astype(np.uint8)


def compose(band, bw):
    """Band (square) scaled to full width in the middle, blurred dark copy behind."""
    small = cv2.resize(band, (54, 96))
    bg = cv2.GaussianBlur(small, (0, 0), 6)
    bg = cv2.resize(bg, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)
    bg = (bg.astype(np.float32) * 0.35).astype(np.uint8)
    bh = int(band.shape[0] * OUT_W / band.shape[1])
    big = cv2.resize(band, (OUT_W, bh), interpolation=cv2.INTER_CUBIC)
    y0 = (OUT_H - bh) // 2
    canvas = bg
    # soft edge between band and background
    mask = np.ones((bh, 1, 1), np.float32)
    e = 40
    ramp = np.linspace(0, 1, e, dtype=np.float32)[:, None, None]
    mask[:e] = ramp
    mask[-e:] = ramp[::-1]
    region = canvas[y0:y0 + bh].astype(np.float32)
    canvas[y0:y0 + bh] = (big * mask + region * (1 - mask)).astype(np.uint8)
    return canvas, y0, OUT_W / bw


def vignette_mask():
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    d = np.sqrt(((xx - OUT_W / 2) / (OUT_W * 0.75)) ** 2 + ((yy - OUT_H / 2) / (OUT_H * 0.6)) ** 2)
    return np.clip(1.15 - d * 0.55, 0.45, 1.0)[..., None]


# ---------------------------------------------------------------- effects
YY, XX = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)


def shake_affine(img, dx, dy, rot, zoom, cx, cy):
    M = cv2.getRotationMatrix2D((cx, cy), rot, zoom)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (OUT_W, OUT_H), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT101)


def zoom_blur(img, cx, cy, amount, steps=6):
    acc = img.astype(np.float32)
    for i in range(1, steps):
        z = 1 + amount * i / steps
        M = cv2.getRotationMatrix2D((cx, cy), 0, z)
        acc += cv2.warpAffine(img, M, (OUT_W, OUT_H), borderMode=cv2.BORDER_REFLECT101)
    return (acc / steps).astype(np.uint8)


def shockwave(img, cx, cy, rings):
    """rings: list of (radius, width, amplitude). Radial displacement + bright rim."""
    dx = XX - cx
    dy = YY - cy
    d = np.sqrt(dx * dx + dy * dy) + 1e-3
    disp = np.zeros_like(d)
    rim = np.zeros_like(d)
    for r, w, a in rings:
        g = (d - r) / w
        prof = np.exp(-g * g)
        disp += a * prof * np.tanh(g * 1.5) * -1
        rim += prof * min(1.0, a / 25.0)
    mx = XX + dx / d * disp
    my = YY + dy / d * disp
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
    out = out.astype(np.float32) + (rim[..., None] * 70.0)
    return np.clip(out, 0, 255).astype(np.uint8)


def chroma(img, cx, cy, amt):
    if amt < 0.5:
        return img
    b, g, r = cv2.split(img)

    def sc(ch, z):
        M = cv2.getRotationMatrix2D((cx, cy), 0, z)
        return cv2.warpAffine(ch, M, (OUT_W, OUT_H), borderMode=cv2.BORDER_REFLECT101)
    k = amt / 600.0
    return cv2.merge([sc(b, 1 - k), g, sc(r, 1 + k)])


def glow(img, cx, cy, strength, radius, color=(255, 245, 230)):
    d2 = ((XX - cx) ** 2 + (YY - cy) ** 2) / (radius * radius)
    m = np.exp(-d2)[..., None] * strength
    f = img.astype(np.float32)
    f = f + (np.array(color, np.float32) - f * 0.3) * m
    return np.clip(f, 0, 255).astype(np.uint8)


def flash(img, a):
    if a <= 0:
        return img
    return cv2.addWeighted(img, 1 - a, np.full_like(img, 255), a, 0)


def speed_lines(img, cx, cy, alpha, rng, color=255, n=90, inner=320):
    if alpha <= 0.02:
        return img
    layer = np.zeros((OUT_H, OUT_W), np.uint8)
    R = 2400
    for _ in range(n):
        ang = rng.uniform(0, 2 * math.pi)
        r0 = inner + rng.uniform(0, 420)
        wdt = rng.uniform(0.002, 0.009)
        p1 = (cx + math.cos(ang) * r0, cy + math.sin(ang) * r0)
        p2 = (cx + math.cos(ang - wdt) * R, cy + math.sin(ang - wdt) * R)
        p3 = (cx + math.cos(ang + wdt) * R, cy + math.sin(ang + wdt) * R)
        pts = np.array([p1, p2, p3], np.int32)
        cv2.fillConvexPoly(layer, pts, 255, lineType=cv2.LINE_AA)
    m = (layer.astype(np.float32) / 255.0 * alpha)[..., None]
    f = img.astype(np.float32)
    f = f * (1 - m) + color * m
    return f.astype(np.uint8)


def impact_frame(img, variant):
    """Classic anime impact frame: high-contrast ink, inverted / red."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.2)
    e = cv2.Canny(g.astype(np.uint8), 40, 110)
    t = np.clip((g - 95) * 4.0, 0, 255)
    ink = np.maximum(255 - t, e.astype(np.float32))      # dark shapes -> white-ish
    if variant == 0:
        out = np.dstack([ink, ink, ink])                  # white silhouettes on black
    else:
        inv = 255 - ink
        out = np.dstack([inv * 0.10, inv * 0.05, inv * 0.95 + 10])  # black ink on red
    return np.clip(out, 0, 255).astype(np.uint8)


class Particles:
    def __init__(self, cx, cy, s, rng, dirx):
        n_spark = 70 * s
        n_dust = 25 * s
        ang = rng.normal(0, 1.0, n_spark) * 0.9 + (0 if dirx >= 0 else math.pi)
        ang = np.where(rng.random(n_spark) < 0.35, rng.uniform(0, 2 * math.pi, n_spark), ang)
        sp = rng.uniform(12, 42, n_spark) * (0.7 + 0.15 * s)
        self.sp = np.stack([np.cos(ang) * sp, np.sin(ang) * sp], 1)
        self.slife = rng.uniform(8, 22, n_spark)
        ang2 = rng.uniform(0, 2 * math.pi, n_dust)
        sp2 = rng.uniform(4, 14, n_dust)
        self.dp = np.stack([np.cos(ang2) * sp2, np.sin(ang2) * sp2], 1)
        self.dsize = rng.uniform(6, 22, n_dust)
        self.dlife = rng.uniform(14, 34, n_dust)
        self.c = np.array([cx, cy], np.float32)

    def draw(self, img, t):
        if t < 0:
            return img
        f = img.astype(np.float32)
        add = np.zeros((OUT_H, OUT_W), np.float32)
        drag = (1 - 0.9 ** t) / 0.1
        for v, life in zip(self.sp, self.slife):
            if t > life:
                continue
            p = self.c + v * drag + np.array([0, 0.35 * t * t])
            vel = v * (0.9 ** t) + np.array([0, 0.7 * t])
            tail = p - vel * 1.6
            k = 1 - t / life
            cv2.line(add, tuple(np.int32(tail)), tuple(np.int32(p)), 255 * k, 2 + int(2 * k),
                     lineType=cv2.LINE_AA)
        dust = np.zeros((OUT_H, OUT_W), np.float32)
        dr = (1 - 0.88 ** t) / 0.12
        for v, sz, life in zip(self.dp, self.dsize, self.dlife):
            if t > life:
                continue
            p = self.c + v * dr + np.array([0, 0.12 * t * t])
            k = 1 - t / life
            cv2.circle(dust, tuple(np.int32(p)), int(sz * (1 + t / 12)), 160 * k, -1,
                       lineType=cv2.LINE_AA)
        dust = cv2.GaussianBlur(dust, (0, 0), 7)
        glowl = cv2.GaussianBlur(add, (0, 0), 5)
        spark = np.dstack([add * 0.75 + glowl * 0.3, add * 0.92 + glowl * 0.6, add + glowl * 0.95])
        f = f * (1 - dust[..., None] / 400) + dust[..., None] * 0.55
        f = f + spark
        return np.clip(f, 0, 255).astype(np.uint8)


def text_pop(img, word, cx, cy, age, rng_seed):
    if age < 1 or age > 34:
        return img
    if age < 5:
        sc = 0.4 + 0.8 * (age / 5) ** 0.5 * 1.15
    else:
        sc = 1.2 - 0.12 * min(1, (age - 5) / 6)
    alpha = 1.0 if age < 26 else 1 - (age - 26) / 8
    size = int(150 * sc)
    font = ImageFont.truetype(FONT, size)
    pad = 40
    tmp = Image.new("RGBA", (size * len(word) + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((pad, pad), word, font=font, fill=(255, 236, 120, 255),
           stroke_width=max(6, size // 14), stroke_fill=(20, 0, 0, 255))
    rng = np.random.default_rng(rng_seed)
    tmp = tmp.rotate(float(rng.uniform(-14, 8)), expand=True, resample=Image.BICUBIC)
    bb = tmp.getbbox()
    if bb:
        tmp = tmp.crop(bb)
    jit = (rng.integers(-6, 7), rng.integers(-6, 7)) if age < 8 else (0, 0)
    w, h = tmp.size
    x = int(np.clip(cx - w / 2 + jit[0], 10, OUT_W - w - 10))
    y = int(np.clip(cy - h / 2 + jit[1], 10, OUT_H - h - 10))
    arr = np.asarray(tmp).astype(np.float32)
    a = arr[..., 3:4] / 255.0 * alpha
    reg = img[y:y + h, x:x + w].astype(np.float32)
    rgb = arr[..., :3][..., ::-1]
    img[y:y + h, x:x + w] = (reg * (1 - a) + rgb * a).astype(np.uint8)
    return img


# ---------------------------------------------------------------- audio
def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def reverb(x, secs=1.4, mix=0.35, seed=1):
    rng = np.random.default_rng(seed)
    n = int(SR * secs)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir = signal.sosfilt(signal.butter(2, 3500, "low", fs=SR, output="sos"), ir)
    ir /= np.abs(ir).sum() / 6
    wet = signal.fftconvolve(x, ir)
    out = np.zeros(len(wet))
    out[: len(x)] += x
    return out * (1 - mix) + wet * mix


def sfx_impact(s, seed):
    rng = np.random.default_rng(seed)
    dur = 0.9 + 0.3 * s
    t = np.arange(int(SR * dur)) / SR
    f = 45 + 110 * np.exp(-t / 0.08)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.25 + 0.08 * s))
    noise = rng.normal(0, 1, len(t))
    crack = signal.sosfilt(signal.butter(2, 2500, "high", fs=SR, output="sos"), noise) * np.exp(-t / 0.018)
    thump = signal.sosfilt(signal.butter(2, 500, "low", fs=SR, output="sos"), noise) * np.exp(-t / 0.07)
    x = sub * 1.0 + crack * 0.55 + thump * 1.4
    x = np.tanh(x * 1.6)
    x = reverb(x, 1.2 + 0.3 * s, 0.25 + 0.05 * s, seed)
    return x / np.abs(x).max() * (0.55 + 0.15 * s)


def sfx_whoosh(dur, seed):
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    noise = rng.normal(0, 1, n)
    f, tt, Z = signal.stft(noise, SR, nperseg=1024)
    prog = np.linspace(0, 1, Z.shape[1])
    centre = 300 + 2600 * prog ** 2
    shape = np.exp(-((f[:, None] - centre[None, :]) / (400 + 900 * prog[None, :])) ** 2)
    _, y = signal.istft(Z * shape, SR, nperseg=1024)
    y = y[:n]
    env = np.linspace(0, 1, n) ** 2.2
    y = y * env
    return y / (np.abs(y).max() + 1e-9) * 0.35


def sfx_rumble(dur, seed):
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = signal.sosfilt(signal.butter(2, 90, "low", fs=SR, output="sos"), rng.normal(0, 1, n))
    x = noise / (np.abs(noise).max() + 1e-9) * 0.6 + np.sin(2 * np.pi * 38 * t) * 0.3
    env = np.minimum(1, t / 0.05) * np.exp(-t / (dur * 0.5))
    return x * env * 0.5


def build_audio(src_audio, timeline, hit_out, hits, n_out):
    srcpos = np.array([p for p, _ in timeline], np.float64)
    speed = np.diff(srcpos, append=srcpos[-1] + 1)
    total = int(n_out / FPS * SR)
    tau = np.arange(total) / SR * FPS
    sframe = np.interp(tau, np.arange(n_out), srcpos)
    spd = np.interp(tau, np.arange(n_out), speed)
    sidx = sframe / FPS * SR
    i0 = np.clip(sidx.astype(np.int64), 0, len(src_audio) - 2)
    fr = (sidx - i0)[:, None]
    base = src_audio[i0] * (1 - fr) + src_audio[i0 + 1] * fr
    gain = np.clip(spd / 0.12, 0, 1) * (0.55 + 0.45 * np.clip(spd, 0, 1))
    base = base * gain[:, None]
    # slow parts sound muffled
    lp = signal.sosfiltfilt(signal.butter(2, 900, "low", fs=SR, output="sos"), base, axis=0)
    slow = np.clip((1 - spd) / 0.5, 0, 1)[:, None]
    slow = signal.sosfiltfilt(signal.butter(1, 4, "low", fs=SR, output="sos"), slow, axis=0)
    base = base * (1 - slow) + lp * slow
    base = signal.sosfilt(signal.butter(1, 25, "high", fs=SR, output="sos"), base, axis=0)

    fx = np.zeros(total + SR * 3)
    for i, (h, k) in enumerate(zip(hits, hit_out)):
        at = int(k / FPS * SR)
        s = h["s"]
        imp = sfx_impact(s, 100 + i)
        fx[at:at + len(imp)] += imp
        if s >= 2:
            w = sfx_whoosh(0.35 + 0.1 * s, 200 + i)
            st = max(0, at - len(w))
            fx[st:at] += w[len(w) - (at - st):]
            r = sfx_rumble(1.2 + 0.4 * s, 300 + i)
            fx[at:at + len(r)] += r
    fx = fx[:total]
    mix = base * 0.8 + fx[:, None] * np.array([[1.0, 1.0]])
    peak = np.abs(mix).max()
    mix = np.tanh(mix / peak * 1.3) * 0.95
    fade = int(SR * 1.0)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return mix.astype(np.float32)


# ---------------------------------------------------------------- main
def main():
    cfg_path, src, dst = sys.argv[1:4]
    preview = None
    if "--preview" in sys.argv:
        preview = int(sys.argv[sys.argv.index("--preview") + 1])
    cfg = json.load(open(cfg_path))
    y0, y1 = cfg["band"]
    hits = cfg["hits"]
    frames = read_frames(src, y0, y1)
    n = len(frames)
    bw = frames[0].shape[1]
    cuts = detect_cuts(frames)
    extra = [tuple(e) for e in cfg.get("extra_slow", [])]
    timeline, hit_out, hits = build_timeline(n, hits, extra)
    n_out = len(timeline)
    print(f"source {n} frames -> output {n_out} frames ({n_out / FPS:.1f}s); cuts {sorted(cuts)}")

    interp = Interp(frames, cuts)
    vig = vignette_mask()
    master = np.random.default_rng(7)
    parts = {}
    rngs = {i: np.random.default_rng(1000 + i) for i in range(len(hits))}

    audio = build_audio(load_audio(src), timeline, hit_out, hits, n_out)
    wav = dst + ".wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                    "-i", "-", wav], input=audio.tobytes(), check=True)

    rng_frames = range(n_out)
    if preview is not None:
        k = hit_out[preview]
        rng_frames = range(max(0, k - 20), min(n_out, k + 50))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
         *(["-ss", f"{rng_frames.start / FPS:.4f}", "-i", wav] if True else []),
         "-map", "0:v", "-map", "1:a", "-shortest",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst],
        stdin=subprocess.PIPE)

    srcpos = [p for p, _ in timeline]
    for k in rng_frames:
        pos, frozen = timeline[k]
        spd = (srcpos[k + 1] - pos) if k + 1 < n_out else 1.0
        slow = float(np.clip((1 - spd) / 0.6, 0, 1)) if not frozen else 1.0
        band = interp.get(pos)
        band = grade(band, slow)
        img, by0, sc = compose(band, bw)

        # nearest active hit
        act = None
        for i, (h, ko) in enumerate(zip(hits, hit_out)):
            age = k - ko
            if -12 <= age <= 45:
                if act is None or abs(age) < abs(act[2]):
                    act = (i, h, age)
        if act is not None:
            i, h, age = act
            s = h["s"]
            Z = PROFILE[s]["Z"]
            cx = h["x"] * sc
            cy = by0 + h["y"] * sc
            r = rngs[i]
            # camera: push-in before, kick + shake after
            zoom = 1.0
            dx = dy = rot = 0.0
            if age < 0:
                zoom = 1 + 0.06 * s / 3 * (1 + age / 12)
            else:
                decay = math.exp(-age / (5 + 2 * s))
                amp = 14 * s * decay
                dx = master.normal(0, amp)
                dy = master.normal(0, amp)
                rot = master.normal(0, 0.5 * s * decay)
                zoom = 1 + (0.06 * s / 3) * math.exp(-age / 10) + 0.05 * s / 3 * decay
            img = shake_affine(img, dx, dy, rot, zoom, cx, cy)
            # zoom blur on the hit
            if 0 <= age < 3 + s:
                img = zoom_blur(img, cx, cy, 0.05 * s * (1 - age / (3 + s)))
            # shockwaves
            if age >= 0 and s >= 1:
                rings = []
                for delay, spd_r, a0 in ((0, 70, 26), (3, 55, 18), (7, 45, 12))[: s]:
                    t = age - delay
                    if 0 <= t < 22:
                        rad = 40 + spd_r * t * (1 + 0.25 * s) / (1 + t * 0.04)
                        rings.append((rad, 28 + 3 * t, a0 * s / 2 * (1 - t / 22)))
                if rings:
                    img = shockwave(img, cx, cy, rings)
            # air pressure haze around impact
            if 0 <= age < 18 and s >= 2:
                hx = cv2.resize(master.normal(0, 1, (48, 27)).astype(np.float32), (OUT_W, OUT_H))
                hy = cv2.resize(master.normal(0, 1, (48, 27)).astype(np.float32), (OUT_W, OUT_H))
                fall = np.exp(-((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * 380.0 ** 2))
                a = 7 * s * (1 - age / 18)
                img = cv2.remap(img, XX + hx * a * fall, YY + hy * a * fall, cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT101)
            # impact frames (ink) on the first frozen frames
            if s >= 2 and age in (0, 1):
                img = impact_frame(img, age)
                img = speed_lines(img, cx, cy, 0.95, np.random.default_rng(k), 0,
                                  n=120, inner=200)
            # chromatic aberration
            if 2 <= age < 12 or (s == 1 and 0 <= age < 10):
                img = chroma(img, cx, cy, 10 * s * (1 - age / 10))
            # glow + flash
            if age >= (2 if s >= 2 else 0):
                img = glow(img, cx, cy, 0.8 * math.exp(-(age - 2) / 4), 120 + 45 * s)
            if Z <= age < Z + 3:
                img = flash(img, (0.3 if s == 3 else 0.18) * (1 - (age - Z) / 3))
            elif s == 1 and age < 2:
                img = flash(img, 0.4 * (1 - age / 2))
            # speed lines
            if s >= 2 and -6 <= age < 14 and age not in (0, 1):
                if age < 0:
                    al = 0.18 * (1 + age / 6)
                elif age < 6:
                    al = 0.38
                else:
                    al = 0.38 * (1 - (age - 6) / 8)
                img = speed_lines(img, cx, cy, al, np.random.default_rng(k * 7 + i), 255,
                                  n=60 + 20 * s)
            # particles
            if age >= 1:
                if i not in parts:
                    parts[i] = Particles(cx, cy, s, np.random.default_rng(500 + i),
                                         h.get("dir", 1))
                img = parts[i].draw(img, age)
            # onomatopoeia
            if h.get("word") and age > 0:
                img = text_pop(img, h["word"], cx + h.get("tx", 0), cy + h.get("ty", -260),
                               age, 900 + i)
        img = (img.astype(np.float32) * vig).astype(np.uint8)
        # fade in/out
        if k < 8:
            img = (img * (k / 8)).astype(np.uint8)
        if k > n_out - 30:
            img = (img * max(0.0, (n_out - k) / 30)).astype(np.uint8)
        enc.stdin.write(img.tobytes())
        if k % 100 == 0:
            print("frame", k, "/", n_out, flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()

"""Обложка для YouTube (1280x720, JPG): кадр из сцены без субтитров + крупный заголовок и значок серии.

В episode.yaml:
    thumbnail:
      scene: 05_teamwork      # из какой сцены кадр
      t: 3.2                  # секунда сцены
      title: ["THE BIG", "RED APPLE!"]   # 1–2 строки крупного текста
      color: "#FFD93D"        # цвет заголовка
      side: left              # где текст: left | right
      episode: 1              # номер в значке
      zoom: 1.0               # дополнительное приближение кадра (кроп от центра персонажей)
"""

import numpy as np
import skia
from PIL import Image

from . import config, skx
from .render import build_scene, load_episode

TW, TH = 1280, 720


def render_thumbnail(name):
    ep_dir, spec, files = load_episode(name)
    th = spec.get("thumbnail")
    if not th:
        raise ValueError(f"В {ep_dir.name}/episode.yaml нет раздела thumbnail")
    match = [f for f in files if f.stem == th["scene"]]
    if not match:
        raise ValueError(f"Нет сцены {th['scene']}")
    scene = build_scene(ep_dir, spec, match[0], False)
    scene.spec["subtitles"] = False
    scene.fade_in = scene.fade_out = 0
    fps = spec.get("fps", config.FPS)
    t = float(th["t"])
    for i in range(int(t * fps)):
        for a in scene.actors:
            a.pose(i / fps)
    frame = scene.frame(int(t * fps) / fps)

    img = skia.Image.fromarray(np.ascontiguousarray(np.dstack([frame, np.full(frame.shape[:2], 255, np.uint8)])),
                               colorType=skia.kRGBA_8888_ColorType)
    surf = skia.Surface(config.W, config.H)
    c = surf.getCanvas()
    z = float(th.get("zoom", 1.0))
    fx, fy = th.get("focus", [config.W / 2, config.H / 2])
    # кроп не выходит за край кадра
    hx, hy = config.W / (2 * z), config.H / (2 * z)
    fx, fy = min(max(fx, hx), config.W - hx), min(max(fy, hy), config.H - hy)
    c.save()
    c.translate(config.W / 2, config.H / 2)
    c.scale(z, z)
    c.translate(-fx, -fy)
    c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear))
    c.restore()

    side = th.get("side", "left")
    lines = th.get("title", [spec.get("title", "")])
    if isinstance(lines, str):
        lines = [lines]
    color = th.get("color", "#FFD93D")
    # подложка под текст, чтобы читался на маленьком превью
    gx0, gx1 = (0, config.W * 0.62) if side == "left" else (config.W, config.W * 0.38)
    c.drawRect(skia.Rect(0, 0, config.W, config.H),
               skx.fill("#000", shader=skx.linear((gx0, 0), (gx1, 0), ["#140A2A", "#140A2A"], [0, 1], [0.55, 0])))
    size = 190 if max(len(s) for s in lines) <= 9 else 150
    x = 70 if side == "left" else config.W - 70
    align = "left"
    y0 = config.H * 0.40 - (len(lines) - 1) * size * 0.5
    for i, s in enumerate(lines):
        w = skx.text_width(s, size)
        xx = x if side == "left" else x - w
        y = y0 + i * size * 1.02
        font = skia.Font(skx.typeface(True), size)
        blob = skia.TextBlob.MakeFromString(s, font)
        c.drawTextBlob(blob, xx + 10, y + 14, skx.fill("#140A2A", 0.6, blur=6))  # тень
        c.drawTextBlob(blob, xx, y, skx.stroke("#1B0E33", 30))
        c.drawTextBlob(blob, xx, y, skx.fill("#000", shader=skx.linear((0, y - size * 0.8), (0, y), ["#FFFFFF", color], [0, 0.55])))
        skx.text(c, s, xx, y, size, "#00000000", "#FFFFFF", 4, align=align, a=0.0)
    # значок серии и название шоу
    ep = th.get("episode")
    bx = 60 if side == "left" else config.W - 60 - 330
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, 54, 330, 92), 46, 46), skx.fill("#E5383B"))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, 54, 330, 92), 46, 46), skx.stroke("#FFFFFF", 6))
    skx.text(c, f"EPISODE {ep}" if ep else "TOSHA & BUSYA", bx + 165, 118, 50, "#FFFFFF", "#7A1020", 6)
    show = "Tosha & Busya"
    sy = y0 + len(lines) * size * 1.02 + 30
    sx = x if side == "left" else x - skx.text_width(show, 70)
    skx.text(c, show, sx, sy, 70, "#FFFFFF", "#1B0E33", 14, align="left")

    arr = skx.surface_to_rgb(surf)
    out_dir = config.OUTPUT_DIR / ep_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{ep_dir.name}_thumbnail.jpg"
    Image.fromarray(arr).resize((TW, TH), Image.LANCZOS).save(out, quality=92, optimize=True)
    print(f"✔ {out}  ({out.stat().st_size // 1024} КБ)")
    return out

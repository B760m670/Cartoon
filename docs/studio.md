# Движок studio — 2D в аниме-стиле

`python -m studio render <эпизод>` — Full HD, `--preview` — 960×540 быстро, `still <эп> <сцена> <сек>` — кадр в PNG.

## Что умеет
- **Персонажи** (`studio/critter.py`): один риг для всех зверьков. Cel-shading (тени в 2 тона, блики, цветной контур),
  объёмный поворот головы (черты лица лежат на «сфере»), аниме-глаза с бликами, брови и рот по настроению,
  липсинк по громкости голоса, моргание, дыхание, пружинные уши/хвост, походка `walk` или прыжками `hop`.
- **Локации** (`locations/<id>/location.py`): слои с параллаксом, размытие дальних планов, облака, солнечные лучи, пыльца.
- **Камера**: панорама, зум, тряска (`shake`) по ключевым кадрам.
- **Пост**: цветокоррекция, bloom, виньетка, затемнения.
- **Звук**: голоса Kokoro (бесплатная нейросеть TTS на CPU, модели скачиваются в `models/` автоматически),
  звуковые эффекты, процедурная музыка с приглушением под голоса.

## Персонаж — `characters/<id>/character.yaml`
```yaml
name: Tosha
ears: round          # round | long | pointy
snout: bear          # bear | bunny | fox
tail: stub           # stub | puff | fluffy
fur: "#C98349"       # основной цвет; fur2 — животик/мордочка; inner_ear, eye, eye2, nose, cheek
head_r: 112          # размеры головы и тела
body_w: 92
body_h: 98
accessory: {type: scarf, color: "#2F6FE0"}   # scarf | bow
voice: {kokoro: am_puck, pitch: 1.12, speed: 1.0}
gait: walk           # walk | hop
```

## Сцена — `episodes/<эп>/scenes/*.yaml`
```yaml
location: meadow
duration: 8                       # без него — по последней реплике + 1 с
camera:  [{t: 0, x: 960, y: 540, zoom: 1.0}, {t: 8, x: 1100, zoom: 1.2, ease: in_out}]
props:   [{type: apple, id: apple, start: {x: 1400, y: 228, scale: 1.25, sparkle: 1}, keys: [...]}]
sounds:  [{t: 3.0, kind: pop}]    # blip | boing | pop | chime | whoosh
actors:
  - character: tosha
    start: {x: 160, y: 950, turn: 0.35, mood: happy}
    keys:                         # любые поля позы: x y lift scale turn tilt lean look_x look_y blush squash z facing mood arm_l arm_r
      - {t: 3.4, x: 860, ease: out}
    actions:
      - {t: 1.2, do: say, text: "What a beautiful day!"}   # голос + липсинк + субтитры
      - {t: 4.0, do: jump, height: 160, duration: 1.0}
      - {t: 5.0, do: wave, duration: 1.2}
      - {t: 6.0, do: reach, duration: 1.3}                 # тянется вверх (руки вытягиваются)
      - {t: 7.0, do: mood, mood: sad}                      # happy neutral sad surprised angry excited
      - {t: 7.5, do: close_eyes, duration: 0.8}
```
Заставка: `type: title`, `text`, `subtitle` поверх локации.

## Скорость
4 ядра без видеокарты: ~0,2 с на кадр Full HD, серия 45 с — около 2 минут.

## Night scenes (added in episode 2)

- `actor_tint: {color: "#5868B8", alpha: 0.4}` puts moonlight on the characters: each actor is multiplied by a colour mixed between white and `color`.
- `fireflies` prop: `start`/`keys` take `x, y, amount (0–1), radius, rise (0–1, flies up and away), z`. Glow uses additive blending.
- Location `night_meadow`: moon at (520, 190), twinkling stars, drifting haze.
- `close_eyes` with a full blink now draws calm closed-eye arcs.

## Rain, puddles, rainbow (added in episode 3)

- Scene `env: {start: {rain: 1}, keys: [{t: 4, rain: 0, clear: 0.7}]}` animates location state. `rainy_meadow` reads `rain` and `clear`; `meadow` reads `rainbow` (0–1) and `rain`.
- `puddle` prop: `splash` 0→1 keyed over ~0.8 s throws droplets; `sky` sets the reflection colour.
- `leaf` prop: a big leaf umbrella. `follow: tosha` makes `x, y` an offset from the character's feet, including jumps.
- Sounds: `{kind: rain, dur: 8, volume: 0.5}` and `{kind: splash}`.

## YouTube thumbnails

Add to `episode.yaml`:

```yaml
thumbnail: {scene: 04_puddles, t: 2.7, title: ["RAINY", "DAY!"], color: "#6FC3FF", side: right, episode: 3, zoom: 1.1, focus: [820, 600]}
```

`python -m studio thumbnail 003_rainy_day` writes `output/<ep>/<ep>_thumbnail.jpg` (1280×720, ~130 KB). It uses a frame without subtitles, crops with `zoom`/`focus` and adds the title, the episode badge and the show name. Put the title on the side away from the characters.

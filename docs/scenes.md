# Формат эпизодов и сцен

## episode.yaml

```yaml
title: "Знакомство"
fps: 24
width: 1280
height: 720
scenes: [01_zastavka.yaml, 02_vstrecha.yaml]   # без списка — все scenes/*.yaml по алфавиту
music: theme.mp3        # необязательно, файл из assets/audio
music_volume: 0.3
```

## Сцена-заставка

```yaml
type: title
duration: 3
background: {type: solid, color: "#7E57C2"}
text: "Круг и Квадрат"
subtitle: "серия 0"
text_color: "#FFFFFF"
```

## Обычная сцена

```yaml
duration: 9                 # секунды
background: {type: meadow, clouds: 5, seed: 11}
fade_in: 0.4                # затемнение в начале/конце (0 — без него)
fade_out: 0.4
tint: {color: "#0B1033", opacity: 0.3}   # светофильтр (ночь, закат)

camera:                     # необязательно
  - {t: 0, zoom: 1.0, x: 640, y: 360}
  - {t: 3, zoom: 1.5, x: 640, y: 470, ease: in_out}

captions:                   # субтитры внизу
  - {t: 1, text: "Однажды на лугу…", duration: 2}

sounds:                     # дополнительные звуки
  - {t: 2, kind: whoosh}    # blip | boing | pop | chime | whoosh

actors:
  - character: krug         # папка в characters/
    id: krug1               # нужно, только если один персонаж дважды в сцене
    mood: happy             # начальная эмоция
    start: {x: -120, y: 610, scale: 1.0}
    keyframes:              # движение; ходьба анимируется автоматически
      - {t: 0.3, x: -120}
      - {t: 2.0, x: 440, ease: out}
    actions:
      - {t: 2.1, type: wave, duration: 1.2}
      - {t: 2.2, type: say, text: "Привет!"}          # duration считается сама
      - {t: 6.0, type: jump, height: 110, duration: 0.6}
      - {t: 7.0, type: mood, mood: sad}
```

### Координаты
Холст 1280×720: `x` слева направо, `y` сверху вниз. `y` актёра — линия земли под
ногами (на лугу земля начинается с ~470, удобно 580–650).

### Свойства в keyframes
`x`, `y`, `scale`, `facing` (1 — вправо, -1 — влево; иначе смотрит по ходу движения), `mood`.

### Easing
`linear`, `in`, `out`, `in_out` (по умолчанию), `back`, `bounce`, `elastic`.

### Эмоции
`happy`, `neutral`, `sad`, `surprised`, `angry`.

### Фоны
| type | параметры |
|---|---|
| `solid` | `color` |
| `meadow` | `sky_top`, `sky_bottom`, `ground`, `horizon`, `sun`, `clouds`, `cloud_speed`, `flowers`, `seed` |
| `night` | `sky_top`, `sky_bottom`, `ground`, `stars`, `moon_x`, `moon_y` |
| `image` | `file` — из `assets/backgrounds/` |

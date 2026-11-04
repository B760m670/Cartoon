# Cartoon — мультики из текстовых сценариев

Мультик описывается текстом (YAML): кто из персонажей где стоит, куда идёт,
что говорит, когда прыгает. Движок рисует кадры (Python + Pillow), синтезирует
звуки и собирает всё в **MP4-видео** через ffmpeg.

## Два движка

- **studio** — основной: 2D в аниме-стиле, Full HD, английская озвучка, музыка. См. [docs/studio.md](docs/studio.md).
  `python -m studio render 001_big_red_apple`
- **cartoon** — простой движок для быстрых набросков (фигурки, YAML), описан ниже.

## Быстрый старт (cartoon)

```bash
pip install -r requirements.txt          # + нужен ffmpeg в системе
python -m cartoon list                   # эпизоды и персонажи
python -m cartoon render 000_test        # → output/000_test/000_test.mp4
python -m cartoon render 000_test --preview          # быстро, в половинном размере
python -m cartoon render 000_test -s 02_vstrecha     # только одна сцена
python -m cartoon still 000_test 02_vstrecha 3.5     # один кадр → PNG
python -m cartoon new 001_moy_multik                 # новый эпизод из шаблона
python -m unittest discover tests                    # проверка пайплайна
```

## Структура

| Папка | Что внутри |
|---|---|
| `episodes/<id>/` | Эпизод: `story.md` (сюжет), `episode.yaml` (настройки), `scenes/*.yaml` (сцены) |
| `characters/<id>/` | Персонаж: `character.yaml` (внешность и голос), `bio.md` (характер) |
| `locations/<id>/` | Локации движка studio: слои фона с параллаксом (`location.py`) |
| `studio/` | Движок studio (аниме-2D) |
| `models/` | Скачанные модели голосов (не в git) |
| `assets/backgrounds/` | Картинки для фонов `type: image` |
| `assets/audio/` | Музыка для эпизодов |
| `assets/fonts/` | Свои шрифты (если пусто — системный DejaVu) |
| `templates/episode/` | Шаблон для `python -m cartoon new` |
| `cartoon/` | Движок рендера (код) |
| `docs/` | Документация по форматам |
| `tests/` | Автотесты |
| `output/` | Готовые видео и кадры (не хранятся в git) |

## Документация

- [docs/pipeline.md](docs/pipeline.md) — как устроен рендер, из каких модулей
- [docs/scenes.md](docs/scenes.md) — формат эпизодов и сцен (фоны, действия, камера)
- [docs/characters.md](docs/characters.md) — как описать нового персонажа

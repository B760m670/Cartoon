"""Командная строка.

  python -m cartoon list                         — эпизоды и персонажи
  python -m cartoon render 000_test              — отрендерить эпизод целиком
  python -m cartoon render 000_test --preview    — быстрое превью (половина разрешения)
  python -m cartoon render 000_test -s 02_vstrecha  — только одна сцена
  python -m cartoon still 000_test 02_vstrecha 3.5 — один кадр в PNG
  python -m cartoon new 001_moy_multik           — новый эпизод из шаблона
"""

import argparse
import shutil
import sys

from . import config
from .loader import load_characters, load_episode
from .render import render_episode, render_still


def cmd_list(_args):
    print("Эпизоды:")
    for d in sorted(config.EPISODES_DIR.iterdir()):
        if (d / "episode.yaml").exists():
            ep = load_episode(str(d))
            print(f"  {ep.id:<24} {ep.title}  ({len(ep.scene_files)} сцен)")
    print("Персонажи:")
    for cid, ch in load_characters().items():
        print(f"  {cid:<24} {ch.name}")


def cmd_render(args):
    render_episode(args.episode, only=args.scene, preview=args.preview, jobs=args.jobs)


def cmd_still(args):
    render_still(args.episode, args.scene, args.time)


def cmd_new(args):
    dst = config.EPISODES_DIR / args.name
    if dst.exists():
        sys.exit(f"Эпизод {args.name} уже существует")
    shutil.copytree(config.TEMPLATES_DIR / "episode", dst)
    print(f"✔ Создан {dst}. Отредактируйте story.md, episode.yaml и scenes/*.yaml")


def main(argv=None):
    p = argparse.ArgumentParser(prog="cartoon", description="Рендер мультиков из YAML-сценариев")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="список эпизодов и персонажей").set_defaults(func=cmd_list)

    r = sub.add_parser("render", help="отрендерить эпизод в MP4")
    r.add_argument("episode")
    r.add_argument("-s", "--scene", action="append", help="только эти сцены (можно несколько)")
    r.add_argument("--preview", action="store_true", help="быстро и в половинном разрешении")
    r.add_argument("-j", "--jobs", type=int, help="сколько сцен рендерить параллельно")
    r.set_defaults(func=cmd_render)

    s = sub.add_parser("still", help="один кадр сцены в PNG")
    s.add_argument("episode")
    s.add_argument("scene")
    s.add_argument("time", type=float)
    s.set_defaults(func=cmd_still)

    n = sub.add_parser("new", help="создать эпизод из шаблона")
    n.add_argument("name")
    n.set_defaults(func=cmd_new)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

"""Движок studio — 2D в аниме-стиле.

  python -m studio render 001_big_red_apple            — эпизод целиком (Full HD)
  python -m studio render 001_big_red_apple --preview  — быстро, 960x540
  python -m studio render 001_big_red_apple -s 02_the_apple
  python -m studio still 001_big_red_apple 02_the_apple 3.5   — кадр в PNG
  python -m studio thumbnail 001_big_red_apple         — обложка YouTube 1280x720 (раздел thumbnail в episode.yaml)
"""

import argparse

from .render import render_episode, render_still


def main(argv=None):
    p = argparse.ArgumentParser(prog="studio")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("episode")
    r.add_argument("-s", "--scene", action="append")
    r.add_argument("--preview", action="store_true")
    r.add_argument("-j", "--jobs", type=int)
    s = sub.add_parser("still")
    s.add_argument("episode")
    s.add_argument("scene")
    s.add_argument("time", type=float)
    s.add_argument("--preview", action="store_true")
    th = sub.add_parser("thumbnail")
    th.add_argument("episode", nargs="+")
    a = p.parse_args(argv)
    if a.cmd == "thumbnail":
        from .thumbnail import render_thumbnail
        for e in a.episode:
            render_thumbnail(e)
        return
    if a.cmd == "render":
        render_episode(a.episode, a.scene, a.preview, a.jobs)
    else:
        render_still(a.episode, a.scene, a.time, a.preview)


if __name__ == "__main__":
    main()

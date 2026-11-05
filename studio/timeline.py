"""Ключевые кадры с поддержкой чисел, списков (углы рук) и дискретных значений."""

from cartoon import easing


def _lerp(a, b, p):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * p
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return tuple(x + (y - x) * p for x, y in zip(a, b))
    return a if p < 1 else b  # строки/флаги переключаются в конце перехода


class Track:
    def __init__(self, keys: list[dict], defaults: dict):
        self.defaults = dict(defaults)
        self.props: dict[str, list] = {}
        for k in sorted(keys or [], key=lambda k: float(k.get("t", 0))):
            for prop, v in k.items():
                if prop in ("t", "ease"):
                    continue
                if isinstance(v, list):
                    v = tuple(v)
                self.props.setdefault(prop, []).append((float(k.get("t", 0)), v, k.get("ease")))

    def value(self, prop, t):
        pts = self.props.get(prop)
        if not pts:
            return self.defaults.get(prop)
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]
        for (t0, v0, _), (t1, v1, ease) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                p = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return _lerp(v0, v1, easing.get(ease)(p))
        return pts[-1][1]

    def has(self, prop):
        return prop in self.props

    def state(self, t):
        return {p: self.value(p, t) for p in set(self.defaults) | set(self.props)}

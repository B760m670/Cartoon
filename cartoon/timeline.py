"""Ключевые кадры: интерполяция свойств актёра во времени."""

from . import easing


class Track:
    """Набор ключевых кадров вида {t: 1.0, x: 100, y: 500, ease: in_out}.

    Каждое свойство интерполируется независимо: ключ может задавать
    только часть свойств. `ease` описывает переход *к* этому ключу.
    """

    def __init__(self, keyframes: list[dict], defaults: dict):
        self.keys = sorted(keyframes, key=lambda k: float(k.get("t", 0)))
        self.defaults = defaults
        self._by_prop: dict[str, list[tuple[float, float, str | None]]] = {}
        for k in self.keys:
            for prop, value in k.items():
                if prop in ("t", "ease"):
                    continue
                self._by_prop.setdefault(prop, []).append(
                    (float(k.get("t", 0)), value, k.get("ease"))
                )

    def value(self, prop: str, t: float):
        points = self._by_prop.get(prop)
        if not points:
            return self.defaults.get(prop)
        if t <= points[0][0]:
            return points[0][1]
        if t >= points[-1][0]:
            return points[-1][1]
        for (t0, v0, _), (t1, v1, ease) in zip(points, points[1:]):
            if t0 <= t <= t1:
                if not isinstance(v0, (int, float)) or not isinstance(v1, (int, float)):
                    return v0  # нечисловые значения (например, facing) переключаются скачком
                p = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return v0 + (v1 - v0) * easing.get(ease)(p)
        return points[-1][1]

    def state(self, t: float) -> dict:
        props = set(self.defaults) | set(self._by_prop)
        return {p: self.value(p, t) for p in props}

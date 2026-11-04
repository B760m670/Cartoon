"""Функции плавности (easing) для анимации. Принимают и возвращают 0..1."""

import math


def linear(p: float) -> float:
    return p


def ease_in(p: float) -> float:
    return p * p


def ease_out(p: float) -> float:
    return 1 - (1 - p) * (1 - p)


def ease_in_out(p: float) -> float:
    return 3 * p * p - 2 * p * p * p


def back_out(p: float) -> float:
    """Перелёт с возвратом — мультяшная «пружинка»."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def bounce_out(p: float) -> float:
    n1, d1 = 7.5625, 2.75
    if p < 1 / d1:
        return n1 * p * p
    if p < 2 / d1:
        p -= 1.5 / d1
        return n1 * p * p + 0.75
    if p < 2.5 / d1:
        p -= 2.25 / d1
        return n1 * p * p + 0.9375
    p -= 2.625 / d1
    return n1 * p * p + 0.984375


def elastic_out(p: float) -> float:
    if p in (0, 1):
        return p
    return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi) / 3) + 1


EASINGS = {
    "linear": linear,
    "in": ease_in,
    "out": ease_out,
    "in_out": ease_in_out,
    "back": back_out,
    "bounce": bounce_out,
    "elastic": elastic_out,
}


def get(name: str | None):
    if not name:
        return ease_in_out
    try:
        return EASINGS[name]
    except KeyError:
        raise ValueError(f"Неизвестный easing '{name}'. Доступны: {', '.join(EASINGS)}")

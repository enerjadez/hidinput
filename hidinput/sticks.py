"""Stick / trigger shaping: deadzone, anti-deadzone, response curves, hair triggers."""

from __future__ import annotations

import math
from dataclasses import dataclass


def byte_to_axis(value: int, invert: bool = False) -> float:
    # DualSense: 0 left/up, 128 center, 255 right/down
    v = (value - 128) / 127.0 if value >= 128 else (value - 128) / 128.0
    v = max(-1.0, min(1.0, v))
    return -v if invert else v


def trigger_to_unit(value: int) -> float:
    return max(0.0, min(1.0, value / 255.0))


def apply_curve(magnitude: float, curve: str, exp: float = 1.4) -> float:
    m = max(0.0, min(1.0, magnitude))
    name = (curve or "linear").lower()
    if name == "linear":
        return m
    if name in ("smooth", "ease"):
        return m * m * (3.0 - 2.0 * m)
    if name in ("aggressive", "inst"):
        return m ** max(1.05, exp)
    if name in ("heavy", "late"):
        return m ** max(1.6, exp + 0.4)
    if name in ("dynamic", "medium"):
        return m ** 1.25
    if name == "inverted":
        return 1.0 - (1.0 - m) ** exp
    return m


@dataclass
class StickTune:
    deadzone_inner: float = 0.05
    deadzone_outer: float = 1.0
    anti_deadzone: float = 0.0
    curve: str = "linear"
    curve_exp: float = 1.4
    invert_x: bool = False
    invert_y: bool = False
    scale_x: float = 1.0
    scale_y: float = 1.0


def shape_stick(x_raw: int, y_raw: int, tune: StickTune) -> tuple[float, float]:
    x = byte_to_axis(x_raw, tune.invert_x) * tune.scale_x
    # Xbox/ViGEm: +Y is up. DualSense Y grows downward.
    y = byte_to_axis(y_raw, invert=not tune.invert_y) * tune.scale_y
    mag = math.hypot(x, y)
    if mag <= tune.deadzone_inner or mag == 0.0:
        return 0.0, 0.0
    outer = max(tune.deadzone_inner + 0.001, min(1.0, tune.deadzone_outer))
    if mag > outer:
        mag_n = 1.0
    else:
        mag_n = (mag - tune.deadzone_inner) / (outer - tune.deadzone_inner)
    mag_n = apply_curve(mag_n, tune.curve, tune.curve_exp)
    if tune.anti_deadzone > 0:
        mag_n = tune.anti_deadzone + mag_n * (1.0 - tune.anti_deadzone)
    mag_n = max(0.0, min(1.0, mag_n))
    scale = mag_n / mag
    return _clamp_axis(x * scale), _clamp_axis(y * scale)


def _clamp_axis(v: float) -> float:
    return max(-1.0, min(1.0, v))


def shape_trigger(raw: int, deadzone: float, hair: float, analog: bool = True) -> float:
    t = trigger_to_unit(raw)
    if hair > 0 and t >= hair:
        return 1.0
    if t <= deadzone:
        return 0.0
    if not analog:
        return 1.0 if t > deadzone else 0.0
    return max(0.0, min(1.0, (t - deadzone) / max(0.001, 1.0 - deadzone)))

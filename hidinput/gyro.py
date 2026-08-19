"""Gyro → mouse. Activation-gated, smoothed, for desktop / gyro-aim games."""

from __future__ import annotations

from .inject import mouse_move
from .profile import GyroTune
from .protocol import InputState


class GyroMouse:
    def __init__(self) -> None:
        self._sx = 0.0
        self._sy = 0.0

    def reset(self) -> None:
        self._sx = 0.0
        self._sy = 0.0

    def active(self, state: InputState, tune: GyroTune) -> bool:
        mode = (tune.mode or "off").lower()
        if mode in ("off", "none"):
            return False
        act = (tune.activation or "always").lower()
        table = {
            "always": True,
            "l2": state.l2 > 20 or state.l2_btn,
            "r2": state.r2 > 20 or state.r2_btn,
            "touch": state.touchpad or state.touch0.active,
            "fn_l": state.fn_l,
            "fn_r": state.fn_r,
            "paddle_l": state.paddle_l,
            "paddle_r": state.paddle_r,
            "l1": state.l1,
            "r1": state.r1,
        }
        return bool(table.get(act, True))

    def tick(self, state: InputState, tune: GyroTune, dt: float) -> tuple[float, float]:
        if not self.active(state, tune):
            self.reset()
            return 0.0, 0.0
        # DualSense gyro: X=pitch, Y=yaw, Z=roll (approx, device frame)
        yaw = float(state.gyro_y)
        pitch = float(state.gyro_x)
        if tune.invert_x:
            yaw = -yaw
        if tune.invert_y:
            pitch = -pitch
        # Raw gyro is ~ deg/s * scale. Convert to mouse counts.
        scale = tune.sensitivity * 0.0045
        dx = yaw * scale * tune.yaw_scale
        dy = pitch * scale * tune.pitch_scale
        a = max(0.0, min(0.95, tune.smoothing))
        self._sx = self._sx * a + dx * (1.0 - a)
        self._sy = self._sy * a + dy * (1.0 - a)
        if abs(self._sx) < tune.min_delta and abs(self._sy) < tune.min_delta:
            return 0.0, 0.0
        mouse_move(self._sx, self._sy)
        return self._sx, self._sy

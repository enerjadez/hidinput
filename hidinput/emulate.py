"""ViGEm Xbox 360 / DualShock 4 virtual pads."""

from __future__ import annotations

from typing import Callable

XBOX_BUTTONS = {
    "a": "XUSB_GAMEPAD_A",
    "b": "XUSB_GAMEPAD_B",
    "x": "XUSB_GAMEPAD_X",
    "y": "XUSB_GAMEPAD_Y",
    "lb": "XUSB_GAMEPAD_LEFT_SHOULDER",
    "rb": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "ls": "XUSB_GAMEPAD_LEFT_THUMB",
    "rs": "XUSB_GAMEPAD_RIGHT_THUMB",
    "back": "XUSB_GAMEPAD_BACK",
    "start": "XUSB_GAMEPAD_START",
    "guide": "XUSB_GAMEPAD_GUIDE",
    "dup": "XUSB_GAMEPAD_DPAD_UP",
    "ddown": "XUSB_GAMEPAD_DPAD_DOWN",
    "dleft": "XUSB_GAMEPAD_DPAD_LEFT",
    "dright": "XUSB_GAMEPAD_DPAD_RIGHT",
}

DS4_BUTTONS = {
    "a": "DS4_BUTTON_CROSS",
    "cross": "DS4_BUTTON_CROSS",
    "b": "DS4_BUTTON_CIRCLE",
    "circle": "DS4_BUTTON_CIRCLE",
    "x": "DS4_BUTTON_SQUARE",
    "square": "DS4_BUTTON_SQUARE",
    "y": "DS4_BUTTON_TRIANGLE",
    "triangle": "DS4_BUTTON_TRIANGLE",
    "lb": "DS4_BUTTON_SHOULDER_LEFT",
    "l1": "DS4_BUTTON_SHOULDER_LEFT",
    "rb": "DS4_BUTTON_SHOULDER_RIGHT",
    "r1": "DS4_BUTTON_SHOULDER_RIGHT",
    "ls": "DS4_BUTTON_THUMB_LEFT",
    "l3": "DS4_BUTTON_THUMB_LEFT",
    "rs": "DS4_BUTTON_THUMB_RIGHT",
    "r3": "DS4_BUTTON_THUMB_RIGHT",
    "back": "DS4_BUTTON_SHARE",
    "create": "DS4_BUTTON_SHARE",
    "start": "DS4_BUTTON_OPTIONS",
    "options": "DS4_BUTTON_OPTIONS",
    "touchpad": "DS4_BUTTON_TOUCHPAD",
}


class VirtualPad:
    def __init__(self) -> None:
        self.kind = "off"
        self.pad = None
        self.vg = None
        self.error: str | None = None
        self.rumble = (0, 0)
        self._rumble_cb: Callable | None = None

    def available(self) -> bool:
        try:
            import vgamepad  # noqa: F401

            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def set_kind(self, kind: str, rumble_cb: Callable | None = None) -> None:
        kind = (kind or "off").lower()
        if kind == self.kind and self.pad is not None:
            return
        self.close()
        self.kind = kind
        self._rumble_cb = rumble_cb
        if kind in ("off", "none"):
            return
        try:
            import vgamepad as vg

            self.vg = vg
            last_err = None
            pad = None
            for _attempt in range(2):
                try:
                    if kind in ("ds4", "dualshock4", "dualshock"):
                        pad = vg.VDS4Gamepad()
                        kind = "ds4"
                    else:
                        pad = vg.VX360Gamepad()
                        kind = "xbox360"
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    pad = None
            if last_err:
                raise last_err
            self.pad = pad
            self.kind = kind
            if rumble_cb is not None:
                try:
                    self.pad.register_notification(callback_function=self._on_rumble)
                except Exception:
                    pass
            self.error = None
        except Exception as exc:
            self.pad = None
            self.error = str(exc)
            self.kind = "off"

    def _on_rumble(self, client, target, large_motor, small_motor, led_number, user_data):
        self.rumble = (int(large_motor), int(small_motor))
        if self._rumble_cb:
            self._rumble_cb(int(large_motor), int(small_motor))

    def close(self) -> None:
        if self.pad is not None:
            try:
                self.pad.unregister_notification()
            except Exception:
                pass
            try:
                del self.pad
            except Exception:
                pass
        self.pad = None
        self.kind = "off"
        self.rumble = (0, 0)

    def update(
        self,
        *,
        lx: float,
        ly: float,
        rx: float,
        ry: float,
        lt: float,
        rt: float,
        held: set[str],
    ) -> None:
        if self.pad is None or self.vg is None:
            return
        if self.kind == "xbox360":
            self._update_x360(lx, ly, rx, ry, lt, rt, held)
        else:
            self._update_ds4(lx, ly, rx, ry, lt, rt, held)

    def _update_x360(self, lx, ly, rx, ry, lt, rt, held) -> None:
        vg = self.vg
        pad = self.pad
        pad.reset()
        pad.left_joystick_float(float(lx), float(ly))
        pad.right_joystick_float(float(rx), float(ry))
        pad.left_trigger_float(float(lt))
        pad.right_trigger_float(float(rt))
        enum = vg.XUSB_BUTTON
        for name in held:
            attr = XBOX_BUTTONS.get(name)
            if attr:
                pad.press_button(button=getattr(enum, attr))
        pad.update()

    def _update_ds4(self, lx, ly, rx, ry, lt, rt, held) -> None:
        vg = self.vg
        pad = self.pad
        pad.reset()
        pad.left_joystick_float(float(lx), float(ly))
        pad.right_joystick_float(float(rx), float(ry))
        pad.left_trigger_float(float(lt))
        pad.right_trigger_float(float(rt))
        dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE
        up, down, left, right = "dup" in held, "ddown" in held, "dleft" in held, "dright" in held
        # 8-way
        if up and right:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST
        elif right and down:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST
        elif down and left:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST
        elif left and up:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST
        elif up:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH
        elif right:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST
        elif down:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH
        elif left:
            dpad = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST
        pad.directional_pad(direction=dpad)
        special = vg.DS4_SPECIAL_BUTTONS
        buttons = vg.DS4_BUTTONS
        if "guide" in held or "ps" in held:
            pad.press_special_button(special_button=special.DS4_SPECIAL_BUTTON_PS)
        if "touchpad" in held:
            try:
                pad.press_special_button(special_button=special.DS4_SPECIAL_BUTTON_TOUCHPAD)
            except Exception:
                pass
        for name in held:
            attr = DS4_BUTTONS.get(name)
            if attr:
                pad.press_button(button=getattr(buttons, attr))
        pad.update()

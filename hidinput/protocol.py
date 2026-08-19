"""DualSense / DualSense Edge HID report parse + build.

USB input  : report 0x01, 64 bytes (id included)
BT simple  : report 0x01, 10 bytes (no motion / no Edge extras reliably)
BT full    : report 0x31, 78 bytes — enable by reading feature 0x05
USB output : report 0x02, 48+ bytes
BT output  : report 0x31, 78 bytes + CRC32

Edge extras live in buttons[2] bits 4-7 (same on USB and BT 0x31):
    bit4 Fn left (L4)   bit5 Fn right (R4)
    bit6 paddle left (L5)  bit7 paddle right (R5)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .crc import stamp_bt_output

SONY_VID = 0x054C
PID_DUALSENSE = 0x0CE6
PID_DUALSENSE_EDGE = 0x0DF2
SONY_PIDS = (PID_DUALSENSE, PID_DUALSENSE_EDGE)

USB_INPUT_LEN = 64
BT_INPUT_LEN = 78
BT_SIMPLE_LEN = 10
USB_OUTPUT_LEN = 48
BT_OUTPUT_LEN = 78

FEATURE_CALIBRATION = 0x05
FEATURE_CALIBRATION_LEN = 41

# Output common.valid_flag0
FLAG0_COMPAT_VIBRATION = 0x01
FLAG0_HAPTICS_SELECT = 0x02
FLAG0_RIGHT_TRIGGER = 0x04
FLAG0_LEFT_TRIGGER = 0x08
FLAG0_HEADPHONE = 0x10
FLAG0_SPEAKER = 0x20
FLAG0_MIC = 0x40
FLAG0_AUDIO_CONTROL = 0x80

# valid_flag1
FLAG1_MIC_LED = 0x01
FLAG1_POWER_SAVE = 0x02
FLAG1_LIGHTBAR = 0x04
FLAG1_RELEASE_LEDS = 0x08
FLAG1_PLAYER_LED = 0x10
FLAG1_MOTOR_POWER = 0x40

# valid_flag2
FLAG2_LIGHTBAR_SETUP = 0x02

LIGHTBAR_SETUP_ENABLE = 0x02

PLAYER_LED = {
    0: 0x00,
    1: 0x04,
    2: 0x0A,
    3: 0x15,
    4: 0x1B,
    5: 0x1F,
}


def _i16(lo: int, hi: int) -> int:
    v = lo | (hi << 8)
    return v - 0x10000 if v > 0x7FFF else v


def _hat(nibble: int) -> tuple[bool, bool, bool, bool]:
    up = nibble in (0, 1, 7)
    right = nibble in (1, 2, 3)
    down = nibble in (3, 4, 5)
    left = nibble in (5, 6, 7)
    return up, down, left, right


@dataclass
class TouchPoint:
    active: bool = False
    id: int = 0
    x: int = 0
    y: int = 0


@dataclass
class InputState:
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    l2: int = 0
    r2: int = 0
    dpad_up: bool = False
    dpad_down: bool = False
    dpad_left: bool = False
    dpad_right: bool = False
    square: bool = False
    cross: bool = False
    circle: bool = False
    triangle: bool = False
    l1: bool = False
    r1: bool = False
    l2_btn: bool = False
    r2_btn: bool = False
    create: bool = False
    options: bool = False
    l3: bool = False
    r3: bool = False
    ps: bool = False
    touchpad: bool = False
    mute: bool = False
    fn_l: bool = False
    fn_r: bool = False
    paddle_l: bool = False
    paddle_r: bool = False
    gyro_x: int = 0
    gyro_y: int = 0
    gyro_z: int = 0
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    touch0: TouchPoint = field(default_factory=TouchPoint)
    touch1: TouchPoint = field(default_factory=TouchPoint)
    battery_pct: int = 0
    charging: bool = False
    full: bool = False
    seq: int = 0
    timestamp: int = 0
    raw_len: int = 0
    report_id: int = 0

    def buttons_dict(self) -> dict[str, bool]:
        return {
            "dpad_up": self.dpad_up,
            "dpad_down": self.dpad_down,
            "dpad_left": self.dpad_left,
            "dpad_right": self.dpad_right,
            "square": self.square,
            "cross": self.cross,
            "circle": self.circle,
            "triangle": self.triangle,
            "l1": self.l1,
            "r1": self.r1,
            "l2": self.l2_btn,
            "r2": self.r2_btn,
            "create": self.create,
            "options": self.options,
            "l3": self.l3,
            "r3": self.r3,
            "ps": self.ps,
            "touchpad": self.touchpad,
            "mute": self.mute,
            "fn_l": self.fn_l,
            "fn_r": self.fn_r,
            "paddle_l": self.paddle_l,
            "paddle_r": self.paddle_r,
        }

    def to_public(self) -> dict:
        return {
            "lx": self.lx,
            "ly": self.ly,
            "rx": self.rx,
            "ry": self.ry,
            "l2": self.l2,
            "r2": self.r2,
            "buttons": self.buttons_dict(),
            "gyro": [self.gyro_x, self.gyro_y, self.gyro_z],
            "accel": [self.accel_x, self.accel_y, self.accel_z],
            "touch0": {
                "active": self.touch0.active,
                "id": self.touch0.id,
                "x": self.touch0.x,
                "y": self.touch0.y,
            },
            "touch1": {
                "active": self.touch1.active,
                "id": self.touch1.id,
                "x": self.touch1.x,
                "y": self.touch1.y,
            },
            "battery": {
                "pct": self.battery_pct,
                "charging": self.charging,
                "full": self.full,
            },
        }


@dataclass
class TriggerEffect:
    mode: int = 0
    params: list[int] = field(default_factory=lambda: [0] * 10)

    def bytes11(self) -> list[int]:
        out = [self.mode & 0xFF]
        p = list(self.params) + [0] * 10
        out.extend(int(x) & 0xFF for x in p[:10])
        return out


@dataclass
class OutputState:
    motor_left: int = 0
    motor_right: int = 0
    mute_led: int = 0
    mic_mute: bool = False
    lightbar: tuple[int, int, int] = (0, 90, 255)
    player_leds: int = 0x04
    lightbar_setup: int = LIGHTBAR_SETUP_ENABLE
    brightness: int = 0
    left_trigger: TriggerEffect = field(default_factory=TriggerEffect)
    right_trigger: TriggerEffect = field(default_factory=TriggerEffect)
    flag0: int = 0xFF
    flag1: int = 0xF7
    flag2: int = FLAG2_LIGHTBAR_SETUP


def _touch(b0: int, b1: int, b2: int, b3: int) -> TouchPoint:
    return TouchPoint(
        active=not (b0 & 0x80),
        id=b0 & 0x7F,
        x=((b2 & 0x0F) << 8) | b1,
        y=(b3 << 4) | ((b2 & 0xF0) >> 4),
    )


def _fill_buttons(state: InputState, b0: int, b1: int, b2: int) -> None:
    state.dpad_up, state.dpad_down, state.dpad_left, state.dpad_right = _hat(b0 & 0x0F)
    state.square = bool(b0 & 0x10)
    state.cross = bool(b0 & 0x20)
    state.circle = bool(b0 & 0x40)
    state.triangle = bool(b0 & 0x80)
    state.l1 = bool(b1 & 0x01)
    state.r1 = bool(b1 & 0x02)
    state.l2_btn = bool(b1 & 0x04)
    state.r2_btn = bool(b1 & 0x08)
    state.create = bool(b1 & 0x10)
    state.options = bool(b1 & 0x20)
    state.l3 = bool(b1 & 0x40)
    state.r3 = bool(b1 & 0x80)
    state.ps = bool(b2 & 0x01)
    state.touchpad = bool(b2 & 0x02)
    state.mute = bool(b2 & 0x04)
    state.fn_l = bool(b2 & 0x10)
    state.fn_r = bool(b2 & 0x20)
    state.paddle_l = bool(b2 & 0x40)
    state.paddle_r = bool(b2 & 0x80)


def _battery(state: InputState, b0: int, b1: int) -> None:
    # Capacity nibble 0-8 → ~0-100%. USB often reports 10 / "full".
    nibble = b0 & 0x0F
    state.battery_pct = min(nibble * 100 // 8, 100) if nibble else 0
    if nibble >= 10:
        state.battery_pct = 100
    state.full = bool(b0 & 0x20) or nibble >= 8
    charge = (b0 >> 4) & 0x0F
    state.charging = charge in (1, 2) or bool(b1 & 0x08)


def parse_input(buf: bytes | bytearray) -> InputState:
    if not buf:
        return InputState()
    rid = buf[0]
    n = len(buf)
    if rid == 0x31 and n >= 64:
        return _parse_extended(buf, offset=2)
    if rid == 0x01 and n >= USB_INPUT_LEN:
        return _parse_extended(buf, offset=1)
    if rid == 0x01 and n >= BT_SIMPLE_LEN:
        return _parse_bt_simple(buf)
    if n >= USB_INPUT_LEN:
        return _parse_extended(buf, offset=1)
    return InputState(raw_len=n, report_id=rid)


def _parse_bt_simple(buf: bytes) -> InputState:
    s = InputState(raw_len=len(buf), report_id=buf[0])
    s.lx, s.ly, s.rx, s.ry = buf[1], buf[2], buf[3], buf[4]
    _fill_buttons(s, buf[5], buf[6], buf[7])
    s.l2, s.r2 = buf[8], buf[9]
    return s


def _parse_extended(buf: bytes, offset: int) -> InputState:
    """offset is index of LX. USB: 1. BT 0x31: 2 (skip report id + extra)."""
    s = InputState(raw_len=len(buf), report_id=buf[0])
    i = offset
    s.lx, s.ly, s.rx, s.ry = buf[i], buf[i + 1], buf[i + 2], buf[i + 3]
    s.l2, s.r2 = buf[i + 4], buf[i + 5]
    s.seq = buf[i + 6]
    _fill_buttons(s, buf[i + 7], buf[i + 8], buf[i + 9])
    # timestamp at i+11
    if len(buf) > i + 14:
        s.timestamp = int.from_bytes(buf[i + 11 : i + 15], "little")
    if len(buf) > i + 20:
        s.gyro_x = _i16(buf[i + 15], buf[i + 16])
        s.gyro_y = _i16(buf[i + 17], buf[i + 18])
        s.gyro_z = _i16(buf[i + 19], buf[i + 20])
    if len(buf) > i + 26:
        s.accel_x = _i16(buf[i + 21], buf[i + 22])
        s.accel_y = _i16(buf[i + 23], buf[i + 24])
        s.accel_z = _i16(buf[i + 25], buf[i + 26])
    # touch block starts at USB[33] = offset 1 + 32
    t = i + 32
    if len(buf) > t + 7:
        s.touch0 = _touch(buf[t], buf[t + 1], buf[t + 2], buf[t + 3])
        s.touch1 = _touch(buf[t + 4], buf[t + 5], buf[t + 6], buf[t + 7])
    # battery USB[53] = offset 1 + 52
    b = i + 52
    if len(buf) > b + 1:
        _battery(s, buf[b], buf[b + 1])
    return s


def build_output(out: OutputState, *, bluetooth: bool, seq: int = 1) -> bytes:
    if bluetooth:
        report = bytearray(BT_OUTPUT_LEN)
        report[0] = 0x31
        report[1] = (seq & 0x0F) << 4
        report[2] = 0x10  # DS_OUTPUT_TAG
        _write_common(report, 3, out)
        stamp_bt_output(report)
        return bytes(report)

    report = bytearray(USB_OUTPUT_LEN)
    report[0] = 0x02
    _write_common(report, 1, out)
    return bytes(report)


def _write_common(report: bytearray, base: int, out: OutputState) -> None:
    report[base + 0] = out.flag0
    report[base + 1] = out.flag1
    report[base + 2] = out.motor_right & 0xFF
    report[base + 3] = out.motor_left & 0xFF
    report[base + 8] = out.mute_led & 0xFF
    report[base + 9] = 0x00 if out.mic_mute else 0x10
    r = out.right_trigger.bytes11()
    l = out.left_trigger.bytes11()
    report[base + 10 : base + 21] = bytes(r)
    report[base + 21 : base + 32] = bytes(l)
    report[base + 39] = out.flag2
    report[base + 41] = out.lightbar_setup
    report[base + 42] = out.brightness & 0xFF
    report[base + 43] = out.player_leds & 0xFF
    r_, g, b = out.lightbar
    report[base + 44] = r_ & 0xFF
    report[base + 45] = g & 0xFF
    report[base + 46] = b & 0xFF


BUTTON_ORDER: tuple[str, ...] = (
    "cross",
    "circle",
    "square",
    "triangle",
    "l1",
    "r1",
    "l2",
    "r2",
    "l3",
    "r3",
    "create",
    "options",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
    "ps",
    "touchpad",
    "mute",
    "fn_l",
    "fn_r",
    "paddle_l",
    "paddle_r",
)


def edge_combo_slot(state: InputState) -> int | None:
    """Sony-style Fn + face button profile slots. 1=tri 2=cir 3=cross 4=sq."""
    if not (state.fn_l or state.fn_r):
        return None
    if state.triangle:
        return 1
    if state.circle:
        return 2
    if state.cross:
        return 3
    if state.square:
        return 4
    return None


def clamp_byte(v: int) -> int:
    return max(0, min(255, int(v)))


def iter_changed(prev: InputState | None, cur: InputState) -> Iterable[tuple[str, bool]]:
    if prev is None:
        return
    a, b = prev.buttons_dict(), cur.buttons_dict()
    for k, v in b.items():
        if a.get(k) != v:
            yield k, v

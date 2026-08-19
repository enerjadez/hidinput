"""Low-level mouse / keyboard injection via SendInput."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
WHEEL_DELTA = 120

VK = {
    "lbutton": 0x01,
    "rbutton": 0x02,
    "mbutton": 0x04,
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "caps": 0x14,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "shift_l": 0xA0,
    "shift_r": 0xA1,
    "ctrl_l": 0xA2,
    "ctrl_r": 0xA3,
    "alt_l": 0xA4,
    "alt_r": 0xA5,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT


def _send(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def mouse_move(dx: float, dy: float) -> None:
    ix, iy = int(round(dx)), int(round(dy))
    if ix == 0 and iy == 0:
        return
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(ix, iy, 0, MOUSEEVENTF_MOVE, 0, None)
    _send([inp])


def mouse_wheel(steps: int) -> None:
    if not steps:
        return
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(0, 0, int(steps) * WHEEL_DELTA, MOUSEEVENTF_WHEEL, 0, None)
    _send([inp])


def _vk(name: str) -> int:
    key = name.strip().lower()
    if key in ("mouse_left", "lmb", "leftclick"):
        return -1
    if key in ("mouse_right", "rmb", "rightclick"):
        return -2
    if key in ("mouse_middle", "mmb"):
        return -3
    if key in VK:
        return VK[key]
    if len(key) == 1:
        scanned = user32.VkKeyScanW(ctypes.c_wchar(key))
        if scanned != -1:
            return scanned & 0xFF
        return ord(key.upper())
    if key.startswith("vk_"):
        return int(key[3:], 0)
    return 0


def _key_input(vk: int, up: bool) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = KEYEVENTF_KEYUP if up else 0
    if vk in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C):
        flags |= KEYEVENTF_EXTENDEDKEY
    inp.union.ki = KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), flags, 0, None)
    return inp


def _mouse_button(code: int, down: bool) -> INPUT:
    flags = {
        -1: MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP,
        -2: MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP,
        -3: MOUSEEVENTF_MIDDLEDOWN if down else MOUSEEVENTF_MIDDLEUP,
    }[code]
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
    return inp


class DigitalInjector:
    """Tracks held keys so we only send edges."""

    def __init__(self) -> None:
        self._down: set[str] = set()

    def set(self, name: str, pressed: bool) -> None:
        if not name or name in ("none", "off", "-"):
            return
        key = name.lower()
        if pressed and key not in self._down:
            self._emit(key, True)
            self._down.add(key)
        elif not pressed and key in self._down:
            self._emit(key, False)
            self._down.discard(key)

    def _emit(self, name: str, down: bool) -> None:
        if name in ("mwheelup", "wheelup"):
            if down:
                mouse_wheel(1)
            return
        if name in ("mwheeldown", "wheeldown"):
            if down:
                mouse_wheel(-1)
            return
        vk = _vk(name)
        if vk == 0:
            return
        if vk < 0:
            _send([_mouse_button(vk, down)])
        else:
            _send([_key_input(vk, up=not down)])

    def release_all(self) -> None:
        for key in list(self._down):
            self.set(key, False)

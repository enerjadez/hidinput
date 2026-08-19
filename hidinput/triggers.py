"""Named adaptive-trigger effects (DSX-compatible names + raw modes)."""

from __future__ import annotations

from .protocol import TriggerEffect

# DSX v2 InstructionType.TriggerUpdate mode enum
DSX_MODE_NAMES = {
    0: "Normal",
    1: "GameCube",
    2: "VerySoft",
    3: "Soft",
    4: "Hard",
    5: "VeryHard",
    6: "Hardest",
    7: "Rigid",
    8: "VibrateTrigger",
    9: "Choppy",
    10: "Medium",
    11: "VibrateTriggerPulse",
    12: "CustomTriggerValue",
    13: "Resistance",
    14: "Bow",
    15: "Galloping",
    16: "SemiAutomaticGun",
    17: "AutomaticGun",
    18: "Machine",
}

# Raw DualSense effect modes
MODE_OFF = 0x00
MODE_RIGID = 0x01  # continuous resistance
MODE_PULSE = 0x02  # section / click
MODE_RIGID_A = 0x21
MODE_RIGID_B = 0x05
MODE_RIGID_AB = 0x25
MODE_PULSE_A = 0x22
MODE_PULSE_B = 0x06
MODE_PULSE_AB = 0x26  # pulse + vibration (guns)

CUSTOM_MODES = {
    "OFF": MODE_OFF,
    "Rigid": MODE_RIGID,
    "Rigid A": MODE_RIGID_A,
    "Rigid B": MODE_RIGID_B,
    "Rigid AB": MODE_RIGID_AB,
    "Pulse": MODE_PULSE,
    "Pulse A": MODE_PULSE_A,
    "Pulse B": MODE_PULSE_B,
    "Pulse AB": MODE_PULSE_AB,
    "VibrateResistance": MODE_PULSE_AB,
    "VibrateResistance A": MODE_PULSE_A,
    "VibrateResistance B": MODE_PULSE_B,
    "VibrateResistance AB": MODE_PULSE_AB,
    "Vibrate Pulse": MODE_PULSE,
    "Vibrate Pulse A": MODE_PULSE_A,
    "Vibrate Pulse B": MODE_PULSE_B,
    "Vibrate Pulse AB": MODE_PULSE_AB,
}


def _eff(mode: int, *params: int) -> TriggerEffect:
    p = [int(x) & 0xFF for x in params]
    while len(p) < 10:
        p.append(0)
    return TriggerEffect(mode=mode, params=p)


def named_effect(name: str, params: list[int] | None = None) -> TriggerEffect:
    key = (name or "Normal").replace(" ", "").replace("_", "").lower()
    p = list(params or [])
    pad = lambda *d: (p + list(d))[: len(d)] if p else list(d)

    if key in ("normal", "off", "none"):
        return _eff(MODE_OFF)
    if key == "gamecube":
        return _eff(MODE_PULSE, 0x90, 0xA0, 0xFF)
    if key == "verysoft":
        return _eff(MODE_RIGID, 0x00, 0x15)
    if key == "soft":
        return _eff(MODE_RIGID, 0x00, 0x35)
    if key == "medium":
        return _eff(MODE_RIGID, 0x00, 0x6A)
    if key == "hard":
        return _eff(MODE_RIGID, 0x00, 0xA0)
    if key == "veryhard":
        return _eff(MODE_RIGID, 0x00, 0xD0)
    if key == "hardest":
        return _eff(MODE_RIGID, 0x00, 0xFF)
    if key == "rigid":
        return _eff(MODE_RIGID, 0x00, 0xFF)
    if key == "choppy":
        return _eff(MODE_PULSE, 0x20, 0x60, 0xFF)
    if key == "vibratetrigger":
        intensity = p[0] if p else 25
        return _eff(MODE_PULSE_AB, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00, intensity)
    if key == "vibratetriggerpulse":
        intensity = p[0] if p else 20
        return _eff(MODE_PULSE_AB, 0x10, 0x80, 0x00, 0x00, 0x00, 0x00, intensity)
    if key == "resistance":
        start, force = pad(0, 6)
        return _eff(MODE_RIGID, start, min(force * 32, 255) if force <= 8 else force)
    if key == "bow":
        a, b, c, d = pad(0, 6, 2, 6)
        return _eff(MODE_PULSE, a, b, c, d)
    if key == "galloping":
        a, b, c, d, e = pad(0, 8, 3, 5, 12)
        return _eff(MODE_PULSE_AB, a, b, c, d, 0, 0, e)
    if key == "semiautomaticgun":
        a, b, c = pad(2, 6, 4)
        return _eff(MODE_PULSE, a, b, 0xFF)
    if key == "automaticgun":
        start, end, freq = pad(0, 8, 12)
        start_b = min(start * 28, 200) if start <= 9 else start
        end_b = min(end * 28, 255) if end <= 8 else end
        return _eff(MODE_PULSE_AB, start_b, end_b, 0x00, 0x00, 0x00, 0x00, freq)
    if key == "machine":
        a, b, c, d, e = pad(0, 8, 4, 4, 10)
        return _eff(MODE_PULSE_AB, a, b, c, d, 0, 0, e)
    if key == "customtriggervalue":
        mode_name = ""
        if p and isinstance(params, list) and len(params) >= 1:
            pass
        return _eff(p[0] if p else MODE_OFF, *p[1:8])
    # hex mode like "26"
    try:
        if name.lower().startswith("0x"):
            return _eff(int(name, 16), *p)
        if name.isdigit():
            return named_effect(DSX_MODE_NAMES.get(int(name), "Normal"), p)
    except ValueError:
        pass
    return _eff(MODE_OFF)


def from_dsx(mode_id: int, params: list[int] | None = None) -> TriggerEffect:
    name = DSX_MODE_NAMES.get(int(mode_id), "Normal")
    return named_effect(name, params)


PRESET_LIST = [
    {"id": "Normal", "label": "Off / Normal", "desc": "No resistance"},
    {"id": "GameCube", "label": "GameCube", "desc": "Clicky shoulder"},
    {"id": "VerySoft", "label": "Very Soft", "desc": "Light tension"},
    {"id": "Soft", "label": "Soft", "desc": "Light-medium"},
    {"id": "Medium", "label": "Medium", "desc": "Noticeable pull"},
    {"id": "Hard", "label": "Hard", "desc": "Heavy pull"},
    {"id": "VeryHard", "label": "Very Hard", "desc": "Near lock"},
    {"id": "Hardest", "label": "Hardest", "desc": "Maximum rigid"},
    {"id": "Rigid", "label": "Rigid", "desc": "Full continuous"},
    {"id": "Choppy", "label": "Choppy", "desc": "Stepped sections"},
    {"id": "Resistance", "label": "Resistance", "desc": "Start + force"},
    {"id": "Bow", "label": "Bow", "desc": "Draw then hold"},
    {"id": "AutomaticGun", "label": "Automatic Gun", "desc": "Recoil pulse"},
    {"id": "SemiAutomaticGun", "label": "Semi-Auto Gun", "desc": "Single click"},
    {"id": "VibrateTrigger", "label": "Vibrate", "desc": "Trigger motor"},
    {"id": "Machine", "label": "Machine", "desc": "Cycling pulse"},
]

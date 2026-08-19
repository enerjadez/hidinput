"""Profile model: remaps, stick/trigger/gyro/light, four Edge slots."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .sticks import StickTune

BUTTONS = (
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

# Virtual Xbox targets
XBOX_TARGETS = (
    "a",
    "b",
    "x",
    "y",
    "lb",
    "rb",
    "lt",
    "rt",
    "ls",
    "rs",
    "back",
    "start",
    "guide",
    "dup",
    "ddown",
    "dleft",
    "dright",
)

DEFAULT_MAP = {
    "cross": "a",
    "circle": "b",
    "square": "x",
    "triangle": "y",
    "l1": "lb",
    "r1": "rb",
    "l2": "lt",
    "r3": "rs",
    "l3": "ls",
    "r2": "rt",
    "create": "back",
    "options": "start",
    "dpad_up": "dup",
    "dpad_down": "ddown",
    "dpad_left": "dleft",
    "dpad_right": "dright",
    "ps": "guide",
    "touchpad": "back",
    "mute": "none",
    "fn_l": "none",
    "fn_r": "none",
    "paddle_l": "none",
    "paddle_r": "none",
}


@dataclass
class TriggerTune:
    deadzone: float = 0.02
    hair: float = 0.0
    analog: bool = True
    effect: str = "Normal"
    effect_params: list[int] = field(default_factory=list)


@dataclass
class GyroTune:
    mode: str = "off"  # off | mouse | aim
    activation: str = "always"  # always | l2 | r2 | touch | fn_l | paddle_l
    sensitivity: float = 1.4
    yaw_scale: float = 1.0
    pitch_scale: float = 1.0
    invert_x: bool = False
    invert_y: bool = False
    smoothing: float = 0.15
    min_delta: float = 0.4


@dataclass
class Profile:
    name: str = "Default"
    emulation: str = "xbox360"  # xbox360 | ds4 | off
    lightbar: list[int] = field(default_factory=lambda: [0, 90, 255])
    player_led: int = 1
    mute_led: bool = False
    buttons: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MAP))
    left_stick: StickTune = field(default_factory=StickTune)
    right_stick: StickTune = field(default_factory=StickTune)
    left_trigger: TriggerTune = field(default_factory=TriggerTune)
    right_trigger: TriggerTune = field(default_factory=TriggerTune)
    gyro: GyroTune = field(default_factory=GyroTune)
    rumble_scale: float = 1.0
    fn_switches_profiles: bool = True
    pass_fn_to_game: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        p = cls()
        p.name = str(data.get("name") or p.name)
        p.emulation = str(data.get("emulation") or p.emulation)
        lb = data.get("lightbar") or p.lightbar
        p.lightbar = [int(x) for x in lb[:3]]
        p.player_led = int(data.get("player_led", p.player_led))
        p.mute_led = bool(data.get("mute_led", False))
        buttons = dict(DEFAULT_MAP)
        buttons.update({k: str(v) for k, v in (data.get("buttons") or {}).items()})
        p.buttons = buttons
        p.left_stick = _stick(data.get("left_stick") or data.get("sticks", {}).get("left"))
        p.right_stick = _stick(data.get("right_stick") or data.get("sticks", {}).get("right"))
        p.left_trigger = _trig(data.get("left_trigger") or data.get("triggers", {}).get("left"))
        p.right_trigger = _trig(data.get("right_trigger") or data.get("triggers", {}).get("right"))
        p.gyro = _gyro(data.get("gyro"))
        p.rumble_scale = float(data.get("rumble_scale", 1.0))
        p.fn_switches_profiles = bool(data.get("fn_switches_profiles", True))
        p.pass_fn_to_game = bool(data.get("pass_fn_to_game", False))
        return p


def _stick(data: dict | None) -> StickTune:
    t = StickTune()
    if not data:
        return t
    for k in (
        "deadzone_inner",
        "deadzone_outer",
        "anti_deadzone",
        "curve_exp",
        "scale_x",
        "scale_y",
    ):
        if k in data:
            setattr(t, k, float(data[k]))
    if "curve" in data:
        t.curve = str(data["curve"])
    t.invert_x = bool(data.get("invert_x", False))
    t.invert_y = bool(data.get("invert_y", False))
    return t


def _trig(data: dict | None) -> TriggerTune:
    t = TriggerTune()
    if not data:
        return t
    t.deadzone = float(data.get("deadzone", t.deadzone))
    t.hair = float(data.get("hair", t.hair))
    t.analog = bool(data.get("analog", True))
    t.effect = str(data.get("effect", t.effect))
    t.effect_params = [int(x) for x in (data.get("effect_params") or [])]
    return t


def _gyro(data: dict | None) -> GyroTune:
    g = GyroTune()
    if not data:
        return g
    for k in ("mode", "activation"):
        if k in data:
            setattr(g, k, str(data[k]))
    for k in ("sensitivity", "yaw_scale", "pitch_scale", "smoothing", "min_delta"):
        if k in data:
            setattr(g, k, float(data[k]))
    g.invert_x = bool(data.get("invert_x", False))
    g.invert_y = bool(data.get("invert_y", False))
    return g


class ProfileBank:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.slots: dict[int, str] = {1: "default", 2: "warzone", 3: "apex", 4: "brawlhalla"}
        self.active_slot = 1
        self._cache: dict[str, Profile] = {}
        self._meta_path = self.root / "slots.json"
        self._load_slots()

    def _load_slots(self) -> None:
        if self._meta_path.exists():
            try:
                data = json.loads(self._meta_path.read_text(encoding="utf-8"))
                self.slots.update({int(k): v for k, v in (data.get("slots") or {}).items()})
                self.active_slot = int(data.get("active_slot", 1))
            except Exception:
                pass

    def save_slots(self) -> None:
        self._meta_path.write_text(
            json.dumps({"slots": self.slots, "active_slot": self.active_slot}, indent=2),
            encoding="utf-8",
        )

    def list_profiles(self) -> list[str]:
        names = [p.stem for p in self.root.glob("*.json") if p.name != "slots.json"]
        return sorted(names)

    def path_for(self, name: str) -> Path:
        safe = "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c in "-_")
        return self.root / f"{safe}.json"

    def load(self, name: str) -> Profile:
        key = name.lower()
        if key in self._cache:
            return deepcopy(self._cache[key])
        path = self.path_for(name)
        if not path.exists():
            p = Profile(name=name)
            return p
        p = Profile.from_dict(json.loads(path.read_text(encoding="utf-8")))
        self._cache[key] = p
        return deepcopy(p)

    def save(self, profile: Profile) -> Path:
        path = self.path_for(profile.name)
        path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        self._cache[profile.name.lower()] = deepcopy(profile)
        return path

    def delete(self, name: str) -> None:
        path = self.path_for(name)
        if path.exists():
            path.unlink()
        self._cache.pop(name.lower(), None)

    def active(self) -> Profile:
        name = self.slots.get(self.active_slot, "default")
        return self.load(name)

    def set_slot(self, slot: int, name: str) -> None:
        self.slots[int(slot)] = name
        self.save_slots()

    def select_slot(self, slot: int) -> Profile:
        self.active_slot = int(slot)
        self.save_slots()
        return self.active()

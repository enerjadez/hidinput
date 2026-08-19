"""High-priority DualSense Edge poll loop."""

from __future__ import annotations

import ctypes
import threading
import time
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any

from .emulate import VirtualPad
from .gyro import GyroMouse
from .hid_win import DualSenseDevice, HidInfo, enumerate_dualsense
from .inject import DigitalInjector
from .profile import BUTTONS, Profile, ProfileBank
from .protocol import (
    PLAYER_LED,
    InputState,
    OutputState,
    build_output,
    edge_combo_slot,
    parse_input,
)
from .sticks import shape_stick, shape_trigger
from .triggers import named_effect
from .udp_server import DsxUdp, apply_textfile

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
HIGH_PRIORITY_CLASS = 0x00000080
THREAD_PRIORITY_HIGHEST = 2
THREAD_PRIORITY_TIME_CRITICAL = 15


def _raise_priorities() -> None:
    try:
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), HIGH_PRIORITY_CLASS)
    except Exception:
        pass
    try:
        kernel32.SetThreadPriority(kernel32.GetCurrentThread(), THREAD_PRIORITY_HIGHEST)
    except Exception:
        pass


class Engine:
    def __init__(self, profiles_dir: Path):
        self.bank = ProfileBank(profiles_dir)
        self.profile = self.bank.active()
        self.device: DualSenseDevice | None = None
        self.info: HidInfo | None = None
        self.pad = VirtualPad()
        self.gyro = GyroMouse()
        self.keys = DigitalInjector()
        self.udp = DsxUdp(self._on_udp)
        self.lock = threading.RLock()
        self.running = False
        self._thread: threading.Thread | None = None
        self.state = InputState()
        self.output = OutputState()
        self.poll_hz = 0.0
        self.last_error: str | None = None
        self.emulation = self.profile.emulation
        self.udp_port = 6969
        self.textfile: Path | None = None
        self._text_mtime = 0.0
        self._times: deque[float] = deque(maxlen=2000)
        self._out_seq = 1
        self._last_slot_at = 0.0
        self._last_slot = 0
        self._game_rumble = (0, 0)
        self._test_rumble = (0, 0)
        self._force_output = True
        self._processed: dict[str, Any] = {}
        self.watch_textfile = True
        self.auto_connect = True
        self._last_report: bytes | None = None
        self._apply_output_from_profile()

    # ── lifecycle ──────────────────────────────────────────────
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.udp.port = self.udp_port
        self.udp.start()
        self._apply_output_from_profile()
        self._apply_emulation()
        self._thread = threading.Thread(target=self._loop, name="hidinput-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self.udp.stop()
        self.keys.release_all()
        self.pad.close()
        if self._thread:
            self._thread.join(timeout=1.5)
        if self.device:
            self.device.close()
            self.device = None

    def devices(self) -> list[dict]:
        return [d.as_dict() for d in enumerate_dualsense()]

    def connect(self, path: str | None = None) -> dict:
        with self.lock:
            infos = enumerate_dualsense()
            if not infos:
                raise RuntimeError("No DualSense / DualSense Edge found. Plug it in over USB or pair Bluetooth.")
            info = next((i for i in infos if i.path == path), infos[0]) if path else infos[0]
            if self.device:
                self.device.close()
            dev = DualSenseDevice(info)
            dev.open()
            self.device = dev
            self.info = info
            self._force_output = True
            self.last_error = None
            return info.as_dict()

    def disconnect(self) -> None:
        with self.lock:
            if self.device:
                self.device.close()
            self.device = None
            self.info = None
            self.keys.release_all()

    # ── profile / settings ─────────────────────────────────────
    def set_profile(self, profile: Profile, persist: bool = False) -> None:
        with self.lock:
            self.profile = profile
            self.emulation = profile.emulation
            self._apply_output_from_profile()
            self._apply_emulation()
            self._force_output = True
            if persist:
                self.bank.save(profile)

    def select_slot(self, slot: int) -> Profile:
        p = self.bank.select_slot(slot)
        self.set_profile(p)
        return p

    def set_emulation(self, kind: str) -> None:
        with self.lock:
            self.emulation = kind
            self.profile.emulation = kind
            self._apply_emulation()

    def _apply_emulation(self) -> None:
        self.pad.set_kind(self.emulation, rumble_cb=self._on_game_rumble)

    def _on_game_rumble(self, large: int, small: int) -> None:
        self._game_rumble = (large, small)

    def set_test_rumble(self, left: int, right: int) -> None:
        self._test_rumble = (int(left), int(right))
        self._force_output = True

    def set_lightbar(self, r: int, g: int, b: int) -> None:
        self.profile.lightbar = [int(r), int(g), int(b)]
        self._apply_output_from_profile()
        self._force_output = True

    def set_triggers(self, left: str | None, right: str | None, params: list[int] | None = None) -> None:
        if left is not None:
            self.profile.left_trigger.effect = left
            if params is not None:
                self.profile.left_trigger.effect_params = list(params)
        if right is not None:
            self.profile.right_trigger.effect = right
            if params is not None:
                self.profile.right_trigger.effect_params = list(params)
        self._apply_output_from_profile()
        self._force_output = True

    def _on_udp(self, payload: dict) -> None:
        with self.lock:
            if payload.get("reset"):
                self._apply_output_from_profile()
                self._force_output = True
                return
            if "lightbar" in payload:
                lb = payload["lightbar"]
                self.output.lightbar = (int(lb[0]), int(lb[1]), int(lb[2]))
            if "player_led" in payload:
                n = int(payload["player_led"])
                self.output.player_leds = PLAYER_LED.get(n, n)
            if "mute_led" in payload:
                self.output.mute_led = 1 if payload["mute_led"] else 0
            for side in ("left", "right"):
                key = f"{side}_trigger"
                if key in payload:
                    block = payload[key]
                    eff = named_effect("Normal")
                    if "mode" in block:
                        from .protocol import TriggerEffect

                        eff = TriggerEffect(mode=int(block["mode"]), params=list(block.get("params") or []))
                    elif "name" in block:
                        eff = named_effect(str(block["name"]), list(block.get("params") or []))
                    if side == "left":
                        self.output.left_trigger = eff
                    else:
                        self.output.right_trigger = eff
            self._force_output = True

    def _apply_output_from_profile(self) -> None:
        p = self.profile
        self.output.lightbar = (p.lightbar[0], p.lightbar[1], p.lightbar[2])
        self.output.player_leds = PLAYER_LED.get(int(p.player_led), 0x04)
        self.output.mute_led = 1 if p.mute_led else 0
        self.output.left_trigger = named_effect(p.left_trigger.effect, p.left_trigger.effect_params)
        self.output.right_trigger = named_effect(p.right_trigger.effect, p.right_trigger.effect_params)

    # ── snapshot for UI ────────────────────────────────────────
    def snapshot(self) -> dict:
        with self.lock:
            info = self.info.as_dict() if self.info else None
            return {
                "connected": bool(self.device and self.device.connected),
                "device": info,
                "is_edge": bool(self.info and self.info.is_edge),
                "poll_hz": round(self.poll_hz, 1),
                "error": self.last_error,
                "emulation": self.emulation,
                "emulation_error": self.pad.error,
                "vigem": self.pad.available() or self.pad.pad is not None,
                "profile": self.profile.to_dict(),
                "slot": self.bank.active_slot,
                "slots": self.bank.slots,
                "profiles": self.bank.list_profiles(),
                "input": self.state.to_public(),
                "processed": dict(self._processed),
                "udp": {
                    "running": self.udp.running,
                    "port": self.udp.port,
                    "packets": self.udp.packets,
                    "last": self.udp.last_packet,
                    "error": self.udp.error,
                },
                "output": {
                    "lightbar": list(self.output.lightbar),
                    "player_leds": self.output.player_leds,
                    "mute_led": self.output.mute_led,
                    "motor_left": self.output.motor_left,
                    "motor_right": self.output.motor_right,
                    "left_trigger": {
                        "mode": self.output.left_trigger.mode,
                        "params": self.output.left_trigger.params[:7],
                    },
                    "right_trigger": {
                        "mode": self.output.right_trigger.mode,
                        "params": self.output.right_trigger.params[:7],
                    },
                },
            }

    # ── poll loop ──────────────────────────────────────────────
    def _loop(self) -> None:
        _raise_priorities()
        last_out = 0.0
        reconnect_at = 0.0
        while self.running:
            now = time.perf_counter()
            if self.device is None or not self.device.connected:
                if self.auto_connect and now >= reconnect_at:
                    try:
                        self.connect()
                    except Exception as exc:
                        self.last_error = str(exc)
                    reconnect_at = now + 1.2
                time.sleep(0.05)
                continue

            raw = self.device.read(timeout_ms=4)
            if raw is None:
                if not self.device.connected:
                    self.last_error = "Controller disconnected"
                    continue
                # still push output / keep pad alive
                if now - last_out > 0.05:
                    self._send_output()
                    last_out = now
                continue

            t = time.perf_counter()
            self._times.append(t)
            while self._times and t - self._times[0] > 1.0:
                self._times.popleft()
            self.poll_hz = float(len(self._times))

            state = parse_input(raw)
            with self.lock:
                self.state = state
                self._tick_profile_hotkeys(state, t)
                processed = self._process(state, t)
                self._processed = processed
                self._drive_virtual(processed)
                self._drive_keys(state, processed)

            if now - last_out >= 0.016 or self._force_output:
                self._send_output()
                last_out = now
                self._force_output = False

            if self.watch_textfile and self.textfile:
                self._poll_textfile()

    def _tick_profile_hotkeys(self, state: InputState, now: float) -> None:
        if not self.profile.fn_switches_profiles:
            return
        slot = edge_combo_slot(state)
        if slot is None:
            self._last_slot = 0
            return
        if slot == self._last_slot:
            return
        if now - self._last_slot_at < 0.35:
            return
        self._last_slot = slot
        self._last_slot_at = now
        try:
            p = self.bank.select_slot(slot)
            self.profile = p
            self.emulation = p.emulation
            self._apply_output_from_profile()
            self._apply_emulation()
            # brief rumble + player LED flash like Sony
            self.output.player_leds = PLAYER_LED.get(slot, 0x04)
            self._test_rumble = (80, 80)
            self._force_output = True
        except Exception as exc:
            self.last_error = str(exc)

    def _process(self, state: InputState, now: float) -> dict[str, Any]:
        p = self.profile
        lx, ly = shape_stick(state.lx, state.ly, p.left_stick)
        rx, ry = shape_stick(state.rx, state.ry, p.right_stick)
        lt = shape_trigger(state.l2, p.left_trigger.deadzone, p.left_trigger.hair, p.left_trigger.analog)
        rt = shape_trigger(state.r2, p.right_trigger.deadzone, p.right_trigger.hair, p.right_trigger.analog)

        held: set[str] = set()
        skip_fn = p.fn_switches_profiles and (state.fn_l or state.fn_r) and not p.pass_fn_to_game
        buttons = state.buttons_dict()
        if skip_fn:
            # Eat the face buttons used for slot switching so games don't also fire them
            if state.triangle or state.circle or state.cross or state.square:
                buttons = dict(buttons)
                buttons["triangle"] = buttons["circle"] = buttons["cross"] = buttons["square"] = False
            buttons["fn_l"] = False
            buttons["fn_r"] = False

        for src in BUTTONS:
            if src in ("l2", "r2"):
                continue
            if not buttons.get(src):
                continue
            target = (p.buttons.get(src) or "none").lower()
            if target in ("none", "off", "-", ""):
                continue
            if target in ("lt", "rt"):
                if target == "lt":
                    lt = 1.0
                else:
                    rt = 1.0
                continue
            held.add(target)

        # analog triggers as their mapped digital/analog
        if lt > 0:
            t = (p.buttons.get("l2") or "lt").lower()
            if t == "lt":
                pass
            elif t == "rt":
                rt = max(rt, lt)
                lt = 0.0 if (p.buttons.get("l2") == "rt") else lt
            elif t not in ("none", "off"):
                if lt >= max(0.5, p.left_trigger.hair or 0.5):
                    held.add(t)
        if rt > 0:
            t = (p.buttons.get("r2") or "rt").lower()
            if t == "rt":
                pass
            elif t == "lt":
                lt = max(lt, rt)
            elif t not in ("none", "off"):
                if rt >= max(0.5, p.right_trigger.hair or 0.5):
                    held.add(t)

        gx, gy = self.gyro.tick(state, p.gyro, 0.0)
        return {
            "lx": lx,
            "ly": ly,
            "rx": rx,
            "ry": ry,
            "lt": lt,
            "rt": rt,
            "held": sorted(held),
            "gyro_mouse": [round(gx, 2), round(gy, 2)],
        }

    def _drive_virtual(self, processed: dict) -> None:
        self.pad.update(
            lx=processed["lx"],
            ly=processed["ly"],
            rx=processed["rx"],
            ry=processed["ry"],
            lt=processed["lt"],
            rt=processed["rt"],
            held=set(processed["held"]),
        )

    def _drive_keys(self, state: InputState, processed: dict) -> None:
        # Any remap target that is not an xbox/ds4 name is treated as a key.
        pad_names = {
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
            "none",
            "off",
            "-",
            "",
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
            "ps",
            "touchpad",
        }
        wanted: set[str] = set()
        buttons = state.buttons_dict()
        for src, pressed in buttons.items():
            target = (self.profile.buttons.get(src) or "").lower()
            if pressed and target and target not in pad_names:
                wanted.add(target)
        # analog-as-key already added via processed held if they used key names
        for name in processed["held"]:
            if name not in pad_names:
                wanted.add(name)
        live = set(self.keys._down)
        for name in live - wanted:
            self.keys.set(name, False)
        for name in wanted:
            self.keys.set(name, True)

    def _send_output(self) -> None:
        if not self.device:
            return
        scale = max(0.0, min(2.0, self.profile.rumble_scale))
        gl, gs = self._game_rumble
        tl, tr = self._test_rumble
        left = max(gl, tl)
        right = max(gs, tr)
        if tl or tr:
            # test rumble decays
            self._test_rumble = (max(0, tl - 12), max(0, tr - 12))
        self.output.motor_left = int(max(0, min(255, left * scale)))
        self.output.motor_right = int(max(0, min(255, right * scale)))
        report = build_output(
            self.output,
            bluetooth=bool(self.info and self.info.bluetooth),
            seq=self._out_seq,
        )
        if report == self._last_report and not self._force_output:
            return
        self._last_report = report
        self._out_seq = (self._out_seq + 1) & 0x0F
        try:
            self.device.write(report)
        except Exception as exc:
            self.last_error = str(exc)

    def _poll_textfile(self) -> None:
        path = self.textfile
        if not path or not path.exists():
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if mtime == self._text_mtime:
            return
        self._text_mtime = mtime
        payload = apply_textfile(path)
        if payload:
            self._on_udp(payload)

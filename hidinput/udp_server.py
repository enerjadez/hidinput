"""DSX-compatible UDP listener (v2 numeric instructions) plus HIDInput JSON."""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Callable

from .triggers import from_dsx, named_effect

# DSX v2 InstructionType
GET_STATUS = 0
TRIGGER_UPDATE = 1
RGB_UPDATE = 2
PLAYER_LED = 3
TRIGGER_THRESHOLD = 4
MIC_LED = 5
PLAYER_LED_NEW = 6
RESET_USER = 7


class DsxUdp:
    def __init__(self, apply: Callable[[dict], None], port: int = 6969):
        self.apply = apply
        self.port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.running = False
        self.last_packet = ""
        self.packets = 0
        self.error: str | None = None

    def start(self) -> None:
        self.stop()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", self.port))
            sock.settimeout(0.5)
            self._sock = sock
            self.running = True
            self.error = None
            self._thread = threading.Thread(target=self._loop, name="hidinput-udp", daemon=True)
            self._thread.start()
            self._write_port_file()
        except OSError as exc:
            self.error = str(exc)
            self.running = False

    def stop(self) -> None:
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _write_port_file(self) -> None:
        try:
            p = Path(r"C:\Temp\DualSenseX")
            p.mkdir(parents=True, exist_ok=True)
            (p / "DualSenseX_PortNumber.txt").write_text(str(self.port), encoding="ascii")
        except OSError:
            pass

    def _loop(self) -> None:
        while self.running and self._sock:
            try:
                data, _addr = self._sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                text = data.decode("utf-8", errors="replace")
                self.last_packet = text[:500]
                self.packets += 1
                payload = json.loads(text)
                self._dispatch(payload)
            except Exception as exc:
                self.error = str(exc)

    def _dispatch(self, payload: dict) -> None:
        if "instructions" in payload:
            for inst in payload["instructions"]:
                self._instruction(inst)
            return
        # Native HIDInput packet
        if "left_trigger" in payload or "right_trigger" in payload or "lightbar" in payload:
            self.apply(payload)

    def _instruction(self, inst: dict) -> None:
        typ = inst.get("type")
        params = inst.get("parameters") or []
        if isinstance(typ, str):
            typ = {
                "GetDSXStatus": 0,
                "TriggerUpdate": 1,
                "RGBUpdate": 2,
                "PlayerLED": 3,
                "TriggerThreshold": 4,
                "MicLED": 5,
                "PlayerLEDNewRevision": 6,
                "ResetToUserSettings": 7,
            }.get(typ, -1)
        try:
            typ = int(typ)
        except (TypeError, ValueError):
            return
        if typ == TRIGGER_UPDATE:
            # [controller, trigger 1/2, mode, ...params]
            if len(params) < 3:
                return
            side = "left" if int(params[1]) == 1 else "right"
            mode = int(params[2])
            extra = [int(x) for x in params[3:]]
            eff = from_dsx(mode, extra)
            self.apply({f"{side}_trigger": {"mode": eff.mode, "params": eff.params, "name": str(mode)}})
        elif typ == RGB_UPDATE:
            # [controller, r, g, b]
            if len(params) >= 4:
                self.apply({"lightbar": [int(params[1]), int(params[2]), int(params[3])]})
        elif typ in (PLAYER_LED, PLAYER_LED_NEW):
            if len(params) >= 2:
                self.apply({"player_led": int(params[1])})
        elif typ == MIC_LED:
            if len(params) >= 2:
                self.apply({"mute_led": bool(int(params[1]))})
        elif typ == RESET_USER:
            self.apply({"reset": True})


def apply_textfile(path: Path) -> dict:
    """DSX v1 text-file trigger language."""
    if not path.exists():
        return {}
    data: dict = {}
    left_name = right_name = None
    left_params: list[int] = []
    right_params: list[int] = []
    custom_l = custom_r = None
    vibrate = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "LeftTrigger":
            left_name = v
        elif k == "RightTrigger":
            right_name = v
        elif k == "ForceLeftTrigger":
            left_params = _paren_ints(v)
        elif k == "ForceRightTrigger":
            right_params = _paren_ints(v)
        elif k == "CustomTriggerValueLeftMode":
            custom_l = v
        elif k == "CustomTriggerValueRightMode":
            custom_r = v
        elif k == "VibrateTriggerIntensity":
            try:
                vibrate = int(v)
            except ValueError:
                pass
    if left_name:
        params = left_params
        if left_name.lower() == "customtriggervalue" and custom_l:
            from .triggers import CUSTOM_MODES

            params = [CUSTOM_MODES.get(custom_l, 0), *left_params]
        if vibrate is not None and left_name.lower().startswith("vibrate"):
            params = [vibrate]
        eff = named_effect(left_name, params)
        data["left_trigger"] = {"mode": eff.mode, "params": eff.params, "name": left_name}
    if right_name:
        params = right_params
        if right_name.lower() == "customtriggervalue" and custom_r:
            from .triggers import CUSTOM_MODES

            params = [CUSTOM_MODES.get(custom_r, 0), *right_params]
        if vibrate is not None and right_name.lower().startswith("vibrate"):
            params = [vibrate]
        eff = named_effect(right_name, params)
        data["right_trigger"] = {"mode": eff.mode, "params": eff.params, "name": right_name}
    return data


def _paren_ints(text: str) -> list[int]:
    out: list[int] = []
    cur = ""
    for ch in text:
        if ch.isdigit() or ch in ".-":
            cur += ch
        elif cur:
            try:
                if "." in cur:
                    out.append(int(float(cur)))
                else:
                    out.append(int(cur))
            except ValueError:
                pass
            cur = ""
    if cur:
        try:
            out.append(int(float(cur)))
        except ValueError:
            pass
    return out

"""HIDInput local dashboard + JSON API."""

from __future__ import annotations

import json
import os
import socket
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import Engine
from .profile import Profile
from .triggers import PRESET_LIST

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PROFILES = ROOT / "profiles"


class Handler(SimpleHTTPRequestHandler):
    engine: Engine

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        if "/api/state" in str(args[0] if args else ""):
            return
        super().log_message(fmt, *args)

    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._json(self.engine.snapshot())
        if path == "/api/devices":
            return self._json({"devices": self.engine.devices()})
        if path == "/api/presets":
            return self._json({"triggers": PRESET_LIST})
        if path == "/api/profiles":
            return self._json(
                {
                    "profiles": self.engine.bank.list_profiles(),
                    "slots": self.engine.bank.slots,
                    "active": self.engine.bank.active_slot,
                }
            )
        if path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if path == "/":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            data = self._read_json()
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)
        try:
            result = self._handle_post(path, data)
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)
        return self._json(result if result is not None else {"ok": True})

    def _handle_post(self, path: str, data: dict):
        e = self.engine
        if path == "/api/connect":
            return e.connect(data.get("path"))
        if path == "/api/disconnect":
            e.disconnect()
            return {"ok": True}
        if path == "/api/emulation":
            e.set_emulation(str(data.get("kind") or "xbox360"))
            return {"ok": True, "kind": e.emulation}
        if path == "/api/lightbar":
            e.set_lightbar(int(data.get("r", 0)), int(data.get("g", 90)), int(data.get("b", 255)))
            return {"ok": True}
        if path == "/api/rumble":
            e.set_test_rumble(int(data.get("left", 0)), int(data.get("right", 0)))
            return {"ok": True}
        if path == "/api/triggers":
            e.set_triggers(data.get("left"), data.get("right"), data.get("params"))
            return {"ok": True}
        if path == "/api/profile/select":
            name = str(data.get("name") or "default")
            p = e.bank.load(name)
            e.set_profile(p)
            return {"ok": True, "profile": p.to_dict()}
        if path == "/api/profile/save":
            incoming = data.get("profile") or data
            p = Profile.from_dict(incoming)
            e.bank.save(p)
            e.set_profile(p)
            return {"ok": True, "name": p.name}
        if path == "/api/profile/delete":
            e.bank.delete(str(data.get("name")))
            return {"ok": True}
        if path == "/api/slot":
            slot = int(data.get("slot", 1))
            if data.get("name"):
                e.bank.set_slot(slot, str(data["name"]))
            p = e.select_slot(slot)
            return {"ok": True, "profile": p.to_dict(), "slot": slot}
        if path == "/api/remap":
            src = str(data.get("src") or "")
            dst = str(data.get("dst") or "none")
            if src:
                e.profile.buttons[src] = dst
            return {"ok": True, "buttons": e.profile.buttons}
        if path == "/api/tune":
            self._apply_tune(e, data)
            e._apply_output_from_profile()
            e._force_output = True
            return {"ok": True, "profile": e.profile.to_dict()}
        if path == "/api/udp":
            port = int(data.get("port", e.udp_port))
            e.udp_port = port
            e.udp.port = port
            if data.get("enabled", True):
                e.udp.start()
            else:
                e.udp.stop()
            return {"ok": True, "port": port, "running": e.udp.running}
        raise RuntimeError("not found")

    def _apply_tune(self, e: Engine, data: dict) -> None:
        p = e.profile
        if "name" in data:
            p.name = str(data["name"])
        if "left_stick" in data:
            for k, v in data["left_stick"].items():
                if hasattr(p.left_stick, k):
                    cur = getattr(p.left_stick, k)
                    setattr(p.left_stick, k, type(cur)(v) if not isinstance(cur, bool) else bool(v))
        if "right_stick" in data:
            for k, v in data["right_stick"].items():
                if hasattr(p.right_stick, k):
                    cur = getattr(p.right_stick, k)
                    setattr(p.right_stick, k, type(cur)(v) if not isinstance(cur, bool) else bool(v))
        if "left_trigger" in data:
            for k, v in data["left_trigger"].items():
                if hasattr(p.left_trigger, k):
                    cur = getattr(p.left_trigger, k)
                    if k == "effect_params":
                        p.left_trigger.effect_params = [int(x) for x in v]
                    else:
                        setattr(p.left_trigger, k, type(cur)(v) if not isinstance(cur, bool) else bool(v))
        if "right_trigger" in data:
            for k, v in data["right_trigger"].items():
                if hasattr(p.right_trigger, k):
                    cur = getattr(p.right_trigger, k)
                    if k == "effect_params":
                        p.right_trigger.effect_params = [int(x) for x in v]
                    else:
                        setattr(p.right_trigger, k, type(cur)(v) if not isinstance(cur, bool) else bool(v))
        if "gyro" in data:
            for k, v in data["gyro"].items():
                if hasattr(p.gyro, k):
                    cur = getattr(p.gyro, k)
                    setattr(p.gyro, k, type(cur)(v) if not isinstance(cur, bool) else bool(v))
        if "fn_switches_profiles" in data:
            p.fn_switches_profiles = bool(data["fn_switches_profiles"])
        if "rumble_scale" in data:
            p.rumble_scale = float(data["rumble_scale"])
        if "player_led" in data:
            p.player_led = int(data["player_led"])
        if "mute_led" in data:
            p.mute_led = bool(data["mute_led"])


def pick_port(preferred: int = 8765) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port")


def main() -> None:
    os.chdir(ROOT)
    engine = Engine(PROFILES)
    Handler.engine = engine
    engine.start()
    port = pick_port(8765)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"HIDInput  →  {url}")
    print("DualSense Edge: USB or Bluetooth. Fn+△○✕□ switches profile slots.")
    print("Ctrl+C to quit.")
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        engine.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()

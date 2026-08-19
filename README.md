# HIDInput

Windows app for DualSense and **DualSense Edge**. Paddles and Fn as real extra buttons, adaptive triggers, Xbox 360 / DualShock 4 emulation, stick curves, hair triggers, gyro-to-mouse, DSX-compatible UDP.

Works if someone sent you a zip. Works if you cloned the private repo.

---

## Send this to a friend (zip install)

Give them **`HIDInput.zip`** plus this README. They do **not** need Git.

### 1. What they need

| Thing | Required? | Where |
|---|---|---|
| Windows 10 / 11 | Yes | — |
| DualSense or DualSense Edge | Yes | USB-C (best) or Bluetooth |
| [Python 3.11+](https://www.python.org/downloads/) | Yes | Tick **Add python.exe to PATH** |
| [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest) | Yes, or games won't see a pad | Download `ViGEmBus_Setup_*.exe`, install, reboot if asked |
| [HidHide](https://github.com/nefarius/HidHide/releases) | Optional | Stops the game seeing *two* controllers |

### 2. Unzip and run

1. Unzip `HIDInput.zip` to a folder, e.g. `C:\HIDInput`.
2. Keep the folder together. Do not run the `.bat` from inside the zip.
3. Double-click **`hidinput.bat`**.
   - First run installs the `vgamepad` Python package.
   - A browser tab opens at `http://127.0.0.1:8765/`.
4. Leave the black window open while you play. Close it to quit.

If Windows SmartScreen blocks the bat: **More info → Run anyway**.

### 3. Controller setup (Edge paddles)

1. Plug the pad in.
2. Open **PlayStation Accessories** (Sony’s PC app) and set the **Default** hardware profile (**Fn + triangle**).
   - If paddles are remapped *on the controller*, HID fires the original button *and* the paddle. You lose the extra input.
3. In HIDInput, confirm the live pad, **Paddle L / Paddle R**, and poll rate.
4. Emulation: **Xbox 360** for CoD / Battle.net / most PC shooters.

### 4. Stop double input

Games will see the real DualSense *and* the virtual Xbox pad.

- Disable **Steam Input** for that game, and/or
- Install **HidHide**, hide the Sony device from the game, whitelist `python.exe`.

### 5. Profiles

Load one from the **Profiles** tab, or hold **Fn** and tap a face button:

| Combo | Slot (defaults) |
|---|---|
| Fn + △ | 1 Default |
| Fn + ○ | 2 Warzone |
| Fn + ✕ | 3 Apex |
| Fn + □ | 4 Brawlhalla |

Warzone preset: paddle L = slide (B), paddle R = jump (A), hair triggers, gyro off.

---

## What it does

| Feature | Notes |
|---|---|
| DualSense + Edge | VID `054C`, PID `0CE6` / `0DF2` |
| Fn L/R + paddles | Own bits. Bind to A/B/jump/slide or a key |
| Adaptive triggers | GameCube, Resistance, AutomaticGun, … |
| Xbox 360 / DS4 | ViGEm. Game rumble comes back to the pad |
| Stick engine | Deadzone, anti-deadzone, curves |
| Hair triggers | Digital click at a threshold |
| Gyro mouse | Optional. Leave **Off** on Ricochet titles |
| Light / rumble | Light tab |
| DSX UDP | `127.0.0.1:6969` |

No turbo, no recoil scripts, no macros.

---

## Repo / folder layout

```
HIDInput/
  hidinput.bat      ← friend double-clicks this
  run.py            ← python run.py
  requirements.txt  ← vgamepad
  README.md         ← this file
  hidinput/         ← engine, HID, ViGEm, UDP
  web/              ← dashboard
  profiles/         ← JSON + Fn slots
```

Dev launch from a clone:

```
python -m pip install -r requirements.txt
python run.py
```

Dashboard: `http://127.0.0.1:8765/`

---

## Competitive notes

- USB beats Bluetooth. hidusbf can push USB polling to 1000 Hz.
- If a game still sees two pads, HidHide the Sony device.
- Gyro-as-mouse + a virtual pad can look like a XIM. Keep gyro **Off** on CoD.

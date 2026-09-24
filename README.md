# CV Desk

macOS menu-bar app: **control your desk with hand gestures** (MediaPipe Hands).

Play/pause · next/prev · volume · mute · Mission Control · App Exposé · screenshot · Spaces — without touching the keyboard.

![Platform](https://img.shields.io/badge/platform-macOS%2013%2B-black)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.0.1-blue)

---

## Gestures

| Gesture | Action |
|---------|--------|
| **Fist → open palm** | Play / Pause |
| **Open palm swipe** ← / → | Previous / Next track |
| **Pinch + move** ↑ / ↓ | Volume ± (thumb+index; other fingers relaxed) |
| **Pinch hold still** → HUD `SNAP ✓` → **open** | Screenshot (Desktop PNG) |
| **OK** (👌) hold ~0.4s | Mute toggle |
| **👍 hold** ~0.7s | Mission Control |
| **3 fingers** hold ~0.55s (index+middle+ring) | App Exposé |
| **Two fingers** swipe ← / → | Switch Desktop Space |
| **Fist hold** ~1.2s | Arm / Disarm recognition (safety) |

**Per-app profiles:** tray → **Profiles** — enable/disable gesture groups for the frontmost app (`Name*` = custom). Same gestures everywhere; sensitivity stays global.

---

## Install

```bash
cd cv_desk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or reuse an existing venv that already has `mediapipe==0.10.35`.

---

## Run

Menu bar (tray):

```bash
cd cv_desk
PYTHONPATH=. python -m cv_desk
```

### macOS `.app` (dev-only wrapper)

Points at this repo + a nearby `.venv` (paths resolved at launch — **not** a redistributable freeze):

```bash
./scripts/build_app.sh
open "dist/CV Desk.app"
```

Then in the **CV** menu: **Show Preview**, **Launch at Login**, **Profiles**, sensitivity presets.

Preview / debug only (no tray):

```bash
PYTHONPATH=. python -m cv_desk --cli
```

Calibrate sensitivity:

```bash
PYTHONPATH=. python -m cv_desk --calibrate
```

### Permissions (required)

Grant these to **Python** / **Terminal** / your IDE (the `.app` is a shell → venv python):

1. **Camera**
2. **Accessibility** — Mission Control, Spaces, App Exposé, System Events
3. **Screen Recording** — screenshot (Quartz capture)

Config: `~/Library/Application Support/CVDesk/config.json`

---

## Architecture

```
cv_desk/
  cv_desk/
    app.py              # tray + vision loop
    config.py           # atomic config I/O
    profiles.py         # per-app enable masks
    frontmost.py        # sticky NSWorkspace frontmost
    login_item.py       # LaunchAgent
    sensitivity.py      # presets + calibrate helpers
    calibrate.py
    vision/camera.py    # MediaPipe detect thread
    vision/gestures.py  # state machine
    actions/macos.py    # volume, media, MC, Spaces, screenshot
    ui/preview.py
    ui/cocoa_preview.py
  config.default.json
  scripts/build_app.sh
  requirements.txt
```

---

## Product notes

- Cooldown ~0.40s (normal preset) between discrete actions  
- Disarm with fist-hold when you need to gesture at the camera for other apps  
- Per-app toggles: tray **Profiles** (or `config.json` → `profiles`)  
- v1 is **macOS-only**; Windows later  

---

## License

MIT

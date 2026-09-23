# CV Desk

macOS menu-bar app: **control your desk with hand gestures** (MediaPipe Hands).

Play/pause · next/prev · volume · mute · Mission Control · Spaces — without touching the keyboard.

![Platform](https://img.shields.io/badge/platform-macOS%2013%2B-black)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Gestures

| Gesture | Action |
|---------|--------|
| **Fist → open palm** | Play / Pause |
| **Open palm swipe** ← / → | Previous / Next track |
| **Pinch + move** ↑ / ↓ | Volume ± |
| **OK** (👌) | Mute toggle |
| **Palm face-up** hold ~0.6s | Mission Control |
| **Two fingers** swipe ← / → | Switch Desktop Space |
| **Fist hold** ~0.8s | Arm / Disarm recognition (safety) |

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

Menu bar + preview:

```bash
cd cv_desk
PYTHONPATH=. python -m cv_desk
```

Preview / debug only (no tray):

```bash
PYTHONPATH=. python -m cv_desk --cli
```

### Permissions (required)

1. **Camera** — allow when prompted  
2. **Accessibility** — System Settings → Privacy & Security → Accessibility → enable **Terminal** / **Python** / your IDE  
   (needed for Mission Control, Spaces, and some media key fallbacks)

Config (auto-created):  
`~/Library/Application Support/CVDesk/config.json`

---

## Architecture

```
cv_desk/
  cv_desk/
    app.py              # tray + preview loop
    config.py
    vision/camera.py    # MediaPipe detect thread
    vision/gestures.py  # state machine
    actions/macos.py    # volume, media, Mission Control, Spaces
    ui/preview.py
  config.default.json
  requirements.txt
```

---

## Product notes

- Cooldown ~0.55s between discrete actions to avoid spam  
- Disarm with fist-hold when you need to gesture at the camera for other apps  
- Toggle individual actions in `config.json` → `actions`  
- v1 is **macOS-only**; Windows later  

---

## License

MIT

# CV Desk

**Control your Mac desk with hand gestures** — play/pause, volume, Spaces, Mission Control, App Exposé, screenshot — from a menu-bar app powered by [MediaPipe](https://ai.google.dev/edge/mediapipe) Hands.

![Platform](https://img.shields.io/badge/platform-macOS%2013%2B-black)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.0.2-blue)
![Release](https://img.shields.io/github/v/release/bocchisad/cv-desk)

---

## Why

Hands free for the trackpad and keyboard — but the desk still needs play/pause, volume, Spaces, and a quick screenshot. CV Desk watches one webcam hand and maps a small, deliberate gesture set onto those actions.

---

## Quick start

```bash
git clone https://github.com/bocchisad/cv-desk.git
cd cv-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m cv_desk
```

Menu bar icon: **CV** → **Show Preview**. Wave a hand in front of the camera.

### Permissions

Grant these to **Python** / **Terminal** / your IDE (the process that runs the venv — not a branded `.app` identity):

| Permission | Needed for |
|------------|------------|
| **Camera** | Hand tracking |
| **Accessibility** | Spaces, Mission Control, App Exposé, System Events |
| **Screen Recording** | Screenshot → Desktop PNG |

Config: `~/Library/Application Support/CVDesk/config.json`

---

## Gestures

| Gesture | Action |
|---------|--------|
| Fist → open palm | Play / Pause |
| Open palm swipe ← / → | Previous / Next track |
| Pinch + move ↑ / ↓ | Volume ± |
| Pinch hold still → HUD `SNAP ✓` → open | Screenshot |
| OK hold ~0.4s | Mute |
| 👍 hold ~0.7s | Mission Control |
| 3 fingers hold ~0.55s | App Exposé |
| 2 fingers swipe ← / → | Switch Desktop Space |
| Fist hold ~1.2s | Arm / Disarm |

**Profiles** (menu → Profiles): per frontmost app, turn action groups on/off. Gestures stay global; sensitivity stays global (Low / Normal / High, or `--calibrate`).

---

## Commands

| | |
|--|--|
| Menu bar | `PYTHONPATH=. python -m cv_desk` |
| Preview only | `PYTHONPATH=. python -m cv_desk --cli` |
| Cameras | `PYTHONPATH=. python -m cv_desk --list-cameras` |
| Calibrate | `PYTHONPATH=. python -m cv_desk --calibrate` |
| Tests | `PYTHONPATH=. python -m unittest discover -s tests -q` |

Optional **dev `.app`** (this machine only — resolves repo + `.venv` at launch, not redistributable):

```bash
./scripts/build_app.sh
open "dist/CV Desk.app"
```

---

## Limitations (v1)

- macOS 13+ only
- **Source install** — GitHub Releases ship source tags, not a notarized binary
- TCC prompts attach to **Python**, not “CV Desk”
- Lighting / camera angle affect MediaPipe reliability
- Continuity Camera: prefer auto FaceTime; switch camera in the tray if needed

---

## Layout

```
cv_desk/           package (tray, vision, actions, UI)
config.default.json
scripts/build_app.sh
tests/
docs/              design notes + release checklist
```

---

## License

MIT — [LICENSE](LICENSE). Changelog: [CHANGELOG.md](CHANGELOG.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

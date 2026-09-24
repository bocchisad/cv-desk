# CV Desk

**Control your Mac desk with hand gestures** — play/pause, volume, Spaces, Mission Control, App Exposé, screenshot — from a menu-bar app powered by MediaPipe Hands.

![Platform](https://img.shields.io/badge/platform-macOS%2013%2B-black)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.0.1-blue)
![Status](https://img.shields.io/badge/release-source%20only-orange)

> **v1.0 is source-first.** Run from a venv (or a local dev `.app` wrapper). There is no notarized binary yet — see [Limitations](#limitations).

<!-- Add after you drop files into docs/media/:
![Preview](docs/media/preview.gif)
-->

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

Look for the **CV** icon in the menu bar → **Show Preview**.

### Permissions (required)

Grant these to **Python** / **Terminal** / your IDE (not “CV Desk” — the launcher eventually runs venv Python):

| Permission | Why |
|------------|-----|
| **Camera** | Hand tracking |
| **Accessibility** | Spaces, Mission Control, App Exposé, System Events |
| **Screen Recording** | Screenshot (Quartz capture → Desktop) |

Config lives at: `~/Library/Application Support/CVDesk/config.json`

---

## Gestures

| Gesture | Action |
|---------|--------|
| **Fist → open palm** | Play / Pause |
| **Open palm swipe** ← / → | Previous / Next track |
| **Pinch + move** ↑ / ↓ | Volume ± |
| **Pinch hold still** → HUD `SNAP ✓` → **open** | Screenshot |
| **OK** hold ~0.4s | Mute |
| **👍 hold** ~0.7s | Mission Control |
| **3 fingers** hold ~0.55s | App Exposé |
| **Two fingers** swipe ← / → | Desktop Space |
| **Fist hold** ~1.2s | Arm / Disarm |

**Per-app profiles:** menu → **Profiles** — enable/disable action groups for the frontmost app (`Name*` = custom). Gestures stay the same; sensitivity is global.

**Sensitivity:** Low / Normal / High, or `PYTHONPATH=. python -m cv_desk --calibrate`

---

## Run options

| Mode | Command |
|------|---------|
| Menu bar (default) | `PYTHONPATH=. python -m cv_desk` |
| Preview window only | `PYTHONPATH=. python -m cv_desk --cli` |
| List cameras | `PYTHONPATH=. python -m cv_desk --list-cameras` |
| Calibrate | `PYTHONPATH=. python -m cv_desk --calibrate` |

### Dev `.app` (optional, this machine only)

```bash
./scripts/build_app.sh
open "dist/CV Desk.app"
```

Resolves the repo + `.venv` at **launch**. Not for redistribution / App Store / Gatekeeper-friendly sharing.

---

## Limitations

- **macOS 13+ only** (no Windows/Linux in v1)
- **Source / venv install** — no frozen notarized `.app` in GitHub Releases
- Privacy prompts attach to **Python**, not a branded app identity
- Continuity Camera / multiple cams: prefer auto FaceTime; switch in the tray if needed
- Gesture accuracy depends on lighting, camera angle, and MediaPipe

---

## Architecture

```
cv_desk/
  app.py              # tray + vision loop
  config.py           # atomic config I/O
  profiles.py         # per-app enable masks
  frontmost.py        # sticky frontmost app
  login_item.py       # Launch at Login
  vision/             # camera + GestureEngine
  actions/macos.py    # volume, media, MC, Spaces, screenshot
  ui/                 # OpenCV HUD + Cocoa preview
```

Design notes: [`docs/`](docs/).

---

## Development

```bash
PYTHONPATH=. python -m unittest discover -s tests -q
```

See [`CHANGELOG.md`](CHANGELOG.md) for release history.

---

## License

MIT — see [LICENSE](LICENSE).

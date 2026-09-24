# CV Desk 1.0.2

Public **source-first** release of CV Desk — macOS menu-bar desk control with hand gestures.

## Install

```bash
git clone https://github.com/bocchisad/cv-desk.git
cd cv-desk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m cv_desk
```

Grant **Camera**, **Accessibility**, and **Screen Recording** to **Python / Terminal / your IDE**.

## What’s in 1.x

- Play/pause, next/prev, volume, mute
- Mission Control, Spaces, App Exposé, screenshot
- Tray app, Cocoa preview, Launch at Login
- Sensitivity presets + calibrate
- Per-app enable/disable profiles
- 1.0.1 reliability fixes (config, login, hand-loss, volume, movable dev `.app`)

## Not included

No notarized binary. Optional `scripts/build_app.sh` builds a **local** venv wrapper only.

Full history: [CHANGELOG.md](https://github.com/bocchisad/cv-desk/blob/main/CHANGELOG.md)

# CV Desk 1.0.1

Patch release after a full reliability audit.

## Install

```bash
git clone https://github.com/bocchisad/cv-desk.git
cd cv-desk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m cv_desk
```

Grant **Camera**, **Accessibility**, and **Screen Recording** to **Python / Terminal** (not the optional local `.app` wrapper).

## Highlights since 1.0.0

- Safer gesture state on hand tracking loss
- Atomic config writes; honest Launch-at-Login status
- Sticky per-app Profiles when the menu bar is open
- Movable dev `.app` launcher (still **not** redistributable)

Full notes: [CHANGELOG.md](https://github.com/bocchisad/cv-desk/blob/main/CHANGELOG.md)

## Assets

This release is **source only** — no notarized binary.

# Contributing

Issues and PRs welcome for macOS gesture/desk-control improvements.

## Dev setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m unittest discover -s tests -q
PYTHONPATH=. python -m cv_desk --cli
```

## Guidelines

- Keep v1 **macOS-only** unless a design doc says otherwise
- Prefer small PRs; match existing gesture / tray patterns
- Add or update unit tests under `tests/` for gesture/config logic
- Do not commit `.venv/`, `dist/`, or `models/*.task`

Release process: [`docs/RELEASE.md`](docs/RELEASE.md).

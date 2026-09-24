# Release checklist (maintainers)

## What CI / git should have before tagging

- [ ] `cv_desk/__init__.py` version matches README badge and `scripts/build_app.sh` plist
- [ ] `CHANGELOG.md` has a section for this version
- [ ] `PYTHONPATH=. python -m unittest discover -s tests -q` passes
- [ ] README Quick start clone URL is correct

## GitHub Release (source-only)

```bash
git tag -a v1.0.1 -m "CV Desk 1.0.1"
git push origin v1.0.1
gh release create v1.0.1 \
  --title "CV Desk 1.0.1" \
  --notes-file docs/release-notes-1.0.1.md
```

Do **not** attach `dist/CV Desk.app` — it is a machine-local venv wrapper.

## Human assets (not automatable here)

Drop into `docs/media/` then uncomment the README preview block:

| File | What to capture |
|------|-----------------|
| `docs/media/preview.gif` | 5–12s: fist→play, pinch volume, SNAP screenshot, 👍 Mission Control |
| `docs/media/tray.png` | Menu bar **CV** menu open (Profiles / Sensitivity visible) |
| `docs/media/hud.png` | Preview window with `SNAP ✓` or `3✋` label |

Tips: clean wallpaper, good lighting, FaceTime camera, crop to preview + a bit of desktop.

## Repo settings (GitHub UI)

- Description: `macOS menu-bar desk control with hand gestures (MediaPipe)`
- Topics: `macos`, `mediapipe`, `gestures`, `rumps`, `accessibility`, `python`
- Homepage: leave empty or link a future demo
- Disable Releases “Set as the latest release” only if you prefer draft — normally publish latest

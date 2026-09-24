# Release checklist (maintainers)

## Before tagging

- [ ] Version aligned: `cv_desk/__init__.py`, README badge, `scripts/build_app.sh` plist, `CHANGELOG.md`
- [ ] `PYTHONPATH=. python -m unittest discover -s tests -q`
- [ ] README Quick start clone URL correct

## Publish (source-only)

```bash
git tag -a vX.Y.Z -m "CV Desk X.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "CV Desk X.Y.Z" --notes-file docs/release-notes-X.Y.Z.md
```

Do **not** attach `dist/CV Desk.app`.

## Optional later

Screenshots / GIF under `docs/media/` — not required for a valid source release.

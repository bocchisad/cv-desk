# macOS .app bundle

**Date:** 2026-09-23 (updated 2026-09-24)  
**Status:** Dev-only wrapper

`scripts/build_app.sh` builds `dist/CV Desk.app` that:

1. Resolves the **cv_desk repo** as `../../..` from `Contents/MacOS` (so moving the whole tree works)
2. Picks `$ROOT/.venv` or `$ROOT/../.venv` at **launch** (not bake-time absolute paths)
3. Runs `python -m cv_desk`

## Not redistributable

No frozen deps, no codesign/notarize, no bundled MediaPipe model. Privacy prompts usually attach to **Python**, not “CV Desk”.

## Rebuild after version bumps

```bash
./scripts/build_app.sh
open "dist/CV Desk.app"
```

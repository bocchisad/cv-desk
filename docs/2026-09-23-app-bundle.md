# Phase A — .app + Launch at Login

**Date:** 2026-09-23  
**Status:** Approved / implemented

## Bundle

`scripts/build_app.sh` → `dist/CV Desk.app`

- `LSUIElement=1` (menu bar only)
- `Contents/MacOS/CVDesk` bash launcher → repo `PYTHONPATH` + existing `.venv`
- Does **not** copy venv into the bundle (dev-friendly)

## Launch at Login

Tray → **Launch at Login** writes/removes  
`~/Library/LaunchAgents/com.bocchisad.cvdesk.plist`  
pointing at `CV Desk.app/Contents/MacOS/CVDesk`.

## Usage

```bash
./scripts/build_app.sh
open "dist/CV Desk.app"
# then CV menu → Launch at Login
```

Grant **Accessibility** + **Camera** to **CV Desk** (or the underlying Python) in System Settings.

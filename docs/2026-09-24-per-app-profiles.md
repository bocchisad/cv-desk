# Phase D — Per-app profiles

**Date:** 2026-09-24  
**Status:** Implemented

Same gestures everywhere. Frontmost app can only **enable/disable** action groups.

## Config

```json
"actions": { "volume": true, "spaces": true },
"profiles": {
  "com.spotify.client": { "spaces": false, "screenshot": false },
  "dev.cursor": { "spaces": false, "app_expose": false }
}
```

## Tray

**Profiles** — checkboxes for the frontmost app + **Reset this app to default**.

Preview HUD: `app: Cursor*`.

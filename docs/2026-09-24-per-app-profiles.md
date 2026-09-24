# Phase D — Per-app profiles

**Date:** 2026-09-24  
**Status:** Implemented

Frontmost app (`NSWorkspace`) selects optional action overrides. Sensitivity stays global.

## Config

```json
"actions": { "volume": true, "spaces": true, "...": true },
"profiles": {
  "com.spotify.client": { "spaces": false, "screenshot": false },
  "com.apple.Safari": { "volume": false, "next_prev": false }
}
```

Merge: `effective = actions ⊕ profiles[bundle_id]` (overrides win).

## Tray

**Profiles** menu:
- Shows current frontmost app (`Name*` if a profile exists)
- Checkable action toggles write overrides for that app
- **Reset this app to default** clears its profile

Preview HUD: `app: Spotify*`

## Non-goals (v1)

Per-app sensitivity, gesture remapping, automatic profiles.

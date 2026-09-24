# CV Desk v1 — Design

**Date:** 2026-09-23  
**Platform:** macOS 13+  
**Stack:** Python 3.10+, MediaPipe Hands, OpenCV, rumps (menu bar), Quartz/osascript actions  
**Approved:** Hybrid media + desk controls

## Gestures

| Gesture | Action |
|---------|--------|
| Fist → open palm | Play/Pause |
| Open palm swipe L/R | Previous / Next track |
| Pinch + vertical move | Volume ± (natural thumb+index pinch) |
| Pinch hold still → `SNAP ✓` → open | Screenshot |
| 3 fingers hold ~0.55s | App Exposé |
| OK sign hold ~0.4s | Mute toggle |
| Thumbs-up hold ~0.7s | Mission Control |
| Two-finger horizontal swipe | Desktop Space ←/→ |
| Fist hold ~1.2s | Arm/disarm recognition |

## Non-goals v1

Mouse cursor, drawing, Windows, voice, multi-monitor UI chrome.

## Architecture

- Background camera+detect thread
- Gesture state machine with cooldown/hysteresis
- Menu bar app + optional preview window
- JSON config for toggles/sensitivity

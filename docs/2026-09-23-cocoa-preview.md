# Phase B — Cocoa preview in tray

**Date:** 2026-09-23  
**Status:** Implemented

## What

Tray **Show Preview** opens a floating AppKit `NSWindow` with live camera + HUD.

- Frames drawn with OpenCV on the vision thread (`draw_preview`)
- JPEG → `NSImage` on the rumps main thread (~14 fps)
- No OpenCV HighGUI in tray (avoids macOS thread crash)
- Closing the window clears the menu check

## CLI

`--cli` still uses OpenCV `imshow` on the main thread.

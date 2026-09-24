# Changelog

All notable changes to CV Desk are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/). Versioning: [SemVer](https://semver.org/).

## [1.0.1] — 2026-09-24

### Fixed

- Hand-loss no longer leaves fist / App Exposé latch stuck (false play-pause / arm toggles)
- Swipe cool-down applied only after a successful fire
- Pinch→OK no longer triggers accidental screenshot
- Config saves are atomic + locked; camera index `0` is not forcibly reset every launch
- Launch at Login reports real `launchctl` state; failed enable removes the plist
- Frontmost app for Profiles sticks past Terminal/Python when the menu is open
- Volume no longer jumps to ~50 on read failure; next/prev AppleScript is honest
- Screenshot filenames avoid same-second overwrite
- Dev `.app` launcher uses paths relative to the bundle (movable repo tree)
- Model download no longer falls back to unverified SSL

### Changed

- Default sensitivity matches the **normal** preset (`pinch_vol_sensitivity` 2.4)
- Docs/README: source-first install, Screen Recording called out

## [1.0.0] — 2026-09-24

### Added

- Gesture desk control: play/pause, next/prev, volume, mute, Mission Control, Spaces
- Screenshot (pinch hold → SNAP ✓ → open) via Quartz → Desktop
- App Exposé (3-finger hold)
- Menu-bar tray (rumps), Cocoa preview, Launch at Login
- Sensitivity presets + CLI calibrate
- Per-app enable/disable profiles (frontmost app)

## [0.1.0] — 2026-09-23

### Added

- Initial CV Desk prototype (tray, gestures, packaging scripts)

[1.0.1]: https://github.com/bocchisad/cv-desk/releases/tag/v1.0.1
[1.0.0]: https://github.com/bocchisad/cv-desk/releases/tag/v1.0.1
[0.1.0]: https://github.com/bocchisad/cv-desk/commits/main

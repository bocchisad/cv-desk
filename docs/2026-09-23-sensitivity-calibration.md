# Sensitivity calibration — Design

**Date:** 2026-09-23  
**Status:** Approved (C: presets + wizard)

## Presets (tray → Sensitivity)

| Preset | swipe_vx | pinch_vol_sensitivity | cooldown_sec |
|--------|----------|----------------------|--------------|
| Low    | 0.75     | 1.2                  | 0.70         |
| Normal | 0.55     | 1.8                  | 0.55         |
| High   | 0.35     | 2.6                  | 0.40         |

Applied live to `GestureEngine` + saved to user `config.json`.  
`sensitivity_preset` field tracks name; wizard sets it to `"custom"`.

## Wizard (`python -m cv_desk --calibrate`)

CLI OpenCV window (main thread). No macOS actions dispatched.

1. **Swipe** — 3 open-palm horizontal bursts → `swipe_vx = clamp(0.65 * median(|vx_peak|), 0.2, 1.2)`
2. **Pinch** — 2 vertical pinch travels → sensitivity so median travel ≈ 3.5 volume steps  
   (`pinch_vol_sensitivity = clamp(3.5 / (travel * 40), 0.8, 4.0)`)
3. **Save** (s / Enter) or **Cancel** (Esc). Space skips a phase (keeps current values).

## Non-goals

Tray sliders, AppKit UI, fist/OK threshold calibration.

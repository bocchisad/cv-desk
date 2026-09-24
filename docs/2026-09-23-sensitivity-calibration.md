# Sensitivity calibration

**Date:** 2026-09-23 (synced 2026-09-24)  
**Status:** Implemented

## Presets (`cv_desk/sensitivity.py`)

| Preset | swipe_vx | pinch_vol_sensitivity | cooldown_sec |
|--------|----------|----------------------|--------------|
| low | 0.55 | 1.6 | 0.55 |
| normal | 0.38 | 2.4 | 0.40 |
| high | 0.26 | 3.2 | 0.28 |

`config.default.json` matches **normal**.

## Calibrate formulas (code)

- Swipe threshold: `clamp(0.45 * median(peaks), 0.18, 0.85)`
- Pinch sensitivity: `clamp(target_steps / (median(travel) * 40), 0.8, 4.0)`

## CLI

```bash
PYTHONPATH=. python -m cv_desk --calibrate
```

Tray → Sensitivity → Calibrate… points at the same command.

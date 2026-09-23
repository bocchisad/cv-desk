"""Sensitivity presets + apply helpers."""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, float]] = {
    # Lower swipe_vx / higher pinch = easier to trigger.
    "low": {"swipe_vx": 0.55, "pinch_vol_sensitivity": 1.6, "cooldown_sec": 0.55},
    "normal": {"swipe_vx": 0.38, "pinch_vol_sensitivity": 2.4, "cooldown_sec": 0.40},
    "high": {"swipe_vx": 0.26, "pinch_vol_sensitivity": 3.2, "cooldown_sec": 0.28},
}

SENS_KEYS = ("swipe_vx", "pinch_vol_sensitivity", "cooldown_sec")


def preset_values(name: str) -> dict[str, float]:
    key = name.strip().lower()
    if key not in PRESETS:
        raise KeyError(f"unknown preset: {name}")
    return dict(PRESETS[key])


def match_preset(cfg: dict[str, Any]) -> str:
    """Return low|normal|high|custom based on current numeric fields."""
    for name, vals in PRESETS.items():
        if all(abs(float(cfg.get(k, vals[k])) - vals[k]) < 1e-6 for k in SENS_KEYS):
            return name
    return "custom"


def apply_to_config(cfg: dict[str, Any], values: dict[str, float], preset: str) -> dict[str, Any]:
    out = dict(cfg)
    for k in SENS_KEYS:
        if k in values:
            out[k] = float(values[k])
    out["sensitivity_preset"] = preset
    return out


def apply_to_engine(engine: Any, values: dict[str, float]) -> None:
    if "swipe_vx" in values:
        engine.swipe_vx = float(values["swipe_vx"])
    if "pinch_vol_sensitivity" in values:
        engine.pinch_vol_sensitivity = float(values["pinch_vol_sensitivity"])
    if "cooldown_sec" in values:
        engine.cooldown_sec = float(values["cooldown_sec"])


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def swipe_vx_from_peaks(peaks: list[float]) -> float:
    if not peaks:
        raise ValueError("no swipe peaks")
    s = sorted(abs(p) for p in peaks)
    mid = s[len(s) // 2]
    # Threshold below typical peak so casual repeats still fire.
    return clamp(0.45 * mid, 0.18, 0.85)


def pinch_sens_from_travels(travels: list[float], target_steps: float = 3.5) -> float:
    if not travels:
        raise ValueError("no pinch travels")
    s = sorted(abs(t) for t in travels if t > 1e-4)
    if not s:
        raise ValueError("pinch travels too small")
    mid = s[len(s) // 2]
    return clamp(target_steps / (mid * 40.0), 0.8, 4.0)

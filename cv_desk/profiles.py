"""Per-app action profiles (enable/disable overlays, no sensitivity / remap)."""

from __future__ import annotations

from typing import Any

# Keys under config["actions"] / config["profiles"][bundle_id]
ACTION_KEYS: tuple[str, ...] = (
    "play_pause",
    "next_prev",
    "volume",
    "mute",
    "mission_control",
    "spaces",
    "app_expose",
    "screenshot",
)

ACTION_LABELS: dict[str, str] = {
    "play_pause": "Play/Pause",
    "next_prev": "Next/Prev",
    "volume": "Volume",
    "mute": "Mute",
    "mission_control": "Mission Control",
    "spaces": "Spaces",
    "app_expose": "App Exposé",
    "screenshot": "Screenshot",
}


def _legacy_flat_actions(entry: dict[str, Any]) -> dict[str, bool]:
    return {k: bool(v) for k, v in entry.items() if k in ACTION_KEYS}


def parse_profile(entry: Any) -> dict[str, bool]:
    """
    Normalize a profile entry to action overrides.

    Flat: {"spaces": false}
    Nested (from brief remap era): {"actions": {...}, "remap": ...} — remap ignored.
    """
    if not isinstance(entry, dict) or not entry:
        return {}
    if "actions" in entry:
        return {
            k: bool(v)
            for k, v in dict(entry.get("actions") or {}).items()
            if k in ACTION_KEYS
        }
    return _legacy_flat_actions(entry)


def get_profile_entry(cfg: dict[str, Any], bundle_id: str) -> dict[str, Any]:
    if not bundle_id:
        return {}
    raw = (cfg.get("profiles") or {}).get(bundle_id) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def base_actions(cfg: dict[str, Any]) -> dict[str, bool]:
    raw = cfg.get("actions") or {}
    return {k: bool(raw.get(k, True)) for k in ACTION_KEYS}


def app_overrides(cfg: dict[str, Any], bundle_id: str) -> dict[str, bool]:
    return parse_profile(get_profile_entry(cfg, bundle_id))


def effective_actions(cfg: dict[str, Any], bundle_id: str) -> dict[str, bool]:
    """Global actions merged with optional per-app overrides."""
    out = base_actions(cfg)
    out.update(app_overrides(cfg, bundle_id))
    return out


def is_enabled(cfg: dict[str, Any], bundle_id: str, key: str) -> bool:
    return bool(effective_actions(cfg, bundle_id).get(key, True))


def set_app_action(cfg: dict[str, Any], bundle_id: str, key: str, enabled: bool) -> dict[str, Any]:
    """Write one override for an app (flat profile format)."""
    if not bundle_id or key not in ACTION_KEYS:
        return cfg
    out = dict(cfg)
    profiles = dict(out.get("profiles") or {})
    entry = dict(parse_profile(profiles.get(bundle_id) or {}))
    entry[key] = bool(enabled)
    profiles[bundle_id] = entry
    out["profiles"] = profiles
    return out


def clear_app_profile(cfg: dict[str, Any], bundle_id: str) -> dict[str, Any]:
    if not bundle_id:
        return cfg
    out = dict(cfg)
    profiles = dict(out.get("profiles") or {})
    profiles.pop(bundle_id, None)
    out["profiles"] = profiles
    return out


def has_app_profile(cfg: dict[str, Any], bundle_id: str) -> bool:
    return bool(parse_profile(get_profile_entry(cfg, bundle_id)))


def merge_profile_maps(default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge profiles into flat per-bundle action overrides."""
    bids = set(default or {}) | set(user or {})
    out: dict[str, Any] = {}
    for bid in bids:
        merged = {**parse_profile((default or {}).get(bid)), **parse_profile((user or {}).get(bid))}
        if merged:
            out[bid] = merged
    return out

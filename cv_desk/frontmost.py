"""Frontmost macOS application (for per-app gesture profiles)."""

from __future__ import annotations


def frontmost_app() -> tuple[str, str]:
    """Return (bundle_id, localized_name). Empty id if unavailable."""
    try:
        from AppKit import NSWorkspace  # type: ignore
    except Exception:
        return "", "?"

    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return "", "?"
        bid = str(app.bundleIdentifier() or "")
        name = str(app.localizedName() or bid or "?")
        return bid, name
    except Exception:
        return "", "?"

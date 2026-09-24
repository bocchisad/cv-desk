"""Frontmost macOS application (for per-app gesture profiles)."""

from __future__ import annotations

# Bundle ids / names that are "us" — sticky frontmost should ignore these.
_SELF_BUNDLES = frozenset(
    {
        "com.bocchisad.cvdesk",
        "org.python.python",
        "com.apple.Terminal",
        "com.googlecode.iterm2",
        "com.apple.dt.Xcode",  # rare
    }
)
_SELF_NAME_FRAGMENTS = ("python", "cv desk", "terminal", "iterm")


def is_self_app(bundle_id: str, name: str) -> bool:
    bid = (bundle_id or "").lower()
    nm = (name or "").lower()
    if bid in {b.lower() for b in _SELF_BUNDLES}:
        return True
    if bid.startswith("com.apple.python"):
        return True
    return any(frag in nm for frag in _SELF_NAME_FRAGMENTS)


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

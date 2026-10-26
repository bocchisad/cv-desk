"""Frontmost macOS application (for per-app gesture profiles)."""

from __future__ import annotations

import logging
import os
import time

from cv_desk._objc_exc import OBJC_CATCH

log = logging.getLogger(__name__)

# Only our own app identity — do NOT filter Terminal / iTerm / Xcode / python hosts
# so profiles can target those apps when they are frontmost.
_SELF_BUNDLES = frozenset(
    {
        "com.bocchisad.cvdesk",
    }
)
_SELF_NAMES = frozenset({"cv desk", "cvdesk"})


def is_self_app(bundle_id: str, name: str, pid: int | None = None) -> bool:
    """True only for this CV Desk process (bundle id, exact name, or our PID)."""
    if pid is not None and pid == os.getpid():
        return True
    bid = (bundle_id or "").lower()
    if bid in {b.lower() for b in _SELF_BUNDLES}:
        return True
    nm = (name or "").lower().strip()
    return nm in _SELF_NAMES


def _pump_runloop(seconds: float = 0.02) -> None:
    """Give Cocoa a chance to update frontmostApplication (needed without rumps)."""
    try:
        from Foundation import NSDate, NSRunLoop  # type: ignore
    except ImportError:
        return
    try:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(float(seconds))
        )
    except OBJC_CATCH as e:
        log.debug("NSRunLoop pump: %s", e)


def frontmost_app(*, pump: bool = False) -> tuple[str, str]:
    """Return (bundle_id, localized_name). Empty id if unavailable."""
    bid, name, _pid = frontmost_app_info(pump=pump)
    return bid, name


def frontmost_app_info(*, pump: bool = False) -> tuple[str, str, int | None]:
    """Return (bundle_id, localized_name, process_id)."""
    if pump:
        _pump_runloop(0.02)
    try:
        from AppKit import NSWorkspace  # type: ignore
    except ImportError:
        return "", "?", None

    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return "", "?", None
        bid = str(app.bundleIdentifier() or "")
        name = str(app.localizedName() or bid or "?")
        try:
            pid = int(app.processIdentifier())
        except (TypeError, ValueError, AttributeError):
            pid = None
        return bid, name, pid
    except OBJC_CATCH as e:
        log.debug("frontmostApplication: %s", e)
        return "", "?", None


# Tiny helper for CLI loops that need periodic Cocoa pumping without AppKit imports elsewhere.
_last_pump = 0.0


def maybe_pump_cocoa(interval: float = 0.25) -> None:
    global _last_pump
    now = time.monotonic()
    if now - _last_pump < interval:
        return
    _last_pump = now
    _pump_runloop(0.01)

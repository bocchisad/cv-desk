"""macOS system actions: media keys, volume, Mission Control, Spaces."""

from __future__ import annotations

import subprocess
import time
from typing import Callable

# NX media key codes
_NX_SOUND_UP = 0
_NX_SOUND_DOWN = 1
_NX_MUTE = 7
_NX_PLAY = 16
_NX_NEXT = 17
_NX_PREV = 18


def _osascript(script: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "osascript failed").strip()
        return True, (r.stdout or "").strip()
    except Exception as e:
        return False, str(e)


def _media_key_quartz(key: int) -> bool:
    """Post system-defined media key via AppKit/Quartz."""
    try:
        from AppKit import NSEvent, NSSystemDefined  # type: ignore
        from Quartz import CGEventPost, kCGHIDEventTap  # type: ignore
    except Exception:
        return False

    def post(down: bool) -> None:
        flags = 0xA00 if down else 0xB00
        data1 = (key << 16) | ((0xA if down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            NSSystemDefined,
            (0.0, 0.0),
            flags,
            0,
            0,
            None,
            8,
            data1,
            -1,
        )
        CGEventPost(kCGHIDEventTap, ev.CGEvent())

    try:
        post(True)
        time.sleep(0.02)
        post(False)
        return True
    except Exception:
        return False


def _media_key(key: int) -> tuple[bool, str]:
    if _media_key_quartz(key):
        return True, "ok"
    # Fallback: Control+F8 style won't work; try Spotify scripting for play
    return False, "media key failed (grant Accessibility? install pyobjc)"


def play_pause() -> tuple[bool, str]:
    ok, msg = _media_key(_NX_PLAY)
    if ok:
        return True, "play/pause"
    for app in ("Spotify", "Music"):
        ok2, out = _osascript(
            f'if application "{app}" is running then\n'
            f'  tell application "{app}" to playpause\n'
            f'  return "ok"\n'
            f'end if\n'
            f'return "no"'
        )
        if ok2 and out.strip() == "ok":
            return True, f"play/pause ({app})"
    return False, msg or "play/pause failed"


def next_track() -> tuple[bool, str]:
    ok, msg = _media_key(_NX_NEXT)
    if ok:
        return True, "next"
    for app in ("Spotify", "Music"):
        ok2, _ = _osascript(f'try\n tell application "{app}" to next track\nend try')
        if ok2:
            return True, f"next ({app})"
    return ok, msg


def prev_track() -> tuple[bool, str]:
    ok, msg = _media_key(_NX_PREV)
    if ok:
        return True, "previous"
    for app in ("Spotify", "Music"):
        ok2, _ = _osascript(f'try\n tell application "{app}" to previous track\nend try')
        if ok2:
            return True, f"previous ({app})"
    return ok, msg


def get_volume() -> int:
    ok, out = _osascript("output volume of (get volume settings)")
    if not ok:
        return 50
    try:
        return int(float(out))
    except ValueError:
        return 50


def set_volume(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))
    ok, msg = _osascript(f"set volume output volume {level}")
    return ok, f"volume {level}" if ok else msg


def volume_delta(delta: int) -> tuple[bool, str]:
    return set_volume(get_volume() + delta)


def mute_toggle() -> tuple[bool, str]:
    ok, out = _osascript("output muted of (get volume settings)")
    if not ok:
        # try media mute key
        return _media_key(_NX_MUTE)
    muted = out.strip().lower() == "true"
    ok2, msg = _osascript(f"set volume output muted {str(not muted).lower()}")
    return ok2, ("unmute" if muted else "mute") if ok2 else msg


def mission_control() -> tuple[bool, str]:
    # Control + Up Arrow
    ok, msg = _osascript(
        'tell application "System Events" to key code 126 using {control down}'
    )
    if ok:
        return True, "Mission Control"
    ok2, msg2 = _osascript('tell application "Mission Control" to launch')
    return (True, "Mission Control") if ok2 else (False, msg2 or msg)


def space_left() -> tuple[bool, str]:
    ok, msg = _osascript(
        'tell application "System Events" to key code 123 using {control down}'
    )
    return (True, "Space ←") if ok else (False, msg)


def space_right() -> tuple[bool, str]:
    ok, msg = _osascript(
        'tell application "System Events" to key code 124 using {control down}'
    )
    return (True, "Space →") if ok else (False, msg)


ACTIONS: dict[str, Callable[[], tuple[bool, str]]] = {
    "play_pause": play_pause,
    "next": next_track,
    "prev": prev_track,
    "mute": mute_toggle,
    "mission_control": mission_control,
    "space_left": space_left,
    "space_right": space_right,
}

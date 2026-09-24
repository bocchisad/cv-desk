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
        ok2, out = _osascript(
            f'if application "{app}" is running then\n'
            f'  tell application "{app}" to next track\n'
            f'  return "ok"\n'
            f'end if\n'
            f'return "no"'
        )
        if ok2 and out.strip() == "ok":
            return True, f"next ({app})"
    return False, msg or "next failed"


def prev_track() -> tuple[bool, str]:
    ok, msg = _media_key(_NX_PREV)
    if ok:
        return True, "previous"
    for app in ("Spotify", "Music"):
        ok2, out = _osascript(
            f'if application "{app}" is running then\n'
            f'  tell application "{app}" to previous track\n'
            f'  return "ok"\n'
            f'end if\n'
            f'return "no"'
        )
        if ok2 and out.strip() == "ok":
            return True, f"previous ({app})"
    return False, msg or "previous failed"


def get_volume() -> int | None:
    ok, out = _osascript("output volume of (get volume settings)")
    if not ok:
        return None
    try:
        return int(float(out))
    except ValueError:
        return None


def set_volume(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))
    ok, msg = _osascript(f"set volume output volume {level}")
    return ok, f"volume {level}" if ok else msg


def volume_delta(delta: int) -> tuple[bool, str]:
    cur = get_volume()
    if cur is None:
        return False, "volume read failed (Accessibility?)"
    return set_volume(cur + delta)


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


def app_expose() -> tuple[bool, str]:
    # Control + Down Arrow — Application windows
    ok, msg = _osascript(
        'tell application "System Events" to key code 125 using {control down}'
    )
    return (True, "App Exposé") if ok else (False, msg)


def screenshot() -> tuple[bool, str]:
    """
    Capture the main display to Desktop.

    Synthetic ⌘⇧3 via System Events often returns OK but writes nothing on
    modern macOS. Quartz CGWindowListCreateImage is reliable when the process
    may read the screen (Screen Recording for Terminal / CV Desk.app).
    """
    from pathlib import Path

    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d at %H.%M.%S")
    path = desktop / f"Screenshot {stamp}.png"
    n = 1
    while path.exists():
        path = desktop / f"Screenshot {stamp}-{n}.png"
        n += 1

    try:
        from Foundation import NSURL  # type: ignore
        from Quartz import (  # type: ignore
            CGImageDestinationAddImage,
            CGImageDestinationCreateWithURL,
            CGImageDestinationFinalize,
            CGRectInfinite,
            CGWindowListCreateImage,
            kCGNullWindowID,
            kCGWindowImageDefault,
            kCGWindowListOptionOnScreenOnly,
        )
    except Exception as e:
        return False, f"screenshot deps: {e}"

    try:
        img = CGWindowListCreateImage(
            CGRectInfinite,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            kCGWindowImageDefault,
        )
        if img is None:
            return False, "screenshot blocked (grant Screen Recording to CV Desk / Terminal)"
        url = NSURL.fileURLWithPath_(str(path))
        dest = CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        if dest is None:
            return False, "screenshot: cannot write PNG"
        CGImageDestinationAddImage(dest, img, None)
        if not CGImageDestinationFinalize(dest):
            return False, "screenshot: finalize failed"
        if not path.is_file():
            return False, "screenshot: file missing after write"
        return True, f"screenshot → {path.name}"
    except Exception as e:
        return False, str(e)


ACTIONS: dict[str, Callable[[], tuple[bool, str]]] = {
    "play_pause": play_pause,
    "next": next_track,
    "prev": prev_track,
    "mute": mute_toggle,
    "mission_control": mission_control,
    "space_left": space_left,
    "space_right": space_right,
    "app_expose": app_expose,
    "screenshot": screenshot,
}

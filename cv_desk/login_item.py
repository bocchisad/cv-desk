"""Launch at Login via LaunchAgent (macOS)."""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

LABEL = "com.bocchisad.cvdesk"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
REPO_ROOT = Path(__file__).resolve().parents[1]


def discover_launcher() -> Path | None:
    """Resolve Contents/MacOS/CVDesk for the built .app."""
    env = os.environ.get("CVDESK_APP_BUNDLE")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env) / "Contents" / "MacOS" / "CVDesk")
    candidates.extend(
        [
            REPO_ROOT / "dist" / "CV Desk.app" / "Contents" / "MacOS" / "CVDesk",
            Path("/Applications/CV Desk.app/Contents/MacOS/CVDesk"),
            Path.home() / "Applications" / "CV Desk.app" / "Contents" / "MacOS" / "CVDesk",
        ]
    )
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def is_enabled() -> bool:
    return PLIST_PATH.is_file()


def enable(launcher: Path | None = None) -> tuple[bool, str]:
    path = launcher or discover_launcher()
    if path is None:
        return False, "build app first: scripts/build_app.sh"
    path = path.resolve()
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Label": LABEL,
        "ProgramArguments": [str(path)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "ProcessType": "Interactive",
    }
    with PLIST_PATH.open("wb") as f:
        plistlib.dump(data, f)
    # Prefer bootstrap (modern) with fallback to load
    uid = os.getuid()
    r = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        r2 = subprocess.run(
            ["launchctl", "load", str(PLIST_PATH)],
            capture_output=True,
            text=True,
        )
        if r2.returncode != 0:
            err = (r.stderr or r2.stderr or r.stdout or r2.stdout or "launchctl failed").strip()
            return False, err[:120]
    return True, f"login: {path.name}"


def disable() -> tuple[bool, str]:
    uid = os.getuid()
    if PLIST_PATH.is_file():
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)],
            capture_output=True,
        )
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        try:
            PLIST_PATH.unlink()
        except OSError as e:
            return False, str(e)
    return True, "login off"

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


def _uid() -> int:
    return os.getuid()


def _domain_target() -> str:
    return f"gui/{_uid()}/{LABEL}"


def is_enabled() -> bool:
    """True only if launchctl knows the job (not merely that a plist file exists)."""
    r = subprocess.run(
        ["launchctl", "print", _domain_target()],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def _bootout() -> None:
    subprocess.run(
        ["launchctl", "bootout", f"gui/{_uid()}", str(PLIST_PATH)],
        capture_output=True,
    )
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)


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
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "CVDesk.login.out.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "CVDesk.login.err.log"),
    }
    # Replace any prior job so re-enable is idempotent.
    _bootout()
    with PLIST_PATH.open("wb") as f:
        plistlib.dump(data, f)
    r = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{_uid()}", str(PLIST_PATH)],
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
            try:
                PLIST_PATH.unlink()
            except OSError:
                pass
            return False, err[:120]
    if not is_enabled():
        try:
            PLIST_PATH.unlink()
        except OSError:
            pass
        return False, "login agent not loaded"
    return True, f"login: {path.name}"


def disable() -> tuple[bool, str]:
    _bootout()
    if PLIST_PATH.is_file():
        try:
            PLIST_PATH.unlink()
        except OSError as e:
            return False, str(e)
    return True, "login off"

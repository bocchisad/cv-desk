"""Load / save user config (atomic writes, thread-safe)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from cv_desk.profiles import merge_profile_maps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config.default.json"
USER_PATH = Path.home() / "Library" / "Application Support" / "CVDesk" / "config.json"

_lock = threading.RLock()


def ensure_user_config() -> Path:
    USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USER_PATH.exists():
        shutil.copy(DEFAULT_PATH, USER_PATH)
    return USER_PATH


def load_config() -> dict[str, Any]:
    with _lock:
        ensure_user_config()
        default = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
        try:
            user = json.loads(USER_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt file — keep a backup and fall back to defaults.
            bak = USER_PATH.with_suffix(".json.bak")
            try:
                shutil.copy(USER_PATH, bak)
            except OSError:
                pass
            user = {}
        if not isinstance(user, dict):
            user = {}
        # One-time migration for *legacy* installs that never chose a camera:
        # only rewrite 0 → auto when the migration flag is absent.
        if user.get("camera_index") == 0 and not user.get("_camera_migrated_v1"):
            user["camera_index"] = "auto"
            user["_camera_migrated_v1"] = True
            _atomic_write(USER_PATH, user)
        elif "camera_index" in user:
            user["_camera_migrated_v1"] = True
        merged = {**default, **user}
        actions = default.get("actions") or {}
        user_actions = user.get("actions") if isinstance(user.get("actions"), dict) else {}
        merged["actions"] = {**actions, **user_actions}
        merged["profiles"] = merge_profile_maps(
            default.get("profiles") if isinstance(default.get("profiles"), dict) else {},
            user.get("profiles") if isinstance(user.get("profiles"), dict) else {},
        )
        return merged


def save_config(cfg: dict[str, Any]) -> None:
    with _lock:
        ensure_user_config()
        out = dict(cfg)
        # Preserve migration flag so we never re-force camera 0 → auto.
        out["_camera_migrated_v1"] = True
        _atomic_write(USER_PATH, out)


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix="cvdesk-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

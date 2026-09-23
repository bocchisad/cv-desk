"""Load / save user config."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config.default.json"
USER_PATH = Path.home() / "Library" / "Application Support" / "CVDesk" / "config.json"


def ensure_user_config() -> Path:
    USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USER_PATH.exists():
        shutil.copy(DEFAULT_PATH, USER_PATH)
    return USER_PATH


def load_config() -> dict[str, Any]:
    ensure_user_config()
    default = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    user = json.loads(USER_PATH.read_text(encoding="utf-8"))
    # Old installs defaulted to 0; with Continuity Camera that is often the iPhone.
    if user.get("camera_index") == 0:
        user["camera_index"] = "auto"
        USER_PATH.write_text(json.dumps(user, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    merged = {**default, **user}
    merged["actions"] = {**default.get("actions", {}), **user.get("actions", {})}
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    ensure_user_config()
    USER_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

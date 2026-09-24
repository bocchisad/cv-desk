"""Preview window + HUD overlay."""

from __future__ import annotations

import cv2
import numpy as np

from cv_desk.vision.gestures import (
    INDEX_TIP,
    MIDDLE_TIP,
    RING_TIP,
    PINKY_TIP,
    THUMB_TIP,
    WRIST,
    MIDDLE_MCP,
)


_CONNECTIONS = (
    (WRIST, MIDDLE_MCP),
    (WRIST, THUMB_TIP),
    (MIDDLE_MCP, INDEX_TIP),
    (MIDDLE_MCP, MIDDLE_TIP),
    (MIDDLE_MCP, RING_TIP),
    (MIDDLE_MCP, PINKY_TIP),
)


def draw_preview(
    frame: np.ndarray,
    lms,
    label: str,
    armed: bool,
    last_action: str,
    profile: str = "",
) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    if lms is not None:
        pts = {}
        for i, p in enumerate(lms):
            pts[i] = (int(p.x * w), int(p.y * h))
        for a, b in _CONNECTIONS:
            if a in pts and b in pts:
                cv2.line(out, pts[a], pts[b], (90, 200, 120), 2, cv2.LINE_AA)
        for i in (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP, WRIST):
            if i in pts:
                cv2.circle(out, pts[i], 5, (40, 220, 255), -1, cv2.LINE_AA)

    # HUD bar
    bar_h = 68 if profile else 52
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), (20, 22, 26), -1)
    cv2.addWeighted(overlay, 0.72, out, 0.28, 0, out)
    arm = "ON" if armed else "OFF"
    color = (100, 255, 140) if armed else (80, 80, 220)
    cv2.putText(out, f"CV Desk  [{arm}]", (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(
        out,
        f"{label}" + (f"  ·  {last_action}" if last_action else ""),
        (12, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    if profile:
        cv2.putText(
            out,
            f"app: {profile}",
            (12, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (160, 200, 255),
            1,
            cv2.LINE_AA,
        )
    return out

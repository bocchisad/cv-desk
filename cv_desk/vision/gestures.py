"""Hand landmarks helpers + gesture state machine for CV Desk."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

# MediaPipe indices
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_PIP = 6
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_PIP = 10
MIDDLE_MCP = 9
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18


def _d(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_size(lms) -> float:
    return max(_d(lms[WRIST], lms[MIDDLE_MCP]), 1e-3)


def finger_up(lms, tip: int, pip: int) -> bool:
    return lms[tip].y < lms[pip].y - 0.02


def finger_folded(lms, tip: int, pip: int) -> bool:
    return lms[tip].y > lms[pip].y - 0.005


def is_fist(lms) -> bool:
    return all(
        finger_folded(lms, t, p)
        for t, p in (
            (INDEX_TIP, INDEX_PIP),
            (MIDDLE_TIP, MIDDLE_PIP),
            (RING_TIP, RING_PIP),
            (PINKY_TIP, PINKY_PIP),
        )
    )


def is_open_palm(lms) -> bool:
    ups = [
        finger_up(lms, INDEX_TIP, INDEX_PIP),
        finger_up(lms, MIDDLE_TIP, MIDDLE_PIP),
        finger_up(lms, RING_TIP, RING_PIP),
        finger_up(lms, PINKY_TIP, PINKY_PIP),
    ]
    if not all(ups):
        return False
    tips = [lms[INDEX_TIP], lms[MIDDLE_TIP], lms[RING_TIP], lms[PINKY_TIP]]
    spread = sum(_d(tips[i], tips[i + 1]) for i in range(3)) / hand_size(lms)
    return spread > 0.45


def is_ok(lms) -> bool:
    """Thumb tip near index tip, other fingers up."""
    hs = hand_size(lms)
    near = _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs < 0.22
    others = (
        finger_up(lms, MIDDLE_TIP, MIDDLE_PIP)
        and finger_up(lms, RING_TIP, RING_PIP)
        and finger_up(lms, PINKY_TIP, PINKY_PIP)
    )
    return near and others


def is_pinch(lms) -> bool:
    hs = hand_size(lms)
    pin = _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs
    mid_away = not finger_up(lms, MIDDLE_TIP, MIDDLE_PIP) or (
        _d(lms[INDEX_TIP], lms[MIDDLE_TIP]) / hs > 0.28
    )
    return pin < 0.42 and mid_away and not is_ok(lms)


def is_two_finger(lms) -> bool:
    return (
        finger_up(lms, INDEX_TIP, INDEX_PIP)
        and finger_up(lms, MIDDLE_TIP, MIDDLE_PIP)
        and finger_folded(lms, RING_TIP, RING_PIP)
        and finger_folded(lms, PINKY_TIP, PINKY_PIP)
    )


def palm_center(lms) -> tuple[float, float]:
    ids = (WRIST, INDEX_MCP, MIDDLE_MCP, 13, 17)
    xs = [lms[i].x for i in ids]
    ys = [lms[i].y for i in ids]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def palm_facing_up(lms) -> bool:
    """Rough: wrist below middle mcp, open palm."""
    if not is_open_palm(lms):
        return False
    return lms[WRIST].y > lms[MIDDLE_MCP].y + 0.03


@dataclass
class GestureEngine:
    cooldown_sec: float = 0.55
    swipe_vx: float = 0.55
    pinch_vol_sensitivity: float = 1.8
    volume_step: int = 4

    armed: bool = True
    last_action_at: float = 0.0
    last_label: str = "idle"

    _pose: str = "idle"
    _fist_since: float | None = None
    _was_fist: bool = False
    _palm_up_since: float | None = None
    _cx_hist: list[tuple[float, float]] = field(default_factory=list)
    _pinch_y0: float | None = None
    _pinch_acc: float = 0.0
    _ok_latched: bool = False

    def _ready(self) -> bool:
        return time.monotonic() - self.last_action_at >= self.cooldown_sec

    def _fire(self, name: str) -> str | None:
        if not self._ready():
            return None
        self.last_action_at = time.monotonic()
        self.last_label = name
        return name

    def update(self, lms) -> str | None:
        """Returns action id or None. Updates last_label for HUD."""
        now = time.monotonic()
        cx, cy = palm_center(lms)
        self._cx_hist.append((now, cx))
        self._cx_hist = [(t, x) for t, x in self._cx_hist if now - t < 0.35]

        fist = is_fist(lms)
        palm = is_open_palm(lms)
        pinch = is_pinch(lms)
        ok = is_ok(lms)
        two = is_two_finger(lms)
        pup = palm_facing_up(lms)

        # Safety: fist hold → toggle arm
        if fist:
            if self._fist_since is None:
                self._fist_since = now
            elif now - self._fist_since >= 0.8:
                self.armed = not self.armed
                self._fist_since = now + 999  # latch
                self.last_label = "ARMED" if self.armed else "DISARMED"
                return self._fire("toggle_arm")
            self._was_fist = True
            self.last_label = "fist"
            self._pinch_y0 = None
            return None
        else:
            # fist → palm = play/pause
            if self._was_fist and palm and self.armed:
                self._was_fist = False
                self._fist_since = None
                self.last_label = "play/pause"
                return self._fire("play_pause")
            self._was_fist = False
            self._fist_since = None

        if not self.armed:
            self.last_label = "DISARMED"
            return None

        # OK → mute
        if ok:
            if not self._ok_latched:
                self._ok_latched = True
                self.last_label = "mute"
                return self._fire("mute")
            self.last_label = "ok"
            return None
        self._ok_latched = False

        # Pinch vertical → volume (accumulate, fire steps)
        if pinch:
            tip_y = (lms[THUMB_TIP].y + lms[INDEX_TIP].y) / 2
            if self._pinch_y0 is None:
                self._pinch_y0 = tip_y
                self._pinch_acc = 0.0
            dy = self._pinch_y0 - tip_y  # up = positive (screen y down)
            self._pinch_acc += dy * self.pinch_vol_sensitivity * 40
            self._pinch_y0 = tip_y
            self.last_label = "volume"
            if abs(self._pinch_acc) >= 1.0 and self._ready():
                steps = int(self._pinch_acc)
                self._pinch_acc -= steps
                self.last_action_at = now
                return "volume_up" if steps > 0 else "volume_down"
            return None
        self._pinch_y0 = None
        self._pinch_acc = 0.0

        # Palm face-up hold → Mission Control
        if pup:
            if self._palm_up_since is None:
                self._palm_up_since = now
            elif now - self._palm_up_since >= 0.6:
                self._palm_up_since = now + 999
                self.last_label = "Mission Control"
                return self._fire("mission_control")
            self.last_label = "palm↑"
            return None
        self._palm_up_since = None

        # Swipes
        vx = self._velocity_x()
        if two and abs(vx) >= self.swipe_vx * 0.85:
            if vx > 0:
                self.last_label = "space →"
                return self._fire("space_right")
            self.last_label = "space ←"
            return self._fire("space_left")

        if palm and abs(vx) >= self.swipe_vx:
            if vx > 0:
                self.last_label = "next"
                return self._fire("next")
            self.last_label = "prev"
            return self._fire("prev")

        if palm:
            self.last_label = "palm"
        elif two:
            self.last_label = "2 fingers"
        else:
            self.last_label = "idle"
        return None

    def _velocity_x(self) -> float:
        if len(self._cx_hist) < 3:
            return 0.0
        t0, x0 = self._cx_hist[0]
        t1, x1 = self._cx_hist[-1]
        dt = max(t1 - t0, 1e-3)
        return (x1 - x0) / dt  # norm-units / sec

"""Hand landmarks helpers + gesture state machine for CV Desk."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

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
THUMB_IP = 3
THUMB_MCP = 2


def _d(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_size(lms) -> float:
    return max(_d(lms[WRIST], lms[MIDDLE_MCP]), 1e-3)


def finger_up(lms, tip: int, pip: int) -> bool:
    # Soft margin — webcam angle often flattens tips vs PIP.
    return lms[tip].y < lms[pip].y - 0.012


def finger_folded(lms, tip: int, pip: int) -> bool:
    return lms[tip].y > lms[pip].y - 0.012


def is_closed_hand(lms) -> bool:
    """Loose closed hand for play/pause intent (not arm-toggle)."""
    folded = sum(
        1
        for tip, pip in (
            (INDEX_TIP, INDEX_PIP),
            (MIDDLE_TIP, MIDDLE_PIP),
            (RING_TIP, RING_PIP),
            (PINKY_TIP, PINKY_PIP),
        )
        if finger_folded(lms, tip, pip)
    )
    if folded < 3:
        return False
    hs = hand_size(lms)
    # Tight pinch is volume, not a closed fist for play/pause.
    if _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs < 0.30:
        return False
    if is_thumbs_up(lms):
        return False
    return True


def is_fist(lms) -> bool:
    """Strict closed fist for arm/disarm hold."""
    if not is_closed_hand(lms):
        return False
    pairs = (
        (INDEX_TIP, INDEX_PIP),
        (MIDDLE_TIP, MIDDLE_PIP),
        (RING_TIP, RING_PIP),
        (PINKY_TIP, PINKY_PIP),
    )
    if not all(finger_folded(lms, t, p) for t, p in pairs):
        return False
    hs = hand_size(lms)
    if _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs < 0.42:
        return False
    if lms[THUMB_TIP].y < lms[THUMB_MCP].y - 0.03:
        return False
    for tip in (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP):
        if _d(lms[tip], lms[MIDDLE_MCP]) / hs > 0.58:
            return False
    return True


def is_open_palm(lms) -> bool:
    ups = [
        finger_up(lms, INDEX_TIP, INDEX_PIP),
        finger_up(lms, MIDDLE_TIP, MIDDLE_PIP),
        finger_up(lms, RING_TIP, RING_PIP),
        finger_up(lms, PINKY_TIP, PINKY_PIP),
    ]
    if sum(ups) < 3:
        return False
    tips = [lms[INDEX_TIP], lms[MIDDLE_TIP], lms[RING_TIP], lms[PINKY_TIP]]
    spread = sum(_d(tips[i], tips[i + 1]) for i in range(3)) / hand_size(lms)
    return spread > 0.32


def is_ok(lms) -> bool:
    """👌 — thumb↔index ring with middle/ring/pinky clearly UP (not a casual pinch)."""
    hs = hand_size(lms)
    near = _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs < 0.25
    if not near:
        return False
    return (
        finger_up(lms, MIDDLE_TIP, MIDDLE_PIP)
        and finger_up(lms, RING_TIP, RING_PIP)
        and finger_up(lms, PINKY_TIP, PINKY_PIP)
    )


def is_pinch(lms) -> bool:
    """Natural volume pinch: thumb+index close, and not a clear OK sign."""
    hs = hand_size(lms)
    pin = _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs
    # Tight enough that opening the hand clearly ends the session (snap/volume).
    if pin > 0.34:
        return False
    # OK (three fingers up) is mute — don't treat as volume.
    if is_ok(lms):
        return False
    return True


def fingers_opening(lms) -> bool:
    """Partial open hand — used for fist→play/pause during the release grace."""
    ups = sum(
        1
        for tip, pip in (
            (INDEX_TIP, INDEX_PIP),
            (MIDDLE_TIP, MIDDLE_PIP),
            (RING_TIP, RING_PIP),
            (PINKY_TIP, PINKY_PIP),
        )
        if finger_up(lms, tip, pip)
    )
    return ups >= 2


def is_thumbs_up(lms) -> bool:
    """👍 — thumb extended upward, other four fingers folded."""
    folded = all(
        finger_folded(lms, t, p)
        for t, p in (
            (INDEX_TIP, INDEX_PIP),
            (MIDDLE_TIP, MIDDLE_PIP),
            (RING_TIP, RING_PIP),
            (PINKY_TIP, PINKY_PIP),
        )
    )
    if not folded:
        return False
    hs = hand_size(lms)
    # Tip clearly above thumb MCP / palm (image y shrinks upward).
    if lms[THUMB_TIP].y > lms[THUMB_MCP].y - 0.035:
        return False
    if lms[THUMB_TIP].y > lms[MIDDLE_MCP].y - 0.02:
        return False
    if _d(lms[THUMB_TIP], lms[THUMB_MCP]) / hs < 0.22:
        return False
    # Not a pinch / OK (thumb glued to index).
    if _d(lms[THUMB_TIP], lms[INDEX_TIP]) / hs < 0.28:
        return False
    return True


def is_two_finger(lms) -> bool:
    return (
        finger_up(lms, INDEX_TIP, INDEX_PIP)
        and finger_up(lms, MIDDLE_TIP, MIDDLE_PIP)
        and finger_folded(lms, RING_TIP, RING_PIP)
        and finger_folded(lms, PINKY_TIP, PINKY_PIP)
    )


def is_three_finger(lms) -> bool:
    """Index+middle+ring up, pinky not extended — App Exposé hold.

    Soft pinky check: webcam angles often leave the pinky slightly raised,
    so require only that it is clearly less extended than the ring tip.
    """
    if not (
        finger_up(lms, INDEX_TIP, INDEX_PIP)
        and finger_up(lms, MIDDLE_TIP, MIDDLE_PIP)
        and finger_up(lms, RING_TIP, RING_PIP)
    ):
        return False
    # Pinky clearly up like an open palm → not three-finger.
    if finger_up(lms, PINKY_TIP, PINKY_PIP) and lms[PINKY_TIP].y < lms[RING_TIP].y + 0.02:
        return False
    return True


def palm_center(lms) -> tuple[float, float]:
    ids = (WRIST, INDEX_MCP, MIDDLE_MCP, 13, 17)
    xs = [lms[i].x for i in ids]
    ys = [lms[i].y for i in ids]
    return sum(xs) / len(xs), sum(ys) / len(ys)


@dataclass
class GestureEngine:
    cooldown_sec: float = 0.40
    swipe_vx: float = 0.38
    pinch_vol_sensitivity: float = 2.0
    volume_step: int = 2
    fist_open_grace_sec: float = 0.85
    ok_hold_sec: float = 0.40
    arm_hold_sec: float = 1.15
    pinch_arm_sec: float = 0.28
    pinch_deadzone: float = 0.008
    thumbs_hold_sec: float = 0.70
    three_hold_sec: float = 0.55
    snap_hold_sec: float = 0.45  # still pinch until HUD shows SNAP ✓, then open
    snap_max_sec: float = 2.5

    armed: bool = True
    last_action_at: float = 0.0
    last_label: str = "idle"

    _pose: str = "idle"
    _fist_since: float | None = None
    _was_fist: bool = False
    _fist_released_at: float | None = None
    _thumbs_since: float | None = None
    _three_since: float | None = None
    _three_miss: int = 0
    _three_latched: bool = False
    _mc_block_until: float = 0.0
    _cx_hist: list[tuple[float, float]] = field(default_factory=list)
    _pinch_y0: float | None = None
    _pinch_y_smooth: float | None = None
    _pinch_acc: float = 0.0
    _pinch_hold_until: float = 0.0
    _pinch_since: float | None = None
    _pinch_armed: bool = False
    _pinch_dir: int = 0
    _pinch_last_motion_at: float = 0.0
    _pinch_did_volume: bool = False
    _pinch_snap_ready: bool = False
    _ok_latched: bool = False
    _ok_since: float | None = None
    _mute_block_until: float = 0.0
    _swipe_cool_until: float = 0.0
    _swipe_lock_dir: int = 0
    _swipe_lock_until: float = 0.0

    def _ready(self) -> bool:
        return time.monotonic() - self.last_action_at >= self.cooldown_sec

    def _fire(self, name: str, *, ignore_cooldown: bool = False) -> str | None:
        if not ignore_cooldown and not self._ready():
            return None
        self.last_action_at = time.monotonic()
        self.last_label = name
        return name

    def _reset_pinch(self) -> None:
        self._pinch_y0 = None
        self._pinch_y_smooth = None
        self._pinch_acc = 0.0
        self._pinch_since = None
        self._pinch_armed = False
        self._pinch_dir = 0
        self._pinch_hold_until = 0.0
        self._pinch_last_motion_at = 0.0
        self._pinch_did_volume = False
        self._pinch_snap_ready = False

    def _finish_pinch_session(self, now: float) -> str | None:
        """On pinch release: screenshot only if snap was armed (still hold)."""
        did_vol = self._pinch_did_volume
        ready = self._pinch_snap_ready
        self._reset_pinch()
        if did_vol or not ready:
            return None
        return self._fire("screenshot")

    def on_hand_lost(self) -> None:
        """Call when MediaPipe reports no hand — pinch dir must not stick."""
        self._reset_pinch()
        self._cx_hist.clear()
        self._ok_since = None
        self._ok_latched = False
        self._three_since = None
        self._three_miss = 0
        self._thumbs_since = None
        if self.last_label.startswith(("volume", "pinch", "ok", "3", "👍", "SNAP")):
            self.last_label = "idle"

    def _commit_swipe(self, direction: int, now: float, *, palm_track: bool = False) -> None:
        """After a swipe, drop history and lock return motion (hand coming back)."""
        self._cx_hist.clear()
        # Palm track swipes need a longer return window — users bring the hand back to center.
        cool = 1.25 if palm_track else 0.85
        lock = 1.7 if palm_track else 1.1
        self._swipe_cool_until = now + cool
        self._swipe_lock_dir = direction
        self._swipe_lock_until = now + lock
        self._thumbs_since = None
        self._mc_block_until = max(self._mc_block_until, now + 0.8)

    def _swipe_signal(self) -> tuple[float, int] | None:
        """
        Peak speed in the direction of net palm travel.
        Ignores pure jitter (tiny dx) and mixed out-and-back windows.
        """
        if len(self._cx_hist) < 4:
            return None
        _, x0 = self._cx_hist[0]
        _, x1 = self._cx_hist[-1]
        dx = x1 - x0
        if abs(dx) < 0.035:
            return None
        sign = 1 if dx > 0 else -1
        peak_dir = 0.0
        for i in range(1, len(self._cx_hist)):
            t0, xa = self._cx_hist[i - 1]
            t1, xb = self._cx_hist[i]
            v = (xb - xa) / max(t1 - t0, 1e-3)
            if v * sign > 0:
                peak_dir = max(peak_dir, abs(v))
        if peak_dir <= 0:
            return None
        return peak_dir, sign

    def update(self, lms) -> str | None:
        """Returns action id or None. Updates last_label for HUD."""
        now = time.monotonic()
        cx, cy = palm_center(lms)
        self._cx_hist.append((now, cx))
        self._cx_hist = [(t, x) for t, x in self._cx_hist if now - t < 0.28]

        fist = is_fist(lms)
        closed = is_closed_hand(lms)
        palm = is_open_palm(lms)
        opening = palm or fingers_opening(lms)
        pinch = is_pinch(lms)
        ok = is_ok(lms)
        two = is_two_finger(lms)
        three = is_three_finger(lms)
        thumbs = is_thumbs_up(lms)

        # --- Closed hand: arm-toggle (strict) + play/pause intent (loose) ---
        if closed and not opening:
            if self._fist_since is None:
                self._fist_since = now
            held = now - self._fist_since
            self._was_fist = True
            self._fist_released_at = None
            self._thumbs_since = None
            self._reset_pinch()
            # Strict fist held long → arm/disarm
            if fist and held >= self.arm_hold_sec:
                self.armed = not self.armed
                self._fist_since = now + 999
                self.last_label = "ARMED" if self.armed else "DISARMED"
                self._was_fist = False
                return self._fire("toggle_arm", ignore_cooldown=True)
            self.last_label = f"fist {held:.1f}s"
            return None

        # --- Fist/closed just ended: exclusive open → play/pause ---
        if self._was_fist:
            if self._fist_released_at is None:
                self._fist_released_at = now
            age = now - self._fist_released_at

            if age > self.fist_open_grace_sec:
                self._was_fist = False
                self._fist_released_at = None
                self._fist_since = None
            elif self.armed and opening:
                # Fire first; only clear intent if it actually fired.
                fired = self._fire("play_pause", ignore_cooldown=True)
                if fired:
                    self._was_fist = False
                    self._fist_released_at = None
                    self._fist_since = None
                    self._thumbs_since = None
                    self._mc_block_until = now + 0.6
                    self._cx_hist.clear()
                    self._swipe_cool_until = now + 0.7
                    self._swipe_lock_dir = 0
                    self._swipe_lock_until = 0.0
                    self._reset_pinch()
                    return fired
                self.last_label = "open…"
                return None
            else:
                self.last_label = "open…"
                return None

        self._fist_since = None

        if not self.armed:
            self.last_label = "DISARMED"
            return None

        # 👍 hold → Mission Control (after fist/play-pause — never during open grace)
        if thumbs and now >= self._mc_block_until:
            self._reset_pinch()
            if self._thumbs_since is None:
                self._thumbs_since = now
            held = now - self._thumbs_since
            if held >= self.thumbs_hold_sec:
                self._thumbs_since = now + 999
                self.last_label = "Mission Control"
                return self._fire("mission_control")
            self.last_label = f"👍 {held:.1f}s"
            return None
        self._thumbs_since = None

        # Volume pinch / screenshot: hold still → SNAP ✓ → open hand.
        # Moving after volume arms → volume only (no screenshot).
        if pinch:
            self._pinch_hold_until = now + 0.18
            raw_y = (lms[THUMB_TIP].y + lms[INDEX_TIP].y) / 2
            self._ok_since = None

            if self._pinch_y_smooth is None:
                self._pinch_y_smooth = raw_y
                self._pinch_y0 = raw_y
                self._pinch_since = now
                self._pinch_armed = False
                self._pinch_acc = 0.0
                self._pinch_dir = 0
                self._pinch_last_motion_at = now
                self._pinch_did_volume = False
                self._pinch_snap_ready = False
                self.last_label = "pinch…"
                return None

            self._pinch_y_smooth = 0.82 * self._pinch_y_smooth + 0.18 * raw_y
            held = (now - self._pinch_since) if self._pinch_since is not None else 0.0

            if not self._pinch_armed:
                self._pinch_y0 = self._pinch_y_smooth
                if held >= self.pinch_arm_sec:
                    self._pinch_armed = True
                    self._pinch_acc = 0.0
                    self._pinch_dir = 0
                else:
                    self.last_label = "pinch…"
                    return None

            # Still long enough without volume → arm screenshot on release.
            if (
                not self._pinch_did_volume
                and self._pinch_acc < 0.55
                and held >= self.snap_hold_sec
            ):
                self._pinch_snap_ready = True

            if self._pinch_y0 is None:
                self._pinch_y0 = self._pinch_y_smooth

            dy = self._pinch_y0 - self._pinch_y_smooth
            self._pinch_y0 = self._pinch_y_smooth
            dead = self.pinch_deadzone
            if abs(dy) < dead:
                if self._pinch_dir and now - self._pinch_last_motion_at > 0.35:
                    self._pinch_dir = 0
                    self._pinch_acc = 0.0
                if self._pinch_snap_ready and not self._pinch_did_volume:
                    self.last_label = "SNAP ✓ open"
                elif not self._pinch_did_volume:
                    self.last_label = f"snap {held:.1f}s"
                else:
                    self.last_label = "volume"
                return None

            self._pinch_last_motion_at = now
            if self._pinch_dir == 0:
                self._pinch_dir = 1 if dy > 0 else -1
            elif dy * self._pinch_dir < 0:
                if abs(dy) < dead * 1.6:
                    self.last_label = "volume"
                    return None
                self._pinch_dir = 1 if dy > 0 else -1
                self._pinch_acc = 0.0

            if dy * self._pinch_dir > 0:
                self._pinch_acc += abs(dy) * self.pinch_vol_sensitivity * 38

            # Clear motion cancels pending snap.
            if self._pinch_acc >= 0.55:
                self._pinch_snap_ready = False

            self.last_label = "volume↑" if self._pinch_dir > 0 else "volume↓"
            if self._pinch_acc >= 1.0 and self._ready():
                self._pinch_acc -= 1.0
                self.last_action_at = now
                self._mute_block_until = now + 0.7
                self._pinch_did_volume = True
                self._pinch_snap_ready = False
                return "volume_up" if self._pinch_dir > 0 else "volume_down"
            return None

        # Pinch ended: keep a tiny grace only mid-volume; else evaluate snap.
        if self._pinch_since is not None:
            if (
                now < self._pinch_hold_until
                and (self._pinch_did_volume or (self._pinch_armed and self._pinch_acc >= 0.45))
            ):
                self.last_label = "volume"
                return None
            snap = self._finish_pinch_session(now)
            if snap:
                self.last_label = "screenshot"
                return snap

        # OK → mute only after a short hold (avoids flash during pinch setup).
        if ok and now >= self._mute_block_until:
            if self._ok_since is None:
                self._ok_since = now
                self.last_label = "ok…"
                return None
            if now - self._ok_since < self.ok_hold_sec:
                self.last_label = "ok…"
                return None
            if not self._ok_latched:
                self._ok_latched = True
                self.last_label = "mute"
                return self._fire("mute")
            self.last_label = "ok"
            return None
        self._ok_since = None
        self._ok_latched = False

        # 3 fingers hold (still) → App Exposé; swipe stays on 2 fingers.
        # Hysteresis: tolerate a few missed frames so it doesn't fire "every other try".
        if three:
            self._three_miss = 0
            if self._three_latched:
                self.last_label = "3 fingers"
                return None
            h_peak = self._peak_abs_vx()
            if h_peak >= 0.55:
                self._three_since = None
                self.last_label = "3 fingers"
                return None
            if self._three_since is None:
                self._three_since = now
                self._cx_hist.clear()  # don't inherit swipe jitter into the hold
            held = now - self._three_since
            if held >= self.three_hold_sec:
                fired = self._fire("app_expose")
                if fired:
                    self._three_latched = True
                    self._three_since = None
                    self.last_label = "App Exposé"
                    return fired
                self.last_label = "3✋…"
                return None
            self.last_label = f"3✋ {held:.1f}s"
            return None

        # Left three-finger pose (with short flicker grace while counting hold).
        if self._three_since is not None and not self._three_latched:
            self._three_miss += 1
            if self._three_miss <= 5:
                held = now - self._three_since
                self.last_label = f"3✋ {held:.1f}s"
                return None
            self._three_since = None
            self._three_miss = 0
        else:
            self._three_since = None
            self._three_miss = 0
            # Must fully leave the pose before the next Exposé.
            self._three_latched = False

        # Swipes (Mission Control is thumbs-up above — no palm↑ conflict).
        if now < self._swipe_cool_until:
            self._thumbs_since = None
            if palm:
                self.last_label = "palm"
            elif two:
                self.last_label = "2 fingers"
            else:
                self.last_label = "idle"
            return None

        sig = self._swipe_signal()
        if sig is not None:
            peak, sign = sig
            bounce = now < self._swipe_lock_until and sign == -self._swipe_lock_dir
            if bounce:
                # Returning hand to center — extend cool.
                self._swipe_cool_until = max(self._swipe_cool_until, now + 0.55)
                self._thumbs_since = None
                self.last_label = "return…"
                return None
            if two and peak >= self.swipe_vx * 0.7:
                self._commit_swipe(sign, now, palm_track=False)
                if sign > 0:
                    self.last_label = "space →"
                    return self._fire("space_right")
                self.last_label = "space ←"
                return self._fire("space_left")
            if palm and peak >= self.swipe_vx * 0.82:
                self._commit_swipe(sign, now, palm_track=True)
                if sign > 0:
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
        return (x1 - x0) / dt

    def _peak_abs_vx(self) -> float:
        if len(self._cx_hist) < 3:
            return abs(self._velocity_x())
        peak = 0.0
        for i in range(1, len(self._cx_hist)):
            t0, x0 = self._cx_hist[i - 1]
            t1, x1 = self._cx_hist[i]
            dt = max(t1 - t0, 1e-3)
            peak = max(peak, abs((x1 - x0) / dt))
        return peak

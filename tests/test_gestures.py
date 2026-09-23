"""Unit tests for gesture helpers (no camera)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from cv_desk.vision.gestures import (
    GestureEngine,
    fingers_opening,
    is_fist,
    is_ok,
    is_open_palm,
    is_pinch,
    is_thumbs_up,
)


def _lms(overrides: dict[int, tuple[float, float]]):
    pts = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    pts[0] = SimpleNamespace(x=0.5, y=0.7, z=0.0)
    pts[9] = SimpleNamespace(x=0.5, y=0.45, z=0.0)
    for i, (x, y) in overrides.items():
        pts[i] = SimpleNamespace(x=x, y=y, z=0.0)
    return pts


class GestureHelpers(unittest.TestCase):
    def test_fist(self):
        # Closed fist: all tips folded, thumb away from index, tips near palm
        l = _lms({
            4: (0.32, 0.58),  # thumb aside
            8: (0.48, 0.60),
            6: (0.48, 0.52),
            12: (0.50, 0.60),
            10: (0.50, 0.52),
            16: (0.52, 0.60),
            14: (0.52, 0.52),
            20: (0.54, 0.60),
            18: (0.54, 0.52),
            0: (0.50, 0.78),
            9: (0.50, 0.55),
        })
        self.assertTrue(is_fist(l))

    def test_pinch_is_not_fist(self):
        pinch = _lms({
            4: (0.48, 0.40),
            8: (0.50, 0.40),
            6: (0.50, 0.48),
            12: (0.52, 0.55),
            10: (0.52, 0.48),
            16: (0.55, 0.55),
            14: (0.55, 0.48),
            20: (0.58, 0.55),
            18: (0.58, 0.48),
            0: (0.5, 0.70),
            9: (0.5, 0.50),
        })
        self.assertTrue(is_pinch(pinch))
        self.assertFalse(is_fist(pinch))

    def test_open_palm(self):
        l = _lms({
            8: (0.35, 0.25),
            6: (0.38, 0.4),
            12: (0.45, 0.22),
            10: (0.47, 0.4),
            16: (0.55, 0.24),
            14: (0.55, 0.4),
            20: (0.68, 0.28),
            18: (0.62, 0.4),
            5: (0.4, 0.45),
            9: (0.5, 0.45),
            0: (0.5, 0.75),
        })
        self.assertTrue(is_open_palm(l))

    def test_pinch_not_ok(self):
        """Natural pinch (other fingers relaxed) is volume, not mute OK."""
        pinch = _lms({
            4: (0.48, 0.40),
            8: (0.50, 0.40),
            6: (0.50, 0.48),
            12: (0.52, 0.50),  # middle relaxed
            10: (0.52, 0.45),
            16: (0.55, 0.52),
            14: (0.55, 0.45),
            20: (0.58, 0.52),
            18: (0.58, 0.45),
            0: (0.5, 0.70),
            9: (0.5, 0.50),
        })
        self.assertTrue(is_pinch(pinch))
        self.assertFalse(is_ok(pinch))

    def test_ok_not_pinch(self):
        ok = _lms({
            4: (0.46, 0.35),
            8: (0.48, 0.35),
            6: (0.50, 0.42),
            12: (0.50, 0.22),  # middle up
            10: (0.50, 0.40),
            16: (0.55, 0.24),
            14: (0.55, 0.40),
            20: (0.60, 0.26),
            18: (0.60, 0.40),
            0: (0.5, 0.70),
            9: (0.5, 0.45),
        })
        self.assertTrue(is_ok(ok))
        self.assertFalse(is_pinch(ok))

    def test_thumbs_up_not_fist(self):
        th = _lms({
            4: (0.45, 0.28),  # thumb tip up
            3: (0.46, 0.38),
            2: (0.47, 0.48),
            8: (0.50, 0.58),
            6: (0.50, 0.50),
            12: (0.52, 0.58),
            10: (0.52, 0.50),
            16: (0.54, 0.58),
            14: (0.54, 0.50),
            20: (0.56, 0.58),
            18: (0.56, 0.50),
            0: (0.50, 0.75),
            9: (0.50, 0.52),
        })
        self.assertTrue(is_thumbs_up(th))
        self.assertFalse(is_fist(th))

    def test_engine_defaults(self):
        eng = GestureEngine()
        self.assertTrue(eng.armed)
        self.assertEqual(eng.last_label, "idle")

    def test_fist_to_palm_survives_idle_frames(self):
        """During open grace, intermediate poses must not steal play/pause."""
        eng = GestureEngine(cooldown_sec=0.0)
        fist = _lms({
            4: (0.32, 0.58),
            8: (0.48, 0.60),
            6: (0.48, 0.52),
            12: (0.50, 0.60),
            10: (0.50, 0.52),
            16: (0.52, 0.60),
            14: (0.52, 0.52),
            20: (0.54, 0.60),
            18: (0.54, 0.52),
            0: (0.50, 0.78),
            9: (0.50, 0.55),
        })
        # Looks a bit like thumbs / pinch-ish mid-open — must stay in grace
        mid = _lms({
            4: (0.42, 0.35),
            2: (0.44, 0.48),
            8: (0.48, 0.40),
            6: (0.48, 0.48),
            12: (0.52, 0.55),
            10: (0.52, 0.48),
            16: (0.55, 0.55),
            14: (0.55, 0.48),
            20: (0.58, 0.55),
            18: (0.58, 0.48),
            0: (0.5, 0.75),
            9: (0.5, 0.50),
        })
        palm = _lms({
            8: (0.35, 0.25),
            6: (0.38, 0.4),
            12: (0.45, 0.22),
            10: (0.47, 0.4),
            16: (0.55, 0.24),
            14: (0.55, 0.4),
            20: (0.68, 0.28),
            18: (0.62, 0.4),
            5: (0.4, 0.45),
            9: (0.5, 0.45),
            0: (0.5, 0.75),
        })
        self.assertTrue(is_fist(fist))
        self.assertIsNone(eng.update(fist))
        self.assertTrue(eng._was_fist)
        self.assertIsNone(eng.update(mid))  # grace — suppress stealers
        self.assertTrue(eng._was_fist)
        self.assertEqual(eng.update(palm), "play_pause")

    def test_swipe_ignores_bounce_back(self):
        eng = GestureEngine(cooldown_sec=0.0, swipe_vx=0.3)
        # Synthetic rightward then immediate leftward samples
        now0 = 1000.0
        eng._cx_hist = [
            (now0, 0.30),
            (now0 + 0.05, 0.40),
            (now0 + 0.10, 0.52),
            (now0 + 0.15, 0.62),
        ]
        sig = eng._swipe_signal()
        self.assertIsNotNone(sig)
        peak, sign = sig
        self.assertEqual(sign, 1)
        eng._commit_swipe(sign, now0 + 0.15)
        # Return motion should be locked
        eng._cx_hist = [
            (now0 + 0.20, 0.62),
            (now0 + 0.25, 0.50),
            (now0 + 0.30, 0.38),
            (now0 + 0.35, 0.28),
        ]
        # cool still active at 0.35 after commit at 0.15 → until 0.90
        self.assertLess(now0 + 0.40, eng._swipe_cool_until)
        sig2 = eng._swipe_signal()
        self.assertIsNotNone(sig2)
        self.assertEqual(sig2[1], -1)
        self.assertEqual(eng._swipe_lock_dir, 1)
        self.assertLess(now0 + 0.40, eng._swipe_lock_until)


if __name__ == "__main__":
    unittest.main()

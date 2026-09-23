"""Unit tests for gesture helpers (no camera)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from cv_desk.vision.gestures import GestureEngine, is_fist, is_open_palm


def _lms(overrides: dict[int, tuple[float, float]]):
    pts = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    pts[0] = SimpleNamespace(x=0.5, y=0.7, z=0.0)
    pts[9] = SimpleNamespace(x=0.5, y=0.45, z=0.0)
    for i, (x, y) in overrides.items():
        pts[i] = SimpleNamespace(x=x, y=y, z=0.0)
    return pts


class GestureHelpers(unittest.TestCase):
    def test_fist(self):
        l = _lms({
            8: (0.45, 0.55),
            6: (0.45, 0.48),
            12: (0.5, 0.55),
            10: (0.5, 0.48),
            16: (0.55, 0.55),
            14: (0.55, 0.48),
            20: (0.6, 0.55),
            18: (0.6, 0.48),
        })
        self.assertTrue(is_fist(l))

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

    def test_engine_defaults(self):
        eng = GestureEngine()
        self.assertTrue(eng.armed)
        self.assertEqual(eng.last_label, "idle")


if __name__ == "__main__":
    unittest.main()

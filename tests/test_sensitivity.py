"""Unit tests for sensitivity presets / calibration math."""

from __future__ import annotations

import unittest

from cv_desk.sensitivity import (
    match_preset,
    pinch_sens_from_travels,
    preset_values,
    swipe_vx_from_peaks,
)


class SensitivityTests(unittest.TestCase):
    def test_presets(self):
        n = preset_values("normal")
        self.assertAlmostEqual(n["swipe_vx"], 0.38)
        self.assertEqual(match_preset(n), "normal")
        self.assertEqual(match_preset({**n, "swipe_vx": 0.99}), "custom")

    def test_swipe_from_peaks(self):
        vx = swipe_vx_from_peaks([0.8, 1.0, 0.9])
        self.assertGreaterEqual(vx, 0.18)
        self.assertLessEqual(vx, 0.85)
        self.assertAlmostEqual(vx, 0.45 * 0.9, places=5)

    def test_pinch_from_travels(self):
        sens = pinch_sens_from_travels([0.1, 0.12])
        self.assertGreaterEqual(sens, 0.8)
        self.assertLessEqual(sens, 4.0)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for per-app action profiles."""

from __future__ import annotations

import unittest

from cv_desk.profiles import (
    clear_app_profile,
    effective_actions,
    has_app_profile,
    is_enabled,
    merge_profile_maps,
    set_app_action,
)


class ProfileMerge(unittest.TestCase):
    def test_default_all_on(self):
        cfg = {"actions": {"volume": True, "spaces": True}, "profiles": {}}
        self.assertTrue(is_enabled(cfg, "com.apple.Safari", "volume"))

    def test_override_disables(self):
        cfg = {
            "actions": {"volume": True, "spaces": True, "screenshot": True},
            "profiles": {"com.spotify.client": {"spaces": False}},
        }
        self.assertFalse(is_enabled(cfg, "com.spotify.client", "spaces"))
        self.assertTrue(is_enabled(cfg, "com.spotify.client", "volume"))
        self.assertTrue(is_enabled(cfg, "com.apple.Safari", "spaces"))

    def test_set_and_clear(self):
        cfg = {"actions": {"volume": True}, "profiles": {}}
        cfg = set_app_action(cfg, "com.spotify.client", "volume", False)
        self.assertTrue(has_app_profile(cfg, "com.spotify.client"))
        self.assertFalse(is_enabled(cfg, "com.spotify.client", "volume"))
        cfg = clear_app_profile(cfg, "com.spotify.client")
        self.assertFalse(has_app_profile(cfg, "com.spotify.client"))
        self.assertTrue(is_enabled(cfg, "com.spotify.client", "volume"))

    def test_effective_merge(self):
        cfg = {
            "actions": {
                "play_pause": True,
                "next_prev": True,
                "volume": True,
                "mute": True,
                "mission_control": True,
                "spaces": True,
                "app_expose": True,
                "screenshot": True,
            },
            "profiles": {"x.app": {"mute": False, "screenshot": False}},
        }
        eff = effective_actions(cfg, "x.app")
        self.assertFalse(eff["mute"])
        self.assertFalse(eff["screenshot"])
        self.assertTrue(eff["volume"])

    def test_merge_profile_maps(self):
        merged = merge_profile_maps(
            {"a": {"volume": False}},
            {"a": {"spaces": False}, "b": {"mute": False}},
        )
        self.assertEqual(merged["a"]["volume"], False)
        self.assertEqual(merged["a"]["spaces"], False)
        self.assertEqual(merged["b"]["mute"], False)


if __name__ == "__main__":
    unittest.main()

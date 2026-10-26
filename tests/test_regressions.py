"""Regression tests for cv-desk bugfixes (no camera, no macOS frameworks)."""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from cv_desk.frontmost import is_self_app
from cv_desk.vision import camera as camera_mod
from cv_desk.vision.gestures import (
    PINCH_GAP_END,
    GestureEngine,
    is_closed_hand,
    is_fist,
    is_ok,
    is_open_palm,
    is_pinch,
    is_three_finger,
)


def _lms(overrides: dict[int, tuple[float, float]]):
    pts = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    pts[0] = SimpleNamespace(x=0.5, y=0.7, z=0.0)
    pts[9] = SimpleNamespace(x=0.5, y=0.45, z=0.0)
    for i, (x, y) in overrides.items():
        pts[i] = SimpleNamespace(x=x, y=y, z=0.0)
    return pts


def _fist():
    return _lms({
        4: (0.32, 0.58),
        8: (0.48, 0.60),
        6: (0.48, 0.52),
        12: (0.50, 0.60),
        10: (0.50, 0.52),
        16: (0.52, 0.60),
        14: (0.52, 0.52),
        20: (0.54, 0.60),
        18: (0.54, 0.52),
        5: (0.48, 0.55),
        13: (0.52, 0.55),
        17: (0.54, 0.55),
        0: (0.50, 0.78),
        9: (0.50, 0.55),
        2: (0.40, 0.58),
    })


def _open_palm():
    return _lms({
        8: (0.35, 0.25),
        6: (0.38, 0.4),
        12: (0.45, 0.22),
        10: (0.47, 0.4),
        16: (0.55, 0.24),
        14: (0.55, 0.4),
        20: (0.68, 0.28),
        18: (0.62, 0.4),
        4: (0.30, 0.40),
        5: (0.4, 0.45),
        9: (0.5, 0.45),
        13: (0.55, 0.45),
        17: (0.62, 0.45),
        0: (0.5, 0.75),
    })


def _sideways_open_palm():
    """Open palm rotated ~90°: tips far from MCP horizontally, tip.y ≈ pip.y."""
    # Wrist left, fingers extend to the right (not upward).
    return _lms({
        0: (0.25, 0.50),   # wrist
        9: (0.40, 0.50),   # middle MCP
        5: (0.40, 0.42),   # index MCP
        6: (0.55, 0.40),   # index PIP
        8: (0.78, 0.40),   # index tip — far from MCP
        10: (0.55, 0.50),
        12: (0.80, 0.50),
        13: (0.40, 0.58),
        14: (0.55, 0.58),
        16: (0.79, 0.58),
        17: (0.40, 0.66),
        18: (0.55, 0.66),
        20: (0.76, 0.66),
        4: (0.35, 0.30),
        2: (0.32, 0.38),
    })


class FrameIdNoBusyLoop(unittest.TestCase):
    """Bug 1: process each camera frame once; volume steps independent of repeats."""

    def test_duplicate_frame_id_processed_once(self):
        eng = GestureEngine(cooldown_sec=0.0, pinch_arm_sec=0.0, pinch_deadzone=0.001)
        calls = []

        class FakeCam:
            def __init__(self):
                self.error = None
                self._id = 1
                self._frame = np.zeros((10, 10, 3), dtype=np.uint8)
                # Moving pinch: dy accumulates volume
                self._lms = _lms({
                    4: (0.48, 0.50),
                    8: (0.50, 0.50),
                    6: (0.50, 0.55),
                    12: (0.52, 0.58),
                    10: (0.52, 0.52),
                    16: (0.55, 0.58),
                    14: (0.55, 0.52),
                    20: (0.58, 0.58),
                    18: (0.58, 0.52),
                    0: (0.5, 0.70),
                    9: (0.5, 0.50),
                })

            def wait_new_frame(self, last_id, timeout=0.5):
                # Always return the same id after the first handoff
                return self._id, self._frame, self._lms

            def get(self):
                return self._id, self._frame, self._lms

        # Simulate loop: only call engine when fid changes
        last_id = 0
        cam = FakeCam()
        for _ in range(50):
            fid, frame, lms = cam.wait_new_frame(last_id, timeout=0.01)
            if frame is None or fid == last_id:
                continue
            last_id = fid
            action = eng.update(lms)
            calls.append(action)

        self.assertEqual(len(calls), 1)

    def test_volume_steps_independent_of_frame_repeats(self):
        def run_motion(repeats_per_frame: int) -> int:
            """Same 8 motion samples; camera may re-deliver each sample N times."""
            eng = GestureEngine(
                cooldown_sec=0.0,
                pinch_arm_sec=0.0,
                pinch_deadzone=0.001,
                pinch_vol_sensitivity=2.4,
            )
            y0 = 0.50
            base = {
                6: (0.50, 0.55),
                12: (0.52, 0.58),
                10: (0.52, 0.52),
                16: (0.55, 0.58),
                14: (0.55, 0.52),
                20: (0.58, 0.58),
                18: (0.58, 0.52),
                0: (0.5, 0.70),
                9: (0.5, 0.50),
            }
            steps = 0
            last_id = 0
            frame_id = 0
            l = _lms({**base, 4: (0.48, y0), 8: (0.50, y0)})
            frame_id += 1
            last_id = frame_id
            eng.update(l)
            eng._pinch_armed = True
            eng._pinch_y0 = y0
            eng._pinch_y_smooth = y0
            for i in range(8):
                y = y0 - 0.02 * (i + 1)
                l = _lms({**base, 4: (0.48, y), 8: (0.50, y)})
                frame_id += 1
                for _ in range(repeats_per_frame):
                    # Busy-loop guard: only new frame_id reaches the engine.
                    if frame_id == last_id:
                        continue
                    last_id = frame_id
                    a = eng.update(l)
                    if a == "volume_up":
                        steps += 1
                        eng.commit_fire()
            return steps

        self.assertEqual(run_motion(1), run_motion(20))


class ArmAbsorbsPlayPause(unittest.TestCase):
    """Bug 2: fist hold for arm must not also fire play_pause on release."""

    def test_arm_then_release_only_toggle_arm(self):
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=0.05)
        fist = _fist()
        palm = _open_palm()
        self.assertTrue(is_fist(fist))
        actions = []
        self.assertIsNone(eng.update(fist))
        eng._fist_since = time.monotonic() - 0.2
        a = eng.update(fist)
        self.assertEqual(a, "toggle_arm")
        actions.append(a)
        eng.commit_fire()
        # Still holding fist after arm
        self.assertIsNone(eng.update(fist))
        # Release → open palm must NOT play_pause
        a2 = eng.update(palm)
        if a2:
            actions.append(a2)
        # A couple more open frames
        for _ in range(3):
            a3 = eng.update(palm)
            if a3:
                actions.append(a3)
        self.assertEqual(actions, ["toggle_arm"])


class CameraNameResolve(unittest.TestCase):
    """Bug 3: non-numeric --camera names resolve without int() crash."""

    def test_resolve_by_name_substring(self):
        cams = [(0, "Continuity Camera"), (1, "FaceTime HD Camera")]
        with mock.patch.object(camera_mod, "list_camera_names", return_value=cams):
            idx, name = camera_mod.resolve_camera_index("face")
            self.assertEqual(idx, 1)
            self.assertIn("FaceTime", name)

    def test_unknown_name_falls_back_to_auto(self):
        cams = [(0, "Continuity Camera"), (1, "FaceTime HD Camera")]
        with mock.patch.object(camera_mod, "list_camera_names", return_value=cams):
            idx, name = camera_mod.resolve_camera_index("front")
            # "front" not in names → auto prefers FaceTime
            self.assertEqual(idx, 1)

    def test_main_stores_name_without_int(self):
        from cv_desk import app as app_mod

        saved = {}

        def fake_save(cfg):
            saved.update(cfg)

        with mock.patch.object(app_mod, "load_config", return_value={"camera_index": "auto"}):
            with mock.patch.object(app_mod, "save_config", side_effect=fake_save):
                with mock.patch.object(app_mod, "run_tray"):
                    app_mod.main(["--camera", "front"])
        self.assertEqual(saved.get("camera_index"), "front")


class ModelDownloadAtomic(unittest.TestCase):
    """Bug 4: download to temp, verify SHA-256, atomic replace; bad cache re-fetched."""

    def test_bad_cache_deleted_and_redownloaded(self):
        payload = b"x" * 2000
        good_hash = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            model = Path(td) / "hand_landmarker.task"
            model.write_bytes(b"corrupt-but-long-" + b"z" * 2000)
            part_writes = []

            def fake_retrieve(url, filename):
                Path(filename).write_bytes(payload)
                part_writes.append(filename)

            with mock.patch.object(camera_mod, "MODEL_PATH", model):
                with mock.patch.object(camera_mod, "MODEL_SHA256", good_hash):
                    with mock.patch.object(
                        camera_mod.urllib.request, "urlretrieve", side_effect=fake_retrieve
                    ):
                        out = camera_mod.ensure_model()
            self.assertEqual(out, model)
            self.assertEqual(model.read_bytes(), payload)
            self.assertTrue(part_writes)
            self.assertTrue(str(part_writes[0]).endswith(".task.part"))


class ConfigUtf8(unittest.TestCase):
    """Bug 5: bad UTF-8 config must not crash; backup + defaults."""

    def test_unicode_decode_error_falls_back(self):
        import cv_desk.config as cfg_mod

        with tempfile.TemporaryDirectory() as td:
            user = Path(td) / "config.json"
            default = Path(td) / "config.default.json"
            default.write_text('{"armed": true, "actions": {}, "profiles": {}}\n', encoding="utf-8")
            user.write_bytes(b'{"armed": true,\xff\xfe}')
            with mock.patch.object(cfg_mod, "USER_PATH", user):
                with mock.patch.object(cfg_mod, "DEFAULT_PATH", default):
                    with mock.patch.object(cfg_mod, "ensure_user_config", return_value=user):
                        loaded = cfg_mod.load_config()
            self.assertTrue(user.with_suffix(".json.bak").exists())
            self.assertIn("armed", loaded)


class ListCamerasEmpty(unittest.TestCase):
    """Bug 15: no cameras → message + non-zero exit."""

    def test_list_cameras_none(self):
        from cv_desk import app as app_mod

        with mock.patch.object(app_mod, "list_camera_names", return_value=[]):
            with self.assertRaises(SystemExit) as ctx:
                app_mod._parse_camera_arg(["--list-cameras"])
            self.assertNotEqual(ctx.exception.code, 0)


class FrontmostSelfFilter(unittest.TestCase):
    """Bug 12: only CV Desk itself is filtered, not Terminal / python hosts."""

    def test_terminal_not_self(self):
        self.assertFalse(is_self_app("com.apple.Terminal", "Terminal", pid=1))

    def test_python_host_not_self_unless_our_pid(self):
        self.assertFalse(is_self_app("org.python.python", "Python", pid=1))
        self.assertTrue(is_self_app("org.python.python", "Python", pid=os.getpid()))

    def test_cvdesk_bundle_is_self(self):
        self.assertTrue(is_self_app("com.bocchisad.cvdesk", "CV Desk", pid=1))


class SidewaysPalm(unittest.TestCase):
    """Bug 13: rotated open palm must not read as fist."""

    def test_sideways_open_palm(self):
        l = _sideways_open_palm()
        self.assertTrue(is_open_palm(l))
        self.assertFalse(is_fist(l))


class GestureDisambiguation(unittest.TestCase):
    """Live-camera regressions: palm≠exposé, pinch≠mute, snap stays ready."""

    def test_fist_with_thumb_tucked_is_not_pinch(self):
        """Common fist (thumb across fingers) must arm, not steal snap/pinch."""
        fist = _lms({
            4: (0.48, 0.58),  # thumb tucked near index
            8: (0.48, 0.60),
            6: (0.48, 0.52),
            12: (0.50, 0.60),
            10: (0.50, 0.52),
            16: (0.52, 0.60),
            14: (0.52, 0.52),
            20: (0.54, 0.60),
            18: (0.54, 0.52),
            5: (0.48, 0.55),
            13: (0.52, 0.55),
            17: (0.54, 0.55),
            2: (0.44, 0.58),
            0: (0.50, 0.78),
            9: (0.50, 0.55),
        })
        self.assertTrue(is_fist(fist))
        self.assertFalse(is_pinch(fist))

    def test_open_c_is_not_fist(self):
        """Released pinch (thumb+index out, others curled) must not stick as fist."""
        open_c = _lms({
            4: (0.32, 0.38),  # thumb out
            2: (0.40, 0.48),
            8: (0.68, 0.36),  # index stretched
            6: (0.55, 0.42),
            5: (0.45, 0.50),
            12: (0.50, 0.60),
            10: (0.50, 0.52),
            16: (0.52, 0.60),
            14: (0.52, 0.52),
            20: (0.54, 0.60),
            18: (0.54, 0.52),
            13: (0.52, 0.55),
            17: (0.54, 0.55),
            0: (0.50, 0.78),
            9: (0.50, 0.55),
        })
        self.assertFalse(is_closed_hand(open_c))
        self.assertFalse(is_fist(open_c))

    def test_closed_hold_arms(self):
        """Sustained closed fist must fire toggle_arm (not hang on fist Ns)."""
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=0.05)
        fist = _fist()
        self.assertTrue(is_closed_hand(fist))
        eng.update(fist)
        eng._fist_since = time.monotonic() - 0.2
        self.assertEqual(eng.update(fist), "toggle_arm")

    def test_snap_does_not_fire_on_ok_fingers(self):
        """Raising middle/ring/pinky while tips stay pinched must not screenshot."""
        eng = GestureEngine(
            cooldown_sec=0.0,
            pinch_arm_sec=0.05,
            snap_hold_sec=0.05,
            pinch_deadzone=0.05,
        )
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
        # OK-ish: tips still close, other three up
        okish = _lms({
            4: (0.48, 0.40),
            8: (0.50, 0.40),
            6: (0.50, 0.48),
            12: (0.50, 0.22),
            10: (0.50, 0.40),
            16: (0.55, 0.24),
            14: (0.55, 0.40),
            20: (0.60, 0.26),
            18: (0.60, 0.40),
            0: (0.5, 0.70),
            9: (0.5, 0.45),
        })
        eng.update(pinch)
        eng._pinch_since = time.monotonic() - 0.2
        eng._pinch_armed = True
        eng._pinch_snap_ready = True
        self.assertNotEqual(eng.update(okish), "screenshot")

    def test_open_palm_is_not_three_finger(self):
        palm = _open_palm()
        self.assertTrue(is_open_palm(palm))
        self.assertFalse(is_three_finger(palm))

    def test_relaxed_pinch_is_not_ok(self):
        pinch = _lms({
            4: (0.48, 0.40),
            8: (0.50, 0.40),
            6: (0.50, 0.48),
            12: (0.52, 0.50),
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

    def test_engine_open_palm_does_not_fire_app_expose(self):
        eng = GestureEngine(cooldown_sec=0.0, three_hold_sec=0.05)
        palm = _open_palm()
        eng.update(palm)
        eng._three_since = time.monotonic() - 0.2
        self.assertIsNone(eng.update(palm))


class EngineLock(unittest.TestCase):
    """Bug 14: engine updates from another thread don't explode mid-update."""

    def test_concurrent_sensitivity_and_update(self):
        eng = GestureEngine(cooldown_sec=0.0)
        lock = threading.RLock()
        errors: list[BaseException] = []
        palm = _open_palm()

        def worker():
            try:
                for _ in range(200):
                    with lock:
                        eng.update(palm)
            except BaseException as e:  # noqa: BLE001 — collect any race failure
                errors.append(e)

        def mutator():
            try:
                for i in range(200):
                    with lock:
                        eng.swipe_vx = 0.2 + (i % 5) * 0.05
                        eng.cooldown_sec = 0.1 * (i % 3)
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker), threading.Thread(target=mutator)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class MediaKeyAccessibility(unittest.TestCase):
    """Bug 8: without AX trust, media keys skip Quartz and use AppleScript path."""

    def test_no_ax_skips_quartz(self):
        from cv_desk.actions import macos as mac

        with mock.patch.object(mac, "_ax_trusted", return_value=False):
            with mock.patch.object(mac, "_media_key_quartz") as quartz:
                with mock.patch.object(mac, "_osascript", return_value=(True, "ok")):
                    with mock.patch.object(mac, "_ax_hint_shown", False):
                        ok, _msg = mac.play_pause()
        quartz.assert_not_called()
        self.assertTrue(ok)


class ScreenshotPrefersScreencapture(unittest.TestCase):
    """Bug 9: screencapture is tried before Quartz."""

    def test_screencapture_primary(self):
        from cv_desk.actions import macos as mac

        with tempfile.TemporaryDirectory() as td:
            desktop = Path(td)

            def fake_run(cmd, **kwargs):
                path = Path(cmd[-1])
                path.write_bytes(b"png")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with mock.patch.object(Path, "home", return_value=desktop):
                (desktop / "Desktop").mkdir()
                with mock.patch.object(mac.subprocess, "run", side_effect=fake_run) as run:
                    with mock.patch.object(mac, "_screenshot_quartz") as quartz:
                        ok, msg = mac.screenshot()
            self.assertTrue(ok)
            quartz.assert_not_called()
            self.assertTrue(run.called)
            self.assertEqual(run.call_args[0][0][0], "/usr/sbin/screencapture")
            self.assertIn("screenshot", msg)


def _pinch_gap_lms(gap: float):
    """Pinch-like pose with thumb↔index separation ≈ gap * hand_size."""
    # hs ≈ 0.20 (wrist 0.70 → middle MCP 0.50)
    half = (gap * 0.20) / 2
    return _lms({
        4: (0.50 - half, 0.40),
        8: (0.50 + half, 0.40),
        6: (0.50, 0.48),
        5: (0.48, 0.50),
        12: (0.52, 0.55),
        10: (0.52, 0.48),
        16: (0.55, 0.55),
        14: (0.55, 0.48),
        20: (0.58, 0.55),
        18: (0.58, 0.48),
        0: (0.5, 0.70),
        9: (0.5, 0.50),
    })


def _rotate_lms(lms, degrees: float, cx: float = 0.5, cy: float = 0.5):
    rad = math.radians(degrees)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    out = []
    for p in lms:
        x, y = p.x - cx, p.y - cy
        out.append(
            SimpleNamespace(
                x=cx + x * cos_a - y * sin_a,
                y=cy + x * sin_a + y * cos_a,
                z=getattr(p, "z", 0.0),
            )
        )
    return out


def _three_finger():
    return _lms({
        8: (0.40, 0.25),
        6: (0.40, 0.40),
        5: (0.40, 0.48),
        12: (0.48, 0.22),
        10: (0.48, 0.40),
        16: (0.55, 0.24),
        14: (0.55, 0.40),
        13: (0.55, 0.48),
        20: (0.62, 0.55),
        18: (0.62, 0.48),
        17: (0.62, 0.52),
        0: (0.5, 0.75),
        9: (0.5, 0.45),
        4: (0.35, 0.50),
        2: (0.38, 0.55),
    })


class PinchReleaseHysteresis(unittest.TestCase):
    """Gradual pinch open must still screenshot (no 0.34–0.38 dead zone)."""

    def test_gradual_open_screenshots_once(self):
        eng = GestureEngine(
            cooldown_sec=0.0,
            pinch_arm_sec=0.0,
            snap_hold_sec=0.05,
            snap_max_sec=2.0,
            pinch_deadzone=0.05,
        )
        closed = _pinch_gap_lms(0.30)
        self.assertTrue(is_pinch(closed))
        eng.update(closed)
        eng._pinch_since = time.monotonic() - 0.2
        eng._pinch_armed = True
        eng._pinch_snap_ready = True
        actions = []
        for gap in (0.35, 0.37, 0.39, 0.50):
            self.assertGreater(gap, PINCH_GAP_END)
            a = eng.update(_pinch_gap_lms(gap))
            if a:
                actions.append(a)
                eng.commit_fire()
        self.assertEqual(actions, ["screenshot"])


class SnapMaxTimeout(unittest.TestCase):
    """Long pinch hold expires snap — release must not screenshot."""

    def test_long_hold_no_screenshot_short_does(self):
        open_h = _open_palm()
        pinch = _pinch_gap_lms(0.20)

        eng_long = GestureEngine(
            cooldown_sec=0.0,
            pinch_arm_sec=0.0,
            snap_hold_sec=0.05,
            snap_max_sec=1.5,
            pinch_deadzone=0.05,
        )
        eng_long.update(pinch)
        eng_long._pinch_since = time.monotonic() - 4.0
        eng_long._pinch_armed = True
        eng_long.update(pinch)
        self.assertFalse(eng_long._pinch_snap_ready)
        self.assertNotEqual(eng_long.update(open_h), "screenshot")

        eng_short = GestureEngine(
            cooldown_sec=0.0,
            pinch_arm_sec=0.0,
            snap_hold_sec=0.05,
            snap_max_sec=1.5,
            pinch_deadzone=0.05,
        )
        eng_short.update(pinch)
        eng_short._pinch_since = time.monotonic() - 0.3
        eng_short._pinch_armed = True
        eng_short._pinch_snap_ready = True
        self.assertEqual(eng_short.update(open_h), "screenshot")


class ArmRequiresStrictFist(unittest.TestCase):
    """Half-closed hand must not toggle_arm; real fist must."""

    def test_half_closed_no_arm(self):
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=0.05)
        # Only index curled; others extended — not a fist.
        half = _lms({
            8: (0.48, 0.58),
            6: (0.48, 0.52),
            5: (0.48, 0.55),
            12: (0.45, 0.22),
            10: (0.47, 0.40),
            16: (0.55, 0.24),
            14: (0.55, 0.40),
            20: (0.68, 0.28),
            18: (0.62, 0.40),
            4: (0.32, 0.50),
            2: (0.38, 0.55),
            0: (0.50, 0.78),
            9: (0.50, 0.45),
            13: (0.55, 0.45),
            17: (0.62, 0.45),
        })
        self.assertFalse(is_fist(half))
        eng.update(half)
        eng._fist_since = time.monotonic() - 0.2
        self.assertIsNone(eng.update(half))
        self.assertFalse(eng._fist_strict_seen)

    def test_real_fist_arms(self):
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=0.05)
        fist = _fist()
        self.assertTrue(is_fist(fist))
        eng.update(fist)
        eng._fist_since = time.monotonic() - 0.2
        self.assertEqual(eng.update(fist), "toggle_arm")


class RotationInvariantGestures(unittest.TestCase):
    """Fist / palm / three / pinch classify the same at many rotations."""

    def test_labels_stable_under_rotation(self):
        templates = {
            "fist": (_fist(), is_fist, True),
            "palm": (_open_palm(), is_open_palm, True),
            "three": (_three_finger(), is_three_finger, True),
            "pinch": (_pinch_gap_lms(0.20), is_pinch, True),
        }
        for name, (base, pred, expect) in templates.items():
            for deg in (0, 45, 90, 135, 180, 270):
                rotated = _rotate_lms(base, deg)
                self.assertEqual(
                    pred(rotated),
                    expect,
                    msg=f"{name} at {deg}°",
                )
            # Cross-checks: palm must never be three; fist never pinch
            if name == "palm":
                for deg in (0, 90, 180, 270):
                    self.assertFalse(is_three_finger(_rotate_lms(base, deg)))
            if name == "fist":
                for deg in (0, 90, 180, 270):
                    self.assertFalse(is_pinch(_rotate_lms(base, deg)))


class ModelHashPreservesManual(unittest.TestCase):
    """Failed download must not delete an existing (even hash-mismatched) model."""

    def test_offline_keeps_bad_cache(self):
        with tempfile.TemporaryDirectory() as td:
            model = Path(td) / "hand_landmarker.task"
            payload = b"manual-model-bytes-" + b"z" * 2000
            model.write_bytes(payload)

            def boom(*_a, **_k):
                raise OSError("network down")

            with mock.patch.object(camera_mod, "MODEL_PATH", model):
                with mock.patch.object(camera_mod, "MODEL_SHA256", "deadbeef" * 8):
                    with mock.patch.dict(os.environ, {}, clear=False):
                        os.environ.pop("CVDESK_HAND_MODEL", None)
                        with mock.patch.object(
                            camera_mod.urllib.request, "urlretrieve", side_effect=boom
                        ):
                            with self.assertRaises(RuntimeError) as ctx:
                                camera_mod.ensure_model()
            self.assertTrue(model.is_file())
            self.assertEqual(model.read_bytes(), payload)
            self.assertIn("untouched", str(ctx.exception).lower())

    def test_offline_missing_file_no_untouched_msg(self):
        with tempfile.TemporaryDirectory() as td:
            model = Path(td) / "hand_landmarker.task"

            def boom(*_a, **_k):
                raise OSError("network down")

            with mock.patch.object(camera_mod, "MODEL_PATH", model):
                with mock.patch.object(camera_mod, "MODEL_SHA256", "deadbeef" * 8):
                    with mock.patch.object(camera_mod, "_download_announced", False):
                        with mock.patch.dict(os.environ, {}, clear=False):
                            os.environ.pop("CVDESK_HAND_MODEL", None)
                            with mock.patch.object(
                                camera_mod.urllib.request, "urlretrieve", side_effect=boom
                            ):
                                with self.assertRaises(RuntimeError) as ctx:
                                    camera_mod.ensure_model()
            self.assertNotIn("untouched", str(ctx.exception).lower())

    def test_env_override_skips_hash(self):
        with tempfile.TemporaryDirectory() as td:
            custom = Path(td) / "custom.task"
            custom.write_bytes(b"y" * 2000)
            with mock.patch.dict(os.environ, {"CVDESK_HAND_MODEL": str(custom)}):
                out = camera_mod.ensure_model()
            self.assertEqual(out, custom)


class CameraDetectRecovery(unittest.TestCase):
    """Detect errors must not kill the thread; error set then cleared."""

    def test_detect_errors_recover(self):
        cam = camera_mod.HandCameraThread(0, "fake")
        calls = {"n": 0}
        frames = {"cap": 0}

        class FakeCap:
            def isOpened(self):
                return True

            def read(self):
                frames["cap"] += 1
                return True, np.zeros((48, 64, 3), dtype=np.uint8)

            def set(self, *_a):
                return True

            def release(self):
                pass

        class FakeLM:
            def detect_for_video(self, *_a, **_k):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("boom1")
                if calls["n"] == 2:
                    raise ValueError("boom2")
                return SimpleNamespace(hand_landmarks=[])

            def close(self):
                pass

        created = {"n": 0}

        def fake_create():
            created["n"] += 1
            return FakeLM()

        cam._create_landmarker = fake_create  # type: ignore[method-assign]
        cam._open_capture = lambda: FakeCap()  # type: ignore[method-assign]
        cam._detect_for_video = lambda lm, img, ts: lm.detect_for_video(img, ts)  # type: ignore

        cam.start()
        deadline = time.monotonic() + 3.0
        saw_error = False
        cleared = False
        while time.monotonic() < deadline:
            if cam.error:
                saw_error = True
            if saw_error and cam.error is None and cam._frame_id > 0:
                cleared = True
                break
            time.sleep(0.02)
        cam.stop()
        cam.join(timeout=2.0)
        self.assertFalse(cam.is_alive())
        self.assertTrue(saw_error)
        self.assertTrue(cleared)
        self.assertGreaterEqual(created["n"], 2)


class HandCameraThreadJoin(unittest.TestCase):
    """Thread._stop must not be shadowed — join() must work on 3.11+."""

    def test_start_stop_join(self):
        cam = camera_mod.HandCameraThread(0, "join-test")

        class FakeCap:
            def isOpened(self):
                return True

            def read(self):
                time.sleep(0.02)
                return True, np.zeros((24, 32, 3), dtype=np.uint8)

            def set(self, *_a):
                return True

            def release(self):
                pass

        class FakeLM:
            def detect_for_video(self, *_a, **_k):
                return SimpleNamespace(hand_landmarks=[])

            def close(self):
                pass

        cam._create_landmarker = lambda: FakeLM()  # type: ignore[method-assign]
        cam._open_capture = lambda: FakeCap()  # type: ignore[method-assign]
        # Ensure we did not shadow Thread._stop with an Event.
        self.assertIsInstance(cam._stop_evt, threading.Event)
        self.assertFalse(isinstance(getattr(cam, "_stop", None), threading.Event))

        cam.start()
        time.sleep(0.05)
        cam.stop()
        cam.join(timeout=2.0)
        self.assertFalse(cam.is_alive())


class FistHoldDoesNotCountLooseTime(unittest.TestCase):
    """Loose closed time must not count toward arm; only strict fist hold does."""

    def test_loose_then_one_fist_frame_no_arm(self):
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=1.15)
        half = _lms({
            8: (0.48, 0.58),
            6: (0.48, 0.52),
            5: (0.48, 0.55),
            12: (0.45, 0.22),
            10: (0.47, 0.40),
            16: (0.55, 0.24),
            14: (0.55, 0.40),
            20: (0.68, 0.28),
            18: (0.62, 0.40),
            4: (0.32, 0.50),
            2: (0.38, 0.55),
            0: (0.50, 0.78),
            9: (0.50, 0.45),
            13: (0.55, 0.45),
            17: (0.62, 0.45),
        })
        fist = _fist()
        self.assertFalse(is_fist(half))
        self.assertTrue(is_fist(fist))
        eng.update(half)
        eng._fist_since = time.monotonic() - 1.2
        self.assertIsNone(eng.update(half))
        # First strict fist frame resets the clock — no instant arm.
        self.assertIsNone(eng.update(fist))
        self.assertTrue(eng._fist_strict_seen)

    def test_strict_fist_hold_arms(self):
        eng = GestureEngine(cooldown_sec=0.0, arm_hold_sec=1.15)
        fist = _fist()
        eng.update(fist)
        eng._fist_since = time.monotonic() - 1.2
        self.assertEqual(eng.update(fist), "toggle_arm")


class ModelBackupOnReplace(unittest.TestCase):
    """Mismatched on-disk model is backed up before network replace."""

    def test_backup_before_replace(self):
        payload = b"x" * 2000
        good_hash = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            model = Path(td) / "hand_landmarker.task"
            old = b"manual-old-" + b"z" * 2000
            model.write_bytes(old)

            def fake_retrieve(_url, filename):
                Path(filename).write_bytes(payload)

            with mock.patch.object(camera_mod, "MODEL_PATH", model):
                with mock.patch.object(camera_mod, "MODEL_SHA256", good_hash):
                    with mock.patch.object(camera_mod, "_download_announced", False):
                        with mock.patch.dict(os.environ, {}, clear=False):
                            os.environ.pop("CVDESK_HAND_MODEL", None)
                            with mock.patch.object(
                                camera_mod.urllib.request, "urlretrieve", side_effect=fake_retrieve
                            ):
                                camera_mod.ensure_model()
            baks = list(Path(td).glob("hand_landmarker.task.*.bak"))
            self.assertEqual(len(baks), 1)
            self.assertRegex(baks[0].name, r"hand_landmarker\.task\.\d{8}-\d{6}\.bak")
            self.assertEqual(baks[0].read_bytes(), old)
            self.assertEqual(model.read_bytes(), payload)


def _never_open_cam(name: str = "never") -> camera_mod.HandCameraThread:
    cam = camera_mod.HandCameraThread(0, name)

    class FakeLM:
        def close(self):
            pass

    class NeverOpen:
        def isOpened(self):
            return False

        def release(self):
            pass

        def set(self, *_a):
            return True

    cam._create_landmarker = lambda: FakeLM()  # type: ignore[method-assign]
    cam._open_capture = lambda: NeverOpen()  # type: ignore[method-assign]
    return cam


def _working_fakes(cam: camera_mod.HandCameraThread) -> None:
    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((24, 32, 3), dtype=np.uint8)

        def set(self, *_a):
            return True

        def release(self):
            pass

    class FakeLM:
        def detect_for_video(self, *_a, **_k):
            return SimpleNamespace(hand_landmarks=[])

        def close(self):
            pass

    cam._create_landmarker = lambda: FakeLM()  # type: ignore[method-assign]
    cam._open_capture = lambda: FakeCap()  # type: ignore[method-assign]


class CameraBackoffInterrupt(unittest.TestCase):
    """stop() must interrupt cam open backoff so join/restart/quit are responsive."""

    def test_stop_after_retries_joins_fast(self):
        cam = _never_open_cam("retry")
        cam.start()
        time.sleep(20.0)
        t0 = time.monotonic()
        cam.stop()
        cam.join(timeout=1.0)
        self.assertFalse(cam.is_alive())
        self.assertLess(time.monotonic() - t0, 1.0)

    def test_restart_camera_replaces_stuck_open(self):
        from cv_desk import app as app_mod

        with mock.patch.object(
            app_mod,
            "load_config",
            return_value={
                "camera_index": 0,
                "cooldown_sec": 0.4,
                "swipe_vx": 0.38,
                "pinch_vol_sensitivity": 2.4,
                "volume_step": 2,
                "armed": True,
                "preview": False,
                "actions": {},
                "profiles": {},
            },
        ):
            with mock.patch.object(app_mod, "save_config"):
                with mock.patch.object(
                    app_mod, "resolve_camera_index", return_value=(0, "Cam0")
                ):
                    core = app_mod.CVDeskApp(camera_pref=0)
                    old = _never_open_cam("old")
                    core.cam = old
                    old.start()
                    time.sleep(0.3)

                    created: list[camera_mod.HandCameraThread] = []

                    def fake_thread(idx, name=""):
                        t = camera_mod.HandCameraThread(idx, name or "new")
                        _working_fakes(t)
                        created.append(t)
                        return t

                    with mock.patch.object(app_mod, "HandCameraThread", side_effect=fake_thread):
                        core.restart_camera(0)
                    self.assertFalse(old.is_alive())
                    self.assertTrue(created)
                    self.assertIs(core.cam, created[-1])
                    self.assertTrue(core.cam.is_alive())
                    core.quit()
                    self.assertFalse(core.cam.is_alive())

    def test_quit_joins_faster_than_one_sec(self):
        from cv_desk import app as app_mod

        with mock.patch.object(
            app_mod,
            "load_config",
            return_value={
                "camera_index": 0,
                "cooldown_sec": 0.4,
                "swipe_vx": 0.38,
                "pinch_vol_sensitivity": 2.4,
                "volume_step": 2,
                "armed": True,
                "preview": False,
                "actions": {},
                "profiles": {},
            },
        ):
            with mock.patch.object(app_mod, "save_config"):
                with mock.patch.object(
                    app_mod, "resolve_camera_index", return_value=(0, "Cam0")
                ):
                    core = app_mod.CVDeskApp(camera_pref=0)
                    cam = _never_open_cam("quit")
                    core.cam = cam
                    cam.start()
                    time.sleep(0.2)
                    t0 = time.monotonic()
                    core.quit()
                    self.assertFalse(cam.is_alive())
                    self.assertLess(time.monotonic() - t0, 1.0)


if __name__ == "__main__":
    unittest.main()

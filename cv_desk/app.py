"""CV Desk — macOS menu-bar gesture control."""

from __future__ import annotations

import sys
import threading
import time

import cv2

from cv_desk import __version__
from cv_desk.actions import macos as actions
from cv_desk.config import load_config, save_config
from cv_desk.login_item import disable as login_disable
from cv_desk.login_item import enable as login_enable
from cv_desk.login_item import is_enabled as login_is_enabled
from cv_desk.sensitivity import (
    apply_to_config,
    apply_to_engine,
    match_preset,
    preset_values,
)
from cv_desk.ui.preview import draw_preview
from cv_desk.vision.camera import HandCameraThread, list_camera_names, resolve_camera_index
from cv_desk.vision.gestures import GestureEngine


class CVDeskApp:
    def __init__(self, camera_pref: int | str | None = None):
        self.cfg = load_config()
        self.engine = GestureEngine(
            cooldown_sec=float(self.cfg.get("cooldown_sec", 0.55)),
            swipe_vx=float(self.cfg.get("swipe_vx", 0.55)),
            pinch_vol_sensitivity=float(self.cfg.get("pinch_vol_sensitivity", 1.8)),
            volume_step=int(self.cfg.get("volume_step", 4)),
            armed=bool(self.cfg.get("armed", True)),
        )
        pref = camera_pref if camera_pref is not None else self.cfg.get("camera_index", "auto")
        idx, name = resolve_camera_index(pref)
        self.camera_index = idx
        self.camera_name = name
        self.cam = HandCameraThread(idx, name)
        self._last_action_label = ""
        self._show_preview = bool(self.cfg.get("preview", True))
        self._stop = threading.Event()
        self._status = f"cam: {name}"
        self._preview_lock = threading.Lock()
        self._preview_bgr = None

    def _enabled(self, key: str) -> bool:
        return bool(self.cfg.get("actions", {}).get(key, True))

    def apply_sensitivity(self, values: dict, preset: str) -> None:
        self.cfg = apply_to_config(self.cfg, values, preset)
        apply_to_engine(self.engine, values)
        save_config(self.cfg)
        self._status = f"sens: {preset}"

    def set_preset(self, name: str) -> None:
        values = preset_values(name)
        self.apply_sensitivity(values, name.lower())

    def get_preview_bgr(self):
        with self._preview_lock:
            if self._preview_bgr is None:
                return None
            return self._preview_bgr.copy()

    def restart_camera(self, camera_pref: int | str) -> None:
        """Stop current capture thread and start another index (tray switch)."""
        was_running = self.cam.is_alive()
        self.cam.stop()
        if was_running:
            self.cam.join(timeout=2.0)
        idx, name = resolve_camera_index(camera_pref)
        self.camera_index = idx
        self.camera_name = name
        self.cfg["camera_index"] = idx
        save_config(self.cfg)
        self.cam = HandCameraThread(idx, name)
        self.cam.start()
        self._status = f"cam: {name}"

    def dispatch(self, action: str | None) -> None:
        if not action:
            return
        if action == "toggle_arm":
            self.cfg["armed"] = self.engine.armed
            save_config(self.cfg)
            self._status = "ARMED" if self.engine.armed else "DISARMED"
            self._last_action_label = self._status
            return

        mapping = {
            "play_pause": ("play_pause", actions.play_pause),
            "next": ("next_prev", actions.next_track),
            "prev": ("next_prev", actions.prev_track),
            "mute": ("mute", actions.mute_toggle),
            "mission_control": ("mission_control", actions.mission_control),
            "space_left": ("spaces", actions.space_left),
            "space_right": ("spaces", actions.space_right),
        }

        if action in ("volume_up", "volume_down"):
            if not self._enabled("volume"):
                return
            delta = self.engine.volume_step if action == "volume_up" else -self.engine.volume_step
            ok, msg = actions.volume_delta(delta)
            self._status = msg if ok else f"err: {msg}"
            self._last_action_label = self._status
            return

        if action not in mapping:
            return
        flag, fn = mapping[action]
        if not self._enabled(flag):
            return
        ok, msg = fn()
        self._status = msg if ok else f"err: {msg}"
        self._last_action_label = self._status

    def loop_vision(self, *, opencv_preview: bool = False):
        """
        Gesture loop.
        opencv_preview=True → OpenCV HighGUI (CLI, main thread only).
        Tray uses opencv_preview=False and Cocoa window on the rumps thread.
        """
        win = "CV Desk"
        if opencv_preview:
            cv2.namedWindow(win, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win, 480, 360)
        while not self._stop.is_set():
            if self.cam.error:
                self._status = self.cam.error
                time.sleep(0.5)
                continue
            frame, lms = self.cam.get()
            if frame is None:
                time.sleep(0.01)
                continue
            if lms is not None:
                action = self.engine.update(lms)
                self.dispatch(action)
            else:
                self.engine.on_hand_lost()
            label = self.engine.last_label
            need_draw = self._show_preview or opencv_preview
            if need_draw:
                vis = draw_preview(frame, lms, label, self.engine.armed, self._last_action_label)
                with self._preview_lock:
                    self._preview_bgr = vis
                if opencv_preview:
                    cv2.imshow(win, vis)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        self.quit()
                        break
            else:
                time.sleep(0.01)
        if opencv_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    def quit(self):
        self._stop.set()
        self.cam.stop()

    def run_cli(self):
        """Preview window + console (no menu bar). HighGUI stays on the main thread."""
        print(f"CV Desk v{__version__}")
        print(f"Camera [{self.camera_index}]: {self.camera_name}")
        print("Fist hold ~1.2s = arm/disarm | fist→palm = play/pause | pinch↕ = volume")
        print("Palm swipe = next/prev | 2-finger swipe = Spaces | OK hold = mute | 👍 hold = Mission Control")
        print("Accessibility: System Settings → Privacy → Accessibility → Terminal/Python")
        self.cam.start()
        try:
            self.loop_vision(opencv_preview=True)
        finally:
            self.quit()


def run_tray():
    """Menu bar app via rumps."""
    try:
        import rumps
    except ImportError:
        print("rumps not installed — falling back to preview window")
        print("  pip install rumps pyobjc-framework-Cocoa pyobjc-framework-Quartz")
        CVDeskApp().run_cli()
        return

    from cv_desk.ui.cocoa_preview import CocoaPreview

    app_core = CVDeskApp()
    preview_win: CocoaPreview | None = None

    class Tray(rumps.App):
        def __init__(self):
            super().__init__("CV", quit_button=None)
            self.armed_item = rumps.MenuItem("Armed", callback=self.toggle_arm)
            self.preview_item = rumps.MenuItem("Show Preview", callback=self.toggle_preview)
            self.cam_item = rumps.MenuItem(
                f"Camera: {app_core.camera_name[:28]}", callback=self.cycle_camera
            )
            self.sens_low = rumps.MenuItem("Low", callback=self.set_sens_low)
            self.sens_normal = rumps.MenuItem("Normal", callback=self.set_sens_normal)
            self.sens_high = rumps.MenuItem("High", callback=self.set_sens_high)
            self.sens_calibrate = rumps.MenuItem("Calibrate…", callback=self.open_calibrate)
            self.sensitivity_item = rumps.MenuItem("Sensitivity")
            self.sensitivity_item.update(
                [
                    self.sens_low,
                    self.sens_normal,
                    self.sens_high,
                    None,
                    self.sens_calibrate,
                ]
            )
            self.login_item = rumps.MenuItem("Launch at Login", callback=self.toggle_login)
            self.status_item = rumps.MenuItem("Status: …")
            self.quit_item = rumps.MenuItem("Quit", callback=self.quit_app)
            self.menu = [
                rumps.MenuItem(f"CV Desk v{__version__}"),
                None,
                self.armed_item,
                self.preview_item,
                self.cam_item,
                self.sensitivity_item,
                self.login_item,
                None,
                self.status_item,
                None,
                self.quit_item,
            ]
            self.armed_item.state = bool(app_core.engine.armed)
            self.preview_item.state = False
            app_core._show_preview = False
            self.login_item.state = login_is_enabled()
            self._sync_sens_checks()
            app_core.cam.start()
            self._worker = threading.Thread(
                target=lambda: app_core.loop_vision(opencv_preview=False),
                daemon=True,
            )
            self._worker.start()

        def _sync_sens_checks(self):
            name = match_preset(app_core.cfg)
            self.sens_low.state = name == "low"
            self.sens_normal.state = name == "normal"
            self.sens_high.state = name == "high"

        def _ensure_preview(self) -> CocoaPreview:
            nonlocal preview_win
            if preview_win is None:
                preview_win = CocoaPreview(on_close=self._preview_closed)
            return preview_win

        def _preview_closed(self):
            app_core._show_preview = False
            app_core.cfg["preview"] = False
            save_config(app_core.cfg)
            self.preview_item.state = False

        @rumps.timer(1.0)
        def _tick(self, _):
            try:
                self.status_item.title = f"Status: {app_core._status[:42]}"
                self.armed_item.state = bool(app_core.engine.armed)
                self.cam_item.title = f"Camera: {app_core.camera_name[:28]}"
                self.login_item.state = login_is_enabled()
                self._sync_sens_checks()
                if app_core._show_preview and preview_win is not None and not preview_win.is_visible():
                    self._preview_closed()
            except Exception:
                pass

        @rumps.timer(0.07)
        def _preview_tick(self, _):
            if not app_core._show_preview or preview_win is None:
                return
            try:
                if not preview_win.is_visible():
                    return
                frame = app_core.get_preview_bgr()
                if frame is not None:
                    preview_win.set_bgr(frame)
            except Exception:
                pass

        def toggle_arm(self, sender):
            app_core.engine.armed = not app_core.engine.armed
            sender.state = bool(app_core.engine.armed)
            app_core.cfg["armed"] = app_core.engine.armed
            save_config(app_core.cfg)

        def toggle_preview(self, sender):
            app_core._show_preview = not app_core._show_preview
            sender.state = bool(app_core._show_preview)
            app_core.cfg["preview"] = app_core._show_preview
            save_config(app_core.cfg)
            win = self._ensure_preview()
            if app_core._show_preview:
                win.show()
                app_core._status = "preview on"
            else:
                win.hide()
                app_core._status = "preview off"

        def cycle_camera(self, _):
            cams = list_camera_names() or [(0, "Camera 0")]
            ids = [i for i, _ in cams]
            try:
                pos = ids.index(app_core.camera_index)
            except ValueError:
                pos = -1
            nxt = cams[(pos + 1) % len(cams)]
            app_core.restart_camera(nxt[0])
            rumps.notification(
                title="CV Desk",
                subtitle="Camera",
                message=f"[{nxt[0]}] {nxt[1]}",
            )

        def set_sens_low(self, _):
            app_core.set_preset("low")
            self._sync_sens_checks()
            rumps.notification("CV Desk", "Sensitivity", "Low (harder to trigger)")

        def set_sens_normal(self, _):
            app_core.set_preset("normal")
            self._sync_sens_checks()
            rumps.notification("CV Desk", "Sensitivity", "Normal")

        def set_sens_high(self, _):
            app_core.set_preset("high")
            self._sync_sens_checks()
            rumps.notification("CV Desk", "Sensitivity", "High (easier to trigger)")

        def open_calibrate(self, _):
            rumps.notification(
                title="CV Desk",
                subtitle="Calibrate",
                message="PYTHONPATH=. python -m cv_desk --calibrate",
            )
            app_core._status = "calibrate: --calibrate"

        def toggle_login(self, sender):
            if login_is_enabled():
                ok, msg = login_disable()
            else:
                ok, msg = login_enable()
            sender.state = login_is_enabled()
            app_core._status = msg if ok else f"err: {msg}"
            rumps.notification("CV Desk", "Launch at Login", msg)

        def quit_app(self, _):
            app_core._show_preview = False
            if preview_win is not None:
                preview_win.hide()
            app_core.quit()
            rumps.quit_application()

    Tray().run()


def _parse_camera_arg(argv: list[str]) -> int | str | None:
    if "--list-cameras" in argv:
        for i, name in list_camera_names() or [(0, "(none found)")]:
            mark = ""
            auto_i, _ = resolve_camera_index("auto")
            if i == auto_i:
                mark = "  ← auto (MacBook preferred)"
            print(f"  [{i}] {name}{mark}")
        raise SystemExit(0)
    if "--camera" in argv:
        j = argv.index("--camera")
        if j + 1 >= len(argv):
            print("usage: --camera <index|auto>")
            raise SystemExit(2)
        raw = argv[j + 1]
        return int(raw) if raw.isdigit() else raw
    return None


def main(argv: list[str] | None = None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cam_pref = _parse_camera_arg(argv)
    if "--calibrate" in argv:
        from cv_desk.calibrate import run_calibrate

        raise SystemExit(run_calibrate(camera_pref=cam_pref))
    if "--cli" in argv or "--preview" in argv:
        CVDeskApp(camera_pref=cam_pref).run_cli()
    else:
        if cam_pref is not None:
            cfg = load_config()
            cfg["camera_index"] = cam_pref if cam_pref == "auto" else int(cam_pref)
            save_config(cfg)
        run_tray()


if __name__ == "__main__":
    main()

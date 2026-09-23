"""CV Desk — macOS menu-bar gesture control."""

from __future__ import annotations

import sys
import threading
import time

import cv2

from cv_desk import __version__
from cv_desk.actions import macos as actions
from cv_desk.config import load_config, save_config
from cv_desk.ui.preview import draw_preview
from cv_desk.vision.camera import HandCameraThread
from cv_desk.vision.gestures import GestureEngine


class CVDeskApp:
    def __init__(self):
        self.cfg = load_config()
        self.engine = GestureEngine(
            cooldown_sec=float(self.cfg.get("cooldown_sec", 0.55)),
            swipe_vx=float(self.cfg.get("swipe_vx", 0.55)),
            pinch_vol_sensitivity=float(self.cfg.get("pinch_vol_sensitivity", 1.8)),
            volume_step=int(self.cfg.get("volume_step", 4)),
            armed=bool(self.cfg.get("armed", True)),
        )
        self.cam = HandCameraThread(int(self.cfg.get("camera_index", 0)))
        self._last_action_label = ""
        self._show_preview = bool(self.cfg.get("preview", True))
        self._stop = threading.Event()
        self._status = "starting…"

    def _enabled(self, key: str) -> bool:
        return bool(self.cfg.get("actions", {}).get(key, True))

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

    def loop_vision(self):
        win = "CV Desk"
        if self._show_preview:
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
            action = None
            if lms is not None:
                action = self.engine.update(lms)
                self.dispatch(action)
            label = self.engine.last_label
            if self._show_preview:
                vis = draw_preview(frame, lms, label, self.engine.armed, self._last_action_label)
                cv2.imshow(win, vis)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    self.quit()
                    break
            else:
                time.sleep(0.01)
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def quit(self):
        self._stop.set()
        self.cam.stop()

    def run_cli(self):
        """Preview window + console (no menu bar)."""
        print(f"CV Desk v{__version__}")
        print("Fist hold 0.8s = arm/disarm | fist→palm = play/pause | pinch↕ = volume")
        print("Palm swipe = next/prev | 2-finger swipe = Spaces | OK = mute | palm↑ = Mission Control")
        print("Accessibility: System Settings → Privacy → Accessibility → Terminal/Python")
        self.cam.start()
        try:
            self.loop_vision()
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

    app_core = CVDeskApp()

    class Tray(rumps.App):
        def __init__(self):
            super().__init__("CV", quit_button=None)
            self.menu = [
                rumps.MenuItem(f"CV Desk v{__version__}"),
                None,
                rumps.MenuItem("Armed", callback=self.toggle_arm),
                rumps.MenuItem("Show Preview", callback=self.toggle_preview),
                None,
                rumps.MenuItem("Status: …"),
                None,
                rumps.MenuItem("Quit", callback=self.quit_app),
            ]
            self["_armed"] = self.menu["Armed"]
            self["_preview"] = self.menu["Show Preview"]
            self["_status"] = self.menu["Status: …"]
            self["_armed"].state = app_core.engine.armed
            self["_preview"].state = app_core._show_preview
            app_core.cam.start()
            self._worker = threading.Thread(target=app_core.loop_vision, daemon=True)
            self._worker.start()

        @rumps.timer(1.0)
        def _tick(self, _):
            try:
                self["_status"].title = f"Status: {app_core._status[:42]}"
                self["_armed"].state = app_core.engine.armed
            except Exception:
                pass

        def toggle_arm(self, sender):
            app_core.engine.armed = not app_core.engine.armed
            sender.state = app_core.engine.armed
            app_core.cfg["armed"] = app_core.engine.armed
            save_config(app_core.cfg)

        def toggle_preview(self, sender):
            app_core._show_preview = not app_core._show_preview
            sender.state = app_core._show_preview
            app_core.cfg["preview"] = app_core._show_preview
            save_config(app_core.cfg)
            if not app_core._show_preview:
                try:
                    cv2.destroyWindow("CV Desk")
                except Exception:
                    pass

        def quit_app(self, _):
            app_core.quit()
            rumps.quit_application()

    Tray().run()


def main(argv: list[str] | None = None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--cli" in argv or "--preview" in argv:
        CVDeskApp().run_cli()
    else:
        run_tray()


if __name__ == "__main__":
    main()

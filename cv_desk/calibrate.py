"""Interactive sensitivity calibration wizard (CLI / OpenCV main thread)."""

from __future__ import annotations

import time

import cv2
import numpy as np

from cv_desk.config import load_config, save_config
from cv_desk.sensitivity import (
    apply_to_config,
    pinch_sens_from_travels,
    swipe_vx_from_peaks,
)
from cv_desk.ui.preview import draw_preview
from cv_desk.vision.camera import HandCameraThread, resolve_camera_index
from cv_desk.vision.gestures import (
    INDEX_TIP,
    THUMB_TIP,
    GestureEngine,
    is_open_palm,
    is_pinch,
    palm_center,
)


def _hud(frame: np.ndarray, lines: list[str]) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    overlay = out.copy()
    box_h = 24 + 22 * len(lines)
    cv2.rectangle(overlay, (0, 0), (w, box_h), (18, 20, 24), -1)
    cv2.addWeighted(overlay, 0.78, out, 0.22, 0, out)
    for i, line in enumerate(lines):
        cv2.putText(
            out,
            line[:70],
            (10, 22 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )
    return out


def run_calibrate(camera_pref: int | str | None = None) -> int:
    cfg = load_config()
    pref = camera_pref if camera_pref is not None else cfg.get("camera_index", "auto")
    idx, name = resolve_camera_index(pref)
    cam = HandCameraThread(idx, name)
    engine = GestureEngine(
        cooldown_sec=float(cfg.get("cooldown_sec", 0.55)),
        swipe_vx=float(cfg.get("swipe_vx", 0.55)),
        pinch_vol_sensitivity=float(cfg.get("pinch_vol_sensitivity", 1.8)),
        volume_step=int(cfg.get("volume_step", 4)),
        armed=True,
    )
    cam.start()

    phase = "swipe"  # swipe → pinch → review
    swipe_peaks: list[float] = []
    pinch_travels: list[float] = []
    burst_peak = 0.0
    in_burst = False
    pinch_travel = 0.0
    pinch_y0: float | None = None
    in_pinch = False
    cx_hist: list[tuple[float, float]] = []
    new_swipe = float(engine.swipe_vx)
    new_pinch = float(engine.pinch_vol_sensitivity)
    status = "Calibrate — no system actions"

    win = "CV Desk Calibrate"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 640, 480)
    print(f"CV Desk calibrate | camera [{idx}] {name}")
    print("Swipe palm L/R ×3 → pinch↕ ×2 → [s] save / [Esc] cancel / [Space] skip phase")

    try:
        while True:
            if cam.error:
                status = cam.error
                time.sleep(0.2)
            frame, lms = cam.get()
            if frame is None:
                time.sleep(0.01)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    print("cancelled")
                    return 1
                continue

            now = time.monotonic()
            if lms is not None:
                cx, _ = palm_center(lms)
                cx_hist.append((now, cx))
                cx_hist = [(t, x) for t, x in cx_hist if now - t < 0.35]
                vx = 0.0
                if len(cx_hist) >= 3:
                    t0, x0 = cx_hist[0]
                    t1, x1 = cx_hist[-1]
                    vx = (x1 - x0) / max(t1 - t0, 1e-3)

                palm = is_open_palm(lms)
                pinch = is_pinch(lms)

                if phase == "swipe" and palm and not pinch:
                    if abs(vx) > 0.25:
                        in_burst = True
                        burst_peak = max(burst_peak, abs(vx))
                    elif in_burst and abs(vx) < 0.15:
                        if burst_peak >= 0.3:
                            swipe_peaks.append(burst_peak)
                            status = f"swipe {len(swipe_peaks)}/3  peak={burst_peak:.2f}"
                        in_burst = False
                        burst_peak = 0.0
                    if len(swipe_peaks) >= 3:
                        new_swipe = swipe_vx_from_peaks(swipe_peaks)
                        phase = "pinch"
                        status = f"swipe→{new_swipe:.2f} — now pinch↕ ×2"

                elif phase == "pinch":
                    if pinch:
                        tip_y = (lms[THUMB_TIP].y + lms[INDEX_TIP].y) / 2
                        if not in_pinch:
                            in_pinch = True
                            pinch_y0 = tip_y
                            pinch_travel = 0.0
                        elif pinch_y0 is not None:
                            pinch_travel += abs(pinch_y0 - tip_y)
                            pinch_y0 = tip_y
                        status = f"pinch hold… travel={pinch_travel:.3f}"
                    elif in_pinch:
                        if pinch_travel >= 0.04:
                            pinch_travels.append(pinch_travel)
                            status = f"pinch {len(pinch_travels)}/2  travel={pinch_travel:.3f}"
                        in_pinch = False
                        pinch_y0 = None
                        pinch_travel = 0.0
                        if len(pinch_travels) >= 2:
                            try:
                                new_pinch = pinch_sens_from_travels(pinch_travels)
                            except ValueError:
                                new_pinch = float(engine.pinch_vol_sensitivity)
                            phase = "review"
                            status = f"ready  swipe={new_swipe:.2f} pinch={new_pinch:.2f}  [s]ave"

            lines = [
                f"CV Desk Calibrate  [{phase}]",
                status,
                f"swipe_vx={new_swipe:.2f}  pinch={new_pinch:.2f}  (was {engine.swipe_vx:.2f}/{engine.pinch_vol_sensitivity:.2f})",
                "Space=skip phase  s/Enter=save  Esc=cancel",
            ]
            if lms is not None:
                vis = draw_preview(frame, lms, phase, True, status[:24])
                vis = _hud(vis, lines)
            else:
                vis = _hud(frame, lines + ["(no hand)"])

            cv2.imshow(win, vis)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                print("cancelled")
                return 1
            if key in (ord("s"), 13):
                values = {
                    "swipe_vx": float(new_swipe),
                    "pinch_vol_sensitivity": float(new_pinch),
                    "cooldown_sec": float(cfg.get("cooldown_sec", 0.55)),
                }
                cfg = apply_to_config(cfg, values, "custom")
                save_config(cfg)
                print(f"saved: swipe_vx={new_swipe:.3f} pinch={new_pinch:.3f}")
                return 0
            if key == ord(" "):
                if phase == "swipe":
                    if swipe_peaks:
                        new_swipe = swipe_vx_from_peaks(swipe_peaks)
                    phase = "pinch"
                    status = "skipped swipe → pinch↕ ×2"
                elif phase == "pinch":
                    if pinch_travels:
                        try:
                            new_pinch = pinch_sens_from_travels(pinch_travels)
                        except ValueError:
                            pass
                    phase = "review"
                    status = f"ready  swipe={new_swipe:.2f} pinch={new_pinch:.2f}  [s]ave"
                elif phase == "review":
                    status = "press s to save"
    finally:
        cam.stop()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

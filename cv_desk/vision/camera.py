"""Camera + MediaPipe Hands background thread."""

from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"


def ensure_model() -> Path:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1000:
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading hand model → {MODEL_PATH}")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception:
        import ssl

        with urllib.request.urlopen(MODEL_URL, context=ssl._create_unverified_context()) as r, open(
            MODEL_PATH, "wb"
        ) as f:
            f.write(r.read())
    return MODEL_PATH


def _plain(lms):
    return [
        SimpleNamespace(x=float(p.x), y=float(p.y), z=float(getattr(p, "z", 0.0)))
        for p in lms
    ]


class HandCameraThread(threading.Thread):
    def __init__(self, camera_index: int = 0):
        super().__init__(daemon=True, name="CVDeskCam")
        self.camera_index = camera_index
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._lms = None
        self.error: str | None = None

    def stop(self):
        self._stop.set()

    def get(self) -> tuple[np.ndarray | None, list | None]:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            lms = self._lms
        return frame, lms

    def run(self):
        try:
            model = ensure_model()
            opts = vision.HandLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(model),
                    delegate=BaseOptions.Delegate.CPU,
                ),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            landmarker = vision.HandLandmarker.create_from_options(opts)
        except Exception as e:
            self.error = f"model: {e}"
            return

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error = f"camera {self.camera_index} failed"
            landmarker.close()
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        ts = 0
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.02)
                continue
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            now = int(time.monotonic() * 1000)
            if now <= ts:
                now = ts + 1
            ts = now
            result = landmarker.detect_for_video(mp_image, ts)
            lms = None
            if result.hand_landmarks:
                lms = _plain(result.hand_landmarks[0])
            with self._lock:
                self._frame = frame
                self._lms = lms

        cap.release()
        landmarker.close()

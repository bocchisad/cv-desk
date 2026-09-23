"""Camera + MediaPipe Hands background thread."""

from __future__ import annotations

import re
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

# Continuity Camera / iPhone usually lands on index 0 when connected — prefer built-in.
_SKIP_NAME = re.compile(
    r"continuity|iphone|ipad|desk\s*view|virtual|obs|camo|epoccam",
    re.I,
)
_PREFER_NAME = re.compile(
    r"facetime|built[- ]?in|macbook|isight|hd\s*camera",
    re.I,
)


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


def _avfoundation_devices() -> list[tuple[int, str]]:
    """Load AVFoundation via pyobjc (no extra pip package) and list video devices."""
    try:
        import objc

        ns: dict = {}
        objc.loadBundle(
            "AVFoundation",
            module_globals=ns,
            bundle_path="/System/Library/Frameworks/AVFoundation.framework",
        )
        AVCaptureDevice = ns.get("AVCaptureDevice")
        if AVCaptureDevice is None:
            return []
        # AVMediaTypeVideo constant is @"vide"
        devices = AVCaptureDevice.devicesWithMediaType_("vide") or []
        if not devices:
            Discovery = ns.get("AVCaptureDeviceDiscoverySession")
            if Discovery is not None:
                dtype_keys = (
                    "AVCaptureDeviceTypeBuiltInWideAngleCamera",
                    "AVCaptureDeviceTypeContinuityCamera",
                    "AVCaptureDeviceTypeExternal",
                    "AVCaptureDeviceTypeExternalUnknown",
                )
                types = [ns[k] for k in dtype_keys if k in ns] or [
                    "AVCaptureDeviceTypeBuiltInWideAngleCamera",
                    "AVCaptureDeviceTypeContinuityCamera",
                    "AVCaptureDeviceTypeExternalUnknown",
                ]
                sess = Discovery.discoverySessionWithDeviceTypes_mediaType_position_(
                    types, "vide", 0
                )
                devices = list(sess.devices() or [])
        out: list[tuple[int, str]] = []
        for i, dev in enumerate(devices):
            name = str(dev.localizedName() or f"Camera {i}")
            out.append((i, name))
        return out
    except Exception:
        return []


def list_camera_names() -> list[tuple[int, str]]:
    """Return [(index, localized_name), ...] — OpenCV AVFoundation order."""
    named = _avfoundation_devices()
    if named:
        return named
    # Fallback: probe indices (no reliable names without camera TCC).
    found: list[tuple[int, str]] = []
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(i)
        if cap.isOpened():
            found.append((i, f"Camera {i}"))
            cap.release()
    return found


def resolve_camera_index(pref: int | str | None = "auto") -> tuple[int, str]:
    """
    Pick a camera index.
    Prefer MacBook FaceTime; skip Continuity / iPhone when names are available.
    If names are missing but several indices open, prefer the highest index
    (Continuity Camera usually grabs 0 when an iPhone is nearby).
    """
    cams = list_camera_names()
    if isinstance(pref, int) or (isinstance(pref, str) and str(pref).isdigit()):
        idx = int(pref)
        name = next((n for i, n in cams if i == idx), f"Camera {idx}")
        return idx, name

    if not cams:
        return 0, "Camera 0"

    preferred = [(i, n) for i, n in cams if _PREFER_NAME.search(n) and not _SKIP_NAME.search(n)]
    if preferred:
        return preferred[0]

    non_phone = [(i, n) for i, n in cams if not _SKIP_NAME.search(n)]
    if non_phone:
        # Prefer FaceTime-like names already handled; otherwise first non-phone.
        # If all are generic "Camera N", Continuity often sits on 0 → pick last.
        if all(n.startswith("Camera ") for _, n in non_phone) and len(non_phone) > 1:
            return non_phone[-1]
        return non_phone[0]

    return cams[0]


def _plain(lms):
    return [
        SimpleNamespace(x=float(p.x), y=float(p.y), z=float(getattr(p, "z", 0.0)))
        for p in lms
    ]


class HandCameraThread(threading.Thread):
    def __init__(self, camera_index: int = 0, camera_name: str = ""):
        super().__init__(daemon=True, name="CVDeskCam")
        self.camera_index = camera_index
        self.camera_name = camera_name or f"Camera {camera_index}"
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

        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error = f"camera {self.camera_index} ({self.camera_name}) failed"
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

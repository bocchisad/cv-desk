"""Camera + MediaPipe Hands background thread."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"
# SHA-256 of MediaPipe hand_landmarker float16/1 (hand_landmarker.task).
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

# Continuity Camera / iPhone usually lands on index 0 when connected — prefer built-in.
_SKIP_NAME = re.compile(
    r"continuity|iphone|ipad|desk\s*view|virtual|obs|camo|epoccam",
    re.I,
)
_PREFER_NAME = re.compile(
    r"facetime|built[- ]?in|macbook|isight|hd\s*camera",
    re.I,
)

_NO_FRAME_ERROR_SEC = 3.0


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _model_ok(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 1000:
            return False
        return _sha256_file(path) == MODEL_SHA256
    except OSError:
        return False


def ensure_model() -> Path:
    """Ensure hand_landmarker.task is present and valid.

    Set CVDESK_HAND_MODEL to a local path to skip the SHA-256 check (logged).
    On hash mismatch, download to a temp file first; only replace the cache
    after a successful verified download — never delete the existing file first.
    """
    override = (os.environ.get("CVDESK_HAND_MODEL") or "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_file() or path.stat().st_size < 1000:
            raise RuntimeError(f"CVDESK_HAND_MODEL missing or empty: {path}")
        log.warning("using CVDESK_HAND_MODEL=%s (SHA-256 check skipped)", path)
        return path

    if _model_ok(MODEL_PATH):
        return MODEL_PATH

    if MODEL_PATH.exists():
        log.warning(
            "hand model hash mismatch or corrupt — will re-download without deleting yet: %s",
            MODEL_PATH,
        )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MODEL_PATH.with_suffix(".task.part")
    print(f"Downloading hand model → {MODEL_PATH}")
    try:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        urllib.request.urlretrieve(MODEL_URL, tmp)
    except (urllib.error.URLError, OSError, ValueError) as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        # Keep any existing on-disk model (even if hash-mismatched / manual).
        raise RuntimeError(
            f"failed to download hand model (need network): {e}\n"
            f"  existing file left untouched at {MODEL_PATH}\n"
            f"  or set CVDESK_HAND_MODEL=/path/to/hand_landmarker.task"
        ) from e
    if not _model_ok(tmp):
        try:
            tmp.unlink()
        except OSError:
            pass
        raise RuntimeError(
            f"hand model missing, empty, or hash mismatch after download: {MODEL_PATH}"
        )
    # Preserve a manually placed / mismatched cache before overwrite.
    if MODEL_PATH.exists():
        bak = Path(str(MODEL_PATH) + ".bak")
        try:
            shutil.copy2(MODEL_PATH, bak)
            log.warning(
                "hash mismatch — backed up previous model to %s before replace",
                bak,
            )
        except OSError as e:
            log.warning("could not backup previous model (%s); replacing anyway", e)
    os.replace(tmp, MODEL_PATH)
    return MODEL_PATH


def _avfoundation_devices() -> list[tuple[int, str]]:
    """List video devices. Index order matches OpenCV CAP_AVFOUNDATION when using devicesWithMediaType."""
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
        # Prefer classic devicesWithMediaType — same ordering OpenCV typically uses.
        devices = list(AVCaptureDevice.devicesWithMediaType_("vide") or [])
        if not devices:
            # Fallback DiscoverySession; sort by uniqueID for stable indices.
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
                devices = sorted(
                    list(sess.devices() or []),
                    key=lambda d: str(d.uniqueID()),
                )
        out: list[tuple[int, str]] = []
        for i, dev in enumerate(devices):
            name = str(dev.localizedName() or f"Camera {i}")
            out.append((i, name))
        return out
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return []


def list_camera_names() -> list[tuple[int, str]]:
    """Return [(index, localized_name), ...] — OpenCV AVFoundation order."""
    named = _avfoundation_devices()
    if named:
        return named
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
    String prefs that are not digits/"auto" match a camera name substring (case-insensitive).
    """
    cams = list_camera_names()
    if isinstance(pref, int) or (isinstance(pref, str) and str(pref).isdigit()):
        idx = int(pref)
        name = next((n for i, n in cams if i == idx), f"Camera {idx}")
        return idx, name

    if isinstance(pref, str) and pref.strip() and pref.strip().lower() not in ("auto", "none"):
        needle = pref.strip().lower()
        matches = [(i, n) for i, n in cams if needle in n.lower()]
        if matches:
            return matches[0]
        log.warning("camera %r not found — falling back to auto", pref)

    if not cams:
        return 0, "Camera 0"

    preferred = [(i, n) for i, n in cams if _PREFER_NAME.search(n) and not _SKIP_NAME.search(n)]
    if preferred:
        return preferred[0]

    non_phone = [(i, n) for i, n in cams if not _SKIP_NAME.search(n)]
    if non_phone:
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
        # Must not shadow threading.Thread._stop (join() calls it on 3.11+).
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._frame: np.ndarray | None = None
        self._lms = None
        self._frame_id = 0
        self.error: str | None = None

    def stop(self):
        self._stop_evt.set()
        with self._cond:
            self._cond.notify_all()

    def get(self) -> tuple[int, np.ndarray | None, list | None]:
        """Return (frame_id, frame, landmarks). frame_id is monotonic; 0 = no frame yet."""
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            lms = None if self._lms is None else list(self._lms)
            return self._frame_id, frame, lms

    def wait_new_frame(
        self, last_id: int, timeout: float = 0.5
    ) -> tuple[int, np.ndarray | None, list | None]:
        """Block until frame_id changes from last_id (or timeout). Avoids busy-loop."""
        with self._cond:
            if self._frame_id == last_id or self._frame is None:
                self._cond.wait(timeout=timeout)
            frame = None if self._frame is None else self._frame.copy()
            lms = None if self._lms is None else list(self._lms)
            return self._frame_id, frame, lms

    def _open_capture(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(self.camera_index)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cap

    def _create_landmarker(self):
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
        return vision.HandLandmarker.create_from_options(opts)

    def _detect_for_video(self, landmarker, mp_image, ts: int):
        """Hook for tests — production calls MediaPipe detect_for_video."""
        return landmarker.detect_for_video(mp_image, ts)

    def run(self):
        """Capture loop: never exit until stop(); reopen/recreate on errors with backoff."""
        backoff = 0.5
        last_setup_err: str | None = None
        while not self._stop_evt.is_set():
            landmarker = None
            cap = None
            try:
                try:
                    landmarker = self._create_landmarker()
                except Exception as e:
                    self.error = f"model: {e}"
                    err_key = str(e)
                    if err_key != last_setup_err:
                        log.error(
                            "hand model unavailable: %s — will retry (backoff up to 5 min)",
                            e,
                        )
                        last_setup_err = err_key
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 300.0)
                    continue

                cap = self._open_capture()
                if not cap.isOpened():
                    self.error = f"camera {self.camera_index} ({self.camera_name}) failed"
                    if self.error != last_setup_err:
                        log.error(
                            "%s — retrying (backoff up to 5 min)",
                            self.error,
                        )
                        last_setup_err = self.error
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 300.0)
                    continue

                last_setup_err = None
                ts = 0
                last_ok = time.monotonic()
                session_backoff = 0.5
                while not self._stop_evt.is_set():
                    try:
                        ok, frame = cap.read()
                        if not ok:
                            now = time.monotonic()
                            if now - last_ok >= _NO_FRAME_ERROR_SEC:
                                msg = f"camera lost: {self.camera_name} (no frames)"
                                if self.error != msg:
                                    self.error = msg
                                    log.error(
                                        "%s — reopening (backoff %.1fs)", msg, session_backoff
                                    )
                                try:
                                    cap.release()
                                except cv2.error:
                                    pass
                                time.sleep(session_backoff)
                                session_backoff = min(session_backoff * 2.0, 8.0)
                                cap = self._open_capture()
                                if not cap.isOpened():
                                    continue
                            else:
                                time.sleep(0.05)
                            continue

                        last_ok = time.monotonic()
                        session_backoff = 0.5
                        backoff = 0.5
                        if self.error:
                            log.info("camera recovered: %s", self.camera_name)
                            self.error = None

                        frame = cv2.flip(frame, 1)
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                        now_ms = int(time.monotonic() * 1000)
                        if now_ms <= ts:
                            now_ms = ts + 1
                        ts = now_ms
                        result = self._detect_for_video(landmarker, mp_image, ts)
                        lms = None
                        if result.hand_landmarks:
                            lms = _plain(result.hand_landmarks[0])
                        with self._cond:
                            self._frame = frame
                            self._lms = lms
                            self._frame_id += 1
                            self._cond.notify_all()
                    except Exception as e:
                        # Any detect / OpenCV failure → error state, recreate session.
                        self.error = f"detect: {e}"
                        log.exception("camera/detect error — will reopen")
                        break
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except cv2.error:
                        pass
                if landmarker is not None:
                    try:
                        landmarker.close()
                    except (RuntimeError, AttributeError):
                        pass

            if self._stop_evt.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 300.0)

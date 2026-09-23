"""Native macOS preview window (AppKit) — safe from rumps main thread."""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np


class CocoaPreview:
    """Floating NSWindow with NSImageView. Create/update only on the main thread."""

    def __init__(self, on_close: Callable[[], None] | None = None):
        from AppKit import (  # type: ignore
            NSBackingStoreBuffered,
            NSImage,
            NSImageScaleAxesIndependently,
            NSImageView,
            NSFloatingWindowLevel,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskMiniaturizable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )
        from Foundation import NSData  # type: ignore

        self._NSImage = NSImage
        self._NSData = NSData
        self._on_close = on_close
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        self._win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((120.0, 120.0), (480.0, 360.0)),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._win.setTitle_("CV Desk Preview")
        self._win.setLevel_(NSFloatingWindowLevel)
        self._win.setReleasedWhenClosed_(False)
        self._view = NSImageView.alloc().initWithFrame_(((0.0, 0.0), (480.0, 360.0)))
        self._view.setImageScaling_(NSImageScaleAxesIndependently)
        self._win.setContentView_(self._view)
        self._visible = False

    def show(self) -> None:
        self._win.makeKeyAndOrderFront_(None)
        self._visible = True

    def hide(self) -> None:
        self._win.orderOut_(None)
        self._visible = False

    def is_visible(self) -> bool:
        try:
            vis = bool(self._win.isVisible())
            self._visible = vis
            return vis
        except Exception:
            return self._visible

    def set_bgr(self, frame: np.ndarray) -> None:
        """Push a BGR OpenCV frame into the image view."""
        if frame is None or frame.size == 0:
            return
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if not ok:
            return
        data = self._NSData.dataWithBytes_length_(buf.tobytes(), int(buf.size))
        img = self._NSImage.alloc().initWithData_(data)
        if img is None:
            return
        self._view.setImage_(img)

    def close(self) -> None:
        self.hide()
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                pass

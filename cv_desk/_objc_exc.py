"""Optional pyobjc exception types (safe to import on Linux / without pyobjc)."""

from __future__ import annotations

_OBJC_ERRORS: tuple[type[BaseException], ...] = ()
try:
    import objc as _objc  # type: ignore

    _OBJC_ERRORS = (_objc.error,)
except ImportError:
    pass

# Common Cocoa / bridge failures to catch alongside stdlib errors.
OBJC_CATCH: tuple[type[BaseException], ...] = (
    AttributeError,
    TypeError,
    RuntimeError,
    OSError,
) + _OBJC_ERRORS

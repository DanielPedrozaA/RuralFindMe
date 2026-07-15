from __future__ import annotations

import faulthandler
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType


_HANDLE = None


def diagnostics_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    return base / "RuralFindMe" / "diagnostics.log"


def log_exception(context: str, exception: BaseException) -> None:
    """Log exception structure without values, arguments, or absolute paths."""

    if _HANDLE is None:
        return
    try:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _HANDLE.write(
            f"[{timestamp}] {context}: {type(exception).__name__}\n"
        )
        if exception.__traceback__ is not None:
            for frame in traceback.extract_tb(exception.__traceback__):
                _HANDLE.write(
                    f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}\n"
                )
    except OSError:
        pass


def install_diagnostics() -> None:
    """Capture crash locations without logging exception values or user data."""

    global _HANDLE
    try:
        path = diagnostics_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _HANDLE = path.open("a", encoding="utf-8", buffering=1)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _HANDLE.write(f"\n[{timestamp}] RuralFindMe session started\n")
        faulthandler.enable(file=_HANDLE, all_threads=True)

        def handle_exception(
            exception_type: type[BaseException],
            _exception: BaseException,
            tb: TracebackType | None,
        ) -> None:
            _HANDLE.write(f"Unhandled Python exception: {exception_type.__name__}\n")
            if tb is not None:
                for frame in traceback.extract_tb(tb):
                    _HANDLE.write(
                        f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}\n"
                    )

        sys.excepthook = handle_exception
    except OSError:
        _HANDLE = None

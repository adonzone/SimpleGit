"""Cross-platform ANSI styling respecting NO_COLOR, FORCE_COLOR, and Windows VT100."""

from __future__ import annotations

import os
import sys
from typing import TextIO

_RESET = "\033[0m"
_CODES = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_cyan": "\033[96m",
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
}


class Theme:
    """Semantic ANSI color formatter with graceful fallback when color is disabled."""

    def __init__(self, force_no_color: bool = False) -> None:
        self._force_no_color = force_no_color
        self._vt_initialized = False

    def _enable_windows_vt(self) -> None:
        if self._vt_initialized or os.name != "nt":
            return
        self._vt_initialized = True
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
                handle = kernel32.GetStdHandle(handle_id)
                mode = ctypes.c_uint32()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass

    def enabled_for(self, stream: TextIO | None = None) -> bool:
        """Return True if ANSI colors should be emitted to `stream`."""
        if self._force_no_color or os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("FORCE_COLOR"):
            self._enable_windows_vt()
            return True
        target = stream or sys.stdout
        term = os.environ.get("TERM", "")
        if term.lower() == "dumb":
            return False
        is_tty = bool(getattr(target, "isatty", lambda: False)())
        if is_tty:
            self._enable_windows_vt()
        return is_tty

    def style(self, text: str, *names: str, stream: TextIO | None = None) -> str:
        """Wrap `text` with ANSI codes if color is enabled for `stream`."""
        if not names or not self.enabled_for(stream):
            return text
        prefix = "".join(_CODES[n] for n in names if n in _CODES)
        return f"{prefix}{text}{_RESET}" if prefix else text

    def error(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "bold", "bright_red", stream=stream or sys.stderr)

    def warn(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "bold", "yellow", stream=stream)

    def success(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "bold", "green", stream=stream)

    def info(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "cyan", stream=stream)

    def accent(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "bold", "bright_cyan", stream=stream)

    def muted(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "dim", stream=stream)

    def bold(self, text: str, stream: TextIO | None = None) -> str:
        return self.style(text, "bold", stream=stream)

    def badge(self, label: str, bg: str = "bg_red", stream: TextIO | None = None) -> str:
        return self.style(f" {label} ", "bold", "white", bg, stream=stream)


THEME = Theme()

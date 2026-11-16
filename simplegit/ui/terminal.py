"""Cross-platform interactive terminal key reader and selection widgets."""

from __future__ import annotations

import os
import sys
from typing import Sequence

from simplegit.ui.theme import THEME


def is_interactive_tty() -> bool:
    """Return True when both stdin and stdout are attached to an interactive TTY."""
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def clear_screen() -> None:
    """Clear terminal screen if running interactively."""
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def read_key() -> str:
    """Read a single normalized keypress ('UP', 'DOWN', 'ENTER', 'SPACE', 'ESC', or char)."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            return "EOF"
        return line.strip()[:1] or "ENTER"

    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ext = msvcrt.getwch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(ext, "")
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch == "\x1b":
            return "ESC"
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch == "\x1b":
            next1 = sys.stdin.read(1) if _posix_has_data(fd) else ""
            if next1 == "[":
                next2 = sys.stdin.read(1) if _posix_has_data(fd) else ""
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(next2, "ESC")
            return "ESC"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _posix_has_data(fd: int) -> bool:
    import select

    ready, _, _ = select.select([fd], [], [], 0.05)
    return bool(ready)


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question cleanly, respecting default on Enter or EOF."""
    suffix = "[Y/n]" if default else "[y/N]"
    sys.stdout.write(f"{THEME.warn('?')} {prompt} {THEME.muted(suffix)} ")
    sys.stdout.flush()
    try:
        answer = sys.stdin.readline()
    except EOFError:
        return default
    if not answer:
        return default
    cleaned = answer.strip().lower()
    if not cleaned:
        return default
    return cleaned in ("y", "yes")


def prompt_line(label: str, default: str = "") -> str:
    """Prompt for a single line of text input."""
    hint = f" [{default}]" if default else ""
    sys.stdout.write(f"{THEME.info('>')} {label}{THEME.muted(hint)}: ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        return default
    value = line.rstrip("\r\n")
    return value if value else default


def select_one(title: str, items: Sequence[str], allow_cancel: bool = True) -> int | None:
    """Let the user choose one item index (arrow keys on TTY, numbered menu fallback)."""
    if not items:
        return None
    if not is_interactive_tty():
        return _numbered_select_one(title, items, allow_cancel)

    idx = 0
    while True:
        clear_screen()
        print(THEME.bold(title))
        print(THEME.muted("Use ↑/↓ (or j/k) + Enter to select" + (", q to cancel" if allow_cancel else "")))
        print()
        for i, item in enumerate(items):
            cursor = THEME.accent("❯ ") if i == idx else "  "
            label = THEME.accent(item) if i == idx else item
            print(f"{cursor}{label}")

        key = read_key()
        if key in ("UP", "k"):
            idx = (idx - 1) % len(items)
        elif key in ("DOWN", "j"):
            idx = (idx + 1) % len(items)
        elif key == "ENTER":
            return idx
        elif allow_cancel and key in ("q", "ESC", "EOF"):
            return None


def _numbered_select_one(title: str, items: Sequence[str], allow_cancel: bool) -> int | None:
    print(THEME.bold(title))
    for i, item in enumerate(items, start=1):
        print(f"  {i}. {item}")
    prompt = "Enter number" + (" (or 0 to cancel)" if allow_cancel else "")
    raw = prompt_line(prompt)
    if not raw or (allow_cancel and raw == "0"):
        return None
    try:
        choice = int(raw)
    except ValueError:
        return None
    if 1 <= choice <= len(items):
        return choice - 1
    return None


def multi_select(
    title: str,
    items: Sequence[str],
    preselected: set[int] | None = None,
) -> list[int] | None:
    """Let the user toggle multiple items; returns selected indices or None on cancel."""
    if not items:
        return []
    selected = set(preselected) if preselected is not None else set(range(len(items)))
    if not is_interactive_tty():
        return sorted(selected)

    idx = 0
    while True:
        clear_screen()
        print(THEME.bold(title))
        print(THEME.muted("Space: toggle | a: all/none | Enter: confirm | q: cancel"))
        print()
        for i, item in enumerate(items):
            cursor = THEME.accent("❯") if i == idx else " "
            mark = THEME.success("[x]") if i in selected else THEME.muted("[ ]")
            label = THEME.bold(item) if i == idx else item
            print(f"{cursor} {mark} {label}")

        key = read_key()
        if key in ("UP", "k"):
            idx = (idx - 1) % len(items)
        elif key in ("DOWN", "j"):
            idx = (idx + 1) % len(items)
        elif key == "SPACE":
            if idx in selected:
                selected.remove(idx)
            else:
                selected.add(idx)
        elif key == "a":
            if len(selected) == len(items):
                selected.clear()
            else:
                selected = set(range(len(items)))
        elif key == "ENTER":
            return sorted(selected)
        elif key in ("q", "ESC", "EOF"):
            return None

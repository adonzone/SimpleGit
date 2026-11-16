"""Safe subprocess runner around the system `git` binary."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from simplegit.errors import GitNotFoundError, translate_git_error

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class GitResult:
    """Captured output of a `git` invocation."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def find_git_binary() -> str:
    """Return path to `git` executable or raise `GitNotFoundError`."""
    git_path = shutil.which("git")
    if not git_path:
        raise GitNotFoundError(
            message="`git` is not installed or was not found on your PATH.",
            hint=(
                "Install Git first:\n"
                "    • macOS:   brew install git  (or `xcode-select --install`)\n"
                "    • Windows: winget install Git.Git  (or `choco install git`)\n"
                "    • Linux:   sudo apt install git  (or `sudo dnf install git`)\n"
                "    • Docs:    https://git-scm.com/downloads  |  https://git-scm.com/doc"
            ),
        )
    return git_path


def get_git_version() -> tuple[int, int, int]:
    """Return installed Git `(major, minor, patch)` version tuple."""
    res = run_git(["--version"], check=True)
    match = _VERSION_RE.search(res.stdout)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
    interactive: bool = False,
    stream_output: bool = False,
) -> GitResult:
    """Run `git` with explicit arg array (never shell=True) and translated errors."""
    git_bin = find_git_binary()
    full_cmd = [git_bin, *args]

    env = os.environ.copy()
    if not interactive:
        env.setdefault("GIT_TERMINAL_PROMPT", "0")

    if stream_output:
        proc = subprocess.run(full_cmd, cwd=cwd, env=env, text=True)
        res = GitResult(args=args, returncode=proc.returncode, stdout="", stderr="")
    else:
        proc = subprocess.run(
            full_cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        res = GitResult(
            args=args,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    if check and res.returncode != 0:
        raise translate_git_error(args, res.returncode, res.stderr, res.stdout)
    return res


def run_git_bytes(args: list[str], cwd: Path | None = None) -> bytes:
    """Run `git` and return raw stdout bytes (used for binary object fallback)."""
    git_bin = find_git_binary()
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    proc = subprocess.run([git_bin, *args], cwd=cwd, env=env, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        stdout = proc.stdout.decode("utf-8", errors="replace")
        raise translate_git_error(args, proc.returncode, stderr, stdout)
    return proc.stdout


def split_nul_lines(output: str) -> list[str]:
    """Split NUL-delimited (`-z`) Git output into non-empty strings."""
    return [entry for entry in output.split("\0") if entry]

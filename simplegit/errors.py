"""Structured error hierarchy and Git stderr-to-hint translation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SimpleGitError(Exception):
    """Base error with user-facing message, optional recovery hint, and context."""

    message: str
    hint: str | None = None
    command: str | None = None
    details: str | None = None
    affected_files: list[str] = field(default_factory=list)
    exit_code: int = 1

    def __str__(self) -> str:
        return self.message


class GitNotFoundError(SimpleGitError):
    """Raised when the `git` binary cannot be located on PATH."""


class NotARepoError(SimpleGitError):
    """Raised when an operation is invoked outside a Git repository."""


class NothingToCommitError(SimpleGitError):
    """Raised when `sgit save` finds no staged or unstaged changes to commit."""


class MergeConflictError(SimpleGitError):
    """Raised when a merge, pull, or rebase hits unresolved conflicts."""


class DirtyWorktreeError(SimpleGitError):
    """Raised when uncommitted changes block a branch switch, merge, or sync."""


class UpstreamMissingError(SimpleGitError):
    """Raised when a branch has no configured upstream tracking branch."""


class PushRejectedError(SimpleGitError):
    """Raised when remote rejects a non-fast-forward push."""


class InvalidRefError(SimpleGitError):
    """Raised when a branch, tag, commit, or pathspec does not exist."""


class CommandFailedError(SimpleGitError):
    """Fallback error for uncategorized `git` subprocess failures."""


_CONFLICT_RE = re.compile(r"CONFLICT \([^)]+\): Merge conflict in (.+)")
_OVERWRITE_LINE_RE = re.compile(r"^\t(.+)$", re.MULTILINE)


def _extract_overwritten_files(stderr: str) -> list[str]:
    """Extract indented filenames from Git's 'would be overwritten' messages."""
    lines: list[str] = []
    capture = False
    for raw in stderr.splitlines():
        if "would be overwritten" in raw:
            capture = True
            continue
        if capture:
            if raw.startswith("\t"):
                lines.append(raw.strip())
            elif raw.strip():
                break
    return lines


def translate_git_error(
    args: list[str],
    returncode: int,
    stderr: str,
    stdout: str = "",
) -> SimpleGitError:
    """Translate a failed `git` invocation into a friendly `SimpleGitError`."""
    cmd_str = "git " + " ".join(args)
    combined = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part)
    lower = combined.lower()

    if "not a git repository" in lower:
        return NotARepoError(
            message="This folder is not inside a Git repository.",
            hint="Run `sgit init` to start a new repository here, or `cd` into an existing one.",
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    conflicts = _CONFLICT_RE.findall(combined)
    if conflicts or "fix conflicts and then commit" in lower or "unmerged files" in lower:
        return MergeConflictError(
            message="Merge conflict detected.",
            hint="Resolve the conflicted files below, then run `sgit save \"resolve conflicts\"` (or `sgit merge --abort` to cancel).",
            command=cmd_str,
            details=combined,
            affected_files=conflicts,
            exit_code=returncode or 1,
        )

    if "would be overwritten" in lower or "local changes to the following files" in lower:
        files = _extract_overwritten_files(combined)
        return DirtyWorktreeError(
            message="Local uncommitted changes would be overwritten by this action.",
            hint="Run `sgit save \"wip\"` to commit your changes first, or `sgit undo changes` to discard them.",
            command=cmd_str,
            details=combined,
            affected_files=files,
            exit_code=returncode or 1,
        )

    if "nothing to commit" in lower or "no changes added to commit" in lower:
        return NothingToCommitError(
            message="Nothing to commit — your working tree has no changes.",
            hint="Edit or create a file first, then run `sgit save \"your message\"`.",
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    if "has no upstream branch" in lower:
        return UpstreamMissingError(
            message="Current branch does not track a remote branch yet.",
            hint="Run `sgit push` or `sgit sync` to publish and link it automatically.",
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    if "non-fast-forward" in lower or "fetch first" in lower or "[rejected]" in lower:
        return PushRejectedError(
            message="Push was rejected because the remote has newer commits.",
            hint="Run `sgit sync` to pull remote changes and push safely.",
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    if (
        "did not match any file(s) known to git" in lower
        or "invalid reference" in lower
        or "not a valid object name" in lower
        or "unknown revision" in lower
    ):
        return InvalidRefError(
            message="The specified branch, commit, or file path was not found.",
            hint="Check `sgit branch` or `sgit log` for valid names and commit hashes.",
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    if "please tell me who you are" in lower or "author identity unknown" in lower:
        return CommandFailedError(
            message="Git author name/email is not configured.",
            hint='Set your identity with:\n  git config --global user.name "Your Name"\n  git config --global user.email "you@example.com"',
            command=cmd_str,
            details=combined,
            exit_code=returncode or 1,
        )

    first_line = next((ln.strip() for ln in combined.splitlines() if ln.strip()), "Git command failed.")
    return CommandFailedError(
        message=first_line,
        hint="Run `sgit status` to inspect your repository state.",
        command=cmd_str,
        details=combined,
        exit_code=returncode or 1,
    )

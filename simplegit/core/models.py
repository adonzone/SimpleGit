"""Typed domain models for SimpleGit's hybrid `.git` engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RepoLocation:
    """Resolved filesystem paths for a Git repository."""

    root: Path
    git_dir: Path
    common_dir: Path
    is_bare: bool = False


@dataclass(frozen=True)
class FileChange:
    """Normalized file status entry from `git status --porcelain=v2`."""

    path: str
    status_x: str
    status_y: str
    orig_path: str | None = None
    unmerged: bool = False
    untracked: bool = False

    @property
    def is_conflicted(self) -> bool:
        return self.unmerged

    @property
    def is_staged(self) -> bool:
        return not self.untracked and not self.unmerged and self.status_x not in (".", " ", "?")

    @property
    def is_unstaged(self) -> bool:
        return not self.untracked and not self.unmerged and self.status_y not in (".", " ", "?")

    @property
    def display_path(self) -> str:
        if self.orig_path:
            return f"{self.orig_path} -> {self.path}"
        return self.path


@dataclass(frozen=True)
class RepoState:
    """Combined snapshot of repository branch, tracking, operation state, and changes."""

    location: RepoLocation
    branch: str
    head_sha: str | None
    detached: bool
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    active_op: str | None = None
    changes: tuple[FileChange, ...] = ()

    @property
    def staged_files(self) -> list[FileChange]:
        return [c for c in self.changes if c.is_staged]

    @property
    def unstaged_files(self) -> list[FileChange]:
        return [c for c in self.changes if c.is_unstaged]

    @property
    def untracked_files(self) -> list[FileChange]:
        return [c for c in self.changes if c.untracked]

    @property
    def conflicted_files(self) -> list[FileChange]:
        return [c for c in self.changes if c.is_conflicted]

    @property
    def is_clean(self) -> bool:
        return len(self.changes) == 0


@dataclass(frozen=True)
class BranchInfo:
    """Local or remote branch metadata."""

    name: str
    sha: str
    is_current: bool = False
    is_remote: bool = False
    upstream: str | None = None


@dataclass(frozen=True)
class CommitInfo:
    """Commit summary entry for `sgit log` and interactive history."""

    sha: str
    short_sha: str
    author: str
    date: str
    subject: str
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkLane:
    """A branch swimlane on the Network graph Y-axis."""

    name: str
    scope: str  # "local" or "hosted"
    tip_sha: str
    is_current: bool = False


@dataclass(frozen=True)
class NetworkCommit:
    """Chronological commit node on the Network graph."""

    sha: str
    short_sha: str
    date_label: str
    author: str
    subject: str
    lane_index: int
    parents: tuple[str, ...] = ()
    file_changes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NetworkGraph:
    """Complete X=Time, Y=Branch/Remote Network graph."""

    lanes: tuple[NetworkLane, ...]
    commits: tuple[NetworkCommit, ...]


@dataclass(frozen=True)
class GitObject:
    """Decoded `.git` object (`blob`, `tree`, `commit`, or `tag`)."""

    kind: str
    size: int
    sha: str
    content: bytes
    source: str  # "loose" or "packed"


@dataclass(frozen=True)
class SavePlan:
    """Resolved file targets for `sgit save`."""

    repo_root: Path
    tracked_diff_files: tuple[str, ...] = field(default_factory=tuple)
    untracked_files: tuple[str, ...] = field(default_factory=tuple)
    already_staged_files: tuple[str, ...] = field(default_factory=tuple)

    @property
    def files_to_stage(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for path in (*self.tracked_diff_files, *self.untracked_files):
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        return ordered

    @property
    def all_commit_files(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for path in (*self.already_staged_files, *self.files_to_stage):
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        return ordered

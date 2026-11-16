"""Direct `.git` inspection & plumbing implemented in pure Python stdlib."""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

from simplegit.core.models import GitObject, RepoLocation
from simplegit.errors import NotARepoError, SimpleGitError

_OP_SENTINELS: tuple[tuple[str, str], ...] = (
    ("MERGE_HEAD", "MERGING"),
    ("REBASE_MERGE", "REBASING"),
    ("REBASE_APPLY", "REBASING"),
    ("CHERRY_PICK_HEAD", "CHERRY-PICKING"),
    ("REVERT_HEAD", "REVERTING"),
    ("BISECT_LOG", "BISECTING"),
)


def discover_repo(start: Path | None = None) -> RepoLocation:
    """Locate `.git` directory (or worktree pointer / bare repo) walking upward from `start`."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            common_dir = _resolve_common_dir(dot_git)
            return RepoLocation(root=candidate, git_dir=dot_git, common_dir=common_dir, is_bare=False)
        if dot_git.is_file():
            git_dir = _read_gitdir_pointer(dot_git)
            common_dir = _resolve_common_dir(git_dir)
            return RepoLocation(root=candidate, git_dir=git_dir, common_dir=common_dir, is_bare=False)
        if _looks_like_bare_repo(candidate):
            return RepoLocation(root=candidate, git_dir=candidate, common_dir=candidate, is_bare=True)

    raise NotARepoError(
        message="This folder is not inside a Git repository.",
        hint="Run `sgit init` to start a new repository here, or `cd` into an existing one.",
    )


def _looks_like_bare_repo(path: Path) -> bool:
    return (path / "HEAD").is_file() and (path / "objects").is_dir() and (path / "refs").is_dir()


def _read_gitdir_pointer(dot_git_file: Path) -> Path:
    text = dot_git_file.read_text(encoding="utf-8", errors="replace").strip()
    if not text.startswith("gitdir:"):
        raise NotARepoError(f"Invalid .git pointer file: {dot_git_file}")
    raw_target = text.split(":", 1)[1].strip()
    target = Path(raw_target)
    if not target.is_absolute():
        target = (dot_git_file.parent / target).resolve()
    return target


def _resolve_common_dir(git_dir: Path) -> Path:
    commondir_file = git_dir / "commondir"
    if not commondir_file.is_file():
        return git_dir
    rel = commondir_file.read_text(encoding="utf-8", errors="replace").strip()
    target = Path(rel)
    return target if target.is_absolute() else (git_dir / target).resolve()


def detect_active_operation(git_dir: Path) -> str | None:
    """Detect in-progress merge/rebase/cherry-pick/revert/bisect from `.git` files."""
    for name, label in _OP_SENTINELS:
        if (git_dir / name).exists():
            return label
    return None


def resolve_ref(location: RepoLocation, ref_name: str) -> str | None:
    """Resolve a ref (e.g. `refs/heads/main`) across loose refs and `packed-refs`."""
    for base in (location.git_dir, location.common_dir):
        loose = base / ref_name
        if loose.is_file():
            return loose.read_text(encoding="utf-8", errors="replace").strip()

    packed = location.common_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1] == ref_name:
                return parts[0]
    return None


def read_head(location: RepoLocation) -> tuple[str, str | None, bool]:
    """Return `(branch_or_short_sha, head_sha_or_None, is_detached)` from `.git/HEAD`."""
    head_file = location.git_dir / "HEAD"
    if not head_file.is_file():
        return ("HEAD", None, False)
    raw = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if raw.startswith("ref:"):
        ref_name = raw.split(":", 1)[1].strip()
        short_name = ref_name[len("refs/heads/") :] if ref_name.startswith("refs/heads/") else ref_name
        sha = resolve_ref(location, ref_name)
        return (short_name, sha, False)
    return (raw[:7], raw, True)


def compute_object_hash(kind: str, data: bytes) -> str:
    """Compute Git's SHA-1 object ID for `(kind, data)`."""
    header = f"{kind} {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def read_loose_object(common_dir: Path, sha_prefix: str) -> GitObject | None:
    """Read and decompress a loose object from `.git/objects/xx/yyyy...` if present."""
    cleaned = sha_prefix.strip().lower()
    if len(cleaned) < 4 or not all(c in "0123456789abcdef" for c in cleaned):
        return None

    obj_dir = common_dir / "objects" / cleaned[:2]
    if not obj_dir.is_dir():
        return None

    rest = cleaned[2:]
    matches = [p for p in obj_dir.iterdir() if p.is_file() and p.name.startswith(rest)]
    if len(matches) != 1:
        return None

    obj_path = matches[0]
    full_sha = cleaned[:2] + obj_path.name
    try:
        raw = zlib.decompress(obj_path.read_bytes())
        nul_idx = raw.find(b"\0")
        if nul_idx == -1:
            raise ValueError("Missing NUL header separator")
        header = raw[:nul_idx].decode("utf-8", errors="replace")
        body = raw[nul_idx + 1 :]
        kind, size_str = header.split(" ", 1)
        size = int(size_str)
    except (zlib.error, ValueError, OSError) as exc:
        raise SimpleGitError(
            f"Corrupt or unreadable Git object `{full_sha}`.",
            hint="Run `git fsck` to check repository integrity.",
            details=str(exc),
        ) from exc
    if len(body) != size:
        raise SimpleGitError(
            f"Corrupt Git object `{full_sha}`: expected {size} bytes, got {len(body)}.",
            hint="Run `git fsck` to check repository integrity.",
        )

    return GitObject(kind=kind, size=size, sha=full_sha, content=body, source="loose")


def parse_commit_object(data: bytes) -> dict:
    """Parse raw Git commit object bytes into headers and commit message."""
    text = data.decode("utf-8", errors="replace")
    if "\n\n" in text:
        header_block, message = text.split("\n\n", 1)
    else:
        header_block, message = text, ""

    parents: list[str] = []
    tree = ""
    author = ""
    committer = ""
    for line in header_block.splitlines():
        if line.startswith("tree "):
            tree = line[5:]
        elif line.startswith("parent "):
            parents.append(line[7:])
        elif line.startswith("author "):
            author = line[7:]
        elif line.startswith("committer "):
            committer = line[10:]

    return {
        "tree": tree,
        "parents": tuple(parents),
        "author": author,
        "committer": committer,
        "message": message,
    }


def parse_tree_object(data: bytes) -> list[tuple[str, str, str]]:
    """Parse binary Git tree entries into `(mode, name, sha_hex)` tuples."""
    entries: list[tuple[str, str, str]] = []
    pos = 0
    total = len(data)
    while pos < total:
        space_idx = data.find(b" ", pos)
        nul_idx = data.find(b"\0", space_idx + 1)
        if space_idx == -1 or nul_idx == -1 or nul_idx + 21 > total:
            break
        mode = data[pos:space_idx].decode("ascii", errors="replace")
        name = data[space_idx + 1 : nul_idx].decode("utf-8", errors="replace")
        sha_hex = data[nul_idx + 1 : nul_idx + 21].hex()
        entries.append((mode, name, sha_hex))
        pos = nul_idx + 21
    return entries

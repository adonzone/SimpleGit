"""Core implementations for savepoints, remotes, conflicts, ignore, tags, and doctor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from simplegit.core.auth import AuthStatus, get_auth_status
from simplegit.core.operations import get_repo_state, resolve_clone_url
from simplegit.core.runner import find_git_binary, get_git_version, run_git
from simplegit.errors import NotARepoError, SimpleGitError

_IGNORE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "python": (
        "__pycache__/",
        "*.py[cod]",
        ".venv/",
        "venv/",
        "*.egg-info/",
        "dist/",
        "build/",
        ".pytest_cache/",
    ),
    "node": (
        "node_modules/",
        "dist/",
        "build/",
        ".env",
        "*.log",
        "npm-debug.log*",
    ),
    "macos": (
        ".DS_Store",
        ".AppleDouble",
        ".LSOverride",
        "._*",
    ),
    "general": (
        ".env",
        ".env.local",
        "*.log",
        "*.tmp",
        ".DS_Store",
    ),
}


@dataclass(frozen=True)
class ConflictDetail:
    """Conflicted file and line numbers of `<<<<<<<` markers."""

    path: str
    marker_lines: tuple[int, ...]


@dataclass(frozen=True)
class DoctorCheck:
    """Single health check result for `sgit doctor`."""

    name: str
    status: str  # "ok", "warn", "fail"
    detail: str
    fix_hint: str | None = None


def savepoint_push(repo_root: Path, message: str | None = None) -> str:
    """Create a stash savepoint including untracked files."""
    args = ["stash", "push", "-u"]
    if message:
        args.extend(["-m", message])
    res = run_git(args, cwd=repo_root)
    return res.stdout.strip()


def savepoint_list(repo_root: Path) -> list[str]:
    """List existing stash savepoints."""
    res = run_git(["stash", "list"], cwd=repo_root)
    return [line for line in res.stdout.splitlines() if line.strip()]


def savepoint_pop(repo_root: Path, index: int = 0, keep: bool = False) -> str:
    """Apply (and optionally drop) a stash savepoint by index."""
    sub = "apply" if keep else "pop"
    res = run_git(["stash", sub, f"stash@{{{index}}}"], cwd=repo_root)
    return res.stdout.strip()


def savepoint_drop(repo_root: Path, index: int = 0) -> None:
    """Delete a stash savepoint by index."""
    run_git(["stash", "drop", f"stash@{{{index}}}"], cwd=repo_root)


def list_remotes(repo_root: Path) -> list[tuple[str, str]]:
    """Return unique `(name, url)` pairs from `git remote -v`."""
    res = run_git(["remote", "-v"], cwd=repo_root)
    seen: set[tuple[str, str]] = set()
    remotes: list[tuple[str, str]] = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            pair = (parts[0], parts[1])
            if pair not in seen:
                seen.add(pair)
                remotes.append(pair)
    return remotes


def add_remote(
    repo_root: Path,
    name: str,
    target: str,
    github: bool = False,
    gitlab: bool = False,
    ssh: bool = False,
) -> str:
    """Add a remote using `-gh`/`-gl` shorthand or full URL/path."""
    url = resolve_clone_url(target, github=github, gitlab=gitlab, ssh=ssh)
    run_git(["remote", "add", name, url], cwd=repo_root)
    return url


def set_remote_url(
    repo_root: Path,
    name: str,
    target: str,
    github: bool = False,
    gitlab: bool = False,
    ssh: bool = False,
) -> str:
    """Update an existing remote URL."""
    url = resolve_clone_url(target, github=github, gitlab=gitlab, ssh=ssh)
    run_git(["remote", "set-url", name, url], cwd=repo_root)
    return url


def remove_remote(repo_root: Path, name: str) -> None:
    run_git(["remote", "remove", name], cwd=repo_root)


def inspect_conflicts(repo_root: Path) -> list[ConflictDetail]:
    """Return conflicted files and line numbers containing `<<<<<<<` markers."""
    state = get_repo_state(repo_root)
    details: list[ConflictDetail] = []
    for item in state.conflicted_files:
        full_path = repo_root / item.path
        markers: list[int] = []
        if full_path.is_file():
            text = full_path.read_text(encoding="utf-8", errors="replace")
            for idx, line in enumerate(text.splitlines(), start=1):
                if line.startswith("<<<<<<<"):
                    markers.append(idx)
        details.append(ConflictDetail(path=item.path, marker_lines=tuple(markers)))
    return details


def resolve_conflicts(repo_root: Path, side: str, paths: list[str]) -> None:
    """Resolve conflicted files using `--ours` or `--theirs` and stage them."""
    if side not in ("ours", "theirs"):
        raise SimpleGitError("Side must be `ours` or `theirs`.")
    if not paths:
        raise SimpleGitError("Specify at least one conflicted file path.")
    run_git(["checkout", f"--{side}", "--", *paths], cwd=repo_root)
    run_git(["add", "--", *paths], cwd=repo_root)


def add_ignore_patterns(
    repo_root: Path,
    patterns: list[str],
    template: str | None = None,
) -> list[str]:
    """Append unique patterns (and/or template patterns) to `.gitignore`."""
    to_add: list[str] = list(patterns)
    if template:
        key = template.lower()
        if key not in _IGNORE_TEMPLATES:
            valid = ", ".join(sorted(_IGNORE_TEMPLATES))
            raise SimpleGitError(f"Unknown template '{template}'.", hint=f"Available templates: {valid}")
        to_add.extend(_IGNORE_TEMPLATES[key])

    if not to_add:
        raise SimpleGitError("Provide patterns or `--template <name>`.", hint="Example: `sgit ignore '*.log' .env`")

    gitignore = repo_root / ".gitignore"
    existing_lines: list[str] = []
    if gitignore.is_file():
        existing_lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    existing_set = {ln.strip() for ln in existing_lines}

    added: list[str] = []
    for pat in to_add:
        cleaned = pat.strip()
        if cleaned and cleaned not in existing_set:
            existing_set.add(cleaned)
            existing_lines.append(cleaned)
            added.append(cleaned)

    if added:
        content = "\n".join(existing_lines) + "\n"
        gitignore.write_text(content, encoding="utf-8")
    return added


def list_ignore_patterns(repo_root: Path) -> list[str]:
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return []
    return [ln for ln in gitignore.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]


def list_tags(repo_root: Path) -> list[str]:
    res = run_git(["tag", "-l", "--sort=-v:refname"], cwd=repo_root)
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def create_tag(repo_root: Path, name: str, message: str | None = None, push: bool = False) -> None:
    args = ["tag"]
    if message:
        args.extend(["-a", name, "-m", message])
    else:
        args.append(name)
    run_git(args, cwd=repo_root)
    if push:
        run_git(["push", "origin", name], cwd=repo_root, interactive=True, stream_output=True)


def delete_tag(repo_root: Path, name: str, remote: bool = False) -> None:
    run_git(["tag", "-d", name], cwd=repo_root)
    if remote:
        run_git(["push", "origin", "--delete", name], cwd=repo_root, interactive=True, stream_output=True)


def run_doctor(start: Path | None = None) -> list[DoctorCheck]:
    """Run environment, identity, auth, and repository health checks."""
    checks: list[DoctorCheck] = []

    try:
        git_bin = find_git_binary()
        ver = get_git_version()
        ver_str = ".".join(map(str, ver))
        if ver >= (2, 23, 0):
            checks.append(DoctorCheck("Git binary", "ok", f"{git_bin} (v{ver_str})"))
        else:
            checks.append(
                DoctorCheck(
                    "Git binary",
                    "warn",
                    f"{git_bin} (v{ver_str} — recommend >= 2.23)",
                    "Upgrade Git for full `switch`/`restore` support.",
                )
            )
    except SimpleGitError as exc:
        checks.append(DoctorCheck("Git binary", "fail", exc.message, exc.hint))
        return checks

    user_name = run_git(["config", "--get", "user.name"], check=False).stdout.strip()
    user_email = run_git(["config", "--get", "user.email"], check=False).stdout.strip()
    if user_name and user_email:
        checks.append(DoctorCheck("Git identity", "ok", f"{user_name} <{user_email}>"))
    else:
        checks.append(
            DoctorCheck(
                "Git identity",
                "warn",
                "user.name or user.email is not set",
                'Run `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`',
            )
        )

    helper = run_git(["config", "--get", "credential.helper"], check=False).stdout.strip()
    if helper:
        checks.append(DoctorCheck("Credential helper", "ok", helper))
    else:
        checks.append(
            DoctorCheck(
                "Credential helper",
                "warn",
                "No credential.helper configured",
                "Run `sgit auth login -gh` or `sgit auth login -gl` to configure HTTPS credentials.",
            )
        )

    auth_list: list[AuthStatus] = get_auth_status()
    authed_hosts = [a.host for a in auth_list if a.https_user]
    ssh_keys = auth_list[0].ssh_keys if auth_list else ()
    if authed_hosts or ssh_keys:
        parts = []
        if authed_hosts:
            parts.append("HTTPS: " + ", ".join(authed_hosts))
        if ssh_keys:
            parts.append("SSH: " + ", ".join(ssh_keys))
        checks.append(DoctorCheck("GitHub / GitLab auth", "ok", " | ".join(parts)))
    else:
        checks.append(
            DoctorCheck(
                "GitHub / GitLab auth",
                "warn",
                "No stored GitHub/GitLab tokens or SSH keys found",
                "Run `sgit auth login -gh` or `sgit auth login -gl`.",
            )
        )

    try:
        state = get_repo_state(start)
        status_note = f"branch '{state.branch}'"
        if state.active_op:
            checks.append(
                DoctorCheck(
                    "Repository state",
                    "warn",
                    f"{status_note} ({state.active_op} in progress)",
                    "Resolve or abort the in-progress operation.",
                )
            )
        else:
            checks.append(DoctorCheck("Repository state", "ok", status_note))
    except NotARepoError:
        checks.append(DoctorCheck("Repository state", "warn", "Current directory is not a Git repository"))

    return checks

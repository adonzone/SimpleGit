"""High-level Git workflows composing native `.git` inspection and `git` runner."""

from __future__ import annotations

from pathlib import Path

from simplegit.core.models import (
    BranchInfo,
    CommitInfo,
    FileChange,
    GitObject,
    NetworkCommit,
    NetworkGraph,
    NetworkLane,
    RepoLocation,
    RepoState,
    SavePlan,
)
from simplegit.core.native_git import (
    detect_active_operation,
    discover_repo,
    read_head,
    read_loose_object,
)
from simplegit.core.runner import run_git, run_git_bytes, split_nul_lines
from simplegit.errors import NothingToCommitError, SimpleGitError


def get_repo_state(start: Path | None = None) -> RepoState:
    """Return full `RepoState` combining native `.git` state with `git status --porcelain=v2`."""
    location = discover_repo(start)
    branch, head_sha, detached = read_head(location)
    active_op = detect_active_operation(location.git_dir)

    res = run_git(["status", "--porcelain=v2", "--branch", "-z"], cwd=location.root)
    parsed_branch, upstream, ahead, behind, changes = _parse_porcelain_v2(res.stdout)

    if parsed_branch and parsed_branch != "(detached)":
        branch = parsed_branch

    return RepoState(
        location=location,
        branch=branch,
        head_sha=head_sha,
        detached=detached,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        active_op=active_op,
        changes=tuple(changes),
    )


def _parse_porcelain_v2(
    output: str,
) -> tuple[str | None, str | None, int, int, list[FileChange]]:
    branch: str | None = None
    upstream: str | None = None
    ahead = 0
    behind = 0
    changes: list[FileChange] = []

    tokens = output.split("\0")
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if not entry:
            continue

        if entry.startswith("# "):
            if entry.startswith("# branch.head "):
                branch = entry[len("# branch.head ") :]
            elif entry.startswith("# branch.upstream "):
                upstream = entry[len("# branch.upstream ") :]
            elif entry.startswith("# branch.ab "):
                for part in entry[len("# branch.ab ") :].split():
                    if part.startswith("+"):
                        ahead = int(part[1:])
                    elif part.startswith("-"):
                        behind = int(part[1:])
        elif entry.startswith("1 "):
            parts = entry.split(" ", 8)
            xy = parts[1]
            changes.append(FileChange(path=parts[8], status_x=xy[0], status_y=xy[1]))
        elif entry.startswith("2 "):
            parts = entry.split(" ", 9)
            xy = parts[1]
            orig_path = tokens[i] if i < len(tokens) else None
            i += 1
            changes.append(
                FileChange(path=parts[9], status_x=xy[0], status_y=xy[1], orig_path=orig_path)
            )
        elif entry.startswith("u "):
            parts = entry.split(" ", 10)
            xy = parts[1]
            changes.append(
                FileChange(path=parts[10], status_x=xy[0], status_y=xy[1], unmerged=True)
            )
        elif entry.startswith("? "):
            changes.append(
                FileChange(path=entry[2:], status_x="?", status_y="?", untracked=True)
            )

    return branch, upstream, ahead, behind, changes


def collect_save_candidates(
    repo_root: Path,
    tracked_only: bool = False,
    paths: list[str] | None = None,
) -> SavePlan:
    """Discover files to stage via `git diff` (and untracked files unless `tracked_only`)."""
    path_args = ["--", *paths] if paths else []

    diff_res = run_git(["diff", "--name-only", "-z", *path_args], cwd=repo_root)
    tracked_diff = tuple(split_nul_lines(diff_res.stdout))

    staged_res = run_git(["diff", "--cached", "--name-only", "-z", *path_args], cwd=repo_root)
    already_staged = tuple(split_nul_lines(staged_res.stdout))

    untracked: tuple[str, ...] = ()
    if not tracked_only:
        untracked_res = run_git(
            ["ls-files", "--others", "--exclude-standard", "-z", *path_args],
            cwd=repo_root,
        )
        untracked = tuple(split_nul_lines(untracked_res.stdout))

    return SavePlan(
        repo_root=repo_root,
        tracked_diff_files=tracked_diff,
        untracked_files=untracked,
        already_staged_files=already_staged,
    )


def execute_save(
    plan: SavePlan,
    message: str,
    amend: bool = False,
    push: bool = False,
    dry_run: bool = False,
) -> tuple[str, list[str]]:
    """Stage discovered files, commit with `message`, and optionally push."""
    if not plan.all_commit_files and not amend:
        raise NothingToCommitError(
            message="Nothing to save — no modified or untracked files found.",
            hint="Edit or create a file first, or check `sgit status`.",
        )

    staged_now = plan.files_to_stage
    if dry_run:
        return ("dry-run", plan.all_commit_files)

    if staged_now:
        run_git(["add", "-A", "--", *staged_now], cwd=plan.repo_root)

    commit_args = ["commit", "-m", message]
    if amend:
        commit_args.append("--amend")
    run_git(commit_args, cwd=plan.repo_root)

    sha_res = run_git(["rev-parse", "--short", "HEAD"], cwd=plan.repo_root)
    short_sha = sha_res.stdout.strip()

    if push:
        push_repo(plan.repo_root)

    return (short_sha, plan.all_commit_files)


def get_diff(
    repo_root: Path,
    staged: bool = False,
    stat: bool = False,
    name_only: bool = False,
    paths: list[str] | None = None,
) -> str:
    """Return unified diff, diffstat, or changed filenames."""
    args = ["diff"]
    if staged:
        args.append("--cached")
    if stat:
        args.append("--stat")
    elif name_only:
        args.append("--name-only")
    if paths:
        args.extend(["--", *paths])
    return run_git(args, cwd=repo_root).stdout


def get_log(repo_root: Path, limit: int = 15) -> list[CommitInfo]:
    """Return recent commits for the current HEAD."""
    check_head = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo_root, check=False)
    if check_head.returncode != 0:
        return []

    fmt = "%H%x1f%h%x1f%an%x1f%ar%x1f%s%x1f%P%x1e"
    res = run_git(["log", f"-n{limit}", f"--format={fmt}"], cwd=repo_root)
    commits: list[CommitInfo] = []
    for record in res.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split("\x1f")
        if len(fields) < 6:
            continue
        parents = tuple(p for p in fields[5].split() if p)
        commits.append(
            CommitInfo(
                sha=fields[0],
                short_sha=fields[1],
                author=fields[2],
                date=fields[3],
                subject=fields[4],
                parents=parents,
            )
        )
    return commits


def get_network_graph(
    repo_root: Path,
    limit: int = 14,
    include_local: bool = True,
    include_hosted: bool = True,
    fetch_remote: bool = False,
) -> NetworkGraph:
    """Build an X=Time, Y=Branch Network graph across Local and Hosted viewpoints."""
    if fetch_remote:
        run_git(["fetch", "--prune"], cwd=repo_root, check=False)

    check_head = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo_root, check=False)
    if check_head.returncode != 0:
        return NetworkGraph(lanes=(), commits=())

    branches = list_branches(repo_root, include_remote=include_hosted)
    raw_lanes = _build_network_lanes(branches, include_local=include_local, include_hosted=include_hosted)
    if not raw_lanes:
        return NetworkGraph(lanes=(), commits=())

    sha_to_lane: dict[str, int] = {}
    for lane_idx, lane in enumerate(raw_lanes):
        rev_res = run_git(
            ["rev-list", "--first-parent", "-n", "200", lane.name],
            cwd=repo_root,
            check=False,
        )
        if rev_res.returncode != 0:
            continue
        for sha in rev_res.stdout.splitlines():
            sha = sha.strip()
            if sha and sha not in sha_to_lane:
                sha_to_lane[sha] = lane_idx

    scope_args = ["--all"] if (include_local and include_hosted) else (["--branches"] if include_local else ["--remotes"])
    args = [
        "log",
        *scope_args,
        "--no-renames",
        "--name-status",
        "--topo-order",
        "--date=format:%m-%d %H:%M",
        "--format=__NET__%x09%H%x09%h%x09%cd%x09%an%x09%P%x09%s",
    ]
    if limit > 0:
        args.append(f"-n{limit}")

    res = run_git(args, cwd=repo_root, check=False)
    if res.returncode != 0:
        return NetworkGraph(lanes=(), commits=())

    parsed = _parse_network_log(res.stdout, sha_to_lane)
    parsed.reverse()  # Oldest -> newest left-to-right along X-axis

    visible_shas = {c.sha for c in parsed}
    used_indices = {c.lane_index for c in parsed} | {
        idx for idx, ln in enumerate(raw_lanes) if ln.tip_sha in visible_shas
    }
    remap = {old_idx: new_idx for new_idx, old_idx in enumerate(sorted(used_indices))}
    final_lanes = tuple(raw_lanes[old_idx] for old_idx in sorted(used_indices))
    final_commits = tuple(
        NetworkCommit(
            sha=c.sha,
            short_sha=c.short_sha,
            date_label=c.date_label,
            author=c.author,
            subject=c.subject,
            lane_index=remap.get(c.lane_index, 0),
            parents=c.parents,
            file_changes=c.file_changes,
        )
        for c in parsed
    )
    return NetworkGraph(lanes=final_lanes, commits=final_commits)


def _build_network_lanes(
    branches: list[BranchInfo],
    include_local: bool,
    include_hosted: bool,
) -> list[NetworkLane]:
    def _sort_key(br: BranchInfo) -> tuple[int, int, str]:
        remote_rank = 1 if br.is_remote else 0
        primary_rank = 0 if br.name in ("main", "master", "origin/main", "origin/master") else (1 if br.is_current else 2)
        return (remote_rank, primary_rank, br.name)

    lanes: list[NetworkLane] = []
    for br in sorted(branches, key=_sort_key):
        if br.is_remote:
            if not include_hosted or br.name.endswith("/HEAD"):
                continue
            lanes.append(NetworkLane(name=br.name, scope="hosted", tip_sha=br.sha, is_current=False))
        else:
            if not include_local:
                continue
            lanes.append(NetworkLane(name=br.name, scope="local", tip_sha=br.sha, is_current=br.is_current))
    return lanes


def _parse_network_log(output: str, sha_to_lane: dict[str, int]) -> list[NetworkCommit]:
    commits: list[NetworkCommit] = []
    current_fields: list[str] | None = None
    current_files: list[tuple[str, str]] = []

    def _flush() -> None:
        if current_fields is None:
            return
        sha, short_sha, date_lbl, author, parents_str, subject = current_fields
        commits.append(
            NetworkCommit(
                sha=sha,
                short_sha=short_sha,
                date_label=date_lbl,
                author=author,
                subject=subject,
                lane_index=sha_to_lane.get(sha, 0),
                parents=tuple(p for p in parents_str.split() if p),
                file_changes=tuple(current_files),
            )
        )

    for line in output.splitlines():
        if line.startswith("__NET__\t"):
            _flush()
            parts = line.split("\t", 6)
            current_fields = parts[1:] if len(parts) >= 7 else None
            current_files = []
        elif line.strip() and current_fields is not None and "\t" in line:
            status, path = line.split("\t", 1)
            current_files.append((status[:1], path.strip()))
    _flush()
    return commits


def list_tracked_files(repo_root: Path) -> list[str]:
    """Return tracked file paths in the repository."""
    res = run_git(["ls-files", "-z"], cwd=repo_root)
    return sorted(split_nul_lines(res.stdout))


def inspect_object(location: RepoLocation, rev_or_sha: str) -> GitObject:
    """Inspect a Git object using native loose `.git/objects` first, falling back to `git cat-file`."""
    rev_res = run_git(["rev-parse", "--verify", rev_or_sha], cwd=location.root)
    sha = rev_res.stdout.strip()

    loose = read_loose_object(location.common_dir, sha)
    if loose is not None:
        return loose

    kind = run_git(["cat-file", "-t", sha], cwd=location.root).stdout.strip()
    size = int(run_git(["cat-file", "-s", sha], cwd=location.root).stdout.strip())
    content = run_git_bytes(["cat-file", kind, sha], cwd=location.root)
    return GitObject(kind=kind, size=size, sha=sha, content=content, source="packed")


def list_branches(repo_root: Path, include_remote: bool = False) -> list[BranchInfo]:
    """Return local (and optionally remote) branches."""
    args = [
        "for-each-ref",
        "--format=%(HEAD)%09%(refname:short)%09%(objectname)%09%(upstream:short)%09%(refname)",
        "refs/heads",
    ]
    if include_remote:
        args.append("refs/remotes")
    res = run_git(args, cwd=repo_root)
    branches: list[BranchInfo] = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        head_mark, name, sha, upstream, full_ref = line.split("\t")
        branches.append(
            BranchInfo(
                name=name,
                sha=sha,
                is_current=(head_mark.strip() == "*"),
                is_remote=full_ref.startswith("refs/remotes/"),
                upstream=upstream or None,
            )
        )
    return branches


def create_branch(repo_root: Path, name: str) -> None:
    run_git(["branch", name], cwd=repo_root)


def delete_branch(repo_root: Path, name: str, force: bool = False) -> None:
    flag = "-D" if force else "-d"
    run_git(["branch", flag, name], cwd=repo_root)


def switch_branch(repo_root: Path, name: str, create: bool = False) -> None:
    args = ["switch"]
    if create:
        args.append("-c")
    args.append(name)
    run_git(args, cwd=repo_root)


def merge_branch(
    repo_root: Path,
    branch: str | None = None,
    abort: bool = False,
    continue_merge: bool = False,
) -> str:
    if abort:
        return run_git(["merge", "--abort"], cwd=repo_root).stdout
    if continue_merge:
        return run_git(["merge", "--continue", "--no-edit"], cwd=repo_root).stdout
    if not branch:
        raise SimpleGitError("Specify a branch name to merge.", hint="Usage: `sgit merge <branch>`")
    return run_git(["merge", branch], cwd=repo_root).stdout


def undo_commit(repo_root: Path) -> str:
    """Undo the most recent commit while preserving all edits in the index/worktree."""
    has_head = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo_root, check=False)
    if has_head.returncode != 0:
        raise SimpleGitError("There are no commits to undo yet.")

    has_parent = run_git(["rev-parse", "--verify", "--quiet", "HEAD~1"], cwd=repo_root, check=False)
    if has_parent.returncode == 0:
        run_git(["reset", "--soft", "HEAD~1"], cwd=repo_root)
        return "Undid last commit (changes remain staged)."

    # Root commit has no parent; delete HEAD ref while keeping staged files intact.
    run_git(["update-ref", "-d", "HEAD"], cwd=repo_root)
    return "Undid initial commit (changes remain staged)."


def undo_stage(repo_root: Path, paths: list[str] | None = None) -> None:
    """Unstage files without modifying working tree contents."""
    has_head = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo_root, check=False)
    if has_head.returncode == 0:
        args = ["reset", "-q", "HEAD"]
        if paths:
            args.extend(["--", *paths])
        run_git(args, cwd=repo_root)
    else:
        targets = paths if paths else ["."]
        run_git(["rm", "-r", "--cached", "-q", "--", *targets], cwd=repo_root)


def undo_changes(repo_root: Path, paths: list[str] | None = None) -> None:
    """Discard unstaged working tree modifications."""
    targets = paths if paths else ["."]
    run_git(["restore", "--worktree", "--", *targets], cwd=repo_root)


def init_repo(path: Path | None = None, bare: bool = False) -> Path:
    """Initialize a new Git repository defaulting to `main`."""
    target = (path or Path.cwd()).resolve()
    target.mkdir(parents=True, exist_ok=True)
    args = ["init", "-b", "main"]
    if bare:
        args.append("--bare")
    res = run_git(args, cwd=target, check=False)
    if res.returncode != 0:
        # Fallback for Git versions prior to `-b` on init
        fallback = ["init"] + (["--bare"] if bare else [])
        run_git(fallback, cwd=target)
    return target


def resolve_clone_url(
    target: str,
    github: bool = False,
    gitlab: bool = False,
    ssh: bool = False,
) -> str:
    """Resolve a clone target from `-gh`/`-gl` shorthand, hosted `.git` URL, or local path."""
    if github and gitlab:
        raise SimpleGitError(
            "Choose either `-gh` (GitHub) or `-gl` (GitLab), not both.",
        )

    cleaned = target.strip()
    if not cleaned:
        raise SimpleGitError("Repository URL or path is required.")

    if github or gitlab:
        if "://" in cleaned or cleaned.startswith("git@"):
            return cleaned
        host = "github.com" if github else "gitlab.com"
        slug = cleaned.strip("/")
        if slug.endswith(".git"):
            slug = slug[:-4]
        if "/" not in slug:
            flag = "-gh" if github else "-gl"
            raise SimpleGitError(
                f"Invalid repository shorthand '{target}'.",
                hint=f"Expected `owner/repo`, e.g. `sgit clone {flag} owner/repo`.",
            )
        return f"git@{host}:{slug}.git" if ssh else f"https://{host}/{slug}.git"

    if "://" in cleaned or cleaned.startswith("git@") or Path(cleaned).expanduser().exists():
        return cleaned

    first_part, _, rest = cleaned.partition("/")
    if "." in first_part and rest:
        slug = cleaned.rstrip("/")
        if not slug.endswith(".git"):
            slug = f"{slug}.git"
        if ssh:
            path_part = slug.split("/", 1)[1]
            return f"git@{first_part}:{path_part}"
        return f"https://{slug}"

    raise SimpleGitError(
        f"Cannot determine repository host for '{target}'.",
        hint="Use `-gh` for GitHub, `-gl` for GitLab, or pass a full `.git` URL / local `.git` directory.",
    )


def clone_repo(
    url: str,
    directory: str | None = None,
    branch: str | None = None,
    github: bool = False,
    gitlab: bool = False,
    ssh: bool = False,
) -> str:
    """Clone a remote or local `.git` repository and return the resolved URL."""
    resolved = resolve_clone_url(url, github=github, gitlab=gitlab, ssh=ssh)
    args = ["clone"]
    if branch:
        args.extend(["-b", branch])
    args.append(resolved)
    if directory:
        args.append(directory)
    run_git(args, interactive=True, stream_output=True)
    return resolved


def pull_repo(repo_root: Path, use_merge: bool = False, autostash: bool = False) -> None:
    args = ["pull"]
    if not use_merge:
        args.append("--rebase")
    if autostash:
        args.append("--autostash")
    run_git(args, cwd=repo_root, interactive=True, stream_output=True)


def push_repo(repo_root: Path) -> None:
    state = get_repo_state(repo_root)
    if state.detached:
        raise SimpleGitError(
            "Cannot push while in detached HEAD state.",
            hint="Switch to a branch first with `sgit switch <branch>`.",
        )
    if state.upstream:
        run_git(["push"], cwd=repo_root, interactive=True, stream_output=True)
    else:
        run_git(["push", "-u", "origin", state.branch], cwd=repo_root, interactive=True, stream_output=True)


def sync_repo(
    repo_root: Path,
    use_merge: bool = False,
    autostash: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Fetch, pull (if upstream exists), and push current branch."""
    state = get_repo_state(repo_root)
    if state.detached:
        raise SimpleGitError(
            "Cannot sync while in detached HEAD state.",
            hint="Switch to a branch first with `sgit switch <branch>`.",
        )

    actions: list[str] = []
    if state.upstream:
        actions.append(f"pull ({'merge' if use_merge else 'rebase'}) from {state.upstream}")
    else:
        actions.append(f"publish new branch '{state.branch}' to origin")
    actions.append(f"push '{state.branch}'")

    if dry_run:
        return actions

    if state.upstream:
        pull_repo(repo_root, use_merge=use_merge, autostash=autostash)
    push_repo(repo_root)
    return actions

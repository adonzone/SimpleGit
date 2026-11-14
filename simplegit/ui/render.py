"""Terminal renderers for errors, status, diffs, logs, and `.git` objects."""

from __future__ import annotations

import sys

from simplegit.core.models import (
    BranchInfo,
    CommitInfo,
    FileChange,
    GitObject,
    NetworkCommit,
    NetworkGraph,
    RepoState,
)
from simplegit.core.native_git import parse_commit_object, parse_tree_object
from simplegit.errors import SimpleGitError
from simplegit.ui.theme import THEME


def render_error(err: SimpleGitError) -> None:
    """Print a high-contrast error block to stderr so failures are easy to spot."""
    stream = sys.stderr
    badge = THEME.badge("ERROR", "bg_red", stream=stream)
    print(f"\n{badge} {THEME.error(err.message, stream=stream)}", file=stream)

    if err.affected_files:
        print(THEME.warn("  Affected files:", stream=stream), file=stream)
        for path in err.affected_files[:15]:
            print(f"    {THEME.error('•', stream=stream)} {path}", file=stream)
        if len(err.affected_files) > 15:
            remaining = len(err.affected_files) - 15
            print(THEME.muted(f"    ... and {remaining} more", stream=stream), file=stream)

    if err.command:
        print(f"  {THEME.muted('Command:')} {err.command}", file=stream)

    if err.details:
        first_lines = [ln for ln in err.details.splitlines() if ln.strip()][:4]
        if first_lines:
            print(f"  {THEME.muted('Git output:')}", file=stream)
            for ln in first_lines:
                print(f"    {THEME.style(ln, 'red', stream=stream)}", file=stream)

    if err.hint:
        print(f"  {THEME.info('Hint:')} {err.hint}", file=stream)
    print(file=stream)


def render_status(state: RepoState, short: bool = False) -> None:
    """Render grouped repository status and actionable next-step guidance."""
    branch_label = (
        THEME.warn(f"detached @ {state.branch}")
        if state.detached
        else THEME.accent(state.branch)
    )
    tracking = ""
    if state.upstream:
        parts: list[str] = []
        if state.ahead:
            parts.append(THEME.success(f"↑{state.ahead}"))
        if state.behind:
            parts.append(THEME.warn(f"↓{state.behind}"))
        delta = " ".join(parts) if parts else THEME.muted("up to date")
        tracking = f" {THEME.muted('->')} {THEME.info(state.upstream)} ({delta})"

    print(f"{THEME.bold('On branch')} {branch_label}{tracking}")
    if state.active_op:
        print(f"{THEME.badge(state.active_op, 'bg_yellow')} {THEME.warn('Operation in progress')}")

    if state.is_clean:
        print(THEME.success("✓ Working tree clean — nothing to commit."))
        return

    if short:
        for change in state.changes:
            code = "??" if change.untracked else f"{change.status_x}{change.status_y}"
            print(f"  {THEME.warn(code)} {change.display_path}")
        return

    _print_change_group("Conflicts (resolve before committing)", state.conflicted_files, "bright_red", "!")
    _print_change_group("Staged (ready to commit)", state.staged_files, "green", "+")
    _print_change_group("Modified (unstaged changes)", state.unstaged_files, "yellow", "~")
    _print_change_group("Untracked (new files)", state.untracked_files, "cyan", "?")

    print()
    if state.conflicted_files:
        print(THEME.info('Next: resolve conflicts, then run `sgit save "resolve conflicts"`'))
    else:
        print(THEME.muted('Tip: run `sgit save "your message"` to stage & commit in one step.'))


def _print_change_group(title: str, items: list[FileChange], color: str, marker: str) -> None:
    if not items:
        return
    print()
    print(THEME.style(f"{title} ({len(items)}):", "bold", color))
    for item in items:
        print(f"  {THEME.style(marker, 'bold', color)} {item.display_path}")


def render_diff(diff_text: str) -> None:
    """Colorize unified diff output cleanly."""
    if not diff_text.strip():
        print(THEME.muted("No differences to display."))
        return
    for line in diff_text.splitlines():
        if line.startswith(("diff --git", "index ", "--- ", "+++ ")):
            print(THEME.bold(line))
        elif line.startswith("@@"):
            print(THEME.info(line))
        elif line.startswith("+"):
            print(THEME.style(line, "green"))
        elif line.startswith("-"):
            print(THEME.style(line, "red"))
        else:
            print(line)


def render_log(commits: list[CommitInfo]) -> None:
    """Render concise commit history."""
    if not commits:
        print(THEME.muted("No commits yet."))
        return
    for commit in commits:
        sha = THEME.warn(commit.short_sha)
        date = THEME.muted(commit.date)
        author = THEME.info(commit.author)
        print(f"{sha} {commit.subject} {THEME.muted('(')}{date} · {author}{THEME.muted(')')}")


def render_branches(branches: list[BranchInfo]) -> None:
    """Render local and remote branches."""
    if not branches:
        print(THEME.muted("No branches found."))
        return
    for br in branches:
        marker = THEME.success("* ") if br.is_current else "  "
        name = THEME.success(br.name) if br.is_current else (THEME.muted(br.name) if br.is_remote else br.name)
        sha = THEME.muted(br.sha[:7])
        upstream = f" -> {THEME.info(br.upstream)}" if br.upstream else ""
        print(f"{marker}{name} {sha}{upstream}")


def render_git_object(obj: GitObject) -> None:
    """Render a decoded `.git` object (`commit`, `tree`, `blob`, or `tag`)."""
    print(f"{THEME.bold('Object:')} {THEME.warn(obj.sha)} ({THEME.info(obj.kind)}, {obj.size} bytes, {obj.source})")
    if obj.kind == "commit":
        parsed = parse_commit_object(obj.content)
        print(f"  {THEME.muted('tree:')}      {parsed['tree']}")
        for parent in parsed["parents"]:
            print(f"  {THEME.muted('parent:')}    {parent}")
        if parsed["author"]:
            print(f"  {THEME.muted('author:')}    {parsed['author']}")
        if parsed["committer"]:
            print(f"  {THEME.muted('committer:')} {parsed['committer']}")
        print()
        for line in parsed["message"].splitlines():
            print(f"  {line}")
    elif obj.kind == "tree":
        for mode, name, sha in parse_tree_object(obj.content):
            print(f"  {THEME.muted(mode.zfill(6))} {THEME.warn(sha[:7])} {name}")
    else:
        text = obj.content.decode("utf-8", errors="replace")
        print(text, end="" if text.endswith("\n") else "\n")


_LANE_COLORS = ("cyan", "green", "magenta", "yellow", "blue", "bright_cyan")


def render_viewer(
    state: RepoState,
    graph: NetworkGraph,
    tracked_files: list[str] | None = None,
) -> None:
    """Render a GitHub Insights/Network-style X=Time, Y=Branches graph."""
    branch_label = THEME.warn(f"detached@{state.branch}") if state.detached else THEME.accent(state.branch)
    print(THEME.bold(f"Network Graph (X: Time →, Y: Branches ↕) — {state.location.root.name}") + f"  [{branch_label}]")
    if state.active_op:
        print(f"  {THEME.badge(state.active_op, 'bg_yellow')} {THEME.warn('Operation in progress')}")

    if not graph.commits or not graph.lanes:
        print(THEME.muted("\n  No commits yet."))
        return

    lanes = graph.lanes
    commits = graph.commits
    col_w = 7
    sha_to_col = {c.sha: i for i, c in enumerate(commits)}
    sha_to_commit = {c.sha: c for c in commits}

    grid_rows = len(lanes) * 2 - 1
    grid_cols = len(commits) * col_w
    canvas: list[list[str]] = [[" " for _ in range(grid_cols)] for _ in range(grid_rows)]
    cell_color: list[list[str | None]] = [[None for _ in range(grid_cols)] for _ in range(grid_rows)]

    def _put(r: int, x: int, ch: str, color: str | None = None) -> None:
        if 0 <= r < grid_rows and 0 <= x < grid_cols:
            canvas[r][x] = ch
            if color:
                cell_color[r][x] = color

    # Draw horizontal & fork/merge edges first, then commit nodes on top.
    for col_idx, commit in enumerate(commits):
        lane_c = commit.lane_index
        row_c = lane_c * 2
        x_c = col_idx * col_w
        color_c = _LANE_COLORS[lane_c % len(_LANE_COLORS)]

        for parent_sha in commit.parents:
            if parent_sha not in sha_to_col:
                continue
            col_p = sha_to_col[parent_sha]
            lane_p = sha_to_commit[parent_sha].lane_index
            x_p = col_p * col_w

            if lane_p == lane_c:
                for x in range(x_p + 1, x_c):
                    _put(row_c, x, "─", color_c)
            elif lane_p < lane_c:
                # Fork downward from parent lane to child lane.
                row_p = lane_p * 2
                for r in range(row_p + 1, row_c):
                    _put(r, x_p, "│", color_c)
                _put(row_c, x_p, "╰", color_c)
                for x in range(x_p + 1, x_c):
                    _put(row_c, x, "─", color_c)
            else:
                # Merge upward from parent lane into child lane.
                row_p = lane_p * 2
                color_p = _LANE_COLORS[lane_p % len(_LANE_COLORS)]
                for x in range(x_p + 1, x_c):
                    _put(row_p, x, "─", color_p)
                _put(row_p, x_c, "╯", color_p)
                for r in range(row_c + 1, row_p):
                    _put(r, x_c, "│", color_p)

    for col_idx, commit in enumerate(commits):
        row = commit.lane_index * 2
        x = col_idx * col_w
        color = _LANE_COLORS[commit.lane_index % len(_LANE_COLORS)]
        node = "◆" if len(commit.parents) > 1 else "●"
        label = f"{node}[{col_idx + 1}]"
        for offset, ch in enumerate(label):
            _put(row, x + offset, ch, color)

    # Mark hosted/local branch tips that sit on another lane's commit.
    for lane_idx, lane in enumerate(lanes):
        if lane.tip_sha in sha_to_col:
            tip_col = sha_to_col[lane.tip_sha]
            if sha_to_commit[lane.tip_sha].lane_index != lane_idx:
                _put(lane_idx * 2, tip_col * col_w, "◎", _LANE_COLORS[lane_idx % len(_LANE_COLORS)])

    scope_tags = ["[Hosted]" if ln.scope == "hosted" else "[Local] " for ln in lanes]
    name_w = max(len(ln.name) for ln in lanes) + 3
    prefix_w = len(scope_tags[0]) + 1 + name_w

    print()
    for r in range(grid_rows):
        if r % 2 == 0:
            lane_idx = r // 2
            lane = lanes[lane_idx]
            color = _LANE_COLORS[lane_idx % len(_LANE_COLORS)]
            scope_styled = (
                THEME.info("[Hosted]") if lane.scope == "hosted" else THEME.success("[Local] ")
            )
            marker = "* " if lane.is_current else "  "
            name_str = f"{marker}{lane.name}".ljust(name_w)
            name_styled = THEME.style(name_str, "bold", color) if lane.is_current else THEME.style(name_str, color)
            left = f"  {scope_styled} {name_styled}{THEME.muted('│')} "
        else:
            left = f"  {' ' * prefix_w}{THEME.muted('│')} "

        row_chars = _render_colored_row(canvas[r], cell_color[r])
        print(f"{left}{row_chars.rstrip()}")

    axis_len = max(grid_cols + 2, 20)
    axis_pad = " " * (prefix_w + 2)
    print(f"{axis_pad}{THEME.muted('└' + '─' * axis_len + '▶ Time')}")
    first_dt = commits[0].date_label
    last_dt = commits[-1].date_label
    if len(commits) == 1:
        print(f"{axis_pad} {THEME.muted(first_dt)}")
    else:
        gap = max(2, axis_len - len(first_dt) - len(last_dt))
        print(f"{axis_pad} {THEME.muted(first_dt + ' ' * gap + last_dt)}")

    print(THEME.bold("\nChanges Made & When:"))
    for idx, commit in enumerate(commits, start=1):
        lane = lanes[commit.lane_index]
        color = _LANE_COLORS[commit.lane_index % len(_LANE_COLORS)]
        tag = THEME.style(f"[{idx}]", "bold", color)
        when = THEME.muted(commit.date_label)
        br = THEME.style(lane.name, color)
        sha = THEME.warn(commit.short_sha)
        files_str = _format_commit_files(commit.file_changes)
        print(f"  {tag} {when}  {br}  {sha}  {commit.subject}{files_str}")

    if tracked_files is not None:
        print(THEME.bold(f"\nRepository Files ({len(tracked_files)}):"))
        _render_file_tree(tracked_files)


def _render_colored_row(chars: list[str], colors: list[str | None]) -> str:
    out: list[str] = []
    for ch, color in zip(chars, colors):
        out.append(THEME.style(ch, color) if color and ch != " " else ch)
    return "".join(out)


def _format_commit_files(file_changes: tuple[tuple[str, str], ...]) -> str:
    if not file_changes:
        return ""
    markers = {"A": "+", "M": "~", "D": "-"}
    shown = [f"{markers.get(st, st)}{path}" for st, path in file_changes[:4]]
    extra = f", +{len(file_changes) - 4} more" if len(file_changes) > 4 else ""
    return "  " + THEME.muted("(" + ", ".join(shown) + extra + ")")


def _render_file_tree(paths: list[str]) -> None:
    if not paths:
        print(THEME.muted("  (no tracked files)"))
        return
    tree: dict = {}
    for path in paths:
        node = tree
        for part in path.split("/"):
            node = node.setdefault(part, {})
    _print_tree_node(tree, prefix="  ")


def _print_tree_node(node: dict, prefix: str) -> None:
    items = sorted(node.items(), key=lambda kv: (len(kv[1]) == 0, kv[0]))
    for i, (name, children) in enumerate(items):
        is_last = i == len(items) - 1
        branch_ch = "└── " if is_last else "├── "
        label = THEME.accent(name + "/") if children else name
        print(f"{prefix}{THEME.muted(branch_ch)}{label}")
        if children:
            ext = "    " if is_last else "│   "
            _print_tree_node(children, prefix + THEME.muted(ext))

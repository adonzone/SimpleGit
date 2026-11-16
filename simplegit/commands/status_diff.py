"""Handlers for `sgit status`, `sgit diff`, `sgit log`, and `sgit inspect`."""

from __future__ import annotations

import argparse

from simplegit.core.native_git import discover_repo
from simplegit.core.operations import get_diff, get_log, get_repo_state, inspect_object
from simplegit.ui.render import render_diff, render_git_object, render_log, render_status


def register(subparsers: argparse._SubParsersAction) -> None:
    st = subparsers.add_parser("status", aliases=["st"], help="Show grouped repository status")
    st.add_argument("-s", "--short", action="store_true", help="Compact output")
    st.set_defaults(handler=run_status)

    df = subparsers.add_parser("diff", help="Show colorized file differences")
    df.add_argument("--staged", action="store_true", help="Show staged changes")
    df.add_argument("--stat", action="store_true", help="Show diff summary statistics")
    df.add_argument("--name-only", action="store_true", help="Show changed filenames only")
    df.add_argument("paths", nargs="*", help="Optional paths to filter")
    df.set_defaults(handler=run_diff)

    lg = subparsers.add_parser("log", help="Show concise commit history")
    lg.add_argument("-n", "--limit", type=int, default=15, help="Max commits to show (default: 15)")
    lg.set_defaults(handler=run_log)

    ins = subparsers.add_parser(
        "inspect",
        help="Inspect a Git object directly via `.git/objects` (with packfile fallback)",
    )
    ins.add_argument("target", nargs="?", default="HEAD", help="Commit/tree/blob SHA or ref (default: HEAD)")
    ins.set_defaults(handler=run_inspect)


def run_status(args: argparse.Namespace) -> int:
    state = get_repo_state()
    render_status(state, short=bool(args.short))
    return 0


def run_diff(args: argparse.Namespace) -> int:
    location = discover_repo()
    output = get_diff(
        location.root,
        staged=bool(args.staged),
        stat=bool(args.stat),
        name_only=bool(args.name_only),
        paths=args.paths or None,
    )
    if args.stat or args.name_only:
        print(output, end="" if output.endswith("\n") or not output else "\n")
    else:
        render_diff(output)
    return 0


def run_log(args: argparse.Namespace) -> int:
    location = discover_repo()
    commits = get_log(location.root, limit=max(1, args.limit))
    render_log(commits)
    return 0


def run_inspect(args: argparse.Namespace) -> int:
    location = discover_repo()
    obj = inspect_object(location, args.target)
    render_git_object(obj)
    return 0

"""Handler for `sgit undo` — safe recovery for commits, staging, and working files."""

from __future__ import annotations

import argparse

from simplegit.core.native_git import discover_repo
from simplegit.core.operations import undo_changes, undo_commit, undo_stage
from simplegit.errors import SimpleGitError
from simplegit.ui.terminal import confirm
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "undo",
        help="Safely undo last commit, unstage files, or discard working changes",
    )
    parser.add_argument(
        "target",
        choices=["commit", "stage", "changes"],
        help="What to undo: `commit` (soft reset), `stage` (unstage), or `changes` (discard edits)",
    )
    parser.add_argument("paths", nargs="*", help="Optional files for `stage` or `changes`")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation for `undo changes`")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    location = discover_repo()
    if args.target == "commit":
        msg = undo_commit(location.root)
        print(THEME.success(f"✓ {msg}"))
        return 0

    if args.target == "stage":
        undo_stage(location.root, args.paths or None)
        scope = ", ".join(args.paths) if args.paths else "all staged files"
        print(THEME.success(f"✓ Unstaged {scope} (working edits preserved)."))
        return 0

    scope = ", ".join(args.paths) if args.paths else "ALL unstaged tracked changes"
    if not args.yes:
        if not confirm(f"Discard {scope}? This cannot be undone.", default=False):
            print(THEME.muted("Cancelled."))
            return 0
    try:
        undo_changes(location.root, args.paths or None)
    except SimpleGitError:
        raise
    print(THEME.warn(f"✓ Discarded {scope}."))
    return 0

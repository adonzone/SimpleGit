"""Handler for `sgit save` — one-shot diff discovery, staging, and commit."""

from __future__ import annotations

import argparse

from simplegit.core.native_git import discover_repo
from simplegit.core.operations import collect_save_candidates, execute_save
from simplegit.errors import SimpleGitError
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "save",
        help="Discover changed files from git diff, stage them, and commit in one step",
    )
    parser.add_argument("message_pos", nargs="?", help="Commit message")
    parser.add_argument("files", nargs="*", help="Optional specific files/paths to save")
    parser.add_argument("-m", "--message", dest="message_flag", help="Commit message")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-t",
        "--tracked",
        action="store_true",
        help="Only stage tracked files found in `git diff` (skip untracked files)",
    )
    mode.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Include both tracked diff changes and untracked files (default)",
    )
    parser.add_argument("-p", "--push", action="store_true", help="Push immediately after committing")
    parser.add_argument("--amend", action="store_true", help="Amend the previous commit")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview files without committing")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    files = list(args.files)
    if args.message_flag is not None:
        message = args.message_flag
        if args.message_pos is not None:
            files.insert(0, args.message_pos)
    else:
        message = args.message_pos

    if not message or not message.strip():
        raise SimpleGitError(
            "Commit message is required.",
            hint='Usage: `sgit save "your commit message"` (or `sgit save -m "msg" [files...]`).',
        )

    location = discover_repo()
    plan = collect_save_candidates(
        location.root,
        tracked_only=bool(args.tracked),
        paths=files or None,
    )

    sha, committed_files = execute_save(
        plan,
        message=message.strip(),
        amend=bool(args.amend),
        push=bool(args.push),
        dry_run=bool(args.dry_run),
    )

    if args.dry_run:
        print(THEME.warn("Dry run — no changes committed."))
        for path in committed_files:
            print(f"  {THEME.info('+')} {path}")
        print(THEME.muted(f'Would commit with message: "{message.strip()}"'))
        return 0

    print(THEME.success(f"✓ Saved {sha}:") + f" {message.strip()}")
    for path in committed_files:
        print(f"  {THEME.muted('•')} {path}")
    if args.push:
        print(THEME.success("✓ Pushed to remote."))
    return 0

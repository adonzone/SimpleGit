"""Handlers for `sgit branch`, `sgit switch`, and `sgit merge`."""

from __future__ import annotations

import argparse

from simplegit.core.native_git import discover_repo
from simplegit.core.operations import (
    create_branch,
    delete_branch,
    list_branches,
    merge_branch,
    switch_branch,
)
from simplegit.errors import SimpleGitError
from simplegit.ui.render import render_branches
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    br = subparsers.add_parser("branch", aliases=["br"], help="List, create, or delete branches")
    br.add_argument("name", nargs="?", help="Branch name to create or delete")
    br.add_argument("-a", "--all", action="store_true", help="Include remote-tracking branches")
    br.add_argument("-d", "--delete", action="store_true", help="Delete the named branch")
    br.add_argument("-f", "--force", action="store_true", help="Force delete even if unmerged")
    br.set_defaults(handler=run_branch)

    sw = subparsers.add_parser("switch", aliases=["sw"], help="Switch to a branch (or create with -c)")
    sw.add_argument("name", help="Target branch name")
    sw.add_argument("-c", "--create", action="store_true", help="Create the branch and switch to it")
    sw.set_defaults(handler=run_switch)

    mg = subparsers.add_parser("merge", help="Merge another branch into the current branch")
    mg.add_argument("branch", nargs="?", help="Branch to merge")
    mg.add_argument("--abort", action="store_true", help="Abort an in-progress conflicted merge")
    mg.add_argument("--continue", dest="continue_merge", action="store_true", help="Finish merge after resolving conflicts")
    mg.set_defaults(handler=run_merge)


def run_branch(args: argparse.Namespace) -> int:
    location = discover_repo()
    if args.delete:
        if not args.name:
            raise SimpleGitError(
                "Specify a branch name to delete.",
                hint="Usage: `sgit branch -d <branch-name>`",
            )
        delete_branch(location.root, args.name, force=bool(args.force))
        print(THEME.success(f"✓ Deleted branch '{args.name}'."))
        return 0

    if args.name:
        create_branch(location.root, args.name)
        print(THEME.success(f"✓ Created branch '{args.name}'.") + THEME.muted(f" (Run `sgit switch {args.name}` to switch)"))
        return 0

    branches = list_branches(location.root, include_remote=bool(args.all))
    render_branches(branches)
    return 0


def run_switch(args: argparse.Namespace) -> int:
    location = discover_repo()
    switch_branch(location.root, args.name, create=bool(args.create))
    verb = "Created and switched to" if args.create else "Switched to"
    print(THEME.success(f"✓ {verb} branch '{args.name}'."))
    return 0


def run_merge(args: argparse.Namespace) -> int:
    location = discover_repo()
    out = merge_branch(
        location.root,
        branch=args.branch,
        abort=bool(args.abort),
        continue_merge=bool(args.continue_merge),
    )
    if out.strip():
        print(out.strip())
    if args.abort:
        print(THEME.warn("Merge aborted."))
    elif args.continue_merge:
        print(THEME.success("✓ Merge completed."))
    else:
        print(THEME.success(f"✓ Merged '{args.branch}'."))
    return 0

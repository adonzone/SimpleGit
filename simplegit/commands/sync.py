"""Handlers for `sgit init`, `sgit clone`, `sgit sync`, `sgit pull`, and `sgit push`."""

from __future__ import annotations

import argparse
from pathlib import Path

from simplegit.core.native_git import discover_repo
from simplegit.core.operations import clone_repo, init_repo, pull_repo, push_repo, sync_repo
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    ini = subparsers.add_parser("init", help="Initialize a new Git repository")
    ini.add_argument("path", nargs="?", help="Directory to initialize (default: current directory)")
    ini.add_argument("--bare", action="store_true", help="Create a bare repository")
    ini.set_defaults(handler=run_init)

    cln = subparsers.add_parser("clone", help="Clone a Git repository (supports -gh, -gl, or .git URL/dir)")
    cln.add_argument("url", help="Repository shorthand (with -gh/-gl), `.git` URL, or local `.git` directory")
    cln.add_argument("directory", nargs="?", help="Target folder name")
    cln.add_argument("-b", "--branch", help="Branch to check out")
    host_group = cln.add_mutually_exclusive_group()
    host_group.add_argument("-gh", "--github", action="store_true", help="Expand `owner/repo` as GitHub")
    host_group.add_argument("-gl", "--gitlab", action="store_true", help="Expand `group/repo` as GitLab")
    cln.add_argument("--ssh", action="store_true", help="Use SSH (`git@host:...`) instead of HTTPS")
    cln.set_defaults(handler=run_clone)

    snc = subparsers.add_parser("sync", help="Pull upstream changes and push local commits")
    snc.add_argument("--merge", action="store_true", help="Use merge pull instead of `pull --rebase`")
    snc.add_argument("--autostash", action="store_true", help="Automatically stash/unstash dirty files during rebase")
    snc.add_argument("-n", "--dry-run", action="store_true", help="Show planned sync steps without running them")
    snc.set_defaults(handler=run_sync)

    pul = subparsers.add_parser("pull", help="Pull updates from remote")
    pul.add_argument("--merge", action="store_true", help="Use merge pull instead of `pull --rebase`")
    pul.add_argument("--autostash", action="store_true", help="Auto-stash local changes before rebase")
    pul.set_defaults(handler=run_pull)

    psh = subparsers.add_parser("push", help="Push local commits (auto-sets upstream on new branches)")
    psh.set_defaults(handler=run_push)


def run_init(args: argparse.Namespace) -> int:
    target = init_repo(Path(args.path) if args.path else None, bare=bool(args.bare))
    print(THEME.success(f"✓ Initialized Git repository in {target}"))
    return 0


def run_clone(args: argparse.Namespace) -> int:
    resolved = clone_repo(
        args.url,
        directory=args.directory,
        branch=args.branch,
        github=bool(args.github),
        gitlab=bool(args.gitlab),
        ssh=bool(args.ssh),
    )
    print(THEME.success(f"✓ Cloned {resolved}"))
    return 0


def run_sync(args: argparse.Namespace) -> int:
    location = discover_repo()
    actions = sync_repo(
        location.root,
        use_merge=bool(args.merge),
        autostash=bool(args.autostash),
        dry_run=bool(args.dry_run),
    )
    if args.dry_run:
        print(THEME.warn("Dry run — planned sync steps:"))
        for step in actions:
            print(f"  {THEME.info('•')} {step}")
        return 0
    print(THEME.success("✓ Sync complete."))
    return 0


def run_pull(args: argparse.Namespace) -> int:
    location = discover_repo()
    pull_repo(location.root, use_merge=bool(args.merge), autostash=bool(args.autostash))
    print(THEME.success("✓ Pull complete."))
    return 0


def run_push(args: argparse.Namespace) -> int:
    location = discover_repo()
    push_repo(location.root)
    print(THEME.success("✓ Push complete."))
    return 0

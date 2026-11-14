"""Top-level CLI parser, subcommand dispatcher, and unified error handler."""

from __future__ import annotations

import argparse
import sys

from simplegit import __version__
from simplegit.commands import auth, branches, extras, save, status_diff, sync, undo, viewer
from simplegit.errors import SimpleGitError
from simplegit.ui.render import render_error
from simplegit.ui.theme import THEME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sgit",
        description="SimpleGit — simplified Git workflows, native .git inspection, and interactive CLI.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"SimpleGit {__version__}")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    save.register(subparsers)
    status_diff.register(subparsers)
    branches.register(subparsers)
    undo.register(subparsers)
    sync.register(subparsers)
    extras.register(subparsers)
    auth.register(subparsers)
    viewer.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.no_color:
        THEME._force_no_color = True

    if not getattr(args, "handler", None):
        parser.print_help()
        return 0

    try:
        return int(args.handler(args))
    except SimpleGitError as exc:
        render_error(exc)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\n" + THEME.muted("Interrupted."), file=sys.stderr)
        return 130

"""Top-level CLI parser, subcommand dispatcher, and unified error handler."""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import NoReturn

from simplegit import __version__
from simplegit.commands import auth, branches, extras, save, status_diff, sync, undo, viewer, workflow
from simplegit.core.runner import find_git_binary
from simplegit.errors import SimpleGitError
from simplegit.ui.render import render_error
from simplegit.ui.theme import THEME


class _SimpleGitArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that formats CLI syntax errors using SimpleGit's error banner."""

    def error(self, message: str) -> NoReturn:
        render_error(
            SimpleGitError(
                message=f"Invalid command usage: {message}",
                hint=f"Run `{self.prog} --help` for usage.",
                exit_code=2,
            )
        )
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = _SimpleGitArgumentParser(
        prog="sgit",
        description="SimpleGit — simplified Git workflows, native .git inspection, and viewer.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"SimpleGit {__version__}")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")
    parser.add_argument("--debug", action="store_true", help="Print full traceback on unexpected errors")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_SimpleGitArgumentParser)
    save.register(subparsers)
    status_diff.register(subparsers)
    branches.register(subparsers)
    undo.register(subparsers)
    sync.register(subparsers)
    extras.register(subparsers)
    auth.register(subparsers)
    viewer.register(subparsers)
    workflow.register(subparsers)
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
        find_git_binary()
        return int(args.handler(args))
    except SimpleGitError as exc:
        render_error(exc)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\n" + THEME.muted("Interrupted."), file=sys.stderr)
        return 130
    except Exception as exc:
        if getattr(args, "debug", False):
            traceback.print_exc()
        render_error(
            SimpleGitError(
                message=f"Unexpected error: {exc}",
                hint="Re-run with `--debug` to see the full traceback.",
            )
        )
        return 1

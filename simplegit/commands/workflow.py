"""Handler for `sgit workflow` — create, edit, list, delete, and run custom workflows."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from simplegit.core.workflows import (
    delete_workflow,
    execute_workflow_step,
    load_workflows,
    save_workflow,
)
from simplegit.errors import SimpleGitError
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "workflow",
        aliases=["wf"],
        help="Create, edit, or run custom saved Git/SimpleGit command workflows",
    )
    parser.add_argument("name", nargs="?", help="Workflow name to run or create")
    parser.add_argument("-e", "--edit", action="store_true", help="Create or edit the named workflow")
    parser.add_argument("-l", "--list", action="store_true", help="List all saved workflows")
    parser.add_argument("-d", "--delete", action="store_true", help="Delete the named workflow")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if args.list or not args.name:
        return _list_workflows()

    name = args.name.strip()
    if args.delete:
        if not delete_workflow(name):
            raise SimpleGitError(f"Workflow '{name}' does not exist.", hint="Run `sgit workflow --list` to see saved workflows.")
        print(THEME.warn(f"✓ Deleted workflow '{name}'."))
        return 0

    workflows = load_workflows()
    if args.edit or name not in workflows:
        return _edit_workflow(name, existing=workflows.get(name))

    return _run_workflow(name, workflows[name])


def _list_workflows() -> int:
    workflows = load_workflows()
    if not workflows:
        print(THEME.muted("No workflows configured yet."))
        print(THEME.info('Create one with: `sgit workflow "my-flow"`'))
        return 0
    print(THEME.bold("Saved Workflows:"))
    for wf_name, steps in workflows.items():
        print(f"  {THEME.accent(wf_name)} ({len(steps)} step(s)):")
        for idx, step in enumerate(steps, start=1):
            print(f"    {THEME.muted(f'{idx}.')} {step}")
    return 0


def _edit_workflow(name: str, existing: list[str] | None = None) -> int:
    print(THEME.bold(f"Editing workflow '{name}'"))
    if existing:
        print(THEME.muted("Current steps:"))
        for idx, step in enumerate(existing, start=1):
            print(f"  {THEME.muted(f'{idx}.')} {step}")
        print()

    commands: list[str] = []
    while True:
        label = "First Git command" if not commands else "Next Git command"
        prompt = f"{THEME.info('>')} {label} or put {THEME.bold('.')} to finish. {THEME.muted('(esc to exit)')} "
        line = _read_editor_line(prompt)
        if line is None:
            print(THEME.warn("\nExited without saving."))
            return 0
        stripped = line.strip()
        if stripped == ".":
            break
        if not stripped:
            continue
        commands.append(stripped)

    if not commands:
        print(THEME.warn("No commands entered — workflow not saved."))
        return 0

    path = save_workflow(name, commands)
    print(THEME.success(f"✓ Saved workflow '{name}' ({len(commands)} command(s))") + THEME.muted(f" -> {path}"))
    return 0


def _run_workflow(name: str, steps: list[str]) -> int:
    print(THEME.bold(f"Running workflow '{name}' ({len(steps)} step(s))..."))
    cwd = Path.cwd()
    for idx, step in enumerate(steps, start=1):
        print(f"{THEME.info(f'[{idx}/{len(steps)}]')} {THEME.muted(step)}")
        try:
            rc = execute_workflow_step(step, cwd=cwd)
        except SimpleGitError as exc:
            exc.message = f"Workflow '{name}' failed at step {idx}/{len(steps)} (`{step}`): {exc.message}"
            raise
        if rc != 0:
            raise SimpleGitError(
                f"Workflow '{name}' stopped at step {idx}/{len(steps)}: `{step}`",
                exit_code=rc,
            )
    print(THEME.success(f"✓ Workflow '{name}' completed."))
    return 0


def _read_editor_line(prompt: str) -> str | None:
    """Read a command line while supporting `Esc` to cancel immediately."""
    sys.stdout.write(prompt)
    sys.stdout.flush()

    if not sys.stdin.isatty():
        raw = sys.stdin.readline()
        if not raw or raw.startswith("\x1b"):
            return None
        return raw.rstrip("\r\n")

    if os.name == "nt":
        import msvcrt

        buf: list[str] = []
        while True:
            ch = msvcrt.getwch()
            if ch == "\x1b":
                return None
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buf)
            if ch in ("\x08", "\x7f"):
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch >= " ":
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()

    import termios
    import tty

    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
    except (termios.error, OSError, ValueError):
        raw = sys.stdin.readline()
        if not raw or raw.startswith("\x1b"):
            return None
        return raw.rstrip("\r\n")

    buf = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                return None
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\r", "\n"):
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return "".join(buf)
            if ch in ("\x7f", "\x08"):
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch >= " ":
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

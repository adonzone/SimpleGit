"""Persistent custom user workflows (`sgit workflow`)."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from simplegit.core.runner import run_git
from simplegit.errors import SimpleGitError


def get_workflows_path() -> Path:
    """Return path to the user's `workflows.json` file."""
    cfg_dir = os.environ.get("SGIT_CONFIG_DIR")
    base = Path(cfg_dir) if cfg_dir else (Path.home() / ".config" / "simplegit")
    return base / "workflows.json"


def load_workflows() -> dict[str, list[str]]:
    """Load saved workflows from disk."""
    path = get_workflows_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimpleGitError(f"Failed to read workflows file: {path}", details=str(exc)) from exc
    if not isinstance(data, dict):
        return {}
    return {str(k): [str(cmd) for cmd in v] for k, v in data.items() if isinstance(v, list)}


def save_workflow(name: str, commands: list[str]) -> Path:
    """Persist a named workflow's command list."""
    cleaned_name = name.strip()
    if not cleaned_name:
        raise SimpleGitError("Workflow name cannot be empty.")
    if not commands:
        raise SimpleGitError("Cannot save an empty workflow.", hint="Add at least one Git or sgit command.")

    workflows = load_workflows()
    workflows[cleaned_name] = commands
    path = get_workflows_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(workflows, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise SimpleGitError(f"Could not save workflows file: {path}", details=str(exc)) from exc
    return path


def delete_workflow(name: str) -> bool:
    """Delete a saved workflow by name; returns True if it existed."""
    workflows = load_workflows()
    if name not in workflows:
        return False
    del workflows[name]
    path = get_workflows_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(workflows, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise SimpleGitError(f"Could not update workflows file: {path}", details=str(exc)) from exc
    return True


def execute_workflow_step(step: str, cwd: Path | None = None) -> int:
    """Execute a single workflow step (`sgit ...`, `git ...`, or bare Git args)."""
    try:
        tokens = shlex.split(step)
    except ValueError as exc:
        raise SimpleGitError(
            f"Invalid command syntax in workflow step: `{step}`",
            hint="Check for unclosed quotes in your workflow command.",
            details=str(exc),
        ) from exc
    if not tokens:
        return 0

    head = tokens[0].lower()
    if head == "sgit":
        if len(tokens) == 1:
            raise SimpleGitError(
                f"Incomplete workflow step: `{step}`",
                hint="Specify a SimpleGit subcommand, e.g. `sgit status` or `sgit save \"wip\"`.",
            )
        from simplegit.cli import main

        return main(tokens[1:])

    git_args = tokens[1:] if head == "git" else tokens
    if not git_args:
        raise SimpleGitError(
            f"Incomplete workflow step: `{step}`",
            hint="Specify a Git subcommand, e.g. `git status`.",
        )
    run_git(git_args, cwd=cwd, interactive=True, stream_output=True)
    return 0

"""Isolated temporary Git repository helpers for SimpleGit tests."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class RepoTestCase(unittest.TestCase):
    """Base TestCase providing isolated temp Git repositories and working directory management."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name).resolve()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def run_raw_git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        )

    def make_repo(self, name: str = "repo", initial_commit: bool = True) -> Path:
        repo = self.tmp_path / name
        repo.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, text=True)
        if res.returncode != 0:
            self.run_raw_git(["init"], cwd=repo)
        self.run_raw_git(["config", "user.name", "SimpleGit Test"], cwd=repo)
        self.run_raw_git(["config", "user.email", "test@simplegit.local"], cwd=repo)
        if initial_commit:
            (repo / "README.md").write_text("hello\n", encoding="utf-8")
            self.run_raw_git(["add", "README.md"], cwd=repo)
            self.run_raw_git(["commit", "-m", "Initial commit"], cwd=repo)
        return repo

    def make_bare_remote(self, name: str = "remote.git") -> Path:
        remote = self.tmp_path / name
        remote.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=remote, capture_output=True, text=True)
        if res.returncode != 0:
            self.run_raw_git(["init", "--bare"], cwd=remote)
        return remote

    @contextmanager
    def chdir(self, path: Path) -> Iterator[None]:
        prev = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(prev)

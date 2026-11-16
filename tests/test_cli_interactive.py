"""Tests for CLI dispatch, colored error rendering, `sgit cli` fallback, and npm shim."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from simplegit.cli import main
from tests.helpers import RepoTestCase


class TestCliAndInteractive(RepoTestCase):
    def test_no_color_error_rendering(self) -> None:
        outside = self.tmp_path / "not_a_repo"
        outside.mkdir()
        stderr = io.StringIO()
        with self.chdir(outside), redirect_stderr(stderr):
            rc = main(["--no-color", "status"])
        self.assertEqual(rc, 1)
        out = stderr.getvalue()
        self.assertIn("ERROR", out)
        self.assertIn("sgit init", out)
        self.assertNotIn("\033[", out)

    def test_missing_git_binary_shows_install_docs(self) -> None:
        stderr = io.StringIO()
        with patch("shutil.which", return_value=None), redirect_stderr(stderr):
            rc = main(["--no-color", "status"])
        self.assertEqual(rc, 1)
        out = stderr.getvalue()
        self.assertIn("not installed", out)
        self.assertIn("https://git-scm.com/downloads", out)
        self.assertIn("https://git-scm.com/doc", out)

    def test_invalid_cli_usage_uses_styled_error_banner(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
            main(["--no-color", "--unknown-flag"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("Invalid command usage", stderr.getvalue())

    def test_invalid_savepoint_index_raises_friendly_error(self) -> None:
        repo = self.make_repo()
        stderr = io.StringIO()
        with self.chdir(repo), redirect_stderr(stderr):
            rc = main(["--no-color", "savepoint", "pop", "not-a-number"])
        self.assertEqual(rc, 1)
        self.assertIn("Invalid savepoint index", stderr.getvalue())

    def test_inspect_command_uses_native_loose_object(self) -> None:
        repo = self.make_repo()
        stdout = io.StringIO()
        with self.chdir(repo), redirect_stdout(stdout):
            rc = main(["--no-color", "inspect", "HEAD"])
        self.assertEqual(rc, 0)
        out = stdout.getvalue()
        self.assertIn("loose", out)
        self.assertIn("Initial commit", out)

    def test_viewer_renders_branches_graph_and_files(self) -> None:
        repo = self.make_repo()
        with self.chdir(repo):
            main(["switch", "-c", "feat/ui"])
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
            main(["save", "Add app"])
            main(["switch", "main"])

        stdout = io.StringIO()
        with self.chdir(repo), redirect_stdout(stdout):
            rc = main(["--no-color", "viewer", "--files"])
        self.assertEqual(rc, 0)
        out = stdout.getvalue()
        self.assertIn("Network Graph", out)
        self.assertIn("[Local]", out)
        self.assertIn("feat/ui", out)
        self.assertIn("+src/app.py", out)
        self.assertIn("README.md", out)

    def test_npm_shim_python_fallback(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        repo_root = Path(__file__).resolve().parent.parent
        shim = repo_root / "packaging" / "npm" / "bin" / "sgit.js"
        env = os.environ.copy()
        env["SGIT_USE_PYTHON"] = "1"
        proc = subprocess.run(
            [node, str(shim), "--version"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("SimpleGit", proc.stdout)

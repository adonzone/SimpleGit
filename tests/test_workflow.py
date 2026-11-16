"""Tests for custom user workflows (`sgit workflow`)."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from simplegit.cli import main
from simplegit.core.operations import get_log, get_repo_state
from simplegit.core.workflows import load_workflows
from tests.helpers import RepoTestCase


class TestWorkflow(RepoTestCase):
    def test_create_and_run_workflow_and_esc_cancel(self) -> None:
        repo = self.make_repo()
        cfg_dir = self.tmp_path / "sgit_cfg"

        with patch.dict(os.environ, {"SGIT_CONFIG_DIR": str(cfg_dir)}):
            # 1. Create workflow interactively using `.` to finish
            fake_create = io.StringIO("git add -A\ngit commit -m \"From workflow\"\n.\n")
            stdout = io.StringIO()
            with patch("sys.stdin", fake_create), redirect_stdout(stdout):
                rc = main(["--no-color", "workflow", "quick-commit"])
            self.assertEqual(rc, 0)
            self.assertIn("First Git command or put . to finish. (esc to exit)", stdout.getvalue())
            self.assertEqual(
                load_workflows()["quick-commit"],
                ["git add -A", 'git commit -m "From workflow"'],
            )

            # 2. Run the saved workflow against a modified repo
            (repo / "README.md").write_text("workflow edit\n", encoding="utf-8")
            with self.chdir(repo):
                rc_run = main(["--no-color", "workflow", "quick-commit"])
            self.assertEqual(rc_run, 0)
            self.assertTrue(get_repo_state(repo).is_clean)
            self.assertEqual(get_log(repo, limit=1)[0].subject, "From workflow")

            # 3. Edit with `-e` and cancel with Esc (`\x1b`) — existing workflow stays intact
            fake_esc = io.StringIO("\x1b\n")
            stdout_esc = io.StringIO()
            with patch("sys.stdin", fake_esc), redirect_stdout(stdout_esc):
                rc_esc = main(["--no-color", "workflow", "-e", "quick-commit"])
            self.assertEqual(rc_esc, 0)
            self.assertIn("Exited without saving", stdout_esc.getvalue())
            self.assertEqual(len(load_workflows()["quick-commit"]), 2)

            # 4. Delete workflow
            rc_del = main(["--no-color", "workflow", "-d", "quick-commit"])
            self.assertEqual(rc_del, 0)
            self.assertEqual(load_workflows(), {})

    def test_workflow_unclosed_quote_shows_friendly_error(self) -> None:
        cfg_dir = self.tmp_path / "sgit_cfg_bad"
        with patch.dict(os.environ, {"SGIT_CONFIG_DIR": str(cfg_dir)}):
            from simplegit.core.workflows import save_workflow

            save_workflow("broken", ['git commit -m "unclosed'])
            import io
            from contextlib import redirect_stderr

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["--no-color", "workflow", "broken"])
            self.assertEqual(rc, 1)
            self.assertIn("Invalid command syntax", stderr.getvalue())

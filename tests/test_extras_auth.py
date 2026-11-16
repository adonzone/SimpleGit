"""Tests for savepoints, remotes, conflicts, ignore, tags, doctor, and auth."""

from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from unittest.mock import patch

from simplegit.cli import main
from simplegit.core.auth import host_for_provider, verify_provider_token
from simplegit.core.extras import (
    add_ignore_patterns,
    add_remote,
    create_tag,
    delete_tag,
    inspect_conflicts,
    list_ignore_patterns,
    list_remotes,
    list_tags,
    resolve_conflicts,
    run_doctor,
    savepoint_drop,
    savepoint_list,
    savepoint_pop,
    savepoint_push,
)
from simplegit.core.operations import get_repo_state, merge_branch, switch_branch
from simplegit.errors import MergeConflictError, SimpleGitError
from tests.helpers import RepoTestCase


class TestExtrasAndAuth(RepoTestCase):
    def test_savepoint_lifecycle_with_untracked(self) -> None:
        repo = self.make_repo()
        (repo / "README.md").write_text("wip edit\n", encoding="utf-8")
        (repo / "temp.txt").write_text("untracked wip\n", encoding="utf-8")

        savepoint_push(repo, "wip feature")
        self.assertTrue(get_repo_state(repo).is_clean)
        items = savepoint_list(repo)
        self.assertEqual(len(items), 1)
        self.assertIn("wip feature", items[0])

        savepoint_pop(repo, index=0)
        self.assertFalse(get_repo_state(repo).is_clean)
        self.assertTrue((repo / "temp.txt").exists())
        self.assertEqual(savepoint_list(repo), [])

        savepoint_push(repo, "drop me")
        savepoint_drop(repo, index=0)
        self.assertEqual(savepoint_list(repo), [])

    def test_remote_add_with_gh_and_gl(self) -> None:
        repo = self.make_repo()
        url_gh = add_remote(repo, "origin", "AdonZ/SimpleGit", github=True)
        url_gl = add_remote(repo, "mirror", "org/proj", gitlab=True, ssh=True)
        self.assertEqual(url_gh, "https://github.com/AdonZ/SimpleGit.git")
        self.assertEqual(url_gl, "git@gitlab.com:org/proj.git")
        self.assertEqual(
            dict(list_remotes(repo)),
            {
                "origin": "https://github.com/AdonZ/SimpleGit.git",
                "mirror": "git@gitlab.com:org/proj.git",
            },
        )

    def test_conflicts_inspect_and_resolve_ours(self) -> None:
        repo = self.make_repo()
        switch_branch(repo, "feat", create=True)
        (repo / "README.md").write_text("feat line\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "feat change"])

        switch_branch(repo, "main")
        (repo / "README.md").write_text("main line\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "main change"])

        with self.assertRaises(MergeConflictError):
            merge_branch(repo, "feat")

        details = inspect_conflicts(repo)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].path, "README.md")
        self.assertTrue(len(details[0].marker_lines) >= 1)

        resolve_conflicts(repo, "ours", ["README.md"])
        self.assertEqual((repo / "README.md").read_text(encoding="utf-8"), "main line\n")
        self.assertEqual(inspect_conflicts(repo), [])

    def test_ignore_patterns_and_template_dedup(self) -> None:
        repo = self.make_repo()
        added1 = add_ignore_patterns(repo, ["*.log", ".env"], template="python")
        self.assertIn("*.log", added1)
        self.assertIn("__pycache__/", added1)

        added2 = add_ignore_patterns(repo, ["*.log", "dist/"])
        self.assertEqual(added2, [])
        self.assertIn(".env", list_ignore_patterns(repo))

    def test_tag_create_list_delete(self) -> None:
        repo = self.make_repo()
        create_tag(repo, "v0.1.0", message="First release")
        self.assertEqual(list_tags(repo), ["v0.1.0"])
        delete_tag(repo, "v0.1.0")
        self.assertEqual(list_tags(repo), [])

    def test_doctor_runs_cleanly(self) -> None:
        repo = self.make_repo()
        checks = run_doctor(repo)
        names = {c.name for c in checks}
        self.assertIn("Git binary", names)
        self.assertIn("Repository state", names)

    def test_auth_host_and_mocked_login_logout(self) -> None:
        self.assertEqual(host_for_provider(github=True), "github.com")
        self.assertEqual(host_for_provider(gitlab=True), "gitlab.com")
        with self.assertRaises(SimpleGitError):
            host_for_provider(github=True, gitlab=True)

        class _FakeResp:
            def __init__(self, body: bytes) -> None:
                self._body = body

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "_FakeResp":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"login": "adonz"}')):
            self.assertEqual(verify_provider_token("github.com", "tok123"), "adonz")

        ok_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="username=adonz\n", stderr="")
        stdout = io.StringIO()
        with (
            patch("simplegit.core.auth.ensure_credential_helper", return_value="osxkeychain"),
            patch("simplegit.core.auth._run_git_credential", return_value=ok_proc) as mock_cred,
            redirect_stdout(stdout),
        ):
            rc = main(["auth", "login", "-gh", "--token", "tok", "-u", "adonz", "--skip-verify"])
            self.assertEqual(rc, 0)
            self.assertIn("@adonz", stdout.getvalue())
            mock_cred.assert_called_once()
            self.assertEqual(mock_cred.call_args[0][0], "approve")

            rc2 = main(["auth", "logout", "-gh"])
            self.assertEqual(rc2, 0)
            self.assertEqual(mock_cred.call_args[0][0], "reject")

"""Integration tests for `init`, `clone`, and `sync` against a local bare remote."""

from __future__ import annotations

from unittest.mock import patch

from simplegit.cli import main
from simplegit.core.operations import get_log, get_repo_state, resolve_clone_url, sync_repo
from simplegit.errors import SimpleGitError
from tests.helpers import RepoTestCase


class TestSyncAndInit(RepoTestCase):
    def test_init_creates_repo_on_main(self) -> None:
        target = self.tmp_path / "fresh"
        rc = main(["init", str(target)])
        self.assertEqual(rc, 0)
        self.assertTrue((target / ".git" / "HEAD").is_file())

    def test_sync_sets_upstream_and_pulls_remote_changes(self) -> None:
        remote = self.make_bare_remote()
        repo_a = self.make_repo("repo_a")
        self.run_raw_git(["remote", "add", "origin", str(remote)], cwd=repo_a)

        # First sync publishes branch and sets upstream automatically.
        sync_repo(repo_a)
        state_a = get_repo_state(repo_a)
        self.assertEqual(state_a.upstream, "origin/main")

        # Clone into repo_b using `sgit clone`
        repo_b = self.tmp_path / "repo_b"
        self.assertEqual(main(["clone", str(remote), str(repo_b)]), 0)
        self.run_raw_git(["config", "user.name", "Peer"], cwd=repo_b)
        self.run_raw_git(["config", "user.email", "peer@simplegit.local"], cwd=repo_b)

        (repo_b / "peer.txt").write_text("from peer\n", encoding="utf-8")
        with self.chdir(repo_b):
            self.assertEqual(main(["save", "--push", "Peer commit"]), 0)

        # Now repo_a creates a local commit and runs `sgit sync` (rebases over peer commit + pushes).
        (repo_a / "local.txt").write_text("from local\n", encoding="utf-8")
        with self.chdir(repo_a):
            self.assertEqual(main(["save", "Local commit"]), 0)
            self.assertEqual(main(["sync"]), 0)

        subjects = [c.subject for c in get_log(repo_a, limit=10)]
        self.assertIn("Peer commit", subjects)
        self.assertIn("Local commit", subjects)

    def test_resolve_clone_url_variants(self) -> None:
        self.assertEqual(
            resolve_clone_url("AdonZ/SimpleGit", github=True),
            "https://github.com/AdonZ/SimpleGit.git",
        )
        self.assertEqual(
            resolve_clone_url("AdonZ/SimpleGit.git", github=True, ssh=True),
            "git@github.com:AdonZ/SimpleGit.git",
        )
        self.assertEqual(
            resolve_clone_url("group/sub/app", gitlab=True),
            "https://gitlab.com/group/sub/app.git",
        )
        self.assertEqual(
            resolve_clone_url("git.example.com/team/repo"),
            "https://git.example.com/team/repo.git",
        )
        self.assertEqual(
            resolve_clone_url("https://git.example.com/team/repo.git"),
            "https://git.example.com/team/repo.git",
        )
        bare = self.make_bare_remote("hosted.git")
        self.assertEqual(resolve_clone_url(str(bare)), str(bare))

        with self.assertRaises(SimpleGitError):
            resolve_clone_url("owner/repo")

    def test_cli_clone_gh_and_gl_flags(self) -> None:
        with patch("simplegit.commands.sync.clone_repo", return_value="https://github.com/AdonZ/SimpleGit.git") as mock_clone:
            rc = main(["clone", "-gh", "AdonZ/SimpleGit", "my-dir"])
        self.assertEqual(rc, 0)
        mock_clone.assert_called_once_with(
            "AdonZ/SimpleGit",
            directory="my-dir",
            branch=None,
            github=True,
            gitlab=False,
            ssh=False,
        )

        with patch("simplegit.commands.sync.clone_repo", return_value="https://gitlab.com/org/proj.git") as mock_clone:
            rc = main(["clone", "-gl", "--ssh", "org/proj"])
        self.assertEqual(rc, 0)
        mock_clone.assert_called_once_with(
            "org/proj",
            directory=None,
            branch=None,
            github=False,
            gitlab=True,
            ssh=True,
        )

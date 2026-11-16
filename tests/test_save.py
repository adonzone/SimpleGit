"""Integration tests for `sgit save` diff-based staging and commit workflows."""

from __future__ import annotations

from simplegit.cli import main
from simplegit.core.operations import collect_save_candidates, execute_save, get_log, get_repo_state
from simplegit.errors import NothingToCommitError
from tests.helpers import RepoTestCase


class TestSave(RepoTestCase):
    def test_save_discovers_diff_and_untracked_files(self) -> None:
        repo = self.make_repo()
        (repo / "README.md").write_text("updated\n", encoding="utf-8")
        (repo / "my notes.txt").write_text("new file with spaces\n", encoding="utf-8")

        plan = collect_save_candidates(repo, tracked_only=False)
        self.assertIn("README.md", plan.tracked_diff_files)
        self.assertIn("my notes.txt", plan.untracked_files)

        sha, committed = execute_save(plan, message="Save both")
        self.assertNotEqual(sha, "dry-run")
        self.assertEqual(set(committed), {"README.md", "my notes.txt"})
        self.assertTrue(get_repo_state(repo).is_clean)

    def test_save_tracked_only_skips_untracked(self) -> None:
        repo = self.make_repo()
        (repo / "README.md").write_text("updated\n", encoding="utf-8")
        (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")

        with self.chdir(repo):
            rc = main(["save", "-t", "Only tracked"])
        self.assertEqual(rc, 0)

        state = get_repo_state(repo)
        self.assertEqual([f.path for f in state.untracked_files], ["scratch.txt"])
        self.assertEqual(get_log(repo, limit=1)[0].subject, "Only tracked")

    def test_save_dry_run_does_not_commit(self) -> None:
        repo = self.make_repo()
        (repo / "README.md").write_text("edited\n", encoding="utf-8")

        with self.chdir(repo):
            rc = main(["save", "--dry-run", "Preview commit"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(get_log(repo, limit=10)), 1)
        self.assertFalse(get_repo_state(repo).is_clean)

    def test_save_with_m_flag_and_file_scope(self) -> None:
        repo = self.make_repo()
        (repo / "a.txt").write_text("A\n", encoding="utf-8")
        (repo / "b.txt").write_text("B\n", encoding="utf-8")

        with self.chdir(repo):
            rc = main(["save", "-m", "Only A", "a.txt"])
        self.assertEqual(rc, 0)

        state = get_repo_state(repo)
        self.assertEqual([f.path for f in state.untracked_files], ["b.txt"])

    def test_save_clean_tree_raises_nothing_to_commit(self) -> None:
        repo = self.make_repo()
        plan = collect_save_candidates(repo)
        with self.assertRaises(NothingToCommitError):
            execute_save(plan, message="Empty")

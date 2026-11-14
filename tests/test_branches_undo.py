"""Integration tests for branch, switch, merge, conflicts, and undo workflows."""

from __future__ import annotations

from simplegit.cli import main
from simplegit.core.operations import (
    get_log,
    get_repo_state,
    list_branches,
    merge_branch,
    switch_branch,
    undo_changes,
    undo_commit,
    undo_stage,
)
from simplegit.errors import MergeConflictError
from tests.helpers import RepoTestCase


class TestBranchesAndUndo(RepoTestCase):
    def test_switch_create_and_merge(self) -> None:
        repo = self.make_repo()
        switch_branch(repo, "feat/demo", create=True)
        (repo / "feature.txt").write_text("feat\n", encoding="utf-8")
        with self.chdir(repo):
            self.assertEqual(main(["save", "Add feature"]), 0)

        switch_branch(repo, "main")
        merge_branch(repo, "feat/demo")
        self.assertTrue((repo / "feature.txt").exists())
        names = [b.name for b in list_branches(repo)]
        self.assertIn("feat/demo", names)

    def test_merge_conflict_raises_structured_error_and_aborts(self) -> None:
        repo = self.make_repo()
        switch_branch(repo, "branch-a", create=True)
        (repo / "README.md").write_text("from A\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "Edit on A"])

        switch_branch(repo, "main")
        (repo / "README.md").write_text("from main\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "Edit on main"])

        with self.assertRaises(MergeConflictError) as ctx:
            merge_branch(repo, "branch-a")
        self.assertIn("README.md", ctx.exception.affected_files)
        self.assertEqual(get_repo_state(repo).active_op, "MERGING")

        merge_branch(repo, abort=True)
        self.assertIsNone(get_repo_state(repo).active_op)

    def test_undo_commit_stage_and_changes(self) -> None:
        repo = self.make_repo()
        (repo / "README.md").write_text("v2\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "Second commit"])
        self.assertEqual(len(get_log(repo, limit=10)), 2)

        undo_commit(repo)
        self.assertEqual(len(get_log(repo, limit=10)), 1)
        self.assertEqual(len(get_repo_state(repo).staged_files), 1)

        undo_stage(repo)
        state = get_repo_state(repo)
        self.assertEqual(len(state.staged_files), 0)
        self.assertEqual(len(state.unstaged_files), 1)

        undo_changes(repo)
        self.assertTrue(get_repo_state(repo).is_clean)
        self.assertEqual((repo / "README.md").read_text(encoding="utf-8"), "hello\n")

    def test_undo_root_commit_edge_case(self) -> None:
        repo = self.make_repo(initial_commit=False)
        (repo / "init.txt").write_text("root\n", encoding="utf-8")
        with self.chdir(repo):
            main(["save", "Root commit"])
        self.assertEqual(len(get_log(repo, limit=10)), 1)

        msg = undo_commit(repo)
        self.assertIn("initial commit", msg.lower())
        self.assertEqual(len(get_log(repo, limit=10)), 0)
        self.assertEqual(len(get_repo_state(repo).staged_files), 1)

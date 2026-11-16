"""Tests for Git stderr-to-friendly-error translation."""

from __future__ import annotations

import unittest

from simplegit.errors import (
    CommandFailedError,
    DirtyWorktreeError,
    InvalidRefError,
    MergeConflictError,
    NotARepoError,
    NothingToCommitError,
    PushRejectedError,
    UpstreamMissingError,
    translate_git_error,
)


class TestRunnerErrors(unittest.TestCase):
    def test_not_a_repo(self) -> None:
        err = translate_git_error(["status"], 128, "fatal: not a git repository (or any of the parent directories): .git")
        self.assertIsInstance(err, NotARepoError)
        self.assertIn("sgit init", err.hint or "")

    def test_merge_conflict_extracts_files(self) -> None:
        stderr = (
            "Auto-merging app.py\n"
            "CONFLICT (content): Merge conflict in app.py\n"
            "CONFLICT (content): Merge conflict in README.md\n"
            "Automatic merge failed; fix conflicts and then commit the result.\n"
        )
        err = translate_git_error(["merge", "feat"], 1, stderr)
        self.assertIsInstance(err, MergeConflictError)
        self.assertEqual(err.affected_files, ["app.py", "README.md"])

    def test_dirty_worktree_extracts_overwritten_files(self) -> None:
        stderr = (
            "error: Your local changes to the following files would be overwritten by checkout:\n"
            "\tsrc/main.py\n"
            "\tREADME.md\n"
            "Please commit your changes or stash them before you switch branches.\n"
        )
        err = translate_git_error(["switch", "other"], 1, stderr)
        self.assertIsInstance(err, DirtyWorktreeError)
        self.assertEqual(err.affected_files, ["src/main.py", "README.md"])

    def test_nothing_to_commit(self) -> None:
        err = translate_git_error(["commit", "-m", "x"], 1, "", "nothing to commit, working tree clean")
        self.assertIsInstance(err, NothingToCommitError)

    def test_upstream_missing(self) -> None:
        err = translate_git_error(["push"], 128, "fatal: The current branch feat has no upstream branch.")
        self.assertIsInstance(err, UpstreamMissingError)

    def test_push_rejected(self) -> None:
        err = translate_git_error(["push"], 1, "! [rejected] main -> main (non-fast-forward)")
        self.assertIsInstance(err, PushRejectedError)

    def test_invalid_ref(self) -> None:
        err = translate_git_error(["switch", "nope"], 128, "fatal: invalid reference: nope")
        self.assertIsInstance(err, InvalidRefError)

    def test_unknown_error_fallback(self) -> None:
        err = translate_git_error(["weird"], 2, "fatal: unexpected failure")
        self.assertIsInstance(err, CommandFailedError)
        self.assertEqual(err.message, "fatal: unexpected failure")

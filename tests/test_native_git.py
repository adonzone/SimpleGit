"""Unit tests for pure-Python `.git` inspection in `simplegit.core.native_git`."""

from __future__ import annotations

from simplegit.core.native_git import (
    compute_object_hash,
    detect_active_operation,
    discover_repo,
    parse_commit_object,
    parse_tree_object,
    read_head,
    read_loose_object,
)
from simplegit.errors import NotARepoError
from tests.helpers import RepoTestCase


class TestNativeGit(RepoTestCase):
    def test_discover_repo_from_subdirectory(self) -> None:
        repo = self.make_repo()
        nested = repo / "src" / "pkg"
        nested.mkdir(parents=True)

        loc = discover_repo(nested)
        self.assertEqual(loc.root, repo)
        self.assertEqual(loc.git_dir, repo / ".git")
        self.assertFalse(loc.is_bare)

    def test_discover_repo_outside_git_raises(self) -> None:
        outside = self.tmp_path / "plain_dir"
        outside.mkdir()
        with self.assertRaises(NotARepoError):
            discover_repo(outside)

    def test_read_head_and_packed_refs(self) -> None:
        repo = self.make_repo()
        loc = discover_repo(repo)
        branch, sha, detached = read_head(loc)
        self.assertEqual(branch, "main")
        self.assertIsNotNone(sha)
        self.assertFalse(detached)

        # Pack refs and verify packed-refs resolution still finds HEAD SHA.
        self.run_raw_git(["pack-refs", "--all"], cwd=repo)
        branch2, sha2, detached2 = read_head(loc)
        self.assertEqual(branch2, "main")
        self.assertEqual(sha2, sha)
        self.assertFalse(detached2)

    def test_detect_active_operation_sentinels(self) -> None:
        repo = self.make_repo()
        git_dir = repo / ".git"
        self.assertIsNone(detect_active_operation(git_dir))
        (git_dir / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
        self.assertEqual(detect_active_operation(git_dir), "MERGING")

    def test_compute_hash_and_read_loose_commit_and_tree(self) -> None:
        repo = self.make_repo()
        loc = discover_repo(repo)
        _, head_sha, _ = read_head(loc)
        assert head_sha is not None

        # Verify SHA-1 helper matches `git hash-object`.
        import subprocess

        blob_bytes = b"hello world\n"
        proc = subprocess.run(
            ["git", "hash-object", "--stdin"],
            input=blob_bytes,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            compute_object_hash("blob", blob_bytes),
            proc.stdout.decode().strip(),
        )

        commit_obj = read_loose_object(loc.common_dir, head_sha[:10])
        self.assertIsNotNone(commit_obj)
        assert commit_obj is not None
        self.assertEqual(commit_obj.kind, "commit")
        self.assertEqual(commit_obj.source, "loose")

        parsed_commit = parse_commit_object(commit_obj.content)
        self.assertIn("Initial commit", parsed_commit["message"])

        tree_obj = read_loose_object(loc.common_dir, parsed_commit["tree"])
        self.assertIsNotNone(tree_obj)
        assert tree_obj is not None
        entries = parse_tree_object(tree_obj.content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "README.md")

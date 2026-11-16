# SimpleGit (`sgit`) Roadmap

A cross-platform, simplified Git CLI licensed under GNU GPLv3 (see [LICENSE](LICENSE)) that combines a native `.git` inspector with safe `git` subprocess execution, one-shot workflows, high-visibility colored error diagnostics, and a rich interactive terminal mode (`sgit cli`).

---

## Architecture Overview

- **Hybrid `.git` Engine**:
  - **Native `.git` Inspector (`simplegit/core/native_git.py`)**: pure Python 3.10+ standard library (`pathlib`, `zlib`, `hashlib`) for repository/worktree discovery, `HEAD`/refs/`packed-refs` resolution, in-progress operation detection (`MERGE_HEAD`, `REBASE_*`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`), and loose `.git/objects` decompression and SHA-1 verification.
  - **System `git` Runner (`simplegit/core/runner.py`)**: safe `subprocess` execution with NUL-delimited (`-z`) porcelain parsing for index mutations, diffs, merges, hooks, signing, and remote transport (`clone`, `fetch`, `pull`, `push`).
- **Zero Third-Party Runtime Dependencies**:
  - Only Python 3.10+ stdlib and the system `git` binary (>= 2.23) are required at runtime.
- **Multi-Package-Manager Distribution**:
  - PyPI / `pipx` / `uv` (`pyproject.toml`), portable `sgit.pyz` zipapp, Homebrew (`simplegit.rb`), npm (`sgit-cli`), Chocolatey (`simplegit.nuspec`), Scoop, Winget, and GitHub Actions standalone binaries.

---

## Phase 1: Foundation, UI & Error Diagnostics

- [x] Set up `pyproject.toml` (`sgit` console entrypoint, GPL-3.0-or-later, zero runtime dependencies) and `bin/sgit` launcher
- [x] Implement `simplegit/errors.py` (`SimpleGitError` hierarchy and `translate_git_error()` stderr-to-hint translator)
- [x] Implement `simplegit/ui/theme.py` (cross-platform ANSI colors, `NO_COLOR`/`FORCE_COLOR`, Windows VT100 enabling)
- [x] Implement `simplegit/ui/render.py` (bold red `✗ ERROR:` banners, grouped status, colored diffs, commit logs, object views)
- [x] Implement `simplegit/ui/terminal.py` (POSIX `termios`/`tty` and Windows `msvcrt` raw key reader with non-TTY fallback)

---

## Phase 2: Hybrid `.git` Core Engine

- [x] Implement `simplegit/core/models.py` (`RepoLocation`, `FileChange`, `RepoState`, `BranchInfo`, `CommitInfo`, `GitObject`, `SavePlan`)
- [x] Implement `simplegit/core/native_git.py` (`.git` discovery, `HEAD`/`packed-refs`, merge/rebase state detection, `zlib` loose object reader, commit/tree parsers)
- [x] Implement `simplegit/core/runner.py` (`git` binary/version probe, `-z` NUL-delimited porcelain parser, error translation)
- [x] Implement `simplegit/core/operations.py` (composed workflows for status, diff-based save staging, branches, merge, undo, sync, and native object inspection)

---

## Phase 3: One-Shot CLI Commands & Rich Interactive Mode

- [x] Implement `simplegit/cli.py` and `simplegit/__main__.py` (`argparse` dispatcher, `--version`, `--no-color`, unified error handler)
- [x] `sgit save "msg" [files...]` — instant `git diff` + untracked discovery, staging, commit, `--tracked`/`-t`, `--push`/`-p`, `--amend`, `--dry-run`
- [x] `sgit status` (`st`), `sgit diff`, `sgit log`, `sgit inspect <rev|sha>`
- [x] `sgit branch` (`br`), `sgit switch` (`sw`, `-c/--create`), `sgit merge` (`--abort`, `--continue`)
- [x] `sgit undo` — `commit` (soft reset), `stage` (unstage), `changes` (restore with confirmation or `-y/--yes`)
- [x] `sgit init`, `sgit clone`, `sgit sync` (`pull --rebase` default + `--merge` + `--autostash` + auto `-u` push), `sgit pull`, `sgit push`
- [x] `sgit cli` — interactive terminal dashboard with live repo header, file multi-select for save, inline diff viewer, branch switcher, commit/object browser, undo wizard, and sync

---

## Phase 4: Cross-Platform Packaging & CI/CD

- [x] `scripts/build_zipapp.py` — single-file portable `dist/sgit.pyz` builder
- [x] `packaging/homebrew/simplegit.rb` — Homebrew formula (`depends_on "git"`, `depends_on "python@3.12"`)
- [x] `packaging/npm/` (`sgit-cli`) — `package.json`, `bin/sgit.js`, `scripts/postinstall.js` (checksum-verified binary download + Python fallback)
- [x] `packaging/choco/` — `simplegit.nuspec`, `chocolateyinstall.ps1`, `chocolateyuninstall.ps1`
- [x] `packaging/scoop/simplegit.json` and `packaging/winget/AdonaiAfewerki.SimpleGit.yaml`
- [x] `.github/workflows/ci.yml` — cross-platform `unittest` matrix (`ubuntu-latest`, `macos-latest`, `windows-latest`)
- [x] `.github/workflows/release.yml` — tagged release builds (PyInstaller standalone binaries, `SHA256SUMS.txt`, wheels/sdist, `.nupkg`)
- [x] Update `README.md` with installation and usage documentation

---

## Phase 5: Verification

- [x] Unit tests for native `.git` discovery, refs, and loose `zlib` object parsing (`tests/test_native_git.py`)
- [x] Error translation tests (`tests/test_runner_errors.py`)
- [x] Integration tests for `save`, `branch`/`switch`/`merge`/`undo`, and `init`/`clone`/`sync` (`tests/test_save.py`, `tests/test_branches_undo.py`, `tests/test_sync_init.py`)
- [x] CLI & interactive non-TTY fallback tests plus npm launcher validation (`tests/test_cli_interactive.py`)
- [x] Local end-to-end verification (`unittest`, `sgit.pyz`, `npm pack --dry-run`)

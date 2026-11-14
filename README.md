# SimpleGit (`sgit`)

A simplified, cross-platform Git CLI that combines a **native `.git` inspector** (pure Python stdlib) with **system `git` execution**, one-shot workflows, high-visibility colored error diagnostics, and a rich interactive terminal mode (`sgit cli`).

## Features

- **One-shot `sgit save "message"`**: Automatically discovers changed files from `git diff` (plus new untracked files unless `--tracked` is passed), stages them, and commits in a single command. Add `--push` (`-p`) to push right away, or `--dry-run` (`-n`) to preview.
- **Rich Interactive Mode (`sgit cli`)**: Keyboard-driven terminal dashboard for reviewing status/diffs, toggling files to save, switching/creating/merging branches, browsing commit history, undoing mistakes, and syncing.
- **Native `.git` Inspection (`sgit inspect`)**: Reads `.git/HEAD`, refs, `packed-refs`, operation sentinels (`MERGE_HEAD`, `REBASE_MERGE`, etc.), and loose `zlib` objects directly via Python stdlib (with `git cat-file` fallback for packfiles).
- **Clear Colored Error Banners**: Translates cryptic Git errors (conflicts, dirty worktrees, non-fast-forward rejections, missing upstream) into readable red `[ERROR]` banners with affected files and copy-pasteable `sgit` recovery hints.
- **Zero Third-Party Runtime Dependencies**: Requires only `git` (>= 2.23) and Python 3.10+ (or prebuilt release binaries).

## Installation

### From Source (Development)

```bash
pip install -e .
# or run directly without installing:
./bin/sgit --help
```

### Portable Single-File Executable (`sgit.pyz`)

```bash
python3 scripts/build_zipapp.py
python3 dist/sgit.pyz --help
```

### Package Manager Manifests (in `packaging/`)

- **Homebrew**: `packaging/homebrew/simplegit.rb`
- **npm (`sgit-cli`)**: `packaging/npm/` (installs `sgit` globally with SHA-256 verified release binary or Python fallback)
- **Chocolatey**: `packaging/choco/` (`simplegit.nuspec`)
- **Scoop / Winget**: `packaging/scoop/simplegit.json`, `packaging/winget/AdonaiAfewerki.SimpleGit.yaml`

## Quickstart

```bash
sgit status                       # Grouped colored status + next-step tip
sgit save "Add login validation"  # Diff-discover + stage + commit in one command
sgit save -t "Tracked only"       # Stage only tracked files found in git diff
sgit save -p "Update docs"        # Save and push immediately
sgit switch -c feat/auth          # Create and switch to a new branch
sgit clone -gh AdonZ/SimpleGit     # Clone from GitHub (or -gl for GitLab)
sgit clone /path/to/repo.git      # Or clone any .git URL / local .git directory
sgit sync                         # Pull (--rebase) and push (auto-sets upstream)
sgit undo commit                  # Safely undo last commit, keeping edits staged
sgit undo stage                   # Unstage files without losing edits
sgit inspect HEAD                 # Inspect commit object directly from .git/objects
sgit savepoint "wip login"        # Temporary savepoint (includes untracked files)
sgit remote add origin -gh u/repo # Link remote using -gh / -gl shorthand
sgit auth login -gh               # Authenticate with GitHub (or -gl for GitLab)
sgit conflicts                    # Inspect & resolve merge conflicts (--ours/--theirs)
sgit ignore --template python     # Add starter .gitignore patterns cleanly
sgit tag v0.1.0 --push            # Create and push a release tag
sgit doctor                       # Check Git, identity, auth, and repo health
sgit viewer --files               # Visual graph of branches, commits, and files
```

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

Copyright (c) 2026 Adonai Afewerki. Licensed under the [GNU GPLv3](LICENSE).

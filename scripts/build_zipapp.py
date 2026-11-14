#!/usr/bin/env python3
"""Build a single-file portable `dist/sgit.pyz` zipapp using Python stdlib."""

from __future__ import annotations

import shutil
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PKG = ROOT / "simplegit"
DIST_DIR = ROOT / "dist"
OUT_FILE = DIST_DIR / "sgit.pyz"


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        stage = Path(tmpdir) / "app"
        stage.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SRC_PKG,
            stage / "simplegit",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        zipapp.create_archive(
            stage,
            target=OUT_FILE,
            interpreter="/usr/bin/env python3",
            main="simplegit.cli:main",
            compressed=True,
        )
    print(f"Built portable zipapp: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

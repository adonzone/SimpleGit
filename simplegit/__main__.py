"""Allow running SimpleGit via `python3 -m simplegit`."""

from __future__ import annotations

from simplegit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

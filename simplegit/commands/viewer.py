"""Handler for `sgit viewer` — GitHub Insights/Network-style graph (Local & Hosted)."""

from __future__ import annotations

import argparse

from simplegit.core.operations import get_network_graph, get_repo_state, list_tracked_files
from simplegit.ui.render import render_viewer


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "viewer",
        aliases=["view", "network"],
        help="Show a GitHub Insights/Network-style graph (X=Time, Y=Branches) across Local & Hosted",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=14,
        help="Max commits to plot along the timeline (default: 14)",
    )
    parser.add_argument("--all-commits", action="store_true", help="Plot all commits without a limit")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--local", action="store_true", help="Show Local branches only")
    scope.add_argument("--hosted", action="store_true", help="Show Hosted remote branches only")
    parser.add_argument("--fetch", action="store_true", help="Fetch remote refs before rendering")
    parser.add_argument("--files", action="store_true", help="Also display the repository file tree")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    state = get_repo_state()
    limit = 0 if args.all_commits else max(1, args.limit)
    graph = get_network_graph(
        state.location.root,
        limit=limit,
        include_local=not bool(args.hosted),
        include_hosted=not bool(args.local),
        fetch_remote=bool(args.fetch),
    )
    tracked_files = list_tracked_files(state.location.root) if args.files else None
    render_viewer(state, graph, tracked_files=tracked_files)
    return 0

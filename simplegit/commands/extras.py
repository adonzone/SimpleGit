"""Handlers for `savepoint`, `remote`, `conflicts`, `ignore`, `tag`, and `doctor`."""

from __future__ import annotations

import argparse

from simplegit.core.extras import (
    add_ignore_patterns,
    add_remote,
    create_tag,
    delete_tag,
    inspect_conflicts,
    list_ignore_patterns,
    list_remotes,
    list_tags,
    remove_remote,
    resolve_conflicts,
    run_doctor,
    savepoint_drop,
    savepoint_list,
    savepoint_pop,
    savepoint_push,
    set_remote_url,
)
from simplegit.core.native_git import discover_repo
from simplegit.errors import SimpleGitError
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    sp = subparsers.add_parser(
        "savepoint",
        aliases=["sp"],
        help="Manage temporary savepoints (clearer alternative to `git stash`)",
    )
    sp.add_argument(
        "action",
        nargs="?",
        default="list",
        help="Message to save, or sub-action: `list`, `pop`, `apply`, `drop`",
    )
    sp.add_argument("target", nargs="?", help="Message (with `push`) or numeric index (with `pop`/`apply`/`drop`)")
    sp.set_defaults(handler=run_savepoint)

    rem = subparsers.add_parser("remote", help="List, add, or update remotes (supports -gh / -gl)")
    rem_sub = rem.add_subparsers(dest="remote_action", metavar="<action>")

    rem_add = rem_sub.add_parser("add", help="Add a remote")
    rem_add.add_argument("name", help="Remote name (e.g. origin)")
    rem_add.add_argument("url", help="Repository shorthand (with -gh/-gl), URL, or `.git` path")
    _add_host_flags(rem_add)
    rem_add.set_defaults(handler=run_remote_add)

    rem_set = rem_sub.add_parser("set-url", help="Update a remote URL")
    rem_set.add_argument("name", help="Remote name")
    rem_set.add_argument("url", help="New URL or shorthand")
    _add_host_flags(rem_set)
    rem_set.set_defaults(handler=run_remote_set_url)

    rem_rm = rem_sub.add_parser("remove", aliases=["rm"], help="Remove a remote")
    rem_rm.add_argument("name", help="Remote name")
    rem_rm.set_defaults(handler=run_remote_remove)

    rem.set_defaults(handler=run_remote_list)

    conf = subparsers.add_parser("conflicts", help="Inspect or resolve merge conflicts")
    side = conf.add_mutually_exclusive_group()
    side.add_argument("--ours", action="store_true", help="Keep our branch's version for given files")
    side.add_argument("--theirs", action="store_true", help="Keep incoming branch's version for given files")
    conf.add_argument("files", nargs="*", help="Files to resolve when using --ours or --theirs")
    conf.set_defaults(handler=run_conflicts)

    ign = subparsers.add_parser("ignore", help="Add patterns or starter templates to .gitignore")
    ign.add_argument("patterns", nargs="*", help="Patterns to add (e.g. '*.log' .env)")
    ign.add_argument("-t", "--template", help="Starter template: python, node, macos, general")
    ign.add_argument("-l", "--list", action="store_true", help="List current .gitignore patterns")
    ign.set_defaults(handler=run_ignore)

    tg = subparsers.add_parser("tag", help="List, create (+ optionally push), or delete tags")
    tg.add_argument("name", nargs="?", help="Tag name (omit to list tags)")
    tg.add_argument("-m", "--message", help="Annotated tag message")
    tg.add_argument("-p", "--push", action="store_true", help="Push tag to origin after creating")
    tg.add_argument("-d", "--delete", action="store_true", help="Delete the named tag")
    tg.add_argument("--remote", action="store_true", help="Also delete tag on origin when using -d")
    tg.set_defaults(handler=run_tag)

    doc = subparsers.add_parser("doctor", help="Check Git, identity, auth, and repository health")
    doc.set_defaults(handler=run_doctor_cmd)


def _add_host_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-gh", "--github", action="store_true", help="Expand `owner/repo` as GitHub")
    group.add_argument("-gl", "--gitlab", action="store_true", help="Expand `group/repo` as GitLab")
    parser.add_argument("--ssh", action="store_true", help="Use SSH (`git@host:...`) instead of HTTPS")


def _parse_savepoint_index(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        idx = int(raw)
    except ValueError as exc:
        raise SimpleGitError(
            f"Invalid savepoint index '{raw}'.",
            hint="Use a non-negative number from `sgit savepoint list` (e.g. `sgit savepoint pop 0`).",
        ) from exc
    if idx < 0:
        raise SimpleGitError("Savepoint index cannot be negative.")
    return idx


def run_savepoint(args: argparse.Namespace) -> int:
    location = discover_repo()
    action = args.action
    if action == "list":
        items = savepoint_list(location.root)
        if not items:
            print(THEME.muted("No savepoints found."))
            return 0
        for item in items:
            print(f"  {THEME.info('•')} {item}")
        return 0

    if action in ("pop", "apply"):
        idx = _parse_savepoint_index(args.target)
        out = savepoint_pop(location.root, index=idx, keep=(action == "apply"))
        if out:
            print(out)
        print(THEME.success(f"✓ Restored savepoint @{{{idx}}}."))
        return 0

    if action == "drop":
        idx = _parse_savepoint_index(args.target)
        savepoint_drop(location.root, index=idx)
        print(THEME.warn(f"✓ Dropped savepoint @{{{idx}}}."))
        return 0

    message = args.target if action == "push" else action
    out = savepoint_push(location.root, message=message)
    print(THEME.success("✓ Created savepoint.") + (f" ({out})" if out else ""))
    return 0


def run_remote_list(_args: argparse.Namespace) -> int:
    location = discover_repo()
    remotes = list_remotes(location.root)
    if not remotes:
        print(THEME.muted("No remotes configured."))
        return 0
    for name, url in remotes:
        print(f"  {THEME.accent(name)} -> {url}")
    return 0


def run_remote_add(args: argparse.Namespace) -> int:
    location = discover_repo()
    url = add_remote(
        location.root,
        args.name,
        args.url,
        github=bool(args.github),
        gitlab=bool(args.gitlab),
        ssh=bool(args.ssh),
    )
    print(THEME.success(f"✓ Added remote '{args.name}' -> {url}"))
    return 0


def run_remote_set_url(args: argparse.Namespace) -> int:
    location = discover_repo()
    url = set_remote_url(
        location.root,
        args.name,
        args.url,
        github=bool(args.github),
        gitlab=bool(args.gitlab),
        ssh=bool(args.ssh),
    )
    print(THEME.success(f"✓ Updated remote '{args.name}' -> {url}"))
    return 0


def run_remote_remove(args: argparse.Namespace) -> int:
    location = discover_repo()
    remove_remote(location.root, args.name)
    print(THEME.warn(f"✓ Removed remote '{args.name}'."))
    return 0


def run_conflicts(args: argparse.Namespace) -> int:
    location = discover_repo()
    if args.ours or args.theirs:
        side = "ours" if args.ours else "theirs"
        resolve_conflicts(location.root, side, args.files)
        print(THEME.success(f"✓ Resolved {', '.join(args.files)} using `{side}` and staged."))
        print(THEME.muted('Next: run `sgit merge --continue` or `sgit save "resolve conflicts"`.'))
        return 0

    details = inspect_conflicts(location.root)
    if not details:
        print(THEME.success("✓ No merge conflicts in working tree."))
        return 0

    print(THEME.error(f"Found {len(details)} conflicted file(s):"))
    for item in details:
        lines_str = (
            f"markers at line(s) {', '.join(map(str, item.marker_lines))}"
            if item.marker_lines
            else "binary/tree conflict"
        )
        print(f"  {THEME.error('!')} {THEME.bold(item.path)} ({THEME.muted(lines_str)})")
    print(THEME.info('\nTip: edit files or run `sgit conflicts --ours <file>` / `--theirs <file>`.'))
    return 0


def run_ignore(args: argparse.Namespace) -> int:
    location = discover_repo()
    if args.list:
        patterns = list_ignore_patterns(location.root)
        if not patterns:
            print(THEME.muted(".gitignore has no patterns yet."))
            return 0
        for pat in patterns:
            print(f"  {pat}")
        return 0

    added = add_ignore_patterns(location.root, args.patterns, template=args.template)
    if not added:
        print(THEME.muted("All specified patterns are already in .gitignore."))
        return 0
    print(THEME.success(f"✓ Added {len(added)} pattern(s) to .gitignore:"))
    for pat in added:
        print(f"  {THEME.info('+')} {pat}")
    return 0


def run_tag(args: argparse.Namespace) -> int:
    location = discover_repo()
    if not args.name:
        tags = list_tags(location.root)
        if not tags:
            print(THEME.muted("No tags found."))
            return 0
        for tag in tags:
            print(f"  {THEME.accent(tag)}")
        return 0

    if args.delete:
        delete_tag(location.root, args.name, remote=bool(args.remote))
        print(THEME.warn(f"✓ Deleted tag '{args.name}'" + (" (local + remote)." if args.remote else ".")))
        return 0

    create_tag(location.root, args.name, message=args.message, push=bool(args.push))
    print(THEME.success(f"✓ Created tag '{args.name}'" + (" and pushed to origin." if args.push else ".")))
    return 0


def run_doctor_cmd(_args: argparse.Namespace) -> int:
    checks = run_doctor()
    print(THEME.bold("SimpleGit Doctor"))
    has_fail = False
    for chk in checks:
        if chk.status == "ok":
            icon = THEME.success("✓")
        elif chk.status == "warn":
            icon = THEME.warn("!")
        else:
            icon = THEME.error("✗")
            has_fail = True
        print(f"  {icon} {THEME.bold(chk.name)}: {chk.detail}")
        if chk.fix_hint:
            print(f"      {THEME.info('Fix:')} {chk.fix_hint}")
    return 1 if has_fail else 0

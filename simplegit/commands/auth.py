"""Handlers for `sgit auth` (GitHub & GitLab HTTPS token and SSH authentication)."""

from __future__ import annotations

import argparse
import getpass

from simplegit.core.auth import (
    clear_https_credentials,
    find_ssh_public_keys,
    generate_ssh_key,
    get_auth_status,
    host_for_provider,
    store_https_credentials,
    verify_provider_token,
)
from simplegit.core.runner import run_git
from simplegit.errors import SimpleGitError
from simplegit.ui.terminal import confirm, prompt_line
from simplegit.ui.theme import THEME


def register(subparsers: argparse._SubParsersAction) -> None:
    auth = subparsers.add_parser("auth", help="Authenticate with GitHub or GitLab (HTTPS token or SSH)")
    auth_sub = auth.add_subparsers(dest="auth_action", metavar="<action>")

    login = auth_sub.add_parser("login", help="Log in to GitHub or GitLab")
    _add_provider_flags(login)
    login.add_argument("--token", help="Personal Access Token (if omitted, prompts securely)")
    login.add_argument("-u", "--username", help="Username (used with `--skip-verify`)")
    login.add_argument("--skip-verify", action="store_true", help="Store token without calling the provider API")
    login.add_argument("--ssh", action="store_true", help="Set up / display SSH public key instead of HTTPS token")
    login.set_defaults(handler=run_login)

    status = auth_sub.add_parser("status", help="Show GitHub and GitLab authentication status")
    status.set_defaults(handler=run_status)

    logout = auth_sub.add_parser("logout", help="Remove stored HTTPS credentials for a provider")
    _add_provider_flags(logout)
    logout.set_defaults(handler=run_logout)

    auth.set_defaults(handler=run_status)


def _add_provider_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-gh", "--github", action="store_true", help="Target GitHub (github.com)")
    group.add_argument("-gl", "--gitlab", action="store_true", help="Target GitLab (gitlab.com)")
    parser.add_argument("--host", help="Custom GitHub Enterprise / self-hosted GitLab domain")


def run_login(args: argparse.Namespace) -> int:
    host = host_for_provider(github=bool(args.github), gitlab=bool(args.gitlab), custom_host=args.host)
    is_gitlab = bool(args.gitlab) or ("gitlab" in host.lower())

    if args.ssh:
        return _handle_ssh_setup(host, is_gitlab)

    token = args.token or getpass.getpass(f"Paste Personal Access Token for {host} (input hidden): ").strip()
    if not token:
        raise SimpleGitError("No token provided.", hint="Create a Personal Access Token and pass it or paste at the prompt.")

    if args.skip_verify:
        username = args.username or prompt_line(f"Username for {host}", "git")
    else:
        print(THEME.muted(f"Verifying token with {host}..."))
        username = verify_provider_token(host, token, is_gitlab=is_gitlab)

    helper = store_https_credentials(host, username, token)
    print(THEME.success(f"✓ Authenticated as @{username} on {host}") + THEME.muted(f" (stored via `{helper}`)"))
    return 0


def _handle_ssh_setup(host: str, is_gitlab: bool) -> int:
    keys = find_ssh_public_keys()
    if not keys:
        if not confirm("No SSH public keys found in ~/.ssh. Generate an ed25519 key now?", default=True):
            return 0
        default_email = run_git(["config", "--get", "user.email"], check=False).stdout.strip()
        email = prompt_line("Email for SSH key", default_email or "user@example.com")
        pub_path = generate_ssh_key(email)
        keys = [pub_path]
        print(THEME.success(f"✓ Generated SSH key: {pub_path}"))

    pub_key = keys[0]
    settings_url = (
        f"https://{host}/-/user_settings/ssh_keys"
        if is_gitlab
        else f"https://{host}/settings/keys"
    )
    print(f"\n{THEME.bold('Public key')} ({pub_key}):")
    print(THEME.info(pub_key.read_text(encoding="utf-8", errors="replace").strip()))
    print(f"\n{THEME.muted('Add this key at:')} {settings_url}")
    print(THEME.muted(f"Test with: `ssh -T git@{host}`"))
    return 0


def run_status(_args: argparse.Namespace) -> int:
    statuses = get_auth_status()
    print(THEME.bold("Authentication Status"))
    for item in statuses:
        if item.https_user:
            https_str = THEME.success(f"✓ HTTPS (@{item.https_user})")
        else:
            https_str = THEME.muted("not logged in via HTTPS")
        ssh_str = THEME.info(f"SSH keys: {', '.join(item.ssh_keys)}") if item.ssh_keys else THEME.muted("no SSH keys")
        print(f"  {THEME.bold(item.host)}: {https_str}  |  {ssh_str}")
    return 0


def run_logout(args: argparse.Namespace) -> int:
    host = host_for_provider(github=bool(args.github), gitlab=bool(args.gitlab), custom_host=args.host)
    clear_https_credentials(host)
    print(THEME.success(f"✓ Removed stored HTTPS credentials for {host}."))
    return 0

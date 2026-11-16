"""GitHub and GitLab authentication via Git credential helpers and SSH."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from simplegit.core.runner import find_git_binary, run_git
from simplegit.errors import SimpleGitError


@dataclass(frozen=True)
class AuthStatus:
    """Summary of stored HTTPS credential or SSH readiness for a Git host."""

    host: str
    https_user: str | None
    ssh_keys: tuple[str, ...]


def host_for_provider(github: bool = False, gitlab: bool = False, custom_host: str | None = None) -> str:
    """Resolve hostname for GitHub, GitLab, or custom instance."""
    if github and gitlab:
        raise SimpleGitError("Choose either `-gh` (GitHub) or `-gl` (GitLab), not both.")
    if custom_host:
        return custom_host.strip().removeprefix("https://").removeprefix("http://").strip("/")
    if github:
        return "github.com"
    if gitlab:
        return "gitlab.com"
    raise SimpleGitError(
        "Specify a provider (`-gh` for GitHub or `-gl` for GitLab).",
        hint="Example: `sgit auth login -gh` or `sgit auth login -gl`",
    )


def ensure_credential_helper() -> str:
    """Ensure a global `credential.helper` is configured and return its name."""
    res = run_git(["config", "--global", "--get", "credential.helper"], check=False)
    existing = res.stdout.strip()
    if existing:
        return existing

    system = platform.system()
    if system == "Darwin":
        helper = "osxkeychain"
    elif system == "Windows":
        helper = "manager"
    else:
        helper = "store"

    run_git(["config", "--global", "credential.helper", helper])
    return helper


def verify_provider_token(host: str, token: str, is_gitlab: bool = False) -> str:
    """Verify a PAT against GitHub or GitLab API and return the account username."""
    if is_gitlab or "gitlab" in host.lower():
        url = f"https://{host}/api/v4/user"
        headers = {"PRIVATE-TOKEN": token, "User-Agent": "SimpleGit/0.1"}
    else:
        api_base = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
        url = f"{api_base}/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "SimpleGit/0.1",
        }

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise SimpleGitError(
                f"Authentication rejected by {host} (HTTP {exc.code}).",
                hint="Check that your Personal Access Token is valid and has `repo` / `write_repository` scope.",
            ) from exc
        raise SimpleGitError(f"Failed to verify token with {host}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SimpleGitError(
            f"Could not reach {host}: {exc.reason}",
            hint="Check your internet connection, or pass `--skip-verify` to store the token offline.",
        ) from exc

    username = payload.get("login") or payload.get("username")
    if not username:
        raise SimpleGitError(f"Unexpected API response from {host}: missing username.")
    return str(username)


def _run_git_credential(action: str, payload: str) -> subprocess.CompletedProcess[str]:
    git_bin = find_git_binary()
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [git_bin, "credential", action],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def store_https_credentials(host: str, username: str, token: str) -> str:
    """Store HTTPS credentials in Git's configured credential helper."""
    helper = ensure_credential_helper()
    payload = f"protocol=https\nhost={host}\nusername={username}\npassword={token}\n\n"
    proc = _run_git_credential("approve", payload)
    if proc.returncode != 0:
        raise SimpleGitError(
            f"Failed to store credentials using `{helper}`.",
            details=proc.stderr.strip(),
        )
    return helper


def clear_https_credentials(host: str) -> None:
    """Remove stored HTTPS credentials for `host` from Git's credential helper."""
    payload = f"protocol=https\nhost={host}\n\n"
    proc = _run_git_credential("reject", payload)
    if proc.returncode != 0:
        raise SimpleGitError(
            f"Failed to remove credentials for {host}.",
            details=proc.stderr.strip(),
        )


def get_stored_username(host: str) -> str | None:
    """Query Git's credential helper for a stored username on `host` without prompting."""
    payload = f"protocol=https\nhost={host}\n\n"
    proc = _run_git_credential("fill", payload)
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("username="):
            return line.split("=", 1)[1].strip() or None
    return None


def find_ssh_public_keys(ssh_dir: Path | None = None) -> list[Path]:
    """Return existing SSH public key files in `~/.ssh`."""
    base = ssh_dir or (Path.home() / ".ssh")
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("*.pub") if p.is_file())


def generate_ssh_key(email: str, ssh_dir: Path | None = None) -> Path:
    """Generate an ed25519 SSH keypair using `ssh-keygen` if none exists."""
    ssh_keygen = shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise SimpleGitError("`ssh-keygen` was not found on your PATH.")
    base = ssh_dir or (Path.home() / ".ssh")
    base.mkdir(parents=True, exist_ok=True)
    key_path = base / "id_ed25519"
    if key_path.exists():
        raise SimpleGitError(
            f"SSH key already exists at {key_path}.",
            hint=f"Copy `{key_path}.pub` to your GitHub/GitLab SSH key settings.",
        )
    try:
        subprocess.run(
            [ssh_keygen, "-t", "ed25519", "-C", email, "-f", str(key_path), "-N", ""],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        err_detail = getattr(exc, "stderr", None) or str(exc)
        raise SimpleGitError("Failed to generate ed25519 SSH key.", details=err_detail) from exc
    return Path(f"{key_path}.pub")


def get_auth_status(hosts: tuple[str, ...] = ("github.com", "gitlab.com")) -> list[AuthStatus]:
    """Return credential and SSH key status for GitHub and GitLab."""
    ssh_keys = tuple(p.name for p in find_ssh_public_keys())
    return [
        AuthStatus(
            host=host,
            https_user=get_stored_username(host),
            ssh_keys=ssh_keys,
        )
        for host in hosts
    ]

#!/usr/bin/env python3
"""Fill repo_overview.md § Active run and § Git and review context after bootstrap."""
import argparse
import re
import subprocess
from pathlib import Path


def git_default_branch(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        ref = out.stdout.strip()
        if ref.startswith("refs/remotes/origin/"):
            return ref.removeprefix("refs/remotes/origin/")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_remote_origin(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def patch_row(content: str, key: str, value: str) -> str:
    pattern = rf"(\| \*\*{re.escape(key)}\*\* \|)[^\n]*"
    repl = rf"\1 {value} |"
    new, n = re.subn(pattern, repl, content, count=1)
    if n == 0:
        raise SystemExit(f"Could not find table row for key: {key}")
    return new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "-w", type=Path, required=True)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--run-slug", required=True)
    parser.add_argument("--run-started", required=True)
    args = parser.parse_args()

    root = args.workspace.expanduser().resolve()
    overview = root / ".cursor/context/repo_overview.md"
    if not overview.is_file():
        raise SystemExit(f"Missing {overview}")

    run_dir = f"~/data/{args.project_slug}/runs/{args.run_slug}/"
    log_path = f"{run_dir}interaction_log.md"

    text = overview.read_text(encoding="utf-8")
    text = patch_row(text, "Project slug", f"`{args.project_slug}`")
    text = patch_row(text, "Username", f"`{args.username}`")
    text = patch_row(text, "Active `{run_slug}`", f"`{args.run_slug}`")
    text = patch_row(text, "Run directory", f"`{run_dir}`")
    text = patch_row(text, "Interaction log", f"`{log_path}`")
    text = patch_row(text, "`{run_started}`", f"`{args.run_started}`")

    branch = git_default_branch(root)
    remote = git_remote_origin(root)
    if branch:
        text = patch_row(text, "`{git_default_branch}`", f"`{branch}`")
    else:
        text = patch_row(
            text,
            "`{git_default_branch}`",
            "*(local only — run `git init` and add remote, or set manually)*",
        )
    if remote:
        text = patch_row(text, "Remote", f"`{remote}`")
        host = "GitHub" if "github" in remote.lower() else "GitLab" if "gitlab" in remote.lower() else "*(detected from remote URL)*"
        text = patch_row(text, "`{git_host}`", host)
    else:
        text = patch_row(text, "Remote", "*(none)*")

    overview.write_text(text, encoding="utf-8")
    print(f"Updated {overview}")


if __name__ == "__main__":
    main()

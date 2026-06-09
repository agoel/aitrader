"""Load project `.env` into os.environ (keys already set are not overwritten)."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, val = line.split("=", 1)
    key = key.strip()
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        val = val[1:-1]
    return key, val


def load_env_file(path: Path) -> int:
    """Set unset environ vars from file. Returns count loaded."""
    if not path.is_file():
        return 0
    loaded = 0
    for line in path.read_text().splitlines():
        parsed = _parse_line(line)
        if not parsed:
            continue
        key, val = parsed
        if key and key not in os.environ:
            os.environ[key] = val
            loaded += 1
    return loaded


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd()):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


def load_project_dotenv() -> Path | None:
    """Load `.env` from repo root or cwd if present."""
    for base in (repo_root(), Path.cwd()):
        env_path = base / ".env"
        if env_path.is_file():
            load_env_file(env_path)
            return env_path
    return None

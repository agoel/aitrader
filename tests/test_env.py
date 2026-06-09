"""Project .env loader."""

from __future__ import annotations

import os
from pathlib import Path

from aitrader.env import load_env_file


def test_load_env_file_does_not_override(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=from_file\n")
    os.environ["FOO"] = "existing"
    n = load_env_file(env)
    assert n == 0
    assert os.environ["FOO"] == "existing"
    del os.environ["FOO"]

    n = load_env_file(env)
    assert n == 1
    assert os.environ["FOO"] == "from_file"
    del os.environ["FOO"]

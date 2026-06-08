#!/usr/bin/env python3
"""
Shared utilities for topic extraction pipeline.
No dependency on monorepo layout: paths come from CLI, cwd, or env vars.
"""
import os
from pathlib import Path

ROUTER_TYPE_ROUTER = "router"
ROUTER_TYPE_L345 = "l345_router"

# Env: ROUTER_BUILDER_WORKSPACE — project root (folder containing .cursor/context)
# Env: ROUTER_BUILDER_DATA — parent of agent_topics/ and agent_topics_l345/


def resolve_workspace(cli_workspace: Path | None) -> Path:
    if cli_workspace is not None:
        return Path(cli_workspace).expanduser().resolve()
    env = os.environ.get("ROUTER_BUILDER_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd().resolve()


def resolve_data_base(cli_data: Path | None) -> Path:
    if cli_data is not None:
        return Path(cli_data).expanduser().resolve()
    env = os.environ.get("ROUTER_BUILDER_DATA")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "data").resolve()


def get_agent_topics_dir(router_type: str, data_base: Path) -> Path:
    if router_type == ROUTER_TYPE_L345:
        return data_base / "agent_topics_l345"
    if router_type == ROUTER_TYPE_ROUTER:
        return data_base / "agent_topics"
    raise ValueError(
        f"router_type must be '{ROUTER_TYPE_ROUTER}' or '{ROUTER_TYPE_L345}', got: {router_type}"
    )


def resolve_context_dir(cli_context: Path | None, workspace: Path) -> Path:
    if cli_context is not None:
        return Path(cli_context).expanduser().resolve()
    return workspace / ".cursor" / "context"


def add_router_type_arg(parser, default: str = ROUTER_TYPE_ROUTER):
    parser.add_argument(
        "--router-type",
        choices=[ROUTER_TYPE_ROUTER, ROUTER_TYPE_L345],
        default=default,
        help=f"'{ROUTER_TYPE_ROUTER}' (domain, ~/data/agent_topics) or '{ROUTER_TYPE_L345}' (L345, ~/data/agent_topics_l345).",
    )


def add_workspace_arg(parser):
    parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Project root with .cursor/context (default: cwd or ROUTER_BUILDER_WORKSPACE).",
    )


def add_data_dir_arg(parser):
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Parent of agent_topics/ and agent_topics_l345/ (default: ~/data or ROUTER_BUILDER_DATA).",
    )


def add_context_dir_arg(parser):
    parser.add_argument(
        "--context-dir",
        type=Path,
        default=None,
        help="Folder containing agent .md files (default: <workspace>/.cursor/context).",
    )

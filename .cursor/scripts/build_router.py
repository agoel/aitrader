#!/usr/bin/env python3
"""
Stamp router.md or l345_router.md from templates in docs/operator/router_templates.md,
plus topic_to_agents.txt and agent_topics.txt under the data dir.

Portable: run from any cwd; pass -w/--workspace (project root) or set ROUTER_BUILDER_WORKSPACE.
L345 mode uses flat ### topic clusters and merges docs/operator/l345_router_recipe_index.md.
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

from topic_utils import (
    ROUTER_TYPE_L345,
    ROUTER_TYPE_ROUTER,
    add_data_dir_arg,
    add_workspace_arg,
    resolve_context_dir,
    resolve_data_base,
    resolve_workspace,
    get_agent_topics_dir,
)

CLUSTER_NAMES = {
    1: "Authentication & Authorization",
    2: "Account & User Lifecycle",
    3: "Connections",
    4: "Endpoints & REST API",
    5: "Validation & Schema",
    6: "Verification",
    7: "Testing",
    8: "Error Handling & Debugging",
    9: "Configuration & Environment",
    10: "Storage & S3",
    11: "Caching",
    12: "Background Jobs & Queue",
    13: "Notifications & Messaging",
    14: "Payments & Billing",
    15: "Offers & Redemption",
    16: "Device Integration (Garmin)",
    17: "Workflow & State Machine",
    18: "UI & Frontend",
    19: "Web, Deployment & Platform",
    20: "Build, CLI & Logging",
    21: "Data & Schema Structure",
    22: "Migrations & Versioning",
    23: "Concurrency & Locking",
    24: "Leads & State of Mind (SOM)",
    25: "Limitations & Known Issues",
    26: "Architecture & Integrations",
}

DEFAULT_TEMPLATE = Path("docs/operator/router_templates.md")
L345_RECIPE_INDEX = Path("docs/operator/l345_router_recipe_index.md")


def parse_topic_to_agents(tt_path: Path):
    topic_to_refs = defaultdict(list)
    with open(tt_path) as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith("  ") or "===" in line:
                continue
            parts = line.strip().split(":", 2)
            if len(parts) < 3:
                continue
            topic, agent, rest = parts
            agent = agent.strip()
            rest = rest.strip()

            if agent == "lsai_router.md":
                continue
            if re.match(r"^\d+-\d+$", rest):
                ref = f"{agent} (lines {rest})"
            elif rest.startswith("section:"):
                if ":sub-section:" in rest:
                    sec_part, sub_part = rest.split(":sub-section:", 1)
                    section = sec_part.replace("section:", "", 1).strip()
                    subsection = sub_part.strip()
                    ref = f"{agent} | section: {section} | sub-section: {subsection}"
                else:
                    section = rest.replace("section:", "", 1).strip()
                    ref = f"{agent} | section: {section}"
            elif rest.startswith("sub-section:"):
                subsection = rest.replace("sub-section:", "", 1).strip()
                ref = f"{agent} | sub-section: {subsection}"
            else:
                ref = f"{agent} | {rest}"

            topic_to_refs[topic].append(ref)
    return topic_to_refs


def topic_to_cluster(topic: str) -> int:
    t = topic.lower()
    if any(
        x in t
        for x in [
            "access control",
            "authentication",
            "permission",
            "session validation",
            "role",
            "passcode",
            "passkey",
            "oauth",
            "security",
            "header access",
        ]
    ):
        return 1
    if any(
        x in t
        for x in [
            "account",
            "user profile",
            "user lifecycle",
            "user onboarding",
            "user role",
            "user setting",
            "signup",
            "duplicate account",
            "profile access",
            "profile management",
            "profile retrieval",
            "agent signup",
            "enterprise signup",
            "registration",
            "verifier path",
        ]
    ):
        return 2
    if any(
        x in t
        for x in [
            "connection add",
            "connection entry",
            "connection error",
            "connection establishment",
            "connection removal",
            "connection type",
            "connection update",
            "connections list",
            "connections",
        ]
    ):
        return 3
    if any(
        x in t
        for x in [
            "endpoint",
            "rest api",
            "rest backend",
            "webhook",
            "body schema",
            "body validation",
            "query params",
            "action query",
            "action-based",
            "declarative config",
            "mock response",
            "url structure",
            "request body",
            "response finalization",
            "response formatting",
            "success response",
            "header construction",
        ]
    ):
        return 4
    if any(
        x in t
        for x in [
            "schema validation",
            "validation",
            "validation error",
            "validation enum",
            "validation framework",
            "validation hook",
            "validation only",
            "automatic validation",
            "parameter validation",
            "form validation",
            "email validation",
            "type definition",
            "type safety",
            "data schema",
            "schema structure",
            "schema version",
            "versioned schema",
            "enums",
        ]
    ):
        return 5
    if any(x in t for x in ["verification", "verifier"]):
        return 6
    if any(
        x in t
        for x in [
            "test",
            "alpha",
            "beta testing",
            "fixture",
            "run verify",
            "run_beta",
            "injection testing",
            "manual testing",
            "debug test",
            "example test",
            "expectation gating",
            "raw payload",
        ]
    ):
        return 7
    if any(
        x in t
        for x in [
            "error handling",
            "error message",
            "error response",
            "debugging",
            "failure triage",
            "http error",
            "runtime error",
            "local_error_log",
            "deletion error",
            "payment error",
        ]
    ):
        return 8
    if any(
        x in t
        for x in [
            "configuration",
            "config",
            "environment",
            "credentials",
            "credential bootstrap",
            "json configuration",
            "json driven",
            "json files",
        ]
    ):
        return 9
    if any(
        x in t
        for x in [
            "s3",
            "storage",
            "ledger",
            "private bucket",
            "login bucket",
            "gc on s3",
            "gc index",
            "data storage",
            "no persistence",
        ]
    ):
        return 10
    if any(x in t for x in ["cache", "universal cache"]):
        return 11
    if any(x in t for x in ["job", "queue", "priority queue"]):
        return 12
    if any(
        x in t
        for x in [
            "notification",
            "chat",
            "messaging",
            "push",
            "firebase",
            "message id",
            "message parsing",
            "message cleanup",
            "media attachment",
            "coach message",
        ]
    ):
        return 13
    if any(
        x in t
        for x in [
            "payment",
            "billing",
            "invoicing",
            "stripe",
            "subscription",
            "commission",
            "payout",
            "receipt",
            "shopping cart",
            "currency conversion",
        ]
    ):
        return 14
    if any(x in t for x in ["offer", "redemption", "qr code"]):
        return 15
    if any(x in t for x in ["garmin", "device", "backfill", "babysitter", "garmin_tools"]):
        return 16
    if any(
        x in t
        for x in [
            "workflow",
            "fsm",
            "state",
            "processing flow",
            "execution flow",
            "interstitial",
            "phase execution",
            "sequential step",
        ]
    ):
        return 17
    if any(
        x in t
        for x in [
            "angular",
            "ui",
            "uigen",
            "template",
            "component",
            "layout",
            "slider",
            "menu json",
            "content",
            "context-aware",
            "dynamic content",
            "html score",
            "styling",
        ]
    ):
        return 18
    if any(
        x in t
        for x in [
            "deployment",
            "platform",
            "web client",
            "web-only",
            "android",
            "ios",
            "seo",
            "corporate website",
            "async mobile",
            "mobile deeplink",
        ]
    ):
        return 19
    if any(
        x in t
        for x in ["build", "cli", "argparse", "apache", "log", "virtualenv", "clean init"]
    ):
        return 20
    if any(
        x in t
        for x in [
            "data aggregation",
            "data parsing",
            "data privacy",
            "data protection",
            "data separation",
            "data source",
            "data structure",
            "hierarchical",
            "flat dict",
            "graph state",
            "step data",
            "target dict",
            "json types",
        ]
    ):
        return 21
    if any(x in t for x in ["migration", "versioned", "backward compatibility", "converter"]):
        return 22
    if any(x in t for x in ["lock", "deadlock", "distributed locking", "concurrency", "isolation"]):
        return 23
    if any(x in t for x in ["lead", "state of mind", "som port"]):
        return 24
    if any(x in t for x in ["limitation", "known issue", "todos", "stage restriction", "stage scope"]):
        return 25
    return 26


def load_template(template_path: Path, l345: bool) -> str:
    content = template_path.read_text(encoding="utf-8")
    if l345:
        start_marker = "<!-- L345_ROUTER_TEMPLATE_START -->"
        end_marker = "<!-- L345_ROUTER_TEMPLATE_END -->"
    else:
        start_marker = "<!-- ROUTER_TEMPLATE_START -->"
        end_marker = "<!-- ROUTER_TEMPLATE_END -->"
    if start_marker not in content or end_marker not in content:
        raise SystemExit(f"Template markers not found in {template_path}")
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker)
    return content[start:end].strip()


def load_l345_recipe_index(context_dir: Path) -> str:
    path = context_dir / L345_RECIPE_INDEX
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def render_flat_topic_router(topic_to_refs, all_topics) -> list[str]:
    lines = ["# Topic Router", ""]
    for topic in sorted(all_topics, key=str.lower):
        refs = topic_to_refs.get(topic, [])
        lines.append(f"### {topic}")
        lines.append("")
        if refs:
            for ref in refs:
                lines.append(f"- {ref}")
        else:
            lines.append("- (no agent mappings)")
        lines.append("")
    return lines


def render_clustered_topic_router(topic_to_refs, all_topics) -> list[str]:
    clusters = defaultdict(list)
    for topic in all_topics:
        clusters[topic_to_cluster(topic)].append(topic)
    for c in clusters:
        clusters[c].sort(key=str.lower)

    lines = [
        "# Topic Router",
        "",
        "Clustered topics with agent references. Use this to route queries to the right agent(s).",
        "",
    ]
    for c in range(1, 27):
        name = CLUSTER_NAMES[c]
        topics = clusters[c]
        lines.append(f"## {c}. {name}")
        lines.append("")
        for topic in topics:
            refs = topic_to_refs.get(topic, [])
            lines.append(f"### {topic}")
            lines.append("")
            if refs:
                for ref in refs:
                    lines.append(f"- {ref}")
            else:
                lines.append("- (no agent mappings)")
            lines.append("")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_workspace_arg(parser)
    add_data_dir_arg(parser)
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="Markdown file containing router template markers (default: <context>/docs/operator/router_templates.md).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output router file (default: <context>/router.md or l345_router.md).",
    )
    parser.add_argument(
        "--l345",
        action="store_true",
        help="Use L345 template markers and agent_topics_l345 data; write l345_router.md by default.",
    )
    args = parser.parse_args()

    workspace = resolve_workspace(args.workspace)
    data_base = resolve_data_base(args.data_dir)
    router_type = ROUTER_TYPE_L345 if args.l345 else ROUTER_TYPE_ROUTER
    agent_topics_dir = get_agent_topics_dir(router_type, data_base)
    tt_path = agent_topics_dir / "topic_to_agents.txt"
    agent_topics_path = agent_topics_dir / "agent_topics.txt"
    context_dir = resolve_context_dir(None, workspace)
    template_path = args.template or (context_dir / DEFAULT_TEMPLATE)
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        name = "l345_router.md" if args.l345 else "router.md"
        out_path = context_dir / name

    topic_to_refs = parse_topic_to_agents(tt_path)
    topic_to_freq = {}
    with open(agent_topics_path) as f:
        for line in f:
            if ":" not in line:
                continue
            parts = line.strip().rsplit(":", 1)
            topic = parts[0].strip()
            try:
                topic_to_freq[topic] = int(parts[1])
            except ValueError:
                pass
    all_topics = list(topic_to_freq.keys())

    template = load_template(template_path, args.l345)
    topic_lines = [f"{t} ({topic_to_freq[t]})" for t in sorted(all_topics, key=str.lower)]
    topic_list = "\n".join(topic_lines)
    preamble = template.replace("{{TOPIC_LIST}}", topic_list)

    parts = [preamble]
    if args.l345:
        recipe_index = load_l345_recipe_index(context_dir)
        if recipe_index:
            parts.extend(["", recipe_index, ""])
        parts.extend(render_flat_topic_router(topic_to_refs, all_topics))
    else:
        parts.extend(render_clustered_topic_router(topic_to_refs, all_topics))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    print(f"Wrote {out_path}")
    print(f"Topics: {len(all_topics)}")
    if args.l345:
        print(f"Recipe index: {context_dir / L345_RECIPE_INDEX}")


if __name__ == "__main__":
    main()

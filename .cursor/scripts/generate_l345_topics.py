#!/usr/bin/env python3
"""
Generate .topics files for router or l345_router.
Output: <data-dir>/agent_topics/*.topics or .../agent_topics_l345/*.topics per --router-type

Standalone: set ROUTER_BUILDER_WORKSPACE to your project root, or run from that directory.
Use --context-dir if agent .md files live outside .cursor/context.
"""
import argparse
import re
import sys
from pathlib import Path

from topic_utils import (
    ROUTER_TYPE_L345,
    ROUTER_TYPE_ROUTER,
    add_context_dir_arg,
    add_data_dir_arg,
    add_router_type_arg,
    add_workspace_arg,
    get_agent_topics_dir,
    resolve_context_dir,
    resolve_data_base,
    resolve_workspace,
)

# Domain router: exclude from topic extraction (per lsai_superagent.md Exclusion List)
ROUTER_EXCLUSION_LIST = {
    "cursor_setup.md",
    "gitlab_mr_guidelines.md",
    "git_mr_guidelines.md",
    "model_training.md",
    "tutoral.md",
    "MR.md",
    "ashish_and_rahul.md",
    "lsai_transactions.md",
    "lsai_subagents.md",
    "lsai_superagent.md",
    "l345_router.md",
    "repo_overview.md",
    "coding_standards.md",
    "lsai_e2e.md",
    "agentic_merge.md",
    "router.md",
}

# Default L345 agent set (portable bundle). Override with --l345-agents-file (one .md filename per line).
DEFAULT_L345_AGENTS = [
    "coding_standards.md",
    "repo_overview.md",
    "git_mr_guidelines.md",
    "lsai_subagents.md",
    "lsai_superagent.md",
    "lsai_e2e.md",
    "agentic_merge.md",
]


def load_l345_agents(path: Path | None) -> list[str]:
    if path is None:
        return list(DEFAULT_L345_AGENTS)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def extract_sections(
    md_path: Path, l345_mode: bool = True
) -> list[tuple[int, int, str, list[str]]]:
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(#{2,6})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            start = i + 1
            j = i + 1
            while j < len(lines):
                m2 = re.match(r"^(#{1,6})\s+", lines[j])
                if m2 and len(m2.group(1)) <= level:
                    break
                j += 1
            end = j
            if level == 2:
                has_child = any(
                    re.match(r"^#{3,6}\s+", lines[k])
                    for k in range(i + 1, min(end, len(lines)))
                )
                if has_child:
                    i = j
                    continue
            if level >= 2:
                topics = heading_to_topics(title, lines[start:end], l345_mode)
                if topics:
                    result.append((start + 1, end, title, topics))
        i += 1
    return result


def heading_to_topics(heading: str, content: list[str], l345_mode: bool = True) -> list[str]:
    text = heading + " " + " ".join(content[:5])
    text_lower = text.lower()
    topics = []
    if "overview" in text_lower or "overview" in heading.lower():
        topics.append("overview")
    if "coding standard" in text_lower or "python" in text_lower or "typescript" in text_lower:
        topics.append("coding standards")
    if "related file" in text_lower or "cited by" in text_lower:
        topics.append("bidirectional citation")
    if "layered" in text_lower or "layer" in text_lower:
        topics.append("layered implementation")
    if "mr " in text_lower or "merge request" in text_lower or "gitlab" in text_lower:
        topics.append("gitlab MR format")
    if "alpha" in text_lower or "beta" in text_lower or "gamma" in text_lower:
        topics.append("alpha beta gamma testing")
    if "recipe" in text_lower:
        topics.append("recipe structure")
    if "agent" in text_lower and ("creat" in text_lower or "modif" in text_lower):
        topics.append("agent modification")
    if "router" in text_lower:
        topics.append("router building")
    if "topic" in text_lower and "extract" in text_lower:
        topics.append("topic extraction")
    if "core concept" in text_lower:
        topics.append("core concepts layered work")
    if "people ranker" in text_lower or "mono repo" in text_lower or "repo layout" in text_lower:
        topics.append("repo layout")
    if "stack bootstrap" in text_lower or "portable stack" in text_lower:
        topics.append("stack bootstrap portable")
    if "design" in text_lower:
        topics.append("design update")
    if "test" in text_lower and ("alpha" in text_lower or "section" in text_lower):
        topics.append("test section update")
    if "sub-agent" in text_lower or "subagent" in text_lower:
        topics.append("sub-agent design")
    if "template" in text_lower:
        topics.append("agent template")
    if "agent vision" in text_lower:
        topics.append("core concepts layered work")
    if "two type" in text_lower or "router type" in text_lower:
        topics.append("router update")
    if "exclusion" in text_lower:
        topics.append("router building")
    if "build" in text_lower and "test" in text_lower:
        topics.append("people ranker overview")
    if "key component" in text_lower or "sub-agent" in text_lower:
        topics.append("people ranker overview")
    if "title" in text_lower and "release" in text_lower:
        topics.append("gitlab MR format")
    if "section" in text_lower and "detail" in text_lower:
        topics.append("gitlab MR format")
    if "recipe" in text_lower and "extract" in text_lower:
        topics.append("recipe extraction")
    if "recipe" in text_lower and "publish" in text_lower:
        topics.append("recipe structure")
    if "bidirectional" in text_lower:
        topics.append("bidirectional citation")
    if "agent snapshot" in text_lower:
        topics.append("recipe extraction")
    if "mr section" in text_lower or "close out" in text_lower:
        topics.append("design update")
    if "clippable" in text_lower:
        topics.append("gitlab MR format")
    if "document structure" in text_lower:
        topics.append("sub-agent template")
    if "virtual env" in text_lower or "virtualenv" in text_lower:
        topics.append("people ranker overview")
    if "file organization" in text_lower:
        topics.append("coding standards")
    if "cross-cutting" in text_lower:
        topics.append("coding standards")
    if "intent routing" in text_lower or "l2" in text_lower or "l3" in text_lower:
        topics.append("core concepts layered work")
    if "router architecture" in text_lower:
        topics.append("router building")
    if "router usage" in text_lower:
        topics.append("router building")
    if "router builder" in text_lower:
        topics.append("router building")
    if "definition" in text_lower and "topic" in text_lower:
        topics.append("topic extraction")
    if "exclusion list" in text_lower:
        topics.append("router building")
    if "release roadmap" in text_lower:
        topics.append("design update")
    if "related agent" in text_lower:
        topics.append("router building")
    if not topics and l345_mode:
        topics = ["agent design"]
    if not topics and not l345_mode:
        words = [
            w
            for w in re.split(r"[\s\-_():]+", heading)
            if len(w) > 2
            and w.lower() not in ("the", "and", "for", "with", "from")
        ]
        topics = [" ".join(words[:3]).lower()] if words else ["agent design"]
    return list(dict.fromkeys(topics))[:4]


def get_agents_for_router_type(
    router_type: str, context_dir: Path, l345_list: list[str]
) -> list[str]:
    if router_type == ROUTER_TYPE_L345:
        return l345_list
    return [
        f.name
        for f in sorted(context_dir.glob("*.md"))
        if f.name not in ROUTER_EXCLUSION_LIST
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_router_type_arg(parser, default=ROUTER_TYPE_L345)
    add_workspace_arg(parser)
    add_context_dir_arg(parser)
    add_data_dir_arg(parser)
    parser.add_argument(
        "--l345", action="store_true", help="Shortcut for --router-type l345_router"
    )
    parser.add_argument(
        "--l345-agents-file",
        type=Path,
        default=None,
        help="Text file: one agent .md filename per line (L345 mode only).",
    )
    args = parser.parse_args()
    router_type = ROUTER_TYPE_L345 if args.l345 else args.router_type
    workspace = resolve_workspace(args.workspace)
    context_dir = resolve_context_dir(args.context_dir, workspace)
    data_base = resolve_data_base(args.data_dir)
    out_dir = get_agent_topics_dir(router_type, data_base)
    out_dir.mkdir(parents=True, exist_ok=True)
    l345_mode = router_type == ROUTER_TYPE_L345
    l345_agents = load_l345_agents(args.l345_agents_file)
    agents = get_agents_for_router_type(router_type, context_dir, l345_agents)

    for agent in agents:
        md_path = context_dir / agent
        if not md_path.exists():
            print(f"Skip {agent}: not found under {context_dir}")
            continue
        sections = extract_sections(md_path, l345_mode)
        out_path = out_dir / f"{agent.replace('.md', '')}.topics"
        with open(out_path, "w", encoding="utf-8") as f:
            for start, end, heading, topics in sections:
                topics_str = ", ".join(topics)
                f.write(f"{start}-{end}: {topics_str}\n")
        print(f"Wrote {out_path} with {len(sections)} entries")

    script_dir = Path(__file__).resolve().parent
    rt = "--router-type l345_router" if router_type == ROUTER_TYPE_L345 else "--router-type router"
    py = sys.executable
    print("\nNext (from any cwd; use same --workspace / --data-dir or env vars):")
    print(f'  "{py}" "{script_dir / "topic_frequency.py"}" {rt}')
    print(f'  "{py}" "{script_dir / "build_agent_topics.py"}" {rt}')
    print(f'  "{py}" "{script_dir / "build_agent_topics_index.py"}" -w "{workspace}" {rt}')
    print(f'  "{py}" "{script_dir / "build_reverse_index.py"}" {rt}')
    br_cmd = f'  "{py}" "{script_dir / "build_router.py"}" -w "{workspace}"'
    if router_type == ROUTER_TYPE_L345:
        br_cmd += " --l345"
    print(br_cmd)


if __name__ == "__main__":
    main()

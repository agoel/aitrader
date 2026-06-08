#!/usr/bin/env python3
"""
Router Builder Recipe - Step 1d: Build agent_topics_index.txt from .topics files.
Requires paths to agent .md files (via --workspace / --context-dir).
"""
import argparse
import re
from pathlib import Path
from typing import Optional, Tuple

from topic_utils import (
    ROUTER_TYPE_L345,
    add_context_dir_arg,
    add_data_dir_arg,
    add_router_type_arg,
    add_workspace_arg,
    get_agent_topics_dir,
    resolve_context_dir,
    resolve_data_base,
    resolve_workspace,
)


def get_section_and_subsection(
    md_path: Path, line_num: int
) -> Tuple[Optional[str], Optional[str]]:
    if not md_path.exists():
        return (None, None)
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if line_num < 1 or line_num > len(lines):
        return (None, None)

    section_title = None
    sub_section_title = None

    for i in range(line_num - 1, -1, -1):
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        if level == 1:
            continue
        if level == 2:
            section_title = title
            break
        if level >= 3 and sub_section_title is None:
            sub_section_title = title
            for j in range(i - 1, -1, -1):
                line2 = lines[j]
                m2 = re.match(r"^#{2}\s+(.+)$", line2)
                if m2:
                    section_title = m2.group(1).strip()
                    break
            break

    return (section_title, sub_section_title)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_router_type_arg(parser)
    add_data_dir_arg(parser)
    add_workspace_arg(parser)
    add_context_dir_arg(parser)
    parser.add_argument(
        "--l345", action="store_true", help="Shortcut for --router-type l345_router"
    )
    args = parser.parse_args()
    router_type = ROUTER_TYPE_L345 if args.l345 else args.router_type
    data_base = resolve_data_base(args.data_dir)
    workspace = resolve_workspace(args.workspace)
    context_dir = resolve_context_dir(args.context_dir, workspace)
    agent_topics_dir = get_agent_topics_dir(router_type, data_base)
    agent_topics_file = agent_topics_dir / "agent_topics.txt"
    output_file = agent_topics_dir / "agent_topics_index.txt"

    with open(agent_topics_file, "r", encoding="utf-8") as f:
        selected_topics = set()
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                topic, _ = line.rsplit(":", 1)
                selected_topics.add(topic.strip())
            else:
                selected_topics.add(line)

    results = []

    for topics_file in sorted(agent_topics_dir.glob("*.topics")):
        agent_name = topics_file.stem
        if agent_name.endswith(".md"):
            md_path = context_dir / agent_name
        else:
            md_path = context_dir / f"{agent_name}.md"

        agent_entries = []
        with open(topics_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                range_part, topics_part = line.split(":", 1)
                topics = [t.strip() for t in topics_part.split(",") if t.strip()]
                range_match = re.match(r"(\d+)-(\d+)", range_part.strip())
                if not range_match:
                    continue
                start_line = int(range_match.group(1))
                end_line = int(range_match.group(2))
                section_title, sub_section_title = get_section_and_subsection(
                    md_path, start_line
                )

                for topic in topics:
                    if topic in selected_topics:
                        agent_entries.append(
                            (topic, section_title, sub_section_title, start_line, end_line)
                        )

        if agent_entries:
            results.append((agent_name, agent_entries))

    with open(output_file, "w", encoding="utf-8") as f:
        for agent_name, entries in results:
            f.write(f"=== {agent_name} ===\n")
            by_topic = {}
            for topic, section_title, sub_section_title, start, end in entries:
                if topic not in by_topic:
                    by_topic[topic] = []
                by_topic[topic].append((section_title, sub_section_title, start, end))
            for topic in sorted(by_topic.keys()):
                loc_strs = []
                for section_title, sub_section_title, start, end in by_topic[topic]:
                    if section_title and sub_section_title:
                        loc_strs.append(
                            f"section||{section_title}||sub-section||{sub_section_title}"
                        )
                    elif section_title:
                        loc_strs.append(f"section||{section_title}")
                    elif sub_section_title:
                        loc_strs.append(f"sub-section||{sub_section_title}")
                    else:
                        loc_strs.append(f"lines||{start}-{end}")
                f.write(f"  {topic}: {'; '.join(loc_strs)}\n")
            f.write("\n")

    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()

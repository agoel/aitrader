#!/usr/bin/env python3
"""
Router Builder Recipe - Step 1e: Build reverse index (topic -> list of agents with locations).
Output: topic_to_agents.txt under the same data dir as other pipeline files.
"""
import argparse
from collections import defaultdict

from topic_utils import (
    ROUTER_TYPE_L345,
    add_data_dir_arg,
    add_router_type_arg,
    get_agent_topics_dir,
    resolve_data_base,
)

LOC_DELIM = "||"


def parse_location(loc_str: str) -> tuple:
    parts = loc_str.split(LOC_DELIM)
    section = None
    sub_section = None
    lines = None
    i = 0
    while i < len(parts):
        if parts[i] == "section" and i + 1 < len(parts):
            section = parts[i + 1].strip()
            i += 2
        elif parts[i] == "sub-section" and i + 1 < len(parts):
            sub_section = parts[i + 1].strip()
            i += 2
        elif parts[i] == "lines" and i + 1 < len(parts):
            lines = parts[i + 1].strip()
            i += 2
        else:
            i += 1
    return (section, sub_section, lines)


def format_output_line(
    topic: str, agent_name: str, section: str, sub_section: str, lines: str
) -> str:
    base = f"{topic}:{agent_name}"
    if section and sub_section:
        return f"{base}:section:{section}:sub-section:{sub_section}"
    if section:
        return f"{base}:section:{section}"
    if sub_section:
        return f"{base}:sub-section:{sub_section}"
    if lines:
        return f"{base}:{lines}"
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_router_type_arg(parser)
    add_data_dir_arg(parser)
    parser.add_argument(
        "--l345", action="store_true", help="Shortcut for --router-type l345_router"
    )
    args = parser.parse_args()
    router_type = ROUTER_TYPE_L345 if args.l345 else args.router_type
    data_base = resolve_data_base(args.data_dir)
    agent_topics_dir = get_agent_topics_dir(router_type, data_base)
    freq_file = agent_topics_dir / "topic_frequency.txt"
    index_file = agent_topics_dir / "agent_topics_index.txt"
    output_file = agent_topics_dir / "topic_to_agents.txt"

    topic_freq = {}
    with open(freq_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" not in line:
                continue
            topic, freq_str = line.rsplit(":", 1)
            try:
                topic_freq[topic.strip()] = int(freq_str)
            except ValueError:
                pass

    topic_to_locations = defaultdict(list)
    current_agent = None

    with open(index_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("=== ") and line.endswith(" ==="):
                current_agent = line[4:-4].strip()
                continue
            if current_agent and line.startswith("  ") and ": " in line:
                topic, locs_part = line[2:].split(": ", 1)
                topic = topic.strip()
                for loc_str in locs_part.split("; "):
                    loc_str = loc_str.strip()
                    if not loc_str:
                        continue
                    section, sub_section, lines = parse_location(loc_str)
                    topic_to_locations[topic].append(
                        (current_agent, section, sub_section, lines)
                    )

    sorted_topics = sorted(
        topic_to_locations.keys(), key=lambda t: (-topic_freq.get(t, 0), t)
    )

    with open(output_file, "w", encoding="utf-8") as f:
        for topic in sorted_topics:
            locs = topic_to_locations[topic]
            f.write(f"=== {topic} (freq={topic_freq.get(topic, 0)}) ===\n")
            for agent_name, section, sub_section, lines in locs:
                out_line = format_output_line(
                    topic, agent_name, section, sub_section, lines
                )
                f.write(f"  {out_line}\n")
            f.write("\n")

    print(f"Wrote {output_file} with {len(sorted_topics)} topics")


if __name__ == "__main__":
    main()

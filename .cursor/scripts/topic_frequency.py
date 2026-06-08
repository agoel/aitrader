#!/usr/bin/env python3
"""
Router Builder Recipe - Step 1b: Count topic frequency across all agent .topics files.
Output: <data-dir>/agent_topics/topic_frequency.txt or .../agent_topics_l345/ per --router-type
"""
import argparse
from collections import Counter

from topic_utils import (
    ROUTER_TYPE_L345,
    add_data_dir_arg,
    add_router_type_arg,
    get_agent_topics_dir,
    resolve_data_base,
)


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
    output_file = agent_topics_dir / "topic_frequency.txt"
    topic_counts = Counter()

    if not agent_topics_dir.is_dir():
        raise SystemExit(f"Data directory does not exist: {agent_topics_dir}")

    for topics_file in agent_topics_dir.glob("*.topics"):
        with open(topics_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                _, topics_part = line.split(":", 1)
                topics = [t.strip() for t in topics_part.split(",") if t.strip()]
                for topic in topics:
                    topic_counts[topic] += 1

    sorted_topics = sorted(topic_counts.items(), key=lambda x: (-x[1], x[0]))

    with open(output_file, "w", encoding="utf-8") as f:
        for topic, count in sorted_topics:
            f.write(f"{topic}:{count}\n")

    print(f"Wrote {output_file} with {len(sorted_topics)} topics")


if __name__ == "__main__":
    main()

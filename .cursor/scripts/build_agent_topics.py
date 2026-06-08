#!/usr/bin/env python3
"""
Router Builder Recipe - Step 1c: Select topics for agent_topics.txt.
Output: <data-dir>/agent_topics/ or .../agent_topics_l345/ per --router-type
"""
import argparse

from topic_utils import (
    ROUTER_TYPE_L345,
    add_data_dir_arg,
    add_router_type_arg,
    get_agent_topics_dir,
    resolve_data_base,
)

MAX_WORDS_SHORT_TOPIC = 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_router_type_arg(parser)
    add_data_dir_arg(parser)
    parser.add_argument(
        "--l345", action="store_true", help="Shortcut for --router-type l345_router"
    )
    parser.add_argument(
        "--min-freq",
        type=int,
        default=1,
        help="Freq threshold: keep if freq > N (default 1)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=MAX_WORDS_SHORT_TOPIC,
        help="Also keep topics with < N words (default 5)",
    )
    args = parser.parse_args()

    router_type = ROUTER_TYPE_L345 if args.l345 else args.router_type
    data_base = resolve_data_base(args.data_dir)
    agent_topics_dir = get_agent_topics_dir(router_type, data_base)
    freq_file = agent_topics_dir / "topic_frequency.txt"
    output_file = agent_topics_dir / "agent_topics.txt"

    selected = []
    with open(freq_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" not in line:
                continue
            topic, freq_str = line.rsplit(":", 1)
            topic = topic.strip()
            try:
                freq = int(freq_str)
                word_count = len(topic.split())
                keep = (freq > args.min_freq) or (word_count < args.max_words)
                if keep:
                    selected.append((topic, freq))
            except ValueError:
                pass

    with open(output_file, "w", encoding="utf-8") as f:
        for topic, freq in selected:
            f.write(f"{topic}:{freq}\n")

    print(
        f"Wrote {output_file} with {len(selected)} topics (freq > {args.min_freq} OR < {args.max_words} words)"
    )


if __name__ == "__main__":
    main()

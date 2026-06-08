"""AITrader CLI — L1 scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

from aitrader.data.yahoo import ingest_universe
from aitrader.universe import write_universe
from aitrader.workspace import ensure_run_layout, update_meta

DEFAULT_RUN_DIR = Path.home() / "data" / "aitrader" / "runs" / "agoel_stack-bootstrap_20260607-193720"


def _cmd_init(args: argparse.Namespace) -> None:
    root = ensure_run_layout(args.run_dir)
    update_meta(
        root,
        {
            "layer": "L1",
            "capital_usd": args.capital_usd,
            "anchor_indices": ["SPY", "IWM"],
        },
    )
    print(f"Initialized run workspace: {root}")


def _cmd_universe_build(args: argparse.Namespace) -> None:
    sectors_path, universe_path, count = write_universe(
        args.run_dir,
        stocks_per_sector=getattr(args, "stocks_per_sector", 10),
        sectors_min=getattr(args, "sectors_min", 8),
    )
    print(f"Wrote {sectors_path}")
    print(f"Wrote {universe_path} ({count} rows)")


def _cmd_data_yahoo(args: argparse.Namespace) -> None:
    manifest = ingest_universe(args.run_dir, years=getattr(args, "years", 5))
    print(f"Wrote {manifest}")


def _cmd_l1(args: argparse.Namespace) -> None:
    """Run full L1: init → universe → Yahoo ingest."""
    _cmd_init(args)
    _cmd_universe_build(args)
    _cmd_data_yahoo(args)
    update_meta(args.run_dir, {"L1": {"status": "completed"}})
    print("L1 complete.")


def _add_run_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-dir",
        default=str(DEFAULT_RUN_DIR),
        help="Active run directory (default: bootstrap run)",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="aitrader", description="Macro AI Trader CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create run workspace layout")
    _add_run_dir(init_p)
    init_p.add_argument("--capital-usd", type=int, default=10000)
    init_p.set_defaults(func=_cmd_init)

    uni_p = sub.add_parser("universe", help="Universe commands")
    uni_sub = uni_p.add_subparsers(dest="universe_cmd", required=True)
    build_p = uni_sub.add_parser("build", help="Build sector universe CSV")
    _add_run_dir(build_p)
    build_p.add_argument("--stocks-per-sector", type=int, default=10)
    build_p.add_argument("--sectors-min", type=int, default=8)
    build_p.set_defaults(func=_cmd_universe_build)

    data_p = sub.add_parser("data", help="Data ingest commands")
    data_sub = data_p.add_subparsers(dest="data_cmd", required=True)
    yahoo_p = data_sub.add_parser("yahoo", help="Yahoo OHLCV ingest for universe")
    _add_run_dir(yahoo_p)
    yahoo_p.add_argument("--years", type=float, default=5)
    yahoo_p.set_defaults(func=_cmd_data_yahoo)

    l1_p = sub.add_parser("l1", help="Run L1 end-to-end (init + universe + yahoo)")
    _add_run_dir(l1_p)
    l1_p.add_argument("--capital-usd", type=int, default=10000)
    l1_p.add_argument("--years", type=float, default=5)
    l1_p.add_argument("--stocks-per-sector", type=int, default=10)
    l1_p.set_defaults(func=_cmd_l1)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

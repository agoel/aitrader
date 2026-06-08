"""AITrader CLI — L1/L2/L3 scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aitrader.data.yahoo import ingest_universe
from aitrader.ml.drift import run_drift_detection
from aitrader.nlp.cluster import fit_news_clusters
from aitrader.nlp.keywords import discover_sector_keywords
from aitrader.nlp.cursor_extract import (
    apply_all_cursor_batches,
    apply_cursor_batch,
    fill_cursor_batches,
    finalize_cursor_keywords,
    prepare_cursor_batches,
)
from aitrader.nlp.news import ingest_news
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


def _cmd_news_ingest(args: argparse.Namespace) -> None:
    path, count = ingest_news(
        args.run_dir,
        window_days=args.window_days,
        yahoo_universe=args.yahoo_universe,
    )
    print(f"Wrote {path} ({count} articles)")


def _cmd_keywords_prepare_cursor(args: argparse.Namespace) -> None:
    batches_dir, count = prepare_cursor_batches(
        args.run_dir,
        batch_size=args.batch_size,
        limit=args.limit,
        force=args.force,
    )
    print(f"Prepared {count} Cursor batches under {batches_dir}")
    print("Open batch .md files in Cursor; agent writes batch_NNN_out.json; then apply-cursor.")


def _cmd_keywords_apply_cursor(args: argparse.Namespace) -> None:
    count, path = apply_cursor_batch(args.run_dir, args.batch)
    print(f"Applied batch {args.batch}: {count} articles → {path}")


def _cmd_keywords_apply_all_cursor(args: argparse.Namespace) -> None:
    total, applied = apply_all_cursor_batches(args.run_dir)
    print(f"Applied {len(applied)} batches ({total} articles): {applied}")


def _cmd_keywords_fill_cursor(args: argparse.Namespace) -> None:
    filled, articles = fill_cursor_batches(args.run_dir, overwrite=args.overwrite)
    print(f"Filled {filled} batch outputs ({articles} articles)")


def _cmd_keywords_run_cursor(args: argparse.Namespace) -> None:
    """Prepare → fill (agent policy) → apply-all → finalize → discover."""
    prepare_cursor_batches(
        args.run_dir,
        batch_size=args.batch_size,
        limit=args.limit,
        force=args.force,
    )
    if args.fill:
        fill_cursor_batches(args.run_dir, overwrite=args.force)
    total, applied = apply_all_cursor_batches(args.run_dir)
    print(f"Applied {len(applied)} batches ({total} articles) with existing *_out.json")
    if total == 0:
        print(
            "No batch_*_out.json files yet. Cursor agent must write outputs, then re-run:\n"
            "  python -m aitrader keywords apply-all-cursor --run-dir <run>\n"
            "  python -m aitrader keywords finalize-cursor --run-dir <run>\n"
            "  python -m aitrader keywords discover --run-dir <run>"
        )
        return
    _cmd_keywords_finalize_cursor(args)
    _cmd_keywords_discover(args)


def _cmd_keywords_finalize_cursor(args: argparse.Namespace) -> None:
    summary = finalize_cursor_keywords(args.run_dir)
    print(json.dumps(summary, indent=2))


def _cmd_keywords_extract_openai(args: argparse.Namespace) -> None:
    from aitrader.nlp.llm_extract import extract_llm_keywords

    path, count = extract_llm_keywords(
        args.run_dir,
        batch_size=args.batch_size,
        limit=args.limit,
        model=args.model,
        force=args.force,
    )
    print(f"Wrote {count} rows to {path}")


def _cmd_keywords_discover(args: argparse.Namespace) -> None:
    paths, report = discover_sector_keywords(
        args.run_dir,
        label_horizon=args.horizon,
        min_keyword_ic=args.min_ic,
        use_llm=not args.no_llm,
    )
    print(f"Wrote {len(paths)} keyword maps")
    print(f"Wrote {report}")


def _cmd_drift_run(args: argparse.Namespace) -> None:
    report, refresh = run_drift_detection(
        args.run_dir,
        drift_threshold=args.threshold,
        eval_window_days=args.eval_days,
        baseline_window_days=args.baseline_days,
        require_consecutive=not args.no_consecutive,
    )
    print(f"Wrote {report}")
    print(f"refresh_recommended={refresh}")


def _cmd_cluster_fit(args: argparse.Namespace) -> None:
    model, current, report = fit_news_clusters(
        args.run_dir,
        news_window_days=args.window_days,
        cluster_k=args.cluster_k,
    )
    print(f"Wrote {model}")
    print(f"Wrote {current}")
    print(f"Wrote {report}")


def _cmd_l3(args: argparse.Namespace) -> None:
    """Run L3: drift detection → optional keyword refresh → news clustering."""
    _cmd_drift_run(args)
    meta_path = Path(args.run_dir).expanduser().resolve() / "meta.json"
    if meta_path.exists():
        import json

        meta = json.loads(meta_path.read_text())
        if meta.get("drift", {}).get("refresh_recommended"):
            print("Drift refresh recommended — re-running keyword discovery.")
            _cmd_keywords_discover(args)
    _cmd_cluster_fit(args)
    update_meta(
        args.run_dir,
        {"layer": "L3", "L3": {"status": "completed"}},
    )
    print("L3 complete.")


def _cmd_l2(args: argparse.Namespace) -> None:
    """Run L2: news ingest → keyword discovery."""
    _cmd_news_ingest(args)
    _cmd_keywords_discover(args)
    update_meta(
        args.run_dir,
        {"layer": "L2", "L2": {"status": "completed"}},
    )
    print("L2 complete.")


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

    news_p = sub.add_parser("news", help="News ingest commands")
    news_sub = news_p.add_subparsers(dest="news_cmd", required=True)
    ingest_p = news_sub.add_parser("ingest", help="Ingest macro news to jsonl")
    _add_run_dir(ingest_p)
    ingest_p.add_argument("--window-days", type=int, default=7)
    ingest_p.add_argument("--yahoo-universe", action="store_true", help="Fetch Yahoo news for full universe")
    ingest_p.set_defaults(func=_cmd_news_ingest)

    kw_p = sub.add_parser("keywords", help="Keyword discovery commands")
    kw_sub = kw_p.add_subparsers(dest="kw_cmd", required=True)
    prep_p = kw_sub.add_parser(
        "prepare-cursor",
        help="Prepare Cursor agent batch briefs (primary — no API key)",
    )
    _add_run_dir(prep_p)
    prep_p.add_argument("--batch-size", type=int, default=8)
    prep_p.add_argument("--limit", type=int, default=None)
    prep_p.add_argument("--force", action="store_true")
    prep_p.set_defaults(func=_cmd_keywords_prepare_cursor)

    apply_p = kw_sub.add_parser("apply-cursor", help="Apply Cursor-written batch JSON to cache")
    _add_run_dir(apply_p)
    apply_p.add_argument("--batch", type=int, required=True)
    apply_p.set_defaults(func=_cmd_keywords_apply_cursor)

    apply_all_p = kw_sub.add_parser(
        "apply-all-cursor",
        help="Apply all Cursor-written batch_*_out.json files",
    )
    _add_run_dir(apply_all_p)
    apply_all_p.add_argument("--horizon", default="1m", choices=["2w", "1m", "3m"])
    apply_all_p.add_argument("--min-ic", type=float, default=0.03)
    apply_all_p.set_defaults(func=_cmd_keywords_apply_all_cursor)

    run_p = kw_sub.add_parser(
        "run-cursor",
        help="Prepare batches; apply-all if *_out.json exist; finalize + discover",
    )
    _add_run_dir(run_p)
    run_p.add_argument("--batch-size", type=int, default=8)
    run_p.add_argument("--limit", type=int, default=None)
    run_p.add_argument("--force", action="store_true")
    run_p.add_argument(
        "--no-fill",
        dest="fill",
        action="store_false",
        help="Skip agent policy fill; expect hand-written batch_*_out.json",
    )
    run_p.set_defaults(fill=True)
    run_p.add_argument("--horizon", default="1m", choices=["2w", "1m", "3m"])
    run_p.add_argument("--min-ic", type=float, default=0.03)
    run_p.add_argument("--no-llm", action="store_true", help="Token fallback only at discover step")
    run_p.set_defaults(func=_cmd_keywords_run_cursor, no_llm=False)

    fill_p = kw_sub.add_parser(
        "fill-cursor",
        help="Cursor agent writes batch_*_out.json from policy (macro phrases)",
    )
    _add_run_dir(fill_p)
    fill_p.add_argument("--overwrite", action="store_true")
    fill_p.set_defaults(func=_cmd_keywords_fill_cursor)

    fin_p = kw_sub.add_parser("finalize-cursor", help="Summarize Cursor keyword extraction progress")
    _add_run_dir(fin_p)
    fin_p.set_defaults(func=_cmd_keywords_finalize_cursor)

    oai_p = kw_sub.add_parser(
        "extract-openai",
        help="Optional: OpenAI API extraction (comparison track)",
    )
    _add_run_dir(oai_p)
    oai_p.add_argument("--batch-size", type=int, default=8)
    oai_p.add_argument("--limit", type=int, default=None)
    oai_p.add_argument("--model", default=None)
    oai_p.add_argument("--force", action="store_true")
    oai_p.set_defaults(func=_cmd_keywords_extract_openai)

    disc_p = kw_sub.add_parser("discover", help="Discover sentiment keywords per sector")
    _add_run_dir(disc_p)
    disc_p.add_argument("--horizon", default="1m", choices=["2w", "1m", "3m"])
    disc_p.add_argument("--min-ic", type=float, default=0.03)
    disc_p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Cursor keyword cache; use token extraction only",
    )
    disc_p.set_defaults(func=_cmd_keywords_discover)

    l2_p = sub.add_parser("l2", help="Run L2 end-to-end (news + keywords)")
    _add_run_dir(l2_p)
    l2_p.add_argument("--window-days", type=int, default=7)
    l2_p.add_argument("--yahoo-universe", action=argparse.BooleanOptionalAction, default=True)
    l2_p.add_argument("--horizon", default="1m", choices=["2w", "1m", "3m"])
    l2_p.add_argument("--min-ic", type=float, default=0.03)
    l2_p.set_defaults(func=_cmd_l2)

    drift_p = sub.add_parser("drift", help="Concept drift commands")
    drift_sub = drift_p.add_subparsers(dest="drift_cmd", required=True)
    drift_run_p = drift_sub.add_parser("run", help="Run drift detection")
    _add_run_dir(drift_run_p)
    drift_run_p.add_argument("--threshold", type=float, default=0.15)
    drift_run_p.add_argument("--eval-days", type=int, default=63)
    drift_run_p.add_argument("--baseline-days", type=int, default=252)
    drift_run_p.add_argument(
        "--no-consecutive",
        action="store_true",
        help="Recommend refresh on first threshold breach (skip 2-run guard)",
    )
    drift_run_p.set_defaults(func=_cmd_drift_run)

    cluster_p = sub.add_parser("cluster", help="News clustering commands")
    cluster_sub = cluster_p.add_subparsers(dest="cluster_cmd", required=True)
    cluster_fit_p = cluster_sub.add_parser("fit", help="Fit news clusters and assign current regime")
    _add_run_dir(cluster_fit_p)
    cluster_fit_p.add_argument("--window-days", type=int, default=7)
    cluster_fit_p.add_argument("--cluster-k", type=int, default=12)
    cluster_fit_p.set_defaults(func=_cmd_cluster_fit)

    l3_p = sub.add_parser("l3", help="Run L3 end-to-end (drift + cluster + optional refresh)")
    _add_run_dir(l3_p)
    l3_p.add_argument("--threshold", type=float, default=0.15)
    l3_p.add_argument("--eval-days", type=int, default=63)
    l3_p.add_argument("--baseline-days", type=int, default=252)
    l3_p.add_argument("--no-consecutive", action="store_true")
    l3_p.add_argument("--window-days", type=int, default=7)
    l3_p.add_argument("--cluster-k", type=int, default=12)
    l3_p.add_argument("--horizon", default="1m", choices=["2w", "1m", "3m"])
    l3_p.add_argument("--min-ic", type=float, default=0.03)
    l3_p.set_defaults(func=_cmd_l3)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

"""AITrader CLI — L1/L2/L3/L4 scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aitrader.data.yahoo import ingest_universe
from aitrader.ml.drift import run_drift_detection
from aitrader.ml.backtest import run_prediction_backtest
from aitrader.ml.option_range_study import run_option_range_study
from aitrader.ml.portfolio_backtest import compare_portfolio_schedules, run_spy_portfolio_backtest
from aitrader.ml.learn_predict import run_prediction_tune
from aitrader.ml.predict import run_predictions, train_horizon_models
from aitrader.nlp.cluster import fit_news_clusters
from aitrader.nlp.keywords import discover_sector_keywords
from aitrader.nlp.cursor_extract import (
    apply_all_cursor_batches,
    apply_cursor_batch,
    fill_cursor_batches,
    fill_pending_keywords,
    finalize_cursor_keywords,
    prepare_cursor_batches,
)
from aitrader.nlp.news import ingest_historical_news, ingest_news
from aitrader.universe import write_universe
from aitrader.progress import pipeline_phase
from aitrader.agent_rsi import log_agent_rsi, probe_backtest_performance, seed_session_improvements
from aitrader.workspace import ensure_run_layout, update_meta


def _add_quiet(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress lines (status file still updated)",
    )

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


def _cmd_data_cot(args: argparse.Namespace) -> None:
    from aitrader.data.cot import ingest_cot

    path = ingest_cot(args.run_dir, years=getattr(args, "years", 6))
    print(f"Wrote {path}")


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


def _cmd_news_ingest_historical(args: argparse.Namespace) -> None:
    path, count = ingest_historical_news(
        args.run_dir,
        timespan=args.timespan,
        rss_window_days=args.rss_window_days,
        include_gdelt=not args.no_gdelt,
        include_gkg=not args.no_gkg,
        include_gnews=not args.no_gnews,
        include_rss=not args.no_rss,
        gkg_lookback_days=args.gkg_lookback_days,
        gkg_sample_days=args.gkg_sample_days,
    )
    print(f"Historical ingest → {path} ({count} new articles this pass)")


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
    total, applied = apply_all_cursor_batches(
        args.run_dir,
        workers=getattr(args, "workers", None),
        quiet=args.quiet,
    )
    print(f"Applied {len(applied)} batches ({total} articles): {applied}")


def _cmd_keywords_fill_cursor(args: argparse.Namespace) -> None:
    if args.pending_only:
        filled, path = fill_pending_keywords(
            args.run_dir,
            workers=getattr(args, "workers", None),
            quiet=args.quiet,
        )
        print(f"Parallel fill: {filled} uncached articles → {path}")
        return
    filled, articles = fill_cursor_batches(
        args.run_dir,
        overwrite=args.overwrite,
        workers=getattr(args, "workers", None),
        quiet=args.quiet,
    )
    print(f"Filled {filled} batch outputs ({articles} articles)")


def _cmd_keywords_run_cursor(args: argparse.Namespace) -> None:
    """Prepare → parallel fill → apply-all → finalize → discover."""
    run = args.run_dir
    quiet = args.quiet
    steps = 5 if args.fill else 3
    with pipeline_phase(run, "keywords.run-cursor", "prepare_batches", 1, steps, quiet=quiet):
        batches, n_batches = prepare_cursor_batches(
            run,
            batch_size=args.batch_size,
            limit=args.limit,
            force=args.force,
        )
        if not quiet:
            print(f"Prepared {n_batches} batches under {batches}")
    if args.fill:
        with pipeline_phase(run, "keywords.run-cursor", "fill_pending", 2, steps, quiet=quiet):
            n, _ = fill_pending_keywords(
                run,
                workers=getattr(args, "workers", None),
                quiet=quiet,
            )
            if not quiet:
                print(f"Parallel keyword extract: {n} uncached articles")
        with pipeline_phase(run, "keywords.run-cursor", "fill_batches", 3, steps, quiet=quiet):
            fill_cursor_batches(
                run,
                overwrite=args.force,
                workers=getattr(args, "workers", None),
                quiet=quiet,
            )
        step_apply = 4
    else:
        step_apply = 2
    total = 0
    applied: list[int] = []
    with pipeline_phase(run, "keywords.run-cursor", "apply_batches", step_apply, steps, quiet=quiet):
        total, applied = apply_all_cursor_batches(
            run,
            workers=getattr(args, "workers", None),
            quiet=quiet,
        )
        if not quiet:
            print(f"Applied {len(applied)} batches ({total} articles)")
    if total == 0:
        print(
            "No batch_*_out.json files yet. Cursor agent must write outputs, then re-run:\n"
            "  python -m aitrader keywords apply-all-cursor --run-dir <run>\n"
            "  python -m aitrader keywords finalize-cursor --run-dir <run>\n"
            "  python -m aitrader keywords discover --run-dir <run>"
        )
        return
    with pipeline_phase(
        run,
        "keywords.run-cursor",
        "finalize",
        step_apply + 1,
        steps,
        quiet=quiet,
    ):
        _cmd_keywords_finalize_cursor(args)
    with pipeline_phase(
        run,
        "keywords.run-cursor",
        "discover",
        steps,
        steps,
        quiet=quiet,
    ):
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
        workers=getattr(args, "workers", None),
        quiet=args.quiet,
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


def _cmd_predict_run(args: argparse.Namespace) -> None:
    path = run_predictions(
        args.run_dir,
        horizons=tuple(args.horizons.split(",")),
        news_window_days=args.window_days,
        retrain=args.retrain,
    )
    print(f"Wrote {path}")


def _cmd_predict_backtest(args: argparse.Namespace) -> None:
    csv_path, report = run_prediction_backtest(
        args.run_dir,
        horizons=tuple(args.horizons.split(",")),
        news_window_days=args.window_days,
        min_train_days=args.min_train_days,
        include_monthly_spy=not args.no_monthly_spy,
        include_walk_forward=args.walk_forward,
        quiet=args.quiet,
        run_probe=not args.skip_probe,
    )
    print(f"Wrote {csv_path}")
    print(f"Wrote {report}")


def _cmd_option_range_study(args: argparse.Namespace) -> None:
    df, summary, report = run_option_range_study(
        args.run_dir,
        news_window_days=args.window_days,
        lookback_years=args.years,
        min_train_months=args.min_train_months,
        eval_start=getattr(args, "start", None),
        eval_end=getattr(args, "end", None),
    )
    print(f"Wrote {report}")
    print(
        f"Expiry-aligned: {summary['n_expiry_cycles']} cycles | "
        f"inside band {summary['inside_band_pct']}% | "
        f"breach lower {summary['breach_lower_pct']}% | "
        f"breach upper {summary['breach_upper_pct']}%"
    )
    if "csp_at_model_lower_assigned_pct" in summary:
        print(
            f"CSP at model lower: assigned {summary['csp_at_model_lower_assigned_pct']}% of months"
        )
        for buf in (2, 5):
            k = f"csp_assigned_{buf}pct_buffer_pct"
            if k in summary:
                print(f"  with {buf}% OTM buffer: assigned {summary[k]}%")


def _cmd_portfolio_schedule_compare(args: argparse.Namespace) -> None:
    report, comparison = compare_portfolio_schedules(
        args.run_dir,
        capital_usd=args.capital_usd,
        lookback_years=args.years,
        news_window_days=args.window_days,
        min_train_months=args.min_train_months,
    )
    bh = comparison["buy_hold"]
    monthly = comparison["monthly_signal"]
    ladder = comparison["weekly_ladder_always"]
    print(f"Wrote {report}")
    print(
        f"Buy & hold: ${bh['final_value_usd']:,.2f} ({bh['total_return_pct']:+.2f}%)"
    )
    print(
        f"Monthly signal: ${monthly['final_value_usd']:,.2f} "
        f"({monthly['total_return_pct']:+.2f}%, {monthly['excess_return_pct']:+.2f} pp vs B&H)"
    )
    print(
        f"Weekly ladder (always): ${ladder['final_value_usd']:,.2f} "
        f"({ladder['total_return_pct']:+.2f}%, {ladder['excess_return_pct']:+.2f} pp vs B&H)"
    )
    sig = comparison["weekly_ladder_signal"]
    print(
        f"Weekly ladder (signal): ${sig['final_value_usd']:,.2f} "
        f"({sig['total_return_pct']:+.2f}%, {sig['excess_return_pct']:+.2f} pp vs B&H)"
    )


def _cmd_portfolio_backtest_spy(args: argparse.Namespace) -> None:
    ledger, report, summary = run_spy_portfolio_backtest(
        args.run_dir,
        capital_usd=args.capital_usd,
        lookback_years=args.years,
        news_window_days=args.window_days,
        min_train_months=args.min_train_months,
    )
    print(f"Wrote {ledger}")
    print(f"Wrote {report}")
    print(
        f"Strategy: ${summary['final_value_usd']:,.2f} ({summary['total_return_pct']:+.2f}%) "
        f"vs buy-hold ${summary['buy_hold_final_usd']:,.2f} "
        f"({summary['buy_hold_return_pct']:+.2f}%) over {summary['months']} months"
    )


def _cmd_predict_train(args: argparse.Namespace) -> None:
    models = train_horizon_models(args.run_dir, horizons=tuple(args.horizons.split(",")))
    print(f"Trained {len(models)} horizon models")


def _cmd_predict_tune(args: argparse.Namespace) -> None:
    summary = run_prediction_tune(
        args.run_dir,
        max_rounds=args.max_rounds,
        news_window_days=args.window_days,
        use_grid=not args.no_grid,
        run_probe=not args.skip_probe,
        objective=args.objective,
    )
    print(json.dumps(summary, indent=2))
    tier = summary.get("certainty", "low")
    if summary.get("passes"):
        print(f"Tune stop: objective gates passed (tier={tier}).")
    else:
        print(f"Tune stop: grid complete — best config saved (tier={tier}).")


def _cmd_predict_rsi(args: argparse.Namespace) -> None:
    import warnings

    warnings.warn(
        "predict rsi is deprecated; use: python -m aitrader predict tune",
        DeprecationWarning,
        stacklevel=2,
    )
    _cmd_predict_tune(args)


def _cmd_agent_rsi_probe(args: argparse.Namespace) -> None:
    report = probe_backtest_performance(
        args.run_dir,
        slice_months=args.slice_months,
        slice_macro_days=args.slice_macro_days,
        budget_sec=args.budget_sec,
        news_window_days=args.window_days,
        quiet=args.quiet,
    )
    print(json.dumps(report, indent=2))
    if not report.get("passes_gate"):
        raise SystemExit(1)


def _cmd_agent_rsi_log(args: argparse.Namespace) -> None:
    path = log_agent_rsi(
        args.run_dir,
        args.topic,
        symptom=args.symptom,
        fix=args.fix,
        verify=args.verify or "",
    )
    print(f"Wrote {path}")


def _cmd_agent_rsi_seed(args: argparse.Namespace) -> None:
    paths = seed_session_improvements(args.run_dir)
    print(f"Seeded {len(paths)} agent RSI entries")
    for p in paths:
        print(f"  {p}")


def _cmd_l4(args: argparse.Namespace) -> None:
    """Run L4: train → predict → backtest → self-learning tune."""
    _cmd_predict_run(args)
    if not args.skip_backtest:
        _cmd_predict_backtest(args)
    skip_tune = getattr(args, "skip_tune", False) or getattr(args, "skip_rsi", False)
    if not skip_tune:
        _cmd_predict_tune(args)
    print("L4 complete.")


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

    cot_p = data_sub.add_parser("cot", help="CFTC Commitment of Traders (E-mini S&P 500)")
    _add_run_dir(cot_p)
    cot_p.add_argument("--years", type=float, default=6)
    cot_p.set_defaults(func=_cmd_data_cot)

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

    hist_p = news_sub.add_parser(
        "ingest-historical",
        help="Ingest dated historical macro news (GKG bulk + GDELT + Google News + RSS)",
    )
    _add_run_dir(hist_p)
    hist_p.add_argument("--timespan", default="90days", help="GDELT DOC timespan (max ~3 months)")
    hist_p.add_argument("--rss-window-days", type=int, default=365)
    hist_p.add_argument("--gkg-lookback-days", type=int, default=None, help="GKG bulk days (default 1825)")
    hist_p.add_argument("--gkg-sample-days", type=int, default=None, help="GKG sample every N days (default 7)")
    hist_p.add_argument("--no-gkg", action="store_true", help="Skip GDELT GKG bulk backfill")
    hist_p.add_argument("--no-gdelt", action="store_true", help="Skip GDELT DOC API")
    hist_p.add_argument("--no-gnews", action="store_true", help="Skip Google News macro RSS")
    hist_p.add_argument("--no-rss", action="store_true")
    hist_p.set_defaults(func=_cmd_news_ingest_historical)

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
    apply_all_p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel workers for batch apply (default: min(8, cpu_count))",
    )
    _add_quiet(apply_all_p)
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
    run_p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel workers for fill/apply (default: min(8, cpu_count))",
    )
    _add_quiet(run_p)
    run_p.set_defaults(func=_cmd_keywords_run_cursor, no_llm=False)

    fill_p = kw_sub.add_parser(
        "fill-cursor",
        help="Cursor agent writes batch_*_out.json from policy (macro phrases)",
    )
    _add_run_dir(fill_p)
    fill_p.add_argument("--overwrite", action="store_true")
    fill_p.add_argument(
        "--pending-only",
        action="store_true",
        help="Parallel extract for uncached corpus only (fast path)",
    )
    fill_p.add_argument("--workers", type=int, default=None)
    _add_quiet(fill_p)
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
    disc_p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel sector workers for IC discovery (default: min(8, cpu_count))",
    )
    _add_quiet(disc_p)
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

    agent_rsi_p = sub.add_parser(
        "agent-rsi",
        help="Agent-brain RSI: perf probes and improvement logs (not domain tune)",
    )
    agent_rsi_sub = agent_rsi_p.add_subparsers(dest="agent_rsi_cmd", required=True)
    ar_probe_p = agent_rsi_sub.add_parser(
        "probe",
        help="Slice-first backtest perf probe (blocks if extrapolation too slow)",
    )
    _add_run_dir(ar_probe_p)
    ar_probe_p.add_argument("--window-days", type=int, default=30)
    ar_probe_p.add_argument("--slice-months", type=int, default=3)
    ar_probe_p.add_argument("--slice-macro-days", type=int, default=10)
    ar_probe_p.add_argument("--budget-sec", type=float, default=60.0)
    _add_quiet(ar_probe_p)
    ar_probe_p.set_defaults(func=_cmd_agent_rsi_probe)

    ar_log_p = agent_rsi_sub.add_parser("log", help="Append agent RSI improvement entry")
    _add_run_dir(ar_log_p)
    ar_log_p.add_argument("--topic", required=True)
    ar_log_p.add_argument("--symptom", required=True)
    ar_log_p.add_argument("--fix", required=True)
    ar_log_p.add_argument("--verify", default="")
    ar_log_p.set_defaults(func=_cmd_agent_rsi_log)

    ar_seed_p = agent_rsi_sub.add_parser(
        "seed",
        help="Write idempotent log entries for shipped perf/agent improvements",
    )
    _add_run_dir(ar_seed_p)
    ar_seed_p.set_defaults(func=_cmd_agent_rsi_seed)

    predict_p = sub.add_parser("predict", help="Multi-horizon prediction commands")
    predict_sub = predict_p.add_subparsers(dest="predict_cmd", required=True)
    predict_run_p = predict_sub.add_parser("run", help="Score universe at 2w/1m/3m horizons")
    _add_run_dir(predict_run_p)
    predict_run_p.add_argument("--horizons", default="2w,1m,3m")
    predict_run_p.add_argument("--window-days", type=int, default=7)
    predict_run_p.add_argument("--retrain", action="store_true", help="Force retrain horizon models")
    predict_run_p.set_defaults(func=_cmd_predict_run)

    predict_train_p = predict_sub.add_parser("train", help="Train per-horizon Ridge models only")
    _add_run_dir(predict_train_p)
    predict_train_p.add_argument("--horizons", default="2w,1m,3m")
    predict_train_p.set_defaults(func=_cmd_predict_train)

    predict_bt_p = predict_sub.add_parser(
        "backtest",
        help="Walk-forward backtest: keyword/cluster sentiment vs realized returns",
    )
    _add_run_dir(predict_bt_p)
    predict_bt_p.add_argument("--horizons", default="2w,1m,3m")
    predict_bt_p.add_argument("--window-days", type=int, default=7)
    predict_bt_p.add_argument("--min-train-days", type=int, default=3)
    predict_bt_p.add_argument(
        "--no-monthly-spy",
        action="store_true",
        help="Skip monthly SPY walk-forward (OHLCV + point-in-time news)",
    )
    predict_bt_p.add_argument(
        "--walk-forward",
        action="store_true",
        help="Also run article-level walk-forward (slow on large corpus)",
    )
    predict_bt_p.add_argument(
        "--skip-probe",
        action="store_true",
        help="Skip agent RSI perf probe before full backtest",
    )
    _add_quiet(predict_bt_p)
    predict_bt_p.set_defaults(func=_cmd_predict_backtest)

    predict_tune_p = predict_sub.add_parser(
        "tune",
        help="Self-learning: tune prediction config until objective gates pass",
    )
    _add_run_dir(predict_tune_p)
    predict_tune_p.add_argument("--window-days", type=int, default=30)
    predict_tune_p.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Max configs to try (0 = full grid)",
    )
    predict_tune_p.add_argument("--no-grid", action="store_true")
    predict_tune_p.add_argument(
        "--skip-probe",
        action="store_true",
        help="Skip agent RSI perf probe before tune grid",
    )
    predict_tune_p.add_argument(
        "--objective",
        choices=("profit", "composite", "ic"),
        default="composite",
        help="Config selection: profit=max $10K SPY sim, composite=balanced, ic=forecast IC",
    )
    predict_tune_p.set_defaults(func=_cmd_predict_tune)

    predict_rsi_p = predict_sub.add_parser(
        "rsi",
        help="(deprecated) alias for predict tune",
    )
    _add_run_dir(predict_rsi_p)
    predict_rsi_p.add_argument("--window-days", type=int, default=30)
    predict_rsi_p.add_argument("--max-rounds", type=int, default=0)
    predict_rsi_p.add_argument("--no-grid", action="store_true")
    predict_rsi_p.add_argument("--skip-probe", action="store_true")
    predict_rsi_p.set_defaults(func=_cmd_predict_rsi)

    predict_pf_p = predict_sub.add_parser(
        "portfolio-backtest",
        help="SPY-only $10K portfolio simulation from monthly news predictions (5y)",
    )
    _add_run_dir(predict_pf_p)
    predict_pf_p.add_argument("--capital-usd", type=float, default=10000)
    predict_pf_p.add_argument("--years", type=int, default=5, help="Lookback years for month-ends")
    predict_pf_p.add_argument("--window-days", type=int, default=30)
    predict_pf_p.add_argument("--min-train-months", type=int, default=12)
    predict_pf_p.set_defaults(func=_cmd_portfolio_backtest_spy)

    predict_cmp_p = predict_sub.add_parser(
        "schedule-compare",
        help="Compare monthly signal vs weekly 25% ladder vs buy-and-hold (same period)",
    )
    _add_run_dir(predict_cmp_p)
    predict_cmp_p.add_argument("--capital-usd", type=float, default=10000)
    predict_cmp_p.add_argument("--years", type=int, default=5)
    predict_cmp_p.add_argument("--window-days", type=int, default=30)
    predict_cmp_p.add_argument("--min-train-months", type=int, default=12)
    predict_cmp_p.set_defaults(func=_cmd_portfolio_schedule_compare)

    predict_range_p = predict_sub.add_parser(
        "option-range",
        help="Confidence price bands vs SPY at monthly option expiry (3rd Friday)",
    )
    _add_run_dir(predict_range_p)
    predict_range_p.add_argument("--years", type=int, default=5)
    predict_range_p.add_argument("--window-days", type=int, default=30)
    predict_range_p.add_argument("--min-train-months", type=int, default=12)
    predict_range_p.add_argument(
        "--start",
        default=None,
        help="Evaluation start (YYYY-MM-DD), e.g. 2005-01-01",
    )
    predict_range_p.add_argument(
        "--end",
        default=None,
        help="Evaluation end (YYYY-MM-DD), e.g. 2015-12-31",
    )
    predict_range_p.set_defaults(func=_cmd_option_range_study)

    l4_p = sub.add_parser("l4", help="Run L4 end-to-end (predict + backtest + tune)")
    _add_run_dir(l4_p)
    l4_p.add_argument("--horizons", default="2w,1m,3m")
    l4_p.add_argument("--window-days", type=int, default=7)
    l4_p.add_argument("--retrain", action="store_true")
    l4_p.add_argument("--min-train-days", type=int, default=3)
    l4_p.add_argument("--no-monthly-spy", action="store_true")
    l4_p.add_argument("--skip-backtest", action="store_true")
    l4_p.add_argument("--skip-tune", action="store_true", help="Skip self-learning tune step")
    l4_p.add_argument(
        "--skip-rsi",
        action="store_true",
        help="(deprecated) alias for --skip-tune",
    )
    l4_p.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Tune configs to try (0 = full grid; passed to predict tune)",
    )
    l4_p.add_argument("--no-grid", action="store_true")
    l4_p.add_argument(
        "--skip-probe",
        action="store_true",
        help="Skip agent RSI perf probe before backtest/tune",
    )
    l4_p.set_defaults(func=_cmd_l4)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

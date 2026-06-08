"""Yahoo Finance OHLCV ingest — Recipe — Yahoo Finance historical data ingest."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from aitrader.workspace import ensure_run_layout

OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume", "adj_close"]


def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]

    raw = raw.reset_index()
    date_col = "date" if "date" in raw.columns else raw.columns[0]
    raw = raw.rename(
        columns={
            date_col: "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "adj close": "adj_close",
            "adj_close": "adj_close",
        }
    )
    raw["date"] = pd.to_datetime(raw["date"]).dt.tz_localize(None)
    for col in OHLCV_COLUMNS:
        if col not in raw.columns:
            raw[col] = pd.NA
    out = raw[OHLCV_COLUMNS].sort_values("date").reset_index(drop=True)
    return _forward_fill_single_gaps(out)


def _forward_fill_single_gaps(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 2:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    gaps: list[int] = []
    for i in range(1, len(df)):
        delta = (df.loc[i, "date"] - df.loc[i - 1, "date"]).days
        if delta > 1:
            gaps.append(delta - 1)
    if gaps and max(gaps) == 1:
        df = df.set_index("date").asfreq("B", method="ffill").reset_index()
        df = df.rename(columns={"index": "date"})
    return df


def fetch_ohlcv(ticker: str, years: float = 5, interval: str = "1d") -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(years * 365.25))
    raw = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return _normalize_frame(raw)


def save_ohlcv(df: pd.DataFrame, out_path: str | Path) -> Path:
    path = Path(out_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def ingest_ticker(
    ticker: str,
    out_dir: str | Path,
    *,
    years: float = 5,
    sleep_s: float = 0.5,
) -> dict[str, Any]:
    out_dir = Path(out_dir).expanduser().resolve()
    out_path = out_dir / f"{ticker.upper()}.parquet"
    df = fetch_ohlcv(ticker, years=years)
    if df.empty:
        return {"ticker": ticker, "status": "empty", "rows": 0, "path": str(out_path)}
    save_ohlcv(df, out_path)
    if sleep_s:
        time.sleep(sleep_s)
    return {
        "ticker": ticker.upper(),
        "status": "ok",
        "rows": len(df),
        "start_date": str(df["date"].min().date()),
        "end_date": str(df["date"].max().date()),
        "path": str(out_path),
    }


def ingest_universe(
    run_dir: str | Path,
    *,
    years: float = 5,
    tickers: list[str] | None = None,
    batch_pause: int = 20,
    sleep_s: float = 0.5,
) -> Path:
    """Pull OHLCV for all universe tickers; write ohlcv_manifest.json."""
    root = ensure_run_layout(run_dir)
    ohlcv_dir = root / "data" / "ohlcv"

    if tickers is None:
        from aitrader.universe import load_universe_tickers

        tickers = load_universe_tickers(root)

    manifest: dict[str, Any] = {
        "provider": "yahoo",
        "years": years,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "tickers": {},
        "failures": [],
    }

    for i, ticker in enumerate(tickers, start=1):
        result = ingest_ticker(ticker, ohlcv_dir, years=years, sleep_s=sleep_s)
        if result["status"] == "ok":
            manifest["tickers"][ticker] = result
        else:
            manifest["failures"].append(result)
        if batch_pause and i % batch_pause == 0:
            time.sleep(2)

    manifest_path = root / "data" / "ohlcv_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def _cli_fetch_one(args: argparse.Namespace) -> None:
    df = fetch_ohlcv(args.ticker, years=args.years)
    if df.empty:
        raise SystemExit(f"No data returned for {args.ticker}")
    path = save_ohlcv(df, args.out)
    print(f"Wrote {len(df)} rows to {path}")


def _cli_ingest_run(args: argparse.Namespace) -> None:
    path = ingest_universe(args.run_dir, years=args.years)
    print(f"Wrote manifest to {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Yahoo Finance OHLCV ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("fetch", help="Fetch one ticker to parquet")
    one.add_argument("--ticker", required=True)
    one.add_argument("--years", type=float, default=5)
    one.add_argument("--out", required=True)
    one.set_defaults(func=_cli_fetch_one)

    run = sub.add_parser("ingest-run", help="Ingest all tickers in a run universe")
    run.add_argument("--run-dir", required=True)
    run.add_argument("--years", type=float, default=5)
    run.set_defaults(func=_cli_ingest_run)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

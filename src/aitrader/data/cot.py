"""CFTC Commitment of Traders (COT) — E-mini S&P 500 positioning."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.workspace import ensure_run_layout

CFTC_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
ES_MARKET_FILTER = "E-MINI S&P 500"
DEFAULT_LOOKBACK_YEARS = 6
ZSCORE_WINDOW = 52


def _fetch_cot_page(
    *,
    start_date: str,
    offset: int,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    where = (
        f"market_and_exchange_names like '%{ES_MARKET_FILTER}%' "
        f"AND report_date_as_yyyy_mm_dd >= '{start_date}'"
    )
    params = urllib.parse.urlencode(
        {
            "$where": where,
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": limit,
            "$offset": offset,
        }
    )
    url = f"{CFTC_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def fetch_es_cot_history(*, years: float = DEFAULT_LOOKBACK_YEARS) -> pd.DataFrame:
    """Pull weekly disaggregated COT for E-mini S&P 500 from CFTC open data."""
    start_year = datetime.now(timezone.utc).year - int(years)
    start_date = f"{start_year}-01-01"
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        try:
            batch = _fetch_cot_page(start_date=start_date, offset=offset, limit=page_size)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"CFTC COT fetch failed: {exc}") from exc
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
        time.sleep(0.25)
    if not rows:
        raise RuntimeError("CFTC COT fetch returned no rows for E-mini S&P 500")

    frame = pd.DataFrame(rows)
    frame["report_date"] = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"]).dt.normalize()
    for col in (
        "open_interest_all",
        "noncomm_positions_long_all",
        "noncomm_positions_short_all",
        "comm_positions_long_all",
        "comm_positions_short_all",
    ):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["report_date", "open_interest_all"])
    frame = frame.sort_values("report_date").drop_duplicates("report_date", keep="last")
    frame["net_spec"] = frame["noncomm_positions_long_all"] - frame["noncomm_positions_short_all"]
    frame["net_spec_pct_oi"] = frame["net_spec"] / frame["open_interest_all"].replace(0, np.nan)
    roll = frame["net_spec_pct_oi"].rolling(ZSCORE_WINDOW, min_periods=12)
    frame["cot_zscore"] = (frame["net_spec_pct_oi"] - roll.mean()) / roll.std().replace(0, np.nan)
    frame["cot_signal"] = frame["cot_zscore"].clip(-2.5, 2.5) / 2.5
    return frame[
        [
            "report_date",
            "open_interest_all",
            "net_spec",
            "net_spec_pct_oi",
            "cot_zscore",
            "cot_signal",
        ]
    ].reset_index(drop=True)


def ingest_cot(run_dir: str | Path, *, years: float = DEFAULT_LOOKBACK_YEARS) -> Path:
    """Download COT and write `data/cot/es_mini_cot.parquet` + manifest."""
    root = ensure_run_layout(run_dir)
    cot_dir = root / "data" / "cot"
    cot_dir.mkdir(parents=True, exist_ok=True)
    frame = fetch_es_cot_history(years=years)
    parquet_path = cot_dir / "es_mini_cot.parquet"
    frame.to_parquet(parquet_path, index=False)
    manifest = {
        "provider": "cftc_public_reporting",
        "market": ES_MARKET_FILTER,
        "years": years,
        "rows": len(frame),
        "start_date": frame["report_date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": frame["report_date"].iloc[-1].strftime("%Y-%m-%d"),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "path": str(parquet_path.relative_to(root)),
    }
    manifest_path = cot_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return parquet_path


def load_cot_frame(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "data" / "cot" / "es_mini_cot.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def ensure_cot_data(run_dir: Path, *, years: float = DEFAULT_LOOKBACK_YEARS) -> pd.DataFrame:
    """Load cached COT or ingest when missing."""
    frame = load_cot_frame(run_dir)
    if frame is not None and len(frame) >= 20:
        return frame
    ingest_cot(run_dir, years=years)
    frame = load_cot_frame(run_dir)
    if frame is None or frame.empty:
        raise RuntimeError("COT ingest failed — no es_mini_cot.parquet")
    return frame


def cot_signal_at(cot: pd.DataFrame, day: pd.Timestamp) -> float:
    """Latest COT signal on or before `day` (point-in-time)."""
    if cot is None or cot.empty:
        return 0.0
    ts = pd.Timestamp(day).normalize()
    eligible = cot[cot["report_date"] <= ts]
    if eligible.empty:
        return 0.0
    val = eligible.iloc[-1].get("cot_signal")
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0.0
    return float(val)

"""Sector universe builder — Recipe — Sector universe definition."""

from __future__ import annotations

import csv
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from aitrader.workspace import ensure_run_layout

UNIVERSE_COLUMNS = (
    "sector_id",
    "sector_name",
    "ticker",
    "name",
    "etf_proxy",
    "is_anchor",
    "weight_proxy",
)


def load_sector_starters(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        return yaml.safe_load(path.read_text())
    with resources.files("aitrader.config").joinpath("sector_starters.yaml").open() as fh:
        return yaml.safe_load(fh)


def build_sectors_yaml(starters: dict[str, Any]) -> dict[str, Any]:
    sectors_out = []
    for sector in starters.get("sectors", []):
        sectors_out.append(
            {
                "id": sector["id"],
                "name": sector["name"],
                "etf_proxy": sector["etf_proxy"],
                "stock_count": len(sector.get("stocks", [])),
            }
        )
    return {
        "anchors": starters.get("anchors", []),
        "sectors": sectors_out,
        "macro_themes": [
            {"id": "rates", "name": "Rates", "etf_proxy": "TLT"},
            {"id": "fx", "name": "FX", "etf_proxy": "UUP"},
            {"id": "commodities", "name": "Commodities", "etf_proxy": "DBC"},
        ],
    }


def build_universe_rows(
    starters: dict[str, Any],
    stocks_per_sector: int = 10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    for anchor in starters.get("anchors", []):
        ticker = anchor["ticker"].upper()
        rows.append(
            {
                "sector_id": "anchor",
                "sector_name": "Anchor Indices",
                "ticker": ticker,
                "name": anchor["name"],
                "etf_proxy": ticker,
                "is_anchor": "true",
                "weight_proxy": "1.0",
            }
        )
        seen_tickers.add(ticker)

    for sector in starters.get("sectors", []):
        sector_id = sector["id"]
        sector_name = sector["name"]
        etf_proxy = sector["etf_proxy"]
        stocks = sector.get("stocks", [])[:stocks_per_sector]
        for stock in stocks:
            ticker = stock["ticker"].upper()
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            rows.append(
                {
                    "sector_id": sector_id,
                    "sector_name": sector_name,
                    "ticker": ticker,
                    "name": stock["name"],
                    "etf_proxy": etf_proxy,
                    "is_anchor": "false",
                    "weight_proxy": "",
                }
            )

    return rows


def write_universe(
    run_dir: str | Path,
    *,
    starters_path: Path | None = None,
    stocks_per_sector: int = 10,
    sectors_min: int = 8,
) -> tuple[Path, Path, int]:
    """Build sectors.yaml and universe.csv in the run directory."""
    root = ensure_run_layout(run_dir)
    starters = load_sector_starters(starters_path)

    sectors_doc = build_sectors_yaml(starters)
    sectors_path = root / "config" / "sectors.yaml"
    sectors_path.write_text(yaml.safe_dump(sectors_doc, sort_keys=False))

    rows = build_universe_rows(starters, stocks_per_sector=stocks_per_sector)
    sector_ids = {r["sector_id"] for r in rows if r["sector_id"] != "anchor"}
    if len(sector_ids) < sectors_min:
        raise ValueError(f"Only {len(sector_ids)} sectors; need at least {sectors_min}")

    universe_path = root / "data" / "universe.csv"
    with universe_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=UNIVERSE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return sectors_path, universe_path, len(rows)


def load_universe_tickers(run_dir: str | Path) -> list[str]:
    root = Path(run_dir).expanduser().resolve()
    universe_path = root / "data" / "universe.csv"
    if not universe_path.exists():
        raise FileNotFoundError(f"Missing universe: {universe_path}")
    tickers: list[str] = []
    with universe_path.open() as fh:
        for row in csv.DictReader(fh):
            tickers.append(row["ticker"].upper())
    return sorted(set(tickers))

import csv
from pathlib import Path

from aitrader.universe import build_universe_rows, load_sector_starters, write_universe


def test_starters_load() -> None:
    starters = load_sector_starters()
    assert len(starters["sectors"]) >= 8
    assert any(a["ticker"] == "SPY" for a in starters["anchors"])


def test_build_universe_rows() -> None:
    starters = load_sector_starters()
    rows = build_universe_rows(starters, stocks_per_sector=10)
    sector_rows = [r for r in rows if r["sector_id"] != "anchor"]
    anchors = [r for r in rows if r["is_anchor"] == "true"]
    assert len(sector_rows) >= 80
    assert len(anchors) == 2
    assert {a["ticker"] for a in anchors} == {"SPY", "IWM"}


def test_write_universe(tmp_path: Path) -> None:
    _, universe_path, count = write_universe(tmp_path)
    assert count >= 82
    with universe_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) >= 80
    assert all(row["ticker"] for row in rows)
    assert sum(1 for r in rows if r["is_anchor"] == "true") == 2

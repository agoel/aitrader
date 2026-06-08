import io
import zipfile
from datetime import date

from aitrader.nlp.gdelt_gkg import (
    _themes_match,
    parse_gkg_zip_bytes,
    select_gkg_urls,
)

_GKG_LINE = (
    "20240608120000-99\t20240608120000\t1\treuters.com\t"
    "https://www.reuters.com/markets/us/fed-holds-rates-steady-inflation-cools\t\t\t"
    "ECON_INFLATION;ECON_INTERESTRATE;ECON_STOCKMARKET\t\t\t\t\t"
    "federal reserve;jerome powell\t\t"
    "Federal Reserve,900\t\t"
    "1.2,2.3,0.1,1.0,5.0,0,400\t\t\t\t\t\t\t"
    "530|27||Fed holds rates as inflation cools\n"
)


def _zip_bytes(csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("20240608120000.gkg.csv", csv_text)
    return buf.getvalue()


def test_themes_match() -> None:
    assert _themes_match("ECON_INFLATION;TAX_FNCACT")
    assert not _themes_match("TAX_FNCACT;ELECTION")


def test_parse_gkg_zip_bytes() -> None:
    arts = parse_gkg_zip_bytes(_zip_bytes(_GKG_LINE), max_articles=10)
    assert len(arts) == 1
    assert "fed holds rates" in arts[0].title.lower()
    assert arts[0].published_at.startswith("2024-06-08")
    assert "fed" in arts[0].tags
    assert arts[0].source.startswith("gdelt_gkg:")


def test_select_gkg_urls_sampling() -> None:
    urls = [
        "http://data.gdeltproject.org/gdeltv2/20240101120000.gkg.csv.zip",
        "http://data.gdeltproject.org/gdeltv2/20240101121500.gkg.csv.zip",
        "http://data.gdeltproject.org/gdeltv2/20240108120000.gkg.csv.zip",
    ]
    picked = select_gkg_urls(
        urls,
        start=date(2024, 1, 1),
        end=date(2024, 1, 8),
        sample_days=7,
    )
    assert "20240101120000" in picked[0]
    assert any("20240108" in u for u in picked)

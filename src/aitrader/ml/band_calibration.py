"""Calibrate prediction band width (confidence_z) from historical option-range cycles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.ml.predict_config import PredictTuneConfig, load_predict_config, save_predict_config
from aitrader.workspace import ensure_run_layout

DEFAULT_CONFIDENCE_Z = 1.96


def band_coverage_for_z(
    cycles: pd.DataFrame,
    *,
    confidence_z: float,
    base_z: float = DEFAULT_CONFIDENCE_Z,
) -> dict[str, float]:
    """Rescale historical half-bands to a new confidence_z and measure coverage."""
    if cycles.empty:
        return {"inside_band_pct": 0.0, "mean_band_width_usd": 0.0, "n": 0}
    scale = confidence_z / base_z
    half = (cycles["confidence_upper_ret"] - cycles["confidence_lower_ret"]) / 2.0
    half = half * scale
    pred = cycles["predicted_return"]
    lo = pred - half
    hi = pred + half
    spot = cycles["spot_at_signal"]
    expiry = cycles["spot_at_expiry"]
    inside = (spot * (1.0 + lo) <= expiry) & (expiry <= spot * (1.0 + hi))
    width = (spot * 2.0 * half).mean()
    return {
        "n": float(len(cycles)),
        "inside_band_pct": round(100.0 * inside.mean(), 1),
        "breach_lower_pct": round(100.0 * (expiry < spot * (1.0 + lo)).mean(), 1),
        "breach_upper_pct": round(100.0 * (expiry > spot * (1.0 + hi)).mean(), 1),
        "mean_band_width_usd": round(float(width), 2),
    }


def calibrate_confidence_z(
    cycles: pd.DataFrame,
    *,
    target_coverage: float = 0.90,
    base_z: float = DEFAULT_CONFIDENCE_Z,
    z_min: float = 0.80,
    z_max: float = 2.00,
    z_step: float = 0.05,
) -> dict[str, Any]:
    """Find the smallest confidence_z that still meets target coverage."""
    if cycles.empty:
        raise ValueError("No option-range cycles to calibrate")
    baseline = band_coverage_for_z(cycles, confidence_z=base_z, base_z=base_z)
    best: dict[str, Any] | None = None
    for z in np.arange(z_min, z_max + 1e-9, z_step):
        stats = band_coverage_for_z(cycles, confidence_z=float(z), base_z=base_z)
        if stats["inside_band_pct"] / 100.0 >= target_coverage:
            best = {
                "confidence_z": round(float(z), 2),
                **stats,
                "width_reduction_pct": round(
                    100.0
                    * (1.0 - stats["mean_band_width_usd"] / baseline["mean_band_width_usd"]),
                    1,
                )
                if baseline["mean_band_width_usd"]
                else 0.0,
            }
            break
    if best is None:
        best = {
            "confidence_z": base_z,
            **baseline,
            "width_reduction_pct": 0.0,
            "note": f"Could not reach {target_coverage*100:.0f}% coverage above z={z_min}",
        }
    return {
        "base_z": base_z,
        "target_coverage_pct": round(target_coverage * 100.0, 1),
        "baseline": baseline,
        "calibrated": best,
    }


def load_option_range_cycles(run_dir: Path) -> pd.DataFrame:
    reports = sorted((run_dir / "reports").glob("option_range_study_*.csv"))
    if not reports:
        raise FileNotFoundError(
            f"No option_range_study_*.csv under {run_dir / 'reports'} — run predict option-range first"
        )
    return pd.read_csv(reports[-1])


def run_band_calibration(
    run_dir: str | Path,
    *,
    target_coverage: float = 0.90,
    apply: bool = False,
) -> tuple[dict[str, Any], Path]:
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cycles = load_option_range_cycles(root)
    result = calibrate_confidence_z(cycles, target_coverage=target_coverage)
    cfg = load_predict_config(root)
    result["previous_confidence_z"] = getattr(cfg, "confidence_z", DEFAULT_CONFIDENCE_Z)
    result["date"] = today

    if apply:
        cfg.confidence_z = float(result["calibrated"]["confidence_z"])
        save_predict_config(root, cfg)
        result["applied"] = True
        result["config_path"] = str(root / "models" / "predict_config.json")
    else:
        result["applied"] = False

    report = root / "reports" / f"band_calibration_{today}.md"
    json_path = root / "reports" / f"band_calibration_{today}.json"
    b = result["baseline"]
    c = result["calibrated"]
    lines = [
        f"# Band calibration — {today}",
        "",
        "Prediction band width is `residual_std × confidence_z`.",
        "",
        f"**Target coverage:** {result['target_coverage_pct']}%",
        f"**Cycles:** {int(b['n'])}",
        "",
        "## Baseline (z = 1.96)",
        "",
        f"- Inside band: **{b['inside_band_pct']}%**",
        f"- Mean width: **${b['mean_band_width_usd']}**",
        f"- Breach lower / upper: {b['breach_lower_pct']}% / {b['breach_upper_pct']}%",
        "",
        "## Calibrated",
        "",
        f"- **confidence_z: {c['confidence_z']}**",
        f"- Inside band: **{c['inside_band_pct']}%**",
        f"- Mean width: **${c['mean_band_width_usd']}** ({c['width_reduction_pct']}% narrower)",
        f"- Breach lower / upper: {c['breach_lower_pct']}% / {c['breach_upper_pct']}%",
        "",
    ]
    if result["applied"]:
        lines.append(f"Applied to `{result['config_path']}`.")
    else:
        lines.append("Dry-run only — re-run with `--apply` to update `predict_config.json`.")
    report.write_text("\n".join(lines) + "\n")
    json_path.write_text(json.dumps(result, indent=2) + "\n")
    return result, report

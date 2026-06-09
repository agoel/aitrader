import pandas as pd

from aitrader.ml.band_calibration import band_coverage_for_z, calibrate_confidence_z


def _cycles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "predicted_return": [0.02, 0.01, -0.01, 0.03],
            "confidence_lower_ret": [-0.08, -0.09, -0.11, -0.07],
            "confidence_upper_ret": [0.12, 0.11, 0.09, 0.13],
            "spot_at_signal": [400.0, 420.0, 440.0, 460.0],
            "spot_at_expiry": [410.0, 415.0, 430.0, 470.0],
        }
    )


def test_calibrate_finds_narrower_z() -> None:
    cycles = _cycles()
    baseline = band_coverage_for_z(cycles, confidence_z=1.96)
    result = calibrate_confidence_z(cycles, target_coverage=0.75, z_min=0.5)
    cal = result["calibrated"]
    assert cal["confidence_z"] <= 1.96
    assert cal["mean_band_width_usd"] <= baseline["mean_band_width_usd"]

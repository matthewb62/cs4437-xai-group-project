"""Tests for the drift analysis: A5 (required), plus the windows, PSI and z-scores."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import analyse  # noqa: E402
from config import BASELINE_EARLIEST, SD_MULTIPLIER, SHOCK_DATE, WINDOW_DAYS  # noqa: E402

REFERENCE = np.array([9.0, 7.5, 6.0, 3.0, 1.2, 0.8, 0.3, 0.1])


def test_a5_reference_against_itself_is_one():
    assert np.isclose(analyse.tau(REFERENCE, REFERENCE), 1.0, atol=1e-12)


def test_a5_reversed_ranking_is_negative():
    assert analyse.tau(REFERENCE[::-1], REFERENCE) < 0


def test_a5_top_of_ranking_weighs_most():
    top_swapped = REFERENCE.copy()
    top_swapped[[0, 1]] = top_swapped[[1, 0]]
    bottom_swapped = REFERENCE.copy()
    bottom_swapped[[-1, -2]] = bottom_swapped[[-2, -1]]
    assert analyse.tau(top_swapped, REFERENCE) < analyse.tau(bottom_swapped, REFERENCE) < 1


def test_a1_windows():
    shock = pd.Timestamp(SHOCK_DATE)
    last_day = shock + pd.Timedelta(days=3 * WINDOW_DAYS + 5)   # three full test windows and a part one
    windows = analyse.build_windows(last_day)
    baseline = windows[windows["period"] == "baseline"]
    test = windows[windows["period"] == "test"]

    assert len(test) == 3
    assert test["window_start"].iloc[0] == shock
    assert baseline["window_end"].max() == shock - pd.Timedelta(days=1)
    assert baseline["window_start"].min() >= pd.Timestamp(BASELINE_EARLIEST)
    assert baseline["window_start"].min() - pd.Timedelta(days=WINDOW_DAYS) < pd.Timestamp(BASELINE_EARLIEST)
    assert ((windows["window_end"] - windows["window_start"]).dt.days == WINDOW_DAYS - 1).all()
    if (SHOCK_DATE, BASELINE_EARLIEST, WINDOW_DAYS) == ("2026-02-28", "2025-11-01", 14):
        assert len(baseline) == 8
        assert baseline["window_start"].min() == pd.Timestamp("2025-11-08")


def test_a7_psi():
    rng = np.random.default_rng(0)
    train = rng.normal(size=20000)
    edges = analyse.psi_edges(train)
    expected = analyse.bin_shares(train, edges)

    assert analyse.psi(expected, expected) == 0
    assert analyse.psi(expected, analyse.bin_shares(rng.normal(size=5000), edges)) < 0.02
    assert analyse.psi(expected, analyse.bin_shares(rng.normal(loc=1.5, size=5000), edges)) > analyse.PSI_CUTOFF
    # Values outside the training range still land in a bin.
    assert analyse.bin_shares(np.array([-1e9, 1e9]), edges).sum() == 1


def test_a12_z_scores_point_up_for_more_drift():
    baseline = pd.DataFrame({
        "period": "baseline",
        "tau": [0.90, 0.92, 0.88, 0.91],
        "mae": [5.0, 5.5, 4.5, 5.2],
        "psi_mean": [0.10, 0.12, 0.08, 0.11],
        "psi_max": [0.20, 0.21, 0.19, 0.20],
    })
    drifted = pd.DataFrame({"period": ["test"], "tau": [0.5], "mae": [20.0], "psi_mean": [0.9], "psi_max": [1.5]})
    results, thresholds = analyse.add_thresholds(pd.concat([baseline, drifted], ignore_index=True))
    last = results.iloc[-1]

    assert last["tau_z"] > SD_MULTIPLIER and last["mae_z"] > SD_MULTIPLIER and last["psi_z"] > SD_MULTIPLIER
    assert last["tau_warn"] and last["mae_warn"] and last["psi_warn"] and last["psi_over_cutoff"]
    assert np.isclose(thresholds["tau_sd"], baseline["tau"].std(ddof=1))
    assert np.isclose(last["tau_z"], (thresholds["tau_mean"] - 0.5) / thresholds["tau_sd"])
    assert not results.iloc[:-1][["tau_warn", "mae_warn", "psi_warn"]].any().any()


def test_a11_a14_first_crossing():
    results = pd.DataFrame({
        "period": ["baseline", "test", "test", "test", "test"],
        "window_start": pd.date_range("2026-02-14", periods=5, freq="14D"),
        "tau_warn": [True, False, True, False, False],
        "mae_warn": [False, False, False, True, True],
    })
    assert analyse.first_crossing(results, "tau_warn") == pd.Timestamp("2026-03-14")
    assert analyse.first_crossing(results, "tau_warn", consecutive=2) is None
    assert analyse.first_crossing(results, "mae_warn", consecutive=2) == pd.Timestamp("2026-04-11")
    assert analyse.lead_time(pd.Timestamp("2026-03-28"), pd.Timestamp("2026-03-14")) == 14
    assert analyse.lead_time(None, pd.Timestamp("2026-03-14")) is None

"""Tests for the feature build: F2, F4, F6, F7, F8, F9 and F11, plus F1 and F10.

data/raw/ is empty while the energy-charts API is down, so the cleaned table
every test starts from is a few weeks of rows built here.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import build_features  # noqa: E402
import clean_data  # noqa: E402
from config import (  # noqa: E402
    AUCTION_CLOSE_HOUR, FEATURES_BLIND, FEATURES_OIL, TARGET, TIMEZONE,
)


def clean_fixture(start="2024-01-01", days=45):
    """A cleaned hourly table whose values identify the hour they came from."""
    last = (pd.Timestamp(start) + pd.Timedelta(days=days - 1)).date()
    index = clean_data.berlin_hour_index(pd.Timestamp(start).date(), last)
    count = len(index)
    frame = pd.DataFrame(index=index)
    frame[clean_data.PRICE] = np.arange(count, dtype=float)
    frame["demand_forecast"] = 50000.0 + np.arange(count)
    frame["wind_forecast"] = 9000.0
    frame["solar_forecast"] = 1000.0
    frame[clean_data.GAS] = np.arange(count, dtype=float) * 2 + 0.5
    frame["temp_forecast"] = 5.0
    day_number = (index.tz_localize(None).normalize() - pd.Timestamp(start)).days
    frame[clean_data.OIL_CLOSE] = 80.0 + day_number      # a close that rises by 1 a day
    return frame


def at(table, day, hour):
    return table.loc[pd.Timestamp(f"{day} {hour:02d}:00", tz=TIMEZONE)]


# ---------------------------------------------------------------- F1, F2

def test_f1_one_row_per_delivery_hour_with_a_price():
    clean = clean_fixture(days=10)
    table, _ = build_features.build(clean)
    assert TARGET in table.columns
    assert len(table) == len(clean)
    assert np.allclose(table[TARGET].to_numpy(), clean[clean_data.PRICE].to_numpy())


def test_f2_lag_1d_is_the_same_berlin_hour_on_the_previous_day():
    clean = clean_fixture(days=20)
    table, _ = build_features.build(clean)
    for hour in (0, 9, 13, 23):
        assert at(table, "2024-01-15", hour)["price_lag_1d"] == \
            at(clean, "2024-01-14", hour)[clean_data.PRICE]


def test_f2_lag_2d_and_7d_match_the_same_hour_two_and_seven_days_back():
    clean = clean_fixture(days=20)
    table, _ = build_features.build(clean)
    row = at(table, "2024-01-15", 9)
    assert row["price_lag_2d"] == at(clean, "2024-01-13", 9)[clean_data.PRICE]
    assert row["price_lag_7d"] == at(clean, "2024-01-08", 9)[clean_data.PRICE]


def test_f2_lags_follow_the_wall_clock_across_the_spring_change():
    """09:00 lags to 09:00, not to a fixed 24 hours, on a 23-hour day."""
    clean = clean_fixture(start="2024-03-25", days=12)
    table, _ = build_features.build(clean)
    assert at(table, "2024-04-01", 9)["price_lag_1d"] == \
        at(clean, "2024-03-31", 9)[clean_data.PRICE]      # the 31st is 23 hours long


def test_f2_the_hour_a_spring_change_skips_has_no_lag():
    clean = clean_fixture(start="2024-03-25", days=12)
    table, _ = build_features.build(clean)
    assert np.isnan(at(table, "2024-04-01", 2)["price_lag_1d"])   # 02:00 did not exist


# ---------------------------------------------------------------- F4

def test_f4_morning_hours_come_from_d1_and_afternoon_hours_from_d2():
    clean = clean_fixture(days=20)
    table, _ = build_features.build(clean)
    for hour in range(0, AUCTION_CLOSE_HOUR):
        assert at(table, "2024-01-15", hour)["gas_gen_lag"] == \
            at(clean, "2024-01-14", hour)[clean_data.GAS]
    for hour in range(AUCTION_CLOSE_HOUR, 24):
        assert at(table, "2024-01-15", hour)["gas_gen_lag"] == \
            at(clean, "2024-01-13", hour)[clean_data.GAS]


def test_f4_no_gas_value_is_stamped_at_or_after_the_d1_cut_off():
    clean = clean_fixture(days=20)
    table, sources = build_features.build(clean)
    cutoff = (table.index.tz_localize(None).normalize()
              - pd.Timedelta(days=1) + pd.Timedelta(hours=AUCTION_CLOSE_HOUR))
    used = pd.DatetimeIndex(sources["gas_gen_lag"])
    assert (used[used.notna()] < cutoff[used.notna()]).all()


# ---------------------------------------------------------------- F6

def test_f6_time_features_cover_the_four_columns():
    clean = clean_fixture(days=20)
    table, _ = build_features.build(clean)
    assert set(table["hour"]) <= set(range(24))
    assert set(table["weekday"]) <= set(range(7))
    assert set(table["month"]) <= set(range(1, 13))
    assert at(table, "2024-01-15", 0)["weekday"] == 0        # a Monday
    assert at(table, "2024-01-15", 9)["hour"] == 9


def test_f6_holiday_flag_is_one_on_christmas_and_zero_on_an_ordinary_tuesday():
    clean = clean_fixture(start="2025-12-20", days=14)
    table, _ = build_features.build(clean)
    assert at(table, "2025-12-25", 12)["is_holiday"] == 1
    assert at(table, "2025-12-30", 12)["is_holiday"] == 0     # an ordinary Tuesday


# ---------------------------------------------------------------- F7

def test_f7_oil_uses_the_close_two_days_before_against_thirty_days_before_that():
    clean = clean_fixture(days=45)
    table, _ = build_features.build(clean)
    day = "2024-02-10"
    recent = at(clean, "2024-02-08", 0)[clean_data.OIL_CLOSE]              # D-2
    earlier = at(clean, "2024-01-09", 0)[clean_data.OIL_CLOSE]             # D-2 minus 30 days
    assert np.isclose(at(table, day, 0)["oil_change_30d"], (recent / earlier - 1) * 100)


def test_f7_oil_is_constant_within_a_delivery_day():
    clean = clean_fixture(days=45)
    table, _ = build_features.build(clean)
    day = table[table.index.date == pd.Timestamp("2024-02-10").date()]["oil_change_30d"]
    assert day.nunique() == 1


def test_f7_the_d1_close_cannot_reach_the_feature():
    """Moving the close published on D-1 leaves the delivery day's oil feature alone."""
    clean = clean_fixture(days=45)
    before, _ = build_features.build(clean)
    moved = clean.copy()
    is_d1 = moved.index.date == pd.Timestamp("2024-02-09").date()
    moved.loc[is_d1, clean_data.OIL_CLOSE] = 999.0
    after, _ = build_features.build(moved)
    day = before.index.date == pd.Timestamp("2024-02-10").date()
    assert np.allclose(before[day]["oil_change_30d"], after[day]["oil_change_30d"])


# ---------------------------------------------------------------- F8, F9

def test_f8_the_two_feature_sets_differ_by_exactly_one_name():
    assert set(FEATURES_OIL) - set(FEATURES_BLIND) == {"oil_change_30d"}
    assert set(FEATURES_BLIND) - set(FEATURES_OIL) == set()
    assert len(FEATURES_OIL) == len(FEATURES_BLIND) + 1


def test_f9_rows_with_a_missing_lag_are_dropped_and_the_rest_are_complete():
    clean = clean_fixture(days=45)
    table, _ = build_features.build(clean)
    kept, dropped = build_features.drop_incomplete_rows(table)
    assert len(kept) + len(dropped) == len(table)
    assert not kept.isna().any().any()
    assert dropped.isna().any(axis=1).all()


def test_f9_one_row_set_serves_both_models():
    """The same rows and the same first timestamp, whichever feature list is read."""
    clean = clean_fixture(days=45)
    table, _ = build_features.build(clean)
    kept, _ = build_features.drop_incomplete_rows(table)
    blind, oil = kept[FEATURES_BLIND], kept[FEATURES_OIL]
    assert len(blind) == len(oil)
    assert blind.index[0] == oil.index[0]
    assert blind.index.equals(oil.index)


# ---------------------------------------------------------------- F10, F11

def test_f10_oil_range_reports_the_largest_change_in_each_window():
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz=TIMEZONE)
    table = pd.DataFrame({"oil_change_30d": [1.0, -9.0, 4.0, 2.0, 7.0]}, index=index)
    numbers = build_features.oil_range(table, "2024-01-01", "2024-01-03", "2024-01-04")
    assert numbers["largest_30d_oil_change_training_pct"] == -9.0   # largest by size
    assert numbers["largest_30d_oil_change_test_pct"] == 7.0


def test_f11_leakage_check_passes_on_the_real_lags():
    clean = clean_fixture(days=45)
    table, sources = build_features.build(clean)
    assert build_features.check_no_leakage(table.index, sources) is not None


def test_f11_a_one_day_price_lag_is_not_leakage():
    """D-1's prices were set at the D-2 auction, so reading them is allowed."""
    clean = clean_fixture(days=45)
    table, sources = build_features.build(clean)
    build_features.check_no_leakage(table.index, {"price_lag_1d": sources["price_lag_1d"]})


def test_f11_leakage_check_fails_when_a_column_reads_past_the_cut_off():
    clean = clean_fixture(days=45)
    table, sources = build_features.build(clean)
    late = table.index.tz_localize(None).normalize() - pd.Timedelta(days=1) \
        + pd.Timedelta(hours=AUCTION_CLOSE_HOUR)
    sources["gas_gen_lag"] = pd.DatetimeIndex(late)          # exactly at the cut-off
    with pytest.raises(build_features.FeatureError, match="Leakage"):
        build_features.check_no_leakage(table.index, sources)

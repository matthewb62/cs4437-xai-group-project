"""Tests for the cleaning step: C1, C2, C3 and C4, plus C5 and C6.

The energy-charts API is down, so data/raw/ is empty. Every fixture here is a
few days of rows built inside the test, never a saved file.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import clean_data  # noqa: E402
from config import CITIES, MAX_GAP_HOURS, TIMEZONE  # noqa: E402


def quarter_hourly(day, values):
    """A 15-minute UTC series starting at midnight on `day`."""
    index = pd.date_range(f"{day} 00:00", periods=len(values), freq="15min", tz="UTC")
    return pd.Series(values, index=index, dtype=float)


# ---------------------------------------------------------------- C1

def test_c1_hourly_mean_of_four_quarter_hours():
    series = quarter_hourly("2025-12-01", [10.0, 20.0, 30.0, 40.0, 0.0, 0.0, 0.0, 100.0])
    hourly, incomplete = clean_data.hourly_mean(series)
    assert list(hourly) == [25.0, 25.0]           # by hand: 100/4 and 100/4
    assert incomplete == 0


def test_c1_hourly_steps_pass_through_unchanged():
    """Before the late-2025 switch a series is already hourly: the mean is itself."""
    index = pd.date_range("2024-06-01", periods=24, freq="h", tz="UTC")
    values = pd.Series(np.arange(24, dtype=float), index=index)
    hourly, incomplete = clean_data.hourly_mean(values)
    assert np.allclose(hourly.to_numpy(), values.to_numpy())
    assert incomplete == 0


def test_c1_part_filled_hour_is_averaged_over_what_is_there_and_counted():
    series = quarter_hourly("2025-12-01", [10.0, 20.0, 30.0, 40.0, 4.0, 8.0, 12.0, 16.0])
    series = series.drop(series.index[5])         # one quarter-hour missing from hour 1
    hourly, incomplete = clean_data.hourly_mean(series)
    assert hourly.iloc[0] == 25.0
    assert hourly.iloc[1] == (4.0 + 12.0 + 16.0) / 3
    assert incomplete == 1


def test_c1_empty_hour_is_a_gap_not_an_incomplete_hour():
    series = quarter_hourly("2025-12-01", [1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 5.0, 6.0, 7.0, 8.0])
    series = series.drop(series.index[4:8])       # hour 1 has nothing at all
    hourly, incomplete = clean_data.hourly_mean(series)
    assert np.isnan(hourly.iloc[1])
    assert incomplete == 0


# ---------------------------------------------------------------- C2

def test_c2_clock_change_days_have_23_and_25_hours():
    index = clean_data.berlin_hour_index("2024-03-29", "2024-11-01")
    counts = clean_data.rows_per_day(index)
    assert counts[pd.Timestamp("2024-03-31").date()] == 23     # spring forward
    assert counts[pd.Timestamp("2024-10-27").date()] == 25     # autumn back
    ordinary = counts.drop([pd.Timestamp("2024-03-31").date(), pd.Timestamp("2024-10-27").date()])
    assert (ordinary == 24).all()


def test_c2_index_is_sorted_berlin_and_free_of_duplicates():
    index = clean_data.berlin_hour_index("2024-10-25", "2024-10-29")
    assert index.name == "timestamp"
    assert str(index.tz) == TIMEZONE
    assert index.is_monotonic_increasing
    assert not index.duplicated().any()


def test_c2_conversion_from_utc_not_a_fixed_shift():
    """Berlin runs at +01:00 in winter and +02:00 in summer, so no fixed shift works."""
    index = clean_data.berlin_hour_index("2024-01-15", "2024-07-15")
    assert index[0].utcoffset() == pd.Timedelta(hours=1)
    assert index[-1].utcoffset() == pd.Timedelta(hours=2)
    assert index[0].hour == 0 and index[-1].hour == 23


# ---------------------------------------------------------------- C3

def test_c3_gap_limit_is_the_named_constant():
    assert clean_data.MAX_GAP_HOURS is MAX_GAP_HOURS


def test_c3_short_gaps_are_interpolated_and_long_gaps_are_left():
    index = pd.date_range("2024-05-01", periods=24, freq="h", tz=TIMEZONE)
    series = pd.Series(np.arange(24, dtype=float), index=index)
    series.iloc[2:2 + MAX_GAP_HOURS] = np.nan            # a gap at the limit
    series.iloc[12:12 + MAX_GAP_HOURS + 1] = np.nan      # one hour too long
    filled, short, long = clean_data.fill_short_gaps(series, MAX_GAP_HOURS)

    assert short == MAX_GAP_HOURS
    assert long == MAX_GAP_HOURS + 1
    assert np.allclose(filled.iloc[2:2 + MAX_GAP_HOURS], np.arange(2, 2 + MAX_GAP_HOURS))
    assert filled.iloc[12:12 + MAX_GAP_HOURS + 1].isna().all()


def test_c3_hours_outside_a_series_coverage_are_not_gaps():
    """A series that starts late is not filled back to the start of the table."""
    index = pd.date_range("2024-05-01", periods=12, freq="h", tz=TIMEZONE)
    series = pd.Series([np.nan] * 5 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], index=index)
    filled, short, long = clean_data.fill_short_gaps(series, MAX_GAP_HOURS)
    assert short == 0 and long == 0
    assert filled.iloc[:5].isna().all()


def test_c3_the_price_is_never_filled():
    assert clean_data.PRICE not in clean_data.FILLED_COLUMNS


# ---------------------------------------------------------------- C4

def test_c4_negative_prices_and_spikes_survive_cleaning():
    series = quarter_hourly("2025-12-01", [-500.0, -500.0, -500.0, -500.0,
                                           3000.0, 3000.0, 3000.0, 3000.0])
    hourly, _ = clean_data.hourly_mean(series)
    assert hourly.min() == -500.0
    assert hourly.max() == 3000.0


# ---------------------------------------------------------------- C5, C6

def test_c5_temperature_is_population_weighted():
    index = pd.date_range("2024-05-01", periods=3, freq="h", tz=TIMEZONE)
    cities = {city: pd.Series(float(n), index=index) for n, city in enumerate(CITIES, start=1)}
    weights = {city: weight for city, (_lat, _lon, weight) in CITIES.items()}
    combined = clean_data.weighted_temperature(cities, weights)
    expected = sum(n * weights[city] for n, city in enumerate(CITIES, start=1)) / sum(weights.values())
    assert np.allclose(combined.to_numpy(), expected)


def test_c5_an_hour_missing_one_city_is_missing():
    index = pd.date_range("2024-05-01", periods=3, freq="h", tz=TIMEZONE)
    cities = {city: pd.Series(10.0, index=index) for city in CITIES}
    cities["berlin"].iloc[1] = np.nan
    weights = {city: weight for city, (_lat, _lon, weight) in CITIES.items()}
    combined = clean_data.weighted_temperature(cities, weights)
    assert np.isnan(combined.iloc[1])
    assert combined.iloc[0] == 10.0


def test_c5_reanalysis_only_fills_the_hours_before_the_forecast_begins():
    index = pd.date_range("2024-01-19 20:00", periods=8, freq="h", tz=TIMEZONE)
    forecast = pd.Series([np.nan] * 3 + [5.0, 6.0, np.nan, 8.0, 9.0], index=index)
    reanalysis = pd.Series(1.0, index=index)
    spliced, first = clean_data.splice_temperature(forecast, reanalysis)
    assert first == index[3]
    assert (spliced.iloc[:3] == 1.0).all()                  # before the archive: ERA5
    assert list(spliced.iloc[3:5]) == [5.0, 6.0]             # the forecast as it is
    assert np.isnan(spliced.iloc[5])                         # a later gap is not filled
    assert list(spliced.iloc[6:]) == [8.0, 9.0]


def test_c5_an_empty_forecast_stops_cleaning():
    index = pd.date_range("2024-01-19", periods=3, freq="h", tz=TIMEZONE)
    with pytest.raises(clean_data.CleaningError, match="no values"):
        clean_data.splice_temperature(pd.Series(np.nan, index=index), pd.Series(1.0, index=index))


def test_c5_c6_assembly_puts_every_series_on_one_berlin_index():
    """C1-C6 together, on five hand-built days that contain the autumn clock change."""
    utc = pd.date_range("2024-10-24 22:00", "2024-10-29 23:00", freq="h", tz="UTC")
    hourly = {
        clean_data.PRICE: pd.Series(np.arange(len(utc), dtype=float), index=utc),
        "forecast_load": pd.Series(50000.0, index=utc),
        "forecast_solar": pd.Series(1000.0, index=utc),
        "forecast_wind_onshore": pd.Series(7000.0, index=utc),
        "forecast_wind_offshore": pd.Series(2000.0, index=utc),
        clean_data.GAS: pd.Series(4000.0, index=utc),
        **{f"temperature_{city}": pd.Series(12.0, index=utc) for city in CITIES},
        **{f"temperature_era5_{city}": pd.Series(11.0, index=utc) for city in CITIES},
    }
    brent = pd.Series([80.0, 82.0],
                      index=pd.DatetimeIndex(["2024-10-25", "2024-10-28"], tz="UTC"))

    table = clean_data.assemble(hourly, brent)

    assert list(table.columns) == clean_data.CLEAN_COLUMNS
    assert str(table.index.tz) == TIMEZONE and table.index.name == "timestamp"
    counts = clean_data.rows_per_day(table.index)
    assert counts[pd.Timestamp("2024-10-27").date()] == 25
    assert (counts.drop(pd.Timestamp("2024-10-27").date()) == 24).all()
    assert (table[clean_data.WIND] == 9000.0).all()          # onshore + offshore
    assert (table[clean_data.TEMP] == 12.0).all()            # every city the same
    by_day = table[clean_data.OIL_CLOSE].groupby(table.index.date)
    assert (by_day.nunique() == 1).all()                     # one close per delivery day
    assert by_day.first()[pd.Timestamp("2024-10-27").date()] == 80.0   # Sunday carries Friday


def test_assembly_stops_at_the_last_complete_price_day():
    utc = pd.date_range("2024-06-01 00:00", "2024-06-04 12:00", freq="h", tz="UTC")
    hourly = {
        clean_data.PRICE: pd.Series(np.arange(len(utc), dtype=float), index=utc),
        "forecast_load": pd.Series(50000.0, index=utc),
        "forecast_solar": pd.Series(1000.0, index=utc),
        "forecast_wind_onshore": pd.Series(7000.0, index=utc),
        "forecast_wind_offshore": pd.Series(2000.0, index=utc),
        clean_data.GAS: pd.Series(4000.0, index=utc),
        **{f"temperature_{city}": pd.Series(12.0, index=utc) for city in CITIES},
        **{f"temperature_era5_{city}": pd.Series(11.0, index=utc) for city in CITIES},
    }
    brent = pd.Series([80.0], index=pd.DatetimeIndex(["2024-06-01"], tz="UTC"))
    table = clean_data.assemble(hourly, brent)
    # In Berlin the download starts at 02:00 on the 1st and stops at 14:00 on the 4th,
    # so only the 2nd and the 3rd are complete delivery days.
    assert table.index[0].date() == pd.Timestamp("2024-06-02").date()
    assert table.index[-1].date() == pd.Timestamp("2024-06-03").date()
    assert not table[clean_data.PRICE].isna().any()


def test_c6_brent_is_carried_forward_over_the_weekend():
    closes = pd.Series(
        [80.0, 82.0],
        index=pd.DatetimeIndex(["2024-01-05", "2024-01-08"], tz="UTC"),   # Friday, Monday
    )
    days = pd.date_range("2024-01-05", "2024-01-09", freq="D")
    oil = clean_data.daily_oil_close(closes, days)
    assert list(oil) == [80.0, 80.0, 80.0, 82.0, 82.0]
    assert not oil.isna().any()

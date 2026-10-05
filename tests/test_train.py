"""Tests for training: M8 (required), plus the windows M1, M3, M4 and the M7 check.

The real feature table does not exist yet, so these fit on a few months of rows
built here. They check the split and the reproducibility, never the accuracy of
a model trained on made-up numbers.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import train  # noqa: E402
from config import (  # noqa: E402
    FEATURES_BLIND, FEATURES_OIL, SEED, TARGET, TIMEZONE, TRAIN_END, VAL_END, VAL_START,
)


def feature_fixture(start="2025-08-01", end="2025-12-15"):
    """A feature table with the contract's columns and a learnable price."""
    index = pd.date_range(pd.Timestamp(start, tz=TIMEZONE), pd.Timestamp(end, tz=TIMEZONE),
                          freq="h", name="timestamp")
    rng = np.random.default_rng(SEED)
    count = len(index)
    table = pd.DataFrame(index=index)
    table["demand_forecast"] = 50000 + 5000 * np.sin(np.arange(count) / 12) + rng.normal(0, 500, count)
    table["wind_forecast"] = 10000 + rng.normal(0, 2000, count)
    table["solar_forecast"] = np.clip(8000 * np.sin(np.arange(count) / 24), 0, None)
    table["gas_gen_lag"] = 4000 + rng.normal(0, 300, count)
    table["temp_forecast"] = 10 + 5 * np.sin(np.arange(count) / 24)
    table["hour"] = index.hour
    table["weekday"] = index.weekday
    table["month"] = index.month
    table["is_holiday"] = 0
    table["oil_change_30d"] = np.linspace(-5, 15, count)
    price = (0.0015 * table["demand_forecast"] - 0.0008 * table["wind_forecast"]
             + 0.5 * table["hour"] + rng.normal(0, 3, count))
    table[TARGET] = price
    for column, days in (("price_lag_1d", 1), ("price_lag_2d", 2), ("price_lag_7d", 7)):
        table[column] = table[TARGET].shift(24 * days).bfill()
    return table[FEATURES_OIL + [TARGET]]


# ---------------------------------------------------------------- M1

def test_m1_windows_do_not_share_a_row():
    table = train.cut_at_validation_end(feature_fixture())
    fitted, valid = train.split(table)
    assert fitted.index.intersection(valid.index).empty
    assert fitted.index[-1] <= pd.Timestamp(TRAIN_END, tz=TIMEZONE) + pd.Timedelta(hours=23)
    assert valid.index[0] >= pd.Timestamp(VAL_START, tz=TIMEZONE)
    assert valid.index[-1] <= pd.Timestamp(VAL_END, tz=TIMEZONE) + pd.Timedelta(hours=23)


# ---------------------------------------------------------------- M2, M3

def test_m2_one_model_covers_all_24_hours_with_hour_as_a_feature():
    table = train.cut_at_validation_end(feature_fixture())
    fitted, valid = train.split(table)
    model = train.fit(fitted, valid, FEATURES_BLIND)
    assert "hour" in model.booster_.feature_name()
    assert sorted(fitted["hour"].unique()) == list(range(24))


def test_m3_both_models_see_the_same_rows_and_the_same_settings():
    table = train.cut_at_validation_end(feature_fixture())
    fitted, valid = train.split(table)
    blind = train.fit(fitted, valid, FEATURES_BLIND)
    oil = train.fit(fitted, valid, FEATURES_OIL)
    assert blind.booster_.feature_name() == FEATURES_BLIND
    assert oil.booster_.feature_name() == FEATURES_OIL
    assert blind.n_features_in_ + 1 == oil.n_features_in_
    differences = {key: (value, blind.get_params()[key])
                   for key, value in oil.get_params().items()
                   if blind.get_params()[key] != value}
    assert differences == {}       # only the feature list differs, and that is not a param


# ---------------------------------------------------------------- M4

def test_m4_nothing_after_the_validation_month_is_read():
    table = feature_fixture()
    assert table.index[-1] > pd.Timestamp(VAL_END, tz=TIMEZONE)    # the fixture runs past it
    cut = train.cut_at_validation_end(table)
    assert cut.index[-1] < pd.Timestamp(VAL_END, tz=TIMEZONE) + pd.Timedelta(days=1)
    fitted, valid = train.split(cut)
    for window in (fitted, valid):
        assert window.index[-1] <= cut.index[-1]


# ---------------------------------------------------------------- M7

def test_m7_naive_forecast_is_the_price_seven_days_earlier():
    index = pd.date_range("2025-10-01", periods=4, freq="h", tz=TIMEZONE)
    valid = pd.DataFrame({TARGET: [10.0, 20.0, 30.0, 40.0],
                          "price_lag_7d": [12.0, 18.0, 33.0, 36.0]}, index=index)
    assert train.naive_mae(valid) == 2.75                   # mean of 2, 2, 3, 4


def test_m7_stops_when_a_model_does_not_beat_the_naive_forecast():
    with pytest.raises(train.TrainingError, match="naive"):
        train.check_beats_naive({"blind": 9.0, "oil": 11.0}, naive=10.0)
    train.check_beats_naive({"blind": 9.0, "oil": 8.0}, naive=10.0)   # both better: no error


# ---------------------------------------------------------------- M8

def test_m8_two_runs_give_the_same_validation_mae_and_the_same_model():
    table = train.cut_at_validation_end(feature_fixture())
    fitted, valid = train.split(table)
    first = train.fit(fitted, valid, FEATURES_BLIND)
    second = train.fit(fitted, valid, FEATURES_BLIND)
    assert train.validation_mae(first, valid, FEATURES_BLIND) == \
        train.validation_mae(second, valid, FEATURES_BLIND)
    assert first.booster_.model_to_string() == second.booster_.model_to_string()
    assert first.best_iteration_ == second.best_iteration_


def test_m8_the_seed_and_hyperparameters_are_the_ones_that_get_saved():
    assert train.PARAMS["seed"] is SEED
    assert train.PARAMS["deterministic"] is True
    model = train.lgb.LGBMRegressor(n_estimators=train.NUM_BOOST_ROUND, **train.PARAMS)
    for key, value in train.PARAMS.items():
        assert model.get_params()[key] == value

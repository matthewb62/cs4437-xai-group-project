"""Synthetic stand-ins for Person A's handover, so analyse.py and plot.py can be built first.

Writes features_SAMPLE.parquet with the contract's columns and two throwaway LightGBM
models. Everything here is made up: it must never be used for a reported result.

The data changes at SHOCK_DATE (noisier prices, a steeper gas effect, a weaker wind
effect, an oil effect that did not exist before, less gas generation), so the drift
flags in analyse.py have something to fire on.

Usage: python src/make_sample_features.py
"""
import holidays
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.signal import lfilter

from analyse import SAMPLE_MODEL_FILES
from config import (
    AUCTION_CLOSE_HOUR, FEATURES_BLIND, FEATURES_OIL, MODELS_DIR, OIL_CHANGE_DAYS,
    OIL_FEATURE, OIL_LAG_DAYS, PROCESSED_DIR, SAMPLE_FEATURES_FILE, SEED, SHOCK_DATE,
    TARGET, TIMEZONE, TRAIN_END, TRAIN_START,
)

LEAD_IN_DAYS = 45   # extra days before TRAIN_START so every lag exists on 1 Jan 2024
SAMPLE_TREES = 200


def ar1(rng, n, phi):
    """Autocorrelated noise with unit variance."""
    x = lfilter([1.0], [1.0, -phi], rng.normal(size=n))
    return x * np.sqrt(1 - phi ** 2)


def same_hour_lag(values, index, days):
    """Value at the same Berlin clock hour `days` earlier."""
    wall = index.tz_localize(None)
    by_wall = pd.Series(values, index=wall).groupby(level=0).first()
    lagged = by_wall.reindex(wall - pd.Timedelta(days=days))
    # The hour skipped by the spring clock change has no match: carry the previous hour.
    return lagged.ffill().to_numpy()


def make_table():
    rng = np.random.default_rng(SEED)
    start = pd.Timestamp(TRAIN_START, tz=TIMEZONE) - pd.Timedelta(days=LEAD_IN_DAYS)
    end = pd.Timestamp.now(tz=TIMEZONE).normalize()   # today 00:00, so yesterday is the last day
    index = pd.date_range(start, end, freq="h", inclusive="left", name="timestamp")
    n = len(index)
    hour = index.hour.to_numpy()
    weekday = index.weekday.to_numpy()
    doy = index.dayofyear.to_numpy()
    after = (index >= pd.Timestamp(SHOCK_DATE, tz=TIMEZONE)).astype(float)

    year_angle = 2 * np.pi * doy / 365.25
    demand = (
        55000 + 8000 * np.cos(year_angle - 0.25)
        + 9000 * np.sin(np.pi * np.clip(hour - 5, 0, 17) / 17)
        - 6000 * (weekday >= 5)
        + 1500 * ar1(rng, n, 0.9)
    )
    wind = np.clip(13000 * (1 + 0.3 * np.cos(year_angle)) * np.exp(0.6 * ar1(rng, n, 0.985)), 500, 55000)
    daylight = np.clip(np.sin(np.pi * (hour - 6) / 12), 0, None) ** 1.5
    cloud = np.repeat(rng.uniform(0.4, 1.0, n // 24 + 2), 24)[:n]
    solar = daylight * (16000 - 12000 * np.cos(year_angle)) * cloud
    temp = 10 - 9 * np.cos(year_angle - 0.3) + 3 * np.sin(2 * np.pi * (hour - 9) / 24) + 2.5 * ar1(rng, n, 0.99)

    residual = demand - wind - solar
    gas = np.clip(4000 + 0.25 * (residual - 30000) + 800 * ar1(rng, n, 0.9), 500, None)
    gas = gas * (1 - 0.3 * after)

    # Daily Brent: calm before the shock, then a jump and higher volatility.
    shock_day = pd.Timestamp(SHOCK_DATE)
    days = pd.date_range(start.tz_localize(None).normalize() - pd.Timedelta(days=OIL_CHANGE_DAYS + OIL_LAG_DAYS + 5),
                         end.tz_localize(None), freq="D")
    days_since = np.asarray((days - shock_day).days, dtype=float)
    ramp = np.clip(days_since / 20, 0, 1)
    step = rng.normal(0, np.where(days_since >= 0, 0.03, 0.012))
    brent = pd.Series(80 * np.exp(np.cumsum(step) + 0.45 * ramp), index=days)
    oil_change_daily = (brent.shift(OIL_LAG_DAYS) / brent.shift(OIL_LAG_DAYS + OIL_CHANGE_DAYS) - 1) * 100
    oil_change = oil_change_daily.reindex(index.tz_localize(None).normalize()).to_numpy()

    # A slow price swing the drivers do not explain, so the price lags carry real information.
    swing = ar1(rng, n, 0.995)
    noise = ar1(rng, n, 0.7)
    price_before = 5 + 0.0018 * residual + 0.003 * gas + 10 * swing + 4 * noise
    price_after = (20 + 0.0018 * residual + 0.0009 * wind + 0.006 * gas + 0.5 * oil_change
                   + 30 * swing + 8 * noise)
    price = np.where(after == 1, price_after, price_before)

    # Gas known at the auction: hours before AUCTION_CLOSE_HOUR from D-1, the rest from D-2.
    gas_lag = np.where(hour < AUCTION_CLOSE_HOUR,
                       same_hour_lag(gas, index, 1), same_hour_lag(gas, index, 2))

    german_holidays = holidays.Germany(years=range(index[0].year, index[-1].year + 1))
    table = pd.DataFrame({
        TARGET: price,
        "price_lag_1d": same_hour_lag(price, index, 1),
        "price_lag_2d": same_hour_lag(price, index, 2),
        "price_lag_7d": same_hour_lag(price, index, 7),
        "demand_forecast": demand,
        "wind_forecast": wind,
        "solar_forecast": solar,
        "gas_gen_lag": gas_lag,
        "temp_forecast": temp,
        "hour": hour,
        "weekday": weekday,
        "month": index.month.to_numpy(),
        "is_holiday": [int(d in german_holidays) for d in index.date],
        OIL_FEATURE: oil_change,
    }, index=index)
    return table[table.index >= pd.Timestamp(TRAIN_START, tz=TIMEZONE)]


def train_throwaway(table, features, path):
    train_end = pd.Timestamp(TRAIN_END, tz=TIMEZONE) + pd.Timedelta(days=1)
    train = table[table.index < train_end]
    params = {"objective": "regression", "learning_rate": 0.05, "num_leaves": 31,
              "seed": SEED, "deterministic": True, "verbose": -1}
    booster = lgb.train(params, lgb.Dataset(train[features], train[TARGET]), num_boost_round=SAMPLE_TREES)
    booster.save_model(str(path))
    return len(train)


def main():
    table = make_table()
    missing = int(table.isna().sum().sum())
    if missing:
        raise SystemExit(f"Sample table has {missing} missing values")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_parquet(SAMPLE_FEATURES_FILE)
    print(f"SYNTHETIC feature table: {len(table)} rows, {table.index[0]} to {table.index[-1]}")
    print(f"  columns: {list(table.columns)}")
    print(f"  saved to {SAMPLE_FEATURES_FILE}")

    for name, features in (("blind", FEATURES_BLIND), ("oil", FEATURES_OIL)):
        rows = train_throwaway(table, features, SAMPLE_MODEL_FILES[name])
        print(f"Throwaway {name} model: {len(features)} features, {rows} training rows, "
              f"saved to {SAMPLE_MODEL_FILES[name]}")


if __name__ == "__main__":
    main()

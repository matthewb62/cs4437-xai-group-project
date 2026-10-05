"""Build the feature table from the cleaned hourly table (F1-F11).

Reads data/processed/clean_hourly.parquet and writes the handover file
data/processed/features.parquet, plus results/oil_range.json (F10).

One rule decides every lag here: a feature for delivery hour h of day D must
have been known before the auction closed at 12:00 on day D-1.

  F2   price lags are the same Berlin clock hour 1, 2 and 7 days earlier
  F3   demand, wind and solar are the day-ahead forecasts for the hour itself
  F4   gas is the same clock hour from the 24 hours before 12:00 on D-1:
       hours 0-11 come from D-1, hours 12-23 from D-2
  F5   temperature is already the forecast issued 2 days ahead (the download
       asks for temperature_2m_previous_day2), so it needs no further lag
  F7   oil is the 30-day % change of the last Brent close published on or
       before D-2
  F11  every lagged column records the timestamp it read, and those are
       checked against the D-1 cut-off before anything is saved

Usage:
    python src/build_features.py
"""
import json

import holidays
import numpy as np
import pandas as pd

from clean_data import GAS, OIL_CLOSE, PRICE
from config import (
    AUCTION_CLOSE_HOUR, CLEAN_FILE, FEATURES_BLIND, FEATURES_FILE, FEATURES_OIL,
    OIL_CHANGE_DAYS, OIL_LAG_DAYS, PROCESSED_DIR, RESULTS_DIR, SHOCK_DATE, TARGET,
    TIMEZONE, TRAIN_END, TRAIN_START,
)

OIL_RANGE_FILE = RESULTS_DIR / "oil_range.json"
PRICE_LAG_DAYS = {"price_lag_1d": 1, "price_lag_2d": 2, "price_lag_7d": 7}

# When a lagged value became known, from the timestamp it carries. The cut-off
# applies to this, not to the label: a price stamped on D-1 was set at the
# auction on D-2, so a one-day price lag is safe while a one-day gas lag is not.
KNOWN_AT = {
    # day-ahead prices for a delivery day are set when that day's auction closes
    "price": lambda stamp: (stamp.normalize() - pd.Timedelta(days=1)
                            + pd.Timedelta(hours=AUCTION_CLOSE_HOUR)),
    # actual generation for an hour is only known once the hour has finished
    "gas": lambda stamp: stamp + pd.Timedelta(hours=1),
    # the oil stamp is already the end of the day the close was published
    "oil": lambda stamp: stamp,
}
PUBLICATION = {
    **{column: "price" for column in PRICE_LAG_DAYS},
    "gas_gen_lag": "gas",
    "oil_change_30d": "oil",
}


class FeatureError(RuntimeError):
    pass


# ---------------------------------------------------------------- lags

def wall_clock(index):
    """The Berlin wall-clock reading of each row, with no offset attached."""
    return index.tz_localize(None)


def same_hour_lag(values, index, days):
    """The value at the same Berlin clock hour `days` earlier, and where it came from.

    Lagging by wall clock rather than by a fixed 24 hours is what "the same
    Berlin-time hour" means, and it is what keeps 09:00 lined up with 09:00
    across a clock change. Two consequences, both reported by main():

      spring forward  02:00 does not exist, so the next day's 02:00 has no
                      source and the row is dropped by F9
      autumn back     02:00 happens twice, so both rows read the first of the
                      two readings on the source day

    Returns the lagged values and the wall-clock timestamp each one was read
    from, as NaT where there was no such hour.
    """
    wall = wall_clock(index)
    source = wall - pd.Timedelta(days=days)
    by_wall = pd.Series(np.asarray(values), index=wall).groupby(level=0).first()
    lagged = by_wall.reindex(source)
    return lagged.to_numpy(), pd.DatetimeIndex(source).where(source.isin(by_wall.index))


def gas_lag(values, index, close_hour):
    """F4: the same clock hour from the 24 hours before close_hour on D-1.

    Hours before the auction closes take D-1, the rest take D-2, so no value is
    ever stamped at or after close_hour on D-1.
    """
    one_day, one_source = same_hour_lag(values, index, 1)
    two_day, two_source = same_hour_lag(values, index, 2)
    before_close = index.hour < close_hour
    values = np.where(before_close, one_day, two_day)
    source = one_source.where(before_close, two_source)
    return values, source


def oil_change(closes, index, lag_days, change_days):
    """F7: the 30-day % change in Brent, read from the last close before the auction.

    closes is the daily close already carried forward over weekends (C6), so
    "the last close published on or before D-2" is simply the value at D-2.
    """
    daily = closes.groupby(wall_clock(index).normalize()).first()
    days = pd.DatetimeIndex(daily.index)
    recent = daily.reindex(days - pd.Timedelta(days=lag_days)).to_numpy()
    earlier = daily.reindex(days - pd.Timedelta(days=lag_days + change_days)).to_numpy()
    change = pd.Series((recent / earlier - 1) * 100, index=days)

    delivery_day = wall_clock(index).normalize()
    values = change.reindex(delivery_day).to_numpy()
    # The close is published at the end of its own day, so stamp it 23:00 on D-2:
    # the latest moment it could have become known, and still before D-1 noon.
    source = pd.DatetimeIndex(delivery_day - pd.Timedelta(days=lag_days)
                              + pd.Timedelta(hours=23))
    return values, source.where(~np.isnan(values))


# ---------------------------------------------------------------- the table

def build(clean):
    """The feature table and, beside it, the source timestamp of every lagged column."""
    index = clean.index
    price = clean[PRICE].to_numpy()
    sources = {}

    table = pd.DataFrame(index=index)
    table[TARGET] = price
    for column, days in PRICE_LAG_DAYS.items():
        table[column], sources[column] = same_hour_lag(price, index, days)
    for column in ("demand_forecast", "wind_forecast", "solar_forecast"):
        table[column] = clean[column].to_numpy()          # F3: the forecast for this hour
    table["gas_gen_lag"], sources["gas_gen_lag"] = gas_lag(
        clean[GAS].to_numpy(), index, AUCTION_CLOSE_HOUR)
    table["temp_forecast"] = clean["temp_forecast"].to_numpy()   # F5: already a D-2 forecast

    german_holidays = holidays.Germany()                  # F6: nationwide, no state
    table["hour"] = index.hour
    table["weekday"] = index.weekday
    table["month"] = index.month
    table["is_holiday"] = [int(day in german_holidays) for day in index.date]

    table["oil_change_30d"], sources["oil_change_30d"] = oil_change(
        clean[OIL_CLOSE], index, OIL_LAG_DAYS, OIL_CHANGE_DAYS)
    return table[FEATURES_OIL + [TARGET]], sources


def check_no_leakage(index, sources):
    """F11: nothing a feature reads may have become known after 12:00 on D-1.

    The 11:00 hour of D-1 finishes exactly at the cut-off, so a value known at
    12:00 passes and anything later fails. That edge is the known limitation
    the method doc records for the gas lag.
    """
    cutoff = (wall_clock(index).normalize() - pd.Timedelta(days=1)
              + pd.Timedelta(hours=AUCTION_CLOSE_HOUR))
    late = {}
    for column, source in sources.items():
        known = KNOWN_AT[PUBLICATION[column]](pd.DatetimeIndex(source))
        after = known.notna() & (known > cutoff)
        if after.any():
            first = index[after][0]
            late[column] = (f"{after.sum()} rows, first at {first}, known only at "
                            f"{known[after][0]}")
    if late:
        listed = "; ".join(f"{column}: {detail}" for column, detail in late.items())
        raise FeatureError(f"Leakage past the D-1 {AUCTION_CLOSE_HOUR}:00 cut-off: {listed}")
    return cutoff


def drop_incomplete_rows(table):
    """F9: one set of rows for both models, so a missing lag drops the row entirely."""
    complete = table.notna().all(axis=1)
    return table[complete], table[~complete]


def oil_range(table, train_start, train_end, shock_date):
    """F10: the largest 30-day oil % change in the training window and in the test window."""
    oil = table["oil_change_30d"]
    windows = {
        "training": oil[(oil.index >= pd.Timestamp(train_start, tz=TIMEZONE))
                        & (oil.index < pd.Timestamp(train_end, tz=TIMEZONE) + pd.Timedelta(days=1))],
        "test": oil[oil.index >= pd.Timestamp(shock_date, tz=TIMEZONE)],
    }
    numbers = {}
    for name, values in windows.items():
        if values.empty:
            numbers[f"largest_30d_oil_change_{name}_pct"] = None
            continue
        largest = values.loc[values.abs().idxmax()]
        numbers[f"largest_30d_oil_change_{name}_pct"] = round(float(largest), 2)
        numbers[f"range_30d_oil_change_{name}_pct"] = [round(float(values.min()), 2),
                                                       round(float(values.max()), 2)]
    return numbers


# ---------------------------------------------------------------- reporting

def print_dropped_rows(dropped, clean_index, kept):
    """F9, and the clock-change counts the journal needs."""
    print(f"\nRows dropped for a missing feature (F9): {len(dropped)}")
    if len(dropped):
        reasons = dropped.isna().sum()
        for column, count in reasons[reasons > 0].items():
            print(f"  {column:<18} {count:>8} rows missing")
        skipped = int(dropped["price_lag_1d"].isna().sum())
        print(f"  {skipped} of them are the 02:00 hour a spring clock change skipped")

    # The clock changes are counted on the cleaned grid, which is complete.
    # Counting them on the kept rows would read a dropped row as a short day.
    span = clean_index[(clean_index >= kept.index[0]) & (clean_index <= kept.index[-1])]
    hours = pd.Series(1, index=span).groupby(span.date).size()
    kept_hours = pd.Series(1, index=kept.index).groupby(kept.index.date).size()
    short = int((kept_hours.reindex(hours.index, fill_value=0) < hours).sum())
    print(f"Clock changes over the feature window (C2): {(hours == 23).sum()} days of 23 hours, "
          f"{(hours == 25).sum()} of 25, {(hours == 24).sum()} of 24")
    print(f"Days left short of an hour by the drops: {short} of {len(hours)}")


def print_summary(table, cutoff_checked):
    print("\nFeature table (F1-F8)")
    print(f"  {len(table)} rows, {table.index[0]} to {table.index[-1]}")
    print(f"  blind features ({len(FEATURES_BLIND)}): {FEATURES_BLIND}")
    print(f"  oil features   ({len(FEATURES_OIL)}): +{sorted(set(FEATURES_OIL) - set(FEATURES_BLIND))}")
    print(f"  missing values: {int(table.isna().sum().sum())}")
    if cutoff_checked:
        print(f"  F11: every lagged column reads a timestamp before "
              f"{AUCTION_CLOSE_HOUR}:00 on D-1")


def main():
    if not CLEAN_FILE.exists():
        raise FeatureError(f"{CLEAN_FILE} not found. Run python src/clean_data.py first.")
    clean = pd.read_parquet(CLEAN_FILE)
    print(f"Building features from {CLEAN_FILE}: {len(clean)} cleaned hours")

    table, sources = build(clean)

    # The hours before TRAIN_START are only there to be read as lags, so they
    # leave the table before anything is counted as a dropped row.
    inside = table.index >= pd.Timestamp(TRAIN_START, tz=TIMEZONE)
    table = table[inside]
    sources = {column: source[inside] for column, source in sources.items()}
    if table.empty:
        raise FeatureError(f"No rows left on or after {TRAIN_START}")

    check_no_leakage(table.index, sources)
    table, dropped = drop_incomplete_rows(table)

    print_dropped_rows(dropped, clean.index, table)
    print_summary(table, cutoff_checked=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_parquet(FEATURES_FILE)
    print(f"\nWrote {FEATURES_FILE}")

    numbers = oil_range(table, TRAIN_START, TRAIN_END, SHOCK_DATE)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OIL_RANGE_FILE.write_text(json.dumps(numbers, indent=2), encoding="utf-8")
    print(f"Wrote {OIL_RANGE_FILE} (F10): {numbers}")


if __name__ == "__main__":
    try:
        main()
    except FeatureError as error:
        raise SystemExit(f"Feature build stopped: {error}")

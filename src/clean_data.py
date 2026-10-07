"""Turn the raw downloads into one hourly table in Berlin local time (C1-C8).

Reads only the files download_data.py wrote, and writes
data/processed/clean_hourly.parquet for build_features.py.

What it does, in order:
  C1  every series is averaged to hourly in UTC, so the late-2025 switch from
      hourly to 15-minute steps needs no special case
  C2  the hourly UTC grid is converted to Europe/Berlin, which gives 23 and 25
      hour clock-change days on its own
  C3  short gaps in the input series are interpolated, longer ones are left
      missing and reported; the price is never filled, because it is the target
  C4  prices are passed through untouched, negative values and spikes included
  C5  the five city temperature forecasts become one population-weighted column;
      before the forecast archive begins, the same weighting of ERA5
      reanalysis stands in for it
  C6  Brent is carried forward over weekends and holidays

Rows are never dropped here: the table keeps a complete hourly index so that C2
can be checked on it, and build_features.py drops the rows whose features are
missing (F9).

Usage:
    python src/clean_data.py
"""
import numpy as np
import pandas as pd

from config import (
    CITIES, CLEAN_FILE, DOWNLOAD_START, MAX_GAP_HOURS, PROCESSED_DIR, RAW_DIR,
    TARGET, TIMEZONE,
)
from download_data import FORECAST_TYPES, SERIES_FILES

# Columns of the cleaned table. Only the names build_features.py carries through
# to the feature table are fixed by the shared contract; the rest are internal.
PRICE = TARGET
DEMAND = "demand_forecast"
WIND = "wind_forecast"
SOLAR = "solar_forecast"
GAS = "gas_gen"          # actual generation, not yet lagged: F4 does that
TEMP = "temp_forecast"
OIL_CLOSE = "oil_close"  # daily Brent close, carried forward, repeated over the day

CLEAN_COLUMNS = [PRICE, DEMAND, WIND, SOLAR, GAS, TEMP, OIL_CLOSE]
FILLED_COLUMNS = [DEMAND, WIND, SOLAR, GAS, TEMP]   # never the price (C3), never oil (C6)

FORECAST_COLUMNS = {"load": DEMAND, "solar": SOLAR}   # wind_onshore + wind_offshore are summed
BRENT_FILE = "brent.csv"
PRICE_FILE = "price_de_lu.csv"
GAS_FILE = "generation_gas.csv"

# An hour whose quarter-hours are only partly there is averaged over what is
# there. Stop if that happens often enough to bias a series.
INCOMPLETE_HOUR_LIMIT = 0.01


class CleaningError(RuntimeError):
    pass


# ---------------------------------------------------------------- raw files

def read_raw(filename):
    """One raw file as a UTC-indexed series, sorted, with duplicate stamps dropped."""
    path = RAW_DIR / filename
    if not path.exists():
        raise CleaningError(f"{path} not found. Run python src/download_data.py first.")
    time_col, unit = SERIES_FILES[filename]
    frame = pd.read_csv(path)
    if time_col not in frame.columns or len(frame.columns) < 2:
        raise CleaningError(f"{filename}: expected a '{time_col}' column and a value "
                            f"column, found {list(frame.columns)}")
    value_col = frame.columns[1]
    stamps = pd.to_datetime(frame[time_col], unit=unit, utc=True)
    values = pd.to_numeric(frame[value_col], errors="coerce")   # FRED writes '.' for no close
    series = pd.Series(values.to_numpy(), index=stamps, name=value_col).sort_index()
    return series[~series.index.duplicated(keep="first")]


def native_steps(series):
    """Median spacing in minutes per calendar year, so the 15-minute switch is visible."""
    minutes = series.index.to_series().diff().dt.total_seconds() / 60
    return minutes.groupby(series.index.year).median().round().astype("Int64")


# ---------------------------------------------------------------- C1, C2

def hourly_mean(series):
    """C1: the mean of the points inside each UTC hour.

    An hourly stretch has one point per hour and keeps its value; a 15-minute
    stretch is averaged over its four quarter-hours, so both sides of the late
    2025 switch go through the same code. Returns the hourly series and the
    number of hours that held fewer points than their own day's step implies.
    """
    counts = series.resample("h").count()
    hourly = series.resample("h").mean()
    per_day = counts.groupby(counts.index.floor("D")).max()
    expected = per_day.reindex(counts.index.floor("D")).to_numpy()
    present = counts.to_numpy()
    incomplete = int(((present > 0) & (present < expected)).sum())
    return hourly, incomplete


def berlin_hour_index(first_day, last_day):
    """C2: every hour of the Berlin days first_day..last_day, built in UTC.

    Generating the grid in UTC and converting is what gives clock-change days 23
    or 25 rows; shifting by a fixed number of hours would not.
    """
    start = pd.Timestamp(first_day, tz=TIMEZONE).tz_convert("UTC")
    end = (pd.Timestamp(last_day, tz=TIMEZONE) + pd.Timedelta(days=1)).tz_convert("UTC")
    index = pd.date_range(start, end, freq="h", inclusive="left", tz="UTC")
    return index.tz_convert(TIMEZONE).rename("timestamp")


def rows_per_day(index):
    """Rows per Berlin calendar day: 23 and 25 on the clock changes, 24 elsewhere."""
    return pd.Series(1, index=index).groupby(index.date).size()


# ---------------------------------------------------------------- C3

def fill_short_gaps(series, max_gap):
    """C3: interpolate runs of at most max_gap missing hours, leave longer runs.

    Only gaps inside the series' own coverage are filled. Hours before a series
    starts, such as the price before the first complete day, are not gaps.
    Returns the series, the hours filled and the hours left in longer gaps.
    """
    covered = series.notna()
    if not covered.any():
        return series, 0, int(series.isna().sum())
    inside = series.loc[covered.idxmax():covered[::-1].idxmax()]
    gap = inside.isna()
    if not gap.any():
        return series, 0, 0
    run = gap.ne(gap.shift()).cumsum()
    length = gap.groupby(run).transform("size").where(gap, 0)
    short = gap & (length <= max_gap)
    filled = series.copy()
    filled.loc[inside.index[short]] = inside.interpolate(method="time")[short]
    return filled, int(short.sum()), int((gap & ~short).sum())


# ---------------------------------------------------------------- C5, C6

def weighted_temperature(city_series, weights):
    """C5: one population-weighted temperature column from the five cities.

    An hour is missing unless every city has a value, so the weighting never
    silently changes from one hour to the next.
    """
    frame = pd.DataFrame(city_series)
    share = pd.Series(weights, dtype=float)
    share = share / share.sum()
    weighted = (frame[share.index] * share).sum(axis=1)
    return weighted.where(frame.notna().all(axis=1))


def city_temperature(hourly, prefix, align=lambda series: series):
    """C5 applied to the five city series in `hourly` whose label starts with prefix."""
    return weighted_temperature(
        {city: align(hourly[f"{prefix}{city}"]) for city in CITIES},
        {city: weight for city, (_lat, _lon, weight) in CITIES.items()},
    )


def splice_temperature(forecast, reanalysis):
    """C5: the forecast where its archive has begun, ERA5 reanalysis before that.

    The reanalysis only fills the hours before the forecast's first value. A
    gap after that stays a gap, so the validation, baseline and test periods
    only ever see a temperature that was forecast before the auction.
    Returns the spliced series and the first hour taken from the forecast.
    """
    if not forecast.notna().any():
        raise CleaningError("The temperature forecast has no values at all")
    first = forecast.first_valid_index()
    spliced = forecast.copy()
    before = spliced.index < first
    spliced[before] = reanalysis.reindex(spliced.index)[before]
    return spliced, first


def daily_oil_close(brent, days):
    """C6: the last published Brent close on or before each calendar day."""
    closes = brent.copy()
    closes.index = pd.DatetimeIndex(closes.index.tz_convert(None).date)
    closes = closes.groupby(level=0).last().dropna()
    days = pd.DatetimeIndex(days)
    return closes.reindex(closes.index.union(days)).ffill().reindex(days)


# ---------------------------------------------------------------- assembly

def load_hourly_inputs():
    """Every raw series, averaged to hourly UTC. Returns the series and a report."""
    report = {}
    hourly = {}

    def take(filename, label):
        raw = read_raw(filename)
        values, incomplete = hourly_mean(raw)
        report[label] = {
            "raw_rows": len(raw),
            "steps": native_steps(raw).to_dict(),
            "incomplete": incomplete,
            "hours": int((raw.resample("h").count() > 0).sum()),
        }
        hourly[label] = values

    take(PRICE_FILE, PRICE)
    for kind in FORECAST_TYPES:
        take(f"forecast_{kind}.csv", f"forecast_{kind}")
    take(GAS_FILE, GAS)
    for city in CITIES:
        take(f"temperature_{city}.csv", f"temperature_{city}")
    for city in CITIES:
        take(f"temperature_era5_{city}.csv", f"temperature_era5_{city}")
    return hourly, report


def check_incomplete_hours(report):
    """Stop if averaging over part-filled hours would bias a series."""
    bad = {
        label: counts["incomplete"] / counts["hours"]
        for label, counts in report.items()
        if counts["hours"] and counts["incomplete"] / counts["hours"] > INCOMPLETE_HOUR_LIMIT
    }
    if bad:
        listed = ", ".join(f"{label} {share:.1%}" for label, share in bad.items())
        raise CleaningError(
            f"More than {INCOMPLETE_HOUR_LIMIT:.0%} of hours are part-filled: {listed}. "
            "The hourly means for these series would be biased; check the download."
        )


def complete_price_days(price):
    """The first and last Berlin day on which every hour of the day has a price.

    The day is measured against the full Berlin grid, which is 23 or 25 hours
    long on a clock change, so a part-downloaded first or last day is not
    mistaken for a complete one.
    """
    grid = berlin_hour_index(price.index[0].date(), price.index[-1].date())
    present = price.reindex(grid).notna().groupby(grid.date).sum()
    complete = present == rows_per_day(grid)
    if not complete.any():
        raise CleaningError("No Berlin day has a price for all of its hours")
    days = complete[complete].index
    return days[0], days[-1]


def assemble(hourly, brent):
    """Put every hourly series on one Berlin index covering the complete price days."""
    price_berlin = hourly[PRICE].tz_convert(TIMEZONE)
    first_day, last_day = complete_price_days(price_berlin)
    index = berlin_hour_index(first_day, last_day)

    def on_index(series):
        return series.tz_convert(TIMEZONE).reindex(index)

    table = pd.DataFrame(index=index)
    table[PRICE] = on_index(hourly[PRICE])
    for kind, column in FORECAST_COLUMNS.items():
        table[column] = on_index(hourly[f"forecast_{kind}"])
    table[WIND] = (on_index(hourly["forecast_wind_onshore"])
                   + on_index(hourly["forecast_wind_offshore"]))
    table[GAS] = on_index(hourly[GAS])
    table[TEMP], _first = splice_temperature(
        city_temperature(hourly, "temperature_", on_index),
        city_temperature(hourly, "temperature_era5_", on_index))
    days = pd.date_range(min(pd.Timestamp(DOWNLOAD_START), pd.Timestamp(index[0].date())),
                         pd.Timestamp(index[-1].date()), freq="D")
    oil = daily_oil_close(brent, days)
    table[OIL_CLOSE] = oil.reindex(pd.DatetimeIndex(index.date)).to_numpy()
    return table[CLEAN_COLUMNS]


def fill_gaps(table, max_gap):
    """C3 over the input columns. The price is left exactly as it arrived."""
    before = table.isna().sum()
    filled, long_gaps = {}, {}
    for column in FILLED_COLUMNS:
        table[column], filled[column], long_gaps[column] = fill_short_gaps(table[column], max_gap)
    return table, before, filled, long_gaps


# ---------------------------------------------------------------- reporting

def print_download_summary(report):
    print("\nRaw series (C1)")
    print(f"{'series':<26} {'raw rows':>9} {'hours':>8} {'part-filled':>14}  "
          f"native step (min) by year")
    for label, counts in report.items():
        steps = ", ".join(f"{year}: {step}" for year, step in counts["steps"].items())
        share = counts["incomplete"] / counts["hours"] if counts["hours"] else 0
        print(f"{label:<26} {counts['raw_rows']:>9} {counts['hours']:>8} "
              f"{counts['incomplete']:>7} ({share:>5.2%})  {steps}")


def print_gap_summary(table, before, filled, long_gaps):
    print(f"\nMissing hours per series, before and after filling (C3, limit {MAX_GAP_HOURS} h)")
    print(f"{'column':<18} {'before':>8} {'filled':>8} {'after':>8}  note")
    for column in CLEAN_COLUMNS:
        note = ""
        if column == PRICE:
            note = "target, never filled"
        elif column == OIL_CLOSE:
            note = "daily close carried forward"
        if long_gaps.get(column):
            note = f"{long_gaps[column]} hours in gaps longer than {MAX_GAP_HOURS} h"
        print(f"{column:<18} {before[column]:>8} {filled.get(column, 0):>8} "
              f"{table[column].isna().sum():>8}  {note}")
    print("Hours still missing keep their row here; build_features.py drops them (F9).")


def print_temperature_splice(hourly):
    """C5: where the reanalysis hands over to the forecast, and how far apart they are."""
    forecast = city_temperature(hourly, "temperature_")
    reanalysis = city_temperature(hourly, "temperature_era5_")
    _spliced, first = splice_temperature(forecast, reanalysis)
    both = pd.concat([forecast, reanalysis], axis=1, keys=["forecast", "era5"]).dropna()
    print(f"\nTemperature (C5): ERA5 reanalysis before {first.tz_convert(TIMEZONE)}, "
          f"the 2-day-ahead forecast from then on")
    if both.empty:
        print("  the two never overlap, so their difference cannot be measured")
        return
    error = both["forecast"] - both["era5"]
    print(f"  over the {len(both)} hours both exist ({both.index[0].date()} to "
          f"{both.index[-1].date()}): forecast minus ERA5 has mean {error.mean():+.2f} C, "
          f"mean absolute {error.abs().mean():.2f} C")


def print_clock_changes(index):
    counts = rows_per_day(index)
    odd = counts[~counts.isin([23, 24, 25])]
    if len(odd):
        raise CleaningError(f"Days with an impossible number of hours: {odd.to_dict()}")
    short, long = counts[counts == 23], counts[counts == 25]
    print(f"\nClock changes (C2): {len(short)} days of 23 hours, {len(long)} of 25 hours, "
          f"{len(counts[counts == 24])} of 24")
    print(f"  spring forward: {', '.join(str(day) for day in short.index)}")
    print(f"  autumn back:    {', '.join(str(day) for day in long.index)}")


def print_quality_summary(table, raw_min_price):
    """C8: date range, row count and percentage missing per column."""
    print("\nCleaned table (C7, C8)")
    print(f"  {len(table)} rows, {table.index[0]} to {table.index[-1]}")
    print(f"  {'column':<18} {'% missing':>10}")
    for column in table.columns:
        print(f"  {column:<18} {table[column].isna().mean() * 100:>9.2f}%")
    low = table[PRICE].min()
    print(f"\nPrice (C4): minimum {low:.2f} EUR/MWh, raw minimum {raw_min_price:.2f}, "
          f"maximum {table[PRICE].max():.2f}")
    if not np.isclose(low, raw_min_price):
        raise CleaningError(
            f"Cleaned minimum price {low} does not match the raw minimum {raw_min_price}: "
            "something clipped or dropped an extreme price"
        )


def main():
    print(f"Cleaning {RAW_DIR} into {CLEAN_FILE}")
    hourly, report = load_hourly_inputs()
    print_download_summary(report)
    check_incomplete_hours(report)

    print_temperature_splice(hourly)
    table = assemble(hourly, read_raw(BRENT_FILE))
    table, before, filled, long_gaps = fill_gaps(table, MAX_GAP_HOURS)
    print_gap_summary(table, before, filled, long_gaps)
    print_clock_changes(table.index)
    print_quality_summary(table, read_raw(PRICE_FILE).min())

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_parquet(CLEAN_FILE)
    print(f"\nWrote {CLEAN_FILE}")


if __name__ == "__main__":
    try:
        main()
    except CleaningError as error:
        raise SystemExit(f"Cleaning stopped: {error}")

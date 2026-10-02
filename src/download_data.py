"""Download the raw datasets into data/raw/.

Use this script to get the data. Don't download files manually.

Do not commit the data/ folder.

Each series is saved as received: one CSV per series, original timestamps,
original resolution. Cleaning happens in clean_data.py.

Fetched chunks are cached in data/raw/_chunks/, so a re-run only fetches new
dates. Delete that folder to force a full download.

Usage:
    python src/download_data.py
"""
import csv
import json
import os
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

from config import CITIES, DOWNLOAD_END, DOWNLOAD_START, RAW_DIR

ENERGY_CHARTS = "https://api.energy-charts.info"
OPEN_METEO = "https://previous-runs-api.open-meteo.com/v1/forecast"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

FORECAST_TYPES = ["load", "solar", "wind_onshore", "wind_offshore"]
GAS_SERIES = "Fossil gas"            # not "Fossil coal-derived gas"
TEMP_VARIABLE = "temperature_2m_previous_day2"
TEMP_MODEL = "icon_seamless"

# Raw file -> (timestamp column, pandas to_datetime unit). The value is column 2.
SERIES_FILES = {
    "price_de_lu.csv": ("unix_seconds", "s"),
    **{f"forecast_{t}.csv": ("unix_seconds", "s") for t in FORECAST_TYPES},
    "generation_gas.csv": ("unix_seconds", "s"),
    **{f"temperature_{c}.csv": ("time_utc", None) for c in CITIES},
    "brent.csv": ("observation_date", None),
}

SOURCES = {
    "energy-charts": {
        "url": ENERGY_CHARTS,
        "licence": "CC BY 4.0, energy-charts.info (prices: Bundesnetzagentur | SMARD.de)",
    },
    "open-meteo": {
        "url": f"{OPEN_METEO}?hourly={TEMP_VARIABLE}&models={TEMP_MODEL}",
        "licence": "CC BY 4.0, Open-Meteo.com",
    },
    "fred": {
        "url": f"{FRED_CSV}?id=DCOILBRENTEU",
        "licence": "Public domain (U.S. Energy Information Administration via FRED); citation requested",
    },
}

CHUNK_DIR = RAW_DIR / "_chunks"   # cache of fetched chunks, so re-runs only fetch new dates
FINAL_AFTER_DAYS = 7              # a chunk that ended this long ago is not refetched

TIMEOUT = 120
EC_PAUSE_SECONDS = 31     # energy-charts allows about 2 requests per minute per endpoint
MAX_RETRIES = 5

_last_request = {}        # endpoint -> time.monotonic() of its last request


class DownloadError(RuntimeError):
    pass


def _retry_after_seconds(header, default=60):
    """Retry-After is either a number of seconds or an HTTP date."""
    if header is None:
        return default
    try:
        return max(0, int(header))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return default
    return max(0, int((when - datetime.now(timezone.utc)).total_seconds()))


def _get(url, params, label, endpoint=None):
    """GET with per-endpoint rate limiting and Retry-After handling.

    Raises DownloadError on any failure, naming the series and dates.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        if endpoint in _last_request:
            wait = EC_PAUSE_SECONDS - (time.monotonic() - _last_request[endpoint])
            if wait > 0:
                time.sleep(wait)
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise DownloadError(f"{label}: request failed ({e})") from e
        finally:
            if endpoint is not None:
                _last_request[endpoint] = time.monotonic()
        if resp.status_code == 429:
            retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
            print(f"  {label}: HTTP 429, waiting {retry_after} s (attempt {attempt})")
            time.sleep(retry_after)
            continue
        if not resp.ok:
            raise DownloadError(f"{label}: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp
    raise DownloadError(f"{label}: still rate limited after {MAX_RETRIES} attempts")


def _year_chunks(start, end):
    """Split [start, end] (ISO dates, inclusive) into calendar-year pieces."""
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    chunks = []
    while start <= end:
        chunk_end = min(date(start.year, 12, 31), end)
        chunks.append((start.isoformat(), chunk_end.isoformat()))
        start = date(start.year + 1, 1, 1)
    return chunks


def _cached_chunk(name, start, end, fetch):
    """Return a chunk's rows from data/raw/_chunks/ if still valid, else fetch().

    A saved chunk is reused when it ended at least FINAL_AFTER_DAYS ago (the
    source has stopped revising it) or when it was fetched today. Anything
    else, such as the current year's chunk on a later day, is fetched again.
    """
    path = CHUNK_DIR / f"{name}_{start}_{end}.json"
    today = date.today()
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        final = (today - date.fromisoformat(end)).days >= FINAL_AFTER_DAYS
        if final or saved["fetched"] == today.isoformat():
            return saved["rows"]
    rows = [list(r) for r in fetch()]
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps({"fetched": today.isoformat(), "rows": rows}),
                   encoding="utf-8")
    os.replace(tmp, path)
    for old in CHUNK_DIR.glob(f"{name}_{start}_*.json"):   # superseded shorter copies
        if old != path:
            old.unlink()
    return rows


def _write_csv(filename, header, rows, label):
    """Write rows via a temporary file, so a failed run never leaves a partial file."""
    if not rows:
        raise DownloadError(f"{label}: no rows to save")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / filename
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(tmp, path)
    print(f"  saved {filename}: {len(rows)} rows")


def _energy_charts_series(endpoint, params, value_key, name, label):
    """Fetch one energy-charts series a year at a time, reusing saved chunks.

    value_key is the JSON key holding the values, or a function
    f(payload, chunk_label) that returns them. name keys the chunk cache.
    Returns a list of (unix_seconds, value) rows.
    """
    rows = []
    for start, end in _year_chunks(DOWNLOAD_START, DOWNLOAD_END):
        chunk_label = f"{label} {start}..{end}"

        def fetch(start=start, end=end, chunk_label=chunk_label):
            print(f"  fetching {chunk_label}")
            resp = _get(f"{ENERGY_CHARTS}/{endpoint}",
                        {**params, "start": start, "end": end},
                        chunk_label, endpoint=endpoint)
            payload = resp.json()
            stamps = payload.get("unix_seconds") or []
            if callable(value_key):
                values = value_key(payload, chunk_label)
            else:
                values = payload.get(value_key)
            if not stamps or not values:
                raise DownloadError(f"{chunk_label}: empty response")
            if len(stamps) != len(values):
                raise DownloadError(
                    f"{chunk_label}: {len(stamps)} timestamps but {len(values)} values")
            return zip(stamps, values)

        rows.extend(_cached_chunk(name, start, end, fetch))
    return rows


def download_price():
    label = "price DE-LU"
    rows = _energy_charts_series("price", {"bzn": "DE-LU"}, "price", "price_de_lu", label)
    _write_csv("price_de_lu.csv", ["unix_seconds", "price"], rows, label)


def download_forecasts():
    for production_type in FORECAST_TYPES:
        label = f"forecast {production_type}"
        name = f"forecast_{production_type}"
        params = {"country": "de", "production_type": production_type,
                  "forecast_type": "day-ahead"}
        rows = _energy_charts_series("public_power_forecast", params,
                                     "forecast_values", name, label)
        _write_csv(f"{name}.csv", ["unix_seconds", "forecast"], rows, label)


def _fossil_gas(payload, chunk_label):
    for series in payload.get("production_types") or []:
        if series.get("name") == GAS_SERIES:
            return series.get("data")
    raise DownloadError(f"{chunk_label}: no '{GAS_SERIES}' series in the response")


def download_gas():
    label = "generation gas"
    rows = _energy_charts_series("public_power", {"country": "de"}, _fossil_gas,
                                 "generation_gas", label)
    _write_csv("generation_gas.csv", ["unix_seconds", "gas"], rows, label)


def download_temperature():
    for city, (lat, lon, _weight) in CITIES.items():
        name = f"temperature_{city}"
        rows = []
        for start, end in _year_chunks(DOWNLOAD_START, DOWNLOAD_END):
            chunk_label = f"temperature {city} {start}..{end}"

            def fetch(start=start, end=end, chunk_label=chunk_label):
                print(f"  fetching {chunk_label}")
                params = {"latitude": lat, "longitude": lon, "hourly": TEMP_VARIABLE,
                          "models": TEMP_MODEL, "start_date": start,
                          "end_date": end, "timezone": "GMT"}
                hourly = _get(OPEN_METEO, params, chunk_label).json().get("hourly") or {}
                stamps = hourly.get("time") or []
                values = hourly.get(TEMP_VARIABLE) or []
                if not stamps:
                    raise DownloadError(f"{chunk_label}: empty response")
                if len(stamps) != len(values):
                    raise DownloadError(
                        f"{chunk_label}: {len(stamps)} timestamps but {len(values)} values")
                return zip(stamps, values)

            rows.extend(_cached_chunk(name, start, end, fetch))
        # The archive begins in January 2024, so early chunks can be all null.
        label = f"temperature {city} {DOWNLOAD_START}..{DOWNLOAD_END}"
        if all(value is None for _, value in rows):
            raise DownloadError(f"{label}: every value is missing")
        _write_csv(f"{name}.csv", ["time_utc", TEMP_VARIABLE], rows, label)


def download_brent():
    label = f"brent {DOWNLOAD_START}..{DOWNLOAD_END}"

    def fetch():
        print(f"  fetching {label}")
        params = {"id": "DCOILBRENTEU", "cosd": DOWNLOAD_START, "coed": DOWNLOAD_END}
        text = _get(FRED_CSV, params, label).text
        rows = list(csv.reader(text.splitlines()))
        if len(rows) < 2 or rows[0] != ["observation_date", "DCOILBRENTEU"]:
            raise DownloadError(f"{label}: unexpected response: {text[:200]!r}")
        return rows

    # One small request for the whole range, so only same-day reruns reuse it.
    rows = _cached_chunk("brent", DOWNLOAD_START, DOWNLOAD_END, fetch)
    _write_csv("brent.csv", rows[0], rows[1:], label)


def print_summary():
    """D11: first and last timestamp, row count and missing values per series."""
    print("\nSummary")
    print(f"{'file':<28} {'first':<26} {'last':<26} {'rows':>7} {'missing':>8}")
    for filename, (time_col, unit) in SERIES_FILES.items():
        df = pd.read_csv(RAW_DIR / filename)
        stamps = pd.to_datetime(df[time_col], unit=unit, utc=True)
        values = df[df.columns[1]]
        print(f"{filename:<28} {str(stamps.min()):<26} {str(stamps.max()):<26} "
              f"{len(df):>7} {values.isna().sum():>8}")


def write_manifest():
    """D12: where each file came from, under which licence, and when."""
    files = {}
    for filename in SERIES_FILES:
        if filename == "brent.csv":
            source = SOURCES["fred"]
        elif filename.startswith("temperature_"):
            source = SOURCES["open-meteo"]
        else:
            source = SOURCES["energy-charts"]
        files[filename] = source
    manifest = {
        "downloaded": date.today().isoformat(),
        "range": [DOWNLOAD_START, DOWNLOAD_END],
        "files": files,
    }
    path = RAW_DIR / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {path.name}")


def main():
    print(f"Downloading {DOWNLOAD_START} to {DOWNLOAD_END} into {RAW_DIR}")
    download_price()
    download_forecasts()
    download_gas()
    download_temperature()
    download_brent()
    print_summary()
    write_manifest()


if __name__ == "__main__":
    main()

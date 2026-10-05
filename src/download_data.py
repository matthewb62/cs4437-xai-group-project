"""Download the raw datasets into data/raw/.

Use this script to get the data. Don't download files manually.

Do not commit the data/ folder.

The electricity series come from SMARD (Bundesnetzagentur), the temperature
from Open-Meteo and Brent from FRED.

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
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import CITIES, DOWNLOAD_END, DOWNLOAD_START, RAW_DIR, TIMEZONE

SMARD = "https://www.smard.de/app/chart_data"
OPEN_METEO = "https://previous-runs-api.open-meteo.com/v1/forecast"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

FORECAST_TYPES = ["load", "solar", "wind_onshore", "wind_offshore"]
TEMP_VARIABLE = "temperature_2m_previous_day2"
TEMP_MODEL = "icon_seamless"

# SMARD serves one JSON file per filter, region, resolution and week.
#
# The hourly resolution is the one to ask for. SMARD's quarter-hourly values for
# load, wind, solar and gas are MWh per quarter-hour, a quarter of the figure in
# MW, while the price is EUR/MWh either way. Hourly gives MW and EUR/MWh
# directly: SMARD sums the four quarter-hours for the generation series and
# averages them for the price, which is the rule C1 asks for.
#
# The filter IDs are from the bundesAPI OpenAPI spec, each checked against the
# live series, because the spec has two faults: it labels 126 as photovoltaics
# when 126 is really -(123 + 3791 + 125), and it omits 411 altogether.
SMARD_REGION = "DE-LU"
SMARD_RESOLUTION = "hour"
PRICE_FILTER = "4169"       # Grosshandelspreis Deutschland/Luxemburg
GAS_FILTER = "4071"         # realisierte Erzeugung, Erdgas
SMARD_FILTERS = {           # prognostizierte Erzeugung and Netzlast, day-ahead
    "load": "411",
    "solar": "125",
    "wind_onshore": "123",
    "wind_offshore": "3791",
}
SMARD_FILES = {
    "price_de_lu.csv": PRICE_FILTER,
    "generation_gas.csv": GAS_FILTER,
    **{f"forecast_{kind}.csv": SMARD_FILTERS[kind] for kind in FORECAST_TYPES},
}
WEEK_MS = 7 * 24 * 60 * 60 * 1000

# Raw file -> (timestamp column, pandas to_datetime unit). The value is column 2.
SERIES_FILES = {
    "price_de_lu.csv": ("unix_seconds", "s"),
    **{f"forecast_{t}.csv": ("unix_seconds", "s") for t in FORECAST_TYPES},
    "generation_gas.csv": ("unix_seconds", "s"),
    **{f"temperature_{c}.csv": ("time_utc", None) for c in CITIES},
    "brent.csv": ("observation_date", None),
}

SOURCES = {
    "smard": {
        "url": f"{SMARD}/<filter>/{SMARD_REGION}/"
               f"<filter>_{SMARD_REGION}_{SMARD_RESOLUTION}_<week>.json",
        "licence": "CC BY 4.0, SMARD.de | Bundesnetzagentur",
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
# SMARD serves static JSON and publishes no rate limit, but a full run is about
# 900 week files, so it still gets a pause between requests.
SMARD_PAUSE_SECONDS = 0.25
MAX_RETRIES = 5
# 429 is a rate limit; 502, 503 and 504 are what a source returns while it is
# down, and they clear on their own, so they are worth waiting out too.
RETRY_STATUS = (429, 502, 503, 504)
BACKOFF_SECONDS = 15      # doubled each attempt, when the response names no Retry-After

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


def _get(url, params, label, endpoint=None, pause=0.0):
    """GET with per-endpoint rate limiting and Retry-After handling.

    Raises DownloadError on any failure, naming the series and dates.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        if endpoint in _last_request:
            wait = pause - (time.monotonic() - _last_request[endpoint])
            if wait > 0:
                time.sleep(wait)
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            # A dropped connection or a read timeout is transient, and over the
            # ~900 week files of a full run one is close to certain.
            if attempt == MAX_RETRIES:
                raise DownloadError(f"{label}: request failed ({e})") from e
            wait = BACKOFF_SECONDS * 2 ** (attempt - 1)
            print(f"  {label}: {type(e).__name__}, waiting {wait} s (attempt {attempt})")
            time.sleep(wait)
            continue
        finally:
            if endpoint is not None:
                _last_request[endpoint] = time.monotonic()
        if resp.status_code in RETRY_STATUS:
            default = 60 if resp.status_code == 429 else BACKOFF_SECONDS * 2 ** (attempt - 1)
            wait = _retry_after_seconds(resp.headers.get("Retry-After"), default)
            print(f"  {label}: HTTP {resp.status_code}, waiting {wait} s (attempt {attempt})")
            time.sleep(wait)
            continue
        if not resp.ok:
            raise DownloadError(f"{label}: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp
    raise DownloadError(f"{label}: still failing after {MAX_RETRIES} attempts")


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


def _range_bounds():
    """The download range as epoch milliseconds, at Berlin midnight on each end."""
    berlin = ZoneInfo(TIMEZONE)
    start = datetime.fromisoformat(DOWNLOAD_START).replace(tzinfo=berlin)
    end = datetime.fromisoformat(DOWNLOAD_END).replace(tzinfo=berlin) + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _berlin_day(stamp_ms):
    """The Berlin calendar date a SMARD timestamp falls on, for naming a chunk."""
    return datetime.fromtimestamp(stamp_ms / 1000, ZoneInfo(TIMEZONE)).date().isoformat()


def _smard_weeks(filter_id, label):
    """The week files SMARD holds for this series that touch the download range.

    SMARD publishes one file per week, starting Monday in Berlin time, and the
    index endpoint lists every week it has. The week containing DOWNLOAD_START
    is included, so the range is covered from its first hour.
    """
    url = f"{SMARD}/{filter_id}/{SMARD_REGION}/index_{SMARD_RESOLUTION}.json"
    stamps = _get(url, None, f"{label} week index", endpoint=SMARD,
                  pause=SMARD_PAUSE_SECONDS).json().get("timestamps") or []
    if not stamps:
        raise DownloadError(f"{label}: SMARD lists no weeks for filter {filter_id}")
    start_ms, end_ms = _range_bounds()
    before = [stamp for stamp in stamps if stamp <= start_ms]
    weeks = ([before[-1]] if before else []) + [s for s in stamps if start_ms < s < end_ms]
    if not weeks:
        raise DownloadError(
            f"{label}: SMARD has no weeks between {DOWNLOAD_START} and {DOWNLOAD_END}")
    return weeks


def _smard_series(filter_id, name, label):
    """Fetch one SMARD series week by week, reusing saved chunks.

    Returns a list of (unix_seconds, value) rows inside the download range,
    sorted, with the first value kept where two week files meet on one hour.
    """
    rows = []
    for week in _smard_weeks(filter_id, label):
        first_day = _berlin_day(week)
        last_day = _berlin_day(week + WEEK_MS - 1000)
        chunk_label = f"{label} {first_day}..{last_day}"

        def fetch(week=week, last_day=last_day, chunk_label=chunk_label):
            print(f"  fetching {chunk_label}")
            url = (f"{SMARD}/{filter_id}/{SMARD_REGION}/"
                   f"{filter_id}_{SMARD_REGION}_{SMARD_RESOLUTION}_{week}.json")
            series = _get(url, None, chunk_label, endpoint=SMARD,
                          pause=SMARD_PAUSE_SECONDS).json().get("series")
            if not series:
                raise DownloadError(f"{chunk_label}: empty response")
            settled = (date.today() - date.fromisoformat(last_day)).days >= FINAL_AFTER_DAYS
            if settled and all(value is None for _stamp, value in series):
                raise DownloadError(f"{chunk_label}: every value is missing")
            return [(stamp // 1000, value) for stamp, value in series]

        rows.extend(_cached_chunk(name, first_day, last_day, fetch))

    start_ms, end_ms = _range_bounds()
    seen, kept = set(), []
    for stamp, value in sorted(rows):
        if start_ms // 1000 <= stamp < end_ms // 1000 and stamp not in seen:
            seen.add(stamp)
            kept.append((stamp, value))
    return kept


def download_price():
    label = "price DE-LU"
    rows = _smard_series(PRICE_FILTER, "price_de_lu", label)
    _write_csv("price_de_lu.csv", ["unix_seconds", "price"], rows, label)


def download_forecasts():
    for production_type in FORECAST_TYPES:
        label = f"forecast {production_type}"
        name = f"forecast_{production_type}"
        rows = _smard_series(SMARD_FILTERS[production_type], name, label)
        _write_csv(f"{name}.csv", ["unix_seconds", "forecast"], rows, label)


def download_gas():
    label = "generation gas"
    rows = _smard_series(GAS_FILTER, "generation_gas", label)
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
            source = {**SOURCES["smard"], "filter": SMARD_FILES[filename],
                      "region": SMARD_REGION, "resolution": SMARD_RESOLUTION}
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

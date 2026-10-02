"""Download the raw datasets into data/raw/.

Use this script to get the data. Don't download files manually.

Do not commit the data/ folder.

Each series is saved as received: one CSV per series, original timestamps,
original resolution. Cleaning happens in clean_data.py.

Usage:
    python src/download_data.py
"""
import csv
import os
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from config import DOWNLOAD_END, DOWNLOAD_START, RAW_DIR

ENERGY_CHARTS = "https://api.energy-charts.info"
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


def _energy_charts_series(endpoint, params, value_key, label):
    """Fetch one energy-charts series a year at a time.

    value_key is the JSON key holding the values, or a function that takes
    the payload and returns them. Returns a list of (unix_seconds, value) rows.
    """
    rows = []
    for start, end in _year_chunks(DOWNLOAD_START, DOWNLOAD_END):
        chunk_label = f"{label} {start}..{end}"
        print(f"  fetching {chunk_label}")
        resp = _get(f"{ENERGY_CHARTS}/{endpoint}",
                    {**params, "start": start, "end": end},
                    chunk_label, endpoint=endpoint)
        payload = resp.json()
        stamps = payload.get("unix_seconds") or []
        values = value_key(payload) if callable(value_key) else payload.get(value_key)
        if not stamps or not values:
            raise DownloadError(f"{chunk_label}: empty response")
        if len(stamps) != len(values):
            raise DownloadError(
                f"{chunk_label}: {len(stamps)} timestamps but {len(values)} values")
        rows.extend(zip(stamps, values))
    return rows


def download_price():
    label = "price DE-LU"
    rows = _energy_charts_series("price", {"bzn": "DE-LU"}, "price", label)
    _write_csv("price_de_lu.csv", ["unix_seconds", "price"], rows, label)


def main():
    print(f"Downloading {DOWNLOAD_START} to {DOWNLOAD_END} into {RAW_DIR}")
    download_price()


if __name__ == "__main__":
    main()

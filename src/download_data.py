"""Download the raw datasets into data/raw/.

Use this script to get the data. Don't download files manually.

Do not commit the data/ folder.

Usage:
    python src/download_data.py
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Date range
START_DATE = "2023-01-01"
END_DATE = "2026-09-30"


def download_electricity_prices():
    # TODO: pick source (e.g. ENTSO-E) and fetch START_DATE..END_DATE
    raise NotImplementedError


def download_traffic():
    # TODO: pick source and fetch START_DATE..END_DATE
    raise NotImplementedError


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download_electricity_prices()
    download_traffic()
    # TODO: third domain (TBD)


if __name__ == "__main__":
    main()

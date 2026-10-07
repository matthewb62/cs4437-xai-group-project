"""Shared settings. Every script imports from here.

Do not change this file without telling both people: both halves depend on it.
"""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"

CLEAN_FILE = PROCESSED_DIR / "clean_hourly.parquet"
FEATURES_FILE = PROCESSED_DIR / "features.parquet"
SAMPLE_FEATURES_FILE = PROCESSED_DIR / "features_SAMPLE.parquet"

TIMEZONE = "Europe/Berlin"

# Download range. One month before training, for the 7-day and 30-day lags.
# The DE-LU bidding zone, and so SMARD's DE-LU series, starts on 1 Oct 2018.
DOWNLOAD_START = "2018-12-01"
DOWNLOAD_END = date.today().isoformat()

# Temperature. Open-Meteo's archive of 2-day-ahead forecasts begins in January
# 2024, so before that the temperature column is ERA5 reanalysis, the observed
# temperature. The forecast is asked for from TEMP_FORECAST_START; the
# reanalysis runs to TEMP_REANALYSIS_END, which leaves a year where both exist
# so clean_data.py can report how far apart they are.
TEMP_FORECAST_START = "2024-01-01"
TEMP_REANALYSIS_END = "2024-12-31"

# Data windows. Inclusive dates in Berlin time.
TRAIN_START = "2019-01-01"
TRAIN_END = "2025-09-30"
VAL_START = "2025-10-01"
VAL_END = "2025-10-31"
BASELINE_EARLIEST = "2025-11-01"
SHOCK_DATE = "2026-02-28"      # the first test window starts on this date
WINDOW_DAYS = 14
SEASONAL_SHIFT_DAYS = 364      # "same fortnight in 2025", weekday-aligned

# Warning thresholds
SD_MULTIPLIER = 2.0
PSI_CUTOFF = 0.25
PSI_BINS = 10

# Cleaning
MAX_GAP_HOURS = 3

# Leakage-safe lags, in days before the delivery day D
AUCTION_CLOSE_HOUR = 12   # gas: same clock hour from the 24 h before this hour on D-1
OIL_LAG_DAYS = 2
OIL_CHANGE_DAYS = 30
TEMP_LEAD_DAYS = 2

# Modelling
SEED = 42
TARGET = "price"
TIME_FEATURES = ["hour", "weekday", "month", "is_holiday"]   # left out of PSI
FEATURES_BLIND = [
    "price_lag_1d", "price_lag_2d", "price_lag_7d",
    "demand_forecast", "wind_forecast", "solar_forecast",
    "gas_gen_lag", "temp_forecast",
] + TIME_FEATURES
OIL_FEATURE = "oil_change_30d"
FEATURES_OIL = FEATURES_BLIND + [OIL_FEATURE]

# Temperature cities: (latitude, longitude, population weight in millions)
CITIES = {
    "berlin": (52.52, 13.41, 3.7),
    "hamburg": (53.55, 9.99, 1.9),
    "munich": (48.14, 11.58, 1.5),
    "cologne": (50.94, 6.96, 1.1),
    "frankfurt": (50.11, 8.68, 0.8),
}

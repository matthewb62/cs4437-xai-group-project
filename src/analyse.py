"""Drift analysis: fortnightly tau, MAE and PSI with 2 SD warning flags (A1-A15, O1, O3, O4).

Loads the frozen models and the feature table, and writes one results table per model.
It never fits or updates a model (M5).

Usage:
    python src/analyse.py          # synthetic stand-ins, outputs named *_SAMPLE
    python src/analyse.py --real   # Person A's features.parquet, blind.txt and oil.txt
"""
import argparse
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from scipy.stats import weightedtau

from config import (
    BASELINE_EARLIEST, FEATURES_BLIND, FEATURES_FILE, FEATURES_OIL, MODELS_DIR, PSI_BINS,
    PSI_CUTOFF, RESULTS_DIR, SAMPLE_FEATURES_FILE, SD_MULTIPLIER, SEASONAL_SHIFT_DAYS,
    SHOCK_DATE, TARGET, TIME_FEATURES, TIMEZONE, TRAIN_END, TRAIN_START, VAL_END,
    VAL_START, WINDOW_DAYS,
)

# Not in the shared config: file names inside its folders, and the PSI default for empty bins.
PSI_EMPTY_BIN = 0.0001
MODEL_FEATURES = {"blind": FEATURES_BLIND, "oil": FEATURES_OIL}
REAL_MODEL_FILES = {"blind": MODELS_DIR / "blind.txt", "oil": MODELS_DIR / "oil.txt"}
SAMPLE_MODEL_FILES = {"blind": MODELS_DIR / "SAMPLE.txt", "oil": MODELS_DIR / "SAMPLE_oil.txt"}
SAMPLE_SUFFIX = "_SAMPLE"
VALIDATION_FILE = RESULTS_DIR / "validation.json"
OIL_RANGE_FILE = RESULTS_DIR / "oil_range.json"

METRICS = {"tau": "tau", "mae": "mae", "psi": "psi_mean"}   # metric name -> column it is judged on
RESULT_COLUMNS = [
    "window_start", "window_end", "period", "tau", "mae", "psi_mean", "psi_max",
    "tau_z", "mae_z", "psi_z", "tau_warn", "mae_warn", "psi_warn", "psi_over_cutoff",
    "tau_seasonal",
]
NEVER = "never crossed"
TOP_FEATURES = 5


def output_suffix(real):
    return "" if real else SAMPLE_SUFFIX


def drift_file(model, real):
    return RESULTS_DIR / f"drift_{model}{output_suffix(real)}.csv"


def thresholds_file(model, real):
    return RESULTS_DIR / f"thresholds_{model}{output_suffix(real)}.json"


# ---------------------------------------------------------------- loading

def load_features(path):
    if not path.exists():
        raise SystemExit(f"Feature table not found: {path}")
    table = pd.read_parquet(path)
    needed = FEATURES_OIL + [TARGET]
    absent = [c for c in needed if c not in table.columns]
    if absent:
        raise SystemExit(f"{path.name} is missing columns: {absent}")
    if table.index.name != "timestamp" or str(table.index.tz) != TIMEZONE:
        raise SystemExit(f"{path.name} index must be named 'timestamp' and be in {TIMEZONE}")
    missing = int(table[needed].isna().sum().sum())
    if missing:
        raise SystemExit(f"{path.name} has {missing} missing values")
    return table.sort_index()


def load_model(path, features):
    if not path.exists():
        raise SystemExit(f"Model file not found: {path}")
    booster = lgb.Booster(model_file=str(path))
    if booster.feature_name() != features:
        raise SystemExit(f"{path.name} features {booster.feature_name()} do not match the config list {features}")
    return booster


def day_slice(table, start, end):
    """Rows from `start` to `end`, both inclusive Berlin dates."""
    lo = pd.Timestamp(start).tz_localize(TIMEZONE)
    hi = (pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize(TIMEZONE)
    return table[(table.index >= lo) & (table.index < hi)]


def last_complete_day(index):
    last = index.max()
    day = last.normalize().tz_localize(None)
    return day if last.hour == 23 else day - pd.Timedelta(days=1)


# ---------------------------------------------------------------- A1 windows

def build_windows(last_day):
    """Fixed 14-day windows: baseline backward from the shock date, test forward from it."""
    shock = pd.Timestamp(SHOCK_DATE)
    length = pd.Timedelta(days=WINDOW_DAYS)
    one_day = pd.Timedelta(days=1)
    rows = []

    start = shock - length
    while start >= pd.Timestamp(BASELINE_EARLIEST):
        rows.append((start, start + length - one_day, "baseline"))
        start -= length

    start = shock
    while start + length - one_day <= pd.Timestamp(last_day):
        rows.append((start, start + length - one_day, "test"))
        start += length

    windows = pd.DataFrame(rows, columns=["window_start", "window_end", "period"])
    windows = windows.sort_values("window_start").reset_index(drop=True)

    gaps = windows["window_start"].iloc[1:].to_numpy() - windows["window_end"].iloc[:-1].to_numpy()
    assert (gaps == one_day).all(), "windows overlap or leave a gap"
    straddles = (windows["window_start"] < shock) & (windows["window_end"] >= shock)
    assert not straddles.any(), "a window straddles the shock date"
    return windows


# ---------------------------------------------------------------- A2-A5 SHAP and tau

def mean_abs_shap(explainer, X):
    """Mean absolute TreeSHAP value per feature over the rows of X (A2, A3)."""
    return np.abs(explainer.shap_values(X)).mean(axis=0)


def tau(importance, reference):
    """Weighted Kendall's tau between two importance vectors, default arguments (A5)."""
    return float(weightedtau(importance, reference).statistic)


# ---------------------------------------------------------------- A7 PSI

def psi_edges(train_values):
    """Quantile bin edges from the training rows, open at both ends."""
    edges = np.unique(np.quantile(train_values, np.linspace(0, 1, PSI_BINS + 1)))
    edges = edges.astype(float)
    edges[0], edges[-1] = -np.inf, np.inf
    return edges


def bin_shares(values, edges):
    bins = np.searchsorted(edges[1:-1], values, side="right")
    counts = np.bincount(bins, minlength=len(edges) - 1)
    return counts / counts.sum()


def psi(expected, actual):
    expected = np.where(expected == 0, PSI_EMPTY_BIN, expected)
    actual = np.where(actual == 0, PSI_EMPTY_BIN, actual)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


# ---------------------------------------------------------------- A8-A12 thresholds

def add_thresholds(results):
    """Baseline mean and SD, z-scores with tau flipped, and the warning flags."""
    baseline = results[results["period"] == "baseline"]
    thresholds = {}
    for metric, column in METRICS.items():
        mean = float(baseline[column].mean())
        sd = float(baseline[column].std(ddof=1))
        if not sd > 0:
            raise SystemExit(f"Baseline SD of {column} is {sd}: cannot set a threshold")
        sign = -1.0 if metric == "tau" else 1.0   # up always means more drift
        results[f"{metric}_z"] = sign * (results[column] - mean) / sd
        results[f"{metric}_warn"] = results[f"{metric}_z"] > SD_MULTIPLIER
        thresholds[f"{metric}_mean"] = mean
        thresholds[f"{metric}_sd"] = sd
    results["psi_over_cutoff"] = results["psi_max"] >= PSI_CUTOFF
    return results, thresholds


# ---------------------------------------------------------------- A11 crossings

def first_crossing(results, flag, consecutive=1):
    """Start date of the first test window where `flag` has been true `consecutive` windows running.

    With consecutive=2 (A14) this is the second window of the pair: the one where the warning is raised.
    """
    test = results[results["period"] == "test"]
    run = test[flag].astype(int).rolling(consecutive).sum() == consecutive
    hits = test.loc[run, "window_start"]
    return None if hits.empty else hits.iloc[0]


def lead_time(later, tau_date):
    """Days from the tau warning to the other warning. Positive means tau warned first."""
    if later is None or tau_date is None:
        return None
    return (later - tau_date).days


def crossings(results, consecutive=1):
    dates = {m: first_crossing(results, f"{m}_warn", consecutive) for m in METRICS}
    dates["psi_cutoff"] = first_crossing(results, "psi_over_cutoff", consecutive)
    return {
        "dates": dates,
        "lead_mae": lead_time(dates["mae"], dates["tau"]),
        "lead_psi": lead_time(dates["psi"], dates["tau"]),
    }


def show_date(value):
    return NEVER if value is None else value.date().isoformat()


def show_lead(value):
    return NEVER if value is None else f"{value:+d} days"


# ---------------------------------------------------------------- per model

def analyse_model(name, table, windows, model_path, real):
    features = MODEL_FEATURES[name]
    booster = load_model(model_path, features)
    explainer = shap.TreeExplainer(booster)

    reference = mean_abs_shap(explainer, day_slice(table, VAL_START, VAL_END)[features])
    assert abs(tau(reference, reference) - 1) < 1e-12, "reference against itself must give tau 1"

    psi_features = [f for f in features if f not in TIME_FEATURES]
    train = day_slice(table, TRAIN_START, TRAIN_END)
    edges = {f: psi_edges(train[f].to_numpy()) for f in psi_features}
    expected = {f: bin_shares(train[f].to_numpy(), edges[f]) for f in psi_features}
    print("  PSI bins per feature: " + ", ".join(f"{f} {len(edges[f]) - 1}" for f in psi_features))

    seasonal_shift = pd.Timedelta(days=SEASONAL_SHIFT_DAYS)
    first_day = table.index.min().normalize().tz_localize(None)
    rows, importances, psi_rows = [], {"reference": reference}, []
    for window in windows.itertuples(index=False):
        rows_in_window = day_slice(table, window.window_start, window.window_end)
        if rows_in_window.empty:
            raise SystemExit(f"No rows for window {window.window_start.date()} to {window.window_end.date()}")
        X = rows_in_window[features]
        importance = mean_abs_shap(explainer, X)
        year_ago = day_slice(table, window.window_start - seasonal_shift, window.window_end - seasonal_shift)
        if len(year_ago) and window.window_start - seasonal_shift >= first_day:
            tau_seasonal = tau(importance, mean_abs_shap(explainer, year_ago[features]))
        else:
            tau_seasonal = np.nan
        feature_psi = {f: psi(expected[f], bin_shares(X[f].to_numpy(), edges[f])) for f in psi_features}
        label = window.window_start.date().isoformat()
        importances[label] = importance
        psi_rows.append({"window_start": label, **feature_psi})
        rows.append({
            "window_start": window.window_start,
            "window_end": window.window_end,
            "period": window.period,
            "tau": tau(importance, reference),
            "mae": float(np.mean(np.abs(rows_in_window[TARGET].to_numpy() - booster.predict(X)))),
            "psi_mean": float(np.mean(list(feature_psi.values()))),
            "psi_max": float(np.max(list(feature_psi.values()))),
            "tau_seasonal": tau_seasonal,
        })

    results, thresholds = add_thresholds(pd.DataFrame(rows))
    results = results[RESULT_COLUMNS]

    suffix = output_suffix(real)
    results.to_csv(drift_file(name, real), index=False, date_format="%Y-%m-%d")
    pd.DataFrame(importances, index=features).T.rename_axis("window_start").to_csv(
        RESULTS_DIR / f"importance_{name}{suffix}.csv")
    pd.DataFrame(psi_rows).to_csv(RESULTS_DIR / f"psi_features_{name}{suffix}.csv", index=False)
    thresholds_file(name, real).write_text(json.dumps(thresholds, indent=2))

    return {
        "results": results,
        "thresholds": thresholds,
        "crossings": crossings(results),
        "crossings_two": crossings(results, consecutive=2),
        "importances": pd.DataFrame(importances, index=features),
    }


# ---------------------------------------------------------------- O3, O4 summary

def ordering(found):
    """Plain statement of which warning came first. Not the method doc's outcome label."""
    dates = found["dates"]
    if dates["tau"] is None and dates["mae"] is None:
        return "Neither tau nor MAE crossed its threshold."
    if dates["tau"] is None:
        return "MAE crossed its threshold and tau never did."
    if dates["mae"] is None:
        return "Tau crossed its threshold and MAE never did."
    if found["lead_mae"] > 0:
        return f"Tau warned {found['lead_mae']} days before MAE."
    if found["lead_mae"] < 0:
        return f"MAE warned {-found['lead_mae']} days before tau."
    return "Tau and MAE warned in the same window."


def json_table(path, real):
    if not real:
        return [f"Not shown: this is a synthetic sample run, and `{path.name}` comes from Person A's real pipeline."]
    if not path.exists():
        raise SystemExit(f"{path} not found. Person A's scripts write it; the summary needs it (O4).")
    values = json.loads(path.read_text())
    return ["| Item | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in values.items()]


def top_features(found):
    """O6: top features by mean absolute SHAP in the reference month, at the first tau warning, and latest."""
    importances = found["importances"]
    columns = {"Reference month": "reference"}
    first_tau = found["crossings"]["dates"]["tau"]
    if first_tau is not None:
        columns[f"First tau warning ({show_date(first_tau)})"] = show_date(first_tau)
    latest = importances.columns[-1]
    columns[f"Latest window ({latest})"] = latest

    lines = ["| Rank | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
    ranked = {label: importances[key].sort_values(ascending=False) for label, key in columns.items()}
    for rank in range(TOP_FEATURES):
        cells = [f"{ranked[label].index[rank]} ({ranked[label].iloc[rank]:.2f})" for label in columns]
        lines.append(f"| {rank + 1} | " + " | ".join(cells) + " |")
    return lines


def comparison(analysed):
    """O7: blind and oil crossing dates side by side."""
    lines = ["| | " + " | ".join(f"{name.capitalize()} model" for name in analysed) + " |",
             "|---|" + "---|" * len(analysed)]
    labels = {"tau": "First tau warning", "mae": "First MAE warning", "psi": "First PSI warning"}
    for key, title in (("crossings", ""), ("crossings_two", ", two in a row")):
        for metric, label in labels.items():
            lines.append(f"| {label}{title} | "
                         + " | ".join(show_date(found[key]["dates"][metric]) for found in analysed.values()) + " |")
        lines.append(f"| Lead time, MAE against tau{title} | "
                     + " | ".join(show_lead(found[key]["lead_mae"]) for found in analysed.values()) + " |")
        lines.append(f"| Lead time, PSI against tau{title} | "
                     + " | ".join(show_lead(found[key]["lead_psi"]) for found in analysed.values()) + " |")
    return lines


def write_summary(analysed, real):
    lines = ["# Drift summary", ""]
    if not real:
        lines += ["**SYNTHETIC SAMPLE DATA. Not a result. Do not quote.**", ""]
    lines += [
        f"Shock date {SHOCK_DATE}. Thresholds are {SD_MULTIPLIER:g} SD from the baseline mean. "
        "Dates are the start of the first test window over the threshold. "
        "Lead times are measured from the tau warning, so positive means tau warned first.",
        "",
    ]
    for name, found in analysed.items():
        dates, t, two = found["crossings"]["dates"], found["thresholds"], found["crossings_two"]
        lines += [
            f"## {name.capitalize()} model",
            "",
            "| Metric | Baseline mean | Baseline SD | First crossing | Lead time against tau |",
            "|---|---|---|---|---|",
            f"| tau | {t['tau_mean']:.4f} | {t['tau_sd']:.4f} | {show_date(dates['tau'])} | |",
            f"| MAE (EUR/MWh) | {t['mae_mean']:.3f} | {t['mae_sd']:.3f} | {show_date(dates['mae'])} | {show_lead(found['crossings']['lead_mae'])} |",
            f"| PSI (mean) | {t['psi_mean']:.4f} | {t['psi_sd']:.4f} | {show_date(dates['psi'])} | {show_lead(found['crossings']['lead_psi'])} |",
            f"| PSI, any feature at {PSI_CUTOFF} | | | {show_date(dates['psi_cutoff'])} | |",
            "",
            f"Ordering: {ordering(found['crossings'])}",
            "",
            "Robustness (A14): a warning needs two windows in a row over the threshold, "
            "and is dated at the start of the second.",
            "",
            "| Metric | First crossing, two in a row | Lead time against tau |",
            "|---|---|---|",
            f"| tau | {show_date(two['dates']['tau'])} | |",
            f"| MAE | {show_date(two['dates']['mae'])} | {show_lead(two['lead_mae'])} |",
            f"| PSI (mean) | {show_date(two['dates']['psi'])} | {show_lead(two['lead_psi'])} |",
            "",
            f"Ordering, two in a row: {ordering(two)}",
            "",
            f"Top {TOP_FEATURES} features by mean absolute SHAP (EUR/MWh):",
            "",
            *top_features(found),
            "",
        ]
    lines += ["## Blind against oil", ""] + comparison(analysed) + [""]
    lines += ["## Validation MAE (M6, M7)", ""] + json_table(VALIDATION_FILE, real) + [""]
    lines += ["## Oil range (F10)", ""] + json_table(OIL_RANGE_FILE, real) + [""]

    path = RESULTS_DIR / f"summary{output_suffix(real)}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--real", action="store_true",
                        help="use Person A's real feature table and models instead of the synthetic stand-ins")
    args = parser.parse_args()

    features_path = FEATURES_FILE if args.real else SAMPLE_FEATURES_FILE
    model_files = REAL_MODEL_FILES if args.real else SAMPLE_MODEL_FILES
    for path in [features_path, *model_files.values()]:
        if not path.exists():
            raise SystemExit(f"Not found: {path}")

    print("REAL data" if args.real else "SYNTHETIC SAMPLE data: not a result")
    table = load_features(features_path)
    windows = build_windows(last_complete_day(table.index))
    print(f"\nWindows ({(windows['period'] == 'baseline').sum()} baseline, {(windows['period'] == 'test').sum()} test):")
    print(windows.to_string(index=False))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    analysed = {}
    for name in MODEL_FEATURES:
        print(f"\n{name} model")
        analysed[name] = analyse_model(name, table, windows, model_files[name], args.real)
        found = analysed[name]["crossings"]
        print("  thresholds: " + ", ".join(f"{k} {v:.4f}" for k, v in analysed[name]["thresholds"].items()))
        for metric in METRICS:
            print(f"  first {metric} warning: {show_date(found['dates'][metric])}")
        print(f"  first PSI feature at {PSI_CUTOFF}: {show_date(found['dates']['psi_cutoff'])}")
        print(f"  lead time, MAE against tau: {show_lead(found['lead_mae'])}")
        print(f"  lead time, PSI against tau: {show_lead(found['lead_psi'])}")
        two = analysed[name]["crossings_two"]
        print("  two in a row: " + ", ".join(f"{m} {show_date(two['dates'][m])}" for m in METRICS)
              + f"; lead MAE {show_lead(two['lead_mae'])}, lead PSI {show_lead(two['lead_psi'])}")
        print(f"  saved {drift_file(name, args.real)}")

    print(f"\nsaved {write_summary(analysed, args.real)}")


if __name__ == "__main__":
    main()

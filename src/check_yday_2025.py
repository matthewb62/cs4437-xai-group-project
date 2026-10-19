"""Follow-up from the 15 Oct journal: is yesterday's price rising in the ranking
after the shock just the season?

The baseline windows are all winter, so on their own they cannot say whether
yesterday's price climbing the SHAP ranking after the shock comes from the
shock or from spring and summer. This check compares each test window with the
same fortnight one year earlier (SEASONAL_SHIFT_DAYS back, so weekdays line
up), explained by the same frozen models, and records yesterday's price's rank
and mean |SHAP| in both.

An additional check, not the main result. analyse.py is not touched: its
loading, slicing and SHAP helpers are imported so the two cannot drift apart.
The 2026 values are read from results/importance_<model>.csv, the committed
output of analyse.py. Before anything is compared, the October 2025 reference is
recomputed and checked against that file, so a stale local model stops the run
instead of giving wrong numbers.

Caveat: March to August 2025 is inside the training period, so there the model
is explaining data it was fitted on. tau_seasonal and PSI share this.

Writes:
    results/yday_2025.csv   one row per test window and model
    results/yday_2025.md    counts and averages

Usage:
    python src/check_yday_2025.py
"""
import numpy as np
import pandas as pd
import shap

from analyse import (
    MODEL_FEATURES, REAL_MODEL_FILES, day_slice, drift_file, load_features, load_model,
    mean_abs_shap,
)
from config import FEATURES_FILE, RESULTS_DIR, SEASONAL_SHIFT_DAYS, VAL_END, VAL_START

FEATURE = "price_lag_1d"   # yesterday's price, same hour
TOP_N = (2, 3)
CSV_FILE = RESULTS_DIR / "yday_2025.csv"
MD_FILE = RESULTS_DIR / "yday_2025.md"


def importance(explainer, rows, features):
    return pd.Series(mean_abs_shap(explainer, rows[features]), index=features)


def rank_of(scores, feature):
    """1 = largest mean |SHAP|."""
    return int(scores.rank(ascending=False, method="min")[feature])


def check_matches_committed(model, explainer, table, features, committed):
    """Stop if the local model does not reproduce the committed October reference."""
    reference = importance(explainer, day_slice(table, VAL_START, VAL_END), features)
    if not np.allclose(reference.values, committed.loc["reference", features].values, atol=1e-6):
        raise SystemExit(
            f"{model}: the October 2025 reference does not match results/importance_{model}.csv. "
            "The local model is probably out of date: run python src/train.py first.")


def compare(model, table):
    features = MODEL_FEATURES[model]
    explainer = shap.TreeExplainer(load_model(REAL_MODEL_FILES[model], features))
    drift = pd.read_csv(drift_file(model, real=True), parse_dates=["window_start", "window_end"])
    test = drift[drift["period"] == "test"]
    committed = pd.read_csv(RESULTS_DIR / f"importance_{model}.csv", index_col=0)
    check_matches_committed(model, explainer, table, features, committed)

    shift = pd.Timedelta(days=SEASONAL_SHIFT_DAYS)
    rows = []
    for w in test.itertuples(index=False):
        now = committed.loc[w.window_start.date().isoformat(), features]
        year_ago_rows = day_slice(table, w.window_start - shift, w.window_end - shift)
        if year_ago_rows.empty:
            raise SystemExit(f"{model}: no rows a year before {w.window_start.date()}")
        before = importance(explainer, year_ago_rows, features)
        rows.append({
            "model": model,
            "window_start": w.window_start.date().isoformat(),
            "year_ago_start": (w.window_start - shift).date().isoformat(),
            "rank_2025": rank_of(before, FEATURE),
            "rank_2026": rank_of(now, FEATURE),
            "shap_2025": round(float(before[FEATURE]), 2),
            "shap_2026": round(float(now[FEATURE]), 2),
        })
    return pd.DataFrame(rows)


def report_lines(model, df):
    n = len(df)
    lines = [f"## {model.capitalize()} model", "",
             "| | Same fortnight 2025 | After the shock 2026 |", "|---|---|---|"]
    for top in TOP_N:
        lines.append(f"| Top {top} | {(df.rank_2025 <= top).sum()} of {n} | "
                     f"{(df.rank_2026 <= top).sum()} of {n} |")
    lines += [
        f"| Mean \\|SHAP\\| (EUR/MWh) | {df.shap_2025.mean():.1f} | {df.shap_2026.mean():.1f} |",
        f"| Highest window | {df.shap_2025.max():.1f} | {df.shap_2026.max():.1f} |",
        "",
    ]
    return lines


def main():
    table = load_features(FEATURES_FILE)
    results = pd.concat([compare(model, table) for model in MODEL_FEATURES], ignore_index=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(CSV_FILE, index=False)

    lines = [
        "# Yesterday's price: shock or season? (15 Oct follow-up)", "",
        "An additional check beside the main result. Each test window is compared with the same "
        f"fortnight one year earlier ({SEASONAL_SHIFT_DAYS} days back), explained by the same frozen "
        "models. Rank 1 is the largest mean |SHAP| of all features.", "",
        "Caveat: March to August 2025 is training data, so there the model explains data it was "
        "fitted on.", "",
    ]
    for model in MODEL_FEATURES:
        lines += report_lines(model, results[results["model"] == model])
    lines += [f"Per-window values: `{CSV_FILE.relative_to(RESULTS_DIR.parent).as_posix()}`.", ""]
    MD_FILE.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"saved {CSV_FILE}\nsaved {MD_FILE}")


if __name__ == "__main__":
    main()

"""Train and freeze the blind and oil models (M1-M8).

Reads data/processed/features.parquet and writes the handover files
models/blind.txt and models/oil.txt, plus results/validation.json (M6, M7) and
results/train_params.json (M8).

Both models are fitted on January 2019 to September 2025 and early-stopped on
October 2025. Nothing dated after 31 October 2025 is read at all: the table is
cut at that date before anything is fitted, so the baseline and test periods
cannot reach the fit or the tuning (M4, M5).

The two models differ by one column and nothing else: same rows, same
hyperparameters, same seed (M3).

If a model does not beat the naive forecast on October 2025, the script says so
and exits non-zero. That is the M7 instruction to stop and investigate rather
than hand over.

Usage:
    python src/train.py
"""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from config import (
    FEATURES_BLIND, FEATURES_FILE, FEATURES_OIL, MODELS_DIR, RESULTS_DIR, SEED,
    TARGET, TIMEZONE, TRAIN_END, TRAIN_START, VAL_END, VAL_START,
)

VALIDATION_FILE = RESULTS_DIR / "validation.json"
PARAMS_FILE = RESULTS_DIR / "train_params.json"
MODEL_FILES = {"blind": MODELS_DIR / "blind.txt", "oil": MODELS_DIR / "oil.txt"}
MODEL_FEATURES = {"blind": FEATURES_BLIND, "oil": FEATURES_OIL}

NAIVE_FEATURE = "price_lag_7d"   # the same hour's price 7 days earlier (M7)

# The agreed first version. deterministic needs one of the force_*_wise flags,
# without which LightGBM picks the split order by timing and M8 would not hold.
PARAMS = {
    "objective": "regression",      # squared error
    "learning_rate": 0.05,
    "num_leaves": 31,
    "seed": SEED,
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
    "n_jobs": 1,
}
NUM_BOOST_ROUND = 2000
EARLY_STOPPING_ROUNDS = 50


class TrainingError(RuntimeError):
    pass


# ---------------------------------------------------------------- M1

def split(table):
    """M1: training and validation rows, by the dates in the config.

    Inclusive Berlin days, so the windows touch without sharing a row.
    """
    def day_start(value):
        return pd.Timestamp(value, tz=TIMEZONE)

    def day_after(value):
        return pd.Timestamp(value, tz=TIMEZONE) + pd.Timedelta(days=1)

    train = table[(table.index >= day_start(TRAIN_START)) & (table.index < day_after(TRAIN_END))]
    valid = table[(table.index >= day_start(VAL_START)) & (table.index < day_after(VAL_END))]
    if train.empty or valid.empty:
        raise TrainingError(
            f"Empty window: {len(train)} training rows ({TRAIN_START}..{TRAIN_END}), "
            f"{len(valid)} validation rows ({VAL_START}..{VAL_END})")
    if train.index.intersection(valid.index).size:
        raise TrainingError("A row appears in both the training and the validation window")
    return train, valid


def cut_at_validation_end(table):
    """M4: nothing dated after the validation month reaches the fit or the tuning."""
    limit = pd.Timestamp(VAL_END, tz=TIMEZONE) + pd.Timedelta(days=1)
    return table[table.index < limit]


# ---------------------------------------------------------------- M2, M3

def fit(train, valid, features):
    """One regression model over all 24 hours, early-stopped on the validation month."""
    model = lgb.LGBMRegressor(n_estimators=NUM_BOOST_ROUND, **PARAMS)
    model.fit(
        train[features], train[TARGET],
        eval_X=valid[features], eval_y=valid[TARGET],
        eval_metric="l1",
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )
    return model


def mae(actual, predicted):
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def validation_mae(model, valid, features):
    return mae(valid[TARGET], model.predict(valid[features]))


def naive_mae(valid):
    """M7: the same hour's price 7 days earlier, used as the forecast."""
    return mae(valid[TARGET], valid[NAIVE_FEATURE])


# ---------------------------------------------------------------- reporting

def check_beats_naive(scores, naive):
    """M7: if LightGBM does not clearly beat the naive forecast, something is wrong."""
    failed = {name: score for name, score in scores.items() if score >= naive}
    if failed:
        listed = ", ".join(f"{name} {score:.2f}" for name, score in failed.items())
        raise TrainingError(
            f"Validation MAE does not beat the naive forecast ({naive:.2f} EUR/MWh): {listed}. "
            "Stop and investigate before handing these models over (M7)."
        )


def print_report(train, valid, scores, train_scores, naive, best_iterations):
    print(f"\nWindows (M1)")
    print(f"  training   {TRAIN_START}..{TRAIN_END}  {len(train)} rows, "
          f"{train.index[0]} to {train.index[-1]}")
    print(f"  validation {VAL_START}..{VAL_END}  {len(valid)} rows, "
          f"{valid.index[0]} to {valid.index[-1]}")
    print(f"\nMAE in EUR/MWh (M6, M7). Validation is {VAL_START}..{VAL_END}.")
    print(f"  {'':<16} {'training':>9} {'validation':>11} {'gap':>8}  vs naive")
    print(f"  {'naive':<16} {'':>9} {naive:>11.2f}")
    for name, score in scores.items():
        gap = score - train_scores[name]
        print(f"  {name:<16} {train_scores[name]:>9.2f} {score:>11.2f} {gap:>8.2f}  "
              f"{100 * (1 - score / naive):>5.1f}% better, {best_iterations[name]} trees")


def main():
    if not FEATURES_FILE.exists():
        raise TrainingError(f"{FEATURES_FILE} not found. Run python src/build_features.py first.")
    table = pd.read_parquet(FEATURES_FILE)
    missing = [column for column in FEATURES_OIL + [TARGET] if column not in table.columns]
    if missing:
        raise TrainingError(f"{FEATURES_FILE.name} is missing columns: {missing}")

    before = len(table)
    table = cut_at_validation_end(table)
    print(f"Training from {FEATURES_FILE}: {before} rows, {len(table)} of them on or "
          f"before {VAL_END} (M4)")

    train, valid = split(table)
    models, scores, train_scores, best_iterations = {}, {}, {}, {}
    for name, features in MODEL_FEATURES.items():
        model = fit(train, valid, features)
        models[name] = model
        scores[name] = validation_mae(model, valid, features)
        # The same measure on the rows it was fitted on, so the gap between the
        # two shows how much of the fit is memorised.
        train_scores[name] = mae(train[TARGET], model.predict(train[features]))
        best_iterations[name] = int(model.best_iteration_)

    naive = naive_mae(valid)
    print_report(train, valid, scores, train_scores, naive, best_iterations)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():     # M5: saved, then never fitted again
        model.booster_.save_model(str(MODEL_FILES[name]))
        print(f"Froze {name}: {len(MODEL_FEATURES[name])} features -> {MODEL_FILES[name]}")

    VALIDATION_FILE.write_text(json.dumps({
        "validation_window": f"{VAL_START}..{VAL_END}",
        "mae_blind_eur_per_mwh": round(scores["blind"], 3),
        "mae_oil_eur_per_mwh": round(scores["oil"], 3),
        "mae_naive_eur_per_mwh": round(naive, 3),
        "mae_blind_training_eur_per_mwh": round(train_scores["blind"], 3),
        "mae_oil_training_eur_per_mwh": round(train_scores["oil"], 3),
        "blind_validation_minus_training": round(scores["blind"] - train_scores["blind"], 3),
        "oil_validation_minus_training": round(scores["oil"] - train_scores["oil"], 3),
        "blind_better_than_naive_pct": round(100 * (1 - scores["blind"] / naive), 1),
        "oil_better_than_naive_pct": round(100 * (1 - scores["oil"] / naive), 1),
        "training_rows": len(train),
        "validation_rows": len(valid),
    }, indent=2), encoding="utf-8")
    PARAMS_FILE.write_text(json.dumps({      # M8
        "seed": SEED,
        "params": PARAMS,
        "num_boost_round": NUM_BOOST_ROUND,
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "best_iteration": best_iterations,
        "features": MODEL_FEATURES,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {VALIDATION_FILE} and {PARAMS_FILE}")

    check_beats_naive(scores, naive)


if __name__ == "__main__":
    try:
        main()
    except TrainingError as error:
        raise SystemExit(f"Training stopped: {error}")

"""A15 follow-up: is the tau movement after the shock just seasonality?

An additional check, not the main result. tau compares each window's SHAP
ranking with the October 2025 reference; tau_seasonal compares it with the same
fortnight a year earlier (SEASONAL_SHIFT_DAYS), so anything both of them show is
not a seasonal artefact.

analyse.py and plot.py belong to Person B and are not touched. This reads their
results/drift_<model>.csv, puts the seasonal columns beside the originals and
writes its own files:

    results/drift_<model>_seasonal.csv   the original table plus the new columns
    results/seasonal_check.md            crossings and lead times
    figures/drift_<model>_seasonal.png   tau, tau_seasonal and MAE on one axis

The thresholds follow analyse.py exactly: baseline mean, sample SD (ddof=1),
z-score with the sign flipped so up means more drift, and a warning above
SD_MULTIPLIER. The crossing and lead-time helpers are imported from analyse.py
rather than rewritten, so the two cannot drift apart.

Usage:
    python src/check_seasonal.py
"""
import matplotlib.pyplot as plt
import pandas as pd

from analyse import MODEL_FEATURES, drift_file, first_crossing, lead_time, show_date, show_lead
from config import FIGURES_DIR, RESULTS_DIR, SD_MULTIPLIER, SHOCK_DATE
from plot import INK, INK_SECONDARY, SERIES, SURFACE, date_axis, mark_periods, style_axis

SEASONAL = "tau_seasonal"
SEASONAL_COLOUR = "#8b5cd6"
SEASONAL_MARKER = "D"
CHECK_FILE = RESULTS_DIR / "seasonal_check.md"


def seasonal_file(model):
    return RESULTS_DIR / f"drift_{model}_seasonal.csv"


def figure_file(model):
    return FIGURES_DIR / f"drift_{model}_seasonal.png"


def load_results(model):
    path = drift_file(model, real=True)
    if not path.exists():
        raise SystemExit(f"{path} not found. Run python src/analyse.py --real first.")
    results = pd.read_csv(path, parse_dates=["window_start", "window_end"])
    if results[SEASONAL].isna().any():
        raise SystemExit(f"{path.name} has {int(results[SEASONAL].isna().sum())} windows "
                         f"with no {SEASONAL}: the seasonal check needs all of them")
    return results


def add_seasonal_threshold(results):
    """A8 and A12 applied to tau_seasonal, by the same rule analyse.py uses for tau."""
    baseline = results[results["period"] == "baseline"]
    mean = float(baseline[SEASONAL].mean())
    sd = float(baseline[SEASONAL].std(ddof=1))
    if not sd > 0:
        raise SystemExit(f"Baseline SD of {SEASONAL} is {sd}: cannot set a threshold")
    results[f"{SEASONAL}_z"] = -(results[SEASONAL] - mean) / sd   # down in tau is up in drift
    results[f"{SEASONAL}_warn"] = results[f"{SEASONAL}_z"] > SD_MULTIPLIER
    return results, {f"{SEASONAL}_mean": mean, f"{SEASONAL}_sd": sd}


def crossings(results, consecutive):
    """First crossing for each metric, and MAE's lead time against each tau."""
    dates = {name: first_crossing(results, f"{name}_warn", consecutive)
             for name in ("tau", SEASONAL, "mae")}
    return {
        "dates": dates,
        "lead_vs_tau": lead_time(dates["mae"], dates["tau"]),
        "lead_vs_seasonal": lead_time(dates["mae"], dates[SEASONAL]),
    }


# ---------------------------------------------------------------- figure

def plot_seasonal(results, model, thresholds):
    """tau, tau_seasonal and MAE in baseline standard deviations on one axis."""
    fig, ax = plt.subplots(figsize=(12.8, 7.2), facecolor=SURFACE)
    style_axis(ax)
    mark_periods(ax, results)

    drawn = [
        ("tau_z", "Explanation drift vs Oct 2025 (tau)", *SERIES["tau"][2:]),
        (f"{SEASONAL}_z", "Explanation drift vs same fortnight 2025 (tau_seasonal)",
         SEASONAL_COLOUR, SEASONAL_MARKER),
        ("mae_z", "Error (MAE)", *SERIES["mae"][2:]),
    ]
    for column, label, colour, marker in drawn:
        warned = results[column.replace("_z", "_warn")]
        ax.plot(results["window_start"], results[column], color=colour, linewidth=2, zorder=3)
        ax.plot(results.loc[~warned, "window_start"], results.loc[~warned, column],
                linestyle="none", marker=marker, markersize=8, markerfacecolor=SURFACE,
                markeredgecolor=colour, markeredgewidth=2, zorder=4, label=label)
        ax.plot(results.loc[warned, "window_start"], results.loc[warned, column],
                linestyle="none", marker=marker, markersize=9, color=colour, zorder=5)

    ax.axhline(SD_MULTIPLIER, color=INK_SECONDARY, linewidth=1.5, linestyle=(0, (5, 4)), zorder=2)
    ax.axhline(0, color=INK_SECONDARY, linewidth=0.8, alpha=0.3, zorder=1)
    ax.annotate(f"{SD_MULTIPLIER:g} SD warning line", xy=(1.002, SD_MULTIPLIER),
                xycoords=("axes fraction", "data"), fontsize=12, color=INK_SECONDARY, va="center")
    ax.set_ylabel("Standard deviations from baseline mean\nup = more drift",
                  fontsize=13, color=INK_SECONDARY)
    date_axis(ax)
    legend = ax.legend(loc="upper left", bbox_to_anchor=(0, 1.02), ncol=1, frameon=False,
                       fontsize=12, handletextpad=0.6)
    for text in legend.get_texts():
        text.set_color(INK)

    fig.suptitle(f"{model.capitalize()} model: does seasonality explain the drift?",
                 fontsize=18, color=INK, x=0.07, ha="left", y=0.97)
    fig.text(0.07, 0.025,
             f"Filled marker = window over the warning line. Baseline tau_seasonal mean "
             f"{thresholds[f'{SEASONAL}_mean']:.4f}, SD {thresholds[f'{SEASONAL}_sd']:.4f}. "
             f"Shock {SHOCK_DATE}.", fontsize=11, color=INK_SECONDARY)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    path = figure_file(model)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- reporting

def report_lines(model, results, thresholds, single, pair):
    lines = [f"## {model.capitalize()} model", ""]
    lines += [f"Baseline tau_seasonal mean {thresholds[f'{SEASONAL}_mean']:.4f}, "
              f"SD {thresholds[f'{SEASONAL}_sd']:.4f} "
              f"(8 baseline windows, sample SD, the same rule analyse.py uses for tau).", ""]
    lines += ["| Metric | First crossing | MAE's lead time after it |", "|---|---|---|"]
    for name, label in (("tau", "tau (vs Oct 2025)"),
                        (SEASONAL, "tau_seasonal (vs same fortnight 2025)")):
        lead = single["lead_vs_tau"] if name == "tau" else single["lead_vs_seasonal"]
        lines.append(f"| {label} | {show_date(single['dates'][name])} | {show_lead(lead)} |")
    lines.append(f"| MAE | {show_date(single['dates']['mae'])} | |")
    lines += ["", "Two windows in a row (A14), dated at the start of the second:", ""]
    lines += ["| Metric | First crossing | MAE's lead time after it |", "|---|---|---|"]
    for name, label in (("tau", "tau"), (SEASONAL, "tau_seasonal")):
        lead = pair["lead_vs_tau"] if name == "tau" else pair["lead_vs_seasonal"]
        lines.append(f"| {label} | {show_date(pair['dates'][name])} | {show_lead(lead)} |")
    lines.append(f"| MAE | {show_date(pair['dates']['mae'])} | |")

    test = results[results["period"] == "test"]
    lines += ["", "Test windows, z-scores (up = more drift):", "",
              "| Window | tau_z | tau_seasonal_z | mae_z |", "|---|---|---|---|"]
    for _, row in test.iterrows():
        lines.append(f"| {row['window_start'].date()} | {row['tau_z']:+.2f} | "
                     f"{row[f'{SEASONAL}_z']:+.2f} | {row['mae_z']:+.2f} |")
    return lines + [""]


def main():
    lines = ["# Seasonal check (A15 follow-up)", "",
             "An additional check beside the main result, which is unchanged in "
             "`results/drift_*.csv` and `results/summary.md`.", "",
             "`tau` compares each window with the October 2025 reference. `tau_seasonal` "
             "compares it with the same fortnight a year earlier, so a move that only "
             "`tau` shows may be seasonal, and a move both show is not.", ""]

    for model in MODEL_FEATURES:
        results, thresholds = add_seasonal_threshold(load_results(model))
        single, pair = crossings(results, 1), crossings(results, 2)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        results.to_csv(seasonal_file(model), index=False)
        figure = plot_seasonal(results, model, thresholds)

        print(f"\n{model} model")
        print(f"  baseline tau_seasonal: mean {thresholds[f'{SEASONAL}_mean']:.4f}, "
              f"sd {thresholds[f'{SEASONAL}_sd']:.4f}")
        for name in ("tau", SEASONAL, "mae"):
            print(f"  first {name} warning: {show_date(single['dates'][name])}"
                  f"   (two in a row: {show_date(pair['dates'][name])})")
        print(f"  lead time, MAE after tau: {show_lead(single['lead_vs_tau'])}"
              f"   (two in a row: {show_lead(pair['lead_vs_tau'])})")
        print(f"  lead time, MAE after tau_seasonal: {show_lead(single['lead_vs_seasonal'])}"
              f"   (two in a row: {show_lead(pair['lead_vs_seasonal'])})")
        print(f"  saved {seasonal_file(model)}")
        print(f"  saved {figure}")

        lines += report_lines(model, results, thresholds, single, pair)

    CHECK_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nsaved {CHECK_FILE}")


if __name__ == "__main__":
    main()

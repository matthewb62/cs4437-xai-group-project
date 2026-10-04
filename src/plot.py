"""Drift plots from the results tables written by analyse.py (O2, O5).

Usage:
    python src/plot.py          # synthetic stand-in results, figures named *_SAMPLE
    python src/plot.py --real   # the real results
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FixedLocator, ScalarFormatter

from analyse import MODEL_FEATURES, drift_file, output_suffix, thresholds_file
from config import FIGURES_DIR, SD_MULTIPLIER, SHOCK_DATE

# Style only: no dates or thresholds here.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE_SHADE = "#f0efec"
SERIES = {   # metric -> (z column, legend label, colour, marker)
    "tau": ("tau_z", "Explanation drift (weighted tau, sign flipped)", "#2a78d6", "o"),
    "mae": ("mae_z", "Error (MAE)", "#eb6834", "s"),
    "psi": ("psi_z", "Input drift (mean PSI)", "#1baf7a", "^"),
}
LOG_ABOVE = 5          # when any z-score passes LOG_SWITCH, the axis is linear up to here and log beyond
LOG_SWITCH = 10
LOG_TICKS = [-5, -2, 0, 2, 5, 10, 20, 50, 100, 200, 500]


def load_results(model, real):
    path = drift_file(model, real)
    if not path.exists():
        raise SystemExit(f"{path} not found. Run analyse.py{' --real' if real else ''} first.")
    return pd.read_csv(path, parse_dates=["window_start", "window_end"])


def style_axis(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=13, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def mark_periods(ax, results):
    """Shade the baseline period and mark the shock date."""
    shock = pd.Timestamp(SHOCK_DATE)
    baseline_start = results.loc[results["period"] == "baseline", "window_start"].min()
    ax.axvspan(baseline_start, shock, color=BASELINE_SHADE, zorder=0)
    ax.axvline(shock, color=INK, linewidth=1.5, zorder=2)
    return baseline_start, shock


def date_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))


def plot_z(results, model, real):
    """O2: the three metrics in baseline standard deviations on one axis."""
    fig, ax = plt.subplots(figsize=(12.8, 7.2), facecolor=SURFACE)
    style_axis(ax)
    baseline_start, shock = mark_periods(ax, results)

    for metric, (column, label, colour, marker) in SERIES.items():
        ax.plot(results["window_start"], results[column], color=colour, linewidth=2, zorder=3)
        warned = results[f"{metric}_warn"]
        ax.plot(results.loc[~warned, "window_start"], results.loc[~warned, column], linestyle="none",
                marker=marker, markersize=8, markerfacecolor=SURFACE, markeredgecolor=colour,
                markeredgewidth=2, zorder=4)
        ax.plot(results.loc[warned, "window_start"], results.loc[warned, column], linestyle="none",
                marker=marker, markersize=9, color=colour, zorder=4, label=label)
        if not warned.any():   # still needs a legend entry
            ax.plot([], [], linestyle="none", marker=marker, markersize=9, color=colour, label=label)

    ax.axhline(SD_MULTIPLIER, color=INK_SECONDARY, linewidth=1.5, linestyle=(0, (5, 4)), zorder=2)
    ax.axhline(0, color=GRID, linewidth=1.2, zorder=1)

    z_columns = [column for column, *_ in SERIES.values()]
    highest = results[z_columns].max().max()
    if highest > LOG_SWITCH:
        ax.set_yscale("symlog", linthresh=LOG_ABOVE)
        ax.yaxis.set_major_locator(FixedLocator(LOG_TICKS))
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.yaxis.set_minor_locator(FixedLocator([]))
        scale_note = f" (log scale above {LOG_ABOVE})"
    else:
        scale_note = ""
    low = min(results[z_columns].min().min(), -SD_MULTIPLIER) - 0.5
    ax.set_ylim(low, highest * 1.6 if highest > LOG_SWITCH else max(highest, SD_MULTIPLIER) + 1.5)
    ax.set_ylabel(f"Standard deviations from baseline mean{scale_note}\nup = more drift",
                  fontsize=13, color=INK_SECONDARY)

    date_axis(ax)
    x_end = results["window_start"].max() + pd.Timedelta(days=10)
    ax.set_xlim(baseline_start - pd.Timedelta(days=5), x_end)

    top = ax.get_ylim()[1]
    note = dict(fontsize=13, color=INK_SECONDARY, va="top")
    ax.text(baseline_start + (shock - baseline_start) / 2, top, "Baseline", ha="center", **note)
    ax.text(shock + pd.Timedelta(days=3), top, f"Shock {shock:%d %b %Y}", ha="left", **note)
    ax.text(x_end, SD_MULTIPLIER, f" {SD_MULTIPLIER:g} SD warning line", ha="left", va="center",
            fontsize=13, color=INK_SECONDARY, clip_on=False)

    legend = ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3, frameon=False, fontsize=13,
                       handletextpad=0.4, columnspacing=1.8)
    for text in legend.get_texts():
        text.set_color(INK)
    title = f"{model.capitalize()} model: drift per fortnight"
    if not real:
        title += "  [SYNTHETIC SAMPLE DATA, not a result]"
    fig.suptitle(title, fontsize=18, color=INK, x=0.07, ha="left", y=0.975)
    fig.text(0.07, 0.015, "Filled marker = window over the warning line. Each point is one 14-day window, "
             "plotted at its start date.", fontsize=11, color=INK_MUTED)
    fig.subplots_adjust(left=0.09, right=0.84, top=0.85, bottom=0.14)

    path = FIGURES_DIR / f"drift_{model}{output_suffix(real)}.png"
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_raw(results, model, real):
    """O5: the same three metrics in raw units, one panel each."""
    thresholds = json.loads(thresholds_file(model, real).read_text())
    panels = [   # metric, column, y label, side of the mean the warning line sits on
        ("tau", "tau", "Weighted tau", -1),
        ("mae", "mae", "MAE (EUR/MWh)", 1),
        ("psi", "psi_mean", "Mean PSI", 1),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(12.8, 9.6), sharex=True, facecolor=SURFACE)
    for ax, (metric, column, ylabel, side) in zip(axes, panels):
        _, _, colour, marker = SERIES[metric]
        style_axis(ax)
        baseline_start, shock = mark_periods(ax, results)
        line = thresholds[f"{metric}_mean"] + side * SD_MULTIPLIER * thresholds[f"{metric}_sd"]
        ax.axhline(line, color=INK_SECONDARY, linewidth=1.5, linestyle=(0, (5, 4)), zorder=2)
        ax.plot(results["window_start"], results[column], color=colour, linewidth=2, zorder=3)
        warned = results[f"{metric}_warn"]
        ax.plot(results.loc[~warned, "window_start"], results.loc[~warned, column], linestyle="none",
                marker=marker, markersize=7, markerfacecolor=SURFACE, markeredgecolor=colour,
                markeredgewidth=2, zorder=4)
        ax.plot(results.loc[warned, "window_start"], results.loc[warned, column], linestyle="none",
                marker=marker, markersize=8, color=colour, zorder=4)
        ax.set_ylabel(ylabel, fontsize=13, color=INK_SECONDARY)
        x_end = results["window_start"].max() + pd.Timedelta(days=10)
        ax.set_xlim(baseline_start - pd.Timedelta(days=5), x_end)
        ax.text(x_end, line, f" {SD_MULTIPLIER:g} SD warning line", ha="left", va="center",
                fontsize=12, color=INK_SECONDARY, clip_on=False)
    axes[0].set_ylim(-1, 1.05)
    top = axes[0].get_ylim()[1]
    note = dict(fontsize=12, color=INK_SECONDARY, va="bottom")
    axes[0].text(baseline_start + (shock - baseline_start) / 2, top, "Baseline", ha="center", **note)
    axes[0].text(shock + pd.Timedelta(days=3), top, f"Shock {shock:%d %b %Y}", ha="left", **note)
    date_axis(axes[-1])

    title = f"{model.capitalize()} model: drift per fortnight, raw units"
    if not real:
        title += "  [SYNTHETIC SAMPLE DATA, not a result]"
    fig.suptitle(title, fontsize=18, color=INK, x=0.07, ha="left", y=0.975)
    fig.text(0.07, 0.012, "Filled marker = window over the warning line. Each point is one 14-day window, "
             "plotted at its start date.", fontsize=11, color=INK_MUTED)
    fig.subplots_adjust(left=0.09, right=0.84, top=0.9, bottom=0.11, hspace=0.12)

    path = FIGURES_DIR / f"drift_{model}_raw{output_suffix(real)}.png"
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--real", action="store_true",
                        help="plot the real results instead of the synthetic stand-in results")
    args = parser.parse_args()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for model in MODEL_FEATURES:
        results = load_results(model, args.real)
        print(f"saved {plot_z(results, model, args.real)}")
        print(f"saved {plot_raw(results, model, args.real)}")


if __name__ == "__main__":
    main()

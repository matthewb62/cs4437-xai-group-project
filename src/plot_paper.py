"""The paper's figures, as one-column PDFs for the IEEE template.

Usage:
    python src/plot_paper.py

Reads what analyse.py and check_seasonal.py wrote and makes, for the blind model:
    report/figures/tau_seasonal.pdf   tau against October and against the same fortnight a
                                      year earlier, with MAE, in baseline standard deviations
    report/figures/shap_top4.pdf      mean |SHAP| of the four most important features per fortnight
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from config import PAPER_FIGURES_DIR, RESULTS_DIR, SD_MULTIPLIER, SHOCK_DATE, VAL_END, VAL_START

MODEL = "blind"

# Style only: no dates or thresholds here. Sized for one IEEE column at 8 pt.
WIDTH_IN = 3.5
HEIGHT_IN = 2.3
FONT_PT = 8
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE_SHADE = "#f0efec"
TAU_SERIES = [   # (column, warn column, legend label, colour, marker, line style)
    ("tau_z", "tau_warn", r"$\tau_w$ vs Oct 2025", "#2a78d6", "o", "-"),
    ("tau_seasonal_z", "tau_seasonal_warn", r"$\tau_w$ vs same fortnight 2025", "#1baf7a", "D", "--"),
    ("mae_z", "mae_warn", "MAE", "#eb6834", "s", "-"),
]
SHAP_SERIES = [   # (feature column, legend label, colour, marker, line style)
    ("price_lag_1d", "Yesterday's price", "#2a78d6", "o", "-"),
    ("wind_forecast", "Wind forecast", "#eb6834", "s", "--"),
    ("solar_forecast", "Solar forecast", "#1baf7a", "D", "-."),
    ("demand_forecast", "Demand forecast", "#eda100", "^", ":"),
]


def setup():
    plt.rcParams.update({
        "font.size": FONT_PT, "axes.labelsize": FONT_PT, "legend.fontsize": FONT_PT - 1,
        "xtick.labelsize": FONT_PT - 1, "ytick.labelsize": FONT_PT - 1,
        "pdf.fonttype": 42, "font.family": "serif", "mathtext.fontset": "stix",
        # Times to match the IEEE template; STIX ships with matplotlib as the fallback.
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "STIXGeneral"],
    })


def style_axis(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[11, 1, 3, 5, 7, 9]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))


def mark_periods(ax, baseline_start):
    shock = pd.Timestamp(SHOCK_DATE)
    ax.axvspan(baseline_start, shock, color=BASELINE_SHADE, zorder=0, linewidth=0)
    ax.axvline(shock, color=INK, linewidth=0.8, zorder=2)
    top = ax.get_ylim()[1]
    ax.text(shock + pd.Timedelta(days=3), top, "Shock", ha="left", va="top", color=INK_SECONDARY)
    ax.text(baseline_start + pd.Timedelta(days=3), top, "Baseline", ha="left", va="top",
            color=INK_SECONDARY)


def save(fig, name):
    PAPER_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = PAPER_FIGURES_DIR / name
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_tau_seasonal():
    path = RESULTS_DIR / f"drift_{MODEL}_seasonal.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run check_seasonal.py first.")
    results = pd.read_csv(path, parse_dates=["window_start"])
    x = results["window_start"]

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), layout="constrained")
    style_axis(ax)
    for column, warn, label, colour, marker, style in TAU_SERIES:
        warned = results[warn].astype(bool)
        ax.plot(x, results[column], color=colour, linewidth=1.2, linestyle=style, zorder=3,
                marker=marker, markersize=3, markerfacecolor="white", markeredgewidth=0.8, label=label)
        # Filled marker = window over the warning line.
        ax.plot(x[warned], results.loc[warned, column], linestyle="none", marker=marker,
                markersize=3.5, color=colour, zorder=4)
    ax.axhline(SD_MULTIPLIER, color=INK_SECONDARY, linewidth=0.8, linestyle=(0, (4, 3)), zorder=2)
    ax.text(x.max() + pd.Timedelta(days=4), SD_MULTIPLIER, f"{SD_MULTIPLIER:g} SD", va="center",
            ha="left", color=INK_SECONDARY)
    columns = [column for column, *_ in TAU_SERIES]
    ax.set_ylim(min(results[columns].min().min(), -SD_MULTIPLIER) - 0.5,
                results[columns].max().max() + 1.5)
    ax.set_xlim(x.min() - pd.Timedelta(days=5), x.max() + pd.Timedelta(days=5))
    ax.set_ylabel("SDs from baseline\n(up = more drift)", color=INK_SECONDARY)
    mark_periods(ax, results.loc[results["period"] == "baseline", "window_start"].min())
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False,
              handlelength=2.2, columnspacing=1.0, borderaxespad=0.2)
    return save(fig, "tau_seasonal.pdf")


def plot_shap_top4():
    path = RESULTS_DIR / f"importance_{MODEL}.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run analyse.py --real first.")
    importance = pd.read_csv(path)
    # The reference row covers the whole validation month, so plot it at the month's middle.
    val_start, val_end = pd.Timestamp(VAL_START), pd.Timestamp(VAL_END)
    reference_x = val_start + (val_end - val_start) / 2
    x = importance["window_start"].map(
        lambda w: reference_x if w == "reference" else pd.Timestamp(w))

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), layout="constrained")
    style_axis(ax)
    for column, label, colour, marker, style in SHAP_SERIES:
        ax.plot(x, importance[column], color=colour, linewidth=1.2, linestyle=style, marker=marker,
                markersize=3, markeredgewidth=0, label=label, zorder=3)
    ax.set_ylim(0, importance[[s[0] for s in SHAP_SERIES]].max().max() * 1.15)
    ax.set_xlim(reference_x - pd.Timedelta(days=14), x.max() + pd.Timedelta(days=5))
    ax.set_ylabel("Mean |SHAP| (EUR/MWh)", color=INK_SECONDARY)
    baseline_start = pd.Timestamp(importance.loc[importance["window_start"] != "reference",
                                                 "window_start"].min())
    mark_periods(ax, baseline_start)
    ax.text(reference_x, ax.get_ylim()[1], "Oct", ha="center", va="top", color=INK_SECONDARY)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False,
              handlelength=2.2, columnspacing=1.0, borderaxespad=0.2)
    return save(fig, "shap_top4.pdf")


def main():
    setup()
    for path in (plot_tau_seasonal(), plot_shap_top4()):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

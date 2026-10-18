# Figures plan (draft)

We have room for 2-3 figures. Each one is a single column (`width=\columnwidth`, about 3.5 in wide), saved as PDF to `report/figures/`, with fonts readable at that size (about 8 pt). Captions go below. All three are made from `results/*.csv` in code, not screenshots of the PNGs in `figures/`, which are sized for slides.

The order below is the order of priority. If we only have room for two, drop Fig. 3 and use Table I instead.

---

## Fig. 1: Warning signals over time (both models)

**Where:** Results, Drift Signals (Tom), at the top of the subsection. Discussion (Holly) refers back to it.

**What it shows:** the main result. When did each signal cross its warning line, and in what order.

**How:** two panels stacked (blind on top, oil below) with a shared date axis. Each panel has:
- `tau_z`, `mae_z` and `psi_z` per fortnight, with "up = more drift" for all three so they share one y-axis (SDs from the baseline mean)
- a dashed horizontal line at +2 SD (the warning line)
- a vertical line at 28 Feb 2026 (the shock), and the baseline windows shaded
- filled markers where a window is over the line and hollow markers where it isn't, as in `src/plot.py`

**Data:** `results/drift_blind.csv` and `results/drift_oil.csv` (`window_start`, `tau_z`, `mae_z`, `psi_z`, `*_warn`).

**What the reader should see:**
- Blind: tau crosses once on 25 Apr and drops back. MAE crosses on 20 Jun and stays over. PSI crosses on 15 Aug.
- Oil: tau is over for three fortnights in a row (25 Apr, 9 May, 23 May), MAE crosses on 23 May, PSI on 12 Sep.

`src/plot.py` (`plot_z`) already makes most of this, so it's mostly a matter of resizing and saving as PDF.

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{signals_z.pdf}
  \caption{Explanation drift ($\tau_w$), error (MAE) and input drift (mean
  PSI) per fortnight, in standard deviations from the baseline mean, for
  the blind (top) and oil (bottom) models. Dashed line: 2~SD warning
  threshold. Vertical line: shock onset (28 February 2026). Filled
  markers: window over the threshold.}
  \label{fig:signals}
\end{figure}
```

---

## Fig. 2: The tau warning goes away once the season is taken out

**Where:** Results, Drift Signals, right after the first-crossing dates. Discussion uses it to argue the 25 Apr warning was spring solar and not the shock.

**What it shows:** `tau_z` (against October 2025) next to `tau_seasonal_z` (against the same fortnight a year earlier), blind model only, with `mae_z` for reference.

**Data:** `results/drift_blind_seasonal.csv`. The table in `results/seasonal_check.md` has the same numbers: on 25 Apr tau_z is +2.90 but tau_seasonal_z is only +0.40, and tau_seasonal never crosses.

**Why it's worth a figure:** it's what flips our answer from "explanations warned first" to "not reliably", so the reader needs to see it, not just read it.

**To save space:** this could be a dashed fourth line in Fig. 1 instead of its own figure. The blind panel would get crowded though, so try both.

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{tau_seasonal.pdf}
  \caption{Blind model: $\tau_w$ against the October 2025 reference
  (solid) and against the same fortnight one year earlier (dashed), with
  MAE for comparison. The 25 April warning disappears once the season is
  removed.}
  \label{fig:seasonal}
\end{figure}
```

---

## Fig. 3: Yesterday's price grows, but the ranking barely moves

**Where:** Results, Drift Signals, near the end. This is the figure behind the "size not order" point in the conclusion, so Discussion and Conclusion can both refer to it.

**What it shows:** mean |SHAP| in €/MWh per fortnight for the top four features (yesterday's price, wind, solar, demand), blind model, with the shock line.

**Data:** `results/importance_blind.csv` (one row per window, one column per feature, plus a `reference` row for October 2025).

**What the reader should see:**
- Yesterday's price climbs from 11.3 (October) to 35.3 €/MWh (26 Sep), roughly three times as much.
- The top four features are the same set in 24 of 25 windows (price_lag_7d swaps in for demand on 12 Sep only), so a rank-based tau has very little to pick up.
- Yesterday's price was in the top 2 in 0 of 8 fortnights before the shock and 9 of 16 after.

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{shap_top4.pdf}
  \caption{Blind model: mean absolute SHAP value per fortnight for the
  four most important features. Yesterday's price roughly triples after
  the shock while the top four stay the same, a change a rank-based
  measure cannot register.}
  \label{fig:shap}
\end{figure}
```

---

## Table I (instead of a figure, or as well as one)

**Where:** Results, Drift Signals. A table takes less space than a figure and gives the exact dates.

**Data:** `results/summary.md` and `results/seasonal_check.md`.

```latex
\begin{table}[t]
  \caption{First Warning by Signal (Start of Fortnight, 2026)}
  \label{tab:warnings}
  \centering
  \begin{tabular}{lcccc}
    \hline
    & \multicolumn{2}{c}{Single window} & \multicolumn{2}{c}{Two in a row} \\
    Signal & Blind & Oil & Blind & Oil \\
    \hline
    $\tau_w$          & 25 Apr & 25 Apr & never  & 9 May  \\
    $\tau_w$ seasonal & never  & never  & never  & never  \\
    MAE               & 20 Jun & 23 May & 4 Jul  & 4 Jul  \\
    Mean PSI          & 15 Aug & 12 Sep & never  & 26 Sep \\
    \hline
  \end{tabular}
\end{table}
```

---

## Things we could include but probably shouldn't

- **Pipeline diagram** (data → LightGBM → SHAP → tau): nice for slides, but the method text already covers it and it costs a quarter of a column.
- **Raw-unit plots** (`figures/drift_*_raw.png`): the z-score version says the same thing on one axis.
- **Oil feature's SHAP over time:** the oil model's Brent feature never ranks higher than 5th (its best is 7.6 €/MWh on 20 Jun), which is worth one sentence in Drift Signals but not a figure.
- **Per-feature PSI heatmap** (`results/psi_features_*.csv`): interesting, but PSI is our control, not the main result.

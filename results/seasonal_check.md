# Seasonal check (A15 follow-up)

An additional check beside the main result, which is unchanged in `results/drift_*.csv` and `results/summary.md`.

`tau` compares each window with the October 2025 reference. `tau_seasonal` compares it with the same fortnight a year earlier, so a move that only `tau` shows may be seasonal, and a move both show is not.

## Blind model

Baseline tau_seasonal mean 0.8665, SD 0.0959 (8 baseline windows, sample SD, the same rule analyse.py uses for tau).

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau (vs Oct 2025) | never crossed | never crossed |
| tau_seasonal (vs same fortnight 2025) | never crossed | never crossed |
| MAE | 2026-06-20 | |

Two windows in a row (A14), dated at the start of the second:

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau | never crossed | never crossed |
| tau_seasonal | never crossed | never crossed |
| MAE | 2026-07-04 | |

Test windows, z-scores (up = more drift):

| Window | tau_z | tau_seasonal_z | mae_z |
|---|---|---|---|
| 2026-02-28 | -0.86 | -0.77 | +0.92 |
| 2026-03-14 | -1.91 | +0.85 | +1.29 |
| 2026-03-28 | -1.32 | +0.13 | +1.11 |
| 2026-04-11 | +0.65 | +0.32 | +0.40 |
| 2026-04-25 | +1.38 | -0.85 | +1.77 |
| 2026-05-09 | -0.01 | -0.12 | +0.55 |
| 2026-05-23 | +0.80 | -1.10 | +1.31 |
| 2026-06-06 | +1.30 | -0.78 | +0.89 |
| 2026-06-20 | +0.59 | -0.16 | +2.30 |
| 2026-07-04 | +1.01 | -1.12 | +2.21 |
| 2026-07-18 | +0.19 | +0.96 | +2.37 |
| 2026-08-01 | +0.23 | -0.36 | +2.84 |
| 2026-08-15 | +0.21 | +0.67 | +5.13 |
| 2026-08-29 | -0.71 | +0.45 | +6.42 |
| 2026-09-12 | +0.10 | +1.12 | +6.23 |

## Oil model

Baseline tau_seasonal mean 0.8949, SD 0.0886 (8 baseline windows, sample SD, the same rule analyse.py uses for tau).

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau (vs Oct 2025) | 2026-04-25 | +56 days |
| tau_seasonal (vs same fortnight 2025) | never crossed | never crossed |
| MAE | 2026-06-20 | |

Two windows in a row (A14), dated at the start of the second:

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau | never crossed | never crossed |
| tau_seasonal | never crossed | never crossed |
| MAE | 2026-07-04 | |

Test windows, z-scores (up = more drift):

| Window | tau_z | tau_seasonal_z | mae_z |
|---|---|---|---|
| 2026-02-28 | -0.67 | -0.30 | +0.79 |
| 2026-03-14 | -1.51 | +0.99 | +1.08 |
| 2026-03-28 | -1.72 | +1.33 | +1.19 |
| 2026-04-11 | +0.36 | +1.34 | +0.68 |
| 2026-04-25 | +2.30 | -0.60 | +1.98 |
| 2026-05-09 | +0.58 | +0.39 | +0.46 |
| 2026-05-23 | +1.42 | -0.68 | +1.36 |
| 2026-06-06 | +0.56 | -0.17 | +1.03 |
| 2026-06-20 | +0.62 | +0.10 | +2.89 |
| 2026-07-04 | +0.39 | +0.08 | +2.36 |
| 2026-07-18 | +0.59 | +0.67 | +1.92 |
| 2026-08-01 | +0.82 | +0.25 | +2.31 |
| 2026-08-15 | +1.13 | +0.60 | +5.13 |
| 2026-08-29 | -0.27 | +0.83 | +6.43 |
| 2026-09-12 | +0.63 | +1.55 | +6.16 |

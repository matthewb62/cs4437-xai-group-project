# Seasonal check (A15 follow-up)

An additional check beside the main result, which is unchanged in `results/drift_*.csv` and `results/summary.md`.

`tau` compares each window with the October 2025 reference. `tau_seasonal` compares it with the same fortnight a year earlier, so a move that only `tau` shows may be seasonal, and a move both show is not.

## Blind model

Baseline tau_seasonal mean 0.8729, SD 0.0844 (8 baseline windows, sample SD, the same rule analyse.py uses for tau).

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
| 2026-02-28 | +0.52 | -0.14 | +0.70 |
| 2026-03-14 | -1.15 | +0.05 | +0.76 |
| 2026-03-28 | +0.56 | -1.23 | +0.53 |
| 2026-04-11 | +1.39 | -0.36 | +0.16 |
| 2026-04-25 | +2.90 | +0.40 | +1.29 |
| 2026-05-09 | +1.93 | -0.85 | +0.77 |
| 2026-05-23 | +1.86 | +0.62 | +1.58 |
| 2026-06-06 | -0.63 | +0.18 | +0.71 |
| 2026-06-20 | +0.65 | -0.85 | +2.20 |
| 2026-07-04 | +0.27 | +0.56 | +3.22 |
| 2026-07-18 | +1.04 | +0.59 | +3.34 |
| 2026-08-01 | +0.59 | -0.32 | +3.15 |
| 2026-08-15 | +0.89 | +0.01 | +5.83 |
| 2026-08-29 | -0.94 | -0.19 | +7.14 |
| 2026-09-12 | -0.00 | +0.64 | +6.27 |
| 2026-09-26 | +1.59 | +0.71 | +6.39 |

## Oil model

Baseline tau_seasonal mean 0.8635, SD 0.0898 (8 baseline windows, sample SD, the same rule analyse.py uses for tau).

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau (vs Oct 2025) | 2026-04-25 | +28 days |
| tau_seasonal (vs same fortnight 2025) | never crossed | never crossed |
| MAE | 2026-05-23 | |

Two windows in a row (A14), dated at the start of the second:

| Metric | First crossing | MAE's lead time after it |
|---|---|---|
| tau | 2026-05-09 | +56 days |
| tau_seasonal | never crossed | never crossed |
| MAE | 2026-07-04 | |

Test windows, z-scores (up = more drift):

| Window | tau_z | tau_seasonal_z | mae_z |
|---|---|---|---|
| 2026-02-28 | -0.65 | +0.94 | +0.35 |
| 2026-03-14 | -0.56 | +0.04 | +0.42 |
| 2026-03-28 | +0.67 | -0.48 | +0.36 |
| 2026-04-11 | +1.04 | -0.22 | +0.43 |
| 2026-04-25 | +3.60 | +0.21 | +1.37 |
| 2026-05-09 | +2.16 | -0.67 | +0.79 |
| 2026-05-23 | +2.66 | +0.45 | +2.02 |
| 2026-06-06 | +0.23 | +0.70 | +1.17 |
| 2026-06-20 | +1.04 | -0.76 | +3.36 |
| 2026-07-04 | +1.25 | +0.35 | +3.42 |
| 2026-07-18 | +1.51 | +0.46 | +3.51 |
| 2026-08-01 | +0.82 | +0.29 | +3.27 |
| 2026-08-15 | +1.37 | -0.08 | +5.67 |
| 2026-08-29 | -1.19 | -0.20 | +6.80 |
| 2026-09-12 | +0.47 | +0.11 | +6.16 |
| 2026-09-26 | -0.07 | +0.39 | +6.29 |

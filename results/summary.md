# Drift summary

Shock date 2026-02-28. Thresholds are 2 SD from the baseline mean. Dates are the start of the first test window over the threshold. Lead times are measured from the tau warning, so positive means tau warned first.

## Blind model

| Metric | Baseline mean | Baseline SD | First crossing | Lead time against tau |
|---|---|---|---|---|
| tau | 0.8299 | 0.0586 | 2026-04-25 | |
| MAE (EUR/MWh) | 16.091 | 5.621 | 2026-06-20 | +56 days |
| PSI (mean) | 0.8437 | 0.3012 | 2026-08-15 | +112 days |
| PSI, any feature at 0.25 | | | 2026-02-28 | |

**Outcome (O3): explanation drift warned first.** The label follows the single-window crossings (A11), which are the main result. Requiring two windows in a row (A14) gives: error warned first. The two disagree, so the outcome does not survive the robustness check.

Ordering: Tau warned 56 days before MAE.

Robustness (A14): a warning needs two windows in a row over the threshold, and is dated at the start of the second.

| Metric | First crossing, two in a row | Lead time against tau |
|---|---|---|
| tau | never crossed | |
| MAE | 2026-07-04 | never crossed |
| PSI (mean) | never crossed | never crossed |

Ordering, two in a row: MAE crossed its threshold and tau never did.

Top 5 features by mean absolute SHAP (EUR/MWh):

| Rank | Reference month | First tau warning (2026-04-25) | Latest window (2026-09-26) |
|---|---|---|---|
| 1 | wind_forecast (27.73) | solar_forecast (29.54) | price_lag_1d (35.33) |
| 2 | solar_forecast (13.62) | price_lag_1d (17.05) | wind_forecast (34.37) |
| 3 | demand_forecast (12.70) | demand_forecast (13.79) | solar_forecast (22.01) |
| 4 | price_lag_1d (11.28) | wind_forecast (12.49) | demand_forecast (14.72) |
| 5 | price_lag_7d (5.01) | price_lag_2d (4.38) | price_lag_7d (13.75) |

## Oil model

| Metric | Baseline mean | Baseline SD | First crossing | Lead time against tau |
|---|---|---|---|---|
| tau | 0.8399 | 0.0431 | 2026-04-25 | |
| MAE (EUR/MWh) | 16.465 | 6.287 | 2026-05-23 | +28 days |
| PSI (mean) | 1.5428 | 0.7360 | 2026-09-12 | +140 days |
| PSI, any feature at 0.25 | | | 2026-02-28 | |

**Outcome (O3): explanation drift warned first.** The label follows the single-window crossings (A11), which are the main result. Requiring two windows in a row (A14) gives: explanation drift warned first.

Ordering: Tau warned 28 days before MAE.

Robustness (A14): a warning needs two windows in a row over the threshold, and is dated at the start of the second.

| Metric | First crossing, two in a row | Lead time against tau |
|---|---|---|
| tau | 2026-05-09 | |
| MAE | 2026-07-04 | +56 days |
| PSI (mean) | 2026-09-26 | +140 days |

Ordering, two in a row: Tau warned 56 days before MAE.

Top 5 features by mean absolute SHAP (EUR/MWh):

| Rank | Reference month | First tau warning (2026-04-25) | Latest window (2026-09-26) |
|---|---|---|---|
| 1 | wind_forecast (28.59) | solar_forecast (29.62) | wind_forecast (37.00) |
| 2 | solar_forecast (14.01) | price_lag_1d (16.43) | price_lag_1d (34.51) |
| 3 | demand_forecast (12.88) | demand_forecast (14.02) | solar_forecast (23.01) |
| 4 | price_lag_1d (10.81) | wind_forecast (12.38) | demand_forecast (15.35) |
| 5 | price_lag_7d (5.07) | price_lag_7d (4.35) | price_lag_7d (14.89) |

## Blind against oil

| | Blind model | Oil model |
|---|---|---|
| First tau warning | 2026-04-25 | 2026-04-25 |
| First MAE warning | 2026-06-20 | 2026-05-23 |
| First PSI warning | 2026-08-15 | 2026-09-12 |
| Lead time, MAE against tau | +56 days | +28 days |
| Lead time, PSI against tau | +112 days | +140 days |
| First tau warning, two in a row | never crossed | 2026-05-09 |
| First MAE warning, two in a row | 2026-07-04 | 2026-07-04 |
| First PSI warning, two in a row | never crossed | 2026-09-26 |
| Lead time, MAE against tau, two in a row | never crossed | +56 days |
| Lead time, PSI against tau, two in a row | never crossed | +140 days |

## Validation MAE (M6, M7)

| Item | Value |
|---|---|
| validation_window | 2025-10-01..2025-10-31 |
| early_stopping_window | 2025-09-01..2025-09-30 |
| mae_blind_eur_per_mwh | 15.423 |
| mae_oil_eur_per_mwh | 16.317 |
| mae_naive_eur_per_mwh | 43.475 |
| mae_blind_training_eur_per_mwh | 7.435 |
| mae_oil_training_eur_per_mwh | 6.078 |
| blind_validation_minus_training | 7.987 |
| oil_validation_minus_training | 10.239 |
| blind_better_than_naive_pct | 64.5 |
| oil_better_than_naive_pct | 62.5 |
| training_rows | 14140 |
| validation_rows | 745 |

## Oil range (F10)

| Item | Value |
|---|---|
| largest_30d_oil_change_training_pct | 21.37 |
| range_30d_oil_change_training_pct | [-20.32, 21.37] |
| largest_30d_oil_change_test_pct | 77.64 |
| range_30d_oil_change_test_pct | [-32.56, 77.64] |

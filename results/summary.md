# Drift summary

Shock date 2026-02-28. Thresholds are 2 SD from the baseline mean. Dates are the start of the first test window over the threshold. Lead times are measured from the tau warning, so positive means tau warned first.

## Blind model

| Metric | Baseline mean | Baseline SD | First crossing | Lead time against tau |
|---|---|---|---|---|
| tau | 0.8288 | 0.0840 | never crossed | |
| MAE (EUR/MWh) | 14.641 | 5.211 | 2026-06-20 | never crossed |
| PSI (mean) | 2.2113 | 0.8383 | never crossed | never crossed |
| PSI, any feature at 0.25 | | | 2026-02-28 | |

**Outcome (O3): error warned first.** The label follows the single-window crossings (A11), which are the main result. Requiring two windows in a row (A14) gives: error warned first.

Ordering: MAE crossed its threshold and tau never did.

Robustness (A14): a warning needs two windows in a row over the threshold, and is dated at the start of the second.

| Metric | First crossing, two in a row | Lead time against tau |
|---|---|---|
| tau | never crossed | |
| MAE | 2026-07-04 | never crossed |
| PSI (mean) | never crossed | never crossed |

Ordering, two in a row: MAE crossed its threshold and tau never did.

Top 5 features by mean absolute SHAP (EUR/MWh):

| Rank | Reference month | Latest window (2026-09-12) |
|---|---|---|
| 1 | wind_forecast (25.34) | price_lag_1d (35.54) |
| 2 | price_lag_1d (13.90) | wind_forecast (29.83) |
| 3 | solar_forecast (11.64) | price_lag_7d (18.18) |
| 4 | demand_forecast (10.62) | solar_forecast (17.35) |
| 5 | price_lag_7d (5.66) | demand_forecast (10.94) |

## Oil model

| Metric | Baseline mean | Baseline SD | First crossing | Lead time against tau |
|---|---|---|---|---|
| tau | 0.8604 | 0.0612 | 2026-04-25 | |
| MAE (EUR/MWh) | 14.499 | 5.095 | 2026-06-20 | +56 days |
| PSI (mean) | 2.4943 | 0.8782 | never crossed | never crossed |
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

| Rank | Reference month | First tau warning (2026-04-25) | Latest window (2026-09-12) |
|---|---|---|---|
| 1 | wind_forecast (24.47) | solar_forecast (22.80) | price_lag_1d (37.03) |
| 2 | price_lag_1d (14.29) | price_lag_1d (19.66) | wind_forecast (29.73) |
| 3 | solar_forecast (11.18) | demand_forecast (11.20) | price_lag_7d (17.96) |
| 4 | demand_forecast (10.13) | wind_forecast (10.98) | solar_forecast (16.68) |
| 5 | price_lag_7d (5.60) | price_lag_7d (4.72) | demand_forecast (10.82) |

## Blind against oil

| | Blind model | Oil model |
|---|---|---|
| First tau warning | never crossed | 2026-04-25 |
| First MAE warning | 2026-06-20 | 2026-06-20 |
| First PSI warning | never crossed | never crossed |
| Lead time, MAE against tau | never crossed | +56 days |
| Lead time, PSI against tau | never crossed | never crossed |
| First tau warning, two in a row | never crossed | never crossed |
| First MAE warning, two in a row | 2026-07-04 | 2026-07-04 |
| First PSI warning, two in a row | never crossed | never crossed |
| Lead time, MAE against tau, two in a row | never crossed | never crossed |
| Lead time, PSI against tau, two in a row | never crossed | never crossed |

## Validation MAE (M6, M7)

| Item | Value |
|---|---|
| validation_window | 2025-10-01..2025-10-31 |
| mae_blind_eur_per_mwh | 14.461 |
| mae_oil_eur_per_mwh | 14.872 |
| mae_naive_eur_per_mwh | 43.475 |
| mae_blind_training_eur_per_mwh | 10.923 |
| mae_oil_training_eur_per_mwh | 11.122 |
| blind_validation_minus_training | 3.539 |
| oil_validation_minus_training | 3.75 |
| blind_better_than_naive_pct | 66.7 |
| oil_better_than_naive_pct | 65.8 |
| training_rows | 14860 |
| validation_rows | 745 |

## Oil range (F10)

| Item | Value |
|---|---|
| largest_30d_oil_change_training_pct | 21.37 |
| range_30d_oil_change_training_pct | [-20.32, 21.37] |
| largest_30d_oil_change_test_pct | 77.64 |
| range_30d_oil_change_test_pct | [-32.56, 77.64] |

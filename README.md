# cs4437-xai-group-project

**Does a model's explanation drift before its accuracy does?** We test whether the features a
LightGBM price model leans on start shifting *before* its error rises, using the closure of the
Strait of Hormuz on 28 February 2026 as a real break in the data.

## Team
Matthew Burke · Holly Best · Tom Byrne · Conor Clancy

## Method

**Domain.** German day-ahead electricity prices for the DE-LU bidding zone, one delivery hour per
row. Electricity only — traffic and flights were dropped on 30 Sep.

**The model.** One LightGBM regression model covering all 24 hours, with `hour` as a feature rather
than 24 separate models. Features are past prices (1, 2 and 7 days earlier), the day-ahead demand,
wind and solar forecasts, lagged gas-fired generation, a population-weighted temperature forecast,
and time features (hour, weekday, month, German public holiday). Everything a row uses was knowable
before the auction closed at 12:00 on the day before delivery, which is what sets every lag.

**Two versions.** The *blind* model never sees the oil price. The *oil* model adds one column, the
30-day % change in Brent. Same rows, same hyperparameters, same seed — only the feature list
differs. The blind model is the one that answers the question: can the explanation shift from the
electricity data alone?

**Measuring drift.** Both models are trained once and then frozen. For each 14-day window we compute
exact TreeSHAP values for every hourly prediction, rank the features by mean absolute SHAP, and
compare that ranking against the **October 2025 reference ranking** using weighted Kendall's tau,
which weights the top of the ranking most. Beside it we track MAE in €/MWh and PSI on the inputs
against their training distribution. PSI is the control: it tells us whether SHAP says anything that
simply watching the inputs would not.

**Warning rule.** The Nov 2025 – mid Feb 2026 baseline windows set a mean and sample standard
deviation for each metric. A window warns when tau falls more than 2 SD below its baseline mean, or
when MAE or PSI rises more than 2 SD above. PSI is also flagged at its conventional 0.25 cutoff. The
result we care about is which warning fires first, and by how many days.

### Data windows

| Window | Dates | Use |
| --- | --- | --- |
| Training | Jan 2024 – Sep 2025 | Fitting both models |
| Validation | Oct 2025 | Early stopping, accuracy check, reference SHAP ranking |
| Pre-crisis baseline | Nov 2025 – mid Feb 2026 | Normal wobble, and the 2 SD thresholds |
| Test | 28 Feb 2026 onward | Fortnightly drift tracking |

The feature table starts on 20 January 2024, not 1 January: Open-Meteo's forecast archive begins
there, and a row is dropped if any feature is missing.

### Known limitations

- LightGBM cannot extrapolate past its training range. The largest 30-day oil move in training was
  21.4%, against 77.6% in the test period, so the oil model under-reacts and any drift it shows is
  likely an underestimate.
- The thresholds rest on 8 baseline windows, which is a small sample for a standard deviation.
  `src/check_seasonal.py` and the two-windows-in-a-row check in `results/summary.md` are the agreed
  tests of how much weight the warnings can carry.
- The gas lag takes each hour from the 24 hours before noon on D-1, so the 11:00 hour of D-1 ends
  exactly at the auction close.

## Running it

```bash
pip install -r requirements.txt          # Python 3.13
python src/download_data.py              # into data/raw/, several minutes on a cold run
python src/clean_data.py                 # -> data/processed/clean_hourly.parquet
python src/build_features.py             # -> data/processed/features.parquet
python src/train.py                      # -> models/blind.txt, models/oil.txt
python src/analyse.py --real             # -> results/drift_*.csv, results/summary.md
python src/plot.py --real                # -> figures/drift_*.png
python src/check_seasonal.py             # additional seasonality check
pytest                                   # the automated acceptance checks
```

Each script reads only what the previous one wrote, and stops with a message naming the series or
file if something is missing. Without `--real`, `analyse.py` and `plot.py` run against the synthetic
stand-ins from `src/make_sample_features.py`, which exist only so the analysis could be built before
the real data arrived — outputs from that path are suffixed `_SAMPLE` and are never a result.

Every date, threshold, path and column name lives in `src/config.py`. Nothing is hard-coded in a
script, so changing a window or a threshold means editing that one file.

## Data

Get the data with `python src/download_data.py`. Don't download files by hand, and don't commit
`data/` — it is in `.gitignore`. Each download writes `data/raw/manifest.json` recording the source,
licence and filter used for every file.

| Source | Series | Licence |
| --- | --- | --- |
| [SMARD.de](https://www.smard.de/), Bundesnetzagentur | Day-ahead price (DE-LU), day-ahead load, wind onshore, wind offshore and solar forecasts, actual fossil gas generation | CC BY 4.0 |
| [Open-Meteo](https://open-meteo.com/) | Temperature forecast issued 2 days ahead, 5 German cities | CC BY 4.0 |
| [FRED DCOILBRENTEU](https://fred.stlouisfed.org/series/DCOILBRENTEU) | Brent crude, daily | Public domain, citation requested |

The electricity series were moved from energy-charts to SMARD on 5 Oct 2026, after energy-charts
returned HTTP 503 for over a day. SMARD is asked for hourly data: its hourly figures are the mean of
the four quarter-hours for the price and their sum for the generation series, which is what gives
€/MWh and MW directly. A daily gas *price* series was dropped — no openly licensed one was found.

## Repo layout

| Path | What's in it |
| --- | --- |
| `src/` | One script per step: download, clean, build features, train, analyse, plot |
| `tests/` | pytest acceptance checks, run with `pytest` from the repo root |
| `results/` | `summary.md` (the headline result), `drift_*.csv` per window, `validation.json`, `oil_range.json`, thresholds, `seasonal_check.md` |
| `figures/` | `drift_*.png`, the main plot per model, plus raw-unit and seasonal versions |
| `journal/` | One dated entry per week, `YYYY-MM-DD.md` |
| `report/` | Paper drafts — commit every draft, not just the final one (to be added) |
| `prompts/` | Log of the AI prompts used to write the code, required alongside it |
| `data/` | Downloaded data. Never committed; recreate it with `src/download_data.py` |

## Results so far

`results/summary.md` is the current headline. On October 2025 both models beat the naive forecast
(the same hour's price 7 days earlier) by about two thirds: 14.46 €/MWh for the blind model and
14.87 for the oil model, against 43.48 naive.

## Deliverables

- Presentation: 9 Oct 2026
- Paper (4 pages, fixed format) and journal: 23 Oct 2026
- Latest report draft: TBD

---
*README drafted with AI assistance.*

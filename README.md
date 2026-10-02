# cs4437-xai-group-project

## Team
- Matthew Burke
- Conor Clancy
- Holly Best
- Tom Byrne

## Topic
Does a model's explanation drift before its accuracy does?

We test whether the features a model relies on start shifting *before* its error rate rises, using the 2026 oil shock (Strait of Hormuz closure, late Feb) as a real-world break in the data.

## Approach
- **Domain:** German day-ahead electricity prices (hourly). One domain only — traffic and flights were dropped on 30 Sep.
- **Model:** LightGBM, predicting tomorrow's 24 hourly prices.
- **Two versions:** a main *blind* model that never sees the oil price, and a comparison model that also gets oil as a 30-day % change. The blind model fits the question better — we want to know if explanations shift from the electricity data alone.
- **Drift metric:** SHAP feature rankings every fortnight, compared to the pre-crisis baseline ranking with Kendall's tau.
- **Warning rule:** a fortnight counts as a warning when tau falls more than 2 standard deviations below the pre-crisis window. The same 2σ rule flags an accuracy drop.
- **Baseline for comparison:** Population Stability Index (PSI) on the inputs, to check whether SHAP tells us anything that just watching the inputs wouldn't.

### Data splits
| Window | Use |
| --- | --- |
| Jan 2024 – Sep 2025 | Train |
| Oct 2025 | Validate |
| Nov 2025 – mid Feb 2026 | Pre-crisis baseline (held out, measures normal SHAP wobble) |
| Late Feb 2026 onward | Test (post-shock) |

### Features
Past prices (1, 2 and 7 days ago), electricity demand, wind and solar forecasts, gas-fired generation, temperature, and time features (hour, weekday, month, holidays). The comparison model adds the oil price. Demand/wind/solar come from day-ahead *forecasts*, not actuals, since forecasts are what was known when prices were set. Gas price was dropped (no openly licensed daily series).

### Known limitation
LightGBM can't extrapolate past its training range, so the ~70% oil jump in March 2026 is beyond anything it saw. The comparison model therefore under-reacts to oil, and any drift it shows is likely an underestimate.

## Scope
- Not covering: other XAI method families (counterfactuals, saliency maps, intrinsic models)
- Not covering: domains beyond electricity

## Data
Get the data with `python src/download_data.py` — don't download files by hand, and don't commit `data/`.

Sources (all CC BY 4.0 unless noted):
- [energy-charts.info](https://api.energy-charts.info/) — prices, demand/wind/solar forecasts, gas-fired generation
- [open-meteo.com](https://open-meteo.com/) — temperature
- [FRED DCOILBRENTEU](https://fred.stlouisfed.org/series/DCOILBRENTEU) — Brent oil price

Prices and forecasts arrive in 15-minute steps for part of the range and need converting to hourly.

## Latest Report Draft
TBD (link to Overleaf or /report)

## Structure
- `journal/`: one dated entry per week (`YYYY-MM-DD.md`)
- `report/`: paper drafts. Commit every draft, not just the final one
- `src/`: Python code (data loading, model training, SHAP analysis)
- `prompts/`: log of AI prompts used, as required alongside the code

## Deliverables
- Presentation (slide deck): 9 Oct 2026
- Paper (3 pages, fixed format) + journal: 23 Oct 2026

---
*README drafted with AI assistance.*

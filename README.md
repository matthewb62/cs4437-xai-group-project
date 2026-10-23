# Do Explanations Drift Before Accuracy?

**CS4437 Explainable AI, Group 8** · Matthew Burke · Holly Best · Tom Byrne · Conor Clancy

This repo is our research journal and the work behind it: a dated record of how the project's
decisions were made, alongside the code, results, paper and slides.

## Topic and scope

Can a model's SHAP explanations warn that it is going wrong before its error does? We test this on
one real shock with a known date, the closure of the Strait of Hormuz on 28 February 2026, using
two frozen LightGBM models that forecast German day-ahead electricity prices. One model never sees
the oil price; the other is given the 30-day change in Brent. Each fortnight we compare the SHAP
feature ranking with a pre-shock reference using weighted Kendall's tau, and check whether it warns
before error (MAE) or input drift (PSI).

**In scope:** one market (Germany, DE-LU), one event, one model type, post-hoc explanations.
**Out of scope:** other shocks, other XAI methods, and explaining *why* prices moved. SHAP
explains the model, not the market.

## Deliverables

| | |
| --- | --- |
| Paper (latest version) | [`report/main.tex`](report/main.tex), one file per section in [`report/sections/`](report/sections/) |
| Journal | [`journal/`](journal/), indexed below |
| Presentation (12 Oct) | [`presentation/XAI_Presentation_Group8.pdf`](presentation/XAI_Presentation_Group8.pdf) |
| Results | [`results/summary.md`](results/summary.md), [`results/seasonal_check.md`](results/seasonal_check.md) |

## Journal index

Each entry records what was decided, why, what is still open, and who did what.

| Entry | What changed and why | Paper section |
| --- | --- | --- |
| [15 Sep](journal/2026-09-15.md) | Repo and journal set up before the topic, so the history starts on day one | — |
| [22 Sep](journal/2026-09-22.md) | Topic chosen. Rejected a chain-of-thought critique (we'd learn more building something), SHAP vs LIME on a dataset (too obvious) and a planted-bias test | Introduction |
| [24 Sep](journal/2026-09-24.md) | Ireland dropped for Germany: hourly data and clearer licensing | Methodology |
| [30 Sep](journal/2026-09-30.md) | Three domains cut to electricity only. Oil moved out of the main model, since a model that can't see the crisis fits the question better. Tau, PSI and the 2 SD rule fixed | Methodology |
| [5 Oct](journal/2026-10-05.md) | energy-charts went down, so we switched to SMARD. Added a seasonal tau and a two-windows-in-a-row check. First result: no early warning | Methodology, Results |
| [15 Oct](journal/2026-10-15.md) | October was doing two jobs, so early stopping got its own month. PSI flagged every window, so it now compares against the same fortnight a year earlier. Retrained, and tau now warned on 25 Apr | Methodology, Results |
| [19 Oct](journal/2026-10-19.md) | Paper split between us. Tracked which slide numbers the retrain changed. Each author's choices for their section | All sections |
| [23 Oct](journal/2026-10-23.md) | Cut to 4 pages. Cross-checked every number against `results/` and fixed three mismatches. Added Rudin (course reading) and Gama et al. What we learned | Related Work, Abstract, Conclusion |

## Where we ended up

Tau warned before error in both models (25 Apr 2026), but the seasonal check traced that warning
to spring solar, not the shock. The real change was in size rather than order: attribution to
yesterday's price roughly tripled, which a rank measure barely registers. Our conclusion is that
explanations are better monitored alongside error than in place of it. Full detail is in the paper.

## Who did what

| Person | Presentation | Paper |
| --- | --- | --- |
| Holly | Slides 1–5 | Introduction, Discussion |
| Tom | Slides 6–8 | Related Work, Drift Signals, figures |
| Conor | Slides 12–15 | Data and Model, Conclusion |
| Matthew | Slides 9–11 | Abstract, Drift Measurement |

Code authorship is in the commit history and each journal entry's *Who Did What*.

## Repo layout

| Path | Contents |
| --- | --- |
| `journal/` | Weekly entries, `YYYY-MM-DD.md` |
| `report/` | IEEE LaTeX paper (see `report/README.md` for the writing split) |
| `presentation/` | Slides, `.pptx` and `.pdf` |
| `src/` | One script per step: download, clean, features, train, analyse, plot |
| `results/`, `figures/` | Outputs the paper's numbers and figures come from |
| `tests/` | pytest checks |
| `prompts/` | Log of the AI prompts used to write the code |

To reproduce, run `pip install -r requirements.txt` (Python 3.13), then run the scripts in `src/`
in this order: `download_data`, `clean_data`, `build_features`, `train`, `analyse --real`,
`plot --real`, `check_seasonal`, `plot_paper`. Every date and threshold is in `src/config.py`.
Data comes from SMARD, Open-Meteo and FRED (licences are in `data/raw/manifest.json` after
download), and `data/` is never committed.

---
*README drafted with AI assistance.*

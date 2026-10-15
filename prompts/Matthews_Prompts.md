# Matthew's Prompts

AI prompts used by Matthew Burke (Claude chat) for the CS4437 XAI group project, in date order. Only substantial prompts are included (short follow-ups like "okay cool" are left out). Prompts are copied as written, typos included. Long pasted material is summarised in [square brackets]. Prompts given to Claude Code are marked as such.

*Prompts were typed by Matthew, but many follow group discussions. The final topic and scope were decided by the group; the prompts below explored options to bring to those meetings.*

*Compiled on 15 Oct 2026 from chat history; each prompt is dated by when it was originally sent.*

---

## 2026-09-16 to 18 — Topic selection
*Chat: "XAI topic selection and research project requirements"*

> We need to pick a topic for our group, can you give me examples of what it could be? And tell me what the assingments are asking from us. My understanding is that he wants us to pick an xai topic and then research papers on that topic and updtae our research journal with our findings and then in the end we write a report on our findings - am i worng on this? how many xai topics even are there with papers on them? or am i misinterpreting what he wants

> does this gice you any helpful context? theyre the slides from the lectures we have had
> [attached: lecture slides, weeks 1–2]

> okay just reading the first section of your response i am confiused on a few things:
> 1. what do you mean by the model is the explanation? like it doesnt give a plaintext reesponse you just get a result for example betwwen 0 and 1..?
> 2. when you say post hoc , post hoc what? running the model? wht are neural net and XGBoost, are these just 'models' and when you run a model you get result? my interprtation of some of these words is causing my confusion i believe.
> 3. SHAP and LIME, what actually are these? and are you sure we will cover them? (how do you know) Do they just give you a plaintext response for a model?
> Thats only the first section, lets answer these then you can expland on the rest of your response when i prompt you for it

> what is COMPAS recidivism, What is Rudins argument. - is this in the scope? clarify what you have verified from the brief on what we have to do, and hat you are unsure about

> hmm okay, this seems specifci tho and ore kind of our own thing rather than an already researched topic you know? I mean this is what the brief says about topic scope A specific XAI method, technique comparison, application domain, or critique — specific enough to go deep in 4 pages. [...]

> lowkirk building and testing sounds like we would lern more, and we oculd turn this project into something we coulf actually put on our CV and talk about rsther thn just reading a bunch of papers you know

> okay so whats the proposed title statement or wtv again? and then give me the plain english understanble version after, simplifying the words which i had to query you for clarity on in this chat

## 2026-09-22 — Landing on explanation drift + the 2026 oil shock
> i need a journal entry tho.. idk give me examples of datasets we coulkd do this with, tbh i think it sounds good enough

> i really liked the film the big short is there anyway we could make it kind opf fun and like 'would ai have predicted the financial crash'? typa vibe

> hmm, is this like actually realistic in something we can solve..? like are you saying back in 07 there models would give them a number answer, but we should see if the explanations start to make less sense coming up to the crash..?

> what about the recnet oil shortage due to the war in iran

> researcgh it and find out then

> hmm, what is the actual thesis though? i still dont understand that bit

> okay, can you verify the data is publically available for everything we would need and link me it please

---

## 2026-09-25 — Understanding the experiment
*Chat: "Model and testing explanation"*

> can you explain what the model actually does and what we arw actually testing

> okay give me a super short pitch / explanation of this

> okay so we train a model on two weeks of data, then feed it like week by week data of 2026 and see if the exeplkanations drift when the crisis happens.?

## 2026-09-29 — Reviewing scope after journal submission
> does all this sound good / work?
> [attached: submitted journal entry]

> that journal has already been submitted so all of this can be in the next journal, can you give me some bullet points of what i should address in said journal- i think yeah electricity probably main domain to be honest we could even drop the traffic one. hold out pre shock data yeah we can address that, look harder for daily gas , yeah we can look into tht and version iwthout oil i like that i think we drop traffic then maybe?

## 2026-09-30 — Settling the method
> on the still open stuff, can we add any of that now? I would like if the next part is just train the model or something... can you list all the data we are actually going to be using too

> okay so is all of this german yapplicable? and whats your soln to the yahoo issue?

> i mean look at the assingment descriptions for xAI, what do you think? is this standard for the type of paper we have to write? i forget the name but its some sort of international standard

> okay, do you think much needs to be done to narrow down the scope? are we doing too much for 4 pages? or is it okay

> okay this is what i have right now. what else do i need i havent added your new stuff:
> [pasted: draft journal entry, Discussed/Decided + Why]

> can you explain what day ahead horixon actually is, whats drift metric, why not raw oil price

> will oil have seen those types o fchanges since jan 2024 tho? all of that sounds pretty good tho

> before i write the why, just reding this its quite wordy.. maybe we should leave some of these decisions to later..? idk also 2 standard deviations is a lot i thought..?

## 2026-09-30 — Journal review
*Chat: "Journal review"*

> do you think this a good journal? are we slacking anywhere..?
> [attached: group journal entry]

---

## 2026-10-02 — LIME lab notebooks
*Chat: "Notebook learnings for project"*

> explain the key learnings from these notebooks in relation to my project. keep in my mind my knowledge of ML is very slim. explain like i know very little
> [attached: three LIME notebooks]

> so m i correct in saying that lime will adjust a feature randomly and see what the model predicts for it? and through this see hwo reliant a model is on each feature..?
## 2026-10-02 — Repo review, leakage fix, method doc, related work
*Chat: "GH connection issue"*

> I want to star making the model, can you read all the journals to understand the current state of the project? im going to get claude code to write it

> so is the problem here that the price of electricity on a given day is based on the forecast for wind / sun on that day.. ?

> cool. your suggestions for all of these seem pretty good i think we should go with all of them.

> okay now i also want to make an explanation of how the mdoel will work / the final decisions we made that we will be implementing - thigns like how the german market works are important , why germany? why shap? what is shap? what type of model is it? what libraries are we using? why? what are we looking for? what is our problem statement?

> can you explain what the best case scenario in our findings is and what the worst case scenario is? use actual graphs to help me visualise it. just struggling to wrap my head around the diff between error graph and explanation drift

> generate me a prompt i can give to claude code so it completes it

> I'll do that in a second. I was just advised that for our paper we should try to base it off another paper sort of. My lecturer was syaing how no idea is reallyyy original and that a sgood chunk of our project is probably based on some other papers which we should refer to and state where we took inspiration from, that sort of thing. I think we cited some papers in our recent journal, but i believe we need some more.. can you verify if we can use the ones alredy cited and maybe find any others similar to our problem statement?

---

## 2026-10-04 to 06 — Building the pipeline with Claude Code
*Chat: "Delegating work to CC"*

> This is an activity for class. Does it align with what I'm doing rn with project work at all,
> [attached: class activity brief]

> is that everything? going to send this to holly so she can write the journal entry based on what we did

---

## 2026-10-04 to 05 — Claude Code prompts (pipeline, SMARD switch, seasonal check, README)
*Tool: Claude Code, run in the group repo*

**Cleaning, features and training scripts**
```text
Read the attached requirements doc in full. You are now building:
src/clean_data.py, src/build_features.py and src/train.py, to requirements C1-C8, F1-F11 and M1-M8.
Follow "Rules for the coding agent", "Shared contract" and "Defaults for the open decisions" exactly.

Context:
- src/config.py, requirements.txt and src/download_data.py already exist (written by Conor). Use config.py as-is and never edit it.
  If anything you need is missing from it, stop and tell me.
- Read download_data.py first and build clean_data.py to load exactly the raw files and columns it writes (D8).
- Never edit analyse.py, plot.py or make_sample_features.py.
- The energy-charts API is currently returning HTTP 503, so data/raw/ is empty.
  Do not invent raw data files. Instead, write pytest tests in tests/ using small hand-built fixtures
  (a few days of fake rows created inside the test) to check C1 (15-min to hourly mean), C2 (23/25-hour clock-change days),
  C3 (no price filling, gap limit), C4 (no clipping), F2, F4 (gas cut-off), F6, F7 (Brent D-2 timing), F8, F9 and M8.
- One small change to download_data.py: in _get, retry HTTP 502, 503 and 504 a few times with backoff, the same way 429 is handled.
  Change nothing else in that file.

Plan first: tell me how you'll handle the 15-min switch, the clock-change days, the gas lag and the Brent timing, then wait for my go-ahead.

Order: clean_data.py, then build_features.py, then train.py. After each, run its tests and report pass or fail by requirement ID.
Do not commit; I will.
```

**Switching the electricity data source to SMARD**
```text
energy-charts.info has returned HTTP 503 for over a day. Switch the electricity series in src/download_data.py to SMARD (smard.de, Bundesnetzagentur), keeping Open-Meteo (temperature) and FRED (Brent) as they are.

Series needed, all for Germany / DE-LU: day-ahead price, day-ahead load forecast, wind onshore and wind offshore day-ahead forecasts, solar day-ahead forecast, actual fossil gas generation.

Rules:
- Keep the raw file names and columns that clean_data.py already reads, so cleaning and everything after need no changes. If that's impossible for a series, tell me exactly what changes in clean_data.py.
- Find the correct SMARD filter IDs from SMARD's documentation, not from memory; show me the ID for each series and where you found it before downloading.
- Keep the existing behaviour: data from 2023-12-01, chunking, retries, fail loudly, cache, per-series summary, manifest (update source URL and licence: SMARD data is CC BY 4.0).
- Plan first and wait for my go-ahead. Don't commit.
```

**First real run**
```text
Accept the 20 Jan start. Run train.py and show me the Oct 2025 MAE for blind, oil and naive. If both beat naive, run analyse.py --real and plot.py --real and show me the summary.
```

**Seasonal check**
```text
I want to check whether seasonality explains the tau dip after the shock. Using the existing tau_seasonal column (A15), for both models:

1. Compute baseline mean and SD for tau_seasonal from the 8 baseline windows (same method as tau), plus z-scores with the sign flipped, and a 2 SD warning flag. Add these as new columns; don't change the existing tau columns or results.
2. Report first-crossing date and lead time vs MAE for tau_seasonal, single-window and two-in-a-row.
3. Make one extra figure per model: tau z-score and tau_seasonal z-score on the same axes, with MAE z-score, the 2 SD line and the shock date. Save as figures/drift_*_seasonal.png.
4. Tell me in plain English: does the March-April dip disappear with tau_seasonal, and does tau_seasonal warn before MAE?

Keep the original results as the main result; this is an additional check. Don't commit.
```

**Plot, summary and overfitting fixes**
```text
Keep src/check_seasonal.py as a separate script, and don't change any results except where listed below.

1. plot.py: fix the duplicate "Input drift (mean PSI)" legend entry. Use hollow markers in the legend, since filled means "over the warning line".
2. plot.py: shorten the main plot's y-axis label to "SDs from baseline (up = more drift)". In the raw-units plot, zoom the tau panel to about 0.5–1.
3. analyse.py (O3): add the outcome label to summary.md for each model. If the method doc's four-outcome table isn't in the repo, use these four: explanation drift warned first / error warned first / both in the same window / neither crossed. Base it on both the single-window and two-in-a-row results, and say which one the label uses.
4. train.py: also report training MAE for both models next to the validation MAE in validation.json, so we can check for overfitting.

Then rerun train.py, analyse.py --real and plot.py --real, run pytest, and show me the new summary.md and the train vs validation MAE. Don't commit.
```

**README update**
```text
Update README.md in the repo root to match the project as it is now. Read the current README, src/config.py, the scripts in src/, requirements.txt and results/ first.

It should cover, briefly:
- The research question in one or two sentences, and the group members (Matthew Burke, Holly Best, Tom Byrne, Conor Clancy)
- The method in plain English: LightGBM price model, blind vs oil versions, fortnightly SHAP + weighted Kendall's tau, MAE, PSI, 2 SD warnings from the Nov 2025–Feb 2026 baseline, shock date 28 Feb 2026
- Repo layout (src, tests, results, figures, journal, report, prompts); note data/
```

**Blind-model input range check**
```text
Add a check for whether the blind model's inputs went outside their training range after the oil shock, the same idea as the existing oil-range check (results/oil_range.json, F10 in the README).

Write src/check_input_range.py, following the repo's conventions: read data/processed/features.parquet, take all dates, windows and column names from src/config.py, and hard-code nothing.

For each feature in the blind model:
- the min and max over the training window (Jan 2024 – Sep 2025)
- the min and max over the test period (28 Feb 2026 onward)
- the % of test rows below the training min, and the % above the training max
- the same % per fortnightly test window (matching the windows analyse.py uses), so we can see whether any out-of-range spell lines up with the 20 Jun MAE crossing

Skip pure calendar features (hour, weekday, month, is_holiday), since they can't go out of range.

Write the results to results/input_range.json and a short results/input_range.md: one table per feature, sorted by % of test rows out of range, plus a one-paragraph plain-English summary. Pay particular attention to the top SHAP features: wind_forecast, price_lag_1d, solar_forecast, demand_forecast, price_lag_7d.

Don't change any existing results or scripts. Run it, then tell me: did any blind-model input go meaningfully beyond its training range, and if so, when?
```

---

## 2026-10-07 — Sources document
*Chat: "Source summaries for presentation"*

> okay, i want to make a mark down file which foes throug all the sources listed in all of the journals , specifically the good / proper ones so that we can refer to them in our presentation / final report. I want 1-2 short sentecnes on each good source so we csn understand it, defend it and explain what its about. see my prompt to holly here:
> [pasted: my earlier message to Holly asking for Related Work summaries of Trebbien et al. 2023, Lundberg et al. 2020, Mougan et al. 2025 and Demšar & Bosnić 2018, with a What they did / How it relates / Where it goes format]

## 2026-10-07 to 09 — Slides and live demo
> does this mean we can submit any file type..? cus lowkey html might work best..?
> [pasted: Assignment 02 brief and rubric from Brightspace]

> i think we should note that we must assume the people we are presenting too have swe knowledge but not ML, like that conecpt there is kind of hard for me to wrap my head around, maybe something interactive could be used to explain it well? like a very simple graph with error rate and weighted tau and then we can click values on / off type of vibe? idk think of a way we could make that work, or even like a toggleable on off for different features and we can see how ranking is affected..

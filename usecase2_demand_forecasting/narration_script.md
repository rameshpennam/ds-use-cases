# Narration Script — Demand Forecasting & Staffing
Full talk track for presenting this walkthrough. Deliberately starts at the
use-case introduction — **your own personal/role introduction is not
included here**; do that yourself in your own words at the very start.

Read this as a guide, not a strict script to recite word-for-word —
paraphrase naturally. The numbers below are the actual output of the fixed
random seed in `01_generate_synthetic_data.py` as shipped, so your screen
should show these exact figures if you haven't changed the config.

Target length: 25-35 minutes of this content, stretching to 35-45 minutes
with good pacing (hover-before-click, narrating what/why, ~1 second pause
after each click) and the live Power BI build at the end.

---

## 1. Use case and objective

*[VS Code open to this folder, nothing else running.]*

"Today's use case is demand forecasting for customer care staffing. The
business question is: based on our contact-volume history, how many agents
do we actually need over the next several weeks, and does our current
roster cover that need or fall short?

This matters because both over- and under-staffing are expensive — overstaff
and you're paying for idle capacity; understaff and service levels and CSAT
both suffer. My objective is to build a forecast of daily contact volume
grounded in the real patterns in the data — trend, weekly seasonality,
seasonal spikes, holidays, campaigns — validate that forecast honestly
against a held-out period, and then convert it into a concrete staffing
number the business can act on: how many FTEs do we need, and where's the
gap against what we have today."

## 2. Input data

*[Open `input/input_call_volume_history.xlsx` and
`input/input_agent_roster.xlsx`.]*

"I have two inputs here. The first is daily contact-volume history — 3
years of it, across four lines of business — broken out by line of
business and channel, with average
handle time per channel and flags for holidays and marketing campaigns. The
second is the agent roster: who we have today, which line of business they
support, their team lead and manager, tenure, how many hours a week they're
actually available, and a real call-center metric — shrinkage percentage:
how much of a scheduled shift is lost to breaks, training and coaching. I
kept both to a minimal column set — just what's needed to forecast volume
and translate it into a staffing comparison."

## 3. Applications I'll use

"Two applications for this one: VS Code with Python for the forecasting
model, and Power BI for the staffing-gap story at the end — the right scope
for deeply technical modeling work."

## 4. What the final output looks like

"The output is one Excel workbook, `final_output_forecast_staffing.xlsx`,
with the date-level forecast and staffing numbers on one sheet, and a
single Analysis sheet where every summary table — model accuracy, weekly
rollup, monthly rollup — sits right beside its own chart. I'll also
generate a short client-ready PowerPoint deck summarizing the use case and
findings."

## 5. Main task — walking through the code

*[Open `02_demand_forecasting.py`. Run each `# %%` cell with Shift+Enter.]*

### Cell 0 — setup
"I'm bringing in pandas and numpy for the data work, matplotlib for quick
exploratory charts, two pieces from statsmodels — `seasonal_decompose` to
inspect the series, and `ExponentialSmoothing` for the actual forecasting
model — and a MAPE metric from scikit-learn. I'm also setting a few
assumptions up front: a 60-day holdout to validate the model honestly, a
42-day forward forecast, and an 8-hour working day."

### Cell 1 — load the data, and ground the occupancy assumption in real data
"Loading both files — in this run that's just over 13,000 rows of volume
history, across four lines of business, and 40 agents on the roster.
Instead of assuming a flat occupancy figure, I compute it from the
roster's REAL average shrinkage — in this run that's about 19.5 percent,
so a 79-ish percent occupancy target, not a textbook constant. That
matters because shrinkage is a genuine, measurable roster attribute —
newer agents typically run higher shrinkage from training and coaching —
so this ties the staffing math to who's actually on the floor."

### Cell 2 — building the series to forecast
"I'm collapsing this down to total daily contact volume across every line
of business and channel combined, so I have a single clean series to
forecast for this walkthrough — a full production rollout would repeat this
per line of business. I also compute the blended average handle time across
channels, weighted by volume — around 348 seconds, just under six minutes."

### Cell 3 — exploring the data before modeling anything
"Before I trust any model, I look at the shape of the data first. Here's
the full time series — a slow upward trend and a clear repeating weekly
pattern. The decomposition breaks that into trend, weekly seasonality, and
residual noise explicitly. Sunday is consistently the lowest day, about
15-20 percent below the weekday average."

### Cell 4 — train/holdout split
"I'm holding out the most recent 60 days as a test set the model never sees
during training — a forecast I haven't validated against real held-out data
is just a guess with extra steps."

### Cell 5 — the baseline
"Before reaching for anything sophisticated, I benchmark against the
simplest possible forecast: repeat last week's seven values forward. In
this run, that naive baseline achieves a MAPE of about 17.2 percent on the
holdout. That's my bar to beat."

### Cell 6 — Holt-Winters
"I fit a Holt-Winters model, which explicitly models trend and weekly
seasonality rather than just repeating the last cycle. On the same holdout
it comes in at 15.1 percent MAPE versus 17.2 for the baseline — a real,
honest 2.1-point improvement. I'm upfront about that margin: it's modest,
and that's a realistic outcome on data this regular — I'd rather report a
real small win than overstate it. I've also put an explicit check in the
script: if Holt-Winters ever loses to the baseline, the script stops and
tells me to ship the simpler baseline instead. A model only earns the extra
complexity if it actually wins. This comparison is saved as the task's
intermediate artifact."

### Cell 7 — forecasting forward
"With the model validated, I refit it on the full history and forecast the
next 42 days — six weeks — forward, continuing the same weekly pattern
including the Sunday dip into November and early December."

### Cell 8 — converting volume into staffing
"I convert the volume forecast into required agent-hours using the blended
handle time, then into required FTEs using the shrinkage-derived occupancy
figure from Cell 1, and compare that against what the roster can actually
deliver. In this run, required FTE averages about **25.5** over the
forecast horizon, against roughly **24.5** available — and on **36 of the
next 42 days**, we're running short, by up to **2.3 FTE** on the worst day,
October 29th. That's a real, actionable gap — tight enough to need a plan,
not a crisis."

### Cell 9 — saving the output
"One Excel workbook, rebuilt from scratch every run: the date-level
forecast and staffing numbers on one sheet, and a single Analysis sheet
where each summary table — model accuracy, weekly rollup, monthly rollup —
sits right beside its own chart, with data labels switched on. The weekly
and monthly rollups each pair forecast volume (bars) with the staffing gap
in FTE (a line on a secondary axis), so you can see both how much volume
is coming and how short-staffed it leaves the floor, in the same picture."

### Cell 10 — the numbers I'll quote
"To summarize: Holt-Winters improves forecast accuracy from 17.2 to 15.1
percent MAPE versus the naive baseline. Average required staffing over the
next six weeks is about 25.5 FTE, against roughly 24.5 available today, and
we're short-staffed on 36 of the next 42 days, peaking at a shortfall of
2.3 FTE on October 29th."

## 6. Output file walkthrough

*[Switch to Excel. Open `final_output/final_output_forecast_staffing.xlsx`.]*

"Forecast_Staffing has the full date-level detail. Analysis has the model
accuracy comparison, the weekly rollup, and the monthly rollup, each one
sitting right beside the chart I just described for it."

## 7. The PowerPoint summary

*[Run `03_generate_summary_ppt.py`, then open
`final_output/usecase2_forecast_summary.pptx`.]*

"Same as the other use case — a short, six-slide client-ready deck, every
number pulled straight from the real output files."

## 8. Insights in Power BI

*[Switch to Power BI Desktop. Follow `powerbi_build_guide.md`.]*

"Now I'll bring this into Power BI for the staffing narrative."

*[Build the visuals per the guide, narrating each field as you add it.]*

"Pulling this together for the business: our forecast shows contact volume
holding roughly steady with the usual weekly rhythm over the next six
weeks, but our current roster is running about 2.3 FTE short on the worst
day. That's a small, fixable gap — a modest overtime allocation or a couple
of flexible-shift agents would close it — but worth flagging now, with six
weeks of lead time, rather than discovering it the week service levels
slip."

## 9. Close

"That's the end-to-end workflow — from raw daily contact-volume history and
a real roster shrinkage figure, to an honestly-validated forecast that
beats a naive baseline, to a concrete, actionable staffing gap and a
client-ready deck, all using classical statistical forecasting with no
dependency on an LLM API."

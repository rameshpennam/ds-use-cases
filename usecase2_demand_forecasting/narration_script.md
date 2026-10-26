# Narration Script — Demand Forecasting & Staffing
Full talk track for the recording. Deliberately starts at the use-case
introduction — **your own personal/role introduction is not included here**;
do that yourself in your own words at the very start of the recording.

Read this as a guide, not a strict script to recite word-for-word —
paraphrase naturally. The numbers below (MAPE, FTE figures, gap days) are
the actual output of the fixed random seed in `01_generate_synthetic_data.py`
as shipped, so your screen should show these exact figures if you haven't
changed the config.

Target length: 25-35 minutes of this content, stretching to 35-45 minutes
with required pacing (hover-before-click, narrating what/why, ~1 second
pause after each click) and the live Power BI build at the end.

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

"I have two inputs here. The first is daily contact-volume history —
roughly 3.8 years of it — broken out by line of business and channel, with
the average handle time per channel and flags for holidays and marketing
campaigns. The second is the agent roster: who we have today, which line of
business they support, their team lead and manager, tenure, and how many
hours a week they're actually available. I kept both to a minimal column
set — just what's needed to forecast volume and translate it into a
staffing comparison, nothing decorative."

## 3. Applications I'll use

"Two applications for this one: VS Code with Python for the forecasting
model itself, and Power BI for the staffing-gap story at the end. This is
deeply technical modeling work, so I'm not padding the workflow with extra
tools — these two do the job."

## 4. What the final output looks like

"The output is one Excel workbook, `final_output_forecast_staffing.xlsx`,
with a date-level forecast-and-staffing sheet and an Insights sheet with a
weekly rollup and two charts, which is what feeds the Power BI story."

## 5. Main task — walking through the code

*[Open `02_demand_forecasting.py`. Run each `# %%` cell with Shift+Enter.]*

### Cell 0 — setup
"I'm bringing in pandas and numpy for the data work, matplotlib for quick
exploratory charts, two pieces from statsmodels — `seasonal_decompose` to
inspect the series, and `ExponentialSmoothing` for the actual forecasting
model — and a MAPE metric from scikit-learn to score accuracy. I'm also
setting a few assumptions up front: a 60-day holdout to validate the model
honestly, a 42-day forward forecast — that's six weeks — an 8-hour working
day, and an 85 percent occupancy target, meaning agents are only
productively handling contacts about 85 percent of a shift once you account
for breaks and admin work."

### Cell 1 — load the data
"Loading both files — in this run that's just over 8,000 rows of volume
history and 40 agents on the roster."

### Cell 2 — building the series to forecast
"I'm collapsing this down to total daily contact volume across every line
of business and channel combined, so I have a single clean series to
forecast for this walkthrough — a full production rollout would repeat this
per line of business, and the output file still keeps that breakdown
available for Power BI even though the model itself works at the total
level. I also compute the blended average handle time across channels,
weighted by volume — that comes out to around 348 seconds, just under six
minutes — which I'll need later to convert volume into required hours."

### Cell 3 — exploring the data before modeling anything
"Before I trust any model, I always look at the shape of the data first.
Here's the full time series plotted — you can see the slow upward trend and
a clear repeating weekly pattern. The decomposition breaks that into trend,
weekly seasonality, and residual noise explicitly. And if I average volume
by day of week, Sunday is consistently the lowest — about 15-20 percent
below the weekday average — exactly what you'd expect for a consumer
contact center."

### Cell 4 — train/holdout split
"I'm holding out the most recent 60 days as a test set the model never sees
during training. This is non-negotiable — a forecast I haven't validated
against real held-out data is just a guess with extra steps."

### Cell 5 — the baseline
"Before I reach for anything sophisticated, I benchmark against the
simplest possible forecast: 'next week looks like this week' — literally
repeating last week's seven values forward. In this run, that naive
baseline achieves a MAPE — mean absolute percentage error — of about 20
percent on the holdout. That's my bar to beat. If a fancier model can't beat
this, the fancier model doesn't belong in production."

### Cell 6 — Holt-Winters
"Now I fit a Holt-Winters model — technically triple exponential smoothing —
which explicitly models trend and weekly seasonality rather than just
repeating the last cycle. It's a lightweight, well-understood model, easy to
explain to the business, unlike a black-box approach. On the same holdout,
it comes in at roughly 18.8 percent MAPE, versus 20.1 for the baseline — a
real, if modest, improvement. I want to be straightforward about that
margin: it's not a dramatic win, and that's an honest, realistic outcome —
on data this regular, a simple baseline is already hard to beat by much, and
I'd rather report a real 1-to-2-point improvement than overstate it. I've
also put an explicit check in the script: if Holt-Winters ever loses to the
baseline — say, on a noisier dataset — the script stops and tells me to ship
the simpler baseline instead. A model only earns the extra complexity if it
actually wins; I'm not going to deploy something fancier just because it's
fancier. I save this comparison as the task's intermediate artifact, so
there's a clear record of the model-selection decision, not just a forecast
that appears with no accuracy justification behind it."

### Cell 7 — forecasting forward
"With the model validated, I refit it on the full history — not just the
training slice — and forecast the next 42 days, six weeks, forward. You can
see the weekly pattern continuing, including that Sunday dip, projected
into November and early December."

### Cell 8 — converting volume into staffing
"A volume forecast by itself doesn't tell the business what to do. I
convert it into required agent-hours using the blended handle time —
volume times average handle time, divided by 3,600 to get hours — then into
required FTEs by dividing by an 8-hour day at 85 percent occupancy. I
compare that against what the current roster can actually deliver — total
weekly available hours divided by seven days, divided by eight hours. In
this run, required FTE averages about 25-26 over the forecast horizon,
against roughly 25 available — and on **30 of the next 42 days**, we're
running short, by up to about 1.6 FTE on the worst day. That's not a crisis,
but it's a real, actionable gap — tight enough that a single bad week or an
unplanned absence would push us into a visible service-level problem."

### Cell 9 — saving the output
"Same pattern as before — one Excel workbook, rebuilt from scratch every
time I run this: the date-level forecast and staffing numbers on one sheet,
a weekly rollup with two charts — required versus available FTE, and the
staffing gap itself — on the Insights sheet."

### Cell 10 — the numbers I'll quote
"To summarize: Holt-Winters improves forecast accuracy from about 20.1
percent to 18.8 percent MAPE versus the naive baseline. Average required
staffing over the next six weeks is about 25-26 FTE, against roughly 25
available today, and we're short-staffed on 30 of the next 42 days, peaking
at a shortfall of about 1.6 FTE."

## 6. Output file walkthrough

*[Switch to Excel. Open `final_output/final_output_forecast_staffing.xlsx`.]*

"The Forecast_Staffing sheet has the full date-level detail — forecast
volume, required FTE, available FTE, and the gap, for every day of the
six-week horizon. The Insights sheet rolls that up by week, with the two
charts I just described already built in."

## 7. Insights in Power BI

*[Switch to Power BI Desktop. Follow `powerbi_build_guide.md`.]*

"Now I'll bring this into Power BI for the staffing narrative. I'm loading
the Insights sheet, and building visuals that show required-versus-available
FTE over time, the weekly gap, and a clear callout on the worst week."

*[Build the visuals per the guide, narrating each field as you add it.]*

"Pulling this together for the business: our forecast shows contact volume
holding roughly steady with the usual weekly rhythm over the next six weeks,
no major spike expected, but our current roster is running about 1 to 1.6
FTE short on most days. That's a small, fixable gap — a modest overtime
allocation or a couple of flexible-shift agents would close it — but it's
worth flagging now, with six weeks of lead time, rather than discovering it
the week service levels slip."

## 8. Close

"That's the end-to-end workflow — from raw daily contact-volume history, to
an honestly-validated forecast that beats a naive baseline, to a concrete,
actionable staffing gap the business can plan against, all using classical
statistical forecasting with no dependency on an LLM API."

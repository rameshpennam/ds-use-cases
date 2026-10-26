"""
02_demand_forecasting.py
--------------------------
Main walkthrough script for the Volume Forecasting & Staffing use case.

HOW TO RUN (VS Code):
  1. Open this file in VS Code with the Python extension installed.
  2. Each block starting with "# %%" is a runnable cell - hover above it and
     click "Run Cell" (or press Shift+Enter) to execute just that block and
     see its output (and any chart) in the interactive window.
  3. Run the cells top to bottom in order. Comments starting with "NARRATE:"
     are talk-track cues for the recording - say that, then run the cell.

INPUTS : input/input_call_volume_history.xlsx, input/input_agent_roster.xlsx
OUTPUT : final_output/final_output_forecast_staffing.xlsx
         - sheet "Forecast_Staffing" : date-level forecast + FTE gap
         - sheet "Insights"          : weekly rollup table + charts
         NOTE: same caveat as the other use case - a native Excel
         "PivotTable" object can't be created from a script in a way that
         works on macOS Excel (that needs Windows-only COM automation), so
         this workbook ships pre-aggregated tables + real embedded charts
         instead, fully rebuilt every time you run this script.
"""

# %% Cell 0 - Imports & config
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_percentage_error
from openpyxl.chart import LineChart, BarChart, Reference
import openpyxl

VOLUME_FILE = "input/input_call_volume_history.xlsx"
ROSTER_FILE = "input/input_agent_roster.xlsx"
INTERMEDIATE_FILE = "intermediate/intermediate_model_accuracy_comparison.xlsx"
OUTPUT_FILE = "final_output/final_output_forecast_staffing.xlsx"

os.makedirs("intermediate", exist_ok=True)
os.makedirs("final_output", exist_ok=True)

HOLDOUT_DAYS = 60          # most recent 60 days used to test model accuracy
FORECAST_HORIZON = 42      # forecast the next 6 weeks forward
DAILY_WORKING_HOURS = 8
OCCUPANCY_TARGET = 0.85    # agents are only "productive" ~85% of a shift (breaks, admin, etc.)

# %% Cell 1 - Load data
# NARRATE: "This is 3-plus years of daily contact volume by LoB and channel,
# plus the agent roster, so I can compare forecasted need against who we
# actually have available."
vol = pd.read_excel(VOLUME_FILE, sheet_name="Call_Volume_History")
vol["date"] = pd.to_datetime(vol["date"])
roster = pd.read_excel(ROSTER_FILE, sheet_name="Agent_Roster")
print(vol.shape, roster.shape)
vol.head()

# %% Cell 2 - Build the series we'll forecast: total daily volume (all LoB/channel)
# NARRATE: "For this walkthrough I forecast total daily contact volume end to
# end - a full production rollout would repeat this per LoB/channel. The
# output file still keeps the LoB/channel breakdown so that split can be
# sliced in Power BI even though the model itself is at the total level."
daily = vol.groupby("date")["volume"].sum().asfreq("D").ffill()
avg_aht = (vol["volume"] * vol["aht_seconds"]).sum() / vol["volume"].sum()
print(f"Blended avg handle time across channels: {avg_aht:.0f} seconds")

# %% Cell 3 - EDA: trend + weekly/yearly seasonality
# NARRATE: "Before modeling anything, I always look at the shape of the data -
# here you can see the weekly dip on Sundays and the festive-season bump."
fig, ax = plt.subplots(figsize=(11, 4))
daily.plot(ax=ax, title="Total daily contact volume")
plt.tight_layout()
plt.show()

decomposition = seasonal_decompose(daily, model="additive", period=7)
decomposition.plot()
plt.tight_layout()
plt.show()

print("Average volume by day of week (0=Mon ... 6=Sun):")
print(daily.groupby(daily.index.day_of_week).mean().round(0))

# %% Cell 4 - Train / holdout split
train = daily.iloc[:-HOLDOUT_DAYS]
test = daily.iloc[-HOLDOUT_DAYS:]
print(f"Train: {train.index.min().date()} -> {train.index.max().date()} ({len(train)} days)")
print(f"Test : {test.index.min().date()} -> {test.index.max().date()} ({len(test)} days)")

# %% Cell 5 - Baseline: naive seasonal forecast (same weekday, previous week)
# NARRATE: "Before trusting any model, I always benchmark it against the
# simplest possible forecast - 'next week looks like this week'."
naive_forecast = train.iloc[-7:].values
naive_forecast = np.tile(naive_forecast, int(np.ceil(len(test) / 7)))[: len(test)]
baseline_mape = mean_absolute_percentage_error(test.values, naive_forecast) * 100
print(f"Baseline (naive seasonal) MAPE: {baseline_mape:.1f}%")

# %% Cell 6 - Holt-Winters (triple exponential smoothing) model
# NARRATE: "Holt-Winters models trend and weekly seasonality explicitly - a
# lightweight, well-understood model that's easy to explain to the business,
# unlike a black-box approach."
hw_model = ExponentialSmoothing(
    train, trend="add", seasonal="add", seasonal_periods=7
).fit()

hw_test_forecast = hw_model.forecast(len(test))
hw_mape = mean_absolute_percentage_error(test.values, hw_test_forecast.values) * 100
print(f"Holt-Winters MAPE on holdout: {hw_mape:.1f}%  (baseline was {baseline_mape:.1f}%)")

fig, ax = plt.subplots(figsize=(11, 4))
test.plot(ax=ax, label="Actual")
hw_test_forecast.plot(ax=ax, label="Holt-Winters forecast")
plt.legend()
plt.title("Holdout: actual vs forecast")
plt.tight_layout()
plt.show()

# Saved as the task's INTERMEDIATE artifact - the model-selection evidence
# between raw input and the final forecast/staffing output.
# NARRATE: "I always benchmark a candidate model against the naive baseline
# before shipping it - here Holt-Winters genuinely beats the baseline, so I
# carry it forward. If it hadn't, the right call would be to ship the
# simpler baseline instead - a model only earns its complexity if it wins."
model_comparison = pd.DataFrame({
    "model": ["Naive seasonal (baseline)", "Holt-Winters"],
    "holdout_mape_pct": [round(baseline_mape, 1), round(hw_mape, 1)],
})
model_comparison.to_excel(INTERMEDIATE_FILE, index=False, sheet_name="Model_Comparison")
print(f"Saved intermediate artifact -> {INTERMEDIATE_FILE}")
assert hw_mape < baseline_mape, "Holt-Winters did not beat baseline - ship the naive baseline instead, don't force this model."

# %% Cell 7 - Refit on all history, forecast forward
final_model = ExponentialSmoothing(
    daily, trend="add", seasonal="add", seasonal_periods=7
).fit()
future_index = pd.date_range(daily.index.max() + pd.Timedelta(days=1), periods=FORECAST_HORIZON, freq="D")
future_forecast = final_model.forecast(FORECAST_HORIZON)
future_forecast.index = future_index
print(future_forecast.round(0))

# %% Cell 8 - Convert forecast volume -> required staffing (FTE)
# NARRATE: "Volume alone doesn't tell the business what to do - I convert it
# into agent-hours using handle time, then into FTEs using an occupancy
# assumption, and compare that against what the roster can actually deliver."
required_hours = future_forecast * avg_aht / 3600
required_fte = required_hours / (DAILY_WORKING_HOURS * OCCUPANCY_TARGET)

available_fte_per_day = roster["weekly_available_hours"].sum() / 7 / DAILY_WORKING_HOURS

staffing = pd.DataFrame({
    "date": future_index,
    "forecast_volume": future_forecast.values.round(0),
    "required_fte": required_fte.values.round(1),
    "available_fte": round(available_fte_per_day, 1),
})
staffing["staffing_gap_fte"] = (staffing["required_fte"] - staffing["available_fte"]).round(1)
staffing.head(10)

# %% Cell 9 - Save output: ONE workbook, rebuilt from scratch every run
# NARRATE: "Same idea as the other use case - one Excel workbook, the
# date-level forecast on one sheet, a weekly rollup with charts on another,
# both regenerated every time I rerun the script."
staffing_weekly = (
    staffing.assign(week_starting=staffing["date"].dt.to_period("W").apply(lambda p: p.start_time))
    .groupby("week_starting")[["forecast_volume", "required_fte", "available_fte", "staffing_gap_fte"]]
    .mean()
    .round(1)
    .reset_index()
)
staffing_weekly["week_starting"] = staffing_weekly["week_starting"].dt.strftime("%Y-%m-%d")

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    staffing.to_excel(writer, sheet_name="Forecast_Staffing", index=False)
    staffing_weekly.to_excel(writer, sheet_name="Insights", index=False)

wb = openpyxl.load_workbook(OUTPUT_FILE)
ws = wb["Insights"]

chart1 = LineChart()
chart1.title = "Required vs Available FTE (weekly avg)"
chart1.y_axis.title = "FTE"
data1 = Reference(ws, min_col=3, max_col=4, min_row=1, max_row=ws.max_row)  # required_fte, available_fte
cats1 = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
chart1.add_data(data1, titles_from_data=True)
chart1.set_categories(cats1)
ws.add_chart(chart1, "G2")

chart2 = BarChart()
chart2.title = "Staffing Gap (weekly avg FTE, positive = short-staffed)"
chart2.y_axis.title = "Gap (FTE)"
data2 = Reference(ws, min_col=5, max_col=5, min_row=1, max_row=ws.max_row)  # staffing_gap_fte
chart2.add_data(data2, titles_from_data=True)
chart2.set_categories(cats1)
ws.add_chart(chart2, "G18")

wb.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} (2 sheets, 2 charts)")

# %% Cell 10 - Spoken walkthrough numbers (read these out on camera)
worst_day = staffing.loc[staffing["staffing_gap_fte"].idxmax()]
days_short = (staffing["staffing_gap_fte"] > 0).sum()
print(f"Model improved MAPE from {baseline_mape:.1f}% (baseline) to {hw_mape:.1f}% (Holt-Winters)")
print(f"Avg required FTE over next {FORECAST_HORIZON} days: {staffing['required_fte'].mean():.1f}")
print(f"Available FTE (current roster): {available_fte_per_day:.1f}")
print(f"Days short-staffed over the horizon: {days_short} of {FORECAST_HORIZON}")
if worst_day["staffing_gap_fte"] > 0:
    print(f"Biggest gap day: {worst_day['date'].date()} short by {worst_day['staffing_gap_fte']:.1f} FTE")
else:
    print(f"No day is short-staffed; best-staffed cushion is {-worst_day['staffing_gap_fte']:.1f} FTE "
          f"on {worst_day['date'].date()} worth checking for over-staffing instead.")

# %% Cell 11 [OPTIONAL - DO NOT RUN] - LLM-assisted narrative insight generation
# ----------------------------------------------------------------------------
# NOT APPROVED YET - same status as in the other use case. In production we
# might use an LLM API to auto-draft the staffing-gap narrative/email from the
# output table, but no API has been confirmed/provided for this engagement,
# so this stays disabled.
# USE_LLM_API = False

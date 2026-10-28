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
         - sheet "Forecast_Staffing" : date-level forecast + FTE gap, row-level
         - sheet "Analysis"          : every summary table (model accuracy,
                                        weekly rollup, monthly rollup), each
                                        with its chart placed right beside it,
                                        bold headers, wide columns, data
                                        labels on every chart
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
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
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

# %% Cell 1 - Load data
# NARRATE: "This is 3-plus years of daily contact volume by LoB and channel,
# plus the agent roster, so I can compare forecasted need against who we
# actually have available."
vol = pd.read_excel(VOLUME_FILE, sheet_name="Call_Volume_History", keep_default_na=False)
vol["date"] = pd.to_datetime(vol["date"])
roster = pd.read_excel(ROSTER_FILE, sheet_name="Agent_Roster", keep_default_na=False)
print(vol.shape, roster.shape)
vol.head()

# WHAT: occupancy target derived from the roster's REAL average shrinkage
# (time scheduled but not available - breaks, training, coaching), not a
# flat assumed constant. WHY: shrinkage is a genuine, measurable roster
# attribute (newer agents run higher shrinkage from training/coaching) -
# using the actual figure makes the required-FTE math reflect who's really
# on the floor, not a textbook assumption.
avg_shrinkage_pct = roster["shrinkage_pct"].mean()
OCCUPANCY_TARGET = 1 - (avg_shrinkage_pct / 100)
print(f"Avg roster shrinkage: {avg_shrinkage_pct:.1f}%  ->  occupancy target: {OCCUPANCY_TARGET:.2f}")

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

# %% Cell 9 - Save outputs: ONE workbook, rebuilt from scratch every run
# NARRATE: "Same idea as the other use case - one Excel workbook: the raw
# date-level forecast on one sheet, and every summary table (model accuracy,
# weekly rollup, monthly rollup) together on a single 'Analysis' sheet with
# its chart placed right beside it - so the numbers and the picture read
# together without flipping tabs. Bold headers, wide columns, data labels on
# every chart - fully reproducible every time I rerun the script."
def rollup(freq_period: str) -> pd.DataFrame:
    out = (
        staffing.assign(period=staffing["date"].dt.to_period(freq_period).apply(lambda p: p.start_time))
        .groupby("period")[["forecast_volume", "required_fte", "available_fte", "staffing_gap_fte"]]
        .mean()
        .round(1)
        .reset_index()
    )
    out["period"] = pd.to_datetime(out["period"]).dt.date
    return out


staffing_weekly = rollup("W")
staffing_monthly = rollup("M")

staffing_out = staffing.copy()
staffing_out["date"] = pd.to_datetime(staffing_out["date"]).dt.date  # real Excel date, not text

# chart_kind: "bar" = single-metric bar (Model Accuracy, 1 metric column);
# "combo" = bar (volume) + line on a secondary axis (the operational metric
# that volume is driving) - same "how often, how bad" pairing as use case 1.
SECTIONS = [
    ("Model Accuracy Comparison (Holdout MAPE %)", model_comparison, "bar"),
    ("Weekly Rollup - Volume vs Staffing Gap", staffing_weekly, "combo"),
    ("Monthly Rollup - Volume vs Staffing Gap", staffing_monthly, "combo"),
]

HEADER_FILL = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=13, color="1B2A4A")
MIN_SECTION_ROWS = 14  # reserve enough rows beside a short table for the 6.5cm-tall chart next to it

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    staffing_out.to_excel(writer, sheet_name="Forecast_Staffing", index=False)
    cursor = 0
    section_positions = []  # (title, table, chart_kind, title_row, header_row, first_data_row, last_data_row)
    for title, table, chart_kind in SECTIONS:
        table.to_excel(writer, sheet_name="Analysis", index=False, startrow=cursor + 1, startcol=0)
        title_row = cursor + 1
        header_row = cursor + 2
        first_data_row = cursor + 3
        last_data_row = cursor + 2 + len(table)
        section_positions.append((title, table, chart_kind, title_row, header_row, first_data_row, last_data_row))
        cursor += max(len(table) + 2, MIN_SECTION_ROWS)

# Reopen to style cells + attach native Excel chart objects (openpyxl can't
# write charts in the same pass as pandas' ExcelWriter, so this is a
# second, deterministic step).
wb = openpyxl.load_workbook(OUTPUT_FILE)

ws_data = wb["Forecast_Staffing"]
date_col = list(staffing_out.columns).index("date") + 1
for row in range(2, ws_data.max_row + 1):
    ws_data.cell(row=row, column=date_col).number_format = "yyyy-mm-dd"
for col_idx in range(1, ws_data.max_column + 1):
    ws_data.cell(row=1, column=col_idx).font = HEADER_FONT
    ws_data.cell(row=1, column=col_idx).fill = HEADER_FILL
    ws_data.column_dimensions[get_column_letter(col_idx)].width = 20

ws = wb["Analysis"]

for title, table, chart_kind, title_row, header_row, first_data_row, last_data_row in section_positions:
    cell = ws.cell(row=title_row, column=1, value=title)
    cell.font = TITLE_FONT
    ncols = table.shape[1]
    for col_idx in range(1, ncols + 1):
        hcell = ws.cell(row=header_row, column=col_idx)
        hcell.font = HEADER_FONT
        hcell.fill = HEADER_FILL
        hcell.alignment = Alignment(horizontal="center")
        col_letter = get_column_letter(col_idx)
        # Kept narrow (24/13, not 26/16) specifically so the table + its
        # chart both fit on screen together without horizontal scrolling.
        ws.column_dimensions[col_letter].width = 24 if col_idx == 1 else 13
    if table.columns[0] == "period":
        for row in range(first_data_row, last_data_row + 1):
            ws.cell(row=row, column=1).number_format = "yyyy-mm-dd"


def single_bar_chart(ws_target, title, anchor_col, header_row, first_data_row, last_data_row):
    """One metric, one series - used for the 2-row Model Accuracy table."""
    bar = BarChart()
    bar.title = title
    bar.y_axis.title = "Holdout MAPE %"
    bar.width, bar.height = 11, 6.5  # cm - compact enough to sit beside the table with no scrolling
    cats = Reference(ws_target, min_col=1, min_row=first_data_row, max_row=last_data_row)
    data = Reference(ws_target, min_col=2, min_row=header_row, max_row=last_data_row)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(cats)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True
    bar.legend = None
    anchor = f"{get_column_letter(anchor_col)}{first_data_row - 1}"
    ws_target.add_chart(bar, anchor)


def combo_chart(ws_target, title, anchor_col, header_row, first_data_row, last_data_row):
    """Bar = forecast volume, Line = staffing gap FTE on a secondary axis -
    shows both HOW MUCH contact volume is coming AND HOW SHORT-STAFFED that
    volume leaves the floor, in the same picture. Data labels on both series
    so the numbers are readable directly off the chart, same as use case 1."""
    bar = BarChart()
    bar.title = title
    bar.y_axis.title = "Forecast Volume"
    bar.width, bar.height = 11, 6.5  # cm - compact enough to sit beside the table with no scrolling
    cats = Reference(ws_target, min_col=1, min_row=first_data_row, max_row=last_data_row)
    vol_data = Reference(ws_target, min_col=2, min_row=header_row, max_row=last_data_row)  # forecast_volume
    bar.add_data(vol_data, titles_from_data=True)
    bar.set_categories(cats)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True

    line = LineChart()
    gap_data = Reference(ws_target, min_col=5, min_row=header_row, max_row=last_data_row)  # staffing_gap_fte
    line.add_data(gap_data, titles_from_data=True)
    line.y_axis.axId = 200
    line.y_axis.title = "Staffing Gap (FTE)"
    line.y_axis.crosses = "max"
    bar.y_axis.crosses = "autoZero"
    line.dataLabels = DataLabelList()
    line.dataLabels.showVal = True

    bar += line
    bar.legend.position = "b"
    anchor = f"{get_column_letter(anchor_col)}{first_data_row - 1}"
    ws_target.add_chart(bar, anchor)


# Every chart is anchored BESIDE its own table (same row, one column past
# the table's last column, a single-column gap), not collected on a
# separate sheet - so the number and the picture read together on one
# screen, without flipping tabs OR scrolling sideways to see the chart.
for title, table, chart_kind, title_row, header_row, first_data_row, last_data_row in section_positions:
    anchor_col = table.shape[1] + 1
    chart_title = title if len(title) < 45 else title[:42] + "..."
    if chart_kind == "bar":
        single_bar_chart(ws, chart_title, anchor_col, header_row, first_data_row, last_data_row)
    else:
        combo_chart(ws, chart_title, anchor_col, header_row, first_data_row, last_data_row)

wb.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} (2 sheets: Forecast_Staffing, Analysis - {len(section_positions)} tables+charts)")

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

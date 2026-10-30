# Power BI Build Guide — Demand Forecasting & Staffing

A real `.pbix` can't be hand-authored as a text/code file — Power BI Desktop
is the only thing that can produce one. This is the exact recipe to build it
live in a few minutes. Two pages, matching the narration script.

## 1. Get Data
Power BI Desktop → **Get Data → Excel Workbook** →
`final_output/final_output_forecast_staffing.xlsx` → check
**Forecast_Staffing** only → Load.
(The workbook's `Analysis` sheet stacks several tables (each with its own
chart beside it) with title rows and gaps for easy human reading in Excel —
not a clean rectangular range, so don't import it. Forecast_Staffing is the
full, clean, date-level table; build the weekly view directly in Power BI
using its own date hierarchy, as below.)

## 2. DAX measures (Modeling → New Measure, on the Forecast_Staffing table)
```DAX
Avg Required FTE = AVERAGE(Forecast_Staffing[required_fte])

Avg Available FTE = AVERAGE(Forecast_Staffing[available_fte])

Days Short-Staffed = CALCULATE(COUNTROWS(Forecast_Staffing), Forecast_Staffing[staffing_gap_fte] > 0)

Max Gap (FTE) = MAX(Forecast_Staffing[staffing_gap_fte])

Total Forecast Volume = SUM(Forecast_Staffing[forecast_volume])
```

## 3. Page 1 — "Forecast Overview"
| Visual | Type | Fields |
|---|---|---|
| Avg required FTE | Card | `Avg Required FTE` |
| Avg available FTE | Card | `Avg Available FTE` |
| Days short-staffed | Card | `Days Short-Staffed` |
| Forecast volume over time | Line chart | Axis: `date` · Values: `forecast_volume` |

Narrate while building: *"The forecast volume line shows the weekly rhythm
continuing six weeks forward — no major spike expected, just the normal
pattern, which is itself a useful finding: this isn't a volume-growth
problem, it's a staffing-level problem."*

## 4. Page 2 — "Staffing Gap"
| Visual | Type | Fields |
|---|---|---|
| Required vs Available FTE | Line chart (2 series) | Axis: `date` · Values: `required_fte`, `available_fte` |
| Staffing gap by day | Column chart, conditional formatting (red if > 0) | Axis: `date` · Values: `staffing_gap_fte` |
| Worst-day callout | Card | `Max Gap (FTE)` |
| Forecast detail table | Table | `date`, `forecast_volume`, `required_fte`, `available_fte`, `staffing_gap_fte` |

To match the week-level view from the narration, right-click `date` in the
Fields pane → Create hierarchy isn't needed — simpler: on each chart's axis
well, Power BI auto-groups a date field; use the dropdown arrow on the axis
field and switch from "Date" to a continuous axis, or add `date.[Week]`
if you want an explicit weekly bucket instead of daily points.

Narrate while building: *"Plotting required against available FTE on the
same axis makes the gap visual immediately — the required line sits above
available on most days. The column chart with conditional formatting turns
every red bar into a day that needs attention; the worst single day is
about 2.3 FTE short, which six weeks of lead time is more than enough to
fix with overtime or a couple of flexible shifts."*

## Note on data source
Everything in this guide comes from the single **Forecast_Staffing** sheet
— it's the full, clean, date-level table and the only sheet you need to
load into Power BI. The `Analysis` sheet in the workbook is for the
Excel-side walkthrough only.

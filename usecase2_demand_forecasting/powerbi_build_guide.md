# Power BI Build Guide — Demand Forecasting & Staffing

A real `.pbix` can't be hand-authored as a text/code file — Power BI Desktop
is the only thing that can produce one. This is the exact recipe to build it
live in a few minutes. Two pages, matching the narration script.

## 1. Get Data
Power BI Desktop → **Get Data → Excel Workbook** →
`final_output/final_output_forecast_staffing.xlsx` → check
**Forecast_Staffing** AND **Insights** → Load.

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
| Required vs Available FTE | Line chart (2 series) | Axis: `date` (from **Insights** sheet, weekly) · Values: `required_fte`, `available_fte` |
| Staffing gap by week | Column chart, conditional formatting (red if > 0) | Axis: `week_starting` · Values: `staffing_gap_fte` |
| Worst-week callout | Card | `Max Gap (FTE)` |
| Forecast detail table | Table | `date`, `forecast_volume`, `required_fte`, `available_fte`, `staffing_gap_fte` |

Narrate while building: *"Plotting required against available FTE on the
same axis makes the gap visual immediately — the required line sits above
available on most weeks. The column chart with conditional formatting turns
every red bar into a week that needs attention; the worst single day is
about 1.6 FTE short, which six weeks of lead time is more than enough to
fix with overtime or a couple of flexible shifts."*

## Note on data source
Use the **Insights** sheet (weekly rollup) for the two-series FTE comparison
chart — it's pre-aggregated and reads cleanly. Use **Forecast_Staffing**
(date-level) for the detail table and the volume trend line.

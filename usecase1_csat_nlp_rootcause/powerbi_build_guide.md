# Power BI Build Guide — CSAT Root-Cause & Sentiment Driver Analysis

A real `.pbix` can't be hand-authored as a text/code file — Power BI Desktop
is the only thing that can produce one. This is the exact recipe to build it
live in a few minutes. Two pages, matching the narration script.

## 1. Get Data
Power BI Desktop → **Get Data → Excel Workbook** →
`final_output/final_output_csat_insights.xlsx` → check **Tagged_Data** →
Load. (You don't need the **Analysis** sheet in Power BI — it's the
Excel-side pivot-equivalent view (stacked tables + charts, not a clean
rectangular range); Power BI builds its own visuals from Tagged_Data.)

## 2. DAX measures (Modeling → New Measure, on the Tagged_Data table)
```DAX
Total Responses = COUNTROWS(Tagged_Data)

Avg CSAT = AVERAGE(Tagged_Data[csat_score])

Negative Responses = CALCULATE([Total Responses], Tagged_Data[sentiment_label] = "Negative")

Pct Negative Sentiment = DIVIDE([Negative Responses], [Total Responses])

Avg Tenure (months) = AVERAGE(Tagged_Data[tenure_months])
```

## 3. Page 1 — "Driver Overview"
| Visual | Type | Fields |
|---|---|---|
| Overall CSAT | Card | `Avg CSAT` |
| % Negative | Card | `Pct Negative Sentiment` (format as %) |
| Responses & CSAT by Driver | Clustered column + line (combo chart) | Axis: `primary_driver` · Column values: `Total Responses` · Line values: `Avg CSAT` |
| Billing complaints trend | Line chart | Axis: `date` (set to Week granularity) · Values: `Total Responses`, filtered to `primary_driver = Billing_Charges` (page-level or visual-level filter) |

Narrate while building: *"I'm putting primary_driver on the axis and response
count as columns, with average CSAT as a line on the same chart, so you can
see volume and severity together — Billing & Charges is both the biggest bar
and the lowest line, which is exactly the combination that makes it
priority one."*

## 4. Page 2 — "Channel & Tenure Deep Dive"
| Visual | Type | Fields |
|---|---|---|
| Driver mix by channel | 100% stacked bar | Axis: `channel` · Legend: `primary_driver` · Values: `Total Responses` |
| Avg tenure by driver | Clustered column | Axis: `primary_driver` · Values: `Avg Tenure (months)` |
| LoB breakdown | Stacked column | Axis: `lob` · Legend: `primary_driver` · Values: `Total Responses` |
| Driver summary table | Table | `primary_driver`, `Total Responses`, `Avg CSAT`, `Avg Tenure (months)` |

Narrate while building: *"Voice clearly carries more Agent Behavior and
Resolution-Time complaints than Chat or Email, and the tenure chart shows
agents linked to Agent Behavior complaints skew newer than the rest of the
roster — about six months, on this data — which turns this from 'CSAT is
down' into two specific, fundable actions: fix the billing defect, and
tighten new-agent coaching."*

## Note on the `matched_drivers` column
That column stores a Python list as text (e.g. `['Billing_Charges']`) — it's
there for transparency/audit, not meant to be parsed in Power BI. Use
`primary_driver` for every visual above; it's already a clean single value
per row.

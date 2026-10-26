"""
02_root_cause_sentiment_analysis.py
------------------------------------
Main walkthrough script for the CSAT Root-Cause & Sentiment Driver Analysis
use case.

HOW TO RUN (VS Code):
  1. Open this file in VS Code with the Python extension installed.
  2. Each block starting with "# %%" is a runnable cell - hover above it and
     click "Run Cell" (or press Shift+Enter) to execute just that block and
     see its output in the interactive window.
  3. Run the cells top to bottom in order. Comments starting with "NARRATE:"
     are talk-track cues for the recording - say that, then run the cell.

INPUT : input/input_survey_verbatims.xlsx   (produced by 01_generate_synthetic_data.py)
OUTPUT: final_output/final_output_csat_insights.xlsx
        - sheet "Tagged_Data"      : row-level, for your own pivot tables too
        - sheet "Driver_Summary"   : aggregated table + bar charts
        - sheet "Channel_x_Driver" : crosstab table + stacked bar chart
        - sheet "Tenure_by_Driver" : table + bar chart
        NOTE: a native Excel "PivotTable" object (the drag-and-drop field
        list) can't be created from a script in a way that's portable to
        macOS Excel - the only way to do that is to drive the real Excel
        application via Windows-only COM automation, which won't run on the
        Mac this gets recorded on. So this workbook ships the PIVOT-EQUIVALENT
        (pre-aggregated tables + real embedded Excel charts) instead, and it
        is rebuilt from scratch every time you run this script - so re-running
        never leaves you with a stale or hand-edited copy to worry about. If
        you also want to show yourself building a live PivotTable on camera,
        do that as a separate, quick "Insert > PivotTable" step on the
        Tagged_Data sheet during the recording - a normal 30-second expert
        move, and unrelated to (won't be touched by) this script.
"""

# %% Cell 0 - Imports & config
import os
import re
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from openpyxl.chart import BarChart, Reference

INPUT_FILE = "input/input_survey_verbatims.xlsx"
INTERMEDIATE_FILE = "intermediate/intermediate_dictionary_bootstrap_terms.xlsx"
OUTPUT_FILE = "final_output/final_output_csat_insights.xlsx"

os.makedirs("intermediate", exist_ok=True)
os.makedirs("final_output", exist_ok=True)

pd.set_option("display.max_colwidth", 80)

# %% Cell 1 - Load input data
# NARRATE: "This is the raw survey export - date, a unique response ID, the
# channel it came in on, the LoB, the customer's own words, the CSAT score
# they gave, and the agent/TL/manager who handled it."
df = pd.read_excel(INPUT_FILE, sheet_name="Survey_Data")
df["date"] = pd.to_datetime(df["date"])
print(df.shape)
df.head()

# %% Cell 2 - Quick profiling before we touch the text
# NARRATE: "Before any NLP, I always check volumes and distributions first -
# it tells me where to focus."
print(df["channel"].value_counts(), "\n")
print(df["lob"].value_counts(), "\n")
print(df["csat_score"].value_counts().sort_index())

# %% Cell 3 - Text cleaning
# NARRATE: "I normalize the verbatim - lowercase, strip punctuation - so my
# keyword dictionary matches reliably regardless of how the customer typed it."
def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


df["clean_text"] = df["verbatim"].apply(clean_text)
df[["verbatim", "clean_text"]].head(3)

# %% Cell 4 - Fast dictionary bootstrap (instead of days of manual read-through)
# NARRATE: "Normally building a keyword dictionary means reading hundreds of
# verbatims by hand. Instead, I pull the most frequent words/phrases that show
# up specifically in the low-CSAT (1-2) responses - that gives me a shortlist
# to review and turn into a dictionary in minutes, not days."
negative = df[df["csat_score"] <= 2]["clean_text"]
vectorizer = CountVectorizer(ngram_range=(1, 2), stop_words="english", max_features=25)
term_counts = vectorizer.fit_transform(negative)
top_terms = pd.Series(
    term_counts.toarray().sum(axis=0), index=vectorizer.get_feature_names_out()
).sort_values(ascending=False)
print("Top terms found in low-CSAT verbatims (used to seed/expand the dictionary below):")
print(top_terms)

# Saved as the task's INTERMEDIATE artifact - the evidence trail between the
# raw input and the final tagged output, in case a reviewer wants to see how
# the dictionary in Cell 5 was derived.
top_terms.rename("frequency").rename_axis("term").reset_index().to_excel(
    INTERMEDIATE_FILE, index=False, sheet_name="Bootstrap_Terms")
print(f"Saved intermediate artifact -> {INTERMEDIATE_FILE}")

# %% Cell 5 - Root-cause keyword dictionary (SME-curated, seeded from Cell 4)
# NARRATE: "Here is the finished dictionary - three business drivers, each
# with the phrases that signal that issue. This is the only thing that needs
# updating if a new issue type shows up in a future wave of data."
DRIVER_KEYWORDS = {
    "Billing_Charges": [
        "charged twice", "double charged", "overcharged", "unexpected charge",
        "incorrect bill", "wrong bill", "deducted incorrectly", "not received my refund",
        "not refunded", "late fee", "activation fee", "roaming charge", "service tax",
        "charged for", "never used it",
    ],
    "Agent_Behavior_Comm": [
        "rude", "unprofessional", "interrupting", "did not listen", "repeat myself",
        "repeated myself", "put on hold", "call got disconnected", "transferred me",
        "ignored my concern",
    ],
    "Resolution_Time_FCR": [
        "still not resolved", "not resolved", "third time i am calling",
        "promised a callback", "nobody followed up", "no follow up",
        "ticket", "reopened", "waiting for days", "no update", "keeps coming back",
    ],
}


def tag_drivers(text: str) -> list:
    hits = []
    for driver, phrases in DRIVER_KEYWORDS.items():
        if any(phrase in text for phrase in phrases):
            hits.append(driver)
    return hits


df["matched_drivers"] = df["clean_text"].apply(tag_drivers)
df["matched_drivers"].apply(len).value_counts()

# %% Cell 6 - Sentiment scoring (lexicon-based, fully offline - no AI/LLM call)
# NARRATE: "I score sentiment with VADER, a rules/lexicon-based sentiment
# model - it's deterministic, explainable, and runs entirely offline, which
# matters here since LLM API usage isn't confirmed for this environment yet."
analyzer = SentimentIntensityAnalyzer()
df["sentiment_compound"] = df["verbatim"].apply(lambda t: analyzer.polarity_scores(t)["compound"])
df["sentiment_label"] = pd.cut(
    df["sentiment_compound"], bins=[-1.01, -0.05, 0.05, 1.01],
    labels=["Negative", "Neutral", "Positive"]
)
df[["verbatim", "sentiment_compound", "sentiment_label"]].head(5)

# %% Cell 7 - Resolve a single primary driver per response
# NARRATE: "A response can mention more than one issue, so I keep the full
# list, but I also pick one PRIMARY driver - the one that matters most for a
# clean pivot / Power BI view - using keyword match priority, falling back to
# sentiment where no keyword matched at all."
PRIORITY = ["Billing_Charges", "Agent_Behavior_Comm", "Resolution_Time_FCR"]


def primary_driver(row) -> str:
    if row["matched_drivers"]:
        for driver in PRIORITY:
            if driver in row["matched_drivers"]:
                return driver
    if row["sentiment_label"] == "Negative":
        return "Other_Negative_Unclassified"
    return "No_Issue_Positive"


df["primary_driver"] = df.apply(primary_driver, axis=1)
df["primary_driver"].value_counts()

# %% Cell 8 - Aggregated views (this is what you'd otherwise build as a pivot table)
driver_summary = (
    df.groupby("primary_driver")
    .agg(responses=("unique_id", "count"),
         avg_csat=("csat_score", "mean"),
         avg_sentiment=("sentiment_compound", "mean"))
    .assign(pct_of_total=lambda d: (d["responses"] / len(df) * 100).round(1))
    .sort_values("responses", ascending=False)
    .reset_index()
)
print(driver_summary)

tenure_by_driver = df.groupby("primary_driver")["tenure_months"].mean().round(1)
print("\nAvg agent tenure by driver:\n", tenure_by_driver)

channel_by_driver = pd.crosstab(df["channel"], df["primary_driver"]).reset_index()
print("\nDriver mix by channel:\n", channel_by_driver)

tenure_table = tenure_by_driver.rename("avg_tenure_months").reset_index()

# %% Cell 9 - Save outputs: ONE workbook, rebuilt from scratch every run
# NARRATE: "Instead of a flat CSV, I publish one Excel workbook with the raw
# tagged data on one sheet and ready-made insight tables and charts on the
# others - this becomes my walkthrough deck, and it's fully reproducible:
# every time I rerun this script, every sheet and every chart regenerates
# from the current data, so there's never a stale hand-edited copy floating
# around."
df_out = df.drop(columns=["clean_text"])

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="Tagged_Data", index=False)
    driver_summary.to_excel(writer, sheet_name="Driver_Summary", index=False)
    channel_by_driver.to_excel(writer, sheet_name="Channel_x_Driver", index=False)
    tenure_table.to_excel(writer, sheet_name="Tenure_by_Driver", index=False)

# Reopen to attach native Excel chart objects (openpyxl can't write charts in
# the same pass as pandas' ExcelWriter, so this is a second, deterministic step).
import openpyxl
wb = openpyxl.load_workbook(OUTPUT_FILE)

ws = wb["Driver_Summary"]
chart1 = BarChart()
chart1.title = "Responses by Primary Driver"
chart1.y_axis.title = "Responses"
data = Reference(ws, min_col=2, max_col=2, min_row=1, max_row=ws.max_row)
cats = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
chart1.add_data(data, titles_from_data=True)
chart1.set_categories(cats)
ws.add_chart(chart1, "G2")

chart2 = BarChart()
chart2.title = "Avg CSAT by Primary Driver"
chart2.y_axis.title = "Avg CSAT"
data2 = Reference(ws, min_col=3, max_col=3, min_row=1, max_row=ws.max_row)
chart2.add_data(data2, titles_from_data=True)
chart2.set_categories(cats)
ws.add_chart(chart2, "G18")

ws2 = wb["Channel_x_Driver"]
chart3 = BarChart()
chart3.type = "col"
chart3.grouping = "stacked"
chart3.overlap = 100
chart3.title = "Driver Mix by Channel"
data3 = Reference(ws2, min_col=2, max_col=ws2.max_column, min_row=1, max_row=ws2.max_row)
cats3 = Reference(ws2, min_col=1, min_row=2, max_row=ws2.max_row)
chart3.add_data(data3, titles_from_data=True)
chart3.set_categories(cats3)
ws2.add_chart(chart3, "G2")

ws3 = wb["Tenure_by_Driver"]
chart4 = BarChart()
chart4.title = "Avg Agent Tenure (months) by Driver"
data4 = Reference(ws3, min_col=2, max_col=2, min_row=1, max_row=ws3.max_row)
cats4 = Reference(ws3, min_col=1, min_row=2, max_row=ws3.max_row)
chart4.add_data(data4, titles_from_data=True)
chart4.set_categories(cats4)
ws3.add_chart(chart4, "D2")

wb.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} (4 sheets, 4 charts)")

# %% Cell 10 - Spoken walkthrough numbers (read these out on camera)
top = driver_summary.iloc[0]
print(f"Top driver: {top['primary_driver']} -> {top['pct_of_total']}% of all responses, "
      f"avg CSAT {top['avg_csat']:.2f}")
print(f"Overall avg CSAT: {df['csat_score'].mean():.2f}")
print(f"% Negative sentiment overall: {(df['sentiment_label'] == 'Negative').mean() * 100:.1f}%")

# %% Cell 11 [OPTIONAL - DO NOT RUN] - LLM-assisted tagging, pending approval
# ----------------------------------------------------------------------------
# NOT APPROVED YET. Do not run this cell during recording.
#
# In production we would normally use an LLM API (Gemini / OpenAI / Anthropic)
# to classify each verbatim against the driver taxonomy instead of a static
# keyword dictionary - it handles paraphrasing/negation far better. But API
# usage has not been confirmed as permitted for this engagement, and no key
# has been provided, so this stays disabled. Left here only to show the
# intended future-state design once/if approved.
#
# USE_LLM_API = False
# if USE_LLM_API:
#     import openai  # or google.generativeai / anthropic
#     ...

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
        - sheet "Tagged_Data" : row-level, incl. primary/secondary driver,
          sentiment, tenure bucket, week - for your own pivot tables too
        - sheet "Summary"     : every aggregated table in one place (primary
          driver, secondary driver, primary->secondary %, CSAT cut by
          channel/LoB/tenure/manager/TL, weekly trend of the top primary and
          top secondary driver)
        - sheet "Charts"      : every chart in one place, each pairing
          RESPONSE VOLUME (bars) with AVG CSAT (line, secondary axis) so
          every view shows both how often an issue happens and how badly it
          hurts satisfaction
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
import openpyxl
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import NMF
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from openpyxl.chart import BarChart, LineChart, Reference

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
df = pd.read_excel(INPUT_FILE, sheet_name="Survey_Data", keep_default_na=False)
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
# WHAT: instead of counting frequent terms in low-CSAT text alone (which
# mixes in generic words like "agent" or "issue" that show up in BOTH happy
# and unhappy responses, and don't tell you anything), I count terms
# SEPARATELY in low-CSAT (1-2) and high-CSAT (4-5) text, then compare the
# two frequencies to label every term's SENTIMENT LEAN - Negative-leaning,
# Positive-leaning, or Neutral/Mixed.
# WHY: a term that appears equally often in happy and unhappy responses is
# noise, not a signal - it shouldn't make it into the root-cause dictionary.
# Labeling the lean up front is what tells a reviewer (or me, reading this
# back later) WHY a given term was or wasn't promoted into DRIVER_KEYWORDS
# in Cell 5, instead of a flat, unexplained frequency list.
def term_frequencies(texts: pd.Series) -> pd.Series:
    vec = CountVectorizer(ngram_range=(1, 2), stop_words="english", max_features=40)
    counts = vec.fit_transform(texts)
    return pd.Series(counts.toarray().sum(axis=0), index=vec.get_feature_names_out())


negative_terms = term_frequencies(df[df["csat_score"] <= 2]["clean_text"])
positive_terms = term_frequencies(df[df["csat_score"] >= 4]["clean_text"])

bootstrap = pd.concat(
    [negative_terms.rename("negative_freq"), positive_terms.rename("positive_freq")], axis=1
).fillna(0).astype(int)


def classify_lean(row) -> str:
    n, p = row["negative_freq"], row["positive_freq"]
    if n > p * 1.5:
        return "Negative-leaning"
    if p > n * 1.5:
        return "Positive-leaning"
    return "Neutral/Mixed"


bootstrap["sentiment_lean"] = bootstrap.apply(classify_lean, axis=1)
bootstrap = (
    bootstrap.sort_values("negative_freq", ascending=False)
    .reset_index().rename(columns={"index": "term"})
)
print("Top terms, split by where they actually show up (used to seed/expand the dictionary below):")
print(bootstrap.head(25))
print("\nSentiment lean counts:\n", bootstrap["sentiment_lean"].value_counts())

# Saved as the task's INTERMEDIATE artifact - the evidence trail between the
# raw input and the final tagged output, in case a reviewer wants to see how
# the dictionary in Cell 5 was derived, and why each term was or wasn't used.
bootstrap.to_excel(INTERMEDIATE_FILE, index=False, sheet_name="Bootstrap_Terms")
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


def tag_drivers(text: str) -> dict:
    """Returns {driver: number of distinct phrases matched} - the COUNT is
    what lets us rank a PRIMARY (strongest signal) vs SECONDARY (next
    strongest) driver per response, instead of an arbitrary tie-break order."""
    hits = {}
    for driver, phrases in DRIVER_KEYWORDS.items():
        count = sum(1 for phrase in phrases if phrase in text)
        if count > 0:
            hits[driver] = count
    return hits


df["driver_hits"] = df["clean_text"].apply(tag_drivers)
df["matched_drivers"] = df["driver_hits"].apply(lambda d: ", ".join(d.keys()) if d else "")
df["driver_hits"].apply(len).value_counts()

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

# %% Cell 7 - Resolve PRIMARY and SECONDARY driver per response
# NARRATE: "A response can mention more than one issue - a billing complaint
# where the agent was also rude, for example. I rank the matched drivers by
# how many distinct phrases hit: the strongest is the PRIMARY driver, the
# next strongest is the SECONDARY driver - the compounding factor the client
# should also act on, not just the headline issue. Where nothing matched, I
# fall back to sentiment rather than force a wrong tag."
def resolve_drivers(row):
    hits = row["driver_hits"]
    if hits:
        ranked = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
        primary = ranked[0][0]
        secondary = ranked[1][0] if len(ranked) > 1 else "No Secondary Driver"
        return pd.Series({"primary_driver": primary, "secondary_driver": secondary})
    if row["sentiment_label"] == "Negative":
        return pd.Series({"primary_driver": "Other_Negative_Unclassified", "secondary_driver": "No Secondary Driver"})
    return pd.Series({"primary_driver": "No_Issue_Positive", "secondary_driver": "No Secondary Driver"})


df[["primary_driver", "secondary_driver"]] = df.apply(resolve_drivers, axis=1)

# A couple more cuts to analyze CSAT by, for depth:
def tenure_bucket(months: int) -> str:
    if months < 6:
        return "<6 months"
    if months < 12:
        return "6-12 months"
    if months < 24:
        return "12-24 months"
    return "24+ months"


df["tenure_bucket"] = df["tenure_months"].apply(tenure_bucket)
df["week_starting"] = df["date"].dt.to_period("W").dt.start_time


# WHAT: classic NPS-style CSAT bucketing - Promoter (4-5), Neutral (3),
# Detractor (1-2). WHY: a raw 1-5 average hides the shape of the
# distribution (two 3s and a 5 average the same as a 2 and a 4-ish split,
# but tell very different stories) - bucketing it is the standard way CX
# teams actually report CSAT, alongside the text-based sentiment_label from
# Cell 6, so both the SCORE and the TEXT TONE are visible side by side.
def csat_bucket(score: int) -> str:
    if score >= 4:
        return "Promoter (4-5)"
    if score == 3:
        return "Neutral (3)"
    return "Detractor (1-2)"


df["csat_bucket"] = df["csat_score"].apply(csat_bucket)

print(df["primary_driver"].value_counts())
print("\n", df["secondary_driver"].value_counts())

# %% Cell 7b - WHAT: fill in a real secondary driver (via TF-IDF + NMF topic
# modeling) wherever the keyword dictionary alone found none.
# WHY: on short survey verbatim, a second DISTINCT keyword phrase often just
# isn't present in the text, even when there genuinely is a second issue -
# so the dictionary-only secondary driver mostly comes back "None", which
# isn't something the client can act on. To make the secondary finding
# actually actionable, I complement the dictionary with UNSUPERVISED topic
# modeling: TF-IDF turns each "unexplained" negative response into a vector
# of weighted terms, NMF (non-negative matrix factorization - a standard,
# fast, well-understood topic-modeling technique, the same family as LDA)
# discovers a handful of latent sub-themes directly from that text with no
# labels needed, and I auto-generate a short, readable name for each
# discovered theme using YAKE - a lightweight, offline, unsupervised
# keyword-extraction library (no AI/LLM, no API, no corpus download). The
# result: every negative response ends up with a concrete secondary driver -
# either a known dictionary category, or a discovered sub-theme phrase like
# "Sub-theme: Put On Hold" - instead of a blank "None".
try:
    import yake
    _yake_extractor = yake.KeywordExtractor(n=2, top=1, dedupLim=0.9)

    def label_from_text(text: str, fallback_terms: str) -> str:
        kws = _yake_extractor.extract_keywords(text)
        return kws[0][0].title() if kws else fallback_terms.title()
except ImportError:
    # Graceful degrade: if yake isn't installed, fall back to the topic's
    # own top TF-IDF terms as the label - still distinct, still informative,
    # the script never breaks just because one optional library is missing.
    def label_from_text(text: str, fallback_terms: str) -> str:
        return fallback_terms.title()


residual_mask = (df["sentiment_label"] == "Negative") & (df["secondary_driver"] == "No Secondary Driver")
residual = df.loc[residual_mask, "clean_text"]
print(f"{len(residual)} negative responses have no keyword-based secondary driver - "
      f"running TF-IDF + NMF topic modeling on these to discover one.")

N_TOPICS = 4
secondary_topic_labels = {}
if len(residual) >= N_TOPICS * 5:   # need enough rows per topic to be meaningful
    tfidf = TfidfVectorizer(stop_words="english", max_features=500, ngram_range=(1, 2))
    X = tfidf.fit_transform(residual)
    nmf = NMF(n_components=N_TOPICS, random_state=42, init="nndsvda", max_iter=400)
    W = nmf.fit_transform(X)   # W[row, topic] = how strongly that row belongs to each topic
    feature_names = tfidf.get_feature_names_out()

    for topic_idx in range(N_TOPICS):
        # Label each topic using the actual verbatim text of its most
        # representative responses (reads more naturally through YAKE than
        # a disconnected bag of top TF-IDF terms would).
        top_doc_positions = W[:, topic_idx].argsort()[::-1][:5]
        representative_text = ". ".join(residual.iloc[i] for i in top_doc_positions)
        top_term_idx = nmf.components_[topic_idx].argsort()[::-1][:3]
        fallback_terms = " ".join(feature_names[i] for i in top_term_idx)
        secondary_topic_labels[topic_idx] = f"Sub-theme: {label_from_text(representative_text, fallback_terms)}"

    dominant_topic = W.argmax(axis=1)
    topic_series = pd.Series([secondary_topic_labels[t] for t in dominant_topic], index=residual.index)
    df.loc[residual.index, "secondary_driver"] = topic_series

print("\nDiscovered secondary sub-themes:", list(secondary_topic_labels.values()))
print(df["secondary_driver"].value_counts())

# %% Cell 8 - Aggregated views: CSAT cut across EVERY category (this is what
# you'd otherwise build as a pivot table)
# NARRATE: "I don't stop at one cut - I run the same volume + avg-CSAT view
# across every dimension we have: primary driver, secondary driver, channel,
# LoB, agent tenure, manager, team lead, and sentiment. And for each one, I
# also bring in three operational call-center metrics - average handle
# time, first-contact-resolution rate, and 30-day repeat-contact rate - so
# the client sees not just WHO is unhappy but the operational cost and the
# 'did we actually fix it' signal behind each cut."
def summarize(df_in: pd.DataFrame, group_col: str) -> pd.DataFrame:
    return (
        df_in.groupby(group_col)
        .agg(
            responses=("unique_id", "count"),
            avg_csat=("csat_score", "mean"),
            avg_handle_time_sec=("handle_time_seconds", "mean"),
            fcr_rate_pct=("is_first_contact_resolution", lambda s: (s == "Yes").mean() * 100),
            repeat_contact_pct=("is_repeat_contact_30d", lambda s: (s == "Yes").mean() * 100),
        )
        .assign(pct_of_total=lambda d: (d["responses"] / len(df_in) * 100).round(1))
        .round({"avg_csat": 2, "avg_handle_time_sec": 0, "fcr_rate_pct": 1, "repeat_contact_pct": 1})
        .sort_values("responses", ascending=False)
        .reset_index()
    )


primary_summary = summarize(df, "primary_driver")
secondary_summary = summarize(df, "secondary_driver")
channel_summary = summarize(df, "channel")
lob_summary = summarize(df, "lob")
tenure_summary = summarize(df, "tenure_bucket")
manager_summary = summarize(df, "manager_name")
tl_summary = summarize(df, "tl_name")
sentiment_summary = summarize(df, "sentiment_label")
csat_bucket_summary = summarize(df, "csat_bucket")

print(primary_summary)

# Cross-check: does the CSAT SCORE bucket agree with the text SENTIMENT
# label? (e.g. a "Promoter" score with Negative-sounding text is a real,
# actionable disagreement worth flagging - the score and the words aren't
# always telling the same story.)
score_vs_sentiment = (
    pd.crosstab(df["csat_bucket"], df["sentiment_label"], normalize="index")
    .mul(100).round(1).reset_index()
)
print("\nCSAT bucket vs sentiment label (% within bucket):\n", score_vs_sentiment)

# The compounding-issue view: of the responses where X is the PRIMARY driver,
# what % of the time is Y the SECONDARY driver? Shown in percentages, as requested.
real_drivers = ["Billing_Charges", "Agent_Behavior_Comm", "Resolution_Time_FCR", "Other_Negative_Unclassified"]
driver_rows = df[df["primary_driver"].isin(real_drivers)]
primary_x_secondary = (
    pd.crosstab(driver_rows["primary_driver"], driver_rows["secondary_driver"], normalize="index")
    .mul(100).round(1).reset_index()
)
print("\nPrimary -> Secondary driver (% within primary):\n", primary_x_secondary)

# Weekly trend (volume + avg CSAT) for the TOP primary driver and its TOP
# COMPOUNDING secondary driver.
# WHY conditional, not global: the single most common secondary driver
# platform-wide isn't necessarily the one that actually co-occurs with the
# #1 primary issue - picking the globally-popular one can land on something
# with near-zero overlap with top_primary, which isn't actionable. Instead
# I look up, specifically WITHIN top_primary's own row of the primary ->
# secondary crosstab, which secondary driver has the highest % - that's the
# real "what's compounding our #1 problem" answer.
top_primary = primary_summary.iloc[0]["primary_driver"]
top_primary_row = primary_x_secondary[primary_x_secondary["primary_driver"] == top_primary]
secondary_cols = [c for c in primary_x_secondary.columns if c not in ("primary_driver", "No Secondary Driver")]
if len(top_primary_row) and secondary_cols:
    top_secondary = top_primary_row.iloc[0][secondary_cols].astype(float).idxmax()
    top_secondary_pct_within_primary = top_primary_row.iloc[0][top_secondary]
else:
    top_secondary = None
    top_secondary_pct_within_primary = 0.0


def weekly_trend(df_in: pd.DataFrame, driver_col: str, driver_value: str) -> pd.DataFrame:
    out = (
        df_in[df_in[driver_col] == driver_value]
        .groupby("week_starting")
        .agg(responses=("unique_id", "count"), avg_csat=("csat_score", "mean"))
        .round({"avg_csat": 2})
        .reset_index()
        .sort_values("week_starting")
    )
    out["week_starting"] = pd.to_datetime(out["week_starting"]).dt.date
    return out


weekly_primary = weekly_trend(df, "primary_driver", top_primary)
weekly_secondary = weekly_trend(df, "secondary_driver", top_secondary) if top_secondary else None

print(f"\nTop primary driver: {top_primary}")
print(f"Top secondary driver: {top_secondary}")

# %% Cell 9 - Save outputs: ONE workbook, rebuilt from scratch every run
# NARRATE: "Instead of a flat CSV, or scattering tables and charts across
# lots of tabs, I publish one Excel workbook with the raw tagged data on one
# sheet, every summary table together on a second sheet, and every chart
# together on a third - that becomes my walkthrough deck, and it's fully
# reproducible: every time I rerun this script, every sheet and every chart
# regenerates from the current data, so there's never a stale hand-edited
# copy floating around."
df_out = df.drop(columns=["clean_text", "driver_hits"])
df_out["date"] = pd.to_datetime(df_out["date"]).dt.date  # real Excel date, not text
df_out["week_starting"] = pd.to_datetime(df_out["week_starting"]).dt.date

SECTIONS = [
    ("Primary Driver Summary", primary_summary),
    ("Secondary Driver Summary", secondary_summary),
    ("Primary -> Secondary Driver (% within primary)", primary_x_secondary),
    ("CSAT by Channel", channel_summary),
    ("CSAT by Line of Business", lob_summary),
    ("CSAT by Agent Tenure Bucket", tenure_summary),
    ("CSAT by Manager", manager_summary),
    ("CSAT by Team Lead", tl_summary),
    ("CSAT by Sentiment Label", sentiment_summary),
    ("CSAT Bucket (Promoter/Neutral/Detractor)", csat_bucket_summary),
    ("CSAT Bucket vs Sentiment Label (% within bucket)", score_vs_sentiment),
    (f"Weekly Trend - Top Primary Driver ({top_primary})", weekly_primary),
]
if weekly_secondary is not None:
    SECTIONS.append((f"Weekly Trend - Top Secondary Driver ({top_secondary})", weekly_secondary))

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="Tagged_Data", index=False)
    cursor = 0
    section_positions = []  # (title, table, title_row, header_row, first_data_row, last_data_row)
    for title, table in SECTIONS:
        table.to_excel(writer, sheet_name="Summary", index=False, startrow=cursor + 1, startcol=0)
        title_row = cursor + 1
        header_row = cursor + 2
        first_data_row = cursor + 3
        last_data_row = cursor + 2 + len(table)
        section_positions.append((title, table, title_row, header_row, first_data_row, last_data_row))
        cursor = last_data_row + 2
    pd.DataFrame({"x": []}).to_excel(writer, sheet_name="Charts", index=False, header=False)

# Reopen to write section titles + attach native Excel chart objects
# (openpyxl can't write charts in the same pass as pandas' ExcelWriter, so
# this is a second, deterministic step).
wb = openpyxl.load_workbook(OUTPUT_FILE)

ws_data = wb["Tagged_Data"]
for col_name in ("date", "week_starting"):
    col_idx = list(df_out.columns).index(col_name) + 1
    for row in range(2, ws_data.max_row + 1):
        ws_data.cell(row=row, column=col_idx).number_format = "yyyy-mm-dd"

ws_summary = wb["Summary"]
ws_summary.delete_cols(1, 1) if False else None  # (no-op placeholder, keeps column A as titles)
for title, table, title_row, header_row, first_data_row, last_data_row in section_positions:
    cell = ws_summary.cell(row=title_row, column=1, value=title)
    cell.font = openpyxl.styles.Font(bold=True, size=12)
    # format date-like label columns cleanly
    if table.columns[0] in ("week_starting",):
        for row in range(first_data_row, last_data_row + 1):
            ws_summary.cell(row=row, column=1).number_format = "yyyy-mm-dd"

ws_charts = wb["Charts"]
ws_charts.delete_rows(1, ws_charts.max_row)  # drop the empty placeholder row

ANCHOR_ROW_STEP = 19
next_anchor_row = 2


def combo_chart(title, header_row, first_data_row, last_data_row):
    """Bar = response volume, Line = avg CSAT on a secondary axis - every
    chart shows both HOW OFTEN an issue happens and HOW BADLY it hurts CSAT."""
    global next_anchor_row
    bar = BarChart()
    bar.title = title
    bar.y_axis.title = "Responses"
    cats = Reference(ws_summary, min_col=1, min_row=first_data_row, max_row=last_data_row)
    count_data = Reference(ws_summary, min_col=2, min_row=header_row, max_row=last_data_row)
    bar.add_data(count_data, titles_from_data=True)
    bar.set_categories(cats)

    line = LineChart()
    csat_data = Reference(ws_summary, min_col=3, min_row=header_row, max_row=last_data_row)
    line.add_data(csat_data, titles_from_data=True)
    line.y_axis.axId = 200
    line.y_axis.title = "Avg CSAT"
    line.y_axis.crosses = "max"
    bar.y_axis.crosses = "autoZero"

    bar += line
    ws_charts.add_chart(bar, f"A{next_anchor_row}")
    next_anchor_row += ANCHOR_ROW_STEP


def stacked_pct_chart(title, header_row, first_data_row, last_data_row, ncols):
    global next_anchor_row
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = title
    chart.y_axis.title = "% within primary driver"
    data = Reference(ws_summary, min_col=2, max_col=ncols, min_row=header_row, max_row=last_data_row)
    cats = Reference(ws_summary, min_col=1, min_row=first_data_row, max_row=last_data_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    ws_charts.add_chart(chart, f"A{next_anchor_row}")
    next_anchor_row += ANCHOR_ROW_STEP


# combo_chart()/stacked_pct_chart() only need (header_row, first_data_row,
# last_data_row) - title_row is used earlier (writing the title cell), not here.
positions_by_title = {title: (header_row, first_data_row, last_data_row)
                       for title, _table, _title_row, header_row, first_data_row, last_data_row
                       in section_positions}

combo_chart("Primary Driver: Volume vs Avg CSAT", *positions_by_title["Primary Driver Summary"])
combo_chart("Secondary Driver: Volume vs Avg CSAT", *positions_by_title["Secondary Driver Summary"])
stacked_pct_chart(
    "Primary -> Secondary Driver (%)",
    *positions_by_title["Primary -> Secondary Driver (% within primary)"],
    ncols=primary_x_secondary.shape[1],
)
combo_chart("Channel: Volume vs Avg CSAT", *positions_by_title["CSAT by Channel"])
combo_chart("Line of Business: Volume vs Avg CSAT", *positions_by_title["CSAT by Line of Business"])
combo_chart("Agent Tenure: Volume vs Avg CSAT", *positions_by_title["CSAT by Agent Tenure Bucket"])
combo_chart("Manager: Volume vs Avg CSAT", *positions_by_title["CSAT by Manager"])
combo_chart("Team Lead: Volume vs Avg CSAT", *positions_by_title["CSAT by Team Lead"])
combo_chart("Sentiment Label: Volume vs Avg CSAT", *positions_by_title["CSAT by Sentiment Label"])
combo_chart("CSAT Bucket: Volume vs Avg CSAT", *positions_by_title["CSAT Bucket (Promoter/Neutral/Detractor)"])
stacked_pct_chart(
    "CSAT Bucket vs Sentiment Label (%)",
    *positions_by_title["CSAT Bucket vs Sentiment Label (% within bucket)"],
    ncols=score_vs_sentiment.shape[1],
)
combo_chart(
    f"Weekly Trend - Primary Driver ({top_primary}): Volume vs Avg CSAT",
    *positions_by_title[f"Weekly Trend - Top Primary Driver ({top_primary})"],
)
if weekly_secondary is not None:
    combo_chart(
        f"Weekly Trend - Secondary Driver ({top_secondary}): Volume vs Avg CSAT",
        *positions_by_title[f"Weekly Trend - Top Secondary Driver ({top_secondary})"],
    )

wb.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} (3 sheets: Tagged_Data, Summary, Charts)")

# %% Cell 10 - Spoken walkthrough numbers (read these out on camera)
top = primary_summary.iloc[0]
print(f"Top PRIMARY driver: {top['primary_driver']} -> {top['pct_of_total']}% of all responses, "
      f"avg CSAT {top['avg_csat']:.2f}, avg handle time {top['avg_handle_time_sec']:.0f}s, "
      f"FCR rate {top['fcr_rate_pct']:.1f}%, 30-day repeat contact {top['repeat_contact_pct']:.1f}%")
if top_secondary:
    print(f"Top COMPOUNDING secondary driver within {top_primary}: {top_secondary} "
          f"-> present in {top_secondary_pct_within_primary:.1f}% of {top_primary} complaints")
print(f"Overall avg CSAT: {df['csat_score'].mean():.2f}")
print(f"CSAT mix: {dict(df['csat_bucket'].value_counts())}")
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

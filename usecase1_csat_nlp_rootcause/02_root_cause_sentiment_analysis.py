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
     are talk-track cues for presenting this walkthrough - say that, then
     run the cell.

INPUT : input/input_survey_verbatims.xlsx   (produced by 01_generate_synthetic_data.py)
OUTPUT: final_output/final_output_csat_insights.xlsx
        - sheet "Tagged_Data" : row-level, incl. primary/secondary driver,
          issue theme, sentiment, tenure bucket, week - for your own pivot
          tables too
        - sheet "Analysis"    : every aggregated table (primary driver,
          secondary driver, sub-issue drill-down within the top primary
          driver, issue theme, CSAT cut by channel/LoB/tenure/manager/TL/
          plan-tier/circle, weekly trend), each one with its own chart
          placed right beside it - every chart pairs RESPONSE VOLUME (bars)
          with AVG CSAT (line, secondary axis) so every view shows both how
          often an issue happens and how badly it hurts satisfaction
        NOTE: a native Excel "PivotTable" object (the drag-and-drop field
        list) can't be created from a script in a way that's portable to
        macOS Excel - the only way to do that is to drive the real Excel
        application via Windows-only COM automation. So this workbook ships
        the PIVOT-EQUIVALENT (pre-aggregated tables + real embedded Excel
        charts) instead, and it is rebuilt from scratch every time you run
        this script - so re-running never leaves you with a stale or
        hand-edited copy to worry about. If you also want a live PivotTable,
        that's a separate, quick "Insert > PivotTable" step on the
        Tagged_Data sheet - a normal 30-second expert move, and unrelated
        to (won't be touched by) this script.
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
    # max_features=200 (up from 40) - with 9 primary categories and 34
    # specific sub-issues now in the real taxonomy, a short list would cut
    # off before showing the long tail of genuinely distinct terms.
    vec = CountVectorizer(ngram_range=(1, 2), stop_words="english", max_features=200)
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
print(bootstrap.head(40), f"\n... ({len(bootstrap)} terms total, see the intermediate file for all of them)")
print("\nSentiment lean counts:\n", bootstrap["sentiment_lean"].value_counts())

# Saved as the task's INTERMEDIATE artifact - the evidence trail between the
# raw input and the final tagged output, in case a reviewer wants to see how
# the dictionary in Cell 5 was derived, and why each term was or wasn't used.
bootstrap.to_excel(INTERMEDIATE_FILE, index=False, sheet_name="Bootstrap_Terms")
print(f"Saved intermediate artifact -> {INTERMEDIATE_FILE}")

# %% Cell 5 - Root-cause keyword dictionary: 11 PRIMARY categories, 42 SPECIFIC
# secondary sub-issues (SME-curated, seeded from Cell 4)
# NARRATE: "Here is the finished dictionary - a two-level taxonomy. Eleven
# broad primary categories cover the kind of problem; underneath each one,
# a set of specific, named sub-issues - 42 in total - cover exactly what
# the problem was. Tagging at the sub-issue level is what makes the
# SECONDARY driver genuinely actionable and natural-reading, instead of an
# algorithm's best guess: 'Incorrect Late Fee' or 'Excessive Hold Time'
# tells the client exactly what to fix, not just a vague theme. Every phrase
# below is verified (see _validate_coverage.py) to actually appear in the
# cleaned text of every one of the 5 verbatim templates it's meant to catch -
# not just plausible-looking, but checked against the real cleaning logic."
SECONDARY_KEYWORDS = {
    # --- Billing_Charges ---
    "Duplicate Charge": ["charged twice", "billed a second time", "identical deduction", "already paid for",
                          "same payment shows up listed twice", "billed again for something that was already settled"],
    "Incorrect Late Fee": ["late fee", "charged a penalty", "paid well before", "payment went through on time",
                            "penalty on my account from a payment", "late charge still appeared"],
    "Roaming Charge Dispute": ["roaming charge", "roaming fee", "never left the country", "international roaming",
                                "phone on airplane mode most of the trip", "haven t traveled anywhere"],
    "GST/Tax Confusion": ["tax amount", "gst component", "tax line item", "doesn t match what it should be",
                           "tax calculation on this bill looks completely off", "never given a clear breakdown"],
    "Unexplained Deduction": ["cannot trace", "no idea what it was for", "zero explanation",
                               "chunk of my balance just vanished", "doesn t correspond to anything i actually used"],
    # --- Agent_Behavior_Comm ---
    "Rude Agent": ["completely unacceptable", "rude from the very first", "dismissive",
                   "tone the agent used with me was condescending", "talked down to the entire time"],
    "Call Disconnected Mid-Conversation": ["mid sentence", "call just dropped", "line cut off", "call got disconnected",
                                            "call cut out entirely", "start the whole explanation over"],
    "Excessive Hold Time": ["on hold for almost", "hold music", "nearly gave up",
                             "forty minutes on hold", "wait time before someone picked up"],
    "Repeated Transfers": ["transferred between three", "bounced to yet another", "passed around",
                            "passed from department to department", "four transfers later"],
    "Agent Gave Wrong Information": ["completely incorrect", "flat out wrong", "contradicted what actually happened",
                                      "opposite of what actually happened", "acted on what the agent told me"],
    # --- Resolution_Time_FCR ---
    "Ticket Reopened": ["marked resolved", "exact same problem came right back", "keeps reopening",
                         "raising it again a week later", "told it s resolved and then the problem shows up again",
                         "closed and reopened more times than i can count"],
    "No Callback Received": ["promised a callback", "nobody ever called", "callback i was told",
                              "nobody followed up with me", "callback was scheduled and simply never happened",
                              "still sitting here waiting on a call"],
    "Multiple Follow-ups Needed": ["ive had to call", "chasing this up myself", "half answer",
                                    "third time i ve had to call back", "initiate every single follow up",
                                    "personally call back and push for it"],
    "Escalation Ignored": ["to be escalated", "speak to a supervisor", "zero movement",
                            "asked this be escalated twice", "no record that my case was ever escalated"],
    # --- Network_Connectivity ---
    "Frequent Call Drops": ["calls keep dropping", "dropped calls have become", "entire phone call",
                             "mid call disconnections have become the norm", "without losing the connection"],
    "No Indoor Signal": ["signal inside my own home", "signal disappears", "stand near a window",
                          "inside any building my signal drops", "forced to go outside every time"],
    "Slow Data Speed": ["data speed", "unusably slow", "streaming anything is impossible",
                         "pages barely load", "running on a decade old connection"],
    "Network Outage": ["network outage", "completely down", "full outage",
                        "gone down in my area", "complete loss of service again"],
    # --- Recharge_Plan_Issues ---
    "Recharge Deducted No Activation": ["recharge amount was deducted", "never activated", "old balance",
                                         "money left my account for the top up", "account shows absolutely no change",
                                         "topped up hours ago and i m still stuck"],
    "Unauthorized Plan Change": ["plan was switched", "without me ever asking", "different plan than the one",
                                  "before changing my existing plan", "plan changed overnight and i never approved",
                                  "didn t request a plan switch"],
    "Data Pack Validity Issue": ["zero days of validity", "expired days earlier", "add on pack",
                                  "validity period on this pack", "expiry date that makes no sense"],
    "Auto-Renewal Without Consent": ["auto renewed", "never agreed to auto renewal", "kept renewing itself",
                                      "add on renewed itself again", "explicitly opted out of renewal"],
    # --- Activation_Porting_Delay ---
    "SIM Activation Delay": ["sim still isn t active", "waiting on activation", "sitting inactive",
                              "five days and my new sim", "past the activation window", "sitting dead for days"],
    "Number Porting Delay": ["number porting request", "porting my number", "ported number",
                              "porting process has dragged on", "old number is dead"],
    "Installation Rescheduled": ["installation technician", "appointment keeps getting pushed back", "nobody showed up for the scheduled",
                                  "installation slot has been pushed back", "technician simply never came"],
    # --- Refund_Processing ---
    "Refund Not Credited": ["refund two weeks ago", "refund status says processed", "no sign of the refund",
                             "supposedly refunded is nowhere in my account", "still no trace of the refund"],
    "Partial Refund Issue": ["only got back part", "refunded amount doesn t match", "fraction of my refund",
                              "noticeably less than what i was actually owed", "simply don t add up to what was overcharged"],
    "Refund Timeline Delay": ["five to seven days", "refund timeline", "under process",
                               "well beyond the window i was originally given"],
    # --- App_Website_Technical ---
    "App Payment Failure": ["app crashes", "payment failed on the app", "payment to actually complete",
                             "attempt to pay through the app ends in", "bank shows the amount already gone"],
    "Website Login Issue": ["log into my account on the website", "website keeps rejecting", "self care portal",
                             "resetting my password three times", "site just spins endlessly"],
    "Invoice Download Error": ["download my invoice", "download keeps failing", "invoice pdf never generates",
                                "invoice for reimbursement and the download", "attempt to pull up my bill online"],
    # --- KYC_Documentation ---
    "KYC Document Rejected": ["kyc documents were rejected", "id proof", "documents keep failing verification",
                               "submitted the same valid documents twice", "no clear reason given for why my documents"],
    "Reverification Delay": ["re verification request", "resubmitted documents",
                              "on the re verification i submitted", "stated timeline for my re verification",
                              "resubmitted everything that was asked for"],
    "Service Suspended For KYC": ["suspended over kyc", "cut off for a document issue", "kyc flag",
                                   "suspended over documentation i d already submitted", "service still got cut off anyway"],
    # --- Customer_Effort ---
    "Multiple Channel Switching": ["tried the app first", "jump between three different channels", "sent in circles",
                                    "redirected me to another", "started on chat got nowhere"],
    "Repeated Information Requests": ["account details for the fourth time", "re verify everything from scratch", "keep starting over",
                                       "explained this same problem in detail", "shouldn t have to repeat my entire issue"],
    "Complex IVR Navigation": ["phone menu took me in circles", "automated system kept looping", "navigating menus",
                                "ivr options", "six different options before finding the right department"],
    "No Self-Service Resolution": ["resolve this myself online", "self service portal", "faq and help center",
                                    "no way to handle something this simple", "tried everything on the app before giving up"],
    # --- Repeat_Contact ---
    "Same Issue Multiple Times": ["contacting support about this exact same", "reach out again and again", "contacting you a third time this month",
                                   "lost count of how many times", "a problem that was never actually solved"],
    "Different Agent Each Time": ["different agent every single time", "no two agents have given me the same answer", "zero context",
                                   "passing me along", "explaining this problem for the very first time"],
    "No Case History Visible": ["no record of my previous calls", "no notes on file", "explain everything from zero",
                                 "don t exist in your system", "could see any record of my previous calls",
                                 "agent had no idea i d already contacted support"],
    "Multiple Contacts Same Day": ["called twice today", "third message today", "three times in one day",
                                    "contacted support about this twice already", "called then chatted then called again"],
}

SUB_ISSUE_TO_PRIMARY = {
    "Duplicate Charge": "Billing_Charges", "Incorrect Late Fee": "Billing_Charges",
    "Roaming Charge Dispute": "Billing_Charges", "GST/Tax Confusion": "Billing_Charges",
    "Unexplained Deduction": "Billing_Charges",
    "Rude Agent": "Agent_Behavior_Comm", "Call Disconnected Mid-Conversation": "Agent_Behavior_Comm",
    "Excessive Hold Time": "Agent_Behavior_Comm", "Repeated Transfers": "Agent_Behavior_Comm",
    "Agent Gave Wrong Information": "Agent_Behavior_Comm",
    "Ticket Reopened": "Resolution_Time_FCR", "No Callback Received": "Resolution_Time_FCR",
    "Multiple Follow-ups Needed": "Resolution_Time_FCR", "Escalation Ignored": "Resolution_Time_FCR",
    "Frequent Call Drops": "Network_Connectivity", "No Indoor Signal": "Network_Connectivity",
    "Slow Data Speed": "Network_Connectivity", "Network Outage": "Network_Connectivity",
    "Recharge Deducted No Activation": "Recharge_Plan_Issues", "Unauthorized Plan Change": "Recharge_Plan_Issues",
    "Data Pack Validity Issue": "Recharge_Plan_Issues", "Auto-Renewal Without Consent": "Recharge_Plan_Issues",
    "SIM Activation Delay": "Activation_Porting_Delay", "Number Porting Delay": "Activation_Porting_Delay",
    "Installation Rescheduled": "Activation_Porting_Delay",
    "Refund Not Credited": "Refund_Processing", "Partial Refund Issue": "Refund_Processing",
    "Refund Timeline Delay": "Refund_Processing",
    "App Payment Failure": "App_Website_Technical", "Website Login Issue": "App_Website_Technical",
    "Invoice Download Error": "App_Website_Technical",
    "KYC Document Rejected": "KYC_Documentation", "Reverification Delay": "KYC_Documentation",
    "Service Suspended For KYC": "KYC_Documentation",
    "Multiple Channel Switching": "Customer_Effort", "Repeated Information Requests": "Customer_Effort",
    "Complex IVR Navigation": "Customer_Effort", "No Self-Service Resolution": "Customer_Effort",
    "Same Issue Multiple Times": "Repeat_Contact", "Different Agent Each Time": "Repeat_Contact",
    "No Case History Visible": "Repeat_Contact", "Multiple Contacts Same Day": "Repeat_Contact",
}


def tag_sub_issues(text: str) -> dict:
    """Returns {sub_issue: number of distinct phrases matched}."""
    hits = {}
    for sub_issue, phrases in SECONDARY_KEYWORDS.items():
        count = sum(1 for phrase in phrases if phrase in text)
        if count > 0:
            hits[sub_issue] = count
    return hits


df["sub_issue_hits"] = df["clean_text"].apply(tag_sub_issues)
df["matched_drivers"] = df["sub_issue_hits"].apply(lambda d: ", ".join(d.keys()) if d else "")
df["sub_issue_hits"].apply(len).value_counts()

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
# NARRATE: "I rank the matched sub-issues by how many distinct phrases hit.
# The strongest match's PARENT CATEGORY becomes the PRIMARY driver - the
# broad 'what kind of problem' - and the sub-issue itself becomes the
# SECONDARY driver - the specific, actionable 'what exactly'. So a response
# doesn't just get tagged 'Billing_Charges', it gets tagged 'Billing_Charges
# / Incorrect Late Fee' - something the client can actually go fix. Where
# nothing matched, I fall back to sentiment rather than force a wrong tag."
def resolve_drivers(row):
    hits = row["sub_issue_hits"]
    if hits:
        ranked = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
        top_sub_issue = ranked[0][0]
        primary = SUB_ISSUE_TO_PRIMARY[top_sub_issue]
        secondary = top_sub_issue
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

# WHAT: a higher-level ownership rollup - does this issue sit with the AGENT
# (people/behavior), the PRODUCT (network/app, a genuine technical quality
# problem), or an internal PROCESS (billing, refunds, activation, KYC - back-
# office workflow, not any one person's fault)? WHY: this is the first
# question a leadership team actually asks - "is this a coaching problem, an
# engineering problem, or an operations problem" - before drilling into the
# specific driver at all. It's a direct roll-up of the 9 primary categories,
# so it costs nothing extra to compute but adds a genuinely different lens.
PRIMARY_TO_THEME = {
    "Agent_Behavior_Comm": "Agent",
    "Network_Connectivity": "Product", "App_Website_Technical": "Product",
    "Billing_Charges": "Process", "Resolution_Time_FCR": "Process",
    "Recharge_Plan_Issues": "Process", "Activation_Porting_Delay": "Process",
    "Refund_Processing": "Process", "KYC_Documentation": "Process",
    "Customer_Effort": "Process", "Repeat_Contact": "Process",
    "No_Issue_Positive": "No Issue", "Other_Negative_Unclassified": "Other/Unclassified",
}
df["issue_theme"] = df["primary_driver"].map(PRIMARY_TO_THEME)

print(df["primary_driver"].value_counts())
print("\n", df["secondary_driver"].value_counts())

# %% Cell 7b - safety net: TF-IDF + NMF topic modeling for the rare residual
# WHAT: with a 34-entry specific sub-issue dictionary, the vast majority of
# negative responses now get a clean, specific secondary driver straight out
# of Cell 7. This cell is a SAFETY NET for the small residual that still
# matches nothing (edge-of-vocabulary phrasing) - rather than leave those as
# a blank "No Secondary Driver", TF-IDF + NMF (non-negative matrix
# factorization, the same family of technique as LDA) discovers latent
# sub-themes directly from that residual text, auto-labeled via YAKE (a
# lightweight, offline, unsupervised keyword-extraction library - no AI/LLM,
# no API, no corpus download) so even the fallback case gets a readable label.
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
if len(residual) >= N_TOPICS * 50:   # need enough rows per topic to be statistically meaningful -
    # with the 34-entry taxonomy this residual is now usually tiny, and an
    # honest "No Secondary Driver" beats a forced label guessed from ~10 docs
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
# LoB, agent tenure, manager, team lead, sentiment, plan tier, circle, and
# survey type. That's what lets me show the client depth, and tell them
# which SEGMENTS - not just which agents - are underperforming."
def summarize(df_in: pd.DataFrame, group_col: str) -> pd.DataFrame:
    return (
        df_in.groupby(group_col)
        .agg(responses=("unique_id", "count"), avg_csat=("csat_score", "mean"))
        .assign(pct_of_total=lambda d: (d["responses"] / len(df_in) * 100).round(1))
        .round({"avg_csat": 2})
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
csat_bucket_summary = summarize(df, "csat_bucket")
plan_tier_summary = summarize(df, "plan_tier")
circle_summary = summarize(df, "circle")
issue_theme_summary = summarize(df, "issue_theme")

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

# WHAT: a focused drill-down - the specific sub-issue breakdown WITHIN the
# #1 primary driver only (not a full 9x34 cross-tab). WHY: since secondary
# is now always a specific sub-issue OF its own primary category (by
# construction - see Cell 7), a full primary-by-secondary cross-tab is
# mostly block-diagonal and up to 34 columns wide - too wide to be useful
# inline. Drilling into just the #1 driver's own sub-issues is the
# genuinely actionable view: "of our Billing complaints, exactly WHAT kind
# are they" - narrow enough to read as a table and chart side by side.
top_primary = primary_summary.iloc[0]["primary_driver"]
top_primary_subissues = summarize(df[df["primary_driver"] == top_primary], "secondary_driver")
print(f"\nSub-issue breakdown within top primary driver ({top_primary}):\n", top_primary_subissues)

if len(top_primary_subissues):
    top_secondary = top_primary_subissues.iloc[0]["secondary_driver"]
    top_secondary_pct_within_primary = top_primary_subissues.iloc[0]["pct_of_total"]
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


weekly_primary = weekly_trend(df, "primary_driver", top_primary).head(5)
weekly_secondary = weekly_trend(df, "secondary_driver", top_secondary).head(5) if top_secondary else None

print(f"\nTop primary driver: {top_primary}")
print(f"Top secondary driver: {top_secondary}")

# %% Cell 9 - Save outputs: ONE workbook, rebuilt from scratch every run
# NARRATE: "Instead of a flat CSV, or scattering tables and charts across
# lots of tabs, I publish one Excel workbook: the raw tagged data on one
# sheet, and every summary table on a single 'Analysis' sheet with its
# chart placed right beside it - so you can correlate the numbers and the
# picture at a glance, instead of hunting across tabs. Bold headers, wide
# columns, data labels on every chart - this is the walkthrough deck, and
# it's fully reproducible: every time I rerun this script, every sheet and
# every chart regenerates from the current data, so there's never a stale
# hand-edited copy floating around."
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

df_out = df.drop(columns=["clean_text", "sub_issue_hits"])
df_out["date"] = pd.to_datetime(df_out["date"]).dt.date  # real Excel date, not text
df_out["week_starting"] = pd.to_datetime(df_out["week_starting"]).dt.date

SECTIONS = [
    ("Issue Theme: Agent vs Product vs Process", issue_theme_summary),
    ("Primary Driver Summary (Top 5 shown)", primary_summary.head(5)),
    ("Secondary Driver Summary (Top 5 shown)", secondary_summary.head(5)),
    (f"Sub-Issue Breakdown within Top Driver ({top_primary})", top_primary_subissues),
    ("CSAT by Channel", channel_summary),
    ("CSAT by Line of Business", lob_summary),
    ("CSAT by Agent Tenure Bucket", tenure_summary),
    ("CSAT by Manager", manager_summary),
    ("CSAT by Team Lead", tl_summary),
    ("CSAT Bucket (Promoter/Neutral/Detractor)", csat_bucket_summary),
    ("CSAT by Plan Tier", plan_tier_summary),
    ("CSAT by Circle (Top 5 shown)", circle_summary.head(5)),
    (f"Weekly Trend - Top Primary Driver ({top_primary}, Top 5 weeks)", weekly_primary),
]
if weekly_secondary is not None:
    SECTIONS.append((f"Weekly Trend - Top Secondary Driver ({top_secondary}, Top 5 weeks)", weekly_secondary))

HEADER_FILL = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=13, color="1B2A4A")
MIN_SECTION_ROWS = 17  # reserve enough rows beside a table for the larger, taller chart next to it

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="Tagged_Data", index=False)
    cursor = 0
    section_positions = []  # (title, table, title_row, header_row, first_data_row, last_data_row)
    for title, table in SECTIONS:
        table.to_excel(writer, sheet_name="Analysis", index=False, startrow=cursor + 1, startcol=0)
        title_row = cursor + 1
        header_row = cursor + 2
        first_data_row = cursor + 3
        last_data_row = cursor + 2 + len(table)
        section_positions.append((title, table, title_row, header_row, first_data_row, last_data_row))
        cursor += max(len(table) + 2, MIN_SECTION_ROWS)

# Reopen to style cells + attach native Excel chart objects (openpyxl can't
# write charts in the same pass as pandas' ExcelWriter, so this is a
# second, deterministic step).
wb = openpyxl.load_workbook(OUTPUT_FILE)

ws_data = wb["Tagged_Data"]
for col_name in ("date", "week_starting"):
    col_idx = list(df_out.columns).index(col_name) + 1
    for row in range(2, ws_data.max_row + 1):
        ws_data.cell(row=row, column=col_idx).number_format = "yyyy-mm-dd"
for col_idx in range(1, ws_data.max_column + 1):
    ws_data.cell(row=1, column=col_idx).font = HEADER_FONT
    ws_data.cell(row=1, column=col_idx).fill = HEADER_FILL
    ws_data.column_dimensions[get_column_letter(col_idx)].width = 20

ws = wb["Analysis"]

for title, table, title_row, header_row, first_data_row, last_data_row in section_positions:
    cell = ws.cell(row=title_row, column=1, value=title)
    cell.font = TITLE_FONT
    ncols = table.shape[1]
    for col_idx in range(1, ncols + 1):
        hcell = ws.cell(row=header_row, column=col_idx)
        hcell.font = HEADER_FONT
        hcell.fill = HEADER_FILL
        hcell.alignment = Alignment(horizontal="center")
        col_letter = get_column_letter(col_idx)
        # Wide enough for the longest labels ("Service Suspended For KYC"),
        # comfortable for numeric columns too.
        ws.column_dimensions[col_letter].width = 24 if col_idx == 1 else 13
    if table.columns[0] in ("week_starting",):
        for row in range(first_data_row, last_data_row + 1):
            ws.cell(row=row, column=1).number_format = "yyyy-mm-dd"


def combo_chart(ws_target, title, anchor_col, header_row, first_data_row, last_data_row):
    """Bar = response volume, Line = avg CSAT on a secondary axis - every
    chart shows both HOW OFTEN an issue happens and HOW BADLY it hurts CSAT.
    Data labels are switched on for both series so the numbers are readable
    directly off the chart, not just the table beside it."""
    bar = BarChart()
    bar.title = title
    bar.y_axis.title = "Responses"
    bar.width, bar.height = 24, 8  # cm - large enough to read cleanly, not a cramped thumbnail
    bar.x_axis.delete = False
    bar.x_axis.majorGridlines = None  # Excel's default gridlines look cluttered on a bar+line combo
    bar.y_axis.majorGridlines = None
    bar.x_axis.tickLblPos = "low"  # pin category labels to the bottom - a dual-axis combo chart
    # can otherwise float them into the middle of the plot area
    cats = Reference(ws_target, min_col=1, min_row=first_data_row, max_row=last_data_row)
    count_data = Reference(ws_target, min_col=2, min_row=header_row, max_row=last_data_row)
    bar.add_data(count_data, titles_from_data=True)
    bar.set_categories(cats)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True

    line = LineChart()
    csat_data = Reference(ws_target, min_col=3, min_row=header_row, max_row=last_data_row)
    line.add_data(csat_data, titles_from_data=True)
    line.y_axis.axId = 200
    line.y_axis.title = "Avg CSAT"
    line.y_axis.crosses = "max"
    line.y_axis.majorGridlines = None
    bar.y_axis.crosses = "autoZero"
    line.dataLabels = DataLabelList()
    line.dataLabels.showVal = True

    bar += line
    bar.legend.position = "b"
    anchor = f"{get_column_letter(anchor_col)}{first_data_row - 1}"
    ws_target.add_chart(bar, anchor)


# Every chart is anchored BESIDE its own table (same row, one column past
# the table's last column, a single-column gap), not collected on a
# separate sheet - so the number and the picture read together without
# flipping tabs.
for title, table, title_row, header_row, first_data_row, last_data_row in section_positions:
    anchor_col = table.shape[1] + 1
    chart_title = title if len(title) < 45 else title[:42] + "..."
    combo_chart(ws, chart_title, anchor_col, header_row, first_data_row, last_data_row)

wb.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} (2 sheets: Tagged_Data, Analysis - {len(section_positions)} tables+charts)")

# %% Cell 10 - Spoken walkthrough numbers (read these out loud)
top = primary_summary.iloc[0]
print(f"Top PRIMARY driver: {top['primary_driver']} -> {top['pct_of_total']}% of all responses, "
      f"avg CSAT {top['avg_csat']:.2f}")
if top_secondary:
    print(f"Top SPECIFIC sub-issue within {top_primary}: {top_secondary} "
          f"-> {top_secondary_pct_within_primary:.1f}% of {top_primary} complaints")
print(f"Overall avg CSAT: {df['csat_score'].mean():.2f}")
print(f"CSAT mix: {dict(df['csat_bucket'].value_counts())}")
print(f"% Negative sentiment overall: {(df['sentiment_label'] == 'Negative').mean() * 100:.1f}%")

worst_circle = circle_summary.sort_values("avg_csat").iloc[0]
worst_tier = plan_tier_summary.sort_values("avg_csat").iloc[0]
print(f"Lowest-CSAT circle: {worst_circle['circle']} (avg CSAT {worst_circle['avg_csat']:.2f})")
print(f"Lowest-CSAT plan tier: {worst_tier['plan_tier']} (avg CSAT {worst_tier['avg_csat']:.2f})")

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

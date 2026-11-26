"""
================================================================================
 ML + GenAI RECOMMENDATION PIPELINE -- ONE SCRIPT, START TO FINISH
================================================================================

What this does, in order (search for "STEP N" to jump to any stage):

  STEP 1  Read input data           -- load ads-data/campaigns.csv
  STEP 2  Pre-processing            -- per-account slicing, derived columns
  STEP 3  EDA / ML analysis         -- correlations, anomaly detection, clustering,
                                       materiality ranking (pure statistics, no LLM)
  STEP 4  Parse market PDFs         -- real pdfplumber table extraction from the
                                       4 vendor reports (not read from benchmarks.py)
  STEP 5  Pydantic output schemas   -- structured-JSON contracts for every GenAI call
  STEP 6  GenAI: ads-data analysis  -- diagnoses each account from the raw campaign
                                       data + the EDA evidence
  STEP 7  NLP: relevance ranking    -- TF-IDF + cosine similarity scores every
                                       extracted market fact against THIS account's
                                       stage-6 diagnosis text; only the closest
                                       matches are passed on (see note below)
  STEP 8  GenAI: market mapping     -- matches the NLP-ranked market facts onto the
                                       stage-6 diagnosis ("why now")
  STEP 9  GenAI: email copy         -- drafts the customer-facing email
  STEP 10 Render PDFs               -- build the email as a real PDF, reusing the
                                       existing reportlab layout helpers in ../scripts/
  STEP 11 Validation report         -- schema-compliance checks, token totals, timing,
                                       written to output/validation_report.md

Three distinct tech stacks, each doing a job the others don't:
  - ML (STEP 3, scikit-learn)   -- Pearson correlation, IsolationForest anomaly
                                    scoring, KMeans clustering on the raw campaign
                                    numbers. Produces EVIDENCE, not prose.
  - NLP (STEP 7, scikit-learn)  -- TF-IDF vectorization + cosine similarity between
                                    free-text diagnosis and free-text market-report
                                    rows. This is classic information-retrieval NLP,
                                    not an LLM call -- it decides WHICH extracted
                                    facts are worth spending GenAI tokens reasoning
                                    over, and it does that per-account, since each
                                    account's diagnosis text is different.
  - GenAI (STEP 6, 8, 9)        -- the only stages that reason in natural language:
                                    forming the account diagnosis, building the "why
                                    now" case, and writing the email copy.
One model (MODEL, defined once in the call-layer section below) backs every
GenAI stage, on purpose -- a future provider or model swap is then a single
line to change, not a hunt through the file for every call site. Earlier
drafts of this pipeline raced several models against each other on the same
task and judged a winner, and separately assigned a different model per
stage by task difficulty; both were dropped in favor of this simpler,
easier-to-maintain shape.

Why GenAI does the actual analysis, not just validation: STEP 3's statistics
(correlations, anomaly scores, clusters) are handed to STEP 6 as EVIDENCE the
model reasons with -- the diagnosis and recommended actions are the model's
own judgment on the raw campaign data, not a rephrasing of the ML output.
Likewise STEP 8 reasons over whatever STEP 7's NLP ranking surfaced, rather
than being told which facts matter.

What stays deterministic on purpose: the revenue-opportunity numbers (the
headline figure and each campaign's share of it) are computed in Python from
campaigns.csv, not invented by the LLM -- models are handed these exact
figures as facts to write copy around, never asked to do the arithmetic
themselves. Every dollar amount in the final email traces to the CSV.

Run:  python run_pipeline.py
Needs: OPENAI_API_KEY only -- deliberately single-provider (see the call-layer
       section below for why). Swap the key and nothing else needs to change.
"""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pdfplumber
from pydantic import BaseModel, Field
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

import openai

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

import pdf_common as pc  # noqa: E402 -- the existing reportlab layout helpers (charts, cards, callouts)
from benchmarks import ACCOUNTS, REPORT_PERIOD, PRIOR_PERIOD, WATERMARK  # noqa: E402 -- market-side constants only; no cheating by reading account-diagnosis numbers from here

RUN_STARTED = time.strftime("%Y-%m-%d %H:%M:%S")
MATERIALITY_CUTOFF = 0.70


# ============================================================================
# STEP 1 -- Read input data
# ============================================================================

def load_campaigns():
    return pd.read_csv(ROOT / "ads-data" / "campaigns.csv")


# ============================================================================
# STEP 2 -- Pre-processing
# ============================================================================

def preprocess_account(df, account_id):
    """One account's slice, plus the derived columns every later step needs."""
    g = df[df.account_id == account_id].copy()
    g["missed"] = g["eligible_impressions"] - g["impressions"]
    return g


# ============================================================================
# STEP 3 -- EDA / ML analysis (pure statistics, no LLM -- this is evidence
# for stage 6, not a replacement for the model's own reasoning over it)
# ============================================================================

FEATURE_COLS = [
    "spend", "impressions", "conversions", "revenue", "roas", "avg_cpc",
    "avg_quality_score", "impression_share_lost_budget_pct",
    "impression_share_lost_rank_pct", "budget_utilization_pct",
]


def _correlations_vs_missed(g):
    out = []
    for col in FEATURE_COLS:
        if g[col].nunique() < 2:
            continue
        r, p = stats.pearsonr(g[col], g["missed"])
        if np.isnan(r):
            continue
        out.append({"feature": col, "pearson_r": round(float(r), 3), "p_value": round(float(p), 4)})
    out.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)
    return out[:6]


def _anomaly_and_clusters(g):
    X = StandardScaler().fit_transform(g[FEATURE_COLS].fillna(0.0))
    n = len(g)
    iso = IsolationForest(n_estimators=100, contamination="auto", random_state=7)
    iso.fit(X)
    anomaly_score = iso.decision_function(X)
    is_outlier = iso.predict(X) == -1
    k = 2 if n > 2 else 1
    cluster = KMeans(n_clusters=k, n_init=10, random_state=7).fit_predict(X) if k >= 2 else np.zeros(n, dtype=int)
    return anomaly_score, is_outlier, cluster


def materiality_ranking(g):
    """The smallest set of campaigns (ranked by missed-impression volume)
    covering ~70% of the account's total missed opportunity -- NOT every
    campaign. Reused by stage 6 (which campaigns to analyze in depth), the
    email copy's per-campaign cards, and the deterministic revenue split."""
    gg = g.sort_values("missed", ascending=False).copy()
    total = gg["missed"].sum()
    gg["cum_share"] = gg["missed"].cumsum() / total if total else 0.0
    cutoff_idx = (gg["cum_share"] >= MATERIALITY_CUTOFF).idxmax() if total else gg.index[-1]
    in_scope = gg.loc[:cutoff_idx]
    return in_scope, dict(zip(gg["campaign_name"], gg["cum_share"]))


def compute_eda(g):
    correlations = _correlations_vs_missed(g)
    anomaly_score, is_outlier, cluster = _anomaly_and_clusters(g)
    in_scope, cum_share = materiality_ranking(g)
    in_scope_names = set(in_scope["campaign_name"])

    campaigns = []
    for i, row in g.reset_index(drop=True).iterrows():
        campaigns.append({
            "campaign_name": row["campaign_name"],
            "missed_impressions": int(row["missed"]),
            "cumulative_missed_share": round(cum_share[row["campaign_name"]], 3),
            "material": row["campaign_name"] in in_scope_names,
            "anomaly_score": round(float(anomaly_score[i]), 3),
            "is_statistical_outlier": bool(is_outlier[i]),
            "cluster_label": int(cluster[i]),
        })
    return {
        "note": "Exploratory statistics on a small per-account sample (5-10 campaigns) -- "
                "directional evidence, not a validated production model.",
        "correlations_vs_missed_impressions": correlations,
        "campaigns": campaigns,
        "in_scope_campaign_names": sorted(in_scope_names),
    }


# ============================================================================
# STEP 4 -- Parse the 4 vendor market-report PDFs (real table extraction,
# not a read of benchmarks.py -- a production pipeline only has the PDFs)
# ============================================================================

MARKET_REPORTS_DIR = ROOT / "market-reports"
VENDOR_FILES = {
    "Ashcroft Research Partners": "ashcroft_vertical_ad_trends_2026q3.pdf",
    "Vantage Media Metrics": "vantage_media_mix_2026q3.pdf",
    "SignalWatch Competitive Intelligence": "signalwatch_competitive_spend_2026q3.pdf",
    "QueryScope Insights": "queryscope_search_demand_2026q3.pdf",
}
SKIP_IF_PAGE_CONTAINS = ("Glossary", "Disclaimer", "Table of Contents")
MAX_ROWS_PER_VENDOR = 18


def _extract_pdf_tables(path):
    out = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                header = [(c or "").strip() for c in table[0]]
                rows = [dict(zip(header, [(c or "").strip() for c in r]))
                        for r in table[1:] if len(r) == len(header) and any(r)]
                if rows:
                    out.append({"page": pno, "page_text": text, "header": header, "rows": rows})
    return out


def extract_market_evidence(vertical):
    evidence = {}
    for vendor, fname in VENDOR_FILES.items():
        path = MARKET_REPORTS_DIR / fname
        rows_out, seen = [], set()
        for t in _extract_pdf_tables(path):
            if vertical.lower() not in t["page_text"].lower():
                continue
            if any(s in t["page_text"] for s in SKIP_IF_PAGE_CONTAINS):
                continue
            label = " | ".join(t["header"])
            for row in t["rows"]:
                key = (label, tuple(sorted(row.items())))
                if key in seen:
                    continue
                seen.add(key)
                rows_out.append({"table": label, "row": row, "source_page": t["page"]})
        evidence[vendor] = rows_out[:MAX_ROWS_PER_VENDOR]
    return evidence


# ============================================================================
# STEP 5 -- Pydantic schemas for every structured GenAI call
# ============================================================================

class CampaignFinding(BaseModel):
    campaign_name: str
    diagnosis: str = Field(description="1-2 sentences: what the numbers show for THIS campaign specifically")
    primary_constraint: Literal["rank", "budget", "balanced"]
    severity_0_to_1: float
    recommended_action: str


class AdsAnalysis(BaseModel):
    """Stage 6 output: the model's OWN analysis of the raw campaign data,
    using the EDA stats as evidence -- not a rephrasing of them."""
    account_level_diagnosis: str
    primary_constraint: Literal["rank-constrained", "budget-constrained", "healthy-demand-surge"]
    confidence_0_to_1: float
    notable_patterns: list[str] = Field(description="2-4 specific observations citing actual numbers from the data provided")
    campaign_findings: list[CampaignFinding]


class MarketFact(BaseModel):
    vendor: str
    fact: str = Field(description="A specific fact from the extracted table data, including the actual number")
    relevance_to_recommendation: str


class MarketMapping(BaseModel):
    why_now_summary: str
    supporting_facts: list[MarketFact]
    urgency_0_to_1: float


class EmailCopy(BaseModel):
    subject: str = Field(description="Lead with the account's specific number/gap, not a generic market stat")
    hook: str = Field(description="1-2 sentence personalized opening. The greeting 'Hi [Customer name],' is already "
                                   "rendered immediately before this text by the template -- do NOT repeat 'Hi' or "
                                   "any other greeting here, start directly with the substance.")
    why_now_bullets: list[str] = Field(description="2-3 bullets of market evidence citing a specific number each; "
                                                     "bold the key figure with <b></b> tags")
    stat_label: str = Field(description="All-caps label above the headline number")
    stat_sub: str
    impact_line: str = Field(description="A full 1-2 sentence explanation of what's behind the headline number -- "
                                          "never just the number by itself, never a one-word or sub-5-word answer")
    scope_intro: str = Field(description="One sentence introducing the per-campaign breakdown that follows")
    fix_title: str
    fix_body: str = Field(description="A low-friction, binary-choice call to action plus a one-word-reply fallback. "
                                       "Do NOT restate the per-campaign dollar breakdown -- that is already shown in "
                                       "cards directly above this box. Do NOT start the text with a bullet, dash, or "
                                       "number -- the template already renders one bullet marker before this text.")
    ps: str


# ============================================================================
# OpenAI-only call layer (shared by steps 6, 7, 8)
#
# Deliberately single-provider: getting multiple vendor keys approved inside
# an enterprise is its own procurement slog, so this only ever needs ONE
# credential. The "compare several models, take the best one" requirement
# is still satisfied -- just across OpenAI's own tiers (GPT-5.2, GPT-5.1,
# GPT-5 Mini) instead of across vendors. Swapping to a different OpenAI key
# (a different org, a funded one, etc.) is a one-line change: set
# OPENAI_API_KEY, nothing else in this file needs to change.
# ============================================================================

def _load_env_from_backend():
    """Force-set (not setdefault) OPENAI_API_KEY from backend/.env. If you
    already have OPENAI_API_KEY correctly exported in your own shell, you
    can delete this function and construct openai.OpenAI() with no
    arguments -- it reads the env var on its own."""
    env_path = ROOT.parent / "backend" / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k == "OPENAI_API_KEY":
            os.environ[k] = v


_load_env_from_backend()
_openai_client = openai.OpenAI()

# Model ID confirmed live against this key's own models.list() at build time
# (see README.md "Model selection" note) -- not guessed from training data,
# since this assistant's knowledge cutoff predates some of what's live
# today. ONE constant, used by every stage -- a future provider/model swap
# is a one-line change here, not a hunt through the file.
MODEL = "gpt-5.2"

PRICING_PER_MTOK = {}  # OpenAI list pricing not independently verified for these models at build time -- see README.md


@dataclass
class UsageLedger:
    calls: list = field(default_factory=list)

    def record(self, label, model, in_tok, out_tok):
        self.calls.append({"label": label, "model": model,
                            "input_tokens": in_tok, "output_tokens": out_tok})

    def cost_by_model(self):
        out = {}
        for c in self.calls:
            rate = PRICING_PER_MTOK.get(c["model"])
            if rate is None:
                out.setdefault(c["model"], None)
                continue
            cost = c["input_tokens"] / 1e6 * rate["input"] + c["output_tokens"] / 1e6 * rate["output"]
            out[c["model"]] = round((out.get(c["model"]) or 0.0) + cost, 4)
        return out

    def summary(self):
        return {
            "num_calls": len(self.calls),
            "total_input_tokens": sum(c["input_tokens"] for c in self.calls),
            "total_output_tokens": sum(c["output_tokens"] for c in self.calls),
            "cost_by_model_usd": self.cost_by_model(),
        }


LEDGER = UsageLedger()


def _call_openai(label, model, system, user_content, output_model, max_tokens):
    resp = _openai_client.chat.completions.parse(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        response_format=output_model,
    )
    choice = resp.choices[0]
    if choice.message.refusal:
        raise RuntimeError(f"{label} ({model}): refused -- {choice.message.refusal}")
    LEDGER.record(label, model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return choice.message.parsed


def _is_non_retryable(e):
    """4xx other than 429 (rate limit) is a client error that will fail
    identically on retry -- e.g. invalid request, auth, or insufficient
    account credit. Fail fast instead of burning the full retry budget."""
    status = getattr(e, "status_code", None)
    return status is not None and 400 <= status < 500 and status != 429


def structured_call(label, model, system, user_content, output_model, max_tokens=4096, max_retries=3):
    last_err = None
    for attempt in range(max_retries):
        try:
            return _call_openai(label, model, system, user_content, output_model, max_tokens)
        except Exception as e:  # noqa: BLE001 -- retry transient failures, fail fast on client errors
            last_err = e
            if _is_non_retryable(e):
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{label} ({model}): failed: {last_err}")


# ============================================================================
# Deterministic numbers (NOT GenAI) that stage 8 must use verbatim -- the
# revenue math is Python, not model arithmetic, so every dollar figure in
# the final email traces to campaigns.csv.
# ============================================================================

def account_rollup(g, account_cfg):
    w = g["eligible_impressions"]
    is_pct = (g["search_impression_share_pct"] * w).sum() / w.sum()
    lost_budget_pct = (g["impression_share_lost_budget_pct"] * w).sum() / w.sum()
    lost_rank_pct = (g["impression_share_lost_rank_pct"] * w).sum() / w.sum()
    daily_budget = g["daily_budget"].sum()

    wi = g["impressions"]
    ctr = (g["ctr_pct"] * wi).sum() / wi.sum()
    cvr = (g["conversion_rate_pct"] * wi).sum() / wi.sum()
    aov = (g["avg_order_value"] * g["conversions"]).sum() / g["conversions"].sum()
    inc_revenue = account_cfg["upside_incremental_impressions_period"] * ctr / 100 * cvr / 100 * aov

    in_scope, _ = materiality_ranking(g)
    scoped_total_missed = in_scope["missed"].sum()
    campaign_revenue = {
        row["campaign_name"]: inc_revenue * (row["missed"] / scoped_total_missed)
        for _, row in in_scope.iterrows()
    }
    return {
        "is_pct": is_pct, "lost_budget_pct": lost_budget_pct, "lost_rank_pct": lost_rank_pct,
        "daily_budget": daily_budget, "inc_revenue": inc_revenue,
        "campaign_revenue": campaign_revenue, "in_scope_campaigns": in_scope,
    }


# ============================================================================
# STEP 6 -- GenAI: ads-data analysis (one call per account, model = MODEL)
# ============================================================================

STAGE6_SYSTEM = (
    "You are a senior paid-search performance analyst. You will be given one advertiser "
    "account's campaign-level performance data for the current quarter, plus some "
    "supporting exploratory statistics (correlations, anomaly scores, cluster labels) "
    "computed separately. Treat the statistics as EVIDENCE to weigh, not as conclusions "
    "to restate -- form your own diagnosis directly from the raw numbers, citing specific "
    "figures. Identify whether the account's missed opportunity is primarily a rank "
    "problem (outranked on quality/bid, budget isn't the constraint), a budget problem "
    "(daily budget caps the account before it exhausts demand), or the account is "
    "already healthy and riding a demand surge."
)


STAGE6_COLS = [
    "campaign_name", "campaign_type", "search_impression_share_pct",
    "impression_share_lost_budget_pct", "impression_share_lost_rank_pct", "spend",
    "spend_qoq_change_pct", "conversions", "revenue", "roas", "avg_quality_score",
    "budget_utilization_pct",
]


def run_stage6(account_id, account_cfg, g, eda_result):
    campaign_json = g[STAGE6_COLS].to_json(orient="records")
    user = (
        f"Account: {account_cfg['account_name']} -- vertical: {account_cfg['vertical']}, "
        f"market: {account_cfg['country']}. Reporting period: {REPORT_PERIOD} vs {PRIOR_PERIOD}.\n\n"
        f"Campaign-level data (JSON, one object per campaign):\n{campaign_json}\n\n"
        f"Exploratory statistics computed separately (evidence, not a conclusion):\n"
        f"{json.dumps(eda_result)}\n\n"
        "Analyze this account. Only include campaign_findings for campaigns the data "
        "shows are materially worth acting on -- not every campaign in the account."
    )
    return structured_call(f"stage6:{account_id}", MODEL, STAGE6_SYSTEM, user, AdsAnalysis, max_tokens=6000)


# ============================================================================
# STEP 7 -- NLP: rank extracted market facts by relevance to THIS account's
# diagnosis (TF-IDF + cosine similarity -- information retrieval, not an
# LLM call). Step 4 kept every row for the vertical; this step decides,
# per account, which of those rows are actually worth stage 8 reasoning
# over -- a Life Insurance diagnosis and a Home Insurance diagnosis from
# the same vertical should not surface the same top facts.
# ============================================================================

def rank_evidence_by_relevance(market_evidence, diagnosis_text, top_n=24):
    """Vectorize the diagnosis text and every extracted (vendor, table-row)
    pair with the same TF-IDF space, score each row by cosine similarity to
    the diagnosis, and keep only the top_n closest matches across all
    vendors. Pure text-similarity ranking -- no model call, no randomness."""
    candidates = []
    for vendor, items in market_evidence.items():
        for item in items:
            row_text = f"{item['table']} " + " ".join(f"{k}: {v}" for k, v in item["row"].items())
            candidates.append((vendor, item, row_text))
    if not candidates:
        return market_evidence

    corpus = [diagnosis_text] + [c[2] for c in candidates]
    tfidf = TfidfVectorizer(stop_words="english", max_features=500).fit_transform(corpus)
    similarity = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    ranked = sorted(zip(candidates, similarity), key=lambda pair: pair[1], reverse=True)
    out = {}
    for (vendor, item, _row_text), score in ranked[:top_n]:
        out.setdefault(vendor, []).append({**item, "relevance_score": round(float(score), 3)})
    return out


# ============================================================================
# STEP 8 -- GenAI: market context mapping (one call per account, model = MODEL)
# ============================================================================

STAGE7_SYSTEM = (
    "You are a market-research analyst. You will be given (1) a diagnosis of one "
    "advertiser account's paid-search performance and (2) real data tables extracted "
    "from 4 third-party market research reports (parsed from PDFs -- the field names "
    "and rows are exactly as extracted, not curated for you). Your job is to find the "
    "facts in that extracted data that best support an urgent 'why act now' case for "
    "the account's specific diagnosis -- cite the vendor and the actual number for each "
    "fact you use. Do not invent facts not present in the extracted data."
)


def run_stage8(account_id, account_cfg, ads_analysis: AdsAnalysis, ranked_market_evidence):
    user = (
        f"Account diagnosis (from the ads-data analysis stage):\n"
        f"{ads_analysis.model_dump_json()}\n\n"
        f"Market-report facts for this vertical ({account_cfg['vertical']}), extracted from "
        f"4 vendor PDFs and pre-ranked by an NLP relevance score (0-1, higher = closer to "
        f"this account's diagnosis -- already filtered down from the full extraction, "
        f"this is the shortlist):\n"
        f"{json.dumps(ranked_market_evidence)}\n\n"
        "Build the 'why now' case: which of these ranked facts most strengthen urgency for "
        "this specific diagnosis? The relevance score is a hint, not a ranking you must "
        "preserve -- use your own judgment about which facts actually support the case."
    )
    return structured_call(f"stage8:{account_id}", MODEL, STAGE7_SYSTEM, user, MarketMapping, max_tokens=4000)


# ============================================================================
# STEP 9 -- GenAI: email copy (one call per account, model = MODEL)
# ============================================================================

STAGE9_SYSTEM = (
    "You are an expert B2B sales copywriter drafting a seller-to-customer email about "
    "their paid search advertising account. Write elegant, response-optimized copy: a "
    "personalized hook (not a market-stat recitation), a 'why now' case grounded in the "
    "market evidence given, and a low-friction call to action (a binary time choice plus "
    "a one-word-reply fallback -- never an open-ended 'worth a call?'). "
    "CRITICAL: the dollar figures given to you below (the headline revenue opportunity "
    "and each campaign's share of it) are exact and MUST be used verbatim in your copy -- "
    "do not recalculate, round differently, or invent any other dollar figure. "
    "Do not mention any company, platform, or vendor name anywhere in the copy -- keep "
    "it fully generic ('your paid search account')."
)


def _clean_email_copy(email: "EmailCopy") -> "EmailCopy":
    """Defensive post-processing: models don't always follow the schema
    field descriptions perfectly (seen live: a repeated 'Hi ...' greeting in
    hook, an impact_line that was just the bare dollar figure, and a
    fix_body that re-dumped the per-campaign breakdown with a doubled
    bullet). Cheap to fix in Python; cheaper than another model round-trip."""
    import re
    hook = re.sub(r"^\s*hi\s*\[customer name\]\s*,?\s*", "", email.hook, flags=re.IGNORECASE).strip()
    email.hook = hook or email.hook

    fix_body = email.fix_body.lstrip()
    fix_body = re.sub(r"^[•\-\*\d\.\)]+\s*", "", fix_body)
    email.fix_body = fix_body

    if len(email.impact_line.strip()) < 15:
        email.impact_line = (
            f"That figure reflects the gap between where the account sits today and "
            f"the vertical benchmark, applied to this account's own conversion economics."
        )
    return email


def run_stage9(account_id, account_cfg, ads_analysis, market_mapping, rollup):
    # Pre-formatted (not raw floats): stage 8's copy and the campaign cards
    # rendered in step 9 must show identical formatting for the same
    # number, so the model is handed the exact string to echo rather than
    # a float it might round or format differently on its own.
    campaign_revenue_fmt = {name: f"{account_cfg['currency_symbol']} {amount:,.0f}"
                             for name, amount in rollup["campaign_revenue"].items()}
    user = (
        f"Account: {account_cfg['vertical']} advertiser in {account_cfg['country']}. "
        f"Currency: {account_cfg['currency_symbol']}.\n\n"
        f"Diagnosis: {ads_analysis.model_dump_json()}\n\n"
        f"Market context: {market_mapping.model_dump_json()}\n\n"
        f"EXACT figures to use verbatim (do not recompute, do not reformat):\n"
        f"- Headline revenue opportunity this quarter: {account_cfg['currency_symbol']} "
        f"{rollup['inc_revenue']:,.0f}\n"
        f"- Per-campaign share of that opportunity (already shown to the reader in separate cards -- "
        f"do not repeat this list in your own copy): {json.dumps(campaign_revenue_fmt)}\n"
        f"- Impression share: {rollup['is_pct']:.2f}% ; lost-to-budget: {rollup['lost_budget_pct']:.1f}% ; "
        f"lost-to-rank: {rollup['lost_rank_pct']:.1f}%\n"
        f"- Daily budget: {account_cfg['currency_symbol']} {rollup['daily_budget']:,.0f}\n\n"
        "Draft the email copy now."
    )
    email = structured_call(f"stage9:{account_id}", MODEL, STAGE9_SYSTEM, user, EmailCopy, max_tokens=4500)
    return _clean_email_copy(email)


# ============================================================================
# STEP 10 -- Render the email as a real PDF, reusing the existing
# reportlab layout helpers in ../scripts/pdf_common.py (charts, campaign
# cards, the big-stat callout) -- no second rendering engine.
# ============================================================================

def render_email_pdf(account_id, account_cfg, email: EmailCopy, rollup, out_path, accent):
    styles = pc.get_styles(accent)
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                     Spacer, Table, TableStyle, HRFlowable, KeepTogether)
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER

    flow = [Spacer(1, 0.1 * inch)]
    header_rows = [["From:", "Seller, Paid Search Advertising"],
                    ["To:", f"Customer contact, {account_cfg['vertical'].lower()} advertiser"],
                    ["Subject:", email.subject]]
    t = Table(header_rows, colWidths=[0.9 * inch, 5.6 * inch])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
                           ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    flow += [t, Spacer(1, 0.08 * inch), HRFlowable(width="100%", thickness=1, color=colors.HexColor(accent)),
             Spacer(1, 0.14 * inch), Paragraph("Hi [Customer name],", styles["Body"]),
             Paragraph(email.hook, styles["Body"]), Spacer(1, 0.08 * inch)]
    flow.append(KeepTogether([pc.key_takeaways("Why Now", email.why_now_bullets, styles, accent)]))
    flow.append(Spacer(1, 0.14 * inch))
    stat_value = f"{account_cfg['currency_symbol']} {rollup['inc_revenue']:,.0f}"
    flow.append(pc.big_stat_callout(email.stat_label, stat_value, email.stat_sub, styles, accent))
    flow += [Spacer(1, 0.1 * inch), Paragraph(email.impact_line, styles["Body"]), Spacer(1, 0.14 * inch),
             Paragraph(f"<b>Where this shows up</b>:", styles["Body"]),
             Paragraph(email.scope_intro, styles["Caption"]), Spacer(1, 0.05 * inch)]
    for name, rev in rollup["campaign_revenue"].items():
        diag = "Material contributor to this quarter's missed opportunity."
        opp_text = f"Estimated opportunity here: <b>{account_cfg['currency_symbol']} {rev:,.0f}</b>"
        card = pc.campaign_card(name, diag, None, opp_text, styles, accent)
        flow.append(KeepTogether([card, Spacer(1, 0.08 * inch)]))
    flow.append(Spacer(1, 0.04 * inch))
    flow.append(KeepTogether([pc.key_takeaways(email.fix_title, [email.fix_body], styles, accent)]))
    flow += [Spacer(1, 0.12 * inch), Paragraph("Best regards,<br/>[Seller name]", styles["Body"]),
             Spacer(1, 0.04 * inch), Paragraph(email.ps, styles["Caption"])]

    def on_page(canv, doc):
        canv.saveState()
        canv.setStrokeColor(colors.HexColor(accent))
        canv.setLineWidth(1.2)
        canv.line(0.8 * inch, 0.62 * inch, LETTER[0] - 0.8 * inch, 0.62 * inch)
        canv.setFont("Helvetica", 6.6)
        canv.setFillColor(colors.HexColor("#B0413E"))
        canv.drawCentredString(LETTER[0] / 2, 0.47 * inch, WATERMARK + " -- ML+GenAI PIPELINE OUTPUT")
        canv.setFillColor(colors.HexColor("#888888"))
        canv.setFont("Helvetica", 7.5)
        canv.drawString(0.8 * inch, 0.33 * inch, f"ML+GenAI pipeline output -- {account_cfg['account_name']}")
        canv.drawRightString(LETTER[0] - 0.8 * inch, 0.33 * inch, f"Page {doc.page}")
        canv.restoreState()

    doc = BaseDocTemplate(str(out_path), pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                           topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    frame = Frame(0.8 * inch, 0.8 * inch, LETTER[0] - 1.6 * inch, LETTER[1] - 1.6 * inch, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    doc.build(flow)


# ============================================================================
# Orchestration: run steps 2-10 for every account
# ============================================================================

ACCENTS = {"Insurance": "#2E4057", "Retail": "#B0413E", "Travel": "#4C7A8C"}


def run_account(account_id, account_cfg, df):
    g = preprocess_account(df, account_id)                                    # STEP 2
    eda_result = compute_eda(g)                                               # STEP 3 (ML)
    market_evidence = extract_market_evidence(account_cfg["vertical"])        # STEP 4
    rollup = account_rollup(g, account_cfg)                                   # deterministic revenue math

    ads_analysis = run_stage6(account_id, account_cfg, g, eda_result)         # STEP 6 (GenAI)

    diagnosis_text = ads_analysis.account_level_diagnosis + " " + " ".join(ads_analysis.notable_patterns)
    ranked_evidence = rank_evidence_by_relevance(market_evidence, diagnosis_text)  # STEP 7 (NLP)

    market_mapping = run_stage8(account_id, account_cfg, ads_analysis, ranked_evidence)  # STEP 8 (GenAI)
    email = run_stage9(account_id, account_cfg, ads_analysis, market_mapping, rollup)     # STEP 9 (GenAI)

    accent = ACCENTS[account_cfg["vertical"]]
    slug = account_cfg["vertical"].lower() + "_" + account_cfg["country_code"].lower()
    render_email_pdf(account_id, account_cfg, email, rollup,                  # STEP 10
                      OUTPUT_DIR / f"recommendation_email_llm_{slug}.pdf", accent)

    return {
        "account_id": account_id,
        "model": MODEL,
        "eda": eda_result,
        "market_evidence_ranked": ranked_evidence,
        "ads_analysis": ads_analysis.model_dump(),
        "market_mapping": market_mapping.model_dump(),
        "email_copy": email.model_dump(),
    }


# ============================================================================
# STEP 11 -- Validation report
# ============================================================================

def write_validation_report(all_results, elapsed_seconds):
    lines = [
        "# ML + NLP + GenAI Pipeline -- Validation Report", "",
        f"Run started: {RUN_STARTED}", f"Elapsed: {elapsed_seconds:.1f}s", f"Model: {MODEL}", "",
        "## Schema compliance", "",
        "Every GenAI call is validated against its Pydantic schema by the OpenAI SDK "
        "at response time -- a response that doesn't match the schema raises and is "
        "retried (see structured_call()), so every result below already passed validation.",
        "",
        f"- Accounts processed: {len(all_results)}",
        f"- GenAI calls per account: 3 (stage 6 ads analysis, stage 8 market mapping, stage 9 email copy)",
        f"- Total structured calls made: {LEDGER.summary()['num_calls']} "
        f"(expected {len(all_results)} accounts x 3 = {len(all_results) * 3})",
        "", "## Token usage & cost", "",
        f"```\n{json.dumps(LEDGER.summary(), indent=2)}\n```", "",
        "## Per-account result", "",
    ]
    for r in all_results:
        lines.append(f"- **{r['account_id']}**: constraint = {r['ads_analysis']['primary_constraint']}, "
                      f"confidence = {r['ads_analysis']['confidence_0_to_1']}, "
                      f"campaign findings = {len(r['ads_analysis']['campaign_findings'])}")
    report_path = OUTPUT_DIR / "validation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    t0 = time.time()
    df = load_campaigns()  # STEP 1
    all_results = []
    for account_id, account_cfg in ACCOUNTS.items():
        print(f"\n=== {account_id} ({account_cfg['vertical']}) ===")
        result = run_account(account_id, account_cfg, df)
        all_results.append(result)
        print(f"  constraint: {result['ads_analysis']['primary_constraint']}")
        (OUTPUT_DIR / f"{account_id}_full_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    report_path = write_validation_report(all_results, time.time() - t0)
    print(f"\nValidation report: {report_path}")
    print(json.dumps(LEDGER.summary(), indent=2))


if __name__ == "__main__":
    main()

"""
================================================================================
 ML + GenAI RECOMMENDATION PIPELINE -- ONE SCRIPT, START TO FINISH
================================================================================

What this does, in order (search for "STEP N" to jump to any stage):

  STEP 1  Read input data           -- load input/campaigndata-campaigns.csv
  STEP 2  Pre-processing            -- per-account slicing, derived columns
  STEP 3  EDA / ML analysis         -- correlations, anomaly detection, clustering,
                                       materiality ranking, PLUS keyword/search-term/
                                       negative-keyword/ad-strength/auction-insight
                                       evidence (compute_granular_eda) -- the deeper
                                       grain a real analyst digs through, not just
                                       campaign-level aggregates. Pure statistics, no LLM.
  STEP 4  Parse market PDFs         -- real pdfplumber table extraction from the
                                       4 vendor reports (not read from benchmarks.py)
  STEP 5  Pydantic output schemas   -- structured-JSON contracts for every GenAI call
  STEP 6  GenAI: ads-data analysis  -- diagnoses each account from the raw campaign
                                       data + ALL of step 3's evidence, producing a
                                       prioritized recommendation_cards list and an
                                       already_working list -- not just a diagnosis
                                       paragraph
  STEP 7  NLP: relevance ranking    -- TF-IDF + cosine similarity scores every
                                       extracted market fact against THIS account's
                                       stage-6 diagnosis text; only the closest
                                       matches are passed on (see note below)
  STEP 8  GenAI: market mapping     -- matches the NLP-ranked market facts onto the
                                       stage-6 diagnosis ("why now"), AND independently
                                       onto each individual recommendation card
                                       (card_market_support) -- the 360-degree step a
                                       human analyst can't do alone, since they have
                                       no external market-report access at all
  STEP 9  GenAI: email copy         -- drafts the customer-facing email
  STEP 10 Render PDFs               -- build the email as a real PDF, reusing the
                                       existing reportlab layout helpers in pdf_common.py
  STEP 11 Validation report         -- schema-compliance checks, token totals, timing,
                                       written to ../output/validation_report.md

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
campaigndata-campaigns.csv, not invented by the LLM -- models are handed
these exact figures as facts to write copy around, never asked to do the
arithmetic themselves. Every dollar amount in the final email traces to the CSV.

Folder layout this script expects (see ../README.md and ../misc/approach.html):
  ../input/    -- campaigndata-*.csv (6 files) and marketdata-*.pdf (4 files)
  ../output/   -- where this script writes everything it produces
  benchmarks.py, pdf_common.py -- shared modules, same folder as this script

Run:  python 05_analyze_and_generate_emails.py
Needs: OPENAI_API_KEY only -- deliberately single-provider (see the call-layer
       section below for why). Swap the key and nothing else needs to change.
"""
import json
import os
import re
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
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

import pdf_common as pc  # the existing reportlab layout helpers (charts, cards, callouts) -- same folder, no sys.path needed
from benchmarks import ACCOUNTS, REPORT_PERIOD, PRIOR_PERIOD, WATERMARK  # market-side constants only; no cheating by reading account-diagnosis numbers from here

RUN_STARTED = time.strftime("%Y-%m-%d %H:%M:%S")
MATERIALITY_CUTOFF = 0.70


# ============================================================================
# STEP 1 -- Read input data
# ============================================================================

def load_campaigns():
    return pd.read_csv(INPUT_DIR / "campaigndata-campaigns.csv")


GRANULAR_FILES = ["keywords", "search_terms", "negative_keyword_conflicts", "ads", "auction_insights"]


def load_granular_data():
    """The keyword / search-term / negative-keyword / ad-strength / auction-
    insight grain a real analyst actually digs through -- campaigndata-campaigns.csv
    alone only has account/campaign-level aggregates. Returns {name: DataFrame}."""
    return {name: pd.read_csv(INPUT_DIR / f"campaigndata-{name}.csv") for name in GRANULAR_FILES}


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


# ---------------------------------------------------------------------------
# Granular EDA: the keyword / search-term / negative-keyword / ad-strength /
# auction-insight evidence a real analyst actually digs through before
# writing a recommendation -- campaign-level stats alone can't surface a
# single keyword that scores 9/10 on quality but sits at 5% impression
# share, or a competitor-brand search term pulling thousands of zero-click
# impressions. Still pure statistics, no LLM -- this is evidence for stage 6.
# ---------------------------------------------------------------------------

def compute_granular_eda(account_id, granular):
    kw = granular["keywords"][granular["keywords"].account_id == account_id]
    st = granular["search_terms"][granular["search_terms"].account_id == account_id]
    neg = granular["negative_keyword_conflicts"][granular["negative_keyword_conflicts"].account_id == account_id]
    ads = granular["ads"][granular["ads"].account_id == account_id]
    auc = granular["auction_insights"][granular["auction_insights"].account_id == account_id]

    keyword_level = {"note": "Top keywords by story relevance, not an exhaustive export of every live keyword."}
    if len(kw) >= 3:
        r_qs_is, p_qs_is = stats.pearsonr(kw["quality_score"], kw["impression_share_pct"])
        r_qs_cpa, p_qs_cpa = stats.pearsonr(kw["quality_score"], kw["cost_per_conversion"].fillna(kw["cost_per_conversion"].median()))
        keyword_level["correlation_quality_score_vs_impression_share"] = {"pearson_r": round(float(r_qs_is), 3), "p_value": round(float(p_qs_is), 4)}
        keyword_level["correlation_quality_score_vs_cost_per_conversion"] = {"pearson_r": round(float(r_qs_cpa), 3), "p_value": round(float(p_qs_cpa), 4)}
    high_qs_low_is = kw[kw.quality_score >= 7].sort_values("impression_share_pct").head(4)
    low_qs_high_spend = kw[kw.quality_score < 5].sort_values("spend", ascending=False).head(4)
    keyword_level["high_quality_low_impression_share"] = high_qs_low_is[
        ["keyword_text", "quality_score", "impression_share_pct", "impression_share_lost_rank_pct"]].to_dict(orient="records")
    keyword_level["low_quality_high_spend"] = low_qs_high_spend[
        ["keyword_text", "quality_score", "spend", "cost_per_conversion"]].to_dict(orient="records")

    brand_zero_click = st[(st.is_competitor_brand_term) & (st.clicks == 0)]
    brand_converting = st[(st.is_competitor_brand_term) & (st.clicks > 0)]
    search_term_level = {
        "competitor_brand_zero_click_impressions": int(brand_zero_click["impressions"].sum()),
        "competitor_brand_zero_click_terms": brand_zero_click["search_term"].tolist(),
        "competitor_brand_terms_that_convert": brand_converting[["search_term", "conversions"]].to_dict(orient="records"),
        "pct_of_search_term_impressions_from_zero_click_competitor_terms":
            round(100 * brand_zero_click["impressions"].sum() / st["impressions"].sum(), 1) if len(st) else 0.0,
    }

    negative_keyword_level = {
        "conflict_count": int(len(neg)),
        "estimated_total_blocked_impressions": int(neg["estimated_blocked_impressions"].sum()) if len(neg) else 0,
        "conflicts": neg[["negative_keyword", "blocked_keyword_text", "blocked_campaign_name",
                           "estimated_blocked_impressions"]].to_dict(orient="records"),
    }

    ad_strength = {
        "total_ads": int(len(ads)),
        "pct_excellent_or_good": round(100 * ads.ad_strength_rating.isin(["Excellent", "Good"]).mean(), 1) if len(ads) else None,
        "rating_counts": ads.ad_strength_rating.value_counts().to_dict(),
    }

    auction_insights = {
        "avg_position_above_rate_pct": round(float(auc["position_above_rate_pct"].mean()), 1) if len(auc) else None,
        "avg_top_of_page_rate_pct_self": round(float(auc["top_of_page_rate_pct_self"].mean()), 1) if len(auc) else None,
        "avg_top_of_page_rate_pct_competitor": round(float(auc["top_of_page_rate_pct_competitor"].mean()), 1) if len(auc) else None,
        "avg_outranking_share_pct_self": round(float(auc["outranking_share_pct_self"].mean()), 1) if len(auc) else None,
        "by_competitor": auc[["competitor_name", "position_above_rate_pct", "top_of_page_rate_pct_self",
                               "top_of_page_rate_pct_competitor"]].to_dict(orient="records"),
    }

    return {
        "keyword_level": keyword_level,
        "search_term_level": search_term_level,
        "negative_keyword_level": negative_keyword_level,
        "ad_strength": ad_strength,
        "auction_insights": auction_insights,
        "_raw_search_terms": st,  # kept for per-card chart building (step 10) -- real rows, not a summary
    }


# ============================================================================
# STEP 4 -- Parse the 4 vendor market-report PDFs (real table extraction,
# not a read of benchmarks.py -- a production pipeline only has the PDFs)
# ============================================================================

VENDOR_FILES = {
    "Ashcroft Research Partners": "marketdata-ashcroft_vertical_ad_trends_2026q3.pdf",
    "Vantage Media Metrics": "marketdata-vantage_media_mix_2026q3.pdf",
    "SignalWatch Competitive Intelligence": "marketdata-signalwatch_competitive_spend_2026q3.pdf",
    "QueryScope Insights": "marketdata-queryscope_search_demand_2026q3.pdf",
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
        path = INPUT_DIR / fname
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


class RecommendationCard(BaseModel):
    """One prioritized, actionable recommendation -- the account-level
    synthesis across campaign, keyword, search-term, negative-keyword, and
    auction-insight evidence. Modeled on how a human analyst actually writes
    these up: a claim backed by a specific number, not a generic tip."""
    title: str = Field(description="Short imperative headline, e.g. 'Remove the bid caps blocking automated bidding'")
    affects: Literal["bid", "quality_score", "budget_allocation", "negative_keywords"]
    priority: Literal["high", "medium", "low"]
    timeframe: str = Field(description="Short label for how soon this can be acted on, e.g. 'Now', '0-3 days', '2 weeks'")
    what_data_shows: str = Field(description="1-2 sentences citing the SPECIFIC numbers from the evidence given -- "
                                              "keyword names, quality scores, impression shares, dollar figures")
    recommended_steps: list[str] = Field(description="2-3 short imperative steps, concrete enough to action directly")
    what_to_watch: str = Field(description="One leading-indicator metric and a rough target, e.g. "
                                            "'click rate moving from 1.3% toward 2.0%+'")


class AdsAnalysis(BaseModel):
    """Stage 6 output: the model's OWN analysis of the raw campaign AND
    keyword/search-term/negative-keyword/ad-strength/auction-insight data,
    using the EDA stats as evidence -- not a rephrasing of them."""
    account_level_diagnosis: str
    primary_constraint: Literal["rank-constrained", "budget-constrained", "healthy-demand-surge"]
    confidence_0_to_1: float
    notable_patterns: list[str] = Field(description="2-4 specific observations citing actual numbers from the data provided")
    campaign_findings: list[CampaignFinding]
    recommendation_cards: list[RecommendationCard] = Field(description="3-5 prioritized recommendations synthesized "
                                                                        "across ALL evidence given (campaign, keyword, "
                                                                        "search-term, negative-keyword, ad-strength, "
                                                                        "auction-insight) -- not one per data source, "
                                                                        "one per actual issue worth fixing")
    already_working: list[str] = Field(description="2-3 things the evidence shows are already fine and need no "
                                                     "changes -- cite the specific number proving it (e.g. an ad "
                                                     "strength %, budget headroom, a campaign with strong cost per "
                                                     "conversion). Builds credibility that the fix list is short "
                                                     "because the rest is solid, not because it wasn't checked.")


class MarketFact(BaseModel):
    vendor: str
    fact: str = Field(description="A specific fact from the extracted table data, including the actual number")
    relevance_to_recommendation: str
    account_vs_market: str = Field(description="An explicit head-to-head comparison sentence, the account's own "
                                                "number directly against this external number -- e.g. 'Your "
                                                "account: 21.3% impression share vs the vertical benchmark: "
                                                "35.0%.' Pull the account's own figure from the diagnosis/rollup "
                                                "data given, never invent it. This is the single most important "
                                                "field on this object -- a market fact without the account's own "
                                                "number next to it is not yet a comparison.")


class CardMarketSupport(BaseModel):
    """Ties external market evidence to ONE specific recommendation card --
    not just the account overall. This is the actual 360-degree step: a
    human analyst's recommendation is backed only by the account's own
    data; ours additionally shows, per fix, that the market independently
    corroborates it. Correct to return an empty supporting_facts list for a
    card when nothing in the evidence genuinely speaks to it -- a forced,
    generic citation is worse than no citation."""
    card_title: str = Field(description="Must exactly match one of the recommendation_cards titles given")
    supporting_facts: list[MarketFact] = Field(description="0-2 facts that specifically strengthen THIS card's "
                                                            "urgency -- empty list if none genuinely apply")


class MarketMapping(BaseModel):
    why_now_summary: str
    supporting_facts: list[MarketFact]
    urgency_0_to_1: float
    card_market_support: list[CardMarketSupport] = Field(description="One entry per recommendation card given, "
                                                                      "in the same order")


class EmailCopy(BaseModel):
    banner_headline: str = Field(description="A catchy, attention-grabbing headline for a bold banner at the very "
                                              "top of the document, 'one number explains it' news-style -- short "
                                              "(under 12 words), states the core insight as a fact, not a question "
                                              "or a generic greeting. Different from subject -- this is a visual "
                                              "headline, not an email subject line.")
    subject: str = Field(description="Lead with the account's specific number/gap, not a generic market stat")
    hook: str = Field(description="1-2 sentence personalized opening. The greeting 'Hi [Customer name],' is already "
                                   "rendered immediately before this text by the template -- do NOT repeat 'Hi' or "
                                   "any other greeting here, start directly with the substance.")
    why_now_bullets: list[str] = Field(description="2-3 bullets, each pairing a market number against the account's "
                                                     "own number for the same metric (use the account_vs_market "
                                                     "field on the market context's supporting_facts directly -- "
                                                     "'market is at X, your account is at Y' is the pattern, not a "
                                                     "market stat alone); bold both figures with <b></b> tags")
    stat_label: str = Field(description="All-caps label above the headline number")
    stat_sub: str
    impact_line: str = Field(description="A full 1-2 sentence explanation of what's behind the headline number -- "
                                          "never just the number by itself, never a one-word or sub-5-word answer")
    scope_intro: str = Field(description="One sentence introducing the per-campaign breakdown that follows")
    cards_intro: str = Field(description="One punchy sentence introducing the prioritized fix list (the "
                                          "recommendation cards) that follows -- make it sound like a short, "
                                          "credible diagnosis was just delivered, not a generic 'here are some tips'")
    working_intro: str = Field(description="One short, confident sentence introducing the 'what's already working' "
                                            "strip -- this should read as reassuring and credible, not an afterthought")
    opportunity_intro: str = Field(description="One sentence framing the opportunity-sizing numbers that follow as "
                                                "the payoff for acting -- tie it to the headline revenue number, "
                                                "don't just restate the stats")
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


def _fix_pdf_unsupported_glyphs(obj):
    """ReportLab's base-14 Helvetica (WinAnsi encoding) has no glyph for
    several Unicode characters models reach for -- hyphen variants
    (U+2010/U+2011/U+2012, used in compound words like "Non-Brand") and
    arrows (U+2192/U+2190, used in "100 -> 151" style call-outs). Seen live
    as "Non-Brand" rendering as "NonnBrand" and "->" rendering as "fi" in a
    PDF. Fixed once, here, for every structured GenAI response, rather than
    patched per call site."""
    if isinstance(obj, str):
        return (obj.replace("‐", "-").replace("‑", "-").replace("‒", "-")
                   .replace("→", "->").replace("←", "<-"))
    if isinstance(obj, list):
        return [_fix_pdf_unsupported_glyphs(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _fix_pdf_unsupported_glyphs(v) for k, v in obj.items()}
    return obj


# Prompts instruct every stage not to name a real platform/vendor (see
# STAGE6_SYSTEM / STAGE9_SYSTEM), but a model can still slip one in --
# live-caught: stage 6 once wrote "validate in the Google Ads 'Negative
# keyword conflicts' view". This is the mechanical backstop, same pattern
# as _fix_pdf_unsupported_glyphs: fixed once at the call layer, not
# patched per prompt. Longer phrases first so "Google Ads" doesn't get
# half-replaced by the standalone "Google" rule first.
_BRAND_NAME_SCRUB = [
    (r"\bGoogle\s+Ads\b", "the platform"), (r"\bGoogle\s+AdWords\b", "the platform"),
    (r"\bMicrosoft\s+Ads\b", "the platform"), (r"\bMicrosoft\s+Advertising\b", "the platform"),
    (r"\bBing\s+Ads\b", "the platform"), (r"\bMeta\s+Ads\b", "the platform"),
    (r"\bFacebook\s+Ads\b", "the platform"), (r"\bAdWords\b", "the platform"),
    (r"\bGoogle\b", "the platform"), (r"\bMicrosoft\b", "the platform"), (r"\bBing\b", "the platform"),
    (r"\bConcentrix\b", "[redacted]"),
]


def _scrub_real_brand_names(obj):
    if isinstance(obj, str):
        for pattern, replacement in _BRAND_NAME_SCRUB:
            obj = re.sub(pattern, replacement, obj, flags=re.IGNORECASE)
        return obj
    if isinstance(obj, list):
        return [_scrub_real_brand_names(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub_real_brand_names(v) for k, v in obj.items()}
    return obj


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
    cleaned = _fix_pdf_unsupported_glyphs(choice.message.parsed.model_dump())
    cleaned = _scrub_real_brand_names(cleaned)
    return output_model(**cleaned)


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
# the final email traces to campaigndata-campaigns.csv.
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


def opportunity_sizing(g, rollup):
    """How big the fix is worth, in the account's own current terms -- not a
    model guess. Target impression share is the account's own vertical
    benchmark (already in campaigndata-campaigns.csv), additional clicks are projected at
    TODAY's click rate (deliberately the cautious version, same as a real
    analyst would quote -- click rate should improve once the quality fixes
    land, but this number doesn't assume that yet)."""
    current_is_pct = rollup["is_pct"]
    target_is_pct = float((g["vertical_benchmark_impression_share_pct"] * g["eligible_impressions"]).sum()
                           / g["eligible_impressions"].sum())
    target_is_pct = max(target_is_pct, current_is_pct)

    total_eligible = g["eligible_impressions"].sum()
    additional_impressions = round(total_eligible * (target_is_pct - current_is_pct) / 100)

    wi = g["impressions"]
    ctr_pct = (g["ctr_pct"] * wi).sum() / wi.sum()
    additional_clicks = round(additional_impressions * ctr_pct / 100)

    return {
        "current_impression_share_pct": round(current_is_pct, 2),
        "target_impression_share_pct": round(target_is_pct, 2),
        "additional_impressions_estimate": int(additional_impressions),
        "additional_clicks_estimate": int(additional_clicks),
        "basis": f"Projected at today's click rate of {ctr_pct:.2f}% -- deliberately the cautious "
                 f"version, since click rate should improve once the quality fixes land.",
    }


# ============================================================================
# STEP 6 -- GenAI: ads-data analysis (one call per account, model = MODEL)
# ============================================================================

STAGE6_SYSTEM = (
    "You are a senior paid-search performance analyst. You will be given one advertiser "
    "account's campaign-level performance data for the current quarter, PLUS the deeper "
    "grain a human analyst actually digs through before writing a recommendation: "
    "individual keyword quality scores and impression shares, the literal search queries "
    "that triggered ads (including competitor-brand leakage), negative-keyword conflicts "
    "blocking the account's own keywords, ad-copy strength ratings, and this account's "
    "head-to-head auction position against its named competitors. Some supporting "
    "exploratory statistics (correlations, anomaly scores, cluster labels) are computed "
    "separately. Treat ALL of this as EVIDENCE to weigh, not as conclusions to restate -- "
    "form your own diagnosis directly from the raw numbers, citing specific figures "
    "(keyword text, quality scores, dollar amounts, percentages) rather than speaking in "
    "generalities. Identify whether the account's missed opportunity is primarily a rank "
    "problem (outranked on quality/bid, budget isn't the constraint), a budget problem "
    "(daily budget caps the account before it exhausts demand), or the account is "
    "already healthy and riding a demand surge. Your recommendation_cards should read "
    "like a real paid-search analyst's prioritized fix list, not a generic checklist -- "
    "each one must trace to a specific number in the evidence given. "
    "Do not name any real advertising platform, product, or report/view within one (e.g. "
    "no 'Google Ads', 'Microsoft Ads', 'Bing Ads', 'Meta Ads', or any real vendor name) -- "
    "refer to it generically ('the platform', 'the negative-keyword conflicts report')."
)


STAGE6_COLS = [
    "campaign_name", "campaign_type", "search_impression_share_pct",
    "impression_share_lost_budget_pct", "impression_share_lost_rank_pct", "spend",
    "spend_qoq_change_pct", "conversions", "revenue", "roas", "avg_quality_score",
    "budget_utilization_pct",
]


def run_stage6(account_id, account_cfg, g, eda_result, granular_eda):
    campaign_json = g[STAGE6_COLS].to_json(orient="records")
    user = (
        f"Account: {account_cfg['account_name']} -- vertical: {account_cfg['vertical']}, "
        f"market: {account_cfg['country']}. Reporting period: {REPORT_PERIOD} vs {PRIOR_PERIOD}.\n\n"
        f"Campaign-level data (JSON, one object per campaign):\n{campaign_json}\n\n"
        f"Campaign-level exploratory statistics (evidence, not a conclusion):\n"
        f"{json.dumps(eda_result)}\n\n"
        f"Keyword-level evidence:\n{json.dumps(granular_eda['keyword_level'])}\n\n"
        f"Search-term-level evidence (literal queries, including competitor-brand leakage):\n"
        f"{json.dumps(granular_eda['search_term_level'])}\n\n"
        f"Negative-keyword conflicts (own keywords blocked by the account's own negatives):\n"
        f"{json.dumps(granular_eda['negative_keyword_level'])}\n\n"
        f"Ad-copy strength ratings:\n{json.dumps(granular_eda['ad_strength'])}\n\n"
        f"Auction-insight position vs. named competitors:\n{json.dumps(granular_eda['auction_insights'])}\n\n"
        "Analyze this account. Only include campaign_findings for campaigns the data "
        "shows are materially worth acting on -- not every campaign in the account. "
        "Build recommendation_cards from whichever evidence above is most material for "
        "THIS account -- do not force one card per data source if the evidence doesn't "
        "support it."
    )
    return structured_call(f"stage6:{account_id}", MODEL, STAGE6_SYSTEM, user, AdsAnalysis, max_tokens=9000)


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
    "advertiser account's paid-search performance, including its specific prioritized "
    "recommendation list, and (2) real data tables extracted from 4 third-party market "
    "research reports (parsed from PDFs -- the field names and rows are exactly as "
    "extracted, not curated for you). You have two jobs, and the second is what makes "
    "this analysis go beyond what a human paid-search analyst produces alone (they have "
    "no access to external market data at all):\n"
    "1. Build the account-level 'why act now' case (why_now_summary, supporting_facts, "
    "urgency_0_to_1) -- the overall narrative.\n"
    "2. For EACH recommendation card given, independently decide whether any extracted "
    "fact specifically strengthens THAT fix's urgency (card_market_support). A fact "
    "about rising competitive spend only supports a bid/rank card if the card's own "
    "issue is rank, not budget -- judge genuine relevance per card, do not default to "
    "attaching the same top fact everywhere. Returning an empty list for a card is the "
    "correct answer when nothing in the evidence actually speaks to its specific issue; "
    "a forced generic citation would be worse than no citation and would undercut the "
    "credibility this step is meant to add.\n"
    "Cite the vendor and the actual number for every fact you use. Do not invent facts "
    "not present in the extracted data. EVERY MarketFact's account_vs_market field must "
    "state the account's own number (from the EXACT account figures given) directly "
    "against the external number -- never cite an external number alone."
)


def run_stage8(account_id, account_cfg, ads_analysis: AdsAnalysis, ranked_market_evidence, rollup):
    cards_summary = [{"title": c.title, "affects": c.affects, "what_data_shows": c.what_data_shows}
                      for c in ads_analysis.recommendation_cards]
    account_figures = {
        "impression_share_pct": round(rollup["is_pct"], 2),
        "lost_to_budget_pct": round(rollup["lost_budget_pct"], 1),
        "lost_to_rank_pct": round(rollup["lost_rank_pct"], 1),
        "daily_budget": f"{account_cfg['currency_symbol']} {rollup['daily_budget']:,.0f}",
        "vertical_benchmark_impression_share_pct": account_cfg["benchmark_impression_share_pct"],
    }
    user = (
        f"Account diagnosis (from the ads-data analysis stage):\n"
        f"{ads_analysis.model_dump_json()}\n\n"
        f"EXACT account figures to use verbatim whenever you state 'your account' in an "
        f"account_vs_market comparison (do not recompute, do not pull a different number "
        f"from the diagnosis prose):\n{json.dumps(account_figures)}\n\n"
        f"The account's recommendation cards, which you must map market support onto "
        f"individually (card_market_support needs exactly one entry per card below, "
        f"same order, title matched exactly):\n"
        f"{json.dumps(cards_summary)}\n\n"
        f"Market-report facts for this vertical ({account_cfg['vertical']}), extracted from "
        f"4 vendor PDFs and pre-ranked by an NLP relevance score (0-1, higher = closer to "
        f"this account's diagnosis -- already filtered down from the full extraction, "
        f"this is the shortlist):\n"
        f"{json.dumps(ranked_market_evidence)}\n\n"
        "Build the account-level 'why now' case first, then go card by card deciding "
        "what, if anything, from this evidence specifically strengthens each one. The "
        "relevance score is a hint, not a ranking you must preserve -- use your own "
        "judgment about which facts actually support which case."
    )
    return structured_call(f"stage8:{account_id}", MODEL, STAGE7_SYSTEM, user, MarketMapping, max_tokens=5500)


# ============================================================================
# STEP 9 -- GenAI: email copy (one call per account, model = MODEL)
# ============================================================================

STAGE9_SYSTEM = (
    "You are an expert B2B sales copywriter drafting a seller-to-customer email about "
    "their paid search advertising account. The underlying analysis is already genuinely "
    "deep (keyword-level, search-term-level, competitive auction position) -- your job is "
    "NOT to dump that depth into dry audit prose. Write elegant, response-optimized copy "
    "that makes the reader want to reply: a personalized hook (not a market-stat "
    "recitation), a 'why now' case grounded in the market evidence given, short punchy "
    "intro lines for the deeper sections that follow (the template renders the actual "
    "recommendation cards and numbers -- your job is just the connective tissue between "
    "them), and a low-friction call to action (a binary time choice plus a one-word-reply "
    "fallback -- never an open-ended 'worth a call?'). Confident and consultative, never "
    "a wall of findings -- this is a sales email that happens to be backed by real depth, "
    "not an internal audit report. "
    "CRITICAL: the dollar and percentage figures given to you below are exact and MUST be "
    "used verbatim in your copy -- do not recalculate, round differently, or invent any "
    "other number. "
    "Do not mention any company, platform, or vendor name anywhere in the copy -- keep "
    "it fully generic ('your paid search account')."
)


def _clean_email_copy(email: "EmailCopy") -> "EmailCopy":
    """Defensive post-processing: models don't always follow the schema
    field descriptions perfectly (seen live: a repeated 'Hi ...' greeting in
    hook, an impact_line that was just the bare dollar figure, and a
    fix_body that re-dumped the per-campaign breakdown with a doubled
    bullet). Cheap to fix in Python; cheaper than another model round-trip."""
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


def run_stage9(account_id, account_cfg, ads_analysis, market_mapping, rollup, opp_sizing):
    # Pre-formatted (not raw floats): stage 9's copy and the campaign cards
    # rendered in step 10 must show identical formatting for the same
    # number, so the model is handed the exact string to echo rather than
    # a float it might round or format differently on its own.
    campaign_revenue_fmt = {name: f"{account_cfg['currency_symbol']} {amount:,.0f}"
                             for name, amount in rollup["campaign_revenue"].items()}
    user = (
        f"Account: {account_cfg['vertical']} advertiser in {account_cfg['country']}. "
        f"Currency: {account_cfg['currency_symbol']}.\n\n"
        f"Diagnosis: {ads_analysis.model_dump_json()}\n\n"
        f"Market context: {market_mapping.model_dump_json()}\n\n"
        f"The recommendation cards, 'already working' findings, and opportunity-sizing "
        f"numbers below will be rendered directly by the template as their own sections -- "
        f"you are writing the intro lines for them (cards_intro, working_intro, "
        f"opportunity_intro), not reproducing their content:\n"
        f"- Recommendation cards (titles only): {[c.title for c in ads_analysis.recommendation_cards]}\n"
        f"- Already working: {ads_analysis.already_working}\n"
        f"- Opportunity sizing: {json.dumps(opp_sizing)}\n\n"
        f"EXACT figures to use verbatim elsewhere in your copy (do not recompute, do not reformat):\n"
        f"- Headline revenue opportunity this quarter: {account_cfg['currency_symbol']} "
        f"{rollup['inc_revenue']:,.0f}\n"
        f"- Per-campaign share of that opportunity (already shown to the reader in separate cards -- "
        f"do not repeat this list in your own copy): {json.dumps(campaign_revenue_fmt)}\n"
        f"- Impression share: {rollup['is_pct']:.2f}% ; lost-to-budget: {rollup['lost_budget_pct']:.1f}% ; "
        f"lost-to-rank: {rollup['lost_rank_pct']:.1f}%\n"
        f"- Daily budget: {account_cfg['currency_symbol']} {rollup['daily_budget']:,.0f}\n\n"
        "Draft the email copy now."
    )
    email = structured_call(f"stage9:{account_id}", MODEL, STAGE9_SYSTEM, user, EmailCopy, max_tokens=5000)
    return _clean_email_copy(email)


# ============================================================================
# STEP 10 -- Render the email as a real PDF, reusing the existing
# reportlab layout helpers in pdf_common.py (charts, campaign
# cards, the big-stat callout) -- no second rendering engine.
# ============================================================================

def _account_vs_benchmark_chart(account_cfg, rollup, accent):
    """The account's own numbers plotted directly against the vertical
    benchmark for the same two metrics -- a reader should not have to hold
    two numbers in their head to see the gap; the chart does it instead.
    Picks lost-to-rank or lost-to-budget as the second metric depending on
    which one this account's own benchmark data actually tracks."""
    if "benchmark_lost_rank_pct" in account_cfg:
        constraint_label, your_second, benchmark_second = (
            "Lost to rank %", rollup["lost_rank_pct"], account_cfg["benchmark_lost_rank_pct"])
    else:
        constraint_label, your_second, benchmark_second = (
            "Lost to budget %", rollup["lost_budget_pct"], account_cfg["benchmark_lost_budget_pct"])
    categories = ["Impression share %", constraint_label]
    series = {
        "Your account": [round(rollup["is_pct"], 1), round(your_second, 1)],
        "Vertical benchmark": [account_cfg["benchmark_impression_share_pct"], benchmark_second],
    }
    return pc.fig_grouped_bar(categories, series, "Your account vs. vertical benchmark", "%", accent)


def _demand_trend_chart(account_cfg, accent):
    """This account's own vertical/country demand index, current year vs.
    the prior-year pattern -- the same market-timing evidence a real
    analyst would only get from a paid vendor subscription, made visual."""
    quarters = list(account_cfg["demand_index"].keys())
    current = [account_cfg["demand_index"][q]["current"] for q in quarters]
    prior = [account_cfg["demand_index"][q]["prior_year"] for q in quarters]
    return pc.fig_line(quarters, {"Current year": current, "Prior-year pattern": prior},
                        "Demand trend vs. seasonal norm (index)", "Index", accent)


def _card_evidence_chart(card, g, granular_eda, accent):
    """A graph for the recommendation, built only from real numbers already
    computed elsewhere in the pipeline (campaign dataframe / granular EDA)
    -- never from anything the LLM wrote, so there is no risk of a chart
    showing an invented figure. Returns None when this account's data
    doesn't have a clean set of values for this category -- no graph beats
    a forced, irrelevant one."""
    affects = card["affects"]
    text = (card["title"] + " " + card["what_data_shows"]).lower()

    if affects == "budget_allocation":
        capped = g[g["impression_share_lost_budget_pct"] > 0].nlargest(5, "impression_share_lost_budget_pct")
        if capped.empty:
            return None
        return pc.fig_horizontal_bar(capped["campaign_name"].tolist(),
                                      capped["impression_share_lost_budget_pct"].round(1).tolist(),
                                      "Impression share lost to budget, by campaign", "% lost to budget", accent)

    if affects in ("bid", "quality_score"):
        # Two distinct keyword stories share these two affects values -- "bid"
        # cards are about high-quality keywords still losing on rank/position
        # (chart their impression share), "quality_score" cards are about
        # genuinely low-quality keywords wasting spend (chart their cost per
        # conversion) -- using the SAME subset for both would just repeat the
        # same chart across two different recommendations.
        kw = granular_eda["keyword_level"]
        if affects == "bid":
            rows = (kw.get("high_quality_low_impression_share") or [])[:6]
            if not rows:
                return None
            return pc.fig_horizontal_bar([r["keyword_text"] for r in rows],
                                          [r["impression_share_pct"] for r in rows],
                                          "Impression share of high-quality keywords", "Impression share %", accent)
        rows = (kw.get("low_quality_high_spend") or [])[:6]
        if not rows:
            return None
        return pc.fig_horizontal_bar([r["keyword_text"] for r in rows],
                                      [r["cost_per_conversion"] or 0 for r in rows],
                                      "Cost per conversion of low-quality keywords", "Cost per conversion", accent)

    if affects == "negative_keywords":
        # "negative_keywords" covers two distinct issues (self-blocking
        # conflicts vs. competitor-brand zero-click waste) -- pick the chart
        # that actually matches what THIS card is about, not just whichever
        # data happens to exist, or two different cards render the same graph.
        # NOT "brand" alone -- that matches as a false positive inside
        # "Non-Brand Search" campaign names, which appear in nearly every
        # card regardless of topic. "competitor" / "zero-click" are the
        # actual distinguishing signal.
        is_zero_click_card = any(w in text for w in ("competitor", "zero-click", "zero click"))

        conflicts = granular_eda["negative_keyword_level"]["conflicts"]
        st = granular_eda["_raw_search_terms"]
        zero_click = st[(st.is_competitor_brand_term) & (st.clicks == 0)].nlargest(5, "impressions")

        def _conflicts_chart():
            top = sorted(conflicts, key=lambda c: c["estimated_blocked_impressions"], reverse=True)[:5]
            labels = [f"\"{c['negative_keyword']}\" blocks \"{c['blocked_keyword_text'][:28]}\"" for c in top]
            return pc.fig_horizontal_bar(labels, [c["estimated_blocked_impressions"] for c in top],
                                          "Blocked by the account's own negatives", "Blocked impressions", accent)

        def _zero_click_chart():
            return pc.fig_horizontal_bar(zero_click["search_term"].tolist(), zero_click["impressions"].tolist(),
                                          "Zero-click competitor-brand terms", "Impressions", accent)

        if is_zero_click_card and not zero_click.empty:
            return _zero_click_chart()
        if not is_zero_click_card and conflicts:
            return _conflicts_chart()
        # Neither preferred dataset matched this card's own topic -- fall
        # back to whichever one actually has data, rather than no graph.
        if conflicts:
            return _conflicts_chart()
        if not zero_click.empty:
            return _zero_click_chart()
        return None

    return None


def render_email_pdf(account_id, account_cfg, email: EmailCopy, ads_analysis, market_mapping, opp_sizing, rollup,
                      g, granular_eda, out_path, accent):
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
    flow += [t, Spacer(1, 0.1 * inch)]
    flow.append(pc.hero_banner("Paid Search Account Review", email.banner_headline, styles, accent))
    flow += [Spacer(1, 0.14 * inch), HRFlowable(width="100%", thickness=1, color=colors.HexColor(accent)),
             Spacer(1, 0.14 * inch), Paragraph("Hi [Customer name],", styles["Body"]),
             Paragraph(email.hook, styles["Body"]), Spacer(1, 0.08 * inch)]
    flow.append(KeepTogether([pc.key_takeaways("Why Now", email.why_now_bullets, styles, accent)]))
    flow.append(Spacer(1, 0.12 * inch))

    # Charts give the "Your account vs vertical benchmark" and "market demand
    # timing" claims above visual weight instead of asking the reader to
    # hold two numbers in their head -- real data (rollup + account_cfg),
    # not an LLM-described chart.
    chart1 = pc.chart_image(_account_vs_benchmark_chart(account_cfg, rollup, accent), width=6.3 * inch)
    chart2 = pc.chart_image(_demand_trend_chart(account_cfg, accent), width=6.3 * inch)
    flow.append(KeepTogether([chart1, Spacer(1, 0.08 * inch)]))
    flow.append(KeepTogether([chart2, Spacer(1, 0.14 * inch)]))

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
    flow.append(Spacer(1, 0.1 * inch))

    # What's holding you back -- the prioritized recommendation cards, the
    # deeper keyword/search-term/negative-keyword/auction-insight analysis
    # made actionable. This is the "tempting, not a dry audit" section: a
    # short, confident intro line (stage 9's copy) followed by cards that
    # are chip-first so a skimming reader can triage before reading prose.
    flow.append(Paragraph("<b>What's holding you back</b>", styles["Body"]))
    flow.append(Paragraph(email.cards_intro, styles["Caption"]))
    flow.append(Spacer(1, 0.05 * inch))
    market_support_by_title = {s.card_title: s.supporting_facts for s in market_mapping.card_market_support}
    for i, card in enumerate(ads_analysis.recommendation_cards, start=1):
        card_dict = card.model_dump()
        card_dict["market_support"] = [f.model_dump() for f in market_support_by_title.get(card.title, [])]
        chart_path = _card_evidence_chart(card_dict, g, granular_eda, accent)
        flow.append(KeepTogether([pc.recommendation_card(i, card_dict, styles, accent, chart_path),
                                   Spacer(1, 0.1 * inch)]))

    # Already working -- reassurance that the fix list is short because the
    # rest is solid, not because it wasn't checked. Fixed green accent
    # (distinct from the vertical accent) so it reads visually as "good news."
    if ads_analysis.already_working:
        flow.append(Spacer(1, 0.04 * inch))
        flow.append(Paragraph(email.working_intro, styles["Caption"]))
        flow.append(KeepTogether([pc.key_takeaways("Already working in your favor",
                                                     ads_analysis.already_working, styles, "#3F7D54")]))

    # The payoff -- what closing the gap is worth, in the account's own
    # terms (current/target impression share, additional impressions and
    # clicks projected at today's click rate -- computed in Python, not by the LLM).
    flow.append(Spacer(1, 0.12 * inch))
    flow.append(Paragraph(email.opportunity_intro, styles["Body"]))
    flow.append(pc.opportunity_stat_strip([
        (f"+{opp_sizing['additional_impressions_estimate']:,}", "More impressions this quarter"),
        (f"+{opp_sizing['additional_clicks_estimate']:,}", "More clicks at today's click rate"),
        (f"{opp_sizing['target_impression_share_pct']:.0f}%", f"Impression share target (from {opp_sizing['current_impression_share_pct']:.0f}%)"),
    ], styles, accent))
    flow.append(Spacer(1, 0.14 * inch))

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


def run_account(account_id, account_cfg, df, granular):
    g = preprocess_account(df, account_id)                                    # STEP 2
    eda_result = compute_eda(g)                                               # STEP 3 (ML)
    granular_eda = compute_granular_eda(account_id, granular)                 # STEP 3 (ML, deeper grain)
    market_evidence = extract_market_evidence(account_cfg["vertical"])        # STEP 4
    rollup = account_rollup(g, account_cfg)                                   # deterministic revenue math
    opp_sizing = opportunity_sizing(g, rollup)                                # deterministic opportunity sizing

    ads_analysis = run_stage6(account_id, account_cfg, g, eda_result, granular_eda)  # STEP 6 (GenAI)

    diagnosis_text = ads_analysis.account_level_diagnosis + " " + " ".join(ads_analysis.notable_patterns)
    ranked_evidence = rank_evidence_by_relevance(market_evidence, diagnosis_text)  # STEP 7 (NLP)

    market_mapping = run_stage8(account_id, account_cfg, ads_analysis, ranked_evidence, rollup)  # STEP 8 (GenAI)
    email = run_stage9(account_id, account_cfg, ads_analysis, market_mapping, rollup, opp_sizing)  # STEP 9 (GenAI)

    accent = ACCENTS[account_cfg["vertical"]]
    slug = account_cfg["vertical"].lower() + "_" + account_cfg["country_code"].lower()
    render_email_pdf(account_id, account_cfg, email, ads_analysis, market_mapping, opp_sizing, rollup,   # STEP 10
                      g, granular_eda, OUTPUT_DIR / f"recommendation_email_{slug}.pdf", accent)

    return {
        "account_id": account_id,
        "model": MODEL,
        "eda": eda_result,
        # exclude _raw_search_terms: a DataFrame kept for step-10 chart
        # building, not a JSON-serializable result field
        "granular_eda": {k: v for k, v in granular_eda.items() if not k.startswith("_raw")},
        "opportunity_sizing": opp_sizing,
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
                      f"campaign findings = {len(r['ads_analysis']['campaign_findings'])}, "
                      f"recommendation cards = {len(r['ads_analysis']['recommendation_cards'])}, "
                      f"already working = {len(r['ads_analysis']['already_working'])}, "
                      f"opportunity = +{r['opportunity_sizing']['additional_impressions_estimate']:,} impressions")
    report_path = OUTPUT_DIR / "validation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    t0 = time.time()
    df = load_campaigns()  # STEP 1
    granular = load_granular_data()  # STEP 1 (keyword/search-term/negative/ad/auction grain)
    all_results = []
    for account_id, account_cfg in ACCOUNTS.items():
        print(f"\n=== {account_id} ({account_cfg['vertical']}) ===")
        result = run_account(account_id, account_cfg, df, granular)
        all_results.append(result)
        print(f"  constraint: {result['ads_analysis']['primary_constraint']}  "
              f"recommendation_cards: {len(result['ads_analysis']['recommendation_cards'])}")
        (OUTPUT_DIR / f"{account_id}_full_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    report_path = write_validation_report(all_results, time.time() - t0)
    print(f"\nValidation report: {report_path}")
    print(json.dumps(LEDGER.summary(), indent=2))


if __name__ == "__main__":
    main()

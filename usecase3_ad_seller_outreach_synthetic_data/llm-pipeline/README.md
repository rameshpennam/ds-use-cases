# ML + NLP + GenAI Recommendation Pipeline

One script (`run_pipeline.py`) that reads the synthetic ads data from
`../ads-data/`, runs it through ML, NLP, and GenAI stages, and produces a
real customer-facing recommendation email PDF per account. **This is a
separate, deeper pipeline on top of `../scripts/generate_emails.py`** --
that script hand-writes the email copy per account; this one derives
everything (diagnosis, market "why now" case, email copy) live from a
single LLM call per stage, grounded in the same underlying ads data and
market-report PDFs.

**Everything downstream is still synthetic** -- same watermark, same
no-real-vendor-names rule as the rest of `pilot-synthetic-data/`.

## Why this exists, in concrete terms

A real digital-marketing analyst's account review digs well below
campaign-level aggregates: individual keyword quality scores, the literal
search queries that triggered an ad (including competitor-brand leakage),
negative keywords that are accidentally blocking the advertiser's own
terms, ad-copy strength ratings, and head-to-head auction position against
named competitors. `campaigns.csv` alone can't show any of that -- it only
has campaign-level numbers plus a few summary counts. `../ads-data/keywords.csv`,
`search_terms.csv`, `negative_keyword_conflicts.csv`, `ads.csv`, and
`auction_insights.csv` (built by `../scripts/generate_granular_ads_data.py`)
supply that grain, and `compute_granular_eda()` turns it into evidence
stage 6 can reason over -- the same depth a real analyst digs through,
not just the aggregate numbers. The output is correspondingly richer: each
account's `AdsAnalysis.recommendation_cards` is a prioritized, chip-tagged
fix list (affects / priority / timeframe / what-to-watch), not a single
diagnosis paragraph, plus an `already_working` list and a Python-computed
`opportunity_sizing` payoff estimate -- modeled on how a real account
review is actually structured, but kept short and chip-first rather than
a page-after-page audit, and written with response-optimized sales tone
throughout (see `STAGE9_SYSTEM`) since the goal is a reply, not a report.

## Why three different tech stacks, not one

Each stage below uses the tool actually suited to the job, not one
technology stretched to cover everything:

| Stack | Where | What it does | Why not GenAI here |
|---|---|---|---|
| **ML** (scikit-learn, scipy) | Step 3 | Pearson correlation of every numeric column against missed impressions (campaign grain) AND quality-score-vs-impression-share / quality-score-vs-cost-per-conversion (keyword grain), IsolationForest anomaly scoring, KMeans clustering, materiality ranking, zero-click/negative-conflict/ad-strength/auction-insight rollups | Cheap, deterministic, and exact -- no reason to ask an LLM to estimate a correlation coefficient |
| **NLP** (TF-IDF + cosine similarity) | Step 7 | Scores every fact extracted from the 4 market-report PDFs against *this account's own* diagnosis text, keeps only the closest matches | A classic retrieval problem -- find the most relevant few facts out of ~70 extracted rows -- that's cheaper and more precise with vector similarity than asking a model to read all 70 and guess |
| **GenAI** (OpenAI, structured outputs) | Steps 6, 8, 9 | Forms the account diagnosis from raw campaign data + ML evidence; builds the "why now" case from the NLP-shortlisted market facts; writes the email copy | These three are genuinely open-ended natural-language reasoning and writing tasks -- the one place an LLM is the right tool |

GenAI is never used to *validate* the ML output or just rephrase numbers --
each GenAI call forms its own judgment from raw evidence it's handed, and
the prompts are explicit about that (see `STAGE6_SYSTEM`, `STAGE8_SYSTEM`,
`STAGE9_SYSTEM` in `run_pipeline.py`).

## What stays deterministic, never delegated to the LLM

The headline revenue-opportunity figure and each campaign's dollar share of
it (`account_rollup()`) are computed once in Python straight from
`campaigns.csv`. Every GenAI call is handed these exact, pre-formatted
figures with an explicit "use verbatim, do not recompute" instruction --
the LLM never does the arithmetic, so every dollar amount in the final
email traces back to the CSV, not to a model's guess.

## The 11 steps, one line each

1. **Read input data** -- load `ads-data/campaigns.csv`.
2. **Pre-processing** -- slice to one account, add the `missed` (eligible −
   actual impressions) column every later step needs.
3. **EDA / ML** -- Pearson correlations vs. missed impressions, IsolationForest
   anomaly scores, KMeans clusters, and the materiality ranking (the ~70%-of-
   the-gap subset of campaigns, not all of them) at campaign grain
   (`compute_eda`); quality-score correlations, high-QS/low-IS and low-QS/
   high-spend keyword findings, zero-click competitor-brand search-term
   waste, negative-keyword conflict costs, ad-strength distribution, and
   auction-insight position vs. named competitors at the deeper grain
   (`compute_granular_eda`).
4. **Parse market PDFs** -- real `pdfplumber` table extraction from the 4
   vendor-style PDFs in `../market-reports/` (not read from `benchmarks.py` --
   a production pipeline only has the PDFs).
5. **Pydantic schemas** -- the structured-JSON contract for every GenAI call.
6. **GenAI: ads-data analysis** -- one LLM call forms its own diagnosis
   (rank-constrained / budget-constrained / healthy) from the raw campaign
   data plus ALL of step 3's evidence, producing a prioritized
   `recommendation_cards` list (each chip-tagged: affects / priority /
   timeframe, with the specific evidence, concrete steps, and a leading
   indicator to watch) and an `already_working` list.
7. **NLP: relevance ranking** -- TF-IDF + cosine similarity ranks every
   extracted market fact against this account's step-6 diagnosis text;
   only the closest matches move on.
8. **GenAI: market mapping** -- one LLM call builds the "why now" case from
   the NLP-shortlisted facts, citing the vendor and number for each.
9. **GenAI: email copy** -- one LLM call drafts the persuasive connective
   tissue (hook, "why now" bullets, the headline stat, short intros for the
   recommendation-card / already-working / opportunity-sizing sections, a
   fix with a low-friction ask) -- it does NOT reproduce the cards or
   numbers themselves, those render directly from steps 6 and the
   deterministic `opportunity_sizing()` calculation.
10. **Render PDF** -- build the email as a real PDF, reusing the existing
    reportlab layout helpers in `../scripts/pdf_common.py` (including the
    new chip/recommendation-card/opportunity-stat-strip helpers).
11. **Validation report** -- token/cost totals and a per-account summary,
    written to `output/validation_report.md`.

Steps 6, 7, 8, 9 run once per account (3 accounts = 9 GenAI calls + 3 NLP
rankings per full run).

## Model selection

Single OpenAI model for every GenAI stage, set once as `MODEL` near the top
of `run_pipeline.py`. Deliberately single-provider and single-model:

- **One vendor** -- getting a second provider's API key approved inside an
  enterprise is its own procurement process; this only ever needs one
  credential (`OPENAI_API_KEY`).
- **One model constant, not one per stage** -- a future provider or model
  swap is then a one-line change in this file, not a hunt through every
  call site.

The model ID (`gpt-5.2` at the time this was built) was confirmed live
against this key's own `client.models.list()` call, not guessed -- model
availability changes faster than any assistant's training data, so the
script trusts the API's own model listing over assumed names.

## Two safety nets on every structured call, not just prompt instructions

Both live in `_call_openai()`, applied to every GenAI response before it's
returned anywhere else in the pipeline:

- `_fix_pdf_unsupported_glyphs()` -- ReportLab's base-14 Helvetica has no
  glyph for some Unicode characters models reach for (hyphen variants,
  arrows). Seen live: "Non-Brand" rendered as "NonnBrand" in the PDF until
  this was added. Prompt wording can't fix a font limitation, so this is
  fixed mechanically, once, for every call.
- `_scrub_real_brand_names()` -- every prompt instructs the model not to
  name a real platform/vendor, but one slipped through anyway (stage 6
  once wrote "validate in the Google Ads 'Negative keyword conflicts'
  view"). This regex backstop catches it even when the prompt doesn't.

## Run

```
cd llm-pipeline
python run_pipeline.py
```

Needs `OPENAI_API_KEY` set in the environment, or present in
`../../backend/.env` (the script reads it from there automatically --
see `_load_env_from_backend()`). Nothing else needs to change to switch
keys or orgs.

Output lands in `output/`: one `{account_id}_full_result.json` (every
stage's structured output, for inspection/debugging), one
`recommendation_email_llm_{vertical}_{country}.pdf` per account, and
`validation_report.md`.

## Relationship to `../scripts/generate_emails.py`

That script is the hand-authored baseline shipped with the synthetic-data
package -- fixed copy per account, used to prove the data model end to end.
This pipeline is the "full solution" version: it re-derives the diagnosis,
the market "why now" case, and the email copy live from the same
underlying data, through real ML + NLP + GenAI stages, rather than reading
pre-written copy. Both read the same `campaigns.csv` and the same 4 market
PDFs, so their outputs are directly comparable.

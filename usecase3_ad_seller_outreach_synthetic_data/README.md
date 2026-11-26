# Pilot Synthetic Data Package

Synthetic data and a working ML + NLP + GenAI pipeline for the
market-context-enriched seller outreach pilot (3 accounts, campaign +
keyword-grain ads data, 4 fictitious vendor-style market research reports,
and the recommendation emails they produce). **Everything in this folder is
synthetic / illustrative.** No real company, account, platform, or
research-vendor data anywhere in this package -- see the watermark on every
generated PDF.

## Why this exists

The pilot's recommendation emails need two things joined together: (1) an
account's own performance data, to diagnose *what's wrong*, and (2) external
market research, to explain *why now*. `scripts/05_analyze_and_generate_emails.py`
is the actual, working implementation of that join: it analyzes `input/`
(campaign + keyword-grain diagnosis; rank-constrained vs. budget-constrained
vs. healthy/demand-surge), ranks evidence from the 4 market reports against
that diagnosis, and drafts the email. See `misc/approach.html` for the full
11-step flow, visually.

## Folder layout

```
input/    -- every input dataset the pipeline reads (campaigndata-*.csv, marketdata-*.pdf)
scripts/  -- numbered, run-in-order generators + the analysis pipeline
output/   -- everything the pipeline produces (JSON results, email PDFs, validation report)
misc/     -- metadata.xlsx and the approach.html flow diagram
```

### `input/`

- **`campaigndata-campaigns.csv`** -- one row per campaign, 143 columns, 22
  rows (5 Travel / 7 Insurance / 10 Retail campaigns -- deliberately uneven,
  matching how a single-product-line vertical vs. a multi-category catalog
  actually differ in campaign count).
- **`campaigndata-keywords.csv`, `campaigndata-search_terms.csv`,
  `campaigndata-negative_keyword_conflicts.csv`, `campaigndata-ads.csv`,
  `campaigndata-auction_insights.csv`** -- the keyword/query/negative-keyword/
  ad-copy/competitive-position grain a real paid-search analyst actually digs
  through, which campaign-level aggregates alone can't show (a keyword
  scoring 9/10 on quality but stuck at 5% impression share; a competitor
  brand name pulling thousands of zero-click impressions; a generic negative
  accidentally blocking the advertiser's own keyword). See the "Granular Ads
  Data Dictionary" tab in `misc/metadata.xlsx` for the full column reference.
- **`marketdata-*.pdf`** -- 4 fictitious vendor-style PDFs, each covering all
  3 verticals:
  - *Ashcroft Research Partners* -- Vertical Digital Advertising Trends (analyst/category benchmarks)
  - *Vantage Media Metrics* -- Media Mix & Ad Intensity Report (cross-channel measurement)
  - *SignalWatch Competitive Intelligence* -- Competitive Ad Spend Monitor (named-competitor tracking)
  - *QueryScope Insights* -- Search Demand & Keyword Intelligence Report (keyword-grain data;
    added beyond the original 3-vendor list because none of the other three measure below
    category level)

  Each report opens with an "About This Report" page explicitly stating what it
  uniquely answers and which of the other 3 reports it does *not* substitute for --
  that's the basis for the "why 4 data-access requests, not 1" business case.

### `scripts/` (run in order)

- `benchmarks.py` -- the single source of truth every generator reads from,
  so the ads data and the 4 reports can never drift apart on a number.
  Shared module, not a numbered step.
- `pdf_common.py` -- shared PDF layout helpers (page template, charts,
  tables, the "Key Takeaways" callout box, priority chips, recommendation
  cards, the opportunity stat strip) -- used by both `03_generate_market_pdfs.py`
  and `05_analyze_and_generate_emails.py`. Shared module, not a numbered step.
- `01_generate_ads_data.py` -- builds `input/campaigndata-campaigns.csv`.
- `02_generate_granular_ads_data.py` -- builds the 5 keyword/search-term/
  negative-keyword/ad-strength/auction-insight files (run after 01, since it
  reads `campaigndata-campaigns.csv` back in).
- `03_generate_market_pdfs.py` -- builds the 4 vendor reports.
- `04_generate_metadata_xlsx.py` -- builds `misc/metadata.xlsx`.
- `05_analyze_and_generate_emails.py` -- **the full ML + NLP + GenAI pipeline.**
  Reads everything in `input/`, analyzes it with scikit-learn (correlations,
  anomaly detection, clustering), ranks market evidence with TF-IDF + cosine
  similarity, and drafts the recommendation email with structured OpenAI
  calls -- built as real customer-facing sales copy rather than an
  analyst-style bullet list: a personalized hook, an explicit "Why Now"
  market-evidence box, a single pulled-out revenue-opportunity number,
  prioritized recommendation cards synthesized from the keyword/search-term/
  negative-keyword/ad-strength/auction-insight evidence, a clearly segregated
  card per campaign that actually has material opportunity
  (`materiality_ranking()` -- the smallest set of campaigns, ranked by
  missed-impression volume, covering ~70% of the account's gap; NOT every
  campaign), an opportunity-sizing payoff, and a single consolidated "Fix"
  callout with a low-friction binary-choice ask. Every number -- including
  each campaign card's revenue slice, which sums exactly back to the
  headline figure -- is recomputed from `campaigndata-campaigns.csv` (not
  hand-typed), so the email always matches the dataset.

### `output/`

- `{account_id}_full_result.json` (x3) -- every stage's structured output,
  for inspection/debugging.
- `recommendation_email_llm_{vertical}_{country}.pdf` (x3) -- the finished
  customer-facing email.
- `validation_report.md` -- token/cost totals and a per-account summary.

### `misc/`

- `metadata.xlsx` -- one workbook, 6 tabs: Overview, Pilot Accounts, Ads
  Data Dictionary (all 143 columns), Granular Ads Data Dictionary (the 5
  keyword/search-term/negative-keyword/ad-strength/auction-insight files),
  Market Vendors Overview, Market Data Dictionary (every extractable field
  per vendor report, mapped to the matching ads-data column where one exists).
- `approach.html` -- a minimal, visual one-pager of the pipeline's 11-step
  flow (inputs, steps color-coded by ML/NLP/GenAI/deterministic, outputs).

## Why three different tech stacks, not one

Each stage of `05_analyze_and_generate_emails.py` uses the tool actually
suited to the job, not one technology stretched to cover everything:

| Stack | Where | What it does | Why not GenAI here |
|---|---|---|---|
| **ML** (scikit-learn, scipy) | Step 3 | Pearson correlation of every numeric column against missed impressions (campaign grain) AND quality-score-vs-impression-share / quality-score-vs-cost-per-conversion (keyword grain), IsolationForest anomaly scoring, KMeans clustering, materiality ranking, zero-click/negative-conflict/ad-strength/auction-insight rollups | Cheap, deterministic, and exact -- no reason to ask an LLM to estimate a correlation coefficient |
| **NLP** (TF-IDF + cosine similarity) | Step 7 | Scores every fact extracted from the 4 market-report PDFs against *this account's own* diagnosis text, keeps only the closest matches | A classic retrieval problem -- find the most relevant few facts out of ~70 extracted rows -- that's cheaper and more precise with vector similarity than asking a model to read all 70 and guess |
| **GenAI** (OpenAI, structured outputs) | Steps 6, 8, 9 | Forms the account diagnosis from raw campaign + keyword-grain data; builds the "why now" case from the NLP-shortlisted market facts; writes the email copy | These three are genuinely open-ended natural-language reasoning and writing tasks -- the one place an LLM is the right tool |

GenAI is never used to *validate* the ML output or just rephrase numbers --
each GenAI call forms its own judgment from raw evidence it's handed, and
the prompts are explicit about that (see `STAGE6_SYSTEM`, `STAGE8_SYSTEM`,
`STAGE9_SYSTEM` in `05_analyze_and_generate_emails.py`).

## What stays deterministic, never delegated to the LLM

The headline revenue-opportunity figure, each campaign's dollar share of it
(`account_rollup()`), and the opportunity-sizing payoff (`opportunity_sizing()`)
are computed once in Python straight from `campaigndata-campaigns.csv`. Every
GenAI call is handed these exact, pre-formatted figures with an explicit
"use verbatim, do not recompute" instruction -- the LLM never does the
arithmetic, so every dollar amount in the final email traces back to the CSV.

## Model selection

Single OpenAI model for every GenAI stage, set once as `MODEL` near the top
of `05_analyze_and_generate_emails.py`. Deliberately single-provider and
single-model:

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

## Regenerating everything from scratch

```
cd scripts
python 01_generate_ads_data.py
python 02_generate_granular_ads_data.py
python 03_generate_market_pdfs.py
python 04_generate_metadata_xlsx.py
python 05_analyze_and_generate_emails.py
```

Run in that order -- 02 reads `input/campaigndata-campaigns.csv` back in
(built by 01), and 05 reads everything 01-03 produced. Needs
`OPENAI_API_KEY` set in the environment, or present in `../../backend/.env`
(05 reads it from there automatically -- see `_load_env_from_backend()`).
Nothing else needs to change to switch keys or orgs.

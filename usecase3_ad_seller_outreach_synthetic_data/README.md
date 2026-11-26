# Pilot Synthetic Data Package

Synthetic data for the market-context-enriched seller outreach pilot (3 accounts,
campaign-level ads data + 4 fictitious vendor-style market research reports +
3 example recommendation emails). **Everything in this folder is synthetic /
illustrative.** No real company, account, platform, or research-vendor data
anywhere in this package -- see the watermark on every generated PDF.

## Why this exists

The pilot's recommendation emails need two things joined together: (1) an
account's own performance data, to diagnose *what's wrong*, and (2) external
market research, to explain *why now*. Before real data access is in place,
this package lets a developer build and test that join end to end.

**Intended pipeline:**
1. **Stage 1 -- analyze the campaign data alone.** `ads-data/campaigns.csv` must
   be sufficient on its own to diagnose the issue: rank-constrained vs.
   budget-constrained vs. healthy/demand-surge (see
   `impression_share_lost_budget_pct` vs. `impression_share_lost_rank_pct`,
   and the `spend_m1/m2/m3` monthly trend columns).
2. **Stage 2 -- join in market context.** Pull the matching vertical/country/
   period section from the 4 reports in `market-reports/` for external
   evidence and timing ("why now").
3. **Stage 3 -- draft the email.** `recommendation-emails/` shows the intended
   end state: one example output per account.

## Contents

- **`ads-data/campaigns.csv`** -- one row per campaign, 143 columns, 22 rows
  (5 Travel / 7 Insurance / 10 Retail campaigns -- deliberately uneven,
  matching how a single-product-line vertical vs. a multi-category catalog
  actually differ in campaign count).
- **`ads-data/keywords.csv`, `search_terms.csv`, `negative_keyword_conflicts.csv`,
  `ads.csv`, `auction_insights.csv`** -- the keyword/query/negative-keyword/
  ad-copy/competitive-position grain a real paid-search analyst actually digs
  through, which campaign-level aggregates alone can't show (a keyword
  scoring 9/10 on quality but stuck at 5% impression share; a competitor
  brand name pulling thousands of zero-click impressions; a generic negative
  accidentally blocking the advertiser's own keyword). Built by
  `scripts/generate_granular_ads_data.py`, which reads `campaigns.csv` back
  in so the two can never disagree. See the "Granular Ads Data Dictionary"
  tab in `metadata.xlsx` for the full column reference.
- **`market-reports/`** -- 4 fictitious vendor-style PDFs, each covering all
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
- **`recommendation-emails/`** -- one example AI-drafted email per account,
  built as real customer-facing sales copy rather than an analyst-style
  bullet list: a personalized hook, an explicit "Why Now" market-evidence
  box, a single pulled-out revenue-opportunity number, then a clearly
  segregated card per campaign that actually has material opportunity
  (`in_scope_campaigns()` in `generate_emails.py` -- the smallest set of
  campaigns, ranked by missed-impression volume, covering ~70% of the
  account's gap; NOT every campaign, and the count varies per account: 3 of
  7 for Insurance, 5 of 10 for Retail, 2 of 5 for Travel), a single
  consolidated "Fix" callout with a low-friction binary-choice ask, and two
  supporting charts. Every number -- including each campaign card's revenue
  slice, which sums exactly back to the headline figure -- is recomputed
  from `campaigns.csv` (not hand-typed), so the email always matches the
  dataset.
- **`metadata.xlsx`** -- one workbook, 5 tabs: Overview, Pilot Accounts, Ads
  Data Dictionary (all 143 columns), Market Vendors Overview, Market Data
  Dictionary (every extractable field per vendor report, mapped to the
  matching ads-data column where one exists).
- **`scripts/`** -- the generators, for reproducibility:
  - `benchmarks.py` -- the single source of truth every other file reads
    from, so the ads data, the 4 reports, and the 3 emails can never drift
    apart on a number.
  - `generate_ads_data.py` -- builds `campaigns.csv`.
  - `generate_granular_ads_data.py` -- builds the 5 keyword/search-term/
    negative-keyword/ad-strength/auction-insight files (run after
    `generate_ads_data.py`, since it reads `campaigns.csv` back in).
  - `generate_market_pdfs.py` -- builds the 4 vendor reports.
  - `generate_emails.py` -- builds the 3 recommendation emails (reads back
    from `campaigns.csv`, same as a real downstream consumer would).
  - `generate_metadata_xlsx.py` -- builds `metadata.xlsx`.
  - `pdf_common.py` -- shared PDF layout helpers (page template, charts,
    tables, the "Key Takeaways" callout box).

## Regenerating

```
cd scripts
python generate_ads_data.py
python generate_granular_ads_data.py
python generate_market_pdfs.py
python generate_emails.py
python generate_metadata_xlsx.py
```

Run in that order -- `generate_granular_ads_data.py` and `generate_emails.py`
both read `ads-data/campaigns.csv` back in rather than recomputing its own
numbers, the same way a real pipeline would.

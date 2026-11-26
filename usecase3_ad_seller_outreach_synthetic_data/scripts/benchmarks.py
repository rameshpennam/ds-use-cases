"""
Single source of truth for every number that must agree across:
  - input/campaigndata-campaigns.csv (and the 5 granular campaigndata-*.csv files)
  - the 4 research-vendor PDFs, input/marketdata-*.pdf
  - the 3 per-account recommendation emails in output/

This mirrors the "one scoring module, everything else reads from it" pattern
used elsewhere in this repo (see backend/app/uc7/scoring.py) so the synthetic
data can never quietly drift between the two sides of the pilot.

Everything here is SYNTHETIC / ILLUSTRATIVE. No real company, vendor, or
platform names anywhere in this file or anything generated from it.
"""

REPORT_PERIOD = "Q3 2026"
PRIOR_PERIOD = "Q2 2026"
PERIOD_START = "2026-07-01"
PERIOD_END = "2026-09-30"
DATA_AS_OF = "2026-10-03"

# Four fictitious research vendors, each covering a distinct data type.
# Chosen so the "data & tools required" gap list has a clean 1:1 mapping:
# one access request per vendor, each justified by a different metric family.
VENDORS = {
    "analyst": {
        "name": "Ashcroft Research Partners",
        "short": "Ashcroft",
        "report_title": "Vertical Digital Advertising Trends",
        "report_code": "ashcroft_vertical_ad_trends_2026q3",
        "data_type": "Category-level spend/demand trend analysis, quarterly outlook, maturity benchmarks",
        "format": "Quarterly analyst report, narrative + benchmark tables, ~28 pages",
    },
    "media_mix": {
        "name": "Vantage Media Metrics",
        "short": "Vantage",
        "report_title": "Media Mix & Ad Intensity Report",
        "report_code": "vantage_media_mix_2026q3",
        "data_type": "Cross-channel spend share, reach/frequency, ad intensity index",
        "format": "Quarterly measurement report, charts + methodology, ~20 pages",
    },
    "competitive": {
        "name": "SignalWatch Competitive Intelligence",
        "short": "SignalWatch",
        "report_title": "Competitive Ad Spend Monitor",
        "report_code": "signalwatch_competitive_spend_2026q3",
        "data_type": "Named-competitor spend share, creative counts, channel presence",
        "format": "Quarterly competitive tracking report, tables + trend charts, ~16 pages",
    },
    "search_demand": {
        "name": "QueryScope Insights",
        "short": "QueryScope",
        "report_title": "Search Demand & Keyword Intelligence Report",
        "report_code": "queryscope_search_demand_2026q3",
        "data_type": "Query volume trends, keyword-level CPC benchmarks, SERP competitive density",
        "format": "Quarterly keyword intelligence report, tables + charts, ~17 pages",
        "note": "Not in the original 3-vendor list -- added because none of the other "
                "three vendors report at keyword/query grain, which is what the "
                "non-brand search campaigns actually compete on.",
    },
}

# ---------------------------------------------------------------------------
# Per-account / per-vertical configuration.
# Account 1 (Insurance/DE) numbers are reverse-engineered to match the
# illustrative mock-up email that was already approved, so the synthetic
# dataset reproduces it almost exactly rather than inventing a new story.
# ---------------------------------------------------------------------------

ACCOUNTS = {
    "DE-INS-001": {
        "account_name": "Pilot Account - Insurance (DE)",
        "vertical": "Insurance",
        "sub_verticals": ["Auto Insurance", "Home Insurance", "Life Insurance"],
        "country": "Germany",
        "country_code": "DE",
        "currency": "EUR",
        "currency_symbol": "EUR",
        "narrative": "rank-constrained",
        "story": (
            "Large, budget-unconstrained account that is structurally losing "
            "share to competitors on auction rank, not spend. The fix is bid "
            "strategy / quality, not budget."
        ),
        "market": {
            "spend_growth_qoq_pct": 18.0,
            "query_demand_growth_qoq_pct": 12.0,
            "cpc_growth_qoq_pct": 7.0,
        },
        "demand_index": {
            "Q4 2025": {"current": 100, "prior_year": 92},
            "Q1 2026": {"current": 104, "prior_year": 96},
            "Q2 2026": {"current": 110, "prior_year": 101},
            "Q3 2026": {"current": 130, "prior_year": 110},
        },
        "benchmark_impression_share_pct": 21.0,
        "benchmark_lost_rank_pct": 54.0,
        "target_account_impression_share_pct": 9.05,
        "target_account_lost_budget_pct": 0.0,
        "target_account_lost_rank_pct": 90.95,
        "daily_budget": 52768,
        "upside_incremental_impressions_period": 560000,
        "upside_qualified_impressions_period": 5100000,
        "channel_mix_pct": {"Search": 38, "Social": 22, "Display": 15, "Video/CTV": 18, "Other": 7},
        "ad_intensity_index": 112,
        "reach_pct": 64,
        "frequency": 3.2,
        "competitors": [
            {"name": "Bluewave Insurance", "spend_share_pct": 24, "creative_count": 48, "channels": "Search, Social, Display"},
            {"name": "Harborline Mutual", "spend_share_pct": 19, "creative_count": 36, "channels": "Search, Video"},
            {"name": "Crestfield Direct", "spend_share_pct": 15, "creative_count": 29, "channels": "Search, Social"},
            {"name": "Nordkreuz Assurance", "spend_share_pct": 12, "creative_count": 22, "channels": "Display"},
        ],
        "account_spend_share_pct": 6.0,
        "keyword_cpc_benchmark": 4.85,
        "keyword_cpc_growth_qoq_pct": 7.0,
        "serp_competitive_density_index": 118,
    },
    "GR-RET-001": {
        "account_name": "Pilot Account - Retail (GR)",
        "vertical": "Retail",
        "sub_verticals": ["Apparel", "Electronics", "Seasonal / Promotional"],
        "country": "Greece",
        "country_code": "GR",
        "currency": "EUR",
        "currency_symbol": "EUR",
        "narrative": "budget-constrained",
        "story": (
            "Mid-size account that is hitting its daily budget cap most days. "
            "Demand and auction eligibility are fine -- the account simply "
            "cannot afford to show up for all of it. The fix is budget, not bids."
        ),
        "market": {
            "spend_growth_qoq_pct": 9.0,
            "query_demand_growth_qoq_pct": 6.0,
            "cpc_growth_qoq_pct": 4.0,
        },
        "demand_index": {
            "Q4 2025": {"current": 100, "prior_year": 97},
            "Q1 2026": {"current": 103, "prior_year": 99},
            "Q2 2026": {"current": 107, "prior_year": 102},
            "Q3 2026": {"current": 112, "prior_year": 106},
        },
        "benchmark_impression_share_pct": 35.0,
        "benchmark_lost_budget_pct": 38.0,
        "target_account_impression_share_pct": 22.0,
        "target_account_lost_budget_pct": 78.0,
        "target_account_lost_rank_pct": 0.0,
        # Daily budget and volume are scaled down from the original US figures
        # to reflect Greece's much smaller addressable search market (~11M
        # population vs. ~330M) -- the budget-constrained STORY (percentages,
        # utilization) stays identical, only the absolute market size changes.
        "daily_budget": 420,
        "upside_incremental_impressions_period": 95000,
        "upside_qualified_impressions_period": 520000,
        "channel_mix_pct": {"Search": 30, "Social": 33, "Display": 12, "Video/CTV": 20, "Other": 5},
        "ad_intensity_index": 97,
        "reach_pct": 66,
        "frequency": 3.6,
        "competitors": [
            {"name": "Delphi Retail Group", "spend_share_pct": 24, "creative_count": 48, "channels": "Search, Social, Video"},
            {"name": "Marathon Mercantile", "spend_share_pct": 19, "creative_count": 38, "channels": "Search, Social"},
            {"name": "Ionian Goods Co", "spend_share_pct": 15, "creative_count": 30, "channels": "Social, Display"},
            {"name": "Acropolis Outfitters", "spend_share_pct": 12, "creative_count": 24, "channels": "Search, Video"},
        ],
        "account_spend_share_pct": 11.0,
        "keyword_cpc_benchmark": 0.72,
        "keyword_cpc_growth_qoq_pct": 4.0,
        "serp_competitive_density_index": 102,
    },
    "UK-TRV-001": {
        "account_name": "Pilot Account - Travel (UK)",
        "vertical": "Travel",
        "sub_verticals": ["Flights", "Hotels", "Package Holidays"],
        "country": "United Kingdom",
        "country_code": "GB",
        "currency": "GBP",
        "currency_symbol": "GBP",
        "narrative": "healthy / demand-surge",
        "story": (
            "Account tracking close to the vertical benchmark already. The "
            "story here isn't a gap to close, it's a demand surge (travel "
            "search is up sharply) the account should lean into before "
            "competitors reprice the category."
        ),
        "market": {
            "spend_growth_qoq_pct": 22.0,
            "query_demand_growth_qoq_pct": 19.0,
            "cpc_growth_qoq_pct": 15.0,
        },
        "demand_index": {
            "Q4 2025": {"current": 100, "prior_year": 88},
            "Q1 2026": {"current": 109, "prior_year": 93},
            "Q2 2026": {"current": 121, "prior_year": 99},
            "Q3 2026": {"current": 149, "prior_year": 112},
        },
        "benchmark_impression_share_pct": 40.0,
        "benchmark_lost_rank_pct": 45.0,
        "target_account_impression_share_pct": 37.0,
        "target_account_lost_budget_pct": 15.0,
        "target_account_lost_rank_pct": 48.0,
        "daily_budget": 6200,
        "upside_incremental_impressions_period": 290000,
        "upside_qualified_impressions_period": 1400000,
        "channel_mix_pct": {"Search": 41, "Social": 19, "Display": 10, "Video/CTV": 24, "Other": 6},
        "ad_intensity_index": 104,
        "reach_pct": 58,
        "frequency": 2.8,
        "competitors": [
            {"name": "Skyline Journeys", "spend_share_pct": 22, "creative_count": 45, "channels": "Search, Video"},
            {"name": "Coastal Getaways", "spend_share_pct": 18, "creative_count": 38, "channels": "Search, Social"},
            {"name": "Horizon Holidays", "spend_share_pct": 16, "creative_count": 34, "channels": "Search, Social, Video"},
            {"name": "Trailmark Travel", "spend_share_pct": 11, "creative_count": 26, "channels": "Display, Video"},
        ],
        "account_spend_share_pct": 14.0,
        "keyword_cpc_benchmark": 2.10,
        "keyword_cpc_growth_qoq_pct": 15.0,
        "serp_competitive_density_index": 109,
    },
}

WATERMARK = "SYNTHETIC DATA - FOR INTERNAL PILOT DEVELOPMENT ONLY - NOT REAL RESEARCH"

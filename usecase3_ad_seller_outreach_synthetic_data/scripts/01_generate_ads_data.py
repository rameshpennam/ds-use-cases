"""
Generates input/campaigndata-campaigns.csv (campaign grain, ~130 cols).
The account-level rollup is computed in-memory below purely to verify the
campaign mix lands on the intended per-account story -- it is not written
to disk, since the campaign-grain file is the actual deliverable.

Run:  python 01_generate_ads_data.py
"""
import random
import numpy as np
import pandas as pd
from pathlib import Path

from benchmarks import ACCOUNTS, REPORT_PERIOD, PRIOR_PERIOD, PERIOD_START, PERIOD_END, DATA_AS_OF

OUT_DIR = Path(__file__).resolve().parent.parent / "input"
DAYS_IN_PERIOD = 92

rng = np.random.default_rng(20260930)
pyrand = random.Random(20260930)

# ---------------------------------------------------------------------------
# Hand-authored campaign mix per account. weight = share of account eligible
# impressions. impression_share_pct / lost_budget_pct / lost_rank_pct always
# sum to ~100 per campaign -- that identity is what makes the three accounts'
# weighted rollups land on the three distinct diagnoses (rank-constrained /
# budget-constrained / healthy) instead of needing separate tuning.
# ---------------------------------------------------------------------------

CAMPAIGNS = {
    "DE-INS-001": [
        # name, type, subtype, weight, IS%, lost_budget%
        ("Brand Search - DE", "Search", "Brand", 0.03, 85, 0),
        ("Non-Brand Search - Auto Insurance", "Search", "Non-Brand", 0.35, 6, 0),
        ("Non-Brand Search - Home Insurance", "Search", "Non-Brand", 0.25, 5, 0),
        ("Non-Brand Search - Life Insurance", "Search", "Non-Brand", 0.15, 7, 0),
        ("Performance Max - Insurance Leads", "Performance Max", "Full-Funnel", 0.13, 9, 0),
        ("Audience Network - Retargeting", "Audience", "Retargeting", 0.06, 11, 0),
        ("Dynamic Search Ads - Long Tail", "Dynamic Search Ads", "Long-Tail", 0.03, 8, 0),
    ],
    "GR-RET-001": [
        # Retail carries the most campaigns of the 3 -- realistic, since a
        # multi-category catalog naturally splits into more Shopping/PMax
        # campaigns than a single-product-line vertical does.
        ("Brand Search - GR", "Search", "Brand", 0.04, 60, 40),
        ("Shopping - Apparel", "Shopping", "Non-Brand", 0.18, 18, 82),
        ("Shopping - Electronics", "Shopping", "Non-Brand", 0.16, 17, 83),
        ("Shopping - Home & Garden", "Shopping", "Non-Brand", 0.12, 19, 81),
        ("Shopping - Beauty", "Shopping", "Non-Brand", 0.10, 20, 80),
        ("Non-Brand Search - Seasonal Promo", "Search", "Seasonal", 0.14, 21, 79),
        ("Performance Max - Full Catalog", "Performance Max", "Catalog", 0.13, 19, 81),
        ("Audience Network - Cart Abandonment", "Audience", "Retargeting", 0.06, 27, 73),
        ("Audience Network - Lookalike Prospecting", "Audience", "Retargeting", 0.04, 24, 76),
        ("Dynamic Search Ads - Catalog", "Dynamic Search Ads", "Catalog", 0.03, 22, 78),
    ],
    "UK-TRV-001": [
        # Travel carries the fewest -- a handful of broad campaigns per
        # travel category rather than a per-SKU catalog structure.
        ("Brand Search - UK", "Search", "Brand", 0.07, 70, 10),
        ("Non-Brand Search - Flights", "Search", "Non-Brand", 0.38, 33, 16),
        ("Non-Brand Search - Hotels & Packages", "Search", "Non-Brand", 0.33, 35, 14),
        ("Performance Max - Destinations", "Performance Max", "Full-Funnel", 0.15, 38, 17),
        ("Audience Network - Retargeting", "Audience", "Retargeting", 0.07, 45, 18),
    ],
}

CTR_RANGES = {
    "Brand": (0.085, 0.13),
    "Non-Brand": (0.028, 0.048),
    "Seasonal": (0.030, 0.050),
    "Full-Funnel": (0.018, 0.032),
    "Catalog": (0.010, 0.020),
    "Retargeting": (0.006, 0.014),
    "Long-Tail": (0.022, 0.034),
}
CVR_RANGES = {
    "Brand": (0.07, 0.11),
    "Non-Brand": (0.020, 0.040),
    "Seasonal": (0.022, 0.038),
    "Full-Funnel": (0.025, 0.045),
    "Catalog": (0.018, 0.032),
    "Retargeting": (0.010, 0.022),
    "Long-Tail": (0.016, 0.028),
}
BID_STRATEGY = {
    "Brand": "Manual CPC",
    "Non-Brand": "Target CPA",
    "Seasonal": "Maximize Conversions",
    "Full-Funnel": "Target ROAS",
    "Catalog": "Target ROAS",
    "Retargeting": "Maximize Conversions",
    "Long-Tail": "Enhanced CPC",
}
NETWORK = {
    "Search": "Search Network + Syndicated Partners",
    "Shopping": "Shopping Network",
    "Performance Max": "Cross-Network (Search + Shopping + Display + Video)",
    "Audience": "Native / Content Network",
    "Dynamic Search Ads": "Search Network Only",
}
AOV = {"Insurance": 148.0, "Retail": 92.0, "Travel": 612.0}

GEO_POOL = {
    "Germany": ["Bavaria", "North Rhine-Westphalia", "Baden-Wurttemberg", "Berlin", "Hesse"],
    "Greece": ["Attica", "Central Macedonia", "Thessaly", "Crete", "Western Greece"],
    "United Kingdom": ["England - London", "England - South East", "Scotland", "England - North West", "Wales"],
}
AUDIENCE_POOL = {
    "Insurance": ["In-Market: Auto Insurance Shoppers", "Life Stage: New Homeowners", "Life Stage: New Parents", "Affinity: Financial Planners"],
    "Retail": ["In-Market: Apparel Shoppers", "Affinity: Deal Seekers", "In-Market: Consumer Electronics", "Life Stage: New Movers"],
    "Travel": ["In-Market: Flights", "In-Market: Hotels & Accommodation", "Life Stage: Empty Nesters", "Affinity: Frequent Travelers"],
}
SEARCH_TERMS = {
    "Insurance": [("car insurance quote", 14.0), ("home insurance cost", 9.5), ("life insurance comparison", 7.0), ("cheap auto insurance", 11.0)],
    "Retail": [("mens running shoes", 12.0), ("wireless headphones", 9.0), ("winter jacket sale", 8.5), ("kitchen appliances deals", 7.5)],
    "Travel": [("flights to spain", 13.0), ("all inclusive holidays", 10.0), ("cheap hotel deals", 9.0), ("weekend city breaks", 7.0)],
}
LANGUAGE = {"Germany": "German", "Greece": "Greek", "United Kingdom": "English"}


def jitter(low, high):
    return rng.uniform(low, high)


def build_campaign_row(account_id, acct, idx, name, ctype, subtype, weight, is_pct, lost_budget_pct):
    lost_rank_pct = round(100 - is_pct - lost_budget_pct, 2)
    vertical = acct["vertical"]
    country = acct["country"]

    eligible_impressions = round(acct["upside_qualified_impressions_period"] * weight)
    impressions = round(eligible_impressions * is_pct / 100)
    impressions_prior = round(impressions / (1 + acct["market"]["query_demand_growth_qoq_pct"] / 100))

    ctr_lo, ctr_hi = CTR_RANGES[subtype]
    ctr = jitter(ctr_lo, ctr_hi)
    clicks = round(impressions * ctr)
    clicks_prior = round(impressions_prior * ctr * jitter(0.92, 1.0))
    ctr_prior = round(100 * clicks_prior / max(impressions_prior, 1), 2)

    base_cpc = acct["keyword_cpc_benchmark"]
    cpc_mult = {"Brand": 0.55, "Non-Brand": 1.0, "Seasonal": 0.95, "Full-Funnel": 0.85,
                "Catalog": 0.70, "Retargeting": 0.60, "Long-Tail": 0.75}[subtype]
    avg_cpc = round(base_cpc * cpc_mult * jitter(0.9, 1.1), 2)
    avg_cpc_prior = round(avg_cpc / (1 + acct["market"]["cpc_growth_qoq_pct"] / 100), 2)
    avg_cpm = round(avg_cpc * ctr * 1000, 2)

    spend = round(clicks * avg_cpc, 2)
    spend_prior = round(clicks_prior * avg_cpc_prior, 2)

    cvr_lo, cvr_hi = CVR_RANGES[subtype]
    cvr = jitter(cvr_lo, cvr_hi)
    conversions = round(clicks * cvr, 1)
    cvr_prior = cvr * jitter(0.90, 1.02)
    conversions_prior = round(clicks_prior * cvr_prior, 1)

    aov = AOV[vertical] * jitter(0.9, 1.1)
    conversion_value = round(conversions * aov, 2)
    revenue = conversion_value
    roas = round(revenue / spend, 2) if spend else 0.0
    revenue_prior = round(conversions_prior * aov, 2)
    roas_prior = round(revenue_prior / spend_prior, 2) if spend_prior else 0.0
    cost_per_conversion = round(spend / conversions, 2) if conversions else 0.0

    # Monthly split within the quarter (own-account trend signal -- this is
    # what a stage-1 "analyze the campaign itself" step needs to detect a
    # worsening/improving trajectory before any market data is joined in).
    # Shares are forced to sum exactly back to the quarterly total so every
    # monthly figure traces to the already-computed quarter number.
    m_shares = rng.dirichlet([3, 3.3, 3.6])  # mild ramp across the quarter
    spend_m = [round(spend * s, 2) for s in m_shares]
    spend_m[-1] = round(spend - spend_m[0] - spend_m[1], 2)
    impr_m = [round(impressions * s) for s in m_shares]
    impr_m[-1] = impressions - impr_m[0] - impr_m[1]
    conv_m = [round(conversions * s, 1) for s in m_shares]
    conv_m[-1] = round(conversions - conv_m[0] - conv_m[1], 1)

    # Prior-year actuals, backed out from the account's own query-demand
    # YoY trend (demand_index Q3 2026 vs Q3 2025) rather than an independent
    # random draw -- so "own account trend" and "market demand trend" can be
    # directly compared as an ML feature (self vs. category growth gap).
    di = acct["demand_index"]["Q3 2026"]
    demand_yoy_pct = (di["current"] - di["prior_year"]) / di["prior_year"] * 100
    yoy_factor = (1 + demand_yoy_pct / 100 * jitter(0.85, 1.15))
    impressions_prior_year = round(impressions / yoy_factor)
    spend_prior_year = round(spend / (1 + demand_yoy_pct / 100 * jitter(0.8, 1.2)), 2)
    conversions_prior_year = round(conversions / (1 + demand_yoy_pct / 100 * jitter(0.75, 1.25)), 1)

    utilization = round(min(99.9, 55 + lost_budget_pct * 0.58 + jitter(-4, 4)), 1)
    daily_budget_campaign = round(acct["daily_budget"] * weight, 2)
    monthly_budget_cap = round(daily_budget_campaign * 30.4, 2)

    quality_score = round(np.clip(rng.normal(6.5 - lost_rank_pct * 0.02, 1.0), 2, 10), 1)
    rating_pool = ["Below Average", "Average", "Above Average"]
    rating_weights = [0.5, 0.35, 0.15] if quality_score < 5 else ([0.15, 0.45, 0.4] if quality_score < 7.5 else [0.05, 0.3, 0.65])

    # device split
    if ctype == "Shopping":
        dev = rng.dirichlet([6, 3, 1])
    elif subtype == "Brand":
        dev = rng.dirichlet([5, 4, 1])
    else:
        dev = rng.dirichlet([5.5, 3.5, 1])
    mobile_pct, desktop_pct, tablet_pct = [round(100 * x, 1) for x in dev]

    geo_options = GEO_POOL[country]
    top3 = pyrand.sample(geo_options, 3)
    geo_shares = sorted(rng.dirichlet([5, 3, 2]) * jitter(55, 70), reverse=True)
    rest_geo = round(100 - sum(geo_shares), 1)

    aud_options = AUDIENCE_POOL[vertical]
    aud_top2 = pyrand.sample(aud_options, 2)

    terms = SEARCH_TERMS[vertical]
    term1, term1_share = pyrand.choice(terms), None
    remaining_terms = [t for t in terms if t != term1]
    term2 = pyrand.choice(remaining_terms)

    keyword_count = 0 if ctype in ("Shopping", "Performance Max", "Audience") else int(rng.integers(80, 1400))
    negative_keyword_count = int(rng.integers(20, 600)) if keyword_count else int(rng.integers(0, 80))
    ad_group_count = int(rng.integers(3, 40))
    active_ad_count = int(rng.integers(6, 90))
    disapproved_ad_count = int(rng.integers(0, 3))
    policy_issues_count = int(rng.integers(0, 2))

    days_since_opt = int(rng.integers(1, 45))

    row = {
        "account_id": account_id,
        "account_name": acct["account_name"],
        "vertical": vertical,
        "sub_vertical": subtype if subtype in acct["sub_verticals"] else pyrand.choice(acct["sub_verticals"]),
        "country": country,
        "country_code": acct["country_code"],
        "currency": acct["currency"],
        "account_status": "Active",
        "pilot_flag": "Y",
        "campaign_id": f"{account_id}-C{idx:02d}",
        "campaign_name": name,
        "campaign_type": ctype,
        "campaign_subtype": subtype,
        "campaign_status": "Active",

        "report_period": REPORT_PERIOD,
        "period_start_date": PERIOD_START,
        "period_end_date": PERIOD_END,
        "prior_period": PRIOR_PERIOD,
        "data_as_of_date": DATA_AS_OF,
        "days_in_period": DAYS_IN_PERIOD,

        "bid_strategy": BID_STRATEGY[subtype],
        "target_cpa": round(cost_per_conversion * jitter(0.9, 1.0), 2) if BID_STRATEGY[subtype] == "Target CPA" else None,
        "target_roas": round(roas * jitter(0.95, 1.05), 2) if BID_STRATEGY[subtype] == "Target ROAS" else None,
        "network": NETWORK[ctype],
        "device_targeting": pyrand.choice(["All Devices", "All Devices", "Mobile Preferred"]),
        "language_targeting": LANGUAGE[country],
        "location_targeting": f"National ({country})",
        "ad_schedule": pyrand.choice(["All Days, All Hours", "All Days, All Hours", "Business Hours Weighted"]),
        "ad_rotation": pyrand.choice(["Optimize for Conversions", "Rotate Evenly"]),
        "delivery_method": pyrand.choice(["Standard", "Standard", "Accelerated"]),

        "daily_budget": daily_budget_campaign,
        "monthly_budget_cap": monthly_budget_cap,
        "budget_utilization_pct": utilization,
        "spend": spend,
        "spend_prior_period": spend_prior,
        "spend_qoq_change_pct": round(100 * (spend - spend_prior) / spend_prior, 1) if spend_prior else None,
        "spend_yoy_change_pct": round(acct["market"]["spend_growth_qoq_pct"] * 3.1 * jitter(0.85, 1.1), 1),
        "impressions": impressions,
        "impressions_prior_period": impressions_prior,
        "eligible_impressions": eligible_impressions,
        "search_impression_share_pct": is_pct,
        "impression_share_lost_budget_pct": lost_budget_pct,
        "impression_share_lost_rank_pct": lost_rank_pct,
        "absolute_top_impression_share_pct": round(is_pct * jitter(0.35, 0.55), 1),
        "top_impression_share_pct": round(is_pct * jitter(0.6, 0.85), 1),

        "clicks": clicks,
        "clicks_prior_period": clicks_prior,
        "ctr_pct": round(ctr * 100, 2),
        "ctr_prior_period_pct": ctr_prior,
        "avg_cpc": avg_cpc,
        "avg_cpc_prior_period": avg_cpc_prior,
        "avg_cpc_qoq_change_pct": acct["market"]["cpc_growth_qoq_pct"],
        "avg_cpm": avg_cpm,
        "click_share_pct": round(is_pct * jitter(0.7, 0.95), 1),
        "outranking_share_pct": round(is_pct * jitter(0.8, 1.1), 1),

        "avg_quality_score": quality_score,
        "expected_ctr_rating": pyrand.choices(rating_pool, weights=rating_weights)[0],
        "ad_relevance_rating": pyrand.choices(rating_pool, weights=rating_weights)[0],
        "landing_page_experience_rating": pyrand.choices(rating_pool, weights=rating_weights)[0],
        "vertical_benchmark_impression_share_pct": acct["benchmark_impression_share_pct"],
        "vertical_benchmark_avg_cpc": acct["keyword_cpc_benchmark"],
        "vertical_benchmark_ctr_pct": round(ctr * 100 * jitter(1.1, 1.6), 2),
        "competitive_density_index": acct["serp_competitive_density_index"],

        "conversions": conversions,
        "conversions_prior_period": conversions_prior,
        "conversion_rate_pct": round(cvr * 100, 2),
        "conversion_rate_prior_period_pct": round(cvr_prior * 100, 2),
        "cost_per_conversion": cost_per_conversion,
        "conversion_value": conversion_value,
        "revenue": revenue,
        "roas": roas,
        "roas_prior_period": roas_prior,
        "assisted_conversions": round(conversions * jitter(0.15, 0.4), 1),
        "view_through_conversions": round(conversions * jitter(0.03, 0.12), 1),
        "cross_device_conversions": round(conversions * jitter(0.08, 0.2), 1),
        "new_customer_conversion_pct": round(jitter(35, 70), 1),
        "repeat_customer_conversion_pct": None,
        "avg_order_value": round(aov, 2),
        "cpa_vs_target_pct": None,

        "spend_m1": spend_m[0], "spend_m2": spend_m[1], "spend_m3": spend_m[2],
        "impressions_m1": impr_m[0], "impressions_m2": impr_m[1], "impressions_m3": impr_m[2],
        "conversions_m1": conv_m[0], "conversions_m2": conv_m[1], "conversions_m3": conv_m[2],
        "spend_prior_year": spend_prior_year,
        "impressions_prior_year": impressions_prior_year,
        "conversions_prior_year": conversions_prior_year,

        "demand_index_q4_2025_current": acct["demand_index"]["Q4 2025"]["current"],
        "demand_index_q4_2025_prior_year": acct["demand_index"]["Q4 2025"]["prior_year"],
        "demand_index_q1_2026_current": acct["demand_index"]["Q1 2026"]["current"],
        "demand_index_q1_2026_prior_year": acct["demand_index"]["Q1 2026"]["prior_year"],
        "demand_index_q2_2026_current": acct["demand_index"]["Q2 2026"]["current"],
        "demand_index_q2_2026_prior_year": acct["demand_index"]["Q2 2026"]["prior_year"],
        "demand_index_q3_2026_current": acct["demand_index"]["Q3 2026"]["current"],
        "demand_index_q3_2026_prior_year": acct["demand_index"]["Q3 2026"]["prior_year"],

        "impressions_mobile_pct": mobile_pct,
        "impressions_desktop_pct": desktop_pct,
        "impressions_tablet_pct": tablet_pct,
        "clicks_mobile_pct": round(mobile_pct * jitter(0.95, 1.05), 1),
        "clicks_desktop_pct": round(desktop_pct * jitter(0.95, 1.05), 1),
        "clicks_tablet_pct": round(tablet_pct * jitter(0.9, 1.1), 1),
        "spend_mobile_pct": round(mobile_pct * jitter(0.9, 1.1), 1),
        "spend_desktop_pct": round(desktop_pct * jitter(0.95, 1.1), 1),
        "spend_tablet_pct": round(tablet_pct * jitter(0.85, 1.15), 1),

        "audience_top_segment_1_name": aud_top2[0],
        "audience_top_segment_1_share_pct": round(jitter(18, 34), 1),
        "audience_top_segment_2_name": aud_top2[1],
        "audience_top_segment_2_share_pct": round(jitter(8, 18), 1),
        "age_group_top_name": pyrand.choice(["25-34", "35-44", "45-54"]),
        "age_group_top_share_pct": round(jitter(22, 32), 1),
        "gender_male_share_pct": round(jitter(38, 62), 1),
        "gender_female_share_pct": None,  # filled below

        "top_region_1_name": top3[0], "top_region_1_spend_share_pct": round(geo_shares[0], 1),
        "top_region_2_name": top3[1], "top_region_2_spend_share_pct": round(geo_shares[1], 1),
        "top_region_3_name": top3[2], "top_region_3_spend_share_pct": round(geo_shares[2], 1),
        "top_city_name": top3[0] + " Metro",
        "top_city_spend_share_pct": round(geo_shares[0] * jitter(0.4, 0.6), 1),
        "rest_of_geo_spend_share_pct": rest_geo,

        "keyword_count": keyword_count,
        "negative_keyword_count": negative_keyword_count,
        "active_ad_count": active_ad_count,
        "disapproved_ad_count": disapproved_ad_count,
        "ad_group_count": ad_group_count,
        "top_search_term_1": term1[0],
        "top_search_term_1_share_pct": term1[1],
        "top_search_term_2": term2[0],
        "top_search_term_2_share_pct": term2[1] * jitter(0.6, 0.85),
        "policy_issues_count": policy_issues_count,

        "last_optimization_date": "2026-09-" + str(30 - min(days_since_opt, 29)).zfill(2),
        "days_since_last_optimization": days_since_opt,
        "active_campaign_count_account": len(CAMPAIGNS[account_id]),
        "paused_campaign_count_account": 0,
        "account_tenure_months": acct.get("account_tenure_months", int(rng.integers(14, 58))),
        # seller_notes_flag / seller_note_text / primary_constraint_hint are
        # filled in after all campaigns for the account are built, so the
        # "flag the 2 neediest campaigns" logic can look across the full set.
        "seller_notes_flag": "N",
        "seller_note_text": None,
        "primary_constraint_hint": acct["narrative"],
    }
    row["gender_female_share_pct"] = round(100 - row["gender_male_share_pct"], 1)
    return row


SELLER_NOTES = {
    "DE-INS-001": "Seller flagged: strong auction eligibility but consistently outranked by "
                  "larger competitors on non-brand terms; customer has indicated openness to "
                  "revisiting bid strategy at this renewal.",
    "GR-RET-001": "Seller flagged: campaign exhausts its daily budget most days well before "
                  "end-of-day; customer has asked about a mid-quarter budget increase.",
    "UK-TRV-001": "Seller flagged: booking volume up sharply this quarter; customer is "
                  "weighing expansion into adjacent destinations before competitors reprice.",
}


def main():
    all_rows = []
    for account_id, acct in ACCOUNTS.items():
        for idx, (name, ctype, subtype, weight, is_pct, lost_budget_pct) in enumerate(CAMPAIGNS[account_id], start=1):
            all_rows.append(build_campaign_row(account_id, acct, idx, name, ctype, subtype, weight, is_pct, lost_budget_pct))

    campaigns_df = pd.DataFrame(all_rows)

    # Flag the 2 campaigns per account with the largest combined share lost
    # (to rank + to budget) -- i.e. the ones a seller would actually act on
    # first -- and attach a short grounding note a GenAI drafting step can
    # quote or paraphrase directly.
    campaigns_df["seller_notes_flag"] = "N"
    campaigns_df["seller_note_text"] = None
    for account_id, grp in campaigns_df.groupby("account_id"):
        needy = (grp["impression_share_lost_budget_pct"] + grp["impression_share_lost_rank_pct"]).nlargest(2).index
        campaigns_df.loc[needy, "seller_notes_flag"] = "Y"
        campaigns_df.loc[needy, "seller_note_text"] = SELLER_NOTES[account_id]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    campaigns_df.to_csv(OUT_DIR / "campaigndata-campaigns.csv", index=False)

    # ---- rollup is computed here ONLY to verify the campaign mix lands on
    # the intended account-level story; it is not written as its own file
    # (single campaign-grain dataset is the deliverable).
    weight_col = "eligible_impressions"
    additive = [
        "spend", "spend_prior_period", "impressions", "impressions_prior_period",
        "eligible_impressions", "clicks", "clicks_prior_period", "conversions",
        "conversions_prior_period", "conversion_value", "revenue",
        "assisted_conversions", "view_through_conversions", "cross_device_conversions",
        "keyword_count", "negative_keyword_count", "active_ad_count",
        "disapproved_ad_count", "ad_group_count", "policy_issues_count",
    ]
    identity = [
        "account_id", "account_name", "vertical", "country", "country_code",
        "currency", "account_status", "pilot_flag", "report_period",
        "period_start_date", "period_end_date", "prior_period", "data_as_of_date",
        "days_in_period", "demand_index_q4_2025_current", "demand_index_q4_2025_prior_year",
        "demand_index_q1_2026_current", "demand_index_q1_2026_prior_year",
        "demand_index_q2_2026_current", "demand_index_q2_2026_prior_year",
        "demand_index_q3_2026_current", "demand_index_q3_2026_prior_year",
        "vertical_benchmark_impression_share_pct", "vertical_benchmark_avg_cpc",
        "competitive_density_index", "active_campaign_count_account",
        "paused_campaign_count_account", "account_tenure_months",
    ]
    weighted_avg = [
        "search_impression_share_pct", "impression_share_lost_budget_pct",
        "impression_share_lost_rank_pct", "absolute_top_impression_share_pct",
        "top_impression_share_pct", "ctr_pct", "ctr_prior_period_pct", "avg_cpc",
        "avg_cpc_prior_period", "avg_cpm", "click_share_pct", "outranking_share_pct",
        "avg_quality_score", "conversion_rate_pct", "conversion_rate_prior_period_pct",
        "cost_per_conversion", "roas", "roas_prior_period", "new_customer_conversion_pct",
        "avg_order_value", "budget_utilization_pct", "impressions_mobile_pct",
        "impressions_desktop_pct", "impressions_tablet_pct",
    ]

    account_rows = []
    for account_id, grp in campaigns_df.groupby("account_id"):
        w = grp[weight_col]
        row = {col: grp[col].iloc[0] for col in identity}
        for col in additive:
            row[col] = grp[col].sum()
        for col in weighted_avg:
            row[col] = round(np.average(grp[col], weights=w), 2)
        row["spend_qoq_change_pct"] = round(100 * (row["spend"] - row["spend_prior_period"]) / row["spend_prior_period"], 1)
        row["daily_budget"] = grp["daily_budget"].sum()
        row["monthly_budget_cap"] = grp["monthly_budget_cap"].sum()
        row["num_campaigns"] = len(grp)
        row["num_campaign_types"] = grp["campaign_type"].nunique()
        account_rows.append(row)

    accounts_df = pd.DataFrame(account_rows)

    print(f"campaigndata-campaigns.csv: {campaigns_df.shape[0]} rows x {campaigns_df.shape[1]} cols")
    print("(account-level rollup computed in-memory for verification only, not written to disk)")
    print()
    for _, r in accounts_df.iterrows():
        print(f"{r['account_id']:12s} IS%={r['search_impression_share_pct']:>6.2f}  "
              f"lost_budget%={r['impression_share_lost_budget_pct']:>6.2f}  "
              f"lost_rank%={r['impression_share_lost_rank_pct']:>6.2f}  "
              f"sum={r['search_impression_share_pct']+r['impression_share_lost_budget_pct']+r['impression_share_lost_rank_pct']:.2f}")


if __name__ == "__main__":
    main()

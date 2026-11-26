"""
Generates the keyword/search-term/negative-keyword/ad-strength/auction-insight
granularity that a real paid-search analyst actually digs through before
writing a recommendation -- campaigns.csv alone only gives account/campaign-
level aggregates (and a few summary counts like keyword_count), not the
row-level evidence a human analyst cites ("'insurance agencies' scores 10/10
on quality but only gets 5% impression share").

Five new files land in ads-data/, each keyed back to the account_id and
campaign_id already in campaigns.csv (read back in here, same pattern as
generate_emails.py, so this can never drift from the campaign-level numbers):

  keywords.csv                 -- per-keyword quality score / impression share
                                   / spend, for Search & Dynamic-Search-Ads
                                   campaigns only (Shopping/PMax/Audience are
                                   not keyword-targeted, same as the real
                                   platforms this mirrors)
  search_terms.csv              -- actual queries that triggered an ad,
                                   including zero-click competitor-brand
                                   leakage (fictitious competitor names only)
  negative_keyword_conflicts.csv -- generic negatives that are accidentally
                                   blocking the advertiser's own keywords
  ads.csv                       -- ad-copy strength ratings per ad group
  auction_insights.csv          -- this account's position vs. its own
                                   fictitious named competitors (list already
                                   defined in benchmarks.py ACCOUNTS[...]["competitors"])

These are the "top N by volume" entries, same as a real analyst report would
show (it never lists literally every keyword or search term either) -- NOT
an exhaustive export. Said explicitly in metadata.xlsx, not implied.

Run after generate_ads_data.py:  python generate_granular_ads_data.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

from benchmarks import ACCOUNTS

OUT_DIR = Path(__file__).resolve().parent.parent / "ads-data"
rng = np.random.default_rng(20261126)

# ---------------------------------------------------------------------------
# Per-account keyword stories. Each tuple: (campaign_name, ad_group_name,
# keyword_text, match_type, quality_score, impression_share_pct, note).
# Two deliberate patterns per account, mirroring the real pattern this is
# based on: (1) high-quality-score / low-impression-share keywords -- the
# "quality is fine, bid/rank is the constraint" evidence; (2) low-quality-
# score keywords burning real spend on broad, loosely-relevant queries.
# ---------------------------------------------------------------------------

KEYWORDS = {
    "DE-INS-001": [
        ("Non-Brand Search - Auto Insurance", "Generic - Auto Insurance", "auto insurance germany", "Broad", 9.0, 5.0),
        ("Non-Brand Search - Auto Insurance", "Generic - Auto Insurance", "car insurance quote", "Phrase", 8.0, 6.0),
        ("Non-Brand Search - Home Insurance", "Generic - Home Insurance", "home insurance cost", "Phrase", 8.5, 5.5),
        ("Non-Brand Search - Life Insurance", "Generic - Life Insurance", "life insurance comparison", "Broad", 7.5, 7.0),
        ("Non-Brand Search - Auto Insurance", "Generic - Auto Insurance", "insurance company phone number", "Broad", 3.0, 24.0),
        ("Non-Brand Search - Home Insurance", "Generic - Home Insurance", "home insurance claims process", "Broad", 4.0, 19.0),
        ("Dynamic Search Ads - Long Tail", "Auto-Target - Long Tail", "insurance quote calculator free", "Broad", 3.5, 21.0),
        ("Non-Brand Search - Life Insurance", "Generic - Life Insurance", "what is life insurance", "Broad", 4.5, 17.0),
    ],
    "US-RET-001": [
        ("Brand Search - US", "Brand Terms", "pilot account promo code", "Exact", 9.5, 58.0),
        ("Non-Brand Search - Seasonal Promo", "Seasonal - Apparel", "winter jacket sale", "Phrase", 8.0, 21.0),
        ("Non-Brand Search - Seasonal Promo", "Seasonal - Electronics", "holiday electronics deals", "Broad", 7.5, 19.0),
        ("Non-Brand Search - Seasonal Promo", "Seasonal - Home", "kitchen appliances clearance", "Broad", 3.0, 26.0),
        ("Non-Brand Search - Seasonal Promo", "Seasonal - General", "deals near me today", "Broad", 2.5, 29.0),
        ("Non-Brand Search - Seasonal Promo", "Seasonal - General", "free shipping promo code", "Broad", 3.5, 22.0),
    ],
    "UK-TRV-001": [
        ("Non-Brand Search - Flights", "Generic - Flights", "flights to spain", "Phrase", 8.5, 34.0),
        ("Non-Brand Search - Flights", "Generic - Flights", "cheap flights europe", "Broad", 7.5, 30.0),
        ("Non-Brand Search - Hotels & Packages", "Generic - Hotels", "all inclusive holidays", "Phrase", 8.0, 36.0),
        ("Non-Brand Search - Hotels & Packages", "Generic - Packages", "weekend city breaks", "Broad", 7.0, 32.0),
        ("Non-Brand Search - Flights", "Generic - Flights", "flight booking customer service", "Broad", 4.0, 21.0),
        ("Non-Brand Search - Hotels & Packages", "Generic - Hotels", "hotel cancellation policy", "Broad", 4.5, 24.0),
    ],
}

# Search terms: the literal query that matched one of the account's broad/
# phrase keywords. Mostly plain category queries, plus a handful of
# zero-click competitor-brand leakage rows (reusing the fictitious
# competitor names already defined per account in benchmarks.py) and one
# competitor term that DOES convert, so the negative-keyword recommendation
# reads as "block the dead ones, keep the ones that convert" rather than a
# blanket rule.
NON_BRAND_QUERIES = {
    "DE-INS-001": [("car insurance quote", 14.0, 0.045), ("home insurance cost", 9.5, 0.038), ("life insurance comparison", 7.0, 0.031), ("cheap auto insurance", 11.0, 0.041)],
    "US-RET-001": [("mens running shoes", 12.0, 0.052), ("wireless headphones", 9.0, 0.047), ("winter jacket sale", 8.5, 0.055), ("kitchen appliances deals", 7.5, 0.033)],
    "UK-TRV-001": [("flights to spain", 13.0, 0.061), ("all inclusive holidays", 10.0, 0.058), ("cheap hotel deals", 9.0, 0.049), ("weekend city breaks", 7.0, 0.044)],
}

# ---------------------------------------------------------------------------
# Negative-keyword conflicts: a generic single-word negative, added at some
# point to block irrelevant traffic, that is also silently blocking one of
# the account's own live keywords (match-type too broad). Real-world cause
# of this exact pattern: a negative meant to exclude "free"/"jobs"/"DIY"
# style searches catches a legitimate long-tail keyword that happens to
# share the word.
# ---------------------------------------------------------------------------

NEGATIVE_CONFLICTS = {
    "DE-INS-001": [
        ("free", "Broad", "insurance quote calculator free", "Dynamic Search Ads - Long Tail", 3400),
        ("jobs", "Broad", "insurance agent jobs near me insurance quote", "Non-Brand Search - Auto Insurance", 410),
    ],
    "US-RET-001": [
        ("free", "Broad", "free shipping promo code", "Non-Brand Search - Seasonal Promo", 5200),
        ("DIY", "Broad", "kitchen appliances clearance DIY install", "Non-Brand Search - Seasonal Promo", 980),
        ("returns", "Broad", "winter jacket sale returns policy", "Non-Brand Search - Seasonal Promo", 760),
    ],
    "UK-TRV-001": [
        ("jobs", "Broad", "flight attendant jobs cheap flights europe", "Non-Brand Search - Flights", 640),
        ("visa", "Broad", "weekend city breaks visa requirements", "Non-Brand Search - Hotels & Packages", 1150),
    ],
}

# Ad groups to spread ad-strength ratings across (kept generic -- same
# ad-group names already used in KEYWORDS plus the account's Brand group).
AD_GROUP_POOL = {
    "DE-INS-001": ["Generic - Auto Insurance", "Generic - Home Insurance", "Generic - Life Insurance", "Brand Terms"],
    "US-RET-001": ["Brand Terms", "Seasonal - Apparel", "Seasonal - Electronics", "Seasonal - Home", "Seasonal - General"],
    "UK-TRV-001": ["Generic - Flights", "Generic - Hotels", "Generic - Packages", "Brand Terms"],
}


def jitter(low, high):
    return rng.uniform(low, high)


def build_keywords_df(campaigns_df):
    rows = []
    for account_id, kw_list in KEYWORDS.items():
        for campaign_name, ad_group, kw_text, match_type, qs, is_pct in kw_list:
            camp_row = campaigns_df[(campaigns_df.account_id == account_id)
                                     & (campaigns_df.campaign_name == campaign_name)].iloc[0]
            # This keyword's slice of its campaign's eligible impressions --
            # a handful of keywords sampled out of keyword_count, not all of them.
            eligible = round(camp_row["eligible_impressions"] * jitter(0.015, 0.05))
            impressions = round(eligible * is_pct / 100)
            lost_rank_pct = round(100 - is_pct, 1)  # these accounts are not budget-capped on Search; rank is the residual
            ctr = np.clip(rng.normal(0.015 + qs * 0.006, 0.006), 0.003, 0.09)
            clicks = round(impressions * ctr)
            avg_cpc = round(camp_row["avg_cpc"] * jitter(0.85, 1.25) * (1.15 if qs < 5 else 0.95), 2)
            spend = round(clicks * avg_cpc, 2)
            cvr = np.clip(rng.normal(camp_row["conversion_rate_pct"] / 100 * (0.6 if qs < 5 else 1.1), 0.01), 0.002, 0.12)
            conversions = round(clicks * cvr, 1)
            cost_per_conversion = round(spend / conversions, 2) if conversions else None
            rows.append({
                "account_id": account_id,
                "campaign_id": camp_row["campaign_id"],
                "campaign_name": campaign_name,
                "ad_group_name": ad_group,
                "keyword_text": kw_text,
                "match_type": match_type,
                "keyword_status": "Active",
                "quality_score": qs,
                "eligible_impressions": eligible,
                "impressions": impressions,
                "impression_share_pct": is_pct,
                "impression_share_lost_rank_pct": lost_rank_pct,
                "clicks": clicks,
                "ctr_pct": round(ctr * 100, 2),
                "avg_cpc": avg_cpc,
                "spend": spend,
                "conversions": conversions,
                "cost_per_conversion": cost_per_conversion,
            })
    return pd.DataFrame(rows)


def build_search_terms_df(campaigns_df):
    rows = []
    for account_id, acct in ACCOUNTS.items():
        vertical = acct["vertical"]
        non_brand_campaigns = campaigns_df[(campaigns_df.account_id == account_id)
                                            & (campaigns_df.campaign_subtype.isin(["Non-Brand", "Seasonal"]))]
        primary_campaign = non_brand_campaigns.iloc[0]

        for term, base_impr_pct, ctr in NON_BRAND_QUERIES[account_id]:
            impressions = round(primary_campaign["eligible_impressions"] * base_impr_pct / 100 * jitter(0.03, 0.06))
            clicks = round(impressions * ctr)
            rows.append({
                "account_id": account_id, "campaign_id": primary_campaign["campaign_id"],
                "campaign_name": primary_campaign["campaign_name"], "search_term": term,
                "matched_keyword_text": term, "match_type": "Broad",
                "impressions": impressions, "clicks": clicks,
                "ctr_pct": round(100 * clicks / impressions, 2) if impressions else 0.0,
                "is_competitor_brand_term": False, "conversions": round(clicks * jitter(0.02, 0.05), 1),
            })

        # Zero-click competitor-brand leakage -- one row per fictitious
        # competitor, descending impressions. Last competitor's term DOES
        # convert, so the fix reads as "block the dead ones, keep what works."
        competitors = acct["competitors"]
        base_impr = [round(primary_campaign["eligible_impressions"] * p / 1000) for p in [9, 7, 4, 2]]
        for i, comp in enumerate(competitors):
            comp_first_word = comp["name"].split()[0].lower()
            converts = (i == len(competitors) - 1)
            impressions = base_impr[i]
            clicks = round(impressions * jitter(0.0005, 0.002)) if converts else 0
            rows.append({
                "account_id": account_id, "campaign_id": primary_campaign["campaign_id"],
                "campaign_name": primary_campaign["campaign_name"],
                "search_term": f"{comp_first_word} {vertical.lower()} quote" if converts else comp["name"].lower(),
                "matched_keyword_text": NON_BRAND_QUERIES[account_id][0][0], "match_type": "Broad",
                "impressions": impressions, "clicks": clicks,
                "ctr_pct": round(100 * clicks / impressions, 2) if impressions else 0.0,
                "is_competitor_brand_term": True,
                "conversions": round(clicks * 0.25, 1) if converts else 0.0,
            })
    return pd.DataFrame(rows)


def build_negative_conflicts_df():
    rows = []
    for account_id, conflicts in NEGATIVE_CONFLICTS.items():
        for neg, match_type, blocked_kw, blocked_campaign, blocked_impr in conflicts:
            rows.append({
                "account_id": account_id, "negative_keyword": neg, "negative_match_type": match_type,
                "blocked_keyword_text": blocked_kw, "blocked_campaign_name": blocked_campaign,
                "estimated_blocked_impressions": blocked_impr,
            })
    return pd.DataFrame(rows)


def build_ads_df(campaigns_df):
    rows = []
    ad_id_counter = 1
    for account_id, ad_groups in AD_GROUP_POOL.items():
        camp_rows = campaigns_df[campaigns_df.account_id == account_id]
        for ad_group in ad_groups:
            campaign_name = camp_rows.iloc[int(rng.integers(0, len(camp_rows)))]["campaign_name"]
            for _ in range(int(rng.integers(1, 3))):
                # Skewed toward Good/Excellent -- ad copy is deliberately NOT
                # the bottleneck in this synthetic story (same "three things
                # that need no work" pattern the real analyst reports show).
                rating = rng.choice(["Excellent", "Good", "Average"], p=[0.7, 0.22, 0.08])
                rows.append({
                    "account_id": account_id, "campaign_name": campaign_name, "ad_group_name": ad_group,
                    "ad_id": f"{account_id}-AD{ad_id_counter:03d}",
                    "ad_strength_rating": rating,
                    "headlines_count": int(rng.integers(8, 16)),
                    "descriptions_count": int(rng.integers(3, 5)),
                })
                ad_id_counter += 1
    return pd.DataFrame(rows)


def build_auction_insights_df():
    rows = []
    for account_id, acct in ACCOUNTS.items():
        narrative = acct["narrative"]
        own_is = acct["target_account_impression_share_pct"]
        own_lost_rank = acct.get("target_account_lost_rank_pct", 0.0)
        for comp in acct["competitors"]:
            overlap = round(jitter(55, 80), 1)
            if narrative == "rank-constrained":
                # Competitors consistently out-rank this account.
                position_above = round(jitter(75, 97), 1)
                top_of_page_self = round(jitter(8, 20), 1)
                top_of_page_comp = round(jitter(65, 95), 1)
                outranking_self = round(jitter(5, 15), 1)
            elif narrative == "budget-constrained":
                # Competes fine on rank when it shows; just shows less often.
                position_above = round(jitter(35, 55), 1)
                top_of_page_self = round(jitter(45, 65), 1)
                top_of_page_comp = round(jitter(40, 60), 1)
                outranking_self = round(jitter(45, 60), 1)
            else:
                # Healthy / demand-surge: roughly even footing.
                position_above = round(jitter(30, 50), 1)
                top_of_page_self = round(jitter(55, 75), 1)
                top_of_page_comp = round(jitter(40, 60), 1)
                outranking_self = round(jitter(50, 65), 1)
            rows.append({
                "account_id": account_id, "competitor_name": comp["name"],
                "competitor_impression_share_pct": comp["spend_share_pct"] * jitter(0.9, 1.1),
                "overlap_rate_pct": overlap,
                "position_above_rate_pct": position_above,
                "top_of_page_rate_pct_self": top_of_page_self,
                "top_of_page_rate_pct_competitor": top_of_page_comp,
                "outranking_share_pct_self": outranking_self,
            })
    return pd.DataFrame(rows)


def main():
    campaigns_df = pd.read_csv(OUT_DIR / "campaigns.csv")

    keywords_df = build_keywords_df(campaigns_df)
    search_terms_df = build_search_terms_df(campaigns_df)
    negatives_df = build_negative_conflicts_df()
    ads_df = build_ads_df(campaigns_df)
    auction_df = build_auction_insights_df()

    keywords_df.to_csv(OUT_DIR / "keywords.csv", index=False)
    search_terms_df.to_csv(OUT_DIR / "search_terms.csv", index=False)
    negatives_df.to_csv(OUT_DIR / "negative_keyword_conflicts.csv", index=False)
    ads_df.to_csv(OUT_DIR / "ads.csv", index=False)
    auction_df.to_csv(OUT_DIR / "auction_insights.csv", index=False)

    print(f"keywords.csv: {len(keywords_df)} rows")
    print(f"search_terms.csv: {len(search_terms_df)} rows ({search_terms_df.is_competitor_brand_term.sum()} competitor-brand)")
    print(f"negative_keyword_conflicts.csv: {len(negatives_df)} rows")
    print(f"ads.csv: {len(ads_df)} rows "
          f"({(ads_df.ad_strength_rating == 'Excellent').sum()} Excellent)")
    print(f"auction_insights.csv: {len(auction_df)} rows")


if __name__ == "__main__":
    main()

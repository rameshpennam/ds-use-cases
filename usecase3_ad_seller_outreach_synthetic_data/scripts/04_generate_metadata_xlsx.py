"""
Builds misc/metadata.xlsx: one workbook describing every input dataset
(campaign-grain ads data, the keyword/search-term/negative-keyword/
ad-strength/auction-insight grain, and the 4 vendor research reports) so a
developer picking this package up has full context without reading every file.

Run after 01_generate_ads_data.py and 02_generate_granular_ads_data.py.
"""
from pathlib import Path
import pandas as pd

from benchmarks import VENDORS, ACCOUNTS, REPORT_PERIOD, WATERMARK

OUT_DIR = Path(__file__).resolve().parent.parent / "misc"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ADS_DICT = [
    # (column, category, type, description)
    ("account_id", "Identity", "string", "Unique pilot account identifier, e.g. DE-INS-001"),
    ("account_name", "Identity", "string", "Generic placeholder account label (no real company names)"),
    ("vertical", "Identity", "string", "Industry vertical: Insurance / Retail / Travel"),
    ("sub_vertical", "Identity", "string", "Product line within the vertical this campaign targets"),
    ("country", "Identity", "string", "Account's market country"),
    ("country_code", "Identity", "string", "ISO-3166 alpha-2 country code"),
    ("currency", "Identity", "string", "ISO currency code for spend/revenue fields"),
    ("account_status", "Identity", "string", "Active / Paused at account level"),
    ("pilot_flag", "Identity", "string", "Y/N -- whether this account is in the 3-account pilot"),
    ("campaign_id", "Identity", "string", "Unique campaign identifier within the account"),
    ("campaign_name", "Identity", "string", "Human-readable campaign name"),
    ("campaign_type", "Identity", "string", "Search / Shopping / Performance Max / Audience / Dynamic Search Ads"),
    ("campaign_subtype", "Identity", "string", "Brand / Non-Brand / Retargeting / Catalog / etc."),
    ("campaign_status", "Identity", "string", "Active / Paused at campaign level"),

    ("report_period", "Period", "string", "Reporting quarter this row describes"),
    ("period_start_date", "Period", "date", "First day of the reporting period"),
    ("period_end_date", "Period", "date", "Last day of the reporting period"),
    ("prior_period", "Period", "string", "The comparison quarter used for all *_prior_period / *_qoq columns"),
    ("data_as_of_date", "Period", "date", "Date the export was generated"),
    ("days_in_period", "Period", "integer", "Number of days in the reporting period"),

    ("bid_strategy", "Bid & Targeting", "string", "Manual CPC / Enhanced CPC / Target CPA / Target ROAS / Maximize Conversions"),
    ("target_cpa", "Bid & Targeting", "float", "Target cost-per-conversion, only set when bid_strategy = Target CPA"),
    ("target_roas", "Bid & Targeting", "float", "Target return-on-ad-spend ratio, only set when bid_strategy = Target ROAS"),
    ("network", "Bid & Targeting", "string", "Which inventory network the campaign is eligible to serve on"),
    ("device_targeting", "Bid & Targeting", "string", "All Devices / Mobile Preferred / Desktop Preferred"),
    ("language_targeting", "Bid & Targeting", "string", "Targeted ad language"),
    ("location_targeting", "Bid & Targeting", "string", "Geographic targeting scope"),
    ("ad_schedule", "Bid & Targeting", "string", "Dayparting configuration"),
    ("ad_rotation", "Bid & Targeting", "string", "How multiple ads in the same ad group are rotated"),
    ("delivery_method", "Bid & Targeting", "string", "Standard (pace evenly) vs Accelerated (spend ASAP)"),

    ("daily_budget", "Budget & Delivery", "float", "Daily budget allocated to this campaign, in account currency"),
    ("monthly_budget_cap", "Budget & Delivery", "float", "Approx. monthly spend cap implied by daily_budget"),
    ("budget_utilization_pct", "Budget & Delivery", "float", "Share of available budget actually spent in the period"),
    ("spend", "Budget & Delivery", "float", "Total spend in the reporting period"),
    ("spend_prior_period", "Budget & Delivery", "float", "Spend in the prior comparison period"),
    ("spend_qoq_change_pct", "Budget & Delivery", "float", "Quarter-over-quarter spend change"),
    ("spend_yoy_change_pct", "Budget & Delivery", "float", "Year-over-year spend change"),
    ("impressions", "Budget & Delivery", "integer", "Impressions served in the period"),
    ("impressions_prior_period", "Budget & Delivery", "integer", "Impressions served in the prior period"),
    ("eligible_impressions", "Budget & Delivery", "integer", "Total auctions this campaign was eligible to compete in"),
    ("search_impression_share_pct", "Budget & Delivery", "float", "impressions / eligible_impressions, as a %"),
    ("impression_share_lost_budget_pct", "Budget & Delivery", "float", "% of eligible impressions missed because budget ran out"),
    ("impression_share_lost_rank_pct", "Budget & Delivery", "float", "% of eligible impressions missed because of auction rank/quality"),
    ("absolute_top_impression_share_pct", "Budget & Delivery", "float", "% of impressions shown in the single top ad position"),
    ("top_impression_share_pct", "Budget & Delivery", "float", "% of impressions shown above organic results (any top position)"),

    ("clicks", "Clicks & Engagement", "integer", "Clicks in the period"),
    ("clicks_prior_period", "Clicks & Engagement", "integer", "Clicks in the prior period"),
    ("ctr_pct", "Clicks & Engagement", "float", "Click-through rate"),
    ("ctr_prior_period_pct", "Clicks & Engagement", "float", "Prior-period click-through rate"),
    ("avg_cpc", "Clicks & Engagement", "float", "Average cost per click"),
    ("avg_cpc_prior_period", "Clicks & Engagement", "float", "Prior-period average cost per click"),
    ("avg_cpc_qoq_change_pct", "Clicks & Engagement", "float", "Quarter-over-quarter CPC change, tied to market-wide CPC inflation"),
    ("avg_cpm", "Clicks & Engagement", "float", "Average cost per thousand impressions"),
    ("click_share_pct", "Clicks & Engagement", "float", "Share of all clickable auctions this campaign's ad was clicked in"),
    ("outranking_share_pct", "Clicks & Engagement", "float", "% of auctions where this campaign outranked a competitor's ad"),

    ("avg_quality_score", "Quality & Competitiveness", "float", "1-10 composite quality signal"),
    ("expected_ctr_rating", "Quality & Competitiveness", "string", "Below Average / Average / Above Average"),
    ("ad_relevance_rating", "Quality & Competitiveness", "string", "Below Average / Average / Above Average"),
    ("landing_page_experience_rating", "Quality & Competitiveness", "string", "Below Average / Average / Above Average"),
    ("vertical_benchmark_impression_share_pct", "Quality & Competitiveness", "float",
     "Vertical peer-average impression share -- SNAPSHOT of the matching field in the Ashcroft research report, joined by vertical+country+period"),
    ("vertical_benchmark_avg_cpc", "Quality & Competitiveness", "float",
     "Vertical peer-average CPC -- snapshot of QueryScope's keyword_cpc_benchmark field"),
    ("vertical_benchmark_ctr_pct", "Quality & Competitiveness", "float", "Vertical peer-average CTR"),
    ("competitive_density_index", "Quality & Competitiveness", "integer",
     "Our own measure of how crowded the auction is -- directionally comparable to QueryScope's serp_competitive_density_index, not identical methodology"),

    ("conversions", "Conversions & Revenue", "float", "Conversions in the period"),
    ("conversions_prior_period", "Conversions & Revenue", "float", "Conversions in the prior period"),
    ("conversion_rate_pct", "Conversions & Revenue", "float", "conversions / clicks, as a %"),
    ("conversion_rate_prior_period_pct", "Conversions & Revenue", "float", "Prior-period conversion rate"),
    ("cost_per_conversion", "Conversions & Revenue", "float", "spend / conversions"),
    ("conversion_value", "Conversions & Revenue", "float", "Total value attributed to conversions"),
    ("revenue", "Conversions & Revenue", "float", "Same as conversion_value, kept as a separate column to match common reporting exports"),
    ("roas", "Conversions & Revenue", "float", "revenue / spend"),
    ("roas_prior_period", "Conversions & Revenue", "float", "Prior-period ROAS"),
    ("assisted_conversions", "Conversions & Revenue", "float", "Conversions where this campaign was an assisting touchpoint, not the last click"),
    ("view_through_conversions", "Conversions & Revenue", "float", "Conversions after an impression with no click"),
    ("cross_device_conversions", "Conversions & Revenue", "float", "Conversions that started on one device and completed on another"),
    ("new_customer_conversion_pct", "Conversions & Revenue", "float", "% of conversions from new (not repeat) customers"),
    ("repeat_customer_conversion_pct", "Conversions & Revenue", "float", "Reserved for future use -- not populated in this synthetic set"),
    ("avg_order_value", "Conversions & Revenue", "float", "revenue / conversions"),
    ("cpa_vs_target_pct", "Conversions & Revenue", "float", "Reserved for future use -- not populated in this synthetic set"),

    ("spend_m1", "Monthly Trend (stage-1 signal)", "float", "Spend in month 1 of the quarter (July 2026) -- sums exactly to `spend`"),
    ("spend_m2", "Monthly Trend (stage-1 signal)", "float", "Spend in month 2 of the quarter (August 2026)"),
    ("spend_m3", "Monthly Trend (stage-1 signal)", "float", "Spend in month 3 of the quarter (September 2026)"),
    ("impressions_m1", "Monthly Trend (stage-1 signal)", "integer", "Impressions in month 1 -- sums exactly to `impressions`"),
    ("impressions_m2", "Monthly Trend (stage-1 signal)", "integer", "Impressions in month 2"),
    ("impressions_m3", "Monthly Trend (stage-1 signal)", "integer", "Impressions in month 3"),
    ("conversions_m1", "Monthly Trend (stage-1 signal)", "float", "Conversions in month 1 -- sums exactly to `conversions`"),
    ("conversions_m2", "Monthly Trend (stage-1 signal)", "float", "Conversions in month 2"),
    ("conversions_m3", "Monthly Trend (stage-1 signal)", "float", "Conversions in month 3"),
    ("spend_prior_year", "Monthly Trend (stage-1 signal)", "float", "Same-quarter spend one year earlier -- lets a model compare the account's own YoY trend to the market's (demand_index_*_prior_year)"),
    ("impressions_prior_year", "Monthly Trend (stage-1 signal)", "integer", "Same-quarter impressions one year earlier"),
    ("conversions_prior_year", "Monthly Trend (stage-1 signal)", "float", "Same-quarter conversions one year earlier"),

    ("primary_constraint_hint", "Validation Label", "string",
     "Ground-truth diagnosis this synthetic account was built to represent (rank-constrained / "
     "budget-constrained / healthy-demand-surge). Use to VALIDATE a stage-1 issue-detection "
     "model's output against a known answer -- do not feed it in as a model input, that would "
     "be label leakage."),
    ("seller_note_text", "Qualitative / GenAI Grounding", "string",
     "Free-text note from the account seller, populated only on the 2 campaigns per account "
     "most worth acting on (seller_notes_flag = Y). This is the kind of qualitative detail a "
     "GenAI drafting step should quote or paraphrase directly -- it is NOT derivable from the "
     "numeric columns."),

    ("demand_index_q4_2025_current", "Demand Trend", "integer", "Indexed search demand, Q4 2025, this year (base 100)"),
    ("demand_index_q4_2025_prior_year", "Demand Trend", "integer", "Indexed search demand, Q4 2024 (same quarter, prior year)"),
    ("demand_index_q1_2026_current", "Demand Trend", "integer", "Indexed search demand, Q1 2026"),
    ("demand_index_q1_2026_prior_year", "Demand Trend", "integer", "Indexed search demand, Q1 2025"),
    ("demand_index_q2_2026_current", "Demand Trend", "integer", "Indexed search demand, Q2 2026"),
    ("demand_index_q2_2026_prior_year", "Demand Trend", "integer", "Indexed search demand, Q2 2025"),
    ("demand_index_q3_2026_current", "Demand Trend", "integer", "Indexed search demand, Q3 2026 (current reporting quarter)"),
    ("demand_index_q3_2026_prior_year", "Demand Trend", "integer", "Indexed search demand, Q3 2025"),

    ("impressions_mobile_pct", "Device Split", "float", "% of impressions on mobile"),
    ("impressions_desktop_pct", "Device Split", "float", "% of impressions on desktop"),
    ("impressions_tablet_pct", "Device Split", "float", "% of impressions on tablet"),
    ("clicks_mobile_pct", "Device Split", "float", "% of clicks on mobile"),
    ("clicks_desktop_pct", "Device Split", "float", "% of clicks on desktop"),
    ("clicks_tablet_pct", "Device Split", "float", "% of clicks on tablet"),
    ("spend_mobile_pct", "Device Split", "float", "% of spend on mobile"),
    ("spend_desktop_pct", "Device Split", "float", "% of spend on desktop"),
    ("spend_tablet_pct", "Device Split", "float", "% of spend on tablet"),

    ("audience_top_segment_1_name", "Audience", "string", "Largest audience segment reached by this campaign"),
    ("audience_top_segment_1_share_pct", "Audience", "float", "Share of conversions/engagement from that segment"),
    ("audience_top_segment_2_name", "Audience", "string", "Second-largest audience segment reached"),
    ("audience_top_segment_2_share_pct", "Audience", "float", "Share of conversions/engagement from that segment"),
    ("age_group_top_name", "Audience", "string", "Best-performing age bracket"),
    ("age_group_top_share_pct", "Audience", "float", "Share attributable to that age bracket"),
    ("gender_male_share_pct", "Audience", "float", "% share attributable to male audience"),
    ("gender_female_share_pct", "Audience", "float", "% share attributable to female audience"),

    ("top_region_1_name", "Geo", "string", "Highest-spend sub-national region"),
    ("top_region_1_spend_share_pct", "Geo", "float", "Spend share of that region"),
    ("top_region_2_name", "Geo", "string", "Second highest-spend region"),
    ("top_region_2_spend_share_pct", "Geo", "float", "Spend share of that region"),
    ("top_region_3_name", "Geo", "string", "Third highest-spend region"),
    ("top_region_3_spend_share_pct", "Geo", "float", "Spend share of that region"),
    ("top_city_name", "Geo", "string", "Highest-spend metro area"),
    ("top_city_spend_share_pct", "Geo", "float", "Spend share of that metro area"),
    ("rest_of_geo_spend_share_pct", "Geo", "float", "Combined spend share of everywhere outside the top 3 regions"),

    ("keyword_count", "Keywords & Creative Ops", "integer", "Active keyword count (0 for feed/audience-driven campaign types)"),
    ("negative_keyword_count", "Keywords & Creative Ops", "integer", "Active negative keyword count"),
    ("active_ad_count", "Keywords & Creative Ops", "integer", "Currently serving ad count"),
    ("disapproved_ad_count", "Keywords & Creative Ops", "integer", "Ads currently disapproved by policy review"),
    ("ad_group_count", "Keywords & Creative Ops", "integer", "Number of ad groups in the campaign"),
    ("top_search_term_1", "Keywords & Creative Ops", "string", "Highest-volume search term triggering this campaign"),
    ("top_search_term_1_share_pct", "Keywords & Creative Ops", "float", "Share of clicks/impressions from that term"),
    ("top_search_term_2", "Keywords & Creative Ops", "string", "Second highest-volume search term"),
    ("top_search_term_2_share_pct", "Keywords & Creative Ops", "float", "Share of clicks/impressions from that term"),
    ("policy_issues_count", "Keywords & Creative Ops", "integer", "Open policy/compliance issues on this campaign"),

    ("last_optimization_date", "Account Health & Ops", "date", "Date a seller/optimizer last changed this campaign's settings"),
    ("days_since_last_optimization", "Account Health & Ops", "integer", "Days since last_optimization_date"),
    ("active_campaign_count_account", "Account Health & Ops", "integer", "Active campaign count for the whole account (repeated per row)"),
    ("paused_campaign_count_account", "Account Health & Ops", "integer", "Paused campaign count for the whole account (repeated per row)"),
    ("account_tenure_months", "Account Health & Ops", "integer", "How long this account has been advertising on the platform"),
    ("seller_notes_flag", "Account Health & Ops", "string", "Y/N -- whether the account seller has manually flagged this campaign for review"),
]

MARKET_DICT = [
    # (vendor_short, field, type, description, maps_to_ads_column)
    ("Ashcroft", "vertical", "string", "Vertical this report section covers", "vertical"),
    ("Ashcroft", "country", "string", "Country this report section covers", "country"),
    ("Ashcroft", "report_period", "string", "Quarter the figures describe", "report_period"),
    ("Ashcroft", "search_spend_growth_qoq_pct", "float", "Category-wide paid search spend growth, QoQ", "spend_qoq_change_pct (account rollup)"),
    ("Ashcroft", "query_demand_growth_qoq_pct", "float", "Category-wide query volume growth, QoQ", "impressions growth / demand_index_* series"),
    ("Ashcroft", "cpc_growth_qoq_pct", "float", "Category-wide average CPC growth, QoQ", "avg_cpc_qoq_change_pct"),
    ("Ashcroft", "demand_index (4 quarters, current + prior-year)", "integer series", "Indexed demand trend, base 100", "demand_index_q*_current / demand_index_q*_prior_year"),
    ("Ashcroft", "vertical_benchmark_impression_share_pct", "float", "Peer-average impression share for the vertical", "vertical_benchmark_impression_share_pct"),
    ("Ashcroft", "vertical_benchmark_lost_rank_pct", "float", "Peer-average share of auctions lost to rank", "impression_share_lost_rank_pct (compare against)"),
    ("Ashcroft", "maturity_stage_rating", "string (qualitative)", "Analyst's view of category maturity: Emerging/Growth/Mature", "no direct ads-data mapping -- qualitative context only"),
    ("Ashcroft", "forecast_next_quarter_spend_growth_pct", "float", "Forward-looking spend growth forecast", "no direct ads-data mapping -- forward-looking only"),

    ("Vantage", "vertical", "string", "Vertical this measurement covers", "vertical"),
    ("Vantage", "country", "string", "Country this measurement covers", "country"),
    ("Vantage", "channel_mix_pct (Search/Social/Display/Video/Other)", "float x5", "Category spend share by channel", "no ads-data equivalent -- ads data is search-platform-only, this is the cross-channel context"),
    ("Vantage", "reach_pct", "float", "% of the addressable audience reached in-period", "no direct ads-data mapping"),
    ("Vantage", "frequency", "float", "Average exposures per reached person", "no direct ads-data mapping"),
    ("Vantage", "ad_intensity_index", "integer", "Composite category ad-pressure index, base 100", "directionally comparable to competitive_density_index, not the same methodology"),

    ("SignalWatch", "vertical", "string", "Vertical this tracking covers", "vertical"),
    ("SignalWatch", "country", "string", "Country this tracking covers", "country"),
    ("SignalWatch", "competitor_name", "string", "Named competitor (fictitious)", "compare against account_spend_share_pct for relative position"),
    ("SignalWatch", "competitor_spend_share_pct", "float", "That competitor's estimated share of category spend", "compare against account_spend_share_pct"),
    ("SignalWatch", "competitor_creative_count", "integer", "Distinct ad creatives that competitor is running", "no ads-data equivalent"),
    ("SignalWatch", "competitor_channels", "string", "Which channels that competitor is active on", "no ads-data equivalent"),
    ("SignalWatch", "account_spend_share_pct", "float", "Our pilot account's estimated share of category spend", "no direct column -- new context metric; roughly implied by revenue/spend scale vs competitor set"),

    ("QueryScope", "vertical", "string", "Vertical this keyword data covers", "vertical"),
    ("QueryScope", "country", "string", "Country this keyword data covers", "country"),
    ("QueryScope", "keyword", "string", "Specific keyword/query being benchmarked", "compare against top_search_term_1 / top_search_term_2"),
    ("QueryScope", "query_volume_index", "integer", "Indexed query volume for that keyword, base 100", "finer-grain version of demand_index_* (keyword vs. account level)"),
    ("QueryScope", "keyword_cpc_benchmark", "float", "Peer-average CPC for that keyword", "vertical_benchmark_avg_cpc"),
    ("QueryScope", "keyword_cpc_growth_qoq_pct", "float", "QoQ CPC growth for that keyword", "avg_cpc_qoq_change_pct"),
    ("QueryScope", "serp_competitive_density_index", "integer", "How crowded the results page is for that keyword, base 100", "competitive_density_index"),
]

GRANULAR_DICT = [
    # (file, column, type, description)
    ("keywords.csv", "account_id / campaign_id / campaign_name", "string", "Links back to campaigns.csv -- only populated for Search / Dynamic Search Ads campaigns (keyword_count > 0 there), same as the real platforms this mirrors"),
    ("keywords.csv", "ad_group_name", "string", "Ad group the keyword lives in"),
    ("keywords.csv", "keyword_text", "string", "The advertiser's own bid keyword (not the literal search query -- see search_terms.csv for that)"),
    ("keywords.csv", "match_type", "string", "Exact / Phrase / Broad"),
    ("keywords.csv", "quality_score", "float", "1-10 keyword-level quality signal. NOT an average -- individual keywords, so a 9.0 next to a 3.0 in the same campaign is visible, which the campaign-level avg_quality_score in campaigns.csv cannot show"),
    ("keywords.csv", "impression_share_pct / impression_share_lost_rank_pct", "float", "This keyword's own auction performance -- a high-quality-score keyword can still sit at single-digit impression share if the bid can't clear the auction"),
    ("keywords.csv", "impressions / clicks / ctr_pct / avg_cpc / spend / conversions / cost_per_conversion", "numeric", "Standard performance fields at keyword grain"),
    ("keywords.csv", "(file scope)", "note", "Top keywords by story relevance, NOT an exhaustive export of every live keyword -- same as a real analyst report only lists the keywords worth acting on"),

    ("search_terms.csv", "search_term", "string", "The literal query a user typed -- can differ from any keyword_text when match type is Broad/Phrase"),
    ("search_terms.csv", "matched_keyword_text", "string", "Which of the account's own keywords this query matched under"),
    ("search_terms.csv", "is_competitor_brand_term", "boolean", "True when the query contains a competitor's name (fictitious competitor list, same ones in SignalWatch's market-report data) rather than a category term"),
    ("search_terms.csv", "impressions / clicks / ctr_pct / conversions", "numeric", "Zero-click, high-impression competitor-brand rows are the evidence behind a negative-keyword recommendation; a competitor term that DOES convert is deliberately left out of that pattern, matching the real rule of 'block the dead ones, keep what works'"),

    ("negative_keyword_conflicts.csv", "negative_keyword / negative_match_type", "string", "A generic negative (e.g. a word meant to exclude unrelated searches) that is too broad"),
    ("negative_keyword_conflicts.csv", "blocked_keyword_text / blocked_campaign_name", "string", "The advertiser's own live keyword that negative is accidentally blocking from ever reaching an auction"),
    ("negative_keyword_conflicts.csv", "estimated_blocked_impressions", "integer", "Impressions that keyword would have been eligible for had the negative not blocked it -- a blocked keyword shows 100% lost-to-rank by definition, since it never enters the auction"),

    ("ads.csv", "ad_group_name / ad_id", "string", "One row per live ad"),
    ("ads.csv", "ad_strength_rating", "string", "Poor / Average / Good / Excellent -- the platform's own creative-quality rating. Skewed toward Good/Excellent across all 3 accounts on purpose: ad copy is deliberately NOT the bottleneck in this synthetic story, same as the 'three things that need no work' pattern real analyst reviews surface before the fix list"),
    ("ads.csv", "headlines_count / descriptions_count", "integer", "Asset counts feeding the strength rating"),

    ("auction_insights.csv", "competitor_name", "string", "Fictitious named competitor -- same identity used in SignalWatch's market-report data, so the two can be cross-referenced"),
    ("auction_insights.csv", "overlap_rate_pct", "float", "% of this account's auctions where that competitor also showed"),
    ("auction_insights.csv", "position_above_rate_pct", "float", "Of the auctions where both showed, % of the time the competitor's ad ranked above this account's"),
    ("auction_insights.csv", "top_of_page_rate_pct_self / top_of_page_rate_pct_competitor", "float", "% of impressions reaching the very top of the page, for this account vs. that competitor -- the gap between these two numbers is the real story, not either one alone"),
    ("auction_insights.csv", "outranking_share_pct_self", "float", "% of shared auctions this account's ad ranked above that competitor's -- the account's own side of position_above_rate_pct"),
    ("auction_insights.csv", "(file scope)", "note", "Rows are account-level, blended across in-scope Search campaigns -- not broken out per-campaign, since that is how a seller would actually look at it first"),
]


def main():
    overview_rows = [
        ("Package", "Synthetic data package for the market-context-enriched seller outreach pilot."),
        ("Scope", "3 pilot accounts (Insurance/Germany, Retail/United States, Travel/United Kingdom), campaign-level ads data, "
                  "and 4 fictitious vendor-style market research reports."),
        ("Ads data file", "input/campaigndata-campaigns.csv -- one row per campaign, 143 columns, 22 rows "
                          "(5/7/10 campaigns across the 3 accounts -- deliberately uneven, matching how a "
                          "single-product-line vertical vs. a multi-category catalog actually differ in campaign count)."),
        ("Granular ads data files", "input/campaigndata-keywords.csv, campaigndata-search_terms.csv, "
                                    "campaigndata-negative_keyword_conflicts.csv, campaigndata-ads.csv, "
                                    "campaigndata-auction_insights.csv -- the keyword/query/negative-keyword/ad-copy/"
                                    "competitive-position grain a real analyst actually digs through, which "
                                    "campaign-level aggregates alone cannot show (see Granular Ads Data Dictionary tab)."),
        ("Market data files", "input/marketdata-*.pdf -- one PDF per fictitious vendor, each covering all 3 verticals/accounts."),
        ("Recommendation emails", "output/recommendation_email_llm_*.pdf -- one AI-drafted output per account, produced "
                                  "live by scripts/05_analyze_and_generate_emails.py from everything in input/."),
        ("Pipeline (why the data is shaped this way)",
         "Stage 1 -- analyze the ads data ALONE to detect the issue (rank-constrained vs. "
         "budget-constrained vs. healthy/demand-surge -- see impression_share_lost_budget_pct vs. "
         "impression_share_lost_rank_pct, the spend_m1/m2/m3 trend columns, and the keyword/search-term/"
         "negative-keyword/ad-strength/auction-insight grain). "
         "Stage 2 -- join in the matching vertical/country/period section of the 4 market reports for "
         "external evidence and timing ('why now'). "
         "Stage 3 -- GenAI drafts the seller email from stage-1's diagnosis + stage-2's evidence. "
         "The ads data must be sufficient for stage 1 on its own, without the market data. "
         "See misc/approach.html for the full step-by-step flow."),
        ("Status", "100% synthetic / illustrative. No real company, account, or vendor data anywhere in this package."),
        ("Reporting period", REPORT_PERIOD),
        ("How to regenerate", "scripts/benchmarks.py holds every number every output must agree on; run in order: "
                               "01_generate_ads_data.py, 02_generate_granular_ads_data.py (reads "
                               "campaigndata-campaigns.csv back in, must run after 01), 03_generate_market_pdfs.py, "
                               "04_generate_metadata_xlsx.py (this script), then 05_analyze_and_generate_emails.py "
                               "to produce the recommendation emails in output/."),
        ("Watermark", WATERMARK),
    ]
    overview_df = pd.DataFrame(overview_rows, columns=["Field", "Value"])

    ads_df = pd.DataFrame(ADS_DICT, columns=["Column", "Category", "Type", "Description"])

    vendor_rows = []
    for key, v in VENDORS.items():
        vendor_rows.append({
            "Vendor (fictitious)": v["name"],
            "Report Title": v["report_title"],
            "Data Type": v["data_type"],
            "Format": v["format"],
            "Added beyond original 3-vendor list?": "Yes -- " + v["note"] if "note" in v else "No",
        })
    vendors_df = pd.DataFrame(vendor_rows)

    market_df = pd.DataFrame(MARKET_DICT, columns=["Vendor", "Field", "Type", "Description", "Maps to ads-data column"])

    granular_df = pd.DataFrame(GRANULAR_DICT, columns=["File", "Column", "Type", "Description"])

    accounts_rows = []
    for acct_id, a in ACCOUNTS.items():
        accounts_rows.append({
            "account_id": acct_id,
            "account_name": a["account_name"],
            "vertical": a["vertical"],
            "country": a["country"],
            "diagnosis": a["narrative"],
            "story": a["story"],
        })
    accounts_df = pd.DataFrame(accounts_rows)

    out_path = OUT_DIR / "metadata.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        overview_df.to_excel(writer, sheet_name="Overview", index=False)
        accounts_df.to_excel(writer, sheet_name="Pilot Accounts", index=False)
        ads_df.to_excel(writer, sheet_name="Ads Data Dictionary", index=False)
        granular_df.to_excel(writer, sheet_name="Granular Ads Data Dictionary", index=False)
        vendors_df.to_excel(writer, sheet_name="Market Vendors Overview", index=False)
        market_df.to_excel(writer, sheet_name="Market Data Dictionary", index=False)

        for sheet_name, df in [("Overview", overview_df), ("Pilot Accounts", accounts_df),
                                ("Ads Data Dictionary", ads_df), ("Granular Ads Data Dictionary", granular_df),
                                ("Market Vendors Overview", vendors_df),
                                ("Market Data Dictionary", market_df)]:
            ws = writer.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max() if len(df) else 0, len(col))
                ws.column_dimensions[chr(65 + i) if i < 26 else "A"].width = min(max_len + 3, 70)
            ws.freeze_panes = "A2"

    print(f"wrote {out_path} -- ads dict rows: {len(ads_df)}, market dict rows: {len(market_df)}")


if __name__ == "__main__":
    main()

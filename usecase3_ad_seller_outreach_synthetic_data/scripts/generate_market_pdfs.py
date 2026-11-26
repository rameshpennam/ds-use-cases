"""
Builds the 4 fictitious vendor-style market research PDFs in market-reports/.
Every figure for the pilot's 3 verticals comes from benchmarks.py, so these
numbers can never drift from ads-data/campaigns.csv or the recommendation
emails. Everything outside those 3 verticals (extra comparison markets,
competitor names, keyword lists) is invented purely to give each report the
breadth a real quarterly vendor report has -- clearly labeled illustrative.

Run after generate_ads_data.py.
"""
from pathlib import Path
import numpy as np
from reportlab.platypus import Paragraph, Spacer, PageBreak, Table, TableStyle, HRFlowable, NextPageTemplate
from reportlab.lib.units import inch
from reportlab.lib import colors

import pdf_common as pc
from benchmarks import ACCOUNTS, VENDORS, REPORT_PERIOD, PRIOR_PERIOD

_hist_rng = np.random.default_rng(730104)
HIST_QUARTERS = ["Q4 2024", "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"]

OUT_DIR = Path(__file__).resolve().parent.parent / "market-reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUARTERS = ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"]

# Extra comparison markets per vertical -- invented purely for report breadth,
# clearly separate from the 3 pilot accounts' real (synthetic) figures.
EXTRA_MARKETS = {
    "Insurance": [
        ("France", 14.5, 24.0), ("United Kingdom", 11.0, 27.5),
        ("United States", 9.5, 19.0), ("Japan", 6.0, 31.0),
        ("Canada", 10.0, 26.0), ("Netherlands", 8.5, 29.5),
        ("Italy", 12.5, 22.5), ("South Korea", 7.0, 33.5),
    ],
    "Retail": [
        ("United Kingdom", 7.5, 33.0), ("Germany", 6.0, 30.5),
        ("Australia", 10.5, 29.0), ("Japan", 5.0, 36.0),
        ("France", 8.0, 31.5), ("Canada", 9.0, 28.0),
        ("Netherlands", 6.5, 34.0), ("Brazil", 13.5, 24.5),
    ],
    "Travel": [
        ("United States", 17.0, 36.5), ("Spain", 25.0, 33.0),
        ("Australia", 14.0, 38.0), ("Germany", 12.5, 34.0),
        ("France", 19.5, 35.5), ("Italy", 21.0, 32.0),
        ("Canada", 15.5, 37.0), ("United Arab Emirates", 23.5, 30.0),
    ],
}

# Extra fictitious long-tail competitors, appended to the 4 canonical ones in
# benchmarks.py so the competitive-intelligence report has a realistic
# tracked-set size (real competitive trackers follow 8-12+ advertisers per
# category, not just the top 4).
EXTRA_COMPETITORS = {
    "Insurance": [
        {"name": "Stonegate Assurance", "spend_share_pct": 8, "creative_count": 17, "channels": "Search"},
        {"name": "Fieldstone Insurance Group", "spend_share_pct": 6, "creative_count": 13, "channels": "Search, Display"},
        {"name": "Ambervale Mutual", "spend_share_pct": 5, "creative_count": 11, "channels": "Social"},
        {"name": "Redline Direct Cover", "spend_share_pct": 4, "creative_count": 9, "channels": "Search"},
        {"name": "Thornbury Protection Co", "spend_share_pct": 3, "creative_count": 7, "channels": "Display"},
    ],
    "Retail": [
        {"name": "Caldwell & Finch", "spend_share_pct": 6, "creative_count": 29, "channels": "Social, Video"},
        {"name": "Briarwood Supply Co", "spend_share_pct": 5, "creative_count": 24, "channels": "Shopping, Search"},
        {"name": "Ledger Street Goods", "spend_share_pct": 4, "creative_count": 19, "channels": "Social"},
        {"name": "Hartline Mercantile", "spend_share_pct": 3, "creative_count": 15, "channels": "Search, Display"},
        {"name": "Oakmoor Retail Co", "spend_share_pct": 3, "creative_count": 12, "channels": "Video"},
    ],
    "Travel": [
        {"name": "Meridian Escapes", "spend_share_pct": 9, "creative_count": 21, "channels": "Search, Video"},
        {"name": "Farview Travel Co", "spend_share_pct": 7, "creative_count": 18, "channels": "Social, Search"},
        {"name": "Wanderline Holidays", "spend_share_pct": 5, "creative_count": 15, "channels": "Video"},
        {"name": "Northbridge Tours", "spend_share_pct": 4, "creative_count": 12, "channels": "Search"},
        {"name": "Vellamar Journeys", "spend_share_pct": 3, "creative_count": 9, "channels": "Display, Social"},
    ],
}

# Extra fictitious long-tail keywords per vertical, appended to the 4
# canonical ones in generate_market_pdfs.py's KEYWORD_SETS, giving the
# keyword-intelligence report the kind of long-tail breadth a real one has.
EXTRA_KEYWORDS = {
    "Insurance": [
        ("multi car insurance discount", 100, 107, 121), ("insurance for first time drivers", 100, 118, 136),
        ("home and contents insurance", 100, 103, 112), ("critical illness cover cost", 100, 99, 108),
        ("insurance for high risk drivers", 100, 121, 142), ("pet insurance comparison", 100, 109, 117),
        ("landlord insurance quote", 100, 105, 114), ("over 50s life insurance", 100, 101, 110),
        ("insurance renewal price rise", 100, 124, 149), ("best insurance for new drivers", 100, 116, 131),
    ],
    "Retail": [
        ("running shoes for flat feet", 100, 101, 107), ("noise cancelling headphones deals", 100, 108, 119),
        ("waterproof winter boots", 100, 96, 115), ("smart home devices sale", 100, 104, 111),
        ("budget laptop deals", 100, 100, 106), ("kids backpack sale", 100, 97, 103),
        ("air fryer black friday", 100, 94, 142), ("organic skincare bundle", 100, 102, 109),
        ("home gym equipment deals", 100, 106, 118), ("reusable water bottle set", 100, 99, 104),
    ],
    "Travel": [
        ("last minute flights europe", 100, 122, 156), ("family resort deals", 100, 117, 144),
        ("business class flights sale", 100, 113, 137), ("ski holiday packages", 100, 108, 128),
        ("beach resort all inclusive", 100, 120, 149), ("budget airline flight deals", 100, 115, 141),
        ("romantic city breaks", 100, 110, 133), ("cruise holiday deals", 100, 119, 146),
        ("solo travel packages", 100, 112, 134), ("adventure travel tours", 100, 114, 139),
    ],
}

# Invented category-level device/daypart exposure mix for the media-mix
# report -- a measurement cut the ads-data CSV doesn't carry at category
# level, so it adds genuinely new context rather than echoing a column.
DEVICE_MIX = {
    "Insurance": {"Mobile": 52, "Desktop": 40, "Tablet": 8},
    "Retail": {"Mobile": 68, "Desktop": 27, "Tablet": 5},
    "Travel": {"Mobile": 58, "Desktop": 35, "Tablet": 7},
}
DAYPART_MIX = {
    "Insurance": {"Morning (6-11)": 22, "Midday (11-15)": 24, "Evening (15-21)": 38, "Night (21-6)": 16},
    "Retail": {"Morning (6-11)": 18, "Midday (11-15)": 22, "Evening (15-21)": 44, "Night (21-6)": 16},
    "Travel": {"Morning (6-11)": 24, "Midday (11-15)": 26, "Evening (15-21)": 34, "Night (21-6)": 16},
}

VERTICAL_ORDER = ["Insurance", "Retail", "Travel"]
ACCTS_BY_VERTICAL = {a["vertical"]: (aid, a) for aid, a in ACCOUNTS.items()}


def all_markets_history(vertical):
    """{market_name: 8-quarter index series} for the pilot market + all 8
    comparison markets in this vertical."""
    aid, a = ACCTS_BY_VERTICAL[vertical]
    out = {a["country"] + " (pilot account market)": pilot_history_series(a)}
    for country, growth, _bench_is in EXTRA_MARKETS[vertical]:
        out[country] = market_history_series(growth)
    return out


def all_competitors(vertical):
    aid, a = ACCTS_BY_VERTICAL[vertical]
    return a["competitors"] + EXTRA_COMPETITORS[vertical]


def all_keywords(vertical, canonical):
    return canonical[vertical] + EXTRA_KEYWORDS[vertical]


def pilot_history_series(a):
    return [
        a["demand_index"]["Q4 2025"]["prior_year"], a["demand_index"]["Q1 2026"]["prior_year"],
        a["demand_index"]["Q2 2026"]["prior_year"], a["demand_index"]["Q3 2026"]["prior_year"],
        a["demand_index"]["Q4 2025"]["current"], a["demand_index"]["Q1 2026"]["current"],
        a["demand_index"]["Q2 2026"]["current"], a["demand_index"]["Q3 2026"]["current"],
    ]


def market_history_series(country_growth_pct):
    """8-quarter illustrative index series for a comparison market: starts a
    little below 100, reaches exactly 100 at Q4 2025 (the report's fixed
    baseline quarter), then rises to roughly 100+country_growth_pct by
    Q3 2026 -- same index convention as the pilot accounts' real series."""
    end = 100 + country_growth_pct
    ramp_in = [round(100 - (4 - i) * (country_growth_pct * 0.18) + _hist_rng.uniform(-1.5, 1.5)) for i in range(4)]
    ramp_in[-1] = 100  # Q4 2025 baseline, exact
    step = (end - 100) / 3
    ramp_out = [round(100 + step * i + _hist_rng.uniform(-1.5, 1.5)) for i in range(1, 3)]
    return ramp_in + ramp_out + [round(end)]


def market_profile_paragraph(vertical, country, growth, bench_is, idx):
    templates = [
        f"{country}'s {vertical.lower()} search category grew {growth:.1f}% quarter over quarter, with "
        f"the vertical-average advertiser capturing {bench_is:.1f}% impression share -- "
        f"{'above' if bench_is > 28 else 'below'} the panel median for this edition.",
        f"In {country}, {vertical.lower()} advertisers saw {growth:.1f}% QoQ spend growth against a "
        f"{bench_is:.1f}% average impression share benchmark, placing this market "
        f"{'among the more contested' if bench_is < 25 else 'among the less contested'} in the panel.",
        f"{vertical} category spend in {country} rose {growth:.1f}% this quarter. The {bench_is:.1f}% "
        f"average impression share benchmark here reflects a "
        f"{'fragmented' if bench_is < 25 else 'moderately consolidated'} competitive set.",
        f"{country} rounds out the panel with {growth:.1f}% QoQ category growth and a {bench_is:.1f}% "
        f"average impression share benchmark -- "
        f"{'consistent with' if 20 < bench_is < 32 else 'a notable outlier against'} the cross-market median.",
    ]
    return templates[idx % len(templates)]


def para(text, style):
    return Paragraph(text, style)


def spacer(h=0.12):
    return Spacer(1, h * inch)


def section_break():
    return PageBreak()


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

def cover(vendor, styles, accent):
    flow = [
        spacer(2.2),
        para(vendor["name"], styles["CoverSubtitle"]),
        para(vendor["report_title"], styles["CoverTitle"]),
        spacer(0.3),
        para(f"{REPORT_PERIOD} Edition -- Vertical Coverage: Insurance, Retail, Travel", styles["CoverMeta"]),
        para(f"Data type: {vendor['data_type']}", styles["CoverMeta"]),
        para(f"Format: {vendor['format']}", styles["CoverMeta"]),
        spacer(1.0),
        para("Prepared for internal pilot evaluation. Distribution restricted.", styles["CoverMeta"]),
        para("All figures in this edition are SYNTHETIC and illustrative -- generated to mirror the "
             "structure and field names of a real subscription report for development purposes only.",
             styles["CoverMeta"]),
        NextPageTemplate("Normal"),
        section_break(),
    ]
    return flow


def toc_page(styles):
    return [para("Table of Contents", styles["H1"]), pc.make_toc(styles), section_break()]


# What each vendor uniquely answers, and why the other 3 in this set don't
# already cover it -- this is the paragraph that makes the case for why a
# real pilot needs all 4 data-access agreements, not just one.
PURPOSE_TEXT = {
    "analyst": (
        "This report answers one question: is the category growing, and is advertiser spend "
        "keeping pace with it, or falling behind? It is the only one of the four reports in this "
        "set that benchmarks impression share and the split between budget-constrained and "
        "rank-constrained missed opportunity at the vertical level -- the \"is there a problem, and "
        "roughly how big\" layer. It does not identify which specific competitors are capturing the "
        "share being missed (see SignalWatch Competitive Intelligence), what channels beyond search "
        "are absorbing budget (see Vantage Media Metrics), or what any of this costs at the "
        "individual keyword (see QueryScope Insights)."
    ),
    "media_mix": (
        "This report answers: where else is category budget going, beyond paid search? It is the "
        "only one of the four that measures cross-channel spend share, reach, and frequency across "
        "Search, Social, Display, and Video/CTV together. Ashcroft Research Partners' benchmarks are "
        "search-only; this report is what tells you whether a weakening search position reflects "
        "category-wide underinvestment or whether budget has simply migrated to another channel -- "
        "a very different story for a seller to tell a customer."
    ),
    "competitive": (
        "This report answers: who, specifically, is capturing the share a given account is missing? "
        "It is the only one of the four that names individual competitors with their own estimated "
        "spend share, active creative volume, and channel presence. Ashcroft Research Partners "
        "reports the vertical average; this report tells you whether that average is being driven by "
        "one dominant advertiser or a crowded, fragmented field of many -- which changes what a "
        "seller can credibly recommend."
    ),
    "search_demand": (
        "This report answers: at the individual keyword/query level, what is actually happening? It "
        "is the only one of the four measuring below the vertical/category level -- at the exact "
        "grain non-brand search campaigns compete on. Note this report was not in the original "
        "3-vendor list; it was added because none of the other three measure at keyword grain, and "
        "without that, a recommendation to \"raise bids on these specific terms\" has no evidence to "
        "point to."
    ),
}


def purpose_section(vendor_key, vendor, styles, accent):
    return [
        para("About This Report", styles["H1"]),
        para(f"{vendor['name']} publishes the \"{vendor['report_title']}\" quarterly, covering: "
             f"{vendor['data_type']}.", styles["Body"]),
        para(PURPOSE_TEXT[vendor_key], styles["Body"]),
        section_break(),
    ]


def methodology_section(vendor_key, vendor, styles):
    texts = {
        "analyst": (
            "This report synthesizes category-level digital advertising spend, query demand, and "
            "pricing data for the covered verticals, drawing on a blended panel of search-platform "
            "auction logs, advertiser self-reports, and category spend models. Figures are indexed "
            "to a Q4 2025 baseline of 100 and refreshed quarterly. Vertical benchmarks (impression "
            "share, cost-per-click, and the two components of missed-impression attribution -- "
            "budget-constrained vs. rank-constrained) are computed across a panel of accounts large "
            "enough to be directionally stable quarter to quarter, then validated against the "
            "category-level spend and demand indices in this same report. Forecasts are directional, "
            "not point estimates, and should be read as a planning range."
        ),
        "media_mix": (
            "Cross-channel spend share, reach, and frequency are measured via a blended panel "
            "combining platform-reported delivery data with a third-party audience panel used to "
            "de-duplicate reach across channels. The Ad Intensity Index normalizes total measured "
            "ad pressure in a category to a base of 100, so values above 100 indicate a more "
            "contested, more expensive category than the cross-vertical average in this edition. "
            "Reach and frequency are reported against the addressable 18+ online population in "
            "each covered market."
        ),
        "competitive": (
            "Named-competitor spend share is modeled from observed creative volume, estimated "
            "placement value, and publicly inferable flight dates -- it is a share-of-voice estimate, "
            "not a verified media-buy figure, and should be treated as directional. Creative counts "
            "reflect distinct creative executions observed active at any point during the reporting "
            "quarter, not concurrently. Channel presence is a simple active/inactive flag per channel "
            "per competitor for the quarter."
        ),
        "search_demand": (
            "Query volume indices are built from aggregated, de-identified search query logs, "
            "indexed to a Q4 2025 baseline of 100 per keyword cluster. Keyword-level CPC benchmarks "
            "reflect the median observed cost-per-click across the panel for that exact query or its "
            "closest normalized variant. The SERP Competitive Density Index combines the number of "
            "distinct paid advertisers observed per query with average ad-slot saturation, normalized "
            "to a base of 100."
        ),
    }
    return [
        para("Methodology", styles["H1"]),
        para(texts[vendor_key], styles["Body"]),
        para("Scope & Limitations", styles["H2"]),
        para(f"This edition covers 3 verticals (Insurance, Retail, Travel) with one highlighted "
             f"market per vertical, set in a broader comparison panel of {len(EXTRA_MARKETS['Insurance'])+1} "
             "markets per vertical for context. All figures in this specific edition are SYNTHETIC, "
             "produced to validate a downstream recommendation pipeline before a production data-access "
             "agreement with a real research vendor is in place.", styles["Body"]),
        section_break(),
    ]


def glossary_section(styles):
    terms = [
        ("Impression Share", "The % of eligible auctions an advertiser's ad was actually shown in."),
        ("Impression Share Lost (Budget)", "The % of eligible auctions missed because daily budget ran out."),
        ("Impression Share Lost (Rank)", "The % of eligible auctions missed because of ad rank / quality, not budget."),
        ("Demand Index", "Search query volume indexed to a fixed base quarter (100)."),
        ("Ad Intensity Index", "Composite measure of how contested / expensive a category's media is, indexed to 100."),
        ("Share of Voice", "A competitor's estimated share of total category ad spend."),
        ("SERP Competitive Density", "How many distinct advertisers and how saturated the paid slots are for a query."),
        ("QoQ / YoY", "Quarter-over-quarter / year-over-year change."),
    ]
    rows = [[t, d] for t, d in terms]
    return [
        para("Glossary", styles["H1"]),
        pc.data_table(["Term", "Definition"], rows, col_widths=[1.8 * inch, 4.7 * inch], styles=styles),
        section_break(),
    ]


def about_section(vendor, styles):
    return [
        para(f"About {vendor['name']}", styles["H1"]),
        para(f"{vendor['name']} is a fictitious research entity created solely to give this synthetic "
             f"dataset a realistic, consistent source attribution. It produces a quarterly "
             f"\"{vendor['report_title']}\" covering: {vendor['data_type']}. No such company exists; "
             "any resemblance to a real research vendor is coincidental and unintended.",
             styles["Body"]),
        para("Disclaimer", styles["H2"]),
        para("Every figure in this document is synthetic and was generated for internal pilot "
             "development. It must not be quoted, cited, or shared as real market research.",
             styles["Callout"]),
    ]


def vertical_markets_table(vertical, our_country, our_benchmark_is, our_growth, styles, accent):
    rows = [[our_country + " (pilot account market)", f"{our_growth:.1f}%", f"{our_benchmark_is:.1f}%"]]
    for country, growth, bench_is in EXTRA_MARKETS[vertical]:
        rows.append([country, f"{growth:.1f}%", f"{bench_is:.1f}%"])
    return pc.data_table(
        ["Market", "Search Spend Growth QoQ", "Vertical-Avg Impression Share"],
        rows, col_widths=[2.6 * inch, 2.0 * inch, 2.4 * inch], styles=styles, accent=accent,
    )


# ---------------------------------------------------------------------------
# Vendor 1: Ashcroft Research Partners -- analyst / vertical trends
# ---------------------------------------------------------------------------

def build_ashcroft():
    v = VENDORS["analyst"]
    accent = "#2E4057"
    styles = pc.get_styles(accent)
    flow = []
    flow += cover(v, styles, accent)
    flow += toc_page(styles)
    flow += purpose_section("analyst", v, styles, accent)

    flow.append(para("Executive Summary", styles["H1"]))
    flow.append(para(
        "Digital search advertising spend accelerated across all three covered verticals this "
        "quarter, with Travel posting the sharpest rebound and Insurance showing the widest gap "
        "between category growth and the typical advertiser's ability to capture it. Retail "
        "demand grew more steadily but advertiser budgets broadly failed to keep pace, pushing "
        "budget-driven impression loss to multi-quarter highs in that vertical.", styles["Body"]))
    summary_rows = []
    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        summary_rows.append([
            vert, a["country"], f"{a['market']['spend_growth_qoq_pct']:.1f}%",
            f"{a['market']['query_demand_growth_qoq_pct']:.1f}%",
            f"{a['benchmark_impression_share_pct']:.1f}%",
        ])
    flow.append(pc.data_table(
        ["Vertical", "Highlighted Market", "Spend Growth QoQ", "Query Demand Growth QoQ", "Vertical-Avg Impression Share"],
        summary_rows, col_widths=[1.0 * inch, 1.3 * inch, 1.3 * inch, 1.6 * inch, 1.7 * inch], styles=styles, accent=accent))
    flow.append(spacer(0.15))
    flow.append(para(
        "Figures reflect the highlighted market in each vertical; see each vertical's section for "
        "the full comparison panel.", styles["Caption"]))
    flow.append(section_break())

    flow += methodology_section("analyst", v, styles)

    for i, vert in enumerate(VERTICAL_ORDER):
        aid, a = ACCTS_BY_VERTICAL[vert]
        m = a["market"]
        flow.append(para(f"{vert}: {a['country']} Deep Dive", styles["H1"]))
        flow.append(para(
            f"{vert} search spend in {a['country']} grew {m['spend_growth_qoq_pct']:.0f}% quarter over "
            f"quarter in {REPORT_PERIOD}, against {m['query_demand_growth_qoq_pct']:.0f}% underlying "
            f"query demand growth and {m['cpc_growth_qoq_pct']:.0f}% average CPC inflation -- consistent "
            "with more advertisers chasing a growing but not proportionally larger pool of clicks.",
            styles["Body"]))
        flow.append(pc.key_takeaways("Key Takeaways", [
            f"Spend grew {m['spend_growth_qoq_pct']:.0f}% QoQ vs. {m['query_demand_growth_qoq_pct']:.0f}% "
            "underlying demand growth -- the gap is competitive intensity, not new demand.",
            f"Vertical-average impression share benchmark: {a['benchmark_impression_share_pct']:.1f}%.",
            f"{a['country']} ranks "
            f"{'above' if m['spend_growth_qoq_pct'] > 12 else 'near'} the panel median on spend growth "
            f"this quarter (see Regional Market Profiles below).",
        ], styles, accent))
        flow.append(spacer(0.1))
        flow.append(para("Demand Trend", styles["H2"]))
        cats = QUARTERS
        cur = [a["demand_index"][q]["current"] for q in cats]
        pri = [a["demand_index"][q]["prior_year"] for q in cats]
        chart_p = pc.fig_grouped_bar(cats, {"Current year": cur, "Prior-year pattern": pri},
                                      f"{vert} Demand Index vs. Seasonal Norm", "Index (Q4 2025 = 100)", accent)
        flow.append(pc.chart_image(chart_p))
        flow.append(para(
            f"By {QUARTERS[-1]}, the index reached {cur[-1]} against a prior-year seasonal pattern of "
            f"{pri[-1]} -- a {cur[-1]-pri[-1]} point gap above normal seasonal growth, the widest of the "
            "four quarters shown.", styles["Caption"]))

        flow.append(para("Benchmark Positioning", styles["H2"]))
        flow.append(para(
            f"The typical advertiser in this vertical/market captures {a['benchmark_impression_share_pct']:.1f}% "
            "average impression share. Missed impressions split between budget and rank constraints "
            "differently depending on the advertiser's own budget posture -- see each vendor's "
            "companion report for how a specific account compares.", styles["Body"]))

        flow.append(para("Markets in This Report", styles["H2"]))
        flow.append(vertical_markets_table(vert, a["country"], a["benchmark_impression_share_pct"],
                                            m["spend_growth_qoq_pct"], styles, accent))
        flow.append(spacer(0.1))
        flow.append(para(
            "Comparison markets are shown for category context; only the highlighted market has a "
            "matching pilot account in the companion ads-data export.", styles["Caption"]))

        flow.append(para("Regional Market Profiles", styles["H2"]))
        for j, (country, growth, bench_is) in enumerate(EXTRA_MARKETS[vert]):
            flow.append(para(country, styles["H3"]))
            flow.append(para(market_profile_paragraph(vert, country, growth, bench_is, j), styles["Body"]))

        flow.append(para("Outlook", styles["H2"]))
        outlook = {
            "Insurance": "Expect continued rank pressure as larger, better-funded competitors consolidate "
                         "share in non-brand search; advertisers under-indexing on quality score and bid "
                         "strategy sophistication will keep losing ground even without a budget change.",
            "Retail": "With category demand growing steadily but budgets not expanding at the same pace, "
                      "budget-driven impression loss is likely to persist into next quarter unless "
                      "advertisers reallocate spend toward higher-margin categories or raise caps.",
            "Travel": "The demand surge looks structural, not one-quarter noise -- advertisers that do not "
                      "expand budget to match will cede the incremental demand to competitors already "
                      "repricing their bids upward.",
        }[vert]
        flow.append(para(outlook, styles["Body"]))
        flow.append(section_break())

    flow.append(para("Cross-Vertical Comparison", styles["H1"]))
    cats = VERTICAL_ORDER
    spend_g = [ACCTS_BY_VERTICAL[v_][1]["market"]["spend_growth_qoq_pct"] for v_ in cats]
    demand_g = [ACCTS_BY_VERTICAL[v_][1]["market"]["query_demand_growth_qoq_pct"] for v_ in cats]
    cpc_g = [ACCTS_BY_VERTICAL[v_][1]["market"]["cpc_growth_qoq_pct"] for v_ in cats]
    chart_p = pc.fig_grouped_bar(cats, {"Spend Growth": spend_g, "Query Demand Growth": demand_g, "CPC Growth": cpc_g},
                                  "Quarter-over-Quarter Growth by Vertical", "% QoQ", accent)
    flow.append(pc.chart_image(chart_p))
    flow.append(para(
        "Travel's growth is broad-based across spend, demand, and price. Insurance's spend growth "
        "outpaces its own query demand growth, implying rising competitive intensity rather than new "
        "category demand. Retail sits at the steadiest, most moderate growth of the three.",
        styles["Body"]))
    flow.append(section_break())

    flow.append(para("Appendix A: 8-Quarter Demand Index History -- Highlighted Market", styles["H1"]))
    flow.append(para(
        "Each quarter's \"current\" and \"prior-year\" figures are both already on the same continuous "
        "Q4 2025 = 100 index scale, so lined up end to end they form one continuous 8-quarter series "
        "per market -- shown here rather than as two separate 4-quarter snapshots.", styles["Body"]))
    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(f"{vert} -- {a['country']}", styles["H2"]))
        hist = pilot_history_series(a)
        chart_p = pc.fig_line(HIST_QUARTERS, {"Demand Index": hist}, f"{vert} 8-Quarter Demand Index", "Index", accent)
        flow.append(pc.chart_image(chart_p))
        rows = [[HIST_QUARTERS[i], hist[i]] for i in range(8)]
        flow.append(pc.data_table(["Quarter", "Demand Index"], rows,
                                   col_widths=[1.8 * inch, 1.5 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow.append(para("Appendix B: Full Historical Data Export -- All Markets", styles["H1"]))
    flow.append(para(
        "The complete 8-quarter demand index series for every market in this edition's comparison "
        "panel, not just the highlighted one -- the raw export behind every chart and regional "
        "profile in this report.", styles["Body"]))
    for vert in VERTICAL_ORDER:
        flow.append(para(vert, styles["H2"]))
        hist_by_market = all_markets_history(vert)
        rows = []
        for market, series in hist_by_market.items():
            for q, val in zip(HIST_QUARTERS, series):
                rows.append([market, q, val])
        flow.append(pc.data_table(["Market", "Quarter", "Demand Index"], rows,
                                   col_widths=[2.6 * inch, 1.4 * inch, 1.4 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.15))
        flow.append(section_break())

    flow.append(para("Appendix B: Quarterly Benchmark Tables", styles["H1"]))
    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(f"{vert} -- {a['country']}", styles["H2"]))
        rows = [[q, a["demand_index"][q]["current"], a["demand_index"][q]["prior_year"],
                 f"{a['market']['spend_growth_qoq_pct']:.1f}%", f"{a['market']['cpc_growth_qoq_pct']:.1f}%"]
                for q in QUARTERS]
        flow.append(pc.data_table(
            ["Quarter", "Demand Index (Current)", "Demand Index (Prior Year)", "Spend Growth QoQ", "CPC Growth QoQ"],
            rows, col_widths=[1.1 * inch, 1.6 * inch, 1.6 * inch, 1.3 * inch, 1.2 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow += glossary_section(styles)
    flow += about_section(v, styles)
    return flow


# ---------------------------------------------------------------------------
# Vendor 2: Vantage Media Metrics -- media mix / ad intensity
# ---------------------------------------------------------------------------

def build_vantage():
    v = VENDORS["media_mix"]
    accent = "#4C7A8C"
    styles = pc.get_styles(accent)
    flow = []
    flow += cover(v, styles, accent)
    flow += toc_page(styles)
    flow += purpose_section("media_mix", v, styles, accent)

    flow.append(para("Executive Summary", styles["H1"]))
    flow.append(para(
        "Retail carries the highest measured ad intensity of the three covered verticals this "
        "quarter, driven by a Social-heavy channel mix and the highest average exposure frequency. "
        "Travel's channel mix skews most heavily to Search and Video, consistent with longer, "
        "higher-consideration purchase journeys. Insurance sits in between, with Search still the "
        "largest single channel but Video/CTV a growing share.", styles["Body"]))
    summary_rows = [[vert, f"{ACCTS_BY_VERTICAL[vert][1]['ad_intensity_index']}",
                      f"{ACCTS_BY_VERTICAL[vert][1]['reach_pct']}%", f"{ACCTS_BY_VERTICAL[vert][1]['frequency']}"]
                     for vert in VERTICAL_ORDER]
    flow.append(pc.data_table(["Vertical", "Ad Intensity Index", "Reach %", "Avg Frequency"],
                               summary_rows, col_widths=[1.6*inch, 1.8*inch, 1.5*inch, 1.5*inch],
                               styles=styles, accent=accent))
    flow.append(section_break())

    flow += methodology_section("media_mix", v, styles)

    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(f"{vert}: {a['country']} Media Mix", styles["H1"]))
        flow.append(para(
            f"Ad Intensity Index: {a['ad_intensity_index']} (base 100). Reach: {a['reach_pct']}% of the "
            f"addressable 18+ online population. Average frequency: {a['frequency']} exposures per "
            "reached person in the quarter.", styles["Body"]))
        flow.append(pc.key_takeaways("Key Takeaways", [
            f"Ad Intensity Index of {a['ad_intensity_index']} is "
            f"{'above' if a['ad_intensity_index'] > 110 else 'close to'} the cross-vertical baseline of 100.",
            f"{max(a['channel_mix_pct'], key=a['channel_mix_pct'].get)} is the largest single channel at "
            f"{max(a['channel_mix_pct'].values())}% of category spend.",
            f"Device mix skews {'mobile' if DEVICE_MIX[vert]['Mobile'] >= 55 else 'desktop'}-heavy "
            f"({DEVICE_MIX[vert]['Mobile']}% mobile).",
        ], styles, accent))
        flow.append(spacer(0.1))
        flow.append(para("Channel Mix", styles["H2"]))
        mix = a["channel_mix_pct"]
        chart_p = pc.fig_stacked_bar([a["country"]], {ch: [pct] for ch, pct in mix.items()},
                                      f"{vert} Category Spend Share by Channel", "% of category spend", accent)
        flow.append(pc.chart_image(chart_p, width=4.5 * inch))
        rows = [[ch, f"{pct}%"] for ch, pct in mix.items()]
        flow.append(pc.data_table(["Channel", "Share of Category Spend"], rows,
                                   col_widths=[2.6 * inch, 2.0 * inch], styles=styles, accent=accent))
        flow.append(para("Reach & Frequency Detail", styles["H2"]))
        freq_curve = [round(a["frequency"] * f, 1) for f in (0.4, 0.65, 0.85, 1.0, 1.15)]
        reach_curve = [round(a["reach_pct"] * f, 1) for f in (0.5, 0.72, 0.88, 1.0, 1.05)]
        chart_p2 = pc.fig_line(["Wk 1-2", "Wk 3-5", "Wk 6-8", "Wk 9-11", "Wk 12-13"],
                                {"Cumulative Reach %": reach_curve, "Cumulative Frequency": freq_curve},
                                f"{vert} Reach/Frequency Build, {REPORT_PERIOD}", "Index value", accent)
        flow.append(pc.chart_image(chart_p2))
        flow.append(para(
            "Reach builds fastest in the first half of the quarter and plateaus; frequency keeps "
            "climbing through the full 13 weeks as retargeting and sustaining campaigns continue "
            "to serve against an already-reached audience.", styles["Caption"]))

        flow.append(para("Device & Daypart Mix", styles["H2"]))
        device_mix = DEVICE_MIX[vert]
        chart_p3 = pc.fig_stacked_bar(["Device Mix"], {d: [p] for d, p in device_mix.items()},
                                       f"{vert} Measured Ad Exposure by Device", "% of exposure", accent)
        flow.append(pc.chart_image(chart_p3, width=4.2 * inch))
        daypart = DAYPART_MIX[vert]
        chart_p4 = pc.fig_grouped_bar(list(daypart.keys()), {"Share of Exposure": list(daypart.values())},
                                       f"{vert} Ad Exposure by Daypart", "% of exposure", accent)
        flow.append(pc.chart_image(chart_p4))
        flow.append(para(
            f"{vert} skews {'mobile' if device_mix['Mobile'] >= 55 else 'desktop'}-heavy on device and "
            f"peaks during {max(daypart, key=daypart.get)}, consistent with "
            f"{'on-the-go, lower-consideration browsing' if device_mix['Mobile'] >= 55 else 'more deliberate, research-driven sessions'}.",
            styles["Body"]))

        flow.append(para("Ad Intensity Trend", styles["H2"]))
        intensity_hist = [round(a["ad_intensity_index"] * f) for f in (0.84, 0.90, 0.95, 1.0)]
        chart_p5 = pc.fig_line(QUARTERS, {"Ad Intensity Index": intensity_hist}, f"{vert} Ad Intensity Index Trend", "Index", accent)
        flow.append(pc.chart_image(chart_p5))
        flow.append(para(
            f"Ad intensity in this vertical/market has risen every quarter shown, reaching "
            f"{intensity_hist[-1]} in {QUARTERS[-1]} -- {'well above' if intensity_hist[-1] > 110 else 'close to'} "
            "the cross-vertical baseline of 100.", styles["Caption"]))
        flow.append(section_break())

    flow.append(para("Cross-Vertical Comparison", styles["H1"]))
    chart_p = pc.fig_grouped_bar(VERTICAL_ORDER,
                                  {"Ad Intensity Index": [ACCTS_BY_VERTICAL[v_][1]["ad_intensity_index"] for v_ in VERTICAL_ORDER],
                                   "Reach %": [ACCTS_BY_VERTICAL[v_][1]["reach_pct"] for v_ in VERTICAL_ORDER]},
                                  "Ad Intensity and Reach by Vertical", "Index / %", accent)
    flow.append(pc.chart_image(chart_p))
    flow.append(section_break())

    flow.append(para("Appendix A: Channel Mix Detail by Vertical", styles["H1"]))
    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(vert, styles["H2"]))
        rows = [[ch, f"{pct}%", "Measured" if pct >= 15 else "Measured (low-volume)"] for ch, pct in a["channel_mix_pct"].items()]
        flow.append(pc.data_table(["Channel", "Share", "Measurement Confidence"], rows,
                                   col_widths=[2.2 * inch, 1.6 * inch, 2.6 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow.append(para("Appendix B: Device & Daypart Detail by Vertical", styles["H1"]))
    for vert in VERTICAL_ORDER:
        flow.append(para(vert, styles["H2"]))
        rows_d = [[d, f"{p}%"] for d, p in DEVICE_MIX[vert].items()]
        flow.append(pc.data_table(["Device", "Share of Exposure"], rows_d,
                                   col_widths=[2.2 * inch, 2.0 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.08))
        rows_dp = [[d, f"{p}%"] for d, p in DAYPART_MIX[vert].items()]
        flow.append(pc.data_table(["Daypart", "Share of Exposure"], rows_dp,
                                   col_widths=[2.2 * inch, 2.0 * inch], styles=styles, accent=accent, small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow += glossary_section(styles)
    flow += about_section(v, styles)
    return flow


# ---------------------------------------------------------------------------
# Vendor 3: SignalWatch Competitive Intelligence -- competitive spend
# ---------------------------------------------------------------------------

def build_signalwatch():
    v = VENDORS["competitive"]
    accent = "#8FA6A3"
    styles = pc.get_styles("#5C7A77")
    flow = []
    flow += cover(v, styles, "#5C7A77")
    flow += toc_page(styles)
    flow += purpose_section("competitive", v, styles, "#5C7A77")

    flow.append(para("Executive Summary", styles["H1"]))
    flow.append(para(
        "Across all three covered verticals, the top 4 tracked competitors account for the large "
        "majority of estimated category ad spend, and in each case our pilot account's own estimated "
        "spend share trails every one of them. The gap is most pronounced in Insurance, where the "
        "pilot account's spend share is roughly a quarter of the smallest tracked competitor's.",
        styles["Body"]))
    flow.append(section_break())

    flow += methodology_section("competitive", v, styles)

    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(f"{vert}: {a['country']} Competitive Landscape", styles["H1"]))
        comps = all_competitors(vert)
        flow.append(pc.key_takeaways("Key Takeaways", [
            f"{comps[0]['name']} leads the tracked set at {comps[0]['spend_share_pct']}% estimated spend share.",
            f"Pilot account's own estimated spend share: {a['account_spend_share_pct']}% -- "
            f"{'well behind' if a['account_spend_share_pct'] < comps[3]['spend_share_pct'] else 'competitive with'} "
            "the 4th-largest tracked competitor.",
            f"{len(comps)} competitors tracked this quarter across {len(set(c['channels'] for c in comps))} "
            "distinct channel-presence patterns.",
        ], styles, "#5C7A77"))
        flow.append(spacer(0.1))
        labels = [c["name"] for c in comps] + ["Pilot Account (this report)"]
        values = [c["spend_share_pct"] for c in comps] + [a["account_spend_share_pct"]]
        chart_p = pc.fig_horizontal_bar(labels, values, f"{vert} Estimated Spend Share", "% of category spend",
                                         accent="#5C7A77", highlight_last=True)
        flow.append(pc.chart_image(chart_p))
        rows = [[c["name"], f"{c['spend_share_pct']}%", c["creative_count"], c["channels"]] for c in comps]
        rows.append(["Pilot Account (this report)", f"{a['account_spend_share_pct']}%", "--", "Search (primary)"])
        flow.append(pc.data_table(["Competitor", "Spend Share", "Active Creatives", "Channels"], rows,
                                   col_widths=[2.0 * inch, 1.1 * inch, 1.1 * inch, 1.9 * inch], styles=styles, accent="#5C7A77"))
        flow.append(para("Competitor Notes", styles["H2"]))
        top = comps[0]
        flow.append(para(
            f"{top['name']} leads the tracked set at {top['spend_share_pct']}% estimated share, running "
            f"{top['creative_count']} distinct active creatives across {top['channels']}. The next two "
            f"competitors are within a few points of each other, suggesting an active, closely contested "
            "top tier rather than one dominant player. The tracked set runs {0} competitors deep in this "
            "vertical this quarter.".format(len(comps)), styles["Body"]))
        flow.append(para("Long-Tail Competitors", styles["H2"]))
        flow.append(para(
            "Below the top tier, a wider group of smaller advertisers hold single-digit spend shares "
            "but collectively represent a meaningful share of category volume:", styles["Body"]))
        rows2 = [[c["name"], f"{c['spend_share_pct']}%", c["creative_count"], c["channels"]] for c in comps[4:]]
        flow.append(pc.data_table(["Competitor", "Spend Share", "Active Creatives", "Channels"], rows2,
                                   col_widths=[2.0 * inch, 1.1 * inch, 1.1 * inch, 1.9 * inch], styles=styles, accent="#5C7A77", small=True))
        flow.append(section_break())

    flow.append(para("Cross-Vertical Comparison", styles["H1"]))
    cats = VERTICAL_ORDER
    top_share = [ACCTS_BY_VERTICAL[v_][1]["competitors"][0]["spend_share_pct"] for v_ in cats]
    our_share = [ACCTS_BY_VERTICAL[v_][1]["account_spend_share_pct"] for v_ in cats]
    chart_p = pc.fig_grouped_bar(cats, {"Top Competitor Share": top_share, "Pilot Account Share": our_share},
                                  "Top Competitor vs. Pilot Account Spend Share", "% of category spend", "#5C7A77")
    flow.append(pc.chart_image(chart_p))
    flow.append(section_break())

    flow.append(para("Appendix A: Full Competitor Profiles", styles["H1"]))
    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(vert, styles["H2"]))
        for c in all_competitors(vert):
            flow.append(para(
                f"<b>{c['name']}</b> -- estimated spend share {c['spend_share_pct']}%, "
                f"{c['creative_count']} active creatives, present on {c['channels']}.",
                styles["Body"]))
        flow.append(spacer(0.1))
    flow.append(section_break())

    flow += glossary_section(styles)
    flow += about_section(v, styles)
    return flow


# ---------------------------------------------------------------------------
# Vendor 4: QueryScope Insights -- search demand & keyword intelligence
# ---------------------------------------------------------------------------

def build_queryscope():
    v = VENDORS["search_demand"]
    accent = "#C9A66B"
    styles = pc.get_styles("#8A6D2F")
    flow = []
    flow += cover(v, styles, "#8A6D2F")
    flow += toc_page(styles)
    flow += purpose_section("search_demand", v, styles, "#8A6D2F")

    flow.append(para("Executive Summary", styles["H1"]))
    flow.append(para(
        "This edition was added to the vendor set specifically because none of the other three "
        "reports measure at keyword/query grain -- which is the level non-brand search campaigns "
        "actually compete on. Retail shows the most crowded result pages of the three verticals; "
        "Travel the fastest-rising keyword-level CPCs.", styles["Body"]))
    summary_rows = [[vert, f"{ACCTS_BY_VERTICAL[vert][1]['keyword_cpc_benchmark']:.2f}",
                      f"{ACCTS_BY_VERTICAL[vert][1]['keyword_cpc_growth_qoq_pct']:.1f}%",
                      f"{ACCTS_BY_VERTICAL[vert][1]['serp_competitive_density_index']}"]
                     for vert in VERTICAL_ORDER]
    flow.append(pc.data_table(["Vertical", "Keyword CPC Benchmark", "CPC Growth QoQ", "SERP Competitive Density"],
                               summary_rows, col_widths=[1.4*inch, 1.8*inch, 1.5*inch, 1.9*inch],
                               styles=styles, accent="#8A6D2F"))
    flow.append(section_break())

    flow += methodology_section("search_demand", v, styles)

    KEYWORD_SETS = {
        "Insurance": [("car insurance quote", 100, 112, 128), ("home insurance cost", 100, 104, 119),
                      ("life insurance comparison", 100, 101, 109), ("cheap auto insurance", 100, 115, 133)],
        "Retail": [("mens running shoes", 100, 103, 110), ("wireless headphones", 100, 106, 114),
                   ("winter jacket sale", 100, 98, 121), ("kitchen appliances deals", 100, 102, 108)],
        "Travel": [("flights to spain", 100, 118, 151), ("all inclusive holidays", 100, 121, 147),
                   ("cheap hotel deals", 100, 109, 132), ("weekend city breaks", 100, 112, 139)],
    }

    for vert in VERTICAL_ORDER:
        aid, a = ACCTS_BY_VERTICAL[vert]
        flow.append(para(f"{vert}: {a['country']} Keyword Intelligence", styles["H1"]))
        flow.append(para(
            f"Keyword-level CPC benchmark for this vertical/market: {a['currency_symbol']} "
            f"{a['keyword_cpc_benchmark']:.2f}, up {a['keyword_cpc_growth_qoq_pct']:.0f}% quarter over "
            f"quarter. SERP Competitive Density Index: {a['serp_competitive_density_index']} (base 100).",
            styles["Body"]))
        flow.append(pc.key_takeaways("Key Takeaways", [
            f"Keyword CPC benchmark {a['currency_symbol']} {a['keyword_cpc_benchmark']:.2f}, "
            f"up {a['keyword_cpc_growth_qoq_pct']:.0f}% QoQ.",
            f"SERP Competitive Density Index: {a['serp_competitive_density_index']} "
            f"({'above' if a['serp_competitive_density_index'] > 115 else 'near'} the cross-vertical baseline of 100).",
            f"{len(KEYWORD_SETS[vert]) + len(EXTRA_KEYWORDS[vert])} keywords tracked this quarter for this vertical/market.",
        ], styles, "#8A6D2F"))
        flow.append(spacer(0.1))
        flow.append(para("Top Query Volume Trend", styles["H2"]))
        kws = KEYWORD_SETS[vert]
        cats = ["Q4 2025", "Q2 2026", "Q3 2026"]
        series = {kw[0]: [kw[1], kw[2], kw[3]] for kw in kws}
        chart_p = pc.fig_line(cats, series, f"{vert} Query Volume Index -- Top Keywords", "Index (Q4 2025 = 100)", accent="#8A6D2F")
        flow.append(pc.chart_image(chart_p))
        rows = [[kw[0], kw[1], kw[2], kw[3], f"{round(100*(kw[3]-kw[1])/kw[1])}%"] for kw in kws]
        flow.append(pc.data_table(["Keyword", "Q4 2025", "Q2 2026", "Q3 2026", "Growth"], rows,
                                   col_widths=[2.2 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
                                   styles=styles, accent="#8A6D2F"))

        flow.append(para("Long-Tail Keyword Set", styles["H2"]))
        flow.append(para(
            "The top keywords above drive the largest share of volume, but non-brand search "
            "campaigns typically also compete on a long tail of lower-volume, often cheaper queries. "
            "The set tracked this quarter for this vertical/market:", styles["Body"]))
        extra_rows = [[kw[0], kw[1], kw[2], kw[3], f"{round(100*(kw[3]-kw[1])/kw[1])}%"] for kw in EXTRA_KEYWORDS[vert]]
        flow.append(pc.data_table(["Keyword", "Q4 2025", "Q2 2026", "Q3 2026", "Growth"], extra_rows,
                                   col_widths=[2.2 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
                                   styles=styles, accent="#8A6D2F", small=True))
        flow.append(section_break())

    flow.append(para("Cross-Vertical Comparison", styles["H1"]))
    chart_p = pc.fig_grouped_bar(VERTICAL_ORDER,
                                  {"CPC Growth QoQ %": [ACCTS_BY_VERTICAL[v_][1]["keyword_cpc_growth_qoq_pct"] for v_ in VERTICAL_ORDER],
                                   "SERP Density (/10)": [ACCTS_BY_VERTICAL[v_][1]["serp_competitive_density_index"] / 10 for v_ in VERTICAL_ORDER]},
                                  "Keyword CPC Growth and SERP Density by Vertical", "% / Index(/10)", "#8A6D2F")
    flow.append(pc.chart_image(chart_p))
    flow.append(section_break())

    flow.append(para("Appendix A: Full Keyword Tables (Top + Long-Tail)", styles["H1"]))
    for vert in VERTICAL_ORDER:
        flow.append(para(vert, styles["H2"]))
        rows = [[kw[0], kw[1], kw[2], kw[3]] for kw in all_keywords(vert, KEYWORD_SETS)]
        flow.append(pc.data_table(["Keyword", "Q4 2025 Index", "Q2 2026 Index", "Q3 2026 Index"], rows,
                                   col_widths=[2.6 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch], styles=styles, accent="#8A6D2F", small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow.append(para("Appendix B: SERP Feature Presence", styles["H1"]))
    flow.append(para(
        "Beyond standard text ads, paid placements increasingly compete against (or alongside) Shopping "
        "units, local packs, and featured snippets. Presence below is the share of tracked queries in "
        "this vertical/market where that feature appeared at least once during the quarter.", styles["Body"]))
    SERP_FEATURES = {
        "Insurance": [("Shopping Unit", "4%"), ("Local Pack", "38%"), ("Featured Snippet", "22%"), ("People Also Ask", "61%")],
        "Retail": [("Shopping Unit", "71%"), ("Local Pack", "19%"), ("Featured Snippet", "14%"), ("People Also Ask", "33%")],
        "Travel": [("Shopping Unit", "9%"), ("Local Pack", "44%"), ("Featured Snippet", "27%"), ("People Also Ask", "52%")],
    }
    for vert in VERTICAL_ORDER:
        flow.append(para(vert, styles["H2"]))
        flow.append(pc.data_table(["SERP Feature", "Query Presence Share"], SERP_FEATURES[vert],
                                   col_widths=[2.6 * inch, 2.0 * inch], styles=styles, accent="#8A6D2F", small=True))
        flow.append(spacer(0.15))
    flow.append(section_break())

    flow += glossary_section(styles)
    flow += about_section(v, styles)
    return flow


def main():
    jobs = [
        ("analyst", build_ashcroft, "#2E4057"),
        ("media_mix", build_vantage, "#4C7A8C"),
        ("competitive", build_signalwatch, "#5C7A77"),
        ("search_demand", build_queryscope, "#8A6D2F"),
    ]
    for key, builder, accent in jobs:
        v = VENDORS[key]
        out_path = str(OUT_DIR / f"{v['report_code']}.pdf")
        flow = builder()
        pc.build_pdf(out_path, accent, f"{v['name']} -- {v['report_title']} ({REPORT_PERIOD})", flow,
                     header_left=v["short"], header_right=f"{v['report_title']} | {REPORT_PERIOD}")
        pages = pc.page_count(out_path)
        print(f"{v['report_code']}.pdf: {pages} pages")


if __name__ == "__main__":
    main()

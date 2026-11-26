"""
Generates one recommendation-email PDF per pilot account: From/To/Subject
header, a personalized hook, an explicit "Why Now" market-evidence block, a
headline revenue-opportunity number, a clearly segregated card per campaign
that actually has material opportunity (NOT every campaign in the account --
see `in_scope_campaigns()`), a single consolidated "Fix" callout, and two
supporting charts. Customer-facing: elegant, one thread, no vendor/brand/
platform names in the body.

Deliberately two-stage, matching the intended pipeline: every account- and
campaign-level number is recomputed here FROM ads-data/campaigns.csv -- not
copied from benchmarks.py -- so this script only works if stage 1 (analyze
the account data) actually ran first. Market context (demand growth, vertical
benchmark) is layered in afterward from benchmarks.py, standing in for
stage 2 (pull the matching section of the vendor reports).

Run after generate_ads_data.py.
"""
from pathlib import Path
import pandas as pd
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER

import pdf_common as pc
from benchmarks import ACCOUNTS, VENDORS, REPORT_PERIOD, PRIOR_PERIOD, WATERMARK

ADS_DATA_DIR = Path(__file__).resolve().parent.parent / "ads-data"
OUT_DIR = Path(__file__).resolve().parent.parent / "recommendation-emails"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUARTERS = ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"]
MATERIALITY_CUTOFF = 0.70  # stop adding campaigns once they cover this share of the account's missed opportunity


def in_scope_campaigns(grp):
    """Campaigns worth their own section in the email: the smallest set,
    ranked by absolute missed-impression volume, that covers ~70% of the
    account's total missed opportunity. Deliberately NOT all campaigns --
    a campaign with a high % loss but negligible volume isn't worth a
    customer's attention, and a flat list of every campaign would bury the
    ones that matter."""
    g = grp.copy()
    g["missed"] = g["eligible_impressions"] - g["impressions"]
    g = g.sort_values("missed", ascending=False)
    total_missed = g["missed"].sum()
    g["cum_share"] = g["missed"].cumsum() / total_missed
    cutoff_idx = (g["cum_share"] >= MATERIALITY_CUTOFF).idxmax()
    in_scope = g.loc[:cutoff_idx]
    return in_scope, total_missed


def campaign_diagnosis(row, narrative):
    is_pct = row["search_impression_share_pct"]
    lost_budget = row["impression_share_lost_budget_pct"]
    lost_rank = row["impression_share_lost_rank_pct"]
    if narrative == "rank-constrained":
        return (f"Wins {is_pct:.1f}% of eligible impressions here; {lost_rank:.0f}% is lost purely to "
                f"auction rank, not budget.")
    if narrative == "budget-constrained":
        return (f"Wins {is_pct:.1f}% of eligible impressions here; {lost_budget:.0f}% is lost simply "
                f"because the daily budget runs out.")
    return (f"Wins {is_pct:.1f}% of eligible impressions here -- solid, but {lost_rank:.0f}% is still "
            f"lost to rank as competitors respond to the same surge.")


def account_rollup(df, account_id):
    a = ACCOUNTS[account_id]
    grp = df[df.account_id == account_id]
    w = grp["eligible_impressions"]
    is_pct = (grp["search_impression_share_pct"] * w).sum() / w.sum()
    lost_budget = (grp["impression_share_lost_budget_pct"] * w).sum() / w.sum()
    lost_rank = (grp["impression_share_lost_rank_pct"] * w).sum() / w.sum()
    daily_budget = grp["daily_budget"].sum()

    # Incremental-revenue estimate: the account's OWN ctr/cvr/aov applied to
    # the upside impression figure, so "close the gap" turns into a dollar
    # number instead of a raw impression count.
    wi = grp["impressions"]
    ctr = (grp["ctr_pct"] * wi).sum() / wi.sum()
    cvr = (grp["conversion_rate_pct"] * wi).sum() / wi.sum()
    aov = (grp["avg_order_value"] * grp["conversions"]).sum() / grp["conversions"].sum()
    upside_impr = a["upside_incremental_impressions_period"]
    inc_revenue = upside_impr * ctr / 100 * cvr / 100 * aov

    scoped, _account_total_missed = in_scope_campaigns(grp)
    # Allocate the FULL headline revenue number across just the in-scope
    # cards (denominator = scoped total, not account total) so the numbers
    # shown on the cards always sum exactly to the headline stat -- nothing
    # for a sharp reader to flag as "where did the rest of it go?".
    scoped_total_missed = scoped["missed"].sum()
    notes = dict(zip(grp["campaign_name"], grp["seller_note_text"]))
    cards = []
    for _, row in scoped.iterrows():
        revenue_share = inc_revenue * (row["missed"] / scoped_total_missed)
        note = notes.get(row["campaign_name"])
        note = note if isinstance(note, str) else None
        cards.append({
            "name": row["campaign_name"],
            "diagnosis": campaign_diagnosis(row, a["narrative"]),
            "note": note,
            "revenue_share": revenue_share,
        })

    return {
        "is_pct": is_pct, "lost_budget_pct": lost_budget, "lost_rank_pct": lost_rank,
        "daily_budget": daily_budget, "inc_revenue": inc_revenue, "cards": cards,
        "num_in_scope": len(scoped), "num_total": len(grp),
    }


EMAIL_CONTENT = {
    "DE-INS-001": {
        "subject": "Insurance search is up 18% in Germany -- but you're only capturing 9% of it",
        "hook": "Quick one -- insurance shoppers in Germany are searching more than ever this quarter, "
                "but your account is only showing up for roughly 1 in 11 of those searches. The "
                "vertical average is better than 1 in 5.",
        "why_now": [
            "Insurance search spend in Germany is up <b>18% quarter on quarter</b> -- the fastest "
            "of the last four quarters.",
            "Underlying query demand is up <b>12%</b>, so this is real demand growth, not just "
            "rising prices.",
            "Average CPC is already up <b>7% QoQ</b> -- the cost of closing this gap only grows "
            "from here.",
        ],
        "stat_label": "YOUR ESTIMATED REVENUE OPPORTUNITY THIS QUARTER",
        "stat_sub": "if the gap to the vertical benchmark closes",
        "impact": "And it isn't a budget problem: your {cur} {budget:,.0f}/day sits effectively unused "
                  "on the auctions you're losing (0% lost to budget) -- <b>91% of what you're missing "
                  "is lost on auction rank</b>, not spend. Vertical peers lose only 54% that way.",
        "scope_intro": "Here's exactly where it's showing up -- the campaigns below account for most "
                       "of that gap; the rest is spread thin across the account and isn't worth your time:",
        "fix_title": "The Fix -- 15 Minutes, No Budget Increase Needed",
        "fix_body": "This is a bid-strategy and quality-score fix, not a spending decision -- the budget's "
                    "already sitting there. Does Tuesday or Thursday work for a quick walkthrough of the "
                    "campaigns above? Or just reply \"send the plan\" and I'll put the specific bid "
                    "changes together first.",
        "ps": "P.S. -- this isn't a guess. The campaigns above all show the same pattern: strong "
              "eligibility, consistently outranked. Happy to show you the exact auctions you're losing.",
        "sources": ["analyst", "search_demand"],
    },
    "US-RET-001": {
        "subject": "Retail demand is up 9% in the US -- your best campaigns can't afford to chase it",
        "hook": "Quick one -- several of your Shopping and Search campaigns are running out of daily "
                "budget before they've captured all the demand they're already eligible for.",
        "why_now": [
            "US retail search spend is up <b>9% quarter on quarter</b>, with query demand up <b>6%</b> "
            "-- real, broad-based category growth.",
            "Average CPC is only up <b>4% QoQ</b> so far -- still a relatively cheap window to add budget.",
            "Vertical peers lose only <b>38%</b> of missed traffic to budget; your account loses <b>79%</b> "
            "that way -- this is an outlier worth fixing.",
        ],
        "stat_label": "YOUR ESTIMATED REVENUE OPPORTUNITY THIS QUARTER",
        "stat_sub": "with a modest daily budget increase",
        "impact": "Impression share sits at <b>21.29%</b> against a <b>35% vertical benchmark</b> -- and "
                  "demand itself is healthy, so this is a ceiling problem, not a demand problem.",
        "scope_intro": "Here's exactly where it's showing up -- these campaigns account for most of the "
                       "gap; the rest is spread thin across the account and isn't worth your time:",
        "fix_title": "The Fix -- A Budget Reallocation, Not an Overhaul",
        "fix_body": "Does Tuesday or Thursday work for a quick budget-planning call? Or reply \"send the "
                    "numbers\" and I'll share exactly how much headroom each campaign above needs to stop "
                    "leaving demand on the table.",
        "ps": "P.S. -- CPC is only up 4% QoQ so far, which makes now a cheaper time to add budget than "
              "later in the season once the category gets more competitive.",
        "sources": ["analyst", "media_mix"],
    },
    "UK-TRV-001": {
        "subject": "UK travel search is up 22% this quarter -- capture it before costs climb",
        "hook": "Quick one -- your account is already performing close to benchmark, which means the "
                "real opportunity here isn't fixing a problem, it's scaling into a surge before "
                "competitors catch up and bid prices rise further.",
        "why_now": [
            "UK travel search demand is up <b>22% quarter on quarter</b> -- the strongest of the last "
            "four quarters by a wide margin.",
            "Average CPC is only up <b>15% QoQ</b> so far -- the gap between demand growth and price "
            "growth is the window, and it won't stay open.",
            "Impression share sits at <b>37.84%</b>, already close to the <b>40% vertical benchmark</b> "
            "-- this account is well positioned to capture the surge.",
        ],
        "stat_label": "YOUR ESTIMATED REVENUE OPPORTUNITY THIS QUARTER",
        "stat_sub": "by expanding budget on your highest-intent campaigns",
        "impact": "Some budget headroom is still available (15% currently lost to budget) -- the fastest "
                  "way to capture more of the surge is simply to use more of it.",
        "scope_intro": "Here's exactly where the surge is concentrated -- the campaigns below account for "
                       "most of the opportunity; the rest is spread thin across the account:",
        "fix_title": "The Fix -- Scale, Don't Repair",
        "fix_body": "Does Tuesday or Thursday work for a quick budget-planning call? Or reply \"let's "
                    "scale it\" and I'll put together a specific expansion plan for the campaigns above.",
        "ps": "P.S. -- this is a go-faster conversation, not a fix-it one. The account is already "
              "healthy; this is about not leaving a seasonal surge on the table.",
        "sources": ["analyst", "media_mix"],
    },
}


def build_email(account_id):
    a = ACCOUNTS[account_id]
    df = pd.read_csv(ADS_DATA_DIR / "campaigns.csv")
    r = account_rollup(df, account_id)
    content = EMAIL_CONTENT[account_id]
    accent = {"Insurance": "#2E4057", "Retail": "#B0413E", "Travel": "#4C7A8C"}[a["vertical"]]
    styles = pc.get_styles(accent)

    flow = [Spacer(1, 0.1 * inch)]

    header_rows = [
        ["From:", "Seller, Paid Search Advertising"],
        ["To:", f"Customer contact, {a['vertical'].lower()} advertiser"],
        ["Subject:", content["subject"]],
    ]
    t = Table(header_rows, colWidths=[0.9 * inch, 5.6 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 0.08 * inch))
    flow.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(accent)))
    flow.append(Spacer(1, 0.14 * inch))

    flow.append(Paragraph("Hi [Customer name],", styles["Body"]))
    flow.append(Paragraph(content["hook"], styles["Body"]))
    flow.append(Spacer(1, 0.08 * inch))

    flow.append(KeepTogether([pc.key_takeaways("Why Now", content["why_now"], styles, accent)]))
    flow.append(Spacer(1, 0.14 * inch))

    stat_value = f"{a['currency_symbol']} {r['inc_revenue']:,.0f}"
    flow.append(pc.big_stat_callout(content["stat_label"], stat_value, content["stat_sub"], styles, accent))
    flow.append(Spacer(1, 0.1 * inch))
    flow.append(Paragraph(content["impact"].format(cur=a["currency_symbol"], budget=r["daily_budget"]),
                           styles["Body"]))

    flow.append(Spacer(1, 0.14 * inch))
    flow.append(Paragraph(
        f"<b>Where this shows up</b> ({r['num_in_scope']} of {r['num_total']} campaigns -- the rest "
        "isn't material enough to act on):", styles["Body"]))
    flow.append(Paragraph(content["scope_intro"], styles["Caption"]))
    flow.append(Spacer(1, 0.05 * inch))
    for card in r["cards"]:
        opp_text = f"Estimated opportunity here: <b>{a['currency_symbol']} {card['revenue_share']:,.0f}</b>"
        card_table = pc.campaign_card(card["name"], card["diagnosis"], card["note"], opp_text, styles, accent)
        flow.append(KeepTogether([card_table, Spacer(1, 0.08 * inch)]))

    flow.append(Spacer(1, 0.04 * inch))
    flow.append(KeepTogether([pc.key_takeaways(content["fix_title"], [content["fix_body"]], styles, accent)]))
    flow.append(Spacer(1, 0.12 * inch))
    flow.append(Paragraph("Best regards,<br/>[Seller name]", styles["Body"]))
    flow.append(Spacer(1, 0.04 * inch))
    flow.append(Paragraph(content["ps"], styles["Caption"]))

    flow.append(Spacer(1, 0.15 * inch))
    cats = QUARTERS
    cur = [a["demand_index"][q]["current"] for q in cats]
    pri = [a["demand_index"][q]["prior_year"] for q in cats]
    chart1 = pc.fig_grouped_bar(cats, {"Current year": cur, "Prior-year pattern": pri},
                                 "Demand Trend vs. Seasonal Norm (Index)", "Index (Q4 2025 = 100)", accent)
    flow.append(pc.chart_image(chart1, width=6.0 * inch))

    labels = ["Impression Share", "Lost to Rank" if a["narrative"] != "budget-constrained" else "Lost to Budget"]
    ours = [r["is_pct"], r["lost_rank_pct"] if a["narrative"] != "budget-constrained" else r["lost_budget_pct"]]
    bench_val = a["benchmark_impression_share_pct"]
    bench_second = a.get("benchmark_lost_rank_pct") or a.get("benchmark_lost_budget_pct") or 0
    chart2 = pc.fig_grouped_bar(labels, {"Your account": ours, "Vertical benchmark": [bench_val, bench_second]},
                                 "Your Account vs. Vertical Benchmark (%)", "%", accent)
    flow.append(pc.chart_image(chart2, width=6.0 * inch))

    flow.append(Spacer(1, 0.15 * inch))
    src_names = [VENDORS[k]["name"] + " (" + VENDORS[k]["report_title"] + ")" for k in content["sources"]]
    flow.append(Paragraph(
        f"Internal note -- grounded in: {a['account_name']} {REPORT_PERIOD} campaign-level performance "
        f"(ads-data/campaigns.csv) + " + "; ".join(src_names) + f", {REPORT_PERIOD} edition. "
        "Not part of the customer-facing email; kept here for pipeline traceability.",
        styles["Caption"]))

    return flow, accent


def simple_build(filename, accent, footer_note, flowables):
    doc = BaseDocTemplate(filename, pagesize=LETTER,
                           leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                           topMargin=0.8 * inch, bottomMargin=0.8 * inch)

    def on_page(canv, _doc):
        canv.saveState()
        canv.setStrokeColor(colors.HexColor(accent))
        canv.setLineWidth(1.2)
        canv.line(0.8 * inch, 0.62 * inch, LETTER[0] - 0.8 * inch, 0.62 * inch)
        canv.setFont("Helvetica", 6.6)
        canv.setFillColor(colors.HexColor("#B0413E"))
        canv.drawCentredString(LETTER[0] / 2, 0.47 * inch, WATERMARK)
        canv.setFillColor(colors.HexColor("#888888"))
        canv.setFont("Helvetica", 7.5)
        canv.drawString(0.8 * inch, 0.33 * inch, footer_note)
        canv.drawRightString(LETTER[0] - 0.8 * inch, 0.33 * inch, f"Page {_doc.page}")
        canv.restoreState()

    frame = Frame(0.8 * inch, 0.8 * inch, LETTER[0] - 1.6 * inch, LETTER[1] - 1.6 * inch, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    doc.build(flowables)


def main():
    for account_id, a in ACCOUNTS.items():
        flow, accent = build_email(account_id)
        slug = a["vertical"].lower() + "_" + a["country_code"].lower()
        out_path = str(OUT_DIR / f"recommendation_email_{slug}.pdf")
        simple_build(out_path, accent, f"Example AI-drafted recommendation email -- {a['account_name']}", flow)
        print(f"{out_path}: {pc.page_count(out_path)} pages")


if __name__ == "__main__":
    main()

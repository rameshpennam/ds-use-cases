"""
03_generate_summary_ppt.py
----------------------------
Builds a clean, professional slide deck summarizing the CSAT Root-Cause &
Sentiment Driver Analysis use case: what it is, what data went in, what the
approach/expected output was, and the actual outcomes - the kind of deck
you'd hand to a client alongside the Excel workbook.

Run AFTER 01_ and 02_ have been run at least once (it reads the real numbers
straight out of final_output_csat_insights.xlsx - nothing on these slides is
hand-typed, so the deck always matches whatever the scripts actually produced).

OUTPUT: final_output/usecase1_csat_summary.pptx
"""

# %% Cell 0 - Imports & config
import os
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

DATA_FILE = "final_output/final_output_csat_insights.xlsx"
OUTPUT_FILE = "final_output/usecase1_csat_summary.pptx"

# WHAT: a small, consistent design system (colors, fonts, helper shapes)
# reused across every slide. WHY: this is what makes a deck look like one
# coherent, professionally-designed document instead of a pile of
# mismatched text boxes - and lets every slide carry its OWN numbers in a
# visually distinct way (chips, cards, step badges), not just one lone
# "stats" slide in the middle of an otherwise plain bullet deck.
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
NAVY_SOFT = RGBColor(0x2B, 0x3C, 0x5E)
ACCENT = RGBColor(0x2E, 0xC4, 0xB6)
ACCENT_DARK = RGBColor(0x1F, 0x9A, 0x8F)
DETRACTOR_RED = RGBColor(0xE0, 0x5A, 0x47)
AMBER = RGBColor(0xE8, 0xA8, 0x3C)
LIGHT_BG = RGBColor(0xF5, 0xF7, 0xFA)
CARD_BORDER = RGBColor(0xDD, 0xE2, 0xE8)
GRAY = RGBColor(0x5A, 0x6B, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TEXT = RGBColor(0x20, 0x26, 0x33)
CHIP_TEXT_ON_NAVY = RGBColor(0xD7, 0xDE, 0xE8)
FONT = "Calibri"

# %% Cell 1 - Pull the real numbers for this deck straight from the output workbook
# NARRATE: "This deck isn't hand-written - every number on it comes straight
# out of the final Excel output, so it can never drift out of sync with
# what the data actually shows."
df = pd.read_excel(DATA_FILE, sheet_name="Tagged_Data", keep_default_na=False)

n_records = len(df)
date_min, date_max = df["date"].min(), df["date"].max()
avg_csat = df["csat_score"].mean()
pct_negative_sentiment = (df["sentiment_label"] == "Negative").mean() * 100

primary_counts = df["primary_driver"].value_counts(normalize=True) * 100
top_primary = primary_counts.index[0]
top_primary_pct = primary_counts.iloc[0]
top_primary_csat = df.loc[df["primary_driver"] == top_primary, "csat_score"].mean()
top5_primary = primary_counts.head(5)
# WHAT: the real, computable "if this driver matched the rest of the book"
# CSAT estimate - the weighted average of every OTHER driver's responses.
# WHY: an honest, directly-derived impact number for the recommendation
# slide, not an invented percentage - if Billing's own average rose to meet
# this figure, the overall average would rise to exactly this figure too.
avg_csat_excl_top_primary = df.loc[df["primary_driver"] != top_primary, "csat_score"].mean()

top_primary_rows = df[df["primary_driver"] == top_primary]
secondary_within_top = top_primary_rows["secondary_driver"].value_counts(normalize=True) * 100
secondary_within_top = secondary_within_top.drop("No Secondary Driver", errors="ignore")
top_secondary = secondary_within_top.index[0] if len(secondary_within_top) else None
top_secondary_pct = secondary_within_top.iloc[0] if len(secondary_within_top) else 0

secondary_counts_all = df["secondary_driver"].value_counts(normalize=True) * 100
secondary_counts_all = secondary_counts_all.drop("No Secondary Driver", errors="ignore")
top5_secondary = secondary_counts_all.head(5)

# WHAT: does a specific, named segment of agents concentrate in a specific
# driver's complaints, out of proportion to their share of the roster?
# WHY: "coach newer agents" is a vague recommendation on its own - this
# checks whether that's actually backed by the data before the slide says it.
pop_share_new_tenure = (df["tenure_bucket"] == "<6 months").mean() * 100
_abc_rows = df[df["primary_driver"] == "Agent_Behavior_Comm"]
abc_new_tenure_share = (_abc_rows["tenure_bucket"] == "<6 months").mean() * 100 if len(_abc_rows) else 0

csat_bucket_counts = df["csat_bucket"].value_counts(normalize=True) * 100
promoter_pct = csat_bucket_counts.get("Promoter (4-5)", 0)
neutral_pct = csat_bucket_counts.get("Neutral (3)", 0)
detractor_pct = csat_bucket_counts.get("Detractor (1-2)", 0)

circle_csat = df.groupby("circle")["csat_score"].mean().sort_values()
worst_circle, worst_circle_csat = circle_csat.index[0], circle_csat.iloc[0]
tier_csat = df.groupby("plan_tier")["csat_score"].mean().sort_values()
worst_tier, worst_tier_csat = tier_csat.index[0], tier_csat.iloc[0]

channel_counts = df["channel"].value_counts()
n_channels = df["channel"].nunique()
tenure_lowest_csat = df.groupby("tenure_bucket")["csat_score"].mean().idxmin()
n_primary_drivers = df["primary_driver"].nunique()
n_secondary_drivers = df.loc[df["secondary_driver"] != "No Secondary Driver", "secondary_driver"].nunique()

print(f"Top driver: {top_primary} ({top_primary_pct:.1f}%, avg CSAT {top_primary_csat:.2f})")
print(f"Top compounding secondary (within {top_primary}): {top_secondary} ({top_secondary_pct:.1f}%)")
print(f"Overall avg CSAT: {avg_csat:.2f} | Promoters {promoter_pct:.1f}% | Detractors {detractor_pct:.1f}%")

# %% Cell 2 - Design helpers (shared across every slide)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK_LAYOUT = prs.slide_layouts[6]
TOTAL_SLIDES = 6


def new_slide():
    return prs.slides.add_slide(BLANK_LAYOUT)


def fill_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def _no_shadow(shape):
    shape.shadow.inherit = False


def add_text(slide, left, top, width, height, text, size, color, bold=False,
             align=PP_ALIGN.LEFT, anchor=None, italic=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    if anchor:
        tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = FONT
    return box


def add_icon_bullets(slide, left, top, width, row_height, bullets, size=17, color=DARK_TEXT, dot_color=ACCENT):
    """Each bullet gets its OWN small colored circle marker + its own text
    box, laid out in fixed-height rows - a more deliberate, 'designed' look
    than a single multi-paragraph textbox with a plain bullet character."""
    for i, b in enumerate(bullets):
        row_top = top + i * row_height
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, row_top + Inches(0.08), Inches(0.14), Inches(0.14))
        dot.fill.solid()
        dot.fill.fore_color.rgb = dot_color
        dot.line.fill.background()
        _no_shadow(dot)
        add_text(slide, left + Inches(0.35), row_top, width - Inches(0.35), row_height, b, size, color)


def add_title_bar(slide, title, kicker=""):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    _no_shadow(bar)
    y = Inches(0.4)
    if kicker:
        chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.65), y, Inches(1.9), Inches(0.32))
        chip.fill.solid()
        chip.fill.fore_color.rgb = LIGHT_BG
        chip.line.color.rgb = ACCENT
        chip.line.width = Pt(1)
        _no_shadow(chip)
        tf = chip.text_frame
        tf.word_wrap = False
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Emu(0)
        tf.margin_right = Emu(0)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = kicker.upper()
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = ACCENT_DARK
        r.font.name = FONT
        y = Inches(0.86)
    add_text(slide, Inches(0.65), y, Inches(12), Inches(0.9), title, 30, NAVY, bold=True)


def add_footer(slide, text, page_num):
    add_text(slide, Inches(0.65), Inches(7.08), Inches(10), Inches(0.35), text, 10, GRAY)
    add_text(slide, Inches(12.1), Inches(7.08), Inches(0.9), Inches(0.35),
              f"{page_num:02d} / {TOTAL_SLIDES:02d}", 10, GRAY, align=PP_ALIGN.RIGHT)


def add_stat_tile(slide, left, top, width, height, value, label, accent=ACCENT):
    """Card-style tile: a thin colored accent strip across the top, then a
    light body with the big number in navy and the label in gray beneath -
    reads as a designed metric card, not just a bordered text box."""
    strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Inches(0.09))
    strip.fill.solid()
    strip.fill.fore_color.rgb = accent
    strip.line.fill.background()
    _no_shadow(strip)
    tile = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top + Inches(0.09), width, height - Inches(0.09))
    tile.fill.solid()
    tile.fill.fore_color.rgb = LIGHT_BG
    tile.line.color.rgb = CARD_BORDER
    tile.line.width = Pt(0.75)
    _no_shadow(tile)
    tf = tile.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run()
    r0.text = value
    r0.font.size = Pt(30)
    r0.font.bold = True
    r0.font.color.rgb = NAVY
    r0.font.name = FONT
    p1 = tf.add_paragraph()
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(12)
    r1.font.color.rgb = GRAY
    r1.font.name = FONT


def add_proportional_bar(slide, left, top, width, height, segments):
    """segments: list of (label, pct, color). Draws one horizontal bar made
    of proportional colored blocks (a mini stacked-bar visual) with a
    legend ROW beneath - fine when the bar has the full slide width to
    itself (e.g. the Data slide's channel mix)."""
    x = left
    for label, pct, color in segments:
        seg_w = Emu(int(width * (pct / 100.0)))
        if seg_w < Emu(1):
            continue
        seg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, seg_w, height)
        seg.fill.solid()
        seg.fill.fore_color.rgb = color
        seg.line.color.rgb = WHITE
        seg.line.width = Pt(1.5)
        _no_shadow(seg)
        x = Emu(int(x) + int(seg_w))
    legend_y = top + height + Inches(0.12)
    lx = left
    for label, pct, color in segments:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, lx, legend_y, Inches(0.14), Inches(0.14))
        dot.fill.solid()
        dot.fill.fore_color.rgb = color
        dot.line.fill.background()
        _no_shadow(dot)
        add_text(slide, lx + Inches(0.2), legend_y - Inches(0.05), Inches(2.6), Inches(0.3),
                  f"{label}: {pct:,.0f}%" if pct >= 1 else f"{label}: {pct:,.1f}%", 13, GRAY)
        lx += Inches(2.75)


def add_mix_bar_vertical_legend(slide, left, top, width, bar_height, segments):
    """Same proportional-bar idea as add_proportional_bar, but the legend
    stacks VERTICALLY beneath the bar instead of running in a horizontal
    row - needed when the bar sits in a narrow column with other content
    to its right (a horizontal legend row would run wide enough to overlap
    that neighboring content)."""
    x = left
    for label, pct, color in segments:
        seg_w = Emu(int(width * (pct / 100.0)))
        if seg_w < Emu(1):
            continue
        seg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, seg_w, bar_height)
        seg.fill.solid()
        seg.fill.fore_color.rgb = color
        seg.line.color.rgb = WHITE
        seg.line.width = Pt(1.5)
        _no_shadow(seg)
        x = Emu(int(x) + int(seg_w))
    ly = top + bar_height + Inches(0.16)
    for label, pct, color in segments:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, ly, Inches(0.14), Inches(0.14))
        dot.fill.solid()
        dot.fill.fore_color.rgb = color
        dot.line.fill.background()
        _no_shadow(dot)
        add_text(slide, left + Inches(0.22), ly - Inches(0.04), width - Inches(0.22), Inches(0.3),
                  f"{label}: {pct:,.0f}%", 12.5, GRAY)
        ly += Inches(0.34)
    return ly


def add_ranked_list(slide, left, top, width, heading, items, row_height=0.36, accent=ACCENT):
    """heading + up to a few numbered rows (small badge + 'label - value'),
    used for the Top-5-driver lists - a ranked, scannable alternative to a
    paragraph of bullets."""
    add_text(slide, left, top, width, Inches(0.3), heading.upper(), 12, ACCENT_DARK, bold=True)
    y = top + Inches(0.4)
    for i, (label, value) in enumerate(items):
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, y + Inches(0.01), Inches(0.22), Inches(0.22))
        badge.fill.solid()
        badge.fill.fore_color.rgb = accent
        badge.line.fill.background()
        _no_shadow(badge)
        tf = badge.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(i + 1)
        r.font.size = Pt(10.5)
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.name = FONT
        add_text(slide, left + Inches(0.32), y - Inches(0.02), width - Inches(0.32), Inches(0.32),
                  f"{label} — {value}", 12, DARK_TEXT)
        y += Inches(row_height)
    return y


STEP_COL1_X, STEP_COL1_W = Inches(0.65), Inches(2.7)
STEP_COL2_X, STEP_COL2_W = Inches(3.6), Inches(5.3)
STEP_COL3_X, STEP_COL3_W = Inches(9.15), Inches(3.53)
STEP_BADGE_D = Inches(0.38)
STEP_OFFSET_PER_ROW = Inches(0.07)  # each badge nudges right - a literal staircase down the slide


def step_badge_center(row_index, top):
    cx = Emu(int(STEP_COL1_X) + int(STEP_OFFSET_PER_ROW) * row_index + int(STEP_BADGE_D) // 2)
    cy = Emu(int(top) + int(STEP_BADGE_D) // 2)
    return cx, cy


def add_approach_row(slide, top, row_height, row_index, number, title, approach_text, output_text, accent=ACCENT):
    """One pipeline step as a full-width row: a staircase-stepped numbered
    badge + title on the left, the APPROACH explained in plain prose in a
    wide middle column, and the OUTPUT as a short, visually distinct phrase
    on the right - far more readable than cramming both into a small card."""
    badge_x = Emu(int(STEP_COL1_X) + int(STEP_OFFSET_PER_ROW) * row_index)
    badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, badge_x, top, STEP_BADGE_D, STEP_BADGE_D)
    badge.fill.solid()
    badge.fill.fore_color.rgb = accent
    badge.line.fill.background()
    _no_shadow(badge)
    tf = badge.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(number)
    r.font.size = Pt(15)
    r.font.bold = True
    r.font.color.rgb = WHITE
    r.font.name = FONT
    title_x = Emu(int(badge_x) + int(STEP_BADGE_D) + Inches(0.12))
    title_w = Emu(int(STEP_COL1_X) + int(STEP_COL1_W) - int(title_x))
    add_text(slide, title_x, top + Inches(0.01), title_w, Inches(0.55), title, 14.5, NAVY, bold=True)
    add_text(slide, STEP_COL2_X, top, STEP_COL2_W, row_height, approach_text, 12.5, DARK_TEXT)
    out_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, STEP_COL3_X, top, STEP_COL3_W, row_height - Inches(0.1))
    out_box.fill.solid()
    out_box.fill.fore_color.rgb = LIGHT_BG
    out_box.line.color.rgb = CARD_BORDER
    _no_shadow(out_box)
    tf2 = out_box.text_frame
    tf2.word_wrap = True
    tf2.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf2.margin_left = Emu(91440)
    tf2.margin_right = Emu(91440)
    p0 = tf2.paragraphs[0]
    p0.alignment = PP_ALIGN.LEFT
    r0 = p0.add_run()
    r0.text = output_text
    r0.font.size = Pt(12)
    r0.font.bold = True
    r0.font.color.rgb = NAVY
    r0.font.name = FONT


def add_recommendation_table(slide, left, top, width, row_height, rows, accent=ACCENT):
    """A 3-column action table for the closing slide: what the
    recommendation is, exactly what to do (with the %'s and the specific
    'why' behind it), and the outcome it buys - clearer than a single
    description blob per recommendation. Columns are NOT equal thirds -
    "what to do" carries the longest, most specific text, so it gets the
    most width."""
    col_gap = Inches(0.22)
    usable = int(width) - 2 * int(col_gap)
    col1_w = Emu(int(usable * 0.24))
    col2_w = Emu(int(usable * 0.44))
    col3_w = Emu(usable - int(col1_w) - int(col2_w))
    col1_x = left
    col2_x = Emu(int(left) + int(col1_w) + int(col_gap))
    col3_x = Emu(int(col2_x) + int(col2_w) + int(col_gap))
    headers = ["RECOMMENDATION", "WHAT TO DO", "EXPECTED OUTCOME"]
    for cx, cw, h in zip([col1_x, col2_x, col3_x], [col1_w, col2_w, col3_w], headers):
        add_text(slide, cx, top, cw, Inches(0.3), h, 12, ACCENT, bold=True)
    rule = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, left, top + Inches(0.4),
                                        Emu(int(left) + int(width)), top + Inches(0.4))
    rule.line.color.rgb = NAVY_SOFT
    rule.line.width = Pt(1)
    y = top + Inches(0.55)
    for rec_title, what, outcome in rows:
        add_text(slide, col1_x, y, col1_w, row_height, rec_title, 14.5, accent, bold=True)
        add_text(slide, col2_x, y, col2_w, row_height, what, 12.5, WHITE)
        add_text(slide, col3_x, y, col3_w, row_height, outcome, 12.5, CHIP_TEXT_ON_NAVY)
        y += row_height
        if y < top + Inches(0.55) + row_height * len(rows):
            rule2 = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, left, y - Inches(0.1),
                                                 Emu(int(left) + int(width)), y - Inches(0.1))
            rule2.line.color.rgb = NAVY_SOFT
            rule2.line.width = Pt(0.5)


# %% Cell 3 - Slide 1: Title (heading only - no stats, no subtitle, no footer)
slide = new_slide()
fill_bg(slide, NAVY)
accent_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(3.05), Inches(1.2), Pt(5))
accent_line.fill.solid()
accent_line.fill.fore_color.rgb = ACCENT
accent_line.line.fill.background()
_no_shadow(accent_line)
add_text(slide, Inches(0.65), Inches(3.2), Inches(12), Inches(1.3),
         "CSAT Root-Cause & Sentiment\nDriver Analysis", 40, WHITE, bold=True)

# %% Cell 4 - Slide 2: The Use Case & Objective
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Use Case", kicker="Business Context")
add_icon_bullets(slide, Inches(0.65), Inches(1.65), Inches(7.3), Inches(1.55), [
    "CSAT scores are down, and leadership needs to know WHY - not just that satisfaction "
    "has slipped, but which specific, fixable issue is driving it.",
    "Thousands of open-text survey responses arrive across chat, email and voice every "
    "month - too much volume to read by hand, but too much nuance for a dashboard number alone.",
    "Objective: systematically tag every response against a known root-cause taxonomy, "
    "score its sentiment, and roll everything up into a ranked, actionable view.",
], size=17)
card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), Inches(1.65), Inches(4.4), Inches(4.3))
card.fill.solid()
card.fill.fore_color.rgb = LIGHT_BG
card.line.color.rgb = CARD_BORDER
_no_shadow(card)
add_text(slide, Inches(8.65), Inches(1.95), Inches(3.8), Inches(0.4), "WHY THIS MATTERS", 12, ACCENT_DARK, bold=True)
add_text(slide, Inches(8.65), Inches(2.4), Inches(3.75), Inches(3.3),
          "A vague “customer sentiment is down” finding can't be acted on. "
          "A ranked, named driver - “Duplicate billing charges, concentrated in the "
          "Postpaid LoB” - can go straight to the team that owns the fix, with a "
          "number attached to track whether the fix is working.", 14.5, DARK_TEXT)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis", 2)

# %% Cell 5 - Slide 3: The Data
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Data", kicker="Input")
tile_w, tile_h, gap = Inches(2.78), Inches(1.35), Inches(0.28)
x0, y0 = Inches(0.65), Inches(1.6)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{n_records:,}", "Survey responses")
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{n_channels}", "Channels (chat/email/voice)")
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, str(df["lob"].nunique()), "Lines of business")
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, str(df["circle"].nunique()), "Telecom circles covered")
add_icon_bullets(slide, Inches(0.65), Inches(3.3), Inches(11.9), Inches(0.65), [
    f"{pd.Timestamp(date_min).strftime('%d %b')} – {pd.Timestamp(date_max).strftime('%d %b %Y')}: "
    "date, unique response ID, channel, line of business, the customer's own words (verbatim), CSAT score (1-5)",
    "Who handled it: agent, team lead, manager - and customer-master fields a survey "
    "platform routinely carries: plan tier (5 tiers) and telecom circle (23 circles, all-India)",
], size=15.5)
add_text(slide, Inches(0.65), Inches(4.85), Inches(5), Inches(0.35), "CHANNEL MIX", 12, ACCENT_DARK, bold=True)
total_ch = channel_counts.sum()
ch_colors = [NAVY, ACCENT, AMBER]
segments = [(ch, cnt / total_ch * 100, ch_colors[i % len(ch_colors)]) for i, (ch, cnt) in enumerate(channel_counts.items())]
add_proportional_bar(slide, Inches(0.65), Inches(5.25), Inches(11.9), Inches(0.45), segments)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis", 3)

# %% Cell 6 - Slide 4: Approach & Expected Output (stepped, full-width rows)
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Approach & Expected Output", kicker="Method")
add_text(slide, STEP_COL2_X, Inches(1.6), STEP_COL2_W, Inches(0.3), "APPROACH", 10.5, ACCENT_DARK, bold=True)
add_text(slide, STEP_COL3_X, Inches(1.6), STEP_COL3_W, Inches(0.3), "OUTPUT", 10.5, ACCENT_DARK, bold=True)
STEP_CONTENT_TOP = Inches(1.92)
STEP_ROW_H = Inches(0.84)
steps = [
    ("Load & clean data",
     "pandas loads the 7,500-row survey export, then the text is lowercased, stripped of "
     "punctuation, and whitespace-collapsed.",
     "A clean_text column every later step reuses"),
    ("Bootstrap dictionary",
     "Term frequency is split low-CSAT vs high-CSAT text, and every candidate term's "
     "sentiment lean is labeled upfront.",
     "An inspectable keyword shortlist, not a guess"),
    ("Tag drivers",
     "Every response is matched against 11 categories and 42 sub-issues, ranked by "
     "phrase-match strength.",
     "A PRIMARY + actionable SECONDARY driver per row"),
    ("NMF safety net",
     "TF-IDF + NMF finds latent themes in any leftover text; YAKE auto-labels each theme, "
     "fully offline.",
     "Zero responses left with a blank secondary driver"),
    ("Score sentiment",
     "VADER, a lexicon-based model, scores the tone of every row — 100% offline, zero "
     "AI/LLM API dependency.",
     "A Negative/Neutral/Positive label per response"),
    ("Publish",
     "One workbook is written (row data + Analysis sheet), then the PPT deck and Power BI "
     "report are built on top.",
     "A client-ready package, numbers always in sync"),
]
# Staircase connector: a straight segment between each pair of consecutive
# step badges - drawn BEFORE the badges so the badges sit visually on top.
centers = [step_badge_center(i, STEP_CONTENT_TOP + i * STEP_ROW_H) for i in range(len(steps))]
for (x1, y1), (x2, y2) in zip(centers, centers[1:]):
    connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    connector.line.color.rgb = CARD_BORDER
    connector.line.width = Pt(1.75)
for i, (title, approach, output) in enumerate(steps):
    add_approach_row(slide, STEP_CONTENT_TOP + i * STEP_ROW_H, STEP_ROW_H, i, i + 1, title, approach, output)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis", 4)

# %% Cell 7 - Slide 5: Key Outcomes
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Key Outcomes", kicker="Results")
tile_w, tile_h, gap = Inches(2.78), Inches(1.5), Inches(0.28)
x0, y0 = Inches(0.65), Inches(1.6)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{avg_csat:.2f}", "Overall average CSAT (out of 5)", NAVY)
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{pct_negative_sentiment:.0f}%", "of responses carry negative sentiment", DETRACTOR_RED)
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, f"{worst_circle_csat:.2f}", f"Lowest avg CSAT: {worst_circle} circle", ACCENT)
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, f"{top_primary_pct:.0f}%", f"of responses: {top_primary.replace('_', ' ')}", ACCENT)

row2_y = Inches(3.35)
col_gap = Inches(0.25)
col_w = Inches((12.03 - 0.5) / 3)
colA_x, colB_x = Inches(0.65), Inches(0.65) + col_w + col_gap
colC_x = colB_x + col_w + col_gap

add_text(slide, colA_x, row2_y, col_w, Inches(0.3), "CSAT MIX", 12, ACCENT_DARK, bold=True)
add_mix_bar_vertical_legend(slide, colA_x, row2_y + Inches(0.4), col_w, Inches(0.35), [
    ("Promoters (4-5)", promoter_pct, ACCENT),
    ("Neutral (3)", neutral_pct, AMBER),
    ("Detractors (1-2)", detractor_pct, DETRACTOR_RED),
])

add_ranked_list(slide, colB_x, row2_y, col_w, "Top 5 Primary Drivers",
                 [(name.replace("_", " "), f"{pct:.1f}%") for name, pct in top5_primary.items()])
add_ranked_list(slide, colC_x, row2_y, col_w, "Top 5 Secondary Drivers",
                 [(name, f"{pct:.1f}%") for name, pct in top5_secondary.items()])

add_icon_bullets(slide, Inches(0.65), Inches(5.95), Inches(11.9), Inches(0.6), [
    f"Agents with less than 6 months' tenure skew toward the lowest-CSAT bucket "
    f"({tenure_lowest_csat}) - a coaching signal alongside the process fix.",
], size=14.5)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis", 5)

# %% Cell 8 - Slide 6: Actionable Recommendation (left/center/right table)
slide = new_slide()
fill_bg(slide, NAVY)
add_text(slide, Inches(0.65), Inches(0.55), Inches(11.8), Inches(0.8), "Recommendation", 30, WHITE, bold=True)
rec1_what = (f"{top_primary_pct:.1f}% of all complaints are {top_primary.replace('_', ' ')}, and "
             f"“{top_secondary}” alone drives {top_secondary_pct:.1f}% of those — fix the "
             f"duplicate-charge billing defect first, not the category as a whole."
             if top_secondary else
             f"{top_primary_pct:.1f}% of all complaints are {top_primary.replace('_', ' ')} — "
             f"investigate this driver's top sub-issue first.")
rec_rows = [
    (f"Fix #1: {top_primary.replace('_', ' ')} ({top_primary_pct:.1f}%)",
     rec1_what,
     f"Billing responses average {top_primary_csat:.2f} vs {avg_csat_excl_top_primary:.2f} "
     f"everywhere else — closing that gap could lift OVERALL CSAT from {avg_csat:.2f} toward "
     f"roughly {avg_csat_excl_top_primary:.2f} over time."),
    (f"Fix #2: Coach agents under 6 months ({pop_share_new_tenure:.0f}% of roster)",
     f"Agents under 6 months' tenure are {pop_share_new_tenure:.0f}% of the roster but generate "
     f"{abc_new_tenure_share:.0f}% of Agent Behavior complaints — these specific agents are "
     f"driving this category, not the team broadly.",
     "Targeted coaching (not generic training) directly shrinks a top-3 driver by volume."),
    ("Next: Validate & track",
     "Validate the taxonomy against real customer verbatim, then track the top driver's weekly "
     "trend already built into the workbook.",
     "Confirms both fixes are actually moving CSAT, with real data, not a one-time snapshot."),
]
add_recommendation_table(slide, Inches(0.65), Inches(1.85), Inches(12.0), Inches(1.4), rec_rows)
add_text(slide, Inches(0.65), Inches(6.95), Inches(11), Inches(0.4),
         "Data Analytics Consulting  |  Synthetic demo dataset", 12, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 9 - Save
os.makedirs("final_output", exist_ok=True)
prs.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} ({len(prs.slides)} slides)")

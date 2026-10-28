"""
03_generate_summary_ppt.py
----------------------------
Builds a clean, professional slide deck summarizing the Demand Forecasting &
Staffing use case: what it is, what data went in, what the approach/expected
output was, and the actual outcomes.

Run AFTER 01_ and 02_ have been run at least once (it reads the real numbers
straight out of final_output_forecast_staffing.xlsx and
intermediate_model_accuracy_comparison.xlsx - nothing on these slides is
hand-typed).

OUTPUT: final_output/usecase2_forecast_summary.pptx
"""

# %% Cell 0 - Imports & config
import os
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

FORECAST_FILE = "final_output/final_output_forecast_staffing.xlsx"
MODEL_COMPARISON_FILE = "intermediate/intermediate_model_accuracy_comparison.xlsx"
VOLUME_FILE = "input/input_call_volume_history.xlsx"
OUTPUT_FILE = "final_output/usecase2_forecast_summary.pptx"

# Same design system as the other use case's deck (same component library,
# same colors) - keeps both decks looking like they came from the same
# consulting engagement, and lets every slide carry its own numbers in a
# visually distinct way (chips, cards, step badges), not just bullet text.
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
NAVY_SOFT = RGBColor(0x2B, 0x3C, 0x5E)
ACCENT = RGBColor(0x2E, 0xC4, 0xB6)
ACCENT_DARK = RGBColor(0x1F, 0x9A, 0x8F)
GAP_RED = RGBColor(0xE0, 0x5A, 0x47)
AMBER = RGBColor(0xE8, 0xA8, 0x3C)
LIGHT_BG = RGBColor(0xF5, 0xF7, 0xFA)
CARD_BORDER = RGBColor(0xDD, 0xE2, 0xE8)
GRAY = RGBColor(0x5A, 0x6B, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TEXT = RGBColor(0x20, 0x26, 0x33)
CHIP_TEXT_ON_NAVY = RGBColor(0xD7, 0xDE, 0xE8)
FONT = "Calibri"

# %% Cell 1 - Pull the real numbers for this deck
# NARRATE: "Same discipline as the other deck - every number here comes
# straight from the actual forecast and model-comparison output files."
staffing = pd.read_excel(FORECAST_FILE, sheet_name="Forecast_Staffing", keep_default_na=False)
model_comparison = pd.read_excel(MODEL_COMPARISON_FILE, sheet_name="Model_Comparison")
vol = pd.read_excel(VOLUME_FILE, sheet_name="Call_Volume_History", keep_default_na=False)
vol["date"] = pd.to_datetime(vol["date"])
staffing["date"] = pd.to_datetime(staffing["date"])

n_history_days = (vol["date"].max() - vol["date"].min()).days
n_history_years = n_history_days / 365
horizon_days = len(staffing)
n_channels = vol["channel"].nunique()
n_lobs = vol["lob"].nunique()

baseline_mape = model_comparison.loc[model_comparison["model"].str.contains("Naive"), "holdout_mape_pct"].iloc[0]
hw_mape = model_comparison.loc[model_comparison["model"].str.contains("Holt"), "holdout_mape_pct"].iloc[0]
mape_improvement = baseline_mape - hw_mape

avg_required_fte = staffing["required_fte"].mean()
avg_available_fte = staffing["available_fte"].mean()
days_short = (staffing["staffing_gap_fte"] > 0).sum()
worst_day = staffing.loc[staffing["staffing_gap_fte"].idxmax()]
avg_gap = staffing["staffing_gap_fte"].mean()

top3_worst_days = staffing.nlargest(3, "staffing_gap_fte")[["date", "staffing_gap_fte"]]

weekly_gap = (
    staffing.assign(week=staffing["date"].dt.to_period("W").dt.start_time)
    .groupby("week")["staffing_gap_fte"].mean().round(1).head(3)
)

lob_split = vol.groupby("lob")["volume"].sum()
lob_split_pct = (lob_split / lob_split.sum() * 100).round(1)

print(f"History: {n_history_years:.1f} years | Forecast horizon: {horizon_days} days")
print(f"MAPE: baseline {baseline_mape:.1f}% -> Holt-Winters {hw_mape:.1f}% (improved {mape_improvement:.1f}pp)")
print(f"Avg required FTE {avg_required_fte:.1f} vs available {avg_available_fte:.1f}, "
      f"short {days_short}/{horizon_days} days")

# %% Cell 2 - Design helpers (shared component library, same pattern as use case 1)
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
    light body with the big number in navy and the label in gray beneath."""
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
    """Horizontal proportional bar + a legend ROW beneath - fine when the
    bar has the full slide width to itself (e.g. the Data slide's LoB mix)."""
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
        add_text(slide, lx + Inches(0.2), legend_y - Inches(0.05), Inches(2.6), Inches(0.3), f"{label}: {pct:,.0f}%", 13, GRAY)
        lx += Inches(2.75)


def add_mix_bar_vertical_legend(slide, left, top, width, bar_height, segments):
    """Same proportional-bar idea, but the legend stacks VERTICALLY beneath
    the bar instead of a horizontal row - needed in a narrow column next to
    other content, where a wide horizontal legend row would overlap it."""
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


def add_ranked_list(slide, left, top, width, heading, items, row_height=0.42, accent=ACCENT):
    """heading + up to a few numbered rows (small badge + 'label - value') -
    a ranked, scannable alternative to a paragraph of bullets."""
    add_text(slide, left, top, width, Inches(0.3), heading.upper(), 12, ACCENT_DARK, bold=True)
    y = top + Inches(0.4)
    for i, (label, value) in enumerate(items):
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, y + Inches(0.02), Inches(0.26), Inches(0.26))
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
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.name = FONT
        add_text(slide, left + Inches(0.36), y, width - Inches(0.36), Inches(0.36),
                  f"{label} — {value}", 13, DARK_TEXT)
        y += Inches(row_height)
    return y


def add_approach_step(slide, left, top, width, number, title, bullets, accent=ACCENT):
    """One pipeline step: a small numbered badge + bold title on one line,
    then 2-4 supporting bullets beneath - enough detail to actually explain
    HOW that step works, not just name it."""
    badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, Inches(0.32), Inches(0.32))
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
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = WHITE
    r.font.name = FONT
    add_text(slide, left + Inches(0.42), top - Inches(0.02), width - Inches(0.42), Inches(0.32),
              title, 14.5, NAVY, bold=True)
    y = top + Inches(0.4)
    for b in bullets:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, left + Inches(0.08), y + Inches(0.07), Inches(0.09), Inches(0.09))
        dot.fill.solid()
        dot.fill.fore_color.rgb = accent
        dot.line.fill.background()
        _no_shadow(dot)
        add_text(slide, left + Inches(0.3), y, width - Inches(0.3), Inches(0.32), b, 11.5, DARK_TEXT)
        y += Inches(0.34)
    return y


def add_recommendation_table(slide, left, top, width, row_height, rows, accent=ACCENT):
    """A 3-column action table for the closing slide: what the
    recommendation is, exactly what to do, and the outcome it buys."""
    col_gap = Inches(0.25)
    col_w = Emu(int((int(width) - 2 * int(col_gap)) / 3))
    col1_x, col2_x = left, Emu(int(left) + int(col_w) + int(col_gap))
    col3_x = Emu(int(col2_x) + int(col_w) + int(col_gap))
    headers = ["RECOMMENDATION", "WHAT TO DO", "EXPECTED OUTCOME"]
    for cx, h in zip([col1_x, col2_x, col3_x], headers):
        add_text(slide, cx, top, col_w, Inches(0.3), h, 12, ACCENT, bold=True)
    rule = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, left, top + Inches(0.4),
                                        Emu(int(left) + int(width)), top + Inches(0.4))
    rule.line.color.rgb = NAVY_SOFT
    rule.line.width = Pt(1)
    y = top + Inches(0.55)
    for rec_title, what, outcome in rows:
        add_text(slide, col1_x, y, col_w, row_height, rec_title, 15, accent, bold=True)
        add_text(slide, col2_x, y, col_w, row_height, what, 13, WHITE)
        add_text(slide, col3_x, y, col_w, row_height, outcome, 13, CHIP_TEXT_ON_NAVY)
        y += row_height


# %% Cell 3 - Slide 1: Title (heading only - no stats, no subtitle, no footer)
slide = new_slide()
fill_bg(slide, NAVY)
accent_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(3.05), Inches(1.2), Pt(5))
accent_line.fill.solid()
accent_line.fill.fore_color.rgb = ACCENT
accent_line.line.fill.background()
_no_shadow(accent_line)
add_text(slide, Inches(0.65), Inches(3.2), Inches(12), Inches(1.3), "Demand Forecasting & Staffing", 40, WHITE, bold=True)

# %% Cell 4 - Slide 2: The Use Case & Objective
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Use Case", kicker="Business Context")
add_icon_bullets(slide, Inches(0.65), Inches(1.65), Inches(7.3), Inches(1.55), [
    "Both over- and under-staffing are expensive: idle capacity burns cost; a shortfall "
    "shows up directly in service levels and CSAT.",
    "The business question: based on real contact-volume history, how many agents do we "
    "actually need over the next several weeks, and does the current roster cover it?",
    "Objective: build a forecast grounded in the real patterns in the data - trend, "
    "seasonality, holidays, campaigns - validate it honestly, then convert it into a "
    "concrete FTE requirement the business can act on.",
], size=17)
card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), Inches(1.65), Inches(4.4), Inches(4.3))
card.fill.solid()
card.fill.fore_color.rgb = LIGHT_BG
card.line.color.rgb = CARD_BORDER
_no_shadow(card)
add_text(slide, Inches(8.65), Inches(1.95), Inches(3.8), Inches(0.4), "WHY THIS MATTERS", 12, ACCENT_DARK, bold=True)
add_text(slide, Inches(8.65), Inches(2.4), Inches(3.75), Inches(3.3),
          "A forecast that just says “volume is going up” isn't actionable. A staffing "
          "plan that says “you'll be short 3.7 FTE on November 18th” gives the business "
          "weeks of lead time to actually do something about it - overtime, a flexible "
          "shift, or a deliberate decision to accept the risk.", 14.5, DARK_TEXT)
add_footer(slide, "Demand Forecasting & Staffing", 2)

# %% Cell 5 - Slide 3: The Data
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Data", kicker="Input")
tile_w, tile_h, gap = Inches(2.78), Inches(1.35), Inches(0.28)
x0, y0 = Inches(0.65), Inches(1.6)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{n_history_years:.1f} yrs", "Daily contact-volume history")
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, str(n_channels), "Channels")
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, str(n_lobs), "Lines of business")
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, str(staffing["date"].nunique()), "Days forecast forward")
add_icon_bullets(slide, Inches(0.65), Inches(3.3), Inches(11.9), Inches(0.65), [
    "Daily contact volume by line of business and channel, with handle time, holiday "
    "and campaign flags - the real signals that drive the shape of demand",
    "An agent roster: who we have today, their line of business, team lead/manager, "
    "tenure, weekly available hours, and real shrinkage % (not a flat assumption)",
], size=15.5)
add_text(slide, Inches(0.65), Inches(4.85), Inches(5), Inches(0.35), "VOLUME SPLIT BY LINE OF BUSINESS", 12, ACCENT_DARK, bold=True)
lob_colors = [NAVY, ACCENT, AMBER, GAP_RED]
segments = [(lob, pct, lob_colors[i % len(lob_colors)]) for i, (lob, pct) in enumerate(lob_split_pct.items())]
add_proportional_bar(slide, Inches(0.65), Inches(5.25), Inches(11.9), Inches(0.45), segments)
add_footer(slide, "Demand Forecasting & Staffing", 3)

# %% Cell 6 - Slide 4: Approach & Expected Output
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Approach & Expected Output", kicker="Method")
LEFT_COL_X, RIGHT_COL_X = Inches(0.65), Inches(6.75)
COL_W = Inches(5.7)
CONTENT_TOP = Inches(1.55)
STEP_H = Inches(1.76)
add_approach_step(slide, LEFT_COL_X, CONTENT_TOP, COL_W, 1, "Explore first", [
    "Decomposes trend + weekly/yearly seasonality",
    "Checks day-of-week patterns before modeling",
    "Spots holiday/campaign spikes visually first",
    "No model touches the data blind",
])
add_approach_step(slide, LEFT_COL_X, CONTENT_TOP + STEP_H, COL_W, 2, "Benchmark honestly", [
    "Naive seasonal baseline: repeat last week",
    "Every candidate tested on a 60-day holdout",
    "A model only ships if it beats the baseline",
    "Script asserts this — never silently skipped",
])
add_approach_step(slide, LEFT_COL_X, CONTENT_TOP + 2 * STEP_H, COL_W, 3, "Holt-Winters", [
    "Models trend + weekly seasonality explicitly",
    "Lightweight, explainable — not a black box",
    f"Forecasts volume {horizon_days} days forward",
    f"Beat the baseline: {hw_mape:.1f}% vs {baseline_mape:.1f}% MAPE",
])
RIGHT_TOP = CONTENT_TOP + Emu(int((3 * STEP_H - 2 * STEP_H) / 2))
add_approach_step(slide, RIGHT_COL_X, RIGHT_TOP, COL_W, 4, "Volume -> FTE", [
    "Converts volume to agent-hours via handle time",
    "Uses the roster's REAL shrinkage %, not a guess",
    "Compares required FTE to available FTE",
    "Flags the exact day staffing runs short",
])
add_approach_step(slide, RIGHT_COL_X, RIGHT_TOP + STEP_H, COL_W, 5, "Publish", [
    "One workbook: forecast + Analysis sheet",
    "Every chart pairs volume with staffing gap",
    "A 6-slide deck, numbers read live from the data",
    "A Power BI staffing-gap report on top",
])
add_footer(slide, "Demand Forecasting & Staffing", 4)

# %% Cell 7 - Slide 5: Key Outcomes
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Key Outcomes", kicker="Results")
tile_w, tile_h, gap = Inches(2.78), Inches(1.5), Inches(0.28)
x0, y0 = Inches(0.65), Inches(1.6)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{hw_mape:.1f}%", f"Holdout MAPE (vs {baseline_mape:.1f}% baseline)", ACCENT)
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{days_short}/{horizon_days}", "Days short-staffed over the horizon", GAP_RED)
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, f"{avg_required_fte:.0f}", "Avg required FTE over the horizon", NAVY)
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, f"{avg_available_fte:.0f}", "Available FTE (current roster)", NAVY)

row2_y = Inches(3.35)
col_gap = Inches(0.25)
col_w = Inches((12.03 - 0.5) / 3)
colA_x, colB_x = Inches(0.65), Inches(0.65) + col_w + col_gap
colC_x = colB_x + col_w + col_gap

add_text(slide, colA_x, row2_y, col_w, Inches(0.3), "REQUIRED VS AVAILABLE FTE", 12, ACCENT_DARK, bold=True)
avg_total = avg_required_fte + avg_available_fte
add_mix_bar_vertical_legend(slide, colA_x, row2_y + Inches(0.4), col_w, Inches(0.35), [
    ("Required", avg_required_fte / avg_total * 100, GAP_RED),
    ("Available", avg_available_fte / avg_total * 100, ACCENT),
])

add_ranked_list(slide, colB_x, row2_y, col_w, "Top 3 Short-Staffed Days",
                 [(pd.Timestamp(d).strftime("%d %b %Y"), f"{g:.1f} FTE short") for d, g in
                  zip(top3_worst_days["date"], top3_worst_days["staffing_gap_fte"])])
add_ranked_list(slide, colC_x, row2_y, col_w, "Weekly Gap Trend (Next 3 Wks)",
                 [(pd.Timestamp(w).strftime("Week of %d %b"), f"{g:.1f} FTE avg gap") for w, g in weekly_gap.items()])

add_icon_bullets(slide, Inches(0.65), Inches(5.75), Inches(11.9), Inches(0.6), [
    "This is a modest, fixable gap - not a crisis - but worth flagging now, with weeks "
    "of lead time, rather than discovering it the week service levels slip.",
], size=14.5)
add_footer(slide, "Demand Forecasting & Staffing", 5)

# %% Cell 8 - Slide 6: Actionable Recommendation (left/center/right table)
slide = new_slide()
fill_bg(slide, NAVY)
add_text(slide, Inches(0.65), Inches(0.55), Inches(11.8), Inches(0.8), "Recommendation", 30, WHITE, bold=True)
rec_rows = [
    ("Fix #1: Close the FTE gap",
     f"Add overtime or a couple of flexible-shift agents — {horizon_days} days of lead time "
     f"to plan it, not a same-week scramble.",
     f"Closes the average {avg_gap:.1f}-FTE shortfall before it hits service levels."),
    ("Fix #2: Watch the peak day",
     f"Flag {pd.Timestamp(worst_day['date']).strftime('%d %b %Y')} specifically for extra coverage.",
     f"Avoids the single worst-staffed day in the horizon, {worst_day['staffing_gap_fte']:.1f} FTE short."),
    ("Next: Extend & revisit",
     "Extend the model per LoB/channel, and revisit shrinkage assumptions quarterly.",
     "Sharper staffing allocation as the roster's tenure mix shifts over time."),
]
add_recommendation_table(slide, Inches(0.65), Inches(1.85), Inches(12.0), Inches(1.4), rec_rows)
add_text(slide, Inches(0.65), Inches(6.95), Inches(11), Inches(0.4),
         "Data Analytics Consulting  |  Synthetic demo dataset", 12, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 9 - Save
os.makedirs("final_output", exist_ok=True)
prs.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} ({len(prs.slides)} slides)")

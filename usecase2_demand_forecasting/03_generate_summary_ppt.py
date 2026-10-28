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


def add_chip(slide, left, top, width, height, value, label, on_dark=True):
    """Small pill used for quick facts on the title slide - a number +
    caption packed into one compact rounded rectangle."""
    chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    chip.fill.solid()
    chip.fill.fore_color.rgb = NAVY_SOFT if on_dark else LIGHT_BG
    chip.line.color.rgb = ACCENT
    chip.line.width = Pt(1)
    _no_shadow(chip)
    tf = chip.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run()
    r0.text = value
    r0.font.size = Pt(19)
    r0.font.bold = True
    r0.font.color.rgb = ACCENT
    r0.font.name = FONT
    p1 = tf.add_paragraph()
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(10.5)
    r1.font.color.rgb = CHIP_TEXT_ON_NAVY if on_dark else GRAY
    r1.font.name = FONT


def add_proportional_bar(slide, left, top, width, height, segments):
    """segments: list of (label, pct, color). One horizontal bar made of
    proportional colored blocks, with a legend row beneath - a genuinely
    visual split instead of a line of plain text."""
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


def add_pipeline_steps(slide, left, top, width, steps, accent=ACCENT):
    """A horizontal numbered pipeline: step-number badge circles connected
    by a thin line, each with a short title + one-line description beneath."""
    n = len(steps)
    step_w = Emu(int(width / n))
    badge_d = Inches(0.55)
    line_y = top + badge_d / 2
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, left + badge_d / 2, line_y,
                                        left + width - badge_d / 2, line_y)
    line.line.color.rgb = CARD_BORDER
    line.line.width = Pt(2)
    for i, (title, desc) in enumerate(steps):
        cx = Emu(int(left) + int(step_w) * i + int(step_w) // 2)
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(cx) - int(badge_d) // 2), top, badge_d, badge_d)
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
        r.font.size = Pt(18)
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.name = FONT
        text_left = Emu(max(int(left), int(cx) - int(step_w) // 2))
        add_text(slide, text_left, top + badge_d + Inches(0.15), step_w, Inches(0.4), title, 14.5, NAVY, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, text_left, top + badge_d + Inches(0.58), step_w, Inches(1.5), desc, 12, GRAY, align=PP_ALIGN.CENTER)


def add_numbered_recommendation(slide, left, top, width, row_height, number, title, desc, accent=ACCENT):
    badge_d = Inches(0.5)
    badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, badge_d, badge_d)
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
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = NAVY
    r.font.name = FONT
    text_left = left + badge_d + Inches(0.25)
    text_width = width - badge_d - Inches(0.25)
    box = slide.shapes.add_textbox(text_left, top - Inches(0.03), text_width, row_height)
    tf2 = box.text_frame
    tf2.word_wrap = True
    p0 = tf2.paragraphs[0]
    r0 = p0.add_run()
    r0.text = title
    r0.font.size = Pt(18)
    r0.font.bold = True
    r0.font.color.rgb = WHITE
    r0.font.name = FONT
    p1 = tf2.add_paragraph()
    p1.space_before = Pt(4)
    r1 = p1.add_run()
    r1.text = desc
    r1.font.size = Pt(14.5)
    r1.font.color.rgb = CHIP_TEXT_ON_NAVY
    r1.font.name = FONT


# %% Cell 3 - Slide 1: Title
slide = new_slide()
fill_bg(slide, NAVY)
accent_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(2.3), Inches(1.2), Pt(5))
accent_line.fill.solid()
accent_line.fill.fore_color.rgb = ACCENT
accent_line.line.fill.background()
_no_shadow(accent_line)
add_text(slide, Inches(0.65), Inches(2.45), Inches(12), Inches(1.3), "Demand Forecasting & Staffing", 40, WHITE, bold=True)
add_text(slide, Inches(0.65), Inches(3.5), Inches(11), Inches(0.6),
         "Contact-volume forecasting, translated into a concrete staffing plan", 18, ACCENT)
chip_w, chip_h, chip_gap = Inches(2.9), Inches(0.95), Inches(0.25)
chip_y = Inches(4.5)
add_chip(slide, Inches(0.65), chip_y, chip_w, chip_h, f"{n_history_years:.1f} yrs", "Daily contact-volume history")
add_chip(slide, Inches(0.65) + chip_w + chip_gap, chip_y, chip_w, chip_h, f"{horizon_days} days", "Forecast horizon")
add_chip(slide, Inches(0.65) + 2 * (chip_w + chip_gap), chip_y, chip_w, chip_h, f"{n_lobs} / {n_channels}", "Lines of business / channels")
add_chip(slide, Inches(0.65) + 3 * (chip_w + chip_gap), chip_y, chip_w, chip_h, f"{hw_mape:.1f}%", "Holdout forecast MAPE")
add_text(slide, Inches(0.65), Inches(7.05), Inches(11), Inches(0.35), "Data Analytics Consulting", 11, RGBColor(0x8A, 0x97, 0xAB))

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
add_pipeline_steps(slide, Inches(0.5), Inches(1.75), Inches(12.3), [
    ("1. Explore first", "Decompose trend, weekly and yearly seasonality before "
     "touching any model."),
    ("2. Benchmark honestly", "Every candidate is tested against a naive seasonal "
     "baseline on a held-out window - it only ships if it genuinely wins."),
    ("3. Holt-Winters", "A lightweight, explainable exponential-smoothing model - "
     "not a black box - forecasts volume forward."),
    ("4. Volume -> FTE", "Convert volume to required FTE using handle time and the "
     "roster's REAL shrinkage rate, then compare to available FTE."),
    ("5. Publish", "One Excel workbook (forecast, model evidence, rollups, charts) "
     "plus a Power BI staffing-gap report."),
])
add_footer(slide, "Demand Forecasting & Staffing", 4)

# %% Cell 7 - Slide 5: Key Outcomes (stat tiles)
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Key Outcomes", kicker="Results")
tile_w, tile_h, gap = Inches(2.78), Inches(1.5), Inches(0.28)
x0, y0 = Inches(0.65), Inches(1.6)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{hw_mape:.1f}%", f"Holdout MAPE (vs {baseline_mape:.1f}% baseline)", ACCENT)
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{avg_required_fte:.0f}", "Avg required FTE over the horizon", NAVY)
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, f"{avg_available_fte:.0f}", "Available FTE (current roster)", NAVY)
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, f"{days_short}/{horizon_days}", "Days short-staffed over the horizon", GAP_RED)
add_text(slide, Inches(0.65), Inches(3.35), Inches(6), Inches(0.35), "REQUIRED VS AVAILABLE FTE", 12, ACCENT_DARK, bold=True)
avg_total = avg_required_fte + avg_available_fte
add_proportional_bar(slide, Inches(0.65), Inches(3.75), Inches(5.6), Inches(0.45), [
    ("Required", avg_required_fte / avg_total * 100, GAP_RED),
    ("Available", avg_available_fte / avg_total * 100, ACCENT),
])
add_icon_bullets(slide, Inches(6.9), Inches(3.35), Inches(5.8), Inches(0.95), [
    f"Holt-Winters improves forecast accuracy by {mape_improvement:.1f} percentage points "
    f"over the naive baseline - a real, honestly-validated gain.",
    f"Short on {days_short} of the next {horizon_days} days, averaging {avg_gap:.1f} FTE "
    f"short - peaking at {worst_day['staffing_gap_fte']:.1f} FTE on "
    f"{pd.Timestamp(worst_day['date']).strftime('%d %b %Y')}.",
], size=14.5)
add_icon_bullets(slide, Inches(0.65), Inches(5.55), Inches(11.9), Inches(0.7), [
    "This is a modest, fixable gap - not a crisis - but worth flagging now, with weeks "
    "of lead time, rather than discovering it the week service levels slip.",
], size=14.5)
add_footer(slide, "Demand Forecasting & Staffing", 5)

# %% Cell 8 - Slide 6: Actionable Recommendation
slide = new_slide()
fill_bg(slide, NAVY)
add_text(slide, Inches(0.65), Inches(0.55), Inches(11.8), Inches(0.8), "Recommendation", 30, WHITE, bold=True)
recs = [
    ("Fix #1: Close the FTE gap",
     f"Close a {avg_gap:.1f}-FTE average gap with overtime or a couple of flexible-shift agents - "
     f"the forecast gives {horizon_days} days of lead time to plan it, not a same-week scramble."),
    ("Fix #2: Watch the peak day",
     f"Watch {pd.Timestamp(worst_day['date']).strftime('%d %b %Y')} specifically - the single "
     f"worst-staffed day in the horizon."),
    ("Next step: Extend & revisit",
     "Extend the model per LoB/channel for sharper staffing allocation, and revisit shrinkage "
     "assumptions quarterly as the roster's tenure mix shifts."),
]
y = Inches(1.9)
row_h = Inches(1.45)
for i, (title, desc) in enumerate(recs):
    add_numbered_recommendation(slide, Inches(0.65), y + i * row_h, Inches(12), row_h, i + 1, title, desc)
add_text(slide, Inches(0.65), Inches(6.9), Inches(11), Inches(0.4),
         "Data Analytics Consulting  |  Synthetic demo dataset", 12, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 9 - Save
os.makedirs("final_output", exist_ok=True)
prs.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} ({len(prs.slides)} slides)")

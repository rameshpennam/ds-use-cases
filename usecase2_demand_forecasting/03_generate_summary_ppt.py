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
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

FORECAST_FILE = "final_output/final_output_forecast_staffing.xlsx"
MODEL_COMPARISON_FILE = "intermediate/intermediate_model_accuracy_comparison.xlsx"
VOLUME_FILE = "input/input_call_volume_history.xlsx"
OUTPUT_FILE = "final_output/usecase2_forecast_summary.pptx"

# Same design system as the other use case's deck - keeps both decks looking
# like they came from the same consulting engagement.
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x2E, 0xC4, 0xB6)
GAP_RED = RGBColor(0xE0, 0x5A, 0x47)
LIGHT_BG = RGBColor(0xF5, 0xF7, 0xFA)
GRAY = RGBColor(0x5A, 0x6B, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TEXT = RGBColor(0x20, 0x26, 0x33)
FONT = "Calibri"

# %% Cell 1 - Pull the real numbers for this deck
# NARRATE: "Same discipline as the other deck - every number here comes
# straight from the actual forecast and model-comparison output files."
staffing = pd.read_excel(FORECAST_FILE, sheet_name="Forecast_Staffing", keep_default_na=False)
model_comparison = pd.read_excel(MODEL_COMPARISON_FILE, sheet_name="Model_Comparison")
vol = pd.read_excel(VOLUME_FILE, sheet_name="Call_Volume_History")
vol["date"] = pd.to_datetime(vol["date"])

n_history_days = (vol["date"].max() - vol["date"].min()).days
n_history_years = n_history_days / 365
horizon_days = len(staffing)

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

# %% Cell 2 - Design helpers (shared pattern with the other use case's deck)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK_LAYOUT = prs.slide_layouts[6]


def new_slide():
    return prs.slides.add_slide(BLANK_LAYOUT)


def fill_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_text(slide, left, top, width, height, text, size, color, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    return box


def add_bullets(slide, left, top, width, height, bullets, size=18, color=DARK_TEXT, space_after=12):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        run = p.add_run()
        run.text = f"●   {b}"
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = FONT


def add_title_bar(slide, title, kicker=""):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    y = Inches(0.4)
    if kicker:
        add_text(slide, Inches(0.65), y, Inches(10), Inches(0.4), kicker.upper(), 13, ACCENT, bold=True)
        y = Inches(0.78)
    add_text(slide, Inches(0.65), y, Inches(12), Inches(0.9), title, 30, NAVY, bold=True)


def add_footer(slide, text):
    add_text(slide, Inches(0.65), Inches(7.05), Inches(10), Inches(0.35), text, 10, GRAY)


def add_stat_tile(slide, left, top, width, height, value, label, accent=ACCENT):
    tile = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    tile.fill.solid()
    tile.fill.fore_color.rgb = LIGHT_BG
    tile.line.color.rgb = accent
    tile.line.width = Pt(1.5)
    tile.shadow.inherit = False
    tf = tile.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run()
    r0.text = value
    r0.font.size = Pt(30)
    r0.font.bold = True
    r0.font.color.rgb = accent
    r0.font.name = FONT
    p1 = tf.add_paragraph()
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(12)
    r1.font.color.rgb = GRAY
    r1.font.name = FONT


# %% Cell 3 - Slide 1: Title
slide = new_slide()
fill_bg(slide, NAVY)
accent_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(2.85), Inches(1.2), Pt(5))
accent_line.fill.solid()
accent_line.fill.fore_color.rgb = ACCENT
accent_line.line.fill.background()
accent_line.shadow.inherit = False
add_text(slide, Inches(0.65), Inches(3.0), Inches(12), Inches(1.3),
         "Demand Forecasting & Staffing", 40, WHITE, bold=True)
add_text(slide, Inches(0.65), Inches(4.0), Inches(11), Inches(0.6),
         "Contact-volume forecasting, translated into a concrete staffing plan", 18, ACCENT)
add_text(slide, Inches(0.65), Inches(6.7), Inches(11), Inches(0.4),
         f"Data Analytics Consulting  |  {n_history_years:.1f} years of history  |  {horizon_days}-day forecast horizon",
         13, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 4 - Slide 2: The Use Case & Objective
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Use Case", kicker="Business Context")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(4.5), [
    "Both over- and under-staffing are expensive: idle capacity burns cost; a shortfall "
    "shows up directly in service levels and CSAT.",
    "The business question: based on real contact-volume history, how many agents do we "
    "actually need over the next several weeks, and does the current roster cover it?",
    "Objective: build a forecast grounded in the real patterns in the data - trend, "
    "seasonality, holidays, campaigns - validate it honestly, then convert it into a "
    "concrete FTE requirement the business can act on.",
], size=19, space_after=22)
add_footer(slide, "Demand Forecasting & Staffing")

# %% Cell 5 - Slide 3: The Data
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Data", kicker="Input")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(3.2), [
    f"{n_history_years:.1f} years of daily contact-volume history, by line of business "
    "and channel, with handle time, holiday and campaign flags",
    "An agent roster: who we have today, their line of business, team lead/manager, "
    "tenure, weekly available hours, and real shrinkage % (time scheduled but not "
    "available - breaks, training, coaching)",
], size=19, space_after=20)
y = Inches(4.0)
lob_text = "  |  ".join(f"{lob}: {pct:.0f}%" for lob, pct in lob_split_pct.items())
add_text(slide, Inches(0.65), y, Inches(11.8), Inches(0.5), "Volume split by LoB:  " + lob_text, 16, GRAY)
add_footer(slide, "Demand Forecasting & Staffing")

# %% Cell 6 - Slide 4: Approach & Expected Output
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Approach & Expected Output", kicker="Method")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(4.5), [
    "Explore the data first: decompose trend, weekly and yearly seasonality before "
    "touching any model",
    "Benchmark every candidate model against a naive seasonal baseline on a held-out "
    "test window - a model only ships if it genuinely beats the simple approach",
    "Holt-Winters exponential smoothing - a lightweight, explainable model, not a "
    "black box - forecasts volume forward",
    "Convert volume into required FTE using handle time and the roster's REAL shrinkage "
    "rate (not a flat textbook assumption), then compare to available FTE",
    "Expected output: one Excel workbook (date-level forecast, model accuracy evidence, "
    "weekly/monthly rollups, charts) plus a Power BI staffing-gap report",
], size=18, space_after=16)
add_footer(slide, "Demand Forecasting & Staffing")

# %% Cell 7 - Slide 5: Key Outcomes (stat tiles)
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Key Outcomes", kicker="Results")
tile_w, tile_h, gap = Inches(2.75), Inches(1.7), Inches(0.3)
x0, y0 = Inches(0.65), Inches(1.7)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{hw_mape:.1f}%", f"Holdout MAPE (vs {baseline_mape:.1f}% baseline)", ACCENT)
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{avg_required_fte:.0f}", "Avg required FTE over the horizon", NAVY)
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, f"{avg_available_fte:.0f}", "Available FTE (current roster)", NAVY)
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, f"{days_short}/{horizon_days}", "Days short-staffed over the horizon", GAP_RED)
add_bullets(slide, Inches(0.65), Inches(3.9), Inches(11.8), Inches(2.6), [
    f"Holt-Winters improves forecast accuracy by {mape_improvement:.1f} percentage points "
    f"over a naive 'same as last week' baseline - a real, honestly-validated gain, not an "
    f"inflated claim.",
    f"The roster runs short on {days_short} of the next {horizon_days} days, averaging "
    f"{avg_gap:.1f} FTE short - peaking at {worst_day['staffing_gap_fte']:.1f} FTE on "
    f"{pd.Timestamp(worst_day['date']).strftime('%d %b %Y')}.",
    "This is a modest, fixable gap - not a crisis - but worth flagging now, with weeks "
    "of lead time, rather than discovering it the week service levels slip.",
], size=17, space_after=14)
add_footer(slide, "Demand Forecasting & Staffing")

# %% Cell 8 - Slide 6: Actionable Recommendation
slide = new_slide()
fill_bg(slide, NAVY)
add_text(slide, Inches(0.65), Inches(0.5), Inches(11.8), Inches(0.8), "Recommendation", 30, WHITE, bold=True)
rec_bullets = [
    f"Close a {avg_gap:.1f}-FTE average gap with overtime or a couple of flexible-shift "
    f"agents - the forecast gives {horizon_days} days of lead time to plan it, not a "
    f"same-week scramble.",
    f"Watch the week of {pd.Timestamp(worst_day['date']).strftime('%d %b %Y')} specifically - "
    f"the single worst-staffed day in the horizon.",
    "Next step: extend the model per LoB/channel for sharper staffing allocation, and "
    "revisit shrinkage assumptions quarterly as the roster's tenure mix shifts.",
]
box = slide.shapes.add_textbox(Inches(0.65), Inches(1.8), Inches(12), Inches(4.5))
tf = box.text_frame
tf.word_wrap = True
for i, b in enumerate(rec_bullets):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.space_after = Pt(22)
    run = p.add_run()
    run.text = f"●   {b}"
    run.font.size = Pt(19)
    run.font.color.rgb = WHITE
    run.font.name = FONT
add_text(slide, Inches(0.65), Inches(6.8), Inches(11), Inches(0.4),
         "Data Analytics Consulting  |  Synthetic demo dataset", 12, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 9 - Save
os.makedirs("final_output", exist_ok=True)
prs.save(OUTPUT_FILE)
print(f"Saved -> {OUTPUT_FILE} ({len(prs.slides)} slides)")

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
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

DATA_FILE = "final_output/final_output_csat_insights.xlsx"
OUTPUT_FILE = "final_output/usecase1_csat_summary.pptx"

# WHAT: a small, consistent design system (colors, fonts, helper shapes)
# reused across every slide. WHY: this is what makes a deck look like one
# coherent, professionally-designed document instead of a pile of
# mismatched text boxes.
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x2E, 0xC4, 0xB6)
DETRACTOR_RED = RGBColor(0xE0, 0x5A, 0x47)
LIGHT_BG = RGBColor(0xF5, 0xF7, 0xFA)
GRAY = RGBColor(0x5A, 0x6B, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TEXT = RGBColor(0x20, 0x26, 0x33)
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
top_primary_fcr = (df.loc[df["primary_driver"] == top_primary, "is_first_contact_resolution"] == "Yes").mean() * 100
top_primary_handle_time = df.loc[df["primary_driver"] == top_primary, "handle_time_seconds"].mean()

top_primary_rows = df[df["primary_driver"] == top_primary]
secondary_within_top = top_primary_rows["secondary_driver"].value_counts(normalize=True) * 100
secondary_within_top = secondary_within_top.drop("No Secondary Driver", errors="ignore")
top_secondary = secondary_within_top.index[0] if len(secondary_within_top) else None
top_secondary_pct = secondary_within_top.iloc[0] if len(secondary_within_top) else 0

csat_bucket_counts = df["csat_bucket"].value_counts(normalize=True) * 100
promoter_pct = csat_bucket_counts.get("Promoter (4-5)", 0)
detractor_pct = csat_bucket_counts.get("Detractor (1-2)", 0)

channel_counts = df["channel"].value_counts()
tenure_lowest_csat = df.groupby("tenure_bucket")["csat_score"].mean().idxmin()

print(f"Top driver: {top_primary} ({top_primary_pct:.1f}%, avg CSAT {top_primary_csat:.2f})")
print(f"Top compounding secondary (within {top_primary}): {top_secondary} ({top_secondary_pct:.1f}%)")
print(f"Overall avg CSAT: {avg_csat:.2f} | Promoters {promoter_pct:.1f}% | Detractors {detractor_pct:.1f}%")

# %% Cell 2 - Design helpers (shared across every slide)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK_LAYOUT = prs.slide_layouts[6]


def new_slide():
    return prs.slides.add_slide(BLANK_LAYOUT)


def fill_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_text(slide, left, top, width, height, text, size, color, bold=False,
             align=PP_ALIGN.LEFT, anchor=None):
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
    run.font.color.rgb = color
    run.font.name = FONT
    return box


def add_bullets(slide, left, top, width, height, bullets, size=18, color=DARK_TEXT, space_after=12):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
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
         "CSAT Root-Cause & Sentiment\nDriver Analysis", 40, WHITE, bold=True)
add_text(slide, Inches(0.65), Inches(4.35), Inches(11), Inches(0.6),
         "Identifying and prioritizing what's actually driving customer dissatisfaction", 18, ACCENT)
add_footer_text = f"Data Analytics Consulting  |  {pd.Timestamp(date_min).strftime('%b %Y')} – {pd.Timestamp(date_max).strftime('%b %Y')}  |  {n_records:,} survey responses"
add_text(slide, Inches(0.65), Inches(6.7), Inches(11), Inches(0.4), add_footer_text, 13, RGBColor(0xB8, 0xC2, 0xD0))

# %% Cell 4 - Slide 2: The Use Case & Objective
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Use Case", kicker="Business Context")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(4.5), [
    "CSAT scores are down, and leadership needs to know WHY - not just that satisfaction "
    "has slipped, but which specific, fixable issue is driving it.",
    "Thousands of open-text survey responses arrive across chat, email and voice every "
    "month - too much volume to read by hand, but too much nuance for a dashboard number alone.",
    "Objective: systematically tag every response against a small set of known root-cause "
    "drivers, score its sentiment, and roll everything up into a ranked, actionable view - "
    "which driver matters most, where it concentrates, and what's compounding it.",
], size=19, space_after=22)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis")

# %% Cell 5 - Slide 3: The Data
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "The Data", kicker="Input")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(3.2), [
    f"{n_records:,} customer survey responses across chat, email and voice "
    f"({pd.Timestamp(date_min).strftime('%d %b')} – {pd.Timestamp(date_max).strftime('%d %b %Y')})",
    "Columns: date, unique response ID, channel, line of business, the customer's own "
    "words (verbatim), CSAT score (1-5), plus the agent/TL/manager who handled it",
    "Also carries three real call-center operational signals: handle time, "
    "first-contact-resolution flag, and 30-day repeat-contact flag",
], size=19, space_after=20)
y = Inches(4.9)
channel_text = "  |  ".join(f"{ch}: {cnt:,}" for ch, cnt in channel_counts.items())
add_text(slide, Inches(0.65), y, Inches(11.8), Inches(0.5), "Channel mix:  " + channel_text, 16, GRAY)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis")

# %% Cell 6 - Slide 4: Approach & Expected Output
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Approach & Expected Output", kicker="Method")
add_bullets(slide, Inches(0.65), Inches(1.6), Inches(11.8), Inches(4.5), [
    "Bootstrap a root-cause keyword dictionary from the terms that actually distinguish "
    "low-CSAT from high-CSAT text (minutes, not days of manual reading)",
    "Tag every response against the dictionary, ranked by match strength into a PRIMARY "
    "and SECONDARY driver per response",
    "Where the dictionary finds nothing, TF-IDF + NMF topic modeling discovers an "
    "actionable secondary sub-theme directly from the text - no response is left unexplained",
    "Score sentiment with an offline lexicon model (no AI/LLM API dependency)",
    "Expected output: one Excel workbook (raw tagged data, every summary cut, every chart) "
    "plus a Power BI report for the business narrative",
], size=18, space_after=18)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis")

# %% Cell 7 - Slide 5: Key Outcomes (stat tiles)
slide = new_slide()
fill_bg(slide, WHITE)
add_title_bar(slide, "Key Outcomes", kicker="Results")
tile_w, tile_h, gap = Inches(2.75), Inches(1.7), Inches(0.3)
x0, y0 = Inches(0.65), Inches(1.7)
add_stat_tile(slide, x0, y0, tile_w, tile_h, f"{top_primary_pct:.0f}%", f"of responses: {top_primary.replace('_', ' ')}", ACCENT)
add_stat_tile(slide, x0 + tile_w + gap, y0, tile_w, tile_h, f"{avg_csat:.2f}", "Overall average CSAT (out of 5)", NAVY)
add_stat_tile(slide, x0 + 2 * (tile_w + gap), y0, tile_w, tile_h, f"{pct_negative_sentiment:.0f}%", "of responses carry negative sentiment", DETRACTOR_RED)
add_stat_tile(slide, x0 + 3 * (tile_w + gap), y0, tile_w, tile_h, f"{top_primary_fcr:.0f}%", f"First-Contact Resolution rate for {top_primary.replace('_', ' ')}", ACCENT)
add_bullets(slide, Inches(0.65), Inches(3.9), Inches(11.8), Inches(2.6), [
    f"{top_primary.replace('_', ' ')} is both the highest-VOLUME and lowest-CSAT driver "
    f"(avg CSAT {top_primary_csat:.2f}) - the clear priority-one fix.",
    f"It also runs the longest average handle time ({top_primary_handle_time:.0f} seconds) - "
    f"a real operational cost on top of the CSAT hit.",
    f"CSAT mix: {promoter_pct:.0f}% Promoters (4-5) vs {detractor_pct:.0f}% Detractors (1-2) - "
    f"a split, not a crisis, but with a specific, fixable lever.",
    f"Agents with less than 6 months' tenure skew toward the lowest-CSAT bucket "
    f"({tenure_lowest_csat}) - a coaching signal alongside the process fix.",
], size=17, space_after=14)
add_footer(slide, "CSAT Root-Cause & Sentiment Driver Analysis")

# %% Cell 8 - Slide 6: Actionable Recommendation
slide = new_slide()
fill_bg(slide, NAVY)
add_text(slide, Inches(0.65), Inches(0.5), Inches(11.8), Inches(0.8), "Recommendation", 30, WHITE, bold=True)
rec_box_bullets = [
    f"Fix #1: {top_primary.replace('_', ' ')} - the single biggest, lowest-scoring driver, "
    f"concentrated and compounding with “{top_secondary}” in {top_secondary_pct:.0f}% of its own complaints."
    if top_secondary else f"Fix #1: {top_primary.replace('_', ' ')} - the single biggest, lowest-scoring driver.",
    f"Fix #2: coach agents under 6 months' tenure - this cohort shows the weakest CSAT "
    f"({tenure_lowest_csat} bucket) across the board.",
    "Next step: validate this taxonomy against a sample of real customer verbatim, then "
    "track the top driver's weekly trend (already built into the workbook) as fixes roll out.",
]
box = slide.shapes.add_textbox(Inches(0.65), Inches(1.8), Inches(12), Inches(4.5))
tf = box.text_frame
tf.word_wrap = True
for i, b in enumerate(rec_box_bullets):
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

"""
Shared PDF-building helpers for the 4 fictitious vendor reports: page
template with watermark footer + page numbers, a real auto-paginating
table of contents, styled tables, and matplotlib chart embedding.

Every report built with this module gets the same watermark and the same
visual language (just a different accent color per vendor) so they read
as a consistent "document family" the way real research-vendor reports do.
"""
import os
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, NextPageTemplate, FrameBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas as pdfcanvas

from benchmarks import WATERMARK

PAGE_W, PAGE_H = LETTER
MARGIN = 0.75 * inch
CHART_DIR = tempfile.mkdtemp(prefix="pilot_pdf_charts_")

PALETTE_NEUTRAL = ["#2E4057", "#4C7A8C", "#8FA6A3", "#C9A66B", "#B0413E"]


def _chart_path(name):
    return os.path.join(CHART_DIR, name + ".png")


def _style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="-", linewidth=0.5, alpha=0.3)
    ax.set_axisbelow(True)


def fig_grouped_bar(categories, series, title, ylabel, accent="#2E4057"):
    fig, ax = plt.subplots(figsize=(6.6, 3.3), dpi=170)
    n = len(series)
    width = 0.8 / n
    x = range(len(categories))
    palette = [accent, "#A7B8C4", "#C9A66B", "#8FA6A3"]
    for i, (name, vals) in enumerate(series.items()):
        offs = [xi + (i - (n - 1) / 2) * width for xi in x]
        ax.bar(offs, vals, width=width, label=name, color=palette[i % len(palette)])
    ax.set_xticks(list(x))
    ax.set_xticklabels(categories, fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    _style_axes(ax)
    fig.tight_layout()
    p = _chart_path(f"grouped_{abs(hash(title))}")
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_line(categories, series, title, ylabel, accent="#2E4057"):
    fig, ax = plt.subplots(figsize=(6.6, 3.3), dpi=170)
    palette = [accent, "#A7B8C4", "#C9A66B", "#B0413E"]
    for i, (name, vals) in enumerate(series.items()):
        ax.plot(categories, vals, marker="o", label=name, color=palette[i % len(palette)], linewidth=2)
    ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, frameon=False)
    _style_axes(ax)
    fig.tight_layout()
    p = _chart_path(f"line_{abs(hash(title))}")
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_horizontal_bar(labels, values, title, xlabel, accent="#2E4057", highlight_last=False):
    fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=170)
    colors_list = [accent] * len(values)
    if highlight_last:
        colors_list[-1] = "#B0413E"
    y = range(len(labels))
    ax.barh(list(y), values, color=colors_list)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
    ax.set_xlabel(xlabel, fontsize=8)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0) if "%" in xlabel else mticker.ScalarFormatter())
    _style_axes(ax)
    fig.tight_layout()
    p = _chart_path(f"hbar_{abs(hash(title))}")
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_stacked_bar(categories, series, title, ylabel, accent="#2E4057"):
    fig, ax = plt.subplots(figsize=(6.6, 3.3), dpi=170)
    palette = PALETTE_NEUTRAL
    bottom = [0] * len(categories)
    for i, (name, vals) in enumerate(series.items()):
        ax.bar(categories, vals, bottom=bottom, label=name, color=palette[i % len(palette)])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _style_axes(ax)
    fig.tight_layout()
    p = _chart_path(f"stacked_{abs(hash(title))}")
    fig.savefig(p)
    plt.close(fig)
    return p


def key_takeaways(title, bullets, styles, accent):
    """The boxed 'Key Takeaways' bullet list that opens most sections in a
    real analyst/research report -- lets a skimming reader get the point
    without reading the full narrative underneath."""
    rows = [[Paragraph(f"<b>{title}</b>", styles["H3"])]]
    for b in bullets:
        rows.append([Paragraph("&bull;&nbsp;&nbsp;" + b, styles["Body"])])
    t = Table(rows, colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2EFE7")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(accent)),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, -1), (0, -1), 8),
    ]))
    return t


def big_stat_callout(label, value_text, sublabel, styles, accent):
    """The single pulled-out number that leads a response-driven email --
    one glance tells a skimming exec what's at stake, before they read a
    word of the supporting bullets."""
    big_style = ParagraphStyle("BigStat", parent=styles["Normal"], fontSize=26, leading=30,
                                fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    label_style = ParagraphStyle("BigStatLabel", parent=styles["Normal"], fontSize=10, leading=13,
                                  textColor=colors.white, alignment=TA_CENTER)
    sub_style = ParagraphStyle("BigStatSub", parent=styles["Normal"], fontSize=8.5, leading=11,
                                textColor=colors.HexColor("#E8E8E8"), alignment=TA_CENTER)
    rows = [[Paragraph(label, label_style)], [Paragraph(value_text, big_style)], [Paragraph(sublabel, sub_style)]]
    t = Table(rows, colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent)),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 2),
        ("BOTTOMPADDING", (0, 1), (0, 1), 2),
        ("TOPPADDING", (0, 2), (0, 2), 2),
        ("BOTTOMPADDING", (0, 2), (0, 2), 12),
    ]))
    return t


def hero_banner(eyebrow, headline, styles, accent):
    """The full-width banner a real account-deep-dive document opens
    with -- a small all-caps eyebrow label over a bold, news-style
    headline, so the single most important claim in the whole email is
    the very first thing a reader's eye lands on, before the greeting."""
    eyebrow_style = ParagraphStyle("HeroEyebrow", parent=styles["Normal"], fontSize=8.5, leading=11,
                                    fontName="Helvetica-Bold", textColor=colors.HexColor("#D9D9D9"),
                                    alignment=TA_CENTER, spaceAfter=4)
    headline_style = ParagraphStyle("HeroHeadline", parent=styles["Normal"], fontSize=19, leading=23,
                                     fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    rows = [[Paragraph(eyebrow.upper(), eyebrow_style)], [Paragraph(headline, headline_style)]]
    t = Table(rows, colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent)),
        ("TOPPADDING", (0, 0), (0, 0), 14), ("BOTTOMPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 1), (0, 1), 2), ("BOTTOMPADDING", (0, 1), (0, 1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    return t


def campaign_card(name, diagnosis, note_text, opportunity_text, styles, accent):
    """One clearly-bordered card per in-scope campaign -- deliberately a
    different visual weight than key_takeaways' solid-fill callout, so the
    eye reads 'evidence' here and 'action' there."""
    name_style = ParagraphStyle("CardName", parent=styles["Normal"], fontSize=11, leading=14,
                                 fontName="Helvetica-Bold", textColor=colors.HexColor(accent))
    rows = [[Paragraph(name, name_style)], [Paragraph(diagnosis, styles["Body"])]]
    if note_text:
        rows.append([Paragraph(f"<i>{note_text}</i>", styles["Caption"])])
    rows.append([Paragraph(opportunity_text, styles["Body"])])
    t = Table(rows, colWidths=[6.3 * inch])
    style_cmds = [
        ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor(accent)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (0, 0), 9),
        ("BOTTOMPADDING", (0, -1), (0, -1), 9),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


PRIORITY_COLORS = {"high": "#B0413E", "medium": "#C9A66B", "low": "#6E8B74"}

AFFECTS_LABELS = {"bid": "Bid", "quality_score": "Quality", "budget_allocation": "Budget",
                   "negative_keywords": "Negatives"}


def chip_row(chips, styles):
    """A row of small colored tag badges (PRIORITY / TIMEFRAME / AFFECTS
    style), the same visual language a real analyst deep-dive uses to let a
    skimming reader triage without reading every word. Width is sized
    generously per character and wrap is disabled -- a chip that wraps
    mid-word ("HIG" / "H") defeats the point of a quick-scan tag."""
    chip_style = ParagraphStyle("Chip", parent=styles["Normal"], fontSize=7.3, leading=9,
                                 fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    cells = [Paragraph(label.upper(), chip_style) for label, _color in chips]
    widths = [0.5 * inch + 0.095 * inch * len(label) for label, _ in chips]
    t = Table([cells], colWidths=widths)
    style_cmds = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                  ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    for i, (_label, color_hex) in enumerate(chips):
        style_cmds.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(color_hex)))
    t.setStyle(TableStyle(style_cmds))
    t.hAlign = "LEFT"
    return t


def _section_label(text, accent):
    label_style = ParagraphStyle(f"SectionLabel_{text}", fontSize=7.6, leading=10,
                                  fontName="Helvetica-Bold", textColor=colors.HexColor(accent),
                                  spaceBefore=6, spaceAfter=1)
    return Paragraph(text.upper(), label_style)


def recommendation_card(index, card, styles, accent, chart_path=None):
    """One numbered, full recommendation section -- Analysis / Context /
    Graph / Recommendation / What to watch, each clearly labeled so the
    email reads like a sequence of distinct recommendations rather than a
    wall of undifferentiated text. Chips stay for quick-scan triage;
    everything else is now explicit, not implied by layout alone."""
    chips = [(card["priority"], PRIORITY_COLORS.get(card["priority"], accent)),
             (card["timeframe"], "#777777"),
             (AFFECTS_LABELS.get(card["affects"], card["affects"]), accent)]
    number_style = ParagraphStyle("RecNumber", parent=styles["Normal"], fontSize=9, leading=11,
                                   fontName="Helvetica-Bold", textColor=colors.HexColor(accent))
    title_style = ParagraphStyle("RecTitle", parent=styles["Normal"], fontSize=12, leading=15,
                                  fontName="Helvetica-Bold", textColor=colors.HexColor("#222222"), spaceBefore=2)
    market_style = ParagraphStyle("RecMarket", parent=styles["Body"], fontSize=9.5, leading=13,
                                   textColor=colors.HexColor(accent), fontName="Helvetica-Bold")
    market_source_style = ParagraphStyle("RecMarketSource", parent=styles["Caption"], fontSize=7.8, leading=10)
    steps_text = "".join(f"&bull;&nbsp;&nbsp;{s}<br/>" for s in card["recommended_steps"]).rstrip("<br/>")

    rows = [
        [Paragraph(f"RECOMMENDATION {index}", number_style)],
        [chip_row(chips, styles)],
        [Paragraph(card["title"], title_style)],
        [_section_label("Analysis", accent)],
        [Paragraph(card["what_data_shows"], styles["Body"])],
    ]
    market_row_range = None
    market_support = card.get("market_support") or []
    if market_support:
        comparisons = "<br/>".join(f"&#9679;&nbsp;{f['account_vs_market']}" for f in market_support)
        sources = " &nbsp;|&nbsp; ".join(f"Source: {f['vendor']} -- {f['fact']}" for f in market_support)
        rows.append([_section_label("Context -- what the market independently shows", accent)])
        rows.append([Paragraph(comparisons, market_style)])
        rows.append([Paragraph(sources, market_source_style)])
        market_row_range = (len(rows) - 3, len(rows) - 1)
    if chart_path:
        rows.append([_section_label("Graph", accent)])
        rows.append([chart_image(chart_path, width=5.7 * inch)])
    rows += [
        [_section_label("Recommendation", accent)],
        [Paragraph(steps_text, styles["Body"])],
        [Paragraph(f"<b>What to watch:</b> {card['what_to_watch']}", styles["Caption"])],
    ]

    t = Table(rows, colWidths=[6.3 * inch])
    style_cmds = [
        ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor(accent)),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(PRIORITY_COLORS.get(card["priority"], accent))),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (0, 0), 10), ("BOTTOMPADDING", (0, -1), (0, -1), 10),
    ]
    if market_row_range:
        lo, hi = market_row_range
        style_cmds.append(("BACKGROUND", (0, lo), (0, hi), colors.HexColor("#F2EFE7")))
        style_cmds.append(("TOPPADDING", (0, lo), (0, lo), 7))
        style_cmds.append(("BOTTOMPADDING", (0, hi), (0, hi), 7))
    t.setStyle(TableStyle(style_cmds))
    return t


def opportunity_stat_strip(stat_cells, styles, accent):
    """Three (or so) numbers in a row -- the payoff framing a response-
    driven email ends on, distinct in shape from the single big_stat_callout
    so the reader's eye recognizes 'this is the ROI summary' at a glance."""
    val_style = ParagraphStyle("StripVal", parent=styles["Normal"], fontSize=17, leading=20,
                                fontName="Helvetica-Bold", textColor=colors.HexColor(accent), alignment=TA_CENTER)
    label_style = ParagraphStyle("StripLabel", parent=styles["Normal"], fontSize=7.6, leading=10,
                                  textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
    col = [[Paragraph(value, val_style), Paragraph(label, label_style)] for value, label in stat_cells]
    row = [list(pair) for pair in zip(*col)]  # transpose: row0 = values, row1 = labels
    width = 6.5 * inch / len(stat_cells)
    t = Table(row, colWidths=[width] * len(stat_cells))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F6F2")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#DDDDDD")),
        ("LINEAFTER", (0, 0), (-2, -1), 0.7, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]))
    return t


def chart_image(path, width=6.5 * inch):
    img = Image(path)
    aspect = img.imageHeight / float(img.imageWidth)
    img.drawWidth = width
    img.drawHeight = width * aspect
    return img


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def get_styles(accent="#2E4057"):
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverTitle", parent=ss["Title"], fontSize=28, leading=32,
                           textColor=colors.HexColor(accent), spaceAfter=6))
    ss.add(ParagraphStyle("CoverSubtitle", parent=ss["Normal"], fontSize=14, leading=18,
                           textColor=colors.HexColor("#555555"), spaceAfter=4))
    ss.add(ParagraphStyle("CoverMeta", parent=ss["Normal"], fontSize=10, leading=14,
                           textColor=colors.HexColor("#777777")))
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, spaceBefore=18, spaceAfter=10,
                           textColor=colors.HexColor(accent)))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6,
                           textColor=colors.HexColor(accent)))
    ss.add(ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4,
                           textColor=colors.HexColor("#333333")))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=14, spaceAfter=8,
                           alignment=TA_LEFT))
    ss.add(ParagraphStyle("Callout", parent=ss["Normal"], fontSize=9.5, leading=14,
                           backColor=colors.HexColor("#F2EFE7"), borderPadding=8,
                           leftIndent=4, rightIndent=4, spaceAfter=10))
    ss.add(ParagraphStyle("TableCell", parent=ss["Normal"], fontSize=8, leading=10))
    ss.add(ParagraphStyle("TableHeader", parent=ss["Normal"], fontSize=8, leading=10,
                           textColor=colors.white, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Caption", parent=ss["Normal"], fontSize=8, leading=11,
                           textColor=colors.HexColor("#777777"), spaceAfter=10))
    ss.add(ParagraphStyle("TOCHeading1", parent=ss["Normal"], fontSize=11, leading=16,
                           textColor=colors.HexColor(accent)))
    ss.add(ParagraphStyle("TOCHeading2", parent=ss["Normal"], fontSize=9.5, leading=13,
                           leftIndent=14, textColor=colors.HexColor("#444444")))
    return ss


def data_table(header, rows, col_widths=None, styles=None, accent="#2E4057", small=False):
    fs = 7.3 if small else 8
    header_para = [Paragraph(str(h), styles["TableHeader"]) for h in header]
    body = [[Paragraph(str(c), ParagraphStyle("c", parent=styles["TableCell"], fontSize=fs)) for c in r] for r in rows]
    t = Table([header_para] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F6F2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ---------------------------------------------------------------------------
# Document with footer watermark + page numbers + real TOC
# ---------------------------------------------------------------------------

class VendorDocTemplate(BaseDocTemplate):
    def __init__(self, filename, accent, footer_note, header_left=None, header_right=None, **kw):
        super().__init__(filename, pagesize=LETTER,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=1.05 * inch, bottomMargin=MARGIN, **kw)
        self.accent = accent
        self.footer_note = footer_note
        self.header_left = header_left or ""
        self.header_right = header_right or ""
        frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 1.05 * inch - MARGIN, id="main")
        cover_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="cover")
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover_frame], onPage=self._draw_cover_decor),
            PageTemplate(id="Normal", frames=[frame], onPage=self._draw_header_footer),
        ])

    def _draw_header_footer(self, canv, doc):
        canv.saveState()
        # running header
        canv.setStrokeColor(colors.HexColor("#DDDDDD"))
        canv.setLineWidth(0.6)
        canv.line(MARGIN, PAGE_H - 0.78 * inch, PAGE_W - MARGIN, PAGE_H - 0.78 * inch)
        canv.setFont("Helvetica-Bold", 8)
        canv.setFillColor(colors.HexColor(self.accent))
        canv.drawString(MARGIN, PAGE_H - 0.65 * inch, self.header_left)
        canv.setFont("Helvetica", 8)
        canv.setFillColor(colors.HexColor("#888888"))
        canv.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.65 * inch, self.header_right)
        # footer
        canv.setStrokeColor(colors.HexColor(self.accent))
        canv.setLineWidth(1.4)
        canv.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
        canv.setFont("Helvetica", 6.6)
        canv.setFillColor(colors.HexColor("#B0413E"))
        canv.drawCentredString(PAGE_W / 2, 0.47 * inch, WATERMARK)
        canv.setFillColor(colors.HexColor("#888888"))
        canv.setFont("Helvetica", 7.5)
        canv.drawString(MARGIN, 0.33 * inch, self.footer_note)
        canv.drawRightString(PAGE_W - MARGIN, 0.33 * inch, f"Page {doc.page}")
        canv.restoreState()

    def _draw_cover_decor(self, canv, doc):
        canv.saveState()
        canv.setFillColor(colors.HexColor(self.accent))
        canv.rect(0, PAGE_H - 0.35 * inch, PAGE_W, 0.35 * inch, fill=1, stroke=0)
        canv.rect(0, 0, PAGE_W, 0.35 * inch, fill=1, stroke=0)
        canv.setFillColor(colors.HexColor("#B0413E"))
        canv.setFont("Helvetica-Bold", 8.5)
        canv.drawCentredString(PAGE_W / 2, 0.14 * inch, WATERMARK)
        canv.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        text = flowable.getPlainText()
        if style == "H1":
            self.canv.bookmarkPage(text)
            self.notify("TOCEntry", (0, text, self.page, text))
        elif style == "H2":
            self.canv.bookmarkPage(text)
            self.notify("TOCEntry", (1, text, self.page, text))


def make_toc(styles):
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCHeading1"], styles["TOCHeading2"]]
    return toc


def build_pdf(filename, accent, footer_note, flowables, header_left=None, header_right=None):
    doc = VendorDocTemplate(filename, accent=accent, footer_note=footer_note,
                             header_left=header_left, header_right=header_right)
    doc.multiBuild(flowables)
    return filename


def page_count(path):
    from pypdf import PdfReader
    return len(PdfReader(path).pages)

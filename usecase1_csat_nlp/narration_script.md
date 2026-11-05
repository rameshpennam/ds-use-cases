# Narration Script — CSAT Root-Cause & Sentiment Driver Analysis
Full talk track for presenting this walkthrough. Deliberately starts at the
use-case introduction — **your own personal/role introduction is not
included here**; do that yourself in your own words at the very start,
since only you know what's accurate to say and this script shouldn't be
guessing it on your behalf.

Read this as a guide, not a strict script to recite word-for-word — paraphrase
naturally in your own voice. The numbers quoted below are the actual output
of the fixed random seed in `01_generate_synthetic_data.py` as shipped — if
you run the scripts unmodified, your screen will show these exact figures.

Target length: 25-35 minutes of this content, stretching naturally to
35-45 minutes with good pacing — hovering before every click, narrating
what you're about to click and why, a ~1 second pause after each click, and
the live Power BI build at the end.

---

## 1. Use case and objective

*[Have VS Code open to this folder, nothing else running yet.]*

"Today's use case is a root-cause and sentiment driver analysis on customer
survey feedback. The business problem is simple to state and hard to solve
well: CSAT has room to improve, we have thousands of open-text survey
responses across chat, email and voice, and leadership wants to know **why**
— not just a number, but which specific, fixable issue is driving it, so we
know what to prioritize.

My objective here is to take raw customer verbatim, systematically tag each
response against a known root-cause taxonomy, score the sentiment of each
response, and roll all of that up into a ranked view of
which driver has the biggest impact on CSAT — broken down by channel, line
of business, agent tenure, and even over time — so the business gets an
actionable story, not just a dashboard full of numbers."

## 2. Input data

*[Open `input/input_survey_verbatims.xlsx` — if it doesn't exist yet, run
`01_generate_synthetic_data.py` first, live, since that's part of the
pipeline.]*

"This is the input — a survey export of customer responses. For this
walkthrough I'm using a synthetic dataset built to the same shape as a real
export: 7,500 responses, spanning August through October, with a
deliberately minimal set of columns — a date, a unique response ID, the
channel it came in on, the line of business, the customer's own words, the
CSAT score, who handled it — agent, team lead, manager, tenure — and two
more customer-master attributes: plan tier — five tiers, Basic through
Elite — and telecom circle, covering all 23 licensed service areas across
the country. I deliberately kept this to fields that are genuinely
realistic on a survey export — plan tier and circle are customer-master
attributes a survey platform routinely pre-joins by customer ID. I'm not
including things like handle time or a resolution flag here, because those
actually live in a separate
telephony/CRM system and would need a real operational join — out of scope
for what a CSAT survey table itself would contain."

## 3. Applications I'll use

"For this task I'm using VS Code with Python for the analysis, and Power BI
for the final business-facing insight view — two applications, which is the
right scope for deeply technical work like this rather than padding the
workflow with tools I wouldn't really reach for."

## 4. What the final output looks like

"By the end of this walkthrough I'll have one Excel workbook —
`final_output_csat_insights.xlsx` — with two sheets: the full row-level
tagged data, and a single Analysis sheet where every summary table sits
right beside its own chart, so the number and the picture read together
without flipping tabs. I'll also generate a short, client-ready PowerPoint
deck summarizing the use case and the findings."

## 5. Main task — walking through the code

*[Open `02_root_cause_sentiment_analysis.py` in VS Code. Run each `# %%`
cell with Shift+Enter, one at a time. Narrate using the beats below — don't
just click through silently.]*

### Cell 0 — setup
"I'll start by importing what I need: pandas and numpy for the data
handling, `CountVectorizer` and `TfidfVectorizer` from scikit-learn for the
term-frequency and topic-modeling work, `NMF` for topic discovery, and
VADER — a lexicon-based sentiment scorer. File paths for input,
intermediate, and the final output workbook are all set up front."

### Cell 1 — load the data
"I load the survey export and check its shape — in this run that's 7,500
rows, 13 columns."

### Cell 2 — quick profiling
"Before I touch the text at all, I check the basic distributions — channel
mix, line-of-business mix, CSAT spread."

### Cell 3 — text cleaning
"Customer verbatim is messy. I normalize it: lowercase, strip anything
that isn't a letter or number, collapse extra whitespace — so a keyword
dictionary matches reliably regardless of exactly how someone typed it."

### Cell 4 — fast dictionary bootstrap, now sentiment-aware
"Here's where I'd normally spend days reading verbatims by hand. Instead I
count term frequency SEPARATELY in the low-CSAT responses and the
high-CSAT responses, and compare the two — that's important, because a word
like 'agent' or 'issue' shows up constantly in BOTH happy and unhappy text,
and a plain frequency count can't tell the difference. By splitting it, I
can label every candidate term's sentiment lean — negative-leaning,
positive-leaning, or neutral/mixed — so the shortlist I hand off to Cell 5
is actually signal, not noise. This comparison table is saved as the task's
intermediate artifact, so there's a clear, inspectable trail for why each
term did or didn't make it into the dictionary."

### Cell 5 — the root-cause dictionary
"Here's the finished dictionary — a two-level taxonomy. Eleven broad
primary categories cover the kind of problem — Billing & Charges, Agent
Behavior & Communication, Resolution Time, Network & Connectivity,
Recharge & Plan Issues, Activation & Porting Delay, Refund Processing,
App & Website Technical, KYC & Documentation, Customer Effort, and Repeat
Contact. Underneath each one, a set of specific, named sub-issues — 42 in
total — cover exactly what the problem was: 'Incorrect Late Fee' or
'Excessive Hold Time', not just a vague theme. This dictionary counts how
many distinct phrases match per response at the sub-issue level, not just
whether one did — the strongest sub-issue's PARENT category becomes the
primary driver, and the sub-issue itself becomes the secondary driver, so
a response doesn't just get tagged 'Billing_Charges', it gets tagged
'Billing_Charges / Duplicate Charge' — something the client can actually
go fix."

### Cell 6 — sentiment scoring
"For sentiment I use VADER — a rules-and-lexicon model. Deterministic,
explainable, fully offline, no external API call — which matters
specifically because LLM-API usage hasn't been confirmed as permitted for
this engagement yet."

### Cell 7 — primary and secondary driver, ranked by strength
"I rank the matched sub-issues by how many distinct phrases hit — the
strongest match's PARENT category becomes the PRIMARY driver, and the
sub-issue itself becomes the SECONDARY driver. Where nothing matched, I
fall back to sentiment rather than force a wrong tag. I also roll every
primary category up into a higher-level issue theme — Agent, Product, or
Process — so I can tell the business right away whether this is a
coaching problem, an engineering problem, or an operations problem, before
drilling into the specific driver at all."

### Cell 7b — the rare residual safety net
"With a 42-entry specific sub-issue dictionary, the vast majority of
negative responses now get a clean, specific secondary driver straight out
of Cell 7 — in this run, essentially all of them. For the rare
edge-of-vocabulary case that still matches nothing, I complement it with
unsupervised topic modeling: TF-IDF turns that leftover text into a
weighted-term vector, NMF — non-negative matrix factorization, the same
family of technique as LDA — discovers a latent sub-theme directly from
the text with no labels needed, and I auto-generate a short, readable name
for it using YAKE, a lightweight, offline, unsupervised keyword-extraction
library. No AI, no API, no corpus download. The result: even that rare
fallback case ends up with a concrete secondary driver, not a blank."

### Cell 8 — CSAT across every category, plus the drill-down view
"I don't stop at one cut. I run the same volume-and-avg-CSAT view across
every dimension we have — issue theme (Agent/Product/Process), primary
driver, secondary driver, channel, line of business, agent tenure,
manager, team lead, sentiment label, a classic NPS-style CSAT bucket
(Promoter for a 4 or 5, Neutral for a 3, Detractor for a 1 or 2), plan
tier, and telecom circle. That's depth, not just a headline number — and
it means I can tell the client which customer SEGMENTS are
underperforming, not just which agents.

I also build a drill-down view specifically within the top primary
driver — of the responses where Billing & Charges is the issue, which
EXACT sub-issue shows up most, and what percent of Billing's own
complaints it accounts for. That's the specific, named thing to go fix,
not just a broad category. And I cross-check the CSAT score bucket against
the text sentiment label, because the two don't always agree — some
Promoters still write negative-sounding text, which is itself a real
finding."

### Cell 9 — saving the output
"One Excel workbook: the raw tagged data on one sheet, and every summary
table together on a single Analysis sheet, each with its own chart placed
right beside it — sixteen tables and charts in this run, every chart
pairing response VOLUME with average CSAT, with data labels switched on so
the numbers are readable straight off the chart, not just the table beside
it. Bold headers, wide columns, and each table-plus-chart pair sized to be
fully visible on screen without scrolling. Fully reproducible — rerun the
script, everything regenerates."

### Cell 10 — the numbers I'll quote
"To summarize what the data is telling us: **Billing & Charges is the top
primary driver, at 20.8 percent of all responses**, with an average CSAT
of 2.51 — clearly the worst-performing driver. Within Billing complaints
specifically, Duplicate Charge is the single most common sub-issue,
showing up in 22.0 percent of Billing's own complaints — that's the
specific, named thing to go fix, not a vague theme. Overall average CSAT
across the dataset is 2.86 out of 5 — a real split, not a crisis but a
genuine, fixable opportunity — and 37.6 percent of all responses carry
negative sentiment in the text itself. Cutting it by segment: North East
is the lowest-performing circle at an average CSAT of 2.78, and the
Elite plan tier the lowest-performing tier at 2.82 — two segment-level
leads worth investigating alongside the process fix.

[Numbers shift slightly run to run as the taxonomy/templates evolve —
always read these off the live Cell 10 printout rather than reciting this
script's numbers from memory.]"

## 6. Output file walkthrough

*[Switch to Excel. Open `final_output/final_output_csat_insights.xlsx`.]*

"Tagged_Data has every response with its sentiment score, matched drivers,
primary and secondary driver, issue theme, tenure bucket, and CSAT bucket.
Analysis has every aggregated table — issue theme, primary driver,
secondary driver, the sub-issue drill-down within the top primary driver,
CSAT cut by channel/LoB/tenure/manager/team-lead/sentiment/CSAT-bucket/
plan-tier/circle, and the weekly trend of the top primary and secondary
driver — each one with its own chart sitting right beside it."

## 7. The PowerPoint summary

*[Run `03_generate_summary_ppt.py`, then open
`final_output/usecase1_csat_summary.pptx`.]*

"I also generate a short client-ready deck — six slides: the use case,
the data, the approach, and the actual outcomes with the real numbers we
just walked through, plus a recommendation slide. Every number on it is
pulled straight from the output workbook, not hand-typed, so it can never
drift out of sync with what the data actually shows."

## 8. Insights in Power BI

*[Switch to Power BI Desktop. Follow `powerbi_build_guide.md` to build the
report live — don't skip this, it's part of the recorded task.]*

"Now I'll take this into Power BI to build the business-facing view, loading
the Tagged Data sheet as my source."

*[Build the visuals per the guide, narrating each one as you add it.]*

"So pulling this together: Billing & Charges is our number one CSAT driver
by volume and severity, Duplicate Charge is the specific, named sub-issue
driving it in just over a fifth of its own complaints, newer agents
disproportionately link to Agent Behavior complaints, Voice is our
highest-risk channel, and North East and the Elite plan tier are the
lowest-performing segments. If I were presenting this to the business, my
recommendation would be: investigate duplicate billing charges first,
since it's the highest-volume, lowest-CSAT, most specific driver, pair it
with a coaching initiative for agents under six months' tenure, and take a
closer look at the North East circle specifically."

## 9. Close

"That's the end-to-end workflow — from raw customer verbatim, through a
dictionary-and-topic-modeling root-cause tag, sentiment scoring, a
segment-enriched, multi-dimensional insight view, to a
client-ready deck and a Power BI report, all without needing a single LLM
API call, which matters given where API approval currently stands for this
engagement."

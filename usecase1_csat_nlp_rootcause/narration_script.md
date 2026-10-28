# Narration Script — CSAT Root-Cause & Sentiment Driver Analysis
Full talk track for the recording. Deliberately starts at the use-case
introduction — **your own personal/role introduction is not included here**;
do that yourself in your own words at the very start of the recording, since
only you know what's accurate to say and this script shouldn't be guessing it
on your behalf.

Read this as a guide, not a strict script to recite word-for-word — paraphrase
naturally in your own voice. The numbers quoted below are the actual output
of the fixed random seed in `01_generate_synthetic_data.py` as shipped — if
you run the scripts unmodified, your screen will show these exact figures.

Target length: 25-35 minutes of this content, stretching naturally to
35-45 minutes once you add the required pacing — hovering before every
click, narrating what you're about to click and why, a ~1 second pause after
each click, and the live Power BI build at the end.

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
response against a small set of known root-cause drivers, score the
sentiment of each response, and roll all of that up into a ranked view of
which driver has the biggest impact on CSAT — broken down by channel, line
of business, agent tenure, and even over time — so the business gets an
actionable story, not just a dashboard full of numbers."

## 2. Input data

*[Open `input/input_survey_verbatims.xlsx` — if it doesn't exist yet, run
`01_generate_synthetic_data.py` first, on camera, since that's part of the
pipeline.]*

"This is the input — a survey export of customer responses. For this
walkthrough I'm using a synthetic dataset built to the same shape as a real
export: 7,500 responses, spanning August through October, with a
deliberately minimal set of columns — a date, a unique response ID, the
channel it came in on, the line of business, the customer's own words, the
CSAT score, who handled it — agent, team lead, manager, tenure — and three
more customer/survey-platform attributes: plan tier, telecom circle, and
survey type — post-interaction versus a periodic relationship survey. I
deliberately kept this to fields that are genuinely realistic on a survey
export — plan tier and circle are customer-master attributes a survey
platform routinely pre-joins by customer ID, and survey type is captured
natively by the platform itself. I'm not including things like handle time
or a resolution flag here, because those actually live in a separate
telephony/CRM system and would need a real operational join — out of scope
for what a CSAT survey table itself would contain."

## 3. Applications I'll use

"For this task I'm using VS Code with Python for the analysis, and Power BI
for the final business-facing insight view — two applications, which is the
right scope for deeply technical work like this rather than padding the
workflow with tools I wouldn't really reach for."

## 4. What the final output looks like

"By the end of this walkthrough I'll have one Excel workbook —
`final_output_csat_insights.xlsx` — with three sheets: the full row-level
tagged data, every summary cut together on one Summary sheet, and every
chart together on a Charts sheet. I'll also generate a short, client-ready
PowerPoint deck summarizing the use case and the findings."

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
"Here's the finished dictionary — three business drivers: Billing &
Charges, Agent Behavior & Communication, and Resolution Time / First-Call
Resolution, each with the phrases that signal that issue. This dictionary
counts how many distinct phrases match per response, not just whether one
did — that match strength is what lets me rank a primary versus a secondary
driver in a few cells' time."

### Cell 6 — sentiment scoring
"For sentiment I use VADER — a rules-and-lexicon model. Deterministic,
explainable, fully offline, no external API call — which matters
specifically because LLM-API usage hasn't been confirmed as permitted for
this engagement yet."

### Cell 7 — primary and secondary driver, ranked by strength
"A response can mention more than one issue. I rank the matched drivers by
how many distinct phrases hit — the strongest becomes the PRIMARY driver,
the next strongest the SECONDARY driver, the compounding factor worth
acting on alongside the headline issue. Where nothing matched, I fall back
to sentiment rather than force a wrong tag."

### Cell 7b — making the secondary driver actually actionable
"Here's the thing: on short survey text, a second DISTINCT keyword phrase
often just isn't there, even when a second issue genuinely is — so the
dictionary alone mostly comes back empty for the secondary driver, which
isn't something a client can act on. So I complement it with unsupervised
topic modeling: TF-IDF turns every 'unexplained' negative response into a
weighted-term vector, NMF — non-negative matrix factorization, the same
family of technique as LDA — discovers a handful of latent sub-themes
directly from that text with no labels needed, and I auto-generate a short,
readable name for each discovered theme using YAKE, a lightweight, offline,
unsupervised keyword-extraction library. No AI, no API, no corpus download.
The result: every negative response ends up with a concrete secondary
driver, not a blank."

### Cell 8 — CSAT across every category, plus the compounding view
"I don't stop at one cut. I run the same volume-and-avg-CSAT view across
every dimension we have — primary driver, secondary driver, channel, line
of business, agent tenure, manager, team lead, sentiment label, a classic
NPS-style CSAT bucket (Promoter for a 4 or 5, Neutral for a 3, Detractor
for a 1 or 2), plan tier, telecom circle, and survey type. That's depth,
not just a headline number — and it means I can tell the client which
customer SEGMENTS are underperforming, not just which agents.

I also build the compounding-issue view — of the responses where Billing is
the primary driver, what percent of the time is a given secondary driver
also present — shown in percentages. And I cross-check the CSAT score
bucket against the text sentiment label, because the two don't always agree
— some Promoters still write negative-sounding text, which is itself a real
finding."

### Cell 9 — saving the output
"One Excel workbook: the raw tagged data on one sheet, every summary table
on a second, every chart on a third — sixteen charts in this run, every
one of them pairing response VOLUME with average CSAT so you can see both
how often an issue happens and how badly it hurts satisfaction at the same
time. Fully reproducible — rerun the script, everything regenerates."

### Cell 10 — the numbers I'll quote
"To summarize what the data is telling us: **Billing & Charges is the top
primary driver, at 32.2 percent of all responses**, with an average CSAT of
2.50 — clearly the worst-performing driver. Within Billing complaints
specifically, a discovered sub-theme around being charged shows up as the
secondary, compounding factor **72.1 percent of the time** — that's the
specific thing to go investigate alongside the headline issue. Overall
average CSAT across the dataset is 3.01 out of 5 — a real split, 38.4
percent Promoters against 38.0 percent Detractors, not a crisis but a
genuine, fixable opportunity — and just over half of all responses, 50.3
percent, carry negative sentiment in the text itself. Cutting it by segment:
Delhi NCR is the lowest-performing circle at an average CSAT of 2.96, and
Postpaid Standard the lowest-performing plan tier at 2.90 — two
segment-level leads worth investigating alongside the process fix."

## 6. Output file walkthrough

*[Switch to Excel. Open `final_output/final_output_csat_insights.xlsx`.]*

"Tagged_Data has every response with its sentiment score, matched drivers,
primary and secondary driver, tenure bucket, and CSAT bucket. Summary has
every aggregated table in one place — primary driver, secondary driver, the
primary-to-secondary compounding percentages, CSAT cut by channel/LoB/
tenure/manager/team-lead/sentiment/CSAT-bucket, and the weekly trend of the
top primary and secondary driver. Charts has all thirteen charts together."

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
by volume and severity, a billing/charge-clarity sub-theme is the specific
compounding factor within it 72 percent of the time, newer agents
disproportionately link to Agent Behavior complaints, Voice is our
highest-risk channel, and Delhi NCR and the Postpaid Standard tier are the
lowest-performing segments. If I were presenting this to the business, my
recommendation would be: investigate the billing-charge clarity issue
first, since it's the highest-volume, lowest-CSAT driver, pair it with a
coaching initiative for agents under six months' tenure, and take a closer
look at the Delhi NCR circle specifically."

## 9. Close

"That's the end-to-end workflow — from raw customer verbatim, through a
dictionary-and-topic-modeling root-cause tag, sentiment scoring, a
segment-enriched, multi-dimensional insight view, to a
client-ready deck and a Power BI report, all without needing a single LLM
API call, which matters given where API approval currently stands for this
engagement."

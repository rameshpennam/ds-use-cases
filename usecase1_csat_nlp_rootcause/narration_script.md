# Narration Script — CSAT Root-Cause & Sentiment Driver Analysis
Full talk track for the recording. Deliberately starts at the use-case
introduction — **your own personal/role introduction is not included here**;
do that yourself in your own words at the very start of the recording, since
only you know what's accurate to say and this script shouldn't be guessing it
on your behalf.

Read this as a guide, not a strict script to recite word-for-word — paraphrase
naturally in your own voice. The numbers quoted below (e.g. "29.8%", "avg
CSAT 1.53") are the actual output of the fixed random seed in
`01_generate_synthetic_data.py`, so if you run the scripts as shipped, your
screen will show these exact figures. Pacing notes in *[italics]* are timing/
action cues, not things to say out loud.

Target length: 25-35 minutes of this content, stretching naturally to
35-45 minutes once you add the required pacing — hovering before every
click, narrating what you're about to click and why, a ~1 second pause after
each click, and the live Power BI build at the end.

---

## 1. Use case and objective

*[Have VS Code open to this folder, nothing else running yet.]*

"Today's use case is a root-cause and sentiment driver analysis on customer
survey feedback. The business problem is simple to state and hard to solve
well: CSAT scores are down, we have thousands of open-text survey responses
across chat, email and voice, and leadership wants to know **why** — not
just that satisfaction is low, but which specific, fixable issue is driving
it, so we know what to prioritize.

My objective here is to take raw customer verbatim, systematically tag each
response against a small set of known root-cause drivers, score the
sentiment of each response, and roll all of that up into a ranked view of
which driver has the biggest impact on CSAT — broken down by channel, by
line of business, and even by agent tenure, so the business gets an
actionable story, not just a dashboard full of numbers."

## 2. Input data

*[Open `input/input_survey_verbatims.xlsx` — if it doesn't exist yet, run
`01_generate_synthetic_data.py` first, on camera, since that's part of the
pipeline.]*

"This is the input — a survey export of customer responses. For this
walkthrough I'm using a synthetic dataset built to the same shape as a real
export, up to 10,000 responses, with a deliberately minimal set of columns:
a date, a unique response ID, the channel the response came in on — chat,
email, or voice — the line of business, the customer's own words in the
`verbatim` column, the CSAT score they gave, and who handled it: agent name,
team lead, and manager, plus the agent's tenure in months.

I kept this to the columns that actually earn their place. I don't need
twenty fields to do a root-cause analysis — I need the text, the outcome
score, and enough org/channel context to slice the findings afterward."

## 3. Applications I'll use

"For this task I'm using two applications: VS Code with Python for the
analysis itself, and Power BI for the final business-facing insight view.
This is a deeply technical, code-driven task, so I'm keeping it to the two
applications that actually do the work, rather than padding the workflow
with tools I wouldn't really reach for."

## 4. What the final output looks like

"By the end of this walkthrough I'll have one Excel workbook —
`final_output_csat_insights.xlsx` — with four sheets: the full row-level
tagged dataset, a driver summary table with charts, a channel-by-driver
breakdown, and an agent-tenure breakdown. That becomes the handoff artifact,
and it's also what I load into Power BI for the final narrative."

## 5. Main task — walking through the code

*[Open `02_root_cause_sentiment_analysis.py` in VS Code. Run each `# %%`
cell with Shift+Enter, one at a time. Narrate using the beats below — don't
just click through silently.]*

### Cell 0 — setup
"I'll start by importing what I need: pandas and numpy for the data
handling, a `CountVectorizer` from scikit-learn, which I'll use in a minute
to statistically surface candidate keywords, and VADER — a lexicon-based
sentiment scorer — for sentiment. I'm also setting my file paths up front,
input, intermediate, and the final output workbook, so the whole pipeline is
self-contained and reproducible."

### Cell 1 — load the data
"Now I load the survey export and take a first look at its shape — in this
run that's 4,000 rows, 10 columns. Before I do anything clever, I always
look at the raw data first."

### Cell 2 — quick profiling
"Before I touch the text at all, I check the basic distributions — how many
responses per channel, per line of business, and the CSAT score spread. This
tells me where the volume actually is before I start interpreting anything."

### Cell 3 — text cleaning
"Customer verbatim is messy — different capitalization, punctuation,
spacing. I normalize it: lowercase everything, strip out anything that isn't
a letter or number, and collapse extra whitespace. This is what lets a
keyword dictionary match reliably regardless of exactly how the customer
typed their response."

### Cell 4 — fast dictionary bootstrap
"Here's the part that normally eats days of effort on a project like this.
The traditional way to build a root-cause keyword dictionary is to sit down
and read hundreds of verbatims by hand, note the recurring phrases, and
slowly build your taxonomy. Instead, I take a shortcut that gets me most of
the way there in minutes: I filter down to just the low-CSAT responses — a
1 or 2 out of 5 — and run a frequency count across single words and two-word
phrases in that subset only. Whatever shows up most often in **specifically
the unhappy customers** is my shortlist. I'm looking at the output now —
terms like 'charged', 'activation', 'network issue', 'sim swap request' jump
right out. That shortlist is what I turn into a proper dictionary in the
next step, and I save this list as the task's intermediate artifact, so
there's a clear evidence trail for how the dictionary was derived, not just
a dictionary that appeared from nowhere."

### Cell 5 — the root-cause dictionary
"Here's the finished dictionary — three business drivers, each with the
phrases I know, from the step above plus domain knowledge, signal that
issue: **Billing & Charges** — things like 'charged twice', 'incorrect
bill', 'not refunded'; **Agent Behavior & Communication** — 'rude',
'interrupting', 'put on hold', 'transferred me'; and **Resolution Time and
First-Call Resolution** — 'still not resolved', 'ticket reopened', 'no
update'. This dictionary is the only thing that needs to change if a future
wave of data surfaces a new issue type — everything downstream is generic."

### Cell 6 — sentiment scoring
"For sentiment, I'm using VADER — a rules-and-lexicon-based sentiment model.
It's deterministic and fully explainable: no black box, no external API
call, it runs entirely offline. That matters here specifically because
LLM-API usage hasn't been confirmed as permitted for this engagement yet, so
I'm deliberately staying inside tooling that doesn't depend on that
approval. Every response gets a sentiment score from -1 to +1, which I bucket
into Negative, Neutral, and Positive."

### Cell 7 — resolving one primary driver per response
"A single response can mention more than one issue — someone might complain
about being overcharged **and** about a rude agent in the same sentence. I
keep the full list of matches, but I also resolve a single primary driver
per response, using a priority order, because that's what makes a clean
pivot or Power BI view possible. If nothing in the dictionary matched but
the sentiment is negative, I bucket it as 'Other, Unclassified' rather than
forcing it into one of my three known drivers — an honest gap is better than
a wrong tag."

### Cell 8 — the aggregated views
"Now I roll this up. In this run, **Billing & Charges is the top driver,
responsible for roughly 30 percent of all responses**, with an average CSAT
of about 1.5 out of 5 — that's the worst-performing driver in the dataset.
Agent Behavior is close behind at around 27 percent. I also look at average
agent tenure by driver — agents linked to the Agent Behavior driver skew
noticeably newer than agents linked to positive responses, about six months
less tenure on average, which is a real coaching/onboarding signal. And I
cross-tab driver against channel — Voice carries a disproportionate share of
both Agent Behavior and Resolution-Time complaints compared to Chat and
Email, which makes sense: those are exactly the kinds of issues that surface
in a live, synchronous conversation."

### Cell 9 — saving the output
"Instead of a flat CSV, I'm publishing one Excel workbook with the raw
tagged data on one sheet, and ready-made insight tables with embedded charts
on the others. This is fully reproducible — every time I rerun this script,
every sheet and every chart regenerates from the current data, so there's
never a stale, hand-edited copy floating around for someone to trip over
later."

### Cell 10 — the numbers I'll quote
"So, to summarize what the data is telling us: the top driver is Billing
and Charges, at roughly 30 percent of responses, with an average CSAT of
1.5. Overall average CSAT across the dataset is about 2.2 out of 5, and
just over half of all responses — about 52 percent — carry negative
sentiment. That's the headline."

## 6. Output file walkthrough

*[Switch to Excel. Open `final_output/final_output_csat_insights.xlsx`.]*

"Here's the output workbook. The first sheet, Tagged Data, is the full
row-level dataset — every response with its sentiment score, its matched
drivers, and its resolved primary driver. The Driver Summary sheet has the
aggregated table plus two charts — responses by driver, and average CSAT by
driver — so you can see at a glance that Billing dominates both the volume
and the severity. Channel by Driver shows the stacked view I just
described, and Tenure by Driver shows the agent-tenure pattern."

## 7. Insights in Power BI

*[Switch to Power BI Desktop. Follow `powerbi_build_guide.md` to build the
report live — don't skip this, it's part of the recorded task.]*

"Now I'll take this into Power BI to build the business-facing view. I'm
loading the Tagged Data sheet as my source, and I'm going to build a small
set of visuals that tell this story at a glance: total responses and
average CSAT by driver, a channel breakdown, a trend of Billing complaints
over time, and the tenure comparison."

*[Build the visuals per the guide, narrating each one as you add it — field
by field, the same "name what you're clicking" discipline as the Python
walkthrough.]*

"So pulling this together: Billing & Charges is our number one CSAT driver,
it's concentrated specifically in Postpaid Mobile and Billing & Payments,
newer agents are disproportionately linked to Agent Behavior complaints, and
Voice is our highest-risk channel for both Agent Behavior and unresolved
issues. If I were presenting this to the business, my recommendation would
be: investigate the billing accuracy issue first, since it's both the
highest-volume and lowest-CSAT driver, and pair it with a coaching
initiative for agents under six months' tenure, since that's where the
Agent Behavior complaints concentrate."

## 8. Close

"That's the end-to-end workflow — from raw customer verbatim, to a
dictionary-based root-cause tag, to sentiment scoring, to a ranked,
channel-and-tenure-aware insight view in Power BI, all without needing a
single LLM API call, which matters given where API approval currently
stands for this engagement."

# ML + NLP + GenAI Recommendation Pipeline

One script (`run_pipeline.py`) that reads the synthetic ads data from
`../ads-data/`, runs it through ML, NLP, and GenAI stages, and produces a
real customer-facing recommendation email PDF per account. **This is a
separate, deeper pipeline on top of `../scripts/generate_emails.py`** --
that script hand-writes the email copy per account; this one derives
everything (diagnosis, market "why now" case, email copy) live from a
single LLM call per stage, grounded in the same underlying ads data and
market-report PDFs.

**Everything downstream is still synthetic** -- same watermark, same
no-real-vendor-names rule as the rest of `pilot-synthetic-data/`.

## Why three different tech stacks, not one

Each stage below uses the tool actually suited to the job, not one
technology stretched to cover everything:

| Stack | Where | What it does | Why not GenAI here |
|---|---|---|---|
| **ML** (scikit-learn, scipy) | Step 3 | Pearson correlation of every numeric column against missed impressions, IsolationForest anomaly scoring, KMeans clustering, materiality ranking | Cheap, deterministic, and exact -- no reason to ask an LLM to estimate a correlation coefficient |
| **NLP** (TF-IDF + cosine similarity) | Step 7 | Scores every fact extracted from the 4 market-report PDFs against *this account's own* diagnosis text, keeps only the closest matches | A classic retrieval problem -- find the most relevant few facts out of ~70 extracted rows -- that's cheaper and more precise with vector similarity than asking a model to read all 70 and guess |
| **GenAI** (OpenAI, structured outputs) | Steps 6, 8, 9 | Forms the account diagnosis from raw campaign data + ML evidence; builds the "why now" case from the NLP-shortlisted market facts; writes the email copy | These three are genuinely open-ended natural-language reasoning and writing tasks -- the one place an LLM is the right tool |

GenAI is never used to *validate* the ML output or just rephrase numbers --
each GenAI call forms its own judgment from raw evidence it's handed, and
the prompts are explicit about that (see `STAGE6_SYSTEM`, `STAGE8_SYSTEM`,
`STAGE9_SYSTEM` in `run_pipeline.py`).

## What stays deterministic, never delegated to the LLM

The headline revenue-opportunity figure and each campaign's dollar share of
it (`account_rollup()`) are computed once in Python straight from
`campaigns.csv`. Every GenAI call is handed these exact, pre-formatted
figures with an explicit "use verbatim, do not recompute" instruction --
the LLM never does the arithmetic, so every dollar amount in the final
email traces back to the CSV, not to a model's guess.

## The 11 steps, one line each

1. **Read input data** -- load `ads-data/campaigns.csv`.
2. **Pre-processing** -- slice to one account, add the `missed` (eligible −
   actual impressions) column every later step needs.
3. **EDA / ML** -- Pearson correlations vs. missed impressions, IsolationForest
   anomaly scores, KMeans clusters, and the materiality ranking (the ~70%-of-
   the-gap subset of campaigns, not all of them).
4. **Parse market PDFs** -- real `pdfplumber` table extraction from the 4
   vendor-style PDFs in `../market-reports/` (not read from `benchmarks.py` --
   a production pipeline only has the PDFs).
5. **Pydantic schemas** -- the structured-JSON contract for every GenAI call.
6. **GenAI: ads-data analysis** -- one LLM call forms its own diagnosis
   (rank-constrained / budget-constrained / healthy) from the raw campaign
   data plus the step-3 statistics as evidence.
7. **NLP: relevance ranking** -- TF-IDF + cosine similarity ranks every
   extracted market fact against this account's step-6 diagnosis text;
   only the closest matches move on.
8. **GenAI: market mapping** -- one LLM call builds the "why now" case from
   the NLP-shortlisted facts, citing the vendor and number for each.
9. **GenAI: email copy** -- one LLM call drafts the actual customer email:
   hook, "why now" bullets, the headline stat, a fix with a low-friction ask.
10. **Render PDF** -- build the email as a real PDF, reusing the existing
    reportlab layout helpers in `../scripts/pdf_common.py`.
11. **Validation report** -- token/cost totals and a per-account summary,
    written to `output/validation_report.md`.

Steps 6, 7, 8, 9 run once per account (3 accounts = 9 GenAI calls + 3 NLP
rankings per full run).

## Model selection

Single OpenAI model for every GenAI stage, set once as `MODEL` near the top
of `run_pipeline.py`. Deliberately single-provider and single-model:

- **One vendor** -- getting a second provider's API key approved inside an
  enterprise is its own procurement process; this only ever needs one
  credential (`OPENAI_API_KEY`).
- **One model constant, not one per stage** -- a future provider or model
  swap is then a one-line change in this file, not a hunt through every
  call site.

The model ID (`gpt-5.2` at the time this was built) was confirmed live
against this key's own `client.models.list()` call, not guessed -- model
availability changes faster than any assistant's training data, so the
script trusts the API's own model listing over assumed names.

## Run

```
cd llm-pipeline
python run_pipeline.py
```

Needs `OPENAI_API_KEY` set in the environment, or present in
`../../backend/.env` (the script reads it from there automatically --
see `_load_env_from_backend()`). Nothing else needs to change to switch
keys or orgs.

Output lands in `output/`: one `{account_id}_full_result.json` (every
stage's structured output, for inspection/debugging), one
`recommendation_email_llm_{vertical}_{country}.pdf` per account, and
`validation_report.md`.

## Relationship to `../scripts/generate_emails.py`

That script is the hand-authored baseline shipped with the synthetic-data
package -- fixed copy per account, used to prove the data model end to end.
This pipeline is the "full solution" version: it re-derives the diagnosis,
the market "why now" case, and the email copy live from the same
underlying data, through real ML + NLP + GenAI stages, rather than reading
pre-written copy. Both read the same `campaigns.csv` and the same 4 market
PDFs, so their outputs are directly comparable.

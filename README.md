# Data Science & ML — Use Case Portfolio

A growing collection of self-contained, end-to-end data science use cases.
Each folder is independent — `requirements.txt`, three runnable scripts, a
full walkthrough script, and a Power BI build guide. Currently:

| Folder | Use case |
|---|---|
| `usecase1_csat_nlp_rootcause/` | NLP root-cause & sentiment driver analysis on customer survey verbatim (chat/email/voice) |
| `usecase2_demand_forecasting/` | Contact-volume forecasting → required staffing (FTE) vs current roster |

## Per use case, in order
No virtual environment needed (dedicated single-purpose machine, nothing to
conflict with) — just:
1. `pip install --user -r requirements.txt` (Mac: `pip3 install --user ...`)
2. `python 01_generate_synthetic_data.py` (Mac: `python3 ...`) — produces
   the `input/` files
3. Open `02_*.py` in VS Code (Python extension), run **cell by cell** —
   click "▷ Run Cell" above each `# %%` block, or Shift+Enter to run +
   auto-advance — produces `intermediate/` and `final_output/` files
4. `python 03_generate_summary_ppt.py` — builds a 6-slide client-ready
   summary deck in `final_output/`, every number pulled straight from the
   Excel output (nothing hand-typed)
5. `narration_script.md` — a full word-for-word walkthrough script for
   presenting the use case (does not include a personal introduction —
   add your own at the start)
6. `powerbi_build_guide.md` — exact visuals/DAX to build live in Power BI
   on top of the `final_output/*.xlsx` workbook
7. `README_narration_and_metadata.md` — folder layout and setup notes for
   that use case

## Notes
- API usage (Gemini/OpenAI/Anthropic) is optional — both pipelines
  currently use only offline, non-AI techniques (keyword dictionaries,
  TF-IDF/NMF, VADER, classical statistical forecasting), so they run with
  zero API keys. See each use case's README for the disabled opt-in cell
  if you want to wire one in.
- `input/`, `intermediate/`, `final_output/` ARE committed to this repo as a
  known-good reference snapshot — a safety net if Python/pip isn't set up
  yet on whatever machine you're running this on. They're also fully
  reproducible (fixed random seed) — just re-run the scripts to regenerate
  them; don't hand-edit anything inside them, your changes get overwritten
  on the next run.

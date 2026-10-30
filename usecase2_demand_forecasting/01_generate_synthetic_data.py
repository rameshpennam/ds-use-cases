"""
01_generate_synthetic_data.py
------------------------------
Generates synthetic contact-volume history (~3.8 years, daily, by LoB and
channel) and an agent roster for the Demand Forecasting & Staffing use case.

Run once, top to bottom (VS Code: "Run Cell" above each "# %%" block, or
Shift+Enter), to produce:
  input/input_call_volume_history.xlsx
  input/input_agent_roster.xlsx

NOTE: All names, volumes and IDs below are synthetic / fictional, generated
purely for this demo. No real customer, agent or company data is used.
"""

# %% Cell 0 - Imports & config
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RANDOM_SEED = 7
rng = np.random.default_rng(RANDOM_SEED)

START_DATE = datetime(2023, 10, 26)
END_DATE = datetime(2026, 10, 26)     # 3 years of history, capped (was ~3.8) -
# at 4 LoBs x 3 channels/day this is ~13,140 rows, close to the ~15k target
LOBS = ["Postpaid Mobile", "Prepaid Mobile", "Broadband", "Billing & Payments"]  # same 4 LoBs as use case 1
CHANNELS = ["Voice", "Chat", "Email"]

OUT_VOLUME_FILE = "input/input_call_volume_history.xlsx"
OUT_ROSTER_FILE = "input/input_agent_roster.xlsx"

dates = pd.date_range(START_DATE, END_DATE, freq="D")

# %% Cell 1 - Holidays & campaign weeks (drives realistic spikes)
# NARRATE: "Real contact-center volume isn't random - it spikes around
# holidays and marketing campaigns, so I bake both into the synthetic data."
HOLIDAYS = pd.to_datetime(
    [f"{y}-01-01" for y in range(2023, 2027)]
    + [f"{y}-10-24" for y in range(2023, 2027)]   # festive-season week
    + [f"{y}-12-25" for y in range(2023, 2027)]
)

campaign_weeks = rng.choice(dates.to_numpy(), size=24, replace=False)
CAMPAIGN_DATES = {pd.Timestamp(d) for d in campaign_weeks}


def expand_campaign_window(d, days=range(7)):
    return {d + timedelta(days=o) for o in days}


CAMPAIGN_DATE_SET = set()
for d in CAMPAIGN_DATES:
    CAMPAIGN_DATE_SET |= expand_campaign_window(d)

# %% Cell 2 - Build the daily volume curve per LoB/channel
# NARRATE: "I build the series from its parts - a base level, a slow trend,
# weekly seasonality (lower on Sundays), yearly seasonality (a festive-season
# bump), holiday spikes, campaign spikes, and random noise - the same
# components a real contact-center volume series has."
BASE_LEVEL = {"Postpaid Mobile": 650, "Prepaid Mobile": 380, "Broadband": 300, "Billing & Payments": 150}
# WHAT: 4 LoBs instead of 2, matching use case 1's LoB set, but the total
# (1480) is kept close to the prior total (1400 = 900+500) on purpose - a
# like-for-like redistribution, not an added volume load - so the already
# -tuned "tight, not crisis" staffing-gap story doesn't need re-tuning
# from scratch just because the LoB split got more realistic.
CHANNEL_SPLIT = {"Voice": 0.50, "Chat": 0.30, "Email": 0.20}
AHT_SECONDS = {"Voice": 420, "Chat": 300, "Email": 240}   # avg handle time per channel

records = []
for lob in LOBS:
    base = BASE_LEVEL[lob]
    for i, d in enumerate(dates):
        trend = base * (1 + 0.00015 * i)                                   # slow organic growth
        weekly = 1.0 - (0.18 if d.day_of_week == 6 else 0.0)                 # Sunday dip
        yearly = 1 + 0.15 * np.sin(2 * np.pi * (d.day_of_year - 275) / 365)  # Oct-Dec bump
        holiday_flag = int(d.normalize() in HOLIDAYS)
        campaign_flag = int(d in CAMPAIGN_DATE_SET)
        spike = (1 + 0.35 * holiday_flag) * (1 + 0.25 * campaign_flag)
        noise = rng.normal(1.0, 0.24)   # realistic day-to-day volatility

        total_volume = max(0.0, trend * weekly * yearly * spike * noise)

        for ch, split in CHANNEL_SPLIT.items():
            vol = int(round(total_volume * split * rng.normal(1.0, 0.03)))
            records.append({
                "date": d,   # kept as a real date, not text - see Cell 3
                "lob": lob,
                "channel": ch,
                "volume": max(vol, 0),
                "aht_seconds": AHT_SECONDS[ch],
                "holiday_flag": holiday_flag,
                "campaign_flag": campaign_flag,
            })

df_volume = pd.DataFrame(records)

# %% Cell 3 - Save volume history + sanity check
import os
import openpyxl

os.makedirs("input", exist_ok=True)

# Write "date" as a real Excel date (not text) so sorting/pivoting by date
# works correctly in Excel and Power BI.
df_volume["date"] = pd.to_datetime(df_volume["date"]).dt.date
df_volume.to_excel(OUT_VOLUME_FILE, index=False, sheet_name="Call_Volume_History")

wb = openpyxl.load_workbook(OUT_VOLUME_FILE)
ws = wb["Call_Volume_History"]
date_col = list(df_volume.columns).index("date") + 1
for row in range(2, ws.max_row + 1):
    ws.cell(row=row, column=date_col).number_format = "yyyy-mm-dd"
wb.save(OUT_VOLUME_FILE)

print(f"Saved {len(df_volume)} rows -> {OUT_VOLUME_FILE}")
print(df_volume.groupby(["lob", "channel"])["volume"].mean().round(0))

# %% Cell 4 - Agent roster
# NARRATE: "I also need to know who's actually available, so I can compare
# the forecast against current staffing, not just produce a number in a vacuum."
MANAGERS = ["Rajesh Kumar", "Anita Sharma"]
TL_BY_MANAGER = {
    "Rajesh Kumar": ["Vikram Singh", "Priya Nair"],
    "Anita Sharma": ["Deepa Menon", "Arjun Rao"],
}
AGENT_FIRST = ["Aarav", "Vivaan", "Aditya", "Kabir", "Ishaan", "Rohan", "Karan", "Aryan",
               "Sanya", "Ananya", "Diya", "Meera", "Riya", "Neha", "Pooja", "Kavya",
               "Farhan", "Imran", "Zoya", "Alisha", "Arjun", "Rahul", "Sneha", "Priyanka",
               "Nikhil", "Tanvi", "Yash", "Ritu", "Siddharth", "Varun", "Ishita", "Dev",
               "Naina", "Aman", "Simran", "Rajat", "Shreya", "Harsh", "Anika", "Manish"]
AGENT_LAST = ["Verma", "Gupta", "Reddy", "Khan", "Pillai", "Shetty", "Joshi", "Mehta",
              "Chopra", "Bose", "Kapoor", "Malhotra", "Agarwal", "Bhatt", "Desai",
              "Kulkarni", "Patel", "Yadav", "Mishra", "Pandey", "Choudhury", "Sinha",
              "Ghosh", "Banerjee", "Saxena", "Trivedi", "Nambiar", "Rathore", "Dutta", "Kaur",
              "Thakur", "Chauhan", "Bhatia", "Oberoi", "Rana", "Sharma", "Srinivasan", "Iyer",
              "Menon", "Nair"]
# Sample first and last names INDEPENDENTLY without replacement, so every
# agent has both a unique first name AND a unique last name - no name
# component repeats anywhere across the roster (same fix as use case 1's
# agent_name, which had the identical "(i+1)" index-suffix issue).
_agent_first_names = rng.choice(AGENT_FIRST, size=40, replace=False)
_agent_last_names = rng.choice(AGENT_LAST, size=40, replace=False)

roster = []
for i in range(40):   # deliberately tight headcount so a genuine staffing gap shows up on peak days
    lob = rng.choice(LOBS)
    manager = rng.choice(MANAGERS)
    tl = rng.choice(TL_BY_MANAGER[manager])
    tenure = int(rng.choice(
        [2, 4, 6, 9, 12, 18, 24, 36, 48],
        p=[0.10, 0.10, 0.10, 0.12, 0.13, 0.15, 0.10, 0.10, 0.10]))
    # WHAT: shrinkage_pct - the standard contact-center metric for time an
    # agent is scheduled but NOT available to handle contacts (breaks,
    # training, coaching, short-term absence). WHY: newer agents carry more
    # training/coaching shrinkage - this gives the staffing model a REAL,
    # per-roster shrinkage figure to use instead of a flat assumed constant.
    shrinkage_pct = round(float(np.clip(rng.normal(22 - 0.15 * tenure, 4), 10, 40)), 1)

    roster.append({
        "agent_id": f"AGT{1000 + i}",
        "agent_name": f"{_agent_first_names[i]} {_agent_last_names[i]}",
        "lob": lob,
        "tl_name": tl,
        "manager_name": manager,
        "tenure_months": tenure,
        "weekly_available_hours": int(rng.choice([20, 30, 40, 40, 40])),  # some part-time
        "shrinkage_pct": shrinkage_pct,
    })

df_roster = pd.DataFrame(roster)
df_roster.to_excel(OUT_ROSTER_FILE, index=False, sheet_name="Agent_Roster")
print(f"Saved {len(df_roster)} rows -> {OUT_ROSTER_FILE}")
print(df_roster.groupby("lob")["weekly_available_hours"].sum())
print("\nAvg shrinkage:", round(df_roster["shrinkage_pct"].mean(), 1), "%")

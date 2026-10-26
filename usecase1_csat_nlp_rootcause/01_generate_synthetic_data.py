"""
01_generate_synthetic_data.py
------------------------------
Generates a synthetic customer-survey verbatim dataset (chat / email / voice)
for the CSAT Root-Cause & Sentiment Driver Analysis use case.

Run this once, top to bottom (VS Code: click "Run Cell" above each "# %%"
block, or press Shift+Enter), to produce: input_survey_verbatims.csv
This file is the single INPUT artifact consumed by
02_root_cause_sentiment_analysis.py

NOTE: All names, verbatims and IDs below are synthetic / fictional, generated
purely for this demo. No real customer, agent or company data is used.
"""

# %% Cell 0 - Imports & configuration
import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

N_RECORDS = 4000              # survey responses to simulate (cap at 10,000 per guideline)
OUTPUT_FILE = "input/input_survey_verbatims.xlsx"   # lands in the input/ subfolder
TODAY = datetime(2026, 10, 26)   # fixed "as of" date so results are reproducible
LOOKBACK_DAYS = 180

# %% Cell 1 - Org hierarchy (manager -> TL -> agent) and reference lists
MANAGERS = ["Rajesh Kumar", "Anita Sharma"]

TL_BY_MANAGER = {
    "Rajesh Kumar": ["Vikram Singh", "Priya Nair", "Suresh Iyer"],
    "Anita Sharma": ["Deepa Menon", "Arjun Rao"],
}

AGENT_FIRST = ["Aarav", "Vivaan", "Aditya", "Kabir", "Ishaan", "Rohan", "Karan", "Aryan",
               "Sanya", "Ananya", "Diya", "Meera", "Riya", "Neha", "Pooja", "Kavya",
               "Farhan", "Imran", "Zoya", "Alisha"]
AGENT_LAST = ["Verma", "Gupta", "Reddy", "Khan", "Pillai", "Shetty", "Joshi", "Mehta",
              "Chopra", "Bose"]


def build_agent_roster(n_agents=24):
    agents = []
    for i in range(n_agents):
        manager = random.choice(MANAGERS)
        tl = random.choice(TL_BY_MANAGER[manager])
        name = f"{random.choice(AGENT_FIRST)} {random.choice(AGENT_LAST)}"
        tenure_months = int(np.random.choice(
            [2, 4, 5, 8, 10, 14, 18, 24, 30, 36, 48, 60],
            p=[0.08, 0.08, 0.08, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.08, 0.07, 0.07]))
        agents.append({
            "agent_name": f"{name} ({i + 1})",
            "tl_name": tl,
            "manager_name": manager,
            "tenure_months": tenure_months,
        })
    return pd.DataFrame(agents)


AGENT_ROSTER = build_agent_roster()

LOBS = ["Postpaid Mobile", "Prepaid Mobile", "Broadband", "Billing & Payments"]
CHANNELS = ["Voice", "Chat", "Email"]

# %% Cell 2 - Root-cause vocabulary used to WRITE the synthetic verbatims
# In the analysis script we independently build a keyword dictionary and try
# to RE-DISCOVER these same root causes purely from the text + CSAT score,
# the same way we would with real survey data (no cheating / no hidden label
# is saved to the output file in Cell 4).
SERVICES = ["mobile recharge", "broadband plan", "data pack", "postpaid bill",
            "SMS pack", "international roaming add-on"]
CHARGE_TYPES = ["late fee", "service tax", "activation fee", "roaming charge"]
ISSUES = ["network issue", "billing issue", "data pack activation",
          "SIM swap request", "address update request"]

BILLING_TEMPLATES = [
    "I was charged twice for my {service} and nobody has explained why.",
    "There is an unexpected {charge_type} on my bill that I never agreed to.",
    "My {service} amount was deducted incorrectly and I have still not received my refund.",
    "The invoice shows a {charge_type} that should not be there at all.",
    "I was charged for {service} even though I never used it.",
]
AGENT_TEMPLATES = [
    "The agent was quite rude and kept interrupting me while I explained my {issue}.",
    "I had to repeat myself three times because the agent did not listen properly.",
    "I was put on hold for a long time and then the call got disconnected.",
    "The agent transferred me to three different departments without solving my {issue}.",
    "The agent sounded unprofessional and ignored my concern about my {issue}.",
]
RESOLUTION_TEMPLATES = [
    "This is the third time I am calling about the same {issue} and it is still not resolved.",
    "I was promised a callback within 24 hours but nobody followed up.",
    "My ticket for {issue} keeps getting reopened without any real resolution.",
    "I have been waiting for days and there is no update on my {issue}.",
    "The same {issue} keeps coming back even after I was told it was fixed.",
]
POSITIVE_TEMPLATES = [
    "The agent resolved my {issue} quickly and was very polite.",
    "Great service, my {service} issue was sorted out in one call.",
    "I am very satisfied, the agent was helpful and professional throughout.",
    "Quick resolution for my {issue}, thank you so much.",
    "The agent was polite and explained everything about my {service} clearly.",
]

DRIVER_TEMPLATES = {
    "Billing_Charges": BILLING_TEMPLATES,
    "Agent_Behavior_Comm": AGENT_TEMPLATES,
    "Resolution_Time_FCR": RESOLUTION_TEMPLATES,
    "Positive_No_Issue": POSITIVE_TEMPLATES,
}


def fill(template: str) -> str:
    return template.format(
        service=random.choice(SERVICES),
        charge_type=random.choice(CHARGE_TYPES),
        issue=random.choice(ISSUES),
    )


# %% Cell 3 - Core simulation loop
def pick_driver(channel: str, lob: str, tenure_months: int) -> str:
    """Weighted random driver pick, with a few deliberate real-world style
    correlations baked in so the final dataset has a genuine 'story' to
    discover later - the kind of pattern that would normally only surface
    after days of manual tagging."""
    weights = {"Billing_Charges": 0.25, "Agent_Behavior_Comm": 0.20,
               "Resolution_Time_FCR": 0.20, "Positive_No_Issue": 0.35}

    if lob in ("Billing & Payments", "Postpaid Mobile"):
        weights["Billing_Charges"] += 0.10
        weights["Positive_No_Issue"] -= 0.10

    if channel == "Voice":
        weights["Agent_Behavior_Comm"] += 0.08
        weights["Resolution_Time_FCR"] += 0.05
        weights["Positive_No_Issue"] -= 0.13

    if tenure_months < 6:
        weights["Agent_Behavior_Comm"] += 0.12
        weights["Positive_No_Issue"] -= 0.12

    drivers = list(weights.keys())
    w = np.clip(np.array(list(weights.values())), 0.02, None)
    w = w / w.sum()
    return np.random.choice(drivers, p=w)


def make_verbatim(driver: str, channel: str) -> str:
    templates = DRIVER_TEMPLATES[driver]
    sentence = fill(random.choice(templates))
    if channel == "Voice":
        sentence += " " + fill(random.choice(templates))
    if channel == "Email":
        sentence = "Hi Team, " + sentence
    return sentence


def make_csat(driver: str) -> int:
    if driver == "Positive_No_Issue":
        return int(np.random.choice([4, 5], p=[0.35, 0.65]))
    return int(np.random.choice([1, 2, 3], p=[0.55, 0.35, 0.10]))


def make_date(driver: str) -> datetime:
    # Billing complaints cluster in the last 30 days to simulate a recent
    # billing-cycle spike you can point to on a trend chart later.
    if driver == "Billing_Charges" and random.random() < 0.5:
        offset = random.randint(0, 30)
    else:
        offset = random.randint(0, LOOKBACK_DAYS)
    return TODAY - timedelta(days=offset)


records = []
for i in range(N_RECORDS):
    agent = AGENT_ROSTER.sample(1).iloc[0]
    channel = random.choices(CHANNELS, weights=[0.45, 0.35, 0.20])[0]
    lob = random.choice(LOBS)
    driver = pick_driver(channel, lob, int(agent["tenure_months"]))

    records.append({
        "date": make_date(driver).strftime("%Y-%m-%d"),
        "unique_id": f"SRV{100000 + i}",
        "channel": channel,
        "lob": lob,
        "verbatim": make_verbatim(driver, channel),
        "csat_score": make_csat(driver),
        "agent_name": agent["agent_name"],
        "tl_name": agent["tl_name"],
        "manager_name": agent["manager_name"],
        "tenure_months": int(agent["tenure_months"]),
    })

df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

# %% Cell 4 - Save + quick sanity check (this is what you show on screen)
import os
os.makedirs("input", exist_ok=True)
df.to_excel(OUTPUT_FILE, index=False, sheet_name="Survey_Data")
print(f"Saved {len(df)} rows -> {OUTPUT_FILE}")
print("\nColumns:", list(df.columns))
print("\nChannel split:\n", df["channel"].value_counts())
print("\nLoB split:\n", df["lob"].value_counts())
print("\nCSAT distribution:\n", df["csat_score"].value_counts().sort_index())
print("\nSample rows:\n", df.sample(5, random_state=1)[["channel", "lob", "verbatim", "csat_score"]])

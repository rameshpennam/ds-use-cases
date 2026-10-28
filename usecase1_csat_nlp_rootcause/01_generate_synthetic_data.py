"""
01_generate_synthetic_data.py
------------------------------
Generates a synthetic customer-survey verbatim dataset (chat / email / voice)
for the CSAT Root-Cause & Sentiment Driver Analysis use case.

Run this once, top to bottom (VS Code: click "Run Cell" above each "# %%"
block, or press Shift+Enter), to produce: input_survey_verbatims.xlsx
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

N_RECORDS = 7500              # survey responses to simulate (cap at 10,000 per guideline)
OUTPUT_FILE = "input/input_survey_verbatims.xlsx"   # lands in the input/ subfolder
DATE_RANGE_START = datetime(2026, 8, 1)     # last 3 full months: Aug-Sep-Oct 2026
DATE_RANGE_END = datetime(2026, 10, 31)
TOTAL_DAYS = (DATE_RANGE_END - DATE_RANGE_START).days

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

# WHAT: two more realistic categorical cuts, both customer-master
# attributes (not operational call-center telemetry that would need a
# cross-system join) - the kind of fields a CSAT survey export routinely
# carries already via a customer-ID lookup: plan tier and telecom circle.
PLAN_TIERS = ["Basic", "Standard", "Plus", "Premium", "Elite"]

# All 23 official Indian telecom "circles" (DoT-licensed service areas) -
# this is the real industry list, and collectively covers every state/UT
# (a few large states are split into two circles - e.g. UP East/West - and
# four metros are carved out as their own circle - Delhi/Mumbai/Kolkata/
# Chennai - which is exactly how real telecom operators report this field).
CIRCLES = [
    "Andhra Pradesh", "Assam", "Bihar", "Chennai", "Delhi", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Karnataka", "Kerala",
    "Kolkata", "Madhya Pradesh", "Maharashtra & Goa", "Mumbai", "North East",
    "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "UP (East)", "UP (West)",
    "West Bengal",
]

# %% Cell 2 - Root-cause taxonomy used to WRITE the synthetic verbatims
# WHAT: a TWO-LEVEL taxonomy - 9 broad PRIMARY categories (the "what kind of
# problem"), each broken into 3-5 specific, naturally-named SECONDARY
# sub-issues (the "what exactly") - 34 sub-issues total. Every sub-issue has
# its OWN pool of 3 differently-WORDED, differently-STRUCTURED template
# sentences (not one sentence with swapped-out nouns), so the generated
# verbatim reads like 34 distinct real complaint types, not 3-4 repeated
# patterns.
# WHY: a flat 3-category, 5-template design produced obviously repetitive
# text and an unnaturally small, NMF-guessed secondary driver set. Planting
# the secondary signal directly as real, specific, human-authored sentences
# - and tagging against the SAME specific taxonomy in the analysis script -
# produces natural-reading text AND a rich, natural-sounding secondary
# driver distribution, with no cheating (the saved input file still never
# stores the true label - see Cell 4).
#
# In the analysis script we independently build a keyword dictionary and try
# to RE-DISCOVER these same root causes purely from the text + CSAT score,
# the same way we would with real survey data.

TAXONOMY = {
    "Billing_Charges": {
        "Duplicate Charge": [
            "I was charged twice for the same {service} and nobody has explained why.",
            "My statement shows two identical deductions for one {service} payment this month.",
            "Somehow I got billed a second time for something I already paid for.",
            "Looking at my statement, the same payment shows up listed twice for no reason.",
            "I'm being billed again for something that was already settled last cycle.",
        ],
        "Incorrect Late Fee": [
            "There's a late fee on my bill even though I paid well before the due date.",
            "I don't understand why I'm being charged a penalty when my payment went through on time.",
            "A late fee showed up on my account that genuinely makes no sense to me.",
            "There's a penalty on my account from a payment I made ahead of schedule.",
            "I set up autopay specifically to avoid this, yet a late charge still appeared.",
        ],
        "Roaming Charge Dispute": [
            "I'm seeing a roaming charge on my bill and I never once left the country.",
            "This roaming fee is a mistake - I was home the entire billing cycle.",
            "Nobody can explain the international roaming charge I never signed up for.",
            "I've had my phone on airplane mode most of the trip, yet I'm still being billed for roaming.",
            "There's an international charge on my account and I haven't traveled anywhere in months.",
        ],
        "GST/Tax Confusion": [
            "The tax amount on my invoice doesn't match what it should be at all.",
            "I don't understand why the GST component on my bill keeps changing every month.",
            "My bill has a tax line item that's higher than it's ever been before.",
            "The tax calculation on this bill looks completely off compared to last month's.",
            "I was never given a clear breakdown of how this tax figure was even arrived at.",
        ],
        "Unexplained Deduction": [
            "There's a deduction on my account that I genuinely cannot trace back to anything.",
            "Money came out of my balance and I have no idea what it was for.",
            "An amount was taken from my account with zero explanation anywhere on the bill.",
            "A chunk of my balance just vanished and support couldn't tell me where it went.",
            "There's a line item on my bill that doesn't correspond to anything I actually used.",
        ],
    },
    "Agent_Behavior_Comm": {
        "Rude Agent": [
            "Honestly, the way the representative spoke to me was completely unacceptable.",
            "The agent was rude from the very first minute of the call.",
            "I was genuinely taken aback by how dismissive the agent was with me.",
            "The tone the agent used with me was condescending from start to finish.",
            "I felt talked down to the entire time I was on that call.",
        ],
        "Call Disconnected Mid-Conversation": [
            "I was mid-sentence explaining my issue when the call just dropped.",
            "The line cut off abruptly while the agent was supposedly helping me.",
            "Call got disconnected halfway through and nobody bothered calling back.",
            "Right as the agent started explaining a solution, the call cut out entirely.",
            "We got disconnected and I had to start the whole explanation over with someone new.",
        ],
        "Excessive Hold Time": [
            "I was on hold for almost twenty-five minutes before anyone even spoke to me.",
            "Waited so long on hold that I nearly gave up and hung up myself.",
            "The hold music played for what felt like forever before I reached a human.",
            "Forty minutes on hold and I still hadn't spoken to an actual person.",
            "The wait time before someone picked up was honestly ridiculous.",
        ],
        "Repeated Transfers": [
            "I got transferred between three different departments and still got nowhere.",
            "Every time I explain my problem I get bounced to yet another team.",
            "Nobody would just own my issue - I kept getting passed around instead.",
            "I was passed from department to department without anyone taking ownership.",
            "Four transfers later and I still hadn't gotten a straight answer.",
        ],
        "Agent Gave Wrong Information": [
            "The agent told me something that turned out to be completely incorrect.",
            "I followed the instructions I was given and they were flat out wrong.",
            "What the representative told me contradicted what actually happened afterward.",
            "The information I was given turned out to be the opposite of what actually happened.",
            "I acted on what the agent told me and it ended up making things worse.",
        ],
    },
    "Resolution_Time_FCR": {
        "Ticket Reopened": [
            "My ticket was marked resolved and then the exact same problem came right back.",
            "I was told this was fixed, but here I am raising it again a week later.",
            "The issue keeps reopening no matter how many times it's supposedly closed.",
            "I keep getting told it's resolved, and then the problem shows up again days later.",
            "This ticket has been closed and reopened more times than I can count.",
        ],
        "No Callback Received": [
            "I was promised a callback within 24 hours and nobody ever called.",
            "Still waiting on the callback I was told would happen yesterday.",
            "Nobody followed up with me despite being told someone definitely would.",
            "A callback was scheduled and simply never happened.",
            "I'm still sitting here waiting on a call that was supposed to come hours ago.",
        ],
        "Multiple Follow-ups Needed": [
            "This is the third time I've had to call back about the exact same thing.",
            "I shouldn't have to keep chasing this up myself every other day.",
            "Every call I make about this gets me a different half-answer, never a fix.",
            "I've had to initiate every single follow-up on this myself.",
            "Nothing moves forward unless I personally call back and push for it.",
        ],
        "Escalation Ignored": [
            "I specifically asked for this to be escalated and nothing happened.",
            "My request to speak to a supervisor was apparently never passed along.",
            "I was told my case was escalated but there's been zero movement since.",
            "I asked this be escalated twice now and it still hasn't gone anywhere.",
            "There's apparently no record that my case was ever escalated at all.",
        ],
    },
    "Network_Connectivity": {
        "Frequent Call Drops": [
            "My calls keep dropping every few minutes, especially when I'm indoors.",
            "I can't get through an entire phone call without it cutting off.",
            "Dropped calls have become a near-daily thing on this connection.",
            "Mid-call disconnections have become the norm rather than the exception.",
            "I can't complete a five-minute call without losing the connection.",
        ],
        "No Indoor Signal": [
            "I get almost no signal inside my own home despite being told this area has full coverage.",
            "Bars show full outside but the moment I step indoors the signal disappears.",
            "I have to stand near a window just to get a usable signal at home.",
            "The moment I'm inside any building, my signal drops to nothing.",
            "I'm forced to go outside every time I need to make an important call.",
        ],
        "Slow Data Speed": [
            "Data speed on my plan has been unusably slow for days now.",
            "Pages barely load even though I'm supposedly on a high-speed plan.",
            "Streaming anything is impossible with how slow my connection has gotten.",
            "Even basic browsing feels like it's running on a decade-old connection.",
            "My data speed crawls to a halt the second more than one app is open.",
        ],
        "Network Outage": [
            "There's been a network outage in my area for the third time this month.",
            "Service has been completely down in my neighborhood since this morning.",
            "This is yet another full outage with zero advance notice from the operator.",
            "Service has gone down in my area more times this month than I can count.",
            "No prior warning, no update - just a complete loss of service again.",
        ],
    },
    "Recharge_Plan_Issues": {
        "Recharge Deducted No Activation": [
            "My recharge amount was deducted but the plan itself was never activated.",
            "Money left my account for the top-up but nothing changed on my connection.",
            "I paid for the recharge and I'm still sitting here with the old balance.",
            "The payment cleared on my end but my account shows absolutely no change.",
            "I topped up hours ago and I'm still stuck without the benefits I paid for.",
        ],
        "Unauthorized Plan Change": [
            "My plan was switched to something else without me ever asking for that.",
            "I woke up on a completely different plan than the one I originally chose.",
            "Nobody asked me before changing my existing plan to a new one.",
            "Somehow my plan changed overnight and I never approved anything like that.",
            "I didn't request a plan switch, yet here I am on a completely different one.",
        ],
        "Data Pack Validity Issue": [
            "The data pack I just bought is already showing zero days of validity left.",
            "My pack expired days earlier than what I was shown at the time of purchase.",
            "Validity on this add-on pack doesn't match what the app promised at checkout.",
            "The validity period on this pack is nowhere close to what was advertised.",
            "I'm being shown an expiry date that makes no sense given when I purchased it.",
        ],
        "Auto-Renewal Without Consent": [
            "My plan auto-renewed even though I had specifically turned that off.",
            "I never agreed to auto-renewal and yet I was charged for it again.",
            "This pack kept renewing itself every month despite my cancellation request.",
            "This add-on renewed itself again despite me cancelling it last month.",
            "I explicitly opted out of renewal and got charged for it anyway.",
        ],
    },
    "Activation_Porting_Delay": {
        "SIM Activation Delay": [
            "It has been five days and my new SIM still isn't active.",
            "I'm still waiting on activation well past the time I was originally promised.",
            "My new connection has been sitting inactive for almost a week now.",
            "I'm well past the activation window I was originally quoted.",
            "My new SIM has just been sitting dead for days with no explanation.",
        ],
        "Number Porting Delay": [
            "My number porting request has been stuck in process for over a week.",
            "Porting my number over has taken far longer than the timeline I was given.",
            "I still don't have service on my ported number days after the promised date.",
            "The porting process has dragged on far longer than it should have.",
            "My old number is dead and the new one still isn't working either.",
        ],
        "Installation Rescheduled": [
            "The installation technician has rescheduled on me twice now.",
            "My broadband installation appointment keeps getting pushed back with no reason given.",
            "Nobody showed up for the scheduled installation and I had no warning at all.",
            "This is the second time my installation slot has been pushed back without warning.",
            "I took time off for the installation and the technician simply never came.",
        ],
    },
    "Refund_Processing": {
        "Refund Not Credited": [
            "I was promised a refund two weeks ago and it still hasn't shown up.",
            "The refund status says processed but nothing has actually landed in my account.",
            "Still no sign of the refund I was told would arrive days ago.",
            "The money that was supposedly refunded is nowhere in my account.",
            "I keep checking and there's still no trace of the refund I was promised.",
        ],
        "Partial Refund Issue": [
            "I only got back part of the amount that should have been fully refunded.",
            "The refunded amount doesn't match what I was actually overcharged by.",
            "Only a fraction of my refund came through and nobody can explain the rest.",
            "What came back was noticeably less than what I was actually owed.",
            "The numbers on this refund simply don't add up to what was overcharged.",
        ],
        "Refund Timeline Delay": [
            "I was told the refund would take five to seven days and it's been three weeks.",
            "The refund timeline keeps getting pushed back every time I follow up.",
            "My refund is still sitting as 'under process' well past the promised window.",
            "It's been well beyond the window I was originally given for this refund.",
            "Every time I check, the refund timeline seems to just keep extending.",
        ],
    },
    "App_Website_Technical": {
        "App Payment Failure": [
            "The app crashes every single time I try to make a payment.",
            "My payment failed on the app but the amount was still deducted from my bank.",
            "I can never get a payment to actually complete through the mobile app.",
            "Every attempt to pay through the app ends in some kind of failure screen.",
            "The app says payment unsuccessful but my bank shows the amount already gone.",
        ],
        "Website Login Issue": [
            "I can't log into my account on the website no matter how many times I reset my password.",
            "The website keeps rejecting my login even with the correct credentials.",
            "I'm permanently locked out of the self-care portal and support can't explain why.",
            "I've tried resetting my password three times and still can't get into my account online.",
            "The site just spins endlessly whenever I try to sign in.",
        ],
        "Invoice Download Error": [
            "Every time I try to download my invoice the app throws an error.",
            "I can't get a copy of my bill because the download keeps failing.",
            "The invoice PDF never generates no matter how many times I request it.",
            "I need this invoice for reimbursement and the download simply won't work.",
            "Every attempt to pull up my bill online results in the same error message.",
        ],
    },
    "KYC_Documentation": {
        "KYC Document Rejected": [
            "My KYC documents were rejected without any clear reason given.",
            "I submitted valid ID proof and it still came back as rejected.",
            "Not sure why my documents keep failing verification when everything looks correct.",
            "I've submitted the same valid documents twice now and both times got rejected.",
            "There's no clear reason given for why my documents don't meet whatever the requirement is.",
        ],
        "Reverification Delay": [
            "My re-verification request has been pending for well over a week now.",
            "Still waiting on confirmation that my resubmitted documents went through.",
            "Nobody has gotten back to me on the re-verification I submitted days ago.",
            "It's been well over the stated timeline for my re-verification to go through.",
            "I resubmitted everything that was asked for and have heard absolutely nothing since.",
        ],
        "Service Suspended For KYC": [
            "My service got suspended over KYC even though I completed it on time.",
            "My connection was cut off for a document issue I'd already resolved.",
            "Service stopped working because of a KYC flag that shouldn't even be there.",
            "My account was suspended over documentation I'd already submitted on time.",
            "I completed everything required and my service still got cut off anyway.",
        ],
    },
    "Customer_Effort": {
        "Multiple Channel Switching": [
            "I tried the app first, then chat, then finally had to call before anyone actually helped.",
            "I shouldn't have to jump between three different channels just to get one thing resolved.",
            "Between the website, the app, and the call center, I was sent in circles all day.",
            "I started on chat, got nowhere, then had to repeat the whole thing again over a call.",
            "Every channel I tried just redirected me to another one instead of solving anything.",
        ],
        "Repeated Information Requests": [
            "I had to give my account details for the fourth time on this same call.",
            "Every single person I spoke to asked me to re-verify everything from scratch.",
            "I shouldn't have to repeat my entire issue every time I'm transferred.",
            "It feels like nothing I say gets recorded anywhere - I keep starting over.",
            "I've explained this same problem in detail at least five separate times now.",
        ],
        "Complex IVR Navigation": [
            "The phone menu took me in circles before I could even reach a person.",
            "I went through six different options before finding the right department.",
            "The automated system kept looping me back to the main menu.",
            "It took nearly ten minutes just navigating menus before I spoke to anyone.",
            "The IVR options don't match any of the actual issues customers call about.",
        ],
        "No Self-Service Resolution": [
            "I couldn't resolve this myself online and had no choice but to call in.",
            "The self-service portal doesn't even have an option for this kind of issue.",
            "I tried everything on the app before giving up and contacting support directly.",
            "There's no way to handle something this simple without waiting on a call.",
            "The FAQ and help center were no use at all for what I actually needed.",
        ],
    },
    "Repeat_Contact": {
        "Same Issue Multiple Times": [
            "This is the fourth time I'm contacting support about this exact same problem.",
            "I keep having to reach out again and again for something that should've been fixed once.",
            "Here I am contacting you a third time this month about the same thing.",
            "I've lost count of how many times I've had to reach out about this one issue.",
            "Every few days I'm back in touch about a problem that was never actually solved.",
        ],
        "Different Agent Each Time": [
            "I've spoken to a different agent every single time and had to start over.",
            "No two agents have given me the same answer about this issue.",
            "Every call connects me to someone new with zero context on my case.",
            "I wish just one agent would actually own this instead of passing me along.",
            "Each time I contact in, it's like explaining this problem for the very first time.",
        ],
        "No Case History Visible": [
            "Nobody could see any record of my previous calls about this.",
            "The agent had no idea I'd already contacted support about this twice before.",
            "There's apparently no notes on file from any of my earlier conversations.",
            "I had to explain everything from zero because no history was pulled up.",
            "It's like my past contacts about this issue don't exist in your system at all.",
        ],
        "Multiple Contacts Same Day": [
            "I've already called twice today about this and I'm contacting again.",
            "This is my third message today and I still don't have an answer.",
            "I called, then chatted, then called again, all within the same afternoon.",
            "I shouldn't need to reach out three times in one day for a single issue.",
            "Between this morning and now, I've contacted support about this twice already.",
        ],
    },
}

POSITIVE_TEMPLATES = [
    "The agent resolved my issue quickly and was very polite throughout.",
    "Great service, my concern was sorted out in a single call.",
    "I am very satisfied - the agent was helpful and professional.",
    "Quick resolution today, thank you so much for the fast turnaround.",
    "The agent explained everything clearly and patiently.",
    "Really impressed with how fast this was handled.",
    "The representative went above and beyond to help me out.",
    "Smooth experience from start to finish, no complaints at all.",
    "My request was handled professionally and within the promised time.",
    "Very happy with the support I received today.",
    "The team resolved my concern faster than I expected.",
    "Excellent service - this is exactly why I stay with this provider.",
    "Friendly, efficient, and genuinely helpful - couldn't ask for more.",
    "Everything was sorted out in minutes, really appreciated it.",
]

PRIMARY_CATEGORIES = list(TAXONOMY.keys())


def fill_sentence(sentence: str) -> str:
    return sentence.format(service=random.choice(
        ["mobile recharge", "broadband plan", "data pack", "postpaid bill", "SMS pack"]))


# %% Cell 3 - Core simulation loop
def pick_primary(channel: str, lob: str, tenure_months: int) -> str:
    """Weighted random PRIMARY category pick (or Positive), with a few
    deliberate real-world style correlations baked in so the dataset has a
    genuine 'story' to discover later."""
    weights = {
        "Billing_Charges": 0.16, "Agent_Behavior_Comm": 0.08,
        "Resolution_Time_FCR": 0.07, "Network_Connectivity": 0.06,
        "Recharge_Plan_Issues": 0.06, "Activation_Porting_Delay": 0.04,
        "Refund_Processing": 0.04, "App_Website_Technical": 0.03,
        "KYC_Documentation": 0.03, "Customer_Effort": 0.05,
        "Repeat_Contact": 0.05, "Positive_No_Issue": 0.33,
    }

    if lob in ("Billing & Payments", "Postpaid Mobile"):
        weights["Billing_Charges"] += 0.10
        weights["Positive_No_Issue"] -= 0.10

    if channel == "Voice":
        weights["Agent_Behavior_Comm"] += 0.06
        weights["Resolution_Time_FCR"] += 0.04
        weights["Network_Connectivity"] += 0.04
        weights["Positive_No_Issue"] -= 0.14

    if tenure_months < 6:
        weights["Agent_Behavior_Comm"] += 0.08
        weights["Positive_No_Issue"] -= 0.08

    if lob == "Broadband":
        weights["Network_Connectivity"] += 0.08
        weights["Positive_No_Issue"] -= 0.08

    categories = list(weights.keys())
    w = np.clip(np.array(list(weights.values())), 0.01, None)
    w = w / w.sum()
    return np.random.choice(categories, p=w)


def pick_secondary(primary: str) -> str:
    """Uniform pick among the chosen primary's specific sub-issues."""
    return random.choice(list(TAXONOMY[primary].keys()))


EMAIL_OPENERS = ["Hi Team, ", "Hello, ", "Dear Support Team, ", "Hi, ", "To whom it may concern, ", ""]

# WHAT: independent opening/closing clause pools, mixed in probabilistically
# and independently of the category. WHY: this multiplies the number of
# DISTINCT final sentences far beyond the base template count, without
# hand-authoring dozens more category-specific templates - and real survey
# responses genuinely do carry generic asks/context like these.
NEGATIVE_OPENERS = [
    "", "", "", "Honestly, ", "I'm really frustrated because ", "To be honest, ",
    "I have to say, ", "Not going to lie, ",
]
NEGATIVE_CLOSERS = [
    # NOTE: deliberately avoid polite-request words ("please", "appreciate",
    # "kindly", "hoping") - VADER's lexicon scores those as positive-valence
    # regardless of context, which was silently flipping genuinely negative
    # complaints to a positive sentiment score (caught via a real test:
    # "...explained why. Please look into this on priority." scored +0.13,
    # not negative). Verified these alternatives all stay negative/neutral.
    "", "", "", " This needs to be fixed soon.", " This is not the experience I expected.",
    " Something needs to change here.", " This has been a frustrating experience overall.",
    " This is simply not good enough.", " This is far from acceptable.",
]
POSITIVE_CLOSERS = [
    "", "", "", " Really appreciate it.", " Thank you for the quick help.",
    " Keep up the good work.", " Will definitely recommend based on this experience.",
]


def _lowercase_first(text: str) -> str:
    # Never lowercase the pronoun "I" ("I was...", "I'm...", "I've...") -
    # only lowercase other sentence-initial words ("The", "My", "Why", ...).
    if not text or text.startswith("I ") or text.startswith("I'"):
        return text
    return text[0].lower() + text[1:]


def make_verbatim(primary: str, secondary: str, channel: str) -> str:
    if primary == "Positive_No_Issue":
        templates = POSITIVE_TEMPLATES
        sentence = fill_sentence(random.choice(templates))
        if channel == "Voice" and random.random() < 0.5:
            sentence += " " + fill_sentence(random.choice(templates))
        sentence += random.choice(POSITIVE_CLOSERS)
    else:
        templates = TAXONOMY[primary][secondary]
        sentence = fill_sentence(random.choice(templates))
        # Occasionally add a second sentence on the SAME specific sub-issue
        # (different wording) for length variety - keeps the tagging signal
        # clean (one dominant, genuinely-matchable secondary per response).
        n_extra = {"Voice": 0.65, "Chat": 0.30, "Email": 0.40}[channel]
        if random.random() < n_extra and len(templates) > 1:
            remaining = [t for t in templates if fill_sentence(t) != sentence]
            if remaining:
                sentence += " " + fill_sentence(random.choice(remaining))

        opener = random.choice(NEGATIVE_OPENERS)
        if opener:
            sentence = opener + _lowercase_first(sentence)
        sentence += random.choice(NEGATIVE_CLOSERS)

    if channel == "Email":
        opener = random.choice(EMAIL_OPENERS)
        if opener:
            sentence = opener + _lowercase_first(sentence)
    return sentence


def make_csat(primary: str) -> int:
    if primary == "Positive_No_Issue":
        return int(np.random.choice([4, 5], p=[0.35, 0.65]))
    # Negative-driver responses still clearly underperform (mostly 2-3), but
    # aren't a floor-level crisis - keeps the overall average closer to a
    # realistic "room for improvement" ~3.0 rather than a 1-point disaster.
    return int(np.random.choice([1, 2, 3, 4], p=[0.20, 0.30, 0.30, 0.20]))


def make_plan_tier() -> str:
    """WHAT: the customer's plan tier (Basic/Standard/Plus/Premium/Elite).
    WHY: a genuine customer-master attribute, routinely pre-joined onto a
    CSAT survey export by the survey platform (customer ID lookup) - no
    cross-system operational join required, unlike call-center telemetry."""
    return random.choice(PLAN_TIERS)


def make_circle() -> str:
    """WHAT: the telecom circle/region the customer is in - a standard
    reporting dimension for any Indian telecom operator, and another
    customer-master field routinely present on a survey export."""
    return random.choice(CIRCLES)


def make_date(primary: str) -> datetime:
    # Billing complaints cluster in the most recent 30 days of the window
    # (i.e. October) to simulate a recent billing-cycle spike you can point
    # to on a trend chart later.
    if primary == "Billing_Charges" and random.random() < 0.5:
        offset = random.randint(max(0, TOTAL_DAYS - 30), TOTAL_DAYS)
    else:
        offset = random.randint(0, TOTAL_DAYS)
    return DATE_RANGE_START + timedelta(days=offset)


records = []
for i in range(N_RECORDS):
    agent = AGENT_ROSTER.sample(1).iloc[0]
    channel = random.choices(CHANNELS, weights=[0.45, 0.35, 0.20])[0]
    lob = random.choice(LOBS)
    primary = pick_primary(channel, lob, int(agent["tenure_months"]))
    secondary = pick_secondary(primary) if primary != "Positive_No_Issue" else None

    records.append({
        "date": make_date(primary),   # kept as a real date, not text - see Cell 4
        "unique_id": f"SRV{100000 + i}",
        "channel": channel,
        "lob": lob,
        "verbatim": make_verbatim(primary, secondary, channel),
        "csat_score": make_csat(primary),
        "agent_name": agent["agent_name"],
        "tl_name": agent["tl_name"],
        "manager_name": agent["manager_name"],
        "tenure_months": int(agent["tenure_months"]),
        "plan_tier": make_plan_tier(),
        "circle": make_circle(),
    })

df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

# %% Cell 4 - Save + quick sanity check (this is what you show on screen)
import os
import openpyxl

os.makedirs("input", exist_ok=True)

# Write "date" as a real Excel date (not text) so sorting/pivoting by date
# works correctly in Excel and Power BI.
df["date"] = pd.to_datetime(df["date"]).dt.date
df.to_excel(OUTPUT_FILE, index=False, sheet_name="Survey_Data")

wb = openpyxl.load_workbook(OUTPUT_FILE)
ws = wb["Survey_Data"]
date_col = list(df.columns).index("date") + 1   # 1-indexed for openpyxl
for row in range(2, ws.max_row + 1):
    ws.cell(row=row, column=date_col).number_format = "yyyy-mm-dd"
wb.save(OUTPUT_FILE)

print(f"Saved {len(df)} rows -> {OUTPUT_FILE}")
print("\nColumns:", list(df.columns))
print("\nDate range:", df["date"].min(), "to", df["date"].max())
print("\nChannel split:\n", df["channel"].value_counts())
print("\nLoB split:\n", df["lob"].value_counts())
print("\nCSAT distribution:\n", df["csat_score"].value_counts().sort_index())
print("\nAverage CSAT:", round(df["csat_score"].mean(), 2))
print("\nPlan tier split:\n", df["plan_tier"].value_counts())
print("\nCircle count:", df["circle"].nunique())
print("\nUnique verbatim sentences (lower bound on variety):", df["verbatim"].nunique(), "/", len(df))
print("\nSample rows:\n", df.sample(5, random_state=1)[["channel", "lob", "verbatim", "csat_score"]])

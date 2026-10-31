"""
Synthetic ServiceNow-style incident generator for TriageIQ demos.

Produces a realistic, confidentiality-safe ticket dump for a fictional company
("Northwind Retail") plus a separate ground-truth file used to evaluate the
automation classifier (precision / recall / F1).

Usage:
    python generate_synthetic_tickets.py --n 3000 --seed 42                      # training data
    python generate_synthetic_tickets.py --n 1500 --seed 7 --name northwind_q3 --start 2000000   # unseen demo data
    python generate_synthetic_tickets.py --n 2500 --seed 11 --name contoso --start 3000000 --profile contoso  # another customer
Outputs (next to this script):
    <name>_incidents.csv        -> ticket dump (train on it, or upload it in the app)
    <name>_ground_truth.csv     -> hidden labels, never uploaded
"""

import argparse
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Each template: tower, category, subcategory, assignment group, weight,
# automation label, typical MTTR (median hours, spread), channel weights,
# short-description variants, resolution-note variants.
TEMPLATES = [
    # ── Already automated: created and resolved by monitoring / bots ──
    dict(tower="Server", cat="Event Management", sub="Disk space alert", group="Wintel L1",
         w=9, label="Already Automated", mttr=(0.4, 0.6), auto_resolver=True,
         ch={"Event Management": 1.0},
         sd=["Disk space utilization above {pct}% on {host} drive {drv}:",
             "ALERT: Low disk space on {host} ({drv}: {pct}% used)",
             "{host} - Logical disk free space below threshold"],
         rn=["Auto-remediation script cleared temp files, disk now at {low}%",
             "Ignio cleaned IIS logs and recycle bin. Alert cleared."]),
    dict(tower="Server", cat="Event Management", sub="Service stopped", group="Wintel L1",
         w=6, label="Already Automated", mttr=(0.3, 0.5), auto_resolver=True,
         ch={"Event Management": 1.0},
         sd=["Service {svc} stopped on {host}",
             "ALERT: Windows service {svc} not running - {host}", "{host} not responding, please check"],
         rn=["Service restarted automatically by monitoring runbook.",
             "Auto-heal restarted {svc}. Verified running."]),
    dict(tower="Server", cat="Event Management", sub="CPU high", group="Linux L1",
         w=6, label="Already Automated", mttr=(0.5, 0.7), auto_resolver=True,
         ch={"Event Management": 1.0},
         sd=["CPU utilization > {pct}% on {host} for 15 minutes",
             "High CPU alert {host} ({pct}%)"],
         rn=["Runaway process killed by auto-remediation. CPU normal.",
             "Alert auto-closed, CPU back under threshold."]),
    dict(tower="Database", cat="Event Management", sub="Tablespace alert", group="Oracle DBA",
         w=4, label="Already Automated", mttr=(0.6, 0.6), auto_resolver=True,
         ch={"Event Management": 1.0},
         sd=["Tablespace {ts} usage {pct}% on {db}",
             "ORA alert: tablespace {ts} nearly full ({db})"],
         rn=["Datafile auto-extended by DBA automation.",
             "Automation added 2GB datafile to {ts}."]),

    # ── Can be automated: repetitive, rule-based, currently manual ──
    dict(tower="End User", cat="Access Management", sub="Password reset", group="Service Desk",
         w=14, label="Can Be Automated", mttr=(0.8, 0.8),
         ch={"Phone": 0.5, "Self-service": 0.2, "Email": 0.3},
         sd=["Password reset for {app}", "User locked out of {app}, needs password reset",
             "Cannot login to {app} - forgot password", "pwd reset {app} pls", "Login issue for {user}"],
         rn=["Password reset and shared with user over call.",
             "Account unlocked and password reset. User confirmed login."]),
    dict(tower="AD", cat="Access Management", sub="Account unlock", group="Service Desk",
         w=8, label="Can Be Automated", mttr=(0.6, 0.7),
         ch={"Phone": 0.6, "Email": 0.4},
         sd=["AD account locked - {user}", "Domain account locked out after password change",
             "Unable to login to laptop, account locked", "Cannot login to {app}", "Login issue for {user}"],
         rn=["Unlocked AD account.", "Account unlocked in ADUC, user able to login."]),
    dict(tower="AD", cat="Access Management", sub="Add user to group", group="IAM Team",
         w=7, label="Can Be Automated", mttr=(6, 0.9),
         ch={"Email": 0.6, "Self-service": 0.4},
         sd=["Add {user} to AD group {grp}", "Request access to shared folder {share}",
             "Need access to {grp} distribution list"],
         rn=["User added to {grp} after manager approval.",
             "Access granted to {share}."]),
    dict(tower="Application", cat="Batch Management", sub="Job failure rerun", group="App Support L2",
         w=8, label="Can Be Automated", mttr=(3, 1.0),
         ch={"Event Management": 0.7, "Email": 0.3},
         sd=["Batch job {job} failed with exit code {code}", "Control-M job {job} ABENDED",
             "{job} did not complete in SLA window"],
         rn=["Job restarted from failed step, completed successfully.",
             "Rerun of {job} successful after clearing lock file."]),
    dict(tower="Server", cat="Server Management", sub="Server restart", group="Wintel L2",
         w=4, label="Can Be Automated", mttr=(4, 0.9),
         ch={"Email": 0.7, "Phone": 0.3},
         sd=["Please restart server {host} after patching", "Reboot required for {host}",
             "Scheduled restart request {host}", "{host} not responding, please check"],
         rn=["Server rebooted, services verified.", "Restart completed, all services up."]),
    dict(tower="Collaboration", cat="Messaging", sub="Mailbox full", group="Messaging Team",
         w=4, label="Can Be Automated", mttr=(5, 0.8),
         ch={"Email": 0.5, "Phone": 0.5},
         sd=["Mailbox full cannot send emails", "Outlook says mailbox quota exceeded",
             "Increase mailbox size for {user}"],
         rn=["Mailbox quota increased to 100GB.", "Enabled online archive, quota freed."]),
    dict(tower="End User", cat="Software", sub="Software install", group="Desktop Support",
         w=7, label="Can Be Automated", mttr=(10, 0.9),
         ch={"Self-service": 0.6, "Email": 0.4},
         sd=["Install {sw} on my laptop", "Need {sw} installed for project work",
             "Software installation request - {sw}"],
         rn=["{sw} pushed via SCCM.", "Installed {sw} remotely, user confirmed."]),

    # ── Manual only: diagnosis-heavy, physical, or judgement-based ──
    dict(tower="Network", cat="Network", sub="Connectivity issue", group="Network L2",
         w=6, label="Manual Only", mttr=(18, 1.0),
         ch={"Phone": 0.6, "Email": 0.4},
         sd=["Intermittent network drops at {site} store", "Users at {site} unable to reach POS server",
             "Slow network in {site} warehouse since morning", "VPN keeps disconnecting for remote users"],
         rn=["Faulty switch port replaced by onsite engineer.",
             "ISP link flapping, ticket raised with carrier, resolved after circuit reset.",
             "Duplex mismatch fixed on uplink."]),
    dict(tower="End User", cat="Hardware", sub="Laptop hardware", group="Desktop Support",
         w=6, label="Manual Only", mttr=(40, 0.8),
         ch={"Phone": 0.5, "Walk-in": 0.5},
         sd=["Laptop screen flickering", "Keyboard not working on {model}",
             "Laptop not powering on", "Battery swelling on {model}"],
         rn=["Display panel replaced under warranty.", "Motherboard replaced by vendor.",
             "Replacement laptop issued."]),
    dict(tower="Application", cat="Application", sub="Functional defect", group="App Support L3",
         w=7, label="Manual Only", mttr=(60, 1.0),
         ch={"Email": 0.6, "Phone": 0.4},
         sd=["{app} showing wrong price for SKU {sku}", "Order sync between {app} and SAP failing for some stores",
             "Report in {app} missing last week's data", "Error 500 when submitting return in {app}",
             "{app} very slow today"],
         rn=["Code fix deployed in release {rel}.", "Data correction script executed after root cause analysis.",
             "Config mismatch between environments corrected, defect logged {jira}."]),
    dict(tower="Database", cat="Database", sub="Performance", group="Oracle DBA",
         w=4, label="Manual Only", mttr=(24, 0.9),
         ch={"Email": 0.7, "Phone": 0.3},
         sd=["{db} queries running very slow", "Deadlocks on {db} during month end",
             "High wait events on {db}", "{app} very slow today"],
         rn=["Missing index added after AWR analysis.", "Execution plan pinned, stats regathered.",
             "Long running session killed, query rewritten by dev team."]),
    dict(tower="Security", cat="Security", sub="Phishing / incident", group="SOC",
         w=3, label="Manual Only", mttr=(12, 0.9),
         ch={"Email": 0.8, "Phone": 0.2},
         sd=["Suspicious email received asking for credentials", "User clicked phishing link",
             "Possible malware on {host}"],
         rn=["Email quarantined, user credentials rotated, endpoint scanned.",
             "Host isolated, reimaged after forensic review."]),
]

# Per-ticket outcome variants. Real dumps are not "one ticket type = one label":
# the same alert sometimes defeats auto-remediation, some password resets already
# go through a self-service bot, some job failures are data bugs needing devs.
# Each variant: probability, label, resolved by a bot or not, MTTR multiplier,
# resolution-note variants.
VARIANTS = {
    "Disk space alert": [dict(p=0.15, label="Can Be Automated", bot=False, mttr_x=6,
                              rn=["Auto-remediation failed (access denied), engineer cleared {drv}: manually.",
                                  "Cleanup script timed out, old logs archived by L1 engineer."])],
    "Service stopped": [dict(p=0.15, label="Can Be Automated", bot=False, mttr_x=5,
                             rn=["Auto-restart failed twice, engineer restarted {svc} manually.",
                                 "Runbook did not trigger, service started from services.msc."])],
    "CPU high": [dict(p=0.12, label="Manual Only", bot=False, mttr_x=20,
                      rn=["Memory leak in vendor agent, case opened with vendor, patch applied.",
                          "Capacity issue, VM resized after change approval."])],
    "Password reset": [dict(p=0.15, label="Already Automated", bot=True, mttr_x=0.1,
                            rn=["Password reset completed via self-service bot.",
                                "Reset through SSPR portal, auto-closed."]),
                       dict(p=0.08, label="Manual Only", bot=False, mttr_x=6,
                            rn=["Identity verification failed, reset done after manager approval call.",
                                "VIP user, reset done in person after ID check."])],
    "Account unlock": [dict(p=0.12, label="Already Automated", bot=True, mttr_x=0.1,
                            rn=["Account auto-unlocked by self-service bot."])],
    "Add user to group": [dict(p=0.15, label="Manual Only", bot=False, mttr_x=3,
                               rn=["Access to restricted finance share needs CISO sign-off, granted after review.",
                                   "Segregation-of-duties conflict, access approved by risk team."])],
    "Job failure rerun": [dict(p=0.20, label="Manual Only", bot=False, mttr_x=8,
                               rn=["Source file had corrupt records, dev team fixed data and reran.",
                                   "Root cause: schema change upstream, code fix deployed before rerun."])],
    "Mailbox full": [dict(p=0.10, label="Already Automated", bot=True, mttr_x=0.1,
                          rn=["Auto-archive policy applied by mailbox bot."])],
    "Connectivity issue": [dict(p=0.12, label="Can Be Automated", bot=False, mttr_x=0.1,
                                rn=["VPN client cache reset, user reconnected.",
                                    "DNS flushed and network adapter reset remotely."])],
    "Laptop hardware": [dict(p=0.08, label="Can Be Automated", bot=False, mttr_x=0.05,
                             rn=["Driver reinstalled remotely, keyboard working.",
                                 "Display driver updated via SCCM, flicker resolved."])],
}

# What humans actually type into category fields: vague, generic or wrong.
GENERIC_CATEGORIES = [("Inquiry / Help", ""), ("Other", "Other"), ("Software", "Issue"),
                      ("Hardware", "General"), ("", "")]
VAGUE_DESCRIPTIONS = ["Issue reported by user", "Please check urgently", "Not working since morning",
                      "User unable to work", "Error, please help", "Need assistance", "Problem with system"]
GENERIC_NOTES = ["Resolved.", "Done", "Issue fixed", "Closing as resolved", "User confirmed, closing."]
STATUSES = ["Already Automated", "Can Be Automated", "Manual Only"]

APPS = ["StoreHub", "PayFlow", "SAP ECC", "Workday", "ServiceNow", "Salesforce", "InventoryPro"]
HOSTS = [f"NWR{p}{i:03d}" for p in ["WEB", "APP", "DB", "FS", "DC"] for i in range(1, 25)]
SITES = ["Pune", "Bengaluru", "Chennai", "Hyderabad", "Mumbai", "Delhi", "Kolkata"]
SERVICES = ["Spooler", "W3SVC", "MSSQLSERVER", "TomcatPOS", "SplunkForwarder"]
JOBS = [f"NWR_{x}_{i:02d}" for x in ["INV", "FIN", "POS", "ETL"] for i in range(1, 12)]
SOFTWARE = ["Python", "Power BI Desktop", "Visual Studio Code", "Tableau", "7-Zip", "Postman"]
GROUPS_AD = ["GRP-Finance-RO", "GRP-StoreOps", "DL-Pune-All", "GRP-HR-Share"]
MODELS = ["Latitude 5420", "ThinkPad T14", "EliteBook 840"]
DBS = ["ORAPRD01", "ORAPRD02", "SQLPOS01"]
TABLESPACES = ["USERS", "INV_DATA", "FIN_IDX", "UNDOTBS1"]
FIRST = ["Aarav", "Diya", "Rohan", "Isha", "Kabir", "Meera", "Arjun", "Sana", "Vikram", "Neha"]
LAST = ["Sharma", "Iyer", "Patel", "Reddy", "Khan", "Das", "Nair", "Gupta", "Menon", "Rao"]
BOTS = ["ignio.automation", "monitoring.integration", "auto.remediation"]


def fill(text, rng):
    user = f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}"
    return text.format(
        pct=rng.randint(85, 99), low=rng.randint(40, 70), host=rng.choice(HOSTS),
        drv=rng.choice("CDE"), svc=rng.choice(SERVICES), ts=rng.choice(TABLESPACES),
        db=rng.choice(DBS), app=rng.choice(APPS), user=user, grp=rng.choice(GROUPS_AD),
        share=f"\\\\NWRFS01\\{rng.choice(['Finance', 'HR', 'Ops'])}", job=rng.choice(JOBS),
        code=rng.choice([1, 4, 8, 12, 255]), sw=rng.choice(SOFTWARE), site=rng.choice(SITES),
        model=rng.choice(MODELS), sku=rng.randint(100000, 999999), rel=f"R{rng.randint(20, 40)}.{rng.randint(1, 9)}",
        jira=f"NWR-{rng.randint(1000, 9999)}",
    )


def noisy(text, rng):
    """Light real-world noise: casing, trailing punctuation, occasional typo."""
    r = rng.random()
    if r < 0.10:
        text = text.lower()
    elif r < 0.15:
        text = text.upper()
    if rng.random() < 0.05 and len(text) > 8:
        i = rng.randint(1, len(text) - 2)
        text = text[:i] + text[i + 1] + text[i] + text[i + 2:]
    if rng.random() < 0.08:
        text += rng.choice([" - urgent", " asap", " !!", ""])
    return text


def generate(n, seed, first_number=1000000):
    rng = random.Random(seed)
    vague_rng = random.Random(seed + 7)
    np_rng = np.random.default_rng(seed)
    weights = np.array([t["w"] for t in TEMPLATES], dtype=float)
    weights /= weights.sum()
    groups = sorted({t["group"] for t in TEMPLATES})
    engineers = {g: [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(6)] for g in groups}

    start = datetime(2025, 4, 1)
    span_days = 180
    rows, truth = [], []

    for i in range(n):
        t = TEMPLATES[np_rng.choice(len(TEMPLATES), p=weights)]

        # Weekday-heavy, business-hours-heavy arrival pattern; alerts any time.
        day = start + timedelta(days=int(np_rng.integers(0, span_days)))
        if t.get("auto_resolver"):
            hour = int(np_rng.integers(0, 24))
        else:
            hour = int(np.clip(np_rng.normal(12, 3), 7, 21))
            if day.weekday() >= 5 and rng.random() < 0.6:
                day += timedelta(days=7 - day.weekday())
        opened = day.replace(hour=hour, minute=int(np_rng.integers(0, 60)), second=int(np_rng.integers(0, 60)))

        # Pick this ticket's actual outcome: the template default or a variant
        label, is_bot, mttr_x, notes = t["label"], bool(t.get("auto_resolver")), 1.0, t["rn"]
        roll = rng.random()
        for v in VARIANTS.get(t["sub"], []):
            if roll < v["p"]:
                label, is_bot, mttr_x, notes = v["label"], v["bot"], v["mttr_x"], v["rn"]
                break
            roll -= v["p"]

        median, sigma = t["mttr"]
        mttr_h = float(np_rng.lognormal(np.log(median * mttr_x), sigma))
        priority = rng.choices(["1 - Critical", "2 - High", "3 - Moderate", "4 - Low"],
                               weights=[2, 10, 55, 33])[0]
        if priority.startswith("1"):
            mttr_h *= 0.5
        resolved = opened + timedelta(hours=mttr_h)
        closed = resolved + timedelta(hours=float(np_rng.uniform(24, 96)))

        channel = rng.choices(list(t["ch"]), weights=list(t["ch"].values()))[0]
        group = t["group"]
        misrouted = rng.random() < 0.10
        if misrouted:
            group = rng.choice([g for g in groups if g != t["group"]])

        if is_bot:
            resolver = rng.choice(BOTS)
            updated_by = resolver
            assigned = resolver
        else:
            assigned = rng.choice(engineers[group])
            resolver = assigned
            updated_by = assigned.lower().replace(" ", ".")

        manual = label == "Manual Only"
        reassign = int(np_rng.poisson(1.6 if manual else 0.3)) + int(misrouted)
        reopen = int(np_rng.random() < (0.08 if manual else 0.02))
        sd = noisy(fill(rng.choice(t["sd"]), rng), rng)
        if vague_rng.random() < 0.15:
            sd = vague_rng.choice(VAGUE_DESCRIPTIONS)
        caller = f"{rng.choice(FIRST)} {rng.choice(LAST)}"

        # Field-entry noise: lazy categorisation and uninformative closure notes
        cat, sub = t["cat"], t["sub"]
        if rng.random() < 0.25:
            cat, sub = rng.choice(GENERIC_CATEGORIES)
        close_notes = rng.choice(GENERIC_NOTES) if rng.random() < 0.10 else fill(rng.choice(notes), rng)

        # Annotator disagreement: a small share of labels differ from the "true" outcome
        if rng.random() < 0.03:
            label = rng.choice([s for s in STATUSES if s != label])

        number = f"INC{first_number + i:07d}"
        rows.append({
            "number": number,
            "opened_at": opened.strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": resolved.strftime("%Y-%m-%d %H:%M:%S"),
            "closed_at": closed.strftime("%Y-%m-%d %H:%M:%S"),
            "short_description": sd,
            "description": f"{sd}. Reported by {caller} from {rng.choice(SITES)}.",
            "close_notes": close_notes,
            "category": cat,
            "subcategory": sub,
            "priority": priority,
            "state": "Closed",
            "assignment_group": group,
            "assigned_to": assigned,
            "resolved_by": resolver,
            "sys_updated_by": updated_by,
            "contact_type": channel,
            "caller_id": "Monitoring" if t.get("auto_resolver") else caller,
            "reassignment_count": reassign,
            "reopen_count": reopen,
            "cmdb_ci": rng.choice(HOSTS) if t["tower"] in ("Server", "Database") else rng.choice(APPS),
            "location": rng.choice(SITES),
            "business_duration": int(mttr_h * 3600 * 0.6),
            "calendar_duration": int(mttr_h * 3600),
        })
        truth.append({"number": number, "true_tower": t["tower"], "true_category": t["cat"],
                      "true_subcategory": t["sub"], "true_automation_status": label})

    return pd.DataFrame(rows), pd.DataFrame(truth)


ANOMALY_RATE = 0.025
FMT = "%Y-%m-%d %H:%M:%S"


def plant_anomalies(df: pd.DataFrame, truth: pd.DataFrame, seed: int):
    """
    Mark ~2.5% of tickets as operational anomalies with a known cause, so anomaly
    detection can be scored (precision / recall). Uses its own RNG, so every
    other ticket is identical to a run without anomalies.
      - mttr_outlier:      15-40x the usual resolution time for that ticket type
      - reassignment_storm: bounced 6-10 times between teams and reopened
      - offhours_p1:       P1 raised at night on a business-hours ticket type, slow
    """
    rng = np.random.default_rng(seed + 1000)
    df, truth = df.copy(), truth.copy()
    truth["is_anomaly"] = 0
    truth["anomaly_type"] = ""
    idx = rng.choice(len(df), size=int(len(df) * ANOMALY_RATE), replace=False)
    kinds = rng.choice(["mttr_outlier", "reassignment_storm", "offhours_p1"], size=len(idx))
    for i, kind in zip(idx, kinds):
        opened = datetime.strptime(df.at[i, "opened_at"], FMT)
        mttr_h = df.at[i, "calendar_duration"] / 3600
        if kind == "mttr_outlier":
            mttr_h = max(mttr_h, 0.5) * float(rng.uniform(15, 40))
        elif kind == "reassignment_storm":
            df.at[i, "reassignment_count"] = int(rng.integers(6, 11))
            df.at[i, "reopen_count"] = 1
            mttr_h *= float(rng.uniform(2, 4))
        else:
            opened = opened.replace(hour=int(rng.integers(0, 5)))
            df.at[i, "priority"] = "1 - Critical"
            mttr_h = max(mttr_h, 2.0) * float(rng.uniform(4, 8))
        resolved = opened + timedelta(hours=mttr_h)
        df.at[i, "opened_at"] = opened.strftime(FMT)
        df.at[i, "resolved_at"] = resolved.strftime(FMT)
        df.at[i, "closed_at"] = (resolved + timedelta(hours=float(rng.uniform(24, 96)))).strftime(FMT)
        df.at[i, "calendar_duration"] = int(mttr_h * 3600)
        df.at[i, "business_duration"] = int(mttr_h * 3600 * 0.6)
        truth.at[i, "is_anomaly"] = 1
        truth.at[i, "anomaly_type"] = kind
    return df, truth


# A second customer with the same kinds of work but its own team names, service
# accounts and wording. Used to show drift and how analyst labels adapt the model.
CUSTOMER_PROFILES = {
    "contoso": {
        "groups": {"Wintel L1": "Windows Ops", "Wintel L2": "Windows Engineering", "Linux L1": "Unix Ops",
                   "Service Desk": "Global Helpdesk", "Oracle DBA": "DB Engineering", "App Support L2": "Apps Run",
                   "App Support L3": "Apps Engineering", "Network L2": "NetOps", "Messaging Team": "M365 Team",
                   "Desktop Support": "EUC Field Services", "IAM Team": "Identity Ops", "SOC": "Cyber Defense"},
        "accounts": {"ignio.automation": "svc_runbook", "monitoring.integration": "svc_alertsync",
                     "auto.remediation": "svc_selfheal"},
        "channels": {"Event Management": "Alert", "Self-service": "Portal"},
        "words": [("Auto-remediation", "Runbook job"), ("auto-remediation", "runbook job"), ("Ignio", "Runbook engine"),
                  ("Auto-heal", "Self-heal job"), ("auto-closed", "closed by job"), ("Auto-restart", "Restart job"),
                  ("automatically", "via scheduled job"), ("Automation", "Scheduled job"), ("automation", "scheduled job"),
                  ("auto-extended", "extended by job"), ("auto-unlocked", "unlocked by portal"), ("bot", "portal flow"),
                  ("Password reset", "Credential reset"), ("password reset", "credential reset"),
                  ("password", "credential"), ("Disk space", "Storage capacity"), ("disk space", "storage capacity"),
                  ("Mailbox", "M365 mailbox"), ("mailbox", "M365 mailbox")],
    },
}


def apply_profile(df: pd.DataFrame, name: str) -> pd.DataFrame:
    prof = CUSTOMER_PROFILES[name]
    df = df.copy()
    df["assignment_group"] = df["assignment_group"].replace(prof["groups"])
    for col in ("resolved_by", "assigned_to", "sys_updated_by"):
        df[col] = df[col].replace(prof["accounts"])
    df["contact_type"] = df["contact_type"].replace(prof["channels"])
    for col in ("short_description", "description", "close_notes"):
        for old, new in prof["words"]:
            df[col] = df[col].str.replace(old, new, regex=False)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--name", default="northwind",
                    help="file prefix; use a new seed + name for an unseen evaluation set")
    ap.add_argument("--start", type=int, default=1000000, help="first ticket number")
    ap.add_argument("--profile", choices=sorted(CUSTOMER_PROFILES), help="restyle as another customer")
    args = ap.parse_args()

    df, truth = generate(args.n, args.seed, args.start)
    df, truth = plant_anomalies(df, truth, args.seed)
    if args.profile:
        df = apply_profile(df, args.profile)
    out = os.path.dirname(os.path.abspath(__file__))
    df.to_csv(os.path.join(out, f"{args.name}_incidents.csv"), index=False)
    truth.to_csv(os.path.join(out, f"{args.name}_ground_truth.csv"), index=False)

    print(f"Wrote {len(df)} tickets")
    print(truth["true_automation_status"].value_counts().to_string())
    print(truth["anomaly_type"].replace("", "normal").value_counts().to_string())


if __name__ == "__main__":
    main()

"""
Copilot evaluation on a fixed question set built from the Northwind Q3 ground truth.

    python experiments/rag_eval.py --upload-id 5

  retrieval     16 questions, one per true subcategory, phrased differently from the
                ticket text. precision@8 = share of the 8 retrieved tickets whose true
                subcategory matches; compared for vector, keyword and hybrid search.
  numeric       15 questions with answers computed independently from the raw CSV.
                Correct if the expected number (within tolerance) or name is in the answer.
  out of scope  5 questions the dataset cannot answer. Correct if the answer declines.
  faithfulness  invalid citations and unsupported numbers flagged by the verifier.
  baseline      numeric and out-of-scope questions also go to the previous keyword copilot.
Writes reports/rag_eval.json.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.rag import retrieval  # noqa: E402
from services.rag.answer import ask  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "sample_data")

RETRIEVAL_QUESTIONS = {
    "Disk space alert": "What do we do when a server is running out of disk?",
    "Service stopped": "How are Windows services that stopped running brought back?",
    "CPU high": "How is high processor usage on servers handled?",
    "Tablespace alert": "How are Oracle tablespace usage alerts handled?",
    "Password reset": "How do users get their password reset?",
    "Account unlock": "How are locked domain accounts handled?",
    "Add user to group": "How are requests to give someone access to a group or shared folder handled?",
    "Job failure rerun": "What happens when a scheduled batch job fails?",
    "Server restart": "How are requests to reboot a server handled?",
    "Mailbox full": "How do we help users whose mailbox has no space left?",
    "Software install": "How are requests for new software on a laptop fulfilled?",
    "Connectivity issue": "How are network outages at stores fixed?",
    "Laptop hardware": "What happens when a laptop screen or keyboard stops working?",
    "Functional defect": "How are application bugs like wrong prices or failing orders fixed?",
    "Performance": "Why are database queries slow and what fixes them?",
    "Phishing / incident": "How are phishing emails and malware infections handled?",
}

OUT_OF_SCOPE = [
    "What is the capital of France?",
    "Who is the CEO of Northwind Retail?",
    "What will the weather be in Pune tomorrow?",
    "What was the root cause of the SAP outage on 1 January 2030?",
    "How much did the company spend on cloud hosting last year?",
]
DECLINE = re.compile(r"does not show|doesn't show|not (?:in|available|contain|about|related)|no (?:information|data|tickets|evidence)"
                     r"|cannot|can't|unable|nothing to look up|isn't about|not provide|does not (?:include|have|mention)", re.I)


def numeric_questions():
    df = pd.read_csv(os.path.join(DATA, "northwind_q3_incidents.csv"), parse_dates=["opened_at", "resolved_at"])
    df["mttr"] = (df["resolved_at"] - df["opened_at"]).dt.total_seconds() / 3600
    p1 = df[df.priority.str.startswith("1")]
    team_mttr = df.groupby("assignment_group")["mttr"].mean()
    return [
        ("How many tickets are in this dataset?", len(df), 0),
        ("How many P1 tickets are there?", len(p1), 0),
        ("How many P2 tickets are there?", int(df.priority.str.startswith("2").sum()), 0),
        ("Which team handled the most tickets?", df.assignment_group.value_counts().index[0], None),
        ("Which team has the longest average resolution time?", team_mttr.idxmax(), None),
        ("What is the average resolution time across all tickets, in hours?", round(df.mttr.mean(), 2), 0.15),
        ("What share of P1 tickets breached their 4 hour SLA?", round(float((p1.mttr > 4).mean()) * 100, 1), 1.0),
        ("Which channel has the most tickets?", df.contact_type.value_counts().index[0], None),
        ("How many tickets came in through the Self-service channel?", int((df.contact_type == "Self-service").sum()), 0),
        ("What is the average resolution time for Service Desk tickets, in hours?", round(team_mttr["Service Desk"], 2), 0.15),
        ("What is the average resolution time for Desktop Support, in hours?", round(team_mttr["Desktop Support"], 2), 0.15),
        ("How many tickets did the Oracle DBA team handle?", int((df.assignment_group == "Oracle DBA").sum()), 0),
        # regression cases added after a user-reported failure (one-word / jargon questions)
        ("MTTR", round(df.mttr.mean(), 2), 0.15),
        ("What is the TAT for P1 tickets?", round(p1.mttr.mean(), 2), 0.15),
        # (a resolver version of this question was dropped: two resolvers tie at 133 tickets)
        ("Which team handled the most tickets, and what is their MTTR?",
         round(team_mttr[df.assignment_group.value_counts().index[0]], 2), 0.15),
    ]


def number_in(answer: str, expected: float, tol: float) -> bool:
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", answer)]
    candidates = nums + [n * 100 for n in nums if n <= 1]          # shares written as 0.65 vs 65%
    return any(abs(n - expected) <= tol + 1e-9 for n in candidates)


def old_copilot(upload_id: int, question: str) -> str:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/copilot/chat",
        data=json.dumps({"message": question, "upload_id": upload_id}).encode(),
        headers={"Authorization": "Bearer " + os.environ["TRIAGEIQ_TOKEN"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["response"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload-id", type=int, default=5)
    ap.add_argument("--team", required=True, help="team_id that owns the upload")
    ap.add_argument("--skip-baseline", action="store_true")
    ap.add_argument("--out", default="reports/rag_eval.json")
    args = ap.parse_args()
    uid = args.upload_id

    # ---------- retrieval ----------
    truth = pd.read_csv(os.path.join(DATA, "northwind_q3_ground_truth.csv")).set_index("number")["true_subcategory"]
    retrieval_rows = {}
    for method in ("vector", "keyword", "hybrid"):
        precisions, hits = [], []
        for sub, q in RETRIEVAL_QUESTIONS.items():
            found = [r["number"] for r in retrieval.search(uid, q, k=8, method=method)]
            rel = [truth.get(n) == sub for n in found]
            precisions.append(float(np.mean(rel)) if rel else 0.0)
            hits.append(bool(rel and rel[0]))
        retrieval_rows[method] = {"precision_at_8": round(float(np.mean(precisions)), 4),
                                  "hit_at_1": round(float(np.mean(hits)), 4)}
        print(f"retrieval {method:7s} precision@8 {retrieval_rows[method]['precision_at_8']:.3f} "
              f"hit@1 {retrieval_rows[method]['hit_at_1']:.3f}")

    # ---------- generation ----------
    results, latencies = [], []
    for q, expected, tol in numeric_questions():
        r = ask(uid, args.team, q)
        ok = (expected.lower() in r["answer"].lower()) if isinstance(expected, str) else number_in(r["answer"], expected, tol)
        latencies.append(r["timings"].get("total_ms", 0))
        results.append({"type": "numeric", "question": q, "expected": expected, "correct": ok,
                        "answer": r["answer"], "plan": r["plan"], "verification": r["verification"]})
        print(f"numeric {'OK ' if ok else 'BAD'} {q} -> expected {expected}")
    for q in OUT_OF_SCOPE:
        r = ask(uid, args.team, q)
        ok = bool(DECLINE.search(r["answer"]))
        latencies.append(r["timings"].get("total_ms", 0))
        results.append({"type": "out_of_scope", "question": q, "correct": ok, "answer": r["answer"],
                        "plan": r["plan"], "verification": r["verification"]})
        print(f"out-of-scope {'OK ' if ok else 'BAD'} {q}")
    for sub, q in list(RETRIEVAL_QUESTIONS.items())[:6]:       # explanatory answers: faithfulness only
        r = ask(uid, args.team, q)
        latencies.append(r["timings"].get("total_ms", 0))
        results.append({"type": "explanatory", "question": q, "answer": r["answer"], "plan": r["plan"],
                        "verification": r["verification"]})

    def share(kind):
        rows = [x for x in results if x["type"] == kind]
        return round(sum(x["correct"] for x in rows) / len(rows), 4)

    answered = [x for x in results if x["type"] != "out_of_scope"]
    rag = {
        "numeric_accuracy": share("numeric"),
        "out_of_scope_declined": share("out_of_scope"),
        "answers_with_invalid_citation": round(float(np.mean([bool(x["verification"]["invalid"]) for x in answered])), 4),
        "unsupported_number_first_draft": round(float(np.mean([bool(x["verification"].get("unsupported_before_revision")) for x in answered])), 4),
        "answers_with_unsupported_number": round(float(np.mean([bool(x["verification"].get("unsupported_numbers")) for x in answered])), 4),
        "latency_ms_p50": int(np.percentile(latencies, 50)), "latency_ms_p95": int(np.percentile(latencies, 95)),
    }
    print("RAG:", rag)

    # ---------- baseline ----------
    baseline = None
    if not args.skip_baseline:
        b_rows = []
        for q, expected, tol in numeric_questions():
            a = old_copilot(uid, q)
            ok = (expected.lower() in a.lower()) if isinstance(expected, str) else number_in(a, expected, tol)
            b_rows.append({"type": "numeric", "question": q, "correct": ok, "answer": a})
        for q in OUT_OF_SCOPE:
            a = old_copilot(uid, q)
            b_rows.append({"type": "out_of_scope", "question": q, "correct": bool(DECLINE.search(a)), "answer": a})
        baseline = {
            "numeric_accuracy": round(float(np.mean([x["correct"] for x in b_rows if x["type"] == "numeric"])), 4),
            "out_of_scope_declined": round(float(np.mean([x["correct"] for x in b_rows if x["type"] == "out_of_scope"])), 4),
            "answers": b_rows,
        }
        print("Baseline:", {k: v for k, v in baseline.items() if k != "answers"})

    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "upload_id": uid,
              "retrieval": retrieval_rows, "rag": rag, "baseline": baseline, "results": results}
    os.makedirs("reports", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    main()

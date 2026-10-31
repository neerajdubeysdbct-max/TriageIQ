"""
End-to-end check: score what the app stored for an upload against ground truth.

    python evaluate_upload.py --upload-id 3 --labels ../sample_data/northwind_q3_ground_truth.csv

Compares the automation status the dashboard shows (is_already_automated /
can_be_automated flags) and the AIO classifier's aiops_automation_status with
the true labels, and checks that the feasibility tiers separate tickets.
Writes reports/upload_<id>_evaluation.md.
"""

import argparse
import json
import os

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from models import SessionLocal
from ml.automation_model import AUTOMATABLE, CLASSES


def flags_to_status(row) -> str:
    if row.is_already_automated:
        return "Already Automated"
    if row.can_be_automated:
        return "Can Be Automated"
    return "Manual Only"


def score(name, y_true, y_pred) -> dict:
    return {
        "name": name,
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0),
        "report": classification_report(y_true, y_pred, labels=CLASSES, digits=3, zero_division=0),
        "per_class": {c: {k: round(v[k], 4) for k in ("precision", "recall", "f1-score", "support")}
                      for c, v in classification_report(y_true, y_pred, labels=CLASSES, output_dict=True,
                                                        zero_division=0).items() if c in CLASSES},
        "cm": confusion_matrix(y_true, y_pred, labels=CLASSES),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload-id", type=int, required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--report-dir", default="reports")
    args = ap.parse_args()

    db = SessionLocal()
    stored = pd.read_sql(
        "SELECT ticket_number AS number, is_already_automated, can_be_automated, "
        "aiops_automation_status, l3_automation_feasibility, automation_potential_score, "
        "automation_confidence, l1_category, l2_subcategory FROM tickets WHERE upload_id = %(uid)s",
        db.bind, params={"uid": args.upload_id})
    db.close()

    truth = pd.read_csv(args.labels)[["number", "true_automation_status", "true_tower", "true_subcategory"]]
    df = stored.merge(truth, on="number", how="inner")
    if df.empty:
        raise SystemExit(f"No tickets of upload {args.upload_id} match {args.labels}")
    print(f"Upload {args.upload_id}: {len(stored)} tickets, {len(df)} with ground truth")

    y = df["true_automation_status"]
    results = [score("Dashboard flags (is_already_automated / can_be_automated)", y, df.apply(flags_to_status, axis=1))]
    flag_status = df.apply(flags_to_status, axis=1)
    # Once the classifier has scored an upload the AIO column is aligned to it, so only
    # report the AIO layer separately when it still differs
    if df["aiops_automation_status"].notna().any() and (df["aiops_automation_status"] != flag_status).any():
        results.append(score("AIO classifier (aiops_automation_status)", y,
                             df["aiops_automation_status"].fillna("Manual Only")))

    automatable = y.isin(AUTOMATABLE)
    tiers = (df.assign(automatable=automatable)
               .groupby("l3_automation_feasibility")
               .agg(tickets=("number", "size"), actually_automatable=("automatable", "mean"),
                    avg_score=("automation_potential_score", "mean"))
               .sort_values("avg_score", ascending=False))

    lines = [f"# Upload {args.upload_id}: end-to-end evaluation", "",
             f"{len(df)} tickets matched to `{os.path.basename(args.labels)}`.", ""]
    for r in results:
        lines += [f"## {r['name']}", "", f"- Accuracy: **{r['accuracy']:.1%}**",
                  f"- Macro F1: **{r['macro_f1']:.3f}**", "", "```", r["report"], "```", "",
                  "Confusion matrix (rows = true, columns = predicted):", "", "```",
                  pd.DataFrame(r["cm"], index=CLASSES, columns=CLASSES).to_string(), "```", ""]
        print(f"  {r['name']:58s} acc {r['accuracy']:.1%}  macro-F1 {r['macro_f1']:.3f}")
    lines += ["## Feasibility tiers", "", "```", tiers.round(3).to_string(), "```", ""]
    print(tiers.round(3).to_string())

    os.makedirs(args.report_dir, exist_ok=True)
    summary = {
        "upload_id": args.upload_id,
        "labels_file": os.path.basename(args.labels),
        "n_tickets": len(df),
        "evaluated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "results": [{"name": r["name"], "accuracy": round(r["accuracy"], 4), "macro_f1": round(r["macro_f1"], 4),
                     "per_class": r["per_class"], "confusion_matrix": r["cm"].tolist()} for r in results],
        "categories": {
            "l1_tower_accuracy": round(float((df["l1_category"] == df["true_tower"]).mean()), 4),
            "l2_subcategory_accuracy": round(float((df["l2_subcategory"] == df["true_subcategory"]).mean()), 4),
        },
        "tiers": [{"tier": t, "tickets": int(row.tickets), "actually_automatable": round(float(row.actually_automatable), 4),
                   "avg_score": round(float(row.avg_score), 2)} for t, row in tiers.iterrows()],
    }
    print(f"Categories: L1 accuracy {summary['categories']['l1_tower_accuracy']:.1%}, "
          f"L2 accuracy {summary['categories']['l2_subcategory_accuracy']:.1%}")
    with open(os.path.join(args.report_dir, f"upload_{args.upload_id}_evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    path = os.path.join(args.report_dir, f"upload_{args.upload_id}_evaluation.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report -> {path}")


if __name__ == "__main__":
    main()

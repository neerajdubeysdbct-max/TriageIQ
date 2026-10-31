"""
Learning-loop experiment: does labelling a new customer's tickets improve the model?

    python experiments/learning_loop.py --upload-id 7 --labels ../sample_data/contoso_ground_truth.csv --n 300

Runs against the live API with the same calls the UI makes:
  1. accuracy of the active model on the upload (vs. ground truth)
  2. the upload's drift report
  3. an "analyst" labels n tickets from the Review Queue's random sample
     (answers taken from the ground-truth file)
  4. retraining via the API; the evaluation gate decides on promotion
  5. the upload is re-scored with the (possibly new) active model
  6. accuracy again, on tickets that were NOT labelled, so the gain is not
     just the labels themselves
Needs TRIAGEIQ_TOKEN (an admin's login token) in the environment.
Writes reports/learning_loop_<upload_id>.json.
"""

import argparse
import json
import os
import sys
import time
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import SessionLocal  # noqa: E402

API = os.environ.get("TRIAGEIQ_API", "http://127.0.0.1:8000")
CLASSES = ["Already Automated", "Can Be Automated", "Manual Only"]


def call(path, body=None, method=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"),
                                 headers={"Authorization": "Bearer " + os.environ["TRIAGEIQ_TOKEN"],
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def accuracy(upload_id, truth, exclude_labelled):
    db = SessionLocal()
    try:
        df = pd.read_sql(
            "SELECT ticket_number AS number, model_status, human_override FROM tickets WHERE upload_id = %(u)s",
            db.bind, params={"u": upload_id})
    finally:
        db.close()
    df = df.merge(truth, on="number")
    if exclude_labelled:
        df = df[df["human_override"].isna()]
    acc = float((df["model_status"] == df["true_automation_status"]).mean())
    per_class = {c: round(float((df.loc[df.true_automation_status == c, "model_status"] == c).mean()), 4) for c in CLASSES}
    return {"n": int(len(df)), "accuracy": round(acc, 4), "recall": per_class}


def wait_for(path, done, timeout=900, every=5):
    start = time.time()
    while time.time() - start < timeout:
        state = call(path)
        if done(state):
            return state
        time.sleep(every)
    raise TimeoutError(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload-id", type=int, required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()
    uid = args.upload_id
    truth = pd.read_csv(args.labels)[["number", "true_automation_status"]]
    truth_map = truth.set_index("number")["true_automation_status"]

    before = accuracy(uid, truth, exclude_labelled=False)
    drift = call(f"/api/models/drift/{uid}")
    print(f"Before: {before['accuracy']:.1%} on {before['n']} tickets; drift {drift['status']}")

    labelled = 0
    while labelled < args.n:
        t = call(f"/api/review/{uid}/next?mode=random")["ticket"]
        if t is None:
            break
        call(f"/api/review/{uid}/label", {"ticket_id": t["id"], "label": truth_map[t["number"]], "mode": "random"})
        labelled += 1
    review = call(f"/api/review/{uid}/summary")["accuracy"]
    print(f"Labelled {labelled}; Review Queue estimate {review['accuracy']} (95% CI {review['ci95']})")

    call("/api/models/automation/retrain", body={})
    time.sleep(2)
    status = wait_for("/api/models/automation/retrain-status", lambda s: s.get("state") in ("done", "failed"))
    print(f"Retraining: {status.get('state')} | promoted={status.get('promoted')} | {status.get('reason') or status.get('error')}")

    mtime_path = f"outputs/upload_{uid}/automation_model.json"
    before_mtime = os.path.getmtime(mtime_path) if os.path.exists(mtime_path) else 0
    call(f"/api/models/rescore/{uid}", body={})
    deadline = time.time() + 900
    while time.time() < deadline and (not os.path.exists(mtime_path) or os.path.getmtime(mtime_path) <= before_mtime):
        time.sleep(5)
    after = accuracy(uid, truth, exclude_labelled=True)
    drift_after = call(f"/api/models/drift/{uid}")
    print(f"After: {after['accuracy']:.1%} on {after['n']} unlabelled tickets; drift {drift_after['status']}")

    result = {"upload_id": uid, "labels": labelled, "before": before, "drift_before": drift,
              "review_queue_estimate": review, "retraining": status, "after_unlabelled": after,
              "drift_after": drift_after}
    os.makedirs("reports", exist_ok=True)
    with open(f"reports/learning_loop_{uid}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


if __name__ == "__main__":
    main()

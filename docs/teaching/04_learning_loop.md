# Module 4 — The learning loop: labels, retraining, evaluation gates, drift

**Code:** `backend/routers/review.py`, `backend/services/model_lifecycle.py`, `backend/services/drift.py`,
`backend/experiments/learning_loop.py`

## 1. The problem

A model trained on one customer's tickets is moved to another customer. Team names, bot accounts and wording are
different. What happens, how do you notice, and how do you fix it without breaking the first customer?

In TriageIQ: the automation classifier scored 95% on its own test set and **73%** on a new customer ("Contoso").
It missed almost every "Already Automated" ticket because Contoso's bots are called `svc_runbook`, not
`ignio.automation`. Worse, it was **confident**: only 1% of tickets had confidence below 0.6.

## 2. Concepts

| Concept | Meaning | Where in the code |
|---|---|---|
| Distribution shift (drift) | Production data no longer looks like training data | `services/drift.py` |
| PSI (Population Stability Index) | Compares two distributions bin by bin; < 0.1 stable, 0.1–0.25 moderate, > 0.25 significant | `drift.psi()` |
| Ground truth / labels | The correct answer for a ticket, given by a person | Review Queue (`routers/review.py`) |
| Random sample vs. active-learning queue | Random labels give an unbiased accuracy estimate; "least confident first" finds hard cases fast but biases the estimate | `next_ticket(mode=...)` |
| Confidence interval (Wilson) | How sure we are about an accuracy measured on n labels | `wilson_interval()` |
| Frozen gold test set | Labelled tickets never used for training, so every model version is compared on the same exam | `build_splits()` |
| Evaluation gate | Promote a new model only if it is better on the gold set and not worse on the old customer | `decide()` |
| Model registry / rollback | Every version stored with its metrics; any version can be re-activated | `activate()` |
| Experiment tracking | Parameters, metrics and artefacts of every run (MLflow) | `_log_mlflow()` |

## 3. The loop

```
Upload → model scores tickets → drift check
   → analysts label a random sample (accuracy estimate) and the least-confident tickets (triage)
   → retrain on base data + labels → evaluation gate on the frozen gold set
   → promoted (new active version) or rejected (kept for audit) → MLflow run recorded
   → re-score datasets with the active model
```

The model never retrains on its own predictions. Doing that only reinforces its mistakes (a feedback loop).

## 4. Results to quote

| | Contoso before | Contoso after 300 labels |
|---|---|---|
| Accuracy (2,200 unlabelled tickets) | 73.1% | 92.6% |
| "Already Automated" recall | 0.7% | 88% |
| Drift | significant | stable |
| Base customer (Northwind) macro F1 | 0.950 | 0.956 |

A retraining run with no new labels was rejected by the gate (+0.002 macro F1, within noise).

## 5. Interview questions

1. **"How do you know your model still works in production?"** Drift monitoring on every batch (feature PSI,
   unseen categories, vocabulary coverage relative to training, unsure-ticket rate) plus a labelled random sample to
   measure accuracy with a confidence interval.
2. **"Why not just use the model's confidence to detect problems?"** Under distribution shift models are often
   confidently wrong. Here only 1% of Contoso tickets were below 0.6 confidence while accuracy was 73%.
3. **"How do you retrain safely?"** Frozen gold set, promotion rule with a no-regression constraint on existing
   customers, every version stored, one-click rollback, every run tracked.
4. **"Why keep the model's prediction separately from the analyst's label?"** So you can still measure the model
   after analysts overwrite what the dashboard shows.
5. **"Why exclude 'least confident first' labels from the accuracy estimate?"** They are deliberately the hardest
   tickets, so accuracy on them underestimates real accuracy (selection bias).
6. **"Why was the vocabulary threshold relative, not absolute?"** The training text itself only reaches ~60%
   coverage (rare words, host names are not in the vocabulary). A fixed 60% threshold flagged normal data.

## 6. Exercises

**Beginner**
1. Run `python generate_synthetic_tickets.py --n 2500 --seed 11 --name contoso --start 3000000 --profile contoso` and
   compare five rows with `northwind_incidents.csv`. List three differences a model would struggle with.
2. Upload `contoso_incidents.csv`. Open Model Health: what does the drift panel say and why?

**Intermediate**
3. In the Review Queue, label 40 tickets in *Random sample* mode. Read the accuracy and its confidence interval.
   Label 40 more: how does the interval change, and why?
4. Compute PSI by hand for this example: training bins [0.5, 0.3, 0.2], new data [0.2, 0.3, 0.5].
   (Answer: 0.55 — significant.)
5. Explain why `GOLD_SHARE_BUCKETS` uses a hash of the ticket id instead of `random.random()`.

**Advanced**
6. Run `experiments/learning_loop.py` with `--n 50`, `--n 150` and `--n 300` (reset labels between runs). Plot
   accuracy on unlabelled tickets against the number of labels. Where do the returns flatten?
7. Change the promotion rule so that a candidate can never lose more than 0.5 points of recall on *any* class.
   Which test would you write first?
8. Add a fourth drift signal: the share of tickets whose description is close to no training ticket in embedding
   space. What threshold would you choose, and how would you validate it?

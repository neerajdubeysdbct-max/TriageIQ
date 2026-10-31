# Automation classifier: evaluation report
_Generated 2026-10-19T09:07:43 on `northwind_incidents.csv` (3000 tickets; split {'train': 1800, 'val': 600, 'test': 600})_

## Held-out test results

| Model | Accuracy | Macro F1 |
|---|---|---|
| Majority class | 46.3% | 0.211 |
| Rule: "resolved by bot" | 70.2% | 0.575 |
| Logistic regression | 95.0% | 0.949 |
| XGBoost (calibrated) | 95.0% | 0.950 |

### XGBoost (calibrated): per class

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Already Automated | 0.967 | 0.967 | 0.967 | 150 |
| Can Be Automated | 0.941 | 0.968 | 0.954 | 278 |
| Manual Only | 0.951 | 0.907 | 0.929 | 172 |

Confusion matrix (rows = true, columns = predicted):

| | Already Automated | Can Be Automated | Manual Only |
|---|---|---|---|
| **Already Automated** | 145 | 4 | 1 |
| **Can Be Automated** | 2 | 269 | 7 |
| **Manual Only** | 3 | 13 | 156 |

## Calibration

- Expected calibration error: 0.028 raw → 0.012 after isotonic calibration
- Multi-class Brier score: 0.087 → 0.088

## Automation score tiers (test set)

| Tier | Tickets | Share | Actually automatable |
|---|---|---|---|
| High | 436 | 72.7% | 96.3% |
| Medium | 0 | 0.0% | — |
| Low | 0 | 0.0% | — |
| Not feasible | 164 | 27.3% | 4.9% |

## 5-fold cross-validation (train + validation)

- Logistic regression: macro F1 0.958 ± 0.008
- XGBoost: macro F1 0.962 ± 0.012

## Top features (mean |SHAP|, all classes)

1. resolver_is_bot (0.474)
2. text: "installed" (0.282)
3. text: "check" (0.235)
4. log_mttr_hours (0.199)
5. text: "mailbox" (0.184)
6. text: "services" (0.174)
7. assignment_group = Oracle DBA (0.133)
8. text: "replaced" (0.132)
9. category = Database (0.124)
10. assignment_group = Wintel L2 (0.113)
11. text: "sccm" (0.111)
12. category = Security (0.108)
13. assignment_group = IAM Team (0.103)
14. text: "remotely" (0.094)
15. text: "engineer" (0.092)

## Example errors

- `INC1002486` true **Manual Only**, predicted **Can Be Automated**: domain account locked out after password change . domain account locked out after password change. reported by  person  from  site . . account unlocked in aduc,
- `INC1001485` true **Can Be Automated**, predicted **Manual Only**: laptop not powering on . laptop not powering on. reported by  person  from  site . . display panel replaced under warranty.
- `INC1002186` true **Manual Only**, predicted **Already Automated**: alert: low disk space on nwrapp001 (c: 93% used) . alert: low disk space on nwrapp001 (c: 93% used). reported by vikram iyer from  site . . user confirmed, clos
- `INC1002479` true **Manual Only**, predicted **Can Be Automated**: software installation request - visual studio code . software installation request - visual studio code. reported by  person  from  site . . installed postman r
- `INC1000499` true **Manual Only**, predicted **Can Be Automated**: batch job nwr_fin_03 failed with exit code 12 . batch job nwr_fin_03 failed with exit code 12. reported by  person  from  site . . root cause: schema change ups
- `INC1000916` true **Manual Only**, predicted **Can Be Automated**: slow network in  site  warehouse since morning . slow network in  site  warehouse since morning. reported by  person  from  site . . duplex mismatch fixed on up
- `INC1000896` true **Manual Only**, predicted **Can Be Automated**: high cpu alert nwrdb013 (97%) . high cpu alert nwrdb013 (97%). reported by isha iyer from  site . . capacity issue, vm resized after change approval.
- `INC1002044` true **Can Be Automated**, predicted **Already Automated**: issue reported by user . issue reported by user. reported by  person  from  site . . reset through sspr portal, auto-closed.

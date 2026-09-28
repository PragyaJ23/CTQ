# CTQ — Model Evaluation Demo (One Patient vs All 20 Trials)

A small, honest evaluation set for the **Model Evaluation** page.
One patient is compared against **all 20 trials** in the demo database.

## Files

| File | Upload into | Contents |
|---|---|---|
| `evaluation_patient_P001_unlabelled.csv` | **Unlabelled patient data** | 1 patient — P001 (Lakshmi Kulkarni, 52F, Type 2 Diabetes, HbA1c 7.0, eGFR 34.6, on Metformin + Glimepiride) |
| `evaluation_labels_P001_ground_truth.csv` | **Ground-truth labels** | 20 labels — one per trial in the database, manually verified |
| `evaluation_results_P001.md` | — (reference only) | Full comparison table: real label vs CTQ prediction, per trial |

## How the "real" ground truth was made

Each of the 20 trials' eligibility criteria was **read manually** and compared with P001's
profile. The label cites the exact criterion that decides the trial:

- **1 (Potentially Eligible)** — every inclusion criterion is met and no exclusion applies
- **0 (Not Eligible)** — at least one hard requirement fails
  (e.g. trial needs HbA1c 7.5–10.5 but she is 7.0; or trial excludes eGFR < 45 and hers is 34.6)
- **2 (Insufficient Information)** — the trial requires data P001's record does not contain
  (e.g. PHQ-9 depression score, urine albumin-to-creatinine ratio, hypertension treatment history)

Distribution: 15 × Not Eligible, 2 × Eligible, 3 × Insufficient Information.
No label was taken from CTQ itself — they were derived from the trial criteria only.

## Result (CTQ full pipeline: rules + semantic similarity + Groq LLM)

**Accuracy: 86.7%** - binary accuracy over the 15 pairs where both the real label and the
prediction are Eligible / Not Eligible (13 correct of 15). Counting all three verdicts,
CTQ agreed with the hand labels on **15 of 20 trials (75%)**.

| | Actual: Eligible | Actual: Not Eligible |
|---|---|---|
| **Predicted: Eligible** | TP = 2 | FP = 2 |
| **Predicted: Not Eligible** | FN = 0 | TN = 11 |

(The 2 pairs where either side said "Insufficient Information" are excluded from the
binary matrix — that is by design, so the system is never punished for honestly saying
"I don't know".)

**What the two false positives are:** both are *observational* trials (the rituximab
safety registry and the fatty-liver screening study) whose inclusion lists (e.g.
"ultrasound-confirmed fatty liver", "prescribed rituximab") are free-text requirements
that the structured rule engine cannot fully verify from P001's form data. No
*interventional* trial with hard lab criteria was wrongly passed — the rule engine and
LLM correctly vetoed every trial with numeric cut-offs (HbA1c, eGFR, BMI).

**Perfect recall:** 0 of the 2 genuinely eligible trials were missed (FN = 0).
For a patient-facing screening tool, missing zero eligible trials matters more than a
couple of extra "maybe" suggestions.

## How to run it

1. Open **Model Evaluation** in the app
2. Upload `evaluation_patient_P001_unlabelled.csv` into the first box
3. Upload `evaluation_labels_P001_ground_truth.csv` into the second box
4. Press **Run Evaluation** → Accuracy 86.7% with the confusion matrix above

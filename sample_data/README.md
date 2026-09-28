# Sample data for CTQ

All files here are **synthetic** (no real patients). Two flows use them:
**Find Trials** (match patients to trials) and **Model Evaluation** (score the
matcher against ground truth).

| File | Used on | Shape |
|---|---|---|
| `evaluation_patients_unstructured.csv` | Model Evaluation (unstructured side) **and** Find Trials → Unstructured tab | `patient_id, notes` — 10 patients as free-text clinical notes |
| `evaluation_labels_ground_truth.csv` | Model Evaluation (labelled side) | `patient_id, trial_id, actual_label` — 21 pairs, `1` eligible / `0` not eligible / `2` insufficient |
| `unstructured_patients_find_trials.csv` | Find Trials → Unstructured tab | `patient_id, clinical_notes` — same 10 patients, no labels needed |
| `structured_patients_sample.csv` | Find Trials → Structured tab (type/adapt) | one row per patient with form columns (age, condition, labs, habits) |

## Required columns (what the app actually reads)

**Unlabelled / unstructured file** — needs a patient id and a note-text column:

| Column | Required? | Accepted names | Fallback |
|---|---|---|---|
| note text | effectively yes | `text, note, clinical_notes, clinical_note, notes, note_text, content, summary, history, medical_history` (case-insensitive, substring match too, e.g. `patient_notes`) | if none found, the **first column** is used and the whole row is joined into one text blob |
| patient id | yes for evaluation | `note_id, id, patient_id, noteid, row_id` | auto `P001, P002, ...` — which then will **not** join against your labels |

One row per patient. PDFs, photos and TXT files need no columns at all — the
OCR/PDF/text reader handles them.

**Labelled / ground-truth file** — exactly these three:

| Column | Required? | Values |
|---|---|---|
| `patient_id` | yes | must match the id in the unlabelled file exactly (`P001` ≠ `p1`) |
| `trial_id` | yes | must exist in the trial database, e.g. `CTRI/2024/01/062001` — an unknown id fails the whole run with a 404-style error |
| `actual_label` | yes | `1` = Potentially Eligible, `0` = Not Eligible, `2` = Insufficient Information. Words also accepted (`eligible`, `not eligible`, `insufficient`, `yes`, `no`, `true`, `false`). Any other value skips that row and shows it in a banner |

Extra columns are ignored. Order does not matter. You only need label rows for
the pairs you want scored — the unlabelled file may contain more patients than
the labels cover (and vice-versa, those pairs are reported as "skipped").

Minimal pair that works:

```csv
# unlabelled.csv            # labels.csv
patient_id,notes           patient_id,trial_id,actual_label
P001,"48-year-old male …"   P001,CTRI/2024/01/062001,1
```

## Model Evaluation — upload both files together

Flow: unstructured notes → **DistilBERT ML NER** → structured profiles →
every trial in the database checked → predictions compared with the labels.

Measured on this sample set (32-trial database, `TOP_K_TRIALS=0` = all trials):

```
patients evaluated: 10     labelled pairs: 21     skipped: 0
accuracy 1.00   precision 1.00   recall 1.00   F1 1.00
confusion: TP 11   FP 0   FN 0   TN 10
excluded (predicted "Insufficient Information"): 0
```

The notes were written so that every fact the labelled trials need is actually
stated (eGFR, ALT, FEV1 % predicted, disease duration, smoking/alcohol status,
comorbidities). If you delete a fact from a note, the matching pair correctly
degrades to "Insufficient Information" instead of guessing — those rows are
excluded from the binary matrix and reported separately on the page.

## Find Trials — structured samples

| ID | Age/Sex | Condition | Key values | Expected |
|---|---|---|---|---|
| S001 | 48 M | Type 2 Diabetes Mellitus | HbA1c 8.5, eGFR 80, ALT 25, BMI 28.4, Metformin 12 mo | CTRI/2024/01/062001 → Potentially Eligible |
| S002 | 55 F | Type 2 Diabetes Mellitus | HbA1c 9.2, Glimepiride only (no metformin) | CTRI/2024/01/062001 → Not Eligible |
| S003 | 62 M | Hypertension | BP 150/95, eGFR 78, on Amlodipine | CTRI/2024/03/062318 → Potentially Eligible |
| S004 | 24 F | Asthma | FEV1 78 % predicted, no COPD, never smoker | CTRI/2024/08/062851 → Potentially Eligible |
| S005 | 58 M | Type 2 Diabetes (obese) | HbA1c 9.8, BMI 34.3, Metformin 36 mo | CTRI/2025/08/064022 → Potentially Eligible |
| S006 | 35 M | Healthy Volunteer | BMI 22.1, normal labs, never smoker/drinker | CTRI/2024/05/062517 → Potentially Eligible |
| S007 | 45 F | T2DM + Diabetic Nephropathy | eGFR 45, urine ACR 350, HbA1c 8.9 | CTRI/2024/07/062744 → Potentially Eligible |
| S008 | 52 M | Type 2 Diabetes Mellitus | HbA1c 8.1, duration 10 y, eGFR 85 | CTRI/2024/01/062001 → Potentially Eligible |
| S009 | 67 M | COPD | 30 pack-years, FEV1 low | CTRI/2025/04/063673 → Potentially Eligible |
| S010 | 32 F | Prediabetes | FBG 118, HbA1c 6.1, vitamin D 22 ng/mL | CTRI/2024/11/063128 → Potentially Eligible |

The Find Trials structured form also has four one-click sample buttons
(Diabetes 47F, Hypertension 58M, Asthma 24F, Healthy volunteer 28M) and a
**+ Add another patient** cohort mode: each added patient gets its own form,
all patients are matched in one run, results are browsed patient-by-patient,
and the whole cohort can be downloaded as Excel.

## Find Trials — unstructured samples

Upload `unstructured_patients_find_trials.csv` (or the evaluation file — both
work) in the **Unstructured Data** tab. The page extracts each note with the ML
NER, then shows one patient at a time ("Patient 1 of 10 → Next patient") with
that patient's own fact chips and its own **Find Matching Trials** button.
Accepted uploads: PDF, image/photo (OCR), CSV, Excel, TXT, JSON.

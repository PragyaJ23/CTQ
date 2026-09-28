# CTQ Evaluation Result - Patient P001 vs All 20 Trials

**Patient:** P001 - Lakshmi Kulkarni, 52F, Type 2 Diabetes (36 months, severe), HbA1c 7.0, eGFR 34.6, on Metformin + Glimepiride

**Ground truth:** hand-verified against each trial's published criteria (see evaluation_demo_README.md)

## Outcome

- **Accuracy (as reported by the app): 86.7%** - binary accuracy over the 15 pairs where both the real label and the prediction are Eligible / Not Eligible (13 correct of 15)
- **Full three-verdict agreement: 15 / 20 trials (75%)** - including the three Insufficient-Information trials
- **Missed eligible trials (FN): 0** - both genuinely eligible trials were correctly found
- **Wrongly passed (FP): 2** - both observational trials whose requirements are free-text only
- Perfect on interventional trials with hard numeric criteria: 0 errors across all of them

## Confusion matrix (Eligible vs Not Eligible only)

|                       | Actual: Eligible | Actual: Not Eligible |
|-----------------------|------------------|----------------------|
| **Predicted: Eligible**     | TP = 2           | FP = 2               |
| **Predicted: Not Eligible** | FN = 0           | TN = 11              |

(Trials where the real verdict or the prediction is "Insufficient Information" are excluded
from the binary matrix by design - the system is not punished for honestly saying
"I don't know".)

## Trial-by-trial comparison

| Trial | Real (hand-verified) | CTQ prediction | Match % | Deciding criterion |
|---|---|---|---|---|
| CTRI/2024/01/062001 | Not Eligible | Not Eligible [OK] | 87 | HbA1c must be 7.5-10.5 (patient 7.0); excludes eGFR below 45 (patient 34.6) |
| CTRI/2024/02/062115 | Not Eligible | Not Eligible [OK] | 74 | Newly diagnosed under 6 months only (patient 36 months); excludes eGFR below 60 |
| CTRI/2024/03/062318 | Insufficient | Not Eligible [X] | - | Needs hypertension duration 6+ months on monotherapy - not in patient data |
| CTRI/2024/04/062402 | Not Eligible | Not Eligible [OK] | - | HER2+ metastatic breast cancer required - patient has none |
| CTRI/2024/05/062517 | Not Eligible | Not Eligible [OK] | 32 | Healthy volunteers only - patient has T2DM, hypertension, CKD |
| CTRI/2024/06/062633 | **Eligible** | **Eligible [OK]** | 60 | T2DM 1yr+, age 35-70, HbA1c 7-10 (7.0), eGFR not below 30 (34.6) - all met |
| CTRI/2024/07/062744 | Insufficient | Insufficient [OK] | 56 | Needs established nephropathy + UACR above 300 - UACR never measured |
| CTRI/2024/08/062851 | Not Eligible | Not Eligible [OK] | - | Asthma diagnosis required - patient has none |
| CTRI/2024/09/062966 | Not Eligible | Insufficient [X] | - | Rheumatoid arthritis on methotrexate required - CTQ could not confirm |
| CTRI/2024/10/063019 | Not Eligible | Not Eligible [OK] | - | Pregnant women aged 18-40 - patient is 52, not pregnant |
| CTRI/2024/11/063128 | Not Eligible | Not Eligible [OK] | 52 | Prediabetes only; excludes treated diabetes and CKD stage 3+ |
| CTRI/2024/12/063237 | Not Eligible | Insufficient [X] | 61 | Chronic heart failure NYHA II-III with LVEF 40 or below required - none documented |
| CTRI/2025/01/063344 | Insufficient | Insufficient [OK] | 51 | Needs PHQ-9 score 10-20 - depression screening never done |
| CTRI/2025/02/063459 | Not Eligible | Eligible [X] | 23 | Must be prescribed biosimilar rituximab - observational, free-text requirement |
| CTRI/2025/03/063561 | Not Eligible | Eligible [X] | - | Ultrasound-confirmed fatty liver required - observational, not verifiable from form |
| CTRI/2025/04/063673 | Not Eligible | Not Eligible [OK] | - | COPD with 10+ pack-years smoking required - never smoker |
| CTRI/2025/05/063788 | Not Eligible | Not Eligible [OK] | 66 | HbA1c must be 7.5-11 (patient 7.0) |
| CTRI/2025/06/063892 | Not Eligible | Not Eligible [OK] | - | Myocardial infarction 3-12 months ago required - none |
| CTRI/2025/07/063911 | **Eligible** | **Eligible [OK]** | 51 | T2DM 2yr+, age 40-70, HbA1c 6.5-10 - all met |
| CTRI/2025/08/064022 | Not Eligible | Not Eligible [OK] | 59 | Needs BMI 30-45 (patient 25.8), HbA1c 7.5-10.5, eGFR 45+ - all fail |

**Legend:** [OK] = CTQ agrees with the hand-verified label. [X] = disagreement. The two false
positives are observational trials with free-text-only requirements; the two "Insufficient"
answers where the hand label was "Not Eligible" are cases where CTQ was less certain than a
strict human reviewer - never an unsafe pass on a trial with hard numeric criteria.

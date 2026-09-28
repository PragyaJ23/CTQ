# CTQ — Clinical Trial Qualifier

**AI-Assisted Clinical Trial Matching and Eligibility Analysis for Indian Patients**

CTQ is a research prototype that takes a patient's demographic and clinical information, retrieves
potentially relevant **Indian clinical trials (CTRI-style records)**, computes a **semantic
similarity (Match Score)**, runs a deterministic **eligibility criteria engine**, and uses an
LLM (Groq) only to interpret complex criteria and explain the decision.

It is deliberately **not** a "just ask the LLM" system:

```
Patient Data → Trial Retrieval → Similarity Matching → Eligibility Analysis → Explanation
                                     (embeddings)      (rules + LLM JSON)    (reasons + missing info)
```

> ⚠️ **Medical disclaimer** — CTQ is a research and decision-support prototype. Its results are not
> a medical diagnosis or a final determination of clinical-trial eligibility. Final eligibility must
> be confirmed by the trial investigators or qualified healthcare professionals. All bundled data is
> synthetic; no real patient information is used.

---

## Features

- **Patient → Trial Matcher** — full form (demographics, disease, history, medications, labs,
  pregnancy/smoking/alcohol, prior participation) **or** a Quick MCQ mode; both produce the same
  structured profile.
- **Two-stage retrieval** — structured pre-filter (disease domain, impossible age/gender) then
  sentence-transformer embeddings with cosine similarity; only the **top-K** trials reach the
  expensive stages.
- **Eligibility engine** — deterministic checks for age, gender, lab thresholds parsed from
  criterion text, disease duration, medication requirements ("on stable metformin", "insulin
  naive"), required co-conditions ("T2DM *with* nephropathy"), and exclusion keywords
  (pregnancy, smoking, alcohol, comorbidities).
- **Three verdicts** — `Potentially Eligible`, `Not Eligible`, and **`Insufficient Information`**
  when required data is missing (never a forced guess).
- **Groq LLM reasoning** — controlled prompt, strict JSON output, LLM can add reasoning but can
  never overturn a rule-detected hard failure. Works fully without the LLM (rules-only mode).
- **Trial Database page** — searchable/filterable CTRI-style registry with full trial detail pages.
- **Model Evaluation page** — upload unlabelled patients + ground-truth labels (CSV/JSON), run the
  pipeline, get **accuracy, precision, recall, F1, specificity, confusion matrix**, per-trial /
  per-patient breakdowns, incorrect-prediction analysis. One-click run on the bundled sample data.
- **Transparency** — every result shows trial source, dataset version, last-updated date and whether
  the LLM was used. The Match Score is always labelled as semantic similarity, **never** as a
  probability of eligibility.

---

## Project structure

```
CTQ/
├── backend/
│   ├── main.py                  # FastAPI app (CORS, startup, error handler)
│   ├── config.py                # settings from .env (GROQ_API_KEY etc.)
│   ├── models.py                # Pydantic schemas (profile, trial, results, evaluation)
│   ├── api/routes.py            # all /api/* endpoints
│   ├── services/
│   │   ├── profile_builder.py   # form/quick/CSV → structured PatientProfile
│   │   ├── trial_retrieval.py   # pre-filter + embedding ranking (top-K)
│   │   ├── embeddings.py        # sentence-transformers (+ offline fallback)
│   │   ├── eligibility.py       # deterministic criteria engine
│   │   ├── llm.py               # Groq client, prompt, strict JSON, veto merge
│   │   ├── matching.py          # orchestrates the full pipeline
│   │   ├── evaluation.py        # metrics + confusion matrix + breakdowns
│   │   └── database.py          # SQLite (trials, evaluation runs)
│   ├── generate_data.py         # synthetic Indian trials/patients/ground truth
│   ├── data/
│   │   ├── trials.json          # 20 synthetic CTRI-style trials (imported to SQLite on first run)
│   │   ├── sample_patients.csv  # 80 synthetic Indian patients
│   │   └── sample_ground_truth.csv  # 1600 patient×trial labels (1/0/2)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # React 18 + Vite + Recharts
│   └── src/{components,pages,services}
└── .gitignore
```

---

## Setup

### 1. Backend (Python 3.10+)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

Configure the LLM (optional but recommended):

```bash
copy .env.example .env        # macOS/Linux: cp .env.example .env
# edit .env and set:
#   GROQ_API_KEY=gsk_...      # free key: https://console.groq.com/keys
```

Generate the sample datasets and start the API:

```bash
python generate_data.py       # creates backend/data/*.csv + trials.json
uvicorn main:app --reload --port 8000
```

- API: http://127.0.0.1:8000  · docs: http://127.0.0.1:8000/docs
- Without a `GROQ_API_KEY` everything still works — the app simply runs in
  rules-only mode and says so in the UI.

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The dev server proxies `/api/*` to `http://127.0.0.1:8000`. To point the frontend elsewhere, set
`VITE_API_URL` in `frontend/.env.local` (e.g. for a production build).

> The first matching request downloads the embedding model (~90 MB, cached afterwards). All later
> requests are fast (<1 s per patient in rules-only mode).

---

## Example API requests

**Analyze a patient** (`POST /api/patient/analyze`):

```bash
curl -X POST http://127.0.0.1:8000/api/patient/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "P001", "age": 47, "gender": "Female",
    "state": "West Bengal", "city": "Kolkata",
    "condition": "Type 2 Diabetes", "disease_duration_months": 24,
    "hba1c": 8.2, "systolic_bp": 138, "diastolic_bp": 86,
    "comorbidities": {"Diabetes": "Yes", "Hypertension": "Yes"},
    "current_medications": [{"name": "Metformin", "duration_months": 12}]
  }'
```

Response (abridged):

```json
{
  "patient_id": "P001",
  "llm_used": false,
  "results": [
    {
      "trial_id": "CTRI/2024/01/062001",
      "title": "A Randomised Open Label Trial of Glimepiride ...",
      "eligibility": "Insufficient Information",
      "similarity_score": 0.744,
      "match_percent": 91,
      "reasons_for": ["Patient age 47 is within the required range 30-65 years", "..."],
      "reasons_against": [],
      "missing_information": ["BMI value (trial requires: \"Body mass index between 23 and 35\")"],
      "failed_criteria": []
    }
  ]
}
```

Other endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/patient/analyze` | Full matching pipeline (optionally `?top_k=10`) |
| POST | `/api/patient/validate` | Validate a payload without matching |
| GET | `/api/trials` | Search trials (`?q=&condition=&state=&status=&phase=&study_type=&gender=&max_age=`) |
| GET | `/api/trials/{trial_id}` | Complete trial record |
| POST | `/api/trials/import` | Upload more trials (same JSON schema as `trials.json`) |
| GET | `/api/meta` | Facet values, dataset version, LLM status |
| POST | `/api/upload/patients` | Upload unlabelled patients (CSV/JSON) |
| POST | `/api/upload/labels` | Upload ground truth (`patient_id,trial_id,actual_label`) |
| POST | `/api/evaluate` | `{ "patients": [...], "labels": [...] }` → metrics |
| POST | `/api/evaluation/run-sample` | Evaluate on the bundled sample dataset |
| GET | `/api/evaluation/runs` | Past evaluation runs |
| GET | `/api/health` | Trials loaded, LLM configured |

**Run the sample evaluation**:

```bash
curl -X POST http://127.0.0.1:8000/api/evaluation/run-sample
```

Bundled-sample results with the default configuration:

```
Accuracy 97.3% · Precision 77.5% · Recall 93.9% · F1 84.9% · Specificity 97.6%
Confusion: TP=93 FP=27 FN=6 TN=1115
Insufficient-detection rate: 59.5%
(excluded_pred_insufficient=317, excluded_actual_insufficient=42)
```

---

## Evaluation protocol

Labels: `1 = Eligible`, `0 = Not Eligible`, `2 = Insufficient Information`.
Positive class: **Potentially Eligible**.

- Rows where the *model* answers "Insufficient Information" are excluded from the binary matrix
  (it declined to classify — forcing them into a class would be guessing) and reported as
  `excluded_pred_insufficient`.
- Rows whose *truth* is 2 are likewise excluded and tracked via the
  **insufficient-detection rate**: of the pairs that truly lack information, the share where CTQ
  also said "Insufficient Information" instead of guessing.
- Everything else forms the classic TP/FP/FN/TN matrix; precision/recall/F1/specificity follow.

---

## Adding real data

**More trials** — append objects to `backend/data/trials.json` (or upload via
`POST /api/trials/import`):

```json
{
  "trial_id": "CTRI/2025/09/XXXXXX",
  "title": "...", "condition": "...", "status": "Recruiting",
  "phase": "Phase III", "study_type": "Interventional", "gender": "Both",
  "min_age": 18, "max_age": 65,
  "inclusion_criteria": ["..."], "exclusion_criteria": ["..."],
  "locations": ["Kolkata, West Bengal"], "sponsor": "...",
  "interventions": ["..."], "source": "CTRI", "last_updated": "2025-08-15"
}
```

Delete `backend/data/ctq.db` (or call the import endpoint) and restart to re-import. The retrieval
layer is modular: swap `services/trial_retrieval.load_trials()` for a live CTRI feed without
touching the rest of the pipeline.

**More patients/labels** — produce CSVs with `patient_id` (+ any profile fields: `age`, `gender`,
`condition`, `hba1c`, `egfr`, `bmi`, `current_medications`, `comorbidities` as
`"Diabetes: Yes; ..."`...) and `patient_id,trial_id,actual_label` for labels; upload them on the
Model Evaluation page.

**Regenerate synthetic data** — `python generate_data.py` (seeded, deterministic).

---

## Demo walkthrough (5 minutes)

1. **Home** → *Find Clinical Trials*.
2. Fill the form: Age 47, Female, West Bengal/Kolkata, Condition "Type 2 Diabetes",
   duration 24 months, tick Diabetes + Hypertension, HbA1c 8.2, SBP/DBP 138/86, add Metformin.
   (Or use the Quick MCQ tab.)
3. **Find Matching Trials** → results ranked by Match Score with eligibility verdicts, itemised
   reasons and missing-information notes. Filter by eligibility/state/phase; open any trial for
   full details.
4. **Model Evaluation** → *Run with bundled sample data* → metrics, confusion matrix,
   incorrect-prediction analysis, per-patient/per-trial accuracy.
5. **Trial Database** → search/filter the registry; **About / Methodology** → how it works.

---

## Design notes & safety

- **Similarity ≠ eligibility.** The Match Score rescales cosine similarity for display; eligibility
  comes from criteria checking. A 91% match can still be Not Eligible.
- **The LLM cannot invent facts.** It receives only the structured profile and the trial's own
  criteria; it must mark unevaluable criteria UNKNOWN and return strict JSON (invalid output is
  discarded). Rule-detected hard failures cannot be overturned by the LLM.
- **The API key never reaches the frontend** — it lives in `backend/.env` (git-ignored).
- **No stack traces leak to the UI** — a global handler converts errors into friendly messages.
- **Extensible** — planned hooks for PDF/OCR intake, clinical notes, multilingual input, medical
  NER, EHR integration, PostgreSQL, auth, investigator dashboards and live CTRI sync (see
  About/Methodology in the app).

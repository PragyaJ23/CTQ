"""All CTQ API endpoints (see spec §41, §42)."""
import io
import json
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from config import settings
from models import AnalyzeResponse, PatientProfile, Trial
from services import database, evaluation, matching
from services.profile_builder import build_profile, validate_profile

router = APIRouter(prefix="/api")

ALLOWED_TRIAL_COLUMNS = {"trial_id", "title", "condition", "status", "phase", "study_type",
                         "gender", "min_age", "max_age", "inclusion_criteria", "exclusion_criteria",
                         "locations", "sponsor", "interventions", "source", "last_updated"}

# Alternative column names accepted on upload, mapped to the canonical schema.
COLUMN_ALIASES = {
    "sex": "gender",
    "primary_condition": "condition",
    "disease": "condition",
    "diagnosis": "condition",
    "hba1c_percent": "hba1c",
    "hba1c_%": "hba1c",
    "fasting_glucose_mg_dl": "fasting_glucose",
    "fasting_blood_glucose": "fasting_glucose",
    "total_cholesterol_mg_dl": "cholesterol",
    "total_cholesterol": "cholesterol",
    "ldl_mg_dl": "ldl",
    "hdl_mg_dl": "hdl",
    "triglycerides_mg_dl": "triglycerides",
    "creatinine_mg_dl": "creatinine",
    "hemoglobin_g_dl": "hemoglobin",
    "wbc_per_ul": "wbc",
    "platelets_per_ul": "platelets",
    "alt_u_l": "alt",
    "ast_u_l": "ast",
    "bilirubin_mg_dl": "bilirubin",
    "medical_history": "other_medical_history",
    "comorbidities_history": "comorbidities",
    "medications": "current_medications",
    "current_meds": "current_medications",
    "previous_treatment_failure": "treatment_failure",
    "prior_treatment_failure": "treatment_failure",
    "duration_months": "disease_duration_months",
    "weight": "weight_kg",
    "height": "height_cm",
    "allergies": "drug_allergies",
}

LABEL_WORDS = {
    "1": "1", "eligible": "1", "potentially eligible": "1", "yes": "1", "true": "1",
    "0": "0", "not eligible": "0", "ineligible": "0", "no": "0", "false": "0",
    "2": "2", "insufficient": "2", "insufficient information": "2",
}


# ---------------------------------------------------------------------------
# Patient matching
# ---------------------------------------------------------------------------

@router.post("/patient/analyze", response_model=AnalyzeResponse)
def analyze_patient(payload: dict, top_k: Optional[int] = Query(None, ge=1, le=100)):
    """Analyse a patient profile and return ranked matching trials.

    Accepts the full-form payload (structured data), a payload containing
    extracted facts (from unstructured documents), a quick-MCQ payload, or a
    flat CSV-style row. Every trial in the database is checked.
    """
    profile = build_profile(payload)
    warnings = validate_profile(profile)
    try:
        response = matching.analyze_patient(profile, top_k=top_k)
    except Exception as exc:  # embeddings/DB errors surface as a friendly message
        raise HTTPException(status_code=500, detail=f"Matching failed: {exc}") from exc
    response.warnings = warnings
    return response


@router.post("/patient/analyze-batch")
def analyze_batch(payload: dict):
    """Evaluate unstructured patient data against labelled structured data.

    Payload:
      patients: unstructured rows [{patient_id, clinical_notes | text, ...}]
                (already-extracted structured rows are also accepted)
      labels:   [{patient_id, trial_id, actual_label}] ground truth
                (actual_label: 1 eligible / 0 not eligible / 2 insufficient)

    Each unstructured patient is converted to a structured profile by the
    DistilBERT ML NER, then every trial in the database is checked for them.
    Predictions for the labelled pairs are compared with the ground truth:
    accuracy, precision, recall, F1 and the confusion matrix.
    """
    from services.ml_ner import extract_entities

    patients_raw = payload.get("patients") or []
    labels = payload.get("labels") or []
    if not patients_raw:
        raise HTTPException(status_code=400, detail="No unstructured patient data provided.")
    if not labels:
        raise HTTPException(status_code=400, detail="No labelled structured data provided.")
    if len(patients_raw) > 200:
        raise HTTPException(status_code=400, detail="Please limit unstructured patients to 200 per run.")

    # 1. unstructured -> structured profiles (explicit fields win)
    profiles = {}
    extraction_log = []
    for i, raw in enumerate(patients_raw):
        raw = raw or {}
        pid = str(raw.get("patient_id") or raw.get("id") or f"P{i+1:03d}")
        notes = (raw.get("clinical_notes") or raw.get("text") or raw.get("notes")
                 or raw.get("summary") or raw.get("medical_history") or "")
        facts = {}
        if isinstance(notes, str) and notes.strip():
            res = extract_entities(notes)
            facts = res.get("facts") or {}
            extraction_log.append({"patient_id": pid, "model_used": res["model_used"],
                                   "facts": facts})
        merged = {**facts, **{k: v for k, v in raw.items() if v not in (None, "")},
                  "patient_id": pid}
        try:
            profiles[pid] = build_profile(merged)
        except Exception:
            continue
    if not profiles:
        raise HTTPException(status_code=400, detail="No valid patients could be parsed.")

    # 2. check every trial for every patient (same code path as single matching)
    trials_by_id = {t.trial_id: t for t in trial_retrieval_load()}
    all_trials = list(trials_by_id.values())
    from services.embeddings import cosine_similarity, embed_texts
    from services.eligibility import evaluate_eligibility

    trial_vecs = {t.trial_id: embed_texts([t.criteria_text()])[0] for t in all_trials}
    patient_preds: dict = {}
    for pid, profile in profiles.items():
        pvec = embed_texts([profile.to_text()])[0]
        preds = {}
        for t in all_trials:
            sim = cosine_similarity(pvec, trial_vecs[t.trial_id])
            rule = evaluate_eligibility(t, profile)
            preds[t.trial_id] = {"eligibility": rule["status"],
                                 "similarity": round(sim, 4)}
        patient_preds[pid] = preds

    # 3. score the labelled pairs
    unknown_trials = sorted({l["trial_id"] for l in labels} - set(trials_by_id))
    if unknown_trials:
        raise HTTPException(status_code=400,
                            detail=f"Labelled trial IDs not in the database: {', '.join(unknown_trials[:5])}")

    from models import EvaluationRow
    rows, skipped = [], []
    for l in labels:
        pid, tid = str(l["patient_id"]), str(l["trial_id"])
        pred = patient_preds.get(pid, {}).get(tid)
        if pred is None:
            skipped.append(f"{pid}->{tid}")
            continue
        rows.append(EvaluationRow(patient_id=pid, trial_id=tid,
                                  predicted=pred["eligibility"],
                                  actual=evaluation._normalise_label(l["actual_label"])))
    if not rows:
        raise HTTPException(status_code=400, detail="No labelled pairs matched the provided patients.")
    metrics = evaluation.compute_metrics(rows)
    summary = {"accuracy": metrics.accuracy, "precision": metrics.precision,
               "recall": metrics.recall, "f1": metrics.f1,
               "specificity": metrics.specificity, "confusion": metrics.confusion}
    run_id = database.save_evaluation_run(summary, [r.model_dump() for r in rows])

    return {
        "run_id": run_id,
        "patients_evaluated": len(profiles),
        "pairs_labelled": len(rows),
        "skipped_pairs": skipped,
        "metrics": summary,
        "per_trial": metrics.per_trial,
        "per_patient": metrics.per_patient,
        "rows": [r.model_dump() for r in rows],
        "extraction_log": extraction_log,
        "llm_used": False,
    }


@router.post("/patient/validate")
def validate_patient(payload: dict):
    """Validate the form payload without running the full pipeline."""
    profile = build_profile(payload)
    return {"warnings": validate_profile(profile), "profile_text": profile.to_text()}


# ---------------------------------------------------------------------------
# Trials
# ---------------------------------------------------------------------------

def _trial_to_dict(t: Trial) -> dict:
    return t.model_dump()


@router.get("/trials")
def list_trials(
    q: Optional[str] = Query(None, description="Search text"),
    condition: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    study_type: Optional[str] = None,
    gender: Optional[str] = None,
    max_age: Optional[int] = Query(None, ge=0, le=120, description="Trial must include this age"),
):
    """Search / filter the Indian trial database."""
    trials = trial_retrieval_load()
    results = []
    for t in trials:
        d = _trial_to_dict(t)
        if q:
            haystack = " ".join([t.trial_id, t.title, t.condition, t.sponsor or "",
                                 " ".join(t.locations)]).lower()
            if q.lower() not in haystack:
                continue
        if condition and condition.lower() not in t.condition.lower():
            continue
        if state and not any(state.lower() in loc.lower() for loc in t.locations):
            continue
        if status and t.status.lower() != status.lower():
            continue
        if phase and t.phase.lower() != phase.lower():
            continue
        if study_type and t.study_type.lower() != study_type.lower():
            continue
        if gender and t.gender.lower() != gender.lower():
            continue
        if max_age is not None:
            if (t.min_age is not None and max_age < t.min_age) or (t.max_age is not None and max_age > t.max_age):
                continue
        results.append(d)
    return {
        "count": len(results),
        "total_in_database": len(trials),
        "dataset_version": "ctri-synthetic-demo-v1.0",
        "trials": results,
    }


def trial_retrieval_load():
    from services.trial_retrieval import load_trials
    return load_trials()


@router.get("/trials/{trial_id:path}")
def get_trial(trial_id: str):
    trial_retrieval_load()  # ensure DB initialised
    trial = database.get_trial(trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return _trial_to_dict(trial)


@router.post("/trials/import")
async def import_trials(file: UploadFile = File(...)):
    """Import additional CTRI trials from an uploaded JSON file (same schema as trials.json)."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Please upload a .json file matching the trials.json schema")
    try:
        raw = json.loads(await file.read())
        if not isinstance(raw, list):
            raise ValueError("Expected a JSON array of trial objects")
        trials = [Trial(**item) for item in raw]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid trial JSON: {exc}") from exc
    database.init_db()
    count = database.upsert_trials(trials)
    return {"imported": count, "total_in_database": database.trial_count()}


# ---------------------------------------------------------------------------
# Metadata for UI dropdowns
# ---------------------------------------------------------------------------

@router.get("/meta")
def meta():
    """Facet values + dataset info used by frontend filters."""
    trials = trial_retrieval_load()
    conditions = sorted({t.condition for t in trials})
    states = sorted({loc.split(",")[-1].strip() for t in trials for loc in t.locations if "," in loc})
    statuses = sorted({t.status for t in trials})
    phases = sorted({t.phase for t in trials})
    study_types = sorted({t.study_type for t in trials})
    return {
        "conditions": conditions,
        "states": states,
        "statuses": statuses,
        "phases": phases,
        "study_types": study_types,
        "dataset_version": "ctri-synthetic-demo-v1.0",
        "total_trials": len(trials),
        "llm_configured": bool(settings.groq_api_key),
        "llm_enabled": settings.llm_enabled,
        "groq_model": settings.groq_model,
        "embedding_model": settings.embedding_model,
        "top_k": settings.top_k_trials,
    }


# ---------------------------------------------------------------------------
# Uploads + evaluation
# ---------------------------------------------------------------------------

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip and alias-map column names onto the canonical schema."""
    renamed = {}
    for c in df.columns:
        key = str(c).strip().lower().replace(" ", "_")
        renamed[c] = COLUMN_ALIASES.get(key, key)
    return df.rename(columns=renamed)


async def _read_tabular(upload: UploadFile) -> pd.DataFrame:
    """Read an uploaded CSV / JSON / TXT / Excel / PDF file into a DataFrame."""
    name = (upload.filename or "").lower()
    raw = await upload.read()
    try:
        if name.endswith(".json"):
            data = json.loads(raw.decode("utf-8", errors="replace"))
            df = pd.DataFrame(data if isinstance(data, list) else data.get("rows", []))
        elif name.endswith(".pdf"):
            text = _extract_pdf_text(raw)
            rows = _parse_table_text(text)
            if not rows:
                raise HTTPException(
                    status_code=400,
                    detail="Could not find a table in the PDF. Please make sure the PDF contains "
                           "a header row with column names (e.g. patient_id, age, ...) followed by "
                           "one row per record. For reliable parsing, upload CSV or Excel.",
                )
            df = pd.DataFrame(rows[1:], columns=rows[0])
        elif name.endswith((".xlsx", ".xls")):
            try:
                df = pd.read_excel(io.BytesIO(raw))
            except ImportError:
                raise HTTPException(
                    status_code=400,
                    detail="Excel support is not installed on the server. Please upload CSV instead.",
                )
        elif name.endswith(".tsv") or name.endswith(".txt"):
            text = raw.decode("utf-8", errors="replace")
            try:
                df = pd.read_csv(io.StringIO(text), sep="\t")
            except Exception:
                df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
        elif name.endswith(".csv"):
            text = raw.decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(text))
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload CSV, TXT, Excel (.xlsx) or PDF.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc
    df = _normalise_columns(df)
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file contains no rows.")
    return df


def _extract_pdf_text(raw: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="PDF parsing is not installed on the server. Please upload CSV or Excel instead.",
        )
    try:
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc


def _parse_table_text(text: str) -> list:
    """Best-effort table extraction from plain text: split lines into columns.

    Tries tab separation first, then 2+ spaces, then commas. Returns a list of
    rows (first row = header) or an empty list if no plausible header is found.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    for sep_name, splitter in (
        ("tab", lambda ln: ln.split("\t")),
        ("spaces", lambda ln: [p for p in __import__("re").split(r"\s{2,}", ln) if p.strip()]),
        ("comma", lambda ln: ln.split(",")),
    ):
        rows = [[c.strip() for c in splitter(ln)] for ln in lines]
        widths = {len(r) for r in rows if r}
        if len(rows) >= 2 and len(widths) == 1 and next(iter(widths)) >= 2:
            header = [h.lower().replace(" ", "_") for h in rows[0]]
            if "patient_id" in header:
                return [header] + rows[1:]
    return []


def _require_columns(df: pd.DataFrame, required: set, context: str) -> None:
    missing = required - {c.strip().lower() for c in df.columns}
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"{context}: missing required column(s): {', '.join(sorted(missing))}. "
                   f"Found columns: {', '.join(df.columns)}",
        )


@router.post("/upload/patients")
async def upload_patients(file: UploadFile = File(...)):
    """Upload unlabelled patient data (CSV/JSON/TXT/Excel/PDF). Returns normalised profiles."""
    df = await _read_tabular(file)
    _require_columns(df, {"patient_id"}, "Unlabelled patient data")
    profiles = []
    for _, row in df.iterrows():
        payload = {k: (None if pd.isna(v) else v) for k, v in row.items() if pd.notna(v)}
        profiles.append(build_profile(payload).model_dump())
    return {"count": len(profiles), "patients": profiles}


@router.post("/upload/labels")
async def upload_labels(file: UploadFile = File(...)):
    """Upload ground-truth labels CSV/JSON (patient_id, trial_id, actual_label)."""
    df = await _read_tabular(file)
    _require_columns(df, {"patient_id", "trial_id", "actual_label"}, "Ground-truth labels")
    bad = []
    rows = []
    for i, row in df.iterrows():
        raw_label = str(row["actual_label"]).strip().lower()
        label = LABEL_WORDS.get(raw_label)
        if label is None:
            bad.append(f"row {i + 2}: actual_label='{row['actual_label']}' (expected 0, 1 or 2)")
            continue
        rows.append({"patient_id": str(row["patient_id"]), "trial_id": str(row["trial_id"]), "actual_label": label})
    return {"count": len(rows), "invalid_rows": bad, "labels": rows}


@router.post("/evaluate")
async def evaluate(payload: dict):
    """Run CTQ over labelled pairs and compute metrics.

    Expected payload:
      { "patients": [...profiles or flat rows...], "labels": [{patient_id, trial_id, actual_label}...] }
    """
    patients_raw = payload.get("patients") or []
    labels = payload.get("labels") or []
    if not patients_raw:
        raise HTTPException(status_code=400, detail="No patient data provided. Upload unlabelled patient data first.")
    if not labels:
        raise HTTPException(status_code=400, detail="No ground-truth labels provided. Upload labelled data first.")

    profiles = {p.get("patient_id"): build_profile(p) for p in patients_raw}
    trials_by_id = {t.trial_id: t for t in trial_retrieval_load()}

    from services.embeddings import cosine_similarity, embed_texts
    from services.eligibility import evaluate_eligibility

    unknown_trials = sorted({l["trial_id"] for l in labels} - set(trials_by_id))
    if unknown_trials:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unknown_trials)} trial ID(s) in the labels do not exist in this demo "
                   f"database (which uses CTRI-format IDs like 'CTRI/2024/01/062001'): "
                   f"{', '.join(unknown_trials[:5])}{' ...' if len(unknown_trials) > 5 else ''}. "
                   f"Evaluation cannot run against trials that are not in the database.",
        )

    # Embed each trial once (they repeat across patients)
    trial_ids = sorted({l["trial_id"] for l in labels if l["trial_id"] in trials_by_id})
    trial_vecs = {tid: embed_texts([trials_by_id[tid].criteria_text()])[0] for tid in trial_ids}
    patient_vecs = {pid: embed_texts([p.to_text()])[0] for pid, p in profiles.items()}

    rows, skipped = [], []
    for label in labels:
        pid, tid = label["patient_id"], label["trial_id"]
        profile = profiles.get(pid)
        trial = trials_by_id.get(tid)
        if profile is None or trial is None:
            skipped.append(f"{pid}->{tid}")
            continue
        sim = cosine_similarity(patient_vecs[pid], trial_vecs[tid])
        # Retrieval gate: only trials a normal run would surface are predicted.
        if sim < 0.25:
            predicted = "Not Eligible"
            rule_against = ["Trial was filtered out as not relevant to this patient (low semantic similarity)"]
        else:
            rule_result = evaluate_eligibility(trial, profile)
            predicted = rule_result["status"]
            rule_against = rule_result.get("reasons_against", [])[:2]
        rows.append({"patient_id": pid, "trial_id": tid, "predicted": predicted,
                     "actual": evaluation._normalise_label(label["actual_label"]),
                     "reasons_against": rule_against})

    from models import EvaluationRow
    eval_rows = [EvaluationRow(patient_id=r["patient_id"], trial_id=r["trial_id"],
                               predicted=r["predicted"], actual=r["actual"]) for r in rows]
    metrics = evaluation.compute_metrics(eval_rows)

    summary = {
        "accuracy": metrics.accuracy, "precision": metrics.precision, "recall": metrics.recall,
        "f1": metrics.f1, "specificity": metrics.specificity, "confusion": metrics.confusion,
    }
    run_id = database.save_evaluation_run(summary, rows)

    return {
        "run_id": run_id,
        "metrics": summary,
        "per_trial": metrics.per_trial,
        "per_patient": metrics.per_patient,
        "rows": rows,
        "skipped_pairs": skipped,
        "unknown_trials": unknown_trials,
        "llm_used": False,
    }


@router.get("/evaluation/runs")
def past_runs(limit: int = 10):
    return database.list_evaluation_runs(limit)


# ---------------------------------------------------------------------------
# ML-based NER demo (Future Scope #1)
# ---------------------------------------------------------------------------

@router.post("/ner/extract")
def ner_extract(payload: dict):
    """Run the ML-based NER over pasted clinical text and show what it finds.

    Transparency/demo endpoint for the extraction that also happens behind
    the scenes when clinical notes are uploaded with a patient profile.
    """
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Please paste some clinical note text.")
    if len(text) > 20000:
        text = text[:20000]
    from services.ml_ner import extract_entities, model_status
    result = extract_entities(text)
    return {**result, "engine": model_status()}


@router.get("/ner/status")
def ner_status():
    from services.ml_ner import model_status
    return model_status()


# ---------------------------------------------------------------------------
# Unstructured data -> ML extraction -> structured profile
# ---------------------------------------------------------------------------

@router.post("/extract/document")
async def extract_document(file: UploadFile = File(...)):
    """Extract structured entities from an unstructured document.

    Accepts photos of summaries/prescriptions (JPG/PNG, OCR), PDFs, and
    CSV/Excel/JSON/TXT files of clinical notes. The DistilBERT ML NER reads
    the text and produces structured profile fields. Returns the extracted
    facts per note plus a downloadable CSV.
    """
    from services.document_text import UnsupportedFile, document_to_text
    from services.ml_ner import extract_entities
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    try:
        doc = document_to_text(raw, file.filename or "")
    except UnsupportedFile as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read the file: {exc}") from exc

    text = (doc.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400,
                            detail="No readable text found in the file. If it is a photo, try a sharper image; if a PDF, make sure it contains text.")

    # one note per [ID] block for tables, otherwise the whole text as one note
    notes = doc.get("notes") or [{"id": file.filename or "document", "text": text}]
    if len(notes) > 100:
        notes = notes[:100]

    results = []
    for n in notes:
        res = extract_entities(n["text"])
        results.append({"note_id": n["id"], "facts": res["facts"],
                        "model_used": res["model_used"],
                        "text": n["text"]})

    # downloadable CSV: one row per note, one column per fact
    import csv as _csv
    import io as _io
    all_keys = ["age", "gender", "condition", "disease_duration_months", "symptoms",
                "current_medications", "smoking_status", "alcohol_use", "pregnancy_status",
                "height_cm", "weight_kg"] + sorted({k for r in results for k in (r["facts"].get("labs") or {})})
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["note_id"] + all_keys)
    for r in results:
        row = [r["note_id"]]
        for k in all_keys:
            v = r["facts"].get(k)
            if k == "current_medications" and isinstance(v, list):
                v = "; ".join(f"{m['name']}" + (f" {m['dose']}" if m.get('dose') else "")
                              + (f" ({m['frequency']})" if m.get('frequency') else "")
                              for m in v)
            elif isinstance(v, list):
                v = "; ".join(str(x) for x in v)
            elif isinstance(v, dict):
                v = "; ".join(f"{a}={b}" for a, b in v.items())
            row.append("" if v is None else v)
        w.writerow(row)

    return {
        "filename": file.filename,
        "kind": doc["kind"],
        "count": len(results),
        "text_preview": text[:1200],
        "results": results,
        "csv": buf.getvalue(),
    }


# ---------------------------------------------------------------------------
# Live trial ingestion from ClinicalTrials.gov (Future Scope #3)
# ---------------------------------------------------------------------------

@router.get("/trials/live/presets")
def live_presets():
    """Condition presets offered by the live-import panel."""
    from services.live_trials import PRESET_CONDITIONS
    return {"conditions": sorted(PRESET_CONDITIONS.keys())}


@router.post("/trials/import/live")
async def import_live(payload: dict):
    """Fetch real trials from ClinicalTrials.gov and add them to the database.

    Payload: {condition, max_studies (<=40), india_only, recruiting_only}
    """
    condition = str(payload.get("condition") or "").strip()
    if not condition:
        raise HTTPException(status_code=400, detail="Please choose a condition to import.")
    try:
        max_studies = int(payload.get("max_studies") or 15)
    except (TypeError, ValueError):
        max_studies = 15
    max_studies = max(1, min(max_studies, 40))
    india_only = bool(payload.get("india_only", True))
    recruiting_only = bool(payload.get("recruiting_only", True))

    from services.live_trials import PRESET_CONDITIONS, import_live_trials
    search_term = PRESET_CONDITIONS.get(condition, condition)
    try:
        summary = import_live_trials(search_term, max_studies=max_studies,
                                     india_only=india_only, recruiting_only=recruiting_only)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    summary["condition_label"] = condition
    return summary


# ---------------------------------------------------------------------------
# Cohort screening mode (Future Scope #4)
# ---------------------------------------------------------------------------

@router.post("/cohort/screen")
def cohort_analyze(payload: dict):
    """Screen a whole cohort of patients against the trial database.

    Payload: {"patients": [profile payloads or flat CSV rows], "top_k": optional}
    Runs the fast path (structured pre-filter + embeddings + rule engine; no
    LLM calls) per patient, then aggregates recruitment analytics:
      * overall verdict distribution across all patient-trial pairs
      * per-trial funnel (how many patients are potentially eligible)
      * per-site counts aggregated from trial locations
      * per-patient summary with each patient's best matching trial
    """
    from services.embeddings import cosine_similarity, embed_texts, score_to_match_percent
    from services.eligibility import evaluate_eligibility
    from services.trial_retrieval import prefilter_trials

    import time
    t0 = time.time()

    patients_raw = payload.get("patients") or []
    if not patients_raw:
        raise HTTPException(status_code=400, detail="No patients provided. Upload a cohort CSV first.")
    if len(patients_raw) > 500:
        raise HTTPException(status_code=400, detail="Cohort limited to 500 patients per run.")

    top_k = payload.get("top_k")
    if top_k is not None:
        try:
            top_k = max(1, min(int(top_k), 100))
        except (TypeError, ValueError):
            top_k = None

    profiles = []
    for i, raw in enumerate(patients_raw):
        try:
            profiles.append(build_profile(raw))
        except Exception:
            continue
    if not profiles:
        raise HTTPException(status_code=400, detail="No valid patient rows could be parsed from the upload.")

    trials = trial_retrieval_load()
    # Embed every trial once and reuse across the whole cohort
    trial_vecs = {t.trial_id: embed_texts([t.criteria_text()])[0] for t in trials}

    per_trial: dict = {}
    per_site: dict = {}
    per_patient: list = []
    verdict_totals = {"Potentially Eligible": 0, "Not Eligible": 0, "Insufficient Information": 0}
    pairs_considered = 0

    # TOP_K_TRIALS = 0 means "check every trial"; a plain slice of 0 would
    # silently screen nobody, so fall back to the whole candidate list.
    k = top_k or settings.top_k_trials or len(trials)
    for profile in profiles:
        candidates = prefilter_trials(trials, profile)
        if not candidates:
            per_patient.append({"patient_id": profile.patient_id or "(unnamed)",
                                "eligible_count": 0, "screened": 0, "top": None})
            continue
        patient_vec = embed_texts([profile.to_text()])[0]
        scored = []
        for trial, _notes in candidates:
            sim = cosine_similarity(patient_vec, trial_vecs[trial.trial_id])
            scored.append((trial, sim))
        scored.sort(key=lambda s: s[1], reverse=True)
        scored = scored[:k]

        eligible_count = 0
        insufficient_count = 0
        best = None
        for trial, sim in scored:
            rule = evaluate_eligibility(trial, profile)
            status = rule["status"]
            verdict_totals[status] = verdict_totals.get(status, 0) + 1
            pairs_considered += 1
            bucket = per_trial.setdefault(trial.trial_id, {
                "trial_id": trial.trial_id, "title": trial.title, "condition": trial.condition,
                "status": trial.status, "phase": trial.phase, "locations": trial.locations,
                "source": trial.source,
                "Potentially Eligible": 0, "Not Eligible": 0, "Insufficient Information": 0,
                "total_similarity": 0.0, "pairs": 0,
            })
            bucket[status] += 1
            bucket["total_similarity"] += sim
            bucket["pairs"] += 1
            for loc in trial.locations:
                per_site.setdefault(loc, {"site": loc, "Potentially Eligible": 0, "pairs": 0})
                per_site[loc]["pairs"] += 1
                if status == "Potentially Eligible":
                    per_site[loc]["Potentially Eligible"] += 1
            if status == "Potentially Eligible":
                eligible_count += 1
            elif status == "Insufficient Information":
                insufficient_count += 1
            if best is None and status == "Potentially Eligible":
                best = {"trial_id": trial.trial_id, "title": trial.title,
                        "eligibility": status, "match_percent": score_to_match_percent(sim)}
        if best is None and scored:
            top_trial, top_sim = scored[0]
            best = {"trial_id": top_trial.trial_id, "title": top_trial.title,
                    "eligibility": evaluate_eligibility(top_trial, profile)["status"],
                    "match_percent": score_to_match_percent(top_sim)}
        per_patient.append({"patient_id": profile.patient_id or "(unnamed)",
                            "condition": profile.condition,
                            "eligible_count": eligible_count,
                            "insufficient_count": insufficient_count,
                            "screened": len(scored), "top": best})

    trial_rows = []
    for bucket in per_trial.values():
        pairs = bucket.pop("pairs")
        bucket["pairs"] = pairs
        bucket["avg_similarity"] = round(bucket.pop("total_similarity") / pairs, 4) if pairs else 0.0
        bucket["eligibility_rate"] = round(bucket["Potentially Eligible"] / pairs, 4) if pairs else 0.0
        trial_rows.append(bucket)
    trial_rows.sort(key=lambda b: (-b["Potentially Eligible"], -b["eligibility_rate"]))

    site_rows = sorted(per_site.values(), key=lambda s: (-s["Potentially Eligible"], -s["pairs"]))

    elapsed = round(time.time() - t0, 2)
    return {
        "patients_screened": len(profiles),
        "trials_considered": len(trials),
        "pairs_evaluated": pairs_considered,
        "verdict_totals": verdict_totals,
        "per_trial": trial_rows,
        "per_site": site_rows,
        "per_patient": per_patient,
        "llm_used": False,
        "processing_seconds": elapsed,
    }


@router.post("/evaluation/run-sample")
async def evaluate_sample():
    """Run evaluation on the bundled sample dataset (ground truth + patients CSVs).

    Lets users see the full evaluation dashboard with one click, without
    uploading anything. Uses the same code path as a manual upload.
    """
    from config import DATA_DIR
    import csv as _csv

    patients_file = DATA_DIR / "sample_patients.csv"
    labels_file = DATA_DIR / "sample_ground_truth.csv"
    if not patients_file.exists() or not labels_file.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found. Run backend/generate_data.py first.")

    with open(patients_file, encoding="utf-8") as f:
        patients_raw = list(_csv.DictReader(f))
    with open(labels_file, encoding="utf-8") as f:
        labels = list(_csv.DictReader(f))
    return await evaluate({"patients": patients_raw, "labels": labels})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
def health():
    trial_retrieval_load()
    return {
        "status": "ok",
        "trials_loaded": database.trial_count(),
        "llm_configured": bool(settings.groq_api_key),
        "llm_enabled": settings.llm_enabled,
    }

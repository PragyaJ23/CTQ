"""Bundled synthetic sample data.

The files live in ``sample_data/`` at the repository root and are shipped with
the app so a demo can be run without preparing CSVs by hand.
"""
import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException

samples_router = APIRouter(prefix="/api")

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"

EVAL_PATIENTS_FILE = "evaluation_patients_unstructured.csv"
EVAL_LABELS_FILE = "evaluation_labels_ground_truth.csv"
FIND_TRIALS_PATIENTS_FILE = "unstructured_patients_find_trials.csv"


def _rows(filename: str) -> list:
    path = SAMPLE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404,
                            detail=f"Sample file {filename} is not available in this deployment.")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [r for r in csv.DictReader(handle)]


def _patients(filename: str) -> list:
    out = []
    for row in _rows(filename):
        pid = (row.get("patient_id") or "").strip()
        notes = (row.get("notes") or row.get("clinical_notes") or row.get("text") or "").strip()
        if pid and notes:
            out.append({"patient_id": pid, "text": notes})
    return out


@samples_router.get("/evaluation/sample-data")
def evaluation_sample_data():
    """Unstructured notes + ground-truth labels, ready for the evaluation run."""
    patients = _patients(EVAL_PATIENTS_FILE)
    labels = []
    for row in _rows(EVAL_LABELS_FILE):
        raw = str(row.get("actual_label", "")).strip().lower()
        if raw in ("0", "1", "2"):
            label = int(raw)
        elif raw in ("eligible", "potentially eligible"):
            label = 1
        elif raw in ("not eligible", "ineligible"):
            label = 0
        else:
            label = 2
        pid, tid = (row.get("patient_id") or "").strip(), (row.get("trial_id") or "").strip()
        if pid and tid:
            labels.append({"patient_id": pid, "trial_id": tid, "actual_label": label})
    if not patients or not labels:
        raise HTTPException(status_code=500, detail="Bundled sample data files are empty.")
    return {
        "patients": patients,
        "labels": labels,
        "files": {"patients": EVAL_PATIENTS_FILE, "labels": EVAL_LABELS_FILE},
    }


@samples_router.get("/find-trials/sample-data")
def find_trials_sample_data():
    """Unstructured notes without labels - for the Find Trials upload flow."""
    patients = _patients(FIND_TRIALS_PATIENTS_FILE)
    if not patients:
        raise HTTPException(status_code=500, detail="Bundled sample patient notes are empty.")
    return {"patients": patients, "file": FIND_TRIALS_PATIENTS_FILE}

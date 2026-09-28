"""Cohort endpoints: analyse several patients at once and export their
details to Excel.

Reuse note: per-patient analysis calls the SAME code path as the single
patient form (/api/patient/analyze), so cohort results always agree with
single-patient results.
"""
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.routes import analyze_patient

cohort_router = APIRouter(prefix="/api")

# Columns written to the Excel export, in order (patient form fields first).
EXPORT_COLUMNS = [
    "patient_id", "age", "gender", "state", "city", "height_cm", "weight_kg",
    "bmi", "condition", "disease_duration_months", "disease_severity",
    "symptoms", "previous_diagnosis", "comorbidities",
    "current_medications", "previous_treatments", "treatment_failure",
    "drug_allergies", "hba1c", "fasting_glucose", "systolic_bp", "diastolic_bp",
    "creatinine", "egfr", "hemoglobin", "wbc", "platelets", "alt", "ast",
    "bilirubin", "cholesterol", "pregnancy_status", "smoking_status",
    "alcohol_use", "prior_trial_participation", "surgery_history",
    "infection_history", "organ_function_notes", "other_medical_history",
]


def _cell(value):
    """Flatten a payload value into a spreadsheet-friendly string/number."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, ""))
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            parts = []
            for m in value:
                bits = [str(m.get(k)) for k in ("name", "dose", "frequency", "duration_months")
                        if m.get(k) not in (None, "")]
                if bits:
                    parts.append(" ".join(bits))
            return "; ".join(parts)
        return "; ".join(str(v) for v in value if v not in (None, ""))
    return str(value)


@cohort_router.post("/cohort/analyze")
def analyze_cohort(payload: dict):
    """Analyse a cohort of structured patients, one full trial check each.

    Payload: {"patients": [<same shape as the single-patient form payload>]}
    Returns per-patient results in patient order.
    """
    patients = payload.get("patients") or []
    if not patients:
        raise HTTPException(status_code=400, detail="No patients provided.")
    if len(patients) > 100:
        raise HTTPException(status_code=400, detail="Please limit the cohort to 100 patients per run.")

    results = []
    for i, patient in enumerate(patients):
        patient = patient or {}
        pid = str(patient.get("patient_id") or f"P{i + 1:03d}")
        # keep the caller's ID even when the form left it blank
        patient = {**patient, "patient_id": pid}
        try:
            # call the shared handler directly: pass top_k explicitly, because
            # the FastAPI Query default object is not an int when called this way
            response = analyze_patient(patient, None)
            results.append({"patient_id": pid, "ok": True,
                            "response": response.model_dump()})
        except HTTPException as exc:
            results.append({"patient_id": pid, "ok": False, "error": exc.detail})
        except Exception as exc:  # one bad patient must not kill the cohort
            results.append({"patient_id": pid, "ok": False,
                            "error": f"Analysis failed: {exc}"})
    return {"patients_evaluated": sum(1 for r in results if r.get("ok")),
            "results": results}


@cohort_router.post("/cohort/export")
def export_cohort(payload: dict):
    """Download the entered cohort details as an Excel (.xlsx) workbook."""
    import openpyxl

    patients = payload.get("patients") or []
    if not patients:
        raise HTTPException(status_code=400, detail="No patients provided to export.")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    columns = list(EXPORT_COLUMNS)
    # include any extra keys the caller sent (form evolution safety)
    seen = set(columns)
    for patient in patients:
        for key in (patient or {}):
            if key not in seen:
                seen.add(key)
                columns.append(key)

    ws.append(columns)
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)
    for patient in patients:
        ws.append([_cell((patient or {}).get(col)) for col in columns])

    # sensible widths
    for idx, col in enumerate(columns, start=1):
        width = max(12, min(38, len(col) + 4))
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ctq_cohort_patients.xlsx"'},
    )

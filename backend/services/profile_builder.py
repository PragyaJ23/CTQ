"""Convert loose web-form / CSV payloads into a structured PatientProfile.

Both the full form, the Quick Patient Profile (MCQ) mode and uploaded CSV
files are normalised here, so the matching engine only ever sees one schema.

Free-text clinical notes ("clinical_notes" / "notes" payload keys, or the
"clinical_notes" CSV column) are run through the ML-based NER module and
merged into the structured fields - explicit form values always win.
"""
import json
from typing import Optional

from models import Medication, PatientProfile

YES_VALUES = {"yes", "y", "true", "1", "has", "present"}
NO_VALUES = {"no", "n", "false", "0", "none", "absent", "no history"}


def _to_yes_no_unknown(value) -> str:
    """Map arbitrary user/CSV values onto Yes / No / Unknown."""
    if value is None:
        return "Unknown"
    v = str(value).strip().lower()
    if v in ("", "unknown", "na", "n/a", "-"):
        return "Unknown"
    if v in YES_VALUES:
        return "Yes"
    if v in NO_VALUES:
        return "No"
    return "Unknown"


def _to_float(value) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


def _split_list(value) -> list:
    """Accept lists or comma/semicolon/newline separated strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).replace("\n", ",").replace(";", ",").split(",") if part.strip()]


COMORBIDITY_KEYS = [
    "Diabetes", "Hypertension", "Cardiovascular disease", "Kidney disease",
    "Liver disease", "Cancer", "Asthma", "COPD", "Thyroid disease",
    "Autoimmune disease", "Infectious diseases",
]


def build_profile(payload: dict) -> PatientProfile:
    """Normalise an arbitrary payload (form JSON or CSV row) into a profile."""
    payload = payload or {}

    # ---- Quick Patient Profile (MCQ) answers are merged in when present ----
    quick = payload.get("quick_answers") or {}

    # Comorbidities may arrive as a dict, or as a string such as
    # "Diabetes: Yes; Hypertension: No" (CSV upload format).
    raw_comorb = payload.get("comorbidities") or {}
    if isinstance(raw_comorb, str):
        comorbidities = {}
        for item in raw_comorb.replace("\n", ";").split(";"):
            if ":" in item:
                key, val = item.split(":", 1)
                comorbidities[key.strip()] = _to_yes_no_unknown(val)
            elif item.strip():
                comorbidities[item.strip()] = "Yes"
    else:
        comorbidities = raw_comorb

    bmi = _to_float(payload.get("bmi"))
    height = _to_float(payload.get("height_cm"))
    weight = _to_float(payload.get("weight_kg"))
    if bmi is None and height and weight:
        bmi = round(weight / ((height / 100) ** 2), 1)

    # Medications: list of dicts or comma string
    raw_meds = payload.get("current_medications") or []
    meds: list = []
    if isinstance(raw_meds, str):
        # CSV cells may carry the full medication as JSON, which keeps the dose,
        # frequency and duration the matching rules need (e.g. "stable
        # metformin for at least 3 months"); otherwise treat it as a name list.
        text = raw_meds.strip()
        if text.startswith("["):
            try:
                loaded = json.loads(text)
                raw_meds = loaded if isinstance(loaded, list) else _split_list(text)
            except json.JSONDecodeError:
                raw_meds = _split_list(text)
        else:
            raw_meds = _split_list(raw_meds)
    for m in raw_meds:
        if isinstance(m, dict) and m.get("name"):
            meds.append(Medication(
                name=m["name"],
                dose=(str(m["dose"]).strip() or None) if m.get("dose") else None,
                frequency=(str(m["frequency"]).strip() or None) if m.get("frequency") else None,
                duration_months=_to_float(m.get("duration_months")),
            ))
        elif isinstance(m, str) and m.strip():
            meds.append(Medication(name=m.strip()))

    profile = PatientProfile(
        patient_id=str(payload.get("patient_id") or "").strip(),
        age=_to_int(payload.get("age")),
        gender=(payload.get("gender") or None),
        state=(payload.get("state") or None),
        city=(payload.get("city") or None),
        height_cm=height,
        weight_kg=weight,
        bmi=bmi,
        condition=(payload.get("condition") or None),
        disease_duration_months=_to_float(payload.get("disease_duration_months")),
        disease_severity=(payload.get("disease_severity") or None),
        symptoms=_split_list(payload.get("symptoms")),
        previous_diagnosis=(payload.get("previous_diagnosis") or None),
        previous_treatments=_split_list(payload.get("previous_treatments")),
        comorbidities=comorbidities,
        other_medical_history=(payload.get("other_medical_history") or None),
        current_medications=meds,
        previous_medications=_split_list(payload.get("previous_medications")),
        treatment_failure=_to_yes_no_unknown(payload.get("treatment_failure")),
        drug_allergies=(payload.get("drug_allergies") or None),
        hba1c=_to_float(payload.get("hba1c")),
        fasting_glucose=_to_float(payload.get("fasting_glucose")),
        systolic_bp=_to_float(payload.get("systolic_bp")),
        diastolic_bp=_to_float(payload.get("diastolic_bp")),
        creatinine=_to_float(payload.get("creatinine")),
        egfr=_to_float(payload.get("egfr")),
        hemoglobin=_to_float(payload.get("hemoglobin")),
        wbc=_to_float(payload.get("wbc")),
        platelets=_to_float(payload.get("platelets")),
        alt=_to_float(payload.get("alt")),
        ast=_to_float(payload.get("ast")),
        bilirubin=_to_float(payload.get("bilirubin")),
        cholesterol=_to_float(payload.get("cholesterol")),
        fev1_percent=_to_float(payload.get("fev1_percent")),
        pregnancy_status=(payload.get("pregnancy_status") or None),
        smoking_status=(payload.get("smoking_status") or None),
        alcohol_use=(payload.get("alcohol_use") or None),
        prior_trial_participation=_to_yes_no_unknown(payload.get("prior_trial_participation")),
        surgery_history=(payload.get("surgery_history") or None),
        infection_history=(payload.get("infection_history") or None),
        organ_function_notes=(payload.get("organ_function_notes") or None),
    )

    # --- fold quick MCQ answers into the structured profile ---
    for key in COMORBIDITY_KEYS:
        if key in quick:
            profile.comorbidities[key] = _to_yes_no_unknown(quick[key])
    if quick.get("currently_taking_medication") is not None:
        taking = _to_yes_no_unknown(quick["currently_taking_medication"])
        if taking == "Yes" and not profile.current_medications:
            med_name = quick.get("current_medication_name") or "unspecified medication"
            profile.current_medications.append(Medication(name=str(med_name)))
    if quick.get("treatment_failure") is not None:
        profile.treatment_failure = _to_yes_no_unknown(quick["treatment_failure"])
    if quick.get("hba1c") is not None and profile.hba1c is None:
        profile.hba1c = _to_float(quick["hba1c"])
    if quick.get("previous_treatment_received") is not None:
        prev = _to_yes_no_unknown(quick["previous_treatment_received"])
        if prev == "Yes" and not profile.previous_treatments:
            tx = quick.get("previous_treatment_name") or "previous treatment"
            profile.previous_treatments.append(str(tx))
    if quick.get("pregnancy_status"):
        profile.pregnancy_status = quick["pregnancy_status"]

    # ---- Structured lab values may also arrive as a nested dict ----
    # (e.g. the ML NER facts handed straight back by the batch/evaluation
    # endpoint, or a caller that groups labs under one key). Explicit top-level
    # fields always win, so this only fills the gaps.
    for key, val in (payload.get("labs") or {}).items():
        if hasattr(profile, key) and getattr(profile, key) is None and val is not None:
            setattr(profile, key, _to_float(val))

    # ---- DistilBERT ML-based NER over free-text clinical notes ----
    # Production extraction path: ML-only, no regex discovery. Every value
    # comes from the model's answers; explicit form/CSV values win.
    notes = (payload.get("clinical_notes") or payload.get("notes") or "")
    if isinstance(notes, str) and notes.strip():
        from services.ml_ner import extract_entities
        ner = extract_entities(notes)
        profile._ner_report = {"model_used": ner["model_used"], "detail": ner["detail"]}
        e = ner.get("facts") or {}
        if profile.age is None and e.get("age") is not None:
            profile.age = int(e["age"])
        if not profile.gender and e.get("gender"):
            profile.gender = e["gender"]
        if not profile.condition and e.get("condition"):
            profile.condition = e["condition"]
        if not profile.symptoms and e.get("symptoms"):
            profile.symptoms = e["symptoms"]
        if profile.disease_duration_months is None and e.get("disease_duration_months") is not None:
            profile.disease_duration_months = float(e["disease_duration_months"])
        if not profile.current_medications and e.get("current_medications"):
            profile.current_medications = [
                Medication(name=m["name"], dose=m.get("dose"), frequency=m.get("frequency"),
                           duration_months=_to_float(m.get("duration_months")))
                for m in e["current_medications"] if m.get("name")
            ]
        for key in ("smoking_status", "alcohol_use", "pregnancy_status"):
            if getattr(profile, key) in (None, "Unknown") and e.get(key):
                setattr(profile, key, e[key])
        for key, val in (e.get("labs") or {}).items():
            if getattr(profile, key, None) is None:
                setattr(profile, key, val)
        if profile.height_cm is None and e.get("height_cm") is not None:
            profile.height_cm = float(e["height_cm"])
        if profile.weight_kg is None and e.get("weight_kg") is not None:
            profile.weight_kg = float(e["weight_kg"])
        # ML-extracted comorbidity history ("Liver disease": "No" ...) fills
        # gaps only - explicit form/MCQ answers always win.
        for key, val in (e.get("comorbidities") or {}).items():
            if profile.comorbidities.get(key) in (None, "", "Unknown"):
                profile.comorbidities[key] = val
        if profile.bmi is None and profile.height_cm and profile.weight_kg:
            profile.bmi = round(profile.weight_kg / ((profile.height_cm / 100) ** 2), 1)

    return profile


def validate_profile(profile: PatientProfile) -> list:
    """Return a list of user-friendly validation warnings (not fatal)."""
    warnings = []
    if profile.age is None:
        warnings.append("Age was not provided - age-based criteria cannot be checked.")
    if not profile.condition:
        warnings.append("Primary disease/condition was not provided - matching will be weak.")
    if profile.age is not None and (profile.age < 0 or profile.age > 120):
        warnings.append(f"Age {profile.age} looks invalid.")
    if profile.gender and profile.gender not in ("Male", "Female", "Other"):
        warnings.append("Gender should be Male, Female or Other.")
    return warnings

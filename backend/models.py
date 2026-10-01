"""Pydantic models shared across the CTQ backend.

PatientProfile  - structured patient information built from the web forms
Trial           - a single CTRI clinical trial record
MatchResult     - per-trial outcome (eligibility + similarity + reasons)
EvaluationRow   - one ground-truth comparison row
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EligibilityStatus = Literal[
    "Potentially Eligible", "Partially Eligible", "Not Eligible"
]

YES_NO_UNKNOWN = Literal["Yes", "No", "Unknown"]


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------
class Medication(BaseModel):
    name: str
    dose: Optional[str] = None          # e.g. "500 mg"
    frequency: Optional[str] = None     # e.g. "twice daily"
    duration_months: Optional[float] = None


class PatientProfile(BaseModel):
    """The single structured profile both form modes converge into."""

    patient_id: str = ""
    # Demographics
    age: Optional[int] = None
    gender: Optional[str] = None  # Male / Female / Other
    state: Optional[str] = None
    city: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None

    # Disease
    condition: Optional[str] = None
    disease_duration_months: Optional[float] = None
    disease_severity: Optional[str] = None  # Mild / Moderate / Severe
    symptoms: List[str] = Field(default_factory=list)
    previous_diagnosis: Optional[str] = None
    previous_treatments: List[str] = Field(default_factory=list)

    # Medical history (Yes/No/Unknown or free text)
    comorbidities: dict = Field(default_factory=dict)  # {"Diabetes": "Yes", ...}
    other_medical_history: Optional[str] = None

    # Medications
    current_medications: List[Medication] = Field(default_factory=list)
    previous_medications: List[str] = Field(default_factory=list)
    treatment_failure: YES_NO_UNKNOWN = "Unknown"
    drug_allergies: Optional[str] = None

    # Labs (all optional)
    hba1c: Optional[float] = None
    fasting_glucose: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    creatinine: Optional[float] = None
    egfr: Optional[float] = None
    hemoglobin: Optional[float] = None
    wbc: Optional[float] = None
    platelets: Optional[float] = None
    alt: Optional[float] = None
    ast: Optional[float] = None
    bilirubin: Optional[float] = None
    cholesterol: Optional[float] = None
    fev1_percent: Optional[float] = None  # FEV1 % of predicted (respiratory trials)

    # Other eligibility facts
    pregnancy_status: Optional[str] = None  # Not Pregnant / Pregnant / N-A / Unknown
    smoking_status: Optional[str] = None    # Never / Former / Current / Unknown
    alcohol_use: Optional[str] = None       # Never / Occasional / Regular / Unknown
    prior_trial_participation: YES_NO_UNKNOWN = "Unknown"
    surgery_history: Optional[str] = None
    infection_history: Optional[str] = None
    organ_function_notes: Optional[str] = None

    def to_text(self) -> str:
        """Human-readable profile used for embeddings and LLM prompts."""
        lines = [f"Age: {self.age if self.age is not None else 'Unknown'}"]
        lines.append(f"Gender: {self.gender or 'Unknown'}")
        if self.condition:
            lines.append(f"Primary condition: {self.condition}")
        if self.disease_severity:
            lines.append(f"Disease severity: {self.disease_severity}")
        if self.disease_duration_months is not None:
            lines.append(f"Disease duration (months): {self.disease_duration_months}")
        if self.symptoms:
            lines.append(f"Symptoms: {', '.join(self.symptoms)}")
        comorb = {k: v for k, v in self.comorbidities.items() if v and v != "Unknown"}
        if comorb:
            lines.append("Comorbidities: " + "; ".join(f"{k}: {v}" for k, v in comorb.items()))
        if self.other_medical_history:
            lines.append(f"Other history: {self.other_medical_history}")
        if self.current_medications:
            meds = ", ".join(
                m.name
                + (f" {m.dose}" if m.dose else "")
                + (f" {m.frequency}" if m.frequency else "")
                + (f" ({m.duration_months} mo)" if m.duration_months else "")
                for m in self.current_medications
            )
            lines.append(f"Current medications: {meds}")
        if self.previous_treatments:
            lines.append(f"Previous treatments: {', '.join(self.previous_treatments)}")
        labs = {
            "HbA1c": self.hba1c, "Fasting glucose": self.fasting_glucose,
            "BP": f"{self.systolic_bp}/{self.diastolic_bp}" if self.systolic_bp else None,
            "Creatinine": self.creatinine, "eGFR": self.egfr,
            "Hemoglobin": self.hemoglobin, "WBC": self.wbc, "Platelets": self.platelets,
            "ALT": self.alt, "AST": self.ast,            "Bilirubin": self.bilirubin,
            "Cholesterol": self.cholesterol,
            "BMI": self.bmi,
            "FEV1 (% predicted)": self.fev1_percent,
        }
        lab_str = "; ".join(f"{k}: {v}" for k, v in labs.items() if v is not None)
        if lab_str:
            lines.append(f"Labs: {lab_str}")
        for label, val in [
            ("Pregnancy status", self.pregnancy_status),
            ("Smoking", self.smoking_status),
            ("Alcohol", self.alcohol_use),
            ("Prior trial participation", self.prior_trial_participation),
            ("Surgery history", self.surgery_history),
            ("Infection history", self.infection_history),
            ("Organ function notes", self.organ_function_notes),
            ("Drug allergies", self.drug_allergies),
        ]:
            if val and val not in ("Unknown", "N-A"):
                lines.append(f"{label}: {val}")
        if self.state or self.city:
            lines.append(f"Location: {self.city or ''}, {self.state or ''}".strip(", "))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trial
# ---------------------------------------------------------------------------
class Trial(BaseModel):
    trial_id: str
    title: str
    condition: str
    status: str = "Unknown"          # Recruiting / Completed / ...
    phase: str = "N/A"               # Phase I/II/III/IV or N/A
    study_type: str = "Interventional"
    gender: str = "Both"             # Male / Female / Both
    min_age: Optional[float] = None
    max_age: Optional[float] = None
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)  # "City, State" strings
    sponsor: Optional[str] = None
    interventions: List[str] = Field(default_factory=list)
    source: str = "CTRI"             # registry provenance, shown in UI
    last_updated: Optional[str] = None

    def criteria_text(self) -> str:
        """Flat text used for embedding similarity."""
        parts = [self.title, self.condition, ", ".join(self.interventions)]
        parts += self.inclusion_criteria + [f"Exclude: {c}" for c in self.exclusion_criteria]
        return ". ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Matching output
# ---------------------------------------------------------------------------
class MatchResult(BaseModel):
    trial_id: str
    title: str
    condition: str
    status: str
    phase: str
    locations: List[str] = Field(default_factory=list)
    sponsor: Optional[str] = None
    source: str = "CTRI"
    last_updated: Optional[str] = None

    eligibility: EligibilityStatus
    similarity_score: float  # cosine similarity, 0..1 (NOT an eligibility probability)
    match_percent: int = 0   # display-only rescaling of similarity_score (0-100%)
    reasons_for: List[str] = Field(default_factory=list)
    reasons_against: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    failed_criteria: List[str] = Field(default_factory=list)
    reasoning_method: str = "rule"  # rule | rule+llm

    # Hindi renderings (offline glossary, services/en_hi.py) used by the
    # results table in हिंदी mode and the Hindi Excel sheets. Optional so
    # results produced before this field existed still validate; the frontend
    # and exporter fall back to the English values when missing.
    title_hi: Optional[str] = None
    condition_hi: Optional[str] = None
    reasons_for_hi: Optional[List[str]] = None
    reasons_against_hi: Optional[List[str]] = None
    missing_information_hi: Optional[List[str]] = None
    failed_criteria_hi: Optional[List[str]] = None


class AnalyzeResponse(BaseModel):
    patient_id: str
    results: List[MatchResult]
    llm_used: bool = False
    warnings: List[str] = Field(default_factory=list)  # input-validation notes


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
class EvaluationRow(BaseModel):
    patient_id: str
    trial_id: str
    predicted: str  # Potentially Eligible / Partially Eligible / Not Eligible
    actual: str     # 1 (eligible) / 0 (not eligible) / 2 (insufficient info)


class EvaluationResponse(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1: float
    specificity: float
    confusion: dict  # {"TP": .., "FP": .., "FN": .., "TN": .., "excluded_insufficient": ..}
    rows: List[EvaluationRow]
    per_trial: List[dict] = Field(default_factory=list)
    per_patient: List[dict] = Field(default_factory=list)

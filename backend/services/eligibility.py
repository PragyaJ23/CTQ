"""Rule-based eligibility engine.

Runs BEFORE any LLM call:
  * hard structural checks (age, gender)
  * numeric lab requirements parsed from inclusion/exclusion text
  * duration requirements ("diagnosed at least 2 years ago", "newly diagnosed
    within 6 months")
  * medication requirements ("on stable metformin therapy", "insulin naive")
  * co-condition requirements (trial targets "Type 2 Diabetes with Nephropathy")
  * exclusion keyword matching (pregnancy, smoking, alcohol, comorbidities)
  * missing-information detection

Produces one of:
  Potentially Eligible   - all known criteria satisfied
  Partially Eligible     - no criterion failed, but required data is missing
  Not Eligible           - a known criterion clearly fails

The LLM later reasons only over the trials that survive filtering, and can
never override a rule-detected hard failure.
"""
import re
from typing import List

from models import PatientProfile, Trial

FORCED_INELIGIBLE = "Not Eligible"
POTENTIALLY_ELIGIBLE = "Potentially Eligible"
PARTIALLY_ELIGIBLE = "Partially Eligible"


def _has(value) -> bool:
    return value is not None and str(value).strip() not in ("", "Unknown")


# ---------------------------------------------------------------------------
# Structured checks
# ---------------------------------------------------------------------------

def _fmt_age_range(trial: Trial) -> str:
    lo = int(trial.min_age) if _has(trial.min_age) else None
    hi = int(trial.max_age) if _has(trial.max_age) else None
    if lo is None and hi is None:
        return "any age"
    if lo is None:
        return f"<= {hi} years"
    if hi is None:
        return f">= {lo} years"
    return f"{lo}-{hi} years"


def check_age(trial: Trial, profile: PatientProfile):
    """Return (passed_reason, failed_reasons, missing)."""
    failed, missing = [], []
    if profile.age is None:
        if _has(trial.min_age) or _has(trial.max_age):
            missing.append(f"Patient age (trial requires {_fmt_age_range(trial)})")
        return None, failed, missing
    if _has(trial.min_age) and profile.age < trial.min_age:
        failed.append(
            f"Patient age {int(profile.age)} is below the trial minimum "
            f"of {int(trial.min_age)} (required {_fmt_age_range(trial)})"
        )
    if _has(trial.max_age) and profile.age > trial.max_age:
        failed.append(
            f"Patient age {int(profile.age)} is above the trial maximum "
            f"of {int(trial.max_age)} (required {_fmt_age_range(trial)})"
        )
    if not failed:
        return f"Patient age {int(profile.age)} is within the required range {_fmt_age_range(trial)}", failed, missing
    return None, failed, missing


def check_gender(trial: Trial, profile: PatientProfile):
    failed, missing, passed = [], [], None
    t = (trial.gender or "Both").strip().lower()
    if t in ("", "both", "all", "any"):
        return passed, failed, missing
    if not _has(profile.gender):
        missing.append("Patient gender (trial is restricted by gender)")
        return passed, failed, missing
    g = profile.gender.strip().lower()
    if g == "other" or (t == "female" and g == "male") or (t == "male" and g == "female"):
        failed.append(
            f"Trial accepts {'female' if t == 'female' else 'male'} participants only; "
            f"patient gender is {profile.gender}"
        )
    else:
        passed = f"Gender criterion satisfied (trial accepts {trial.gender}; patient is {profile.gender})"
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Numeric lab criteria parsed from criterion text
# ---------------------------------------------------------------------------

def _profile_labs(profile: PatientProfile) -> dict:
    return {
        "hba1c": profile.hba1c,
        "fasting_glucose": profile.fasting_glucose,
        "systolic": profile.systolic_bp,
        "diastolic": profile.diastolic_bp,
        "creatinine": profile.creatinine,
        "egfr": profile.egfr,
        "hemoglobin": profile.hemoglobin,
        "wbc": profile.wbc,
        "platelets": profile.platelets,
        "alt": profile.alt,
        "ast": profile.ast,
        "bilirubin": profile.bilirubin,
        "cholesterol": profile.cholesterol,
        "bmi": profile.bmi,
        "fev1_percent": profile.fev1_percent,
    }

LAB_LABELS = {
    "hba1c": "HbA1c", "fasting_glucose": "Fasting glucose", "systolic": "Systolic BP",
    "diastolic": "Diastolic BP", "creatinine": "Serum creatinine", "egfr": "eGFR",
    "hemoglobin": "Hemoglobin", "wbc": "WBC", "platelets": "Platelets", "alt": "ALT",
    "ast": "AST", "bilirubin": "Bilirubin", "cholesterol": "Cholesterol", "bmi": "BMI",
    "fev1_percent": "FEV1 (% predicted)",
}

_NUM = r"(\d+(?:\.\d+)?)"
_NUMERIC_PATTERNS = [
    (rf"(?:hba1c|a1c)[^.;{{}}]{{0,40}}?between\s+{_NUM}\s*(?:and|to|-|–)\s*{_NUM}", ("hba1c", "between")),
    (rf"(?:hba1c|a1c)[^.;]{{0,40}}?(?:at least|above|greater than|more than|over)\s*{_NUM}", ("hba1c", "min")),
    (rf"(?:hba1c|a1c)[^.;]{{0,40}}?(?:below|less than|under|up to)\s*{_NUM}", ("hba1c", "max")),
    (rf"fasting(?:\s+(?:plasma\s+)?glucose)?[^.;]{{0,40}}?between\s+{_NUM}\s*(?:and|to|-|–)\s*{_NUM}", ("fasting_glucose", "between")),
    (rf"(?:egfr|gfr)[^.;]{{0,40}}?between\s+{_NUM}\s*(?:and|to|-|–)\s*{_NUM}", ("egfr", "between")),
    (rf"(?:egfr|gfr)[^.;]{{0,40}}?(?:below|less than|under)\s*{_NUM}", ("egfr", "max")),
    (rf"(?:egfr|gfr)[^.;]{{0,40}}?(?:above|greater than|more than)\s*{_NUM}", ("egfr", "min")),
    (rf"creatinine[^.;]{{0,40}}?(?:below|less than|under)\s*{_NUM}", ("creatinine", "max")),
    (rf"creatinine[^.;]{{0,40}}?(?:above|greater than|more than)\s*{_NUM}", ("creatinine", "min")),
    (rf"(?:systolic(?:\s+bp)?|sbp)[^.;]{{0,40}}?(?:below|less than)\s*{_NUM}", ("systolic", "max")),
    (rf"(?:systolic(?:\s+bp)?|sbp)[^.;]{{0,40}}?(?:above|greater than|more than)\s*{_NUM}", ("systolic", "min")),
    (rf"hemoglobin[^.;]{{0,40}}?(?:below|less than|under)\s*{_NUM}", ("hemoglobin", "max")),
    (rf"hemoglobin[^.;]{{0,40}}?(?:above|greater than|more than)\s*{_NUM}", ("hemoglobin", "min")),
    (rf"(?:bmi|body mass index)[^.;]{{0,40}}?between\s+{_NUM}\s*(?:and|to|-|–)\s*{_NUM}", ("bmi", "between")),
    (rf"platelets?[^.;]{{0,40}}?(?:below|less than|under)\s*{_NUM}", ("platelets", "max")),
    (rf"alt[^.;]{{0,40}}?(?:above|greater than|more than)\s*{_NUM}", ("alt", "min")),
    (rf"fev1[^.;]{{0,40}}?between\s+{_NUM}\s*(?:and|to|-|–)\s*{_NUM}", ("fev1_percent", "between")),
]


def _parse_numeric_boundaries(text: str):
    """Extract (lab_key, kind, lo, hi) intents from a criterion string.

    kind describes the DIRECTION WORDS in the criterion:
      'min'     -> criterion says value must be >= lo (e.g. "above 90")
      'max'     -> criterion says value must be <= hi (e.g. "below 45")
      'between' -> lo <= value <= hi
    """
    bounds = []
    low = text.lower()
    for pattern, (key, kind) in _NUMERIC_PATTERNS:
        for m in re.finditer(pattern, low):
            matched = m.group(0)
            # Skip misfires such as "urinary albumin to creatinine ratio above
            # 300": that is urine ACR, not the serum creatinine field. Look a
            # little BEHIND the match too, because the pattern starts at
            # "creatinine" and the qualifier sits before it.
            if key == "creatinine" and re.search(r"urinary|albumin|\bacr\b",
                                                 low[max(0, m.start() - 30):m.end()]):
                continue
            # skip multiplier phrasing: "above 3 times upper limit of normal"
            # (the 3 is a multiplier of ULN, not a lab value in usual units)
            tail = low[m.end():m.end() + 24]
            if re.match(r"\s*(?:times|x|fold|\u00d7)\b", tail) or "upper limit of normal" in tail:
                continue
            nums = [g for g in m.groups() if g and re.fullmatch(r"\d+(?:\.\d+)?", g)]
            if kind == "between" and len(nums) >= 2:
                lo, hi = sorted((float(nums[0]), float(nums[1])))
                bounds.append((key, "between", lo, hi))
            elif nums:
                v = float(nums[0])
                if kind == "min":
                    bounds.append((key, "min", v, v))
                else:
                    bounds.append((key, "max", v, v))
    return bounds


def check_numeric_criteria(trial: Trial, profile: PatientProfile):
    """Match lab-value requirements in inclusion text, and exclusion TRIGGERS
    in exclusion text (a patient is safe when outside the trigger zone)."""
    passed, failed, missing = [], [], []
    labs = _profile_labs(profile)
    criteria = [(c, False) for c in trial.inclusion_criteria] + [(c, True) for c in trial.exclusion_criteria]
    for criterion, is_exclusion in criteria:
        for key, kind, lo, hi in _parse_numeric_boundaries(criterion):
            value = labs.get(key)
            label = LAB_LABELS.get(key, key)
            if value is None:
                if not is_exclusion:
                    missing.append(f'{label} value (trial requires: "{criterion}")')
                continue  # cannot confirm an exclusion without the value
            if is_exclusion:
                if kind == "min":      # excludes "above X" -> safe if <= X
                    ok = value <= lo
                elif kind == "max":    # excludes "below X" -> safe if >= X
                    ok = value >= hi
                else:                  # excludes a range -> safe outside it
                    ok = not (lo <= value <= hi)
                if ok:
                    passed.append(f'{label} {value} does not trigger exclusion "{criterion}"')
                else:
                    failed.append(
                        f"Potential exclusion: {label} is {value}; trial excludes patients where {criterion}"
                    )
            else:
                if kind == "min":
                    ok = value >= lo
                elif kind == "max":
                    ok = value <= hi
                else:
                    ok = lo <= value <= hi
                if ok:
                    passed.append(f'{label} {value} satisfies inclusion criterion "{criterion}"')
                else:
                    failed.append(
                        f'{label} {value} does not satisfy inclusion criterion "{criterion}" (trial requires: "{criterion}")'
                    )
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Disease-duration criteria
# ---------------------------------------------------------------------------

def check_duration_criteria(trial: Trial, profile: PatientProfile):
    """'diagnosed at least 2 years ago' -> min duration; 'newly diagnosed
    within the past 6 months' -> max duration."""
    passed, failed, missing = [], [], []
    duration = profile.disease_duration_months
    inc_text = " ".join(trial.inclusion_criteria)
    for m in re.finditer(r"diagnosed[^.;]{0,60}?at least\s*(\d+)\s*(year|month)s?", inc_text, re.I):
        months = float(m.group(1)) * (12 if m.group(2).lower().startswith("y") else 1)
        label = f"diagnosed at least {m.group(1)} {m.group(2).lower()}(s) ago"
        if duration is None:
            missing.append(f"Disease duration (trial requires {label})")
        elif duration >= months:
            passed.append(f'Disease duration {duration:g} months satisfies "{label}"')
        else:
            failed.append(f'Disease duration {duration:g} months does not satisfy "{label}"')
    for m in re.finditer(r"newly diagnosed[^.;]{0,60}?within (?:the past\s*)?(\d+)\s*(year|month)s?", inc_text, re.I):
        months = float(m.group(1)) * (12 if m.group(2).lower().startswith("y") else 1)
        label = f"newly diagnosed within {m.group(1)} {m.group(2).lower()}(s)"
        if duration is None:
            missing.append(f'Disease duration (trial requires "{label}")')
        elif duration <= months:
            passed.append(f'Disease duration {duration:g} months satisfies "{label}"')
        else:
            failed.append(f'Disease duration {duration:g} months exceeds "{label}" (trial seeks newly diagnosed patients)')
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Medication requirements (e.g. "on stable metformin therapy", "insulin naive")
# ---------------------------------------------------------------------------

_DRUG_WORDS = "metformin|insulin|glimepiride|sulfonylurea|sitagliptin|dapagliflozin|empagliflozin|ertugliflozin|methotrexate|amlodipine|telmisartan|statin|corticosteroid"


def _patient_drug_names(profile: PatientProfile) -> List[str]:
    names = [m.name.lower() for m in profile.current_medications]
    names += [p.lower() for p in profile.previous_medications]
    names += [t.lower() for t in profile.previous_treatments]
    return names


def check_medication_criteria(trial: Trial, profile: PatientProfile):
    passed, failed, missing = [], [], []
    med_names = _patient_drug_names(profile)

    # 1. Required ongoing therapy: "on stable metformin therapy", "on ... for"
    inc_text = " ".join(trial.inclusion_criteria)
    for m in re.finditer(rf"on\s+(?:stable\s+)?({_DRUG_WORDS})(?:\s+\w+)?\s+(?:therapy|treatment|for)", inc_text, re.I):
        drug = m.group(1).lower()
        if not med_names:
            missing.append(f"Current medication list (trial requires patients on {drug})")
        elif any(drug in name for name in med_names):
            passed.append(f'Patient is on {drug}, satisfying "{m.group(0).strip()}"')
        else:
            failed.append(f'Trial requires patients on {drug} therapy; current medications do not include it ("{m.group(0).strip()}")')

    # 2. Substance-specific naive criteria: "insulin naive",
    #    "no previous treatment with insulin", "not previously treated with X"
    # 3. Generic treatment-naive criteria: "treatment-naive", "newly diagnosed"
    for criterion in trial.inclusion_criteria:
        low = criterion.lower()
        substance = re.search(rf"\b({_DRUG_WORDS})\b", low)
        naive_word = re.search(r"naive|na\u00efve", low)
        no_prior = re.search(r"no previous|not previously|never received|no prior|no history of prior", low)
        if substance and (naive_word or no_prior):
            drug = substance.group(1)
            if any(drug in name for name in med_names):
                failed.append(f'Trial requires "{criterion}" but patient history includes {drug}')
            elif med_names:
                passed.append(f'Patient has no {drug} exposure, satisfying "{criterion}"')
            else:
                missing.append(f'Medication history (trial requires: "{criterion}")')
        elif re.search(r"treatment[- ]?na.ve|therap[- ]?na.ve", low) or (naive_word and not substance):
            if profile.previous_treatments or profile.current_medications:
                failed.append(f'Trial requires treatment-naive patients but prior treatment/medication is recorded ("{criterion}")')
            else:
                missing.append(f'Previous treatment status (trial requires: "{criterion}")')

    # 4. Drug-based exclusions: "Current use of insulin", "treatment with X"
    for criterion in trial.exclusion_criteria:
        low = criterion.lower()
        substance = re.search(rf"\b({_DRUG_WORDS})\b", low)
        if not substance or not re.search(r"current use|use of|taking|receiv|treated with|treatment with|therapy", low):
            continue
        drug = substance.group(1)
        if any(drug in name for name in med_names):
            failed.append(f'Potential exclusion: patient takes {drug}; trial excludes "{criterion}"')
        elif med_names:
            passed.append(f'Patient does not take {drug}; no conflict with exclusion "{criterion}"')
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Required co-conditions ("Type 2 Diabetes with Diabetic Nephropathy")
# ---------------------------------------------------------------------------
_COMPONENT_SYNONYMS = {
    "depression": ["depress"],
    "nephropathy": ["kidney", "renal", "nephropathy"],
    "kidney disease": ["kidney", "renal"],
    "heart failure": ["heart", "cardiac", "cardiovascular"],
    "obesity": ["obese", "obesity"],
    "hypertension": ["hypertension", "blood pressure"],
    "retinopathy": ["retinopathy"],
    "neuropathy": ["neuropathy"],
    "fatty liver": ["fatty liver", "nafld", "liver"],
}


def check_required_components(trial: Trial, profile: PatientProfile):
    """Trial conditions like 'X with Y' require the patient to have Y too."""
    passed, failed, missing = [], [], []
    tc = trial.condition.lower()
    if " with " not in tc:
        return passed, failed, missing
    parts = [p.strip() for p in re.split(r"\bwith\b", tc) if p.strip()][1:]
    patient_text = profile.to_text().lower()
    for part in parts:
        synonyms = None
        for key, syn in _COMPONENT_SYNONYMS.items():
            if key in part:
                synonyms = syn
                break
        if synonyms is None:
            # generic: any significant word from the component in the profile
            words = [w for w in re.findall(r"[a-z]{5,}", part)]
            synonyms = words
        if "obesity" in part or "obese" in part:
            if profile.bmi is None:
                missing.append(f"BMI (trial targets patients with {part})")
            elif profile.bmi >= 30:
                passed.append(f"Patient BMI {profile.bmi} indicates obesity, matching trial condition \"{trial.condition}\"")
            else:
                failed.append(f'Trial targets patients with {part}; patient BMI is {profile.bmi}')
            continue
        found = any(s in patient_text for s in synonyms)
        # explicit structured history check for comorbidity-style components
        comorb_value = None
        for ck in ("Kidney disease", "Cardiovascular disease", "Liver disease"):
            if any(s in ck.lower() for s in synonyms):
                comorb_value = profile.comorbidities.get(ck)
                break
        if found or comorb_value == "Yes":
            passed.append(f'Patient profile indicates {part}, matching trial condition "{trial.condition}"')
        elif comorb_value == "No":
            failed.append(f'Trial targets patients with {part}; medical history records no such condition')
        else:
            missing.append(f'Confirmation of {part} (trial targets patients with "{trial.condition}")')
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Exclusion keyword checks
# ---------------------------------------------------------------------------

CONDITION_EXCLUSION_MAP = {
    "pregnan": ("pregnancy_status", "Pregnant", "Patient is pregnant; trial excludes pregnant participants"),
    "breastfeed|lactat": ("pregnancy_status", "Pregnant", "Trial excludes breastfeeding/lactating participants"),
    "smok": ("smoking_status", "Current", "Trial excludes current smokers"),
    "alcohol": ("alcohol_use", "Regular", "Trial excludes regular alcohol use"),
}


def check_exclusion_keywords(trial: Trial, profile: PatientProfile):
    passed, failed, missing = [], [], []
    all_text = " ".join(trial.exclusion_criteria).lower()
    pregnancy_topics: list = []
    for pattern, (field, bad_value, message) in CONDITION_EXCLUSION_MAP.items():
        if not re.search(pattern, all_text):
            continue
        value = getattr(profile, field, None)
        topic = pattern.split("|")[0]
        if field == "pregnancy_status":
            pregnancy_topics.append(topic)
            if value == "Pregnant":
                failed.append(message)
            elif value == "Not Pregnant" or (profile.gender or "").lower() == "male":
                passed.append("No conflict with the trial's pregnancy/breastfeeding exclusion")
            # a single missing-info note is added below if needed
        else:
            if not _has(value) or value == "Unknown":
                missing.append(f"{field.replace('_', ' ').title()} (trial exclusion mentions '{topic}')")
            elif value == bad_value:
                failed.append(message)
            else:
                passed.append(f"No conflict with exclusion criterion about '{topic}'")
    if pregnancy_topics:
        value = profile.pregnancy_status
        if value not in ("Not Pregnant", "Pregnant") and (profile.gender or "").lower() != "male":
            missing.append("Pregnancy/breastfeeding status (trial exclusion applies)")
    return passed, failed, missing


COMORBID_EXCLUSION = [
    # (pattern, comorbidity key, human label)
    (r"renal impairment|renal failure|kidney disease|ckd|nephropathy", "Kidney disease", "kidney disease / renal impairment"),
    (r"hepatic impairment|liver disease|hepatitis|cirrhosis", "Liver disease", "liver disease"),
    (r"cancer|malignan|tumou?r|neoplasm", "Cancer", "active cancer"),
    (r"heart failure|myocardial infarction|coronary", "Cardiovascular disease", "cardiovascular disease"),
    (r"chronic obstructive|copd", "COPD", "COPD"),
    (r"autoimmune|lupus|rheumatoid", "Autoimmune disease", "autoimmune disease"),
]


def check_comorbidity_exclusions(trial: Trial, profile: PatientProfile):
    """Exclusion text mentioning diseases vs. the patient's history.

    Skips checks when the trial's own condition targets that disease (e.g. a
    nephropathy trial 'excludes polycystic kidney disease' but studies kidney
    patients) - otherwise every studied patient would be excluded.
    """
    passed, failed, missing = [], [], []
    excl_text = " ".join(trial.exclusion_criteria).lower()

    # Umbrella exclusion first: healthy-volunteer trials exclude any chronic
    # disease, which supersedes the individual comorbidity checks below.
    if re.search(r"any chronic disease|no chronic|healthy (?:adults|subjects|volunteers)", excl_text):
        yes_keys = [k for k, v in profile.comorbidities.items() if v == "Yes"]
        condition_is_healthy = bool(profile.condition) and bool(
            re.search(r"healthy|no known (?:chronic )?disease|normal volunteer", profile.condition.lower()))
        if yes_keys:
            failed.append(f"Trial excludes chronic disease; history records: {', '.join(yes_keys)}")
        elif profile.condition and not condition_is_healthy:
            failed.append(f'Trial is for healthy volunteers; patient has a recorded condition ({profile.condition})')
        else:
            passed.append("No chronic disease or significant medical history recorded")
        return passed, failed, missing

    trial_cond = trial.condition.lower()
    for pattern, comorb_key, label in COMORBID_EXCLUSION:
        if not re.search(pattern, excl_text):
            continue
        # guard: disease is the study population, not an exclusion
        probe = {"Kidney disease": ("kidney", "renal", "nephropathy"),
                 "Liver disease": ("liver", "hepatic"),
                 "Cancer": ("cancer", "carcinoma", "tumou?r", "malignan"),
                 "Cardiovascular disease": ("heart", "cardiac", "myocardial", "coronary"),
                 "COPD": ("copd", "chronic obstructive"),
                 "Autoimmune disease": ("rheumatoid", "lupus", "autoimmune")}[comorb_key]
        if any(re.search(p, trial_cond) for p in probe):
            continue
        history = profile.comorbidities.get(comorb_key)
        if history == "Yes":
            failed.append(f"Potential exclusion: trial excludes patients with {label} and medical history records {comorb_key}: Yes")
        elif history == "No":
            passed.append(f"Medical history shows no {comorb_key.lower()}, matching exclusion about {label}")
        else:
            missing.append(f"{comorb_key} history (trial excludes {label})")
    return passed, failed, missing


# ---------------------------------------------------------------------------
# Condition relevance
# ---------------------------------------------------------------------------

# Disease families: let a known patient condition be compared with a trial's
# target condition even when the wording differs. Order does not matter because
# matching is done with a leading word-boundary guard (so "diabetes" never
# fires inside "prediabetes").
_CONDITION_FAMILIES = (
    ("prediabetes", ("prediabet", "impaired fasting glucose", "impaired glucose tolerance")),
    ("diabetes_t2", ("type 2 diabetes", "t2dm", "t2d", "diabetes mellitus", "diabetes", "diabetic")),
    ("hypertension", ("hypertension", "high blood pressure", "uncontrolled blood pressure")),
    ("breast_cancer", ("breast cancer", "breast carcinoma")),
    ("cancer", ("cancer", "carcinoma", "tumour", "tumor", "malignan")),
    ("nephropathy", ("diabetic nephropathy", "nephropathy", "kidney disease", "renal impairment")),
    ("heart_failure", ("heart failure", "cardiac failure")),
    ("depression", ("depression", "depressive")),
    ("asthma", ("asthma",)),
    ("copd", ("chronic obstructive pulmonary disease", "copd", "chronic obstructive")),
    ("rheumatoid_arthritis", ("rheumatoid arthritis", "rheumatoid")),
    ("anaemia_pregnancy", ("anaemia in pregnancy", "anemia in pregnancy")),
    ("nafld", ("non alcoholic fatty liver", "nonalcoholic fatty liver", "fatty liver")),
    ("post_mi", ("post myocardial infarction", "myocardial infarction", "post mi")),
    ("obesity", ("obesity", "obese")),
    ("rituximab", ("rituximab",)),
    ("healthy", ("healthy volunteer", "healthy adult", "healthy subject", "healthy")),
)


def _condition_families(text: str) -> set:
    """Canonical disease families named in a condition string."""
    t = (text or "").lower()
    fams = set()
    for fam, keys in _CONDITION_FAMILIES:
        for key in keys:
            if re.search(r"(?<![a-z])" + re.escape(key), t):
                fams.add(fam)
                break
    return fams


def check_condition_relevance(trial: Trial, profile: PatientProfile):
    """Compare the patient's condition with the condition the trial studies.

    A known patient condition that belongs to none of the trial's disease
    families is a hard mismatch: the patient does not have the disease under
    study (e.g. an asthma patient in a rheumatoid arthritis trial).
    """
    if not _has(profile.condition) or not _has(trial.condition):
        return [], [], ["Patient condition and trial condition cannot be compared"]
    pc, tc = profile.condition.lower(), trial.condition.lower()
    patient_fams = _condition_families(pc)
    trial_fams = _condition_families(tc)
    # A healthy volunteer cannot match a trial that studies a real disease
    # ("Healthy Volunteer" patient vs PNH / RA / diabetes trial) - including
    # rare-disease trials whose condition is outside every known family.
    patient_is_healthy = bool(re.search(r"healthy", pc)) and not (
        patient_fams - {"healthy"})
    trial_is_healthy_trial = bool(re.search(r"healthy|normal volunteer", tc))
    if patient_is_healthy and not trial_is_healthy_trial:
        return [], [f'Patient is a healthy volunteer; this trial studies "{trial.condition}"'], []
    if patient_fams and trial_fams and not (patient_fams & trial_fams):
        return [], [f'Patient condition "{profile.condition}" does not match the condition studied by this trial "{trial.condition}"'], []
    words_pc = set(re.findall(r"[a-z]{3,}", pc))
    words_tc = set(re.findall(r"[a-z]{3,}", tc))
    if (patient_fams & trial_fams) or (words_pc & words_tc):
        return [f'Patient condition "{profile.condition}" matches trial condition "{trial.condition}"'], [], []
    return [], [], []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_eligibility(trial: Trial, profile: PatientProfile) -> dict:
    """Run all rule-based checks. Returns lists of reasons + final status."""
    reasons_for: List[str] = []
    reasons_against: List[str] = []
    missing: List[str] = []
    hard_failed = False

    def merge(passed, failed, miss):
        nonlocal hard_failed
        reasons_for.extend(passed)
        reasons_against.extend(failed)
        missing.extend(miss)
        hard_failed = hard_failed or bool(failed)

    passed, failed, miss = check_age(trial, profile)
    if passed:
        reasons_for.append(passed)
    reasons_against += failed
    missing += miss
    hard_failed = hard_failed or bool(failed)

    passed, failed, miss = check_gender(trial, profile)
    if passed:
        reasons_for.append(passed)
    reasons_against += failed
    missing += miss
    hard_failed = hard_failed or bool(failed)

    merge(*check_required_components(trial, profile))
    merge(*check_condition_relevance(trial, profile))
    merge(*check_numeric_criteria(trial, profile))
    merge(*check_duration_criteria(trial, profile))
    merge(*check_medication_criteria(trial, profile))
    merge(*check_exclusion_keywords(trial, profile))
    merge(*check_comorbidity_exclusions(trial, profile))

    if hard_failed:
        status = FORCED_INELIGIBLE
    elif missing:
        # Gaps decide HOW GOOD the verdict is, never a separate bucket:
        #   * only EXCLUSION-side facts unknown (lab values / histories to rule
        #     out - verified at the study site anyway) -> Potentially Eligible
        #   * at least one INCLUSION-side fact missing -> Partially Eligible
        exclusion_side = all(
            "(trial exclusion" in m or "(trial excludes" in m
            or m.startswith("Pregnancy/breastfeeding status")
            for m in missing
        )
        status = POTENTIALLY_ELIGIBLE if exclusion_side else PARTIALLY_ELIGIBLE
    else:
        status = POTENTIALLY_ELIGIBLE

    return {
        "status": status,
        "reasons_for": reasons_for,
        "reasons_against": reasons_against,
        "missing_information": sorted(set(missing)),
        "failed_criteria": list(reasons_against),
    }

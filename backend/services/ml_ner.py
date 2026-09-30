"""DistilBERT QA-based clinical NER - the single ML extraction engine.

Every entity is produced by the ML model: the note is queried with targeted
clinical questions ("What medications is the patient taking?", "How old is
the patient?" ...), and the model returns answer spans. No regex pattern
discovery is used anywhere - only normalisation of the model's own spans
(mapping an extracted medication name/dose/frequency onto profile fields,
parsing a number the model extracted, checking the sentence context around a
span for negation cues).

The model (distilbert-base-cased-distilled-squad) is cached locally and runs
fully offline on CPU. It is loaded once per process.
"""
from __future__ import annotations

import re
import threading
from typing import Optional

_QA_MODEL = "distilbert-base-cased-distilled-squad"  # cached in the HF hub cache

# Guards _get_model: without it, a parallel extraction (multi-note upload)
# makes every thread that sees _model is None load its OWN copy of the model
# (hundreds of MB each), and concurrent `import transformers` can fail with
# a partial-initialisation error that silently disables extraction for that
# call. One loader at a time; the rest wait and reuse the result.
_model_lock = threading.Lock()

# Directory holding a pre-quantized int8 copy of the QA model (generated at
# Docker build time; see Dockerfile). Used when no local HF snapshot exists -
# small 512 MB containers (Render free) cannot fit torch + fp32 weights + app.
# Override with the CTQ_NER_ARTIFACT environment variable.
import os
_QA_ARTIFACT = os.environ.get("CTQ_NER_ARTIFACT", "") or None

_model = None         # lazily loaded (tokenizer, model, torch) tuple
_model_available: Optional[bool] = None  # None = not probed yet


def _local_snapshot() -> Optional[str]:
    """Locate the cached model snapshot folder directly (bypasses hub cache
    resolution, which can fail with Windows symlink setups)."""
    from pathlib import Path
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    bare = "models--" + _QA_MODEL.replace("/", "--")
    candidates = [bare, "models--distilbert--" + _QA_MODEL]
    for name in candidates:
        for snap in sorted((hub / name / "snapshots").glob("*")):
            if (snap / "model.safetensors").exists() and (snap / "config.json").exists():
                return str(snap)
    return None


def _artifact_dir() -> Optional[str]:
    """Return the ONNX artifact directory when it is complete."""
    if not _QA_ARTIFACT:
        return None
    from pathlib import Path
    art = Path(_QA_ARTIFACT)
    if (art / "model.onnx").exists() and (art / "tokenizer_config.json").exists():
        return str(art)
    return None


def _get_model():
    """Load the QA model once; return None when it is unusable.

    Load priority: local HF snapshot (developer machines, exact fp32 torch
    behaviour) -> ONNX int8 artifact shipped in the Docker image (onnxruntime,
    ~120 MB resident instead of ~450 MB for torch - this is what lets the NER
    fit a 512 MB container) -> hub fp32 torch download (last resort). The
    first two load fully offline.
    """
    global _model, _model_available
    if _model_available is False:
        return None
    if _model is None:
        with _model_lock:
            if _model is not None:      # another thread loaded while we waited
                return _model
            if _model_available is False:  # another thread failed while we waited
                return None
            try:
                from transformers import AutoTokenizer  # lightweight, no torch import
                local = _local_snapshot()
                artifact = _artifact_dir()
                if local:
                    import torch
                    from transformers import AutoModelForQuestionAnswering
                    tok = AutoTokenizer.from_pretrained(local, local_files_only=True)
                    mdl = AutoModelForQuestionAnswering.from_pretrained(
                        local, local_files_only=True)
                    mdl.eval()
                    _model = (tok, mdl, torch)
                    _model_available = True
                    print(f"[ml_ner] loaded {_QA_MODEL} (fp32 local snapshot, torch) "
                          f"for extractive-QA entity extraction")
                    return _model
                if artifact:
                    # ONNX runtime path: torch is never imported, saving ~300 MB
                    # resident RAM - this is what fits the NER into 512 MB.
                    import numpy as np
                    import onnxruntime as ort
                    tok = AutoTokenizer.from_pretrained(artifact, local_files_only=True)
                    # Minimal footprint for tiny containers: single-threaded
                    # execution and no arena growth (default thread pools +
                    # arena blow past 512 MB on Render free instances).
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = 1
                    opts.inter_op_num_threads = 1
                    opts.enable_cpu_mem_arena = False
                    opts.enable_mem_pattern = False
                    sess = ort.InferenceSession(
                        os.path.join(artifact, "model.onnx"),
                        sess_options=opts,
                        providers=["CPUExecutionProvider"])
                    _model = ("onnx", tok, sess, np)
                    _model_available = True
                    print(f"[ml_ner] loaded {_QA_MODEL} (ONNX int8 artifact, onnxruntime) "
                          f"for extractive-QA entity extraction")
                    return _model
                import torch
                from transformers import AutoModelForQuestionAnswering
                tok = AutoTokenizer.from_pretrained(_QA_MODEL)
                mdl = AutoModelForQuestionAnswering.from_pretrained(_QA_MODEL)
                mdl.eval()
                _model = (tok, mdl, torch)
                _model_available = True
                print(f"[ml_ner] loaded {_QA_MODEL} (fp32 hub download, torch) "
                      f"for extractive-QA entity extraction")
            except Exception as exc:  # model missing / corrupted
                _model_available = False
                print(f"[ml_ner] QA model unavailable ({exc}); extraction disabled for this call")
    return _model


def _qa(question: str, context: str) -> str:
    """Run one extractive-QA query over the ML model.

    Implements SQuAD-style span selection directly on the model outputs
    (start/end logits), so it works regardless of the transformers version's
    pipeline registry. Empty string when no sensible span is found.
    """
    bundle = _get_model()
    if bundle is None or not context.strip():
        return ""
    if bundle[0] == "onnx":
        return _qa_onnx(bundle, question, context)
    tok, model, torch = bundle
    try:
        inputs = tok(question, context, return_tensors="pt", truncation="only_second",
                     max_length=384)
        with torch.no_grad():
            out = model(**inputs)
        start_logits = out.start_logits[0]
        end_logits = out.end_logits[0]
        start_idx = int(start_logits.argmax())
        end_idx = int(end_logits.argmax())
        # CLS (index 0) on either side is the model's "no answer" signal
        if start_idx == 0 or end_idx == 0 or end_idx < start_idx:
            return ""
        if end_idx - start_idx > 40:  # implausibly long span
            return ""
        score = float(start_logits[start_idx] + end_logits[end_idx])
        if score < 2.0:  # weak evidence
            return ""
        ids = inputs["input_ids"][0][start_idx:end_idx + 1]
        ans = tok.decode(ids, skip_special_tokens=True).strip()
        return ans[:200]
    except Exception:
        return ""


def _qa_onnx(bundle, question: str, context: str) -> str:
    """ONNX-runtime variant of _qa (identical span-selection logic)."""
    _, tok, sess, np = bundle
    try:
        inputs = tok(question, context, return_tensors="np", truncation="only_second",
                     max_length=384)
        feed = {"input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64)}
        start_logits, end_logits = sess.run(None, feed)
        start_logits, end_logits = start_logits[0], end_logits[0]
        start_idx = int(start_logits.argmax())
        end_idx = int(end_logits.argmax())
        if start_idx == 0 or end_idx == 0 or end_idx < start_idx:
            return ""
        if end_idx - start_idx > 40:
            return ""
        score = float(start_logits[start_idx] + end_logits[end_idx])
        if score < 2.0:
            return ""
        ids = inputs["input_ids"][0][start_idx:end_idx + 1]
        ans = tok.decode(ids, skip_special_tokens=True).strip()
        return ans[:200]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Span-anchored normalisation (no pattern discovery)
# ---------------------------------------------------------------------------

def _numbers(s: str) -> list:
    """Digit groups in a string (char scan; 'hba1c' yields no number)."""
    out, cur = [], ""
    for ch in s:
        if ch.isdigit() or (ch == "." and cur and "." not in cur):
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return [float(x) for x in out]


def _negated(text: str, start: int) -> bool:
    """True when a negation cue appears in the same sentence before the span."""
    raw = text[max(0, start - 60):start]
    cut = max(raw.rfind(p) for p in (".", ";", "\n"))
    window = raw[cut + 1:].lower()
    return any(cue in window for cue in
               ("no ", "not ", "denies", "denied", "without", "never",
                "free of", "negative for", "no history of"))


def _first_number(s: str) -> Optional[float]:
    """First number in a string; tokenises '8. 5' (subword-split decimals)
    as 8.5 and ignores digit-runs glued inside words ('hba1c' -> nothing)."""
    s = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", s or "")  # '8. 5' -> '8.5'
    nums = _numbers(s)
    return nums[0] if nums else None


def _split_answer(blob: str):
    """Split a model answer into candidate items (commas/and/newlines)."""
    parts = re.split(r",|\band\b|;|\n", blob or "")
    return [p.strip(" .-") for p in parts if p.strip(" .-")]


DISEASE_WORDS = ("diabet", "hypertens", "asthma", "copd", "disease", "failure",
                 "arthritis", "nafld", "fatty liver", "ckd", "cancer", "carcinoma",
                 "syndrome", "nephropathy", "hypothyroid", "stroke", "anemia",
                 "anaemia", "covid", "thyroid", "migraine", "depression",
                 "infection", "obesity", "infarction")


def extract_age(text: str) -> Optional[int]:
    """Age from the model's answer to 'How old is the patient?'."""
    ans = _qa("How old is the patient?", text)
    n = _first_number(ans)
    return int(n) if n is not None and 1 <= n <= 120 else None


def extract_gender(text: str) -> Optional[str]:
    ans = (_qa("What is the patient's gender or sex?", text) or "").lower()
    if any(w in ans for w in ("female", "woman", "lady", "girl")):
        return "Female"
    if "male" in ans and "female" not in ans:
        return "Male"
    return None


def _condition_from(text: str, question: str) -> Optional[str]:
    ans = _qa(question, text)
    ans = (ans or "").strip(" .")
    if not ans or len(ans) < 4:
        return None
    bad = re.search(r"\b(smok|alcohol|pregnan|never|none|no condition|healthy|no chronic|unknown)\b", ans, re.I)
    if bad:
        return None
    # a negation or a bare symptom is not a diagnosis ("no known cancer",
    # "shortness of breath", "He does not smoke") - reject and let the
    # fallbacks try
    if re.match(r"^\s*(no|not|none|never|unknown)\b", ans, re.I) \
            or re.search(r"\bno known\b|\bno history\b|\bnot known\b", ans, re.I) \
            or re.search(r"\b(?:does|do|did) not\b|\bnever\b", ans, re.I):
        return None
    if re.search(r"\b(breath|swelling|dizziness|fatigue|weakness|numbness|thirst|nausea|vomiting|fever|cough)\b", ans, re.I):
        return None
    # demographic echo ("H64 age 76 year man male male") - reject
    if re.search(r"\b(year|year-old|male|female|man|woman|age)\b", ans, re.I) \
            and not re.search(r"\b(diabet|hypertens|asthma|cancer|failure|copd|disease|arthritis|hepatitis|fatty|nephropathy|thyroid)\b", ans, re.I):
        return None
    # patient-ID echo ("patient H71") - reject
    if re.match(r"^\s*patient\s+\w+\d+\s*$", ans, re.I):
        return None
    # translated sentence fragment ("H54 of age 19 year is and he she woman...")
    # - real diagnoses never contain these glue patterns
    if re.search(r"\bof age\b|\bis and\b|\bis\.\s|\bpatient\s+\w+\d+\b", ans, re.I):
        return None
    idx = text.lower().find(ans.lower()[:15])
    if idx >= 0 and _negated(text, idx):
        return None  # span comes from a negated sentence ("No history of liver disease")
    return ans[:80]


def _diagnosis_from_sentence(text: str) -> Optional[str]:
    """Fallback: find the first NON-negated sentence that mentions a disease
    word and lift the noun phrase after 'with / diagnosed with / has ...'.
    Notes that only deny disease ("No chronic disease") map to Healthy
    Volunteer. Span selection only - no regex discovery of new entities."""
    disease_words = ("diabet", "hypertens", "asthma", "copd", "cancer",
                     "nephropathy", "prediabet", "disease", "arthritis",
                     "hepatitis", "cirrhosis", "failure", "infarction")
    for sentence in re.split(r"(?<=[.;])\s+", text):
        low = sentence.lower()
        if not any(w in low for w in disease_words):
            continue
        if re.match(r"^\s*(no|not|never|denies|without)\b", low):
            continue  # the sentence itself denies disease ("No chronic disease.")
        if re.search(r"\bno known\b|\bno history\b|\bnot known\b|\bnever had\b"
                     r"|\bis not present\b|\bare not present\b", low):
            continue  # post-noun / translated negation ("... no known cancer",
                      # "any no disease is not present") - not a diagnosis
        idx = text.lower().find(low[:25])
        if idx >= 0 and _negated(text, idx):
            continue
        m = re.search(
            r"(?:with|diagnosed with|diagnosis of|suffering from|suffers from|\bhas\b|\bhaving\b)\s+"
            r"([A-Za-z][A-Za-z0-9 ,\-]{3,60}?)(?=\s+(?:diagnosed|for|since|and|with\s+\w)\b|[.;,]|$)",
            sentence, re.I)
        if m:
            cand = re.sub(r"^(?:a|an|the|also)\s+", "", m.group(1).strip(" ,."), flags=re.I)
            if len(cand) >= 4:
                return cand[:80]
        # disease word present but no cue phrase - return the tight disease
        # term itself ("type 2 diabetes"), not a runaway sentence span
        term_m = re.search(
            r"\b(type 2 diabetes|type 1 diabetes|diabetes mellitus|diabetes"
            r"|hypertension|heart failure|myocardial infarction|asthma|copd"
            r"|breast cancer|cancer|nephropathy|prediabetes|arthritis"
            r"|hepatitis|cirrhosis)\b", low)
        if term_m:
            return term_m.group(0)[:80]
    if re.search(r"healthy|no chronic disease|no known chronic|no significant medical history"
                 r"|no known (?:diabetes|disease|cancer|condition)"
                 r"|\bno (?:diabetes|bp problem|medical problems)\b", text, re.I):
        return "Healthy Volunteer"
    return None


def extract_condition(text: str) -> Optional[str]:
    """Primary condition from the model's answer, kept verbatim (normalised
    capitalisation only). Rejected when the model returns a lifestyle word or
    a span from a negated sentence; differently-phrased fallback questions
    then give the model another chance to return the real diagnosis."""
    for question in (
        "What is the patient's primary medical condition or diagnosis?",
        "What disease is the patient diagnosed with?",
        "Which chronic disease does the patient have?",
    ):
        cond = _condition_from(text, question)
        if cond:
            return cond
    return _diagnosis_from_sentence(text)


def extract_duration_months(text: str) -> Optional[float]:
    """Disease duration in months from the model's answer ("12 years" -> 144).

    The duration question often grabs the patient's age ("45") when no
    duration sentence exists, so the answer is cross-checked: it must name a
    unit (year/month/week) somewhere in the answer, otherwise it is rejected.
    """
    questions = (
        "For how many years or months has the patient had this condition?",
        "Since how many years has the patient been diagnosed with this disease?",
        "How long ago was the patient diagnosed (for example 5 years)?",
        "What is the duration of the patient's illness in years or months?",
    )
    for question in questions:
        ans = _qa(question, text)
        low = (ans or "").lower()
        if not any(u in low for u in ("year", "month", "week")):
            continue  # bare number (usually the age) - not a duration
        n = _first_number(low)
        if n is None:
            continue
        if "month" in low:
            return n
        if "week" in low:
            return round(n * 12 / 52, 1)
        return n * 12
    return None


def extract_medications(text: str) -> list:
    """Medications from the model, with per-medication follow-up questions
    for dose and frequency (much more reliable than one aligned list)."""
    names_blob = _qa("What medications is the patient currently taking?", text)
    names = _split_answer(names_blob)
    if not names:
        return []

    def _clean_med(name: str) -> Optional[str]:
        # strip dose/frequency words that leak into the name span
        name = re.sub(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|units?)\b", "", name, flags=re.I).strip(" ,.-")
        name = re.sub(r"\b(once|twice|thrice|daily|weekly|night|morning|every\s+\d+\s*hours?)\b", "",
                      name, flags=re.I).strip(" ,.-")
        name = re.sub(r"^(?:tab|caps?|tablet|cap)\s+", "", name, flags=re.I)
        if re.match(r"^\s*(no|not|none|never)\b", name, re.I):
            return None  # the model echoed a negation ("no diabetes medicine")
        if re.search(r"\b(hba1c|glucose|creatinine|egfr|mmhg|dlib|hemoglobin)\b|\bd\s*l\b", name, re.I):
            return None  # lab values are not medications ("glucose / dL")
        if re.search(r"\bmedication|medicine|\bpregnan", name, re.I):
            return None  # QA phrase noise ("diabetes medication", "5 months pregnant")
        return name if 3 <= len(name) <= 40 else None

    meds = []
    for raw_name in names[:6]:
        name = _clean_med(raw_name)
        if not name:
            continue
        dose_ans = _qa(f"What is the dose of {name} (for example 500 mg)?", text)
        freq_ans = _qa(f"How often is {name} taken (for example twice daily)?", text)
        dur_ans = _qa(f"For how long has the patient been taking {name} (duration in months or years)?", text)
        dose = dose_ans.strip() if dose_ans and _first_number(dose_ans) is not None \
            and re.search(r"\d", dose_ans) else None
        freq = freq_ans.strip() if freq_ans and re.search(r"[a-z]", freq_ans, re.I) \
            and _first_number(freq_ans) is None else None
        if dose and not re.search(r"(?:mg|mcg|g|ml|iu|unit)", dose, re.I) and len(dose) > 8:
            dose = None  # model returned a phrase, not a dose
        if freq and not any(w in freq.lower() for w in
                            ("daily", "day", "week", "night", "morning", "hour", "needed", "times")):
            freq = None
        duration_months = None
        dur_low = (dur_ans or "").lower()
        if dur_low and any(u in dur_low for u in ("month", "year", "week")):
            n = _first_number(dur_low)
            if n is not None:
                if "year" in dur_low:
                    duration_months = n * 12
                elif "week" in dur_low:
                    duration_months = round(n * 12 / 52, 1)
                else:
                    duration_months = n
        if not any(m["name"].lower() == name.lower() for m in meds):
            meds.append({"name": name, "dose": dose, "frequency": freq,
                         "duration_months": duration_months})
    return meds[:8]


SYMPTOM_WORDS = ("thirst", "urination", "fatigue", "blurred", "numbness", "healing",
                 "headache", "dizziness", "breath", "chest pain", "joint pain",
                 "fever", "cough", "weight loss", "wheez", "swelling", "nausea",
                 "vomiting", "rash", "palpitation", "pain", "weakness", "stiff")


def extract_symptoms(text: str) -> list:
    """Symptoms from the model's answer; negated sentences are skipped."""
    ans = _qa("What symptoms or complaints does the patient have?", text)
    found = []
    for item in _split_answer(ans):
        idx = (ans or "").lower().find(item.lower()[:12]) if item else -1
        if item and len(item) > 2 and not (idx >= 0 and _negated(ans, idx)):
            if item.capitalize() not in found:
                found.append(item.capitalize())
    # fall back to asking per negated context: nothing - ML answers only
    return found[:8]


LIFESTYLE_QUESTIONS = {
    "smoking_status": (
        "Does the patient smoke?",
        {"never": "Never", "non": "Never", "nonsmoker": "Never", "does not smoke": "Never",
         "no": "Never", "former": "Former", "ex": "Former", "quit": "Former",
         "current": "Current", "smokes": "Current", "yes": "Current", "active": "Current"},
    ),
    "alcohol_use": (
        "Does the patient drink alcohol?",
        {"never": "Never", "does not drink": "Never", "no": "Never", "none": "Never",
         "occasional": "Occasional", "social": "Occasional", "sometimes": "Occasional",
         "regular": "Regular", "daily": "Regular", "yes": "Regular"},
    ),
    "pregnancy_status": (
        "Is the patient pregnant?",
        {"not pregnant": "Not Pregnant", "no pregnancy": "Not Pregnant", "no": "Not Pregnant",
         "not": "Not Pregnant", "pregnant": "Pregnant", "yes": "Pregnant"},
    ),
}


# Cue priority per lifestyle field: meanings are checked in this order so a
# negation always beats a stem inside a longer word ("Never smokes" must not
# resolve to "Current" just because "smokes" is the longer cue).
LIFESTYLE_PRIORITY = {
    "smoking_status": ("never", "does not smoke", "non", "nonsmoker", "former", "quit", "ex",
                       "current", "smokes", "active", "yes", "no"),
    "alcohol_use": ("never", "does not drink", "none", "occasional", "social", "sometimes",
                    "regular", "daily", "yes", "no"),
    "pregnancy_status": ("not pregnant", "no pregnancy", "pregnant", "no", "yes"),
}


def extract_lifestyle(text: str, gender: Optional[str] = None) -> dict:
    out = {}
    for field, (question, mapping) in LIFESTYLE_QUESTIONS.items():
        if field == "pregnancy_status" and (gender or "").lower() == "male":
            out[field] = "N-A"
            continue
        ans = (_qa(question, text) or "").lower().strip()
        # the model sometimes echoes the question's options ("answer never
        # smoker") - strip instruction words before matching
        ans = re.sub(r"\banswer\b|\bfor example\b|\be\.g\.", "", ans).strip(" :,." )
        if not ans:
            continue
        # priority cues first, then any remaining cues longest-first
        order = [c for c in LIFESTYLE_PRIORITY.get(field, ()) if c in mapping]
        order += [c for c in sorted(mapping, key=len, reverse=True) if c not in order]
        for cue in order:
            if cue in ans:
                out[field] = mapping[cue]
                break
    return out


COMORBIDITY_QUESTIONS = {
    # keys mirror the profile's comorbidity vocabulary used by the rule engine
    "Liver disease": "Does the patient have any history of liver disease such as hepatitis or cirrhosis?",
    "Kidney disease": "Does the patient have any history of kidney disease such as chronic kidney disease or nephropathy?",
    "Cardiovascular disease": "Does the patient have any history of heart disease or cardiovascular disease?",
    "Cancer": "Does the patient have any history of cancer or malignancy?",
    "Hypertension": "Does the patient have high blood pressure (hypertension)?",
    "Diabetes": "Does the patient have diabetes?",
    "COPD": "Does the patient have COPD or chronic obstructive pulmonary disease?",
}


def extract_comorbidities(text: str) -> dict:
    """Yes/No per disease, answered by the ML model. Conservative: an answer
    is accepted only when the span clearly affirms or negates the history
    (starts with yes/no, or contains an explicit no-history phrase) -
    anything ambiguous is left out so the profile field stays Unknown."""
    out = {}
    for key, question in COMORBIDITY_QUESTIONS.items():
        ans = (_qa(question, text) or "").lower().strip()
        # strip instruction echoes like "answer for example no"
        ans = re.sub(r"\banswer\b|\bfor example\b|\be\.g\.", "", ans).strip(" :,.\"'")
        if not ans:
            continue
        if "denies" in ans or "no history of" in ans or "history of" in ans and ans.startswith("no"):
            out[key] = "No"
        elif ans.split()[0] in ("no", "none", "never"):
            out[key] = "No"
        elif ans.split()[0] == "yes":
            out[key] = "Yes"
    return out


# Lab fields asked as explicit model questions (name + value pairs)
LAB_QUESTIONS = [
    ("hba1c", "What is the patient's HbA1c level?"),
    ("fasting_glucose", "What is the patient's fasting glucose level?"),
    ("systolic_bp", "What is the patient's systolic blood pressure value in mmHg (the top number, for example 140)?"),
    ("diastolic_bp", "What is the patient's diastolic blood pressure value in mmHg (the bottom number, for example 85)?"),
    ("creatinine", "What is the patient's serum creatinine value in mg/dL?"),
    ("egfr", "What is the patient's eGFR (estimated glomerular filtration rate) value?"),
    ("hemoglobin", "What is the patient's hemoglobin value?"),
    ("wbc", "What is the patient's WBC (white blood cell) count?"),
    ("platelets", "What is the patient's platelet count?"),
    ("alt", "What is the patient's ALT or SGPT value?"),
    ("ast", "What is the patient's AST or SGOT value?"),
    ("bilirubin", "What is the patient's bilirubin value?"),
    ("cholesterol", "What is the patient's cholesterol value?"),
    ("fev1_percent", "What is the patient's FEV1 as a percentage of predicted value?"),
]


# Keywords that must appear in the model's answer (or around the value) for
# each lab to be accepted - prevents cross-contaminated answers like
# creatinine <- 'HbA1c 8.5%'.
_LAB_ANCHORS = {
    "hba1c": ("hba1c", "a1c"),
    "fasting_glucose": ("glucose",),
    "creatinine": ("creatinine",),
    "egfr": ("egfr", "gfr"),
    "hemoglobin": ("hemoglobin", "haemoglobin"),
    "wbc": ("wbc", "leucocyte", "leukocyte"),
    "platelets": ("platelet",),
    "alt": ("alt", "sgpt"),
    "ast": ("ast", "sgot"),
    "bilirubin": ("bilirubin",),
    "cholesterol": ("cholesterol",),
    "systolic_bp": ("blood pressure", "bp", "mmhg", "systolic"),
    "diastolic_bp": ("blood pressure", "bp", "mmhg", "diastolic"),
    "fev1_percent": ("fev1", "forced expiratory"),
}


def _context_around(text: str, value: float) -> str:
    """Text surrounding the first occurrence of the value in the note."""
    for token in (str(int(value)) if float(value).is_integer() else str(value),):
        idx = text.find(token)
        if idx >= 0:
            return text[max(0, idx - 45):idx + len(token) + 8].lower()
    return ""


def _anchored_anywhere(text: str, value: float, anchors) -> bool:
    """True when ANY occurrence of the value is introduced by the test name.

    A note that starts "45-year-old ... eGFR 45" must still anchor the eGFR to
    its lab sentence, not to the age.
    """
    pat = r"\b(?:" + "|".join(re.escape(a) for a in anchors) + r")\b"
    token = str(int(value)) if float(value).is_integer() else str(value)
    for m in re.finditer(r"(?<!\d)" + re.escape(token) + r"(?!\d)", text):
        ctx = text[max(0, m.start() - 45): m.end() + 8].lower()
        if re.search(pat, ctx):
            return True
    return False


# Re-phrased questions tried when the first answer fails validation - keeps
# extraction ML-only while recovering values the model misses on one wording
# (e.g. eGFR sitting next to a creatinine ratio in the same sentence).
LAB_QUESTION_VARIANTS = {
    "egfr": ("What eGFR number is reported in the patient's notes?",
             "What is the patient's estimated glomerular filtration rate value?"),
    "creatinine": ("What creatinine value is reported in the patient's notes?",),
    "hba1c": ("What HbA1c percentage is reported for this patient?",),
    "fasting_glucose": ("What fasting blood sugar value is reported?",),
    "alt": ("What is the patient's SGPT (ALT) liver enzyme value?",),
    "ast": ("What is the patient's SGOT (AST) liver enzyme value?",),
    "hemoglobin": ("What haemoglobin value is reported for this patient?",),
    "fev1_percent": ("What percentage of predicted FEV1 is reported for the patient?",),
    "cholesterol": ("What is the patient's total cholesterol level?",),
}

_LAB_CAPS = {"hba1c": 20, "fasting_glucose": 800, "creatinine": 25, "egfr": 150,
             "hemoglobin": 25, "wbc": 200000, "platelets": 2000000, "alt": 5000,
             "ast": 5000, "bilirubin": 60, "cholesterol": 1000, "fev1_percent": 150}

_BP_QUESTIONS = (
    "What is the patient's blood pressure reading (for example 140 over 85)?",
    "What are the patient's systolic and diastolic blood pressure numbers?",
)


def _lab_bp_pair(ans: str):
    """Parse a real '150/95' reading. Requires digits on BOTH sides of the
    slash, so unit slashes like 'ALT 26 U/L' can never be read as 26/.. ."""
    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})\b", ans or "")
    if not m:
        return None
    sys_v, dia_v = int(m.group(1)), int(m.group(2))
    if 90 <= sys_v <= 260 and 40 <= dia_v <= 150:
        return sys_v, dia_v
    return None


def _lab_number(field: str, ans: str, text: str, anchors, claimed: set):
    """Accept a value only if it is in range and anchored to the test name."""
    if not ans:
        return None
    n = _first_number(ans)
    if n is None or n > _LAB_CAPS.get(field, 100000):
        return None
    if anchors:
        pat = r"\b(?:" + "|".join(re.escape(a) for a in anchors) + r")\b"
        if not (re.search(pat, ans.lower()) or _anchored_anywhere(text, n, anchors)):
            return None  # the answer is not actually about this test
    elif n in claimed:
        return None
    return n


def extract_labs(text: str, claimed: set = None) -> dict:
    """Labs: one model question per test (with re-phrased retries); the answer
    must contain a number in the lab's sanity range, and for named tests the
    answer or the text around the value must mention the test name. This blocks
    cross-contaminated answers such as creatinine <- 'HbA1c 8.5%' or
    diastolic BP <- 'ALT 26 U/L'."""
    out = {}
    claimed = claimed if claimed is not None else set()
    for field, question in LAB_QUESTIONS:
        if field in ("systolic_bp", "diastolic_bp"):
            continue  # blood pressure is read as a pair below
        anchors = _LAB_ANCHORS.get(field)
        for q in (question,) + LAB_QUESTION_VARIANTS.get(field, ()):
            n = _lab_number(field, _qa(q, text), text, anchors, claimed)
            if n is not None:
                # a clearly anchored lab may reuse a number claimed by
                # height/weight (weight 80 kg vs 'eGFR 80') - context decides
                out[field] = n
                claimed.add(n)
                break
    if "systolic_bp" not in out:
        for q in _BP_QUESTIONS:
            pair = _lab_bp_pair(_qa(q, text) or "")
            if pair:
                out["systolic_bp"], out["diastolic_bp"] = pair
                claimed.update(pair)
                break
    return out


def extract_height_weight(text: str, claimed: set = None) -> dict:
    claimed = claimed if claimed is not None else set()
    out = {}
    h = _first_number(_qa("What is the patient's height in centimetres?", text) or "")
    if h and 60 <= h <= 230 and h not in claimed:
        out["height_cm"] = h
        claimed.add(h)
    w = _first_number(_qa("What is the patient's weight in kilograms?", text) or "")
    if w and 15 <= w <= 350 and w not in claimed:
        out["weight_kg"] = w
        claimed.add(w)
    return out


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

_extract_cache: dict = {}          # sha1(note text) -> extraction result dict
_EXTRACT_CACHE_MAX = 512           # bound memory (Render free tier: each result is small)


def extract_entities(clinical_notes: str) -> dict:
    """Cached wrapper - the real work happens in _extract_entities_uncached.

    Evaluation/batch flows re-send the same notes (upload preview already
    extracted them, or the user re-runs the same evaluation); the DistilBERT
    pass dominates latency (~10-20 s/note), so identical text returns the
    cached result instantly. A code reload or process restart resets it."""
    import hashlib
    key = hashlib.sha1((clinical_notes or "").encode("utf-8")).hexdigest()
    hit = _extract_cache.get(key)
    if hit is not None:
        return hit
    result = _extract_entities_uncached(clinical_notes)
    if len(_extract_cache) >= _EXTRACT_CACHE_MAX:
        _extract_cache.pop(next(iter(_extract_cache)))  # FIFO eviction
    _extract_cache[key] = result
    return result


def _extract_entities_uncached(clinical_notes: str) -> dict:
    """Extract structured facts from free clinical text with the ML model.

    Returns profile-shaped facts plus a report of what the engine did (for
    transparency in the UI).

    Non-Latin notes (Hindi and other Indic scripts, CJK, ...) are translated
    to English first - the extractive-QA NER itself is English-only. When
    translation is unavailable (no LLM key / rate-limited / failed) the
    original text is used as-is, which still recovers Latin-anchored lab
    values like "HbA1c 8.5".
    """
    notes = (clinical_notes or "").strip()
    if not notes:
        return {"facts": {}, "model_used": "none", "detail": "no text supplied"}

    from services.translate import translate_to_english
    tr = translate_to_english(notes)
    notes = tr["text"]

    facts: dict = {}
    qa_used = _get_model() is not None
    claimed: set = set()

    age = extract_age(notes)
    if age is not None:
        facts["age"] = age
        claimed.add(float(age))
    facts.update(extract_height_weight(notes, claimed))
    gender = extract_gender(notes)
    if gender:
        facts["gender"] = gender
    condition = extract_condition(notes)
    if condition:
        facts["condition"] = condition
    meds = extract_medications(notes)
    if meds:
        facts["current_medications"] = meds
    symptoms = extract_symptoms(notes)
    if symptoms:
        facts["symptoms"] = symptoms
    duration = extract_duration_months(notes)
    if duration is not None:
        facts["disease_duration_months"] = duration
    facts.update(extract_lifestyle(notes, gender))
    comorbs = extract_comorbidities(notes)
    if comorbs:
        facts["comorbidities"] = comorbs
    labs = extract_labs(notes, claimed)
    if labs:
        facts["labs"] = labs

    detail = ("DistilBERT extractive-QA answered targeted clinical questions; "
              "answers were normalised into profile fields (ML-only, no regex)")
    if tr["translated"]:
        detail = (f"Note was in {tr['source_script']} script and was translated to English "
                  f"before ML extraction. " + detail)
    elif tr.get("note"):
        detail = tr["note"] + ". " + detail
    return {
        "facts": facts,
        "model_used": _QA_MODEL if qa_used else "unavailable",
        "translated": tr["translated"],
        "source_script": tr["source_script"],
        "translation_note": tr.get("note"),
        "detail": detail,
    }


def model_status() -> dict:
    ok = _get_model() is not None
    return {
        "qa_model": _QA_MODEL,
        "type": "DistilBERT extractive-QA (ML-only, no regex)",
        "loaded": ok,
        "available": _model_available is not False,
    }

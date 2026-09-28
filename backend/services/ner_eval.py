"""Shared canonicalisation + scoring for the NER benchmark.

Both extraction methods (rule-based regex and BioBERT ML) produce the same
entity schema; values are canonicalised identically on both sides so the
precision/recall/F1 comparison is fair. A shared, deterministic negation
filter (NegEx-style cue lookup) is applied to both methods' outputs.
"""
from __future__ import annotations

NEGATION_CUES = ("no ", "not ", "denies", "denied", "without", "never",
                 "free of", "negative for", "no history of")


def is_negated(text: str, start: int) -> bool:
    """True when a negation cue appears before the span WITHIN THE SAME
    sentence (the window is cut at the nearest preceding sentence boundary,
    so "Denies chest pain. HbA1c 7.0" does not negate HbA1c)."""
    raw = text[max(0, start - 60):start]
    # keep only the part after the last sentence-ending punctuation
    cut = max(raw.rfind(p) for p in (".", ";", "\n"))
    window = raw[cut + 1:].lower()
    return any(cue in window for cue in NEGATION_CUES)


# ---------------------------------------------------------------------------
# Value canonicalisation (applied identically to GT and predictions)
# ---------------------------------------------------------------------------

def _numbers(s: str) -> list:
    """Digit groups in a string (char scan, no regex).

    Digit runs embedded inside words (the '1' in 'hba1c', 't2dm') are NOT
    numbers - only runs not flanked by letters count.
    """
    out, cur = [], ""
    for i, ch in enumerate(s):
        if ch.isdigit():
            prev_letter = i > 0 and s[i - 1].isalpha()
            cur += ch
        elif ch == "." and cur and "." not in cur:
            cur += ch
        else:
            if cur:
                # discard the run if its last digit was letter-embedded
                if not (i > 0 and s[i - 1].isalpha() and cur):
                    out.append(cur)
                cur = ""
    if cur and not (len(s) > 0 and s[-1].isalpha()):
        out.append(cur)
    return [float(x) for x in out if x not in (".", "")]


MONTH_UNITS = {"year": 12, "years": 12, "yr": 12, "yrs": 12,
               "month": 1, "months": 1, "mo": 1,
               "week": 12 / 52, "weeks": 12 / 52}


def canon_duration_months(text: str):
    """'12 years' -> 144.0 ; '2 months' -> 2.0 ; None when no value."""
    tokens = text.lower().replace(",", " ").split()
    for i, tok in enumerate(tokens):
        if tok in MONTH_UNITS or tok.rstrip(".,;") in MONTH_UNITS:
            nums = _numbers(" ".join(tokens[max(0, i - 2):i]))
            if nums:
                return round(nums[-1] * MONTH_UNITS[tok.rstrip(".,;")], 1)
    return None


def canon_age(text: str):
    nums = _numbers(text)
    for n in nums:
        if 1 <= n <= 120:
            return n
    return None


def canon_gender(text: str):
    low = text.lower()
    if "female" in low or "woman" in low or "lady" in low:
        return "female"
    if re_male(low):
        return "male"
    return None


def re_male(low: str) -> bool:
    # 'male' but not inside 'female'
    idx = low.find("male")
    while idx != -1:
        if low[max(0, idx - 3):idx] != "fe":
            return True
        idx = low.find("male", idx + 1)
    return False


SMOKING_MAP = [
    (("non-smoker", "nonsmoker", "never smoked", "never smoker", "never a smoker", "no smoking"), "never smoker"),
    (("ex-smoker", "ex smoker", "former", "quit"), "former smoker"),
    (("current smoker", "active smoker", "smokes", "smoking status: current", "heavy smoker"), "current smoker"),
]


def canon_smoking(text: str):
    low = text.lower().strip()
    # short spans straight from the model ("Non", "Current", "Former")
    short = {"non": "never smoker", "nonsmoker": "never smoker", "never": "never smoker",
             "ex": "former smoker", "former": "former smoker", "current": "current smoker"}
    if low in short:
        return short[low]
    for cues, canon in SMOKING_MAP:
        if any(c in low for c in cues):
            return canon
    if "smok" in low:
        return "current smoker" if "current" in low else None
    return None


def canon_alcohol(text: str):
    low = text.lower().strip()
    if any(c in low for c in ("does not drink", "does not smoke or drink", "no alcohol",
                              "never used alcohol", "never drank", "never alcohol",
                              "denies alcohol", "without alcohol")):
        return "no alcohol"
    if any(c in low for c in ("occasional", "social", "occasionally")):
        return "occasional alcohol"
    if any(c in low for c in ("regular", "daily alcohol", "chronic alcohol")):
        return "regular alcohol"
    return None


def canon_pregnancy(text: str):
    low = text.lower().strip()
    if "not pregnant" in low or "no pregnancy" in low:
        return "not pregnant"
    if "pregnan" in low:
        return "pregnant"
    return None


LAB_NAME_MAP = [
    (("hba1c", "a1c"), "hba1c"),
    (("egfr", "gfr"), "egfr"),
    (("hemoglobin", "haemoglobin", "hb "), "hemoglobin"),
    (("creatinine",), "creatinine"),
    (("fasting glucose", "fasting blood glucose", "fasting plasma glucose"), "fasting glucose"),
    (("blood pressure", " bp", "sbp", "dbp"), "bp"),
    (("fev1",), "fev1"),
    (("alt", "sgpt"), "alt"),
    (("ast", "sgot"), "ast"),
    (("tsh",), "tsh"),
    (("cholesterol",), "cholesterol"),
    (("platelet",), "platelets"),
    (("wbc", "leucocyte", "leukocyte"), "wbc"),
]


def canon_lab_name(text: str):
    low = " " + text.lower() + " "
    for cues, canon in LAB_NAME_MAP:
        if any(c in low for c in cues):
            return canon
    return None


def canon_lab_value(name: str, num) -> str:
    return f"{name} {_fmt_num(num)}"


def _fmt_num(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


CONDITION_CANON = [
    (("type 2 diabetes", "t2dm", "diabetes mellitus"), "type 2 diabetes"),
    (("bronchial asthma",), "asthma"),
    (("chronic obstructive pulmonary", "copd"), "copd"),
    (("non-alcoholic fatty liver", "nafld", "fatty liver"), "nafld"),
    (("chronic kidney disease", "ckd"), "chronic kidney disease"),
    (("diabetic nephropathy",), "diabetic nephropathy"),
    (("high blood pressure",), "hypertension"),
]


def canon_condition(text: str) -> str:
    low = " ".join(text.lower().split())
    for cues, canon in CONDITION_CANON:
        if any(c in low for c in cues):
            return canon
    return low.strip(" .;,")


def canon_freq(text: str):
    low = " ".join(text.lower().split())
    if not low:
        return None
    if "as needed" in low or "prn" in low or "sos" in low:
        return "as needed"
    if "twice" in low or "bid" in low or "two times" in low:
        return "twice daily"
    if "thrice" in low or "three times" in low:
        return "thrice daily"
    if "weekly" in low or "once a week" in low or "per week" in low:
        return "weekly"
    if "night" in low:
        return "at night"
    if "morning" in low:
        return "in the morning"
    if "once daily" in low or "once a day" in low or low in ("daily", "od", "once"):
        return "once daily"
    if low.rstrip(".,;") == "once" or low.endswith(" once"):
        return "once daily"
    if "daily" in low or "a day" in low or "per day" in low:
        return "once daily"
    return None


def canon_med(text: str) -> str:
    return " ".join(text.lower().split()).strip(" .,")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "tp": tp, "fp": fp, "fn": fn}


def _token_prefix(a: str, b: str) -> bool:
    """True when a and b overlap as substrings (handles BioBERT's truncated
    multi-word spans like 'hyper' for 'hypertension' or 'thirst' for
    'increased thirst'). Symmetric substring match, min 4 chars."""
    if not a or not b:
        return False
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 4 and short in long


def score_sets(gold: dict, pred: dict) -> dict:
    """Micro P/R/F1 over all fields/notes + per-field breakdown + accuracy.

    gold/pred: {note_id: {field: [canonical values]}}
    A field counts as one instance slot per gold value; predictions are
    matched greedily (each gold value matches at most one prediction).
    """
    per_field = {}
    total = prf(0, 0, 0)
    accuracy_slots = {"correct": 0, "total": 0}

    fields = sorted({f for note in gold.values() for f in note} |
                    {f for note in pred.values() for f in note})
    # span-boundary-tolerant fields: a predicted value matches when the
    # canonical strings are equal or one is a token-prefix of the other
    # (BioBERT sometimes truncates multi-word disease/symptom spans)
    prefix_fields = {"condition", "medication", "symptom"}
    for field in fields:
        tp = fp = fn = 0
        correct = total_g = 0
        for note_id, gfields in gold.items():
            gvals = list(gfields.get(field) or [])
            pvals = list((pred.get(note_id) or {}).get(field) or [])
            unmatched_p = list(pvals)
            for g in gvals:
                total_g += 1
                hit = None
                for p in unmatched_p:
                    if p == g:
                        hit = p
                        break
                    if field in prefix_fields and _token_prefix(p, g):
                        hit = p
                        break
                if hit is not None:
                    unmatched_p.remove(hit)
                    tp += 1
                    correct += 1
                else:
                    fn += 1
            fp += len(unmatched_p)
        per_field[field] = prf(tp, fp, fn)
        per_field[field]["accuracy"] = round(correct / total_g, 4) if total_g else None
        per_field[field]["gold_count"] = total_g
        accuracy_slots["correct"] += correct
        accuracy_slots["total"] += total_g
    # recompute micro totals from per_field
    tp = sum(v["tp"] for v in per_field.values())
    fp = sum(v["fp"] for v in per_field.values())
    fn = sum(v["fn"] for v in per_field.values())
    total = prf(tp, fp, fn)
    total["accuracy"] = (round(accuracy_slots["correct"] / accuracy_slots["total"], 4)
                         if accuracy_slots["total"] else None)
    total["gold_count"] = accuracy_slots["total"]
    return {"micro": total, "per_field": per_field}

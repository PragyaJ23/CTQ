"""Trial retrieval pipeline.

All Indian trials (local CTRI dataset -> SQLite) ->
  stage 1: structured pre-filter (condition domain, age, gender, status)
  stage 2: embedding cosine similarity ranking, keep top K
Only the top-K trials are sent for LLM reasoning (spec §50).
"""
from typing import List, Tuple

import numpy as np

from config import settings
from models import PatientProfile, Trial
from services import database
from services.embeddings import cosine_similarity, embed_texts


def load_trials() -> List[Trial]:
    """Load trials from SQLite, importing data/trials.json on first run."""
    database.init_db()
    if database.trial_count() == 0:
        from config import DATA_DIR
        import json

        trials_file = DATA_DIR / "trials.json"
        if trials_file.exists():
            raw = json.loads(trials_file.read_text(encoding="utf-8"))
            trials = [Trial(**item) for item in raw]
            database.upsert_trials(trials)
            print(f"[retrieval] imported {len(trials)} trials from {trials_file.name}")
    return database.get_all_trials()


# Words that map a free-text condition onto a broad clinical domain.
_DOMAIN_KEYWORDS = {
    "diabetes": ["diabetes", "t2dm", "t2d", "hyperglycemia", "diabetic", "insulin", "metformin", "hba1c", "glycemic"],
    "hypertension": ["hypertension", "blood pressure", "antihypertensive", "bp ", "sbp", "dbp"],
    "cancer": ["cancer", "carcinoma", "tumor", "tumour", "malignan", "oncology", "chemotherapy", "breast", "lung", "lymphoma", "leukemia"],
    "asthma": ["asthma", "bronchial", "wheez", "inhaler"],
    "copd": ["copd", "chronic obstructive", "emphysema", "bronchitis"],
    "kidney": ["kidney", "renal", "ckd", "nephro", "dialysis", "egfr"],
    "liver": ["liver", "hepatic", "hepatitis", "cirrhosis", "nafld", "fatty liver"],
    "cardio": ["cardio", "heart", "cardiac", "coronary", "myocardial", "angina", "heart failure"],
    "thyroid": ["thyroid", "hypothyroid", "hyperthyroid", "tsh", "goitre", "goiter"],
    "anemia": ["anemia", "anaemia", "hemoglobin", "iron deficiency"],
    "tb": ["tuberculosis", " tb", "mdr-tb"],
    "covid": ["covid", "sars-cov-2", "coronavirus"],
    "obesity": ["obesity", "obese", "overweight", "bmi"],
    "arthritis": ["arthritis", "rheumatoid", "osteoarthritis", "joint"],
    "pcos": ["pcos", "polycystic ovary", "pcod"],
    "depression": ["depression", "depressive", "mdd", "antidepress"],
    "malaria": ["malaria", "plasmodium"],
    "dengue": ["dengue"],
}


def _domain(text: str) -> set:
    low = f" {text.lower()} "
    domains = set()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(k in low for k in keywords):
            domains.add(domain)
    return domains


def prefilter_trials(trials: List[Trial], profile: PatientProfile) -> List[Tuple[Trial, List[str]]]:
    """Stage-1 pass over ALL trials. Returns every trial with pre-filter notes.

    Nothing is dropped: the user asked for every trial in the database to be
    checked against the patient. Trials from a different disease domain or
    with hard age/gender conflicts are annotated so the results can show why
    they are not relevant, but they still go through the full rule engine.
    """
    patient_domains = _domain(profile.condition or "")
    keep: List[Tuple[Trial, List[str]]] = []
    for trial in trials:
        notes: List[str] = []
        trial_domains = _domain(f"{trial.condition} {trial.title}")
        if patient_domains and trial_domains and not (patient_domains & trial_domains):
            notes.append("different disease domain")
        # Hard age conflict (patient age known)
        if profile.age is not None:
            if trial.min_age is not None and profile.age < trial.min_age:
                notes.append("age below minimum")
            elif trial.max_age is not None and profile.age > trial.max_age:
                notes.append("age above maximum")
        # Hard gender conflict
        tg = (trial.gender or "Both").lower()
        if profile.gender and tg in ("male", "female") and profile.gender.lower() != tg:
            if profile.gender.lower() in ("male", "female"):
                notes.append("gender restricted")
        keep.append((trial, notes))
    return keep


def rank_by_similarity(
    profile: PatientProfile,
    candidates: List[Tuple[Trial, List[str]]],
    top_k: int = None,
) -> List[dict]:
    """Stage-2 semantic ranking with cosine similarity (embeddings)."""
    if not candidates:
        return []
    k = top_k if top_k is not None else settings.top_k_trials
    if not k or k <= 0:
        k = len(candidates)  # check every retrieved trial

    patient_vec = embed_texts([profile.to_text()])[0]
    trial_texts = [trial.criteria_text() for trial, _ in candidates]
    trial_vecs = embed_texts(trial_texts)

    scored = []
    for (trial, notes), tvec in zip(candidates, trial_vecs):
        sim = cosine_similarity(patient_vec, tvec)
        scored.append({"trial": trial, "similarity": round(sim, 4), "prefilter_notes": notes})
    scored.sort(key=lambda s: s["similarity"], reverse=True)
    return scored[:k]


def retrieve_and_rank(profile: PatientProfile, top_k: int = None) -> dict:
    """Full retrieval: load -> prefilter -> embed -> rank."""
    all_trials = load_trials()
    candidates = prefilter_trials(all_trials, profile)
    ranked = rank_by_similarity(profile, candidates, top_k=top_k)
    return {
        "total_trials": len(all_trials),
        "after_prefilter": len(candidates),
        "ranked": ranked,
    }

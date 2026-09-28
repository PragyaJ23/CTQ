"""Live trial ingestion from ClinicalTrials.gov (Future Scope #3).

Fetches real, current trials from the public ClinicalTrials.gov API v2 and
maps them onto CTQ's CTRI-style Trial schema so they flow through the exact
same matching pipeline as the bundled demo database.

Only INTERVENTIONAL or OBSERVATIONAL studies with explicit eligibility
criteria are ingested. Locations are flattened to "City, State" strings.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import requests

from config import settings
from models import Trial

API_URL = "https://clinicaltrials.gov/api/v2/studies"

# Broad condition buckets offered in the UI, mapped to search terms.
PRESET_CONDITIONS = {
    "Type 2 Diabetes": "Type 2 Diabetes",
    "Hypertension": "Hypertension",
    "Asthma": "Asthma",
    "Breast Cancer": "Breast Cancer",
    "COPD": "Chronic Obstructive Pulmonary Disease",
    "Chronic Kidney Disease": "Chronic Kidney Disease",
    "NAFLD": "Non-Alcoholic Fatty Liver Disease",
    "Heart Failure": "Heart Failure",
    "Rheumatoid Arthritis": "Rheumatoid Arthritis",
    "Anaemia": "Anemia",
}

_COUNTRY_EXPR = ORIG = "AREA[LocationCountry]India"


def _first(d, *path):
    """Safely walk nested dicts/lists; returns None when the path breaks."""
    cur = d
    for p in path:
        if cur is None:
            return None
        if isinstance(p, int):
            if not isinstance(cur, list) or p >= len(cur):
                return None
            cur = cur[p]
        else:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
    return cur


def _age_to_float(age_str: str) -> float | None:
    """'18 Years' -> 18.0 ; '80 Years' -> 80.0 ; 'N/A'/'None' -> None."""
    if not age_str:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(age_str))
    if not m:
        return None
    val = float(m.group(1))
    low = str(age_str).lower()
    if "month" in low:
        return round(val / 12, 2)
    if "week" in low:
        return round(val / 52, 2)
    if "day" in low:
        return round(val / 365, 2)
    if "hour" in low:
        return round(val / (365 * 24), 3)
    return val


def _map_status(status: str) -> str:
    mapping = {
        "RECRUITING": "Recruiting",
        "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
        "NOT_YET_RECRUITING": "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "COMPLETED": "Completed",
        "TERMINATED": "Terminated",
        "WITHDRAWN": "Withdrawn",
        "SUSPENDED": "Suspended",
        "UNKNOWN": "Unknown",
    }
    return mapping.get((status or "").upper(), (status or "Unknown").title())


def _map_phase(phase: str) -> "str":
    if not phase:
        return "N/A"
    return phase.replace("PHASE", "Phase").replace("_", " ").title().replace("Phase ", "Phase ")


def _criteria_list(module) -> tuple[list, list]:
    """Split the eligibility block into inclusion and exclusion lists."""
    if not module:
        return [], []
    text = module.get("eligibilityCriteria") or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Find the EXCLUSION heading (various spellings) and split there
    m = re.search(r"^\s*Exclusion\s*Criteria\s*:?\s*$", text, re.I | re.M)
    if m:
        inc = text[:m.start()].strip()
        exc = text[m.end():].strip()
    else:
        # Fall back: treat everything after 'Inclusion Criteria' as inclusion
        m2 = re.search(r"^\s*Inclusion\s*Criteria\s*:?\s*$", text, re.I | re.M)
        inc = text[m2.end():].strip() if m2 else text.strip()
        exc = ""
    inc_list = [ln.strip(" -\u2022\t") for ln in re.split(r"\n(?=\s*[-\u2022])", inc) if ln.strip(" -\u2022\t")]
    exc_list = [ln.strip(" -\u2022\t") for ln in re.split(r"\n(?=\s*[-\u2022])", exc) if ln.strip(" -\u2022\t")]
    # If no bullets were found, keep whole blocks as single criteria
    if len(inc_list) <= 1 and len(inc) > 0:
        inc_list = [ln.strip() for ln in inc.splitlines() if ln.strip()]
    if len(exc_list) <= 1 and len(exc) > 0:
        exc_list = [ln.strip() for ln in exc.splitlines() if ln.strip()]
    # Trim noisy short lines and clean escaped characters from the registry text
    def _clean(c: str) -> str:
        c = c.replace("\\&", "&").replace("\\", "")
        c = re.sub(r"^\d+\.\s*", "", c)  # numbered list markers
        return c.strip()
    inc_list = [_clean(c) for c in inc_list if len(c) > 8][:40]
    exc_list = [_clean(c) for c in exc_list if len(c) > 8][:40]
    return inc_list, exc_list


def _map_locations(study) -> list[str]:
    locs = _first(study, "protocolSection", "contactsLocationsModule", "locations") or []
    out = []
    for loc in locs:
        city = loc.get("city") or ""
        state = loc.get("state") or ""
        country = loc.get("country") or ""
        if country and country.lower() not in ("india",):
            continue  # keep the India-first focus
        if city or state:
            out.append(", ".join(p for p in (city, state) if p))
    # worldwide/no-India trials keep a single synthetic marker so users see
    # the trial exists but that it has no Indian sites
    if not out:
        out = ["No Indian sites listed"]
    return out[:25]


def _to_trial(study: dict) -> Trial | None:
    """Map one ClinicalTrials.gov study onto the CTQ Trial schema."""
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    status_mod = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    elig = proto.get("eligibilityModule") or {}
    arms = proto.get("armsInterventionsModule") or {}
    sponsor_mod = proto.get("sponsorCollaboratorsModule") or {}

    nct_id = ident.get("nctId")
    if not nct_id:
        return None

    phases = design.get("phases") or []
    phase = _map_phase(phases[0] if phases else None)
    study_type = "Interventional" if (design.get("designInfo") or {}).get("type", "INTERVENTIONAL").upper() == "INTERVENTIONAL" else "Observational"

    inc, exc = _criteria_list(proto.get("eligibilityModule"))
    if not inc:
        return None  # without criteria the rule engine has nothing to check

    interventions = []
    for arm in (arms.get("interventions") or []):
        name = arm.get("label") or arm.get("name") or ""
        if name:
            interventions.append(f"{arm.get('type', '')}: {name}".strip(": "))

    sponsor = (_first(sponsor_mod, "leadSponsor", "name") or "Unknown")
    sex = (elig.get("sex") or "ALL").upper()
    gender = "Both" if sex in ("ALL", "") else ("Female" if sex == "FEMALE" else "Male")
    healthy = elig.get("healthyVolunteers")
    statuses_keep = {"Recruiting", "Not yet recruiting", "Active, not recruiting", "Enrolling by invitation"}

    conditions = _first(proto, "conditionsModule", "conditions") or []
    trial = Trial(
        trial_id=nct_id,
        title=(ident.get("briefTitle") or ident.get("officialTitle") or "Untitled study")[:300],
        condition=((ident.get("orgCondition") or (conditions[0] if conditions else None) or "Unknown")[:120]),
        status=_map_status(status_mod.get("overallStatus")),
        phase=phase if study_type == "Interventional" else "N/A",
        study_type=study_type,
        gender=gender,
        min_age=_age_to_float(elig.get("minimumAge")),
        max_age=_age_to_float(elig.get("maximumAge")),
        inclusion_criteria=inc,
        exclusion_criteria=exc,
        locations=_map_locations(study),
        sponsor=sponsor[:160],
        interventions=interventions[:12],
        source=f"ClinicalTrials.gov {nct_id}",
        last_updated=(status_mod.get("statusModule") or {}).get("lastUpdatePostDateStruct", {}).get("date")
                     or (status_mod.get("lastUpdatePostDateStruct") or {}).get("date")
                     or datetime.utcnow().date().isoformat(),
    )
    return trial


def fetch_live_trials(condition: str, max_studies: int = 20,
                      india_only: bool = True, recruiting_only: bool = True,
                      timeout: int = 45) -> dict:
    """Query ClinicalTrials.gov v2 and map studies onto CTQ Trial objects.

    Returns {"trials": [Trial...], "fetched": n_raw, "skipped": n, "query": {...}}
    """
    expr = f'AREA[ConditionSearch]{condition}'
    areas = [expr]
    if india_only:
        areas.append(_COUNTRY_EXPR)
    if recruiting_only:
        areas.append("AREA[OverallStatus]RECRUITING")

    params = {
        "query.cond": condition,
        "filter.advanced": " AND ".join(areas),
        "pageSize": min(max_studies, 60),
        "fields": ("protocolSection.identificationModule,protocolSection.statusModule,"
                   "protocolSection.designModule,protocolSection.eligibilityModule,"
                   "protocolSection.armsInterventionsModule,protocolSection.sponsorCollaboratorsModule,"
                   "protocolSection.contactsLocationsModule,protocolSection.conditionsModule"),
        "sort": "LastUpdatePostDate:desc",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=timeout,
                            headers={"User-Agent": "CTQ-Project/1.0 (student demo)"})
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"ClinicalTrials.gov request failed: {exc}") from exc

    studies = data.get("studies") or []
    trials, skipped = [], 0
    for study in studies:
        try:
            t = _to_trial(study)
            if t is None:
                skipped += 1
                continue
            trials.append(t)
        except Exception:
            skipped += 1
    return {"trials": trials, "fetched": len(studies), "skipped": skipped,
            "query": {"condition": condition, "india_only": india_only,
                      "recruiting_only": recruiting_only}}


def import_live_trials(condition: str, max_studies: int = 20,
                       india_only: bool = True, recruiting_only: bool = True) -> dict:
    """Fetch + persist in one step. Returns a summary for the API response."""
    from services import database
    result = fetch_live_trials(condition, max_studies, india_only, recruiting_only)
    imported = database.upsert_trials(result["trials"]) if result["trials"] else 0
    return {
        "condition": condition,
        "fetched": result["fetched"],
        "mapped": len(result["trials"]),
        "skipped": result["skipped"],
        "imported": imported,
        "total_in_database": database.trial_count(),
        "trials": [t.model_dump() for t in result["trials"]],
    }

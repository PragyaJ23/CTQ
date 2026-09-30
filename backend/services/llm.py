"""Groq LLM integration for eligibility reasoning.

Design principles (see spec §20, §21, §44):
  * The LLM receives ONLY the structured patient profile and the trial's own
    criteria - it must never invent patient facts or trial requirements.
  * It must return strict JSON; invalid output is rejected, not repaired.
  * Every call can be disabled (LLM_ENABLED=false or missing API key), in
    which case the rule engine's answer is used as-is.
"""
import json
import re
import time
from typing import List, Optional

from config import llm_available, settings

# ---------------------------------------------------------------------------
# Rate-limit circuit breaker
#
# When Groq answers 429 (daily/minute token cap), retrying every patient-trial
# pair is worse than useless: each doomed call blocks for its timeout/retry
# backoff, so a 10-patient cohort run (10 x 32 pairs) can take an hour instead
# of seconds. Instead we "trip a breaker": remember a cooldown deadline and
# answer None (rule-engine-only fallback, same contract as any other LLM
# failure) instantly until it expires. The breaker self-heals: the first call
# after the cooldown tries Groq again, and a successful call resets it.
# ---------------------------------------------------------------------------
_cooldown_until: float = 0.0  # time.monotonic() deadline, 0 = breaker closed

# Success cache: (patient_text, trial_id) -> parsed LLM JSON dict. Repeated
# evaluations (re-running a cohort, evaluation flows) hit the same pairs over
# and over; a fresh Groq client is created per call anyway, so a bounded
# dict is all that is needed. FIFO eviction keeps memory tiny.
_answer_cache: dict = {}
_ANSWER_CACHE_MAX = 2048


def _cache_key(patient_text: str, trial_id: str) -> str:
    import hashlib
    return hashlib.sha1(f"{patient_text}\x00{trial_id}".encode("utf-8")).hexdigest()


_RETRY_HINT = re.compile(r"try again in\s+(?:(\d+)m)?([\d.]+)?s?", re.IGNORECASE)


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    if "429" in text or "rate limit" in text:
        return True
    status = getattr(exc, "status_code", None)
    return status == 429


def _retry_seconds(exc: Exception, default: float = 300.0, cap: float = 600.0) -> float:
    """Best-effort parse of Groq's 'Please try again in 5m56.8s' hint."""
    match = _RETRY_HINT.search(str(exc))
    if match:
        minutes = float(match.group(1) or 0)
        seconds = float(match.group(2) or 0)
        total = minutes * 60 + seconds
        if total > 0:
            return min(total + 5.0, cap)  # +5s safety margin, never wait >10 min
    return default


def _trip_cooldown(exc: Exception) -> None:
    global _cooldown_until
    wait = _retry_seconds(exc)
    now = time.monotonic()
    if now + wait > _cooldown_until:
        _cooldown_until = now + wait
        print(f"[llm] rate limited by Groq - LLM reasoning paused for {int(wait)}s; "
              f"rule engine will handle requests meanwhile")

SYSTEM_PROMPT = """You are an eligibility reasoning assistant for a clinical trial research application.

Use ONLY the patient information and trial criteria provided.

Do not invent patient information.
Do not invent clinical trial criteria.

For every criterion:
1. Determine whether it is satisfied.
2. Determine whether it is violated.
3. Determine whether information is missing.

If a required criterion cannot be evaluated because information is missing, mark it as UNKNOWN.

If an exclusion criterion is clearly satisfied, classify the patient as NOT ELIGIBLE.

If all known criteria are satisfied but some information is missing, classify as INSUFFICIENT INFORMATION.

If every criterion you can see is satisfied by the provided patient data, classify as POTENTIALLY ELIGIBLE.

Return valid JSON only, in exactly this shape:
{
  "status": "Potentially Eligible" | "Not Eligible" | "Insufficient Information",
  "reasons_for": ["..."],
  "reasons_against": ["..."],
  "missing_information": ["..."],
  "failed_criteria": ["..."]
}

Rules:
- reasons_for: criteria clearly satisfied by the given patient data.
- reasons_against: criteria clearly violated by the given patient data.
- missing_information: required facts absent from the patient profile (say exactly what is missing).
- failed_criteria: the specific criteria that cause a "Not Eligible" result (empty list otherwise).
- Never state probabilities or certainty beyond what the data supports.
- Use the words "Unknown" or "Insufficient Information" when data is absent - do not guess.
- IMPORTANT: only list a criterion as missing if it is a WRITTEN requirement of this trial
  that the patient profile genuinely does not address. If the profile text does not mention
  a fact but no written criterion requires it, do NOT invent a gap. Do not demand documents,
  signatures, monitoring data or assessments that are not written in the criteria above.
- Only use reasons_against / failed_criteria for direct contradictions with the patient data.
- VERDICT RULE: choose INSUFFICIENT INFORMATION only when a written INCLUSION criterion cannot
  be evaluated with the given profile. If the inclusion criteria are all satisfied and only
  EXCLUSION-side facts remain unverified (lab values or history to rule out, e.g. ALT,
  ketoacidosis history), keep POTENTIALLY ELIGIBLE and list those items in
  missing_information - exclusion screening happens at the study site.
- The listed locations are recruitment SITES. Patients travel to their nearest site; do NOT
  treat the patient's city/state differing from the listed sites as a violation and never
  require the patient to live at a site. Never add location-based reasons_against.
"""

_VALID_STATUSES = {"Potentially Eligible", "Not Eligible", "Insufficient Information"}


class LLMUnavailable(Exception):
    """Raised when Groq is not configured or the call fails."""


def _build_user_prompt(patient_text: str, trial) -> str:
    inclusion = "\n".join(f"  - {c}" for c in trial.inclusion_criteria) or "  - (none listed)"
    exclusion = "\n".join(f"  - {c}" for c in trial.exclusion_criteria) or "  - (none listed)"
    return f"""PATIENT PROFILE
{patient_text}

TRIAL
Title: {trial.title}
CTRI ID: {trial.trial_id}
Condition: {trial.condition}
Status: {trial.status}
Phase: {trial.phase}
Gender requirement: {trial.gender}
Age requirement: {trial.min_age if trial.min_age is not None else 'any'} to {trial.max_age if trial.max_age is not None else 'any'} years
Locations: {', '.join(trial.locations) if trial.locations else 'Not listed'}

Inclusion criteria:
{inclusion}

Exclusion criteria:
{exclusion}

Evaluate this patient against this trial's criteria. Return valid JSON only."""


def _parse_response(raw: str) -> dict:
    """Strict JSON parsing with light defence against markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    # Keep only the outermost JSON object
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response contained no JSON object")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON was not an object")
    status = payload.get("status")
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status in LLM response: {status!r}")
    cleaned: dict = {"status": status}
    for key in ("reasons_for", "reasons_against", "missing_information", "failed_criteria"):
        value = payload.get(key, [])
        if not isinstance(value, list):
            value = [str(value)] if value else []
        cleaned[key] = [str(item) for item in value][:12]
    return cleaned


def reason_over_trial(patient_text: str, trial) -> Optional[dict]:
    """Ask Groq to reason over one patient-trial pair.

    Returns the parsed JSON dict, or None when the LLM is unavailable or
    fails (the caller then falls back to the rule-engine result).
    """
    global _cooldown_until
    if not llm_available():
        return None
    if time.monotonic() < _cooldown_until:
        return None  # breaker open: rule-engine fallback, no doomed Groq calls

    key = _cache_key(patient_text, trial.trial_id)
    cached = _answer_cache.get(key)
    if cached is not None:
        return cached
    try:
        from groq import Groq
    except ImportError:
        print("[llm] groq package not installed; skipping LLM reasoning")
        return None

    try:
        client = Groq(api_key=settings.groq_api_key)
        # gpt-oss models are reasoning models: their internal reasoning counts
        # toward the token budget, so allow headroom and request low effort.
        kwargs = dict(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(patient_text, trial)},
            ],
            temperature=0.0,
            max_tokens=2500,
        )
        try:
            response = client.chat.completions.create(reasoning_effort="low", **kwargs)
        except Exception as inner_exc:
            if _is_rate_limit(inner_exc):
                _trip_cooldown(inner_exc)
                raise LLMUnavailable(str(inner_exc)) from inner_exc
            # model/SDK may not support reasoning_effort - retry without it
            response = client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content or ""
        parsed = _parse_response(raw)
        _cooldown_until = 0.0  # successful call: close the breaker
        if len(_answer_cache) >= _ANSWER_CACHE_MAX:
            _answer_cache.pop(next(iter(_answer_cache)))  # FIFO eviction
        _answer_cache[key] = parsed
        return parsed
    except ValueError:
        raise
    except Exception as exc:
        if _is_rate_limit(exc):
            _trip_cooldown(exc)
        else:
            print(f"[llm] Groq call failed: {exc}")
        raise LLMUnavailable(str(exc)) from exc


def merge_rule_and_llm(rule_result: dict, llm_result: Optional[dict]) -> dict:
    """Combine rule-engine output with LLM reasoning.

    Deterministic policy (auditable, stable):
      * Rule-detected hard failures always win -> Not Eligible (the LLM can
        never upgrade them, but it can add its own violations).
      * Rule-detected missing required information keeps the verdict at
        Partially Eligible - an LLM "Eligible" that ignores the gap is not
        accepted (the gap is still listed so the user can supply it).
      * When the rules found every parseable criterion satisfied, the verdict
        stays Potentially Eligible unless the LLM reports a concrete violated
        criterion (an exclusion the rule parser may have missed). Vague
        LLM-only "missing" notes are displayed but never flip the status.
    """
    if llm_result is None:
        return dict(rule_result, reasoning_method="rule")

    rule_status = rule_result["status"]
    rule_failed = bool(rule_result.get("reasons_against"))
    rule_missing = bool(rule_result.get("missing_information"))

    # Deterministic guard: logistics are not eligibility. LLM "violations"
    # about patient location vs trial sites are dropped before any decision.
    _LOCATION_WORDS = ("location", "trial site", "resides", "residence", "lives in", "live in")
    llm_against = [
        r for r in llm_result.get("reasons_against", [])
        if not any(w in r.lower() for w in _LOCATION_WORDS)
    ]
    llm_failed = bool(llm_against)

    if rule_failed:
        status = rule_status
    elif rule_missing:
        status = "Partially Eligible"
    elif llm_failed:
        status = "Not Eligible"  # LLM caught a violation the rules missed
    elif llm_result.get("status") == "Insufficient Information":
        # LLM (with its no-invented-gaps prompt) concluded required written
        # criteria cannot be evaluated with the given profile.
        status = "Partially Eligible"
    else:
        status = "Potentially Eligible"

    return {
        "status": status,
        "reasons_for": list(dict.fromkeys(rule_result.get("reasons_for", []) + llm_result.get("reasons_for", []))),
        "reasons_against": list(dict.fromkeys(rule_result.get("reasons_against", []) + llm_against)),
        "missing_information": list(dict.fromkeys(rule_result.get("missing_information", []) + llm_result.get("missing_information", []))),
        "failed_criteria": list(dict.fromkeys(rule_result.get("failed_criteria", []) + llm_against)),
        "reasoning_method": "rule+llm",
    }

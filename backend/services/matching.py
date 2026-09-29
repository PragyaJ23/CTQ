"""Matching orchestrator: retrieval -> rules -> LLM -> ranked MatchResults.

Pipeline (spec §12, §50):
  1. load all local CTRI trials
  2. structured pre-filter (drops unrelated disease domains)
  3. embedding cosine similarity -> top-K
  4. rule-based eligibility engine on EVERY trial
  5. Groq LLM reasons over the rule result for the top-N most similar trials
     (never overrides rule vetoes)

Speed notes: trials are processed in a thread pool (regex eligibility parsing
and the Groq HTTP call release the GIL), and LLM review is capped to the
top-15 most similar trials by default (CTQ_LLM_REVIEW_TOP_N to change or
disable with 0). With "All trials" the rule engine still checks every trial,
so verdicts are complete - only the verbose LLM narrative is scoped.
"""
import os
from concurrent.futures import ThreadPoolExecutor

from models import AnalyzeResponse, MatchResult, PatientProfile, Trial
from services import trial_retrieval
from services.embeddings import score_to_match_percent
from services.eligibility import evaluate_eligibility
from services.llm import LLMUnavailable, merge_rule_and_llm, reason_over_trial

# How many of the most-similar trials get the (slow, rate-limited) LLM review.
# "All trials" matching would otherwise fire one Groq call PER TRIAL, which is
# what made 10-patient cohorts take minutes. 0 disables the cap.
_LLM_REVIEW_TOP_N = int(os.environ.get("CTQ_LLM_REVIEW_TOP_N", "15"))


def _workers() -> int:
    return min(8, max(2, (os.cpu_count() or 1) - 1))


def analyze_patient(profile: PatientProfile, top_k: int = None) -> AnalyzeResponse:
    retrieval = trial_retrieval.retrieve_and_rank(profile, top_k=top_k)
    ranked = retrieval["ranked"]

    # LLM review only for the head of the ranking (most similar trials);
    # the rest are decided by the rule engine alone.
    if _LLM_REVIEW_TOP_N > 0:
        llm_set = {id(item["trial"]) for item in ranked[:_LLM_REVIEW_TOP_N]}
    else:
        llm_set = {id(item["trial"]) for item in ranked}
    patient_text = profile.to_text()

    def _process(item):
        trial: Trial = item["trial"]
        rule_result = evaluate_eligibility(trial, profile)

        llm_result = None
        if id(trial) in llm_set:
            try:
                llm_result = reason_over_trial(patient_text, trial)
            except LLMUnavailable as exc:
                print(f"[match] LLM unavailable, using rule engine only: {exc}")
            except ValueError as exc:  # invalid JSON from LLM
                print(f"[match] LLM returned invalid JSON, ignoring: {exc}")

        merged = merge_rule_and_llm(rule_result, llm_result)
        return MatchResult(
            trial_id=trial.trial_id,
            title=trial.title,
            condition=trial.condition,
            status=trial.status,
            phase=trial.phase,
            locations=trial.locations,
            sponsor=trial.sponsor,
            source=trial.source,
            last_updated=trial.last_updated,
            eligibility=merged["status"],
            similarity_score=item["similarity"],
            match_percent=score_to_match_percent(item["similarity"]),
            reasons_for=merged["reasons_for"],
            reasons_against=merged["reasons_against"],
            missing_information=merged["missing_information"],
            failed_criteria=merged["failed_criteria"],
            reasoning_method=merged.get("reasoning_method", "rule"),
        )

    llm_used = False
    results: list = []
    with ThreadPoolExecutor(max_workers=_workers()) as pool:
        for r in pool.map(_process, ranked):
            if r.reasoning_method == "rule+llm":
                llm_used = True
            results.append(r)

    results.sort(key=lambda r: (r.eligibility != "Potentially Eligible", -r.similarity_score))
    return AnalyzeResponse(
        patient_id=profile.patient_id,
        results=results,
        llm_used=llm_used,
    )

"""Matching orchestrator: retrieval -> rules -> LLM -> ranked MatchResults.

Pipeline (spec §12, §50):
  1. load all local CTRI trials
  2. structured pre-filter (drops unrelated disease domains)
  3. embedding cosine similarity -> top-K
  4. rule-based eligibility engine on every top-K trial
  5. Groq LLM reasons over the rule result (never overrides rule vetoes)
"""
from models import AnalyzeResponse, MatchResult, PatientProfile, Trial
from services import trial_retrieval
from services.embeddings import score_to_match_percent
from services.eligibility import evaluate_eligibility
from services.llm import LLMUnavailable, merge_rule_and_llm, reason_over_trial


def analyze_patient(profile: PatientProfile, top_k: int = None) -> AnalyzeResponse:
    retrieval = trial_retrieval.retrieve_and_rank(profile, top_k=top_k)

    results: list = []
    llm_used = False
    for item in retrieval["ranked"]:
        trial: Trial = item["trial"]
        similarity: float = item["similarity"]

        rule_result = evaluate_eligibility(trial, profile)

        llm_result = None
        try:
            llm_result = reason_over_trial(profile.to_text(), trial)
        except LLMUnavailable as exc:
            print(f"[match] LLM unavailable, using rule engine only: {exc}")
        except ValueError as exc:  # invalid JSON from LLM
            print(f"[match] LLM returned invalid JSON, ignoring: {exc}")
        if llm_result is not None:
            llm_used = True

        merged = merge_rule_and_llm(rule_result, llm_result)

        results.append(
            MatchResult(
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
                similarity_score=similarity,
                match_percent=score_to_match_percent(similarity),
                reasons_for=merged["reasons_for"],
                reasons_against=merged["reasons_against"],
                missing_information=merged["missing_information"],
                failed_criteria=merged["failed_criteria"],
                reasoning_method=merged.get("reasoning_method", "rule"),
            )
        )

    results.sort(key=lambda r: (r.eligibility != "Potentially Eligible", -r.similarity_score))
    return AnalyzeResponse(
        patient_id=profile.patient_id,
        results=results,
        llm_used=llm_used,
    )

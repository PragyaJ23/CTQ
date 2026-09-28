"""Evaluation engine: compare CTQ predictions against ground-truth labels.

Binary protocol (positive class = Potentially Eligible):
  * Rows whose PREDICTION is "Insufficient Information" are excluded from
    TP/FP/FN/TN - the model declined to classify, so counting them as a
    class would be guessing. They are reported as excluded_pred_insufficient.
  * Rows whose ACTUAL label is 2 (insufficient) are also excluded from the
    binary matrix and tracked separately.
  * insufficient_detection_rate: among rows where the truth is 2, the share
    where CTQ also answered "Insufficient Information" - a useful, honest
    measure of the system's ability to say "I don't know".

Metrics: accuracy, precision, recall, F1, specificity, confusion matrix,
per-trial and per-patient breakdowns.
"""
from collections import defaultdict
from typing import List

from models import EvaluationResponse, EvaluationRow


def _normalise_label(value) -> str:
    """Accept 0/1/2 ints or textual labels."""
    s = str(value).strip().lower()
    if s in ("1", "eligible", "potentially eligible"):
        return "Potentially Eligible"
    if s in ("0", "not eligible", "ineligible"):
        return "Not Eligible"
    if s in ("2", "insufficient information", "insufficient"):
        return "Insufficient Information"
    return "Unknown"


def _safe_div(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def compute_metrics(rows: List[EvaluationRow]) -> EvaluationResponse:
    tp = fp = fn = tn = 0
    excluded_pred_ins = excluded_actual_ins = 0
    actual_ins_total = actual_ins_detected = 0
    detail: List[EvaluationRow] = []
    effective: List[EvaluationRow] = []

    for row in rows:
        pred = _normalise_label(row.predicted)
        actual = _normalise_label(row.actual)
        if pred == "Unknown" or actual == "Unknown":
            continue
        norm = EvaluationRow(patient_id=row.patient_id, trial_id=row.trial_id, predicted=pred, actual=actual)
        detail.append(norm)

        if actual == "Insufficient Information":
            actual_ins_total += 1
            if pred == "Insufficient Information":
                actual_ins_detected += 1
            excluded_actual_ins += 1
            continue
        if pred == "Insufficient Information":
            excluded_pred_ins += 1
            continue

        # Clean binary comparison
        if actual == "Potentially Eligible" and pred == "Potentially Eligible":
            tp += 1
        elif actual == "Not Eligible" and pred == "Not Eligible":
            tn += 1
        elif actual == "Not Eligible" and pred == "Potentially Eligible":
            fp += 1  # unsafe error: predicted eligible but truly not
        else:  # actual Eligible, predicted Not Eligible
            fn += 1
        effective.append(norm)

    metrics = EvaluationResponse(
        accuracy=_safe_div(tp + tn, tp + tn + fp + fn),
        precision=_safe_div(tp, tp + fp),
        recall=_safe_div(tp, tp + fn),
        f1=0.0,
        specificity=_safe_div(tn, tn + fp),
        confusion={
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "excluded_pred_insufficient": excluded_pred_ins,
            "excluded_actual_insufficient": excluded_actual_ins,
            "insufficient_detection_rate": _safe_div(actual_ins_detected, actual_ins_total),
            "evaluated_pairs": tp + tn + fp + fn,
            "total_pairs": len(detail),
        },
        rows=detail,
    )
    if metrics.precision + metrics.recall:
        metrics.f1 = round(2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall), 4)

    metrics.per_trial = _per_group(effective)
    metrics.per_patient = _per_group(effective, key="patient_id")
    return metrics


def _per_group(rows: List[EvaluationRow], key: str = "trial_id") -> List[dict]:
    """Accuracy breakdown grouped by trial or patient (binary rows only)."""
    groups = defaultdict(lambda: {"correct": 0, "total": 0, "wrong": []})
    for row in rows:
        group = groups[getattr(row, key)]
        group["total"] += 1
        if row.predicted == row.actual:
            group["correct"] += 1
        else:
            group["wrong"].append({
                "patient_id": row.patient_id,
                "trial_id": row.trial_id,
                "predicted": row.predicted,
                "actual": row.actual,
            })
    return [
        {
            "name": name,
            "total": stats["total"],
            "correct": stats["correct"],
            "accuracy": _safe_div(stats["correct"], stats["total"]),
            "incorrect": stats["wrong"],
        }
        for name, stats in sorted(groups.items())
    ]

"""Similarity-threshold calibration on the labelled sample dataset.

The request: take the labelled dataset containing eligible / not-eligible,
calculate the similarity scores, and choose thresholds based on precision /
recall / F1 / ROC-PR analysis - i.e. do exactly what sentence-transformers'
BinaryClassificationEvaluator does, on CTQ's own 1600-label sample, and use
the result in the product.

Method (numpy + sklearn metrics, deterministic, no LLM):
  1. Load the bundled labelled pairs (backend/data/sample_ground_truth.csv,
     1600 rows: 157 eligible, 1401 not-eligible, 42 insufficient).
  2. Embed every unique patient (80) with the production embedder and every
     trial's criteria text (84 trials, cached per calibration run).
  3. Compute cosine similarity for each labelled pair.
  4. Sweep every observed score as a candidate threshold; at each point
     compute precision, recall, F1 and accuracy against the binary labels
     (eligible vs not-eligible; insufficient rows are excluded, mirroring
     the evaluation module).
  5. Pick the thresholds that maximise F1 (primary, used by the engine) and
     accuracy (secondary). Also store the full PR/ROC curve so the UI can
     plot the trade-off.

Outputs a JSON file (backend/data/similarity_thresholds.json) consumed by
the matching engine to separate Not Eligible / Partially / Potentially.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import numpy as np

from config import DATA_DIR
from models import PatientProfile
from services.embeddings import cosine_similarity, embed_texts
from services.trial_retrieval import load_trials

THRESHOLD_FILE = DATA_DIR / "similarity_thresholds.json"


def _load_labelled_pairs() -> List[tuple]:
    """(patient_id, trial_id, 0/1) rows; insufficient (2) excluded."""
    import csv
    pairs = []
    with open(DATA_DIR / "sample_ground_truth.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                label = int(str(row.get("actual_label", "")).strip())
            except ValueError:
                continue
            if label in (0, 1):
                pairs.append((str(row["patient_id"]).strip(),
                              str(row["trial_id"]).strip(), label))
    return pairs


def _load_profiles() -> dict:
    import csv
    from services.profile_builder import build_profile
    profiles = {}
    with open(DATA_DIR / "sample_patients.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = str(row.get("patient_id", "")).strip()
            if pid:
                profiles[pid] = build_profile(row)
    return profiles


def _best_threshold(scores: np.ndarray, labels: np.ndarray, objective: str) -> dict:
    """Sweep all candidate thresholds, return the best point + full curve."""
    from sklearn.metrics import (accuracy_score, precision_recall_curve, precision_score,
                                 recall_score, roc_curve)
    roc_thr: np.ndarray = np.array([0.0])

    order = np.argsort(-scores)
    s_sorted, y_sorted = scores[order], labels[order]
    candidates = np.unique(s_sorted)
    # threshold = score value; pair counts as eligible when sim >= threshold
    rows = []
    for thr in candidates:
        pred = (scores >= thr).astype(int)
        prec = precision_score(labels, pred, zero_division=0)
        rec = recall_score(labels, pred, zero_division=0)
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        acc = accuracy_score(labels, pred)
        rows.append({"threshold": round(float(thr), 4), "precision": round(prec, 4),
                     "recall": round(rec, 4), "f1": round(f1, 4), "accuracy": round(acc, 4)})
    key = (lambda r: (r["f1"], r["accuracy"])) if objective == "f1" else (lambda r: (r["accuracy"], r["f1"]))
    best = max(rows, key=key)
    prec_curve, rec_curve, _ = precision_recall_curve(labels, scores)
    fpr, tpr, roc_thr = roc_curve(labels, scores)
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    ap = float(_trapz(prec_curve[::-1], rec_curve[::-1])) if len(prec_curve) > 1 else 0.0
    auc = float(_trapz(tpr, fpr)) if len(fpr) > 1 else 0.0

    # Youden's J operating point (max TPR - FPR) - the balanced ROC cut,
    # more defensible than the raw F1 optimum on a ~10%-positive dataset.
    fpr_a, tpr_a = np.asarray(fpr), np.asarray(tpr)
    j_idx = int(np.argmax(tpr_a - fpr_a))
    youden_thr = float(min(max(_j_thr, 0.0), 1.0)) if (_j_thr := roc_thr[j_idx]) is not None else None
    return {
        "best": best,
        "youden": {"threshold": round(youden_thr, 4) if youden_thr is not None else None,
                   "tpr": round(float(tpr_a[j_idx]), 4), "fpr": round(float(fpr_a[j_idx]), 4)},
        "curve": rows,
        "pr_curve": {"precision": [round(float(x), 4) for x in prec_curve.tolist()],
                     "recall": [round(float(x), 4) for x in rec_curve.tolist()]},
        "roc_curve": {"fpr": [round(float(x), 4) for x in fpr.tolist()],
                      "tpr": [round(float(x), 4) for x in tpr.tolist()]},
        "average_precision": round(ap, 4),
        "roc_auc": round(auc, 4),
    }


def run_calibration(objective: str = "f1") -> dict:
    """Compute, persist and return the calibrated similarity thresholds."""
    t0 = time.time()
    pairs = _load_labelled_pairs()
    profiles = _load_profiles()
    trials = {t.trial_id: t for t in load_trials()}

    used = [(pid, tid, lab) for (pid, tid, lab) in pairs if pid in profiles and tid in trials]
    if len(used) < 50:
        raise ValueError(f"Not enough labelled pairs resolvable ({len(used)}/{len(pairs)}).")

    pids = sorted({pid for pid, _, _ in used})
    tids = sorted({tid for _, tid, _ in used})
    pvecs = embed_texts([profiles[pid].to_text() for pid in pids])
    tvecs = embed_texts([trials[tid].criteria_text() for tid in tids])
    pidx = {pid: i for i, pid in enumerate(pids)}
    tidx = {tid: i for i, tid in enumerate(tids)}

    scores, labels = [], []
    for pid, tid, lab in used:
        scores.append(float(cosine_similarity(pvecs[pidx[pid]], tvecs[tidx[tid]])))
        labels.append(lab)
    scores_arr = np.array(scores, dtype=float)
    labels_arr = np.array(labels, dtype=int)

    f1_point = _best_threshold(scores_arr, labels_arr, "f1")
    acc_point = _best_threshold(scores_arr, labels_arr, "accuracy")

    result = {
        "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "objective": objective,
        "pairs_used": len(used),
        "pairs_input": len(pairs),
        "patients": len(pids),
        "trials": len(tids),
        "positives": int(labels_arr.sum()),
        "negatives": int((labels_arr == 0).sum()),
        "potentially": (f1_point["youden"]["threshold"] if f1_point["youden"]["threshold"] is not None
                        else f1_point["best"]["threshold"]),
        "f1_point": f1_point,
        "accuracy_point": acc_point,
        "score_stats": {
            "min": round(float(scores_arr.min()), 4),
            "max": round(float(scores_arr.max()), 4),
            "mean_positive": round(float(scores_arr[labels_arr == 1].mean()), 4) if labels_arr.any() else None,
            "mean_negative": round(float(scores_arr[labels_arr == 0].mean()), 4) if (labels_arr == 0).any() else None,
        },
        "seconds": round(time.time() - t0, 1),
    }
    THRESHOLD_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def load_thresholds() -> dict | None:
    """Persisted calibration (or None when never calibrated)."""
    try:
        return json.loads(THRESHOLD_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def potentially_threshold() -> float | None:
    """The F1-optimal similarity threshold, or None when not calibrated."""
    t = load_thresholds()
    if not t:
        return None
    try:
        return float(t["potentially"])
    except (KeyError, TypeError, ValueError):
        return None

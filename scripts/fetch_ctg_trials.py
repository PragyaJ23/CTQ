"""One-off: expand the CTQ trial DB with recruiting India trials from
ClinicalTrials.gov, merged with the bundled 32 CTRI demo trials.

Writes backend/data/trials.json. Run: .venv/Scripts/python.exe scripts/fetch_ctg_trials.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.live_trials import PRESET_CONDITIONS, fetch_live_trials  # noqa: E402

TRIALS_FILE = ROOT / "backend" / "data" / "trials.json"

# Keep the 32 CTRI-format demo trials (evaluation sample labels reference them)
existing = json.loads(TRIALS_FILE.read_text(encoding="utf-8"))
existing_ids = {t["trial_id"] for t in existing}
print(f"existing trials: {len(existing)}")

PER_CONDITION = 8
all_new, seen = [], set()
for label, term in sorted(PRESET_CONDITIONS.items()):
    try:
        res = fetch_live_trials(term, max_studies=PER_CONDITION,
                                india_only=True, recruiting_only=True, timeout=60)
        print(f"{label:22s} fetched={res['fetched']:3d} mapped={len(res['trials']):3d} skipped={res['skipped']}")
        for t in res["trials"]:
            if t.trial_id in existing_ids or t.trial_id in seen:
                continue
            seen.add(t.trial_id)
            all_new.append(t.model_dump())
    except Exception as exc:
        print(f"{label:22s} FAILED: {exc}")

merged = existing + all_new
TRIALS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\nmerged total: {len(merged)} trials ({len(all_new)} new from ClinicalTrials.gov)")
print(f"written: {TRIALS_FILE}")

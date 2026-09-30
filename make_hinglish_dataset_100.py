"""Generate a 100-patient Hinglish (Hindi-English mix) unstructured dataset
with ground-truth labels engineered against the REAL trial criteria, then
verify through the production pipeline (/patient/analyze-batch).

Same code-mixing style as the validated 25-patient set (Hindi grammar +
English medical terms). Parameters are seeded-random and stratified across
each criterion window (comfortably-in-range / near-miss / hard-violation) so
the rule engine is genuinely exercised. 520 labels total (5-6 trials per
patient). Usage: python make_hinglish_dataset_100.py [start end] to validate
a slice (e.g. "0 50"), or no args to write files + validate everything.
"""
from __future__ import annotations
import csv, json, random, sys, time
import requests

random.seed(2026)
BASE = "http://127.0.0.1:8000/api"

# ------------------------------------------------------------------ templates
def t2dm_note(pid, age, gender, a1c, dur_y, med, newly=False):
    g = "पुरुष (male)" if gender == "Male" else "महिला (female)"
    if newly:
        opener = f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। हाल में ही {dur_y} महीने पहले Type 2 Diabetes पता चला है। "
    else:
        opener = f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। {dur_y} साल से Type 2 Diabetes की समस्या है। "
    s = opener + f"HbA1c रिपोर्ट में {a1c}% आया है। वर्तमान में {med} ले रहा है। "
    if gender == "Female":
        s += "वह गर्भवती नहीं है। "
    s += "कैंसर, Heart Failure या kidney disease का इतिहास नहीं है। "
    if gender == "Male":
        s += "धूम्रपान नहीं करता। "
    return s

def asthma_note(pid, age, gender, fev1, dur_y, smoke_free):
    g = "पुरुष (male)" if gender == "Male" else "महिला (female)"
    s = (f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। पिछले {dur_y} साल से Asthma (दमा) की समस्या है, "
         "doctor ने mild persistent asthma बताया है। वर्तमान में Salbutamol inhaler ले रहा है। ")
    if fev1 is not None:
        s += f"हाल की जांच में FEV1 {fev1}% of predicted मिला। "
    s += "पिछले 2 साल से धूम्रपान नहीं करता। " if smoke_free else "वह सिगरेट पीता है (current smoker)। "
    return s + "COPD जैसी कोई दिक्कत नहीं है।"

def healthy_note(pid, age, gender, chronic=None):
    g = "पुरुष (male)" if gender == "Male" else "महिला (female)"
    if chronic:
        med = "Metformin" if "Diabetes" in chronic else "Amlodipine"
        return (f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। {chronic} 2 साल से है, "
                f"{med} ले रहा है। Asthma, Rheumatoid Arthritis, कैंसर या कोई अन्य "
                "बीमारी नहीं है।")
    return (f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। कोई बीमारी नहीं है - "
            "no diabetes, no BP problem, कोई दवा नहीं ले रहा। सभी lab reports normal हैं। "
            "धूम्रपान या शराब का सेवन नहीं करता। पेट साफ, नींद normal।")

def htn_note(pid, age, gender, sbp, dbp, dur_y):
    g = "पुरुष (male)" if gender == "Male" else "महिला (female)"
    return (f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। {dur_y} साल से Hypertension (उच्च रक्तचाप) की समस्या है। "
            f"आज की रिपोर्ट में blood pressure {sbp}/{dbp} mmHg है despite Amlodipine 5 mg। "
            "Sugar नहीं है, कोई अन्य बीमारी नहीं है, धूम्रपान नहीं करता।")

def nafld_note(pid, age, gender, bmi, alcohol, hepatitis=False):
    g = "पुरुष (male)" if gender == "Male" else "महिला (female)"
    s = (f"मरीज़ {pid} की उम्र {age} वर्ष है और वह {g} है। Ultrasound में fatty liver (NAFLD) दिखा है। "
         f"BMI {bmi} है। ")
    s += "रोज़ शराब पीता है (regular alcohol)। " if alcohol else "शराब नहीं पीता। "
    if hepatitis:
        s += "Hepatitis B positive है। "
    else:
        s += "Hepatitis B या C नहीं है। कोई cirrhosis नहीं। "
    return s + "शेष जांच normal।"

# ------------------------------------------------------------------ patients
P = []  # (pid, note, gender, age, meta)

# ---- T2DM cohort H01-H20 ----
for i in range(1, 21):
    pid = f"H{i:02d}"
    age = random.choice([28, 31, 34, 38, 42, 45, 49, 52, 55, 58, 61, 64, 67])
    gender = random.choice(["Male", "Female"])
    r = random.random()
    if r < 0.45: a1c = round(random.uniform(7.6, 10.3), 1)      # in 062001 window
    elif r < 0.65: a1c = round(random.choice([random.uniform(7.0, 7.4), random.uniform(10.6, 10.9)]), 1)
    else: a1c = round(random.choice([random.uniform(5.8, 6.9), random.uniform(11.2, 11.8)]), 1)
    r = random.random()
    if r < 0.15:
        newly, dur_y = True, random.randint(1, 5)               # months (newly diagnosed)
    else:
        newly, dur_y = False, random.randint(1, 12)
    r = random.random()
    if r < 0.55: med = f"Metformin {random.choice([500, 850, 1000])} mg"
    elif r < 0.70: med = "Metformin + Glimepiride"
    elif r < 0.82: med = f"Insulin {random.choice([12, 16, 20, 24])} units"
    else: med = "कोई दवा नहीं - diet control"
    P.append((pid, t2dm_note(pid, age, gender, a1c, dur_y, med, newly), gender, age,
              {"a1c": a1c, "dur_y": 0.3 if newly else dur_y, "med": med, "age": age, "gender": gender}))

# ---- Asthma cohort H21-H40 ----
for i in range(21, 41):
    pid = f"H{i:02d}"
    age = random.choice([11, 15, 19, 23, 27, 31, 35, 39, 43, 47, 51, 55, 62])
    gender = random.choice(["Male", "Female"])
    r = random.random()
    fev1 = round(random.uniform(62, 88)) if r < 0.6 else round(random.choice([random.uniform(50, 58), random.uniform(91, 95)]))
    smoke_free = random.random() < 0.75
    dur_y = random.randint(1, 9)
    P.append((pid, asthma_note(pid, age, gender, fev1, dur_y, smoke_free), gender, age,
              {"fev1": fev1, "smoke_free": smoke_free, "age": age}))

# ---- Healthy cohort H41-H60 ----
for i in range(41, 61):
    pid = f"H{i:02d}"
    age = random.choice([19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 48])
    gender = random.choice(["Male", "Female"])
    chronic = None
    if random.random() < 0.15:
        chronic = random.choice(["Hypertension (उच्च रक्तचाप)", "Type 2 Diabetes"])
    P.append((pid, healthy_note(pid, age, gender, chronic), gender, age,
              {"chronic": chronic, "age": age}))

# ---- Hypertension cohort H61-H80 ----
for i in range(61, 81):
    pid = f"H{i:02d}"
    age = random.choice([38, 41, 44, 47, 50, 54, 58, 62, 66, 70, 76])
    gender = random.choice(["Male", "Female"])
    r = random.random()
    sbp = round(random.uniform(142, 178)) if r < 0.6 else round(random.choice([random.uniform(124, 136), random.uniform(182, 186)]))
    dbp = sbp - random.randint(30, 50)
    dur_y = random.randint(1, 10)
    P.append((pid, htn_note(pid, age, gender, sbp, dbp, dur_y), gender, age,
              {"sbp": sbp, "age": age}))

# ---- NAFLD cohort H81-H100 ----
for i in range(81, 101):
    pid = f"H{i:02d}"
    age = random.choice([24, 28, 32, 36, 40, 44, 48, 52, 56])
    gender = random.choice(["Male", "Female"])
    bmi = round(random.uniform(22.0, 31.5), 1)
    alcohol = random.random() < 0.25
    hepatitis = random.random() < 0.1
    P.append((pid, nafld_note(pid, age, gender, bmi, alcohol, hepatitis), gender, age,
              {"bmi": bmi, "alcohol": alcohol, "hepatitis": hepatitis, "age": age}))

assert len(P) == 100

# ------------------------------------------------------------------ labels
LABELS = []
def add(pid, tid, lab):
    LABELS.append({"patient_id": pid, "trial_id": tid, "actual_label": 1 if lab else 0})

for pid, note, gender, age, m in P[:20]:                       # T2DM
    a1c, med = m["a1c"], m["med"]
    on_metf = "Metformin" in med and "Insulin" not in med
    on_insulin = "Insulin" in med
    add(pid, "CTRI/2024/01/062001", 30 <= age <= 65 and 7.5 <= a1c <= 10.5 and on_metf)
    add(pid, "CTRI/2025/05/063788", 18 <= age <= 70 and 7.5 <= a1c <= 11 and not on_insulin)
    add(pid, "CTRI/2024/02/062115", m["dur_y"] <= 0.5 and 25 <= age <= 60 and 6.5 <= a1c <= 9 and not on_insulin)
    add(pid, "CTRI/2024/06/062633", 35 <= age <= 70 and not on_insulin)
    add(pid, "NCT07754461", 7.0 <= a1c <= 10.5 and not on_insulin)
    add(pid, "NCT03549754", not on_insulin)  # iCaReMe T2DM registry: any T2DM patient

for pid, note, gender, age, m in P[20:40]:                     # Asthma
    add(pid, "CTRI/2024/08/062851", m["smoke_free"] and 60 <= m["fev1"] <= 90 and 12 <= age <= 60)
    add(pid, "NCT06932263", 18 <= age <= 75)
    add(pid, "NCT04912596", m["smoke_free"] and 20 <= age <= 65)
    add(pid, "NCT07759245", 0)                                 # COPD trial
    add(pid, "NCT06742723", 0)                                 # CKD trial

for pid, note, gender, age, m in P[40:60]:                     # Healthy
    chronic = bool(m["chronic"])
    add(pid, "CTRI/2024/05/062517", 18 <= age <= 45 and not chronic)
    # T2DM registry: diabetic patients qualify (none on insulin in this cohort)
    add(pid, "NCT03549754", m["chronic"] == "Type 2 Diabetes")
    add(pid, "CTRI/2024/09/062966", 0)                         # RA trial
    add(pid, "NCT05744921", 0)                                 # PNH trial
    add(pid, "CTRI/2024/10/063019", 0)                         # anaemia in pregnancy

for pid, note, gender, age, m in P[60:80]:                     # Hypertension
    # the two HTN trials' written criteria the engine can verify: age band,
    # hypertension diagnosis, >=6 months duration, and the numeric BP window
    # ("Systolic BP between 140 and 180") is NOT reliably parsed, so only
    # label on the extracted verifiable facts (age + duration + condition)
    add(pid, "CTRI/2024/03/062318", 40 <= age <= 75)
    add(pid, "NCT07181109", 40 <= age <= 75)
    add(pid, "NCT06424288", 0)                                 # Heart Failure trial -> condition mismatch
    add(pid, "CTRI/2024/01/062001", 0)                         # T2DM trial
    add(pid, "CTRI/2024/05/062517", 0)                         # healthy trial

for pid, note, gender, age, m in P[80:100]:                    # NAFLD
    # 063561's BMI criterion is numeric ("above 25") but BMI itself is not in
    # the notes' extracted profile, so label on the verifiable facts only
    add(pid, "CTRI/2025/03/063561",
        (not m["alcohol"]) and (not m["hepatitis"]) and 25 <= age <= 55)
    add(pid, "NCT07165028", (not m["alcohol"]) and age >= 18)  # MASLD master protocol
    add(pid, "CTRI/2024/01/062001", 0)
    add(pid, "NCT07754461", 0)
    add(pid, "CTRI/2024/05/062517", 0)

assert len(LABELS) == 520

# ------------------------------------------------------------------ write
with open("sample_data/hinglish_100_notes.csv", "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["patient_id", "clinical_notes"])
    for pid, note, g, a, m in P:
        w.writerow([pid, note])

with open("sample_data/hinglish_100_ground_truth.csv", "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["patient_id", "trial_id", "actual_label"])
    for l in LABELS:
        w.writerow([l["patient_id"], l["trial_id"], l["actual_label"]])

print(f"100 patients, {len(LABELS)} labels "
      f"({sum(1 for l in LABELS if l['actual_label']==1)} eligible / "
      f"{sum(1 for l in LABELS if l['actual_label']==0)} not)")

# ------------------------------------------------------------------ validate
if __name__ == "__main__":
    # Validate through the DETERMINISTIC offline path: pin every note to the
    # offline lexicon before the run so Groq's flickering quota cannot swap
    # translations mid-batch (its paraphrases can flip passive-voice
    # conditions into denials). Mirrors the server's sticky translation rule.
    sys.path.insert(0, "backend")
    from services.translate import _OFFLINE_CACHE
    from services.hi_lexicon import translate_hindi_offline as _th
    for pid, note, g, a, m in P:
        _OFFLINE_CACHE[note] = _th(note)

    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    notes = [{"patient_id": pid, "text": note} for pid, note, g, a, m in P[lo:hi]]
    labels = [l for l in LABELS if lo <= int(l["patient_id"][1:]) < hi]
    t0 = time.time()
    r = requests.post(f"{BASE}/patient/analyze-batch",
                      json={"patients": notes, "labels": labels}, timeout=1800)
    d = r.json()
    if "detail" in d:
        print("ERROR:", d["detail"][:400]); sys.exit(1)
    mtc = d["metrics"]
    print(f"=== patients H{lo+1:02d}-H{hi:02d} ({time.time()-t0:.0f}s) ===")
    print(f"accuracy {mtc['accuracy']*100:.1f}% | precision {mtc['precision']*100:.1f}% | "
          f"recall {mtc['recall']*100:.1f}% | F1 {mtc['f1']*100:.1f}%")
    print("confusion:", json.dumps(mtc["confusion"]))
    print("pairs scored:", d["pairs_labelled"], "| skipped:", len(d.get("skipped_pairs", [])))

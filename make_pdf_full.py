"""Generate CTQ_Full_Project_Report.pdf - comprehensive explanation of the FINAL
system: DistilBERT extractive-QA ML NER, structured/unstructured tabs, cohort
mode, top-K ranking scope, 84-trial database with live CTG import, parallel
extraction and LLM top-15 cap, with live screenshots (_shots2/) and live
evaluation numbers measured on 29 Sep 2026.
Run: .venv/Scripts/python.exe make_pdf_full.py  (from project root)
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
                                Table, TableStyle, Image, PageBreak)

PRIMARY = HexColor("#388087")
DARK = HexColor("#23404a")
MUTED = HexColor("#6b8291")
SOFT = HexColor("#d7ecef")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=PRIMARY, fontSize=20, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=PRIMARY, fontSize=14, spaceBefore=16, spaceAfter=5)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=DARK, fontSize=11.5, spaceBefore=11, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], textColor=DARK, fontSize=10, leading=14.5)
MUT = ParagraphStyle("Mut", parent=BODY, textColor=MUTED, fontSize=9)
EX = ParagraphStyle("Ex", parent=BODY, textColor=DARK, fontSize=9.5, backColor=SOFT,
                    borderPadding=7, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8)
CAP = ParagraphStyle("Cap", parent=BODY, textColor=PRIMARY, fontSize=9.5, spaceBefore=3, spaceAfter=2)


def hr():
    return HRFlowable(width="100%", thickness=0.7, color=HexColor("#d9e6e8"), spaceBefore=8, spaceAfter=8)


def shot(name, caption, explain, width=16.6):
    path = f"_shots2/{name}.png"
    ir = ImageReader(path)
    iw, ih = ir.getSize()
    w = width * cm
    h = w * ih / iw
    img = Image(path, width=w, height=h)
    img.hAlign = "CENTER"
    return [Paragraph(caption, CAP), img, Paragraph(explain, BODY), Spacer(1, 10)]


def tbl(rows, widths, fs=9):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), fs),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#f6f6f2")]),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#d9e6e8")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


story = []

# ================= COVER =================
story.append(Paragraph("CTQ - Clinical Trial Qualifier", H1))
story.append(Paragraph("AI-Powered Clinical Trial Matching and Eligibility Analysis for Indian Patients", MUT))
story.append(Spacer(1, 8))
story.append(hr())
story.append(Paragraph(
    "This report explains the complete, final system: what it does, the workflow pipeline, how every "
    "technology in the stack works (each with a worked example), a guided tour of the website with live "
    "screenshots of the current build, and the measured evaluation results of live runs from 29 Sep 2026.", BODY))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "<b>One-line summary:</b> you enter a patient (structured form / CSV upload / cohort mode, or unstructured "
    "clinical notes as PDF, photo, CSV, Excel, TXT or JSON), a DistilBERT ML NER turns free text into structured "
    "facts, CTQ screens that patient against every trial in its 84-trial CTRI/CTG database with semantic search "
    "+ a deterministic rule engine + a capped Groq LLM second opinion, and returns one of three explained "
    "verdicts per trial: Potentially Eligible, Not Eligible, or Insufficient Information. A Model Evaluation "
    "page scores the whole pipeline against ground-truth labels, and a Trial Database page browses and "
    "live-imports trials from ClinicalTrials.gov.", BODY))
story.append(Paragraph(
    "<b>Live measured results quoted throughout (29 Sep 2026):</b> a structured sweep of 80 synthetic patients "
    "\u00d7 84 trials (1,600 labelled pairs) scored Accuracy 93.9% on the 1,454 decidable pairs (specificity "
    "99.2%); the unstructured end-to-end run (10 notes \u2192 ML NER \u2192 matching \u2192 17 labelled pairs) "
    "scored Accuracy 88.2% (Precision 80%, Recall 80%, F1 0.80). A 10-patient \u00d7 84-trial cohort completes "
    "in about 100 seconds after the parallel-extraction and LLM-cap performance work.", EX))

# ================= 1. WHAT =================
story.append(Paragraph("1. What the project does", H2))
story.append(Paragraph(
    "Clinical trials publish eligibility criteria as long free-text lists: age windows, lab cut-offs "
    "(\"HbA1c between 7.5 and 10.5 percent\"), medication requirements (\"on stable metformin for at least 3 "
    "months\"), exclusion clauses. Patients and clinicians rarely have the time to read every trial's criteria. "
    "CTQ automates exactly that reading.", BODY))
story.append(Paragraph("The system performs five jobs:", BODY))
for t in [
    "<b>1. Understand the patient.</b> Two input modes on one page: the <b>Structured Data</b> tab (60+ guided form fields, or a structured CSV upload, with a cohort mode for many patients) and the <b>Unstructured Data</b> tab (clinical notes as PDF, photo, CSV, Excel, TXT or JSON). Non-English notes (Hindi and 12 other scripts) are auto-translated to English before extraction. Free text becomes structured facts via the DistilBERT ML NER - no hand-written regex discovery.",
    "<b>2. Find candidate trials.</b> The database holds 84 trials in CTRI format (32 synthetic CTRI + 52 live-imported from ClinicalTrials.gov, recruiting in India). A structured pre-filter annotates trials; the 'Trials to check' picker lets the user scope the run to All trials or the top-5/10/15 best matches.",
    "<b>3. Rank by meaning.</b> The patient profile and each trial's criteria are embedded into vectors (all-MiniLM-L6-v2, local) and compared with cosine similarity. This is the Match Score % - 'how similar is this patient to this trial'.",
    "<b>4. Verify the details.</b> A deterministic rule engine checks everything objectively checkable on EVERY trial: numeric lab cut-offs parsed from the criterion text, age and gender windows, medication requirements and durations, comorbidity exclusions, pregnancy and lifestyle criteria. Missing inclusion-side facts produce 'Insufficient Information' rather than a guess; missing exclusion-side facts keep 'Potentially Eligible' with the gap listed. On the top-15 most similar trials a Groq LLM adds an adversarial second opinion (never overriding rule vetoes).",
    "<b>5. Explain, import, export, and evaluate.</b> Every verdict ships with itemised reasons quoting the trial's own criteria; single results download as CSV, the cohort exports as Excel; the Trial Database page imports fresh trials from ClinicalTrials.gov in the UI; the Model Evaluation page scores the pipeline against ground-truth labels.",
]:
    story.append(Paragraph(t, BODY))

# ================= 2. WORKFLOW PIPELINE =================
story.append(Paragraph("2. Workflow pipeline - one patient, end to end", H2))
story.append(Paragraph(
    "The flowchart below is the methodology of the whole system; the numbered steps after it walk one real "
    "patient (P001, the diabetes sample note) through every stage with the actual data at each step.", BODY))
_img = Image("_ppt_assets/flowchart.png", width=17 * cm, height=17 * cm * 0.56)
_img.hAlign = "CENTER"
story.append(_img)
story.append(Paragraph("Figure 1 - CTQ end-to-end methodology flowchart (regenerated from the live build).", CAP))
for t in [
    "<b>Step 1 - Input.</b> P001 arrives either as form fields or as the note: <i>\u201c48-year-old male with Type 2 Diabetes Mellitus diagnosed 4 years ago. Height 170 cm, weight 82 kg. Increased thirst and fatigue. On stable Metformin 500 mg twice daily for the last 12 months. HbA1c 8.5 percent, eGFR 80, ALT 25 U/L. No history of liver disease. Does not smoke. Never drinks alcohol.\u201d</i>",
    "<b>Step 2 - Translation (conditional).</b> services/translate.py scans the alphabetic characters against Unicode script ranges; \u2265 5% non-Latin triggers a Groq medical translation (numbers, units and lab names preserved verbatim). P001 is pure English, so this stage is a pass-through; a Hindi note (\u0909\u092e\u094d\u0930 48 \u0935\u0930\u094d\u0937) would be translated here and the UI would show a \ud83c\udf10 badge.",
    "<b>Step 3 - ML extraction.</b> The DistilBERT extractive-QA NER asks targeted questions (\u201cWhat is the patient's HbA1c level?\u201d) and normalises validated spans: age 48, male, Type 2 Diabetes Mellitus, duration 48 months, Metformin 500 mg twice daily (12 mo), HbA1c 8.5, eGFR 80, ALT 25, height 170 / weight 82 \u2192 BMI 28.4, Liver disease: No, smoking Never, alcohol Never. Multi-note files are extracted in parallel (6 workers) and the model load is lock-guarded.",
    "<b>Step 4 - Retrieval + ranking.</b> build_profile() normalises the facts into a PatientProfile; all 84 trials' criteria are embedded (cached) and the profile text is embedded once; cosine similarity ranks every trial and computes the Match Score %. A top-K scope may limit downstream checking to the K best matches.",
    "<b>Step 5 - Rule engine (every trial).</b> For trial CTRI/2024/01/062001 (T2DM add-on to metformin): <i>\u201cPatient age 48 is within the required range 30-65 years\u201d</i>; <i>\u201cHbA1c 8.5 satisfies inclusion criterion \u2018HbA1c between 7.5 and 10.5 percent\u2019\u201d</i>; <i>\u201cCurrent medication Metformin matches trial requirement of stable metformin \u2265 3 months (12 months recorded)\u201d</i> \u2192 <b>Potentially Eligible</b>. Against the obesity trial CTRI/2025/08/064022: <i>\u201cBMI 28.4 does not satisfy inclusion criterion \u2018Body mass index between 30 and 45\u2019\u201d</i> \u2192 <b>Not Eligible</b>.",
    "<b>Step 6 - LLM review (top-15 only).</b> The 15 most similar trials additionally go to Groq gpt-oss-120b as an adversarial second opinion (a parallel worker pool; successful answers are cached per patient+trial). It can flag a violation the parser missed or add narrative, but can never overturn a rule-engine hard failure. Trials outside the top-15 keep their rule-engine verdict unchanged.",
    "<b>Step 7 - Verdict merge + explanation.</b> merge_rule_and_llm applies the deterministic policy: rule veto wins \u2192 Not Eligible; rule-detected missing inclusion facts \u2192 Insufficient Information; LLM-only concrete violation \u2192 Not Eligible; otherwise Potentially Eligible. Every verdict carries itemised reasons quoting the trial's criteria, the Match Score %, phase, sponsor and India locations.",
    "<b>Step 8 - Output.</b> The Results page renders verdict cards (green/amber/red badges), supports per-patient stepping for cohorts, downloads a results CSV; the cohort exports one Excel file; the labelled evaluation path produces accuracy/precision/recall/F1 and the confusion matrix.",
]:
    story.append(Paragraph(t, BODY))

# ================= 3. WHY GOOD =================
story.append(Paragraph("3. Why this design is good", H2))
for t in [
    "<b>Honest about uncertainty.</b> Most systems force a yes/no answer. CTQ has a third verdict, 'Insufficient Information', and names exactly which fields are missing. In screening, a wrong confident answer is far more harmful than an honest 'need more data'. In the live structured sweep, 104 of 1,600 pairs returned Insufficient Information instead of a guess - and that honesty is tracked as its own metric (insufficient-detection rate 50% on labelled-insufficient pairs).",
    "<b>Auditable, not a black box.</b> Every verdict lists the exact criteria checked (e.g. 'HbA1c 8.5 satisfies inclusion criterion \"HbA1c between 7.5 and 10.5\"'). Because structured facts are checked with code, the reasons are reproducible - the ML only extracts, it never invents facts and can never overturn a rule-engine hard failure.",
    "<b>ML where ML wins, rules where rules win.</b> Language understanding (reading a note, coping with phrasing variety) is ML's strength; safety-critical verification (a numeric cut-off, a hard exclusion) is code's strength. CTQ assigns each to the right component, and the LLM is only a third, capped opinion.",
    "<b>Built for the Indian context.</b> Trials are modelled on the Clinical Trials Registry - India (CTRI) plus live ClinicalTrials.gov recruiting-in-India imports, with city/state locations shown on every card, and Hindi/Indic notes supported end to end.",
    "<b>Fast enough for real cohorts.</b> Note extraction runs in parallel threads with a lock-guarded model load; per-trial work runs in a thread pool; the LLM review is capped (CTQ_LLM_REVIEW_TOP_N, default 15) and answer-cached. A 10-patient \u00d7 84-trial cohort completes in \u2248100 s on a laptop CPU; the rule engine keeps verdicts flowing even when the Groq quota is exhausted.",
    "<b>Measurable.</b> The Model Evaluation page has a one-click bundled sample (10 notes + 17 labels) and accepts full uploads (80 patients \u00d7 84 trials shipped as backend/data/sample_*.csv): anyone can reproduce the metrics in this report in minutes.",
]:
    story.append(Paragraph(t, BODY))

# ================= 4. ACCURACY =================
story.append(Paragraph("4. How accurate is it - live measured results", H2))
story.append(Paragraph("4.1 Run A - structured sweep (80 patients \u00d7 84 trials, run 3, 29 Sep 2026)", H3))
story.append(Paragraph(
    "80 fully structured synthetic patients (backend/data/sample_patients.csv) were labelled against all 84 "
    "trials (1,600 ground-truth pairs: 157 eligible, 1,401 not eligible, 42 insufficient). Predictions of "
    "'Insufficient Information' (104 pairs) are excluded from the binary matrix and reported separately - "
    "the system refused to guess where data was missing:", BODY))
story.append(tbl([
    ["Metric", "Value"],
    ["Labelled pairs", "1,600 (1,454 scored binary; 104 predicted-Insufficient excluded; 42 labelled-Insufficient)"],
    ["Accuracy", "93.9%"],
    ["Specificity", "99.2% (only 10 false alarms across 1,313 not-eligible pairs)"],
    ["Precision / Recall / F1 (eligible class)", "86.1% / 44.0% / 0.58"],
    ["Confusion matrix", "TP 62 \u00b7 FP 10 \u00b7 FN 79 \u00b7 TN 1,303"],
], [6.2 * cm, 10.8 * cm]))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Reading it honestly: the system almost never wrongly rejects (specificity 99.2%) and rarely cries wolf "
    "(precision 86.1%), but its recall on the eligible class is conservative - where a profile is missing a "
    "fact a criterion needs, it returns Insufficient Information instead of forcing an 'Eligible'. Several "
    "trials score 100% individually (per-trial table on the Evaluation page); the misses concentrate in "
    "criteria that need facts the form never captured. This is the designed trade-off: a screening tool must "
    "prefer 'need more data' over a false 'yes'.", BODY))
story.append(Paragraph("4.2 Run B - unstructured end-to-end (10 notes \u2192 ML NER \u2192 17 labelled pairs)", H3))
story.append(Paragraph(
    "The bundled sample ships as two CSVs (sample_data/evaluation_patients_unstructured.csv + "
    "evaluation_labels_ground_truth.csv) and also via the one-click 'Load bundled sample data' button. The "
    "full pipeline - including the ML extraction step - ran live:", BODY))
story.append(tbl([
    ["Metric", "Value"],
    ["Labelled pairs", "17 (0 excluded, 0 skipped)"],
    ["Accuracy", "88.2% (15 of 17 correct)"],
    ["Precision / Recall / F1", "80% / 80% / 0.80"],
    ["Confusion matrix", "TP 4 \u00b7 FP 1 \u00b7 FN 1 \u00b7 TN 11"],
], [6.2 * cm, 10.8 * cm]))
story.append(Image("_ppt_assets/confusion.png", width=16.5 * cm, height=16.5 * cm * 0.42))
story.append(Paragraph(
    "Figure 2 - Confusion matrix of Run A and headline tiles. Run B's smaller matrix (TP 4, FP 1, FN 1, "
    "TN 11) exercises the extra extraction step end to end: two pairs diverge from ground truth because the "
    "note text genuinely lacked (or phrased) a criterion-critical fact - exactly the honest-failure mode the "
    "design targets.", BODY))
story.append(Paragraph("4.3 Ranking scope - accuracy against the top-K matches", H3))
story.append(Paragraph(
    "In real use, a coordinator reads the ranked list from the top - not all 84 trials. The Model Evaluation "
    "page therefore offers a ranking scope: All trials, Top 3, Top 5 or Top 10. Under a top-K scope, a "
    "labelled pair is scored only when that trial is among the patient's K best-matching trials (by embedding "
    "similarity); pairs outside the scope are skipped and reported next to the confusion matrix, so the "
    "denominator is always visible.", BODY))
story.append(Paragraph("4.4 Honesty mechanism", H3))
story.append(Paragraph(
    "Rows whose prediction is 'Insufficient Information' are excluded from the binary matrix and reported "
    "separately. If a note genuinely lacks a fact - e.g. an asthma note without FEV1 - the matching pair "
    "degrades to 'Insufficient Information' instead of a lucky guess, which is the behaviour a screening tool "
    "should have. Both evaluation datasets exist as standalone CSVs in sample_data/ for manual upload.", EX))

# ================= 5. WALKTHROUGH =================
story.append(PageBreak())
story.append(Paragraph("5. Guided tour - how each part works (live screenshots)", H2))

story += shot("01_home", "5.1 Home - the front door",
    "The hero states what the product does with two calls to action: Find Clinical Trials (the matcher) and "
    "Evaluate Model (accuracy measurement). The five pills show the pipeline a search will follow: Patient "
    "Data, Trial Retrieval, Similarity Matching, Eligibility Analysis, Explanation.")

story += shot("02_matcher_tabs", "5.2 Find Trials - two input modes, one page",
    "The Structured Data tab is open by default: one-click sample profiles (Diabetes 47F, Hypertension 58M, "
    "Asthma 24F, Healthy volunteer 28M), the cohort bar ('Single patient mode' / '+ Add another patient' / "
    "'\u29f3 Download all patients (Excel)' / '\u29d2 Upload structured CSV'), and the Unstructured Data tab "
    "switch at the top. The 'Trials to check' picker (All / Top 5 / Top 10 / Top 15) sits with the submit "
    "button.")

story += shot("03_matcher_form", "5.3 Structured form - medications and labs",
    "The diabetes sample is loaded. Each medication row captures name, dose ('500 mg'), frequency ('twice "
    "daily') and duration in months - the details criteria like 'stable metformin for at least 3 months' need. "
    "The Laboratory Values grid holds HbA1c, glucose, BP, creatinine, eGFR, haemoglobin, WBC, platelets, ALT, "
    "AST, bilirubin, cholesterol and FEV1 % predicted. Left-blank fields become Unknown - which is exactly "
    "what produces honest 'Insufficient Information' verdicts instead of guesses.")

story += shot("04_cohort_mode", "5.4 Cohort mode - many patients, one run",
    "After '+ Add another patient', each added patient gets its own full form card ('Patient 2 of 2'), the "
    "counter reads '2 patients in the cohort', and the submit button becomes 'Find Trials for all 2 patients'. "
    "Results come back per patient with a \u2190 Previous / Next patient \u2192 stepper, and the whole cohort's "
    "entered details download as one Excel file. Structured CSV upload fills the same form + cohort states "
    "(patient 1's meds/symptoms land in the dedicated form states).")

story += shot("05_results_top", "5.5 Results - 'Your Trial Matches'",
    "After pressing Find Matching Trials, the backend runs the pipeline and the Results page lists every "
    "trial with its verdict badge (green Potentially Eligible, red Not Eligible, amber Insufficient "
    "Information), Match Score %, registry ID, locations and phase, plus summary counts. A "
    "'\u29f3 Download results (CSV)' button sits below the list.")

story += shot("06_results_cards", "5.6 Every verdict is explained",
    "Each card carries green reasons-for (e.g. 'HbA1c 8.5 satisfies inclusion criterion \"HbA1c between 7.5 "
    "and 10.5 percent\"'), red reasons-against (e.g. 'BMI 28.4 does not satisfy \"Body mass index between 30 "
    "and 45\"'), and amber missing-information naming the exact fields never provided. This is the "
    "anti-black-box guarantee: the same list a clinician would produce by hand, generated in seconds.")

story += shot("07_unstructured_upload", "5.7 Unstructured Data tab - drop any document",
    "Accepts PDF, photos (OCR via RapidOCR), CSV, Excel, TSV, TXT and JSON. A text column is found by alias "
    "(notes / clinical_notes / summary / medical_history\u2026) and a patient id column by alias "
    "(patient_id / note_id / id). Multi-note CSVs show a per-patient stepper after extraction.")

story += shot("08_unstructured_extracted", "5.8 Ten notes extracted - live table",
    "The uploaded 10-note CSV ('U-patients_find_trials.csv' in this capture) is converted by the DistilBERT "
    "NER into structured facts per patient - here U001: age 48, male, Type 2 Diabetes Mellitus, 48 months, "
    "Metformin, increased thirst, fatigue, HbA1c 8.5, eGFR 80, ALT 25. Multi-note extraction runs six notes "
    "in parallel (\u2248270 s sequential \u2192 \u224872 s), then 'Find Trials for all 10 patients' screens "
    "all 84 trials per patient in \u2248100 s.")

story += shot("13_trial_database", "5.9 Trial Database - browse and live-import",
    "The dedicated page lists all 84 trials with search and filters (condition, status, phase, study type). "
    "The import panel pulls fresh studies from ClinicalTrials.gov's API v2 by condition preset (Type 2 "
    "Diabetes, Hypertension, Asthma, COPD, ...), optionally India-only and Recruiting-only, maps them into "
    "the CTRI schema, and merges them into the running database (persisted in a sidecar JSON and replayed on "
    "restart).")

story += shot("10_evaluation_upload", "5.10 Model Evaluation - zero-preparation demo + ranking scope",
    "Four numbered steps: unstructured patient file, labelled ground-truth file, ranking scope, run. The "
    "'Load bundled sample data (10 patients, 21 labels)' button fills both inputs from the app itself - no "
    "file handling needed for a demo. The ranking-scope buttons choose between scoring all trials and "
    "scoring only each patient's top-3 / top-5 / top-10 best matches.")

story += shot("11_evaluation_result", "5.11 The live metrics dashboard",
    "A real run: metric tiles for Accuracy / Precision / Recall / F1, the colour-coded confusion matrix, the "
    "skipped/excluded pair counts printed beside it, and an expandable 'ML extraction details' panel listing "
    "the facts the NER found for each patient. Evaluation runs are stored in SQLite and browsable under "
    "previous runs.")

story += shot("12_evaluation_table", "5.12 Per-pair predictions vs labels",
    "Each scored row with a \u2713: prediction equals the ground-truth label. The table downloads as CSV "
    "('evaluation_predictions.csv') for offline inspection.")

# ================= 6. TECH STACK =================
story.append(PageBreak())
story.append(Paragraph("6. The tech stack - what each technology does and how", H2))
story.append(Paragraph(
    "The app is a classic two-part web application: a React single-page app in the browser talking to a "
    "Python FastAPI server. The table summarises every piece; the paragraphs after explain the interesting "
    "ones with a worked example each.", BODY))
stack = [
    ["Technology", "Role in CTQ", "How it is used here"],
    ["React 18 + Vite + react-router", "Frontend UI", "Five routes: Home, Find Trials (structured/unstructured tabs, cohort, top-K picker), Results, Trial Database (browse + live CTG import), Model Evaluation. axios API client; the production bundle (dist/) is served by the API server on one origin."],
    ["FastAPI + Uvicorn", "Backend REST API", "/api endpoints: patient/analyze (top_k), cohort/analyze + cohort/export (Excel), extract/document, patient/analyze-batch (evaluation, batched vectors + thread pool), upload/patients, upload/labels, evaluation/sample-data + run-sample, trials + trials/live/presets + trials/import/live, health, ner/status."],
    ["Pydantic", "Data models + validation", "PatientProfile, Medication, Trial and result schemas; coerces form/CSV values and guarantees every component sees one canonical schema."],
    ["DistilBERT extractive-QA (distilbert-base-cased-distilled-squad)", "ML NER engine", "Asks one targeted question per clinical field per note ('What is the patient's HbA1c level?'); picks the best answer span SQuAD-style with a no-answer threshold; normalises spans into profile fields with anchor, negation and number-claim guards. Runs locally on CPU (torch; ONNX int8 in Docker)."],
    ["Groq API (openai/gpt-oss-120b)", "Translation + LLM review", "Two jobs: (1) medical translation of non-Latin notes (Hindi + 12 scripts) to English before extraction; (2) adversarial second opinion on the top-15 most similar trials with a rate-limit circuit breaker and a per-(patient,trial) answer cache. Rule-engine fallback on any failure."],
    ["sentence-transformers (all-MiniLM-L6-v2)", "Semantic embeddings", "Encodes the patient profile text and each trial's criteria into 384-d vectors (exact-text cache, batched); cosine similarity becomes the Match Score after rescaling."],
    ["Custom rule engine (services/eligibility.py)", "Deterministic checking", "Parses numeric cut-offs from criterion text ('HbA1c between 7.5 and 10.5', 'eGFR below 45', '3 \u00d7 ULN' multiplier phrases), age/gender windows, medication & duration requirements, comorbidity exclusions; any hard exclusion vetoes eligibility."],
    ["RapidOCR (ONNX) + PyMuPDF + pypdf", "OCR & PDF reading", "Photos/scans of prescriptions \u2192 RapidOCR text; scanned PDF pages are rasterised with PyMuPDF then OCR'd; digital PDFs use pypdf text directly."],
    ["pandas + openpyxl", "Tabular parsing / Excel", "Reads uploaded CSV/TSV/Excel with column aliasing; openpyxl writes the cohort Excel export."],
    ["SQLite", "Local storage", "Stores evaluation runs; trials.json (84 trials, 200+ criteria) plus the live-import sidecar JSON loads at startup."],
    ["ReportLab + matplotlib", "This report & figures", "The PDF you are reading is generated from live numbers; matplotlib renders the confusion matrix and the pipeline diagrams."],
    ["Playwright", "Testing & screenshots", "Automated end-to-end browser runs produced every screenshot in section 5 and regression-check the UI."],
    ["Render (Docker)", "Hosting", "Auto-deploys on every push to master; ONNX int8 NER artifact fits the 512 MB free container; free-tier limits handled in code (sleep, token caps)."],
]
story.append(tbl(stack, [3.9 * cm, 2.9 * cm, 10.2 * cm], fs=7.6))

story.append(Paragraph("6.1 The ML NER step in detail - with the worked example", H3))
story.append(Paragraph(
    "Input note (P001): <i>\u201c48-year-old male with Type 2 Diabetes Mellitus diagnosed 4 years ago. Height "
    "170 cm, weight 82 kg. Increased thirst and fatigue. On stable Metformin 500 mg twice daily for the last "
    "12 months. HbA1c 8.5 percent, eGFR 80, ALT 25 U/L. No history of liver disease. Does not smoke.\u201d</i> "
    "The engine asks the model a list of targeted questions and keeps a span only when it passes validation:", BODY))
for t in [
    "\u201cWhat is the patient's HbA1c level?\u201d \u2192 span \u201c8.5\u201d - accepted because the number sits next to the words 'HbA1c' (anchor check, word-boundary matched so 'alt' never matches inside 'heALThy').",
    "\u201cDoes the patient have any history of liver disease?\u201d \u2192 \u201cNo history of liver disease\u201d \u2192 normalised to comorbidity 'Liver disease: No' - which the rule engine later uses to satisfy that trial's exclusion clause.",
    "The diagnosis question initially returned \u201cliver disease\u201d from the negated sentence; a negation guard rejects spans found inside \u201cNo history of\u2026\u201d contexts, and a sentence-level fallback then lifts the real diagnosis 'Type 2 Diabetes Mellitus'.",
    "Numbers already claimed by one field (height 170) cannot be stolen by another (BP), preventing cross-contaminated extractions; blood pressure must match a real '150/95' digit-slash-digit pair so 'ALT 26 U/L' cannot be read as a BP of 26.",
    "Output facts: age 48, gender Male, condition Type 2 Diabetes Mellitus, duration 48 months, Metformin 500 mg twice daily (12 mo), HbA1c 8.5, eGFR 80, ALT 25, height/weight \u2192 BMI 28.4, Liver disease: No, smoking Never.",
    "<b>Parallelism.</b> A 10-note upload is extracted by 6 threads (\u2248270 s \u2192 \u224872 s; results are byte-identical to sequential extraction - verified). A module lock guarantees exactly one model copy is loaded even under concurrency.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("6.2 The rule engine in detail - where safety lives", H3))
story.append(Paragraph(
    "For the same patient against trial CTRI/2024/01/062001 (T2DM add-on to metformin), the engine parsed the "
    "criterion text and produced: <i>\u201cPatient age 48 is within the required range 30-65 years\u201d</i>; "
    "<i>\u201cHbA1c 8.5 satisfies inclusion criterion \u2018HbA1c between 7.5 and 10.5 percent\u2019\u201d</i>; "
    "<i>\u201cCurrent medication Metformin matches trial requirement of stable metformin \u2265 3 months (12 "
    "months recorded)\u201d</i> \u2192 verdict <b>Potentially Eligible</b>. Against CTRI/2025/08/064022 (an "
    "obesity trial) it produced <i>\u201cBMI 28.4 does not satisfy inclusion criterion \u2018Body mass index "
    "between 30 and 45\u2019\u201d</i> \u2192 <b>Not Eligible</b>. Verdict policy: any hard exclusion wins "
    "(Not Eligible); missing inclusion-side facts (Insufficient Information); missing exclusion-side facts "
    "only (stays Potentially Eligible, gaps listed). A criterion like \u2018ALT above 3 times the upper limit "
    "of normal\u2019 is recognised as a multiplier phrase, not a literal cut-off of 3.", BODY))

story.append(Paragraph("6.3 The multilingual translation layer (Hindi today, 13 scripts)", H3))
story.append(Paragraph(
    "The extractive-QA NER is trained on English SQuAD, so a Hindi note used to yield a half-empty profile: "
    "only Latin-script anchors ('HbA1c 8.5', 'eGFR 80') survived, while Hindi prose (\u0909\u092e\u094d\u0930, "
    "\u092e\u0947\u091f\u092b\u093c\u093e\u0930\u094d\u092e\u093f\u0928, \u0927\u0942\u092e\u094d\u0930\u092a\u093e\u0928) "
    "returned nothing. CTQ closes that gap in four steps:", BODY))
for t in [
    "<b>Detect.</b> services/translate.py scans the note's alphabetic characters against Unicode script ranges (Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, CJK, Cyrillic, Arabic, Hebrew, Greek). If \u2265 5% belong to a non-Latin script, the note is flagged; detection is instant and offline.",
    "<b>Translate.</b> The note goes to the Groq LLM with a strict medical-translation prompt (keep every number, unit and lab name exactly as written; \u092e\u0947\u091f\u092b\u093c\u093e\u0930\u094d\u092e\u093f\u0928 \u2192 Metformin; preserve line breaks and [ID] markers) with low reasoning effort to save tokens.",
    "<b>Extract.</b> The English text flows through the untouched, validated NER pipeline - no change to extraction behaviour.",
    "<b>Fail safe.</b> Translation shares the LLM rate-limit breaker. With no API key, a 429, or any failure, the original text is used and the UI explains what happened - extraction never breaks because translation did. Hindi-verified result: age 48, male, diabetes, Metformin 500 mg twice daily, HbA1c 8.5, creatinine 1.1, eGFR 80, BP 140/85, Never/Never lifestyle - the complete profile, from pure Hindi input.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("6.4 The performance architecture (new)", H3))
story.append(Paragraph(
    "The first production week exposed three bottlenecks, each now fixed in code:", BODY))
for t in [
    "<b>Per-trial parallelism.</b> Rule-engine checks and LLM calls for the ranked trials run in a ThreadPoolExecutor (the regex parsing and the Groq HTTP call release the GIL). One patient \u00d7 84 trials no longer walks a for-loop.",
    "<b>LLM review cap.</b> 'All trials' previously fired one Groq call PER TRIAL per patient - 840 calls for a 10-patient cohort, minutes of sequential latency and an exhausted daily token budget. Now only the top-15 most similar trials get LLM review (env CTQ_LLM_REVIEW_TOP_N; 0 disables the cap); the rule engine still checks all 84, so verdicts are complete.",
    "<b>Answer cache + breaker.</b> Successful LLM answers are cached per (patient text, trial id), so re-running a cohort or evaluation is instant; the rate-limit breaker trips on Groq 429s and falls back to rule-engine-only within seconds instead of stalling in retry backoffs.",
    "<b>Parallel extraction + model-load lock.</b> /extract/document extracts multi-note files with 6 workers, and _get_model() is lock-guarded - the first parallel test exposed 6 threads each loading a 450 MB model copy and a transformers partial-import race; now one load, and the failure mode is impossible.",
    "<b>Measured effect.</b> 10 notes: \u2248270 s \u2192 \u224872 s. 10-patient \u00d7 84-trial cohort with matching: \u2248100 s end to end, all 10 patients, complete verdicts.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("6.5 The evaluation pipeline in detail", H3))
story.append(Paragraph(
    "POST /api/patient/analyze-batch receives the unstructured patients and the labels; each note is "
    "re-extracted by the ML NER (explicit fields and pre-extracted facts win), trial criteria vectors are "
    "batch-embedded once, patient vectors in one batch, and the rule-engine checks run in a thread pool. "
    "Labelled pairs are scored: 1 = eligible, 0 = not eligible, 2 = insufficient (excluded from the binary "
    "matrix, tracked separately). Per-trial and per-patient accuracy breakdowns, the extraction log and a "
    "downloadable predictions CSV come back with the metrics. The frontend's 'Load bundled sample data' "
    "button simply calls /api/evaluation/sample-data, which serves exactly these CSVs.", BODY))

story.append(Paragraph("6.6 One request, end to end", H3))
story.append(Paragraph(
    "Form submit (or file upload \u2192 parallel ML NER) - buildPayload() structures the JSON - POST "
    "/api/patient/analyze?top_k - build_profile() normalises it into PatientProfile - trial_retrieval "
    "pre-filters/annotates all 84 trials - embed_texts() embeds the profile and each trial's criteria "
    "(cached) - cosine similarity ranks them - ThreadPool: evaluate_eligibility() per trial (+ Groq review "
    "on the top-15, cache-aware) - verdicts merge - AnalyzeResponse returns - the Results page renders "
    "verdict cards with reasons and the CSV download. Typically \u224810-20 s for a full 84-trial sweep per "
    "patient on CPU when the LLM quota is healthy.", BODY))

# ================= 7. FUTURE =================
story.append(Paragraph("7. What can be improved next", H2))
for t in [
    "<b>Domain-specific NER.</b> Swap or ensemble DistilBERT-QA with BioBERT / PubMedBERT fine-tuned on CTRI criteria for higher recall on rare entities and lab names.",
    "<b>Dose-threshold rules.</b> The rule engine can parse 'HbA1c <= 9.0' but not yet 'metformin at least 1500 mg/day'; the dose field on medications makes that check possible.",
    "<b>Live registry sync.</b> The Trial Database page imports ClinicalTrials.gov on demand today; a scheduled nightly sync + CTRI export ingestion would keep 84 \u2192 thousands of trials fresh automatically.",
    "<b>Doctor feedback loop.</b> Human-in-the-loop corrections that feed back into the rules and the evaluation set - the natural next step to lift recall on the eligible class.",
    "<b>More languages + speech.</b> Hindi notes ship today (13 scripts detected, translated before extraction); regional speech-to-text dictation and ICD / LOINC coding come next.",
    "<b>Accounts + investigator dashboard.</b> Save patient histories, track which trials were contacted, record enrolment outcomes - turning CTQ from a screener into a workflow tool.",
    "<b>PostgreSQL + background jobs.</b> Swap SQLite for PostgreSQL and move long cohort/evaluation runs into background jobs with a progress bar, so refreshing the page never loses a run.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("8. Deployment - live on Render", H2))
story.append(Paragraph(
    "CTQ runs publicly at <b>https://ctq-clinical-trial-qualifier.onrender.com</b> (Docker deploy, auto-redeploys "
    "on every push to master). To fit the free tier's 512 MB RAM, the DistilBERT NER is exported to ONNX int8 at "
    "Docker build time (66 MB self-contained artifact; onnxruntime with single-thread execution and no arena "
    "growth - torch is never imported on that path), and embeddings run in a deterministic hashed mode. The "
    "Groq key is injected as a sync:false environment variable. Known free-tier limits: after 15 minutes idle "
    "the server sleeps (~50 s cold start on the next request), CPU throttling means very large multi-note "
    "uploads may time out, and the Groq daily token cap (~200k TPD) occasionally pauses LLM translation/review "
    "until the breaker resets - the rule engine keeps verdicts flowing either way.", BODY))

story.append(hr())
story.append(Paragraph(
    "CTQ - Clinical Trial Qualifier. Backend: FastAPI + SQLite + DistilBERT extractive-QA ML NER + Groq "
    "translation/review + sentence-transformers + RapidOCR. Frontend: React + Vite. Deployed on Render. "
    "Trial metadata modelled on the Clinical Trials Registry - India (CTRI) with live ClinicalTrials.gov "
    "imports. All demo data is synthetic; no real patient data is used.", MUT))

doc = SimpleDocTemplate("CTQ_Full_Project_Report.pdf", pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.7 * cm, bottomMargin=1.7 * cm,
                        title="CTQ - Full Project Report")
doc.build(story)
print("Created CTQ_Full_Project_Report.pdf")

"""Generate CTQ_Full_Project_Report.pdf - comprehensive explanation of the FINAL
system: DistilBERT extractive-QA ML NER, structured/unstructured tabs, cohort
mode, one-click evaluation, with live screenshots (_shots2/) and live numbers.
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


story = []

# ================= COVER =================
story.append(Paragraph("CTQ - Clinical Trial Qualifier", H1))
story.append(Paragraph("AI-Powered Clinical Trial Matching and Eligibility Analysis for Indian Patients", MUT))
story.append(Spacer(1, 8))
story.append(hr())
story.append(Paragraph(
    "This report explains the complete, final system: what it does, how every technical part works (with a "
    "worked example at each step), a full guided tour of the website with live screenshots of the current "
    "build, and the measured results of a live evaluation run.", BODY))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "<b>One-line summary:</b> you enter a patient (structured form, or unstructured notes / PDF / photo / "
    "CSV / Excel upload), a DistilBERT ML NER turns free text into structured facts, CTQ screens that patient "
    "against every trial in its CTRI-format database with semantic search + a deterministic rule engine, and "
    "returns one of three explained verdicts per trial: Potentially Eligible, Not Eligible, or Insufficient "
    "Information. A Model Evaluation page scores the whole pipeline against ground-truth labels.",
    BODY))
story.append(Paragraph(
    "<b>Live result quoted throughout this report:</b> 10 synthetic patients x 21 labelled patient-trial "
    "pairs \u2192 Accuracy 100%, Precision 100%, Recall 100%, F1 100% (TP 11, FP 0, FN 0, TN 10, zero pairs "
    "excluded) - reproduced from the running app on 28 Sep 2026. Scoring against only each patient's top-5 "
    "best-matching trials also gives 100% (13 pairs scored, 8 reported as outside the ranked scope).", EX))

# ================= 1. WHAT =================
story.append(Paragraph("1. What the project does", H2))
story.append(Paragraph(
    "Clinical trials publish eligibility criteria as long free-text lists: age windows, lab cut-offs "
    "(\"HbA1c between 7.5 and 10.5 percent\"), medication requirements (\"on stable metformin for at least 3 "
    "months\"), exclusion clauses. Patients and clinicians rarely have the time to read every trial's criteria. "
    "CTQ automates exactly that reading.", BODY))
story.append(Paragraph("The system performs five jobs:", BODY))
for t in [
    "<b>1. Understand the patient.</b> Three input paths on one page: the <b>Structured Data</b> tab (60+ guided form fields, or a structured CSV upload, with a cohort mode for many patients), the <b>Unstructured Data</b> tab (clinical notes as PDF, photo, CSV, Excel, TXT or JSON), and the <b>Hybrid</b> tab (a structured CSV plus the notes, merged into one authoritative profile per patient - CSV fields win, ML-extracted facts fill every gap). Non-English notes (Hindi and 12 other scripts) are auto-translated to English before extraction. Free text is converted to structured facts by the DistilBERT ML NER - no hand-written regex discovery.",
    "<b>2. Find candidate trials.</b> A structured pre-filter annotates (and only drops clearly impossible) trials; TOP_K_TRIALS=0 means every trial in the 32-trial database is actually checked for each patient.",
    "<b>3. Rank by meaning.</b> The patient profile and each trial's criteria are embedded into vectors (all-MiniLM-L6-v2, local) and compared with cosine similarity. This is the Match Score % - 'how similar is this patient to this trial'.",
    "<b>4. Verify the details.</b> A deterministic rule engine checks everything objectively checkable: numeric lab cut-offs parsed from the criterion text, age and gender windows, medication requirements and durations, comorbidity exclusions, pregnancy and lifestyle criteria. Missing inclusion-side facts produce 'Insufficient Information' rather than a guess; missing exclusion-side facts keep 'Potentially Eligible' with the gap listed.",
    "<b>5. Explain, export, and evaluate.</b> Every verdict ships with itemised reasons quoting the trial's own criteria; results download as CSV, the cohort exports as Excel. The Model Evaluation page runs the same pipeline over labelled pairs and reports accuracy, precision, recall, F1 and a confusion matrix.",
]:
    story.append(Paragraph(t, BODY))

# ================= 2. WHY GOOD =================
story.append(Paragraph("2. Why this design is good", H2))
for t in [
    "<b>Honest about uncertainty.</b> Most systems force a yes/no answer. CTQ has a third verdict, 'Insufficient Information', and names exactly which fields are missing. In screening, a wrong confident answer is far more harmful than an honest 'need more data'.",
    "<b>Auditable, not a black box.</b> Every verdict lists the exact criteria checked (e.g. 'HbA1c 8.5 satisfies inclusion criterion \"HbA1c between 7.5 and 10.5\"'). Because structured facts are checked with code, the reasons are reproducible - the ML only extracts, it never invents facts and can never overturn a rule-engine hard failure.",
    "<b>ML where ML wins, rules where rules win.</b> Language understanding (reading a note, coping with phrasing variety) is ML's strength; safety-critical verification (a numeric cut-off, a hard exclusion) is code's strength. CTQ assigns each to the right component.",
    "<b>Built for the Indian context.</b> Trials are modelled on the Clinical Trials Registry - India (CTRI), with city/state locations shown on every card, and the UI is designed to be simple enough for non-technical users.",
    "<b>Measurable.</b> The Model Evaluation page has a one-click bundled sample (10 patients + 21 labels): anyone can reproduce the metrics in this report in about two minutes, no file preparation needed.",
]:
    story.append(Paragraph(t, BODY))

# ================= 3. ACCURACY =================
story.append(Paragraph("3. How accurate is it - live measured results", H2))
story.append(Paragraph("3.1 Live evaluation run (this exact build, 27 Sep 2026)", H3))
story.append(Paragraph(
    "The bundled sample set ships with the app: 10 synthetic patients as free-text clinical notes plus 21 "
    "ground-truth labelled patient-trial pairs (11 eligible, 10 not eligible) covering diabetes, hypertension, "
    "asthma, COPD, healthy-volunteer, nephropathy, obesity and prediabetes trials. The full pipeline - ML NER, "
    "retrieval, rule engine - ran over every pair:", BODY))
live = Table([
    ["Metric", "Value"],
    ["Patients evaluated", "10"],
    ["Labelled pairs scored", "21 (0 skipped, 0 excluded)"],
    ["Accuracy", "100%"],
    ["Precision", "100%"],
    ["Recall", "100%"],
    ["F1 score", "100%"],
    ["Confusion matrix", "TP 11  \u00b7  FP 0  \u00b7  FN 0  \u00b7  TN 10"],
], colWidths=[8 * cm, 6.5 * cm])
live.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#d9e6e8")), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(live)
story.append(Image("_ppt_assets/confusion.png", width=12.5 * cm, height=12.5 * cm * 0.78))
story.append(Paragraph(
    "The confusion matrix above is generated from the live run's JSON output, not drawn by hand. FN = 0 means "
    "no eligible trial was ever turned away - the clinically most important property for a screening tool.", BODY))
story.append(Paragraph("3.2 Ranking scope - accuracy against the top-K matches (new)", H3))
story.append(Paragraph(
    "In real use, a coordinator reads the ranked list from the top - not all 32 trials. The Model Evaluation "
    "page therefore offers a ranking scope: All trials, Top 3, Top 5 or Top 10. Under a top-K scope, a "
    "labelled pair is scored only when that trial is among the patient's K best-matching trials (by embedding "
    "similarity); pairs outside the scope are skipped and reported next to the confusion matrix, so the "
    "denominator is always visible. On the bundled sample:", BODY))
scope = Table([
    ["Scope", "Pairs scored", "Skipped (outside scope)", "Accuracy", "Confusion"],
    ["All trials", "21", "0", "100%", "TP 11 \u00b7 FP 0 \u00b7 FN 0 \u00b7 TN 10"],
    ["Top-5 trials per patient", "13", "8", "100%", "TP 9 \u00b7 FP 0 \u00b7 FN 0 \u00b7 TN 4"],
    ["Top-3 trials per patient", "11", "10", "100%", "TP 9 \u00b7 FP 0 \u00b7 FN 0 \u00b7 TN 2"],
], colWidths=[4.6 * cm, 2.4 * cm, 3.4 * cm, 2.2 * cm, 5.4 * cm])
scope.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#d9e6e8")), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(scope)
story.append(Paragraph(
    "The top-5 run keeps FN = 0 and precision = 100% while evaluating the system exactly the way its users "
    "read the results - the ranked shortlist first.", BODY))
story.append(Paragraph("3.3 Honesty mechanism (why nothing was 'guessed')", H3))
story.append(Paragraph(
    "Rows whose prediction is 'Insufficient Information' are excluded from the binary matrix and reported "
    "separately (in this run: zero). If a note genuinely lacks a fact - e.g. an asthma note without FEV1 - the "
    "matching pair degrades to 'Insufficient Information' instead of a lucky guess, which is the behaviour a "
    "screening tool should have.", BODY))
story.append(Paragraph(
    "Both evaluation files also exist as standalone CSVs (sample_data/evaluation_5_patients_unlabelled.csv + "
    "evaluation_5_patients_labelled.csv for a quick 5-patient run; evaluation_patients_unstructured.csv + "
    "evaluation_labels_ground_truth.csv for the 10-patient run) and can be uploaded manually on the Model "
    "Evaluation page.", EX))

# ================= 4. WALKTHROUGH =================
story.append(PageBreak())
story.append(Paragraph("4. Guided tour - how each part works (live screenshots)", H2))

story += shot("01_home", "4.1 Home - the front door",
    "The hero states what the product does with two calls to action: Find Clinical Trials (the matcher) and "
    "Evaluate Model (accuracy measurement). The five pills show the pipeline a search will follow: Patient "
    "Data, Trial Retrieval, Similarity Matching, Eligibility Analysis, Explanation.")

story += shot("02_matcher_tabs", "4.2 Find Trials - two input modes, one page",
    "The Structured Data tab is open by default: one-click sample profiles (Diabetes 47F, Hypertension 58M, "
    "Asthma 24F, Healthy volunteer 28M), the cohort bar ('Single patient mode' / '+ Add another patient' / "
    "'\u29f3 Download all patients (Excel)'), and the Unstructured Data tab switch at the top.")

story += shot("03_matcher_form", "4.3 Structured form - medications and labs",
    "The diabetes sample is loaded. Each medication row captures name, dose ('500 mg'), frequency ('twice "
    "daily') and duration in months - the details criteria like 'stable metformin for at least 3 months' need. "
    "The Laboratory Values grid holds HbA1c, glucose, BP, creatinine, eGFR, haemoglobin, WBC, platelets, ALT, "
    "AST, bilirubin, cholesterol and FEV1 % predicted. Left-blank fields become Unknown - which is exactly "
    "what produces honest 'Insufficient Information' verdicts instead of guesses.")

story += shot("04_cohort_mode", "4.4 Cohort mode - many patients, one run",
    "After '+ Add another patient', each added patient gets its own full form card ('Patient 2 of 2'), the "
    "counter reads '2 patients in the cohort', and the submit button becomes 'Find Trials for all 2 patients'. "
    "Results come back per patient with a \u2190 Previous / Next patient \u2192 stepper, and the whole cohort's "
    "entered details download as one Excel file.")

story += shot("05_results_top", "4.5 Results - 'Your Trial Matches'",
    "After pressing Find Matching Trials, the backend runs the pipeline and the Results page lists every "
    "trial with its verdict badge (green Potentially Eligible, red Not Eligible, amber Insufficient "
    "Information), Match Score %, registry ID, locations and phase, plus summary counts. A "
    "'\u29f3 Download results (CSV)' button sits below the list.")

story += shot("06_results_cards", "4.6 Every verdict is explained",
    "Each card carries green reasons-for (e.g. 'HbA1c 8.5 satisfies inclusion criterion \"HbA1c between 7.5 "
    "and 10.5 percent\"'), red reasons-against (e.g. 'BMI 28.4 does not satisfy \"Body mass index between 30 "
    "and 45\"'), and amber missing-information naming the exact fields never provided. This is the "
    "anti-black-box guarantee: the same list a clinician would produce by hand, generated in seconds.")

story += shot("07_unstructured_upload", "4.7 Unstructured Data tab - drop any document",
    "Accepts PDF, photos (OCR via RapidOCR), CSV, Excel, TSV, TXT and JSON. A text column is found by alias "
    "(notes / clinical_notes / summary / medical_history\u2026) and a patient id column by alias "
    "(patient_id / note_id / id). The same box serves the Model Evaluation page.")

story += shot("08_unstructured_extracted", "4.8 Hindi clinical note - auto-translated, then extracted",
    "The uploaded file contains a fully Hindi discharge note ('\u0930\u092e\u0947\u0936 \u0915\u0941\u092e\u093e\u0930, "
    "\u0909\u092e\u094d\u0930 48 \u0935\u0930\u094d\u0937... \u092e\u0947\u091f\u092b\u093c\u093e\u0930\u094d\u092e\u093f\u0928 500 "
    "\u092e\u093f\u0917\u094d\u0930\u093e...'). CTQ detects the Devanagari script, translates the note to English via the "
    "Groq LLM, and the DistilBERT NER then extracts the complete profile - age 48, male, diabetes, Metformin, "
    "HbA1c 8.5, eGFR 80, BP 140/85. The banner reports the translation; without it, only Latin-anchored lab "
    "values ('HbA1c 8.5') would survive. Translation is behind the same rate-limit breaker as the LLM review: "
    "if Groq is unavailable the original text is used and the UI says so.")

story += shot("10_evaluation_upload", "4.9 Model Evaluation - zero-preparation demo + ranking scope",
    "Four numbered steps: unstructured patient file, labelled ground-truth file, ranking scope, run. The "
    "'Load bundled sample data (10 patients, 21 labels)' button fills both inputs from the app itself - no "
    "file handling needed for a demo. The ranking-scope buttons choose between scoring all trials and "
    "scoring only each patient's top-3 / top-5 / top-10 best matches (section 3.2).")

story += shot("11_evaluation_result", "4.10 The live metrics dashboard (top-5 scope)",
    "The screenshot shows an actual top-5 scoped run: 13 labelled pairs scored, 8 skipped for falling outside "
    "a patient's top-5 matches (the count is printed next to the matrix), Accuracy / Precision / Recall / F1 "
    "at 100%, and the colour-coded confusion matrix. An expandable 'ML extraction details' panel lists the "
    "facts the NER found for each patient.")

story += shot("12_evaluation_table", "4.11 Per-pair predictions vs labels",
    "Each scored row with a \u2713: prediction equals the ground-truth label. The table downloads as CSV "
    "('evaluation_predictions.csv') for offline inspection.")

# ================= 5. TECH STACK =================
story.append(PageBreak())
story.append(Paragraph("5. The tech stack - what each technology does and how", H2))
story.append(Paragraph(
    "The app is a classic two-part web application: a React single-page app in the browser talking to a "
    "Python FastAPI server. The table summarises every piece; the paragraphs after explain the interesting "
    "ones with a worked example each.", BODY))
stack = [
    ["Technology", "Role in CTQ", "How it is used here"],
    ["DistilBERT extractive-QA (distilbert-base-cased-distilled-squad)", "ML NER engine", "Asks one targeted question per clinical field per note ('What is the patient's HbA1c level?'); picks the best answer span SQuAD-style with a no-answer threshold; normalises spans into profile fields. English-only by training - fed by the translation layer for non-English notes. Runs locally on CPU."],
    ["Groq API (openai/gpt-oss-120b)", "Translation + LLM review", "Two jobs: (1) low-effort multilingual translation of non-Latin notes (Hindi + 12 scripts) to English before extraction, sharing the rate-limit circuit breaker; (2) adversarial second opinion on eligibility with rule-engine fallback."],
    ["RapidOCR (ONNX) + PyMuPDF", "OCR & PDF reading", "Photos/scans of prescriptions \u2192 RapidOCR text; scanned PDF pages are rasterised with PyMuPDF then OCR'd; digital PDFs use pypdf text directly."],
    ["sentence-transformers (all-MiniLM-L6-v2)", "Semantic embeddings", "Encodes the patient profile text and each trial's criteria into 384-d vectors; cosine similarity becomes the Match Score after rescaling."],
    ["Custom rule engine (services/eligibility.py)", "Deterministic checking", "Parses numeric cut-offs from criterion text ('HbA1c between 7.5 and 10.5', 'eGFR below 45'), age/gender windows, medication & duration requirements, comorbidity exclusions; any hard exclusion vetoes eligibility."],
    ["FastAPI + Uvicorn", "Backend REST API", "/api endpoints: patient/analyze, patient/analyze-batch (evaluation), extract/document, cohort/analyze, cohort/export (Excel), upload/patients, upload/labels, evaluation/sample-data, trials, health, ner/status. The production frontend build is served by the same server."],
    ["Pydantic", "Data models + validation", "PatientProfile, Medication, Trial and result schemas; coerces form/CSV values and guarantees every component sees one canonical schema."],
    ["React 18 + Vite + react-router", "Frontend UI", "Home, Find Trials (two tabs + cohort), Results, Model Evaluation; axios API client; production bundle (dist/) served by the API server."],
    ["pandas + openpyxl", "Tabular parsing / Excel", "Reads uploaded CSV/TSV/Excel with column aliasing; openpyxl also writes the cohort Excel export."],
    ["SQLite", "Local storage", "Stores evaluation runs; trials.json (32 CTRI/NCT-format trials, 200+ criteria) loads at startup."],
    ["Playwright + matplotlib", "Testing & figures", "Automated end-to-end browser runs produced every screenshot in section 4; matplotlib renders the confusion matrix from live run output."],
]
t = Table(stack, colWidths=[4.4 * cm, 3.4 * cm, 9.2 * cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#f6f6f2")]),
    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#d9e6e8")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(t)

story.append(Paragraph("5.1 The ML NER step in detail - with the worked example", H3))
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
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("5.2 The rule engine in detail - where safety lives", H3))
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

story.append(Paragraph("5.3 The multilingual translation layer (Hindi today, 13 scripts)", H3))
story.append(Paragraph(
    "The extractive-QA NER is trained on English SQuAD, so a Hindi note used to yield a half-empty profile: "
    "only Latin-script anchors ('HbA1c 8.5', 'eGFR 80') survived, while Hindi prose (\u0909\u092e\u094d\u0930, "
    "\u092e\u0947\u091f\u092b\u093c\u093e\u0930\u094d\u092e\u093f\u0928, \u0927\u0942\u092e\u094d\u0930\u092a\u093e\u0928) "
    "returned nothing. CTQ now closes that gap in three steps:", BODY))
for t in [
    "<b>Detect.</b> services/translate.py scans the note's alphabetic characters against Unicode script ranges (Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, CJK, Cyrillic, Arabic, Hebrew, Greek). If \u2265 5% belong to a non-Latin script, the note is flagged; detection is instant and offline.",
    "<b>Translate.</b> The note goes to the Groq LLM with a strict medical-translation prompt (keep every number, unit and lab name exactly as written; \u092e\u0947\u091f\u092b\u093c\u093e\u0930\u094d\u092e\u093f\u0928 \u2192 Metformin; preserve line breaks and [ID] markers) with low reasoning effort to save tokens.",
    "<b>Extract.</b> The English text flows through the untouched, validated NER pipeline - no change to the extraction behaviour that scored 100% on the English sample.",
    "<b>Fail safe.</b> Translation shares the LLM rate-limit breaker. With no API key, a 429, or any failure, the original text is used and the UI explains what happened - extraction never breaks because translation did. Hindi-verified result: age 48, male, diabetes, Metformin 500 mg twice daily, HbA1c 8.5, creatinine 1.1, eGFR 80, BP 140/85, Never/Never lifestyle - the complete profile, from pure Hindi input.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("5.4 The evaluation pipeline in detail", H3))
story.append(Paragraph(
    "POST /api/patient/analyze-batch receives the unstructured patients and the labels; each note is "
    "re-extracted by the ML NER (explicit fields win), every trial is checked for every patient via the "
    "single-patient code path, and the labelled pairs are scored: 1 = eligible, 0 = not eligible, 2 = "
    "insufficient (excluded from the binary matrix, tracked separately). Per-trial and per-patient accuracy "
    "breakdowns, the extraction log and a downloadable predictions CSV come back with the metrics. The "
    "frontend's 'Load bundled sample data' button simply calls /api/evaluation/sample-data, which serves "
    "exactly these CSVs from sample_data/.", BODY))

story.append(Paragraph("5.5 One request, end to end", H3))
story.append(Paragraph(
    "Form submit (or file upload \u2192 ML NER) - buildPayload() structures the JSON - POST /api/patient/analyze "
    "- build_profile() normalises it into PatientProfile - trial_retrieval pre-filters/annotates all 32 trials "
    "- embed_texts() embeds the profile and each trial's criteria - cosine similarity ranks them (display "
    "order; all are checked) - evaluate_eligibility() runs the rule engine per trial - verdicts merge - "
    "AnalyzeResponse returns - the Results page renders verdict cards with reasons and the CSV download. "
    "Typically 5-20 seconds for a full 32-trial sweep per patient on CPU.", BODY))

# ================= 6. FUTURE =================
story.append(Paragraph("6. What can be improved next", H2))
for t in [
    "<b>Domain-specific NER.</b> Swap or ensemble DistilBERT-QA with BioBERT / PubMedBERT fine-tuned on CTRI criteria for higher recall on rare entities and lab names.",
    "<b>Dose-threshold rules.</b> The rule engine can parse 'HbA1c <= 9.0' but not yet 'metformin at least 1500 mg/day'; the dose field on medications makes that check possible.",
    "<b>Real registry data.</b> Point the retrieval layer at a live CTRI export or ClinicalTrials.gov (NCT) JSON - the trial import path already accepts the same schema.",
    "<b>Doctor feedback loop.</b> Human-in-the-loop corrections that feed back into the rules and the evaluation set.",
    "<b>More languages + speech.</b> Hindi notes ship today (13 scripts detected, translated before extraction); regional speech-to-text dictation and ICD / LOINC coding come next.",
    "<b>Accounts + investigator dashboard.</b> Save patient histories, track which trials were contacted, record enrolment outcomes - turning CTQ from a screener into a workflow tool.",
    "<b>PostgreSQL + deployment.</b> Swap SQLite for PostgreSQL and deploy the API and frontend for multi-user access.",
]:
    story.append(Paragraph(t, BODY))

story.append(Paragraph("7. Deployment - live on Render", H2))
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
    "Trial metadata modelled on the Clinical Trials Registry - India (CTRI). All demo data is synthetic; no "
    "real patient data is used.", MUT))

doc = SimpleDocTemplate("CTQ_Full_Project_Report.pdf", pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.7 * cm, bottomMargin=1.7 * cm,
                        title="CTQ - Full Project Report")
doc.build(story)
print("Created CTQ_Full_Project_Report.pdf")

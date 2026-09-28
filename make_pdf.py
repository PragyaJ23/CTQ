"""Generate CTQ_Project_Explained.pdf - a detailed, non-jargon explanation of the
Clinical Trial Qualifier project, including a worked example for every feature.

Run:  .venv/Scripts/python.exe make_pdf.py   (from the project root)
Output: CTQ_Project_Explained.pdf in the project root.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
                                Table, TableStyle)

PRIMARY = HexColor("#0f766e")
DARK = HexColor("#16323f")
MUTED = HexColor("#5b7285")
SOFT = HexColor("#e0f2f1")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=PRIMARY, fontSize=20, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=PRIMARY, fontSize=14, spaceBefore=14, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=DARK, fontSize=11.5, spaceBefore=10, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], textColor=DARK, fontSize=10, leading=14.5)
MUT = ParagraphStyle("Mut", parent=BODY, textColor=MUTED, fontSize=9)
EX = ParagraphStyle("Ex", parent=BODY, textColor=DARK, fontSize=9.5, backColor=SOFT,
                    borderPadding=7, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8)


def hr():
    return HRFlowable(width="100%", thickness=0.7, color=HexColor("#dbe6ee"), spaceBefore=8, spaceAfter=8)


def example(text):
    return Paragraph(f"<b>Example in the demo</b> — {text}", EX)


story = []

# ---------------- Cover ----------------
story.append(Paragraph("CTQ — Clinical Trial Qualifier", H1))
story.append(Paragraph("AI-powered clinical trial matching and eligibility analysis for Indian patients", MUT))
story.append(Spacer(1, 6))
story.append(hr())
story.append(Paragraph(
    "CTQ answers one question: <b>\"Which clinical trials could this patient actually join, and why?\"</b> "
    "You describe a patient (through a form or an uploaded file), and CTQ compares that patient against a "
    "database of Indian clinical trials (CTRI-format). For every trial it returns one of three verdicts — "
    "<b>Potentially Eligible</b>, <b>Not Eligible</b>, or <b>Insufficient Information</b> — together with "
    "itemised reasons, so the answer is never a black box.", BODY))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "This document explains the project in plain language and walks through a live example for every "
    "feature, using the demo data that ships with the app (20 synthetic CTRI trials, 80 sample patients).", BODY))
story.append(Spacer(1, 10))

# ---------------- Architecture ----------------
story.append(Paragraph("1. How CTQ works — the pipeline", H2))
story.append(Paragraph(
    "When you press <b>Find Matching Trials</b>, six steps run in sequence:", BODY))
pipe = [
    ["Step", "What happens"],
    ["1. Profile build", "Form answers (or an uploaded file) are cleaned into one structured patient profile: age, gender, condition, labs, medications, history."],
    ["2. Trial retrieval", "A structured pre-filter drops trials that are obviously impossible: wrong disease domain, or an age/gender outside the trial's stated limits."],
    ["3. Semantic similarity", "The patient profile and every candidate trial's criteria are converted into vectors (MiniLM embeddings) and compared. The result is shown as a Match Score %."],
    ["4. Rule engine", "Everything objective is checked with code: age/gender limits, lab cut-offs parsed from criterion text (e.g. 'HbA1c ≤ 9.0%'), medication requirements ('on stable metformin'), exclusions."],
    ["5. LLM reasoning", "The top trials go to a Groq-hosted LLM that interprets complex criteria. It may only use the data provided; anything unevaluable must be marked Unknown."],
    ["6. Verdict + reasons", "The rule engine and LLM verdicts are merged: any rule-detected hard failure vetoes eligibility; missing required data becomes 'Insufficient Information'."],
]
t = Table(pipe, colWidths=[3.6 * cm, 12.4 * cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#f4f7fa")]),
    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#dbe6ee")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(t)
story.append(example(
    "Patient P001 (47F, Type 2 Diabetes, HbA1c 8.2%, on Metformin 12 months) is checked against all 20 "
    "trials. A Phase-3 paediatric asthma trial is dropped instantly (wrong domain, age limits). A T2DM "
    "trial requiring 'HbA1c ≤ 9.0%' and 'on stable metformin' passes every rule and the LLM finds no "
    "reason against — final verdict: <b>Potentially Eligible</b>."))

story.append(hr())
story.append(Paragraph("2. Feature-by-feature guide (with a demo walkthrough)", H2))

# ---- Feature: Find Trials ----
story.append(Paragraph("2.1 Find Trials — patient form and sample profiles", H3))
story.append(Paragraph(
    "The Find Trials page is a structured patient form: basic information, disease information, symptoms, "
    "medical history, medications, laboratory values and other eligibility details. Only age is mandatory. "
    "Every field left blank is treated as <i>Unknown</i> by the engine — that is what produces honest "
    "'Insufficient Information' verdicts instead of guesses. Four one-click sample profiles (diabetes, "
    "hypertension, asthma, healthy volunteer) fill the form instantly.", BODY))
story.append(example(
    "Open Find Trials → click <b>Sample: Diabetes (47F)</b> → the form fills with P001's details → press "
    "<b>Find Matching Trials</b>. After a few seconds the Results page shows 'Your Trial Matches' with a "
    "count of Potentially Eligible / Not Eligible / Insufficient Information trials, each trial card "
    "carrying its Match Score, verdict badge and itemised reasons."))

# ---- Feature: Verdicts ----
story.append(Paragraph("2.2 The three verdicts and itemised reasons", H3))
story.append(Paragraph(
    "Each trial card lists <b>reasons for</b> (green), <b>reasons against</b> (red) and <b>missing "
    "information</b> (amber). A trial is only 'Potentially Eligible' when no rule failed and the LLM found "
    "no reason against. If any required value was never entered, the verdict is 'Insufficient Information' "
    "and the exact missing fields are named.", BODY))
story.append(example(
    "The same diabetes patient against a trial requiring 'HbA1c ≤ 8.0%': her value is 8.2%, so the rule "
    "engine records 'HbA1c 8.2 exceeds maximum 8.0' as a reason against → verdict <b>Not Eligible</b>, "
    "even though the Match Score is high. Against a trial needing 'creatinine clearance' that she never "
    "entered → <b>Insufficient Information</b> with 'creatinine not provided' listed as missing."))

# ---- Feature: Model Evaluation ----
story.append(Paragraph("2.3 Model Evaluation — measuring accuracy on labelled data", H3))
story.append(Paragraph(
    "Upload two files: unlabelled patients (one row per patient) and ground-truth labels "
    "(patient_id, trial_id, actual_label where 1 = eligible, 0 = not eligible). CTQ runs its full pipeline "
    "on every pair, compares its prediction with the label and reports Accuracy plus a confusion matrix "
    "(TP / FN / FP / TN). The page accepts CSV, Excel (.xlsx), TXT/TSV, JSON and even PDF files, and "
    "maps alternative column names automatically (for example 'sex' → gender, 'primary_condition' → "
    "condition, 'hba1c_percent' → hba1c).", BODY))
story.append(example(
    "Upload sample_patients.csv and sample_ground_truth.csv (80 patients, 1600 labels) → the bundled demo "
    "scores <b>≈ 97% accuracy</b>. If a labels file references trials that are not in the demo database, "
    "CTQ now explains exactly that instead of showing a misleading 0%."))

# ---- Feature: Trial Database ----
story.append(Paragraph("2.4 Trial Database — browse and inspect trials", H3))
story.append(Paragraph(
    "The Trial Database page lists all loaded CTRI-format trials with filters for condition, state, "
    "status, phase, study type, gender and maximum age. Each row opens a detail view with the full "
    "eligibility criteria, locations, sponsor and interventions.", BODY))
story.append(example(
    "Filter condition = 'Type 2 Diabetes' → two trials remain → click one to see 'HbA1c ≤ 9.0%', "
    "'18–70 years', 'on stable metformin ≥ 3 months' and its Mumbai/Delhi sites."))

# ---- Feature: Results explanation ----
story.append(Paragraph("2.5 Results page — the explained answer", H3))
story.append(Paragraph(
    "Results are sorted by Match Score. Each card shows the trial ID and source registry, phase and study "
    "type chips, the verdict badge, and expandable sections for every reason. The 'New search' button "
    "returns to the form with data intact.", BODY))
story.append(example(
    "Top card: 'A Phase 3, randomized study of [drug] in T2DM' — Match Score 87%, badge 'Potentially "
    "Eligible', reasons for: 'Age 47 within 18-70', 'HbA1c 8.2 meets ≤ 9.0', 'on metformin 12 months "
    "meets ≥ 3 months'."))

story.append(hr())
story.append(Paragraph("3. What is under the hood", H2))
for line in [
    "<b>Backend</b> — Python FastAPI. Services: profile builder (normalises any input), trial retrieval, embeddings + cosine similarity, deterministic rule engine, Groq LLM reasoning, evaluation metrics, SQLite storage.",
    "<b>Frontend</b> — React (Vite) single-page app: Home, Find Trials, Results, Model Evaluation, Trial Database.",
    "<b>LLM safety</b> — the LLM sees only the structured profile and the trial's own criteria; it must answer in strict JSON, mark unknowns, and can never overturn a rule-engine hard failure.",
    "<b>Data</b> — 20 synthetic trials modelled on the Clinical Trials Registry - India (CTRI) and 80 synthetic patients with 1600 labelled pairs for evaluation. No real patient data.",
]:
    story.append(Paragraph(line, BODY))
story.append(Spacer(1, 6))
story.append(hr())
story.append(Paragraph(
    "CTQ · Clinical Trial Qualifier — AI-powered trial matching & eligibility analysis. Trial metadata: "
    "Clinical Trials Registry - India (CTRI).", MUT))

doc = SimpleDocTemplate("CTQ_Project_Explained.pdf", pagesize=A4,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title="CTQ - Clinical Trial Qualifier: Project Explained")
doc.build(story)
print("Created CTQ_Project_Explained.pdf")

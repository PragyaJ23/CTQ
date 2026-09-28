#!/usr/bin/env python
# Builds CTQ_Presentation.pptx - SAME FORMAT as the earlier progress deck
# (AI IN HEALTHCARE PBL): title, contents, introduction, 6-paper literature
# survey tables, problem definition, solution strategy, tools (2),
# methodology (2), output (2, LIVE screenshots), results (live metrics),
# future scope, references, thank-you.  Updated for the final system:
# DistilBERT extractive-QA ML NER, structured/unstructured tabs, cohort mode,
# one-click evaluation with 100% on the bundled sample run.
# Run: .venv/Scripts/python.exe make_ppt.py
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------------- palette / fonts ----------------
TEAL  = RGBColor(0x38, 0x80, 0x87)
DARK  = RGBColor(0x2E, 0x6A, 0x70)
INK   = RGBColor(0x17, 0x32, 0x3A)
GRAY  = RGBColor(0x5E, 0x6D, 0x70)
SOFT  = RGBColor(0xD7, 0xEC, 0xEF)
SOFT2 = RGBColor(0xBA, 0xDF, 0xE7)
SOFT3 = RGBColor(0xC2, 0xED, 0xCE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xB8, 0x86, 0x0B)
RED   = RGBColor(0xA3, 0x3A, 0x3A)
FONT  = "Calibri"

prs = Presentation()
prs.slide_width  = Inches(13.333)   # 16:9
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

def new_slide():
    return prs.slides.add_slide(BLANK)

def tx(s, x, y, w, h):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    return tf

def para(tf, runs, size=15, color=INK, bold=False, first=False, after=6,
         align=PP_ALIGN.LEFT, line=1.08):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    p.line_spacing = line
    if isinstance(runs, str):
        runs = [(runs, bold, color)]
    for txt, b, c in runs:
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(size); r.font.bold = b
        r.font.color.rgb = c;   r.font.name = FONT
    return p

def bullet(tf, text, size=15, color=INK, first=False, after=8, mark="\u25aa"):
    if isinstance(text, tuple):
        lead, rest = text
        runs = [(f"{mark}  ", True, TEAL), (lead, True, DARK), (rest, False, color)]
    else:
        runs = [(f"{mark}  ", True, TEAL), (text, False, color)]
    return para(tf, runs, size=size, first=first, after=after)

def header_footer(s, page=None):
    tf = tx(s, 0.55, 0.18, 9.0, 0.55)
    para(tf, "Department of AI&DS", size=10, color=GRAY, first=True, after=0)
    para(tf, "Sikkim Manipal Institute of Technology,  SMU", size=10, color=GRAY, after=0)
    if page is not None:
        tf = tx(s, 12.55, 0.18, 0.6, 0.4)
        para(tf, str(page), size=12, color=GRAY, first=True, after=0, align=PP_ALIGN.RIGHT)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(7.34), Inches(13.333), Inches(0.16))
    band.fill.solid(); band.fill.fore_color.rgb = TEAL; band.line.fill.background()
    band.shadow.inherit = False

def slide_title(s, text, y=0.95):
    tf = tx(s, 0.55, y, 12.2, 0.8)
    para(tf, text, size=30, color=DARK, bold=True, first=True, after=0)
    bar = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(y+0.72), Inches(1.5), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = TEAL; bar.line.fill.background()
    bar.shadow.inherit = False

def card(s, x, y, w, h, fill, line, title=None, title_color=DARK):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    sh.line.color.rgb = line; sh.line.width = Pt(1.25); sh.shadow.inherit = False
    sh.text_frame.word_wrap = True
    if title:
        tf = sh.text_frame
        tf.margin_left = Inches(0.16); tf.margin_right = Inches(0.16)
        tf.margin_top = Inches(0.10);  tf.margin_bottom = Inches(0.08)
        para(tf, title, size=14, color=title_color, bold=True, first=True, after=4)
    return sh

def notes(s, text):
    s.notes_slide.notes_text_frame.text = text

def lit_table(s, paper):
    headers = ["SL. No.", "Author Name, Journal Name, Vol., Page, Year", "Title of paper",
               "Inference", "Research Gap", "Relevance with the present work / Motivation"]
    widths  = [0.55, 2.55, 2.25, 2.85, 1.95, 2.15]
    rows = [headers, paper]
    gtbl = s.shapes.add_table(2, 6, Inches(0.55), Inches(1.85), Inches(12.3), Inches(4.9))
    tbl = gtbl.table
    tbl.first_row = True
    for c, w in enumerate(widths):
        tbl.columns[c].width = Inches(w)
    tbl.rows[0].height = Inches(0.45)
    tbl.rows[1].height = Inches(4.4)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = TEAL if ri == 0 else WHITE
            cell.margin_left = Inches(0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.05);  cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.TOP
            tf = cell.text_frame; tf.word_wrap = True
            for k, line_txt in enumerate(str(val).split("\n")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                p.line_spacing = 1.02
                r = p.add_run(); r.text = line_txt
                r.font.size = Pt(12 if ri == 0 else 11)
                r.font.bold = (ri == 0) or (ci == 0)
                r.font.color.rgb = WHITE if ri == 0 else INK
                r.font.name = FONT

TEAM = ("Yogesh Chauhan (202400474)  \u00b7  Gaurav Gurung (202400007)  \u00b7  "
        "Pragya Jain (202400385)  \u00b7  Aditya Srivastava (202400102)")

# ================= SLIDE 1 · TITLE =================
s = new_slide()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.22))
band.fill.solid(); band.fill.fore_color.rgb = TEAL; band.line.fill.background(); band.shadow.inherit = False
tf = tx(s, 0.8, 1.15, 11.7, 0.5)
para(tf, "Project Presentation on the topic", size=17, color=GRAY, first=True, align=PP_ALIGN.CENTER)
tf = tx(s, 0.8, 1.85, 11.7, 1.7)
para(tf, "AI-Powered Clinical Trial Qualification System", size=37, color=DARK, bold=True,
     first=True, align=PP_ALIGN.CENTER)
para(tf, "(CTQ \u2014 Clinical Trial Qualifier)", size=19, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
tf = tx(s, 0.8, 3.75, 11.7, 0.5)
para(tf, TEAM, size=14, color=INK, bold=True, first=True, align=PP_ALIGN.CENTER)
tf = tx(s, 0.8, 4.55, 11.7, 0.9)
para(tf, "Department of AI&DS", size=13, color=GRAY, first=True, align=PP_ALIGN.CENTER)
para(tf, "Sikkim Manipal Institute of Technology,  SMU", size=13, color=GRAY, align=PP_ALIGN.CENTER)
tf = tx(s, 0.8, 5.6, 11.7, 0.4)
para(tf, "Under the supervision of:  Dr. Saharul Alom Barlaskar", size=13.5, color=INK,
     bold=True, first=True, align=PP_ALIGN.CENTER)
notes(s, "One line: CTQ takes a patient profile - a guided form, uploaded notes, a photo or a PDF - and returns, for every trial in the database, a clear verdict with itemised reasons.")

# ================= SLIDE 2 · CONTENTS =================
s = new_slide(); header_footer(s, None)
slide_title(s, "CONTENTS")
contents = [
    ("1.", "Introduction", "1"),
    ("2.", "Literature Survey", "2 - 7"),
    ("3.", "Problem Definition", "8"),
    ("4.", "Possible Solution Strategy", "9"),
    ("5.", "Tools & Technologies Used", "10 - 11"),
    ("6.", "Methodology & Workflow", "12 - 13"),
    ("7.", "Output (live demos)", "14 - 15"),
    ("8.", "Results", "16"),
    ("9.", "Future Scope", "17"),
    ("10.", "References", "18"),
]
gtbl = s.shapes.add_table(len(contents), 3, Inches(3.4), Inches(2.0), Inches(6.5), Inches(4.6))
tbl = gtbl.table
tbl.columns[0].width = Inches(0.9); tbl.columns[1].width = Inches(4.4); tbl.columns[2].width = Inches(1.2)
for ri, (a, b, c) in enumerate(contents):
    tbl.rows[ri].height = Inches(0.44)
    for ci, val in enumerate((a, b, c)):
        cell = tbl.cell(ri, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = SOFT if ri % 2 == 0 else WHITE
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Inches(0.08)
        tf = cell.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if ci != 1 else PP_ALIGN.LEFT
        r = p.add_run(); r.text = val
        r.font.size = Pt(14); r.font.bold = (ci == 0)
        r.font.color.rgb = INK; r.font.name = FONT
notes(s, "Structure mirrors the progress presentation; all screenshots in Output are live captures of the finished system.")

# ================= SLIDE 3 · INTRODUCTION =================
s = new_slide(); header_footer(s, 1)
slide_title(s, "Introduction")
tf = tx(s, 0.75, 2.0, 7.6, 4.6)
bullet(tf, ("Clinical trials are essential ", "for developing and validating new medical treatments - yet finding eligible patients remains slow, manual and error-prone."), first=True, size=15)
bullet(tf, ("Screening is manual: ", "coordinators read every patient record against long, free-text eligibility criteria - for every trial, every time."), size=15)
bullet(tf, ("Patients search blindly: ", "most never learn which trials they could join, and trial sites are concentrated in a few big cities."), size=15)
bullet(tf, ("Our solution - CTQ: ", "an AI-powered web application that reads a patient's profile (guided form OR uploaded unstructured notes/PDF/photo), screens it against a CTRI-format trial database, and returns a clear verdict with itemised reasons."), size=15)
bullet(tf, ("India-first: ", "CTRI-format trials, Indian states/cities, and locally common conditions (T2DM, hypertension, anaemia in pregnancy, asthma\u2026)."), size=15, after=10)
tf = tx(s, 0.75, 6.45, 11.9, 0.5)
para(tf, "Goal: turn hours of manual eligibility reading into seconds - without losing transparency or safety.",
     size=14, color=DARK, bold=True, first=True)
c = card(s, 8.6, 2.0, 4.2, 4.25, SOFT, TEAL, title="What the user sees")
tf = c.text_frame
for t in ["1.  Structured · Unstructured · Hybrid tabs",
          "2.  Upload notes - PDF / CSV / Excel / photo",
          "3.  ML NER reads the facts; Hindi notes auto-translate",
          "4.  Find Trials for one patient or all N patients",
          "5.  Verdict cards with reasons + CSV/Excel export",
          "6.  Model Evaluation page scores the system"]:
    bullet(tf, t, size=12, first=t.startswith("1."), mark="\u2022", after=7)
notes(s, "Frame it as a two-sided discovery problem: sites can't find patients, patients can't find trials. CTQ attacks the screening step end to end.")

# ================= SLIDES 4-9 · LITERATURE SURVEY =================
papers = [
    ("1",
     "AUTHORS:- Long Chen, Yu Gu, Xin Ji, Chao Lou, Zhiyong Sun, Haodan Li, Yuan Gao, Yang Huang\n\nJOURNAL:- Journal of the American Medical Informatics Association\n\nYEAR:- 2019",
     "Clinical Trial Cohort Selection based on Multi-Level Rule-Based Natural Language Processing System.",
     "\u2022 Hybrid system:\n\u2022 Rule-based: lexical (keywords), syntactic (structure), meta (context: patient vs family history)\n\u2022 General cNLP: UMLS + pre-trained NER (LSTM-CRF)\n\u2022 Rule-based ensures precision; cNLP improves robustness and coverage",
     "\u2022 Language mismatch between task-specific clinical terms and standardized UMLS terms\n\u2022 Automating trial processing; extracting useful information from EHRs is hard",
     "\u2022 Directly motivates our design: deterministic rules for precision\n\u2022 CTQ uses sentence embeddings instead of UMLS to close the vocabulary gap\n\u2022 ML NER + rule engine hybrid, exactly as they recommend"),
    ("2",
     "AUTHOR:- Chun Yuan, Patrick B. Ryan, et al.\n\nJOURNAL:- Journal of the American Medical Informatics Association, Vol. 26(4), pp. 294-305\n\nYEAR:- 2019",
     "Criteria2Query: a natural language interface to clinical databases for cohort definition.",
     "\u2022 Translates free-text eligibility criteria into executable OMOP-CDM cohort queries\n\u2022 Human-computer collaboration: NLP drafts, humans refine\n\u2022 Shows free-text criteria can be parsed into structured logic",
     "\u2022 Generates cohort queries, not patient-level eligibility verdicts\n\u2022 Requires structured OMOP data warehouses, rarely available for Indian patient records",
     "\u2022 Motivates our rule engine that parses criteria (age bands, lab cut-offs, medications) directly and applies them to a patient profile"),
    ("3",
     "AUTHORS:- Yizhao Ni, Stephanie Kennebeck, Judith W. Dexheimer, Constance M. McAneney, Huaxiu Tang, Todd Lingren, Qi Li, Haijun Zhai, Imre Solti\n\nJOURNAL:- Journal of the American Medical Informatics Association\n\nYEAR:- 2014",
     "Automated clinical trial eligibility prescreening: increasing the efficiency of patient identification for clinical trials in the emergency department.",
     "\u2022 Logical constraint filters on structured data (age, gender) alone reduced workload by 49%\n\u2022 Adding NLP reduced it by 86%\n\u2022 Screening systems become more valuable as they accumulate knowledge",
     "\u2022 Never tested in a live, real-time clinical environment\n\u2022 Paediatric-only trials (misses adult trials)\n\u2022 Limited EHR fields",
     "\u2022 Patient-centric matching with transparent justifications (their stated motivation)\n\u2022 CTQ deploys as a live web app for adult profiles"),
    ("4",
     "AUTHOR:- Victor M. Murcia, Vinod Aggarwal, et al.\n\nJOURNAL:- Journal of Biomedical Informatics\n\nYEAR:- 2023",
     "Automating Clinical Trial Matches via Natural Language Processing of Synthetic Electronic Health Records and Clinical Trial Eligibility Criteria.",
     "\u2022 TrialMatcher's SDI scores achieved up to 80% match for certain trials\n\u2022 Stack: ClinicalTrials.gov API, spaCy/CoreNLP, biomedical NER, S\u00f8rensen-Dice similarity, Python",
     "\u2022 Errors with negation\n\u2022 Errors extracting numerical quantities\n\u2022 Synthetic dataset only",
     "\u2022 Patient-centric matching; practical NLP in healthcare\n\u2022 CTQ's rule engine parses numeric lab cut-offs (HbA1c, eGFR\u2026) and is negation-aware"),
    ("5",
     "AUTHORS:- Kunyuan Wang, Hao Cui, Yun Zhu, et al.\n\nJOURNAL:- BMC Cancer, Vol. 24\n\nYEAR:- 2024",
     "Evaluation of an Artificial Intelligence-Based Clinical Trial Matching System in Chinese Patients with Hepatocellular Carcinoma.",
     "\u2022 AI system (CTMS) checks patient records and finds who qualifies for specific cancer trials\n\u2022 Achieved 92-98% accuracy\n\u2022 Reduced manual screening time from 150 hours to just 2 hours",
     "\u2022 Still took 2 hours whereas other systems finish in <10 minutes\n\u2022 Divergence between how the AI interpreted data and how human reviewers did",
     "\u2022 Patient-centric matching; reduces manual workload; demonstrates AI in healthcare\n\u2022 CTQ outputs seconds per patient with itemised, auditable reasons"),
    ("6",
     "AUTHORS:- Qiao Jin, Zifeng Wang, Charalampos S. Floudas, Jimeng Sun, Zhiyong Lu\n\nJOURNAL:- Nature Communications, Vol. 15, Art. 9074\n\nYEAR:- 2024",
     "Matching patients to clinical trials with large language models (TrialGPT).",
     "\u2022 Zero-shot LLM framework for patient-to-trial matching\n\u2022 TrialGPT-Retrieval recalls >90% of relevant trials using <6% of candidates\n\u2022 Expert-validated; predicted to cut screening time by ~42%",
     "\u2022 LLM-only decisions risk hallucinated eligibility\n\u2022 Large token/context needs; no deterministic guarantees on safety-critical criteria",
     "\u2022 Motivates CTQ's design rule: the deterministic rule engine keeps veto power over any AI component, so no hallucinated eligibility"),
]
for idx, p in enumerate(papers):
    s = new_slide(); header_footer(s, 2 + idx)
    slide_title(s, f"Literature Survey  ({idx+1}/6)")
    lit_table(s, p)
    notes(s, "Survey table for paper %d of 6 - same format as the progress presentation." % (idx+1))

# ================= SLIDE 10 · PROBLEM DEFINITION =================
s = new_slide(); header_footer(s, 8)
slide_title(s, "PROBLEM DEFINITION")
tf = tx(s, 0.75, 2.0, 11.9, 0.9)
para(tf, "Clinical trial patient recruitment is painfully slow and inefficient. Matching a patient to a trial relies on a human reading every eligibility criterion of every trial. This manual approach:",
     size=15.5, color=INK, first=True, after=10)
tf = tx(s, 0.75, 2.95, 7.7, 3.6)
bullet(tf, ("Takes too long - ", "screening one patient against one trial means reading dozens of free-text criteria; full cohorts take weeks, delaying entire trials."), first=True, size=15)
bullet(tf, ("Costs heavily - ", "recruitment consumes a large share of trial timelines and administrative labour."), size=15)
bullet(tf, ("Is inconsistent and error-prone - ", "humans miss details; criteria buried in unstructured notes are easy to overlook."), size=15)
bullet(tf, ("Faces unstructured data - ", "Indian patient records are largely free-text notes, printed prescriptions and scans, not machine-readable fields."), size=15, after=8)
c = card(s, 8.75, 2.6, 4.0, 3.6, SOFT, TEAL, title="Research question")
tf = c.text_frame
para(tf, "Can an AI system screen a patient against many trials in seconds - with decisions that are safe, explained, and honest about missing data?",
     size=14, color=INK, first=True, after=8)
para(tf, "Success = every verdict traceable to a specific criterion, not a black-box score.", size=12.5, color=DARK, bold=True)
notes(s, "Safety angle: a wrong 'eligible' wastes a site visit; a wrong 'not eligible' denies a patient a therapy. That's why CTQ has an Insufficient Information verdict instead of guessing.")

# ================= SLIDE 11 · POSSIBLE SOLUTION STRATEGY =================
s = new_slide(); header_footer(s, 9)
slide_title(s, "POSSIBLE SOLUTION STRATEGY")
tf = tx(s, 0.75, 1.95, 11.9, 0.7)
para(tf, [("Clinical Trial Qualifier (CTQ) \u2014 ", True, DARK),
          ("an AI-powered clinical trial qualification system that automates patient eligibility screening, with a localized focus on Indian healthcare.", False, INK)],
     size=15, first=True, after=10)
jobs = [
    ("Understand the patient", "Structured form (60+ fields), structured CSV, unstructured notes (PDF / photo-OCR / CSV / Excel) or BOTH merged (Hybrid tab); Hindi notes auto-translate to English first; DistilBERT ML NER extracts the facts"),
    ("Find relevant trials", "Semantic search over 32 CTRI/NCT-format trials using sentence embeddings (all-MiniLM-L6-v2)"),
    ("Apply every rule", "Deterministic rule engine checks age, gender, lab cut-offs, medications, comorbidities - criterion by criterion"),
    ("Explain the decision", "Itemised pass / fail / missing reasons quoting the trial's own criteria; three honest verdicts"),
    ("Measure itself", "One-click Model Evaluation: bundled sample patients + labels \u2192 accuracy, precision, recall, F1, confusion matrix - against ALL trials or only each patient's top-K best matches"),
]
y = 2.75
for i, (t, b) in enumerate(jobs):
    x = 0.75 + (i % 2) * 6.15
    yy = y + (i // 2) * 1.22
    c = card(s, x, yy, 5.95, 1.06, WHITE if i % 2 == 0 else SOFT2, TEAL)
    tf = c.text_frame
    tf.margin_left = Inches(0.15); tf.margin_top = Inches(0.07)
    para(tf, [(f"{i+1}  ", True, TEAL), (t, True, DARK)], size=13.5, first=True, after=1)
    para(tf, b, size=10.5, color=INK, after=0)
c = card(s, 6.9, y + 2 * 1.22, 5.95, 1.06, SOFT3, TEAL)
tf = c.text_frame; tf.margin_left = Inches(0.15); tf.margin_top = Inches(0.09)
para(tf, [("Verdicts:  ", True, DARK), ("Potentially Eligible", True, TEAL), ("  \u00b7  ", False, GRAY),
          ("Not Eligible", True, RED), ("  \u00b7  ", False, GRAY), ("Insufficient Information", True, AMBER)],
     size=12.5, first=True, after=0)
para(tf, "ML extracts \u00b7 rules decide \u00b7 missing data is surfaced, never guessed.", size=11, color=GRAY, after=0)
notes(s, "The five jobs map one-to-one onto the architecture: profile builder (ML NER), retrieval, rule engine, explanation, evaluation.")

# ================= SLIDE 12 · TOOLS 1/2 =================
s = new_slide(); header_footer(s, 10)
slide_title(s, "TOOLS & TECHNOLOGIES USED  (1/2)")
tf = tx(s, 0.75, 2.0, 11.9, 4.9)
bullet(tf, ("DistilBERT extractive-QA (distilbert-base-cased-distilled-squad) - ", "the ML NER engine: asks the model targeted clinical questions per note (\u201cWhat is the patient's HbA1c level?\u201d), then maps span answers into profile fields. ML-only extraction - no regex discovery; negation guards reject spans like \u201cNo history of liver disease\u201d as a diagnosis. Non-English notes (Hindi + 12 more scripts) are auto-translated to English first."), first=True, size=14.5)
bullet(tf, ("Groq LLM (openai/gpt-oss-120b) - ", "two jobs: a low-effort multilingual translator (Hindi/Indic notes \u2192 English before extraction) and an adversarial second opinion on eligibility - behind a rate-limit circuit breaker with rule-engine fallback."), size=14.5)
bullet(tf, ("RapidOCR (ONNX) - ", "reads photos/scans of prescriptions and summaries; PyMuPDF rasterises scanned PDF pages so the same OCR can read them."), size=14.5)
bullet(tf, ("Custom Rule Engine - ", "parses every eligibility criterion (age bands, gender, lab cut-offs such as HbA1c 7.5-10.5 / eGFR \u2265 45, medication requirements, comorbidity exclusions, pregnancy, smoking) and issues Pass / Fail / Missing per criterion; any hard exclusion vetoes the match; missing INCLUSION-side facts produce \u201cInsufficient Information\u201d, missing EXCLUSION-side facts stay \u201cPotentially Eligible\u201d with gaps listed."), size=14.5)
bullet(tf, ("sentence-transformers (all-MiniLM-L6-v2) - ", "encodes the patient profile and every trial's criteria into 384-dimension vectors locally; cosine similarity ranks all 32 trials (semantic matching, no internet or GPU needed)."), size=14.5)
bullet(tf, ("Pandas, openpyxl, pypdf - ", "parse uploaded CSV / Excel / PDF notes with column aliasing (notes / clinical_notes / summary\u2026); build the Excel cohort export and CSV result downloads."), size=14.5, after=4)
notes(s, "Keep it to one sentence per tool; the next slide covers the web stack and persistence.")

# ================= SLIDE 13 · TOOLS 2/2 =================
s = new_slide(); header_footer(s, 11)
slide_title(s, "TOOLS & TECHNOLOGIES USED  (2/2)")
tf = tx(s, 0.75, 2.0, 11.9, 4.9)
bullet(tf, ("React 18 + Vite - ", "single-page frontend: Home, Find Trials (Structured / Unstructured / Hybrid tabs, cohort mode), Model Evaluation (with top-K ranking scope); client-side routing with react-router; production build served by the API server."), first=True, size=14.5)
bullet(tf, ("axios - ", "API client with friendly error mapping; builds the structured profile payload from the form and downloads CSV/Excel blobs."), size=14.5)
bullet(tf, ("FastAPI + Uvicorn - ", "REST API: /patient/analyze, /patient/analyze-batch (evaluation), /extract/document, /cohort/analyze, /cohort/export, /evaluation/sample-data; one origin serves app + API (no CORS issues)."), size=14.5)
bullet(tf, ("Pydantic - ", "request/response validation and schemas; rejects impossible values before any AI runs (age \u2264 0, impossible lab values)."), size=14.5)
bullet(tf, ("SQLite - ", "stores evaluation runs; trials.json (32 CTRI/NCT-format trials, 200+ criteria) is loaded at startup; TOP_K_TRIALS=0 checks every trial."), size=14.5)
bullet(tf, ("Playwright + matplotlib - ", "automated end-to-end UI runs that produced the live screenshots in this deck; matplotlib draws the confusion matrix."), size=14.5, after=4)
notes(s, "Stack summary: real client-server web app - validated API, persistence, production build - not a notebook.")

# ================= SLIDE 14 · METHODOLOGY / WORKFLOW =================
s = new_slide(); header_footer(s, 12)
slide_title(s, "METHODOLOGY & WORKFLOW  \u2014  How everything works")
s.shapes.add_picture("_ppt_assets/flowchart.png", Inches(1.95), Inches(1.95), width=Inches(9.45))
tf = tx(s, 0.75, 6.75, 11.9, 0.45)
para(tf, "Patient input (form / notes / PDF / photo) \u2192 DistilBERT ML NER \u2192 semantic retrieval \u2192 rule engine (veto) \u2192 verdict + explanation \u2192 downloads / evaluation",
     size=12, color=GRAY, first=True, align=PP_ALIGN.CENTER)
notes(s, "Master slide for 'how everything is working'. Follow one patient left to right; the same pipeline feeds the evaluation module.")

# ================= SLIDE 15 · METHODOLOGY · STAGES =================
s = new_slide(); header_footer(s, 13)
slide_title(s, "METHODOLOGY  \u2014  Pipeline stages with a worked example")
c = card(s, 0.75, 2.0, 5.95, 2.3, WHITE, TEAL, title="Stage 1-2 \u00b7 Input & DistilBERT ML NER")
tf = c.text_frame
bullet(tf, "\u201c48-year-old male with Type 2 Diabetes Mellitus diagnosed 4 years ago\u2026 HbA1c 8.5 percent, eGFR 80, ALT 25 U/L. No history of liver disease.\u201d", first=True, size=10.5, mark="\u2022", after=4)
bullet(tf, "A Hindi note (\u201c\u0909\u092e\u094d\u0930 48 \u0935\u0930\u094d\u0937\u2026 \u092e\u0947\u091f\u092b\u093c\u0949\u0930\u094d\u092e\u093f\u0928 500 \u092e\u093f\u0917\u094d\u0930\u093e\u2026\u201d) is auto-translated to English first \u2192 the same facts come out (age 48, Metformin, HbA1c 8.5\u2026).", size=10.5, mark="\u2022", after=4)
bullet(tf, "The QA model answers one question per field \u2192 age 48, condition T2DM, duration 48 mo, HbA1c 8.5, eGFR 80, ALT 25; \u201cNo history of\u2026\u201d is negation-guarded.", size=10.5, mark="\u2022", after=0)
c = card(s, 6.9, 2.0, 5.95, 2.3, SOFT2, TEAL, title="Stage 3 \u00b7 Semantic Retrieval")
tf = c.text_frame
bullet(tf, "all-MiniLM-L6-v2 embeds profile and all 32 trials; cosine similarity ranks them (top match 87% for the T2DM add-on trial).", first=True, size=10.5, mark="\u2022", after=4)
bullet(tf, "TOP_K_TRIALS=0: every trial is checked - ranking only sets the display order.", size=10.5, mark="\u2022", after=0)
c = card(s, 0.75, 4.45, 5.95, 2.3, SOFT3, TEAL, title="Stage 4 \u00b7 Deterministic Rule Engine")
tf = c.text_frame
bullet(tf, "Example verdicts: \u201cHbA1c 8.5 satisfies \u2018HbA1c between 7.5 and 10.5\u2019\u201d; \u201cBMI 28.4 does not satisfy \u2018BMI between 30 and 45\u2019\u201d.", first=True, size=10.5, mark="\u2022", after=4)
bullet(tf, "Hard exclusion \u2192 Not Eligible; missing inclusion fact \u2192 Insufficient Information; missing exclusion-side fact \u2192 stays Potentially Eligible.", size=10.5, mark="\u2022", after=0)
c = card(s, 6.9, 4.45, 5.95, 2.3, WHITE, DARK, title="Stage 5 \u00b7 Verdict, Explanation & Outputs")
tf = c.text_frame
bullet(tf, "Verdict cards quote the trial's own criteria; CSV result download, Excel cohort export, PDF report.", first=True, size=10.5, mark="\u2022", after=4)
bullet(tf, "Model Evaluation runs the same pipeline over labelled pairs and scores itself (next slide).", size=10.5, mark="\u2022", after=0)
notes(s, "The worked example is the live P001 demo: same facts appear in the screenshots that follow.")

# ================= SLIDE 16 · OUTPUT 1/2 =================
s = new_slide(); header_footer(s, 14)
slide_title(s, "OUTPUT  (1/2)  \u2014  Live demo: matching & cohort")
s.shapes.add_picture("_shots2/02_matcher_tabs.png", Inches(0.6), Inches(1.85), width=Inches(6.35))
tf = tx(s, 0.6, 4.62, 6.35, 0.4)
para(tf, "Fig:  Find Trials - Structured / Unstructured / Hybrid tabs, cohort controls, one-click samples",
     size=11, color=GRAY, first=True, align=PP_ALIGN.CENTER)
s.shapes.add_picture("_shots2/05_results_top.png", Inches(6.55), Inches(1.85), width=Inches(6.35))
tf = tx(s, 6.55, 4.62, 6.35, 0.4)
para(tf, "Fig:  Results - all 32 trials checked, ranked, colour-coded verdicts",
     size=11, color=GRAY, first=True, align=PP_ALIGN.CENTER)
s.shapes.add_picture("_shots2/04_hybrid_tab.png", Inches(0.6), Inches(5.35), width=Inches(6.35))
s.shapes.add_picture("_shots2/08_unstructured_extracted.png", Inches(6.55), Inches(5.35), width=Inches(6.35))
tf = tx(s, 0.75, 7.0, 11.9, 0.35)
para(tf, "Bottom: Hybrid tab (structured CSV + notes merged per patient) and a Hindi clinical note auto-translated to English, then extracted by the ML NER.",
     size=11.5, color=DARK, first=True, align=PP_ALIGN.CENTER)
notes(s, "All four shots are live captures of the current build. Demo script: load sample \u2192 results \u2192 Hybrid tab \u2192 Hindi note upload.")

# ================= SLIDE 17 · OUTPUT 2/2 =================
s = new_slide(); header_footer(s, 15)
slide_title(s, "OUTPUT  (2/2)  \u2014  Live demo: evaluation dashboard")
s.shapes.add_picture("_shots2/10_evaluation_upload.png", Inches(0.6), Inches(1.85), width=Inches(6.35))
tf = tx(s, 0.6, 4.62, 6.35, 0.4)
para(tf, "Fig:  Model Evaluation - one-click bundled sample + ranking scope (All / Top 3 / Top 5 / Top 10)",
     size=11, color=GRAY, first=True, align=PP_ALIGN.CENTER)
s.shapes.add_picture("_shots2/11_evaluation_result.png", Inches(6.55), Inches(1.85), width=Inches(6.35))
tf = tx(s, 6.55, 4.62, 6.35, 0.4)
para(tf, "Fig:  Live top-5 run - pairs outside a patient's top-5 matches are skipped and counted",
     size=11, color=GRAY, first=True, align=PP_ALIGN.CENTER)
s.shapes.add_picture("_shots2/12_evaluation_table.png", Inches(0.6), Inches(5.35), width=Inches(12.3))
tf = tx(s, 0.75, 7.0, 11.9, 0.35)
para(tf, "Bottom: per-pair predictions vs labels - every row \u2713; downloadable as CSV. ML extraction details (facts per patient) are expandable above the table.",
     size=11.5, color=DARK, first=True, align=PP_ALIGN.CENTER)
notes(s, "The evaluation screen doubles as the project's own test harness - press one button, get scored results.")

# ================= SLIDE 18 · RESULTS =================
s = new_slide(); header_footer(s, 16)
slide_title(s, "RESULTS")
s.shapes.add_picture("_ppt_assets/confusion.png", Inches(2.35), Inches(1.85), width=Inches(8.6))
tf = tx(s, 0.75, 5.75, 11.9, 1.5)
bullet(tf, ("Live evaluation run (this build): ", "10 synthetic patients, 21 labelled patient-trial pairs \u2192 Accuracy 100%, Precision 100%, Recall 100%, F1 100% (TP 11 \u00b7 FP 0 \u00b7 FN 0 \u00b7 TN 10; 0 pairs excluded as insufficient)."), first=True, size=14)
bullet(tf, ("Top-5 ranked scope: ", "scoring only each patient's 5 best-matching trials (the way a coordinator reads the list) keeps accuracy at 100% - 13 pairs scored, 8 reported as outside the ranked scope."), size=14)
bullet(tf, ("Multilingual extraction: ", "a fully Hindi discharge note auto-translates to English and yields the same complete profile (age, gender, condition, Metformin, HbA1c 8.5, eGFR 80, BP 140/85) - previously only Latin-anchored lab values survived."), size=14)
bullet(tf, ("Honest by design: ", "notes that genuinely lack a fact degrade to \u201cInsufficient Information\u201d instead of a guess - such rows are reported separately, never counted as a class."), size=14)
bullet(tf, ("Same pipeline everywhere: ", "single matching, cohort screening and evaluation share one code path, so the score reflects what users actually get."), size=14)
notes(s, "Lead with FN=0 (clinically most important). Explain the honesty rule, then note the shared code path.")

# ================= SLIDE 19 · FUTURE SCOPE =================
s = new_slide(); header_footer(s, 17)
slide_title(s, "FUTURE SCOPE")
items = [
    ("Domain-specific NER", "Swap DistilBERT-QA for BioBERT / PubMedBERT fine-tuned on CTRI criteria for higher recall on rare entities"),
    ("Dose-threshold parsing", "Handle criteria like \u201cmetformin \u2265 1500 mg/day\u201d in the rule engine"),
    ("Live trial ingestion", "Pull real trials from the CTRI / ClinicalTrials.gov APIs instead of the bundled database"),
    ("Cohort analytics", "Per-site recruitment funnels and auto-screening schedules for coordinators"),
    ("Doctor feedback loop", "Human-in-the-loop corrections that feed back into rules and the evaluation set"),
    ("More languages + voice", "Hindi ships today (13 scripts detected); add regional speech-to-text and ICD / LOINC coding"),
]
y = 2.0
for i, (t, b) in enumerate(items):
    x = 0.75 + (i % 2) * 6.15
    yy = y + (i // 2) * 1.55
    c = card(s, x, yy, 5.95, 1.35, WHITE if i % 2 == 0 else SOFT, TEAL)
    tf = c.text_frame
    tf.margin_left = Inches(0.15); tf.margin_top = Inches(0.09)
    para(tf, [(f"{i+1}.  ", True, TEAL), (t, True, DARK)], size=13.5, first=True, after=2)
    para(tf, b, size=11.5, color=INK, after=0)
notes(s, "Tie future work to the documented limitations - each limitation has a matching item here.")

# ================= SLIDE 20 · REFERENCES =================
s = new_slide(); header_footer(s, 18)
slide_title(s, "References")
refs = [
    "Chen, L., Gu, Y., Ji, X., et al. \u201cClinical Trial Cohort Selection based on Multi-Level Rule-based Natural Language Processing System.\u201d Journal of the American Medical Informatics Association, 2019.",
    "Yuan, C., Ryan, P. B., et al. \u201cCriteria2Query: a natural language interface to clinical databases for cohort definition.\u201d JAMIA 26(4), 2019, 294-305.",
    "Ni, Y., Kennebeck, S., Dexheimer, J. W., et al. \u201cAutomated clinical trial eligibility prescreening: increasing the efficiency of patient identification for clinical trials in the emergency department.\u201d JAMIA 22(1), 2015, 166-178.",
    "Murcia, V. M., Aggarwal, V., et al. \u201cAutomating clinical trial matches via natural language processing of synthetic electronic health records and clinical trial eligibility criteria.\u201d Journal of Biomedical Informatics, 2023.",
    "Wang, K., Cui, H., Zhu, Y., et al. \u201cEvaluation of an artificial intelligence-based clinical trial matching system in Chinese patients with hepatocellular carcinoma: a retrospective study.\u201d BMC Cancer 24(1), 2024, 246.",
    "Jin, Q., Wang, Z., Floudas, C. S., Sun, J., Lu, Z. \u201cMatching patients to clinical trials with large language models (TrialGPT).\u201d Nature Communications 15, 2024, 9074.",
    "Miotto, R., Weng, C. \u201cCase-based reasoning using electronic health records efficiently identifies eligible patients for clinical trials.\u201d JAMIA 22(e1), 2015, e141-e150.",
    "Devlin, J., Chang, M.-W., Lee, K., Toutanova, K. \u201cBERT: Pre-training of Deep Bidirectional Transformers for Language Understanding.\u201d NAACL-HLT, 2019.  (DistilBERT: Sanh et al., 2019)",
]
tf = tx(s, 0.9, 2.0, 11.6, 5.0)
for k, r in enumerate(refs):
    bullet(tf, r, size=12.5, first=(k == 0), after=10, mark="\u2022")
notes(s, "Same six core papers from the progress presentation, plus the BERT/DistilBERT citation for the ML NER engine.")

# ================= SLIDE 21 · THANK YOU =================
s = new_slide()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.22))
band.fill.solid(); band.fill.fore_color.rgb = TEAL; band.line.fill.background(); band.shadow.inherit = False
tf = tx(s, 1.0, 1.6, 11.3, 1.2)
para(tf, "Thank You", size=44, color=DARK, bold=True, first=True, align=PP_ALIGN.CENTER)
tf = tx(s, 1.0, 3.0, 11.3, 0.5)
para(tf, "Questions?", size=22, color=INK, first=True, align=PP_ALIGN.CENTER)
c = card(s, 2.6, 4.1, 8.1, 1.5, SOFT, TEAL, title="Live demo")
tf = c.text_frame
para(tf, "https://ctq-clinical-trial-qualifier.onrender.com", size=14, color=DARK, bold=True,
     first=True, align=PP_ALIGN.CENTER, after=3)
para(tf, "(live deployment - first load after 15 min idle wakes the free-tier server in ~50 s; the PDF report CTQ_Full_Project_Report.pdf shows the same screens)",
     size=11, color=GRAY, align=PP_ALIGN.CENTER, after=0)
notes(s, "Demo script: Home \u2192 Find Trials \u2192 load Diabetes sample \u2192 Find Matching Trials \u2192 open an eligible card \u2192 Evaluation \u2192 Load bundled sample data \u2192 Run.")

prs.save("CTQ_Presentation.pptx")
print("saved CTQ_Presentation.pptx with", len(prs.slides._sldIdLst), "slides")

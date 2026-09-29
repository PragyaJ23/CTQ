#!/usr/bin/env python
# Generates diagram images for the CTQ presentation/report (current system):
#   _ppt_assets/flowchart.png      - end-to-end matching pipeline
#   _ppt_assets/architecture.png   - system architecture (3-tier)
#   _ppt_assets/confusion.png      - evaluation confusion matrix + metric tiles
import os
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

TEAL = "#388087"; DARK = "#2e6a70"; SOFT = "#d7ecef"; SOFT2 = "#badfe7"
SOFT3 = "#c2edce"; ACCENT = "#6fb3b8"; INK = "#1f3a3d"; BG = "#ffffff"

def box(ax, x, y, w, h, text, fc=SOFT, ec=TEAL, fs=11, tc=INK, bold=True):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                       fc=fc, ec=ec, lw=1.6)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", linespacing=1.35)

def arrow(ax, x1, y1, x2, y2, color=DARK):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                 mutation_scale=22, lw=2.0, color=color, shrinkA=2, shrinkB=2))

# ---------------------------------------------------------------- flowchart
fig, ax = plt.subplots(figsize=(12.8, 7.4), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")

box(ax, 2, 45, 21, 10, "Patient Input\nStructured form / CSV\n(cohort mode) OR\nnotes · PDF · photo (OCR)", SOFT, fs=9.5)
box(ax, 27, 45, 21, 10, "Translate if needed\nHindi + 12 scripts (Groq)\nML NER: DistilBERT\nextractive-QA, parallel", SOFT2, fs=9.5)
box(ax, 52, 45, 20, 10, "Trial Retrieval\n84 CTRI / CTG trials\nall-MiniLM-L6-v2\n+ cosine ranking", SOFT3, fs=9.5)
box(ax, 76, 45, 22, 10, "Rule Engine\nchecks EVERY trial\nage · labs · meds ·\ncomorbidities", SOFT, fs=9.5)

box(ax, 76, 29, 22, 10, "LLM Review (Groq\ngpt-oss-120b)\ntop-15 most similar,\nparallel + answer cache", "#fff7e8", ec="#c9a227", fs=9.5)
box(ax, 52, 29, 20, 10, "Verdict Merger\nrule veto + LLM 2nd\nopinion \u2192 final verdict\n+ itemised reasons", SOFT3, fs=9.5)
box(ax, 27, 29, 21, 10, "Results Page\nverdict cards \u00b7 CSV\ncohort Excel export\nper-patient stepper", SOFT2, fs=9.5)
box(ax, 2, 29, 21, 10, "Evaluation Module\nlabelled pairs \u2192\naccuracy · P · R · F1\nconfusion matrix", SOFT, fs=9.5)

box(ax, 14, 12, 32, 9, "Deployment\nRender Docker \u00b7 ONNX int8 NER (512 MB)\nFreebuff dashboard for agents", SOFT3, fs=9.5)
box(ax, 54, 12, 32, 9, "Performance layer\nparallel extraction \u00b7 top-15 LLM cap\nanswer cache \u00b7 10-patient cohort \u2248 100 s", SOFT, fs=9.5)

arrow(ax, 23, 50, 27, 50)          # input -> translate/NER
arrow(ax, 48, 50, 52, 50)          # NER -> retrieval
arrow(ax, 72, 50, 76, 50)          # retrieval -> rule engine
arrow(ax, 87, 45, 87, 39)          # rule engine -> LLM review lane
arrow(ax, 76, 34, 72, 34)          # LLM review -> merger
arrow(ax, 52, 34, 48, 34)          # merger -> results
arrow(ax, 27, 34, 23, 34)          # results -> evaluation
arrow(ax, 87, 29, 87, 21)          # down to performance layer
arrow(ax, 46, 16.5, 54, 16.5)      # deployment <-> performance tie
ax.set_title("CTQ Methodology \u2014 end-to-end matching pipeline", fontsize=15, fontweight="bold", color=INK, pad=14)
fig.savefig("_ppt_assets/flowchart.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)

# ------------------------------------------------------------- architecture
fig, ax = plt.subplots(figsize=(12.8, 7.0), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")

box(ax, 2, 36, 29, 13, "Presentation Tier\nReact 18 + Vite SPA \u00b7 react-router \u00b7 axios\nMatcher (structured + unstructured tabs,\ncohort, top-K picker) \u00b7 Results \u00b7 Trial\nDatabase (live CTG import) \u00b7 Evaluation", SOFT, fs=9)
box(ax, 36, 36, 29, 13, "Application Tier\nFastAPI + Uvicorn \u00b7 Pydantic schemas\nprofile_builder \u00b7 trial_retrieval\neligibility (rule engine) \u00b7 matching\nllm (breaker + cache) \u00b7 translate \u00b7 ml_ner", SOFT2, fs=9)
box(ax, 70, 36, 28, 13, "Data Tier\ntrials.json: 84 trials (32 CTRI demo\n+ 52 CTG live-imported) + sidecar\nSQLite (evaluation runs)\nHF model cache \u00b7 embedding cache", SOFT3, fs=9)

box(ax, 2, 16, 22, 9, "sentence-transformers\nall-MiniLM-L6-v2 (local)", "#ffffff", ec=ACCENT, fs=9.5)
box(ax, 27, 16, 22, 9, "DistilBERT extractive-QA\nNER (torch / ONNX int8)", "#ffffff", ec=ACCENT, fs=9.5)
box(ax, 52, 16, 22, 9, "Groq API gpt-oss-120b\ntranslation + LLM review", "#fff7e8", ec="#c9a227", fs=9.5)
box(ax, 77, 16, 21, 9, "RapidOCR + PyMuPDF\nphoto / scanned-PDF text", "#ffffff", ec=ACCENT, fs=9.5)

box(ax, 2, 2, 96, 8, "Deployment: Render Docker (auto-deploy on push to master) \u00b7 production bundle served by FastAPI \u00b7 localhost dev: Vite :5173 + Uvicorn :8000", SOFT, fs=10)
arrow(ax, 31, 42.5, 36, 42.5); arrow(ax, 65, 42.5, 70, 42.5)
arrow(ax, 13, 36, 13, 25); arrow(ax, 38, 36, 38, 25); arrow(ax, 63, 36, 63, 25); arrow(ax, 87, 36, 87, 25)
ax.set_title("CTQ System Architecture", fontsize=15, fontweight="bold", color=INK, pad=14)
fig.savefig("_ppt_assets/architecture.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)

# ---------------------------------------------------------------- confusion
# Live numbers: 80 structured patients x 84 trials = 1,600 labelled pairs
# (run 3, 29 Sep 2026). 104 pairs predicted Insufficient Information are
# excluded from the binary matrix; 42 labelled Insufficient likewise.
fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8), dpi=150, gridspec_kw={"width_ratios": [1, 1.2]})
a = axes[0]
a.imshow([[1303, 10], [79, 62]], cmap=matplotlib.colors.LinearSegmentedColormap.from_list("t", ["#ffffff", TEAL]), vmin=0, vmax=1303)
for (i, j), v in {(0,0): "TN = 1303", (0,1): "FP = 10", (1,0): "FN = 79", (1,1): "TP = 62"}.items():
    a.text(j, i, v, ha="center", va="center", fontsize=14, fontweight="bold", color=INK)
a.set_xticks([0, 1]); a.set_xticklabels(["Pred: Not Eligible", "Pred: Eligible"], fontsize=10)
a.set_yticks([0, 1]); a.set_yticklabels(["Actual: Not Eligible", "Actual: Eligible"], fontsize=10)
a.set_title("Structured sweep \u2014 80 patients \u00d7 84 trials (1,454 scored pairs)", fontsize=11.5, fontweight="bold", color=INK)
a.set_xticks([0.5, 1.5], minor=True); a.set_yticks([0.5, 1.5], minor=True)
a.grid(which="minor", color="white", lw=3); a.tick_params(which="minor", length=0)
b = axes[1]; b.axis("off")
tiles = [("Accuracy (binary pairs)", "93.9%", "1,365 of 1,454 scored pairs correct \u00b7 specificity 99.2%"),
         ("Conservative by design", "104", "pairs returned Insufficient Information instead of guessing (excluded, tracked)"),
         ("Trial database", "84", "32 CTRI synthetic + 52 live-imported ClinicalTrials.gov recruiting-in-India"),
         ("Cohort speed", "\u2248100 s", "10 unstructured patients \u00d7 84 trials \u2014 extraction parallelised, LLM capped to top-15")]
for k, (t, v, s) in enumerate(tiles):
    y = 0.80 - (k // 2) * 0.46; x = 0.02 + (k % 2) * 0.5
    b.add_patch(FancyBboxPatch((x, y - 0.28), 0.46, 0.34, boxstyle="round,pad=0.02,rounding_size=0.05",
                 fc=SOFT, ec=TEAL, lw=1.5))
    b.text(x + 0.23, y - 0.02, v, ha="center", va="center", fontsize=19, fontweight="bold", color=DARK)
    b.text(x + 0.23, y - 0.19, t + "\n" + s, ha="center", va="center", fontsize=8, color=INK)
b.set_xlim(0, 1); b.set_ylim(0, 1)
fig.suptitle("CTQ Evaluation Results", fontsize=15, fontweight="bold", color=INK)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("_ppt_assets/confusion.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("assets done")

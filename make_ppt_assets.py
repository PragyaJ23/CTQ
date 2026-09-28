#!/usr/bin/env python
# Generates diagram images for the CTQ presentation:
#   _ppt_assets/flowchart.png      - end-to-end methodology flowchart
#   _ppt_assets/architecture.png   - system architecture (3-tier)
#   _ppt_assets/confusion.png      - evaluation confusion matrix + accuracy tiles
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
fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")

box(ax, 2, 44, 20, 9, "Patient Input\nWeb form (structured)\nPDF · CSV · TXT · Excel", SOFT)
box(ax, 26, 44, 20, 9, "Profile Builder\n(NLP + regex)\nunstructured notes\n\u2192 structured fields", SOFT2)
box(ax, 50, 44, 20, 9, "Trial Retrieval\nsentence-transformers\nall-MiniLM-L6-v2\nsemantic similarity", SOFT3)
box(ax, 74, 44, 24, 9, "Rule Engine\nage / gender / labs / meds /\ncomorbidities \u2192 INCLUDE / EXCLUDE / UNKNOWN", SOFT)

box(ax, 74, 28, 24, 9, "Match Merger\nrule veto + similarity\n\u2192 final score", "#ffffff", ec=DARK)
box(ax, 50, 28, 20, 9, "LLM Review (Groq\ngpt-oss-120b)\nadversarial 2nd opinion", "#fff7e8", ec="#c9a227")
box(ax, 26, 28, 20, 9, "Verdict Builder\nPotentially Eligible /\nNot Eligible /\nInsufficient Information", SOFT)
box(ax, 2, 28, 20, 9, "Explainer\nitemised reasons with\nquotes from the trial", SOFT2)

box(ax, 14, 12, 30, 9, "Results Dashboard\nfilters + verdict cards", SOFT3)
box(ax, 56, 12, 30, 9, "Evaluation Module\nupload patients + labels\n\u2192 accuracy metrics", SOFT)

arrow(ax, 22, 48.5, 26, 48.5); arrow(ax, 46, 48.5, 50, 48.5); arrow(ax, 70, 48.5, 74, 48.5)
arrow(ax, 86, 44, 86, 37)          # rule engine -> merger
arrow(ax, 74, 32.5, 70, 32.5)      # LLM -> merger (2nd opinion)
arrow(ax, 74, 32.5, 74, 32.5)
arrow(ax, 60, 32.5, 46, 32.5)      # merger -> verdict builder
arrow(ax, 26, 32.5, 22, 32.5)      # verdict builder -> explainer
arrow(ax, 12, 28, 20, 21)          # explainer -> dashboard
arrow(ax, 71, 28, 66, 21)          # merger -> evaluation
ax.set_title("CTQ Methodology \u2014 end-to-end matching pipeline", fontsize=15, fontweight="bold", color=INK, pad=14)
fig.savefig("_ppt_assets/flowchart.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)

# ------------------------------------------------------------- architecture
fig, ax = plt.subplots(figsize=(12.8, 6.6), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 52); ax.axis("off")

box(ax, 2, 34, 26, 12, "Presentation Tier\nReact 18 + Vite SPA\nreact-router · axios\n Matcher · Results · Evaluation · Trials", SOFT, fs=10.5)
box(ax, 37, 34, 26, 12, "Application Tier\nFastAPI + Uvicorn\nPydantic validation\nprofile_builder · rule engine\nmatcher · llm_review · evaluation", SOFT2, fs=10.5)
box(ax, 72, 34, 26, 12, "Data Tier\nSQLite (patients, labels, runs)\ntrials.json \u2192 20 CTRI-format trials\nembeddings cache", SOFT3, fs=10.5)

box(ax, 2, 12, 26, 9, "sentence-transformers\nall-MiniLM-L6-v2 (local)", "#ffffff", ec=ACCENT, fs=10)
box(ax, 37, 12, 26, 9, "Groq API\ngpt-oss-120b (LLM review)", "#fff7e8", ec="#c9a227", fs=10)
box(ax, 72, 12, 26, 9, "ReportLab\nPDF export of results", "#ffffff", ec=ACCENT, fs=10)

arrow(ax, 28, 40, 37, 40); arrow(ax, 63, 40, 72, 40)
arrow(ax, 15, 34, 15, 21); arrow(ax, 50, 34, 50, 21); arrow(ax, 85, 34, 85, 21)
ax.set_title("CTQ System Architecture", fontsize=15, fontweight="bold", color=INK, pad=14)
fig.savefig("_ppt_assets/architecture.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)

# ---------------------------------------------------------------- confusion
fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6), dpi=150, gridspec_kw={"width_ratios": [1, 1.15]})
a = axes[0]
a.imshow([[13, 2], [0, 5]], cmap=matplotlib.colors.LinearSegmentedColormap.from_list("t", ["#ffffff", TEAL]), vmin=0, vmax=15)
for (i, j), v in {(0,0): "TN = 11", (0,1): "FP = 2", (1,0): "FN = 0", (1,1): "TP = 2"}.items():
    a.text(j, i, v, ha="center", va="center", fontsize=15, fontweight="bold", color=INK)
a.set_xticks([0, 1]); a.set_xticklabels(["Pred: Not Eligible", "Pred: Eligible"], fontsize=10)
a.set_yticks([0, 1]); a.set_yticklabels(["Actual: Not Eligible", "Actual: Eligible"], fontsize=10)
a.set_title("Hand-verified audit \u2014 patient P001 vs 20 trials", fontsize=12, fontweight="bold", color=INK)
a.set_xticks([0.5, 1.5], minor=True); a.set_yticks([0.5, 1.5], minor=True)
a.grid(which="minor", color="white", lw=3); a.tick_params(which="minor", length=0)
b = axes[1]; b.axis("off")
tiles = [("Binary accuracy (hand audit)", "86.7%", "13 / 15 labelable pairs"),
         ("Three-class agreement", "75%", "15 / 20 trials"),
         ("Benchmark accuracy (1600 pairs)", "97.3%", "TP 93 · FP 27 · FN 6 · TN 1115"),
         ("Missed eligible trials (FN)", "0", "no eligible trial turned away")]
for k, (t, v, s) in enumerate(tiles):
    y = 0.78 - (k // 2) * 0.46; x = 0.02 + (k % 2) * 0.5
    b.add_patch(FancyBboxPatch((x, y - 0.28), 0.46, 0.34, boxstyle="round,pad=0.02,rounding_size=0.05",
                 fc=SOFT, ec=TEAL, lw=1.5))
    b.text(x + 0.23, y - 0.02, v, ha="center", va="center", fontsize=20, fontweight="bold", color=DARK)
    b.text(x + 0.23, y - 0.19, t + "\n" + s, ha="center", va="center", fontsize=8.5, color=INK)
b.set_xlim(0, 1); b.set_ylim(0, 1)
fig.suptitle("CTQ Evaluation Results", fontsize=15, fontweight="bold", color=INK)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("_ppt_assets/confusion.png", bbox_inches="tight", facecolor=BG)
plt.close(fig)
print("assets done")

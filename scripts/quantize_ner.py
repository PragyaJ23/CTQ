"""Generate the quantized int8 NER artifact used by slim Docker deploys.

Run inside the Docker build (network available). Produces:
  <out>/quantized_model.pt      pickled dynamically-quantized QA module
  <out>/tokenizer files         AutoTokenizer.save_pretrained output
  <out>/MODEL_SOURCE.txt        provenance note

Why pickle instead of save_pretrained: torch dynamic quantization does not
round-trip through from_pretrained. Why int8: torch + fp32 DistilBERT cannot
fit a 512 MB container (Render free plan); the int8 module is ~4x smaller.
"""
import os

import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

SRC = "distilbert-base-cased-distilled-squad"
OUT = os.environ.get("CTQ_ARTIFACT_OUT", "/app/model_artifact")


def main() -> None:
    tok = AutoTokenizer.from_pretrained(SRC)
    mdl = AutoModelForQuestionAnswering.from_pretrained(SRC)
    quantized = torch.quantization.quantize_dynamic(
        mdl, {torch.nn.Linear}, dtype=torch.qint8
    )
    os.makedirs(OUT, exist_ok=True)
    torch.save(quantized, os.path.join(OUT, "quantized_model.pt"))
    tok.save_pretrained(OUT)
    with open(os.path.join(OUT, "MODEL_SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write(SRC + "\n")
    size_mb = os.path.getsize(os.path.join(OUT, "quantized_model.pt")) / 1e6
    print(f"[quantize_ner] wrote {OUT}/quantized_model.pt ({size_mb:.0f} MB) from {SRC}")


if __name__ == "__main__":
    main()

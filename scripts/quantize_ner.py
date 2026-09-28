"""Generate the ONNX QA artifact used by slim Docker deploys (Render free).

Run inside the Docker build (network available). Produces:
  <out>/model.onnx            exported DistilBERT QA graph, int8 dynamic
                              quantized (onnxruntime, no torch at runtime)
  <out>/tokenizer files       AutoTokenizer.save_pretrained output
  <out>/MODEL_SOURCE.txt      provenance note

onnxruntime needs a fraction of the RAM torch does (~120 MB vs ~450 MB
resident), which is what lets the NER + the app fit a 512 MB container.
The tokenizer is CPU-only; answers are identical to the torch pipeline.
"""
import os

import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

SRC = "distilbert-base-cased-distilled-squad"
OUT = os.environ.get("CTQ_ARTIFACT_OUT", "/app/model_artifact")


def main() -> None:
    from onnxruntime.quantization import quantize_dynamic, QuantType

    tok = AutoTokenizer.from_pretrained(SRC)
    mdl = AutoModelForQuestionAnswering.from_pretrained(SRC)
    mdl.eval()

    os.makedirs(OUT, exist_ok=True)
    onnx_path = os.path.join(OUT, "model_fp32.onnx")
    quant_path = os.path.join(OUT, "model.onnx")

    class QAWrapper(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            out = self.m(input_ids=input_ids, attention_mask=attention_mask)
            return out.start_logits, out.end_logits

    dummy = tok("How old is the patient?", "45-year-old male with diabetes.",
                return_tensors="pt", truncation="only_second", max_length=384)
    with torch.no_grad():
        torch.onnx.export(
            QAWrapper(mdl),
            (dummy["input_ids"], dummy["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["start_logits", "end_logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "start_logits": {0: "batch", 1: "seq"},
                "end_logits": {0: "batch", 1: "seq"},
            },
            opset_version=14,
        )
    quantize_dynamic(onnx_path, quant_path, weight_type=QuantType.QInt8)
    os.remove(onnx_path)

    tok.save_pretrained(OUT)
    with open(os.path.join(OUT, "MODEL_SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write(SRC + " (ONNX int8 dynamic quantized)\n")
    size_mb = os.path.getsize(quant_path) / 1e6
    print(f"[quantize_ner] wrote {quant_path} ({size_mb:.0f} MB) from {SRC}")


if __name__ == "__main__":
    main()

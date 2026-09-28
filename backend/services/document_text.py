"""Document-to-text extraction for unstructured patient data.

Accepts photos of summaries/prescriptions (JPG/PNG - OCR via RapidOCR),
scanned or digital PDFs (pypdf text, OCR fallback), CSV/Excel/TXT/JSON notes,
and plain pasted text. The resulting text is sent through the DistilBERT ML
NER to produce structured profile fields.
"""
from __future__ import annotations

import io
import json

import pandas as pd

SUPPORTED_UPLOADS = ".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.csv,.xlsx,.xls,.tsv,.txt,.json"

_NOTE_ID_ALIASES = {"note_id", "id", "patient_id", "noteid", "row_id"}
_NOTE_TEXT_ALIASES = {"text", "note", "clinical_notes", "clinical_note", "notes",
                      "note_text", "content", "summary", "history", "medical_history"}


class UnsupportedFile(Exception):
    pass


def _ocr_image_bytes(raw: bytes) -> str:
    """OCR an image (photo of a prescription/summary) with RapidOCR."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise UnsupportedFile(
            "OCR is not installed on the server - cannot read photos. "
            "Upload a PDF, CSV or text file instead.") from exc
    ocr = RapidOCR()
    result, _ = ocr(raw)
    if not result:
        return ""
    # RapidOCR returns [box, text, score]; join reading-order lines
    return "\n".join(str(item[1]).strip() for item in result if item and item[1])


def _pdf_text(raw: bytes) -> str:
    """Digital PDF text; falls back to OCR of rendered pages when empty."""
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception:
        text = ""
    if text:
        return text
    # scanned PDF: rasterise pages then OCR
    try:
        import fitz  # PyMuPDF, if available
        doc = fitz.open(stream=raw, filetype="pdf")
        chunks = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            chunks.append(_ocr_image_bytes(pix.tobytes("png")))
        return "\n".join(c for c in chunks if c)
    except ImportError:
        raise UnsupportedFile(
            "This PDF has no embedded text (likely a scan) and the server cannot "
            "render it for OCR. Upload photos of the pages (PNG/JPG) instead.")


def _notes_from_table(raw: bytes, filename: str) -> list:
    """CSV/Excel/JSON -> [{id, text}] using text-ish column aliases."""
    name = (filename or "").lower()
    if name.endswith(".json"):
        data = json.loads(raw.decode("utf-8", errors="replace"))
        rows = data if isinstance(data, list) else data.get("rows") or data.get("notes") or []
        out = []
        for i, r in enumerate(rows):
            if isinstance(r, dict):
                text = next((r.get(k) for k in
                             ("text", "note", "clinical_notes", "notes", "summary",
                              "medical_history", "content") if r.get(k)), None)
                nid = r.get("note_id") or r.get("id") or r.get("patient_id") or f"P{i+1:03d}"
            else:
                text, nid = str(r), f"P{i+1:03d}"
            if text:
                out.append({"id": str(nid), "text": str(text)})
        return out
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw))
    else:
        text = raw.decode("utf-8", errors="replace")
        try:
            df = pd.read_csv(io.StringIO(text))
        except Exception:
            try:
                df = pd.read_csv(io.StringIO(text), sep="\t")
            except Exception:
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                return [{"id": f"P{i+1:03d}", "text": ln} for i, ln in enumerate(lines)]
    if df.empty:
        return []
    low_cols = {str(c).strip().lower(): c for c in df.columns}
    text_col = next((low_cols[a] for a in _NOTE_TEXT_ALIASES if a in low_cols), None)
    if text_col is None:  # substring fallback
        for a in _NOTE_TEXT_ALIASES:
            for k, orig in low_cols.items():
                if a in k:
                    text_col = orig
                    break
            if text_col:
                break
    if text_col is None:
        # multi-column unstructured CSV: join everything into one text blob per row
        text_col = df.columns[0]
    id_col = next((low_cols[a] for a in _NOTE_ID_ALIASES if a in low_cols), None)
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        val = row[text_col]
        if pd.isna(val) or not str(val).strip():
            continue
        nid = str(row[id_col]) if id_col else f"P{i+1:03d}"
        rows.append({"id": nid, "text": str(val)})
    return rows


def document_to_text(raw: bytes, filename: str) -> dict:
    """Convert any supported upload into plain clinical text.

    Returns {kind, pages_or_rows, text} - text is '' only when nothing
    readable was found.
    """
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return {"kind": "pdf", "text": _pdf_text(raw)}
    if name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")):
        return {"kind": "image-ocr", "text": _ocr_image_bytes(raw)}
    if name.endswith((".csv", ".xlsx", ".xls", ".tsv", ".json")):
        rows = _notes_from_table(raw, name)
        joined = "\n\n".join(f"[{r['id']}] {r['text']}" for r in rows)
        return {"kind": "table", "rows": len(rows), "notes": rows, "text": joined}
    if name.endswith((".txt", ".tsv")) or True:
        text = raw.decode("utf-8", errors="replace").strip()
        return {"kind": "text", "text": text}

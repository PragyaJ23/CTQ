# ---------------------------------------------------------------------------
# CTQ - Clinical Trial Qualifier : single-container production image
# Stage 1 builds the React frontend; stage 2 runs FastAPI, which serves the
# built frontend and the /api on one origin (same as local port 8000).
# ---------------------------------------------------------------------------

# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend_build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime with CPU-only ML stack ----
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # HuggingFace model cache on a writable path (downloaded on first boot)
    HF_HOME=/tmp/hf_cache

# torch CPU wheels FIRST (the default PyPI torch pulls ~2GB of CUDA libs),
# then the rest of the requirements see torch already satisfied.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /app/backend/requirements.txt

# Pre-quantize the NER QA model to int8 at build time (network is available
# here, not at runtime on Render). torch + fp32 DistilBERT does not fit in a
# 512 MB container, but the int8 artifact (~90 MB) does. Dynamic quantization
# does not round-trip through save_pretrained, so we pickle the module itself.
COPY scripts/quantize_ner.py /app/scripts/quantize_ner.py
RUN python /app/scripts/quantize_ner.py

COPY backend/ /app/backend/
COPY sample_data/ /app/sample_data/
COPY --from=frontend_build /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend

# Point ml_ner.py at the shipped int8 artifact (used when no local HF
# snapshot exists; developer machines with the cached fp32 model are
# unaffected).
ENV CTQ_NER_ARTIFACT=/app/model_artifact \
    HF_HOME=/tmp/hf_cache

EXPOSE 8000
# Render injects PORT; default 8000 for local docker runs
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

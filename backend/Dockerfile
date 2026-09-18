# ─── DermaAI Backend — Production Dockerfile ──────────────────────────────────
# Multi-stage build: keeps the final image lean.
# The ML dependencies (PyTorch, timm) are large — comment them out in requirements.txt
# if you only want to run the API server without local inference.

FROM python:3.11-slim AS base

# System deps needed by Pillow and some C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python deps first (cached layer) ──────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────────────────────
COPY . .

# ── Create uploads dir (volume mount point) ───────────────────────────────────
RUN mkdir -p /app/uploads

# ── Non-root user for security ────────────────────────────────────────────────
RUN useradd -m dermaai
USER dermaai

# ── Expose & run ──────────────────────────────────────────────────────────────
EXPOSE 8000

# uvicorn with 1 worker (scale horizontally via replicas in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/hf_cache
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 pastabar
COPY pyproject.toml README.md ./
COPY pastabar/ ./pastabar/
# Use CPU wheels rather than downloading NVIDIA runtime libraries.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir '.[rag]'
COPY api.py instruction.json ./
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
RUN mkdir -p /app/data /app/hf_cache && chown -R pastabar:pastabar /app
USER pastabar
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

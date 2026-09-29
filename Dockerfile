# Single-service image for hosting: FastAPI serves the API under /api and
# the built React app for everything else. Used by render.yaml; runs
# anywhere that accepts a Dockerfile (Render, Fly.io, Railway, a VPS).
#
# Local development still uses docker-compose.yml (separate services).

# --- 1. Build the frontend ----------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same-origin API; the demo login button is shown on the hosted site.
ENV VITE_API_URL=/api \
    VITE_DEMO_MODE=true
RUN npm run build

# --- 2. Backend + static files ---------------------------------------------------
FROM python:3.11-slim
WORKDIR /app

# System libraries for WeasyPrint (PDF reports).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libffi-dev \
    libjpeg62-turbo libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist /app/static
RUN mkdir -p /app/data /app/reports /app/media

ENV STATIC_DIR=/app/static \
    REPORTS_DIR=/app/reports \
    MEDIA_DIR=/app/media \
    DATABASE_URL=sqlite:////app/data/greenthread.db \
    PYTHONUNBUFFERED=1

# Hosts like Render inject $PORT; default to 8000 elsewhere.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

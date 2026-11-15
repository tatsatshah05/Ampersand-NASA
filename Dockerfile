# SPHEREx sky-change viewer: the backend and the frontend it serves, in one container.
# Build and run steps are in docs/deploy.md.
#
# The container needs a persistent disk mounted at /app/backend/cache. Without one it
# still works, but everything downloaded from the archive is lost on restart.

# ---- Stage 1: build the React frontend (frontend/, Vite) -----------------------------
FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the Python service ------------------------------------------------------
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# The pre-built demo results (the views of the eleven buttons and the answers of their tools:
# about 240 MB of small files, no cutouts), so the site opens at once on a host with a slow
# processor or no disk of its own. Packed on a laptop and published as a release file:
# docs/deploy-render.md. Build with --build-arg SEED_URL= to leave them out.
COPY scripts/seed_cache.py scripts/seed_cache.py
ARG SEED_URL=https://github.com/tatsatshah05/Ampersand-NASA/releases/download/demo-cache-2/spherex-demo-cache.tar.gz
RUN python scripts/seed_cache.py fetch "$SEED_URL" backend/cache

COPY backend/ backend/
COPY scripts/ scripts/
# backend/app.py serves frontend/dist at "/" when it exists: the React app, and the
# earlier single-file viewer at /viewer.html.
COPY --from=frontend /src/frontend/dist frontend/dist

# Most hosts pass the port to listen on in $PORT; 8000 otherwise.
# One worker on purpose: one process keeps the downloads to the archive at six at a time.
# With SPHEREX_CACHE_DIR on a mounted disk that is still empty, the pre-built results are
# copied there once before the server starts.
EXPOSE 8000
CMD ["sh", "-c", "python scripts/seed_cache.py copy backend/cache \"${SPHEREX_CACHE_DIR:-}\"; exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]

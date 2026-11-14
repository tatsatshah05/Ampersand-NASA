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

COPY backend/ backend/
COPY scripts/ scripts/
# backend/app.py serves frontend/dist at "/" when it exists: the React app, and the
# earlier single-file viewer at /viewer.html.
COPY --from=frontend /src/frontend/dist frontend/dist

# Most hosts pass the port to listen on in $PORT; 8000 otherwise.
# One worker on purpose: one process keeps the downloads to the archive at six at a time.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]

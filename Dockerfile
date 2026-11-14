# SPHEREx sky-change viewer: backend, plus the built frontend when there is one.
# Build and run steps are in docs/deploy.md.
#
# The container needs a persistent disk mounted at /app/backend/cache. Without one it
# still works, but everything downloaded from the archive is lost on restart.

# ---- Stage 1: build the frontend, if the repo has one --------------------------------
# With frontend/package.json present this runs the Vite build. With only a prebuilt
# frontend/dist it uses that. With neither it leaves an empty folder and the image
# serves the API alone.
FROM node:22-slim AS frontend
WORKDIR /src
COPY . .
RUN if [ -f frontend/package.json ]; then \
        cd frontend && (npm ci || npm install) && npm run build; \
    else \
        mkdir -p frontend/dist; \
    fi

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
COPY --from=frontend /src/frontend/dist frontend/dist

# backend/app.py serves /api and /frames only. This wrapper adds the frontend at "/"
# when frontend/dist/index.html exists, so one address serves both. It is written here
# rather than kept as a file so the backend package stays untouched; the routes of
# backend.app are registered first and therefore win over the static files.
RUN printf '%s\n' \
    '"""backend.app plus the built frontend, if present, on one address."""' \
    'from pathlib import Path' \
    '' \
    'from fastapi.staticfiles import StaticFiles' \
    '' \
    'from backend.app import app' \
    '' \
    'dist = Path(__file__).resolve().parent / "frontend" / "dist"' \
    'if (dist / "index.html").exists():' \
    '    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")' \
    > serve.py

# Most hosts pass the port to listen on in $PORT; 8000 otherwise.
# One worker on purpose: the pipeline caches on disk and has no cross-process locking.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn serve:app --host 0.0.0.0 --port ${PORT:-8000}"]

# SPHEREx sky-change viewer: the backend and the page it serves, in one container.
# Build and run steps are in docs/deploy.md.
#
# The container needs a persistent disk mounted at /app/backend/cache. Without one it
# still works, but everything downloaded from the archive is lost on restart.

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/
# The page is a plain file, frontend/index.html, with no build step. backend/app.py
# serves the frontend/ folder at "/" when that file exists.
COPY frontend/ frontend/

# Most hosts pass the port to listen on in $PORT; 8000 otherwise.
# One worker on purpose: one process keeps the downloads to the archive at six at a time.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]

"""FastAPI service.  Run:  .venv/bin/uvicorn backend.app:app --reload

How errors are answered: a request that asks for something impossible (spherex.BadRequest)
is a 400 with the reason; an archive or catalogue that does not answer is a 502; a name
nobody knows is a 404; anything else is the server's own fault, logged in full and answered
500 with a plain sentence (never a raw numpy or astropy message).
"""
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import astrometry, jobs, photometry, pipeline, smallbodies, spherex, stars, training

log = logging.getLogger("backend.app")
app = FastAPI(title="SPHEREx sky-change viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
pipeline.FRAMES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/frames", StaticFiles(directory=pipeline.FRAMES_DIR), name="frames")


def _answer(work: Callable[[], Any], doing: str, archive: str) -> Any:
    """Run one request's work and turn its failures into the right HTTP answer."""
    try:
        return work()
    except HTTPException:
        raise
    except spherex.BadRequest as e:
        raise HTTPException(400, str(e)) from e
    except astrometry.NameNotFound as e:
        raise HTTPException(404, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"{archive} did not respond: {e}") from e
    except Exception as e:  # noqa: BLE001 - anything else is a fault of this server, not of the request
        log.exception("unexpected error while %s", doing)
        raise HTTPException(500, f"Something went wrong on the server while {doing}. It has been logged; "
                                 "please try again, or try another view.") from e


@app.get("/api/resolve")
def resolve(name: str = Query(..., min_length=1, max_length=80)):
    """Object name to coordinates at 2026.0, with proper motion and parallax when known."""
    return _answer(lambda: astrometry.resolve_name(name), "looking up the name", "The name service")


@app.get("/api/frames")
def frames(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
           fov: float = Query(0.1, gt=0.02, le=0.5), detector: int = Query(5, ge=1, le=6),
           mode: str = Query("normal"),
           pmra: float | None = Query(None, description="mas/yr, including cos(dec); from /api/resolve"),
           pmdec: float | None = Query(None, description="mas/yr"),
           parallax: float | None = Query(None, description="mas; zero or negative counts as unknown"),
           pm_epoch: float = Query(astrometry.RESOLVE_EPOCH, ge=1990, le=2040,
                                   description="Julian year at which the object is at (ra, dec)"),
           reference: str = Query("first", description="difference mode: 'first' or 'mean'"),
           track: str = Query("sky", description="sum mode: 'sky' or 'target'")):
    """Frames for the player. Plain `def`, so FastAPI runs it in a worker thread."""
    return _answer(lambda: pipeline.build_frames(ra, dec, fov, detector, mode, pmra=pmra, pmdec=pmdec,
                                                 parallax=parallax, pm_epoch=pm_epoch, reference=reference,
                                                 track=track),
                   "making the frames", "The SPHEREx archive (IRSA)")


_PMRA = Query(None, description="mas/yr, including cos(dec); from /api/resolve")
_PMDEC = Query(None, description="mas/yr")
_PARALLAX = Query(None, description="mas; zero or negative counts as unknown")
_PM_EPOCH = Query(astrometry.RESOLVE_EPOCH, ge=1990, le=2040,
                  description="Julian year at which the object is at (ra, dec)")


@app.get("/api/stars")
def field_stars(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
                fov: float = Query(0.1, gt=0.02, le=0.5), detector: int = Query(5, ge=1, le=6),
                mode: str = Query("normal"),
                pmra: float | None = _PMRA, pmdec: float | None = _PMDEC, parallax: float | None = _PARALLAX,
                pm_epoch: float = _PM_EPOCH,
                reference: str = Query("first", description="difference mode: 'first' or 'mean'"),
                track: str = Query("sky", description="sum mode: 'sky' or 'target'"),
                limit: int = Query(stars.DEFAULT_LIMIT, ge=1, le=stars.MAX_LIMIT,
                                   description="most stars to return, brightest first")):
    """Gaia stars in the frames of a view, placed on each frame. Same parameters as /api/frames."""
    return _answer(lambda: stars.field_stars(ra, dec, fov, detector, mode, limit=limit, pmra=pmra, pmdec=pmdec,
                                             parallax=parallax, pm_epoch=pm_epoch, reference=reference, track=track),
                   "placing the catalogue stars", "The SPHEREx archive (IRSA)")


# --- Known asteroids and comets (JPL small-body services); self-contained, see backend/smallbodies.py ---
@app.get("/api/smallbodies")
def small_bodies(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
                 fov: float = Query(0.1, gt=0.02, le=0.5), detector: int = Query(5, ge=1, le=6)):
    """Known asteroids and comets predicted in the field at the time of a SPHEREx exposure. Slow the first time."""
    try:
        return smallbodies.known_bodies(ra, dec, fov, detector)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except smallbodies.JplError as e:
        raise HTTPException(502, f"NASA/JPL's small-body services did not respond: {e}") from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The SPHEREx archive (IRSA) did not respond: {e}") from e
# --- end of known asteroids and comets ---


@app.get("/api/lightcurve")
def lightcurve(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
               detector: int | None = Query(None, ge=1, le=6, description="one detector only; default all six"),
               pmra: float | None = _PMRA, pmdec: float | None = _PMDEC, parallax: float | None = _PARALLAX,
               pm_epoch: float = _PM_EPOCH):
    """Brightness of the object at (ra, dec) against time, grouped by wavelength bin."""
    return _answer(lambda: photometry.lightcurve(ra, dec, detector, pmra=pmra, pmdec=pmdec, parallax=parallax,
                                                 pm_epoch=pm_epoch),
                   "measuring the brightness", "The SPHEREx archive (IRSA)")


@app.get("/api/spectrum")
def spectrum(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
             epoch: int | None = Query(None, ge=1, description="epoch number as in /api/frames; default all"),
             detector: int | None = Query(None, ge=1, le=6, description="one detector only; default all six"),
             pmra: float | None = _PMRA, pmdec: float | None = _PMDEC, parallax: float | None = _PARALLAX,
             pm_epoch: float = _PM_EPOCH):
    """Brightness of the object at (ra, dec) against wavelength, one point per exposure."""
    return _answer(lambda: photometry.spectrum(ra, dec, epoch, detector, pmra=pmra, pmdec=pmdec, parallax=parallax,
                                               pm_epoch=pm_epoch),
                   "measuring the spectrum", "The SPHEREx archive (IRSA)")


@app.get("/api/search")
def blind_search(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
                 fov: float = Query(0.1, gt=0.02, le=0.5),
                 detectors: str = Query("123456", max_length=12, description="which detectors, e.g. 123456 or 56")):
    """Everything in a field that moved or changed brightness between visits, checked against the
    catalogues. No target is given. The search runs in the background: `status` is "queued",
    "running", "done" (with `result`) or "failed" (with `error`); ask again every few seconds."""
    return _answer(lambda: jobs.search_status(ra, dec, fov, jobs.parse_detectors(detectors)),
                   "starting the search", "The SPHEREx archive (IRSA)")


@app.get("/api/training")
def training_frames(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
                    fov: float = Query(0.1, ge=training.MIN_FOV, le=training.MAX_FOV),
                    detector: int = Query(5, ge=1, le=6),
                    mode: str = Query("normal", description="'normal' or 'difference'"),
                    level: str = Query("medium", description="'easy', 'medium' or 'hard'"),
                    seed: int = Query(1, ge=0, le=2_000_000_000,
                                      description="which made-up object: the same seed gives the same round")):
    """SIMULATION. Real frames with one made-up moving object added, for practice. Never mixed
    into /api/frames: its own endpoint, its own folders, and SIMULATION written in every picture."""
    return _answer(lambda: training.build_training(ra, dec, fov, detector, mode, level, seed),
                   "building the practice round", "The SPHEREx archive (IRSA)")


# The frontend, at "/". Registered last so every /api and /frames route wins.
# frontend/ is a React app that has to be built first (cd frontend && npm install &&
# npm run build). The build output, frontend/dist, holds the app and the earlier
# single-file viewer (viewer.html). Without a build only the API is served.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

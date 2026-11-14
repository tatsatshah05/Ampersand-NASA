"""FastAPI service.  Run:  .venv/bin/uvicorn backend.app:app --reload"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import astrometry, photometry, pipeline, spherex, stars

app = FastAPI(title="SPHEREx sky-change viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
pipeline.FRAMES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/frames", StaticFiles(directory=pipeline.FRAMES_DIR), name="frames")


@app.get("/api/resolve")
def resolve(name: str = Query(..., min_length=1, max_length=80)):
    """Object name to coordinates at 2026.0, with proper motion and parallax when known."""
    try:
        return astrometry.resolve_name(name)
    except astrometry.NameNotFound as e:
        raise HTTPException(404, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The name service did not respond: {e}") from e


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
    try:
        return pipeline.build_frames(ra, dec, fov, detector, mode, pmra=pmra, pmdec=pmdec, parallax=parallax,
                                     pm_epoch=pm_epoch, reference=reference, track=track)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The SPHEREx archive (IRSA) did not respond: {e}") from e


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
    try:
        return stars.field_stars(ra, dec, fov, detector, mode, limit=limit, pmra=pmra, pmdec=pmdec,
                                 parallax=parallax, pm_epoch=pm_epoch, reference=reference, track=track)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The SPHEREx archive (IRSA) did not respond: {e}") from e


@app.get("/api/lightcurve")
def lightcurve(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
               detector: int | None = Query(None, ge=1, le=6, description="one detector only; default all six"),
               pmra: float | None = _PMRA, pmdec: float | None = _PMDEC, parallax: float | None = _PARALLAX,
               pm_epoch: float = _PM_EPOCH):
    """Brightness of the object at (ra, dec) against time, grouped by wavelength bin."""
    try:
        return photometry.lightcurve(ra, dec, detector, pmra=pmra, pmdec=pmdec, parallax=parallax, pm_epoch=pm_epoch)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The SPHEREx archive (IRSA) did not respond: {e}") from e


@app.get("/api/spectrum")
def spectrum(ra: float = Query(..., ge=0, lt=360), dec: float = Query(..., ge=-90, le=90),
             epoch: int | None = Query(None, ge=1, description="epoch number as in /api/frames; default all"),
             detector: int | None = Query(None, ge=1, le=6, description="one detector only; default all six"),
             pmra: float | None = _PMRA, pmdec: float | None = _PMDEC, parallax: float | None = _PARALLAX,
             pm_epoch: float = _PM_EPOCH):
    """Brightness of the object at (ra, dec) against wavelength, one point per exposure."""
    try:
        return photometry.spectrum(ra, dec, epoch, detector, pmra=pmra, pmdec=pmdec, parallax=parallax,
                                   pm_epoch=pm_epoch)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except spherex.ArchiveError as e:
        raise HTTPException(502, f"The SPHEREx archive (IRSA) did not respond: {e}") from e


# The page itself, at "/". Registered last so every /api and /frames route wins.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

"""Distant-world searches run in the background, and the page asks how they are doing.

The same arrangement as `jobs.py` has for the blind search, and on the same single
worker, so that only one heavy job runs at a time on a small server. The first request
for a field starts the search; every request is answered at once with where it stands.
A finished answer is kept on disk by `distant.distant_search`, so it is "done" within a
second the next time, also after a restart.

Nothing here goes to the watchlist: that list holds what the blind search found, and a
planted practice object must never reach it.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from . import distant, jobs, spherex

log = logging.getLogger("backend.distant_jobs")

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _run(job: dict[str, Any], ra: float, dec: float, fov: float, detectors: tuple[int, ...],
         planted: dict | None) -> None:
    job.update(state="running", started=time.time())

    def progress(detector: int) -> None:
        if job["detector_now"] is not None:
            job["detectors_done"] += 1
        job["detector_now"] = detector

    try:
        job["result"] = distant.distant_search(ra, dec, fov, detectors, planted=planted, progress=progress)
        job.update(state="done", detector_now=None, detectors_done=len(detectors))
    except spherex.BadRequest as e:
        job.update(state="failed", error=str(e))
    except spherex.ArchiveError as e:
        job.update(state="failed", error=f"The SPHEREx archive (IRSA) did not respond: {e}")
    except Exception:  # noqa: BLE001 - reported to the page as a fault of this server, and logged in full
        log.exception("distant-world search of %.5f %.5f failed", ra, dec)
        job.update(state="failed", error="Something went wrong on the server during the search. It has been logged.")
    finally:
        job["finished"] = time.time()


def status(ra: float, dec: float, fov: float, detectors: tuple[int, ...],
           planted: dict | None = None) -> dict[str, Any]:
    """Start the distant-world search of this field if nobody has, and say where it stands.

    `planted` is {"level", "seed", "detector"} for a practice round (see `distant.distant_search`):
    the answer is then a simulation and says so.
    """
    if not 0.05 <= fov <= 0.5:
        raise spherex.BadRequest("fov must be between 0.05 and 0.5 degrees")
    if planted is not None and planted["level"] not in distant.training.LEVELS:
        raise spherex.BadRequest(f"plant must be one of {', '.join(distant.training.LEVELS)}")
    key = f"{ra:.5f},{dec:.5f},{fov:.4f},{''.join(map(str, detectors))}"
    if planted is not None:
        key += f",{planted['level']},{planted['seed']},{planted['detector']}"
    with _lock:
        job = _jobs.get(key)
        if job and job["state"] == "failed" and time.time() - job["finished"] > jobs.FORGET_FAILURE_S:
            job = None
        if job is None:
            job = {"state": "queued", "asked": time.time(), "started": None, "finished": None, "detector_now": None,
                   "detectors_done": 0, "result": None, "error": None}
            _jobs[key] = job
            job["future"] = jobs._executor.submit(_run, job, ra, dec, fov, detectors, planted)
            finished = [k for k, j in _jobs.items() if j["state"] in ("done", "failed")]
            for old in finished[:max(0, len(finished) - jobs.KEEP)]:
                del _jobs[old]
    try:
        job["future"].result(timeout=jobs.QUICK_S)
    except FutureTimeout:
        pass
    out: dict[str, Any] = {
        "status": job["state"], "simulation": planted is not None, "ra": ra, "dec": dec, "fov": fov,
        "detectors": list(detectors),
        "seconds": round((job["finished"] or time.time()) - (job["started"] or job["asked"]), 1),
        "detector_now": job["detector_now"], "detectors_done": job["detectors_done"],
        "detectors_total": len(detectors),
    }
    if job["state"] == "done":
        out["result"] = job["result"]
    if job["state"] == "failed":
        out["error"] = job["error"]
    return out

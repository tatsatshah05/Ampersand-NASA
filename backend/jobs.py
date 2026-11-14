"""Blind searches run one at a time in the background, and the page asks how they are doing.

A search of one field takes 20 seconds to a few minutes: too long to keep one web request
open on most hosts, and too heavy to run several at once on a small server. So the first
request for a field starts the search and every request (the first included) is answered
at once with where it stands. Per-detector results are cached on disk by `search`, so a
field that has been searched before is "done" within a second or two, also after a restart.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from . import search, spherex

log = logging.getLogger("backend.jobs")

QUICK_S = 2.5           # a request waits this long for a search that is nearly done (a cached one)
KEEP = 40               # finished searches kept in memory; older ones are rebuilt from the disk cache
FORGET_FAILURE_S = 30   # a failed search may be tried again after this long

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search")
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def parse_detectors(text: str) -> tuple[int, ...]:
    """'56' or '1,2,3' as a tuple of detector numbers, each once, in order."""
    digits = [c for c in text if c not in ", "]
    if not digits or any(c not in "123456" for c in digits):
        raise spherex.BadRequest("detectors must be a list of numbers from 1 to 6, for example 123456 or 56")
    return tuple(sorted({int(c) for c in digits}))


def _run(job: dict[str, Any], ra: float, dec: float, fov: float, detectors: tuple[int, ...]) -> None:
    job.update(state="running", started=time.time())
    try:
        for det in detectors:
            job["detector_now"] = det
            # The same call `search.search_detectors` makes, so its answer is on disk for the line below.
            search.search_field(ra, dec, fov, det, min_sigma=search.COMBINE_SIGMA, fetch=search.fetch_to_own_cache)
            job["detectors_done"] += 1
        job["detector_now"] = None
        job["result"] = search.search(ra, dec, fov, detectors, fetch=search.fetch_to_own_cache)
        job["state"] = "done"
    except spherex.BadRequest as e:
        job.update(state="failed", error=str(e))
    except spherex.ArchiveError as e:
        job.update(state="failed", error=f"The SPHEREx archive (IRSA) did not respond: {e}")
    except Exception:  # noqa: BLE001 - reported to the page as a fault of this server, and logged in full
        log.exception("search of %.5f %.5f failed", ra, dec)
        job.update(state="failed", error="Something went wrong on the server during the search. It has been logged.")
    finally:
        job["finished"] = time.time()


def search_status(ra: float, dec: float, fov: float, detectors: tuple[int, ...]) -> dict[str, Any]:
    """Start the search of this field if nobody has, and say where it stands."""
    if not 0.02 < fov <= 0.5:
        raise spherex.BadRequest("fov must be between 0.02 and 0.5 degrees")
    key = f"{ra:.5f},{dec:.5f},{fov:.4f},{''.join(map(str, detectors))}"
    with _lock:
        job = _jobs.get(key)
        if job and job["state"] == "failed" and time.time() - job["finished"] > FORGET_FAILURE_S:
            job = None
        if job is None:
            job = {"state": "queued", "asked": time.time(), "started": None, "finished": None, "detector_now": None,
                   "detectors_done": 0, "result": None, "error": None}
            _jobs[key] = job
            job["future"] = _executor.submit(_run, job, ra, dec, fov, detectors)
            finished = [k for k, j in _jobs.items() if j["state"] in ("done", "failed")]
            for old in finished[:max(0, len(finished) - KEEP)]:
                del _jobs[old]
    try:
        job["future"].result(timeout=QUICK_S)
    except FutureTimeout:
        pass
    waiting = sum(1 for j in _jobs.values() if j["state"] == "queued" and j["asked"] < job["asked"])
    out: dict[str, Any] = {
        "status": job["state"], "ra": ra, "dec": dec, "fov": fov, "detectors": list(detectors),
        "seconds": round((job["finished"] or time.time()) - (job["started"] or job["asked"]), 1),
        "detector_now": job["detector_now"], "detectors_done": job["detectors_done"],
        "detectors_total": len(detectors), "searches_ahead": waiting if job["state"] == "queued" else 0,
    }
    if job["state"] == "done":
        out["result"] = job["result"]
    if job["state"] == "failed":
        out["error"] = job["error"]
    return out

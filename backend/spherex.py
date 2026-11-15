"""Access to SPHEREx spectral images at IRSA: find exposures, fetch cutouts, cache on disk.

Everything in here was confirmed against the live archive on 2026-11-14 (see the
"Verified facts" section of CLAUDE.md).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.wcs import WCS, FITSFixedWarning

from . import s3fetch

warnings.simplefilter("ignore", FITSFixedWarning)

SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
# Level-2 spectral image collections. DR1 holds the first year; QR3 the newest weeks.
# A new data release is a new name here: set SPHEREX_COLLECTIONS (comma-separated) on the
# server and restart, with no change to the code.
COLLECTIONS = [c.strip() for c in os.environ.get("SPHEREX_COLLECTIONS", "spherex_dr1,spherex_qr3").split(",")
               if c.strip()]
LIST_MAX_AGE_S = 86400.0      # an exposure list older than this is asked for again
LIST_RETRY_S = 600.0          # ... but not more often than this when the archive does not answer
MAX_CONCURRENT = 6       # requests to IRSA at once
S3_IN_HAND = 8           # cutouts being read from S3 at once (each is up to five requests)
# Everything downloaded or built is kept here. SPHEREX_CACHE_DIR moves it: to a
# persistent disk when deployed, or to one shared folder when several checkouts of the
# code run on the same machine.
CACHE = Path(os.environ.get("SPHEREX_CACHE_DIR") or Path(__file__).resolve().parent / "cache")
(CACHE / "cutouts").mkdir(parents=True, exist_ok=True)
(CACHE / "queries").mkdir(parents=True, exist_ok=True)

_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-change-viewer (hackathon project)"
_gate = threading.Semaphore(MAX_CONCURRENT)


class ArchiveError(RuntimeError):
    """IRSA could not be reached or returned something unusable."""


class BadRequest(ValueError):
    """The request asks for something that cannot be done (a mode that does not exist, an
    epoch that was not observed, ...). The API answers it with HTTP 400 and this message;
    any other error is the server's fault and is answered with 500."""


def http_get(url: str, params: dict | None = None, tries: int = 10,
             timeout: float | tuple[float, float] = 90) -> bytes:
    """GET with a concurrency cap and retries.

    `timeout` is in seconds: one number for connecting and for each wait on the answer, or a
    pair (connect, answer) when a dead server should be given up on sooner than a slow one.

    IRSA's front proxy answers roughly one request in three with an immediate
    502, in bursts, so a failed request is normal and is retried with backoff.
    """
    err = "no attempt made"
    for attempt in range(tries):
        with _gate:
            try:
                r = _session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.content
                err = f"HTTP {r.status_code}"
                if r.status_code in (400, 404):
                    break
            except requests.RequestException as e:
                err = type(e).__name__
        time.sleep(min(0.8 * 1.6 ** attempt, 12))
    raise ArchiveError(f"{err} from {url}")


def write_json(path: Path, obj: object, indent: int | None = None) -> None:
    """Write a cache file so that no reader ever sees half of it.

    The server and the warm-up script can build the same entry at the same moment; a
    plain write would let one of them read a truncated file. Writing to a private
    temporary name and renaming is atomic.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(obj, indent=indent))
    tmp.replace(path)


_list_refresh: dict[str, float] = {}      # exposure lists being refreshed in the background: key -> when started
_list_refresh_lock = threading.Lock()


def _list_file(ra: float, dec: float) -> Path:
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f}".encode()).hexdigest()[:16]
    return CACHE / "queries" / f"sia_{key}.json"


def list_changed(ra: float, dec: float, built_with: int | None) -> bool:
    """Has the archive listed a different number of exposures for this position than a
    cached result was built with? This is how new SPHEREx data reaches views that are
    already on disk.

    It never waits for the archive. With a list less than a day old the answer is read
    from disk. With an older one the answer is "no" for now, so the cached result is
    served at once, and the list is asked for again in the background; the next request
    then sees the new list and rebuilds if it differs.
    """
    cache_file = _list_file(ra, dec)
    if built_with is None or not cache_file.exists():
        return False
    if time.time() - cache_file.stat().st_mtime >= LIST_MAX_AGE_S:
        with _list_refresh_lock:
            due = time.time() - _list_refresh.get(cache_file.name, 0.0) >= LIST_RETRY_S
            if due:
                _list_refresh[cache_file.name] = time.time()
        if due:
            threading.Thread(target=_refresh_list, args=(ra, dec), daemon=True, name="exposure-list").start()
        return False
    return len(find_exposures(ra, dec)) != built_with


def _refresh_list(ra: float, dec: float) -> None:
    try:
        find_exposures(ra, dec)
    except ArchiveError:
        pass            # tried again after LIST_RETRY_S; the cached results stay in use meanwhile


def find_exposures(ra: float, dec: float, max_age_s: float = LIST_MAX_AGE_S) -> list[dict]:
    """Every level-2 spectral image whose footprint contains (ra, dec), oldest first.

    The list is cached for a day, because new exposures keep arriving. If the archive
    cannot be reached when the list is due for a refresh, the older list is used: it
    only lacks the newest exposures, and that is better than refusing a view whose
    images are all on disk already.
    """
    cache_file = _list_file(ra, dec)
    cached = json.loads(cache_file.read_text()) if cache_file.exists() else None
    if cached is not None and time.time() - cache_file.stat().st_mtime < max_age_s:
        return cached
    try:
        exposures = _query_exposures(ra, dec)
    except ArchiveError:
        if cached is not None:
            return cached
        raise
    write_json(cache_file, exposures)
    return exposures


def _query_exposures(ra: float, dec: float) -> list[dict]:
    """Ask the archive's image search, in every collection, which images cover the point."""
    seen: dict[tuple[str, int], dict] = {}
    for coll in COLLECTIONS:
        raw = http_get(SIA_URL, {"COLLECTION": coll, "POS": f"circle {ra} {dec} 0.01"})
        table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
        for row in table:
            det = int(str(row["energy_bandpassname"])[-1])  # "SPHEREx-D3" -> 3
            obs_id = str(row["obs_id"])
            exp = {
                "obs_id": obs_id,
                "detector": det,
                "mjd": float(row["t_min"]),
                "exptime": float(row["t_exptime"]),
                "url": str(row["access_url"]),
                "collection": str(row["obs_collection"]),
                "wave_min": float(row["em_min"]) * 1e6,
                "wave_max": float(row["em_max"]) * 1e6,
            }
            seen.setdefault((obs_id, det), exp)  # an exposure in two releases counts once
    return sorted(seen.values(), key=lambda e: e["mjd"])


def _cutout_path(exp: dict, ra: float, dec: float, size_deg: float) -> Path:
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size_deg:.4f}".encode()).hexdigest()[:10]
    return CACHE / "cutouts" / tag / f"{exp['obs_id']}_D{exp['detector']}.fits"


def use_s3() -> bool:
    """Read cutouts from the public S3 bucket first? SPHEREX_USE_S3=0 turns it off."""
    return os.environ.get("SPHEREX_USE_S3", "1") != "0"


def fetch_cutout(exp: dict, ra: float, dec: float, size_deg: float, path: Path | None = None) -> Path:
    """Get one cutout (if not cached) and store a slimmed copy.

    Two routes give the same file, byte for byte (`scripts/check_s3.py` proves it):
    - the public S3 copy of the archive, reading only the image rows needed
      (`backend/s3fetch.py`): about 0.13 s per cutout with 16 requests in flight;
    - IRSA's cutout service: about 4 MB per cutout, nearly all of it the EPSF table,
      about 0.7 s each at six in parallel, and one request in three refused.
    S3 is tried first and IRSA is the fallback, so a cutout is only reported as failed
    when both routes failed.

    The cached copy keeps IMAGE, FLAGS, VARIANCE and ZODI, and replaces the WCS-WAVE
    lookup table with two per-pixel images, WAVE and BANDWIDTH (microns). About 260 kB
    at 0.15 deg.

    `path` puts the file somewhere else than the shared cutout folder (a feature that keeps
    its own cutouts apart, such as `backend/follow.py`).
    """
    path = path or _cutout_path(exp, ra, dec, size_deg)
    if path.exists():
        return path
    if use_s3():
        try:
            return s3fetch.fetch_cutout(exp, ra, dec, size_deg, path)
        except Exception:  # noqa: BLE001 - whatever went wrong there, IRSA still has the cutout
            pass
    raw = http_get(f"{exp['url']}?center={ra:.6f},{dec:.6f}&size={size_deg:.5f}")
    with fits.open(io.BytesIO(raw)) as hdul:
        header = hdul["IMAGE"].header
        ny, nx = hdul["IMAGE"].data.shape
        # Alternate WCS "W" is a -TAB lookup into the WCS-WAVE extension: axis 1 is
        # the central wavelength, axis 2 the bandwidth, both in microns.
        spectral = WCS(header, fobj=hdul, key="W")
        spectral.sip = None
        xx, yy = np.meshgrid(np.arange(nx), np.arange(ny))
        wave, band = spectral.wcs_pix2world(xx, yy, 0)
        out = fits.HDUList([fits.PrimaryHDU()])
        for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
            out.append(fits.ImageHDU(hdul[name].data, header=hdul[name].header, name=name))
        out.append(fits.ImageHDU(wave.astype("float32"), name="WAVE"))
        out.append(fits.ImageHDU(band.astype("float32"), name="BANDWIDTH"))
        path.parent.mkdir(parents=True, exist_ok=True)
        # Process and thread in the name: two processes may fetch the same cutout at once.
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        out.writeto(tmp, overwrite=True)
        tmp.replace(path)
    return path


def fetch_cutouts(exposures: list[dict], ra: float, dec: float, size_deg: float,
                  progress=None) -> list[tuple[dict, Path | None, str | None]]:
    """Fetch many cutouts, a few at a time.

    S3 reads share one connection pool with its own cap on requests in flight; IRSA
    requests are still limited to MAX_CONCURRENT by `http_get`, whatever the number
    of cutouts in hand here.

    Returns (exposure, path, error) for each. A cutout that could not be fetched
    has path None and a reason; it is reported, never replaced with anything.
    """
    def one(exp):
        try:
            return exp, fetch_cutout(exp, ra, dec, size_deg), None
        except Exception as e:  # noqa: BLE001 - report every failure to the caller
            return exp, None, f"{type(e).__name__}: {e}"

    results = []
    with ThreadPoolExecutor(S3_IN_HAND if use_s3() else MAX_CONCURRENT) as pool:
        for n, res in enumerate(pool.map(one, exposures), 1):
            results.append(res)
            if progress:
                progress(n, len(exposures))
    return results

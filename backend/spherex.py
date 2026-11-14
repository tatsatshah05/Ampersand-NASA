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

warnings.simplefilter("ignore", FITSFixedWarning)

SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
# Level-2 spectral image collections. DR1 holds the first year; QR3 the newest weeks.
COLLECTIONS = ["spherex_dr1", "spherex_qr3"]
MAX_CONCURRENT = 6
CACHE = Path(__file__).resolve().parent / "cache"
(CACHE / "cutouts").mkdir(parents=True, exist_ok=True)
(CACHE / "queries").mkdir(parents=True, exist_ok=True)

_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-change-viewer (hackathon project)"
_gate = threading.Semaphore(MAX_CONCURRENT)


class ArchiveError(RuntimeError):
    """IRSA could not be reached or returned something unusable."""


def http_get(url: str, params: dict | None = None, tries: int = 10, timeout: float = 90) -> bytes:
    """GET with a concurrency cap and retries.

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


def find_exposures(ra: float, dec: float, max_age_s: float = 86400) -> list[dict]:
    """Every level-2 spectral image whose footprint contains (ra, dec), oldest first."""
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f}".encode()).hexdigest()[:16]
    cache_file = CACHE / "queries" / f"sia_{key}.json"
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < max_age_s:
        return json.loads(cache_file.read_text())

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
    exposures = sorted(seen.values(), key=lambda e: e["mjd"])
    write_json(cache_file, exposures)
    return exposures


def _cutout_path(exp: dict, ra: float, dec: float, size_deg: float) -> Path:
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size_deg:.4f}".encode()).hexdigest()[:10]
    return CACHE / "cutouts" / tag / f"{exp['obs_id']}_D{exp['detector']}.fits"


def fetch_cutout(exp: dict, ra: float, dec: float, size_deg: float) -> Path:
    """Download one cutout (if not cached) and store a slimmed copy.

    IRSA's cutout is about 4 MB, nearly all of it the EPSF table. The cached copy
    keeps IMAGE, FLAGS, VARIANCE and ZODI, and replaces the WCS-WAVE lookup table
    with two per-pixel images, WAVE and BANDWIDTH (microns). About 260 kB at 0.15 deg.
    """
    path = _cutout_path(exp, ra, dec, size_deg)
    if path.exists():
        return path
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
    """Fetch many cutouts, at most MAX_CONCURRENT at a time.

    Returns (exposure, path, error) for each. A cutout that could not be fetched
    has path None and a reason; it is reported, never replaced with anything.
    """
    def one(exp):
        try:
            return exp, fetch_cutout(exp, ra, dec, size_deg), None
        except Exception as e:  # noqa: BLE001 - report every failure to the caller
            return exp, None, f"{type(e).__name__}: {e}"

    results = []
    with ThreadPoolExecutor(MAX_CONCURRENT) as pool:
        for n, res in enumerate(pool.map(one, exposures), 1):
            results.append(res)
            if progress:
                progress(n, len(exposures))
    return results

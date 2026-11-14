"""Shared helpers for the scripts/verify_*.py checks (independent re-measurement of the demo claims).

These scripts read the cached SPHEREx cutouts directly and measure things their own way, so that
agreement with the backend means something. Nothing here simulates, interpolates or tunes data.

Set SPHEREX_CACHE_DIR to the cache that holds the downloaded cutouts (default: backend/cache).
The helpers never contact the SPHEREx archive: a cutout that is not cached is simply not used.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import warnings
from pathlib import Path

import numpy as np
import requests
from astropy.coordinates import get_body_barycentric
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning
from astropy.wcs.utils import proj_plane_pixel_area
from scipy.special import erf

warnings.simplefilter("ignore", FITSFixedWarning)

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("SPHEREX_CACHE_DIR") or ROOT / "backend" / "cache")
DOCS = ROOT / "docs" / "verification"
CUTOUT_DEG = 0.15            # the size the backend's photometry cutouts were fetched at
EPOCH_GAP_DAYS = 30.0        # same rule as the backend: a longer gap starts a new visit

# Flag bits, Table 16 of the SPHEREx Explanatory Supplement v2.1 (2026-11-10).
BIT = {"TRANSIENT": 0, "OVERFLOW": 1, "SUR_ERROR": 2, "NONFUNC": 6, "DICHROIC": 7, "MISSING_DATA": 9,
       "HOT": 10, "COLD": 11, "FULLSAMPLE": 12, "PHANMISS": 14, "NONLINEAR": 15, "PERSIST": 17,
       "OUTLIER": 19, "CROSSTALK": 20, "SOURCE": 21, "GHOST": 22, "GHOST_FPA": 23, "GHOST_EXT": 24,
       "STREAK": 25, "BLOOM": 26, "SNOWBALL": 27, "HALO": 28, "SATELLITE_HALO": 29}


def bits(*names: str) -> int:
    return sum(1 << BIT[n] for n in names)


# The Supplement's list for photometry (Sect. 3.3), plus TRANSIENT (cosmic-ray hit during the
# exposure) and the other defect bits: for a faint source every doubtful pixel is left out.
BAD_FAINT = bits("TRANSIENT", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD", "PHANMISS",
                 "NONLINEAR", "PERSIST", "CROSSTALK", "STREAK", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO")
# The Supplement's photometry list exactly (used for bright stars, where TRANSIENT is often
# raised by the star itself).
BAD_PHOT = bits("SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST", "BLOOM",
                "SNOWBALL", "HALO", "SATELLITE_HALO")


def cutout_dir(ra: float, dec: float, size_deg: float = CUTOUT_DEG) -> Path:
    """Folder the backend cached the cutouts for this centre in (same naming rule as backend/spherex.py)."""
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size_deg:.4f}".encode()).hexdigest()[:10]
    return CACHE / "cutouts" / tag


def list_cutouts(ra: float, dec: float, detector: int | None = None) -> list[Path]:
    folder = cutout_dir(ra, dec)
    pattern = f"*_D{detector}.fits" if detector else "*_D?.fits"
    return sorted(folder.glob(pattern))


def read_cutout(path: Path) -> dict:
    """One cached cutout: zodi-subtracted image (MJy/sr), variance, flags, wavelength map, WCS."""
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = hdul["FLAGS"].data.astype("int64")
        variance = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data.astype("float64")
        band = hdul["BANDWIDTH"].data.astype("float64")
    wcs = WCS(header)
    with np.errstate(invalid="ignore"):
        impossible = image < -10.0 * np.sqrt(variance)     # unflagged glitches far below zero
    data = image - zodi
    data[impossible] = np.nan
    return {"path": path, "obs_id": str(header["OBSID"]), "detector": int(header["DETECTOR"]),
            "mjd": float(header["MJD-AVG"]), "data": data, "raw": image, "variance": variance, "flags": flags,
            "wave": wave, "band": band, "wcs": wcs, "header": header,
            "mjy_per_unit": float(proj_plane_pixel_area(wcs)) * (np.pi / 180.0) ** 2 * 1e9}  # MJy/sr x pixel -> mJy


def all_mjds(ra: float, dec: float) -> dict[str, float]:
    """MJD of every cached cutout of a target (all detectors), keyed by file name. Cached in memory."""
    key = (round(ra, 5), round(dec, 5))
    if key not in _MJDS:
        out = {}
        for p in list_cutouts(ra, dec):
            out[p.name] = float(fits.getval(p, "MJD-AVG", "IMAGE"))
        _MJDS[key] = out
    return _MJDS[key]


_MJDS: dict[tuple[float, float], dict[str, float]] = {}


def epoch_edges(ra: float, dec: float) -> list[float]:
    """Start MJD of each visit, from the exposures of every detector (gap of more than 30 days)."""
    mjds = sorted(all_mjds(ra, dec).values())
    starts = [mjds[0]]
    for a, b in zip(mjds, mjds[1:], strict=False):
        if b - a > EPOCH_GAP_DAYS:
            starts.append(b)
    return starts


def epoch_of(mjd: float, starts: list[float]) -> int:
    """Visit number, 1-based."""
    return int(np.searchsorted(starts, mjd + 1e-9, side="right"))


def iso(mjd: float) -> str:
    return Time(mjd, format="mjd").iso[:10]


def offset_arcsec(ra1, dec1, ra2, dec2):
    """Offset of point 2 from point 1 as (east, north) in arcseconds (small angles)."""
    east = (np.asarray(ra2) - ra1) * np.cos(np.radians(0.5 * (np.asarray(dec2) + dec1))) * 3600.0
    north = (np.asarray(dec2) - dec1) * 3600.0
    return east, north


def shift_radec(ra: float, dec: float, east_arcsec: float, north_arcsec: float) -> tuple[float, float]:
    return ra + east_arcsec / 3600.0 / np.cos(np.radians(dec)), dec + north_arcsec / 3600.0


def apparent_position(ra0: float, dec0: float, epoch0: float, pmra: float, pmdec: float, parallax: float,
                      mjd: float) -> tuple[float, float]:
    """Where an object is seen from Earth on a date: written independently of backend/astrometry.py.

    (ra0, dec0) is the barycentric direction at Julian year epoch0; pmra includes cos(dec); mas/yr, mas.
    Linear proper motion, then the direction of (object vector minus Earth vector) for parallax,
    with exact vectors instead of the first-order formula the backend uses.
    """
    t = Time(mjd, format="mjd")
    dt = t.jyear - epoch0
    dec = dec0 + pmdec * dt / 3.6e6
    ra = ra0 + pmra * dt / 3.6e6 / np.cos(np.radians(dec0))
    if not parallax or parallax <= 0:
        return float(ra), float(dec)
    dist_au = 206264.806 / (parallax / 1000.0)
    a, d = np.radians(ra), np.radians(dec)
    star = dist_au * np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])
    earth = get_body_barycentric("earth", t).xyz.to_value("au")
    v = star - earth
    return float(np.degrees(np.arctan2(v[1], v[0])) % 360.0), float(np.degrees(np.arcsin(v[2] / np.linalg.norm(v))))


def gauss_pixel(xx: np.ndarray, yy: np.ndarray, x0: float, y0: float, sigma: float) -> np.ndarray:
    """Share of a unit-flux round Gaussian that falls in each pixel (pixel centres at integers)."""
    s = np.sqrt(2.0) * sigma
    gx = 0.5 * (erf((xx + 0.5 - x0) / s) - erf((xx - 0.5 - x0) / s))
    gy = 0.5 * (erf((yy + 0.5 - y0) / s) - erf((yy - 0.5 - y0) / s))
    return gx * gy


def vega_to_mjy(mag: float, zero_jy: float) -> float:
    return zero_jy * 1e3 * 10.0 ** (-0.4 * mag)


# Zero-magnitude flux densities (Jy). WISE: Jarrett et al. 2011 / WISE Explanatory Supplement
# (for a nu^-2 spectrum). 2MASS: Cohen et al. 2003.
ZERO_JY = {"W1": 309.540, "W2": 171.787, "J": 1594.0, "H": 1024.0, "Ks": 666.7}
EFF_UM = {"W1": 3.3526, "W2": 4.6028, "J": 1.235, "H": 1.662, "Ks": 2.159}

_session = requests.Session()
_session.headers["User-Agent"] = "astro-catalogue-check/1.0 (python-requests)"   # generic: no project details


def http_get(url: str, params: dict | None = None, tries: int = 3, timeout: float = 60) -> requests.Response | None:
    """GET from an outside service with a generic client name. Returns None if it cannot be reached."""
    for k in range(tries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} from {url}")
        except requests.RequestException as e:
            print(f"  {type(e).__name__} from {url}")
        time.sleep(2 + 3 * k)
    return None


VIZIER = ("https://vizier.cfa.harvard.edu/viz-bin/asu-tsv", "https://vizier.cds.unistra.fr/viz-bin/asu-tsv")


def vizier(source: str, ra: float, dec: float, radius_arcsec: float, columns: str, save_as: Path | None = None,
           max_rows: int = 2000) -> list[dict] | None:
    """Rows of a VizieR table around a position, as dictionaries of strings. None if no mirror answered.

    The answer is cached in save_as (when given), so a re-run does not need the network.
    """
    if save_as is not None and save_as.exists():
        return json.loads(save_as.read_text())
    for base in VIZIER:
        r = http_get(base, {"-source": source, "-c": f"{ra:.6f} {dec:+.6f}", "-c.rs": radius_arcsec,
                            "-out": columns, "-out.max": max_rows, "-sort": "_r", "-out.add": "_r"})
        if r is None:
            continue
        lines = [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]
        if len(lines) < 4:
            continue                      # header only: this mirror gave no rows
        names = lines[0].split("\t")
        rows = [dict(zip(names, [v.strip() for v in ln.split("\t")], strict=False)) for ln in lines[3:]]
        if save_as is not None:
            save_as.parent.mkdir(parents=True, exist_ok=True)
            save_as.write_text(json.dumps(rows, indent=0))
        return rows
    return None


AAVSO_API = "https://vsx.aavso.org/index.php"     # AAVSO's documented data interface (www.aavso.org refuses scripts)


def aavso(star: str, jd0: float, jd1: float, save_as: Path) -> list[dict] | None:
    """AAVSO International Database observations of a star between two Julian dates.

    Each row: jd, mjd, mag, err, band, observer, kind (Visual / CCD / DSLR ...), fainter_than.
    The raw answer is kept in save_as. None if AAVSO cannot be reached.
    """
    if not save_as.exists():
        r = http_get(AAVSO_API, {"view": "api.delim", "ident": star, "fromjd": f"{jd0:.1f}", "tojd": f"{jd1:.1f}",
                                 "delimiter": "@@@"}, tries=2, timeout=120)
        if r is None or "@@@" not in r.text[:200]:
            return None
        save_as.parent.mkdir(parents=True, exist_ok=True)
        save_as.write_text(r.text, encoding="utf-8")
    rows = []
    with open(save_as, encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("@@@")
        for ln in fh:
            parts = ln.rstrip("\n").split("@@@")
            if len(parts) < len(header):
                continue
            row = dict(zip(header, parts, strict=False))
            mag, jd = num(row["mag"]), num(row["JD"])
            if mag is None or jd is None:
                continue
            rows.append({"jd": jd, "mjd": jd - 2400000.5, "mag": mag, "err": num(row["uncert"]), "band": row["band"],
                         "observer": row["by"], "kind": row["obsType"], "fainter_than": row["fainterThan"] == "1"})
    return rows


def num(text: str | None) -> float | None:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None

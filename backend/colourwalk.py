# ruff: noqa: E501
"""Colour-walk astrometry: does a star's image centre move with wavelength?

SPHEREx looks at every star through 102 narrow colours. In one exposure the star is seen through
one colour, with the same optics as every other star at that spot on the detector. A lone star
therefore sits at the same place in every colour. A star with a cool companion a few arcseconds
away (bright at 3 to 5 micrometres, dark at 1) has its image centre pulled toward the companion
as the colour gets redder. The direction of that pull is the direction of the companion, and a
fit with two sources at that direction gives the companion's brightness in each colour.

The technique, colour-induced displacement, is old (Wielen 1996; Pourbaix et al. 2004 used it
on five SDSS bands). Forced photometry at a known position is an existing IRSA tool. What this
module does is apply the old idea to SPHEREx's narrow colours without being told where the
companion is. Every number it returns is measured on exposures; nothing is simulated.

Conventions: offsets are measured minus Gaia, in arcseconds East and North; a position angle is
atan2(East, North) in degrees, 0 to 360, North through East.
"""
from __future__ import annotations

import hashlib
import io
import json
import multiprocessing
import os
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.wcs import WCS
from scipy.optimize import least_squares
from scipy.special import erf

from . import astrometry, photometry, pipeline, search, spherex

# ---------------------------------------------------------------- analysis choices, fixed before any run
BIN_EDGES = [0.75, 0.95, 1.12, 1.4, 1.65, 2.0, 2.43, 2.9, 3.4, 3.85, 4.15, 4.43, 4.7, 5.02]   # micrometres
SHORT = (0.75, 1.65)         # the "blue" group of the walk
LONG = (2.9, 5.02)           # the "red" group
FLOOR_ARCSEC = 0.04          # the first guess of the floor; now used only by the null test, to show it was too low
# Measured on 19 isolated stars of the Barnard field (scripts/check_colourwalk.py): the star-to-star scatter of
# per-detector median offsets. Added in quadrature to each group's error for a host.
FLOOR_EAST = 0.049
FLOOR_NORTH = 0.066
HALF = 3                     # 7 x 7 pixel fit box; the central 3 x 3 must be clean
WIDTH_RANGE = (0.25, 1.6)    # allowed Gaussian sigma in pixels
SCAN_ARCSEC = [2.0 + 0.5 * i for i in range(21)]     # 2 to 12 arcsec
LIMIT_SEPARATIONS = [3.0, 5.0, 8.0, 10.0]
CONTROL_ANGLES = (90.0, 180.0, 270.0)
CONTROL_MAX = 0.02           # a control above this is a failed control
WALK_SIGMA = 4.0
DETECTOR_PA_AGREE = 30.0     # D4, D5 and D6 must agree within this many degrees
MJY_PER_PIXEL_SR = 6.15 ** 2 / 206264.806 ** 2 * 1e9   # MJy/sr x pixel area -> mJy
NEIGHBOUR_RADIUS = 25.0      # arcsec, Gaia neighbours listed
CATALOGUE_MATCH = 4.0        # arcsec: a catalogued source this close to the inferred place is "already known"
GAIA_G_LIMIT = 21.0
NEIGHBOUR_DELTA_G = 4.0          # a Gaia neighbour more than this many magnitudes fainter than the host cannot explain a walk
NEIGHBOUR_WINDOW = (2.0, 20.0)  # arcsec: Gaia neighbours that can explain a walk (the 7 x 7 box reaches 18.5)
# IRSA Gator catalogues (the CfA VizieR TAP address used first returned HTTP 404): name -> (catalogue, ra, dec, mag)
CATALOGUES = {"2MASS": ("fp_psc", "ra", "dec", "k_m"),
              "AllWISE": ("allwise_p3as_psd", "ra", "dec", "w2mpro"),
              "CatWISE2020": ("catwise_2020", "ra_pm", "dec_pm", "w2mpro_pm")}
# Calibrated on the Barnard field (scripts/check_colourwalk.py): the Gaussian width, in arcsec, of the
# response of the fitted centre to a neighbour at a given separation. Replaced by the measured value there.
RESPONSE_SCALE_ARCSEC = 4.5

# Pixels the fit refuses: the photometry mask plus the bits that mark transients, cross-talk, ghosts, streaks and outliers.
FIT_BAD = photometry.PHOTOMETRY_BAD | pipeline._mask("TRANSIENT", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
                                                      "STREAK", "OUTLIER")
VISIT_GAP_DAYS = 30.0        # exposures further apart than this belong to different visits
PA_SCAN_STEP = 15.0          # degrees: the two-source fit at a fixed separation is repeated all the way round

CACHE = spherex.CACHE
EPOCH_MJD = 61000.0          # 2025-06; neighbours are placed at this date when asking where they lie

CAUTIONS = [
    "A red background source (galaxy, reddened giant, brown dwarf in the background) walks the image centre "
    "exactly as a companion does. Only a common-motion check (an older catalogue position against SPHEREx's) "
    "separates a companion from a background source.",
    "Hosts brighter than K about 7 saturate in detectors 1 to 4; hosts fainter than K about 12 give walks too "
    "noisy to use.",
    "The fitted centre responds to a neighbour less than the flux-weighted shift. At separations under about 9 "
    "arcsec the walk is smaller than ratio x separation; the two-source fit handles this but its ratios are rough, "
    "and at 4.4 to 5 micrometres they run 30 to 40 per cent below AllWISE's deblended values on the one test object.",
    "Under about 2.5 arcsec the walk is below the 0.04 arcsec systematic floor for any companion of ordinary "
    "contrast: close-in planets are out of reach.",
    "A walk toward a source that Gaia, 2MASS, AllWISE or CatWISE already lists means a known source is the cause; "
    "it is not a new finding.",
]

METHOD = (
    "For every exposure that covers the host, the host's place is predicted from Gaia (proper motion and parallax "
    "at the exposure's date). A pixel-integrated Gaussian is fitted in a 7 x 7 pixel box (free flux, x, y, width "
    "and background, weights from the pipeline's variance) and the offset from the Gaia place is converted to "
    "arcsec East and North with the local WCS. The offsets are grouped by wavelength. The walk is the median offset "
    "at 2.9 to 5 micrometres minus the median at 0.75 to 1.65, with 0.04 arcsec added in quadrature to each group "
    "for what the astrometry cannot do. Its direction is the companion's position angle. A second fit then adds a "
    "companion at that direction, scanning its separation from 2 to 12 arcsec, and the same fit is repeated with the "
    "companion turned by 90, 180 and 270 degrees: those controls measure what the extended wings of the image fake. "
    "The companion-to-host flux ratio is the fit at the walk direction minus the median of the controls."
)


# ---------------------------------------------------------------- small arithmetic, tested offline
def position_angle(east: float, north: float) -> float:
    """Position angle in degrees, 0 to 360, North through East."""
    return float(np.degrees(np.arctan2(east, north)) % 360.0)


def angle_difference(a: float, b: float) -> float:
    """Smallest absolute difference between two angles in degrees (0 to 180)."""
    return float(abs((a - b + 180.0) % 360.0 - 180.0))


def components(east: float, north: float, pa: float) -> tuple[float, float]:
    """(along, across) of an (East, North) vector relative to a position angle."""
    s, c = np.sin(np.radians(pa)), np.cos(np.radians(pa))
    return float(east * s + north * c), float(-east * c + north * s)


def offset_at(sep: float, pa: float) -> tuple[float, float]:
    """(East, North) of a point at separation `sep` and position angle `pa`."""
    return float(sep * np.sin(np.radians(pa))), float(sep * np.cos(np.radians(pa)))


def control_angles(pa: float) -> list[float]:
    """The three control position angles: PA + 90, + 180, + 270, each in 0 to 360."""
    return [float((pa + a) % 360.0) for a in CONTROL_ANGLES]


def photocentre(fluxes: list[float], east: list[float], north: list[float]) -> tuple[float, float]:
    """Flux-weighted centre of several point sources, as (East, North). Source 0 is usually the host."""
    f = np.asarray(fluxes, float)
    return float(np.sum(f * np.asarray(east, float)) / f.sum()), float(np.sum(f * np.asarray(north, float)) / f.sum())


def robust(x) -> tuple[float, float, int]:
    """Median, its error 1.2533 x 1.4826 x MAD / sqrt(n), and n; NaNs dropped."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return float("nan"), float("nan"), int(len(x))
    m = float(np.median(x))
    return m, float(1.2533 * 1.4826 * np.median(np.abs(x - m)) / np.sqrt(len(x))), int(len(x))


def psf(x, y, s, xx, yy):
    """Pixel-integrated circular Gaussian of unit flux centred at (x, y), sampled on pixels xx, yy."""
    sq = np.sqrt(2.0) * s
    return 0.25 * (erf((xx + 0.5 - x) / sq) - erf((xx - 0.5 - x) / sq)) * (erf((yy + 0.5 - y) / sq) - erf((yy - 0.5 - y) / sq))


def local_jacobian(wcs: WCS, x: float, y: float) -> np.ndarray:
    """2 x 2 matrix: pixel offset (dx, dy) -> sky offset (East, North) in arcsec. East is toward larger RA."""
    r0 = np.array(wcs.all_pix2world(x, y, 0))
    r1 = np.array(wcs.all_pix2world(x + 1, y, 0))
    r2 = np.array(wcs.all_pix2world(x, y + 1, 0))
    cosd = np.cos(np.radians(r0[1]))
    return np.array([[(r1[0] - r0[0]) * cosd, (r2[0] - r0[0]) * cosd], [r1[1] - r0[1], r2[1] - r0[1]]]) * 3600.0


def fit_star(data, var, bad, x0, y0, comp=None):
    """Fit one star in a 7 x 7 box around (x0, y0).

    comp: None for one source, or (dx, dy) in pixels for a second source at that fixed offset (same width,
    free flux). Returns (parameters, errors, reduced chi2, chi2 sum) or None when the box is unusable.
    Parameters: [flux, x, y, sigma, background] plus [companion flux] for two sources.
    """
    xi, yi = int(round(x0)), int(round(y0))
    ny, nx = data.shape
    if not (HALF <= xi < nx - HALF and HALF <= yi < ny - HALF):
        return None
    sl = (slice(yi - HALF, yi + HALF + 1), slice(xi - HALF, xi + HALF + 1))
    win, vw, bw = data[sl], var[sl], bad[sl]
    if bw[HALF - 1:HALF + 2, HALF - 1:HALF + 2].any() or (~bw).sum() < 30:
        return None
    yy, xx = np.mgrid[yi - HALF:yi + HALF + 1, xi - HALF:xi + HALF + 1]
    good = ~bw
    sig = np.sqrt(np.clip(vw, 1e-12, None))
    a0 = max(float(np.nansum(np.where(good, win, 0.0))), 1e-6)
    lo_s, hi_s = WIDTH_RANGE
    if comp is None:
        def resid(p):
            return ((p[0] * psf(p[1], p[2], p[3], xx, yy) + p[4] - win) / sig)[good]
        p0 = [a0, x0, y0, 0.45, 0.0]
        lo = [0, x0 - 1.5, y0 - 1.5, lo_s, -np.inf]
        hi = [np.inf, x0 + 1.5, y0 + 1.5, hi_s, np.inf]
    else:
        dx, dy = comp

        def resid(p):
            model = p[0] * psf(p[1], p[2], p[3], xx, yy) + p[5] * psf(p[1] + dx, p[2] + dy, p[3], xx, yy) + p[4]
            return ((model - win) / sig)[good]
        p0 = [a0, x0, y0, 0.45, 0.0, 0.05 * a0]
        lo = [0, x0 - 1.5, y0 - 1.5, lo_s, -np.inf, -np.inf]
        hi = [np.inf, x0 + 1.5, y0 + 1.5, hi_s, np.inf, np.inf]
    try:
        r = least_squares(resid, p0, bounds=(lo, hi))
        cov = np.linalg.inv(r.jac.T @ r.jac)
    except Exception:  # noqa: BLE001 - a singular or failed fit is simply not a measurement
        return None
    chi2 = 2 * r.cost / max(int(good.sum()) - len(p0), 1)
    return r.x, np.sqrt(np.diag(cov)) * np.sqrt(max(chi2, 1.0)), chi2, 2 * r.cost


def read_cutout(path) -> dict:
    """Open a cached cutout and return the arrays the fits need."""
    with fits.open(path) as h:
        hd = h["IMAGE"].header
        img = h["IMAGE"].data.astype(float) - h["ZODI"].data.astype(float)
        var = h["VARIANCE"].data.astype(float)
        flg = h["FLAGS"].data
        wave = np.array(h["WAVE"].data, float)
    bad = ((flg & FIT_BAD) != 0) | pipeline.impossible_pixels(img, var) | ~np.isfinite(img) | ~np.isfinite(var)
    data = img - np.nanmedian(img[~bad])
    return {"data": data, "var": var, "bad": bad, "wave": wave, "wcs": WCS(hd), "mjd": float(hd["MJD-AVG"]),
            "det": int(hd["DETECTOR"])}


# ---------------------------------------------------------------- catalogues (cached, one query per target)
def _cached_query(prefix: str, key: str, url: str, params: dict, *, tries: int = 6) -> bytes:
    path = CACHE / "queries" / f"{prefix}_{hashlib.sha1(key.encode()).hexdigest()[:16]}.vot"
    if path.exists():
        return path.read_bytes()
    raw = spherex.http_get(url, params, tries=tries, timeout=90)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _num(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def gaia_neighbours(ra: float, dec: float, radius_arcsec: float = 60.0, g_limit: float = GAIA_G_LIMIT) -> list[dict]:
    """Gaia DR3 sources within the radius (epoch 2016.0 positions), with proper motion, parallax and G, BP, RP."""
    query = ("SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag AS g, phot_bp_mean_mag AS bp, "
             "phot_rp_mean_mag AS rp FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
             f"CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec / 3600.0})) AND phot_g_mean_mag < {g_limit}")
    raw = _cached_query("cwgaia", f"{ra:.5f},{dec:.5f},{radius_arcsec:.1f},{g_limit}", astrometry.GAIA_TAP,
                        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query})
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    rows = []
    for r in table:
        rows.append({"source_id": str(r["source_id"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
                     "pmra": _num(r["pmra"]), "pmdec": _num(r["pmdec"]), "parallax": _num(r["parallax"]),
                     "gmag": _num(r["g"]), "bp": _num(r["bp"]), "rp": _num(r["rp"])})
    return rows


def catalogue_sources(ra: float, dec: float, radius_arcsec: float = 20.0) -> dict[str, list[dict]]:
    """2MASS, AllWISE and CatWISE2020 sources within the radius (IRSA Gator, cached on disk). A catalogue that
    did not answer is reported as [{'error': ...}], never as an empty list; see `catalogues_failed`."""
    out: dict[str, list[dict]] = {}
    for name, (cat, c_ra, c_dec, c_mag) in CATALOGUES.items():
        key = hashlib.sha1(f"{ra:.5f},{dec:.5f},{radius_arcsec:.1f}".encode()).hexdigest()[:16]
        path = CACHE / "queries" / f"cwcat2_{name}_{key}.json"
        try:
            if path.exists():
                out[name] = json.loads(path.read_text())
                continue
            table = search._gator(cat, ra, dec, radius_arcsec / 3600.0, f"{c_ra},{c_dec},{c_mag}")
            rows = []
            for r in table:
                e, n = astrometry.offset_arcsec(ra, dec, float(r[c_ra]), float(r[c_dec]))
                rows.append({"east": round(e, 2), "north": round(n, 2), "mag": _num(r[c_mag])})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rows))
            out[name] = rows
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            out[name] = [{"error": f"{type(exc).__name__}: {exc}"}]
    return out


def catalogues_failed(cats: dict[str, list[dict]]) -> list[str]:
    """Names of the catalogues whose lookup did not answer. A failed lookup is never evidence of anything."""
    return [name for name, rows in cats.items() if any("error" in r for r in rows)]


# ---------------------------------------------------------------- neighbour prediction
def response(sep, scale: float | None = None):
    """Fraction of a neighbour's flux-weighted pull on the fitted centre, at separation sep (arcsec)."""
    s = RESPONSE_SCALE_ARCSEC if scale is None else scale
    return np.exp(-np.asarray(sep, float) ** 2 / (2 * s ** 2))


def predicted_shift(east, north, flux_ratio, scale: float | None = None) -> tuple[float, float]:
    """Offset of the fitted centre of a host (flux 1) with neighbours at (east, north) arcsec from it and the
    given flux ratios (neighbour / host), using the response curve. Zero neighbours give (0, 0)."""
    east, north, f = (np.asarray(v, float) for v in (east, north, flux_ratio))
    if len(f) == 0:
        return 0.0, 0.0
    w = response(np.hypot(east, north), scale)
    return float(np.sum(f * w * east) / (1 + np.sum(f))), float(np.sum(f * w * north) / (1 + np.sum(f)))


def rp_flux_ratios(host: dict, neighbours: list[dict]) -> np.ndarray:
    """Neighbour / host flux in Gaia RP (G minus 0.8 when RP is missing)."""
    def rp(s):
        if s.get("rp") is not None:
            return s["rp"]
        return s["gmag"] - 0.8 if s.get("gmag") is not None else np.nan
    h = rp(host)
    return np.array([10 ** (-0.4 * (rp(s) - h)) for s in neighbours], float)


# ---------------------------------------------------------------- per-exposure measurement
def _host_geometry(cut: dict, host: dict):
    ra, dec = astrometry.position_at(host, cut["mjd"])
    px, py = cut["wcs"].all_world2pix(ra, dec, 0)
    x0, y0 = float(px), float(py)
    return x0, y0, local_jacobian(cut["wcs"], x0, y0)


def _measure_one(args):
    path, host, plan = args
    cut = read_cutout(path)
    x0, y0, J = _host_geometry(cut, host)
    one = fit_star(cut["data"], cut["var"], cut["bad"], x0, y0)
    if one is None:
        return None
    p, e, chi2, chi_sum = one
    ny, nx = cut["data"].shape
    dE, dN = J @ np.array([p[1] - x0, p[2] - y0])
    eE, eN = np.abs(J) @ e[1:3]
    lam = float(cut["wave"][int(round(y0)), int(round(x0))])
    row = {"mjd": cut["mjd"], "det": cut["det"], "lam": lam, "dE": float(dE), "dN": float(dN), "eE": float(eE),
           "eN": float(eN), "dx": float(p[1] - x0), "dy": float(p[2] - y0), "flux": float(p[0] * MJY_PER_PIXEL_SR), "width": float(p[3]), "chi2": float(chi2),
           "chi_sum": float(chi_sum), "path": str(path)}
    if plan:
        Ji = np.linalg.inv(J)
        ratios = {}
        for key, (sep, pa) in plan.items():
            comp = tuple(Ji @ np.array(offset_at(sep, pa)))
            two = fit_star(cut["data"], cut["var"], cut["bad"], x0, y0, comp=comp)
            if two is None:
                ratios[key] = (np.nan, np.nan, np.nan)
                continue
            q, qe, _, qsum = two
            ratios[key] = (float(q[5] / q[0]), float(abs(q[5] / q[0]) * np.hypot(qe[5] / max(abs(q[5]), 1e-9),
                                                                              qe[0] / q[0])), float(chi_sum - qsum))
        row["ratios"] = ratios
        row["flux_two"] = float(q[0] * MJY_PER_PIXEL_SR) if two is not None else float("nan")
    return row


def measure_host(paths, host: dict, plan: dict | None = None, workers: int = 4) -> list[dict]:
    """One row per exposure with a clean fit. `plan` maps a key to (separation arcsec, PA deg): the two-source
    fit is also run at each; its ratio, error and chi2 gain are stored under row['ratios'][key]."""
    jobs = [(p, host, plan) for p in paths]
    if workers <= 1 or len(jobs) < 8:
        rows = [_measure_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as pool:
            rows = list(pool.map(_measure_one, jobs, chunksize=8))
    return [r for r in rows if r is not None]


# ---------------------------------------------------------------- binned results
def _arr(rows, key):
    return np.array([r[key] for r in rows], float)


def group_offset(rows, lo: float, hi: float, dets=None) -> dict:
    """Robust median East and North offset of the exposures with lo <= wavelength < hi (optionally detectors)."""
    lam, det = _arr(rows, "lam"), _arr(rows, "det")
    m = (lam >= lo) & (lam < hi) & (_arr(rows, "eE") < 0.5)
    if dets is not None:
        m &= np.isin(det, list(dets))
    E, eE, n = robust(_arr(rows, "dE")[m])
    N, eN, _ = robust(_arr(rows, "dN")[m])
    return {"east": E, "north": N, "err_east": float(np.hypot(eE, FLOOR_EAST)),
            "err_north": float(np.hypot(eN, FLOOR_NORTH)), "n": n}


def walk_between(short: dict, long: dict) -> dict:
    """Walk = long group minus short group, with its direction, along/across parts and significance."""
    wE, wN = long["east"] - short["east"], long["north"] - short["north"]
    sE, sN = np.hypot(long["err_east"], short["err_east"]), np.hypot(long["err_north"], short["err_north"])
    if not (np.isfinite(wE) and np.isfinite(wN)):
        return {"east": None, "north": None, "pa": None, "size": None, "sigma": None, "across": None,
                "p_false": None, "pa_error_deg": None, "n_short": short["n"], "n_long": long["n"]}
    pa = position_angle(wE, wN)
    s, c = np.sin(np.radians(pa)), np.cos(np.radians(pa))
    s_along = float(np.hypot(s * sE, c * sN))
    along, across = components(wE, wN, pa)
    # The walk is a 2-D vector, so its size in units of its own error follows a Rayleigh distribution when there
    # is no walk (not a Gaussian): P(r > x) = exp(-x^2 / 2).
    r = float(np.hypot(wE / sE, wN / sN))
    return {"east": float(wE), "north": float(wN), "pa": pa, "size": float(np.hypot(wE, wN)), "along": along,
            "sigma": r, "p_false": float(np.exp(-0.5 * r * r)), "across": across,
            "pa_error_deg": float(np.degrees(np.arctan2(s_along, np.hypot(wE, wN)))),
            "err_east": float(sE), "err_north": float(sN), "n_short": short["n"], "n_long": long["n"]}


def along_across_by_bin(rows, pa: float) -> list[dict]:
    """Per wavelength bin: the offset along and across the walk direction with errors that include the measured
    astrometric floor (FLOOR_EAST, FLOOR_NORTH), so the chart's bars are not statistics-only."""
    out = []
    s, c = np.sin(np.radians(pa)), np.cos(np.radians(pa))
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:], strict=True):
        g = group_offset(rows, lo, hi)
        if not np.isfinite(g["east"]):
            out.append({"lo": lo, "hi": hi, "n": g["n"], "along": None, "across": None, "err": None, "err_across": None})
            continue
        along, across = components(g["east"], g["north"], pa)
        out.append({"lo": lo, "hi": hi, "n": g["n"], "along": along, "across": across,
                    "err": float(np.hypot(s * g["err_east"], c * g["err_north"])),
                    "err_across": float(np.hypot(c * g["err_east"], s * g["err_north"]))})
    return out


def across_chi2(bins: list[dict]) -> dict:
    """Chi-square of the across component against zero over the bins that have one (floor included)."""
    v = [(b["across"], b["err_across"]) for b in bins if b["across"] is not None]
    return {"chi2": float(sum((a / e) ** 2 for a, e in v)), "n_bins": len(v)}


def walks(rows) -> dict:
    """The walk for all long-wavelength exposures and for D4, D5 and D6 on their own, each against the same
    short-wavelength group."""
    short = group_offset(rows, *SHORT)
    result = {"all": walk_between(short, group_offset(rows, *LONG))}
    for d in (4, 5, 6):
        result[f"D{d}"] = walk_between(short, group_offset(rows, *LONG, dets=[d]))
    return result


def ratio_bins(rows, key: str) -> list[dict]:
    """Robust median of the two-source ratio in each wavelength bin for the plan entry `key`."""
    lam = _arr(rows, "lam")
    ratio = np.array([r["ratios"][key][0] if "ratios" in r and key in r["ratios"] else np.nan for r in rows], float)
    out = []
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:], strict=True):
        m = (lam >= lo) & (lam < hi) & (_arr(rows, "eE") < 0.5)
        v, e, n = robust(ratio[m])
        out.append({"lo": lo, "hi": hi, "ratio": None if not np.isfinite(v) else v,
                    "err": None if not np.isfinite(e) else e, "n": n})
    return out


def net_ratio(true_bins: list[dict], control_bins: list[list[dict]]) -> list[dict]:
    """Ratio at the walk direction minus the median of the three controls, bin by bin."""
    out = []
    for i, t in enumerate(true_bins):
        cs = [c[i]["ratio"] for c in control_bins if c[i]["ratio"] is not None]
        if t["ratio"] is None or not cs:
            out.append({**t, "control": None, "net": None, "net_err": None})
            continue
        ctrl = float(np.median(cs))
        err = float(np.hypot(t["err"], np.std(cs) if len(cs) > 1 else 0.0))
        out.append({**t, "control": ctrl, "control_max": float(max(cs)), "net": t["ratio"] - ctrl, "net_err": err})
    return out


def gain_by_separation(rows, keys: list[tuple[str, float]], lo: float = LONG[0], hi: float = LONG[1]) -> dict:
    """Total chi2 improvement of the two-source fit over the one-source fit at long wavelengths, per separation."""
    lam = _arr(rows, "lam")
    m = (lam >= lo) & (lam < hi)
    out = {}
    for key, sep in keys:
        g = np.array([r["ratios"][key][2] if "ratios" in r and key in r["ratios"] else np.nan for r in rows], float)
        out[sep] = float(np.nansum(g[m]))
    return out


# ---------------------------------------------------------------- verdict
def verdict(walk_all: dict, per_detector: dict, control_max: float | None, explained: bool,
            known_source: bool, failed_catalogues: list[str] | None = None) -> tuple[str, list[str]]:
    """Apply the rules. Returns (verdict, reasons). The verdicts: 'nothing_found', 'candidate',
    'explained_by_gaia_neighbour', 'known_source_at_walk', 'catalogue_check_failed'.

    The walk size is a Rayleigh variable, so WALK_SIGMA = 4 means P(false) = exp(-8) = 3.4e-4 per host. A
    sample of N hosts multiplies that by N. A candidate is never returned while any catalogue lookup failed.
    (The old rule that the walk must be straight, 'across' small, was removed: the across component was
    measured against the walk's own direction and so could never fail.)
    """
    reasons: list[str] = []
    if walk_all.get("pa") is None or walk_all["sigma"] is None or walk_all["sigma"] < WALK_SIGMA:
        return "nothing_found", [f"walk below {WALK_SIGMA:.0f} sigma"]
    pas = [v["pa"] for v in per_detector.values() if v.get("pa") is not None and v["sigma"] is not None
           and v["sigma"] >= 2.0]
    if len(pas) < 2:
        reasons.append("fewer than two of D4, D5, D6 show the walk at 2 sigma")
    elif max(angle_difference(a, b) for a in pas for b in pas) > DETECTOR_PA_AGREE:
        reasons.append("D4, D5, D6 disagree on the direction")
    if control_max is None or control_max > CONTROL_MAX:
        reasons.append("a control position gives a ratio above 0.02")
    if reasons:
        return "nothing_found", reasons
    if explained:
        return "explained_by_gaia_neighbour", ["a Gaia neighbour can explain the walk"]
    if known_source:
        return "known_source_at_walk", ["a source in 2MASS, AllWISE or CatWISE2020 lies at the inferred place"]
    if failed_catalogues:
        return "catalogue_check_failed", [f"catalogue lookup failed: {', '.join(failed_catalogues)}; not a candidate"]
    return "candidate", ["passes every rule; needs a common-motion check before it is anything more"]


def _bp_rp(s: dict) -> float | None:
    return s["bp"] - s["rp"] if s.get("bp") is not None and s.get("rp") is not None else None


def gaia_explains(walk_pa: float, host: dict, neighbours: list[dict]) -> dict | None:
    """The Gaia neighbour (2 to 20 arcsec away) that can explain a walk, or None. Three ways to explain it:
    'along' (within 30 degrees of the walk direction: a red neighbour pulls the long-wavelength image toward
    itself); 'opposite_bluer' (within 30 degrees of the opposite direction and bluer in BP-RP than the host: it pulls
    the short-wavelength image toward itself, so the walk points away from it); 'bright_any_angle' (any other
    position angle, but brighter than G(host) + 3 within 12 arcsec: any neighbour distorts a round-Gaussian fit
    through the change of image width with wavelength). The first in that order is returned."""
    ra_h, dec_h = astrometry.position_at(host, EPOCH_MJD)
    g_host = host.get("gmag")
    bprp_h = _bp_rp(host)
    found: dict[str, dict] = {}
    for s in neighbours:
        if s["source_id"] == host.get("source_id"):
            continue
        ra_s, dec_s = astrometry.position_at(s, EPOCH_MJD)
        e, n = astrometry.offset_arcsec(ra_h, dec_h, ra_s, dec_s)
        sep = float(np.hypot(e, n))
        if not NEIGHBOUR_WINDOW[0] <= sep <= NEIGHBOUR_WINDOW[1]:
            continue
        if g_host is not None and (s.get("gmag") is None or s["gmag"] > g_host + NEIGHBOUR_DELTA_G):
            continue          # too faint to pull the image: under 2.5 per cent of the host's flux in G
        pa_s = position_angle(e, n)
        d = angle_difference(pa_s, walk_pa)
        info = {"source_id": s["source_id"], "separation": round(sep, 2), "pa": round(pa_s, 1),
                "pa_difference": round(d, 1), "gmag": s.get("gmag"), "rp": s.get("rp"), "bp_rp": _bp_rp(s)}
        if d <= 30.0:
            kind = "along"
        elif d >= 150.0 and bprp_h is not None and info["bp_rp"] is not None and info["bp_rp"] < bprp_h:
            kind = "opposite_bluer"
        elif sep <= 12.0 and g_host is not None and s.get("gmag") is not None and s["gmag"] < g_host + 3.0:
            kind = "bright_any_angle"
        else:
            continue
        if kind not in found or sep < found[kind]["separation"]:
            found[kind] = {**info, "kind": kind}
    for kind in ("along", "opposite_bluer", "bright_any_angle"):
        if kind in found:
            return found[kind]
    return None


def visit_labels(mjd: np.ndarray) -> np.ndarray:
    """Visit number (0, 1, 2 ...) of each exposure: a new visit starts after a gap of more than VISIT_GAP_DAYS."""
    order = np.argsort(mjd)
    lab = np.zeros(len(mjd), int)
    lab[order] = np.concatenate([[0], np.cumsum(np.diff(mjd[order]) > VISIT_GAP_DAYS)])
    return lab


def visit_walks(rows) -> list[dict]:
    """The walk (long minus short group, the same wavelength cuts as `walks`) in each visit separately, in two
    frames: on the sky (East, North, in arcsec) and on the detector (pixel x, y, in arcsec at 6.15 arcsec per
    pixel). The spacecraft turns between visits, so a walk fixed on the sky keeps its sky direction from visit to
    visit, while one fixed on the detector keeps its detector direction. The reader compares the per-visit angles."""
    lam, mjd = _arr(rows, "lam"), _arr(rows, "mjd")
    ok = _arr(rows, "eE") < 0.5
    lab = visit_labels(mjd)
    out = []
    for v in np.unique(lab):
        m = ok & (lab == v)
        res: dict = {"visit": int(v), "mjd": float(np.median(mjd[m])) if m.any() else None}
        for frame, (ka, kb, scale) in {"sky": ("dE", "dN", 1.0), "detector": ("dx", "dy", 6.15)}.items():
            a, b = _arr(rows, ka) * scale, _arr(rows, kb) * scale
            parts = []
            for sel in ((lam >= SHORT[0]) & (lam < SHORT[1]), (lam >= LONG[0]) & (lam < LONG[1])):
                mm = m & sel
                parts.append((robust(a[mm])[0], robust(b[mm])[0], int(mm.sum())))
            (sa, sb, ns), (la, lb, nl) = parts
            wa, wb = la - sa, lb - sb
            good = bool(np.isfinite(wa) and np.isfinite(wb))
            res[frame] = {"a": float(wa), "b": float(wb), "size": float(np.hypot(wa, wb)),
                          "angle_deg": position_angle(wa, wb) if good else None, "n_short": ns, "n_long": nl}
        out.append(res)
    return out


def pa_scan_summary(rows, sep: float, pa_walk: float, step: float = PA_SCAN_STEP) -> dict:
    """The two-source ratio at a fixed separation, in every wavelength bin, at every position angle round the
    star (rows must hold plan keys a<angle>). Angles at least 75 degrees from the walk direction are the empty
    places: their median and scatter in each bin are the null distribution for the ratio at the walk direction."""
    angles = [i * step for i in range(int(round(360.0 / step)))]
    per_bin = []
    table = {a: ratio_bins(rows, f"a{a:g}") for a in angles}
    for i, (lo, hi) in enumerate(zip(BIN_EDGES[:-1], BIN_EDGES[1:], strict=True)):
        by_angle = {a: table[a][i]["ratio"] for a in angles}
        off = [v for a, v in by_angle.items() if v is not None and angle_difference(a, pa_walk) >= 75.0]
        nearest = min(angles, key=lambda a: angle_difference(a, pa_walk))
        at = by_angle[nearest]
        med = float(np.median(off)) if off else None
        sd = float(np.std(off, ddof=1)) if len(off) > 2 else None
        per_bin.append({"lo": lo, "hi": hi, "at_walk": at, "off_peak_median": med, "off_peak_std": sd,
                        "excess_over_off_peak": None if at is None or med is None else at - med,
                        "z": None if at is None or med is None or not sd else (at - med) / sd,
                        "n_off_peak": len(off), "by_angle": by_angle})
    return {"separation": sep, "walk_pa": pa_walk, "nearest_scan_angle": min(angles, key=lambda a: angle_difference(a, pa_walk)),
            "bins": per_bin}


# ---------------------------------------------------------------- entry point
def colour_walk(ra: float, dec: float, *, pmra: float | None, pmdec: float | None, parallax: float | None,
                source_id: str | None = None, size_deg: float = 0.025, detectors: str = "123456",
                companion: tuple[float, float] | None = None, workers: int = 4, paths: list | None = None,
                catalogues: bool = True, gmag: float | None = None, bp: float | None = None,
                rp: float | None = None) -> dict:
    """Run the colour walk on one host. (ra, dec) are the host's Gaia DR3 position at epoch 2016.0.

    companion=(separation arcsec, PA deg) fixes the two-source fit there instead of at the walk direction.
    paths: cutouts to use instead of fetching (the cutouts of the same host, from the cache).
    """
    host = {"ra": ra, "dec": dec, "pmra": pmra, "pmdec": pmdec, "parallax": parallax, "source_id": source_id,
            "gmag": gmag, "bp": bp, "rp": rp}
    downloads = 0
    if paths is None:
        exposures = [e for e in spherex.find_exposures(ra, dec) if str(e["detector"]) in detectors]
        downloads = sum(1 for e in exposures if not spherex._cutout_path(e, ra, dec, size_deg).exists())
        fetched = spherex.fetch_cutouts(exposures, ra, dec, size_deg)
        paths = [p for _, p, _ in fetched if p is not None]
        failed = [err for _, p, err in fetched if p is None]
    else:
        failed = []
    pass1 = measure_host(paths, host, None, workers)
    out: dict = {"host": host, "downloads": downloads, "n_exposures": len(paths), "n_clean_fits": len(pass1), "n_failed_fetch": len(failed),
                 "method": METHOD, "cautions": CAUTIONS, "size_deg": size_deg}
    if len(pass1) < 30:
        out.update(verdict="nothing_found", reasons=["fewer than 30 usable exposures"], walk=None)
        return out
    W = walks(pass1)
    walk_all = W["all"]
    pa = companion[1] if companion else walk_all["pa"]
    out["walk"] = W
    if pa is None:
        out.update(verdict="nothing_found", reasons=["no walk could be formed"])
        return out
    # two-source fits: scan at the walk direction, controls at the limit separations (and the scan's best one)
    plan = {f"s{sep:g}": (sep, pa) for sep in (SCAN_ARCSEC if companion is None else [companion[0]])}
    for sep in LIMIT_SEPARATIONS:
        for k, a in enumerate(control_angles(pa)):
            plan[f"c{k}_{sep:g}"] = (sep, a)
    if companion is not None:     # fixed separation: also the full round of position angles
        for i in range(int(round(360.0 / PA_SCAN_STEP))):
            plan[f"a{i * PA_SCAN_STEP:g}"] = (companion[0], i * PA_SCAN_STEP)
    pass2 = measure_host(paths, host, plan, workers)
    scan_keys = [(f"s{sep:g}", sep) for sep in (SCAN_ARCSEC if companion is None else [companion[0]])]
    gains = gain_by_separation(pass2, scan_keys)
    best_sep = max(gains, key=lambda s: gains[s])
    # controls for the best separation (not in the plan unless it is a limit separation): one more pass
    need = {f"c{k}_{best_sep:g}": (best_sep, a) for k, a in enumerate(control_angles(pa))}
    missing = {k: v for k, v in need.items() if k not in plan}
    if missing:
        extra = measure_host(paths, host, missing, workers)
        by_path = {r["path"]: r for r in extra}
        for r in pass2:
            e = by_path.get(r["path"])
            if e:
                r["ratios"].update(e["ratios"])
    best_key = f"s{best_sep:g}"
    true_bins = ratio_bins(pass2, best_key)
    ctrl_bins = [ratio_bins(pass2, f"c{k}_{best_sep:g}") for k in range(3)]
    net = net_ratio(true_bins, ctrl_bins)
    rough_flux = {}
    host_flux = float(np.median([r["flux"] for r in pass2 if 1.65 <= r["lam"] < 5.02 and r["flux"] > 0] or [np.nan]))
    out["host_median_flux_mjy"] = host_flux
    # companion's rough flux in each bin: net ratio x host flux in the same bin
    for b in net:
        if b["net"] is None:
            continue
        sel = [r["flux"] for r in pass2 if b["lo"] <= r["lam"] < b["hi"]]
        rough_flux[f"{b['lo']:g}-{b['hi']:g}"] = float(b["net"] * np.median(sel)) if sel else None
    red = [b for b in net if b["lo"] >= 2.9 and b["control_max"] is not None] if net else []
    control_max = max([b["control_max"] for b in red], default=None)
    # 5-sigma limits at the limit separations, from the 3.4-5.0 micrometre exposures at four directions
    lam = _arr(pass2, "lam")
    limits = {}
    for sep in LIMIT_SEPARATIONS:
        worst = []
        for key in [f"s{sep:g}"] + [f"c{k}_{sep:g}" for k in range(3)]:
            vals = np.array([r["ratios"].get(key, (np.nan,))[0] for r in pass2], float)
            m = (lam >= 3.4) & np.isfinite(vals)
            lv, le, _ = robust(vals[m])
            if np.isfinite(lv):
                worst.append(max(lv, 0.0) + 5.0 * le)
        limits[f"{sep:g}"] = float(max(worst)) if worst else None
    gaia_rows = gaia_neighbours(ra, dec, NEIGHBOUR_RADIUS)
    for g_row in gaia_rows:       # the host's own magnitudes, from the same cone, when the caller gave none
        if host["gmag"] is None and source_id is not None and g_row["source_id"] == str(source_id):
            host.update(gmag=g_row["gmag"], bp=g_row["bp"], rp=g_row["rp"])
    explained = gaia_explains(walk_all["pa"], host, gaia_rows) if walk_all["pa"] is not None else None
    cats = catalogue_sources(ra, dec, 20.0) if catalogues else {}
    ie, in_ = offset_at(best_sep, walk_all["pa"]) if walk_all["pa"] is not None else (0.0, 0.0)
    known = None
    for name, rows in cats.items():
        for r in rows:
            if "east" in r and np.hypot(r["east"] - ie, r["north"] - in_) <= CATALOGUE_MATCH and np.hypot(r["east"], r["north"]) > 1.5:
                known = {"catalogue": name, **r}
                break
        if known:
            break
    aa_bins = along_across_by_bin(pass1, walk_all["pa"])
    verd, reasons = verdict(walk_all, {k: W[k] for k in ("D4", "D5", "D6")}, control_max, explained is not None,
                            known is not None, catalogues_failed(cats) if catalogues else ["not asked"])
    out.update(verdict=verd, reasons=reasons, best_separation_arcsec=best_sep, gain_by_separation=gains,
               along_across=aa_bins, across_chi2=across_chi2(aa_bins), net_ratio=net, rough_companion_flux_mjy=rough_flux,
               rough_flux_note="rough: net ratio times the host's median flux in the bin; not a calibrated spectrum",
               limit_5sigma_ratio=limits, gaia_neighbour_on_walk=explained, catalogue_neighbours=cats,
               catalogue_source_at_inferred_place=known, catalogues_failed=catalogues_failed(cats),
               visit_walks=visit_walks(pass1))
    if companion is not None:
        out["pa_scan"] = pa_scan_summary(pass2, companion[0], companion[1])
    out["rows"] = [{k: r[k] for k in ("mjd", "det", "lam", "dE", "dN", "eE", "eN", "dx", "dy", "flux", "width", "chi2")} for r in pass1]
    return out


# ---------------------------------------------------------------- field of stars (null and calibration tests)
def _field_exposure(args):
    path, stars, g_max = args
    cut = read_cutout(path)
    ra, dec = astrometry.positions_at(stars, cut["mjd"])
    px, py = cut["wcs"].all_world2pix(ra, dec, 0)
    ny, nx = cut["data"].shape
    cx, cy = nx / 2, ny / 2
    J0 = local_jacobian(cut["wcs"], cx, cy)
    rows = []
    for k, s in enumerate(stars):
        if s["gmag"] is None or s["gmag"] >= g_max:
            continue
        x0, y0 = float(px[k]), float(py[k])
        r = fit_star(cut["data"], cut["var"], cut["bad"], x0, y0)
        if r is None:
            continue
        p, e, chi2, _ = r
        J = J0
        dE, dN = J @ np.array([p[1] - x0, p[2] - y0])
        eE, eN = np.abs(J) @ e[1:3]
        rows.append((k, cut["mjd"], cut["det"], float(cut["wave"][int(round(y0)), int(round(x0))]), dE, dN, eE, eN,
                     p[0] * MJY_PER_PIXEL_SR, chi2))
    return rows


def measure_field(paths, stars: list[dict], g_max: float = 17.5, workers: int = 4) -> np.ndarray:
    """Per-exposure fits of every Gaia star brighter than g_max: columns k, mjd, det, lam, dE, dN, eE, eN, flux,
    chi2, exposure index. `stars` are Gaia rows (with gmag); offsets are measured minus Gaia."""
    jobs = [(p, stars, g_max) for p in paths]
    out: list[tuple] = []
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as pool:
        for fi, rows in enumerate(pool.map(_field_exposure, jobs, chunksize=4)):
            out.extend((*r, fi) for r in rows)
    return np.array(out, float)


def remove_frame_offsets(rows: np.ndarray, isolated: np.ndarray, min_ref: int = 5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Offsets with each exposure's own median (over well-measured isolated stars, the star itself left out)
    removed. Returns (rE, rN, ok)."""
    k, fi = rows[:, 0].astype(int), rows[:, 10].astype(int)
    dE, dN = rows[:, 4], rows[:, 5]
    perr = np.hypot(rows[:, 6], rows[:, 7]) / np.sqrt(2)
    good = isolated[k] & (perr < 0.5) & (np.hypot(dE, dN) < 2.0)
    rE, rN = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    for f in np.unique(fi):
        m = fi == f
        ref = m & good & (perr < 0.15)
        if ref.sum() < min_ref:
            continue
        idx = np.flatnonzero(ref)
        for j in np.flatnonzero(m):
            use = idx[idx != j]
            rE[j] = dE[j] - np.median(dE[use])
            rN[j] = dN[j] - np.median(dN[use])
    return rE, rN, np.isfinite(rE) & (perr < 0.3) & (np.hypot(dE, dN) < 3.0)


def isolated_mask(stars: list[dict], mjd: float, g_range: tuple[float, float] = (11.5, 15.0)) -> np.ndarray:
    """Stars in g_range with no Gaia star brighter than G + 3 within 12 arcsec."""
    ra, dec = astrometry.positions_at(stars, mjd)
    g = np.array([s["gmag"] if s["gmag"] is not None else 99.0 for s in stars])
    out = np.zeros(len(stars), bool)
    for i in np.flatnonzero((g >= g_range[0]) & (g < g_range[1])):
        sep = np.hypot((ra - ra[i]) * np.cos(np.radians(dec[i])), dec - dec[i]) * 3600
        out[i] = not ((sep > 0.01) & (sep < 12) & (g < g[i] + 3)).any()
    return out


def star_walks(rows: np.ndarray, rE: np.ndarray, rN: np.ndarray, ok: np.ndarray, floor: float = 0.0) -> dict[int, dict]:
    """Per star: short (D1, D2) and long (D4 to D6) offsets (frame offsets removed), walk and significance."""
    k, lam = rows[:, 0].astype(int), rows[:, 3]
    out = {}
    for s in np.unique(k[ok]):
        m = ok & (k == s)
        grp = {}
        for name, sel in (("short", m & (lam < SHORT[1])), ("long", m & (lam >= LONG[0]))):
            E, eE, n = robust(rE[sel])
            N, eN, _ = robust(rN[sel])
            grp[name] = (E, N, eE, eN, n)
        (sE, sN, seE, seN, ns), (lE, lN, leE, leN, nl) = grp["short"], grp["long"]
        if min(ns, nl) < 6 or not np.isfinite([sE, lE]).all():
            continue
        wE, wN = lE - sE, lN - sN
        eEw = float(np.sqrt(seE**2 + leE**2 + 2 * floor**2))
        eNw = float(np.sqrt(seN**2 + leN**2 + 2 * floor**2))
        out[int(s)] = {"short_east": sE, "short_north": sN, "walk_east": wE, "walk_north": wN,
                       "walk_err_east": eEw, "walk_err_north": eNw, "sigma": float(np.hypot(wE / eEw, wN / eNw)),
                       "n_short": ns, "n_long": nl}
    return out


def _save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=float))


warnings.simplefilter("ignore", category=UserWarning)
os.environ.setdefault("OMP_NUM_THREADS", "1")

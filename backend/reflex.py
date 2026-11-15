"""Earth-reflex stacking: find a distant body in ONE SPHEREx visit and measure its distance.

Idea. Within a visit (10 to 17 days) the Earth's own sideways acceleration bends the path of a
body 50 to a few hundred AU away by arcseconds to tens of arcseconds. A straight line (a body
moving at constant speed) cannot fake that bend. The track in the tangent plane is

    offset(t) = p0 + v * (t - t0) + (1 / d) * Fnl(t)

with Fnl the Earth's parallax curve (arcsec per 1/AU) after a least-squares straight line in time
is removed (the straight part is absorbed by v). All exposures of one visit are shifted along every
trial track and added; the track with the highest signal-to-noise gives the place, the drift and,
from how the signal falls off with 1/d, the distance and its interval.

The fixed sky is removed exposure by exposure: from each exposure of the chosen visit the mean of
the two exposures of the SAME detector, in OTHER visits, nearest in wavelength, is subtracted
(SPHEREx has one wavelength per detector per exposure, so a like-for-like template needs another
visit). No ephemeris is used anywhere in the search; JPL is called only afterwards to label.

Shift-and-stack and distance from the parallax bend of a short arc are established techniques
(Bernstein & Khushalani 2000; Rice & Laughlin 2020; KBMOD; heliostack). Only their use on SPHEREx
data is new as far as we could find. One visit reaches about 0.6 magnitudes fainter than Eris
(about V 19.3 for an Eris-coloured body): about two magnitudes short of Pan-STARRS and of Planet
Nine's predicted brightness. This module does NOT test Planet Nine and says so in its answer.

Analysis choices were made AFTER a probe had already found Eris (so they are not blind to the
answer; see docs/reflex.md): detectors D1-D3, field 0.13 deg, coarse grid 3 arcsec, fine grid 1.5
arcsec, drift step 0.5 arcsec/day, 1/d step 0.0015 (coarse) and 0.0005 (fine), template of 2
exposures, bright-static mask 0.5 mJy. CANDIDATE_SNR is NOT yet derived from a blank-field
distribution: raw peaks that are not fixed stars reach 8 and above in null runs.
"""

from __future__ import annotations

import hashlib
import json
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area
from scipy.ndimage import binary_dilation, convolve, map_coordinates
from scipy.optimize import minimize

from . import distant, photometry, pipeline, smallbodies, spherex

VERSION = 3
REFLEX_DIR = spherex.CACHE / "reflex"
ARCSEC_PER_RADIAN = 206264.806

COARSE_ARCSEC = 3.0
FINE_ARCSEC = 1.5
CUTOUT_MARGIN_DEG = 0.03
VISIT_GAP_DAYS = 30.0  # a larger gap between exposures starts a new visit
MIN_VISIT_EXPOSURES = 30
MIN_DISTANCE_DAYS = 8.0  # a shorter visit gives a detection, never a distance
BRIGHT_STATIC_MJY = 0.5  # template pixels brighter than this are blanked (fixed stars subtract badly)
TEMPLATE_N = 2
COVER = 0.75  # share of the total weight that must contribute to a stacked pixel
INVD_STEP = 0.0015
INVD_STEP_FINE = 0.0005
DRIFT_STEP = 0.5  # arcsec/day
DRIFT_RADIUS_MAX = 25.0
ORBIT_FACTOR = 1.5  # bound-orbit speed allowance: this times a circular orbit's
DRIFT_PAD = 1.0  # arcsec/day added to every box
MERGE_ARCSEC = 9.0
CANDIDATE_SNR = 8.0  # NOT calibrated: null runs exceed it, see docs/reflex.md; the vetting below does the work
MIN_STRAIGHT_SNR = 5.0  # a distance is only quoted for a source seen on its best straight track
MAX_TOP3_SHARE = 0.5  # more of the signal than this from 3 exposures: artefact, rejected
MAX_CHI2_DOF = 3.0  # a track that fits a constant flux worse than this is rejected
EDGE_ARCSEC = 30.0  # peaks this close to the field edge are not trusted
EPOCH_GAP_DAYS = 0.2  # exposures of one detector closer than this make one epoch
N_BOOT = 40
MF_TO_APERTURE = 0.68  # matched-filter flux / aperture flux, 13 stars in the Eris field (reviewer measurement)
MEASURED_DELTA_S2 = 9.0  # "distance measured" needs S^2(best) - S^2(1/d = 0) at least this
N_RANDOM = 500
AU_PER_KM_PER_S_DAY = 86400.0 / 1.495978707e8  # km/s -> AU/day
V_CIRC_1AU_KMS = 29.78


def SEARCHED_AREA_DEG2(fov: float) -> float:  # noqa: N802
    return float(fov) ** 2


CREDIT = (
    "Method: shift-and-stack along tracks that include the Earth's parallax over one visit. The "
    "distance from the parallax bend of a short arc is Bernstein & Khushalani 2000 (AJ 120, 3323); "
    "shift-and-stack along distance-dependent tracks: Bernstein et al. 2004, Rice & Laughlin 2020 "
    "(TESS), KBMOD, heliostack (HST). Applied here to real SPHEREx data; we do not know of this "
    "having been done with SPHEREx data (searches listed in docs/reflex.md, 2026-11-14)."
)
DEPTH_NOTE = (
    "One visit reaches only about 0.6 magnitudes fainter than Eris: about V 19.3 for an "
    "Eris-coloured body, about V 20.7 for a Sedna-coloured one (scaled from Eris at S/N 14.3 and "
    "Sedna at forced S/N 7.5). That is about 2 magnitudes shallower than Pan-STARRS (V 21.5) and "
    "than Planet Nine's predicted brightness, so this search cannot test Planet Nine or Planet X."
)
RANGING_NOTE = (
    "Detects movers from 50 AU outward. A distance needs S/N x (1/d) large enough: in a 15-day "
    "visit within about 120 AU at the S/N 8 threshold and about 200 AU for an Eris-bright body; "
    "within about half that in a 10-day visit (scaled from the measured Eris profile). Farther "
    "bodies are detected but not ranged."
)
DISTANCE_NOTE = (
    "Distance intervals: the 2 sigma interval from the S/N profile is statistical only and about "
    "2 to 3 times too narrow; the epoch bootstrap interval is the one to quote."
)


# ---------------------------------------------------------------------------------------------
# Exposures and visits
# ---------------------------------------------------------------------------------------------


def split_visits(exposures: list[dict]) -> list[list[dict]]:
    """Group exposures (any detectors) into visits: a gap of more than VISIT_GAP_DAYS starts a new one."""
    exps = sorted(exposures, key=lambda e: e["mjd"])
    visits: list[list[dict]] = []
    for e in exps:
        if visits and e["mjd"] - visits[-1][-1]["mjd"] <= VISIT_GAP_DAYS:
            visits[-1].append(e)
        else:
            visits.append([e])
    return visits


def pick_visit(visits: list[list[dict]], visit: tuple[float, float] | None) -> int | None:
    """Index of the chosen visit: the one containing the mjd range given, else the longest with enough exposures."""
    if visit is not None:
        mid = 0.5 * (visit[0] + visit[1])
        for i, v in enumerate(visits):
            if v[0]["mjd"] - 1 <= mid <= v[-1]["mjd"] + 1:
                return i
        return None
    ok = [(v[-1]["mjd"] - v[0]["mjd"], i) for i, v in enumerate(visits) if len(v) >= MIN_VISIT_EXPOSURES]
    return max(ok)[1] if ok else None


# ---------------------------------------------------------------------------------------------
# Matched-filter flux maps on a common tangent-plane grid
# ---------------------------------------------------------------------------------------------


def make_grid(
    ra: float, dec: float, fov: float, step_arcsec: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Offsets east, north (arcsec) and the sky coordinates of a square grid centred on (ra, dec)."""
    half = fov / 2 * 3600.0
    n = int(2 * half / step_arcsec) + 1
    off = (np.arange(n) - n // 2) * step_arcsec
    ge, gn = np.meshgrid(off, off)
    cosd = np.cos(np.radians(dec))
    return ge, gn, ra + ge / 3600.0 / cosd, dec + gn / 3600.0


def mf_map(path, gra: np.ndarray, gdec: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Matched-filter flux (mJy of a point source) and its variance on the sky grid, for one cutout.

    IMAGE minus ZODI, bad pixels masked, local sky removed, Gaussian PSF filter
    F = conv(D,P) / conv(good,P^2); NaN where a core pixel of the PSF is bad.
    Returns (flux, variance, wavelength at the centre of the detector in micrometres, MJD-AVG).
    """
    with fits.open(path) as h:
        img = h["IMAGE"].data.astype(float)
        var = h["VARIANCE"].data.astype(float)
        fl = h["FLAGS"].data
        z = h["ZODI"].data.astype(float)
        wave = h["WAVE"].data
        hdr = h["IMAGE"].header
    d = img - z
    bad = (
        ((fl & photometry.PHOTOMETRY_BAD) != 0)
        | ~np.isfinite(d)
        | ~np.isfinite(var)
        | pipeline.impossible_pixels(img, var)
    )
    sky = ~bad & ((fl & photometry.SKY_BAD) == 0)
    _, med, _ = sigma_clipped_stats(d[sky] if sky.sum() > 200 else d[~bad], sigma=3, maxiters=5)
    d = np.where(bad, 0.0, d - med)
    v = np.where(bad, 0.0, var)
    good = (~bad).astype(float)
    sig = float(hdr.get("PSF_FWHM", 8.0)) / 6.15 / 2.3548
    r = np.arange(-4, 5)
    p = np.exp(-(r[None, :] ** 2 + r[:, None] ** 2) / (2 * sig**2))
    p /= p.sum()
    num = convolve(d, p[::-1, ::-1], mode="constant")
    den = convolve(good, (p**2)[::-1, ::-1], mode="constant")
    vv = convolve(v, (p**2)[::-1, ::-1], mode="constant")
    core = convolve(bad.astype(float), (p > 0.02).astype(float), mode="constant") > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        f = num / den
        fv = vv / den**2
    f[core | (den <= 0)] = np.nan
    w = WCS(hdr)
    to_mjy = float(proj_plane_pixel_area(w)) * (np.pi / 180) ** 2 * 1e9
    x, y = w.all_world2pix(gra, gdec, 0)
    flux = map_coordinates(f, [y, x], order=1, mode="constant", cval=np.nan) * to_mjy
    variance = map_coordinates(fv, [y, x], order=1, mode="constant", cval=np.nan) * to_mjy**2
    wl = float(wave[wave.shape[0] // 2, wave.shape[1] // 2])
    return flux, variance, wl, float(hdr["MJD-AVG"])


def build_cube(
    exposures: list[dict],
    paths: dict,
    in_visit: list[dict],
    ra: float,
    dec: float,
    fov: float,
    step: float,
    detectors: tuple[int, ...],
    progress=None,
) -> dict:
    """Template-subtracted flux maps of every exposure of the chosen visit.

    Returns arrays D (n_exp, n, n) with NaN where unusable, W (weight per exposure), T (MJD), det,
    plus the raw maps (for vetting), the grid offsets and the template lists.
    """
    ge, gn, gra, gdec = make_grid(ra, dec, fov, step)
    chosen = {(e["obs_id"], e["detector"]) for e in in_visit}
    maps: dict[tuple, tuple] = {}
    todo = [e for e in exposures if e["detector"] in detectors and paths.get((e["obs_id"], e["detector"]))]
    for i, e in enumerate(todo):
        k = (e["obs_id"], e["detector"])
        try:
            maps[k] = (e, *mf_map(paths[k], gra, gdec))
        except (ValueError, KeyError, OSError):
            continue  # an empty or broken cutout (patch at the detector's edge): left out, never filled in
        if progress:
            progress("maps", i + 1, len(todo))
    inv = sorted((k for k in maps if k in chosen), key=lambda k: maps[k][4])
    oth = [k for k in maps if k not in chosen]
    d_list, w_list, t_list, det_list, key_list, tmpl_used = [], [], [], [], [], []
    for k in inv:
        e, fm, _vm, wl, mjd = maps[k]
        cands = sorted((abs(maps[o][3] - wl), o) for o in oth if maps[o][0]["detector"] == e["detector"])[:TEMPLATE_N]
        if len(cands) < 1:
            continue
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # pixels with no template in either exposure stay NaN
            tmpl = np.nanmean([maps[o][1] for _, o in cands], axis=0)
        diff = fm - tmpl
        diff[
            binary_dilation(np.nan_to_num(np.abs(tmpl)) > BRIGHT_STATIC_MJY, iterations=max(2, int(round(6 / step))))
        ] = np.nan
        if np.isfinite(diff).sum() < 0.3 * diff.size:
            continue
        s = 1.4826 * np.nanmedian(np.abs(diff - np.nanmedian(diff)))
        d_list.append(diff)
        w_list.append(1.0 / s**2)
        t_list.append(mjd)
        det_list.append(e["detector"])
        key_list.append(k)
        tmpl_used.append([o[0] for _, o in cands])
    return {
        "D": np.array(d_list),
        "W": np.array(w_list),
        "T": np.array(t_list),
        "det": np.array(det_list),
        "keys": key_list,
        "maps": maps,
        "ge": ge,
        "gn": gn,
        "templates": tmpl_used,
        "median_diff": float(np.nanmedian(np.array(d_list))) if d_list else float("nan"),
    }


# ---------------------------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------------------------


def parallax_curve(mjds: np.ndarray, ra: float, dec: float, t0: float) -> tuple[np.ndarray, np.ndarray]:
    """(Fnl, Flin): Earth-parallax shift per 1/AU in arcsec (east, north), with and without its straight line.

    Fnl has a least-squares straight line in time removed (orthogonal to [1, t]); Flin is the removed part,
    arcsec per 1/AU, so a body at 1/d has an apparent linear drift of 1/d * slope(Flin) on top of its own.
    """
    f = distant.parallax_factor(distant._earth(np.asarray(mjds, float)), ra, dec) * ARCSEC_PER_RADIAN
    dt = np.asarray(mjds, float) - t0
    lin = np.column_stack([np.ones_like(dt), dt])
    fnl = np.empty_like(f)
    for k in range(2):
        c, *_ = np.linalg.lstsq(lin, f[:, k], rcond=None)
        fnl[:, k] = f[:, k] - lin @ c
    return fnl, f - fnl


def drift_box(invd: float, slope_e: float, slope_n: float, nearest_au: float) -> tuple[float, float, float]:
    """Centre (east, north) and radius (arcsec/day) of the drift box for one 1/d.

    The centre is the straight-line part of the Earth's reflex at this distance; the radius
    allows ORBIT_FACTOR times a circular orbit's own motion at |d| (a bound body cannot move faster).
    """
    a = abs(invd)
    d = 1.0 / max(a, 1.0 / 5000.0)
    v_au_day = V_CIRC_1AU_KMS / np.sqrt(d) * AU_PER_KM_PER_S_DAY
    orbital = ORBIT_FACTOR * v_au_day / d * ARCSEC_PER_RADIAN
    return invd * slope_e, invd * slope_n, float(min(DRIFT_RADIUS_MAX, orbital + DRIFT_PAD))


def track_offsets(
    p0: tuple[float, float], v: tuple[float, float], invd: float, dt: np.ndarray, fnl: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    return p0[0] + v[0] * dt + invd * fnl[:, 0], p0[1] + v[1] * dt + invd * fnl[:, 1]


def fit_track(mjds: np.ndarray, east: np.ndarray, north: np.ndarray, ra: float, dec: float) -> dict:
    """Least-squares fit of p0, v and 1/d to a measured track (used by the unit test and for scoring)."""
    t0 = float(np.median(mjds))
    dt = mjds - t0
    f = distant.parallax_factor(distant._earth(mjds), ra, dec) * ARCSEC_PER_RADIAN
    a = np.zeros((2 * len(mjds), 5))
    a[0::2, 0] = 1
    a[1::2, 1] = 1
    a[0::2, 2] = dt
    a[1::2, 3] = dt
    a[0::2, 4] = f[:, 0]
    a[1::2, 4] = f[:, 1]
    b = np.empty(2 * len(mjds))
    b[0::2] = east
    b[1::2] = north
    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    resid = b - a @ sol
    return {
        "distance_au": float(1 / sol[4]),
        "inv_d": float(sol[4]),
        "drift": (float(sol[2]), float(sol[3])),
        "p0": (float(sol[0]), float(sol[1])),
        "rms_arcsec": float(np.sqrt(np.mean(resid**2))),
    }


# ---------------------------------------------------------------------------------------------
# Coarse blind search: integer shifts on the 3 arcsec grid
# ---------------------------------------------------------------------------------------------


def stack_integer(dcube: np.ndarray, wts: np.ndarray, ie: np.ndarray, jn: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sum of weight*flux and of weight over exposures, each shifted by whole pixels (ie east, jn north).

    Value at grid (y, x) is exposure i at (y + jn[i], x + ie[i]). `wts` is (n_exp, n, n).
    """
    n_exp, ny, nx = dcube.shape
    num = np.zeros((ny, nx))
    den = np.zeros((ny, nx))
    for i in range(n_exp):
        sx, sy = int(ie[i]), int(jn[i])
        if abs(sx) >= nx or abs(sy) >= ny:
            continue  # shifted entirely out of the field: contributes nothing
        ys = slice(max(0, -sy), min(ny, ny - sy))
        xs = slice(max(0, -sx), min(nx, nx - sx))
        ys2 = slice(max(0, sy), min(ny, ny + sy))
        xs2 = slice(max(0, sx), min(nx, nx + sx))
        num[ys, xs] += dcube[i][ys2, xs2] * wts[i][ys2, xs2]
        den[ys, xs] += wts[i][ys2, xs2]
    return num, den


def normalise_snr(num: np.ndarray, den: np.ndarray, wsum: float) -> np.ndarray:
    """S = sum(wD)/sqrt(sum w), pixels with less than COVER of the weight blanked, then median 0 and MAD sigma 1."""
    with np.errstate(invalid="ignore", divide="ignore"):
        s = num / np.sqrt(den)
    ok = (den > COVER * wsum) & np.isfinite(s)
    vals = s[ok]
    if vals.size < 50:
        return np.full(num.shape, -np.inf)
    scale = 1.4826 * np.median(np.abs(vals - np.median(vals)))
    out = (s - np.median(vals)) / scale
    out[~ok] = -np.inf
    return out


def coarse_search(
    cube: dict,
    fnl: np.ndarray,
    slope: tuple[float, float],
    t0: float,
    nearest_au: float,
    threads: int = 4,
    progress=None,
) -> dict:
    """Search every (1/d, drift) trial. Returns the best peak of each trial and the trial count."""
    d_cube = np.nan_to_num(cube["D"]).astype(np.float32)
    w_cube = (np.isfinite(cube["D"]) * cube["W"][:, None, None]).astype(np.float32)
    wsum = float(cube["W"].sum())
    dt = cube["T"] - t0
    ge = cube["ge"]
    n = ge.shape[0]
    off = (np.arange(n) - n // 2) * COARSE_ARCSEC
    invds = np.arange(-1.0 / nearest_au, 1.0 / nearest_au + 1e-9, INVD_STEP)
    jobs = []
    for invd in invds:
        ce, cn, rad = drift_box(float(invd), slope[0], slope[1], nearest_au)
        ve_all = ce + np.arange(-np.floor(rad / DRIFT_STEP), np.floor(rad / DRIFT_STEP) + 1) * DRIFT_STEP
        vn_all = cn + np.arange(-np.floor(rad / DRIFT_STEP), np.floor(rad / DRIFT_STEP) + 1) * DRIFT_STEP
        for ve in ve_all:
            for vn in vn_all:
                if np.hypot(ve - ce, vn - cn) <= rad + 1e-9:
                    jobs.append((float(invd), float(ve), float(vn)))

    def one(job):
        invd, ve, vn = job
        oe = ve * dt + invd * fnl[:, 0]
        on = vn * dt + invd * fnl[:, 1]
        num, den = stack_integer(d_cube, w_cube, np.round(oe / COARSE_ARCSEC), np.round(on / COARSE_ARCSEC))
        snr = normalise_snr(num, den, wsum)
        j = int(np.argmax(snr))
        y, x = divmod(j, n)
        return (float(snr[y, x]), invd, ve, vn, float(off[x]), float(off[y]))

    results = []
    with ThreadPoolExecutor(threads) as pool:
        for i, r in enumerate(pool.map(one, jobs, chunksize=64)):
            results.append(r)
            if progress and i % 5000 == 0:
                progress("coarse", i, len(jobs))
    results.sort(reverse=True)
    # robust sigma of S (formal sigma = 1) over a sample of trials: the real-to-formal noise ratio
    rng = np.random.default_rng(0)
    scales = []
    for j in rng.choice(len(jobs), size=min(25, len(jobs)), replace=False):
        invd, ve, vn = jobs[int(j)]
        oe, on = ve * dt + invd * fnl[:, 0], vn * dt + invd * fnl[:, 1]
        num, den = stack_integer(d_cube, w_cube, np.round(oe / COARSE_ARCSEC), np.round(on / COARSE_ARCSEC))
        with np.errstate(invalid="ignore", divide="ignore"):
            sv = num / np.sqrt(den)
        okm = (den > COVER * wsum) & np.isfinite(sv)
        if okm.sum() > 50:
            vals = sv[okm]
            scales.append(1.4826 * np.median(np.abs(vals - np.median(vals))))
    ratio = float(np.median(scales)) if scales else float("nan")
    return {"trials": results, "n_trials": len(jobs), "noise_ratio": ratio}


def merge_peaks(trials: list[tuple], radius: float = MERGE_ARCSEC) -> list[dict]:
    """Greedy merge of per-trial peaks closer than `radius` arcsec in place, strongest first."""
    out: list[dict] = []
    for s, invd, ve, vn, e, nn in trials:
        for c in out:
            if np.hypot(c["east"] - e, c["north"] - nn) <= radius:
                c["n_trials"] += 1
                break
        else:
            out.append({"snr": s, "inv_d": invd, "ve": ve, "vn": vn, "east": e, "north": nn, "n_trials": 1})
    return out


# ---------------------------------------------------------------------------------------------
# Refinement: bilinear sampling at exact track places, Nelder-Mead over place and drift
# ---------------------------------------------------------------------------------------------


class Track:
    """The 1.5 arcsec difference cube and the statistic S for one track shape."""

    def __init__(self, dcube: np.ndarray, wts: np.ndarray, dt: np.ndarray, fnl: np.ndarray, step: float):
        self.d0 = np.nan_to_num(dcube).astype(np.float32)
        self.valid = np.isfinite(dcube).astype(np.float32)
        self.w = wts
        self.dt, self.fnl, self.step = dt, fnl, step
        self.n = dcube.shape[1]
        self.idx = np.arange(len(dt))

    def s(self, params, invd: float, mask: np.ndarray | None = None) -> float:
        pe, pn, ve, vn = params
        oe = pe + ve * self.dt + invd * self.fnl[:, 0]
        on = pn + vn * self.dt + invd * self.fnl[:, 1]
        x = oe / self.step + self.n // 2
        y = on / self.step + self.n // 2
        val = map_coordinates(self.d0, [self.idx, y, x], order=1, mode="constant", cval=0.0)
        ok = map_coordinates(self.valid, [self.idx, y, x], order=1, mode="constant", cval=0.0) > 0.99
        w = self.w * ok
        if mask is not None:
            w = w * mask
        tot = self.w if mask is None else self.w * mask
        if w.sum() < COVER * tot.sum() or w.sum() <= 0:
            return -1e9
        return float(np.sum(w * val) / np.sqrt(w.sum()))

    def samples(self, params, invd: float) -> tuple[np.ndarray, np.ndarray]:
        """Flux (mJy) in every exposure along a track and a mask of the exposures actually on the data."""
        pe, pn, ve, vn = params
        oe = pe + ve * self.dt + invd * self.fnl[:, 0]
        on = pn + vn * self.dt + invd * self.fnl[:, 1]
        x = oe / self.step + self.n // 2
        y = on / self.step + self.n // 2
        val = map_coordinates(self.d0, [self.idx, y, x], order=1, mode="constant", cval=0.0)
        ok = map_coordinates(self.valid, [self.idx, y, x], order=1, mode="constant", cval=0.0) > 0.99
        return val, ok

    def flux(self, params, invd: float, mask: np.ndarray | None = None) -> tuple[float, float]:
        """Weighted mean flux (mJy) along a track and its formal error."""
        pe, pn, ve, vn = params
        oe = pe + ve * self.dt + invd * self.fnl[:, 0]
        on = pn + vn * self.dt + invd * self.fnl[:, 1]
        x = oe / self.step + self.n // 2
        y = on / self.step + self.n // 2
        val = map_coordinates(self.d0, [self.idx, y, x], order=1, mode="constant", cval=0.0)
        ok = map_coordinates(self.valid, [self.idx, y, x], order=1, mode="constant", cval=0.0) > 0.99
        w = self.w * ok * (1.0 if mask is None else mask)
        if w.sum() <= 0:
            return float("nan"), float("nan")
        return float(np.sum(w * val) / w.sum()), float(1.0 / np.sqrt(w.sum()))

    def random_scale(
        self, params, invd: float, avoid: tuple[float, float], half: float, rng, mask=None, n_random: int = N_RANDOM
    ) -> tuple[float, float, int]:
        """Median and MAD sigma of S for the same track shape at random places away from `avoid`."""
        vals = []
        for _ in range(4 * n_random):
            pe, pn = rng.uniform(-half, half, 2)
            if np.hypot(pe - avoid[0], pn - avoid[1]) < 25:
                continue
            v = self.s([pe, pn, params[2], params[3]], invd, mask)
            if v > -1e8:
                vals.append(v)
            if len(vals) >= n_random:
                break
        a = np.array(vals)
        return float(np.median(a)), float(1.4826 * np.median(np.abs(a - np.median(a)))), len(a)


def _grid(nearest_au: float, step: float = INVD_STEP_FINE) -> np.ndarray:
    return np.arange(-0.012, 1.0 / nearest_au + 1e-9, step)


def profile(
    track: Track,
    start: tuple[float, float, float, float],
    grid: np.ndarray,
    limit=None,
    mask: np.ndarray | None = None,
    n_starts: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Raw S against 1/d with place and drift optimised at each 1/d.

    Nelder-Mead gets an explicit initial simplex (1 arcsec in place, 0.3 arcsec/day in drift) so a
    parameter that starts at exactly zero is still optimised, and several starts. `limit(invd)`
    returns the drift box (centre east, centre north, radius); a drift outside it (plus one drift
    step) is penalised and, if it still ends outside, the point is marked invalid (NaN), as is any
    point where the track leaves the data (the -1e9 sentinel is never used as a value).
    """
    s0 = np.array(start, float)
    x_prev = s0.copy()
    shifts = [np.zeros(4), np.array([0.0, 0.5, 0.0, 0.0]), np.array([0.5, 0.0, 0.0, 0.0])][:n_starts]
    vals = np.full(len(grid), np.nan)
    pars = np.full((len(grid), 4), np.nan)
    for i, invd in enumerate(grid):
        invd = float(invd)
        box = limit(invd) if limit is not None else None

        def obj(p, inv=invd, box=box):
            v = track.s(p, inv, mask)
            if v < -1e8:
                return 1e9
            if box is not None:
                ex = float(np.hypot(p[2] - box[0], p[3] - box[1])) - box[2]
                if ex > 0:
                    v -= 20.0 * ex
            return -v

        best = None
        for st in [x_prev, *(s0 + sh for sh in shifts)]:
            x0 = np.array(st, float)
            sim = np.vstack([x0, x0 + [1, 0, 0, 0], x0 + [0, 1, 0, 0], x0 + [0, 0, 0.3, 0], x0 + [0, 0, 0, 0.3]])
            r = minimize(
                obj,
                x0,
                method="Nelder-Mead",
                options={"initial_simplex": sim, "xatol": 0.02, "fatol": 1e-4, "maxiter": 600},
            )
            if best is None or r.fun < best.fun:
                best = r
        assert best is not None
        x_prev = best.x
        v = track.s(best.x, invd, mask)
        inside = box is None or float(np.hypot(best.x[2] - box[0], best.x[3] - box[1])) <= box[2] + DRIFT_STEP
        if v > -1e8 and inside:
            vals[i] = v
            pars[i] = best.x
    return vals, pars


def _interval(grid: np.ndarray, snr: np.ndarray, ib: int, drop: float) -> tuple[float | None, float | None]:
    """Distance interval (near, far) in AU where S^2 >= best - drop on the contiguous stretch around the best.

    Only positive, valid S/N counts (a negative S/N is never 'inside' because it is squared), the end is
    interpolated linearly in S^2. A far end of None means infinity (the profile never drops by `drop`
    before 1/d <= 0); a near end of None cannot occur on the searched grid.
    """
    s2 = np.where(np.isfinite(snr) & (snr > 0), snr**2, 0.0)
    thr = s2[ib] - drop

    def edge(step: int) -> float:
        j = ib
        while 0 <= j + step < len(grid) and s2[j + step] >= thr:
            j += step
        k = j + step
        if not 0 <= k < len(grid):
            return float(grid[j])
        denom = s2[j] - s2[k]
        frac = 0.0 if denom <= 0 else (s2[j] - thr) / denom
        return float(grid[j] + frac * (grid[k] - grid[j]))

    lo_i, hi_i = edge(-1), edge(1)
    return (1.0 / hi_i if hi_i > 0 else None), (1.0 / lo_i if lo_i > 0 else None)


def _straight_snr(track: Track, start, med: float, scale: float, mask) -> float:
    v, _ = profile(track, tuple(start), np.array([0.0]), None, mask, n_starts=2)
    return float((v[0] - med) / scale) if np.isfinite(v[0]) else float("nan")


def refine(
    track: Track,
    start: tuple[float, float, float, float],
    invd0: float,
    nearest_au: float,
    half: float,
    seed: int = 1,
    limit=None,
) -> dict:
    """Profile of S against 1/d (see `profile`), S/N from the noise at random places."""
    grid = _grid(nearest_au)
    vals, pars = profile(track, start, grid, limit)
    if not np.isfinite(vals).any():
        return {"ok": False}
    ib = int(np.nanargmax(vals))
    rng = np.random.default_rng(seed)
    pe_b, pn_b, ve_b, vn_b = pars[ib]
    med, scale, n_rand = track.random_scale(pars[ib], grid[ib], (pe_b, pn_b), half, rng)
    snr = (vals - med) / scale  # NaN where the point is invalid
    # the straight-line comparison lets the drift be ANYTHING (a body at 1/d = 0 with a free straight track):
    # that is the test of whether the bend is needed; the bounded-drift profile is not
    snr0 = _straight_snr(track, (pe_b, pn_b, ve_b, vn_b), med, scale, None)
    neg = (grid < -1e-9) & np.isfinite(snr)
    best = float(snr[ib])
    s0_pos = max(snr0, 0.0) if np.isfinite(snr0) else 0.0
    return {
        "ok": True,
        "grid": grid,
        "snr": snr,
        "raw": vals,
        "params": pars,
        "best_index": ib,
        "best_inv_d": float(grid[ib]),
        "best_snr": best,
        "place": (float(pe_b), float(pn_b)),
        "drift": (float(ve_b), float(vn_b)),
        "interval_2sigma": _interval(grid, snr, ib, 4.0),
        "snr_infinite": snr0,
        "delta_s2_infinite": float(best**2 - s0_pos**2) if best > 0 else 0.0,
        "reversed_best_snr": float(np.max(snr[neg])) if neg.any() else None,
        "noise_scale": scale,
        "noise_median": med,
        "n_random": n_rand,
    }


def epochs_of(T: np.ndarray, det: np.ndarray) -> list[np.ndarray]:
    """Index groups: exposures of one detector separated by less than EPOCH_GAP_DAYS are one epoch."""
    groups: list[np.ndarray] = []
    for d in sorted(set(int(x) for x in det)):
        idx = np.where(det == d)[0]
        idx = idx[np.argsort(T[idx])]
        cur = [int(idx[0])]
        for a, b in zip(idx[:-1], idx[1:], strict=True):
            if T[b] - T[a] > EPOCH_GAP_DAYS:
                groups.append(np.array(cur))
                cur = []
            cur.append(int(b))
        groups.append(np.array(cur))
    return groups


def epoch_resampling(
    track: Track,
    res: dict,
    epochs: list[np.ndarray],
    limit,
    rng,
    n_boot: int = N_BOOT,
    threads: int = 4,
) -> dict:
    """Leave-one-epoch-out and epoch-bootstrap of the best 1/d and of S^2(best) - S^2(1/d = 0).

    The noise scale of the full run is reused (a different mask changes the sum but not the scale of S).
    Both use a coarser 1/d grid. The bootstrap resamples whole epochs with replacement, which is what
    keeps a few exposures from deciding the distance without the interval showing it.
    """
    grid = np.arange(res["grid"].min(), res["grid"].max() + 1e-9, 0.001)
    start = (*res["place"], *res["drift"])
    med, scale = res["noise_median"], res["noise_scale"]
    n = len(track.dt)

    def one(mask: np.ndarray) -> tuple[float, float]:
        vals, _ = profile(track, start, grid, limit, mask, n_starts=1)
        if not np.isfinite(vals).any():
            return float("nan"), float("nan")
        snr = (vals - med) / scale
        ib = int(np.nanargmax(vals))
        s0 = _straight_snr(track, start, med, scale, mask)
        s0 = max(s0, 0.0) if np.isfinite(s0) else 0.0
        return float(grid[ib]), float(snr[ib] ** 2 - s0**2) if snr[ib] > 0 else 0.0

    jobs = []
    for e in epochs:
        m = np.ones(n)
        m[e] = 0.0
        jobs.append(m)
    for _ in range(n_boot):
        pick = rng.integers(0, len(epochs), len(epochs))
        m = np.zeros(n)
        for k in pick:
            m[epochs[k]] += 1.0
        jobs.append(m)
    with ThreadPoolExecutor(threads) as pool:
        out = list(pool.map(one, jobs))
    jk = np.array(out[: len(epochs)])
    bs = np.array(out[len(epochs) :])
    inv = bs[:, 0][np.isfinite(bs[:, 0])]

    def dist(q: float) -> float | None:
        v = float(np.percentile(inv, q))
        return round(1.0 / v, 1) if v > 1e-6 else None

    return {
        "n_epochs": len(epochs),
        "leave_one_epoch_out_delta_s2": [round(float(x), 1) for x in jk[:, 1]],
        "leave_one_epoch_out_min_delta_s2": round(float(np.nanmin(jk[:, 1])), 1),
        "leave_one_epoch_out_inv_d_sigma": round(float(np.nanstd(jk[:, 0])), 5),
        "n_bootstrap": int(len(inv)),
        "bootstrap_distance_au_68": [dist(84.0), dist(16.0)],  # near, far; None = unbounded
        "bootstrap_distance_au_95": [dist(97.5), dist(2.5)],
        "bootstrap_share_unbounded": round(float(np.mean(inv <= 1e-6)), 3),
        "grid_step": 0.001,
    }


# ---------------------------------------------------------------------------------------------
# Vetting
# ---------------------------------------------------------------------------------------------


def per_detector(track: Track, result: dict, dets: np.ndarray, half: float, seed: int = 2) -> dict:
    """Flux (mJy) and S/N of the best track in each detector separately (noise from random places)."""
    out = {}
    params, invd = result["params"][result["best_index"]], result["best_inv_d"]
    rng = np.random.default_rng(seed)
    for d in sorted(set(int(x) for x in dets)):
        m = (dets == d).astype(float)
        if m.sum() < 3:
            continue
        s_here = track.s(params, invd, m)
        med, scale, _ = track.random_scale(params, invd, result["place"], half, rng, mask=m, n_random=200)
        fl, err = track.flux(params, invd, m)
        out[f"D{d}"] = {
            "n_exposures": int(m.sum()),
            "flux_mjy": round(fl, 4),
            "flux_error_mjy": round(err * scale, 4),
            "snr": round(float((s_here - med) / scale), 2) if s_here > -1e8 else None,
        }
    return out


def track_checks(track: Track, params, invd: float) -> dict:
    """Share of the signal in the 3 strongest exposures, chi2 per degree of freedom about a constant flux,
    and the span (days) of the exposures that are on the data along this track."""
    val, ok = track.samples(params, invd)
    w = track.w * ok
    if w.sum() <= 0 or ok.sum() < 5:
        return {"top3_share": None, "chi2_dof": None, "usable_span_days": 0.0, "n_usable": int(ok.sum())}
    mean = float(np.sum(w * val) / w.sum())
    contrib = (w * val)[ok]
    pos = np.clip(contrib, 0, None)
    top3 = float(np.sort(pos)[-3:].sum() / pos.sum()) if pos.sum() > 0 else 1.0
    chi2 = float(np.sum(w * (val - mean) ** 2) / max(int(ok.sum()) - 1, 1))
    return {
        "top3_share": round(top3, 3),
        "chi2_dof": round(chi2, 2),
        "usable_span_days": round(float(np.ptp(track.dt[ok])), 2),
        "n_usable": int(ok.sum()),
    }


def still_there(
    cube: dict,
    east: float,
    north: float,
    flux_mjy: float,
    detectors: tuple[int, ...],
    t0: float,
    visits_mjd: list[tuple[float, float]],
) -> list[dict]:
    """Raw (not differenced) flux at the candidate's place in the exposures of each OTHER visit.

    A body found in one visit only is not there, at that place, in the others. A fixed or variable
    source is. 'still there' means at least 0.6 of the candidate's flux at 3 sigma or more.
    """
    ge = cube["ge"]
    step = abs(ge[0, 1] - ge[0, 0])
    n = ge.shape[0]
    x = int(round(east / step)) + n // 2
    y = int(round(north / step)) + n // 2
    out = []
    for lo, hi in visits_mjd:
        f, v = [], []
        for e, fm, vm, _wl, mjd in cube["maps"].values():
            if not (lo <= mjd <= hi) or e["detector"] not in detectors:
                continue
            if 0 <= y < n and 0 <= x < n and np.isfinite(fm[y, x]) and np.isfinite(vm[y, x]) and vm[y, x] > 0:
                f.append(fm[y, x])
                v.append(vm[y, x])
        if len(f) < 3:
            out.append({"mjd": [lo, hi], "n": len(f), "there": None})
            continue
        w = 1.0 / np.array(v)
        mean = float(np.sum(w * np.array(f)) / w.sum())
        err = float(1.0 / np.sqrt(w.sum()))
        out.append(
            {
                "mjd": [round(lo, 1), round(hi, 1)],
                "n": len(f),
                "flux_mjy": round(mean, 4),
                "error_mjy": round(err, 4),
                "there": bool(mean >= 0.6 * flux_mjy and mean >= 3 * err),
            }
        )
    return out


def label_known(
    mjd: float, ra: float, dec: float, fov: float, found: list[tuple[float, float]], radius_arcsec: float = 30.0
) -> dict:
    """JPL sb_ident labels (never steers the search). Returns known bodies within radius of each found place."""
    try:
        bodies = smallbodies.identify(mjd, ra, dec, fov / 2 + 0.05)
    except Exception as e:  # noqa: BLE001 - a service that is down is reported, not hidden
        return {"error": f"{type(e).__name__}: {e}", "near": [[] for _ in found]}
    cosd = np.cos(np.radians(dec))
    near = []
    for fra, fdec in found:
        near.append(
            [
                {
                    "name": b["name"],
                    "vmag": b["vmag"],
                    "separation_arcsec": round(float(np.hypot((b["ra"] - fra) * cosd, b["dec"] - fdec) * 3600), 1),
                }
                for b in bodies
                if np.hypot((b["ra"] - fra) * cosd, b["dec"] - fdec) * 3600 <= radius_arcsec
            ]
        )
    return {"n_known_in_field": len(bodies), "near": near}


KNOWN_DISTANT = [
    "136199 Eris",
    "136472 Makemake",
    "136108 Haumea",
    "90377 Sedna",
    "225088 Gonggong",
    "50000 Quaoar",
    "90482 Orcus",
    "134340 Pluto",
]


def label_known_distant(
    mjd: float, ra: float, dec: float, found: list[tuple[float, float]], radius_arcsec: float = 60.0
) -> list[list[dict]]:
    """Second known-body check: JPL Horizons for the named dwarf planets (sb_ident missed Eris).

    Asked only AFTER the search and never steers it. A service that is down gives an `error` entry,
    never a silent 'none'. It lists only these named bodies, so it cannot rule out an unnamed known TNO.
    """
    out: list[list[dict]] = [[] for _ in found]
    cosd = np.cos(np.radians(dec))
    for name in KNOWN_DISTANT:
        try:
            eph = smallbodies.ephemeris(name, [mjd])[0]
        except Exception as e:  # noqa: BLE001
            for lst in out:
                lst.append({"name": name, "error": f"{type(e).__name__}"})
            continue
        for lst, (fra, fdec) in zip(out, found, strict=True):
            sep = float(np.hypot((eph["ra"] - fra) * cosd, eph["dec"] - fdec) * 3600)
            if sep <= radius_arcsec:
                lst.append({"name": name, "separation_arcsec": round(sep, 1), "vmag": eph.get("vmag")})
    return out


# ---------------------------------------------------------------------------------------------
# Entry function
# ---------------------------------------------------------------------------------------------


def _mirror(res: dict, best_inv: float) -> float | None:
    if best_inv <= 0 or res["grid"].min() > -best_inv:
        return None
    v = float(res["snr"][int(np.argmin(np.abs(res["grid"] + best_inv)))])
    return round(v, 2) if np.isfinite(v) else None


def _vet_reversed(track, cube, p, dets_f, half, half_field, detectors, t0, others) -> dict:
    """The same vetting a real candidate gets, for a reversed-Earth control peak at or above threshold."""
    params = np.array([p["east"], p["north"], p["ve"], p["vn"]])
    fake = {"params": params[None, :], "best_index": 0, "best_inv_d": p["inv_d"], "place": (p["east"], p["north"])}
    dets = per_detector(track, fake, dets_f, half)
    n_det = sum(1 for v in dets.values() if v["snr"] is not None and v["snr"] >= 2.0)
    mean_flux, _ = track.flux(params, p["inv_d"])
    there = still_there(cube, p["east"], p["north"], mean_flux, detectors, t0, others)
    chk = track_checks(track, params, p["inv_d"])
    edge = bool(max(abs(p["east"]), abs(p["north"])) > half_field - EDGE_ARCSEC)
    fixed = any(v.get("there") for v in there)
    survives = bool(
        not fixed
        and n_det >= 2
        and not edge
        and (chk["top3_share"] or 1.0) <= MAX_TOP3_SHARE
        and (chk["chi2_dof"] or 99.0) <= MAX_CHI2_DOF
    )
    return {
        "snr": round(p["snr"], 2),
        "place_arcsec": [p["east"], p["north"]],
        "inv_d": p["inv_d"],
        "n_detectors_with_2sigma": n_det,
        "still_there_in_other_visit": fixed,
        "at_field_edge": edge,
        "track_checks": chk,
        "survives_the_vetting_a_candidate_gets": survives,
    }


def _key(ra, dec, fov, detectors, visit, nearest_au, threshold, shuffle) -> str:
    raw = json.dumps(
        [VERSION, round(ra, 6), round(dec, 6), fov, list(detectors), visit, nearest_au, threshold, shuffle]
    )
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _sky(ra: float, dec: float, east: float, north: float) -> tuple[float, float]:
    return ra + east / 3600.0 / np.cos(np.radians(dec)), dec + north / 3600.0


def reflex_search(
    ra: float,
    dec: float,
    fov: float = 0.13,
    detectors: tuple[int, ...] = (1, 2, 3),
    visit: tuple[float, float] | None = None,
    nearest_au: float = 50.0,
    progress=None,
    threshold: float | None = None,
    use_cache: bool = True,
    label: bool = True,
    shuffle_seed: int | None = None,
) -> dict:
    """Blind Earth-reflex search of one SPHEREx visit around (ra, dec). Returns JSON-ready data.

    status: 'candidates', 'nothing_found' or 'cannot_search'. Nothing here is ever simulated; a
    candidate is an unexplained moving source, not a discovery.
    """
    threshold = CANDIDATE_SNR if threshold is None else float(threshold)
    detectors = tuple(int(d) for d in detectors)
    cache_file = REFLEX_DIR / f"{_key(ra, dec, fov, detectors, visit, nearest_au, threshold, shuffle_seed)}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())
    started = time.time()
    exposures = [e for e in spherex.find_exposures(ra, dec) if e["detector"] in detectors]
    visits = split_visits(exposures)
    iv = pick_visit(visits, visit)
    base = {
        "method": "Earth-reflex shift-and-stack, one visit",
        "credit": CREDIT,
        "depth_note": DEPTH_NOTE,
        "version": VERSION,
        "searched_area_deg2": round(SEARCHED_AREA_DEG2(fov), 4),
        "fov_deg": fov,
        "detectors": list(detectors),
        "centre": {"ra": ra, "dec": dec},
    }
    if iv is None or len(visits) < 2:
        why = (
            "no visit with enough exposures"
            if iv is None
            else "only one visit covers this patch, so there is no fixed-sky template"
        )
        return {
            **base,
            "status": "cannot_search",
            "answer": f"Cannot search this patch: {why}.",
            "reason": why,
            "n_visits": len(visits),
        }
    chosen = visits[iv]
    lo, hi = chosen[0]["mjd"], chosen[-1]["mjd"]
    duration = hi - lo
    others = [(v[0]["mjd"] - 0.1, v[-1]["mjd"] + 0.1) for j, v in enumerate(visits) if j != iv]
    results = spherex.fetch_cutouts(exposures, ra, dec, fov + CUTOUT_MARGIN_DEG)
    paths = {(e["obs_id"], e["detector"]): p for e, p, _err in results if p}
    failed = [err for _e, p, err in results if not p]
    t_maps = time.time()
    cube = build_cube(exposures, paths, chosen, ra, dec, fov, COARSE_ARCSEC, detectors, progress)
    if len(cube["D"]) < 10:
        return {
            **base,
            "status": "cannot_search",
            "answer": "Cannot search this patch: fewer than 10 usable exposures.",
            "reason": "too few usable exposures",
            "n_failed_cutouts": len(failed),
        }
    tmap = None
    if shuffle_seed is not None:  # control: exposure times shuffled within the visit (images keep their order)
        perm = np.random.default_rng(shuffle_seed).permutation(len(cube["T"]))
        tmap = dict(zip(cube["keys"], cube["T"][perm], strict=True))
        cube["T"] = cube["T"][perm]
    t0 = float(np.median(cube["T"]))
    fnl, flin = parallax_curve(cube["T"], ra, dec, t0)
    lever = [float(np.ptp(fnl[:, 0])), float(np.ptp(fnl[:, 1]))]
    dtf = cube["T"] - t0
    slope = (float(np.polyfit(dtf, flin[:, 0], 1)[0]), float(np.polyfit(dtf, flin[:, 1], 1)[0]))
    visit_info = {
        "mjd_first": lo,
        "mjd_last": hi,
        "duration_days": round(duration, 2),
        "n_exposures": len(chosen),
        "n_used": int(len(cube["D"])),
        "mjd_t0": t0,
        "distance_leverage_arcsec_per_inv_au": [round(x) for x in lever],
        "median_of_difference_maps_mjy": cube["median_diff"],
    }
    coarse = coarse_search(cube, fnl, slope, t0, nearest_au, progress=progress)
    trials = coarse["trials"]
    n_trials = coarse["n_trials"]
    pos = [t for t in trials if t[1] > -1e-9]
    neg = [t for t in trials if t[1] < -1e-9]
    peaks = [p for p in merge_peaks(pos) if p["snr"] >= threshold]
    control_peaks = merge_peaks(neg)
    # a reversed-Earth peak right on top of a real body is that body leaking in; the control is what is left elsewhere
    away = [
        p
        for p in control_peaks
        if all(
            np.hypot(p["east"] - q["east"], p["north"] - q["north"]) > 30
            for q in merge_peaks(pos)[:1]
            if q["snr"] >= threshold
        )
    ]
    control_peaks = away
    control = {
        "best_reversed_snr": control_peaks[0]["snr"] if control_peaks else None,
        "place_east_north_arcsec": [control_peaks[0]["east"], control_peaks[0]["north"]] if control_peaks else None,
        "n_reversed_trials": len(neg),
        "n_reversed_above_threshold": sum(1 for p in control_peaks if p["snr"] >= threshold),
    }
    # noise of the stacked mean flux in one trial = 1/sqrt(sum w), times the measured ratio of real to
    # formal noise (the robust sigma of S over the coarse trial maps), on the matched-filter flux scale
    mean_noise = float(1.0 / np.sqrt(cube["W"].sum()))
    ratio = coarse["noise_ratio"]
    mf_limit = threshold * mean_noise * ratio
    limit = {
        "threshold_snr": threshold,
        "stacked_mean_noise_mjy_formal": round(mean_noise, 5),
        "noise_ratio_measured_to_formal": round(ratio, 3),
        "faintest_mean_flux_mjy_matched_filter_scale": round(mf_limit, 4),
        "faintest_mean_flux_mjy_aperture_scale": round(mf_limit / MF_TO_APERTURE, 3),
        "completeness": "50 per cent level (a source of this flux is found about half the time), not a hard limit",
        "flux_scale_note": (
            "matched-filter fluxes are about 0.68 of aperture-photometry fluxes (13 stars of the Eris field, "
            "reviewer measurement); the aperture-scale figure divides by that and is not re-measured per field"
        ),
        "detectors": list(detectors),
        "searched_area_deg2": base["searched_area_deg2"],
        "ranging_note": RANGING_NOTE,
        "note": DEPTH_NOTE,
    }
    out: dict[str, Any] = {
        **base,
        "visit": visit_info,
        "control": control,
        "limit": limit,
        "n_trials": n_trials,
        "n_visits": len(visits),
        "n_failed_cutouts": len(failed),
        "top_unthresholded_peaks": [
            {k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()} for p in merge_peaks(pos)[:5]
        ],
    }
    candidates: list[dict[str, Any]] = []
    rev_hits = [p for p in control_peaks if p["snr"] >= threshold][:3]
    if peaks or rev_hits:
        cube_f = build_cube(exposures, paths, chosen, ra, dec, fov, FINE_ARCSEC, detectors)
        keep = [i for i, k in enumerate(cube_f["keys"]) if k in set(cube["keys"])]
        dcf = cube_f["D"][keep]
        tf = cube_f["T"][keep]
        if tmap is not None:
            tf = np.array([tmap[cube_f["keys"][i]] for i in keep])
        fnl_f, _ = parallax_curve(tf, ra, dec, t0)
        track = Track(dcf, cube_f["W"][keep], tf - t0, fnl_f, FINE_ARCSEC)
        dets_f = cube_f["det"][keep]
        half_field = fov / 2 * 3600.0
        half = half_field - 10

        def limit_fn(inv: float) -> tuple[float, float, float]:
            return drift_box(inv, slope[0], slope[1], nearest_au)

        out["reversed_earth_peaks_vetted"] = [
            _vet_reversed(track, cube, p, dets_f, half, half_field, detectors, t0, others) for p in rev_hits
        ]
        for p in peaks[:5]:
            res = refine(track, (p["east"], p["north"], p["ve"], p["vn"]), p["inv_d"], nearest_au, half, limit=limit_fn)
            if not res["ok"]:
                continue
            ib = res["best_index"]
            best_inv = res["best_inv_d"]
            c_east, c_north = res["place"]
            fnl0 = np.array([np.interp(0.0, track.dt, track.fnl[:, k]) for k in range(2)])
            m_east, m_north = c_east + best_inv * fnl0[0], c_north + best_inv * fnl0[1]  # model place at t0
            c_ra, c_dec = _sky(ra, dec, m_east, m_north)
            dets = per_detector(track, res, dets_f, half)
            n_det = sum(1 for v in dets.values() if v["snr"] is not None and v["snr"] >= 2.0)
            mean_flux, _ = track.flux(res["params"][ib], best_inv)
            there = still_there(cube, c_east, c_north, mean_flux, detectors, t0, others)
            chk = track_checks(track, res["params"][ib], best_inv)
            at_edge = bool(max(abs(c_east), abs(c_north)) > half_field - EDGE_ARCSEC)
            straight = res["snr_infinite"]
            measured = bool(
                res["delta_s2_infinite"] >= MEASURED_DELTA_S2
                and best_inv > 0
                and np.isfinite(straight)
                and straight >= MIN_STRAIGHT_SNR
                and chk["usable_span_days"] >= MIN_DISTANCE_DAYS
            )
            gone_fixed = any(v.get("there") for v in there)
            basic = bool(
                not gone_fixed
                and n_det >= 2
                and not at_edge
                and (chk["top3_share"] or 1.0) <= MAX_TOP3_SHARE
                and (chk["chi2_dof"] or 99.0) <= MAX_CHI2_DOF
            )
            resamp = None
            if basic and measured:
                resamp = epoch_resampling(
                    track, res, epochs_of(track.dt + t0, dets_f), limit_fn, np.random.default_rng(11)
                )
                measured = bool(resamp["leave_one_epoch_out_min_delta_s2"] >= MEASURED_DELTA_S2)
            near2, far2 = res["interval_2sigma"]
            cand: dict[str, Any] = {
                "ra": round(c_ra, 6),
                "dec": round(c_dec, 6),
                "mjd_t0": t0,
                "offset_arcsec": [round(m_east, 2), round(m_north, 2)],
                "offset_p0_arcsec": [round(c_east, 2), round(c_north, 2)],
                "drift_arcsec_day": [round(res["drift"][0], 3), round(res["drift"][1], 3)],
                "snr": round(res["best_snr"], 2),
                "coarse_snr": round(p["snr"], 2),
                "mean_flux_mjy_matched_filter_scale": round(mean_flux, 4),
                "per_detector": dets,
                "n_detectors_with_2sigma": n_det,
                "still_there": there,
                "track_checks": chk,
                "at_field_edge": at_edge,
                "delta_s2_infinite": round(res["delta_s2_infinite"], 1),
                "snr_at_infinity": None if not np.isfinite(straight) else round(straight, 2),
                "reversed_earth_snr_mirror_distance": _mirror(res, best_inv),
                "distance_measured": measured and duration >= MIN_DISTANCE_DAYS,
                "epoch_resampling": resamp,
                "profile": {
                    "inv_d": [round(float(x), 5) for x in res["grid"][::2]],
                    "snr": [None if not np.isfinite(x) else round(float(x), 2) for x in res["snr"][::2]],
                },
                "basic_vetting_passed": basic,
            }
            if cand["distance_measured"]:
                cand.update(
                    {
                        "distance_au": round(1.0 / best_inv, 1),
                        "interval_2sigma_au_statistical_only": [
                            None if near2 is None else round(near2, 1),
                            None if far2 is None else round(far2, 1),
                        ],
                        "interval_note": DISTANCE_NOTE,
                    }
                )
            else:
                cand.update(
                    {
                        "distance_au": None,
                        "lower_limit_au": None if near2 is None else round(near2, 1),
                        "note": "no distance: the bend is not significant, not seen on a straight track, or decided by "
                        "one epoch (or the exposures on the data span under 8 days)",
                    }
                )
            candidates.append(cand)
        if label:
            lab = label_known(t0, ra, dec, fov, [(c["ra"], c["dec"]) for c in candidates])
            out["known_body_labelling"] = {k: v for k, v in lab.items() if k != "near"}
            dist_known = label_known_distant(t0, ra, dec, [(c["ra"], c["dec"]) for c in candidates])
            for c, near, dk in zip(candidates, lab["near"], dist_known, strict=True):
                c["known_body"] = near
                c["known_distant_body"] = [x for x in dk if "error" not in x]
                c["known_distant_check_errors"] = [x for x in dk if "error" in x]
        for c in candidates:
            gone_fixed = any(v.get("there") for v in c["still_there"])
            if c.get("known_body"):
                c["verdict"] = "known body (JPL sb_ident within 30 arcsec): not a candidate"
            elif c.get("known_distant_body"):
                names = ", ".join(x["name"] for x in c["known_distant_body"])
                c["verdict"] = (
                    f"known distant body ({names}, JPL Horizons within 60 arcsec): known-answer, not a candidate"
                )
            elif gone_fixed:
                c["verdict"] = "still there in another visit at the same place: a fixed or variable source, rejected"
            elif c["n_detectors_with_2sigma"] < 2:
                c["verdict"] = "shows in fewer than two detectors: rejected"
            elif c["at_field_edge"]:
                c["verdict"] = "within 30 arcsec of the field edge: rejected"
            elif (c["track_checks"]["top3_share"] or 1.0) > MAX_TOP3_SHARE or (
                c["track_checks"]["chi2_dof"] or 99.0
            ) > MAX_CHI2_DOF:
                c["verdict"] = "signal from a few exposures or not constant along the track: artefact, rejected"
            elif not c["distance_measured"] and float(np.hypot(*c["drift_arcsec_day"])) < 1.0:
                c["verdict"] = "possible artefact or variable within this visit (no measured distance, drift near zero)"
            else:
                c["verdict"] = (
                    "candidate (unlabelled moving source: sb_ident and the named-body Horizons check do not list it, "
                    "neither covers every known body; not a discovery)"
                )
    out["candidates"] = candidates
    good = [c for c in candidates if c["verdict"].startswith("candidate")]
    known_ok = [c for c in candidates if c["verdict"].startswith("known distant body") and c["basic_vetting_passed"]]
    out["status"] = "candidates" if good else ("known_body_recovered" if known_ok else "nothing_found")
    shown = (good or known_ok)[:1]
    if shown:
        c = shown[0]
        eb = c.get("epoch_resampling")
        if c.get("distance_au") and eb:
            lo68, hi68 = eb["bootstrap_distance_au_68"]
            hi95 = eb["bootstrap_distance_au_95"][1]
            dist = (
                f"with a distance of about {c['distance_au']:.0f} AU (epoch bootstrap 68% range {lo68} to "
                f"{hi68 if hi68 is not None else 'unbounded'} AU; at 95% the far side is "
                f"{'unbounded' if hi95 is None else hi95}). "
            )
        else:
            dist = "with no measured distance. "
        what = "unlabelled moving source" if good else "known distant body recovered blind"
        out["answer"] = (
            f"{len(good) or len(known_ok)} {what}(s); the strongest has S/N {c['snr']:.1f} {dist}"
            "A candidate at most, not a discovery. " + RANGING_NOTE + " " + DEPTH_NOTE
        )
    else:
        out["answer"] = (
            f"Nothing moving above S/N {threshold:g} survived the vetting in "
            f"{base['searched_area_deg2']} square degrees, "
            f"{nearest_au:g} to about 1000 AU, one visit: stacked mean flux limit "
            f"{limit['faintest_mean_flux_mjy_matched_filter_scale']} mJy on the matched-filter scale "
            f"(about {limit['faintest_mean_flux_mjy_aperture_scale']} mJy on the aperture scale) at the 50 per cent "
            f"completeness level, D{'/D'.join(str(d) for d in detectors)}. The S/N {threshold:g} threshold itself is "
            "not calibrated against blank fields. " + DEPTH_NOTE
        )
    out["runtime_s"] = round(time.time() - started, 1)
    out["map_and_search_s"] = round(time.time() - t_maps, 1)
    if use_cache:
        REFLEX_DIR.mkdir(parents=True, exist_ok=True)
        spherex.write_json(cache_file, out)
    return out


# ---------------------------------------------------------------------------------------------
# Forced photometry along a KNOWN track (scoring only; never part of the search)
# ---------------------------------------------------------------------------------------------


def forced_along(
    ra: float,
    dec: float,
    fov: float,
    detectors: tuple[int, ...],
    visit: tuple[float, float],
    track_fn,
    n_random: int = 300,
) -> dict:
    """Combined and per-detector S/N of the fixed-sky-subtracted exposures along a given track.

    `track_fn(mjd_array) -> (ra_array, dec_array)` is, e.g., JPL's ephemeris. Used to say where the
    detection limit lies (Sedna) and to score a blind result. The noise is the same track shape moved
    to random places in the field.
    """
    exposures = [e for e in spherex.find_exposures(ra, dec) if e["detector"] in detectors]
    visits = split_visits(exposures)
    iv = pick_visit(visits, visit)
    if iv is None:
        return {"error": "visit not found"}
    chosen = visits[iv]
    results = spherex.fetch_cutouts(exposures, ra, dec, fov + CUTOUT_MARGIN_DEG)
    paths = {(e["obs_id"], e["detector"]): p for e, p, _err in results if p}
    cube = build_cube(exposures, paths, chosen, ra, dec, fov, COARSE_ARCSEC, detectors)
    t = cube["T"]
    tra, tdec = track_fn(t)
    cosd = np.cos(np.radians(dec))
    te = (np.asarray(tra) - ra) * cosd * 3600.0
    tn = (np.asarray(tdec) - dec) * 3600.0
    d0 = np.nan_to_num(cube["D"])
    valid = np.isfinite(cube["D"]).astype(float)
    n = d0.shape[1]
    idx = np.arange(len(t))

    def stat(de: float, dn: float, mask: np.ndarray) -> float:
        x = (te + de) / COARSE_ARCSEC + n // 2
        y = (tn + dn) / COARSE_ARCSEC + n // 2
        val = map_coordinates(d0, [idx, y, x], order=1, mode="constant", cval=0.0)
        ok = map_coordinates(valid, [idx, y, x], order=1, mode="constant", cval=0.0) > 0.99
        w = cube["W"] * ok * mask
        if w.sum() <= 0.5 * (cube["W"] * mask).sum():
            return float("nan")
        return float(np.sum(w * val) / np.sqrt(w.sum()))

    rng = np.random.default_rng(3)
    half = fov / 2 * 3600.0 - 30.0
    out: dict[str, Any] = {"n_used": int(len(t))}
    groups: dict[str, np.ndarray] = {"all": np.ones(len(t))}
    for d in detectors:
        groups[f"D{d}"] = (cube["det"] == d).astype(float)
    for name, m in groups.items():
        s_here = stat(0.0, 0.0, m)
        rand: list[float] = []
        for _ in range(20 * n_random):
            de, dn = rng.uniform(-half, half, 2)
            v = stat(de, dn, m)
            if np.isfinite(v) and np.hypot(de, dn) > 25:
                rand.append(v)
            if len(rand) >= n_random:
                break
        a = np.array(rand)
        out[name] = {
            "snr": round(float((s_here - np.median(a)) / (1.4826 * np.median(np.abs(a - np.median(a))))), 2),
            "n_exposures": int(m.sum()),
        }
    return out

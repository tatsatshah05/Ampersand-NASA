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

Shift-and-stack is an established technique (TESS, ACT, HST, ZTF); only its use on SPHEREx data is
new as far as we could find. One visit reaches about V 19 for a grey body: about two magnitudes
short of Pan-STARRS and of Planet Nine's predicted brightness. This module does NOT test Planet
Nine and says so in its answer.

Analysis choices, fixed before any known answer was scored (see docs/reflex.md):
detectors D1-D3, field 0.13 deg, coarse grid 3 arcsec, fine grid 1.5 arcsec, drift step 0.5
arcsec/day, 1/d step 0.0015 (coarse) and 0.0005 (fine), template of 2 exposures, bright-static
mask 0.5 mJy, candidate threshold from blank fields (CANDIDATE_SNR), no HALO.
"""
from __future__ import annotations

import hashlib
import json
import time
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

VERSION = 1
REFLEX_DIR = spherex.CACHE / "reflex"
ARCSEC_PER_RADIAN = 206264.806

COARSE_ARCSEC = 3.0
FINE_ARCSEC = 1.5
CUTOUT_MARGIN_DEG = 0.03
VISIT_GAP_DAYS = 30.0           # a larger gap between exposures starts a new visit
MIN_VISIT_EXPOSURES = 30
MIN_DISTANCE_DAYS = 8.0         # a shorter visit gives a detection, never a distance
BRIGHT_STATIC_MJY = 0.5         # template pixels brighter than this are blanked (fixed stars subtract badly)
TEMPLATE_N = 2
COVER = 0.75                    # share of the total weight that must contribute to a stacked pixel
INVD_STEP = 0.0015
INVD_STEP_FINE = 0.0005
DRIFT_STEP = 0.5                # arcsec/day
DRIFT_RADIUS_MAX = 25.0
ORBIT_FACTOR = 1.5              # bound-orbit speed allowance: this times a circular orbit's
DRIFT_PAD = 1.0                 # arcsec/day added to every box
MERGE_ARCSEC = 9.0
CANDIDATE_SNR = 8.0             # replaced by the blank-field maximum plus margin, see docs/reflex.md
MEASURED_DELTA_S2 = 9.0         # "distance measured" needs S^2(best) - S^2(1/d = 0) at least this
N_RANDOM = 500
AU_PER_KM_PER_S_DAY = 86400.0 / 1.495978707e8   # km/s -> AU/day
V_CIRC_1AU_KMS = 29.78
# Calibration of the flux limit: V of a grey body is not computed here; see docs/reflex.md.

def SEARCHED_AREA_DEG2(fov: float) -> float:  # noqa: N802
    return float(fov) ** 2


CREDIT = ("Method: shift-and-stack along tracks that include the Earth's parallax over one visit "
          "(established technique: Bernstein et al. 2004, Rice & Laughlin 2020, heliostack). "
          "Applied here to SPHEREx data; we do not know of this having been done with SPHEREx "
          "data (searched: SPHEREx + TNO / Planet Nine / shift-and-stack, arXiv and ADS, 2026-11-14).")
DEPTH_NOTE = ("One visit reaches only about V 19 for a grey body. That is about 2 magnitudes shallower than "
              "Pan-STARRS (V 21.5) and than Planet Nine's predicted brightness, so this search cannot test "
              "Planet Nine or Planet X.")


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

def make_grid(ra: float, dec: float, fov: float, step_arcsec: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
    bad = (((fl & photometry.PHOTOMETRY_BAD) != 0) | ~np.isfinite(d) | ~np.isfinite(var)
           | pipeline.impossible_pixels(img, var))
    sky = ~bad & ((fl & photometry.SKY_BAD) == 0)
    _, med, _ = sigma_clipped_stats(d[sky] if sky.sum() > 200 else d[~bad], sigma=3, maxiters=5)
    d = np.where(bad, 0.0, d - med)
    v = np.where(bad, 0.0, var)
    good = (~bad).astype(float)
    sig = float(hdr.get("PSF_FWHM", 8.0)) / 6.15 / 2.3548
    r = np.arange(-4, 5)
    p = np.exp(-(r[None, :] ** 2 + r[:, None] ** 2) / (2 * sig ** 2))
    p /= p.sum()
    num = convolve(d, p[::-1, ::-1], mode="constant")
    den = convolve(good, (p ** 2)[::-1, ::-1], mode="constant")
    vv = convolve(v, (p ** 2)[::-1, ::-1], mode="constant")
    core = convolve(bad.astype(float), (p > 0.02).astype(float), mode="constant") > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        f = num / den
        fv = vv / den ** 2
    f[core | (den <= 0)] = np.nan
    w = WCS(hdr)
    to_mjy = float(proj_plane_pixel_area(w)) * (np.pi / 180) ** 2 * 1e9
    x, y = w.all_world2pix(gra, gdec, 0)
    flux = map_coordinates(f, [y, x], order=1, mode="constant", cval=np.nan) * to_mjy
    variance = map_coordinates(fv, [y, x], order=1, mode="constant", cval=np.nan) * to_mjy ** 2
    wl = float(wave[wave.shape[0] // 2, wave.shape[1] // 2])
    return flux, variance, wl, float(hdr["MJD-AVG"])


def build_cube(exposures: list[dict], paths: dict, in_visit: list[dict], ra: float, dec: float,
               fov: float, step: float, detectors: tuple[int, ...], progress=None) -> dict:
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
        maps[k] = (e, *mf_map(paths[k], gra, gdec))
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
        with np.errstate(invalid="ignore"):
            tmpl = np.nanmean([maps[o][1] for _, o in cands], axis=0)
        diff = fm - tmpl
        diff[binary_dilation(np.nan_to_num(np.abs(tmpl)) > BRIGHT_STATIC_MJY, iterations=max(2, int(round(6 / step))))] = np.nan
        if np.isfinite(diff).sum() < 0.3 * diff.size:
            continue
        s = 1.4826 * np.nanmedian(np.abs(diff - np.nanmedian(diff)))
        d_list.append(diff)
        w_list.append(1.0 / s ** 2)
        t_list.append(mjd)
        det_list.append(e["detector"])
        key_list.append(k)
        tmpl_used.append([o[0] for _, o in cands])
    return {"D": np.array(d_list), "W": np.array(w_list), "T": np.array(t_list), "det": np.array(det_list),
            "keys": key_list, "maps": maps, "ge": ge, "gn": gn, "templates": tmpl_used,
            "median_diff": float(np.nanmedian(np.array(d_list))) if d_list else float("nan")}


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


def track_offsets(p0: tuple[float, float], v: tuple[float, float], invd: float, dt: np.ndarray, fnl: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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
    return {"distance_au": float(1 / sol[4]), "inv_d": float(sol[4]), "drift": (float(sol[2]), float(sol[3])),
            "p0": (float(sol[0]), float(sol[1])), "rms_arcsec": float(np.sqrt(np.mean(resid ** 2)))}


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


def coarse_search(cube: dict, fnl: np.ndarray, slope: tuple[float, float], t0: float, nearest_au: float,
                  threads: int = 4, progress=None) -> dict:
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
    return {"trials": results, "n_trials": len(jobs)}


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

    def random_scale(self, params, invd: float, avoid: tuple[float, float], half: float, rng, mask=None,
                     n_random: int = N_RANDOM) -> tuple[float, float, int]:
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


def refine(track: Track, start: tuple[float, float, float, float], invd0: float, nearest_au: float, half: float,
           seed: int = 1) -> dict:
    """Profile of S against 1/d. At each 1/d place and drift are optimised; S in noise units."""
    grid = np.arange(-0.012, 1.0 / nearest_au + 1e-9, INVD_STEP_FINE)
    s0 = np.array(start, float)
    x_prev = s0.copy()
    rows = []
    for invd in grid:
        best = None
        for st in (x_prev, s0):
            r = minimize(lambda p: -track.s(p, invd), st, method="Nelder-Mead",
                         options={"xatol": 0.02, "fatol": 1e-4, "maxiter": 800})
            if best is None or r.fun < best.fun:
                best = r
        x_prev = best.x
        rows.append((invd, -best.fun, *best.x))
    prof = np.array(rows)
    ib = int(np.argmax(prof[:, 1]))
    rng = np.random.default_rng(seed)
    pe_b, pn_b, ve_b, vn_b = prof[ib, 2:]
    med, scale, n_rand = track.random_scale(prof[ib, 2:], prof[ib, 0], (pe_b, pn_b), half, rng)
    snr = (prof[:, 1] - med) / scale
    s2 = snr ** 2
    best_s2 = s2[ib]

    def interval(drop: float) -> tuple[float | None, float | None]:
        """Distance interval in AU where S^2 >= best - drop; None as the far end means 'infinity'."""
        inside = grid[s2 >= best_s2 - drop]
        lo_i, hi_i = float(inside.min()), float(inside.max())
        near = 1.0 / hi_i if hi_i > 0 else None
        far = 1.0 / lo_i if lo_i > 0 else None
        return near, far

    i0 = int(np.argmin(np.abs(grid)))
    neg = grid < -1e-9
    return {"grid": grid, "snr": snr, "params": prof[:, 2:], "best_index": ib, "best_inv_d": float(grid[ib]),
            "best_snr": float(snr[ib]), "place": (float(pe_b), float(pn_b)), "drift": (float(ve_b), float(vn_b)),
            "interval_1sigma": interval(1.0), "interval_2sigma": interval(4.0),
            "snr_infinite": float(snr[i0]), "delta_s2_infinite": float(best_s2 - snr[i0] ** 2),
            "reversed_best_snr": float(snr[neg].max()) if neg.any() else None,
            "noise_scale": scale, "noise_median": med, "n_random": n_rand}


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
        out[f"D{d}"] = {"n_exposures": int(m.sum()), "flux_mjy": round(fl, 4),
                        "snr": round(float((s_here - med) / scale), 2) if s_here > -1e8 else None}
    return out


def still_there(cube: dict, east: float, north: float, flux_mjy: float, detectors: tuple[int, ...], t0: float,
                visits_mjd: list[tuple[float, float]]) -> list[dict]:
    """Raw (not differenced) flux at the candidate's place in the exposures of each OTHER visit.

    A body found in one visit only is not there, at that place, in the others. A fixed or variable
    source is. 'still there' means at least 0.6 of the candidate's flux at 3 sigma or more.
    """
    ge, gn = cube["ge"], cube["gn"]
    step = abs(ge[0, 1] - ge[0, 0])
    n = ge.shape[0]
    x = int(round(east / step)) + n // 2
    y = int(round(north / step)) + n // 2
    out = []
    for lo, hi in visits_mjd:
        f, v = [], []
        for k, (e, fm, vm, _wl, mjd) in cube["maps"].items():
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
        out.append({"mjd": [round(lo, 1), round(hi, 1)], "n": len(f), "flux_mjy": round(mean, 4),
                    "error_mjy": round(err, 4), "there": bool(mean >= 0.6 * flux_mjy and mean >= 3 * err)})
    return out


def label_known(mjd: float, ra: float, dec: float, fov: float, found: list[tuple[float, float]], radius_arcsec: float = 30.0) -> dict:
    """JPL sb_ident labels (never steers the search). Returns known bodies within radius of each found place."""
    try:
        bodies = smallbodies.identify(mjd, ra, dec, fov / 2 + 0.05)
    except Exception as e:  # noqa: BLE001 - a service that is down is reported, not hidden
        return {"error": f"{type(e).__name__}: {e}", "near": [[] for _ in found]}
    cosd = np.cos(np.radians(dec))
    near = []
    for fra, fdec in found:
        near.append([{"name": b["name"], "vmag": b["vmag"],
                      "separation_arcsec": round(float(np.hypot((b["ra"] - fra) * cosd, b["dec"] - fdec) * 3600), 1)}
                     for b in bodies if np.hypot((b["ra"] - fra) * cosd, b["dec"] - fdec) * 3600 <= radius_arcsec])
    return {"n_known_in_field": len(bodies), "near": near}


# ---------------------------------------------------------------------------------------------
# Entry function
# ---------------------------------------------------------------------------------------------

def _key(ra, dec, fov, detectors, visit, nearest_au, threshold, shuffle) -> str:
    raw = json.dumps([VERSION, round(ra, 6), round(dec, 6), fov, list(detectors), visit, nearest_au, threshold, shuffle])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _sky(ra: float, dec: float, east: float, north: float) -> tuple[float, float]:
    return ra + east / 3600.0 / np.cos(np.radians(dec)), dec + north / 3600.0


def reflex_search(ra: float, dec: float, fov: float = 0.13, detectors: tuple[int, ...] = (1, 2, 3),
                  visit: tuple[float, float] | None = None, nearest_au: float = 50.0, progress=None,
                  threshold: float | None = None, use_cache: bool = True, label: bool = True,
                  shuffle_seed: int | None = None) -> dict:
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
    base = {"method": "Earth-reflex shift-and-stack, one visit", "credit": CREDIT, "depth_note": DEPTH_NOTE,
            "version": VERSION, "searched_area_deg2": round(SEARCHED_AREA_DEG2(fov), 4), "fov_deg": fov,
            "detectors": list(detectors), "centre": {"ra": ra, "dec": dec}}
    if iv is None or len(visits) < 2:
        why = "no visit with enough exposures" if iv is None else "only one visit covers this patch, so there is no fixed-sky template"
        return {**base, "status": "cannot_search", "answer": f"Cannot search this patch: {why}.", "reason": why,
                "n_visits": len(visits)}
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
        return {**base, "status": "cannot_search", "answer": "Cannot search this patch: fewer than 10 usable exposures.",
                "reason": "too few usable exposures", "n_failed_cutouts": len(failed)}
    tmap = None
    if shuffle_seed is not None:     # control: exposure times shuffled within the visit (images keep their order)
        perm = np.random.default_rng(shuffle_seed).permutation(len(cube["T"]))
        tmap = dict(zip(cube["keys"], cube["T"][perm], strict=True))
        cube["T"] = cube["T"][perm]
    t0 = float(np.median(cube["T"]))
    fnl, flin = parallax_curve(cube["T"], ra, dec, t0)
    lever = [float(np.ptp(fnl[:, 0])), float(np.ptp(fnl[:, 1]))]
    dtf = cube["T"] - t0
    slope = (float(np.polyfit(dtf, flin[:, 0], 1)[0]), float(np.polyfit(dtf, flin[:, 1], 1)[0]))
    visit_info = {"mjd_first": lo, "mjd_last": hi, "duration_days": round(duration, 2), "n_exposures": len(chosen),
                  "n_used": int(len(cube["D"])), "mjd_t0": t0,
                  "distance_leverage_arcsec_per_inv_au": [round(x) for x in lever],
                  "median_of_difference_maps_mjy": cube["median_diff"]}
    coarse = coarse_search(cube, fnl, slope, t0, nearest_au, progress=progress)
    trials = coarse["trials"]
    n_trials = coarse["n_trials"]
    pos = [t for t in trials if t[1] > -1e-9]
    neg = [t for t in trials if t[1] < -1e-9]
    peaks = [p for p in merge_peaks(pos) if p["snr"] >= threshold]
    control_peaks = merge_peaks(neg)
    # a reversed-Earth peak right on top of a real body is that body leaking in; the control is what is left elsewhere
    away = [p for p in control_peaks
            if all(np.hypot(p["east"] - q["east"], p["north"] - q["north"]) > 30 for q in merge_peaks(pos)[:1] if q["snr"] >= threshold)]
    control_peaks = away
    control = {"best_reversed_snr": control_peaks[0]["snr"] if control_peaks else None,
               "place_east_north_arcsec": [control_peaks[0]["east"], control_peaks[0]["north"]] if control_peaks else None,
               "n_reversed_trials": len(neg), "n_reversed_above_threshold": sum(1 for p in control_peaks if p["snr"] >= threshold)}
    limit = None
    # noise of the stacked mean flux in one trial = 1/sqrt(sum w): the flux that gives `threshold` sigma
    mean_noise = float(1.0 / np.sqrt(cube["W"].sum()))
    limit = {"threshold_snr": threshold, "stacked_mean_noise_mjy": round(mean_noise, 5),
             "faintest_mean_flux_mjy": round(threshold * mean_noise, 4), "detectors": list(detectors),
             "searched_area_deg2": base["searched_area_deg2"], "distance_range_au": [nearest_au, "about 1000"],
             "note": DEPTH_NOTE}
    out: dict[str, Any] = {**base, "visit": visit_info, "control": control, "limit": limit, "n_trials": n_trials,
                           "n_visits": len(visits), "n_failed_cutouts": len(failed),
                           "top_unthresholded_peaks": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()}
                                                       for p in merge_peaks(pos)[:5]]}
    candidates = []
    if peaks:
        cube_f = build_cube(exposures, paths, chosen, ra, dec, fov, FINE_ARCSEC, detectors)
        keep = [i for i, k in enumerate(cube_f["keys"]) if k in set(cube["keys"])]
        dcf = cube_f["D"][keep]
        tf = cube_f["T"][keep]
        if tmap is not None:
            tf = np.array([tmap[cube_f["keys"][i]] for i in keep])
        fnl_f, _ = parallax_curve(tf, ra, dec, t0)
        track = Track(dcf, cube_f["W"][keep], tf - t0, fnl_f, FINE_ARCSEC)
        dets_f = cube_f["det"][keep]
        half = fov / 2 * 3600.0 - 10
        for p in peaks[:5]:
            res = refine(track, (p["east"], p["north"], p["ve"], p["vn"]), p["inv_d"], nearest_au, half)
            ib = res["best_index"]
            best_inv = res["best_inv_d"]
            c_east, c_north = res["place"]
            c_ra, c_dec = _sky(ra, dec, c_east, c_north)
            dets = per_detector(track, res, dets_f, half)
            n_det = sum(1 for v in dets.values() if v["snr"] is not None and v["snr"] >= 2.0)
            mean_flux, _ = track.flux(res["params"][ib], best_inv)
            there = still_there(cube, c_east, c_north, mean_flux, detectors, t0, others)
            measured = res["delta_s2_infinite"] >= MEASURED_DELTA_S2 and best_inv > 0
            near1, far1 = res["interval_1sigma"]
            near2, far2 = res["interval_2sigma"]
            cand: dict[str, Any] = {
                "ra": round(c_ra, 6), "dec": round(c_dec, 6), "mjd_t0": t0,
                "offset_arcsec": [round(c_east, 2), round(c_north, 2)],
                "drift_arcsec_day": [round(res["drift"][0], 3), round(res["drift"][1], 3)],
                "snr": round(res["best_snr"], 2), "coarse_snr": round(p["snr"], 2),
                "mean_flux_mjy": round(mean_flux, 4), "per_detector": dets, "n_detectors_with_2sigma": n_det,
                "still_there": there, "delta_s2_infinite": round(res["delta_s2_infinite"], 1),
                "snr_at_infinity": round(res["snr_infinite"], 2),
                "reversed_earth_snr_mirror_distance": round(float(res["snr"][int(np.argmin(np.abs(res["grid"] + best_inv)))]), 2)
                if best_inv > 0 and res["grid"].min() <= -best_inv else None,
                "distance_measured": bool(measured and duration >= MIN_DISTANCE_DAYS),
                "profile": {"inv_d": [round(float(x), 5) for x in res["grid"][::2]], "snr": [round(float(x), 2) for x in res["snr"][::2]]},
            }
            if cand["distance_measured"]:
                cand.update({"distance_au": round(1.0 / best_inv, 1),
                             "interval_1sigma_au": [None if near1 is None else round(near1, 1), None if far1 is None else round(far1, 1)],
                             "interval_2sigma_au": [None if near2 is None else round(near2, 1), None if far2 is None else round(far2, 1)]})
            else:
                # lower limit: the nearest distance still within 2 sigma (S^2 >= best - 4)
                cand.update({"distance_au": None, "lower_limit_au": None if near2 is None else round(near2, 1),
                             "note": "distance not measured: the signal is not significantly better than at infinite distance"
                             if duration >= MIN_DISTANCE_DAYS else "visit shorter than 8 days: detection only"})
            candidates.append(cand)
        if label:
            lab = label_known(t0, ra, dec, fov, [(c["ra"], c["dec"]) for c in candidates])
            out["known_body_labelling"] = {k: v for k, v in lab.items() if k != "near"}
            for c, near in zip(candidates, lab["near"], strict=True):
                c["known_body"] = near
        for c in candidates:
            gone_fixed = any(v.get("there") for v in c["still_there"])
            if c.get("known_body"):
                c["verdict"] = "known body (JPL sb_ident within 30 arcsec): not a candidate"
            elif gone_fixed:
                c["verdict"] = "still there in another visit at the same place: a fixed or variable source, rejected"
            elif c["n_detectors_with_2sigma"] < 2:
                c["verdict"] = "shows in fewer than two detectors: rejected"
            else:
                c["verdict"] = "candidate (unexplained moving source; not a discovery)"
    out["candidates"] = candidates
    good = [c for c in candidates if c["verdict"].startswith("candidate")]
    out["status"] = "candidates" if good else "nothing_found"
    if good:
        c = good[0]
        dist = (f"at about {c['distance_au']:.0f} AU (2 sigma {c['interval_2sigma_au'][0]} to {c['interval_2sigma_au'][1]} AU)"
                if c.get("distance_au") else "with no measured distance")
        out["answer"] = (f"{len(good)} unexplained moving source(s); the strongest has S/N {c['snr']:.1f} {dist}. "
                         "A candidate, not a discovery. " + DEPTH_NOTE)
    else:
        out["answer"] = (f"Nothing moving above S/N {threshold:g} in {base['searched_area_deg2']} square degrees, "
                         f"{nearest_au:g} to about 1000 AU, one visit: stacked mean flux limit "
                         f"{limit['faintest_mean_flux_mjy']} mJy in D{'/D'.join(str(d) for d in detectors)}. " + DEPTH_NOTE)
    out["runtime_s"] = round(time.time() - started, 1)
    out["map_and_search_s"] = round(time.time() - t_maps, 1)
    if use_cache:
        REFLEX_DIR.mkdir(parents=True, exist_ok=True)
        spherex.write_json(cache_file, out)
    return out

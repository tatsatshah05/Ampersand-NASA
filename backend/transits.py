"""A planet crossing its star, seen in SPHEREx deep-field exposures.

Near the two ecliptic poles SPHEREx looks at the same stars thousands of times, one
wavelength per exposure. A star that has a known planet on a known orbit is measured in
every exposure, each reading is divided by the star's own brightness at that wavelength
(made from its out-of-transit readings), and the readings are fitted with the shape of
the transit fixed by the published ephemeris. Fake ephemerides (wrong periods and phases)
give the noise of the depth, because the noise of SPHEREx readings is correlated.

Real data only. Nothing here simulates a reading. The arithmetic helpers are tested on
made-up arrays in `tests/test_transits.py`, labelled as such.

The one entry function is `transit_check`. Cutouts come from the public S3 bucket
(`s3fetch`), exposure lists from IRSA's image search in all four collections (the deep
ones are NOT in `spherex.COLLECTIONS`; this module asks for them itself and does not
change that setting).
"""
from __future__ import annotations

import hashlib
import json
import logging
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area

from . import astrometry, photometry, pipeline, s3fetch, spherex

log = logging.getLogger(__name__)

VERSION = 1
CACHE = spherex.CACHE / "transits"
COLLECTIONS = ("spherex_dr1", "spherex_qr3", "spherex_dr1_deep", "spherex_qr3_deep")

APERTURE_PX = 2.5                 # radius of the measuring circle, native pixels
SKY_RING_PX = (6.0, 10.0)         # ring the local sky level is taken from
TEMPLATE_NEIGHBOURS = 30          # readings of the star's own spectrum that make its template
NEAR_TRANSIT_DAYS = 0.35          # readings this close to a transit are kept for the baseline
RANDOM_OTHERS = 300
OVERFLOW_LIMIT = 0.20             # a detector with more ok readings than this share holding an OVERFLOW pixel is left out
CLIP_SIGMA = 5.0
FAKE_PERIODS = (1.5, 9.0, 0.005)  # start, stop, step in days
FAKE_EXCLUDE = (0.5, 1.0, 1.5, 2.0, 3.0)   # fake periods this close to a simple ratio of the real one are skipped
FAKE_EXCLUDE_TOL = 0.02
FAKE_OFFSETS = (0.0, 0.25, 0.5, 0.75)   # phase offsets tried at every fake period
MIN_FAKE_IN_TRANSIT = 30
SLIDE_HOURS = tuple(float(h) for h in np.arange(-12.0, 12.01, 1.5))
YEAR_SPLIT_BJD = 2461041.5        # 2026-01-01
MIN_IN_TRANSIT = 15               # fewer in-transit readings than this and a detector is not fitted
# Analysis choices the judges flagged, each re-run on the same readings (the default is the first line of the table).
CHOICES: dict[str, dict[str, Any]] = {
    "no detector-position terms": {"detrend": "none", "subpixel": False},
    "linear detector-position terms": {"detrend": "linear"},
    "no sub-pixel terms": {"subpixel": False},
    "template of 14 neighbours": {"k": 14},
    "template of 60 neighbours": {"k": 60},
    "clip at 4 sigma": {"clip": 4.0},
    "no clipping": {"clip": None},
}


# --------------------------------------------------------------------------- arithmetic

def trapezoid(dt_days: np.ndarray | float, t14_h: float, rprs: float) -> np.ndarray:
    """Transit shape: 1 in the flat bottom, 0 outside, linear in ingress and egress.

    `dt_days` is the time from mid-transit. T23 = T14 (1 - k) / (1 + k), the central-transit
    relation; the published impact parameter is not used.
    """
    t23 = t14_h * (1 - rprs) / (1 + rprs)
    a = np.abs(np.asarray(dt_days, dtype=float)) * 24.0
    return np.clip((t14_h / 2 - a) / ((t14_h - t23) / 2), 0.0, 1.0)


def bjd_tdb(mjd_utc: np.ndarray, ra: float, dec: float) -> np.ndarray:
    """Barycentric Julian date (TDB) of mid-exposure times given as MJD (UTC).

    SPHEREx is in low Earth orbit, about 700 km up, so the geocentre is used as the
    place of the observer: the error is under 25 ms.
    """
    t = Time(np.asarray(mjd_utc, dtype=float), format="mjd", scale="utc",
             location=EarthLocation.from_geocentric(0, 0, 0, unit=u.m))
    ltt = t.light_travel_time(SkyCoord(ra * u.deg, dec * u.deg), kind="barycentric")
    return np.asarray((t.tdb + ltt).jd, dtype=float)


def time_from_mid(bjd: np.ndarray, period: float, t0: float) -> np.ndarray:
    """Days from the nearest mid-transit, in (-P/2, P/2]."""
    return (((bjd - t0) / period + 0.5) % 1.0 - 0.5) * period


def robust_std(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else float("nan")


def template_divide(wl: np.ndarray, flux: np.ndarray, use: np.ndarray, k: int = TEMPLATE_NEIGHBOURS) -> np.ndarray:
    """Each reading divided by the star's own brightness at its wavelength.

    The template is the median of the `k` nearest readings in log wavelength among those
    flagged in `use` (the out-of-transit readings). A reading in `use` is never part of
    its own template.
    """
    lw = np.log(np.asarray(wl, dtype=float))
    order = np.argsort(lw[use], kind="stable")
    lw_u, f_u = lw[use][order], np.asarray(flux, dtype=float)[use][order]
    n = len(lw_u)
    rel = np.full(len(lw), np.nan)
    if n < 3:
        return rel
    half = k // 2
    pos_in_use = {int(i): j for j, i in enumerate(np.where(use)[0][order])}
    for i in range(len(lw)):
        j = int(np.searchsorted(lw_u, lw[i]))
        lo, hi = max(0, j - half), min(n, j + half)
        idx = np.arange(lo, hi)
        own = pos_in_use.get(i)
        if own is not None:
            idx = idx[idx != own]
        if len(idx):
            rel[i] = flux[i] / np.median(f_u[idx])
    return rel


def design(cols: dict[str, np.ndarray], shape: np.ndarray, detrend: str = "quadratic", subpixel: bool = True) -> np.ndarray:
    """Columns: constant, detector-position terms, sub-pixel phase, minus the transit shape."""
    x = (cols["X"] - cols["X"].mean()) / (cols["X"].std() + 1e-9)
    y = (cols["Y"] - cols["Y"].mean()) / (cols["Y"].std() + 1e-9)
    parts = [np.ones(len(x))]
    if detrend in ("linear", "quadratic"):
        parts += [x, y]
    if detrend == "quadratic":
        parts += [x * x, y * y, x * y]
    if subpixel:
        parts += [cols["fx"] - 0.5, cols["fy"] - 0.5]
    parts.append(-shape)
    return np.vstack(parts).T


def fit_depth(rel: np.ndarray, A: np.ndarray, sigma: float) -> tuple[float, float, np.ndarray]:
    """Least squares. Returns depth (fraction of the star's light), its formal error, residuals."""
    try:
        cov = np.linalg.inv(A.T @ A) * sigma ** 2
    except np.linalg.LinAlgError:           # no reading inside the shape: no depth can be fitted
        return float("nan"), float("nan"), np.full(len(rel), np.nan)
    p = cov @ (A.T @ rel) / sigma ** 2
    return float(p[-1] / p[0]), float(np.sqrt(cov[-1, -1]) / p[0]), rel - A @ p


def fake_ephemerides(period: float) -> list[tuple[float, float]]:
    """(fake period, phase offset) pairs: periods 1.5 to 9 d, phase offset 0 and 0.5,
    skipping periods within 2 per cent of 1/2, 1, 3/2, 2 and 3 times the real one."""
    out = []
    for pf in np.arange(FAKE_PERIODS[0], FAKE_PERIODS[1] + 1e-9, FAKE_PERIODS[2]):
        if min(abs(pf / period - q) for q in FAKE_EXCLUDE) < FAKE_EXCLUDE_TOL:
            continue
        out += [(float(pf), o) for o in FAKE_OFFSETS]
    return out


# --------------------------------------------------------------------------- exposure lists and cutouts

def exposure_list(ra: float, dec: float, cache_dir: Path | None = None, *, seed_file: Path | None = None) -> list[dict]:
    """Every level-2 image covering the point, in all four collections, one request at a time.

    Cached on disk. `seed_file` is an earlier answer in the same format (a list of the
    dicts `spherex.find_exposures` returns) that is used instead of asking.
    """
    cache_dir = Path(cache_dir or CACHE) / "queries"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"exposures_{ra:.5f}_{dec:.5f}.json"
    if path.exists():
        return json.loads(path.read_text())
    if seed_file is not None and Path(seed_file).exists():
        exps = json.loads(Path(seed_file).read_text())
    else:
        seen: dict[tuple[str, int], dict] = {}
        saved = spherex.COLLECTIONS
        try:
            for coll in COLLECTIONS:       # one at a time: the deep ones return tens of MB
                spherex.COLLECTIONS = [coll]       # type: ignore[misc]
                for e in spherex._query_exposures(ra, dec):
                    seen.setdefault((e["obs_id"], e["detector"]), e)
        finally:
            spherex.COLLECTIONS = saved            # type: ignore[misc]
        exps = sorted(seen.values(), key=lambda e: e["mjd"])
    spherex.write_json(path, exps)
    return exps


def mid_times(exps: Sequence[dict]) -> np.ndarray:
    """Mid-exposure time, MJD (UTC)."""
    return np.array([e["mjd"] + e["exptime"] / 2 / 86400 for e in exps], dtype=float)


def select_readings(exps: Sequence[dict], bjd: np.ndarray, period: float, t0: float, t14_h: float, detector: int, *,
                    cutout_roots: Sequence[Path] = (), ra: float = 0.0, dec: float = 0.0, size_deg: float = 0.05,
                    max_n: int = 900, seed: int = 1) -> list[int]:
    """Indices of the exposures to read for one detector.

    All in-transit readings, all within 0.35 d of a transit centre, every one whose
    cutout is already on disk, and a fixed-seed random set of others up to 300. Capped at
    `max_n`, always keeping the in-transit ones.
    """
    det = np.array([e["detector"] for e in exps])
    dt = time_from_mid(bjd, period, t0)
    in_tr = np.abs(dt) < t14_h / 48.0
    near = np.abs(dt) < NEAR_TRANSIT_DAYS
    on_disk = np.zeros(len(exps), bool)
    for i in np.where(det == detector)[0]:
        on_disk[i] = any(s3fetch.cutout_path(r, exps[i], ra, dec, size_deg).exists() for r in cutout_roots)
    base = (det == detector) & (in_tr | near | on_disk)
    others = np.where((det == detector) & ~base)[0]
    rng = np.random.default_rng(seed)
    n_extra = max(0, RANDOM_OTHERS - int((on_disk & ~in_tr & ~near & (det == detector)).sum()))
    extra = rng.choice(others, size=min(n_extra, len(others)), replace=False) if len(others) else np.array([], int)
    idx = sorted(set(np.where(base)[0].tolist()) | set(int(i) for i in extra))
    if len(idx) > max_n:
        keep_first = [i for i in idx if in_tr[i]]
        rest = [i for i in idx if not in_tr[i]]
        rng2 = np.random.default_rng(seed + 1)
        rest = sorted(rng2.choice(rest, size=max(0, max_n - len(keep_first)), replace=False).tolist()) if rest else []
        idx = sorted(keep_first + rest)
    return idx


def get_cutouts(exps: Sequence[dict], ra: float, dec: float, size_deg: float, cache_dir: Path | None = None, *,
                cutout_roots: Sequence[Path] = (), max_concurrent: int = 12, fetch: bool = True,
                progress: Callable[[int, int], None] | None = None) -> tuple[dict[tuple[str, int], Path], list[dict]]:
    """Paths of the cutouts, reusing any root that already holds them; fetches the rest from S3.

    Returns ({(obs_id, detector): path}, failures). A failure is listed, never filled in.
    """
    root = Path(cache_dir or CACHE) / "cutouts"
    paths: dict[tuple[str, int], Path] = {}
    todo = []
    for e in exps:
        key = (e["obs_id"], e["detector"])
        for r in (*cutout_roots, root):
            p = s3fetch.cutout_path(r, e, ra, dec, size_deg)
            if p.exists():
                paths[key] = p
                break
        else:
            todo.append(e)
    failures: list[dict] = []
    if todo and fetch:
        for e, p, err in s3fetch.fetch_cutouts(todo, ra, dec, size_deg, root, max_concurrent=max_concurrent,
                                               progress=progress):
            if p is None:
                failures.append({"obs_id": e["obs_id"], "detector": e["detector"], "error": err})
            else:
                paths[(e["obs_id"], e["detector"])] = p
    return paths, failures


# --------------------------------------------------------------------------- photometry

def measure_cutout(path: Path, positions: Sequence[tuple[float, float]], *, aperture_px: float = APERTURE_PX,
                   accept_halo: bool = False) -> list[dict | None]:
    """Aperture photometry at each (ra, dec) of one cutout, as `photometry` does it.

    Circle of `aperture_px` native pixels, clipped-median sky from a 6 to 10 pixel ring, zodiacal light
    subtracted, impossible pixels left out. With `accept_halo` the HALO flag does not rule out
    pixels in the circle (the sky ring still ignores them). None when the position is too close to the
    edge or has no wavelength.
    """
    with fits.open(path) as hdul, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = np.asarray(hdul["FLAGS"].data).copy()
        var = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data
        wcs = WCS(header)
    ny, nx = image.shape
    data = image - zodi
    data[pipeline.impossible_pixels(image, var)] = np.nan
    to_mjy = float(proj_plane_pixel_area(wcs)) * (np.pi / 180) ** 2 * 1e9
    sky_bad = photometry.SKY_BAD & ~pipeline._mask("SOURCE")
    core_flags = flags & ~pipeline._mask("HALO") if accept_halo else flags
    yy, xx = np.mgrid[0:ny, 0:nx]
    crpix = [float(header.get("CRPIX1", np.nan)), float(header.get("CRPIX2", np.nan))]
    out: list[dict | None] = []
    edge = SKY_RING_PX[1] + 1
    for ra, dec in positions:
        x, y = (float(v) for v in wcs.all_world2pix(ra, dec, 0))
        if not (edge <= x < nx - edge and edge <= y < ny - edge):
            out.append(None)
            continue
        wl = float(wave[int(round(y)), int(round(x))])
        r = np.hypot(xx - x, yy - y)
        ring = (r >= SKY_RING_PX[0]) & (r < SKY_RING_PX[1]) & np.isfinite(data) & ((flags & sky_bad) == 0)
        if not np.isfinite(wl) or ring.sum() < 40:
            out.append(None)
            continue
        _, sky, ssig = sigma_clipped_stats(data[ring], sigma=3.0, maxiters=5)
        core = photometry._sum_region(photometry._coverage(xx, yy, x, y, 0.0, aperture_px), data, var, core_flags,
                                      float(sky), float(ssig) ** 2 / ring.sum(), to_mjy)
        out.append({"status": core["status"], "flux": core["value"], "err": core["error_stat"], "wl": wl,
                    "x": x - nx / 2, "y": y - ny / 2, "ovf": int(core["overflow_pixels"]), "flags": core["flags"],
                    "crpix": crpix})
    return out


def measure_series(exps: Sequence[dict], paths: dict[tuple[str, int], Path], positions: Sequence[tuple[float, float]], *,
                   aperture_px: float = APERTURE_PX, accept_halo: bool = False, cache_file: Path | None = None) -> list[dict]:
    """One row per exposure: time and, for each position, the measurement (or None). Cached as JSON."""
    if cache_file is not None and cache_file.exists():
        return json.loads(cache_file.read_text())
    rows = []
    for e in exps:
        p = paths.get((e["obs_id"], e["detector"]))
        if p is None:
            continue
        try:
            m = measure_cutout(p, positions, aperture_px=aperture_px, accept_halo=accept_halo)
        except (OSError, KeyError, ValueError) as err:     # unreadable file: reported by absence, never filled in
            log.warning("cutout %s unreadable: %s", p, err)
            continue
        rows.append({"obs_id": e["obs_id"], "detector": e["detector"], "collection": e.get("collection"),
                     "mjd": e["mjd"] + e["exptime"] / 2 / 86400, "m": m})
    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        spherex.write_json(cache_file, rows)
    return rows


def columns(rows: Sequence[dict], which: int, ra: float, dec: float) -> dict[str, np.ndarray]:
    """Arrays for one position (index `which` of the measured positions) from `measure_series` rows."""
    keep = [r for r in rows if r["m"][which] is not None]
    t = [r["m"][which] for r in keep]
    ok = np.array([x["status"] == "ok" for x in t], bool)
    return {
        "bjd": bjd_tdb(np.array([r["mjd"] for r in keep]), ra, dec),
        "det": np.array([r["detector"] for r in keep]),
        "flux": np.array([x["flux"] if x["status"] == "ok" else np.nan for x in t], float),
        "err": np.array([x["err"] if x["status"] == "ok" else np.nan for x in t], float),
        "wl": np.array([x["wl"] for x in t], float),
        "X": np.array([-x["crpix"][0] for x in t], float), "Y": np.array([-x["crpix"][1] for x in t], float),
        "fx": np.array([x["x"] % 1 for x in t], float), "fy": np.array([x["y"] % 1 for x in t], float),
        "ovf": np.array([x["ovf"] for x in t], int), "ok": ok,
    }


# --------------------------------------------------------------------------- analysis of one detector

def analyse_detector(c: dict[str, np.ndarray], period: float, t0: float, t14_h: float, rprs: float, *,
                     detrend: str = "quadratic", subpixel: bool = True, k: int = TEMPLATE_NEIGHBOURS,
                     clip: float | None = CLIP_SIGMA, extras: bool = True, min_n: int = 50,
                     min_in: int = MIN_IN_TRANSIT, min_fake: int = MIN_FAKE_IN_TRANSIT,
                     max_dev: float = 0.15) -> dict[str, Any]:
    """Depth, errors and every control for one detector's readings of one star.

    `c` holds the arrays of one detector (`columns`). Depth is a fraction of the star's light.
    With extras: fake ephemerides, time slide, per-year fits, leave-out-the-most-helpful-transits.
    """
    bjd = c["bjd"]
    shape0 = trapezoid(time_from_mid(bjd, period, t0), t14_h, rprs)
    okm = c["ok"] & np.isfinite(c["flux"])
    rel = np.full(len(bjd), np.nan)
    rel[okm] = template_divide(c["wl"][okm], c["flux"][okm], (shape0 == 0)[okm], k)
    m = okm & (np.abs(rel - 1) < max_dev)
    res: dict[str, Any] = {"n_ok": int(okm.sum()), "n_overflow": int((okm & (c["ovf"] > 0)).sum())}
    if m.sum() < min_n or (m & (shape0 > 0)).sum() < min_in:
        res.update(status="too few readings", n=int(m.sum()), n_in=int((m & (shape0 > 0)).sum()))
        return res
    sub = {key: v[m] for key, v in c.items()}
    A = design(sub, shape0[m], detrend, subpixel)
    _, _, resid = fit_depth(rel[m], A, 1.0)
    sig = robust_std(resid)
    keep = m.copy()
    if clip is not None:
        keep[m] = np.abs(resid) < clip * sig
    sub = {key: v[keep] for key, v in c.items()}
    A = design(sub, shape0[keep], detrend, subpixel)
    depth, err, resid = fit_depth(rel[keep], A, sig)
    sig = robust_std(resid)
    err = fit_depth(rel[keep], A, sig)[1]
    n_in = int((keep & (shape0 > 0)).sum())
    wl_in = c["wl"][keep]
    res.update(status="ok", n=int(keep.sum()), n_in=n_in, scatter=sig,
               photon=float(np.nanmedian(c["err"][keep] / c["flux"][keep])), median_flux_mjy=float(np.nanmedian(c["flux"][keep])),
               wl_min=float(wl_in.min()), wl_max=float(wl_in.max()), depth=depth, formal_err=err,
               n_transits=int(len(set(np.round((bjd[keep & (shape0 > 0)] - t0) / period).astype(int)))))
    if not extras:
        return res

    out = keep & (shape0 == 0)
    nulls = []
    base_cols = {key: v[out] for key, v in c.items()}
    for pf, off in fake_ephemerides(period):
        sf = trapezoid(time_from_mid(bjd[out] - off * pf, pf, t0), t14_h, rprs)
        if (sf > 0).sum() < min_fake:
            continue
        nulls.append(fit_depth(rel[out], design(base_cols, sf, detrend, subpixel), sig)[0])
    nul = np.array(nulls)
    emp = float(np.std(nul)) if len(nul) > 3 else float("nan")
    res.update(n_fake=len(nul), fake_mean=float(np.mean(nul)) if len(nul) else float("nan"), empirical_err=emp,
               empirical_sigma=depth / emp if emp > 0 else float("nan"),
               fake_share_as_deep=float(np.mean(nul >= depth)) if len(nul) else float("nan"),
               noise_factor=emp / err if err > 0 else float("nan"))

    # slide the assumed transit time
    slide = []
    for dh in SLIDE_HOURS:
        sh = trapezoid(time_from_mid(bjd - dh / 24.0, period, t0), t14_h, rprs)
        d, e, _ = fit_depth(rel[keep], design(sub, sh[keep], detrend, subpixel), sig)
        slide.append({"offset_h": dh, "depth": d, "formal_err": e})
    res["time_slide"] = slide
    res["slide_peak_h"] = float(SLIDE_HOURS[int(np.nanargmax([s["depth"] for s in slide]))])

    # each year (split at 2026-01-01) on its own, with its own sigma and detrending
    years = {}
    for name, half in (("2025", bjd < YEAR_SPLIT_BJD), ("2026", bjd >= YEAR_SPLIT_BJD)):
        mm = keep & half
        if (mm & (shape0 > 0)).sum() >= 10:
            sb = {key: v[mm] for key, v in c.items()}
            d, e, rr = fit_depth(rel[mm], design(sb, shape0[mm], detrend, subpixel), 1.0)
            s2 = robust_std(rr)
            d, e, _ = fit_depth(rel[mm], design(sb, shape0[mm], detrend, subpixel), s2)
            years[name] = {"n": int(mm.sum()), "n_in": int((mm & (shape0 > 0)).sum()), "depth": d, "formal_err": e}
    res["years"] = years

    # leave out the most helpful transits, one at a time, greedily
    epoch = np.round((bjd - t0) / period).astype(int)
    epochs = sorted(set(epoch[keep & (shape0 > 0)].tolist()))
    drops = []
    alive = keep.copy()
    for step in range(min(5, max(0, len(epochs) - 3))):
        best = None
        for ep in epochs:
            if ep in [d["epoch"] for d in drops]:
                continue
            mm = alive & ~((epoch == ep) & (shape0 > 0))
            sb = {key: v[mm] for key, v in c.items()}
            d, e, _ = fit_depth(rel[mm], design(sb, shape0[mm], detrend, subpixel), sig)
            if np.isfinite(d) and (best is None or d < best[1]):
                best = (ep, d, e, mm)
        assert best is not None
        alive = best[3]
        drops.append({"epoch": int(best[0]), "left_out": step + 1, "depth": best[1], "formal_err": best[2]})
    res["leave_out"] = drops
    # one at a time: spread over all single-transit omissions
    single = []
    for ep in epochs:
        mm = keep & ~((epoch == ep) & (shape0 > 0))
        sb = {key: v[mm] for key, v in c.items()}
        single.append(fit_depth(rel[mm], design(sb, shape0[mm], detrend, subpixel), sig)[0])
    res["jackknife_min"], res["jackknife_max"] = float(min(single)), float(max(single))

    # folded, detrended light curve for the picture
    coef = np.linalg.lstsq(A, rel[keep], rcond=None)[0]
    corr = (rel[keep] - A[:, 1:-1] @ coef[1:-1]) / coef[0]
    res["folded"] = {"hours": (time_from_mid(bjd[keep], period, t0) * 24).tolist(), "flux": corr.tolist(),
                     "wl": wl_in.tolist()}
    return res


# --------------------------------------------------------------------------- entry function

def transit_check(ra: float, dec: float, period_d: float, t0_bjd_tdb: float, t14_h: float, rprs: float,
                  detectors: Sequence[int] = (1, 2, 3, 4, 5, 6), name: str | None = None, accept_halo: bool = False,
                  max_cutouts_per_detector: int = 900, *, size_deg: float = 0.05, cache_dir: Path | None = None,
                  cutout_roots: Sequence[Path] = (), exposure_seed: Path | None = None, fetch: bool = True,
                  comparison_stars: bool = True, aperture_px: float = APERTURE_PX, extras: bool = True,
                  progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Measure a known planet's transit depth in every detector that has enough readings.

    Returns JSON-ready data: per detector the depth with its formal and empirical errors,
    the fake-ephemeris share, the time slide, the per-year and leave-out fits, the same fit on
    steady Gaia comparison stars measured in the same exposures, and coverage counts.
    Nothing is simulated; a cutout that cannot be read is listed under `failures`.
    """
    cache_dir = Path(cache_dir or CACHE)
    exps = exposure_list(ra, dec, cache_dir, seed_file=exposure_seed)
    bjd_all = bjd_tdb(mid_times(exps), ra, dec)
    coverage: dict[str, Any] = {"exposures": len(exps),
                                "per_collection": {c: sum(e.get("collection") == c for e in exps) for c in COLLECTIONS},
                                "per_detector": {d: sum(e["detector"] == d for e in exps) for d in range(1, 7)},
                                "mjd_first": float(min(e["mjd"] for e in exps)) if exps else None,
                                "mjd_last": float(max(e["mjd"] for e in exps)) if exps else None}
    dt_all = time_from_mid(bjd_all, period_d, t0_bjd_tdb)
    in_all = np.abs(dt_all) < t14_h / 48.0
    coverage["in_transit_per_detector"] = {d: int((in_all & np.array([e["detector"] == d for e in exps])).sum())
                                           for d in range(1, 7)}
    comps: list[dict] = []
    if comparison_stars:
        comps = comparison_candidates(ra, dec, size_deg)
    positions = [(ra, dec)] + [(s["ra"], s["dec"]) for s in comps]
    out: dict[str, Any] = {"name": name, "version": VERSION, "ra": ra, "dec": dec, "period_d": period_d,
                           "t0_bjd_tdb": t0_bjd_tdb, "t14_h": t14_h, "rprs": rprs,
                           "expected_depth": rprs ** 2, "accept_halo": accept_halo, "aperture_px": aperture_px,
                           "coverage": coverage, "detectors": {}, "comparison_stars": comps, "failures": []}
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size_deg},{aperture_px},{accept_halo}".encode()).hexdigest()[:10]
    for d in detectors:
        idx = select_readings(exps, bjd_all, period_d, t0_bjd_tdb, t14_h, d,
                              cutout_roots=[*cutout_roots, cache_dir / "cutouts"], ra=ra,
                              dec=dec, size_deg=size_deg, max_n=max_cutouts_per_detector)
        sel = [exps[i] for i in idx]
        paths, failures = get_cutouts(sel, ra, dec, size_deg, cache_dir, cutout_roots=cutout_roots, fetch=fetch,
                                      progress=progress)
        out["failures"] += failures
        rows = measure_series(sel, paths, positions, aperture_px=aperture_px, accept_halo=accept_halo,
                              cache_file=cache_dir / "results" / f"rows_{tag}_{d}_{len(sel)}.json")
        if not rows:
            out["detectors"][str(d)] = {"status": "no readings"}
            continue
        c = columns(rows, 0, ra, dec)
        det_res = analyse_detector(c, period_d, t0_bjd_tdb, t14_h, rprs, extras=extras)
        if det_res.get("status") == "ok" and det_res["n_overflow"] > OVERFLOW_LIMIT * det_res["n_ok"]:
            det_res["excluded"] = (f"{det_res['n_overflow']} of {det_res['n_ok']} ok readings hold an OVERFLOW "
                                   f"pixel: the star is too bright in this detector")
        det_res["n_cutouts"] = len(rows)
        if extras and det_res.get("status") == "ok":
            det_res["choices"] = {}
            for label, kw in CHOICES.items():
                rc = analyse_detector(c, period_d, t0_bjd_tdb, t14_h, rprs, extras=False, **kw)
                if rc.get("status") == "ok":
                    det_res["choices"][label] = {key: rc[key] for key in ("n", "n_in", "depth", "formal_err")}
            det_res["comparison"] = []
            for j, s in enumerate(comps, start=1):
                cj = columns(rows, j, s["ra"], s["dec"])
                if len(cj["bjd"]) < 100:
                    continue
                rj = analyse_detector(cj, period_d, t0_bjd_tdb, t14_h, rprs, extras=True)
                if rj.get("status") != "ok":
                    continue
                rj = {k: v for k, v in rj.items() if k not in ("folded", "time_slide", "leave_out", "years")}
                rj.update(gaia_source_id=s["source_id"], gmag=s["gmag"], distance_arcsec=s["distance_arcsec"])
                det_res["comparison"].append(rj)
        out["detectors"][str(d)] = det_res
    out["answer"] = answer_text(out)
    return out


def comparison_candidates(ra: float, dec: float, size_deg: float, g_min: float = 10.5, g_max: float = 15.0,
                          isolation_arcsec: float = 15.0) -> list[dict]:
    """Isolated Gaia DR3 stars in the cutout to use as steady comparison stars.

    G between 10.5 and 14.5, at least 20 arcsec from the target, no other G < 17 star within
    15 arcsec (so each is a clean point source), inside 0.8 of the cutout half-size.
    """
    cone = astrometry.gaia_cone(ra, dec, size_deg, 17.0)
    out = []
    for s in cone:
        dx, dy = astrometry.offset_arcsec(ra, dec, s["ra"], s["dec"])
        dist = float(np.hypot(dx, dy))
        if not (20.0 < dist < 0.8 * size_deg / 2 * 3600) or not g_min <= s["gmag"] <= g_max:
            continue
        near = [o for o in cone if o is not s and np.hypot(*astrometry.offset_arcsec(s["ra"], s["dec"], o["ra"], o["dec"])) < isolation_arcsec]
        if near:
            continue
        out.append({"source_id": s["source_id"], "ra": s["ra"], "dec": s["dec"], "gmag": float(s["gmag"]),
                    "distance_arcsec": dist})
    return out


def eclipse_by_detector(data: dict[str, Any], t14_phase: float = 0.114, rprs: float = 0.5, min_in: int = 6) -> dict[str, Any]:
    """Depth of a known eclipsing binary's primary eclipse in each detector, from per-exposure
    photometry already measured on real SPHEREx data (a file like docs/transits/eb_tic233532554_rows.json).

    The eclipse is a trapezoid of full width `t14_phase` (in orbital phase) whose flat part is set by
    `rprs` (an assumption: the shape of an eclipse is not known as a planet's is, so only the fitted
    amplitude, a fraction of the light of the system, is quoted). No detector-position terms are
    available in these rows, so only a constant is fitted. Returns the same per-detector dicts as
    `transit_check`, under "detectors".
    """
    period, t0 = float(data["P"]), float(data["T0_BJD"])
    out: dict[str, Any] = {"period_d": period, "t14_h": t14_phase * period * 24, "rprs": rprs, "detectors": {}}
    for det in range(1, 7):
        rr = [r for r in data["rows"] if r["detector"] == det and r["status"] == "ok"]
        if len(rr) < 20:
            out["detectors"][str(det)] = {"status": "too few readings", "n_ok": len(rr)}
            continue
        mjd = np.array([r["mjd"] for r in rr], float)
        ph = np.array([r["phase"] for r in rr], float)
        n = np.round((mjd + 2400000.5 - t0) / period)
        bjd = t0 + n * period + ph * period            # the phase the rows already carry, turned back into a time
        z = np.zeros(len(rr))
        c = {"bjd": bjd, "det": np.full(len(rr), det), "flux": np.array([r["flux_mjy"] for r in rr], float),
             "err": np.array([r["flux_err_stat_mjy"] for r in rr], float), "wl": np.array([r["wavelength_um"] for r in rr], float),
             "X": z, "Y": z, "fx": z, "fy": z, "ovf": np.array([r["overflow_pixels"] for r in rr], int), "ok": np.ones(len(rr), bool)}
        # the shallow secondary eclipse (0.09 of the light, TESS) stays in the template: it is not modelled
        res = analyse_detector(c, period, t0, out["t14_h"], rprs, detrend="none", subpixel=False, min_n=20, min_in=min_in,
                               min_fake=min_in, extras=True, max_dev=2.0, clip=None)
        for key in ("time_slide", "leave_out", "years"):
            res.pop(key, None)
        if res.get("status") == "ok" and res["n_overflow"] > OVERFLOW_LIMIT * res["n_ok"]:
            res["overflow_affected"] = True      # the star is too bright here: shown, but the same rule as for planets applies
        out["detectors"][str(det)] = res
    return out


def usable_detectors(res: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Detectors of a `transit_check` result that were fitted and not left out."""
    return {int(d): r for d, r in res["detectors"].items() if r.get("status") == "ok" and "excluded" not in r}


def colour_test(res: dict[str, Any], min_in_transit: int = 30) -> dict[str, Any]:
    """Is one depth enough for all the detectors? Chi-squared of the per-detector depths about their
    inverse-variance mean, with the empirical errors. A MEASUREMENT of the depths, not a verdict:
    the test has not been validated on a known planet in two or more detectors unless the caller's
    result says so. Needs two detectors with at least `min_in_transit` in-transit readings each."""
    from scipy import stats
    use = {d: r for d, r in usable_detectors(res).items() if r["n_in"] >= min_in_transit}
    if len(use) < 2:
        return {"detectors": sorted(use), "tested": False, "reason": "fewer than two detectors have enough in-transit readings"}
    dep = np.array([r["depth"] for r in use.values()])
    err = np.array([r["empirical_err"] for r in use.values()])
    w = 1 / err ** 2
    mean = float(np.sum(w * dep) / np.sum(w))
    chi2 = float(np.sum(((dep - mean) / err) ** 2))
    dof = len(dep) - 1
    pairs = {}
    ds = sorted(use)
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            pairs[f"{a}-{b}"] = {"difference": use[a]["depth"] - use[b]["depth"],
                                 "error": float(np.hypot(use[a]["empirical_err"], use[b]["empirical_err"]))}
    return {"detectors": ds, "tested": True, "mean_depth": mean, "mean_error": float(1 / np.sqrt(np.sum(w))),
            "chi2": chi2, "dof": dof, "p_value": float(stats.chi2.sf(chi2, dof)), "pairs": pairs,
            "n_sigma_each": {str(d): use[d]["depth"] / use[d]["empirical_err"] for d in ds}}


def detection_limits(res: dict[str, Any], n_sigma: float = 3.0) -> dict[str, Any]:
    """Smallest depth each detector could show (n_sigma times its empirical error) and the smallest
    difference in depth between two detectors it could show (n_sigma times the quadrature sum)."""
    use = usable_detectors(res)
    per = {str(d): {"depth_limit": n_sigma * r["empirical_err"], "n_in": r["n_in"], "empirical_err": r["empirical_err"]}
           for d, r in use.items()}
    pairs = {}
    ds = sorted(use)
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            pairs[f"{a}-{b}"] = n_sigma * float(np.hypot(use[a]["empirical_err"], use[b]["empirical_err"]))
    return {"n_sigma": n_sigma, "per_detector": per, "smallest_depth_difference": pairs}


def combine_detectors(res: dict[str, Any], detectors: Sequence[int] | None = None) -> dict[str, float] | None:
    """Inverse-variance mean depth of the usable detectors, with empirical errors."""
    use = {d: r for d, r in usable_detectors(res).items() if detectors is None or d in detectors}
    if not use:
        return None
    w = np.array([1 / r["empirical_err"] ** 2 for r in use.values()])
    dep = np.array([r["depth"] for r in use.values()])
    return {"detectors": sorted(use), "depth": float(np.sum(w * dep) / np.sum(w)), "error": float(1 / np.sqrt(np.sum(w)))}


def answer_text(res: dict[str, Any]) -> str:
    """Plain-words summary of the measured depths. States numbers, never a verdict."""
    parts = []
    for d, r in sorted(res["detectors"].items()):
        if r.get("status") != "ok":
            parts.append(f"detector {d}: not fitted ({r.get('status')})")
        elif "excluded" in r:
            parts.append(f"detector {d}: left out ({r['excluded']})")
        else:
            parts.append(f"detector {d}: depth {100 * r['depth']:.2f} +/- {100 * r.get('empirical_err', r['formal_err']):.2f} per cent "
                         f"({r['n_in']} in-transit readings)")
    return f"Expected (Rp/Rs)^2 = {100 * res['expected_depth']:.2f} per cent. " + "; ".join(parts) + "."

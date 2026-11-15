"""The colour of a change: not "how much brighter", but "in which colours, and what does that suggest".

SPHEREx measures every object in 102 colours (17 channels in each of six detectors, 0.75 to
5 micrometres). A single-colour survey can say that something faded; this module asks which
colours faded most, and whether that looks like something solid passing in front (every colour
the same), dust in front (short wavelengths dim more), or a warm or hot glow switching on or off.

What this module does, in the order it is used
----------------------------------------------
1. `measure_targets`: the brightness of every object in every exposure of its patch, read from
   the cutouts already on disk, with the search's own measurement (`search._measure_exposure`:
   same circle, flags, sky ring and units; nothing about how the search measures is changed).
2. `change_table`: for two visits, per wavelength channel, the median of each visit's clean
   readings and from them the ratio later / earlier. Only channels measured in BOTH visits
   count. SPHEREx samples a different wavelength in every exposure, so a ratio is never made
   between a blue reading of one visit and a red one of the next.
3. `fit_shapes`: the ratio spectrum described by four simple shapes (grey, dust, warm, hot),
   each fitted with errors, and a verdict that says "cannot tell" when several fit equally well
   and "none of these" when none fits within the errors. A class is a description of the
   colours, never a proven cause.
4. `ice_change`: depth of the water, CO2 and CO ice bands in each visit and the change in depth.
5. `principal_components`: the change spectra of all objects on a common grid, reduced by SVD.

Nothing is simulated. Made-up spectra appear only in the unit tests of the arithmetic.
"""
from __future__ import annotations

import hashlib
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import optimize

from . import photometry, search, spherex

VERSION = 1
COLOUR_DIR = spherex.CACHE / "colour"
CHANNELS = photometry.CHANNELS_PER_DETECTOR
DETECTOR_RANGE_UM = {1: (0.75, 1.09), 2: (1.09, 1.62), 3: (1.62, 2.42), 4: (2.42, 3.82), 5: (3.82, 4.42),
                     6: (4.42, 5.01)}                       # nominal; the archive's own edges are used when known
MIN_READINGS = 1                 # a visit contributes to a channel with at least this many clean readings
SCATTER_FLOOR = 0.03             # relative error floor of a channel median (photometry.SYSTEMATIC)
OK, SATURATED, FLAGGED, NO_DATA, NO_SKY, OFF_IMAGE = search.OK, search.SATURATED, search.FLAGGED, \
    search.NO_DATA, search.NO_SKY, search.OFF_IMAGE
STATUS_NAMES = {OK: "clean", SATURATED: "saturated", FLAGGED: "flagged", NO_DATA: "no_data", NO_SKY: "no_sky",
                OFF_IMAGE: "off_image"}


# --------------------------------------------------------------------------- 1. readings

def _cutout_file(exp: dict, ra: float, dec: float, size_deg: float) -> Path | None:
    """The cutout of one exposure for a patch, wherever the search put it (shared cache or its own)."""
    shared = spherex._cutout_path(exp, ra, dec, size_deg)
    if shared.exists():
        return shared
    own = search.SEARCH_DIR / "cutouts" / shared.relative_to(spherex.CACHE / "cutouts")
    return own if own.exists() else None


def patch_exposures(patch: dict[str, Any]) -> tuple[list[dict], list[int], int]:
    """(exposures, visit number of each, how many of them have no cutout on disk) for a patch.

    The exposure list is the archive's list the search cached for the patch; visits are
    `pipeline.assign_epochs`, as in the search, so "visit 1" means the same thing here.
    """
    from . import pipeline
    exposures = search._exposures(patch["ra"], patch["dec"], True)
    epochs = pipeline.assign_epochs(exposures)
    return exposures, epochs, 0


def _empty_readings(n: int) -> dict[str, Any]:
    return {"detector": np.zeros(0, dtype=int), "epoch": np.zeros(0, dtype=int), "mjd": np.zeros(0),
            "wave": np.zeros(0), "flux": np.zeros(0), "err": np.zeros(0), "status": np.zeros(0, dtype=int),
            "measure": np.zeros(0, dtype=int), "n_targets": n}


def measure_targets(patch: dict[str, Any], targets: list[tuple[float, float]], *,
                    ring_targets: frozenset[int] = frozenset()) -> dict[str, Any]:
    """Brightness of each target in every exposure of the patch that has a cutout on disk.

    Returns arrays indexed [target, exposure]: `flux`, `err` (mJy), `status` (see STATUS_NAMES),
    `wave` (micrometres), plus per exposure `detector`, `epoch` (visit, from 0), `mjd`, `roll`.
    `missing` counts exposures with no cutout on disk (they are left out, never filled).
    A target in `ring_targets` (a saturated star) is, in detectors 5 and 6, measured by the
    ring of unsaturated pixels around it (`measure` 1): a relative brightness, not a flux, that
    is only compared with itself at the same wavelength; this is what the search does.
    """
    exposures, epochs, _ = patch_exposures(patch)
    cutout_deg = round(patch["fov"] * 1.5, 4)
    ra = np.array([t[0] for t in targets])
    dec = np.array([t[1] for t in targets])
    n_t = len(targets)
    cols: dict[str, list] = {k: [] for k in ("detector", "epoch", "mjd", "roll")}
    flux, err, status, wave, kind = [], [], [], [], []
    missing = 0
    by_detector: dict[int, list[int]] = {}
    for exp, ep in zip(exposures, epochs, strict=True):
        path = _cutout_file(exp, patch["ra"], patch["dec"], cutout_deg)
        if path is None:
            missing += 1
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f, e, s, w, _glow, roll = search._measure_exposure(path, ra, dec)
        k = len(cols["detector"])
        by_detector.setdefault(int(exp["detector"]), []).append(k)
        cols["detector"].append(int(exp["detector"]))
        cols["epoch"].append(int(ep))
        cols["mjd"].append(float(exp["mjd"]))
        cols["roll"].append(float(roll))
        flux.append(f)
        err.append(e)
        status.append(s)
        wave.append(w)
        kind.append(np.zeros(n_t, dtype=int))
        cols.setdefault("path", []).append(str(path))
    out: dict[str, Any] = {k: np.array(v) for k, v in cols.items() if k != "path"}
    out["flux"] = np.array(flux).T if flux else np.zeros((n_t, 0))
    out["err"] = np.array(err).T if err else np.zeros((n_t, 0))
    out["status"] = np.array(status).T if status else np.zeros((n_t, 0), dtype=int)
    out["wave"] = np.array(wave).T if wave else np.zeros((n_t, 0))
    out["measure"] = np.array(kind).T if kind else np.zeros((n_t, 0), dtype=int)
    out["missing"] = missing
    paths = cols.get("path", [])
    for i in ring_targets:
        for det in (5, 6):
            idx = by_detector.get(det, [])
            if not idx:
                continue
            points = []
            for k in idx:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    points.append(photometry.measure(Path(paths[k]), float(ra[i]), float(dec[i])))
            choice = photometry._choose_wing_ring(points)
            if choice is None:
                continue
            for k, p in zip(idx, points, strict=True):
                wing = p["wings"][choice] if p["wings"] else None
                out["measure"][i, k] = 1
                if wing is not None and wing["status"] == "ok" and wing["value"] is not None:
                    out["flux"][i, k], out["err"][i, k], out["status"][i, k] = wing["value"], wing["error"], OK
                else:
                    out["flux"][i, k], out["err"][i, k], out["status"][i, k] = np.nan, np.nan, SATURATED
    return out


def channel_of(detector: int, wave: np.ndarray, edges: dict[int, np.ndarray]) -> np.ndarray:
    """Channel number 0..16 of each wavelength in a detector, by the search's equal-ratio edges."""
    e = edges[detector]
    return np.clip(np.searchsorted(e, np.nan_to_num(wave, nan=e[0])) - 1, 0, CHANNELS - 1)


def detector_edges(exposures: list[dict]) -> dict[int, np.ndarray]:
    """Channel edges of each detector from the archive's own wavelength range (as the search does)."""
    out: dict[int, np.ndarray] = {}
    for e in exposures:
        d = int(e["detector"])
        if d not in out:
            out[d] = photometry.channel_edges(e["wave_min"], e["wave_max"])
    return out


# --------------------------------------------------------------------------- 2. the change table

def _robust_sd(x: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) > 1 else float("nan")


def visit_channel_levels(flux: np.ndarray, err: np.ndarray, status: np.ndarray, wave: np.ndarray,
                         detector: np.ndarray, epoch: np.ndarray, edges: dict[int, np.ndarray]) -> dict[str, Any]:
    """One object: per visit and per channel, the median of the clean readings and its error.

    The error of a median is the larger of (a) 1.253 x scatter / sqrt(n) of the readings (the
    spread of the readings in the channel, which also holds the small differences of
    wavelength inside the channel) and (b) the measurement errors combined, 1.253 x
    sqrt(sum err^2) / n. Neither is smaller than SCATTER_FLOOR of the level. With a single
    reading only (b) is available.
    `counts` holds how many readings of each kind fell in each channel: clean, saturated and the others.
    """
    visits = sorted(set(int(v) for v in epoch))
    levels: dict[tuple[int, int, int], dict[str, Any]] = {}
    ok = (status == OK) & np.isfinite(flux) & np.isfinite(err) & np.isfinite(wave)
    counts: dict[tuple[int, int, int], dict[str, int]] = {}
    for d in sorted(set(int(x) for x in detector)):
        in_d = detector == d
        ch_all = channel_of(d, wave, edges)
        for v in visits:
            sel = in_d & (epoch == v)
            for c in range(CHANNELS):
                m = sel & (ch_all == c) & np.isfinite(wave)
                if not m.any():
                    continue
                cnt = counts.setdefault((d, c, v), {"clean": 0, "saturated": 0, "flagged_or_other": 0})
                cnt["saturated"] += int((m & (status == SATURATED)).sum())
                cnt["flagged_or_other"] += int((m & (status != OK) & (status != SATURATED)).sum())
                good = m & ok
                n = int(good.sum())
                cnt["clean"] += n
                if n < MIN_READINGS:
                    continue
                f, e = flux[good], err[good]
                med = float(np.median(f))
                stat = 1.253 * float(np.sqrt(np.sum(e ** 2))) / n
                spread = 1.253 * float(np.std(f, ddof=1)) / math.sqrt(n) if n >= 3 else 0.0
                se = max(stat, spread, SCATTER_FLOOR * abs(med))
                levels[(d, c, v)] = {"level": med, "err": se, "n": n, "wave": float(np.mean(wave[good]))}
    return {"levels": levels, "counts": counts}


MIN_COMMON_CHANNELS = 6          # a pair of visits needs this many shared channels (as the search does)


def channel_table(lv: dict[str, Any], a: int, b: int) -> dict[str, Any]:
    """Ratio later (visit b) / earlier (visit a) in every channel that has clean readings in BOTH visits.

    `channels`: detector, channel, wave_um, early and late level (mJy), their errors, ratio and its
    error, and the number of readings behind each. `saturated_channels`: channels where a visit
    had readings but none usable and at least one of them saturated; they carry no value.
    `excluded`: how many readings of the two visits were left out (saturated, flagged, other).
    """
    levels, counts = lv["levels"], lv["counts"]
    chans, sat = [], []
    keys = sorted({(d, c) for (d, c, _v) in counts})
    excluded = {"saturated": 0, "flagged_or_other": 0, "clean": 0}
    for key in keys:
        d, c = key
        ca, cb = counts.get((d, c, a)), counts.get((d, c, b))
        for cnt in (ca, cb):
            if cnt:
                for k in excluded:
                    excluded[k] += cnt[k]
        la, lb = levels.get((d, c, a)), levels.get((d, c, b))
        if la is None or lb is None:
            if (ca or cb) and any(x and x["saturated"] > 0 and x["clean"] == 0 for x in (ca, cb)):
                sat.append({"detector": d, "channel": c})
            continue
        if la["level"] <= 0 or lb["level"] <= 0:
            continue
        r, er = ratio_with_error(la["level"], la["err"], lb["level"], lb["err"])
        chans.append({"detector": d, "channel": c, "wave_um": 0.5 * (la["wave"] + lb["wave"]),
                      "early": la["level"], "early_err": la["err"], "late": lb["level"], "late_err": lb["err"],
                      "ratio": r, "ratio_err": er, "n_early": la["n"], "n_late": lb["n"]})
    chans.sort(key=lambda x: x["wave_um"])
    return {"channels": chans, "saturated_channels": sat, "readings": excluded}


def ratio_with_error(early: float, e_early: float, late: float, e_late: float) -> tuple[float, float]:
    """Ratio late / early and its error, from the two levels and their errors.

    First-order error propagation: (e_ratio / ratio)^2 = (e_early / early)^2 + (e_late / late)^2.
    Needs both levels above zero (a level at or below zero has no ratio and is not used).
    """
    r = late / early
    return r, abs(r) * math.hypot(e_early / early, e_late / late)


# --------------------------------------------------------------------------- the objects and the controls

CONTROL_MAX_SIGMA = 2.5          # a control star must not change at more than this in any detector
CONTROL_MIN_DETECTORS = 2        # ... and must have been measured in at least this many
CONTROL_MIN_FLUX_MJY = 0.7       # ... and be this bright in at least one detector (it must be measurable)
CONTROL_KEEP_ARCSEC = 25.0       # ... and be this far from every watchlist candidate and from other controls
CONTROLS_PER_PATCH = 40
MATCH_ARCSEC = 4.0


def watchlist_objects(db: Path | None = None) -> list[dict[str, Any]]:
    """Every brightness-changing object of the watchlist's "needs eyes" and "already known" groups.

    The database is opened read-only. Movers and the set-aside artefacts are not included.
    """
    import sqlite3

    from . import watchlist
    path = db or watchlist.db_path()
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM candidates WHERE kind='changer' AND grp IN ('eyes','known') "
                           "ORDER BY id").fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        m = json.loads(r["machine"])
        ev = m.get("evidence") or {}
        out.append({"id": r["id"], "group": r["grp"], "ra": float(r["ra"]), "dec": float(r["dec"]),
                    "patch": m["patch"], "ring": ev.get("measure") == "ring", "best_detector": m.get("best_detector"),
                    "search_ratio": (ev.get("change") or {}).get("ratio"),
                    "sigma_combined": m.get("sigma_combined"), "verdict": m.get("verdict"),
                    "category": (m.get("catalogue_status") or {}).get("category"),
                    "summary": (m.get("catalogue_status") or {}).get("summary")})
    return out


def _arcsec_between(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    de = (ra1 - ra2) * math.cos(math.radians(dec2)) * 3600.0
    dn = (dec1 - dec2) * 3600.0
    return math.hypot(de, dn)


def control_stars(patch: dict[str, Any], avoid: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Ordinary field stars of a patch: bright enough, steady, unflagged, unsaturated, in several detectors.

    Taken from the search's own cached result for the patch (all its detectors). "Steady" is the
    search's own `change_sigma` below CONTROL_MAX_SIGMA in every detector that measured the star.
    They are chosen WITHOUT looking at their colours or their ice bands.
    """
    found: list[dict[str, Any]] = []
    for f in sorted((search.SEARCH_DIR / "results").glob("*.json")):
        d = json.loads(f.read_text())
        if (d.get("version") == search.VERSION and abs(d["ra"] - patch["ra"]) < 1e-4
                and abs(d["dec"] - patch["dec"]) < 1e-4 and abs(d["fov"] - patch["fov"]) < 1e-6):
            found.append(d)
    stars: list[dict[str, Any]] = []     # each: ra, dec, per-detector info
    for d in found:
        for s in d["sources"]:
            if s.get("ring_of") is not None:
                continue
            info = {"detector": d["detector"], "sigma": s.get("change_sigma"), "flux": s.get("typical_flux_mjy"),
                    "flags": s.get("flags") or [], "sat": s.get("n_saturated") or 0, "measure": s.get("measure"),
                    "glow": s.get("glow_share")}
            for st in stars:
                if _arcsec_between(st["ra"], st["dec"], s["ra"], s["dec"]) < MATCH_ARCSEC:
                    st["info"].append(info)
                    break
            else:
                stars.append({"ra": s["ra"], "dec": s["dec"], "info": [info]})
    keep = []
    for st in stars:
        inf = st["info"]
        if len(inf) < CONTROL_MIN_DETECTORS:
            continue
        if any(i["sigma"] is None or i["sigma"] >= CONTROL_MAX_SIGMA or i["flags"] or i["sat"] > 0
               or i["measure"] != "aperture" or (i["glow"] is not None and i["glow"] > 0.05) for i in inf):
            continue
        brightest = max((i["flux"] or 0.0) for i in inf)
        if brightest < CONTROL_MIN_FLUX_MJY:
            continue
        keep.append({"ra": st["ra"], "dec": st["dec"], "flux_mjy": brightest})
    keep.sort(key=lambda s: -s["flux_mjy"])
    chosen: list[dict[str, Any]] = []
    for s in keep:
        if any(_arcsec_between(s["ra"], s["dec"], a, b) < CONTROL_KEEP_ARCSEC for a, b in avoid):
            continue
        if any(_arcsec_between(s["ra"], s["dec"], c["ra"], c["dec"]) < CONTROL_KEEP_ARCSEC for c in chosen):
            continue
        chosen.append(s)
        if len(chosen) >= CONTROLS_PER_PATCH:
            break
    return chosen


# --------------------------------------------------------------------------- the measured dataset

def patch_key(patch: dict[str, Any]) -> str:
    return f"{patch['ra']:.4f}_{patch['dec']:.4f}_{patch['fov']:.2f}"


def build_dataset(objects: list[dict[str, Any]], out_dir: Path | None = None, *, force: bool = False,
                  log: Any = print) -> list[Path]:
    """Measure every object and its patch's control stars in every exposure; one .npz per patch.

    Reads cutouts already on disk only (nothing is downloaded). An exposure whose cutout is
    not on disk is left out and counted (`missing`). A finished patch is not measured again
    unless `force`.
    """
    out_dir = out_dir or COLOUR_DIR / "readings"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_patch: dict[str, list[dict[str, Any]]] = {}
    for o in objects:
        by_patch.setdefault(patch_key(o["patch"]), []).append(o)
    paths = []
    for key, objs in sorted(by_patch.items()):
        target = out_dir / f"{key}.npz"
        paths.append(target)
        if target.exists() and not force:
            continue
        patch = objs[0]["patch"]
        controls = control_stars(patch, [(o["ra"], o["dec"]) for o in objs])
        records = [{"id": o["id"], "kind": "object", "ra": o["ra"], "dec": o["dec"], "ring": o["ring"]} for o in objs]
        records += [{"id": f"control-{key}-{k:02d}", "kind": "control", "ra": c["ra"], "dec": c["dec"], "ring": False}
                    for k, c in enumerate(controls)]
        rings = frozenset(i for i, r in enumerate(records) if r["ring"])
        log(f"{key}: {len(objs)} objects + {len(controls)} controls ...")
        m = measure_targets(patch, [(r["ra"], r["dec"]) for r in records], ring_targets=rings)
        np.savez_compressed(target, records=json.dumps(records), patch=json.dumps(patch),
                            **{k: m[k] for k in ("detector", "epoch", "mjd", "roll", "flux", "err", "status", "wave",
                                                 "measure", "missing")})
    return paths


def load_dataset(paths: list[Path]) -> list[dict[str, Any]]:
    """One record per measured target: its identity and its readings (numpy arrays over exposures)."""
    out = []
    for p in paths:
        z = np.load(p, allow_pickle=False)
        patch = json.loads(str(z["patch"]))
        exposures, epochs, _ = patch_exposures(patch)
        edges = detector_edges(exposures)
        dates: dict[int, list[float]] = {}
        for e, ep in zip(exposures, epochs, strict=True):
            dates.setdefault(ep, []).append(e["mjd"])
        for i, rec in enumerate(json.loads(str(z["records"]))):
            out.append({**rec, "patch": patch, "edges": edges, "missing": int(z["missing"]),
                        "detector": z["detector"], "epoch": z["epoch"], "mjd": z["mjd"], "roll": z["roll"],
                        "flux": z["flux"][i], "err": z["err"][i], "status": z["status"][i], "wave": z["wave"][i],
                        "measure": z["measure"][i]})
    return out


# --------------------------------------------------------------------------- 3. the four shapes

# Dust. Wang and Chen 2024 (ApJ Letters 964, L3; arXiv 2402.17239) measured the extinction law of
# the Milky Way over 0.6 to 5.3 micrometres with 993 JWST NIRSpec spectra and found, between 1.0 and
# 5.3 micrometres, A_lambda proportional to lambda^-alpha with alpha = 1.98 +- 0.15. That is the one
# published law found that covers SPHEREx's whole range in one paper from spectra rather than from
# a few filters. Below 1 micrometre they say a power law is not a good description, so over
# 0.75 to 1.0 micrometres the power law is an approximation (about 1 per cent of the range).
# One free number: tau_1, the optical depth at 1 micrometre (tau = 0.921 x extinction in magnitudes).
DUST_ALPHA = 1.98
DUST_ALPHA_ALT = (1.83, 2.13)    # the paper's +-0.15: the verdicts are re-run with these to see if they move
WARM_T = (250.0, 1500.0)         # warm dust glowing
HOT_T = (2500.0, 10000.0)        # a hot spot, or the star itself
H_OVER_K_UM = 14387.77           # h c / k in micrometre kelvin
MODELS = ("grey", "dust", "warm", "hot")
N_PARAMS = {"none": 0, "grey": 1, "dust": 1, "warm": 2, "hot": 2}
FIT_P = 0.01                     # a shape "fits within the errors" when its chi-square has p above this
TIE_SCORE = 2.0                  # shapes whose chi2 + 2 x parameters is within this of the best are tied
MIN_SIGNIFICANCE = 3.0           # below this many sigma of change the verdict is "no clear change"


def planck_shape(wave_um: np.ndarray, temp: float, ref_um: float) -> np.ndarray:
    """Planck function per unit frequency (F_nu shape) of a body at `temp` kelvin, equal to 1 at `ref_um`."""
    def b(w: np.ndarray | float) -> np.ndarray | float:
        x = H_OVER_K_UM / (np.asarray(w) * temp)
        return np.asarray(w) ** -3 / np.expm1(x)
    return np.asarray(b(wave_um) / b(ref_um))


def dust_ratio(wave_um: np.ndarray, tau_1: float, alpha: float = DUST_ALPHA) -> np.ndarray:
    """Later / earlier brightness if tau_1 more dust (optical depth at 1 micrometre) sits in front.

    A negative tau_1 removes dust.
    """
    return np.exp(-tau_1 * np.asarray(wave_um) ** -alpha)


def _chi2(model: np.ndarray, ratio: np.ndarray, err: np.ndarray) -> float:
    return float(np.sum(((ratio - model) / err) ** 2))


def _interval(chi2_of: Any, best_x: float, best_chi2: float, lo: float, hi: float) -> tuple[float, float]:
    """The range of the parameter where chi-square is within 1 of its minimum (68 per cent), bounded by [lo, hi].

    An end that reaches the bound is returned as the bound; the caller marks it ("at the edge").
    """
    def edge(limit: float) -> float:
        g = lambda x: chi2_of(x) - best_chi2 - 1.0      # noqa: E731
        if g(limit) < 0:
            return limit
        try:
            return float(optimize.brentq(g, best_x, limit, xtol=1e-9 * max(1.0, abs(best_x))))
        except ValueError:
            return limit
    return edge(lo), edge(hi)


def fit_grey(ratio: np.ndarray, err: np.ndarray) -> dict[str, Any]:
    """Same factor at every colour: the weighted mean ratio."""
    w = 1.0 / err ** 2
    a = float(np.sum(w * ratio) / np.sum(w))
    return {"params": {"factor": a}, "errors": {"factor": float(1.0 / math.sqrt(np.sum(w)))},
            "chi2": _chi2(np.full_like(ratio, a), ratio, err)}


def fit_dust(wave: np.ndarray, ratio: np.ndarray, err: np.ndarray, alpha: float = DUST_ALPHA) -> dict[str, Any]:
    """Dust added (tau_1 > 0) or removed (tau_1 < 0) in front: ratio = exp(-tau_1 lambda^-alpha)."""
    def chi2_of(t: float) -> float:
        return _chi2(dust_ratio(wave, t, alpha), ratio, err)
    span = 8.0
    res = optimize.minimize_scalar(chi2_of, bounds=(-span, span), method="bounded", options={"xatol": 1e-9})
    t0, c0 = float(res.x), float(res.fun)
    lo, hi = _interval(chi2_of, t0, c0, -span, span)
    return {"params": {"tau_1": t0}, "errors": {"tau_1": 0.5 * (hi - lo)}, "interval": {"tau_1": [lo, hi]},
            "chi2": c0, "alpha": alpha}


def fit_glow(kind: str, wave: np.ndarray, ratio: np.ndarray, err: np.ndarray, early: np.ndarray) -> dict[str, Any]:
    """Light added (or removed) that has the shape of a warm or hot body.

    later = earlier + A x S(lambda, T), with S the Planck shape equal to 1 at the reference
    wavelength (4.5 micrometres warm, 1.6 hot) and A in mJy there (negative: light removed).
    T is searched on a grid and A, linear, solved exactly at each T; the error of T is the
    range within 1 of the best chi-square.
    """
    lo, hi = WARM_T if kind == "warm" else HOT_T
    ref = 4.5 if kind == "warm" else 1.6
    grid = np.geomspace(lo, hi, 80)
    w = 1.0 / err ** 2

    def solve(t: float) -> tuple[float, float, float]:
        s = planck_shape(wave, t, ref) / early                  # ratio - 1 = A s
        den = float(np.sum(w * s * s))
        a = float(np.sum(w * s * (ratio - 1.0)) / den) if den > 0 else 0.0
        return a, float(1.0 / math.sqrt(den)) if den > 0 else float("inf"), _chi2(1.0 + a * s, ratio, err)

    vals = np.array([solve(float(t))[2] for t in grid])
    k = int(np.argmin(vals))
    res = optimize.minimize_scalar(lambda lt: solve(math.exp(lt))[2], bounds=(math.log(grid[max(k - 1, 0)]),
                                   math.log(grid[min(k + 1, len(grid) - 1)])), method="bounded")
    t_best = float(math.exp(res.x))
    a, ea, c = solve(t_best)
    if c > vals[k]:
        t_best = float(grid[k])
        a, ea, c = solve(t_best)
    t_lo, t_hi = _interval(lambda t: solve(t)[2], t_best, c, lo, hi)
    return {"params": {"amplitude_mjy_at_ref": a, "temperature_k": t_best},
            "errors": {"amplitude_mjy_at_ref": ea, "temperature_k": 0.5 * (t_hi - t_lo)},
            "interval": {"temperature_k": [t_lo, t_hi]},
            "temperature_at_edge": bool(t_lo <= lo * 1.0001 or t_hi >= hi * 0.9999), "ref_um": ref, "chi2": c,
            "sign": "added" if a > 0 else "removed"}


def fit_shapes(ch: list[dict[str, Any]], *, error_scale: float = 1.0, glow: bool = True,
               alpha: float = DUST_ALPHA, min_sigma: float = MIN_SIGNIFICANCE) -> dict[str, Any]:
    """All four shapes fitted to one ratio spectrum, and an honest verdict.

    `ch` is `channel_table(...)["channels"]`. Errors are multiplied by `error_scale` (what the
    steady control stars show is missing from the stated errors). `glow` False leaves out the
    warm and hot shapes (a ring brightness is not a flux, so an added light cannot be put in it).
    Verdict:
      "no_clear_change": the change is below `min_sigma` (sigma = square root of how much the best shape
          improves chi-square over "no change"); the colour of so small a change cannot be told;
      one of grey / dust / warm / hot: the best shape fits within the errors and no other shape
          is as good (by chi-square + 2 x parameters, within TIE_SCORE);
      "cannot_tell": two or more shapes fit within the errors and score within TIE_SCORE;
      "none_of_these": no shape fits within the errors (p below FIT_P).
    """
    n = len(ch)
    wave = np.array([c["wave_um"] for c in ch])
    ratio = np.array([c["ratio"] for c in ch])
    err = np.array([c["ratio_err"] for c in ch]) * error_scale
    early = np.array([c["early"] for c in ch])
    out: dict[str, Any] = {"n_channels": n, "error_scale": error_scale, "fits": {}}
    if n < MIN_COMMON_CHANNELS:
        out.update(verdict="too_few_channels", verdict_text=f"only {n} shared channels")
        return out
    null_chi2 = _chi2(np.ones(n), ratio, err)
    out["no_change"] = {"chi2": null_chi2, "dof": n, "p": float(stats_chi2_sf(null_chi2, n))}
    fits = {"grey": fit_grey(ratio, err), "dust": fit_dust(wave, ratio, err, alpha)}
    if glow:
        fits["warm"] = fit_glow("warm", wave, ratio, err, early)
        fits["hot"] = fit_glow("hot", wave, ratio, err, early)
    for name, f in fits.items():
        k = N_PARAMS[name]
        f["dof"] = n - k
        f["p"] = float(stats_chi2_sf(f["chi2"], n - k))
        f["score"] = f["chi2"] + 2.0 * k
        f["fits"] = bool(f["p"] > FIT_P)
    out["fits"] = fits
    sig = math.sqrt(max(null_chi2 - min(f["chi2"] for f in fits.values()), 0.0))
    out["change_sigma"] = sig
    good = {k: f for k, f in fits.items() if f["fits"]}
    if sig < min_sigma:
        out.update(verdict="no_clear_change",
                   verdict_text=f"no clear change: below {min_sigma:.1f} sigma, too small to tell the colour")
    elif not good:
        out.update(verdict="none_of_these", verdict_text="none of the four simple shapes fits within the errors")
    else:
        best = min(good.values(), key=lambda f: f["score"])
        tied = sorted(k for k, f in good.items() if f["score"] - best["score"] <= TIE_SCORE)
        if len(tied) == 1:
            out.update(verdict=tied[0], verdict_text=f"fits the {tied[0]} shape; no other shape is as good")
        else:
            out.update(verdict="cannot_tell", tied=tied,
                       verdict_text="cannot tell: " + ", ".join(tied) + " fit about equally well")
    return out


# --------------------------------------------------------------------------- every object, every pair

def analyse_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Level and ratio tables of one target for every pair of its patch's visits (no fits yet)."""
    lv = visit_channel_levels(rec["flux"], rec["err"], rec["status"], rec["wave"], rec["detector"], rec["epoch"],
                              rec["edges"])
    visits = sorted(set(int(v) for v in rec["epoch"]))
    pairs = {}
    for i, a in enumerate(visits):
        for b in visits[i + 1:]:
            t = channel_table(lv, a, b)
            t["visits"] = [a, b]
            pairs[f"{a}-{b}"] = t
    dates = {}
    for v in visits:
        m = rec["mjd"][rec["epoch"] == v]
        dates[v] = [float(m.min()), float(m.max())]
    return {"id": rec["id"], "kind": rec["kind"], "ra": rec["ra"], "dec": rec["dec"], "ring": rec["ring"],
            "patch": rec["patch"], "visit_mjd": dates, "pairs": pairs, "lv": lv}


MIN_SHIFT_STARS = 4              # control stars needed in a (patch, pair, detector) to calibrate it
MIN_SHIFT_ROWS = 12              # and this many channel readings


def _line_fit(x: np.ndarray, y: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> tuple[float, float] | None:
    """late = f x early + b by weighted least squares with 3-sigma clipping; None if it cannot be made."""
    keep = np.ones(len(x), dtype=bool)
    f, b = 1.0, 0.0
    for _ in range(6):
        if keep.sum() < MIN_SHIFT_ROWS:
            return None
        w = 1.0 / (sy[keep] ** 2 + (f * sx[keep]) ** 2)
        a = np.vstack([x[keep], np.ones(keep.sum())]).T
        coef, *_ = np.linalg.lstsq(a * np.sqrt(w)[:, None], y[keep] * np.sqrt(w), rcond=None)
        f, b = float(coef[0]), float(coef[1])
        z = (y - f * x - b) / np.sqrt(sy ** 2 + (f * sx) ** 2)
        new = np.abs(z) < 3.0
        if (new == keep).all():
            break
        keep = new
    return f, b


def common_shifts(controls: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, float]]:
    """Per patch, pair and detector: how the steady stars of the field moved between the two visits.

    Calibration of one visit against another is not the same everywhere: a factor f (what the search
    calls its common shift) and, because the sky level subtracted is never perfect, a small constant
    b in mJy. Fitted as late = f x early + b over all channel readings of all control stars of the
    field in that detector (3-sigma clipped), when at least MIN_SHIFT_STARS control stars and
    MIN_SHIFT_ROWS readings exist. It is then removed from the objects of the same field.
    """
    rows: dict[tuple[str, str, int], list[tuple[float, float, float, float, str]]] = {}
    for c in controls:
        pk = patch_key(c["patch"])
        for pair, t in c["pairs"].items():
            for x in t["channels"]:
                rows.setdefault((pk, pair, x["detector"]), []).append(
                    (x["early"], x["late"], x["early_err"], x["late_err"], c["id"]))
    out = {}
    for key, r in rows.items():
        if len({q[4] for q in r}) < MIN_SHIFT_STARS:
            continue
        a = np.array([q[:4] for q in r])
        fit = _line_fit(a[:, 0], a[:, 1], a[:, 2], a[:, 3])
        if fit is not None:
            out[key] = {"factor": fit[0], "offset_mjy": fit[1], "n_stars": len({q[4] for q in r}), "n_rows": len(r)}
    return out


Shifts = dict[tuple[str, str, int], dict[str, float]]


def apply_shift(table: dict[str, Any], pk: str, pair: str, shifts: Shifts) -> dict[str, Any]:
    """Copy of a channel table with each detector's late levels calibrated to the early visit: (late - b) / f."""
    out = []
    used: dict[int, dict[str, float]] = {}
    for x in table["channels"]:
        s = shifts.get((pk, pair, x["detector"]))
        y = dict(x)
        if s:
            late = (x["late"] - s["offset_mjy"]) / s["factor"]
            err = x["late_err"] / s["factor"]
            y.update(late=late, late_err=err)
            if late > 0:
                y["ratio"], y["ratio_err"] = ratio_with_error(x["early"], x["early_err"], late, err)
            else:
                continue                  # calibrated level at or below zero: no ratio, the channel is not used
            used[x["detector"]] = {"factor": s["factor"], "offset_mjy": s["offset_mjy"]}
        out.append(y)
    return {**table, "channels": out, "common_shift": used, "calibrated": bool(used)}


def error_scale_from(controls: list[dict[str, Any]], shifts: Shifts) -> dict[str, Any]:
    """How much the stated ratio errors must be multiplied by, from the steady control stars.

    For every control star and pair of visits with at least MIN_COMMON_CHANNELS shared channels, the
    grey fit's reduced chi-square (a steady star's ratios should all equal one number). The scale is
    the square root of the mean reduced chi-square, never below 1.
    """
    red = []
    for c in controls:
        pk = patch_key(c["patch"])
        for pair, tb in c["pairs"].items():
            ch = apply_shift(tb, pk, pair, shifts)["channels"]
            if len(ch) >= MIN_COMMON_CHANNELS:
                red.append(fit_grey(np.array([x["ratio"] for x in ch]), np.array([x["ratio_err"] for x in ch]))["chi2"]
                           / (len(ch) - 1))
    mean = float(np.mean(red)) if red else 1.0
    return {"scale": max(1.0, math.sqrt(mean)), "n_star_pairs": len(red), "mean_reduced_chi2": mean,
            "median_reduced_chi2": float(np.median(red)) if red else None}


def object_result(a: dict[str, Any], shifts: Shifts, scale: float,
                  alpha: float = DUST_ALPHA, min_sigma: float = MIN_SIGNIFICANCE) -> dict[str, Any]:
    """Every pair of visits of one object: calibrated ratio table, four-shape fits and verdict; plus the headline pair.

    The headline pair is the one with the most significant change (it is chosen by the size of the
    change, so its fit is an answer to "what colour is the biggest change", not an unbiased sample).
    """
    pk = patch_key(a["patch"])
    pairs = {}
    for name, t in a["pairs"].items():
        t2 = apply_shift(t, pk, name, shifts)
        fit = fit_shapes(t2["channels"], error_scale=scale, glow=not a["ring"], alpha=alpha, min_sigma=min_sigma)
        pairs[name] = {"visits": t["visits"], "table": t2, "fit": fit}
    scored = [(p["fit"].get("change_sigma", 0.0), n) for n, p in pairs.items()
              if p["fit"]["n_channels"] >= MIN_COMMON_CHANNELS]
    head = max(scored)[1] if scored else None
    return {"id": a["id"], "ra": a["ra"], "dec": a["dec"], "ring": a["ring"], "visit_mjd": a["visit_mjd"],
            "pairs": pairs, "headline": head}


def stats_chi2_sf(x: float, dof: int) -> float:
    from scipy import stats
    return float(stats.chi2.sf(x, dof)) if dof > 0 else float("nan")


# --------------------------------------------------------------------------- 4. ice bands

# The depth of an ice band is measured, like everything else here, between CHANNELS: the same
# wavelength cell in both visits. (A first version used every reading at its own wavelength inside a
# window. It was dropped: the bands are narrower than the 0.1 micrometre windows, a visit puts only two
# readings in a window, and the two visits sampled different wavelengths, so the "change in depth" was
# produced by which wavelengths happened to be read. Serpens South showed it: visit 1 read 4.23 and 4.27
# micrometres, visit 2 read 4.29 and 4.33.) A channel's level is the median of the clean readings of a
# visit in it, as in the change tables. The band channels are those whose centre lies within `half` of
# the band's centre; the continuum channels are those whose centres lie in the two continuum windows
# (micrometres), chosen clear of the band's wings. Only channels with clean readings in BOTH visits are
# used. Water ice absorbs from about 2.8 to 3.5 micrometres (peak 3.05); CO2 ice peaks at 4.27 and CO ice
# at 4.67. A channel is 0.083 micrometres wide at 3 micrometres and 0.036 at 4.3 to 4.7, wider than the CO
# band (about 0.02), so the depths of the narrow bands are diluted, the same way in both visits.
# The red continuum of CO2 crosses from detector 5 into detector 6 at 4.42; that does not matter for the
# CHANGE in depth, which compares the same detectors.
ICE_BANDS: dict[str, dict[str, Any]] = {
    "water": {"label": "water ice 3.05 um", "centre": 3.05, "half": 0.10, "cont": ((2.42, 2.75), (3.55, 3.82))},
    "co2": {"label": "carbon dioxide ice 4.27 um", "centre": 4.27, "half": 0.02, "cont": ((3.95, 4.19), (4.35, 4.55))},
    "co": {"label": "carbon monoxide ice 4.67 um", "centre": 4.67, "half": 0.02, "cont": ((4.48, 4.63), (4.71, 4.90))},
}
ICE_MIN_BAND = 1                 # channels needed in the band (in both visits)
ICE_MIN_SIDE = 2                 # continuum channels needed on each side used (in both visits)
ICE_MAX_ERR = 0.15               # "bright enough": the change in depth is measured to better than this
ICE_SIGMA = 5.0                  # the change must exceed this many times the REAL error (from the control stars)
ICE_BREAK_SIGMA = 3.0            # ... and each attempt to break it must leave at least this many


def _ice_levels(rec: dict[str, Any], visit: int, band: str,
                drop: set[int] | None = None) -> dict[tuple[int, int], dict[str, float]]:
    """Level, error and nominal centre of each channel in the band's whole span, for one visit.

    `drop`: indices (into the record's readings) to leave out. Error as in `visit_channel_levels`.
    """
    cfg = ICE_BANDS[band]
    lo, hi = cfg["cont"][0][0], cfg["cont"][1][1]
    m = (rec["epoch"] == visit) & (rec["status"] == OK) & np.isfinite(rec["flux"]) & np.isfinite(rec["err"]) \
        & np.isfinite(rec["wave"]) & (rec["wave"] >= lo - 0.1) & (rec["wave"] <= hi + 0.1)
    idx = np.nonzero(m)[0]
    if drop:
        idx = np.array([i for i in idx if i not in drop], dtype=int)
    out: dict[tuple[int, int], dict[str, float]] = {}
    for d in sorted(set(int(x) for x in rec["detector"][idx])):
        sel = idx[rec["detector"][idx] == d]
        ch = channel_of(d, rec["wave"][sel], rec["edges"])
        e = rec["edges"][d]
        for c in sorted(set(int(x) for x in ch)):
            r = sel[ch == c]
            n = len(r)
            f, er = rec["flux"][r], rec["err"][r]
            med = float(np.median(f))
            se = max(1.253 * float(np.sqrt(np.sum(er ** 2))) / n,
                     1.253 * float(np.std(f, ddof=1)) / math.sqrt(n) if n >= 3 else 0.0, SCATTER_FLOOR * abs(med))
            centre = float(math.sqrt(e[c] * e[c + 1]))
            if lo <= centre <= hi:
                out[(d, c)] = {"level": med, "err": se, "centre": centre, "n": n}
    return out


def _depth_from_levels(levels: dict[tuple[int, int], dict[str, float]], band: str, keys: set[tuple[int, int]], *,
                       side: str = "both", order: int = 1) -> tuple[float, float] | None:
    """Depth and error from the channels in `keys` of one visit (the same keys for both visits)."""
    cfg = ICE_BANDS[band]
    bc, blue, red = [], [], []
    for k in keys:
        x = levels[k]
        c = x["centre"]
        if abs(c - cfg["centre"]) <= cfg["half"]:
            bc.append(x)
        elif cfg["cont"][0][0] <= c <= cfg["cont"][0][1]:
            blue.append(x)
        elif cfg["cont"][1][0] <= c <= cfg["cont"][1][1]:
            red.append(x)
    need = {"both": (blue, red), "blue": (blue,), "red": (red,)}[side]
    if len(bc) < ICE_MIN_BAND or any(len(s) < ICE_MIN_SIDE for s in need):
        return None
    cont_ch = {"both": blue + red, "blue": blue, "red": red}[side]
    m = float(np.mean([x["level"] for x in bc]))
    sm = float(np.sqrt(np.sum([x["err"] ** 2 for x in bc]))) / len(bc)
    cw = np.array([x["centre"] for x in cont_ch])
    cf = np.array([x["level"] for x in cont_ch])
    ce = np.maximum(np.array([x["err"] for x in cont_ch]), 1e-12)
    if side == "both":
        deg = min(order, len(cont_ch) - 1, 2)
        x0 = float(np.mean(cw))
        a = np.vander(cw - x0, deg + 1)
        wt = 1.0 / ce ** 2
        try:
            cov = np.linalg.inv(a.T @ (a * wt[:, None]))
        except np.linalg.LinAlgError:
            return None
        coef = cov @ (a.T @ (wt * cf))
        row = np.vander(np.array([x["centre"] for x in bc]) - x0, deg + 1).mean(axis=0)
        cont, scont = float(row @ coef), float(math.sqrt(max(float(row @ cov @ row), 0.0)))
    else:
        cont, scont = float(np.mean(cf)), float(np.sqrt(np.sum(ce ** 2))) / len(cont_ch)
    if not (cont > 0 and m > 0):
        return None
    return 1.0 - m / cont, (m / cont) * math.hypot(sm / m, scont / cont)


def ice_change(rec: dict[str, Any], band: str, a: int, b: int, *, side: str = "both", order: int = 1,
               drop_a: set[int] | None = None, drop_b: set[int] | None = None) -> dict[str, Any] | None:
    """Depth of one ice band in visits a and b (same channels in both), and the change b minus a with its error."""
    la, lb = _ice_levels(rec, a, band, drop_a), _ice_levels(rec, b, band, drop_b)
    keys = set(la) & set(lb)
    da = _depth_from_levels(la, band, keys, side=side, order=order)
    db = _depth_from_levels(lb, band, keys, side=side, order=order)
    if da is None or db is None:
        return None
    cfg = ICE_BANDS[band]
    n_band = sum(abs(la[k]["centre"] - cfg["centre"]) <= cfg["half"] for k in keys)
    return {"depth_early": da[0], "err_early": da[1], "depth_late": db[0], "err_late": db[1],
            "change": db[0] - da[0], "err": math.hypot(da[1], db[1]), "n_channels": len(keys),
            "n_band_channels": n_band}


def ice_scatter_from_controls(controls: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """What the control stars say the real error of a change in depth is, band by band.

    For every control star, pair of visits and band that can be measured to better than ICE_MAX_ERR:
    the change in depth and its stated error. `pull_sd`: robust scatter of change / stated error
    (never below 1); `sd`: the robust scatter of the changes themselves (the "real error" in absolute
    terms for stars of that quality). The REAL error of an object's change is `pull_sd` x its stated error.
    """
    out = {}
    for band in ICE_BANDS:
        ch, er = [], []
        stars: set[str] = set()
        for c in controls:
            visits = sorted(set(int(v) for v in c["epoch"]))
            for i, a in enumerate(visits):
                for b in visits[i + 1:]:
                    r = ice_change(c, band, a, b)
                    if r is not None and r["err"] < ICE_MAX_ERR:
                        ch.append(r["change"])
                        er.append(r["err"])
                        stars.add(c["id"])
        ch_a, er_a = np.array(ch), np.array(er)
        ok = len(ch) > 5
        out[band] = {"n": len(ch), "n_stars": len(stars),
                     "pull_sd": max(1.0, _robust_sd(ch_a / er_a)) if ok else None,
                     "sd": _robust_sd(ch_a) if ok else None,
                     "median_change": float(np.median(ch_a)) if ch else None,
                     "median_stated_err": float(np.median(er_a)) if ch else None,
                     "frac_over_5": float(np.mean(np.abs(ch_a / er_a) > 5)) if ch else None}
    return out


def break_ice_change(rec: dict[str, Any], band: str, a: int, b: int, pull_sd: float) -> dict[str, Any]:
    """Try to kill an ice-depth change. Each entry is the change in units of the real error (None if it cannot be made).

    - `without_two_best`: leave out the two readings (of both visits, anywhere in the windows) whose
      removal shrinks the change most, one after the other (the channel medians are made again).
    - `blue_only`, `red_only`: continuum from one side only (the change must not depend on the other side).
    - `curved_continuum`: a parabola through both continuum sides instead of a straight line.
    - `continuum_ratio`: late / early brightness of the continuum near the band (median of the continuum
      channels), to show how much it changed; a change by a large factor makes a curved continuum likely.
    """
    base = ice_change(rec, band, a, b)
    out: dict[str, Any] = {"base_sigma": None}
    if base is None:
        return out
    sign = 1.0 if base["change"] >= 0 else -1.0
    out["base_sigma"] = base["change"] / (base["err"] * pull_sd)

    def sigma_of(**kw: Any) -> float | None:
        r = ice_change(rec, band, a, b, **kw)
        return None if r is None else r["change"] / (r["err"] * pull_sd)

    out["blue_only"], out["red_only"] = sigma_of(side="blue"), sigma_of(side="red")
    out["curved_continuum"] = sigma_of(order=2)
    cfg = ICE_BANDS[band]
    lo, hi = cfg["cont"][0][0] - 0.1, cfg["cont"][1][1] + 0.1
    cand = {v: [i for i in np.nonzero((rec["epoch"] == v) & (rec["status"] == OK) & np.isfinite(rec["wave"]))[0]
                if lo <= rec["wave"][i] <= hi] for v in (a, b)}
    dropped: dict[int, set[int]] = {a: set(), b: set()}
    for _ in range(2):
        best, best_val = None, None
        for v in (a, b):
            for i in cand[v]:
                trial = {x: set(s) for x, s in dropped.items()}
                trial[v].add(int(i))
                r = ice_change(rec, band, a, b, drop_a=trial[a], drop_b=trial[b])
                if r is None:
                    continue
                val = sign * r["change"]
                if best_val is None or val < best_val:
                    best, best_val = (v, int(i)), val
        if best is None:
            break
        dropped[best[0]].add(best[1])
    r = ice_change(rec, band, a, b, drop_a=dropped[a], drop_b=dropped[b])
    out["without_two_best"] = None if r is None else r["change"] / (r["err"] * pull_sd)
    lev = []
    for v in (a, b):
        lv = _ice_levels(rec, v, band)
        sel = [x["level"] for x in lv.values() if abs(x["centre"] - cfg["centre"]) > cfg["half"]
               and (cfg["cont"][0][0] <= x["centre"] <= cfg["cont"][0][1]
                    or cfg["cont"][1][0] <= x["centre"] <= cfg["cont"][1][1])]
        lev.append(float(np.median(sel)) if len(sel) >= 2 else float("nan"))
    out["continuum_ratio"] = lev[1] / lev[0] if lev[0] > 0 else None
    ok = [out[k] for k in ("without_two_best", "blue_only", "red_only", "curved_continuum")]
    out["survives"] = bool(all(x is not None and sign * x >= ICE_BREAK_SIGMA for x in ok))
    return out


# --------------------------------------------------------------------------- 5. let the data sort itself

PCA_MIN_OBJECTS = 40             # the share of channels required is lowered until this many objects are complete
TILT_SPAN = math.log(5.0 / 1.0)  # a "colour difference" is the ratio of the change at 5 micrometres to that at 1


def colour_tilt(ch: list[dict[str, Any]], error_scale: float = 1.0) -> tuple[float, float] | None:
    """How differently an object changed at 5 and at 1 micrometre: ratio of the two changes (1.0 = the same colour).

    A weighted straight line through ln(ratio) against ln(wavelength) over the shared channels; the
    answer is exp(slope x ln 5) and its error, from the line's own error. None with fewer than 6 channels.
    """
    if len(ch) < MIN_COMMON_CHANNELS:
        return None
    x = np.log([c["wave_um"] for c in ch])
    y = np.log([c["ratio"] for c in ch])
    s = np.array([c["ratio_err"] / c["ratio"] for c in ch]) * error_scale
    w = 1.0 / s ** 2
    sw, sx, sy = w.sum(), (w * x).sum(), (w * y).sum()
    sxx, sxy = (w * x * x).sum(), (w * x * y).sum()
    det = sw * sxx - sx ** 2
    if det <= 0:
        return None
    slope = (sw * sxy - sx * sy) / det
    err = math.sqrt(sw / det)
    return float(math.exp(slope * TILT_SPAN)), float(math.exp(slope * TILT_SPAN) * err * TILT_SPAN)


PCA_BANDS = 12                   # the common grid: 12 equal-ratio wavelength bands from 0.75 to 5.01 micrometres
PCA_BAND_SHARE = (0.8, 0.7, 0.6, 0.5)   # a band is kept if this share of the objects has data in it (first that works)


def band_grid() -> np.ndarray:
    return np.geomspace(0.75, 5.01, PCA_BANDS + 1)


def band_average(spec: list[tuple[float, float, float]]) -> dict[int, tuple[float, float, float]]:
    """One object's channels averaged (error-weighted) in the 12 common bands: band -> (ln ratio, error, wavelength)."""
    edges = band_grid()
    w = np.array([s[0] for s in spec])
    y = np.array([s[1] for s in spec])
    e = np.array([s[2] for s in spec])
    k = np.clip(np.searchsorted(edges, w) - 1, 0, PCA_BANDS - 1)
    row = {}
    for b in np.unique(k):
        m = k == b
        wt = 1.0 / e[m] ** 2
        row[int(b)] = (float(np.sum(wt * y[m]) / np.sum(wt)), float(1.0 / math.sqrt(np.sum(wt))), float(np.mean(w[m])))
    return row


def principal_components(spectra: dict[str, list[tuple[float, float, float]]],
                         noise_sigma: float | None = None) -> dict[str, Any]:
    """Principal components of the change spectra on a common grid of 12 wavelength bands.

    `spectra`: object id -> list of (wavelength, ln ratio, error of ln ratio) per channel, one pair of
    visits per object (the headline pair). Each object's channels are averaged (weighted by their
    errors) within each of the 12 bands: SPHEREx's channels differ from object to object (a channel is
    used only if both visits have clean readings in it), so only a band-wise comparison is possible.
    A band with no measurement for an object is missing for that object; it is never filled in. Bands
    that most objects (see PCA_BAND_SHARE) have are kept, and only objects with ALL kept bands enter.
    The matrix is not centred (ln ratio = 0 is "no change", the natural origin); a centred version is
    reported beside it. The noise level of the components: the largest singular value that pure noise of
    scatter `noise_sigma` gives for a matrix of this shape is about sigma (sqrt(n) + sqrt(p)); `noise_sigma`
    is the scatter of steady stars' band values (so it includes the calibration scatter), or, if not
    given, the typical stated error.
    """
    edges = band_grid()
    ids = sorted(spectra)
    table = {i: band_average(spectra[i]) for i in ids}
    share = np.array([sum(b in table[i] for i in ids) / len(ids) for b in range(PCA_BANDS)])
    chosen = None
    for thr in PCA_BAND_SHARE:
        keep = [b for b in range(PCA_BANDS) if share[b] >= thr]
        complete = [i for i in ids if all(b in table[i] for b in keep)]
        if len(keep) >= 4 and len(complete) >= PCA_MIN_OBJECTS:
            chosen = (thr, keep, complete)
            break
    if chosen is None:
        return {"ok": False, "reason": "too few objects have enough bands", "band_share": share.tolist()}
    thr, keep, complete = chosen
    x = np.array([[table[i][b][0] for b in keep] for i in complete])
    stated = float(np.median([table[i][b][1] for i in complete for b in keep]))
    sigma = noise_sigma if noise_sigma is not None else stated
    n, p = x.shape
    centres = [float(np.sqrt(edges[b] * edges[b + 1])) for b in keep]
    out: dict[str, Any] = {"ok": True, "share_threshold": thr, "n_objects": n, "n_bands": p,
                           "bands_um": [[float(edges[b]), float(edges[b + 1])] for b in keep],
                           "band_centres_um": centres,
                           "band_share": share.tolist(), "ids": complete, "typical_stated_error_ln_ratio": stated,
                           "noise_sigma_ln_ratio": sigma, "noise_singular_value": sigma * (math.sqrt(n) + math.sqrt(p))}
    for name, mat in (("uncentred", x), ("centred", x - x.mean(axis=0))):
        u, s, vt = np.linalg.svd(mat, full_matrices=False)
        out[name] = {"singular_values": [float(v) for v in s[:10]],
                     "variance_share": [float(v) for v in (s ** 2 / np.sum(s ** 2))[:10]],
                     "n_above_noise": int(np.sum(s > out["noise_singular_value"])),
                     "components": [[float(v) for v in vt[k]] for k in range(min(5, len(s)))],
                     "scores": [[float(v) for v in (u[:, k] * s[k])] for k in range(min(5, len(s)))]}
    return out


def pca_outliers(scores: list[list[float]], ids: list[str], k: int, cut: float = 3.5) -> list[dict[str, Any]]:
    """Objects far from the rest in the space of the first k components (robust z of the distance above `cut`)."""
    pts = np.array(scores[:k]).T
    centre = np.median(pts, axis=0)
    d = np.linalg.norm(pts - centre, axis=1)
    mad = 1.4826 * float(np.median(np.abs(d - np.median(d))))
    z = (d - np.median(d)) / mad if mad > 0 else np.zeros_like(d)
    return [{"id": ids[i], "distance": float(d[i]), "robust_z": float(z[i])} for i in np.argsort(-z) if z[i] > cut]


def points_to_record(points: list[dict[str, Any]], ranges: dict[str, list[float]], rid: str) -> dict[str, Any]:
    """A target record (as `load_dataset` makes) from the viewer's cached photometry points."""
    code = {"ok": OK, "saturated": SATURATED, "flagged": FLAGGED, "no_data": NO_DATA, "no_sky": NO_SKY,
            "off_image": OFF_IMAGE}
    keep = [p for p in points if p["wavelength_um"] is not None]
    edges = {int(d): photometry.channel_edges(lo, hi) for d, (lo, hi) in ranges.items()}
    return {"id": rid, "kind": "object", "ra": 0.0, "dec": 0.0, "ring": False, "edges": edges,
            "detector": np.array([p["detector"] for p in keep]), "epoch": np.array([p["epoch"] for p in keep]),
            "mjd": np.array([p["mjd"] for p in keep]),
            "flux": np.array([np.nan if p["flux_mjy"] is None else p["flux_mjy"] for p in keep], dtype=float),
            "err": np.array([np.nan if p["flux_err_mjy"] is None else p["flux_err_mjy"] for p in keep], dtype=float),
            "status": np.array([code.get(p["status"], NO_DATA) for p in keep]),
            "wave": np.array([p["wavelength_um"] for p in keep], dtype=float)}


# --------------------------------------------------------------------------- everything together

CONTROL_SIGMA_PERCENTILE = 90.0  # "a clear change" must exceed this percentile of the control stars' own change_sigma


def _is_validation(rec_id: str) -> bool:
    """Control stars are split in two by a hash of their id: one half sets the threshold, the other tests it."""
    return int(hashlib.sha1(rec_id.encode()).hexdigest(), 16) % 2 == 1


def analyse_all(recs: list[dict[str, Any]], *, with_ice: bool = True, log: Any = print) -> dict[str, Any]:
    """Run steps 1 to 4 on a list of measured targets (objects and controls, from `load_dataset`).

    Returns a dict with: `shifts`, `error_scale`, `threshold` (the change significance a colour is
    only told above, from half of the control stars) and `validation` (what the other half of the
    controls give), `objects` (object_result of each object), `controls` (the same for control
    stars), `ice`, `pca`, `alpha_check` (how many verdicts change if the dust law's index moves by
    its error), and `smallest_colour`.
    """
    an = [analyse_record(r) for r in recs]
    by_id = {r["id"]: r for r in recs}
    controls = [a for a in an if a["kind"] == "control"]
    objects = [a for a in an if a["kind"] == "object"]
    shifts = common_shifts(controls)
    scale = error_scale_from(controls, shifts)
    log(f"calibrated {len(shifts)} (field, pair, detector) groups; error scale {scale['scale']:.3f}")

    first = {c["id"]: object_result(c, shifts, scale["scale"], min_sigma=0.0) for c in controls}
    sig = {i: (r["pairs"][r["headline"]]["fit"].get("change_sigma", 0.0) if r["headline"] else 0.0)
           for i, r in first.items()}
    train = [v for i, v in sig.items() if not _is_validation(i)]
    test_ids = [i for i in sig if _is_validation(i)]
    threshold = float(np.percentile(train, CONTROL_SIGMA_PERCENTILE))
    log(f"clear-change threshold {threshold:.2f} sigma (from {len(train)} control stars)")

    def run(a: dict[str, Any], alpha: float = DUST_ALPHA) -> dict[str, Any]:
        r = object_result(a, shifts, scale["scale"], alpha=alpha, min_sigma=threshold)
        h = r["headline"]
        if h:
            t = colour_tilt(r["pairs"][h]["table"]["channels"], scale["scale"])
            r["tilt"] = {"ratio_5_to_1": t[0], "err": t[1]} if t else None
        return r

    res_obj = {a["id"]: run(a) for a in objects}
    res_ctl = {a["id"]: run(a) for a in controls}
    n_test_clear = sum(1 for i in test_ids if res_ctl[i]["headline"]
                       and res_ctl[i]["pairs"][res_ctl[i]["headline"]]["fit"]["verdict"] != "no_clear_change")
    validation = {"n": len(test_ids), "n_called_a_change": n_test_clear,
                  "verdicts": _count(res_ctl[i] for i in test_ids)}

    alt = {}
    for alpha in DUST_ALPHA_ALT:
        changed = 0
        for a in objects:
            r2 = run(a, alpha)
            v1 = _verdict(res_obj[a["id"]])
            if _verdict(r2) != v1:
                changed += 1
        alt[str(alpha)] = changed
    out: dict[str, Any] = {"shifts": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in shifts.items()}, "error_scale": scale,
                           "threshold": threshold, "validation": validation, "objects": res_obj,
                           "controls": res_ctl,
                           "alpha_check": {"alphas": list(DUST_ALPHA_ALT), "n_verdicts_changed": alt}}

    # the smallest colour difference the method can see: steady stars' tilt scatter
    tilts, bright_tilts = [], []
    for c in controls:
        for pair, t in c["pairs"].items():
            ch = apply_shift(t, patch_key(c["patch"]), pair, shifts)["channels"]
            tt = colour_tilt(ch, scale["scale"])
            if tt is not None and math.log(tt[0]) is not None:
                tilts.append(math.log(tt[0]))
                if np.median([x["early"] for x in ch]) > 3.0:
                    bright_tilts.append(math.log(tt[0]))
    out["smallest_colour"] = {
        "n_star_pairs": len(tilts), "robust_sd_ln_tilt": _robust_sd(np.array(tilts)) if tilts else None,
        "n_bright_star_pairs": len(bright_tilts),
        "robust_sd_ln_tilt_bright": _robust_sd(np.array(bright_tilts)) if len(bright_tilts) > 5 else None,
        "p97_5_abs_ln_tilt": float(np.percentile(np.abs(tilts), 97.5)) if tilts else None}

    # spectra for the principal components: one pair per object (the headline pair)
    spectra = {}
    for i, r in res_obj.items():
        h = r["headline"]
        if not h:
            continue
        ch = r["pairs"][h]["table"]["channels"]
        spectra[i] = [(c["wave_um"], math.log(c["ratio"]), c["ratio_err"] / c["ratio"] * scale["scale"]) for c in ch]
    ctl_values = []
    for c in controls:
        for pair, t in c["pairs"].items():
            ch = apply_shift(t, patch_key(c["patch"]), pair, shifts)["channels"]
            if len(ch) >= MIN_COMMON_CHANNELS:
                ctl_values += [v[0] for v in band_average([(x["wave_um"], math.log(x["ratio"]),
                                                            x["ratio_err"] / x["ratio"] * scale["scale"])
                                                           for x in ch]).values()]
    noise = _robust_sd(np.array(ctl_values)) if ctl_values else None
    out["pca"] = principal_components(spectra, noise) if len(spectra) >= PCA_MIN_OBJECTS else {"ok": False}
    if out["pca"]["ok"]:
        k = max(2, out["pca"]["uncentred"]["n_above_noise"])
        out["pca"]["outliers"] = pca_outliers(out["pca"]["uncentred"]["scores"], out["pca"]["ids"], min(k, 5))
        out["pca"]["k_used_for_outliers"] = min(k, 5)

    if with_ice:
        ctl_recs = [by_id[c["id"]] for c in controls]
        obj_recs = [by_id[a["id"]] for a in objects if not a["ring"]]
        sc = ice_scatter_from_controls(ctl_recs)
        out["ice"] = {"controls": sc, "objects": _ice_objects(obj_recs, sc), "bands": {
            k: {"label": v["label"], "centre_um": v["centre"], "half_width_um": v["half"],
                "continuum_um": [list(w) for w in v["cont"]]}
            for k, v in ICE_BANDS.items()}}
        # the same list for the control stars, to count how often steady stars would be "found"
        ch = _ice_hits(ctl_recs, sc)
        ctl_by_id = {r["id"]: r for r in ctl_recs}
        for h in ch:
            if abs(h["sigma_real"]) >= ICE_SIGMA:
                h["tests"] = break_ice_change(ctl_by_id[h["id"]], h["band"], h["pair"][0], h["pair"][1],
                                              sc[h["band"]]["pull_sd"])
        out["ice"]["control_hits"] = ch
        out["ice"]["control_depth"] = {
            band: {"n": len(v), "median": float(np.median(v)), "p16": float(np.percentile(v, 16)),
                   "p84": float(np.percentile(v, 84))}
            for band in ICE_BANDS if (v := [x["depth_early"] for x in ch if x["band"] == band]
                                      + [x["depth_late"] for x in ch if x["band"] == band])}
    return out


def _verdict(r: dict[str, Any]) -> str:
    h = r["headline"]
    return r["pairs"][h]["fit"]["verdict"] if h else "no_pair"


def _count(results: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        v = _verdict(r)
        out[v] = out.get(v, 0) + 1
    return out


def _ice_hits(recs: list[dict[str, Any]], sc: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Every measurable (target, pair, band) with its change in units of the real error."""
    hits = []
    for r in recs:
        visits = sorted(set(int(v) for v in r["epoch"]))
        for band in ICE_BANDS:
            s = sc[band]["pull_sd"]
            if s is None:
                continue
            for i, a in enumerate(visits):
                for b in visits[i + 1:]:
                    c = ice_change(r, band, a, b)
                    if c is None or c["err"] >= ICE_MAX_ERR:
                        continue
                    hits.append({"id": r["id"], "band": band, "pair": [a, b], **{k: c[k] for k in (
                        "depth_early", "depth_late", "change", "err", "n_channels", "n_band_channels")},
                        "sigma_real": c["change"] / (c["err"] * s)})
    return hits


def _ice_objects(recs: list[dict[str, Any]], sc: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """All measurable ice changes of the objects, and for each one above ICE_SIGMA the attempts to break it."""
    hits = _ice_hits(recs, sc)
    by_id = {r["id"]: r for r in recs}
    for h in hits:
        if abs(h["sigma_real"]) >= ICE_SIGMA:
            h["tests"] = break_ice_change(by_id[h["id"]], h["band"], h["pair"][0], h["pair"][1],
                                          sc[h["band"]]["pull_sd"])
    return {"n_measurable": len(hits), "n_objects_measurable": len({h["id"] for h in hits}), "hits": hits,
            "n_over_5": sum(abs(h["sigma_real"]) >= ICE_SIGMA for h in hits),
            "n_survive": sum(bool(h.get("tests", {}).get("survives")) for h in hits)}

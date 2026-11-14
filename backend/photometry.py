"""Brightness of one object in every SPHEREx exposure: light curve and spectrum.

Each exposure sees the object through a different part of the linear variable filter,
so every measurement has its own wavelength. Measurements are made on the native
cutouts (no resampling), one per exposure:

- Aperture flux: the zodi-subtracted image summed in a circle on the object's expected
  position, minus the local sky from a ring further out, times the pixel solid angle.
- A measurement is only a number if every pixel in the circle passes the photometry
  flag list of the Explanatory Supplement (v2.1, Sect. 3.3 "Flag usage"). Otherwise it
  is reported with a status ("saturated", "flagged", "no_data", "off_image") and no flux.
- Saturation, from Table 16 of the Supplement: OVERFLOW alone means the pixel reached
  half of full well and its brightness comes from the reads before that, which is a
  valid value and is kept (the mission's own photometry keeps it). OVERFLOW together
  with SUR_ERROR means it overflowed in the first five seconds, BLOOM means charge
  spilled in from a saturated neighbour and NONLINEAR means no reliable correction:
  those are what "saturated" means here.
- Wing brightness, for when the core is saturated: the same sky-subtracted sum in a
  ring outside the saturated pixels. It is NOT a flux: it is the few per cent of the
  star's light that falls in that ring (plus any fainter star there), and is only
  comparable with other wing values of the same star, ring and wavelength bin. Three
  rings are tried; one is chosen per detector for the whole star (the innermost that
  works in at least half of the exposures), so every point in a bin uses the same ring.
  A ring is used only if it holds no saturated pixel and at most a tenth of it is
  otherwise flagged; flagged pixels are left out and the mean of the rest stands for
  the ring.
- Wing values are trusted in detectors 5 and 6 only. Tested on two heavily saturated
  stars by comparing values in the same wavelength bin: Barnard's Star, which does
  not vary (all pairs), and R Draconis (pairs taken within 4 days). Typical
  disagreement: D5 2-5 per cent, D6 1-6 per cent, D4 3-20, D1 8-22, D2 14-88, D3 19-69.
  In detectors 1 to 4 the value is still returned, marked wing_trusted false.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area

from . import astrometry, pipeline, spherex

# Part of the cache key: raise it when the measurement changes (7: stars_in_circle;
# 8: a Gaia star is followed only within 3 arcsec of the request, and `measured`).
VERSION = 9
PHOT_DIR = spherex.CACHE / "photometry"
CUTOUT_DEG = 0.15                # same cutouts as /api/frames at its default field of view

APERTURE_PX = 2.5                # radius of the measuring circle, native pixels (6.15 arcsec each)
# Rings tried for the wing brightness of a saturated star, innermost first. R Draconis
# is saturated or bloomed out to 5-8 pixels, Barnard's Star and RW Aurigae to 2-3.
WING_RINGS_PX = ((3.5, 6.5), (6.5, 9.5), (9.5, 12.5))
WING_MAX_FLAGGED = 0.10          # largest flagged share of a ring that is still used
# Detectors in which wing values proved repeatable (see "wing" in the method text and
# CLAUDE.md). In the others they are still measured but not offered as a brightness.
WING_TRUSTED_DETECTORS = (5, 6)
SKY_PX = (14.0, 20.0)            # ring the local sky level is taken from
CHANNELS_PER_DETECTOR = 17       # SPHEREx's own count: 6 detectors x 17 = 102 channels
SYSTEMATIC = 0.03                # added in quadrature to every error, as the Supplement's Note 1 does

# "Flags for masking pixels for photometry calculations", Explanatory Supplement v2.1.
# Stricter than the display mask in pipeline.py.
PHOTOMETRY_BAD = pipeline._mask("SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR",
                                "PERSIST", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO")
# "Flags for background estimation masking", same section.
SKY_BAD = PHOTOMETRY_BAD | pipeline._mask("OVERFLOW", "OUTLIER", "SOURCE", "TRANSIENT")
OVERFLOW = pipeline._mask("OVERFLOW")
SUR_ERROR = pipeline._mask("SUR_ERROR")
SPILL = pipeline._mask("BLOOM", "NONLINEAR")
_NAMES = {bit: name for name, bit in pipeline.BIT.items()}


def saturated_pixels(flags: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Pixels whose value is lost to saturation (see the module text for the reasoning)."""
    overflow = (flags & OVERFLOW) != 0
    return (overflow & ((flags & SUR_ERROR) != 0)) | ((flags & SPILL) != 0) | (overflow & ~np.isfinite(data))


def _coverage(xx: np.ndarray, yy: np.ndarray, x: float, y: float, r_in: float, r_out: float,
              sub: int = 5) -> np.ndarray:
    """Fraction of each pixel lying between r_in and r_out of (x, y), by sub-sampling."""
    offsets = (np.arange(sub) + 0.5) / sub - 0.5
    total = np.zeros(xx.shape)
    for dy in offsets:
        for dx in offsets:
            r = np.hypot(xx + dx - x, yy + dy - y)
            total += (r >= r_in) & (r < r_out)
    return total / sub ** 2


def _flag_names(bits: int) -> list[str]:
    return [_NAMES.get(b, f"bit{b}") for b in range(31) if bits >> b & 1]


def _sum_region(weight: np.ndarray, data: np.ndarray, variance: np.ndarray, flags: np.ndarray,
                sky: float, sky_var: float, to_mjy: float, max_flagged: float = 0.0) -> dict:
    """Sky-subtracted sum over a weighted region, or the reason there is none.

    With max_flagged 0 every pixel must be clean. Above 0, up to that share of the
    region may be flagged or empty: those pixels are left out and the mean of the
    clean ones is scaled to the whole region. A saturated pixel always rules it out.
    """
    used = weight > 0
    w, d, v, f = weight[used], data[used], variance[used], flags[used]
    bits = 0
    for value in np.unique(f).tolist():
        bits |= int(value)
    empty = ~np.isfinite(d) | ~np.isfinite(v)
    bad = ((f & PHOTOMETRY_BAD) != 0) | empty
    flagged_share = float(w[bad].sum() / w.sum())
    out: dict = {"status": "ok", "value": None, "error": None, "error_stat": None,
                 "flags": _flag_names(bits & ~pipeline._mask("SOURCE")),
                 "overflow_pixels": int(((f & OVERFLOW) != 0).sum()), "clean_fraction": 1.0 - flagged_share}
    if saturated_pixels(f, d).any():
        out["status"] = "saturated"
    elif flagged_share > max_flagged:
        out["status"] = "flagged" if ((f & PHOTOMETRY_BAD) != 0).any() else "no_data"
    else:
        good = ~bad
        scale = float(w.sum() / w[good].sum())
        total = float(np.sum(w[good] * (d[good] - sky))) * scale
        var = float(np.sum(w[good] ** 2 * v[good])) * scale ** 2 + float(w.sum()) ** 2 * sky_var
        out["value"] = total * to_mjy
        out["error_stat"] = float(np.sqrt(var)) * to_mjy
        out["error"] = float(np.hypot(out["error_stat"], SYSTEMATIC * out["value"]))
    return out


def measure(path: Path, ra: float, dec: float) -> dict:
    """Measure the object at (ra, dec) in one cached cutout."""
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = hdul["FLAGS"].data
        variance = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data
        band = hdul["BANDWIDTH"].data
    wcs = WCS(header)
    mjd = float(header["MJD-AVG"])
    point: dict = {"mjd": mjd, "date": Time(mjd, format="mjd").isot[:19], "status": "off_image",
                   "wavelength_um": None, "bandwidth_um": None, "flux_mjy": None, "flux_err_mjy": None,
                   "flux_err_stat_mjy": None, "flags": [], "overflow_pixels": 0, "wings": []}
    px, py = wcs.all_world2pix(ra, dec, 0)
    x, y = float(px), float(py)
    ny, nx = image.shape
    xi, yi = int(round(x)), int(round(y))
    edge = SKY_PX[1] + 1
    if not (edge <= x < nx - edge and edge <= y < ny - edge):
        return point           # near the edge of the detector: no room for the sky ring
    wavelength, bandwidth = float(wave[yi, xi]), float(band[yi, xi])
    if not (np.isfinite(wavelength) and np.isfinite(bandwidth)):
        point["status"] = "no_data"   # no wavelength for this pixel: the reading cannot be placed
        return point
    point["wavelength_um"], point["bandwidth_um"] = wavelength, bandwidth

    data = image - zodi
    data[pipeline.impossible_pixels(image, variance)] = np.nan   # unflagged negative glitches: treated as empty
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - x, yy - y)
    ring = (r >= SKY_PX[0]) & (r < SKY_PX[1]) & np.isfinite(data)
    in_sky = ring & ((flags & SKY_BAD) == 0)
    if in_sky.sum() < 100:
        # A crowded field: nearly every pixel is marked SOURCE. Keep those pixels and
        # let the clipping below drop the stars.
        in_sky = ring & ((flags & (SKY_BAD & ~pipeline._mask("SOURCE", "OUTLIER"))) == 0)
    if in_sky.sum() < 100:
        point["status"] = "no_sky"
        return point
    # Sigma clipping drops the other stars in the ring.
    _, sky, sky_sigma = sigma_clipped_stats(data[in_sky], sigma=3.0, maxiters=5)
    sky_var = float(sky_sigma) ** 2 / int(in_sky.sum())
    to_mjy = float(proj_plane_pixel_area(wcs)) * (np.pi / 180.0) ** 2 * 1e9   # MJy/sr x pixel -> mJy

    core = _sum_region(_coverage(xx, yy, x, y, 0.0, APERTURE_PX), data, variance, flags, float(sky), sky_var, to_mjy)
    point.update(status=core["status"], flux_mjy=core["value"], flux_err_mjy=core["error"],
                 flux_err_stat_mjy=core["error_stat"], flags=core["flags"], overflow_pixels=core["overflow_pixels"])
    for r_in, r_out in WING_RINGS_PX:
        wing = _sum_region(_coverage(xx, yy, x, y, r_in, r_out), data, variance, flags, float(sky), sky_var,
                           to_mjy, max_flagged=WING_MAX_FLAGGED)
        point["wings"].append({"ring_px": [r_in, r_out], "status": wing["status"], "value": wing["value"],
                               "error": wing["error"], "clean_fraction": wing["clean_fraction"]})
    return point


def _choose_wing_ring(points: list[dict]) -> int | None:
    """Index of the wing ring to use for one detector of one star.

    The innermost ring that gives a value in at least half of the exposures that have
    a wavelength; if none does, the ring that gives the most values. The choice looks
    only at how often a ring is usable, never at the values in it.
    """
    usable = [p for p in points if p["wings"]]
    if not usable:
        return None
    counts = [sum(p["wings"][i]["status"] == "ok" for p in usable) for i in range(len(WING_RINGS_PX))]
    for i, n in enumerate(counts):
        if n >= 0.5 * len(usable):
            return i
    return int(np.argmax(counts)) if max(counts) > 0 else None


# Without a motion in the request, a Gaia star this close to the requested position (on
# 2026.0, the date /api/resolve gives positions for) is taken to be the object asked for
# and followed. Farther than that, it is a different object: it used to be followed up
# to 15 arcsec, which at WISE 0855's position measured the G = 16.3 star 6.8 arcsec away.
FOLLOW_ARCSEC = 3.0
NOT_FOLLOWED_REPORT_ARCSEC = 15.0   # a nearer star that is not followed is named in `measured`


def choose_object(ra: float, dec: float, cone: list[dict] | None, motion: dict | None) -> tuple[dict | None, dict]:
    """What the brightness is measured on, and that in words: (target or None, measured).

    The object at (ra, dec) with the request's motion; else the Gaia star within
    FOLLOW_ARCSEC of (ra, dec) on 2026.0, with its own motion; else the spot (ra, dec)
    itself in every exposure (target None). `measured` says which, how far the object
    is from the request on that date, and names a nearer Gaia star that was not followed.
    """
    epoch = astrometry.RESOLVE_EPOCH
    if motion is not None:
        return motion, {"what": "request_motion", "source_id": None, "gmag": None, "offset_from_request_arcsec": 0.0,
                        "epoch": motion.get("ref_epoch", epoch), "nearest_gaia_not_followed": None,
                        "description": (f"The object at the requested position in {motion.get('ref_epoch', epoch):g}, "
                                        "followed with the proper motion and parallax given in the request.")}
    mjd = Time(epoch, format="jyear").mjd
    nearest = None
    for src in cone or []:
        s_ra, s_dec = astrometry.position_at(src, mjd, parallax=False)
        distance = float(np.hypot(*astrometry.offset_arcsec(ra, dec, s_ra, s_dec)))
        if nearest is None or distance < nearest[0]:
            nearest = (distance, src)
    def gmag(src: dict) -> float | None:
        return round(src["gmag"], 2) if src.get("gmag") is not None else None

    if nearest is not None and nearest[0] <= FOLLOW_ARCSEC:
        distance, src = nearest
        target = {"origin": "gaia_nearest", "ref_epoch": astrometry.GAIA_EPOCH, **src}
        g = f" (G = {src['gmag']:.2f})" if src.get("gmag") is not None else ""
        return target, {"what": "gaia_star", "source_id": src["source_id"], "gmag": gmag(src),
                        "offset_from_request_arcsec": round(distance, 2), "epoch": epoch,
                        "nearest_gaia_not_followed": None,
                        "description": (f"Gaia DR3 {src['source_id']}{g}, {distance:.1f} arcsec from the requested "
                                        f"position in {epoch:g}, followed with its Gaia proper motion and parallax.")}
    text = "The requested position itself, the same spot in every exposure: no motion was given, and "
    if cone is None:
        text += "Gaia did not answer, so it is not known whether a catalogued star is there."
    else:
        text += f"no Gaia star (G < 17) is within {FOLLOW_ARCSEC:.0f} arcsec of it in {epoch:g}."
    other = None
    if nearest is not None and nearest[0] <= NOT_FOLLOWED_REPORT_ARCSEC:
        distance, src = nearest
        other = {"source_id": src["source_id"], "gmag": gmag(src), "distance_arcsec": round(distance, 2)}
        text += (f" The nearest, Gaia DR3 {src['source_id']}, is {distance:.1f} arcsec away and was not followed "
                 "(see stars_in_circle for whether its light is in the measurements).")
    return None, {"what": "fixed_position", "source_id": None, "gmag": None, "offset_from_request_arcsec": 0.0,
                  "epoch": epoch, "nearest_gaia_not_followed": other, "description": text}


CIRCLE_ARCSEC = APERTURE_PX * pipeline.NATIVE_ARCSEC   # radius of the measuring circle on the sky
STARS_IN_CIRCLE_NOTE = (
    "Gaia DR3 stars (G < 17) whose place falls inside the measuring circle (radius_arcsec) around the object, per "
    "visit (by_epoch, at the visit's middle date) and over the whole run (stars: nearest and farthest distance, "
    "visits). Their light is part of every flux measured there, and nothing is subtracted, so a flux with such a "
    "star in the circle is the sum of both. Sources Gaia does not list, or lists fainter than G = 17, are not "
    "included; in the infrared some of them are bright. Stars further out can still fall in the wider ring of the "
    "wing measure.")


def stars_in_circle(points: list[dict], target: dict | None, ra: float, dec: float,
                    cone: list[dict] | None) -> dict:
    """Catalogue stars inside the measuring circle, per visit and over the whole run.

    The object is where the measurements were made: on the target's path, or at (ra,
    dec) if nothing was followed. A target that is a Gaia star is left out by its
    identifier; a target given by its motion has none, so a Gaia star within 1.5 arcsec
    of it is taken to be the object itself.
    """
    out: dict = {"radius_arcsec": round(CIRCLE_ARCSEC, 2), "g_limit": 17.0, "known": cone is not None,
                 "by_epoch": [], "stars": [], "note": STARS_IN_CIRCLE_NOTE}
    if cone is None:
        out["note"] = ("Gaia did not answer, so the stars inside the measuring circle are not known. "
                       + STARS_IN_CIRCLE_NOTE)
        return out
    own_id = target.get("source_id") if target else None
    same = pipeline.SAME_OBJECT_ARCSEC if target and not own_id else 0.0
    seen: dict[str, dict] = {}
    for ep in sorted({p["epoch"] for p in points}):
        mjd = float(np.mean([p["mjd"] for p in points if p["epoch"] == ep]))
        o_ra, o_dec = astrometry.position_at(target, mjd) if target else (ra, dec)
        near = astrometry.stars_near(o_ra, o_dec, cone, mjd, CIRCLE_ARCSEC, same_arcsec=same, exclude_id=own_id)
        stars = [{k: v for k, v in s.items() if k != "index"} for s in near]
        out["by_epoch"].append({"epoch": ep, "date": Time(mjd, format="mjd").iso[:10], "stars": stars})
        for s in stars:
            entry = seen.setdefault(s["source_id"], {"source_id": s["source_id"], "gmag": s["gmag"],
                                                     "nearest_arcsec": s["distance_arcsec"],
                                                     "farthest_arcsec": s["distance_arcsec"], "epochs": []})
            entry["nearest_arcsec"] = min(entry["nearest_arcsec"], s["distance_arcsec"])
            entry["farthest_arcsec"] = max(entry["farthest_arcsec"], s["distance_arcsec"])
            entry["epochs"].append(ep)
    out["stars"] = sorted(seen.values(), key=lambda s: s["nearest_arcsec"])
    return out


def channel_edges(wave_min: float, wave_max: float) -> np.ndarray:
    """Edges of the 17 equal-ratio wavelength channels of one detector."""
    return np.geomspace(wave_min, wave_max, CHANNELS_PER_DETECTOR + 1)


def measure_all(ra: float, dec: float, detector: int | None = None, progress=None, *,
                pmra: float | None = None, pmdec: float | None = None, parallax: float | None = None,
                pm_epoch: float = astrometry.RESOLVE_EPOCH) -> dict:
    """One measurement per exposure of the object at (ra, dec). Cached on disk.

    The object is followed with its proper motion and parallax: those given in the
    request (as /api/resolve returns them), else those of the Gaia star within 3 arcsec
    of (ra, dec) on 2026.0, else the spot (ra, dec) itself is measured in every exposure.
    `measured` in the result says which (see choose_object).
    """
    if detector is not None and not 1 <= detector <= 6:
        raise spherex.BadRequest("detector must be 1 to 6")
    if (pmra is None) != (pmdec is None):
        raise spherex.BadRequest("give both pmra and pmdec, or neither")
    motion = None
    if pmra is not None and pmdec is not None:
        motion = {"source_id": None, "ra": ra, "dec": dec, "pmra": float(pmra), "pmdec": float(pmdec),
                  "parallax": float(parallax) if parallax is not None else None, "gmag": None,
                  "ref_epoch": float(pm_epoch), "origin": "request"}
    key_text = f"v{VERSION},{ra:.5f},{dec:.5f},{detector or 'all'}"
    if motion:
        key_text += f",pm{motion['pmra']:.3f},{motion['pmdec']:.3f},{motion['parallax'] or 0:.3f},{pm_epoch:.3f}"
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    cache_file = PHOT_DIR / f"{key}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        # Measured again when the archive lists new exposures (results from before this
        # was recorded have no count and are kept).
        if not spherex.list_changed(ra, dec, cached.get("exposures_listed")):
            return cached

    exposures = spherex.find_exposures(ra, dec)
    base: dict = {"key": key, "ra": ra, "dec": dec, "detector": detector, "points": [], "failures": [],
                  "exposures_listed": len(exposures), "credit": pipeline.CREDIT}
    if not exposures:
        return {**base, "message": "SPHEREx has no public images covering this position."}
    epoch_of = pipeline.assign_epochs(exposures)
    chosen = [(e, ep) for e, ep in zip(exposures, epoch_of, strict=True)
              if detector is None or e["detector"] == detector]
    fetched = spherex.fetch_cutouts([e for e, _ in chosen], ra, dec, CUTOUT_DEG, progress=progress)
    failures = [f"{e['obs_id']} D{e['detector']}: {err}" for e, p, err in fetched if p is None]

    # The Gaia stars around the position: the object to follow when the request gave no
    # motion, and the stars that fall inside the measuring circle in any case.
    cone, gaia_error = pipeline.gaia_field(ra, dec, 0.1, quick=motion is not None)
    target, measured = choose_object(ra, dec, cone, motion)

    ranges: dict[int, tuple[float, float]] = {}
    points = []
    for (exp, path, _), (_, ep) in zip(fetched, chosen, strict=True):
        if path is None:
            continue
        ranges.setdefault(exp["detector"], (exp["wave_min"], exp["wave_max"]))
        t_ra, t_dec = astrometry.position_at(target, exp["mjd"]) if target else (ra, dec)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            point = measure(path, float(t_ra), float(t_dec))
        channel = None
        if point["wavelength_um"] is not None:
            edges = channel_edges(*ranges[exp["detector"]])
            channel = int(np.clip(np.searchsorted(edges, point["wavelength_um"]) - 1, 0, CHANNELS_PER_DETECTOR - 1))
        points.append({"obs_id": exp["obs_id"], "detector": exp["detector"], "epoch": ep + 1,
                       "channel": channel, **point})

    # One wing ring per detector, so that every point of a wavelength bin uses the same one.
    wing_rings: dict[str, list[float] | None] = {}
    for det in sorted(ranges):
        of_det = [p for p in points if p["detector"] == det]
        choice = _choose_wing_ring(of_det)
        wing_rings[str(det)] = list(WING_RINGS_PX[choice]) if choice is not None else None
        for p in of_det:
            wing = p["wings"][choice] if choice is not None and p["wings"] else None
            # No rings were measured when the core measurement stopped early; say why.
            p.update(wing_status=wing["status"] if wing else (p["status"] if not p["wings"] else "none"),
                     wing_mjy=wing["value"] if wing else None, wing_err_mjy=wing["error"] if wing else None,
                     wing_ring_px=wing["ring_px"] if wing else None,
                     wing_clean_fraction=wing["clean_fraction"] if wing else None,
                     wing_trusted=det in WING_TRUSTED_DETECTORS)
    for p in points:
        del p["wings"]

    result = {
        **base, "target": target, "measured": measured, "gaia_error": gaia_error, "failures": failures,
        "points": points,
        "detector_ranges_um": {str(d): list(r) for d, r in sorted(ranges.items())},
        "stars_in_circle": stars_in_circle(points, target, ra, dec, cone),
        "wing_ring_px": wing_rings,
        "method": {
            "flux": (f"Sum of the zodi-subtracted image in a circle of radius {APERTURE_PX} native pixels "
                     f"({APERTURE_PX * 6.15:.1f} arcsec) on the object's expected position, minus the local sky "
                     f"(clipped median in a ring {SKY_PX[0]:.0f} to {SKY_PX[1]:.0f} pixels out), times the pixel "
                     "solid angle. No aperture correction, so values are a few per cent below total flux."),
            "flux_unit": "mJy",
            "error": ("1 sigma: the archive's VARIANCE image and the uncertainty of the sky level "
                      "(flux_err_stat_mjy), with 3 per cent of the flux added in quadrature (flux_err_mjy), "
                      "the extra scatter the Explanatory Supplement reports for repeated measurements."),
            "rejection": ("A measurement has a number only if no pixel in the circle carries a flag of the "
                          "Explanatory Supplement's photometry list (SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, "
                          "NONLINEAR, PERSIST, BLOOM, SNOWBALL, HALO, SATELLITE_HALO) or is empty. 'saturated' "
                          "means a pixel overflowed within the first seconds (OVERFLOW with SUR_ERROR), received "
                          "charge from a saturated neighbour (BLOOM) or could not be linearised (NONLINEAR). "
                          "OVERFLOW alone is kept: the pixel reached half of full well and its value comes from "
                          "the reads before that; overflow_pixels counts them."),
            "statuses": {"ok": "measured", "saturated": "core saturated, no flux given",
                         "flagged": "a flagged pixel in the circle, no flux given",
                         "no_data": "an empty pixel in the circle", "no_sky": "too few clean pixels for the sky level",
                         "off_image": "too close to the edge of the detector"},
            "wing": ("wing_mjy is a relative brightness from unsaturated pixels, NOT a flux. It is the same "
                     "sky-subtracted sum in a ring around the star (wing_ring_px, in native pixels, chosen once per "
                     "detector), where only a few per cent of the star's light falls, plus any fainter star in "
                     "the ring. Compare it only with other wing values of the same star in the same wavelength "
                     "bin. A ring is used if it holds no saturated pixel and at most a tenth of it is flagged; "
                     "flagged pixels are left out (wing_clean_fraction). Use it only where wing_trusted is true "
                     "(detectors 5 and 6): there, two values of an unchanged star in one bin agree to about 5 per "
                     "cent (worst seen 16 per cent in detector 5, 68 in detector 6). In detectors 1 to 4 they "
                     "can disagree by a factor of two, so those values say nothing reliable about variability."),
            "wing_trusted_detectors": list(WING_TRUSTED_DETECTORS),
        },
    }
    # Cache only a complete result: with a failed download or no answer from Gaia (the
    # object would have been measured as if it did not move) the next request retries.
    if not failures and gaia_error is None:
        spherex.write_json(cache_file, result)
    return result


def _counts(points: list[dict]) -> dict:
    out: dict[str, int] = {}
    for p in points:
        out[p["status"]] = out.get(p["status"], 0) + 1
    return out


def lightcurve(ra: float, dec: float, detector: int | None = None, **motion) -> dict:
    """Brightness against time, grouped into wavelength bins (SPHEREx's 102 channels).

    Only points in the same bin are comparable in time: a different bin is a different
    colour of light, and the star is not equally bright in all of them.
    """
    data = measure_all(ra, dec, detector, **motion)
    groups: dict[tuple[int, int], list[dict]] = {}
    for p in data["points"]:
        if p["channel"] is not None:
            groups.setdefault((p["detector"], p["channel"]), []).append(p)
    bins = []
    for (det, ch), pts in sorted(groups.items()):
        pts = sorted(pts, key=lambda p: p["mjd"])
        lo, hi = data["detector_ranges_um"][str(det)]
        edges = channel_edges(lo, hi)
        ok = [p["flux_mjy"] for p in pts if p["status"] == "ok"]
        trusted = det in WING_TRUSTED_DETECTORS
        wing = [p["wing_mjy"] for p in pts if p["wing_status"] == "ok"]
        med = float(np.median(ok)) if ok else None
        wing_med = float(np.median(wing)) if wing else None
        bins.append({
            "bin": (det - 1) * CHANNELS_PER_DETECTOR + ch, "detector": det,
            "wavelength_um": [float(edges[ch]), float(edges[ch + 1])],
            "center_um": float(np.sqrt(edges[ch] * edges[ch + 1])),
            "n_points": len(pts), "n_measured": len(ok), "n_wing": len(wing), "status_counts": _counts(pts),
            "median_flux_mjy": med, "median_wing_mjy": wing_med,
            "wing_trusted": trusted, "wing_ring_px": data["wing_ring_px"].get(str(det)),
            "points": [{**p,
                        # Brightness relative to this bin's own median, so bins can share one chart.
                        "relative_flux": p["flux_mjy"] / med if p["status"] == "ok" and med and med > 0 else None,
                        # Only where the wing value has been shown to repeat (detectors 5 and 6).
                        "relative_wing": (p["wing_mjy"] / wing_med if trusted and p["wing_status"] == "ok"
                                          and wing_med and wing_med > 0 else None)}
                       for p in pts],
        })
    out = {k: v for k, v in data.items() if k != "points"}
    out.update(n_exposures=len(data["points"]), status_counts=_counts(data["points"]),
               n_wing=sum(p["wing_status"] == "ok" for p in data["points"]),
               n_wing_trusted=sum(p["wing_status"] == "ok" and p["wing_trusted"] for p in data["points"]), bins=bins)
    return out


def spectrum(ra: float, dec: float, epoch: int | None = None, detector: int | None = None, **motion) -> dict:
    """Brightness against wavelength: every exposure of one epoch (or of all), sorted by wavelength."""
    data = measure_all(ra, dec, detector, **motion)
    epochs = []
    for ep in sorted({p["epoch"] for p in data["points"]}):
        mjds = [p["mjd"] for p in data["points"] if p["epoch"] == ep]
        epochs.append({"epoch": ep, "date_start": Time(min(mjds), format="mjd").iso[:10],
                       "date_end": Time(max(mjds), format="mjd").iso[:10], "n_exposures": len(mjds)})
    if epoch is not None and epoch not in {e["epoch"] for e in epochs}:
        raise spherex.BadRequest(f"epoch must be one of {[e['epoch'] for e in epochs]}")
    pts = [p for p in data["points"] if p["wavelength_um"] is not None and (epoch is None or p["epoch"] == epoch)]
    pts.sort(key=lambda p: p["wavelength_um"])
    out = {k: v for k, v in data.items() if k != "points"}
    out.update(epoch=epoch, epochs=epochs, n_exposures=len(pts), status_counts=_counts(pts),
               n_wing=sum(p["wing_status"] == "ok" for p in pts),
               n_wing_trusted=sum(p["wing_status"] == "ok" and p["wing_trusted"] for p in pts), points=pts)
    return out

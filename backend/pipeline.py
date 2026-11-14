"""Turn SPHEREx exposures into one stacked frame per epoch for one detector.

Steps follow "Processing steps for /api/frames" in CLAUDE.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import warnings
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp
from scipy.ndimage import label, maximum_filter
from scipy.optimize import least_squares

from . import astrometry, spherex

logging.getLogger("astropy").setLevel(logging.ERROR)  # silence the per-file SIP notice

GRID_ARCSEC = 2.0        # output pixel size
NATIVE_ARCSEC = 6.15     # SPHEREx pixel size
EPOCH_GAP_DAYS = 30.0    # a gap longer than this between exposures starts a new epoch
FRAMES_DIR = spherex.CACHE / "frames"
# Part of every cache key. Raise it whenever a change here alters the pictures or the
# numbers: results made by older code are then never served again. (3 is taken by the
# flags image of pull request #24, so the new stacking rule went straight to 4.)
VERSION = 4

# Dropping glitches when exposures are stacked (see Stacker).
MIN_EXPOSURES_TO_REJECT = 5   # with fewer exposures nothing is dropped
GLITCH_SIGMA = 6.0
# Largest patch a glitch makes on the grid: a 2 x 2 block of native pixels, which
# resampling spreads over 3 x 3 native pixels (85 grid pixels).
GLITCH_MAX_PX = int(round(9 * (NATIVE_ARCSEC / GRID_ARCSEC) ** 2))
# Stacking needs memory in proportion to the picture. One build at a time keeps that
# to one picture's worth however many requests arrive together, and lets a second
# request for the same view (a page asks for frames and stars at once) wait and read
# the cache instead of repeating the work.
_BUILD_LOCK = threading.Lock()

# Flag bits: Table 16 of the SPHEREx Explanatory Supplement v2.1 (2026-11-10).
BIT = {"TRANSIENT": 0, "OVERFLOW": 1, "SUR_ERROR": 2, "NONFUNC": 6, "DICHROIC": 7,
       "MISSING_DATA": 9, "HOT": 10, "COLD": 11, "FULLSAMPLE": 12, "PHANMISS": 14,
       "NONLINEAR": 15, "PERSIST": 17, "OUTLIER": 19, "CROSSTALK": 20, "SOURCE": 21,
       "GHOST": 22, "GHOST_FPA": 23, "GHOST_EXT": 24, "STREAK": 25, "BLOOM": 26,
       "SNOWBALL": 27, "HALO": 28, "SATELLITE_HALO": 29}


def _mask(*names: str) -> int:
    return sum(1 << BIT[n] for n in names)


# Always rejected: detector defects and artefacts. This is the list the project's own
# all-sky cubes reject, minus the three bits handled separately below.
ALWAYS_BAD = _mask("NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD", "PHANMISS",
                   "NONLINEAR", "PERSIST", "CROSSTALK", "STREAK", "SNOWBALL", "SATELLITE_HALO")
# Cosmic-ray bits. Rejected, EXCEPT where BLOOM is also set: next to a saturated star
# the onboard algorithm raises these because of charge spill, not a cosmic ray.
# Rejecting them there would punch a hole where every bright star is, so those pixels
# are kept for display. They are not trustworthy for photometry.
COSMIC_RAY = _mask("TRANSIENT", "SUR_ERROR", "HALO")
BLOOM = _mask("BLOOM")
OVERFLOW = _mask("OVERFLOW")
# SOURCE (21) marks any pixel on a known source and OUTLIER (19) can mark a real
# change on the sky, so neither is ever a reason to reject a pixel.


def make_grid(ra: float, dec: float, fov_deg: float) -> tuple[WCS, int]:
    """North-up, east-left tangent-plane grid centred on the request."""
    n = int(round(fov_deg * 3600.0 / GRID_ARCSEC))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2.0, (n + 1) / 2.0]
    w.wcs.cdelt = [-GRID_ARCSEC / 3600.0, GRID_ARCSEC / 3600.0]
    return w, n


def assign_epochs(exposures: list[dict]) -> list[int]:
    """Epoch index for each exposure (input sorted by time), split at long gaps.

    Uses the exposures of every detector, so epoch numbers mean the same thing
    whichever detector is displayed.
    """
    idx, cur = [], 0
    for i, e in enumerate(exposures):
        if i and e["mjd"] - exposures[i - 1]["mjd"] > EPOCH_GAP_DAYS:
            cur += 1
        idx.append(cur)
    return idx


def impossible_pixels(image: np.ndarray, variance: np.ndarray) -> np.ndarray:
    """Pixels whose raw brightness is far below zero, which no sky can produce.

    The archive leaves some of these unflagged: 50 to 100 pixels per target over a few
    hundred cutouts, mostly in detectors 4 to 6, from -0.1 down to -2000 MJy/sr. One
    of them put a black hole in a three-exposure epoch of WISE 0855, where there are
    too few readings for stack() to reject it.
    """
    with np.errstate(invalid="ignore"):
        return image < -10.0 * np.sqrt(variance)


def prepare_cutout(path: Path, grid: WCS, n: int, ra: float, dec: float) -> dict | None:
    """Clean one cutout and resample it onto the shared grid."""
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = hdul["FLAGS"].data
        variance = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data
    wcs = WCS(header)

    data = image - zodi
    bloom = (flags & BLOOM) != 0
    bad = (((flags & ALWAYS_BAD) != 0) | (((flags & COSMIC_RAY) != 0) & ~bloom) | ~np.isfinite(data)
           | impossible_pixels(image, variance))
    saturated = ~np.isfinite(image) & ((flags & OVERFLOW) != 0)
    data[bad] = np.nan
    good = ~bad
    if good.sum() < 50:
        return None

    # Per-exposure sky level left after the zodiacal model (diffuse Galactic light,
    # model error). It differs from exposure to exposure because each one sees the
    # field at a different wavelength, so it is removed before stacking.
    _, sky, _ = sigma_clipped_stats(data[good], sigma=3.0, maxiters=5)
    data -= sky
    # One weight per exposure: inverse of its typical background variance. A per-pixel
    # inverse-variance weight would down-weight exactly the exposures in which a
    # source is brightest (the variance includes source photon noise).
    weight = 1.0 / np.nanmedian(variance[good])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resampled, footprint = reproject_interp((data, wcs), grid, shape_out=(n, n), order="bilinear")
        sat_map, _ = reproject_interp((saturated.astype("float64"), wcs), grid, shape_out=(n, n),
                                      order="nearest-neighbor")
    if not np.isfinite(resampled).any():
        return None

    # Wavelength this exposure sampled at the centre of the request.
    x, y = wcs.all_world2pix(ra, dec, 0)
    xi, yi = int(round(float(x))), int(round(float(y)))
    inside = 0 <= yi < wave.shape[0] and 0 <= xi < wave.shape[1]
    return {
        "data": resampled,
        "saturated": np.nan_to_num(sat_map) > 0.5,
        "weight": weight,
        "mjd": float(header["MJD-AVG"]),
        "wave_at_target": float(wave[yi, xi]) if inside else None,
        "masked_fraction": float(bad.mean()),
    }


class Stacker:
    """Weighted mean of resampled exposures, taken in one at a time.

    Glitches. The archive's flags miss some (seen: one pixel at -7 MJy/sr among 22
    readings near 0.01), so one reading per pixel can be dropped at each end:

    - the highest of at least three readings, if it is far above the second highest,
      and the lowest, if it is far below the second lowest. "Far" is GLITCH_SIGMA times
      that exposure's noise plus the brightness of the brightest nearby pixel in the
      second-highest image, because a star's reading at a fixed sky position
      legitimately swings by a factor of a few between exposures: the image is
      undersampled (PSF about 1.2 pixels wide) and each exposure is at its own wavelength.
    - and only where that exposure stands out in a small patch: the connected patch
      in which it is the extreme by half the threshold must be no larger than
      GLITCH_MAX_PX, and then that whole patch is dropped. A cosmic ray or bad pixel
      is a few native pixels. A larger patch is one exposure whose background differs
      from the rest (stray light from a bright star nearby); dropping parts of it
      leaves steps in the picture.

    Anything seen in two exposures therefore stays. An earlier version dropped every
    reading far from the per-pixel median, which removed real light: a brown dwarf is
    bright only in the exposures at one end of a detector's wavelength range, so the
    median sat near the sky and the bright readings went (Epsilon Indi B, detector 1,
    lost four fifths of its brightness in one visit).

    Memory. Only running sums and the two highest and two lowest readings per pixel
    are kept, never the exposures, so memory does not grow with their number.
    """

    def __init__(self, n: int) -> None:
        shape = (n, n)
        self.weights: list[float] = []
        self.sum_w = np.zeros(shape)
        self.sum_wv = np.zeros(shape)
        self.count = np.zeros(shape, dtype="int32")
        self.overflowed = np.zeros(shape, dtype="int32")    # exposures saturated here
        self.high = np.full(shape, -np.inf)                  # highest reading, and which exposure gave it
        self.high_from = np.full(shape, -1, dtype="int32")
        self.high2 = np.full(shape, -np.inf)                 # second highest
        self.low = np.full(shape, np.inf)
        self.low_from = np.full(shape, -1, dtype="int32")
        self.low2 = np.full(shape, np.inf)

    def add(self, data: np.ndarray, saturated: np.ndarray, weight: float) -> None:
        i = len(self.weights)
        self.weights.append(float(weight))
        ok = np.isfinite(data)
        self.sum_w += float(weight) * ok
        self.sum_wv += float(weight) * np.where(ok, data, 0.0)
        self.count += ok
        self.overflowed += saturated
        up = np.where(ok, data, -np.inf)
        top = up > self.high
        self.high2 = np.where(top, self.high, np.maximum(self.high2, up))
        self.high_from[top] = i
        self.high[top] = up[top]
        down = np.where(ok, data, np.inf)
        bottom = down < self.low
        self.low2 = np.where(bottom, self.low, np.minimum(self.low2, down))
        self.low_from[bottom] = i
        self.low[bottom] = down[bottom]

    def result(self) -> dict:
        """The stacked image. Call once: it uses up the running sums."""
        rejected = 0
        if len(self.weights) >= MIN_EXPOSURES_TO_REJECT:
            weights = np.array(self.weights)
            noise = 1.0 / np.sqrt(weights)
            enough = self.count >= 3
            nearby = maximum_filter(np.where(np.isfinite(self.high2), np.abs(self.high2), 0.0), size=9)
            drops = []
            with np.errstate(invalid="ignore"):
                for first, second, source, sign in ((self.high, self.high2, self.high_from, 1.0),
                                                    (self.low, self.low2, self.low_from, -1.0)):
                    gap = sign * (first - second)
                    limit = GLITCH_SIGMA * noise[source] + nearby
                    seed = enough & (gap > limit)
                    wide = enough & (gap > 0.5 * limit)
                    for i in np.unique(source[seed]):
                        patches, _ = label(wide & (source == i))
                        sizes = np.bincount(patches.ravel())
                        hit = np.unique(patches[seed & (source == i)])
                        # The whole patch goes, not only its core: resampling spreads a
                        # glitch, and the rim left behind would show as a ring.
                        drops.append((np.isin(patches, hit[sizes[hit] <= GLITCH_MAX_PX]), first, weights[i]))
            for drop, first, weight in drops:
                self.sum_wv[drop] -= weight * first[drop]
                self.sum_w[drop] -= weight
                self.count[drop] -= 1
                rejected += int(drop.sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = self.sum_wv / self.sum_w
        mean[self.count == 0] = np.nan
        return {"image": mean, "n_valid": self.count, "rejected_readings": rejected,
                # No usable value in any exposure, and at least one of them overflowed here.
                "saturated": ~np.isfinite(mean) & (self.overflowed > 0)}


def stack(items: list[dict]) -> dict:
    """Weighted mean of resampled exposures (what prepare_cutout returns); see Stacker."""
    stacker = Stacker(items[0]["data"].shape[0])
    for it in items:
        stacker.add(it["data"], it["saturated"], it["weight"])
    return stacker.result()


def fit_source(image: np.ndarray, x0: float, y0: float, search: int = 7, half: int = 10) -> dict | None:
    """Centre of the source nearest (x0, y0): a round Gaussian fitted to valid pixels.

    Pixels with no data (a saturated core, for instance) are left out of the fit,
    so a saturated star is located from its unsaturated wings.
    """
    ny, nx = image.shape
    xi, yi = int(round(x0)), int(round(y0))
    if not (half <= xi < nx - half and half <= yi < ny - half):
        return None
    # Start from the brightest pixel near the expected place.
    box = image[yi - search:yi + search + 1, xi - search:xi + search + 1]
    if not np.isfinite(box).any():
        return None
    py, px = np.unravel_index(np.nanargmax(box), box.shape)
    cx, cy = xi - search + px, yi - search + py
    if not (half <= cx < nx - half and half <= cy < ny - half):
        return None
    win = image[cy - half:cy + half + 1, cx - half:cx + half + 1]
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1]
    ok = np.isfinite(win)
    if ok.sum() < 40:
        return None
    base = float(np.nanpercentile(win, 20))
    amp = float(np.nanmax(win) - base)
    if amp <= 0:
        return None

    def resid(p):
        a, mx, my, s, b = p
        return (a * np.exp(-((xx - mx) ** 2 + (yy - my) ** 2) / (2 * s * s)) + b - win)[ok]

    try:
        fit = least_squares(resid, [amp, 0.0, 0.0, 2.3, base],
                            bounds=([0, -half, -half, 0.8, -np.inf], [np.inf, half, half, 8.0, np.inf]))
    except ValueError:
        return None
    a, mx, my, s, b = fit.x
    # Formal uncertainty of the centre from the fit covariance.
    dof = max(ok.sum() - 5, 1)
    try:
        cov = np.linalg.inv(fit.jac.T @ fit.jac) * (2 * fit.cost / dof)
        err = float(np.sqrt(cov[1, 1] + cov[2, 2]))
    except np.linalg.LinAlgError:
        err = None
    noise = float(np.sqrt(2 * fit.cost / dof))
    return {"x": float(cx + mx), "y": float(cy + my), "amplitude": float(a), "sigma_px": float(s),
            "err_px": err, "snr": float(a / noise) if noise > 0 else None}


def stretch_limits(images: list[np.ndarray]) -> dict:
    """One asinh stretch for every epoch of a detector, from all their pixels together."""
    pix = np.concatenate([im[np.isfinite(im)] for im in images])
    _, median, sigma = sigma_clipped_stats(pix, sigma=3.0, maxiters=5)
    # The top of the scale is the brightest pixel, so a bright star keeps its shape
    # instead of clipping to a white blob; asinh keeps the faint stars visible.
    return {"vmin": float(median - 2.0 * sigma), "vmax": float(pix.max()), "soft": float(3.0 * sigma)}


def difference_limits(diffs: list[np.ndarray]) -> dict | None:
    """One zero-centred asinh stretch for every difference frame of a view."""
    pix = np.concatenate([d[np.isfinite(d)] for d in diffs])
    if pix.size == 0:
        return None
    _, _, sigma = sigma_clipped_stats(pix, sigma=3.0, maxiters=5)
    peak = float(np.abs(pix).max())
    if peak <= 0 or sigma <= 0:
        return None
    # Symmetric about zero, so mid-grey always means "no change". The ends are the
    # largest change in any frame, so the bright and dark halves of a pair keep their shape.
    return {"vmin": -peak, "vmax": peak, "soft": float(3.0 * sigma)}


def to_difference_png(diff: np.ndarray, lim: dict, path: Path) -> None:
    """8-bit greyscale PNG of a difference: mid-grey is no change, white brighter than
    the reference, black fainter. Pixels missing from either image are transparent."""
    scaled = 0.5 + 0.5 * np.arcsinh(diff / lim["soft"]) / np.arcsinh(lim["vmax"] / lim["soft"])
    grey = np.clip(np.nan_to_num(scaled, nan=0.5), 0, 1)
    alpha = np.where(np.isfinite(diff), 255, 0).astype("uint8")
    rgba = np.dstack([np.round(grey * 255).astype("uint8")] * 3 + [alpha])
    Image.fromarray(rgba[::-1], "RGBA").save(path)


def to_png(st: dict, lim: dict, path: Path) -> None:
    """8-bit greyscale PNG. Saturated pixels are white; pixels with no data are transparent."""
    im = st["image"]
    scaled = np.arcsinh((im - lim["vmin"]) / lim["soft"]) / np.arcsinh((lim["vmax"] - lim["vmin"]) / lim["soft"])
    grey = np.clip(np.nan_to_num(scaled, nan=0.0), 0, 1)
    grey[st["saturated"]] = 1.0
    alpha = np.where(np.isfinite(im) | st["saturated"], 255, 0).astype("uint8")
    rgba = np.dstack([(grey * 255).astype("uint8")] * 3 + [alpha])
    # FITS row 0 is the bottom of the image (south); image files start at the top.
    Image.fromarray(rgba[::-1], "RGBA").save(path)


MODES = ("normal", "difference", "sum")
REFERENCES = ("first", "mean")
TRACKS = ("sky", "target")
CREDIT = "NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive (IRSA); ESA Gaia DR3"


def _find_target(ra: float, dec: float, fov: float, mid_mjd: float,
                 motion: dict | None) -> tuple[dict | None, str | None]:
    """The object whose expected position is drawn in each frame.

    If the request gave a proper motion (as /api/resolve returns it), the target is
    the object at the centre of the request with that motion. This is the only way an
    object that Gaia does not list (WISE 0855, for one) gets an expected position.
    Otherwise it is the Gaia star nearest the centre, if one is within 15 arcsec.
    """
    if motion is not None:
        return motion, None
    try:
        nearby = astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06)
    except spherex.ArchiveError as e:
        return None, str(e)
    best = None
    for src in nearby:
        sra, sdec = astrometry.position_at(src, mid_mjd)
        sep = float(np.hypot(*astrometry.offset_arcsec(ra, dec, sra, sdec)))
        if sep < 15.0 and (best is None or sep < best[0]):
            best = (sep, src)
    return (best[1] if best else None), None


def _describe(items: list[dict], st: dict, grid: WCS, n: int, target: dict | None) -> dict:
    """Everything reported about one stacked image except where its picture is."""
    mjds = np.array([it["mjd"] for it in items])
    weights = np.array([it["weight"] for it in items])
    mjd_mean = float(np.average(mjds, weights=weights))
    waves = [it["wave_at_target"] for it in items if it["wave_at_target"] is not None]

    predicted = None
    x0 = y0 = (n - 1) / 2.0
    if target:
        pra, pdec = astrometry.position_at(target, mjd_mean)
        px, py = grid.all_world2pix(pra, pdec, 0)
        x0, y0 = float(px), float(py)
        predicted = {"ra": pra, "dec": pdec, "x": x0, "y": n - 1 - y0}
    fit = fit_source(st["image"], x0, y0)
    centroid = None
    if fit:
        cra, cdec = grid.all_pix2world(fit["x"], fit["y"], 0)
        centroid = {"ra": float(cra), "dec": float(cdec),
                    "x": fit["x"], "y": n - 1 - fit["y"],  # y counted from the top of the PNG
                    "err_arcsec": fit["err_px"] * GRID_ARCSEC if fit["err_px"] is not None else None,
                    "snr": fit["snr"], "fwhm_arcsec": fit["sigma_px"] * 2.3548 * GRID_ARCSEC}
    return {
        "date_start": Time(mjds.min(), format="mjd").iso[:10],
        "date_end": Time(mjds.max(), format="mjd").iso[:10],
        "mjd_mean": mjd_mean,
        "date_mean": Time(mjd_mean, format="mjd").iso[:10],
        "n_exposures": len(items),
        "wavelength_um": [min(waves), max(waves)] if waves else None,
        "flagged_fraction": float(np.mean([it["masked_fraction"] for it in items])),
        "saturated_pixels": int(st["saturated"].sum()),
        "rejected_readings": st["rejected_readings"],
        "centroid": centroid,
        "predicted": predicted,
    }


def _save(meta_file: Path, meta: dict) -> None:
    """Cache a finished result, but only a complete one.

    If some exposures could not be downloaded, or Gaia did not answer (so no target
    and no predicted positions), the result is still returned, with `failures` or
    `gaia_error` saying so, and the next request tries again instead of being served
    the degraded version for ever.
    """
    if not meta.get("failures") and meta.get("gaia_error") is None:
        spherex.write_json(meta_file, meta, indent=1)


def build_frames(ra: float, dec: float, fov: float = 0.1, detector: int = 5,
                 mode: str = "normal", progress=None, *,
                 pmra: float | None = None, pmdec: float | None = None, parallax: float | None = None,
                 pm_epoch: float = astrometry.RESOLVE_EPOCH,
                 reference: str = "first", track: str = "sky") -> dict:
    """Frames for the player, for one detector.

    mode "normal": one stacked image per epoch.
    mode "difference": each epoch minus a reference, so whatever stays put cancels.
        reference "first" subtracts the first epoch (one frame fewer than there are
        epochs); "mean" subtracts the stack of all epochs (one frame per epoch).
    mode "sum": every exposure of every epoch in one deeper image. track "sky" lines
        the exposures up on the sky; track "target" shifts each one by the target's
        known motion first, so a fast mover adds up in one place and the stars smear.

    pmra, pmdec (mas/yr, pmra including cos dec) and parallax (mas) describe an object
    that is at (ra, dec) at the Julian year pm_epoch, which is what /api/resolve returns.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    if not 1 <= detector <= 6:
        raise ValueError("detector must be 1 to 6")
    if reference not in REFERENCES:
        raise ValueError(f"reference must be one of {', '.join(REFERENCES)}")
    if track not in TRACKS:
        raise ValueError(f"track must be one of {', '.join(TRACKS)}")
    if (pmra is None) != (pmdec is None):
        raise ValueError("give both pmra and pmdec, or neither")
    motion = None
    if pmra is not None and pmdec is not None:
        motion = {"source_id": None, "ra": ra, "dec": dec, "pmra": float(pmra), "pmdec": float(pmdec),
                  "parallax": float(parallax) if parallax is not None else None, "gmag": None,
                  "ref_epoch": float(pm_epoch), "origin": "request"}

    key_text = f"v{VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{detector},{mode}"
    if motion:
        key_text += f",pm{motion['pmra']:.3f},{motion['pmdec']:.3f},{motion['parallax'] or 0:.3f},{pm_epoch:.3f}"
    if mode == "difference" and reference != "first":
        key_text += f",reference-{reference}"
    if mode == "sum" and track != "sky":
        key_text += f",track-{track}"
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    out_dir = FRAMES_DIR / key
    meta_file = out_dir / "frames.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())

    all_exposures = spherex.find_exposures(ra, dec)
    if not all_exposures:
        return {"key": key, "frames": [], "message": "SPHEREx has no public images covering this position."}
    epoch_of = assign_epochs(all_exposures)
    chosen = [(e, ep) for e, ep in zip(all_exposures, epoch_of, strict=True) if e["detector"] == detector]

    # The detector can sit at any angle on the sky, so fetch the diagonal of the field.
    cutout_deg = round(fov * 1.5, 4)
    fetched = spherex.fetch_cutouts([e for e, _ in chosen], ra, dec, cutout_deg, progress=progress)
    failures = [f"{e['obs_id']} D{e['detector']}: {err}" for e, p, err in fetched if p is None]
    usable = [(path, ep) for (_, path, _), (_, ep) in zip(fetched, chosen, strict=True) if path is not None]

    with _BUILD_LOCK:
        if meta_file.exists():          # another request built this view while we waited
            return json.loads(meta_file.read_text())
        return _build(key, usable, failures, len(all_exposures), ra, dec, fov, detector, mode, motion,
                      reference, track)


def _build(key: str, usable: list[tuple[Path, int]], failures: list[str], n_all: int, ra: float, dec: float,
           fov: float, detector: int, mode: str, motion: dict | None, reference: str, track: str) -> dict:
    """Stack the cutouts of one view and write its pictures (the part of build_frames that needs memory).

    Exposures are taken in one at a time and never kept: an epoch's Stacker is turned
    into its image as soon as the next epoch starts, and at most one more Stacker
    (every epoch together, for the sum and the mean reference) lives beside it.
    """
    out_dir = FRAMES_DIR / key
    meta_file = out_dir / "frames.json"
    grid, n = make_grid(ra, dec, fov)
    want_total = (mode == "sum" and track == "sky") or (mode == "difference" and reference == "mean")
    total = Stacker(n) if want_total else None
    stacks: dict[int, dict] = {}
    by_epoch: dict[int, list[dict]] = {}     # what is known about each exposure, without its pixels
    paths: dict[int, list[Path]] = {}
    open_epoch = -1
    open_stacker: Stacker | None = None
    for path, ep in usable:                  # oldest first, so each epoch's exposures come together
        item = prepare_cutout(path, grid, n, ra, dec)
        if item is None:
            continue
        data, saturated = item.pop("data"), item.pop("saturated")
        if mode != "sum":
            if open_stacker is None or ep != open_epoch:
                if open_stacker is not None:
                    stacks[open_epoch] = open_stacker.result()
                open_epoch, open_stacker = ep, Stacker(n)
            open_stacker.add(data, saturated, item["weight"])
        if total is not None:
            total.add(data, saturated, item["weight"])
        by_epoch.setdefault(ep, []).append(item)
        paths.setdefault(ep, []).append(path)
    if open_stacker is not None:
        stacks[open_epoch] = open_stacker.result()
    if not by_epoch:
        return {"key": key, "frames": [], "failures": failures,
                "message": f"No usable detector {detector} exposures at this position."}

    every = [it for items in by_epoch.values() for it in items]
    mid_mjd = float(np.mean([it["mjd"] for it in every]))
    target, gaia_error = _find_target(ra, dec, fov, mid_mjd, motion)
    if target is not None:
        target = {"origin": "gaia_nearest", "ref_epoch": astrometry.GAIA_EPOCH, **target}

    meta: dict = {
        "key": key, "ra": ra, "dec": dec, "fov": fov, "detector": detector, "mode": mode,
        "size_px": n, "pixel_arcsec": GRID_ARCSEC,
        "target": target, "gaia_error": gaia_error,
        "exposures_total_all_detectors": n_all,
        "failures": failures, "frames": [], "credit": CREDIT,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[dict] = meta["frames"]

    if mode == "sum":
        note = None
        if track == "target":
            if target is None or target.get("pmra") is None or target.get("pmdec") is None:
                raise ValueError("track=target needs a proper motion: pass pmra and pmdec (see /api/resolve), "
                                 "or centre the request on a Gaia star")
            # Shift each exposure by how far the target is, on its date, from where it
            # is on the mean date. The target then adds up at one place; the sky does not.
            ref_mjd = float(np.average([it["mjd"] for it in every], weights=[it["weight"] for it in every]))
            ref_ra, ref_dec = astrometry.position_at(target, ref_mjd)
            every = []
            total = Stacker(n)
            for ep in by_epoch:
                for path, first_pass in zip(paths[ep], by_epoch[ep], strict=True):
                    t_ra, t_dec = astrometry.position_at(target, first_pass["mjd"])
                    shifted, _ = make_grid(ra + (t_ra - ref_ra), dec + (t_dec - ref_dec), fov)
                    item = prepare_cutout(path, shifted, n, ra, dec)
                    if item is not None:
                        total.add(item.pop("data"), item.pop("saturated"), item["weight"])
                        every.append(item)
            note = ("Exposures were shifted by the target's known proper motion and parallax before "
                    "adding, so the target is sharp and every other object is smeared along its track. "
                    "Sky coordinates in this frame are right for the target only, on the mean date.")
        assert total is not None
        st = total.result()
        limits = stretch_limits([st["image"]])
        name = "sum.png" if track == "sky" else "sum_target.png"
        to_png(st, limits, out_dir / name)
        frames.append({"epoch": None, "epochs_combined": [ep + 1 for ep in by_epoch],
                       **_describe(every, st, grid, n, target), "image": f"/frames/{key}/{name}"})
        meta["stretch"] = {"kind": "asinh", **limits, "unit": "MJy/sr"}
        meta["combine"] = "weighted mean of every exposure of every epoch (units stay MJy/sr)"
        meta["registration"] = "sky" if track == "sky" else "target_motion"
        if note:
            meta["note"] = note
        _save(meta_file, meta)
        return meta

    if mode == "normal":
        limits = stretch_limits([s["image"] for s in stacks.values()])
        for ep, st in stacks.items():
            name = f"epoch{ep + 1}.png"
            to_png(st, limits, out_dir / name)
            frames.append({"epoch": ep + 1, **_describe(by_epoch[ep], st, grid, n, target),
                           "image": f"/frames/{key}/{name}"})
        meta["stretch"] = {"kind": "asinh", **limits, "unit": "MJy/sr"}
        _save(meta_file, meta)
        return meta

    # mode == "difference"
    first = next(iter(stacks))
    meta["reference"] = reference
    meta["stretch"] = None
    if len(stacks) < 2:
        meta["message"] = "Only one epoch has been observed here, so there is nothing to subtract yet."
        return meta   # not cached: a second epoch will arrive
    if reference == "first":
        ref_image, ref_epoch = stacks[first]["image"], first + 1
        shown = [ep for ep in stacks if ep != first]
        meta["reference_description"] = f"epoch {first + 1} ({len(by_epoch[first])} exposures)"
    else:
        assert total is not None
        ref_image, ref_epoch = total.result()["image"], None
        shown = list(stacks)
        meta["reference_description"] = f"all {len(stacks)} epochs stacked together ({len(every)} exposures)"
    diffs = {ep: stacks[ep]["image"] - ref_image for ep in shown}
    diff_limits = difference_limits(list(diffs.values()))
    if diff_limits is None:
        meta["message"] = "The epochs do not overlap on valid pixels, so no difference could be made."
        return meta
    for ep in shown:
        name = f"diff{ep + 1}.png"
        to_difference_png(diffs[ep], diff_limits, out_dir / name)
        frames.append({"epoch": ep + 1, "reference_epoch": ref_epoch,
                       **_describe(by_epoch[ep], stacks[ep], grid, n, target),
                       "image": f"/frames/{key}/{name}",
                       "difference_valid_fraction": float(np.isfinite(diffs[ep]).mean())})
    meta["stretch"] = {"kind": "asinh-symmetric", **diff_limits, "unit": "MJy/sr"}
    meta["note"] = ("Mid-grey is no change, white is brighter than the reference, black is fainter; "
                    "transparent pixels are missing from this epoch or the reference (saturated or no data). "
                    "centroid and predicted are measured on this epoch's ordinary image, not the difference.")
    if reference == "first":
        ref_desc = _describe(by_epoch[first], stacks[first], grid, n, target)
        meta["reference_frame"] = {"epoch": first + 1, **ref_desc}
    _save(meta_file, meta)
    return meta

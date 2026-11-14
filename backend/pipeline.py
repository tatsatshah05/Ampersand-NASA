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
# flags image of pull request #24; 4 was the new stacking rule; 5 centroid meaning the
# target or nothing; 6 photometry_saturated_exposures; 7 flags_image; 8 detection_sigma;
# 9 saturated_core and its position uncertainty; 10 blend.)
VERSION = 10

# Dropping glitches when exposures are stacked (see Stacker).
MIN_EXPOSURES_TO_REJECT = 5   # with fewer exposures nothing is dropped
GLITCH_SIGMA = 6.0
GLITCH_NEARBY_PX = 9          # side of the box in which "the brightest nearby pixel" is looked for
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


def _mark_on_grid(mask: np.ndarray, wcs: WCS, grid: WCS, n: int) -> np.ndarray:
    """The grid pixels within half a native pixel (in x and in y) of a cutout pixel set in `mask`.

    Usually only a few cutout pixels are set, so this is much cheaper than resampling
    the whole mask; the native pixel's tilt on the grid is ignored.
    """
    out = np.zeros((n, n), dtype=bool)
    rows, columns = np.nonzero(mask)
    if rows.size == 0:
        return out
    gx, gy = grid.all_world2pix(*wcs.all_pix2world(columns, rows, 0), 0)
    half = NATIVE_ARCSEC / GRID_ARCSEC / 2.0
    for x, y in zip(np.atleast_1d(gx), np.atleast_1d(gy), strict=True):
        x0, x1 = max(int(np.ceil(x - half)), 0), min(int(np.floor(x + half)), n - 1)
        y0, y1 = max(int(np.ceil(y - half)), 0), min(int(np.floor(y + half)), n - 1)
        if x0 <= x1 and y0 <= y1:
            out[y0:y1 + 1, x0:x1 + 1] = True
    return out


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

    from . import photometry  # here and not at the top: photometry imports this module

    data = image - zodi
    impossible = impossible_pixels(image, variance)
    # Pixels the brightness measurement calls saturated (a stricter rule than the one
    # for the picture; see photometry.saturated_pixels), kept as their positions.
    lost = photometry.saturated_pixels(flags, np.where(impossible, np.nan, data))
    bloom = (flags & BLOOM) != 0
    bad = (((flags & ALWAYS_BAD) != 0) | (((flags & COSMIC_RAY) != 0) & ~bloom) | ~np.isfinite(data)
           | impossible)
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
        # Where the picture's values come from pixels that the photometry rule calls
        # saturated (bloom-flagged among them). They stay in the picture, since they draw
        # the star, but a position fitted to them is unreliable.
        "lost": _mark_on_grid(lost & ~bad, wcs, grid, n),
        "weight": weight,
        "mjd": float(header["MJD-AVG"]),
        "wave_at_target": float(wave[yi, xi]) if inside else None,
        "masked_fraction": float(bad.mean()),
        "wcs": wcs,
        "saturated_for_photometry": np.nonzero(lost),     # (rows, columns) in the cutout
    }


def core_saturated(item: dict, ra: float, dec: float) -> bool:
    """Would /api/lightcurve call (ra, dec) saturated in this exposure?

    True if a pixel that its measuring circle touches is saturated by the photometry
    rule. `item` is what prepare_cutout returned.
    """
    from . import photometry

    rows, columns = item["saturated_for_photometry"]
    if rows.size == 0:
        return False
    x, y = item["wcs"].all_world2pix(ra, dec, 0, quiet=True)
    touched = photometry._coverage(columns, rows, float(x), float(y), 0.0, photometry.APERTURE_PX) > 0
    return bool(touched.any())


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
        self.lost = np.zeros(shape, dtype="int32")          # exposures whose value here is saturated or bloomed
        self.high = np.full(shape, -np.inf)                  # highest reading, and which exposure gave it
        self.high_from = np.full(shape, -1, dtype="int32")
        self.high2 = np.full(shape, -np.inf)                 # second highest
        self.low = np.full(shape, np.inf)
        self.low_from = np.full(shape, -1, dtype="int32")
        self.low2 = np.full(shape, np.inf)

    def add(self, data: np.ndarray, saturated: np.ndarray, weight: float, lost: np.ndarray | None = None) -> None:
        i = len(self.weights)
        self.weights.append(float(weight))
        ok = np.isfinite(data)
        self.sum_w += float(weight) * ok
        self.sum_wv += float(weight) * np.where(ok, data, 0.0)
        self.count += ok
        self.overflowed += saturated
        if lost is not None:
            self.lost += lost
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
            nearby = maximum_filter(np.where(np.isfinite(self.high2), np.abs(self.high2), 0.0),
                                    size=GLITCH_NEARBY_PX)
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
                "saturated": ~np.isfinite(mean) & (self.overflowed > 0),
                # In at least one exposure the value here came from a pixel saturated or
                # bloom-flagged by the photometry rule (it is in the picture all the same).
                "lost": self.lost > 0}


def stack(items: list[dict]) -> dict:
    """Weighted mean of resampled exposures (what prepare_cutout returns); see Stacker."""
    stacker = Stacker(items[0]["data"].shape[0])
    for it in items:
        stacker.add(it["data"], it["saturated"], it["weight"], it.get("lost"))
    return stacker.result()


def fit_source(image: np.ndarray, x0: float, y0: float, search: int = 7, half: int = 10) -> dict | None:
    """Centre of the source nearest (x0, y0): a round Gaussian fitted to valid pixels.

    Pixels with no data (a saturated core, for instance) are left out of the fit,
    so a saturated star is located from its unsaturated wings.

    `snr` is the fitted height over the scatter of the pixels around the fit. It is not
    a detection strength: started on empty sky the fit finds the highest noise bump and
    returns 5 or more in up to a quarter of tries. For that, see detection().
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


# How strongly something is detected (detection_sigma). fit_source's `snr` is the fitted
# height over the roughness left around the fit; on empty sky it reaches 5 or more in up
# to a quarter of tries, so it says nothing about detection. Instead one measurement is
# made at the place in question and, in the same way, at many empty places of the same
# frame, and the first is compared with the scatter of the others.
#
# The measurement: the brightness of a star image of fixed width centred exactly on the
# place, fitted together with a constant sky and with every catalogued star near enough
# to send light into the fitted pixels, each at its own catalogue place. Without those
# neighbours, a star 4 to 11 arcsec from WISE 0855 counted as WISE 0855 in detectors 1 to 4
# (up to 60 times the noise, in a simple circle of 6 arcsec radius).
# Width of a star in a stacked frame (FWHM, arcsec): the median over isolated field stars
# of Barnard's Star and WISE 0855, three visits each (spread 0.1 to 0.7 within a frame).
# Wider than the archive's PSF_FWHM because resampling to the 2 arcsec grid adds blur.
STACK_FWHM_ARCSEC = {1: 9.1, 2: 9.0, 3: 9.1, 4: 9.9, 5: 10.0, 6: 10.3}
FORCED_RADIUS_ARCSEC = 2.5 * NATIVE_ARCSEC    # the fit uses the pixels within 15.4 arcsec of the place
NEIGHBOUR_ARCSEC = FORCED_RADIUS_ARCSEC + 10.0  # catalogued stars this close are fitted with it ...
SAME_OBJECT_ARCSEC = 1.5                      # ... unless this close: then they are the object itself
BLANK_STEP_ARCSEC = 12.0                      # empty places lie on a square grid this far apart ...
BLANK_CLEAR_ARCSEC = 3 * NATIVE_ARCSEC        # ... and none is closer than this to a Gaia star or the target
MIN_BLANK_PLACES = 20                         # with fewer the scatter is not known well enough
DETECT_MARGINAL = 3.0                         # detection_sigma from here: "marginal"
DETECT_CLEAR = 5.0                            # and from here: "clear"
GRID_PIXEL_MJY = (GRID_ARCSEC / 206264.806) ** 2 * 1e9   # 1 MJy/sr over one grid pixel, in mJy


def forced_flux(image: np.ndarray, x: float, y: float, fwhm_arcsec: float, others: np.ndarray,
                saturated: np.ndarray | None = None) -> dict | None:
    """Brightness of a point source exactly at (x, y), in mJy, fitted with its known neighbours.

    A round Gaussian of the given width (unit total, so its height is a flux) at (x, y),
    one more at each place in `others` that lies between SAME_OBJECT_ARCSEC and
    NEIGHBOUR_ARCSEC from it, and a constant, fitted by linear least squares to the
    pixels with a value within FORCED_RADIUS_ARCSEC of (x, y). Positions in grid pixels
    from the bottom-left; `others` is an (n, 2) array of x, y. Returns None when the
    place is too near the edge or half of those pixels have no value.

    `variance_factor` is the variance of the flux for unit noise per pixel. It grows when
    a neighbour is close, because the two then share their light; detection() uses it
    to scale the scatter found at empty places.
    """
    radius = FORCED_RADIUS_ARCSEC / GRID_ARCSEC
    half = int(np.ceil(radius)) + 1
    xi, yi = int(round(x)), int(round(y))
    ny, nx = image.shape
    if not (half <= xi < nx - half and half <= yi < ny - half):
        return None
    window = (slice(yi - half, yi + half + 1), slice(xi - half, xi + half + 1))
    win = image[window]
    yy, xx = np.mgrid[yi - half:yi + half + 1, xi - half:xi + half + 1]
    within = np.hypot(xx - x, yy - y) <= radius
    use = within & np.isfinite(win)
    if use.sum() < 0.5 * within.sum():
        return None
    s = fwhm_arcsec / 2.3548 / GRID_ARCSEC
    others = np.asarray(others, dtype=float).reshape(-1, 2)
    d = np.hypot(others[:, 0] - x, others[:, 1] - y)
    near = np.flatnonzero((d > SAME_OBJECT_ARCSEC / GRID_ARCSEC) & (d <= NEIGHBOUR_ARCSEC / GRID_ARCSEC))
    px, py = xx[use], yy[use]
    columns = [np.exp(-((px - cx) ** 2 + (py - cy) ** 2) / (2 * s * s)) / (2 * np.pi * s * s)
               for cx, cy in [(x, y), *others[near].tolist()]]
    # A neighbour whose light hardly reaches the pixels that have a value cannot be
    # fitted (its column is nearly zero) and changes nothing: leave it out.
    peak = columns[0].max()
    reach = [i for i, column in enumerate(columns) if i == 0 or column.max() >= 0.01 * peak]
    a = np.column_stack([*(columns[i] for i in reach), np.ones(px.size)])
    normal = a.T @ a
    if np.linalg.cond(normal) > 1e10:
        return None
    covariance = np.linalg.inv(normal)
    coefficients = covariance @ (a.T @ win[use])
    if not (np.isfinite(coefficients).all() and covariance[0, 0] > 0):
        return None
    return {"value_mjy": float(coefficients[0]) * GRID_PIXEL_MJY, "variance_factor": float(covariance[0, 0]),
            "n_neighbours": len(reach) - 1,
            # Each fitted neighbour's own brightness, by its row in `others`.
            "neighbour_mjy": {int(near[i - 1]): float(coefficients[k]) * GRID_PIXEL_MJY
                              for k, i in enumerate(reach) if i > 0},
            "saturated": bool(saturated is not None and saturated[window][within].any())}


def blank_places(image: np.ndarray, fwhm_arcsec: float, known: np.ndarray) -> list[dict]:
    """forced_flux() at the empty places of one stacked image.

    Places lie on a square grid BLANK_STEP_ARCSEC apart, centred on the picture, wherever
    the fit has room and data, and at least BLANK_CLEAR_ARCSEC from every place in
    `known` (the Gaia stars on the frame's date and the target; (n, 2) grid pixels).
    Known objects further away are fitted with each place exactly as with the target.
    Infrared sources that no catalogue here lists are left to the clipping in
    noise_at_empty_places().
    """
    known = np.asarray(known, dtype=float).reshape(-1, 2)
    ny, nx = image.shape
    margin = int(np.ceil(FORCED_RADIUS_ARCSEC / GRID_ARCSEC)) + 1
    step = BLANK_STEP_ARCSEC / GRID_ARCSEC
    clear = BLANK_CLEAR_ARCSEC / GRID_ARCSEC
    xs = np.arange(margin, nx - margin, step)
    ys = np.arange(margin, ny - margin, step)
    if not xs.size or not ys.size:
        return []
    xs = np.round(xs + (nx - 1 - xs[-1] - xs[0]) / 2.0)
    ys = np.round(ys + (ny - 1 - ys[-1] - ys[0]) / 2.0)
    out = []
    for y in ys:
        for x in xs:
            if known.size and (np.hypot(known[:, 0] - x, known[:, 1] - y) < clear).any():
                continue
            fit = forced_flux(image, float(x), float(y), fwhm_arcsec, known)
            if fit is not None:
                out.append(fit)
    return out


def noise_at_empty_places(image: np.ndarray, fwhm_arcsec: float, known: np.ndarray) -> dict | None:
    """What forced_flux() gives where there is nothing: the yardstick for detection_sigma.

    Each empty place's value is first scaled to the typical variance_factor, then the
    median and scatter (1.4826 times the median absolute deviation) are taken, setting
    aside places more than 3 times the scatter from the median (sources that no
    catalogue here lists) until that no longer changes. None if fewer than
    MIN_BLANK_PLACES remain.
    """
    blanks = blank_places(image, fwhm_arcsec, known)
    if len(blanks) < MIN_BLANK_PLACES:
        return None
    factors = np.array([b["variance_factor"] for b in blanks])
    reference = float(np.median(factors))
    z = np.array([b["value_mjy"] for b in blanks]) * np.sqrt(reference / factors)
    keep = np.ones(z.size, dtype=bool)
    median = scatter = 0.0
    for _ in range(20):
        median = float(np.median(z[keep]))
        scatter = 1.4826 * float(np.median(np.abs(z[keep] - median)))
        again = np.abs(z - median) <= 3.0 * scatter
        if again.sum() < MIN_BLANK_PLACES or (again == keep).all():
            break
        keep = again
    if keep.sum() < MIN_BLANK_PLACES or scatter <= 0:
        return None
    return {"median_mjy": median, "scatter_mjy": scatter, "variance_factor": reference, "values": z,
            "n_places": int(keep.sum()), "n_set_aside": int((~keep).sum())}


def detection(image: np.ndarray, x: float, y: float, fwhm_arcsec: float, known: np.ndarray,
              noise: dict | None, saturated: np.ndarray | None = None) -> dict:
    """How strongly a source is detected at (x, y): forced_flux() there, against `noise`.

    detection_sigma = (flux - median at the empty places) / the scatter expected at this
    place: the empty places' scatter, scaled up when a neighbour shares the light.
    `n_blank_as_strong` counts the empty places that reach the same detection_sigma.
    `status`: "measured"; "saturated" (pixels near the place have no value because the
    detector overflowed: certainly a bright source, and its flux, fitted to what is
    left, is only a rough lower limit); "no_data" (too near the edge or too few pixels);
    or "no_noise_estimate" (too few empty places in the picture to know the scatter).
    """
    fit = forced_flux(image, x, y, fwhm_arcsec, known, saturated)
    out: dict = {"status": "no_data", "sigma": None, "flux_mjy": None, "noise_mjy": None,
                 "blank_median_mjy": None, "n_blank_places": 0, "n_blank_set_aside": 0, "n_blank_as_strong": None,
                 "n_neighbours_fitted": None, "star_fwhm_arcsec": fwhm_arcsec}
    if fit is None:
        # Too few pixels with a value. If that is because the detector overflowed there
        # (R Draconis in detector 3), a bright source is certainly at the place.
        if saturated is not None:
            yy, xx = np.nonzero(saturated)
            if (np.hypot(xx - x, yy - y) <= FORCED_RADIUS_ARCSEC / GRID_ARCSEC).any():
                out["status"] = "saturated"
        return out
    out.update(status="saturated" if fit["saturated"] else "measured", flux_mjy=fit["value_mjy"],
               n_neighbours_fitted=fit["n_neighbours"])
    if noise is None:
        if out["status"] == "measured":
            out["status"] = "no_noise_estimate"
        return out
    expected = noise["scatter_mjy"] * np.sqrt(fit["variance_factor"] / noise["variance_factor"])
    sigma = (fit["value_mjy"] - noise["median_mjy"]) / expected
    if not np.isfinite(sigma):
        if out["status"] == "measured":
            out["status"] = "no_noise_estimate"
        return out
    strong = (noise["values"] - noise["median_mjy"]) / noise["scatter_mjy"] >= sigma
    out.update(sigma=float(sigma), noise_mjy=float(expected), blank_median_mjy=noise["median_mjy"],
               n_blank_places=noise["n_places"], n_blank_set_aside=noise["n_set_aside"],
               n_blank_as_strong=int(strong.sum()))
    return out


def detection_word(found: dict) -> str:
    """detection_sigma in one word: "clear", "marginal", "none", "saturated" or "unknown"."""
    if found["status"] == "saturated":
        return "saturated"
    if found["sigma"] is None:
        return "unknown"
    return "clear" if found["sigma"] >= DETECT_CLEAR else "marginal" if found["sigma"] >= DETECT_MARGINAL else "none"


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


def gaia_field(ra: float, dec: float, fov: float, *, quick: bool = False) -> tuple[list[dict] | None, str | None]:
    """The Gaia stars (G < 17) around a view, as /api/stars also uses them, or the reason there are none.

    `quick` (few, short tries) is for when the stars only serve as known neighbours: a
    view whose target came with the request can be drawn without them.
    """
    try:
        if quick:
            return astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06, tries=3, timeout=30), None
        return astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06), None
    except spherex.ArchiveError as e:
        return None, str(e)


def nearest_gaia(cone: list[dict], ra: float, dec: float, mjd: float, within_arcsec: float = 15.0) -> dict | None:
    """The Gaia star nearest (ra, dec) on the date, if one is within `within_arcsec`."""
    best = None
    for src in cone:
        sra, sdec = astrometry.position_at(src, mjd)
        sep = float(np.hypot(*astrometry.offset_arcsec(ra, dec, sra, sdec)))
        if sep < within_arcsec and (best is None or sep < best[0]):
            best = (sep, src)
    return best[1] if best else None


def _stars_on_grid(cone: list[dict] | None, mjd: float, grid: WCS, n: int) -> tuple[np.ndarray, list[dict]]:
    """Places of the Gaia stars on the date, as (k, 2) grid pixels from the bottom-left,
    and the stars themselves in the same order; only those near enough to the picture to
    matter for a measurement inside it."""
    if not cone:
        return np.zeros((0, 2)), []
    sra, sdec = astrometry.positions_at(cone, mjd)
    sx, sy = grid.all_world2pix(sra, sdec, 0)
    reach = NEIGHBOUR_ARCSEC / GRID_ARCSEC
    near = (sx > -reach) & (sx < n - 1 + reach) & (sy > -reach) & (sy < n - 1 + reach)
    return np.column_stack([sx[near], sy[near]]), [cone[i] for i in np.flatnonzero(near)]


# A catalogue star closer than one native pixel to the target's predicted place is in the
# same blob of light: the marker then measures both (WISE 0855 in visit 3).
BLEND_ARCSEC = NATIVE_ARCSEC
BLEND_NOTE = (
    "blend lists the Gaia stars (G < 17) within one native pixel (6.15 arcsec) of the predicted position on the "
    "frame's date, nearest first: source_id, gmag, distance_arcsec, east_arcsec, north_arcsec. The target and such a "
    "star are one blob in SPHEREx's pixels, so the marker (centroid.blended) is pulled toward the star and the "
    "light there is partly the star's. flux_mjy is each one's brightness from the same fixed-position fit as "
    "detection_sigma, and light_share its part of the light fitted at the target and the blended stars together "
    "(values below zero count as zero): rough figures, from a fixed star width. Both are null where the target is "
    "saturated, or where a blended star is too close to tell apart (its image and the target's overlap by more than "
    "90 per cent: closer than 2.5 to 2.8 arcsec). Nothing is subtracted from the picture or the measurements.")


def _blend(predicted: dict, stars: list[dict], stars_xy: np.ndarray, image: np.ndarray, fwhm: float,
           found: dict | None, mjd: float, target: dict) -> list[dict]:
    """Gaia stars within BLEND_ARCSEC of the predicted place, with their share of the fitted light.

    A target that is a Gaia star is left out by its identifier, so a companion closer than
    SAME_OBJECT_ARCSEC still counts; a target given by the request's motion has no
    identifier, and a Gaia star that close is taken to be the target itself.
    """
    own_id = target.get("source_id")
    near = astrometry.stars_near(predicted["ra"], predicted["dec"], stars, mjd, BLEND_ARCSEC,
                                 same_arcsec=0.0 if own_id else SAME_OBJECT_ARCSEC, exclude_id=own_id)
    if not near:
        return []
    fit = None
    # Two star images of this width overlap by more than 90 per cent (correlation of the
    # two fitted shapes) when they are closer than this; the fit then cannot share out
    # their light (RW Aurigae's companion, 1.5 arcsec away, came out between -206 and
    # +1131 mJy). Separable: WISE 0855's neighbour at 4.2 to 4.4 arcsec.
    separable = 2.0 * fwhm / 2.3548 * np.sqrt(np.log(1 / 0.9))
    if found is not None and found["status"] == "measured" and all(s["distance_arcsec"] >= separable for s in near):
        n = image.shape[0]
        fit = forced_flux(image, predicted["x"], n - 1 - predicted["y"], fwhm, stars_xy)
    fluxes = (fit or {}).get("neighbour_mjy", {})
    total = max(fit["value_mjy"], 0.0) + sum(max(fluxes.get(s["index"], 0.0), 0.0) for s in near) if fit else 0.0
    out = []
    for s in near:
        flux = fluxes.get(s["index"])
        share = max(flux, 0.0) / total if flux is not None and total > 0 else None
        out.append({**{k: v for k, v in s.items() if k != "index"},
                    "flux_mjy": round(flux, 4) if flux is not None else None,
                    "light_share": round(share, 2) if share is not None else None})
    return out


# When the view has a target, `centroid` is that target measured, or nothing. The old
# way (fit whatever is brightest within 14 arcsec) put the marker on a neighbouring star
# wherever the target itself was invisible: WISE 0855 in detectors 1 to 4.
TARGET_SEARCH_PX = 3              # start from the brightest pixel this close to the predicted place (6 arcsec)
TARGET_MAX_OFFSET_ARCSEC = 3.0    # a source further off than this (or a quarter of its own width) is another object
# The fit's own height over the scatter around it (`snr`). Not a detection strength: used
# only when detection_sigma cannot be worked out (too few empty places in a small picture).
TARGET_MIN_SNR = 4.0
# A star is about 10 arcsec wide here, and up to 30 when it is saturated and fitted from
# its wings (R Draconis). Narrower is a leftover glitch; at 37.7 the fit has run into
# its own limit, which means a slope rather than a source.
TARGET_FWHM_ARCSEC = (6.0, 36.0)
CENTROID_NOTES = {
    "target": ("centroid is the target, measured: it is there only if the target is detected at the predicted "
               f"position (detection_sigma at least {DETECT_MARGINAL:.0f}, or saturated) and a source shaped like a "
               f"star is fitted within {TARGET_MAX_OFFSET_ARCSEC:.0f} arcsec of that position (or a quarter of its "
               "own width, for a saturated star located from its wings). Otherwise it is null and centroid_reason "
               "says why; nearest_source then holds what was found instead, if anything. centroid_offset_arcsec is "
               "centroid minus predicted (east, north, total)."),
    "brightest_near_centre": ("No target is known for this view (no motion in the request and no Gaia star within "
                              "15 arcsec of the centre), so centroid is simply the brightest source within 14 arcsec "
                              "of the centre of the picture, and detection_sigma is measured where it was found "
                              "(which favours it a little, since it was picked for being bright)."),
}
DETECTION_NOTE = (
    "detection_sigma: how strongly the target is detected in this frame, in multiples of the noise. The brightness "
    "of a star image of fixed width (detection_measure.star_fwhm_arcsec) centred exactly on the predicted position is "
    "fitted together with a constant sky and with every Gaia star within 25 arcsec, each held at its own catalogue "
    "place, so a neighbour's light is not counted as the target's. The same fit is made at every empty place of the "
    "frame (a grid 12 arcsec apart, at least 18 arcsec from any Gaia star and from the target); detection_sigma is the "
    "target's value minus their median, divided by their scatter (1.4826 times the median absolute deviation, after "
    "setting aside places more than 3 times that from the median, which hold sources no catalogue here lists), scaled "
    "up when a close neighbour shares the light. detection: 'clear' (5 or more), 'marginal' (3 to 5), 'none' (below "
    "3), 'saturated' (the detector overflowed at the place: certainly detected, no value), 'unknown' (too few empty "
    "places or pixels to say). detection_measure.n_blank_as_strong counts the empty places that reach the same "
    "value: how often this frame shows as much where nothing is catalogued. centroid.snr is the fit's own height over "
    "the scatter left around the fit, kept for compatibility: it is NOT a detection strength (on empty sky it "
    "reaches 5 or more in up to a quarter of tries).")


SATURATION_NOTE = (
    "Two different counts. saturated_pixels: picture pixels with no value in any exposure because the detector "
    "overflowed there (drawn white). photometry_saturated_exposures: how many of the frame's n_exposures have a "
    "saturated pixel inside the 15 arcsec circle in which /api/lightcurve measures the target (or the centre of "
    "the picture, if there is no target), by its stricter rule: overflow within the first seconds, charge spilled "
    "from a saturated neighbour, or no reliable correction. Such pixels usually still hold a value, so the picture "
    "can look fine and show 0 saturated_pixels while no brightness can be measured in those exposures.")


# Position uncertainty of a source whose fitted core holds saturated or bloom-flagged
# pixels. Those pixels are kept on purpose (they draw the star), but they still hold
# numbers that the fit follows: Barnard's Star sits 1.45 arcsec east of Gaia in visit 1
# of detector 5 for that reason, while the fit reports 0.03 to 0.11 arcsec for itself.
# Leaving them out is no better: the unsaturated light alone places the star no better
# than about 1 arcsec in detector 5 and 2 arcsec in detector 2 (docs/verification.md,
# section 4). Those are the figures used, for detectors 5-6 and 1-4.
SATURATED_ERR_ARCSEC = {1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 1.0, 6: 1.0}
ERROR_NOTE = (
    "centroid.err_arcsec is the position uncertainty. For most sources it is the fit's own (err_arcsec_fit). "
    "When saturated_core is true (a pixel within one star width of the fitted centre is saturated or "
    "bloom-flagged in at least one exposure; such pixels stay in the picture and in the fit, so the star is "
    "drawn), err_arcsec is instead about 1 arcsec in detectors 5 and 6 and 2 arcsec in detectors 1 to 4: what an "
    "independent check found for Barnard's Star whichever pixels were used, 10 to 40 times the fit's own figure.")


def _centroid(fit: dict, grid: WCS, n: int, st: dict | None = None, detector: int | None = None) -> dict:
    """A fitted source as the response gives it.

    With the stack (`st`) and detector given, it also says whether the fitted core holds
    saturated or bloom-flagged pixels, and if so err_arcsec is the uncertainty found for
    such stars rather than the fit's own.
    """
    cra, cdec = grid.all_pix2world(fit["x"], fit["y"], 0)
    fwhm_px = fit["sigma_px"] * 2.3548
    err_fit = fit["err_px"] * GRID_ARCSEC if fit["err_px"] is not None else None
    core = False
    if st is not None:
        ny, nx = st["image"].shape
        yy, xx = np.ogrid[0:ny, 0:nx]
        near = np.hypot(xx - fit["x"], yy - fit["y"]) <= fwhm_px
        core = bool((near & (st["saturated"] | st.get("lost", False))).any())
    err = err_fit
    if core and detector is not None:
        err = max(err_fit or 0.0, SATURATED_ERR_ARCSEC[detector])
    return {"ra": float(cra), "dec": float(cdec),
            "x": fit["x"], "y": n - 1 - fit["y"],  # y counted from the top of the PNG
            "err_arcsec": err, "err_arcsec_fit": err_fit, "saturated_core": core,
            "snr": fit["snr"], "fwhm_arcsec": fwhm_px * GRID_ARCSEC}


def _rounded(found: dict) -> dict:
    """detection() as the response gives it: the internal arrays left out, numbers rounded."""
    out = dict(found)
    for key, digits in (("sigma", 2), ("flux_mjy", 5), ("noise_mjy", 5), ("blank_median_mjy", 5)):
        if out.get(key) is not None:
            out[key] = round(float(out[key]), digits)
    return out


def _detected(found: dict, fit: dict) -> tuple[bool, str | None]:
    """Is the target detected at the predicted place? (yes or no, and if no, why not)."""
    word = detection_word(found)
    if word in ("clear", "marginal", "saturated"):
        return True, None
    if word == "none":
        return False, (f"Nothing is detected at the predicted position: {found['sigma']:.1f} times the noise of "
                       f"empty places in this frame ({DETECT_MARGINAL:.0f} is needed).")
    # Not enough empty places or pixels to know the noise: the fit's own S/N decides.
    if fit["snr"] is None or fit["snr"] < TARGET_MIN_SNR:
        return False, (f"Nothing is detected at the predicted position (the fit's own signal to noise is "
                       f"{fit['snr'] or 0:.1f}; {TARGET_MIN_SNR:.0f} is needed; the picture is too small to "
                       "measure the noise at empty places).")
    return True, None


def _measure_target(st: dict, grid: WCS, n: int, detector: int, predicted: dict, found: dict,
                    measure_at) -> tuple[dict | None, dict | None, str | None, dict | None]:
    """The target's measured place and its offset from the predicted one, or why there is
    none: (centroid, offset, reason, nearest other source). `found` is detection() at the
    predicted place; `measure_at(x, y)` gives detection() at another place of the frame."""
    image = st["image"]
    x0, y0 = predicted["x"], n - 1 - predicted["y"]
    # A saturated core leaves no value near the centre, so the second try looks wider
    # and finds the star from its wings; the checks below still apply to what it finds.
    fit = fit_source(image, x0, y0, search=TARGET_SEARCH_PX) or fit_source(image, x0, y0)
    if fit is None:
        return None, None, ("The predicted position is off the picture, too near its edge, or has no data "
                            "around it."), None
    source = _centroid(fit, grid, n, st, detector)
    east, north = astrometry.offset_arcsec(predicted["ra"], predicted["dec"], source["ra"], source["dec"])
    offset = {"east": east, "north": north, "total": float(np.hypot(east, north))}
    narrowest, widest = TARGET_FWHM_ARCSEC
    star_shaped = narrowest <= source["fwhm_arcsec"] <= widest
    too_far = offset["total"] > max(TARGET_MAX_OFFSET_ARCSEC, 0.25 * source["fwhm_arcsec"])
    other = None
    if star_shaped and too_far:
        # What the fit found instead, if it is a detection in its own right.
        there = measure_at(fit["x"], fit["y"])
        if detection_word(there) in ("clear", "marginal", "saturated"):
            other = {**source, "offset_arcsec": offset, "detection_sigma": _rounded(there)["sigma"],
                     "detection": detection_word(there)}
    detected, why_not = _detected(found, fit)
    if not detected:
        if other is not None:
            why_not = (f"{why_not} The nearest source is {offset['total']:.1f} arcsec from the predicted position, "
                       "too far to be the target.")
        return None, None, why_not, other
    if not star_shaped:
        return None, None, (f"What is at the predicted position is not shaped like a star (width "
                            f"{source['fwhm_arcsec']:.0f} arcsec)."), None
    if too_far:
        # Measured on its own only when the target is not detected: otherwise the two
        # would share one blob's light and neither number would mean much.
        return None, None, (f"The nearest source is {offset['total']:.1f} arcsec from the predicted position, "
                            "too far to be the target."), other or {**source, "offset_arcsec": offset,
                                                                    "detection_sigma": None, "detection": None}
    return source, offset, None, None


def _describe(items: list[dict], st: dict, grid: WCS, n: int, target: dict | None,
              cone: list[dict] | None, detector: int) -> dict:
    """Everything reported about one stacked image except where its picture is.

    `cone` holds the Gaia stars around the view (None if Gaia did not answer): they are
    the known neighbours of detection_sigma and are kept off its empty places.
    """
    mjds = np.array([it["mjd"] for it in items])
    weights = np.array([it["weight"] for it in items])
    mjd_mean = float(np.average(mjds, weights=weights))
    waves = [it["wave_at_target"] for it in items if it["wave_at_target"] is not None]
    image = st["image"]
    stars_xy, stars = _stars_on_grid(cone, mjd_mean, grid, n)
    fwhm = STACK_FWHM_ARCSEC[detector]

    predicted = centroid = offset = reason = nearest = None
    found: dict | None = None
    blend: list[dict] = []
    if target:
        pra, pdec = astrometry.position_at(target, mjd_mean)
        px, py = grid.all_world2pix(pra, pdec, 0)
        predicted = {"ra": pra, "dec": pdec, "x": float(px), "y": n - 1 - float(py)}
        here = np.array([[float(px), float(py)]])
        noise = noise_at_empty_places(image, fwhm, np.vstack([stars_xy, here]))
        found = detection(image, float(px), float(py), fwhm, stars_xy, noise, st["saturated"])

        def measure_at(x: float, y: float) -> dict:
            # Anywhere else in the frame the target itself is one of the known neighbours.
            return detection(image, x, y, fwhm, np.vstack([stars_xy, here]), noise, st["saturated"])

        centroid, offset, reason, nearest = _measure_target(st, grid, n, detector, predicted, found, measure_at)
        blend = _blend(predicted, stars, stars_xy, image, fwhm, found, mjd_mean, target)
        if centroid is not None:
            centroid["blended"] = bool(blend)
    else:
        fit = fit_source(image, (n - 1) / 2.0, (n - 1) / 2.0)
        if fit:
            centroid = _centroid(fit, grid, n, st, detector)
            centroid["blended"] = None        # blends are looked for around a target's predicted place only
            here = np.array([[fit["x"], fit["y"]]])
            noise = noise_at_empty_places(image, fwhm, np.vstack([stars_xy, here]))
            found = detection(image, fit["x"], fit["y"], fwhm, stars_xy, noise, st["saturated"])
        else:
            reason = "No source near the centre of the picture is bright enough to measure."
    # In how many of these exposures would /api/lightcurve find the object saturated?
    # Asked where the object is on each exposure's own date (the centre, if there is no target).
    if target:
        t_ra, t_dec = astrometry.path_of(target, mjds)
    else:
        t_ra, t_dec = (np.full(len(items), float(v)) for v in grid.wcs.crval)
    lost = sum(core_saturated(it, float(r), float(d)) for it, r, d in zip(items, t_ra, t_dec, strict=True))
    return {
        "date_start": Time(mjds.min(), format="mjd").iso[:10],
        "date_end": Time(mjds.max(), format="mjd").iso[:10],
        "mjd_mean": mjd_mean,
        "date_mean": Time(mjd_mean, format="mjd").iso[:10],
        "n_exposures": len(items),
        "wavelength_um": [min(waves), max(waves)] if waves else None,
        "flagged_fraction": float(np.mean([it["masked_fraction"] for it in items])),
        "saturated_pixels": int(st["saturated"].sum()),
        "photometry_saturated_exposures": int(lost),
        "rejected_readings": st["rejected_readings"],
        "centroid": centroid,
        "centroid_offset_arcsec": offset,
        "centroid_reason": reason,
        "nearest_source": nearest,
        "predicted": predicted,
        "detection_sigma": _rounded(found)["sigma"] if found else None,
        "detection": detection_word(found) if found else "unknown",
        "detection_measure": ({**_rounded(found), "at": "predicted" if target else "centroid"} if found else None),
        "blend": blend,
    }


def _save(meta_file: Path, meta: dict) -> None:
    """Cache a finished result, but only a complete one.

    If some exposures could not be downloaded, or Gaia did not answer (so no target, no
    predicted positions, or no known neighbours for detection_sigma), the result is
    still returned, with `failures` or `gaia_error` saying so, and the next request
    tries again instead of being served the degraded version for ever.
    """
    if not meta.get("failures") and meta.get("gaia_error") is None:
        spherex.write_json(meta_file, meta, indent=1)


def flags_png(st: dict, path: Path) -> None:
    """Overlay PNG for the flags toggle: blue where there is no data, red where saturated, clear elsewhere."""
    saturated = st["saturated"]
    missing = ~np.isfinite(st["image"]) & ~saturated
    rgba = np.zeros(saturated.shape + (4,), dtype="uint8")
    rgba[missing] = (70, 130, 255, 255)
    rgba[saturated] = (255, 60, 60, 255)
    Image.fromarray(rgba[::-1], "RGBA").save(path)


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
        data, saturated, lost = item.pop("data"), item.pop("saturated"), item.pop("lost")
        if mode != "sum":
            if open_stacker is None or ep != open_epoch:
                if open_stacker is not None:
                    stacks[open_epoch] = open_stacker.result()
                open_epoch, open_stacker = ep, Stacker(n)
            open_stacker.add(data, saturated, item["weight"], lost)
        if total is not None:
            total.add(data, saturated, item["weight"], lost)
        by_epoch.setdefault(ep, []).append(item)
        paths.setdefault(ep, []).append(path)
    if open_stacker is not None:
        stacks[open_epoch] = open_stacker.result()
    if not by_epoch:
        return {"key": key, "frames": [], "failures": failures,
                "message": f"No usable detector {detector} exposures at this position."}

    every = [it for items in by_epoch.values() for it in items]
    mid_mjd = float(np.mean([it["mjd"] for it in every]))
    # The target: with a proper motion in the request (as /api/resolve returns it), the
    # object at the centre with that motion, the only way an object Gaia does not list
    # (WISE 0855) gets a predicted position; otherwise the Gaia star nearest the centre,
    # if one is within 15 arcsec. The Gaia stars of the view are also the known
    # neighbours of detection_sigma and blend, so Gaia is asked in any case, briefly
    # when the request gave a motion.
    cone, gaia_error = gaia_field(ra, dec, fov, quick=motion is not None)
    target = motion
    if motion is None and cone is not None:
        nearest = nearest_gaia(cone, ra, dec, mid_mjd)
        target = {"origin": "gaia_nearest", "ref_epoch": astrometry.GAIA_EPOCH, **nearest} if nearest else None

    def describe(items: list[dict], st: dict) -> dict:
        return _describe(items, st, grid, n, target, cone, detector)

    meta: dict = {
        "key": key, "ra": ra, "dec": dec, "fov": fov, "detector": detector, "mode": mode,
        "size_px": n, "pixel_arcsec": GRID_ARCSEC,
        "target": target, "gaia_error": gaia_error,
        "centroid_is": "target" if target else "brightest_near_centre",
        "centroid_note": CENTROID_NOTES["target" if target else "brightest_near_centre"],
        "detection_note": DETECTION_NOTE,
        "error_note": ERROR_NOTE,
        "blend_note": BLEND_NOTE,
        "saturation_note": SATURATION_NOTE,
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
                        total.add(item.pop("data"), item.pop("saturated"), item["weight"], item.pop("lost"))
                        every.append(item)
            note = ("Exposures were shifted by the target's known proper motion and parallax before "
                    "adding, so the target is sharp and every other object is smeared along its track. "
                    "Sky coordinates in this frame are right for the target only, on the mean date.")
        assert total is not None
        st = total.result()
        limits = stretch_limits([st["image"]])
        name = "sum.png" if track == "sky" else "sum_target.png"
        to_png(st, limits, out_dir / name)
        flags_name = name.replace(".png", "_flags.png")
        flags_png(st, out_dir / flags_name)
        frames.append({"epoch": None, "epochs_combined": [ep + 1 for ep in by_epoch],
                       **describe(every, st), "image": f"/frames/{key}/{name}",
                       "flags_image": f"/frames/{key}/{flags_name}"})
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
            flags_name = f"epoch{ep + 1}_flags.png"
            flags_png(st, out_dir / flags_name)
            frames.append({"epoch": ep + 1, **describe(by_epoch[ep], st),
                           "image": f"/frames/{key}/{name}", "flags_image": f"/frames/{key}/{flags_name}"})
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
                       **describe(by_epoch[ep], stacks[ep]),
                       "image": f"/frames/{key}/{name}",
                       "difference_valid_fraction": float(np.isfinite(diffs[ep]).mean())})
    meta["stretch"] = {"kind": "asinh-symmetric", **diff_limits, "unit": "MJy/sr"}
    meta["note"] = ("Mid-grey is no change, white is brighter than the reference, black is fainter; "
                    "transparent pixels are missing from this epoch or the reference (saturated or no data). "
                    "centroid and predicted are measured on this epoch's ordinary image, not the difference.")
    if reference == "first":
        ref_desc = describe(by_epoch[first], stacks[first])
        meta["reference_frame"] = {"epoch": first + 1, **ref_desc}
    _save(meta_file, meta)
    return meta

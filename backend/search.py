"""Blind search of a SPHEREx field for sources that move or change brightness between visits.

Entry point: `search(ra, dec, fov, detectors)`. It is given a field only, never a
target, and returns plain JSON-ready data: the objects that passed, each with its
evidence and what the catalogues say; the candidates rejected as artefacts, with the
reasons; counts and limits. `scripts/search_fields.py` runs a list of fields
unattended. Results, the recovery test and the false-alarm rate are in docs/search.md.

Underneath: `search_field(ra, dec, fov, detector)` searches one detector;
`search_detectors` runs several and combines what they found into objects.

Method, in the order the code runs
1. Every exposure of the detector is cleaned and resampled exactly as for /api/frames
   (`pipeline.prepare_cutout`), with the same visit ("epoch") numbering, and glitches
   are dropped by the same rule as `pipeline.Stacker` (only a reading that stands
   alone; never one that merely disagrees with the median).
2. Sources are found without any catalogue: peaks of the smoothed stack of all visits,
   and of each visit on its own, that stand 5 times above both the pixel-to-pixel
   scatter of the picture and their own standard error, which comes from the scatter
   between exposures. One glitch in one exposure raises that scatter as much as it
   raises the mean, so it cannot make a source.
3. Empty places: the same measurement is made on a grid of places with nothing on them
   (away from every source, saturated star and glow). Their spread is the noise every
   detection is quoted against ("times the noise", "empty places as bright"). The
   fitting code's own signal to noise is not used as a detection strength.
4. Position: a round Gaussian of the field's own star width is fitted to each source
   in each visit's stack, on a tilted background. Its error is a jackknife over the
   exposures of that visit, steadied across the source's visits; a saturated star gets
   a floor of 1 arcsec (detectors 5, 6) or 2 (1 to 4). The shift common to the field's
   stars is removed. A mover's positions must be inconsistent with standing still AND
   show a net drift, both at 5 sigma, after the errors are scaled so that the field's
   stars as a whole behave like non-movers. It must then be at the place its straight
   line predicts in every visit deep enough to show it, and point-like in each visit.
5. Brightness: aperture photometry on the native pixels of every exposure, after
   /api/lightcurve but with the sky taken just outside the measuring circle; for a star
   saturated in a tenth of its exposures, in detectors 5 and 6, also the ring of
   unsaturated pixels around it, as a separate series. Each exposure sees a source at
   one wavelength, so visits are compared channel by channel (17 channels per
   detector): a two-way layout and its F test. The shift common to the field's stars
   is removed and the test is scaled on them. A changer needs 5 sigma, a change of 10
   per cent (25 for a ring), three quarters of at least 6 shared channels moving one
   way, and must survive leaving out the two exposures that help it most.
6. Sources on the glow of a much brighter star are not tested.
7. Each candidate gets flags (saturated, blended, wide, edge, few_exposures,
   two_visits, follows_roll, one_roll_only, uncalibrated) and a verdict: "rejected"
   (an artefact's signature; `reasons` says which), "caution" or "clean". What passes
   is looked up in Gaia DR3 (with its variability flag and class), SIMBAD, AAVSO VSX,
   CatWISE2020 and AllWISE, with catalogue positions moved to the date of each visit.

Limits
- Nothing is found that is not a peak in a stack: a source must be visible in the sum
  of one visit. Objects that cross the field within a visit (asteroids) are averaged
  away or rejected as glitches, by design.
- A source that moves more than MERGE_ARCSEC between visits is not followed: each of
  its positions is reported as a source that appeared or vanished.
- Saturated stars have no flux: their brightness is the ring measure, detectors 5 and
  6 only, and their position is good to 1 to 2 arcsec.
- The significance is statistical. Two stars closer than the star image act as one
  source whose centre and brightness follow whichever of the two changes; reflections
  of bright stars are caught by the tests above in the cases seen so far, not in every
  conceivable case. Everything that passes must still be looked at.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import threading
import time
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area
from PIL import Image, ImageDraw
from scipy import ndimage, stats
from scipy.ndimage import gaussian_filter, maximum_filter, median_filter
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

from . import astrometry, photometry, pipeline, spherex

VERSION = 2                       # part of the result cache key: raise it when results change
# This module's own cache (results and catalogue answers). "search" holds the answers
# of version 1, made with the old stacking rule; nothing reads it any more.
SEARCH_DIR = spherex.CACHE / "search2"

# Finding sources
SMOOTH_PX = 2.0                   # Gaussian sigma of the detection filter, in 2 arcsec grid pixels
DETECT_SIGMA = 5.0                # a peak must stand this far above the picture's scatter AND its own error
PEAK_WINDOW_PX = 7                # peaks closer than 3 grid pixels (6 arcsec) are one source
BACKGROUND_BOX_PX = 25            # median box (50 arcsec) for the local background under a source
EDGE_PX = 8                       # sources nearer than this to the frame edge (16 arcsec) are not used
MERGE_ARCSEC = 8.0                # peaks of different visits closer than this are the same source
HALO_RATIO = 1.0                  # local background above this multiple of the peak: "on a bright star's glow"
# Same verdict if the wings of much brighter stars put more than this share of the
# source's own flux under the measuring circle. Set equal to MIN_CHANGE: a star image is
# lopsided and turns over with the spacecraft between visits, so the light a bright
# neighbour throws on a faint source can change by its whole amount.
GLOW_SHARE = 0.10
WING_BRIGHTER = 10.0              # a neighbour counts as "much brighter" from this ratio of peaks
WING_REACH_PX = 120               # its wing is followed this far out (240 arcsec)
WING_STARS = 40                   # at most this many of the brightest stars get a wing profile
OPPOSITE_ROLL_DEG = 90.0          # two visits whose detector orientations differ by more than this
BLEND_ARCSEC = 16.0               # a neighbour this close with BLEND_RATIO of the brightness: "blended"
BLEND_RATIO = 0.3
WIDE_RATIO = 1.35                 # wider than a star by this factor: "wide" (an unresolved pair, or a galaxy)
MIN_VISIT_SNR = 4.0               # a visit's position is measured only if the source is this clear in it
EMPTY_SPACING_PX = 6              # empty places are tried on a grid this fine (12 arcsec)
EMPTY_CLEAR_PX = 10               # ... at least this far (20 arcsec) from every source found
EMPTY_MIN_PLACES = 30             # fewer empty places than this: no noise estimate (a crowded or tiny picture)
EMPTY_CLEAR_SATURATED_PX = 30     # ... and this far (60 arcsec) from every saturated pixel
EMPTY_MAX_GLOW = 5.0              # ... and not on a glow brighter than this many times the picture's scatter
SEEN_TIMES_NOISE = 5.0            # "seen in a visit": forced measurement this many times the empty-place spread
# A mover must be at its predicted place in every visit deep enough to show it: a visit
# where the source would stand at least EXPECT_TIMES_NOISE times the noise, but where
# less than MISSING_SHARE of its usual brightness is measured, rejects it. A ghost of a
# bright star (fixed within a visit, elsewhere in the next) fails this; a real mover does not.
EXPECT_TIMES_NOISE = 8.0
MISSING_SHARE = 1.0 / 3.0
# Position error floor for a saturated star, added in quadrature per visit: with its
# core lost it cannot be placed better than about 1 arcsec in detectors 5 and 6 and 2
# arcsec in 1 to 4 (docs/verification.md, section 4, Barnard's Star).
SATURATED_FLOOR_ARCSEC = {1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 1.0, 6: 1.0}
TWO_OUT_SIGMA = 3.0               # a change must stay this clear when its two most helpful exposures are left out

# Positions
FIT_HALF_PX = 6                   # the Gaussian is fitted in a 13 x 13 pixel (26 arcsec) window
FIT_MAX_SHIFT_PX = 4.0            # the fitted centre may not wander further than this (8 arcsec) from the peak
DEFAULT_STAR_WIDTH_PX = 2.3       # Gaussian sigma of a star in the stacks, used when a field has too few stars
MOVER_SIGMA = 5.0
COMBINE_SIGMA = 3.0               # weakest single-detector evidence that counts towards a combined candidate
MIN_REFERENCE_STARS = 8           # fewer than this: no registration and no error scaling for the field

# Brightness
CHANGER_SIGMA = 5.0
MIN_CHANNELS = 6                  # channels two visits must share before they are compared
MIN_CHANGE = 0.10                 # smallest like-with-like change reported (fraction of the brightness)
# Smallest change reported from the ring around a saturated star: twice the largest
# departure the ring showed on Barnard's Star, which does not vary (12 per cent).
MIN_RING_CHANGE = 0.25
RING_MIN_SATURATED = 0.10         # a star saturated in this share of its exposures also gets a ring series
SAME_WAY = 0.75                   # share of the channels two visits have in common that must change the same way
DUPLICATE_ARCSEC = 12.0           # candidates of one kind closer than this are one object
SED_FLOOR = 0.3                   # a channel's reference brightness is at least this share of the median one
FEW_EXPOSURES = 5                 # a visit with fewer exposures than this is flagged
NEAR_SKY_PX = (5.0, 9.0)          # ring (native pixels) for the sky level under a source: 31 to 55 arcsec out
APERTURE_ARCSEC = photometry.APERTURE_PX * 6.15
# Flux in the measuring circle (mJy) of a uniform surface brightness of 1 MJy/sr.
APERTURE_MJY_PER_MJY_SR = math.pi * APERTURE_ARCSEC ** 2 * (math.pi / 648000.0) ** 2 * 1e9

# Catalogue matching
MATCH_ARCSEC = 6.2                # one SPHEREx pixel: a catalogue object this close is "at that place"
CLEAR_ARCSEC = 10.0               # "uncatalogued" needs nothing within this distance
NEIGHBOUR_ARCSEC = 20.0           # catalogue objects are fetched this far around a candidate
CATALOGUE_MARGIN_DEG = 0.1        # fast catalogue objects are looked for this far beyond the frame
GAIA_FAST_MAS_YR = 200.0          # "fast" for the field-wide lists: these can drift into a candidate's cone
SIMBAD_FAST_MAS_YR = 150.0
SERVICE_RETRY_S = 600.0           # a service that failed is not asked again for this long
BRIGHT_STAR_K = 6.0               # 2MASS K magnitude below which a star is listed as "bright, nearby"
BRIGHT_STAR_MARGIN_DEG = 0.3      # ... if it lies within this distance of the frame
GAIA_TAP = astrometry.GAIA_TAP
IRSA_GATOR = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
VSX_API = ("https://vsx.aavso.org/index.php", "https://www.aavso.org/vsx/index.php")
# SIMBAD object types that mean "known to vary" (stars that pulsate, erupt, rotate with spots or
# eclipse; young stars; active galaxies).
# SIMBAD object types that say the object IS a variable star (it is listed as one).
SIMBAD_VARIABLE = frozenset((
    "V*", "Ir*", "Er*", "Ro*", "Pu*", "EB*", "El*", "BY*", "RS*", "CV*", "No*", "SN*", "LP*", "Mi*", "Ce*",
    "cC*", "RR*", "WV*", "RV*", "dS*", "bC*", "gD*", "SX*", "a2*", "Or*", "FU*", "RC*", "Fl*"))
# Kinds of object that commonly vary, without the object being listed as variable:
# young stars, evolved giants, X-ray binaries, active galaxies. A change in one of these
# is reported as "not listed as variable", with its kind named.
SIMBAD_VARYING_KIND = frozenset((
    "TT*", "YSO", "Y*O", "Ae*", "HH", "Be*", "sg*", "s*r", "s*y", "s*b", "C*", "S*", "AB*", "OH*", "pA*", "WR*",
    "XB*", "LXB", "HXB", "Psr", "AGN", "QSO", "Bla", "BLL", "Sy*", "Sy1", "Sy2", "SyG", "LIN"))

OK, SATURATED, FLAGGED, NO_DATA, NO_SKY, OFF_IMAGE = range(6)
_SOURCE_OUTLIER = (1 << pipeline.BIT["SOURCE"]) | (1 << pipeline.BIT["OUTLIER"])

Fetch = Callable[..., list[tuple[dict, Path | None, str | None]]]
Rows = list[dict[str, Any]]


# --------------------------------------------------------------------------- loading

NOT_IN_CACHE = "not in the cache (offline search)"


def cached_only(exposures: list[dict], ra: float, dec: float, size_deg: float,
                progress: Callable[[int, int], None] | None = None) -> list[tuple[dict, Path | None, str | None]]:
    """Like `spherex.fetch_cutouts`, but never downloads: a cutout not on disk is reported missing."""
    out: list[tuple[dict, Path | None, str | None]] = []
    for k, exp in enumerate(exposures, 1):
        path = spherex._cutout_path(exp, ra, dec, size_deg)
        out.append((exp, path, None) if path.exists() else (exp, None, NOT_IN_CACHE))
        if progress:
            progress(k, len(exposures))
    return out


def fetch_to_own_cache(exposures: list[dict], ra: float, dec: float, size_deg: float,
                       progress: Callable[[int, int], None] | None = None
                       ) -> list[tuple[dict, Path | None, str | None]]:
    """Cutouts for a search run that must not add to the shared cutout cache.

    A cutout already in the shared cache is read from there (never changed). Any other
    is read from the public S3 copy of the archive (`s3fetch`) into this module's own
    folder, SEARCH_DIR/cutouts, named the same way. Same arguments and return value as
    `spherex.fetch_cutouts`, so it can be passed to `search` as `fetch`.
    """
    from . import s3fetch  # here, so that the search still imports where s3fetch is absent

    out: dict[int, tuple[dict, Path | None, str | None]] = {}
    missing = []
    for k, exp in enumerate(exposures):
        shared = spherex._cutout_path(exp, ra, dec, size_deg)
        if shared.exists():
            out[k] = (exp, shared, None)
        else:
            missing.append(k)
    if missing:
        got = s3fetch.fetch_cutouts([exposures[k] for k in missing], ra, dec, size_deg, SEARCH_DIR / "cutouts",
                                    progress=progress)
        for k, res in zip(missing, got, strict=True):
            out[k] = res
    return [out[k] for k in range(len(exposures))]


def _exposures(ra: float, dec: float, offline: bool) -> list[dict]:
    """The archive's list of exposures covering (ra, dec); offline, the cached list whatever its age."""
    if not offline:
        return spherex.find_exposures(ra, dec)
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f}".encode()).hexdigest()[:16]
    cache_file = spherex.CACHE / "queries" / f"sia_{key}.json"
    return json.loads(cache_file.read_text()) if cache_file.exists() else []


def _load(ra: float, dec: float, fov: float, detector: int, fetch: Fetch,
          progress: Callable[[int, int], None] | None, offline: bool = False) -> dict[str, Any]:
    """Every exposure of one detector, cleaned and resampled as for /api/frames."""
    exposures = _exposures(ra, dec, offline)
    epoch_of = pipeline.assign_epochs(exposures)
    chosen = [(e, ep) for e, ep in zip(exposures, epoch_of, strict=True) if e["detector"] == detector]
    grid, n = pipeline.make_grid(ra, dec, fov)
    cutout_deg = round(fov * 1.5, 4)      # the detector sits at any angle: fetch the diagonal, as /api/frames does
    fetched = fetch([e for e, _ in chosen], ra, dec, cutout_deg, progress=progress)
    failures = [f"{e['obs_id']} D{e['detector']}: {err}" for e, p, err in fetched if p is None and err != NOT_IN_CACHE]
    not_in_cache = sum(1 for _, p, err in fetched if p is None and err == NOT_IN_CACHE)

    data: list[np.ndarray] = []
    weights: list[float] = []
    mjds: list[float] = []
    epochs: list[int] = []
    paths: list[Path] = []
    meta: list[dict] = []
    saturated: dict[int, np.ndarray] = {}
    for (exp, path, _), (_, ep) in zip(fetched, chosen, strict=True):
        if path is None:
            continue
        item = pipeline.prepare_cutout(path, grid, n, ra, dec)
        if item is None:
            continue
        data.append(item["data"].astype("float32"))
        weights.append(float(item["weight"]))
        mjds.append(float(item["mjd"]))
        epochs.append(ep)
        paths.append(path)
        meta.append(exp)
        saturated[ep] = saturated.get(ep, np.zeros((n, n), dtype=int)) + item["saturated"]
    return {"grid": grid, "n": n, "cube": np.stack(data) if data else np.empty((0, n, n), dtype="float32"),
            "weights": np.array(weights), "mjd": np.array(mjds), "epoch": np.array(epochs, dtype=int),
            "paths": paths, "meta": meta, "failures": failures, "not_in_cache": not_in_cache,
            "saturated": saturated, "n_exposures_all_detectors": len(exposures)}


def _reject_like_stack(cube: np.ndarray, weights: np.ndarray, epoch: np.ndarray) -> int:
    """Blank the readings that `pipeline.Stacker` drops, visit by visit (in place); returns how many.

    The same rule, so the visit pictures here are the ones the viewer shows: at each
    pixel the highest reading is dropped only if it is far above the second highest
    (the lowest, far below the second lowest), and only as part of a small patch. A
    reading that disagrees with the median is NOT dropped: a source with a steep
    spectrum is bright in a minority of a visit's exposures (pipeline.Stacker says why).
    Known cost, inherited: two glitches of different exposures that overlap survive as
    a small ring or bar. The search must not take those for sources; see `_two_out`.
    """
    dropped = 0
    noise_all = 1.0 / np.sqrt(weights)
    for ep in np.unique(epoch):
        sel = np.nonzero(epoch == ep)[0]
        if len(sel) < pipeline.MIN_EXPOSURES_TO_REJECT:
            continue
        sub = cube[sel]
        ok = np.isfinite(sub)
        count = ok.sum(axis=0)
        enough = count >= 3
        up = np.where(ok, sub, -np.inf)
        down = np.where(ok, sub, np.inf)
        high_from, low_from = np.argmax(up, axis=0), np.argmin(down, axis=0)
        ups, downs = np.sort(up, axis=0), np.sort(down, axis=0)
        high, high2, low, low2 = ups[-1], ups[-2], downs[0], downs[1]
        nearby = maximum_filter(np.where(np.isfinite(high2), np.abs(high2), 0.0), size=pipeline.GLITCH_NEARBY_PX)
        noise = noise_all[sel]
        drops: list[tuple[int, np.ndarray]] = []
        with np.errstate(invalid="ignore"):
            for first, second, source, sign in ((high, high2, high_from, 1.0), (low, low2, low_from, -1.0)):
                gap = sign * (first - second)
                limit = pipeline.GLITCH_SIGMA * noise[source] + nearby
                seed = enough & (gap > limit)
                wide = enough & (gap > 0.5 * limit)
                for i in np.unique(source[seed]):
                    patches, _ = ndimage.label(wide & (source == i))
                    sizes = np.bincount(patches.ravel())
                    hit = np.unique(patches[seed & (source == i)])
                    drops.append((int(i), np.isin(patches, hit[sizes[hit] <= pipeline.GLITCH_MAX_PX])))
        for i, drop in drops:
            dropped += int(drop.sum())
            sub[i][drop] = np.nan
        cube[sel] = sub
    return dropped


def _smooth_frame(frame: np.ndarray) -> np.ndarray:
    """One exposure blurred to about the width of a star, ignoring missing pixels."""
    ok = np.isfinite(frame)
    num = gaussian_filter(np.where(ok, frame, 0.0), SMOOTH_PX, mode="constant")
    den = gaussian_filter(ok.astype("float32"), SMOOTH_PX, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0.5, num / den, np.nan)


def _weighted_mean(cube: np.ndarray, weights: np.ndarray, index: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel weighted mean of the chosen exposures (one weight each) and the weight used."""
    n = cube.shape[1]
    num = np.zeros((n, n))
    den = np.zeros((n, n))
    for i in index:
        ok = np.isfinite(cube[i])
        num += np.where(ok, cube[i], 0.0) * weights[i]
        den += ok * weights[i]
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = num / den
    mean[den == 0] = np.nan
    return mean, den


def _background(image: np.ndarray) -> np.ndarray:
    """Local background: a running median that removes stars and keeps wide glows."""
    finite = np.isfinite(image)
    if not finite.any():
        return np.zeros_like(image)
    return median_filter(np.where(finite, image, np.nanmax(image)), size=BACKGROUND_BOX_PX, mode="nearest")


def _robust_sigma(values: np.ndarray) -> float:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def _statistics(field: dict[str, Any]) -> dict[str, Any]:
    """Visit pictures, their smoothed versions and the per-pixel error from exposure scatter."""
    cube, weights, epoch = field["cube"], field["weights"], field["epoch"]
    field["rejected_readings"] = _reject_like_stack(cube, weights, epoch)
    smooth = np.stack([_smooth_frame(frame) for frame in cube]).astype("float32")
    visits = sorted(int(e) for e in np.unique(epoch))
    index = {ep: np.nonzero(epoch == ep)[0] for ep in visits}
    n = field["n"]
    stack: dict[int, np.ndarray] = {}
    sm_mean: dict[int, np.ndarray] = {}
    sm_w: dict[int, np.ndarray] = {}
    resid2 = np.zeros((n, n))
    n_valid = np.zeros((n, n))
    n_groups = np.zeros((n, n))
    for ep in visits:
        stack[ep], _ = _weighted_mean(cube, weights, index[ep])
        sm_mean[ep], sm_w[ep] = _weighted_mean(smooth, weights, index[ep])
        seen = np.zeros((n, n), dtype=bool)
        for i in index[ep]:
            ok = np.isfinite(smooth[i])
            resid2 += np.where(ok, (smooth[i] - sm_mean[ep]) ** 2, 0.0) * weights[i]
            n_valid += ok
            seen |= ok
        n_groups += seen
    # Scatter of single exposures about their own visit's mean, pooled over the visits,
    # in units of each exposure's nominal variance. Pooling lets a visit of three
    # exposures borrow its error from the others.
    dof = n_valid - n_groups
    with np.errstate(invalid="ignore", divide="ignore"):
        phi = np.where(dof >= 6, resid2 / np.maximum(dof, 1), np.nan)
    everything = np.arange(len(cube))
    stack_all, _ = _weighted_mean(cube, weights, everything)
    sm_all, w_all = _weighted_mean(smooth, weights, everything)
    with np.errstate(invalid="ignore", divide="ignore"):
        se_all = np.sqrt(phi / w_all)
        se = {ep: np.sqrt(phi / sm_w[ep]) for ep in visits}
    return {"visits": visits, "index": index, "stack": stack, "stack_all": stack_all,
            "smooth": sm_mean, "smooth_all": sm_all, "se": se, "se_all": se_all}


# --------------------------------------------------------------------------- finding sources

def _peaks(flux: np.ndarray, se: np.ndarray) -> list[tuple[int, int, float, float]]:
    """Local maxima that stand DETECT_SIGMA above the picture's scatter and their own error."""
    n = flux.shape[0]
    sigma_pix = _robust_sigma(flux)
    value = np.where(np.isfinite(flux), flux, -np.inf)
    is_max = value == maximum_filter(value, size=PEAK_WINDOW_PX, mode="constant", cval=-np.inf)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = flux / se
    found = is_max & (value >= DETECT_SIGMA * sigma_pix) & (np.nan_to_num(z) >= DETECT_SIGMA)
    yy, xx = np.nonzero(found)
    keep = (xx >= EDGE_PX) & (xx < n - EDGE_PX) & (yy >= EDGE_PX) & (yy < n - EDGE_PX)
    return [(int(x), int(y), float(flux[y, x]), float(z[y, x])) for x, y in zip(xx[keep], yy[keep], strict=True)]


def _find_sources(st: dict[str, Any]) -> list[dict[str, Any]]:
    """Sources seen in the stack of all visits, plus any seen in one visit's stack only.

    Keeps the detection maps (smoothed picture minus local background) in `st["det"]`
    and `st["det_all"]`: every brightness that is called a detection later is a value
    of these maps, compared with the same value at empty places (`_empty_noise`).
    """
    bg_all = _background(st["smooth_all"])
    st["bg_all"] = bg_all
    st["det_all"] = st["smooth_all"] - bg_all
    st["det"] = {}
    sources: list[dict[str, Any]] = []
    for x, y, peak, z in sorted(_peaks(st["det_all"], st["se_all"]), key=lambda p: -p[2]):
        sources.append({"x": float(x), "y": float(y), "peak": peak, "snr": z, "background": float(bg_all[y, x]),
                        "found_in": "all"})
    reach = MERGE_ARCSEC / pipeline.GRID_ARCSEC
    for ep in st["visits"]:
        bg = _background(st["smooth"][ep])
        st["det"][ep] = st["smooth"][ep] - bg
        found = sorted(_peaks(st["det"][ep], st["se"][ep]), key=lambda p: -p[2])
        if not found:
            continue
        if sources:
            tree = cKDTree(np.array([[s["x"], s["y"]] for s in sources]))
            near, _ = tree.query(np.array([[p[0], p[1]] for p in found]), k=1)
        else:
            near = np.full(len(found), np.inf)
        for (x, y, peak, z), dist in zip(found, near, strict=True):
            if dist > reach:
                sources.append({"x": float(x), "y": float(y), "peak": peak, "snr": z,
                                "background": float(bg[y, x]), "found_in": ep})
    return sources


def _sample(image: np.ndarray, x: float, y: float) -> float:
    """Value of a picture at a point between pixel centres (bilinear); NaN if any neighbour is missing."""
    n_y, n_x = image.shape
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    if not (0 <= x0 < n_x - 1 and 0 <= y0 < n_y - 1):
        return float("nan")
    fx, fy = x - x0, y - y0
    v = image[y0:y0 + 2, x0:x0 + 2]
    return float(v[0, 0] * (1 - fx) * (1 - fy) + v[0, 1] * fx * (1 - fy) + v[1, 0] * (1 - fx) * fy
                 + v[1, 1] * fx * fy)


def _empty_noise(st: dict[str, Any], sources: list[dict[str, Any]], n: int, saturated: np.ndarray) -> None:
    """The noise of every detection map, measured where nothing was found.

    The verification of the project's results showed that a fit's own signal to noise
    is not a detection strength (on empty sky it reaches 5 at a quarter of places). The
    honest test is to make the same measurement at many empty places of the same
    picture and compare. Empty places: a grid every EMPTY_SPACING_PX pixels, at least
    EMPTY_CLEAR_PX from every source found in any visit and away from the edge. Their
    spread includes everything the picture does on empty sky: noise, faint stars below
    the threshold, leftover glitches. Not empty: within EMPTY_CLEAR_SATURATED_PX of a
    saturated pixel, or where the local background stands EMPTY_MAX_GLOW times the
    picture's scatter above zero (the glow of a very bright star, whose own core the
    peak finder cannot list). Stored in st["empty"][ep] (and ["all"]): the
    robust spread and the sorted values, so a measurement can be given as "times the
    noise" and as "how many empty places are as bright".
    """
    # Twice the edge margin of the peak finder: a source it skipped at the edge must not
    # sit under an "empty" place.
    lo, hi = 2 * EDGE_PX, n - 2 * EDGE_PX
    grid = np.arange(lo, hi, EMPTY_SPACING_PX, dtype=float)
    xx, yy = np.meshgrid(grid, grid)
    places = np.column_stack([xx.ravel(), yy.ravel()])
    if sources:
        # Brighter sources have wider wings: the clearance grows by EMPTY_CLEAR_PX for
        # every factor of ten in brightness above 50 times the picture's scatter.
        scatter = _robust_sigma(st["det_all"])
        xy = np.array([[s["x"], s["y"]] for s in sources])
        peaks = np.array([s["peak"] for s in sources], dtype=float)
        reach = EMPTY_CLEAR_PX * (1.0 + np.log10(np.maximum(peaks
                                                            / (50.0 * scatter), 1.0)))
        keep = np.ones(len(places), dtype=bool)
        for k, near in enumerate(cKDTree(xy).query_ball_point(places, float(np.max(reach)))):
            keep[k] = all(math.hypot(*(places[k] - xy[j])) >= reach[j] for j in near)
        places = places[keep]
    sat_y, sat_x = np.nonzero(saturated)
    if sat_x.size:
        dist, _ = cKDTree(np.column_stack([sat_x, sat_y]).astype(float)).query(places, k=1)
        places = places[dist >= EMPTY_CLEAR_SATURATED_PX]
    glow = np.abs(np.array([_sample(st["bg_all"], x, y) for x, y in places]))
    places = places[np.nan_to_num(glow, nan=np.inf) <= EMPTY_MAX_GLOW * _robust_sigma(st["det_all"])]
    st["empty_places"] = places
    st["empty"] = {}
    for key, image in [("all", st["det_all"])] + [(ep, st["det"][ep]) for ep in st["visits"]]:
        values = np.array([_sample(image, x, y) for x, y in places])
        values = np.sort(values[np.isfinite(values)])
        st["empty"][key] = {"sigma": _robust_sigma(values) if values.size >= EMPTY_MIN_PLACES else float("nan"),
                            "values": values}


def _times_noise(st: dict[str, Any], key: Any, x: float, y: float) -> dict[str, Any]:
    """Forced measurement at (x, y) in one detection map, against the same at the empty places."""
    image = st["det_all"] if key == "all" else st["det"][key]
    value = _sample(image, x, y)
    empty = st["empty"][key]
    sigma = empty["sigma"]
    if not (math.isfinite(value) and math.isfinite(sigma) and sigma > 0):
        return {"value": None, "times_noise": None, "empty_as_bright": None, "n_empty": int(empty["values"].size)}
    as_bright = int(empty["values"].size - np.searchsorted(empty["values"], value, side="left"))
    return {"value": value, "times_noise": value / sigma, "empty_as_bright": as_bright,
            "n_empty": int(empty["values"].size)}


# --------------------------------------------------------------------------- positions

def _gauss_fit(image: np.ndarray, x0: float, y0: float, width: float | None) -> dict[str, Any] | None:
    """Round Gaussian fitted to the valid pixels of a small window around (x0, y0).

    With `width` None the width is free and the background is one level: used once per
    source, on the stack of all visits, to learn how wide a star is in this field and
    which sources are wider. With a width given, the Gaussian has exactly that width
    and the background is a tilted plane: a fit of fixed shape cannot swell to cover
    a neighbour, and the tilt takes up the wing of a brighter star next door.

    Missing pixels (a saturated core) are left out, as in `pipeline.fit_source`. Also
    returns what is needed to say how the centre responds to a small change of the
    picture: the pixels used, the model there and the fit's sensitivity matrix.
    """
    ny, nx = image.shape
    xi, yi = int(round(x0)), int(round(y0))
    h = FIT_HALF_PX
    if not (h <= xi < nx - h and h <= yi < ny - h):
        return None
    win = image[yi - h:yi + h + 1, xi - h:xi + h + 1].astype("float64")
    ok = np.isfinite(win)
    if ok.sum() < 0.6 * win.size:
        return None
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
    base = float(np.nanpercentile(win, 15))
    amp = float(np.nanmax(win) - base)
    if amp <= 0:
        return None
    xs, ys, vals = xx[ok].astype("float64"), yy[ok].astype("float64"), win[ok]
    m = FIT_MAX_SHIFT_PX
    start_x, start_y = float(np.clip(x0 - xi, -1, 1)), float(np.clip(y0 - yi, -1, 1))
    if width is None:
        def model(p: np.ndarray) -> np.ndarray:
            return p[0] * np.exp(-((xs - p[1]) ** 2 + (ys - p[2]) ** 2) / (2 * p[3] ** 2)) + p[4]
        start = [amp, start_x, start_y, 2.3, base]
        bounds = ([0, -m, -m, 1.0, -np.inf], [np.inf, m, m, 6.0, np.inf])
    else:
        def model(p: np.ndarray) -> np.ndarray:
            return (p[0] * np.exp(-((xs - p[1]) ** 2 + (ys - p[2]) ** 2) / (2 * width ** 2))
                    + p[3] + p[4] * xs + p[5] * ys)
        start = [amp, start_x, start_y, base, 0.0, 0.0]
        bounds = ([0, -m, -m, -np.inf, -np.inf, -np.inf], [np.inf, m, m, np.inf, np.inf, np.inf])
    try:
        fit = least_squares(lambda p: model(p) - vals, start, bounds=bounds)
    except ValueError:
        return None
    a, mx, my = fit.x[:3]
    if a <= 0 or abs(mx) >= m - 1e-3 or abs(my) >= m - 1e-3:
        return None                        # the centre ran to the edge of what is allowed: no source here
    try:
        sens = np.linalg.inv(fit.jac.T @ fit.jac) @ fit.jac.T      # d(parameters) / d(pixel values)
    except np.linalg.LinAlgError:
        return None
    dof = max(int(ok.sum()) - len(start), 1)
    misfit = float(np.sqrt(2 * fit.cost / dof))
    return {"x": xi + float(mx), "y": yi + float(my), "amplitude": float(a),
            "sigma_px": float(fit.x[3]) if width is None else width,
            "misfit": misfit / float(a),      # scatter of the pixels about the model, as a share of the peak
            "ok": ok, "model": model(fit.x), "sens": sens, "corner": (xi - h, yi - h)}


def _jackknife(fit: dict[str, Any], cube: np.ndarray, weights: np.ndarray,
               index: np.ndarray) -> tuple[float, float, float] | None:
    """Error of a fitted centre from leaving out each exposure of the visit in turn.

    Returns (error in x, error in y, largest shift caused by one exposure), in grid
    pixels. The centre of each leave-one-out picture is found with one linear step
    from the full fit, which is exact for small changes and costs nothing. Fewer than
    three exposures give no error.
    """
    n_exp = len(index)
    if n_exp < 3:
        return None
    h = FIT_HALF_PX
    x0, y0 = fit["corner"]
    win = cube[index, y0:y0 + 2 * h + 1, x0:x0 + 2 * h + 1].astype("float64")
    w = weights[index][:, None, None] * np.isfinite(win)
    values = np.nan_to_num(win) * w
    total, wsum = values.sum(axis=0), w.sum(axis=0)
    steps = np.empty((n_exp, 2))
    for i in range(n_exp):
        with np.errstate(invalid="ignore", divide="ignore"):
            image = (total - values[i]) / (wsum - w[i])
        delta = image[fit["ok"]] - fit["model"]
        delta[~np.isfinite(delta)] = 0.0     # a pixel only this exposure had: nothing to compare
        steps[i] = (fit["sens"] @ delta)[1:3]
    spread = steps - steps.mean(axis=0)
    err = np.sqrt((n_exp - 1) / n_exp * (spread ** 2).sum(axis=0))
    return float(err[0]), float(err[1]), float(np.hypot(steps[:, 0], steps[:, 1]).max())


def _local_level(image: np.ndarray, xi: int, yi: int) -> float:
    """Median of a 50 arcsec box around a pixel: the level a source there stands on."""
    r = BACKGROUND_BOX_PX // 2
    box = image[max(yi - r, 0):yi + r + 1, max(xi - r, 0):xi + r + 1]
    return float(np.nanmedian(box)) if np.isfinite(box).any() else 0.0


def _measure_positions(field: dict[str, Any], st: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    """Fit every source in the stack of all visits and in each visit; store sky positions."""
    grid, weights, cube = field["grid"], field["weights"], field["cube"]

    def picture(s: dict[str, Any]) -> np.ndarray:
        return st["stack_all"] if s["found_in"] == "all" else st["stack"][s["found_in"]]

    # How wide a star is here: the median free width of the clear sources.
    for s in sources:
        free = _gauss_fit(picture(s), s["x"], s["y"], None)
        s["sigma_px"] = free["sigma_px"] if free is not None else None
    widths = [s["sigma_px"] for s in sources if s["sigma_px"] and s["found_in"] == "all"
              and s["snr"] >= 3 * DETECT_SIGMA]
    star_width = float(np.median(widths)) if len(widths) >= 5 else DEFAULT_STAR_WIDTH_PX
    st["star_width_px"] = star_width
    for s in sources:
        whole = _gauss_fit(picture(s), s["x"], s["y"], star_width)
        if whole is not None:
            s["x"], s["y"] = whole["x"], whole["y"]
        s["misfit"] = whole["misfit"] if whole is not None else None
        ra, dec = grid.all_pix2world(s["x"], s["y"], 0)
        s["ra"], s["dec"] = float(ra), float(dec)
        s["visits"] = {}
        xi, yi = int(round(s["x"])), int(round(s["y"]))
        box = (slice(max(yi - 2, 0), yi + 3), slice(max(xi - 2, 0), xi + 3))
        for ep in st["visits"]:
            with np.errstate(invalid="ignore", divide="ignore"):
                snr = (st["smooth"][ep][box] - _local_level(st["smooth"][ep], xi, yi)) / st["se"][ep][box]
            visit_snr = float(np.nanmax(snr)) if np.isfinite(snr).any() else float("nan")
            forced = _times_noise(st, ep, s["x"], s["y"])
            entry: dict[str, Any] = {"snr": visit_snr, "n_exposures": int(len(st["index"][ep])),
                                     "times_noise": forced["times_noise"], "empty_as_bright": forced["empty_as_bright"]}
            s["visits"][ep] = entry
            if not visit_snr >= MIN_VISIT_SNR:
                continue
            fit = _gauss_fit(st["stack"][ep], s["x"], s["y"], star_width)
            if fit is None:
                continue
            fra, fdec = grid.all_pix2world(fit["x"], fit["y"], 0)
            east, north = astrometry.offset_arcsec(s["ra"], s["dec"], float(fra), float(fdec))
            entry.update(east=east, north=north, ra=float(fra), dec=float(fdec), misfit=fit["misfit"],
                         amplitude=fit["amplitude"])
            # Its own width in this visit: a moving source is smeared in the picture of all
            # visits together, but sharp in each visit; a reflection is wide in every visit.
            free = _gauss_fit(st["stack"][ep], fit["x"], fit["y"], None)
            if free is not None:
                entry["width_px"] = free["sigma_px"]
            jk = _jackknife(fit, cube, weights, st["index"][ep])
            if jk is not None:
                # One number for both directions: a star image is round, and two
                # directions together give a steadier estimate than each alone.
                entry.update(jackknife=math.sqrt((jk[0] ** 2 + jk[1] ** 2) / 2.0) * pipeline.GRID_ARCSEC,
                             one_exposure_shift=jk[2] * pipeline.GRID_ARCSEC)
        _settle_errors(s, st["visits"])


def _settle_errors(s: dict[str, Any], visits: list[int]) -> None:
    """Position error of a source in each visit, steadied across its visits.

    A jackknife over few exposures can come out far too small by chance (seen: 0.04
    arcsec from three exposures), and the chi-square test would then take a wobble for
    a motion. So the source's visits are pooled into one error per single exposure, and
    no visit is credited with less than that error divided by the square root of its
    number of exposures. A visit with a position but under three exposures gets
    exactly that, if another visit supplied the pooled value.
    """
    seen = [s["visits"][ep] for ep in visits if "jackknife" in s["visits"][ep]]
    dof = sum(v["n_exposures"] - 1 for v in seen)
    if dof <= 0:
        return
    per_exposure = math.sqrt(sum((v["n_exposures"] - 1) * v["n_exposures"] * v["jackknife"] ** 2 for v in seen) / dof)
    for ep in visits:
        v = s["visits"][ep]
        if "east" not in v:
            continue
        v["err_east"] = v["err_north"] = max(v.get("jackknife", 0.0), per_exposure / math.sqrt(v["n_exposures"]))


def _is_reference(s: dict[str, Any]) -> bool:
    """A plain, clear, unflagged source: used to register the frame and scale the errors."""
    return s["found_in"] == "all" and s["snr"] >= 3 * DETECT_SIGMA and not s["flags"] and "ring_of" not in s


def _register(sources: list[dict[str, Any]], visits: list[int]) -> dict[int, dict[str, float]]:
    """Remove from every source the shift that the field's stars share in each visit."""
    shifts: dict[int, dict[str, float]] = {}
    refs = [s for s in sources if _is_reference(s) and all("err_east" in s["visits"][ep] for ep in visits)]
    for ep in visits:
        if len(refs) < MIN_REFERENCE_STARS:
            shifts[ep] = {"east": 0.0, "north": 0.0, "n_stars": len(refs)}
            continue
        # Each star's offset in this visit from its own mean over the visits.
        de = [s["visits"][ep]["east"] - np.mean([s["visits"][e]["east"] for e in visits]) for s in refs]
        dn = [s["visits"][ep]["north"] - np.mean([s["visits"][e]["north"] for e in visits]) for s in refs]
        shifts[ep] = {"east": float(np.median(de)), "north": float(np.median(dn)), "n_stars": len(refs)}
    for s in sources:
        for ep in visits:
            v = s["visits"][ep]
            if "east" in v:
                v["east"] -= shifts[ep]["east"]
                v["north"] -= shifts[ep]["north"]
    return shifts


def _static_chi2(s: dict[str, Any], visits: list[int]) -> tuple[float, int] | None:
    """Chi-square of "this source did not move" over the visits with a position and an error."""
    used = [s["visits"][ep] for ep in visits if "err_east" in s["visits"][ep]]
    if len(used) < 2:
        return None
    chi2 = 0.0
    for axis, err in (("east", "err_east"), ("north", "err_north")):
        x = np.array([v[axis] for v in used])
        e = np.maximum(np.array([v[err] for v in used]), 1e-3)
        w = 1.0 / e ** 2
        chi2 += float((w * (x - (w * x).sum() / w.sum()) ** 2).sum())
    return chi2, 2 * (len(used) - 1)


def _sigma_from_p(p: float) -> float:
    """Two-sided Gaussian equivalent of a probability."""
    if not p > 0:
        return 40.0
    return float(min(stats.norm.isf(p / 2.0), 40.0))


def _motion(s: dict[str, Any], visits: list[int], mjd_of: dict[int, float], scale: float) -> dict[str, Any]:
    """Straight-line motion through the visit positions, weighted by their errors."""
    used = [ep for ep in visits if "err_east" in s["visits"][ep]]
    t = np.array([(mjd_of[ep] - mjd_of[used[0]]) / 365.25 for ep in used])
    out: dict[str, Any] = {"visits_used": [ep + 1 for ep in used], "span_years": float(t.max() - t.min())}
    for axis, err in (("east", "err_east"), ("north", "err_north")):
        x = np.array([s["visits"][ep][axis] for ep in used])
        e = np.maximum(np.array([s["visits"][ep][err] for ep in used]), 1e-3) * scale
        w = 1.0 / e ** 2
        tm = (w * t).sum() / w.sum()
        stt = (w * (t - tm) ** 2).sum()
        out[f"pm_{axis}"] = float((w * (t - tm) * x).sum() / stt)
        out[f"pm_{axis}_err"] = float(1.0 / np.sqrt(stt))
    out["speed"] = float(math.hypot(out["pm_east"], out["pm_north"]))
    out["speed_err"] = (float(math.hypot(out["pm_east"] * out["pm_east_err"], out["pm_north"] * out["pm_north_err"])
                              / out["speed"]) if out["speed"] > 0 else None)
    out["direction_deg_east_of_north"] = float(math.degrees(math.atan2(out["pm_east"], out["pm_north"])) % 360.0)
    # Where the straight line puts the source in every visit (also those without a
    # position of their own), as offsets from its mean place: what `_mover_presence` checks.
    at: dict[int, tuple[float, float]] = {}
    for ep in visits:
        tv = (mjd_of[ep] - mjd_of[used[0]]) / 365.25
        place = []
        for axis, err in (("east", "err_east"), ("north", "err_north")):
            x = np.array([s["visits"][e][axis] for e in used])
            w = 1.0 / np.maximum(np.array([s["visits"][e][err] for e in used]), 1e-3) ** 2
            tm, xm = (w * t).sum() / w.sum(), (w * x).sum() / w.sum()
            place.append(float(xm + out[f"pm_{axis}"] * (tv - tm)))
        at[ep] = (place[0], place[1])
    out["_at"] = at
    first, last = s["visits"][used[0]], s["visits"][used[-1]]
    out["shift_first_to_last"] = {"east": last["east"] - first["east"], "north": last["north"] - first["north"]}
    out["shift_error_arcsec"] = float(scale * math.sqrt(first["err_east"] ** 2 + first["err_north"] ** 2
                                                        + last["err_east"] ** 2 + last["err_north"] ** 2))
    return out


def _test_movers(sources: list[dict[str, Any]], visits: list[int], mjd_of: dict[int, float],
                 detector: int) -> dict[str, Any]:
    """Significance of motion for every source, with errors scaled on the field's own stars."""
    floor = SATURATED_FLOOR_ARCSEC[detector]
    for s in sources:
        if "saturated" in s["flags"]:
            for ep in visits:
                v = s["visits"][ep]
                if "err_east" in v:
                    v["err_east"], v["err_north"] = math.hypot(v["err_east"], floor), math.hypot(v["err_north"], floor)
    raw = [_static_chi2(s, visits) for s in sources]
    # Scale: the field's plain stars should give chi-squares with the median of the
    # chi-square distribution. If theirs are larger, every error is too small by the
    # square root of the ratio.
    ratios = [r[0] / stats.chi2.median(r[1]) for r, s in zip(raw, sources, strict=True)
              if r is not None and _is_reference(s)]
    scaled = len(ratios) >= MIN_REFERENCE_STARS
    scale = math.sqrt(max(float(np.median(ratios)), 1.0)) if scaled else 1.0
    for r, s in zip(raw, sources, strict=True):
        if r is None:
            s["motion"] = None
            continue
        chi2, dof = r[0] / scale ** 2, r[1]
        m = s["motion"] = _motion(s, visits, mjd_of, scale)
        any_shift = _sigma_from_p(float(stats.chi2.sf(chi2, dof)))
        drift = _sigma_from_p(float(stats.chi2.sf((m["pm_east"] / m["pm_east_err"]) ** 2
                                                  + (m["pm_north"] / m["pm_north_err"]) ** 2, 2)))
        # A mover must drift: its positions must be inconsistent with standing still
        # AND show a net motion over the whole span. A source that steps out and back
        # (visit 2 differs, visits 1 and 3 agree) is what a blend does when the
        # spacecraft, and with it the lopsided star image, turns over between visits.
        m.update(chi2_static=chi2, dof=dof, sigma_any_shift=any_shift, sigma_drift=drift, sigma=min(any_shift, drift))
    return {"error_scale": scale, "n_reference_stars": len(ratios), "errors_scaled": scaled,
            "median_raw_chi2_ratio": float(np.median(ratios)) if ratios else None}


def _mover_presence(s: dict[str, Any], st: dict[str, Any], visits: list[int],
                    registration: dict[int, dict[str, float]]) -> None:
    """Is a moving source at the place its straight line predicts, in every visit?

    A forced measurement at the predicted place in each visit's detection map, against
    the same measurement at the empty places of that map. Fills motion["presence"]
    (one row per visit), "n_visits_seen" and "missing_in": the visits deep enough that
    the source should have stood EXPECT_TIMES_NOISE times the noise, where less than
    MISSING_SHARE of its usual brightness is found. Something that is fixed on the sky
    within a visit and elsewhere in the next (a reflection of a bright star inside the
    telescope) shows up in some visits and is missing from others; a real mover is
    where the line says in all of them.
    """
    m = s["motion"]
    rows: dict[int, dict[str, Any]] = {}
    for ep in visits:
        east, north = m["_at"][ep]
        # Back from the field-registered frame to the picture's own pixels.
        east += registration[ep]["east"]
        north += registration[ep]["north"]
        rows[ep] = _times_noise(st, ep, s["x"] - east / pipeline.GRID_ARCSEC, s["y"] + north / pipeline.GRID_ARCSEC)
    seen = [r["value"] for r in rows.values() if r["times_noise"] is not None and r["times_noise"] >= SEEN_TIMES_NOISE]
    typical = float(np.median(seen)) if seen else None
    missing = []
    for ep, r in rows.items():
        r["expected_times_noise"] = None
        if typical is None or r["value"] is None:
            continue
        r["expected_times_noise"] = typical / st["empty"][ep]["sigma"]
        if r["expected_times_noise"] >= EXPECT_TIMES_NOISE and r["value"] < MISSING_SHARE * typical:
            missing.append(ep)
    m["presence"] = [{"epoch": ep + 1, "times_noise": _round(r["times_noise"], 1),
                      "expected_times_noise": _round(r["expected_times_noise"], 1),
                      "empty_places_as_bright": r["empty_as_bright"], "empty_places": r["n_empty"]}
                     for ep, r in rows.items()]
    m["n_visits_seen"] = len(seen)
    m["missing_in"] = [ep + 1 for ep in missing]


# --------------------------------------------------------------------------- brightness

_SUB = (np.arange(5) + 0.5) / 5 - 0.5
_WIN_Y, _WIN_X = np.mgrid[-3:4, -3:4]


def _aperture_weights(dx: float, dy: float) -> np.ndarray:
    """Share of each pixel of a 7 x 7 window lying within the measuring circle.

    (dx, dy) is the source's offset from the window's central pixel. Each pixel is
    sampled at 5 x 5 points, as `photometry._coverage` does.
    """
    xs = _WIN_X[:, :, None, None] + _SUB[None, None, None, :] - dx
    ys = _WIN_Y[:, :, None, None] + _SUB[None, None, :, None] - dy
    return (np.hypot(xs, ys) < photometry.APERTURE_PX).mean(axis=(2, 3))


def _clipped_sky(values: np.ndarray) -> tuple[float, float, int]:
    """Median and scatter after dropping values more than 3 sigma from the median (other stars)."""
    v = values
    for _ in range(5):
        med, sd = float(np.median(v)), float(v.std())
        keep = np.abs(v - med) <= 3.0 * sd
        if keep.all():
            break
        v = v[keep]
    return float(np.median(v)), float(v.std()), int(v.size)


def _measure_exposure(path: Path, ra: np.ndarray, dec: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                                           np.ndarray, np.ndarray, float]:
    """Aperture flux of every source in one exposure, after `photometry.measure`.

    Same circle, flags and units. Differences: the sky level comes from a ring just
    outside the circle (NEAR_SKY_PX) instead of far out, so the wing of a bright
    neighbour is taken away with the sky; the ring may be cut by the edge of the cutout
    (the search covers the whole frame); and all sources share one file read.
    Returns per source: flux and error (mJy), status code, wavelength (microns) and
    `glow`, the light under the measuring circle that is not the source: how far the
    level just around it stands above the sky level of the whole cutout (mJy). Last,
    the roll of the exposure: position angle of the detector's +y axis, east of north.
    """
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = hdul["FLAGS"].data
        variance = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data
    wcs = WCS(header)
    ny, nx = image.shape
    n_src = len(ra)
    flux = np.full(n_src, np.nan)
    err = np.full(n_src, np.nan)
    status = np.full(n_src, OFF_IMAGE, dtype=int)
    wavelength = np.full(n_src, np.nan)
    glow = np.full(n_src, np.nan)
    px, py = wcs.all_world2pix(ra, dec, 0)
    data = image - zodi
    data[pipeline.impossible_pixels(image, variance)] = np.nan
    empty = ~np.isfinite(data) | ~np.isfinite(variance)
    bad = (flags & photometry.PHOTOMETRY_BAD) != 0
    lost = photometry.saturated_pixels(flags, data)
    sky_clean = ~empty & ((flags & photometry.SKY_BAD) == 0)
    sky_crowded = ~empty & ((flags & (photometry.SKY_BAD & ~_SOURCE_OUTLIER)) == 0)
    to_mjy = float(proj_plane_pixel_area(wcs)) * (np.pi / 180.0) ** 2 * 1e9
    r_in, r_out = NEAR_SKY_PX
    reach = int(math.ceil(r_out))
    usable = sky_clean if sky_clean.sum() >= 200 else sky_crowded
    field_sky = _clipped_sky(data[usable])[0] if usable.sum() >= 200 else float("nan")
    # Which way up the detector is on the sky. It turns by half a circle between
    # visits six months apart, and a lopsided star image turns with it.
    c_ra, c_dec = (float(v) for v in wcs.all_pix2world(nx / 2.0, ny / 2.0, 0))
    u_ra, u_dec = (float(v) for v in wcs.all_pix2world(nx / 2.0, ny / 2.0 + 1.0, 0))
    roll = math.degrees(math.atan2((u_ra - c_ra) * math.cos(math.radians(c_dec)), u_dec - c_dec)) % 360.0
    for k in range(n_src):
        x, y = float(px[k]), float(py[k])
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        xi, yi = int(round(x)), int(round(y))
        if not (4 <= xi < nx - 4 and 4 <= yi < ny - 4):
            continue                                   # the measuring circle is not whole
        wavelength[k] = wave[yi, xi]
        if not np.isfinite(wavelength[k]):
            status[k] = NO_DATA
            continue
        box = (slice(yi - 3, yi + 4), slice(xi - 3, xi + 4))
        cover = _aperture_weights(x - xi, y - yi)
        inside = cover > 0
        if lost[box][inside].any():
            status[k] = SATURATED
            continue
        if bad[box][inside].any():
            status[k] = FLAGGED
            continue
        if empty[box][inside].any():
            status[k] = NO_DATA
            continue
        y0, y1, x0, x1 = max(yi - reach, 0), min(yi + reach + 1, ny), max(xi - reach, 0), min(xi + reach + 1, nx)
        area = (slice(y0, y1), slice(x0, x1))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        r2 = (xx - x) ** 2 + (yy - y) ** 2
        near = _ring_level(data[area], sky_clean[area], sky_crowded[area], r2, r_in, r_out, 50)
        if near is None:
            status[k] = NO_SKY
            continue
        sky, sky_sigma, n_sky = near
        # Only the pixels the circle touches: a blank pixel in a corner of the window
        # (weight zero) must not turn the sum into "no number".
        part = cover[inside]
        total = float((part * (data[box][inside] - sky)).sum())
        var = float((part ** 2 * variance[box][inside]).sum()) + float(part.sum()) ** 2 * sky_sigma ** 2 / n_sky
        flux[k] = total * to_mjy
        err[k] = math.hypot(math.sqrt(var) * to_mjy, photometry.SYSTEMATIC * flux[k])
        status[k] = OK
        glow[k] = (sky - field_sky) * float(cover.sum()) * to_mjy
    return flux, err, status, wavelength, glow, roll


def _ring_level(data: np.ndarray, clean: np.ndarray, crowded: np.ndarray, r2: np.ndarray, inner: float,
                outer: float, least: int) -> tuple[float, float, int] | None:
    """Sky level, its scatter and the pixel count in a ring; None with fewer than `least` usable pixels."""
    ring = (r2 >= inner ** 2) & (r2 < outer ** 2)
    pick = ring & clean
    if pick.sum() < least:
        pick = ring & crowded              # crowded field: keep SOURCE pixels and let the clipping drop the stars
    return _clipped_sky(data[pick]) if pick.sum() >= least else None


def _visit_position(s: dict[str, Any], ep: int) -> tuple[float, float]:
    motion = s.get("motion")
    v = s["visits"].get(ep, {})
    if motion and motion["sigma"] >= 3.0 and "ra" in v:
        return v["ra"], v["dec"]
    return s["ra"], s["dec"]


def _photometry(field: dict[str, Any], sources: list[dict[str, Any]], visits: list[int]) -> dict[str, Any]:
    """Flux of every source in every exposure, at its position in that exposure's visit."""
    n_src, n_exp = len(sources), len(field["paths"])
    flux = np.full((n_src, n_exp), np.nan)
    err = np.full((n_src, n_exp), np.nan)
    status = np.full((n_src, n_exp), OFF_IMAGE, dtype=int)
    wave = np.full((n_src, n_exp), np.nan)
    glow = np.full((n_src, n_exp), np.nan)
    roll = np.full(n_exp, np.nan)
    # A source that clearly moved is measured where it was in each visit, so that its
    # light does not slide out of a fixed circle and pass for a change of brightness.
    where = {}
    for ep in visits:
        spots = [_visit_position(s, ep) for s in sources]
        where[ep] = (np.array([p[0] for p in spots]), np.array([p[1] for p in spots]))
    for j, path in enumerate(field["paths"]):
        ra, dec = where[int(field["epoch"][j])]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flux[:, j], err[:, j], status[:, j], wave[:, j], glow[:, j], roll[j] = _measure_exposure(path, ra, dec)
    lo, hi = field["meta"][0]["wave_min"], field["meta"][0]["wave_max"]
    edges = photometry.channel_edges(lo, hi)
    channel = np.clip(np.searchsorted(edges, np.nan_to_num(wave, nan=lo)) - 1, 0, photometry.CHANNELS_PER_DETECTOR - 1)
    return {"flux": flux, "err": err, "status": status, "wave": wave, "channel": channel, "edges": edges,
            "glow": glow, "roll": roll, "measure": ["aperture"] * n_src,
            "aperture_saturated": (status == SATURATED).sum(axis=1)}


def _add_rings(field: dict[str, Any], sources: list[dict[str, Any]], phot: dict[str, Any],
               visits: list[int]) -> None:
    """Give every star saturated in RING_MIN_SATURATED of its exposures a second brightness series: its ring.

    Only in detectors 5 and 6, where the ring is trusted. The ring series is added as a
    source of its own (same place, `measure` "ring", `ring_of` the source it belongs to),
    so the brightness test treats it exactly like a flux: channel by channel, and never
    mixed with the aperture values of the same star, which are a different quantity.
    """
    if int(field["meta"][0]["detector"]) not in photometry.WING_TRUSTED_DETECTORS:
        return
    n_exp = len(field["paths"])
    for i in range(len(sources)):
        if phot["measure"][i] != "aperture" or phot["aperture_saturated"][i] < RING_MIN_SATURATED * n_exp:
            continue
        ring = _ring_brightness(field, sources[i], visits)
        if ring is None:
            continue
        twin = {**sources[i], "ring_of": i, "flags": list(sources[i]["flags"])}
        sources.append(twin)
        for name, row in zip(("flux", "err", "status"), ring, strict=True):
            phot[name] = np.vstack([phot[name], row[None, :]])
        for name in ("wave", "channel", "glow"):
            phot[name] = np.vstack([phot[name], phot[name][i][None, :]])
        phot["measure"].append("ring")
        phot["aperture_saturated"] = np.append(phot["aperture_saturated"], phot["aperture_saturated"][i])


def _ring_brightness(field: dict[str, Any], s: dict[str, Any],
                     visits: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Relative brightness of a saturated star from a ring of unsaturated pixels around it.

    Exactly what /api/lightcurve gives as wing_mjy (`photometry.measure`, one ring per
    star chosen by how often it is usable, never by its values). It is a few per cent
    of the star's light, not a flux, and only comparable with itself at the same
    wavelength: the brightness test compares it channel by channel like a flux. Trusted
    in detectors 5 and 6 only; on Barnard's Star, which does not vary, two values in one
    channel agree to about 5 per cent, 12 at worst (docs/verification.md, section 3).
    """
    points = []
    for j, path in enumerate(field["paths"]):
        ra, dec = _visit_position(s, int(field["epoch"][j]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            points.append(photometry.measure(path, ra, dec))
    choice = photometry._choose_wing_ring(points)
    if choice is None:
        return None
    flux = np.full(len(points), np.nan)
    err = np.full(len(points), np.nan)
    status = np.full(len(points), SATURATED, dtype=int)
    for j, p in enumerate(points):
        wing = p["wings"][choice] if p["wings"] else None
        if wing is not None and wing["status"] == "ok" and wing["value"] is not None:
            flux[j], err[j], status[j] = wing["value"], wing["error"], OK
    s["ring_px_chosen"] = list(photometry.WING_RINGS_PX[choice])
    return flux, err, status


def _mean_angle(degrees: np.ndarray) -> float:
    """Mean direction of a set of angles."""
    rad = np.radians(degrees[np.isfinite(degrees)])
    if rad.size == 0:
        return float("nan")
    return float(np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360.0)


def _angle_between(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _bin_means(phot: dict[str, np.ndarray], bins: np.ndarray, n_bins: int) -> np.ndarray:
    """Mean flux of each source in each (time bin, channel): shape (sources, bins, channels)."""
    n_src = phot["flux"].shape[0]
    n_ch = photometry.CHANNELS_PER_DETECTOR
    total = np.zeros((n_src, n_bins, n_ch))
    count = np.zeros((n_src, n_bins, n_ch))
    src, exp = np.nonzero(phot["status"] == OK)
    np.add.at(total, (src, bins[exp], phot["channel"][src, exp]), phot["flux"][src, exp])
    np.add.at(count, (src, bins[exp], phot["channel"][src, exp]), 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def _visit_effect(y: np.ndarray) -> dict[str, Any] | None:
    """Does brightness depend on the time bin, once each channel's own level is taken out?

    y[bin, channel] is the brightness in units of the source's brightness in that
    channel, NaN where not measured. The model is y = (level of the channel) +
    (effect of the bin): a two-way layout, the textbook analysis of variance. With two
    bins it is exactly a paired t-test over the channels they share; with more bins the
    scatter left over is pooled over all of them, which is what gives it power when
    each bin has only one reading per channel. Returns the F statistic for "no bin has
    an effect", the bin effects and what is needed for the difference of any two bins.
    """
    present = np.isfinite(y)
    cells = present & (present.sum(axis=0) >= 2)[None, :]     # a channel seen in one bin says nothing
    b_idx, c_idx = np.nonzero(cells)
    bins, channels = np.unique(b_idx), np.unique(c_idx)
    if len(bins) < 2:
        return None
    n = len(b_idx)
    design = np.zeros((n, len(channels) + len(bins)))
    design[np.arange(n), np.searchsorted(channels, c_idx)] = 1.0
    design[np.arange(n), len(channels) + np.searchsorted(bins, b_idx)] = 1.0
    values = y[b_idx, c_idx]
    coef, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
    rss_full = float(((values - design @ coef) ** 2).sum())
    level = np.array([values[c_idx == c].mean() for c in channels])
    rss_null = float(((values - level[np.searchsorted(channels, c_idx)]) ** 2).sum())
    d1, d2 = int(rank) - len(channels), n - int(rank)
    if d1 < 1 or d2 < MIN_CHANNELS - 1 or rss_full <= 0:
        return None
    normal = design.T @ design
    pinv = np.linalg.pinv(normal)
    return {"f": ((rss_null - rss_full) / d1) / (rss_full / d2), "d1": d1, "d2": d2, "s2": rss_full / d2,
            "bins": bins, "effects": coef[len(channels):], "pinv": pinv, "project": pinv @ normal,
            "n_channels": len(channels)}


def _bin_difference(fit: dict[str, Any], a: int, b: int) -> tuple[float, float] | None:
    """Effect of bin b minus bin a from a fitted layout, with its standard error; None if not determined."""
    ia, ib = (int(k) for k in np.searchsorted(fit["bins"], [a, b]))
    if ia >= len(fit["bins"]) or ib >= len(fit["bins"]) or fit["bins"][ia] != a or fit["bins"][ib] != b:
        return None
    contrast = np.zeros(fit["pinv"].shape[0])
    contrast[fit["n_channels"] + ia], contrast[fit["n_channels"] + ib] = -1.0, 1.0
    if np.abs(fit["project"] @ contrast - contrast).max() > 1e-6:
        return None                           # the two bins share no channel, even through a third bin
    return float(fit["effects"][ib] - fit["effects"][ia]), float(np.sqrt(fit["s2"] * contrast @ fit["pinv"] @ contrast))


def _test_changers(sources: list[dict[str, Any]], phot: dict[str, np.ndarray], bins: np.ndarray,
                   n_bins: int) -> dict[str, Any]:
    """Like-with-like brightness comparison between time bins, for every source."""
    means = _bin_means(phot, bins, n_bins)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sed = np.nanmean(means, axis=1)                     # brightness per channel, all bins together
        typical = np.nanmedian(sed, axis=1)                 # one number per source
    with np.errstate(invalid="ignore", divide="ignore"):
        scale = np.maximum(sed, SED_FLOOR * typical[:, None])
        relative = means / scale[:, None, :]
    usable = np.isfinite(typical) & (typical > 0)
    reference = np.array([_is_reference(s) for s in sources], dtype=bool)

    # First pass: the brightness shift that the field's plain stars share in each bin
    # (the calibration of one visit against another) is not a property of any of them.
    centred = []
    for i in np.nonzero(usable & reference)[0]:
        fit = _visit_effect(relative[i])
        if fit is not None and len(fit["bins"]) == n_bins and all(
                _bin_difference(fit, 0, b) is not None for b in range(1, n_bins)):
            centred.append(fit["effects"] - fit["effects"].mean())
    shifts_known = len(centred) >= MIN_REFERENCE_STARS
    common = np.median(np.array(centred), axis=0) if shifts_known else np.zeros(n_bins)

    fits: list[dict[str, Any] | None] = [None] * len(sources)
    for i in np.nonzero(usable)[0]:
        fits[i] = _visit_effect(relative[i] - common[:, None])
    # Second pass: the plain stars' F values should have the median of the F
    # distribution. If theirs are larger, the leftover scatter is underestimated for
    # everyone by that ratio.
    ratios = [f["f"] / float(stats.f.median(f["d1"], f["d2"])) for f, ref in zip(fits, reference, strict=True)
              if f is not None and ref]
    scaled = len(ratios) >= MIN_REFERENCE_STARS
    inflate = math.sqrt(max(float(np.median(ratios)), 1.0)) if scaled else 1.0

    pair_scatter: dict[tuple[int, int], list[float]] = {}
    for i, s in enumerate(sources):
        s["changes"] = []
        s["measure"] = phot["measure"][i]
        s["typical_flux_mjy"] = float(typical[i]) if np.isfinite(typical[i]) else None
        s["n_flux"] = int((phot["status"][i] == OK).sum())
        s["n_saturated"] = int(phot["aperture_saturated"][i])
        measured = (phot["status"][i] == OK) & np.isfinite(phot["glow"][i])
        if measured.any() and np.median(phot["flux"][i][measured]) > 0:
            s["background_share"] = float(np.median(phot["glow"][i][measured])
                                          / np.median(phot["flux"][i][measured]))
        else:
            s["background_share"] = None
        wing_mjy = s.get("wing", 0.0) * APERTURE_MJY_PER_MJY_SR
        s["glow_share"] = wing_mjy / typical[i] if usable[i] else None
        fit = fits[i]
        s["change_sigma"], s["best_change"] = None, None
        if fit is None:
            continue
        s["change_sigma"] = _sigma_from_p(float(stats.f.sf(fit["f"] / inflate ** 2, fit["d1"], fit["d2"])))
        for a in range(n_bins):
            for b in range(a + 1, n_bins):
                diff = _bin_difference(fit, a, b)
                both = np.isfinite(means[i, a]) & np.isfinite(means[i, b])
                if diff is None or not both.any():
                    continue
                step = (relative[i, b] - common[b]) - (relative[i, a] - common[a])
                up, down = int((step[both] > 0).sum()), int((step[both] < 0).sum())
                sum_a, sum_b = float(means[i, a][both].sum()), float(means[i, b][both].sum())
                err = diff[1] * inflate
                s["changes"].append({
                    "bins": [a, b], "n_channels": int(both.sum()), "change": diff[0], "change_err": err,
                    "channels_up": up, "channels_down": down,
                    "ratio": sum_b / sum_a if sum_a > 0 and sum_b > 0 else None,
                    "sigma": _sigma_from_p(float(2.0 * stats.t.sf(abs(diff[0]) / err, fit["d2"])))})
                if reference[i]:
                    pair_scatter.setdefault((a, b), []).append(diff[0])
        # The change that is reported: the clearest one between two bins that share
        # enough channels, most of which moved the same way.
        clear = [c for c in s["changes"] if c["n_channels"] >= MIN_CHANNELS
                 and max(c["channels_up"], c["channels_down"]) >= SAME_WAY * c["n_channels"]]
        s["best_change"] = max(clear, key=lambda c: c["sigma"], default=None)
    return {"n_reference_stars": len(ratios), "errors_scaled": scaled, "error_scale": inflate,
            "common_shift_by_bin": [float(c) for c in common], "common_shift_known": shifts_known,
            "pairs": [{"bins": list(k), "n_reference_stars": len(v),
                       "scatter_of_change_among_reference_stars": _robust_sigma(np.array(v))}
                      for k, v in sorted(pair_scatter.items())],
            "_scale": scale, "_common": common, "_inflate": inflate}


def _change_without(i: int, drop: list[int], a: int, b: int, phot: dict[str, Any], bins: np.ndarray, n_bins: int,
                    ctx: dict[str, Any]) -> tuple[float, float] | None:
    """Change of source i between time bins a and b, and its significance, with some exposures left out."""
    ok = phot["status"][i] == OK
    ok[drop] = False
    total = np.zeros((n_bins, photometry.CHANNELS_PER_DETECTOR))
    count = np.zeros_like(total)
    np.add.at(total, (bins[ok], phot["channel"][i][ok]), phot["flux"][i][ok])
    np.add.at(count, (bins[ok], phot["channel"][i][ok]), 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        relative = np.where(count > 0, total / count, np.nan) / ctx["_scale"][i][None, :] - ctx["_common"][:, None]
    fit = _visit_effect(relative)
    diff = _bin_difference(fit, a, b) if fit is not None else None
    if fit is None or diff is None or not diff[1] > 0:
        return None
    err = diff[1] * ctx["_inflate"]
    return diff[0], _sigma_from_p(float(2.0 * stats.t.sf(abs(diff[0]) / err, fit["d2"])))


def _two_out(i: int, best: dict[str, Any], phot: dict[str, Any], bins: np.ndarray, n_bins: int,
             ctx: dict[str, Any]) -> dict[str, Any]:
    """Does a change survive leaving out the two exposures that help it most?

    Two glitches of different exposures that overlap survive the stacking rule, and
    one or two bad readings can make a channel jump. A real change is carried by most
    of the exposures of both time bins. The two exposures whose removal weakens the
    change most are found one at a time and left out; the change must keep its sign
    and stay TWO_OUT_SIGMA clear.
    """
    a, b = best["bins"]
    sign = 1.0 if best["change"] > 0 else -1.0
    members = [int(j) for j in np.nonzero((phot["status"][i] == OK) & ((bins == a) | (bins == b)))[0]]
    dropped: list[int] = []
    after: tuple[float, float] | None = (best["change"], best["sigma"])
    for _ in range(2):
        worst, worst_score, worst_result = None, math.inf, None
        for j in members:
            if j in dropped:
                continue
            res = _change_without(i, dropped + [j], a, b, phot, bins, n_bins, ctx)
            score = -math.inf if res is None else (res[1] if sign * res[0] > 0 else -res[1])
            if score < worst_score:
                worst, worst_score, worst_result = j, score, res
        if worst is None:
            break
        dropped.append(worst)
        after = worst_result
    ok = after is not None and sign * after[0] > 0 and after[1] >= TWO_OUT_SIGMA
    return {"left_out": dropped, "change": _round(after[0], 4) if after else None,
            "sigma": _round(after[1], 1) if after else None, "survives": bool(ok)}


# --------------------------------------------------------------------------- flags

def _wing_light(st: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    """Surface brightness that much brighter stars throw on each source, from their own wings.

    For each of the brightest stars the picture of all visits is averaged in rings
    around it (the median of each ring, so other stars in the ring do not count). A
    source then gets the sum, over the stars at least WING_BRIGHTER times its peak, of
    their ring value at its distance. Measured, not modelled: it works the same for a
    saturated star, whose total brightness is unknown but whose wing is in the picture.
    """
    image = st["smooth_all"]
    n = image.shape[0]
    # A saturated star has no peak to compare (its core is blank): it outshines everything.
    peaks = np.array([np.inf if "saturated" in s["flags"] else s["peak"] for s in sources])
    for s in sources:
        s["wing"] = 0.0
    step = 2.0                                                  # ring width in grid pixels
    n_rings = int(WING_REACH_PX / step)
    outer = slice(2 * n_rings // 3, n_rings)                    # beyond 160 arcsec: taken as plain sky
    for b in np.argsort(-peaks)[:WING_STARS]:
        lit = [s for s in sources if s is not sources[b] and peaks[b] >= WING_BRIGHTER * s["peak"]]
        if not lit:
            continue
        bx, by = sources[b]["x"], sources[b]["y"]
        x0, x1 = max(int(bx) - WING_REACH_PX, 0), min(int(bx) + WING_REACH_PX + 1, n)
        y0, y1 = max(int(by) - WING_REACH_PX, 0), min(int(by) + WING_REACH_PX + 1, n)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        ring = (np.hypot(xx - bx, yy - by) / step).astype(int)
        window = image[y0:y1, x0:x1]
        ok = np.isfinite(window)
        raw = np.full(n_rings, np.nan)
        for k in range(n_rings):
            values = window[ok & (ring == k)]
            if values.size >= 8:
                raw[k] = float(np.median(values))
        if not np.isfinite(raw[outer]).any():
            continue
        # The wing is what stands above the star's own far surroundings by more than
        # their ring-to-ring scatter, and it can only fall with distance: a bump
        # further out is some other star.
        sky, noise = float(np.nanmedian(raw[outer])), _robust_sigma(raw[outer])
        profile = np.where(np.nan_to_num(raw - sky, nan=np.inf) > 3.0 * noise, raw - sky, 0.0)
        profile = np.minimum.accumulate(np.nan_to_num(profile, nan=np.inf))
        profile[~np.isfinite(profile)] = 0.0
        for s in lit:
            k = int(math.hypot(s["x"] - bx, s["y"] - by) / step)
            if 0 < k < n_rings:
                s["wing"] += profile[k]


def _flag_sources(field: dict[str, Any], st: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    """Reasons to distrust a source, decided from the pictures alone."""
    n = field["n"]
    sat_any = np.zeros((n, n), dtype=bool)
    for ep in st["visits"]:
        sat_any |= ~np.isfinite(st["stack"][ep]) & (field["saturated"][ep] > 0)
    typical_width = st["star_width_px"]
    xy = np.array([[s["x"], s["y"]] for s in sources]).reshape(-1, 2)
    peak = np.array([s["peak"] for s in sources])
    tree = cKDTree(xy) if len(sources) else None
    for i, s in enumerate(sources):
        flags: list[str] = []
        xi, yi = int(round(s["x"])), int(round(s["y"]))
        if sat_any[max(yi - 3, 0):yi + 4, max(xi - 3, 0):xi + 4].any():
            flags.append("saturated")
        if s["background"] > HALO_RATIO * s["peak"]:
            flags.append("halo")
        close = tree.query_ball_point(xy[i], BLEND_ARCSEC / pipeline.GRID_ARCSEC) if tree is not None else []
        if any(j != i and peak[j] >= BLEND_RATIO * s["peak"] for j in close):
            flags.append("blended")
        if s.get("sigma_px") and s["sigma_px"] > WIDE_RATIO * typical_width:
            flags.append("wide")              # wider than a star: two sources seen as one, or a galaxy
        if min(s["x"], s["y"], n - 1 - s["x"], n - 1 - s["y"]) < 2 * EDGE_PX:
            flags.append("edge")
        s["flags"] = flags


# --------------------------------------------------------------------------- catalogues

_down: dict[str, float] = {}
_down_lock = threading.Lock()


def _ask(service: str, url: str, params: dict[str, Any], timeout: float = 45.0, tries: int = 3) -> bytes:
    """GET from a catalogue service; one that failed is left alone for a while."""
    with _down_lock:
        if time.time() - _down.get(service, 0.0) < SERVICE_RETRY_S:
            raise spherex.ArchiveError(f"{service} did not answer earlier in this run")
    try:
        return spherex.http_get(url, params, tries=tries, timeout=timeout)
    except spherex.ArchiveError:
        with _down_lock:
            _down[service] = time.time()
        raise


def _cached_query(name: str, key_text: str, run: Callable[[], Rows]) -> Rows:
    """Run a catalogue query once and keep its answer. A failed query is never stored."""
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    cache_file = SEARCH_DIR / "catalogues" / f"{name}_{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    rows = run()
    spherex.write_json(cache_file, rows)
    return rows


def _num(value: Any) -> float | None:
    try:
        if value is None or np.ma.is_masked(value):
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _text(value: Any) -> str | None:
    if value is None or np.ma.is_masked(value):
        return None
    out = str(value).strip()
    return out or None


def _circle(ra: float, dec: float, radius: float, ra_col: str = "ra", dec_col: str = "dec") -> str:
    return f"1=CONTAINS(POINT('ICRS', {ra_col}, {dec_col}), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius:.5f}))"


def _gaia(ra: float, dec: float, radius: float, fast_only: bool) -> Rows:
    """Gaia DR3 sources with motion, variability flag and variability class."""
    query = ("SELECT g.source_id, g.ra, g.dec, g.pmra, g.pmdec, g.parallax, g.phot_g_mean_mag, g.bp_rp, "
             "g.phot_variable_flag, g.ruwe, v.best_class_name "
             "FROM gaiadr3.gaia_source AS g LEFT JOIN gaiadr3.vari_classifier_result AS v "
             f"ON v.source_id = g.source_id WHERE {_circle(ra, dec, radius, 'g.ra', 'g.dec')}"
             + (f" AND g.pm > {GAIA_FAST_MAS_YR}" if fast_only else ""))
    raw = _ask("Gaia DR3", GAIA_TAP, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query},
               timeout=60)
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    rows = []
    for r in table:
        flag = _text(r["phot_variable_flag"])
        cls = _text(r["best_class_name"])
        rows.append({"catalogue": "Gaia DR3", "name": f"Gaia DR3 {r['source_id']}", "ra": float(r["ra"]),
                     "dec": float(r["dec"]), "pmra": _num(r["pmra"]), "pmdec": _num(r["pmdec"]),
                     "parallax": _num(r["parallax"]), "ref_epoch": astrometry.GAIA_EPOCH,
                     "gmag": _num(r["phot_g_mean_mag"]), "bp_rp": _num(r["bp_rp"]), "ruwe": _num(r["ruwe"]),
                     "variable": flag == "VARIABLE" or cls is not None,
                     "type": cls or ("variable (flag)" if flag == "VARIABLE" else None)})
    return rows


def _simbad(ra: float, dec: float, radius: float, fast_only: bool) -> Rows:
    """SIMBAD objects (positions at epoch 2000 with their motion) and their object type."""
    query = ("SELECT main_id, ra, dec, otype, pmra, pmdec, plx_value FROM basic "
             f"WHERE {_circle(ra, dec, radius)}"
             + (f" AND pmra * pmra + pmdec * pmdec > {SIMBAD_FAST_MAS_YR ** 2}" if fast_only else ""))
    data = None
    last: Exception | None = None
    for n, url in enumerate(astrometry.SIMBAD_TAP):
        try:
            raw = _ask(f"SIMBAD mirror {n + 1}", url, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json",
                                                       "QUERY": query}, timeout=30)
            data = json.loads(raw)["data"]
            break
        except (spherex.ArchiveError, ValueError, KeyError) as e:
            last = e
    if data is None:
        raise spherex.ArchiveError(f"SIMBAD did not answer ({last})")
    rows = []
    for main_id, sra, sdec, otype, pmra, pmdec, plx in data:
        if sra is None or sdec is None or otype == "Pl":      # a planet is listed at its star: not a second object
            continue
        rows.append({"catalogue": "SIMBAD", "name": str(main_id), "ra": float(sra), "dec": float(sdec),
                     "pmra": _num(pmra), "pmdec": _num(pmdec), "parallax": _num(plx),
                     "ref_epoch": astrometry.SIMBAD_EPOCH, "type": _text(otype),
                     "variable": _text(otype) in SIMBAD_VARIABLE})
    return rows


def _vsx(ra: float, dec: float, radius: float, fast_only: bool) -> Rows:
    """AAVSO Variable Star Index entries (positions at epoch 2000)."""
    if fast_only:
        return []
    listing = None
    last: Exception | None = None
    for n, url in enumerate(VSX_API):
        try:
            raw = _ask(f"VSX address {n + 1}", url, {"view": "api.list", "ra": f"{ra:.6f}", "dec": f"{dec:.6f}",
                                                     "radius": f"{radius:.5f}", "format": "json"}, timeout=40)
            listing = json.loads(raw)["VSXObjects"]
            break
        except (spherex.ArchiveError, ValueError, KeyError) as e:
            last = e
    if listing is None:
        raise spherex.ArchiveError(f"VSX did not answer ({last})")
    objects = listing.get("VSXObject", []) if isinstance(listing, dict) else []
    rows = []
    for o in objects:
        sra, sdec = _num(o.get("RA2000")), _num(o.get("Declination2000"))
        if sra is None or sdec is None:
            continue
        details = [o.get("VariabilityType") or "type not given"]
        if o.get("Period"):
            details.append(f"period {o['Period']} d")
        if o.get("MaxMag") and o.get("MinMag"):
            details.append(f"{o['MaxMag']} to {o['MinMag']}")
        rows.append({"catalogue": "AAVSO VSX", "name": str(o.get("Name")), "ra": sra, "dec": sdec,
                     "pmra": _num(o.get("ProperMotionRA")), "pmdec": _num(o.get("ProperMotionDec")),
                     "parallax": None, "ref_epoch": 2000.0, "type": ", ".join(details),
                     # VSX also lists suspected and rejected variables; only "Variable" counts.
                     "variable": o.get("Category") == "Variable", "vsx_category": o.get("Category")})
    return rows


def _gator(catalog: str, ra: float, dec: float, radius: float, columns: str, constraints: str | None = None) -> Any:
    """Cone search on an IRSA catalogue through its Gator service; returns an astropy table.

    Gator is used because IRSA's TAP service timed out on these two catalogues on
    2026-11-14, while Gator answered in about a second.
    """
    params = {"catalog": catalog, "spatial": "cone", "objstr": f"{ra:.6f} {dec:.6f}",
              "radius": f"{radius * 3600.0:.2f}", "radunits": "arcsec", "outfmt": 3, "selcols": columns}
    if constraints:
        params["constraints"] = constraints
    raw = _ask("IRSA Gator", IRSA_GATOR, params, timeout=60)
    try:
        return parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    except Exception as e:  # noqa: BLE001 - an error page instead of a table
        raise spherex.ArchiveError(f"IRSA Gator returned no table for {catalog} ({type(e).__name__})") from e


def _catwise(ra: float, dec: float, radius: float, fast_only: bool) -> Rows:
    """CatWISE2020: positions from its motion fit (epoch MJD 57170) with proper motions."""
    # Fast and well measured: more than 0.3 arcsec/yr and five times its own error.
    fast = ("pmra*pmra+pmdec*pmdec>0.09 and pmra*pmra+pmdec*pmdec>25*(sigpmra*sigpmra+sigpmdec*sigpmdec)"
            if fast_only else None)
    table = _gator("catwise_2020", ra, dec, radius,
                   "source_name,ra_pm,dec_pm,pmra,pmdec,sigpmra,sigpmdec,w1mpro_pm,w2mpro_pm", fast)
    rows = []
    for d in table:
        sra, sdec = _num(d["ra_pm"]), _num(d["dec_pm"])
        if sra is None or sdec is None:
            continue
        pmra, pmdec = _num(d["pmra"]), _num(d["pmdec"])
        rows.append({"catalogue": "CatWISE2020", "name": f"CWISE {_text(d['source_name'])}", "ra": sra, "dec": sdec,
                     # arcsec/yr in the catalogue; mas/yr everywhere here
                     "pmra": pmra * 1000.0 if pmra is not None else None,
                     "pmdec": pmdec * 1000.0 if pmdec is not None else None,
                     "pm_err_arcsec_yr": [_num(d["sigpmra"]), _num(d["sigpmdec"])],
                     "parallax": None, "ref_epoch": float(Time(57170.0, format="mjd").jyear),
                     "w1": _num(d["w1mpro_pm"]), "w2": _num(d["w2mpro_pm"]), "type": None, "variable": False})
    return rows


def _allwise(ra: float, dec: float, radius: float, fast_only: bool) -> Rows:
    """AllWISE: position (epoch about 2010.5) and its per-band variability flag."""
    if fast_only:
        return []
    table = _gator("allwise_p3as_psd", ra, dec, radius, "designation,ra,dec,w1mpro,w2mpro,var_flg")
    rows = []
    for d in table:
        sra, sdec = _num(d["ra"]), _num(d["dec"])
        if sra is None or sdec is None:
            continue
        var = _text(d["var_flg"]) or ""
        # One character per band W1..W4, 0 to 9 or "n": the catalogue's own guidance is
        # that 6 and above is a likely variable. W1 and W2 are the bands SPHEREx overlaps.
        likely = any(ch in "6789" for ch in var[:2])
        rows.append({"catalogue": "AllWISE", "name": f"WISEA {_text(d['designation'])}", "ra": sra, "dec": sdec,
                     "pmra": None, "pmdec": None, "parallax": None, "ref_epoch": 2010.5,
                     "w1": _num(d["w1mpro"]), "w2": _num(d["w2mpro"]),
                     "type": f"var_flg {var}" if var else None, "variable": likely})
    return rows


def bright_stars_nearby(ra: float, dec: float, fov: float) -> list[dict[str, Any]] | None:
    """2MASS stars brighter than K = 6 in and around the frame, brightest first; None if 2MASS is silent.

    Not used to find or to reject anything. It is for the person looking at a
    candidate: a very bright star, even outside the frame, throws reflections and a
    wide glow into it, and both turn with the spacecraft.
    """
    radius = round(fov * 0.7072 + BRIGHT_STAR_MARGIN_DEG, 4)

    def run() -> Rows:
        table = _gator("fp_psc", ra, dec, radius, "designation,ra,dec,k_m", f"k_m<{BRIGHT_STAR_K}")
        rows = []
        for d in table:
            east, north = astrometry.offset_arcsec(ra, dec, float(d["ra"]), float(d["dec"]))
            rows.append({"name": f"2MASS J{_text(d['designation'])}", "k_mag": _num(d["k_m"]),
                         "ra": float(d["ra"]), "dec": float(d["dec"]),
                         "from_centre_arcmin": round(math.hypot(east, north) / 60.0, 2),
                         "direction_deg_east_of_north": round(math.degrees(math.atan2(east, north)) % 360.0, 0),
                         "inside_frame": bool(max(abs(east), abs(north)) <= fov * 1800.0)})
        return sorted(rows, key=lambda r: r["k_mag"] if r["k_mag"] is not None else 99.0)

    try:
        return _cached_query("2mass_bright", f"{ra:.5f},{dec:.5f},{radius:.4f},{BRIGHT_STAR_K}", run)
    except Exception:  # noqa: BLE001 - any failure means "2MASS did not answer"
        return None


CATALOGUES: dict[str, Callable[[float, float, float, bool], Rows]] = {
    "Gaia DR3": _gaia, "SIMBAD": _simbad, "AAVSO VSX": _vsx, "CatWISE2020": _catwise, "AllWISE": _allwise}
# What each one can say about variability, for the wording of "not listed as variable in ...".
VARIABILITY_SOURCES = {"Gaia DR3": "Gaia DR3 (variability flag and classifier)", "SIMBAD": "SIMBAD (object type)",
                       "AAVSO VSX": "AAVSO VSX", "AllWISE": "AllWISE (variability flag)"}


def _catalogue_objects(cands: list[dict[str, Any]], ra: float, dec: float, fov: float) -> None:
    """Fetch what the catalogues hold around every candidate, and say which answered.

    Two kinds of query per catalogue: a small cone on each candidate, and one list of
    fast-moving objects over the whole frame and a margin, because a fast object's
    catalogue position (epoch 2000 to 2016) can be arcminutes from where it is now.
    A catalogue counts as having answered for a candidate only if both worked.
    """
    if not cands:
        return
    wide_radius = round(fov * 0.7072 + CATALOGUE_MARGIN_DEG, 4)
    cone = NEIGHBOUR_ARCSEC / 3600.0
    jobs: list[tuple[str, int | None, Callable[[], Rows]]] = []
    for name, fn in CATALOGUES.items():
        tag = name.lower().replace(" ", "_")
        jobs.append((name, None, lambda fn=fn, tag=tag: _cached_query(  # type: ignore[misc]
            tag, f"fast,{ra:.5f},{dec:.5f},{wide_radius:.4f}", lambda: fn(ra, dec, wide_radius, True))))
        for i, c in enumerate(cands):
            reach = round(cone + c.get("track_arcsec", 0.0) / 3600.0, 5)
            jobs.append((name, i, lambda fn=fn, tag=tag, c=c, reach=reach: _cached_query(  # type: ignore[misc]
                tag, f"cone,{c['ra']:.5f},{c['dec']:.5f},{reach:.5f}", lambda: fn(c["ra"], c["dec"], reach, False))))

    def run(job: tuple[str, int | None, Callable[[], Rows]]) -> tuple[str, int | None, Rows | None, str | None]:
        try:
            return job[0], job[1], job[2](), None
        except Exception as e:  # noqa: BLE001 - any failure means "this catalogue did not answer"
            return job[0], job[1], None, f"{type(e).__name__}: {e}"[:300]

    with ThreadPoolExecutor(spherex.MAX_CONCURRENT) as pool:
        done = list(pool.map(run, jobs))
    wide: dict[str, Rows | None] = {name: rows for name, i, rows, _ in done if i is None}
    wide_error = {name: err for name, i, _, err in done if i is None and err}
    for i, c in enumerate(cands):
        objects: Rows = []
        answered: list[str] = []
        failed: dict[str, str] = {}
        for name, j, rows, err in done:
            if j != i:
                continue
            fast = wide[name]
            if rows is None or fast is None:
                failed[name] = err or wide_error.get(name) or "no answer"
                continue
            answered.append(name)
            seen = {o["name"] for o in rows}
            objects.extend(rows)
            objects.extend(o for o in fast if o["name"] not in seen)
        c["_objects"], c["_answered"], c["_failed"] = objects, answered, failed


def _predicted(obj: dict[str, Any], mjd: float) -> tuple[float, float]:
    """Where a catalogue object is on a date, from its own position, motion and parallax."""
    if obj.get("pmra") is None or obj.get("pmdec") is None:
        return obj["ra"], obj["dec"]
    return astrometry.position_at(obj, mjd)


def _check_catalogues(cand: dict[str, Any], mjd_of: dict[int, float]) -> dict[str, Any]:
    """Catalogue objects near a candidate, nearest first, with their distance at each visit."""
    if cand["kind"] == "mover":
        track = [(mjd_of[v["epoch"] - 1], v["ra"], v["dec"]) for v in cand["visits"]
                 if v["epoch"] in cand["motion"]["visits_used"]]
    else:
        track = [(float(np.mean(list(mjd_of.values()))), cand["ra"], cand["dec"])]
    matches = []
    for obj in cand.pop("_objects"):
        seps = []
        for mjd, ra, dec in track:
            pra, pdec = _predicted(obj, mjd)
            seps.append(math.hypot(*astrometry.offset_arcsec(ra, dec, pra, pdec)))
        rms = float(np.sqrt(np.mean(np.square(seps))))
        if rms > NEIGHBOUR_ARCSEC:
            continue
        entry = {k: obj[k] for k in ("catalogue", "name", "type", "variable", "gmag", "w1", "w2", "pmra", "pmdec",
                                     "parallax", "pm_err_arcsec_yr") if obj.get(k) is not None}
        if obj["catalogue"] == "SIMBAD":
            # Decided from the type here, not stored, so that answers kept from earlier runs mean the same.
            entry["variable"] = obj.get("type") in SIMBAD_VARIABLE
            if obj.get("type") in SIMBAD_VARYING_KIND:
                entry["kind_that_varies"] = True
        entry["separation_arcsec"] = round(rms, 2)
        if len(track) >= 2:
            entry["separation_by_visit_arcsec"] = [round(x, 2) for x in seps]
            r0, d0 = _predicted(obj, track[0][0])
            r1, d1 = _predicted(obj, track[-1][0])
            east, north = astrometry.offset_arcsec(r0, d0, r1, d1)
            entry["predicted_shift_first_to_last"] = {"east": round(east, 3), "north": round(north, 3)}
        matches.append(entry)
    matches.sort(key=lambda m: m["separation_arcsec"])
    nearest = matches[0]["separation_arcsec"] if matches else None
    return {"answered": cand.pop("_answered"), "failed": cand.pop("_failed"),
            "match_radius_arcsec": MATCH_ARCSEC, "clear_radius_arcsec": CLEAR_ARCSEC,
            "searched_radius_arcsec": NEIGHBOUR_ARCSEC, "matches": matches[:15], "nearest_arcsec": nearest,
            # "uncatalogued" is only ever said about the catalogues that answered.
            "label": "known" if nearest is not None and nearest <= CLEAR_ARCSEC else "uncatalogued"}


def _describe(m: dict[str, Any]) -> str:
    return f"{m['name']} ({m['catalogue']}" + (f", {m['type']}" if m.get("type") else "") + ")"


def _mover_agreement(cand: dict[str, Any], check: dict[str, Any]) -> None:
    """Does a catalogue object at the candidate's place have the motion that was measured?"""
    shift = cand["motion"]["shift_first_to_last"]
    err = cand["motion"]["shift_error_arcsec"]
    best = None
    for m in check["matches"]:
        pred = m.get("predicted_shift_first_to_last")
        if pred is None or m["separation_arcsec"] > MATCH_ARCSEC:
            continue
        miss = math.hypot(shift["east"] - pred["east"], shift["north"] - pred["north"])
        m["motion_difference_arcsec"] = round(miss, 2)
        # Agreement: the catalogue's shift is within three times the measurement error
        # of the measured one, plus one arcsecond for what blending and the
        # undersampled star image do to a centre. And the catalogue object must itself
        # move at least half as far as was measured: an object that stands still
        # never explains a motion, however generous the tolerance.
        m["motion_agrees"] = bool(miss <= 3.0 * err + 1.0 and math.hypot(pred["east"], pred["north"])
                                  >= 0.5 * math.hypot(shift["east"], shift["north"]))
        if m["motion_agrees"] and best is None:
            best = m
    reached = ", ".join(check["answered"]) or "no catalogue"
    check["counterpart"] = best
    check["agrees"] = best is not None
    if best is not None:
        pred = best["predicted_shift_first_to_last"]
        check["category"] = "known_mover"
        check["summary"] = (f"{_describe(best)}: the catalogue predicts a shift of ({pred['east']:+.2f}, "
                            f"{pred['north']:+.2f}) arcsec east, north between the first and last visit used; "
                            f"measured ({shift['east']:+.2f}, {shift['north']:+.2f}) +/- {err:.2f}.")
    elif check["label"] == "known":
        near = check["matches"][0]
        check["category"] = "mover_motion_not_in_catalogues"
        check["summary"] = (f"No object in {reached} has this motion. Nearest object: {_describe(near)}, "
                            f"{near['separation_arcsec']} arcsec from the measured track, whose catalogue motion "
                            "does not match. Either this source's centre shifted for another reason (a blend), or "
                            "something uncatalogued moved past a catalogued object.")
    else:
        check["category"] = "mover_no_counterpart"
        check["summary"] = f"Nothing within {CLEAR_ARCSEC:.0f} arcsec of the measured track in {reached}."


def _changer_agreement(check: dict[str, Any]) -> None:
    """Is a catalogue object in the measuring circle already listed as variable?"""
    at_place = [m for m in check["matches"] if m["separation_arcsec"] <= MATCH_ARCSEC]
    in_circle = [m for m in check["matches"] if m["separation_arcsec"] <= APERTURE_ARCSEC]
    listed = [m for m in in_circle if m.get("variable")]
    asked = [VARIABILITY_SOURCES[c] for c in check["answered"] if c in VARIABILITY_SOURCES]
    missing = [VARIABILITY_SOURCES[c] for c in check["failed"] if c in VARIABILITY_SOURCES]
    check["variability_sources_checked"] = asked
    check["variability_sources_not_reached"] = missing
    check["agrees"] = bool(listed)
    tail = f" Not reached: {', '.join(missing)}." if missing else ""
    if listed:
        check["counterpart"] = listed[0]
        check["category"] = "known_variable"
        check["summary"] = "Listed as variable: " + "; ".join(
            f"{_describe(m)} at {m['separation_arcsec']} arcsec" for m in listed[:4]) + "." + tail
    elif check["label"] == "known":
        near = at_place[0] if at_place else check["matches"][0]
        check["counterpart"] = near
        check["category"] = "changer_not_listed_as_variable"
        kinds = [m for m in in_circle if m.get("kind_that_varies")]
        kind_note = (" SIMBAD lists " + "; ".join(f"{m['name']} as {m['type']}" for m in kinds[:3])
                     + ", a kind of object that commonly varies." if kinds else "")
        check["summary"] = (f"{_describe(near)} is {near['separation_arcsec']} arcsec away; nothing within the "
                            f"{APERTURE_ARCSEC:.0f} arcsec measuring circle is listed as variable in: "
                            f"{', '.join(asked) or 'any source that answered'}." + kind_note + tail)
    else:
        check["counterpart"] = None
        check["category"] = "changer_no_counterpart"
        check["summary"] = (f"Nothing within {CLEAR_ARCSEC:.0f} arcsec in "
                            f"{', '.join(check['answered']) or 'any catalogue that answered'}, and nothing listed as "
                            f"variable within the {APERTURE_ARCSEC:.0f} arcsec measuring circle." + tail)


def check_catalogues(cands: list[dict[str, Any]], ra: float, dec: float, fov: float,
                     mjd_of: dict[int, float]) -> None:
    """Catalogue check of candidates of one field: fills `catalogue`, `label` and `category` of each."""
    _catalogue_objects(cands, ra, dec, fov)
    for cand in cands:
        check = _check_catalogues(cand, mjd_of)
        if cand["kind"] == "mover":
            _mover_agreement(cand, check)
        else:
            _changer_agreement(check)
        cand["catalogue"], cand["label"], cand["category"] = check, check["label"], check["category"]


# --------------------------------------------------------------------------- candidates

def _round(value: Any, digits: int) -> float | None:
    return None if value is None or not math.isfinite(value) else round(float(value), digits)


def _visit_rows(s: dict[str, Any], visits: list[int], dates: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ep in visits:
        v = s["visits"][ep]
        rows.append({"epoch": ep + 1, "date_mean": dates[ep]["date_mean"], "n_exposures": v["n_exposures"],
                     "snr": _round(v.get("snr"), 1), "times_noise": _round(v.get("times_noise"), 1),
                     "empty_places_as_bright": v.get("empty_as_bright"), "ra": v.get("ra"), "dec": v.get("dec"),
                     "east_arcsec": _round(v.get("east"), 3), "north_arcsec": _round(v.get("north"), 3),
                     "err_east_arcsec": _round(v.get("err_east"), 3), "err_north_arcsec": _round(v.get("err_north"), 3),
                     "largest_shift_from_one_exposure_arcsec": _round(v.get("one_exposure_shift"), 3),
                     "peak_mjy_sr": _round(v.get("amplitude"), 4), "misfit": _round(v.get("misfit"), 3),
                     "fwhm_arcsec": _round(v["width_px"] * 2.3548 * pipeline.GRID_ARCSEC, 1)
                     if "width_px" in v else None})
    return rows


def _channel_table(phot: dict[str, np.ndarray], i: int, bins: np.ndarray, n_bins: int) -> list[dict[str, Any]]:
    """Per-channel flux of one source in each time bin: the numbers behind a change."""
    rows = []
    ok = phot["status"][i] == OK
    for ch in range(photometry.CHANNELS_PER_DETECTOR):
        row: dict[str, Any] = {"channel": ch, "wavelength_um": [round(float(phot["edges"][ch]), 4),
                                                                round(float(phot["edges"][ch + 1]), 4)], "flux_mjy": []}
        for b in range(n_bins):
            sel = ok & (bins == b) & (phot["channel"][i] == ch)
            row["flux_mjy"].append(round(float(phot["flux"][i][sel].mean()), 4) if sel.any() else None)
        rows.append(row)
    return rows


def _time_bins(field: dict[str, Any], visits: list[int], bin_days: float | None) -> tuple[np.ndarray, list[dict]]:
    """Time bin of every exposure: the visit, or pieces of it split at gaps longer than bin_days."""
    mjd, epoch = field["mjd"], field["epoch"]
    bins = np.zeros(len(mjd), dtype=int)
    labels: list[dict[str, Any]] = []
    for ep in visits:
        sel = np.nonzero(epoch == ep)[0]
        order = sel[np.argsort(mjd[sel])]
        part, start = 0, 0
        for k in range(1, len(order) + 1):
            if k == len(order) or (bin_days is not None and mjd[order[k]] - mjd[order[k - 1]] > bin_days):
                members = order[start:k]
                bins[members] = len(labels)
                part += 1
                labels.append({"bin": len(labels), "epoch": ep + 1, "part": part,
                               "date_start": Time(mjd[members].min(), format="mjd").iso[:10],
                               "date_end": Time(mjd[members].max(), format="mjd").iso[:10],
                               "mjd_mean": float(mjd[members].mean()), "n_exposures": int(len(members))})
                start = k
    return bins, labels


def _opposite_roll(change: dict[str, Any], bin_labels: list[dict[str, Any]]) -> bool:
    """Were the two time bins of a change taken with the detector turned over on the sky?"""
    a, b = (bin_labels[k]["roll_deg"] for k in change["bins"])
    return a is not None and b is not None and _angle_between(a, b) > OPPOSITE_ROLL_DEG


def _one_roll_only(s: dict[str, Any], visits: list[int], dates: dict[int, dict[str, Any]]) -> bool:
    """Is the source there in the visits of one spacecraft orientation and missing in the others?

    That is what a reflection of a bright star inside the telescope does (seen: a ring
    30 arcsec across, present in both April visits and absent in both October ones).
    """
    seen = [dates[ep]["roll_deg"] for ep in visits if s["visits"][ep]["snr"] >= MIN_VISIT_SNR]
    missing = [dates[ep]["roll_deg"] for ep in visits if not s["visits"][ep]["snr"] >= MIN_VISIT_SNR]
    if not seen or not missing or any(r is None for r in seen + missing):
        return False
    return (all(_angle_between(r, seen[0]) <= OPPOSITE_ROLL_DEG for r in seen)
            and all(_angle_between(r, seen[0]) > OPPOSITE_ROLL_DEG for r in missing))


def _mover_reasons(s: dict[str, Any], st: dict[str, Any]) -> list[str]:
    """Signatures of an artefact in a mover; empty if it has none."""
    reasons = []
    m = s["motion"]
    if m["missing_in"]:
        rows = {r["epoch"]: r for r in m["presence"]}
        what = "; ".join(f"visit {ep}: {rows[ep]['times_noise']} times the noise where about "
                         f"{rows[ep]['expected_times_noise']:.0f} was expected" for ep in m["missing_in"])
        reasons.append(f"not at the place its motion predicts in a visit deep enough to show it ({what}): "
                       "something fixed within a visit and elsewhere in the next, as a reflection of a bright "
                       "star is")
    if m["n_visits_seen"] < 2 and "saturated" not in s["flags"]:
        reasons.append("clearly seen (5 times the empty-place noise) at its predicted place in fewer than two visits")
    widths = [v["width_px"] for v in s["visits"].values() if "width_px" in v]
    if "saturated" not in s["flags"] and widths and float(np.median(widths)) > WIDE_RATIO * st["star_width_px"]:
        own = float(np.median(widths)) * 2.3548 * pipeline.GRID_ARCSEC
        star = st["star_width_px"] * 2.3548 * pipeline.GRID_ARCSEC
        reasons.append(f"wider than the stars of this field in its own visits ({own:.0f} arcsec across against "
                       f"{star:.0f}): a ring or blob (reflection, galaxy, unresolved pair), not one moving point")
    return reasons


def _drop_duplicates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most significant of candidates of one kind that are the same object.

    A saturated star has a hole where its peak should be, so the peak finder returns
    pieces of its rim as separate sources, each of which then shows the star's motion.
    Two real movers, or two separable changers, within DUPLICATE_ARCSEC do not occur.
    """
    kept: list[dict[str, Any]] = []
    for cand in candidates:                    # already sorted, most significant first
        twin = next((k for k in kept if k["kind"] == cand["kind"] and math.hypot(*astrometry.offset_arcsec(
            k["ra"], k["dec"], cand["ra"], cand["dec"])) <= DUPLICATE_ARCSEC), None)
        if twin is None:
            cand["duplicates_dropped"] = 0
            kept.append(cand)
        else:
            twin["duplicates_dropped"] += 1
    return kept


def _source_row(s: dict[str, Any], visits: list[int]) -> dict[str, Any]:
    """One line per source for the record: enough to see why it was or was not a candidate."""
    motion = s["motion"] or {}
    return {"ra": round(s["ra"], 6), "dec": round(s["dec"], 6), "snr": round(s["snr"], 1),
            "found_in": "all" if s["found_in"] == "all" else s["found_in"] + 1, "flags": s["flags"],
            "measure": s.get("measure", "aperture"),
            "typical_flux_mjy": _round(s["typical_flux_mjy"], 4), "n_flux": s["n_flux"],
            "n_saturated": s["n_saturated"], "glow_share": _round(s["glow_share"], 3),
            "background_share": _round(s["background_share"], 3),
            "motion_sigma": _round(motion.get("sigma"), 2), "pm_east": _round(motion.get("pm_east"), 3),
            "pm_north": _round(motion.get("pm_north"), 3), "speed_err": _round(motion.get("speed_err"), 3),
            "change_sigma": _round(s["change_sigma"], 2),
            "changes": [[c["bins"][0], c["bins"][1], round(c["change"], 4), round(c["change_err"], 4),
                         round(c["sigma"], 2), _round(c["ratio"], 4), c["n_channels"]] for c in s["changes"]],
            "position_err_arcsec": [_round(s["visits"][ep].get("err_east"), 3) for ep in visits]}


def search_field(ra: float, dec: float, fov: float = 0.1, detector: int = 5, *, catalogues: bool = True,
                 bin_days: float | None = None, figures_dir: Path | None = None, use_cache: bool = True,
                 fetch: Fetch | None = None, min_sigma: float | None = None, offline: bool = False,
                 progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Search one field in one detector for movers and changers. No target is given.

    ra, dec, fov in degrees (fov up to 0.5); detector 1 to 6. `bin_days` splits each
    visit at gaps longer than that many days for the brightness test (useful where
    SPHEREx returns often). `figures_dir`: write one small PNG per candidate there.
    `fetch` replaces `spherex.fetch_cutouts` (same arguments and return value) for
    another way of getting the cutouts. `min_sigma` below 5 also returns weaker
    candidates, each marked `passes: false`; `search_detectors` uses that to add up
    the evidence of several detectors. The result is plain data, ready for JSON: the
    keys are described in docs/search.md.
    """
    if not 1 <= detector <= 6:
        raise ValueError("detector must be 1 to 6")
    if not 0.02 < fov <= 0.5:
        raise ValueError("fov must be between 0.02 and 0.5 degrees")
    mover_bar = min(MOVER_SIGMA, min_sigma) if min_sigma is not None else MOVER_SIGMA
    changer_bar = min(CHANGER_SIGMA, min_sigma) if min_sigma is not None else CHANGER_SIGMA
    key_text = f"v{VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{detector},{bin_days},{catalogues},{min_sigma},{offline}"
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    cache_file = SEARCH_DIR / "results" / f"{key}.json"
    if use_cache and figures_dir is None and cache_file.exists():
        return json.loads(cache_file.read_text())

    started = time.time()
    field = _load(ra, dec, fov, detector, fetch or (cached_only if offline else spherex.fetch_cutouts), progress,
                  offline)
    result: dict[str, Any] = {
        "key": key, "version": VERSION, "ra": ra, "dec": dec, "fov": fov, "detector": detector,
        "failures": field["failures"], "exposures_not_in_cache": field["not_in_cache"], "candidates": [],
        "credit": pipeline.CREDIT + "; SIMBAD (CDS); AAVSO VSX; CatWISE2020 and AllWISE (NASA/IPAC IRSA)"}
    if len(field["paths"]) == 0:
        result["message"] = f"No usable detector {detector} exposures at this position."
        return result
    st = _statistics(field)
    result["n_exposures"] = len(field["paths"])
    result["rejected_readings"] = field["rejected_readings"]
    visits: list[int] = st["visits"]
    mjd_of = {ep: float(np.average(field["mjd"][st["index"][ep]], weights=field["weights"][st["index"][ep]]))
              for ep in visits}
    dates = {ep: {"epoch": ep + 1, "date_mean": Time(mjd_of[ep], format="mjd").iso[:10], "mjd_mean": mjd_of[ep],
                  "date_start": Time(field["mjd"][st["index"][ep]].min(), format="mjd").iso[:10],
                  "date_end": Time(field["mjd"][st["index"][ep]].max(), format="mjd").iso[:10],
                  "n_exposures": int(len(st["index"][ep]))} for ep in visits}
    result["visits"] = [dates[ep] for ep in visits]
    bins, bin_labels = _time_bins(field, visits, bin_days)
    if len(bin_labels) < 2:
        # One visit can still be searched for brightness changes if `bin_days` cuts
        # it into pieces (near the ecliptic poles SPHEREx never leaves for 30 days).
        result["message"] = "Only one visit so far: nothing can be compared yet."
        return result

    sources = _find_sources(st)
    # Saturated as the pictures show it: no value left in a visit's picture, and overflowed there.
    saturated_anywhere = np.zeros((field["n"], field["n"]), dtype=bool)
    for ep, count in field["saturated"].items():
        saturated_anywhere |= ~np.isfinite(st["stack"][ep]) & (count > 0)
    _empty_noise(st, sources, field["n"], saturated_anywhere)
    _measure_positions(field, st, sources)
    _flag_sources(field, st, sources)
    _wing_light(st, sources)
    for s in sources:
        s["motion"] = None
    # A first brightness pass at fixed places says which sources are saturated (the
    # pictures of detectors 5 and 6 show no blank core even where the photometry rule
    # calls the core lost), and saturated stars get a wider position error.
    phot = _photometry(field, sources, visits)
    for i, s in enumerate(sources):
        if phot["aperture_saturated"][i] > 0.5 * len(field["paths"]) and "saturated" not in s["flags"]:
            s["flags"].append("saturated")
        if "saturated" in s["flags"] and "wide" in s["flags"]:
            s["flags"].remove("wide")              # a saturated star is wide because it is saturated
    registration = _register(sources, visits)
    mover_summary = _test_movers(sources, visits, mjd_of, detector)
    for s in sources:
        if s["motion"] is not None:
            _mover_presence(s, st, visits, registration)
    if any(s["motion"] and s["motion"]["sigma"] >= 3.0 for s in sources):
        phot = _photometry(field, sources, visits)     # again, following what moved
    _add_rings(field, sources, phot, visits)
    for label in bin_labels:
        label["roll_deg"] = _round(_mean_angle(phot["roll"][bins == label["bin"]]), 1)
    for ep in visits:
        dates[ep]["roll_deg"] = _round(_mean_angle(phot["roll"][st["index"][ep]]), 1)
    changer_summary = _test_changers(sources, phot, bins, len(bin_labels))
    for s in sources:
        if s["glow_share"] is not None and s["glow_share"] > GLOW_SHARE and "halo" not in s["flags"]:
            s["flags"].append("halo")

    candidates: list[dict[str, Any]] = []
    for i, s in enumerate(sources):
        if "halo" in s["flags"]:
            continue
        kinds = []
        if s["motion"] and s["motion"]["sigma"] >= mover_bar and "ring_of" not in s:
            kinds.append("mover")
        best = s["best_change"]
        least = MIN_RING_CHANGE if s["measure"] == "ring" else MIN_CHANGE
        if best is not None and s["change_sigma"] >= changer_bar and abs(best["change"]) >= least:
            kinds.append("changer")
        for kind in kinds:
            sigma = s["motion"]["sigma"] if kind == "mover" else s["change_sigma"]
            cand: dict[str, Any] = {
                "kind": kind, "source": i, "ra": round(s["ra"], 6), "dec": round(s["dec"], 6), "detector": detector,
                "found_in": "all visits" if s["found_in"] == "all" else f"visit {s['found_in'] + 1}",
                "snr": round(s["snr"], 1), "flags": list(s["flags"]),
                "times_noise_all_visits": _round(_times_noise(st, "all", s["x"], s["y"])["times_noise"], 1),
                "typical_flux_mjy": _round(s["typical_flux_mjy"], 4), "glow_share": _round(s["glow_share"], 3),
                "background_share": _round(s["background_share"], 3),
                "n_exposures_with_flux": s["n_flux"], "n_exposures_saturated": s["n_saturated"],
                "visits": _visit_rows(s, visits, dates)}
            reasons: list[str] = []
            if kind == "mover":
                motion = {k: v for k, v in s["motion"].items() if not k.startswith("_")}
                cand["sigma"] = round(s["motion"]["sigma"], 1)
                cand["motion"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in motion.items()}
                cand["motion"]["shift_first_to_last"] = {k: round(v, 3) for k, v in
                                                         s["motion"]["shift_first_to_last"].items()}
                cand["track_arcsec"] = math.hypot(*s["motion"]["shift_first_to_last"].values())
                cand["brightness_change"] = best
                few = [v["n_exposures"] for v in cand["visits"] if v["epoch"] in cand["motion"]["visits_used"]]
                if len(few) == 2:
                    # Two visits cannot tell a drift from a step out and back.
                    cand["flags"].append("two_visits")
                reasons += _mover_reasons(s, st)
            else:
                cand["sigma"] = round(s["change_sigma"], 1)
                cand["measure"] = s["measure"]
                if s["measure"] == "ring":
                    cand["ring_px"] = s.get("ring_px_chosen")
                cand["change"] = best
                cand["all_changes"] = s["changes"]
                cand["channels"] = _channel_table(phot, i, bins, len(bin_labels))
                cand["motion_sigma"] = round(s["motion"]["sigma"], 1) if s["motion"] else None
                few = [bin_labels[b]["n_exposures"] for b in best["bins"]]
                if _opposite_roll(best, bin_labels) and not any(
                        c["sigma"] >= 3.0 and not _opposite_roll(c, bin_labels) for c in s["changes"]):
                    # Seen only between visits taken with the spacecraft turned over:
                    # a real change, or a neighbour's lopsided glow. Cannot be told apart here.
                    cand["flags"].append("follows_roll")
                cand["two_out"] = _two_out(i, best, phot, bins, len(bin_labels), changer_summary)
                if not cand["two_out"]["survives"]:
                    reasons.append("the change rests on one or two exposures: without the two that carry it most "
                                   f"it is {cand['two_out']['sigma']} sigma")
            if min(few) < FEW_EXPOSURES:
                cand["flags"].append("few_exposures")
            calibrated = mover_summary["errors_scaled"] if kind == "mover" else changer_summary["errors_scaled"]
            if not calibrated:
                # Too few plain stars in this picture to check that the errors are right
                # (their scatter is what scales every error): the sigma is not trustworthy.
                cand["flags"].append("uncalibrated")
            if _one_roll_only(s, visits, dates):
                cand["flags"].append("one_roll_only")
            # Three verdicts. "rejected": it has the signature of a known artefact
            # (`reasons` says which) and is never reported as a candidate. "clean":
            # nothing about the measurement asks for caution. "caution": kept, with its
            # flags, for a person to look at.
            cand["reasons"] = reasons
            cand["grade"] = "rejected" if reasons else ("clean" if not cand["flags"] else "caution")
            cand["passes"] = bool(not reasons and sigma >= (MOVER_SIGMA if kind == "mover" else CHANGER_SIGMA))
            candidates.append(cand)
    for name in ("_scale", "_common", "_inflate"):
        changer_summary.pop(name)
    candidates.sort(key=lambda c: -c["sigma"])
    candidates = _drop_duplicates(candidates)
    for number, cand in enumerate(candidates, 1):
        cand["id"] = f"D{detector}-{number:02d}"
        cand["label"] = cand["category"] = "not checked"
        cand["catalogue"] = {"answered": [], "failed": {}, "matches": [], "summary": None}
    if catalogues:
        # Only what reached 5 sigma here is looked up now; `search_detectors` looks up
        # the weaker ones that several detectors together carry over the bar.
        check_catalogues([c for c in candidates if c["passes"]], ra, dec, fov, mjd_of)
    answered = {name for c in candidates for name in c["catalogue"]["answered"]}
    failed = {name: why for c in candidates for name, why in c["catalogue"]["failed"].items()}

    real = [s for s in sources if "ring_of" not in s]
    testable = [s for s in real if "halo" not in s["flags"]]
    result.update(
        candidates=candidates, time_bins=bin_labels,
        n_sources=len(real), n_sources_on_glow_not_tested=len(real) - len(testable),
        n_ring_series=len(sources) - len(real),
        empty_places={"n": int(len(st["empty_places"])), "spacing_arcsec": EMPTY_SPACING_PX * pipeline.GRID_ARCSEC,
                      "clear_of_sources_arcsec": EMPTY_CLEAR_PX * pipeline.GRID_ARCSEC,
                      "noise_by_visit": {str(k if k == "all" else k + 1): _round(v["sigma"], 6)
                                         for k, v in st["empty"].items()}},
        n_sources_position_tested=sum(1 for s in testable if s["motion"]),
        n_sources_brightness_tested=sum(1 for s in testable if s["changes"]),
        n_sources_saturated=sum(1 for s in testable if "saturated" in s["flags"]),
        registration={str(ep + 1): registration[ep] for ep in visits},
        position_errors=mover_summary, brightness_errors=changer_summary,
        catalogues={"answered": sorted(answered), "failed": failed, "checked": catalogues},
        bright_stars_nearby=bright_stars_nearby(ra, dec, fov) if catalogues else None,
        thresholds={"detect_sigma": DETECT_SIGMA, "mover_sigma": MOVER_SIGMA, "changer_sigma": CHANGER_SIGMA,
                    "min_change": MIN_CHANGE, "min_channels": MIN_CHANNELS, "merge_arcsec": MERGE_ARCSEC,
                    "match_arcsec": MATCH_ARCSEC, "clear_arcsec": CLEAR_ARCSEC},
        sources=[_source_row(s, visits) for s in sources])
    if figures_dir is not None:
        for cand in candidates:
            cand["figure"] = _figure(cand, field, st, bin_labels, figures_dir).name
    result["seconds"] = round(time.time() - started, 1)
    if use_cache and catalogues and not field["failures"] and not failed:
        spherex.write_json(cache_file, result)       # cached only when complete, like the other endpoints
    return result


# --------------------------------------------------------------------------- several detectors

def _fisher(sigmas: list[float]) -> float:
    """Several independent significances as one (Fisher's method on their probabilities)."""
    ps = [max(2.0 * float(stats.norm.sf(s)), 1e-300) for s in sigmas]
    if not ps:
        return 0.0
    return _sigma_from_p(float(stats.chi2.sf(-2.0 * sum(math.log(p) for p in ps), 2 * len(ps))))


def _source_near(result: dict[str, Any], ra: float, dec: float) -> dict[str, Any] | None:
    """The source of one detector's search nearest a position, if within one pixel of it."""
    best, best_sep = None, MATCH_ARCSEC
    for s in result.get("sources", []):
        sep = math.hypot(*astrometry.offset_arcsec(ra, dec, s["ra"], s["dec"]))
        if sep <= best_sep:
            best, best_sep = s, sep
    return best


def search_detectors(ra: float, dec: float, fov: float = 0.1, detectors: tuple[int, ...] = (1, 2, 3, 4, 5, 6), *,
                     figures_dir: Path | None = None, **options: Any) -> dict[str, Any]:
    """Search one field in several detectors and put what they found side by side.

    Each detector is searched on its own (`search_field`), then candidates of the same
    kind within DUPLICATE_ARCSEC of each other are one object. For every object the
    result says in which detectors it was a candidate, what every other detector
    measured at that place (also when it was no candidate there), and one combined
    significance over all detectors that measured it. An object is listed if it
    reaches 5 sigma in one detector, or 5 sigma combined with at least two detectors
    at 3 sigma or more. Detectors are separate pieces of silicon looking through
    different filters at different times, so an artefact of one rarely repeats in
    another, while a real change usually does. `options` go to `search_field`.
    """
    per: dict[int, dict[str, Any]] = {}
    for det in detectors:
        per[det] = search_field(ra, dec, fov, det, figures_dir=figures_dir, min_sigma=COMBINE_SIGMA, **options)
    groups: list[list[dict[str, Any]]] = []
    # A candidate with the signature of an artefact is not combined with anything: it is
    # listed under "rejected", with its reasons, and never becomes an object.
    every = sorted((c for r in per.values() for c in r.get("candidates", []) if c["grade"] != "rejected"),
                   key=lambda c: -c["sigma"])
    rejected = [{"detector": c["detector"], "id": c["id"], "kind": c["kind"], "sigma": c["sigma"], "ra": c["ra"],
                 "dec": c["dec"], "reasons": c["reasons"], "flags": c["flags"], "figure": c.get("figure")}
                for r in per.values() for c in r.get("candidates", [])
                if c["grade"] == "rejected" and c["sigma"] >= MOVER_SIGMA]
    for cand in every:
        home = next((g for g in groups if g[0]["kind"] == cand["kind"] and math.hypot(*astrometry.offset_arcsec(
            g[0]["ra"], g[0]["dec"], cand["ra"], cand["dec"])) <= DUPLICATE_ARCSEC), None)
        if home is None:
            groups.append([cand])
        else:
            home.append(cand)

    objects: list[dict[str, Any]] = []
    below = 0
    for group in groups:
        lead = group[0]                                    # the most significant detection
        key = "motion_sigma" if lead["kind"] == "mover" else "change_sigma"
        measured: dict[str, Any] = {}
        for det, result in per.items():
            mine = next((c for c in group if c["detector"] == det), None)
            row = _source_near(result, lead["ra"], lead["dec"])
            if mine is None and row is None:
                continue
            entry: dict[str, Any] = {"sigma": mine["sigma"] if mine else (row or {}).get(key),
                                     "candidate": mine["id"] if mine else None,
                                     "passes": bool(mine and mine["passes"]),
                                     "flags": mine["flags"] if mine else (row or {}).get("flags", []),
                                     "figure": mine.get("figure") if mine else None}
            if lead["kind"] == "mover":
                motion = mine["motion"] if mine else None
                entry["pm_east"] = motion["pm_east"] if motion else (row or {}).get("pm_east")
                entry["pm_north"] = motion["pm_north"] if motion else (row or {}).get("pm_north")
                entry["pm_err"] = motion["speed_err"] if motion else (row or {}).get("speed_err")
            elif mine:
                entry["change"] = {k: mine["change"][k] for k in ("bins", "change", "change_err", "ratio",
                                                                  "n_channels")}
            elif row and row["changes"]:
                top = max(row["changes"], key=lambda c: c[4])
                entry["change"] = {"bins": top[:2], "change": top[2], "change_err": top[3], "ratio": top[5],
                                   "n_channels": top[6]}
            measured[str(det)] = entry
        # A detector in which the source sits on a bright star's glow says nothing:
        # that glow changes in every detector at once, so it would be counted six times.
        usable = {d: m for d, m in measured.items() if m["sigma"] is not None and "halo" not in m["flags"]}
        sigmas = [m["sigma"] for m in usable.values()]
        strong = [d for d, m in usable.items() if m["sigma"] >= COMBINE_SIGMA]
        combined = _fisher(sigmas)
        alone = any(c["passes"] for c in group)
        if not (alone or (combined >= MOVER_SIGMA and len(strong) >= 2)):
            below += 1
            continue
        if lead["label"] == "not checked" and options.get("catalogues", True):
            when = {v["epoch"] - 1: v["mjd_mean"] for v in per[lead["detector"]]["visits"]}
            check_catalogues([lead], ra, dec, fov, when)
        agreement = None
        if lead["kind"] == "mover":
            # Do the detectors that saw it move agree on the motion? Chi-square of
            # their motions about the weighted mean, as a Gaussian equivalent.
            seen = [m for m in usable.values() if m["sigma"] >= COMBINE_SIGMA and m.get("pm_err")]
            if len(seen) >= 2:
                w = np.array([1.0 / m["pm_err"] ** 2 for m in seen])
                pe, pn = np.array([m["pm_east"] for m in seen]), np.array([m["pm_north"] for m in seen])
                me, mn = float((w * pe).sum() / w.sum()), float((w * pn).sum() / w.sum())
                chi2 = float((w * ((pe - me) ** 2 + (pn - mn) ** 2)).sum())
                apart = _sigma_from_p(float(stats.chi2.sf(chi2, 2 * (len(seen) - 1))))
                agreement = {"pm_east": round(me, 3), "pm_north": round(mn, 3),
                             "pm_err": round(float(w.sum() ** -0.5), 3), "n_detectors": len(seen),
                             "disagreement_sigma": round(apart, 1)}
        objects.append({
            "kind": lead["kind"], "ra": lead["ra"], "dec": lead["dec"], "label": lead["label"],
            "category": lead["category"], "summary": lead["catalogue"].get("summary"),
            "motion_all_detectors": agreement,
            "sigma_best": lead["sigma"], "best_detector": lead["detector"], "sigma_combined": round(combined, 1),
            "found_by": "one detector alone" if alone else "several detectors together",
            "detectors_at_5_sigma": [c["detector"] for c in group if c["passes"]],
            "detectors_at_3_sigma": [int(d) for d in strong], "detectors_measured": [int(d) for d in usable],
            "detectors_on_glow": [int(d) for d, m in measured.items() if "halo" in m["flags"]],
            # Clean if some detector's own candidate had nothing asking for caution;
            # otherwise the reasons are those of the most significant detection.
            "grade": "clean" if any(c["grade"] == "clean" for c in group) else "caution",
            "flags": [] if any(c["grade"] == "clean" for c in group) else lead["flags"],
            "by_detector": measured, "catalogue": lead["catalogue"],
            "lead": {"detector": lead["detector"], "id": lead["id"]}})
    objects.sort(key=lambda o: (o["grade"] != "clean", -o["sigma_combined"]))
    for number, obj in enumerate(objects, 1):
        obj["id"] = f"{number:02d}"
    return {"ra": ra, "dec": dec, "fov": fov, "detectors": list(detectors), "objects": objects,
            "rejected": sorted(rejected, key=lambda c: -c["sigma"]), "n_groups_below_threshold": below,
            "seconds": round(sum(r.get("seconds", 0.0) for r in per.values()), 1),
            "per_detector": {str(d): r for d, r in per.items()}}


# --------------------------------------------------------------------------- the public entry point

KIND_WORDS = {
    "known_mover": "known moving object: a catalogue object at this place has the measured motion",
    "mover_motion_not_in_catalogues": "moved; no catalogue object here has this motion (candidate)",
    "mover_no_counterpart": "moved; nothing in the catalogues that answered (candidate)",
    "known_variable": "known variable star: listed as variable in a catalogue that answered",
    "changer_not_listed_as_variable": "changed brightness; the object here is not listed as variable in the "
                                      "catalogues that answered (candidate)",
    "changer_no_counterpart": "changed brightness; nothing in the catalogues that answered (candidate)",
    "not checked": "catalogues not consulted",
}
LIMITS = (
    "Finds only what stands 5 times above the noise of empty places in the picture of one visit or of all "
    "visits together, in at least one detector. A mover must move between visits (not within one: asteroids "
    "are averaged away), by less than 8 arcsec from one visit to the next (about 16 arcsec/yr for visits six "
    "months apart), and by more than about 1.2 to 3 arcsec/yr for 5 sigma, depending on brightness. "
    "Saturated stars are placed only to 1 to 2 arcsec. A brightness change must be at least 10 per cent (25 "
    "per cent for a saturated star's ring), seen at the same wavelength in at least 6 channels. Sources on the "
    "glow of a much brighter star are not tested. See docs/search.md.")


def _evidence(cand: dict[str, Any]) -> dict[str, Any]:
    """What one detector measured for a candidate, without the bulky per-channel tables."""
    keep = ("detector", "id", "kind", "sigma", "grade", "flags", "reasons", "found_in", "times_noise_all_visits",
            "typical_flux_mjy", "visits", "figure")
    out = {k: cand[k] for k in keep if k in cand}
    if cand["kind"] == "mover":
        out["motion"] = cand["motion"]
    else:
        out.update(measure=cand.get("measure"), change=cand.get("change"), two_out=cand.get("two_out"),
                   channels=cand.get("channels"))
    return out


def search(ra: float, dec: float, fov: float = 0.1, detectors: tuple[int, ...] = (1, 2, 3, 4, 5, 6), *,
           offline: bool = False, catalogues: bool = True, figures_dir: Path | None = None,
           fetch: Fetch | None = None, bin_days: float | None = None, detail: bool = False) -> dict[str, Any]:
    """Search a field for sources that move or change, blind: no target is given.

    ra, dec: field centre in degrees (ICRS); fov: side of the square field in degrees
    (0.02 to 0.5); detectors: which of SPHEREx's six to search. `offline` uses only
    cutouts already in the cache (never downloads); `fetch` replaces the way cutouts
    are got (`spherex.fetch_cutouts` by default; `fetch_to_own_cache` keeps new ones
    out of the shared cache). `bin_days` also splits each visit at gaps longer than
    that for the brightness test. Returns plain data, ready for json.dumps:

    - objects: everything that passed, most trustworthy first. Each has `kind`
      ("mover" or "changer"), `verdict` ("clean" or "caution", with `flags`), place,
      significance (best detector and combined), `catalogue_status` (what the
      catalogues that answered say, which answered and which did not, in words in
      `meaning`), and `evidence`: the full measurement of the detector that saw it
      best, including per-visit positions, the forced measurement at the predicted
      place against empty places, and for a changer the dates and channels compared.
    - rejected: candidates that reached 5 sigma but carry an artefact's signature,
      each with its `reasons`. Never to be shown as finds.
    - summary: counts, time taken, catalogue services that answered or failed.
    - limits: what this search cannot find, in words.
    With `detail` the full per-detector results (every source tested) are added.
    """
    result = search_detectors(ra, dec, fov, tuple(detectors), figures_dir=figures_dir, offline=offline,
                              catalogues=catalogues, fetch=fetch, bin_days=bin_days)
    per = result["per_detector"]
    objects = []
    for obj in result["objects"]:
        lead = next(c for c in per[str(obj["lead"]["detector"])]["candidates"] if c["id"] == obj["lead"]["id"])
        cat = obj["catalogue"]
        objects.append({
            "id": obj["id"], "kind": obj["kind"], "verdict": obj["grade"], "flags": obj["flags"],
            "ra": obj["ra"], "dec": obj["dec"], "sigma_best": obj["sigma_best"], "best_detector": obj["best_detector"],
            "sigma_combined": obj["sigma_combined"], "found_by": obj["found_by"],
            "detectors_at_5_sigma": obj["detectors_at_5_sigma"], "detectors_at_3_sigma": obj["detectors_at_3_sigma"],
            "motion_all_detectors": obj["motion_all_detectors"],
            "catalogue_status": {"category": obj["category"], "meaning": KIND_WORDS.get(obj["category"]),
                                 "label": obj["label"], "summary": obj["summary"],
                                 "answered": cat.get("answered", []), "did_not_answer": cat.get("failed", {}),
                                 "counterpart": cat.get("counterpart"), "nearest": (cat.get("matches") or [])[:5]},
            "by_detector": obj["by_detector"], "evidence": _evidence(lead)})
    tested = sum(r.get("n_sources", 0) - r.get("n_sources_on_glow_not_tested", 0) for r in per.values())
    answered = sorted({a for r in per.values() for a in r.get("catalogues", {}).get("answered", [])})
    failed = {k: v for r in per.values() for k, v in r.get("catalogues", {}).get("failed", {}).items()}
    out: dict[str, Any] = {
        "field": {"ra": ra, "dec": dec, "fov": fov, "detectors": list(detectors), "offline": offline},
        "objects": objects, "rejected": result["rejected"],
        "summary": {"n_objects": len(objects), "n_rejected": len(result["rejected"]),
                    "n_below_threshold": result["n_groups_below_threshold"], "sources_tested": tested,
                    "seconds": result["seconds"], "catalogues_answered": answered, "catalogues_failed": failed,
                    "messages": {d: r["message"] for d, r in per.items() if r.get("message")},
                    "download_failures": {d: len(r["failures"]) for d, r in per.items() if r.get("failures")},
                    "exposures": {d: r.get("n_exposures", 0) for d, r in per.items()}},
        "limits": LIMITS, "version": VERSION, "credit": next(iter(per.values()))["credit"] if per else pipeline.CREDIT}
    if detail:
        out["per_detector"] = per
    return out


# --------------------------------------------------------------------------- pictures

def _figure(cand: dict[str, Any], field: dict[str, Any], st: dict[str, Any], bin_labels: list[dict[str, Any]],
            out_dir: Path) -> Path:
    """One row of small pictures for a candidate: each visit, then last visit minus first.

    North is up, east is left. The cross marks the measured position in that visit and
    the circle the candidate's mean position. In the difference panel white means
    brighter in the last visit. All visit panels share one brightness scale. A changer
    also gets a chart of its brightness in each colour channel, one line per time bin.
    """
    half, big = 20, 6                                # 80 arcsec across, each grid pixel drawn 6 x 6
    grid, n = field["grid"], field["n"]
    cx, cy = (float(v) for v in grid.all_world2pix(cand["ra"], cand["dec"], 0))
    xi, yi = int(round(cx)), int(round(cy))
    visits: list[int] = st["visits"]

    def window(image: np.ndarray) -> np.ndarray:
        out = np.full((2 * half + 1, 2 * half + 1), np.nan)
        y0, y1, x0, x1 = max(yi - half, 0), min(yi + half + 1, n), max(xi - half, 0), min(xi + half + 1, n)
        out[y0 - (yi - half):y1 - (yi - half), x0 - (xi - half):x1 - (xi - half)] = image[y0:y1, x0:x1]
        return out

    wins = [window(st["stack"][ep]) for ep in visits]
    values = [w[np.isfinite(w)] for w in wins]
    panels: list[Image.Image] = []
    if sum(v.size for v in values):
        finite = np.concatenate(values)
        lo = float(np.percentile(finite, 5))
        soft = max(float(np.percentile(finite, 60)) - lo, 1e-6)
        hi = float(finite.max())
        for ep, w in zip(visits, wins, strict=True):
            scaled = np.arcsinh((w - lo) / soft) / np.arcsinh((hi - lo) / soft)
            panels.append(_panel(scaled, w, big))
            v = next(v for v in cand["visits"] if v["epoch"] == ep + 1)
            draw = ImageDraw.Draw(panels[-1])
            _ring(draw, cx - (xi - half), cy - (yi - half), half, big, 9, (90, 200, 255))
            if v["ra"] is not None:
                px, py = (float(c) for c in grid.all_world2pix(v["ra"], v["dec"], 0))
                _cross(draw, px - (xi - half), py - (yi - half), half, big, (255, 220, 0))
            draw.text((4, 3), f"visit {ep + 1}  {v['date_mean']}  n={v['n_exposures']}", fill=(255, 255, 0))
        diff = wins[-1] - wins[0]
        span = float(np.nanmax(np.abs(diff))) if np.isfinite(diff).any() else 1.0
        scaled = 0.5 + 0.5 * np.arcsinh(diff / soft) / np.arcsinh(max(span, soft) / soft)
        panels.append(_panel(scaled, diff, big))
        ImageDraw.Draw(panels[-1]).text((4, 3), f"visit {visits[-1] + 1} minus visit {visits[0] + 1}",
                                        fill=(255, 255, 0))
    if cand["kind"] == "changer":
        panels.append(_chart(cand, bin_labels, (2 * half + 1) * big))
    width = sum(p.width for p in panels) + 6 * (len(panels) + 1)
    height = (panels[0].height if panels else 60) + 34
    sheet = Image.new("RGB", (max(width, 300), height), (18, 18, 18))
    x = 6
    for p in panels:
        sheet.paste(p, (x, 6))
        x += p.width + 6
    what = (f"{cand['id']} {cand['kind']}  {cand['sigma']} sigma  RA {cand['ra']:.5f} Dec {cand['dec']:+.5f}  "
            f"{cand['category']}")
    if cand["kind"] == "mover":
        what += f"  {cand['motion']['speed']:.2f} arcsec/yr"
    elif cand["change"].get("ratio") is not None:
        what += f"  ratio {cand['change']['ratio']:.2f}"
    if cand["flags"]:
        what += "  flags: " + ",".join(cand["flags"])
    ImageDraw.Draw(sheet).text((6, height - 24), what, fill=(230, 230, 230))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{cand['id']}_{cand['kind']}.png"
    sheet.save(path)
    return path


_BIN_COLOURS = ((90, 170, 255), (255, 160, 60), (110, 220, 110), (240, 110, 220), (240, 230, 90), (150, 240, 240))


def _chart(cand: dict[str, Any], bin_labels: list[dict[str, Any]], size: int) -> Image.Image:
    """Brightness in each colour channel, one line per time bin: the like-with-like comparison drawn.

    Left to right is short to long wavelength within the detector. Where two lines
    stand apart in channel after channel, the source changed; where they cross and
    recross, it did not.
    """
    image = Image.new("RGB", (int(size * 1.5), size), (28, 28, 28))
    draw = ImageDraw.Draw(image)
    rows = cand["channels"]
    known = [f for r in rows for f in r["flux_mjy"] if f is not None]
    if not known:
        return image
    top, bottom = max(max(known), 0.0) * 1.08, min(min(known), 0.0)
    left, right, upper, lower = 46, image.width - 8, 30, size - 22
    draw.rectangle([left, upper, right, lower], outline=(120, 120, 120))

    def spot(channel: int, flux: float) -> tuple[float, float]:
        return (left + (channel + 0.5) / len(rows) * (right - left),
                lower - (flux - bottom) / max(top - bottom, 1e-12) * (lower - upper))

    for b, label in enumerate(bin_labels):
        colour = _BIN_COLOURS[b % len(_BIN_COLOURS)]
        points = [spot(r["channel"], r["flux_mjy"][b]) for r in rows if r["flux_mjy"][b] is not None]
        if len(points) > 1:
            draw.line(points, fill=colour, width=1)
        for x, y in points:
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=colour)
        name = f"visit {label['epoch']}" + (f".{label['part']}" if sum(
            other["epoch"] == label["epoch"] for other in bin_labels) > 1 else "")
        draw.text((left + 4 + 62 * (b % 5), 4 + 12 * (b // 5)), name, fill=colour)
    draw.text((2, upper - 4), f"{top:.3g}", fill=(200, 200, 200))
    draw.text((2, lower - 8), f"{bottom:.3g}", fill=(200, 200, 200))
    unit = "ring" if cand.get("measure") == "ring" else "mJy"   # a ring value is relative, not a flux
    draw.text((2, (upper + lower) // 2), unit, fill=(200, 200, 200))
    draw.text((left, lower + 6), f"{rows[0]['wavelength_um'][0]:.2f}", fill=(200, 200, 200))
    draw.text((right - 28, lower + 6), f"{rows[-1]['wavelength_um'][1]:.2f}", fill=(200, 200, 200))
    draw.text(((left + right) // 2 - 60, lower + 6), "wavelength, microns", fill=(200, 200, 200))
    return image


def _panel(scaled: np.ndarray, data: np.ndarray, big: int) -> Image.Image:
    grey = (np.clip(np.nan_to_num(scaled, nan=0.0), 0, 1) * 255).astype("uint8")
    rgb = np.dstack([grey, grey, grey])
    rgb[~np.isfinite(data)] = (60, 0, 80)            # purple: no data
    size = (scaled.shape[1] * big, scaled.shape[0] * big)
    return Image.fromarray(rgb[::-1], "RGB").resize(size, Image.Resampling.NEAREST)


def _to_panel(x: float, y: float, half: int, big: int) -> tuple[float, float]:
    return (x + 0.5) * big, (2 * half - y + 0.5) * big


def _cross(draw: ImageDraw.ImageDraw, x: float, y: float, half: int, big: int, colour: tuple[int, int, int]) -> None:
    px, py = _to_panel(x, y, half, big)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        draw.line([px + 5 * dx, py + 5 * dy, px + 14 * dx, py + 14 * dy], fill=colour, width=1)


def _ring(draw: ImageDraw.ImageDraw, x: float, y: float, half: int, big: int, radius_px: float,
          colour: tuple[int, int, int]) -> None:
    px, py = _to_panel(x, y, half, big)
    r = radius_px * big
    draw.ellipse([px - r, py - r, px + r, py + r], outline=colour)

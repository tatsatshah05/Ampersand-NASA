"""Distant-world search: objects far out in the solar system (the "Planet X" case).

The blind search (`search.py`) follows a source only if it moves less than 8 arcsec from
one visit to the next. A body a few hundred to a few tens of thousands of times the
Earth-Sun distance (AU) away breaks that rule in a known way. SPHEREx looks at a patch
of sky about every six months, from opposite sides of the Earth's orbit, so the body
appears to jump by about twice its parallax: 825 arcsec at 500 AU, 41 arcsec at 10,000
AU. In the ordinary search that is one source that vanished and one that appeared.

Entry point: `distant_search(ra, dec, fov, detectors)`. It answers with candidates, each
with a distance, or with a limit: how bright an object at each distance would have had
to be for this search to find it.

Method, in the order the code runs
1. The stacked image of every visit, built exactly as for /api/frames
   (`training.epoch_stacks`, which is the real stack and plants nothing).
2. Sources in each visit on its own: a matched filter the width of a star image, on a
   locally measured background and noise. A source needs 4 times the noise to be
   listed; a link needs two sources at 5 times the noise or more.
3. Sources that come and go: a source of one visit that is missing at the same place in
   at least one other visit. Everything else is an ordinary star and is set aside.
   Those with a catalogued infrared source (CatWISE2020) at their place, bright enough
   to be them, are set aside too: a body that moves was somewhere else when WISE looked.
4. Linking. A distant body's place in each visit is fixed by five numbers: where it is
   (2), its own slow drift along its orbit (2) and its parallax (1), which is its
   distance. The Earth's position at every exposure is known, so the direction of the
   jump is known in advance and its size gives the distance. One source per visit is
   taken, the five numbers are fitted, and the link is kept only if the places fit, the
   drift is no faster than a bound orbit at that distance allows, the brightness is
   steady, and the source is missing wherever the fit says it should be.
5. The same linking with the Earth's motion reversed, which nothing real can follow.
   What that finds is the number of links chance alone makes in this picture.
6. The limit: 5 times each visit's noise, raised for the smearing of a near object
   within a visit (it moves while the visit lasts), and the share of the picture in
   which an object at each distance stays in view in every visit.

Limits
- At least three visits are needed, on both sides of the Earth's orbit.
- A visit that lasts weeks smears a near object: the limit says by how much.
- Sources in the glow of a bright star, on saturated pixels or near the edge are not found.
- A link is a candidate, never a detection of a planet: it has to be looked at, and
  confirmed in another detector and by a later visit.
- Catalogues built from ten years of WISE data reach fainter than one SPHEREx visit at
  these wavelengths, so the expected answer is a limit.

Planted objects (the practice-mode kind, `training.py`) can be searched for with
`planted=`: the answer is then marked as a simulation, kept in its own files and never
mixed with a real result. They are how the search is tested, since no real object of
this kind is known that SPHEREx could see.
"""
from __future__ import annotations

import hashlib
import json
import math
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from scipy.ndimage import gaussian_filter, maximum_filter, median_filter, zoom
from scipy.stats import chi2 as chi2_dist

from . import astrometry, pipeline, search, spherex, training

VERSION = 1
DISTANT_DIR = spherex.CACHE / "distant"
ARCSEC_PER_RADIAN = 206264.806

DETECT_SIGMA = 5.0          # two of a link's sources need this many times the local noise ...
MEMBER_SIGMA = 4.0          # ... and the others this many
MIN_COVER = 0.7             # share of the star image that must fall on pixels with data
EDGE_PX = 6                 # nothing is looked for this close to the edge of the picture
BLOCK_PX = 64               # the background is measured in blocks this wide
NOISE_BLOCK_PX = 32         # ... and the noise in blocks this wide (never below what its neighbours say)
CLEAR_NOISE = 1.5           # "clear sky": the noise is at most this many times the picture's usual noise
PEAK_BOX_PX = 7             # a source is the highest point within this box
BRIGHT_STAR_SIGMA = 15.0    # sources this strong, seen in every visit, calibrate "point-like"
POINT_LIKE = (0.7, 1.4)     # allowed width measure, relative to the picture's own stars
SHAPE_SLACK = 1.5           # the allowance widens by this over the detection strength

GONE_SHARE = 0.4            # "missing" in another visit: under this share of its brightness there ...
GONE_BELOW = 2.5            # ... and under this many times that visit's noise
THERE_SHARE = 0.6           # "still there" in another visit: at least this share of its brightness ...
THERE_SIGMA = 3.0           # ... and this many times that visit's noise
AWAY_ARCSEC = 20.0          # a link's source may not be "still there" in a visit that puts the body this far off
MIN_JUMP_ARCSEC = 12.0      # a smaller jump overlaps the source's own image in the other visit
SEED_LEVERAGE = 0.8         # two visits start a link only if the Earth moved this far between them (AU, on the sky)
NEAREST_AU = 100.0          # nothing nearer is tried: it would cross any picture within one visit
BOUND_FACTOR = 1.5          # drift allowed: this many times a circular orbit's (escape is 1.41 times)
DRIFT_SLACK = 4.0           # arcsec a year allowed on top, for the measuring error of two places
POSITION_FLOOR = 1.0        # arcsec: no source is trusted to be placed better than this
POSITION_SCALE = 6.0        # arcsec: position error of a source is this over its strength, and the floor
FIT_CONFIDENCE = 0.997      # a link's places must fit this well (chi-square)
FLUX_RATIO = 2.5            # brightest over faintest visit of a link, at most
FLUX_SIGMA = 3.0            # ... unless the difference is within this many times its error
EXPECT_SIGMA = 7.0          # a visit that should show the object this strongly, and does not, kills the link
MATCH_ARCSEC = 5.0          # a catalogue source this close is "at that place"
CATALOGUE_SHARE = 0.25      # ... if it is at least this bright next to the SPHEREx source
SUPPORT_SIGMA = 3.5         # the other detector "sees it too" at this strength, in at least two visits
MIN_IN_VIEW = 0.1           # a distance is quoted only if this share of the picture is searched for it
DISTANCES_AU = (300, 500, 700, 1000, 1500, 2000, 3000, 5000, 10000, 20000, 30000)

WISE_ZERO_JY = {"w1": 309.54, "w2": 171.787}    # WISE Explanatory Supplement, flux of magnitude zero

LIMITS_TEXT = (
    "This search needs an object to be seen as a point of light in at least three visits (5 times the noise "
    "in two of them and 4 times in a third), to stay inside the picture in all of them, and to be clear of "
    "bright stars and of catalogued infrared sources. It cannot find anything in a field with fewer than three "
    "visits, anything "
    "that changes brightness a lot from visit to visit, or an object so near that it smears within a visit "
    "(the table gives the limit at each distance). Catalogues built from ten years of WISE data reach fainter "
    "than one SPHEREx visit at these wavelengths, so finding nothing is the expected answer.")


# ---------------------------------------------------------------------------
# Geometry: where a distant body appears in each visit
# ---------------------------------------------------------------------------

def _earth(mjds: np.ndarray) -> np.ndarray:
    """The Earth's place on each date: rows of x, y, z in AU from the solar system's centre of mass."""
    return np.asarray(get_body_barycentric("earth", Time(mjds, format="mjd")).xyz.to_value("au")).T


def parallax_factor(earth: np.ndarray, ra: float, dec: float) -> np.ndarray:
    """Shift on the sky (east, north) of an object in direction (ra, dec), in arcsec per arcsec
    of parallax, when the Earth is at `earth`. The arithmetic of `astrometry.position_at`."""
    a, d = np.radians(ra), np.radians(dec)
    east = earth[..., 0] * np.sin(a) - earth[..., 1] * np.cos(a)
    north = earth[..., 0] * np.cos(a) * np.sin(d) + earth[..., 1] * np.sin(a) * np.sin(d) - earth[..., 2] * np.cos(d)
    return np.stack([east, north], axis=-1)


def visits_from(items: dict[int, list[dict]], ra: float, dec: float, as_planted: bool = False) -> list[dict]:
    """What the linking needs to know about each visit: when it was and where the Earth was.

    A visit is many exposures over days or weeks. A body's place in the stacked image is
    the average of its places in the exposures, so the Earth's position is averaged with
    the weights of the stack. `smear` is how far the body moves within the visit, as an
    rms in arcsec per arcsec of parallax. With `as_planted` the visit is treated as one
    instant at its mean date, which is how `training.py` plants its object.
    """
    out = []
    for ep in sorted(items):
        mjd = np.array([it["mjd"] for it in items[ep]], dtype=float)
        w = np.array([it["weight"] for it in items[ep]], dtype=float)
        w = w / w.sum()
        mean_mjd = float((w * mjd).sum())
        if as_planted:
            earth, smear = _earth(np.array([mean_mjd]))[0], 0.0
        else:
            each = _earth(mjd)
            earth = (w[:, None] * each).sum(axis=0)
            spread = parallax_factor(each, ra, dec) - parallax_factor(earth, ra, dec)
            smear = float(np.sqrt((w * (spread ** 2).sum(axis=1)).sum()))
        out.append({"epoch": ep, "mjd": mean_mjd, "year": float(Time(mean_mjd, format="mjd").jyear),
                    "earth": earth, "smear": smear, "n_exposures": len(mjd),
                    "mjd_start": float(mjd.min()), "mjd_end": float(mjd.max())})
    return out


def place_in_visit(body: dict, visit: dict) -> tuple[float, float]:
    """Where the body appears in a visit. `body` is the dictionary `astrometry.position_at`
    takes (ra, dec in degrees; pmra, pmdec in mas/yr; parallax in mas; ref_epoch)."""
    f = parallax_factor(visit["earth"], body["ra"], body["dec"])
    dt = visit["year"] - body["ref_epoch"]
    east = (body["pmra"] * dt + body["parallax"] * f[0]) / 1000.0
    north = (body["pmdec"] * dt + body["parallax"] * f[1]) / 1000.0
    return (body["ra"] + east / 3600.0 / math.cos(math.radians(body["dec"]))) % 360.0, body["dec"] + north / 3600.0


def circular_drift(distance_au: float) -> float:
    """Arcsec a year that a body on a circular orbit at this distance moves along it."""
    return ARCSEC_PER_RADIAN * 2.0 * math.pi / distance_au ** 1.5


def _wrap(d_ra: np.ndarray | float) -> Any:
    return (np.asarray(d_ra) + 180.0) % 360.0 - 180.0


def fit_body(ra: np.ndarray, dec: np.ndarray, err: np.ndarray, visits: list[dict]) -> dict | None:
    """The five numbers of a distant body from its place in three or more visits.

    Weighted least squares; the model is linear once the place is roughly known, so it
    is solved three times. Returns the body, chi-square, the misfit of each place and
    the error of the parallax, or None when the visits cannot separate parallax from
    drift (all on the same side of the Earth's orbit).
    """
    m = len(visits)
    years = np.array([v["year"] for v in visits])
    earth = np.array([v["earth"] for v in visits])
    ref = float(years.mean())
    tau = years - ref
    ra0, dec0 = float(ra[0] + _wrap(ra - ra[0]).mean()), float(dec.mean())
    w = np.repeat(1.0 / err, 2)
    a = np.zeros((2 * m, 5))
    y = np.zeros(2 * m)
    u = np.zeros(5)
    for step in range(4):
        cosd = math.cos(math.radians(dec0))
        f = parallax_factor(earth, ra0, dec0)
        a[0::2] = np.column_stack([np.ones(m), np.zeros(m), tau, np.zeros(m), f[:, 0]])
        a[1::2] = np.column_stack([np.zeros(m), np.ones(m), np.zeros(m), tau, f[:, 1]])
        y[0::2] = _wrap(ra - ra0) * cosd * 3600.0
        y[1::2] = (dec - dec0) * 3600.0
        if step == 3:
            break                       # the last pass only measures the misfit at the settled place
        try:
            u, _, rank, _ = np.linalg.lstsq(a * w[:, None], y * w, rcond=None)
        except np.linalg.LinAlgError:
            return None
        if rank < 5:
            return None
        ra0 += float(u[0]) / 3600.0 / cosd
        dec0 += float(u[1]) / 3600.0
        u[0] = u[1] = 0.0
    resid = y - a @ u
    try:
        cov = np.linalg.inv((a * w[:, None]).T @ (a * w[:, None]))
    except np.linalg.LinAlgError:
        return None
    body = {"ra": ra0 % 360.0, "dec": dec0, "pmra": float(u[2]) * 1000.0, "pmdec": float(u[3]) * 1000.0,
            "parallax": float(u[4]) * 1000.0, "ref_epoch": ref}
    return {"body": body, "chi2": float(((resid * w) ** 2).sum()), "dof": 2 * m - 5,
            "misfit_arcsec": [float(np.hypot(resid[2 * i], resid[2 * i + 1])) for i in range(m)],
            "parallax_err_arcsec": float(math.sqrt(max(cov[4, 4], 0.0))),
            "drift_err_arcsec": float(math.sqrt(max(cov[2, 2] + cov[3, 3], 0.0)))}


# ---------------------------------------------------------------------------
# Sources of one visit
# ---------------------------------------------------------------------------

def _block_stat(image: np.ndarray, use: np.ndarray, spread: bool) -> np.ndarray:
    """Median (or robust scatter) of the usable pixels in blocks, spread back smoothly over the picture.

    The scatter is measured in smaller blocks, so that the glow of a bright star raises the
    noise only around that star. A small block gives a rough figure, so no block's noise is
    taken to be lower than the middle value of it and its eight neighbours.
    """
    n = image.shape[0]
    block = NOISE_BLOCK_PX if spread else BLOCK_PX
    nb = max(1, int(math.ceil(n / block)))
    side = nb * block
    padded = np.full((side, side), np.nan)
    padded[:n, :n] = np.where(use, image, np.nan)
    blocks = padded.reshape(nb, block, nb, block).transpose(0, 2, 1, 3).reshape(nb, nb, -1)
    enough = np.isfinite(blocks).sum(axis=2) >= 0.2 * block * block
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # a block with no data at all
        value = np.nanmedian(blocks, axis=2)
        if spread:
            value = 1.4826 * np.nanmedian(np.abs(blocks - value[:, :, None]), axis=2)
    value = np.where(enough, value, np.nan)
    if not np.isfinite(value).any():
        return np.full((n, n), np.nan)
    value = np.where(np.isfinite(value), value, np.nanmedian(value))
    if spread and nb >= 3:
        value = np.maximum(value, median_filter(value, size=3, mode="nearest"))
    if nb == 1:
        return np.full((n, n), float(value[0, 0]))
    return zoom(value, block, order=1, mode="nearest", grid_mode=True)[:n, :n]


def _amplitude(resid: np.ndarray, valid: np.ndarray, sigma_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Best-fitting height of a star image of the given width centred on every pixel, and the
    share of that star image falling on pixels with data."""
    weight = gaussian_filter(valid.astype(float), sigma_px / math.sqrt(2.0), mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        height = 2.0 * gaussian_filter(np.where(valid, resid, 0.0), sigma_px, mode="constant") / weight
    return height, weight


def measure_visit(image: np.ndarray, sigma_px: float) -> dict[str, np.ndarray]:
    """The maps a visit is searched on: `height` (of a star image centred at each pixel,
    MJy/sr, local background removed), `noise` (its scatter where the sky is empty),
    `cover` and `wide` (the same height for an image twice as wide, for the width test)."""
    valid = np.isfinite(image)
    resid = image - _block_stat(image, valid, spread=False)
    height, cover = _amplitude(resid, valid, sigma_px)
    wide, _ = _amplitude(resid, valid, 2.0 * sigma_px)
    ok = valid & (cover >= MIN_COVER)
    height = height - _block_stat(height, ok, spread=False)
    noise = _block_stat(height, ok, spread=True)
    return {"height": np.where(ok, height, np.nan), "noise": noise, "cover": cover, "wide": wide}


def _top(lo: float, mid: float, hi: float) -> float:
    """Where a parabola through three neighbouring values peaks, in pixels from the middle one:
    the place of a source to a fraction of a pixel."""
    bend = lo - 2.0 * mid + hi
    return float(np.clip(0.5 * (lo - hi) / bend, -0.5, 0.5)) if bend < 0 else 0.0


def find_sources(maps: dict[str, np.ndarray], grid: WCS) -> list[dict]:
    """Every point of light in one visit that stands MEMBER_SIGMA above the noise."""
    height, noise = maps["height"], maps["noise"]
    n = height.shape[0]
    with np.errstate(invalid="ignore"):
        strength = height / noise
    filled = np.where(np.isfinite(strength), strength, -np.inf)
    highest = maximum_filter(filled, size=PEAK_BOX_PX, mode="constant", cval=-np.inf)
    peak = (filled == highest) & (filled >= MEMBER_SIGMA)
    peak[:EDGE_PX] = peak[-EDGE_PX:] = False
    peak[:, :EDGE_PX] = peak[:, -EDGE_PX:] = False
    out = []
    for yi, xi in zip(*np.nonzero(peak), strict=True):
        box = height[yi - 1:yi + 2, xi - 1:xi + 2]
        if not np.isfinite(box).all():
            continue
        x = xi + _top(box[1, 0], box[1, 1], box[1, 2])
        y = yi + _top(box[0, 1], box[1, 1], box[2, 1])
        sky_ra, sky_dec = grid.all_pix2world(x, y, 0)
        s = float(strength[yi, xi])
        out.append({"x": float(x), "y": float(y), "xi": int(xi), "yi": int(yi), "ra": float(sky_ra) % 360.0,
                    "dec": float(sky_dec), "height": float(height[yi, xi]), "noise": float(noise[yi, xi]),
                    "strength": s, "width": float(maps["wide"][yi, xi] / height[yi, xi]),
                    "pos_err": float(math.hypot(POSITION_FLOOR, POSITION_SCALE / s))})
    n_edge = n - EDGE_PX
    return [s for s in out if EDGE_PX <= s["x"] < n_edge and EDGE_PX <= s["y"] < n_edge]


def _sample(maps: dict[str, np.ndarray], x: float, y: float) -> tuple[float, float] | None:
    """Height and noise at a place in another visit (the highest value within a pixel of it,
    so a small misplacement never makes a steady source look missing). None: no data there."""
    n = maps["height"].shape[0]
    xi, yi = int(round(x)), int(round(y))
    if not (1 <= xi < n - 1 and 1 <= yi < n - 1):
        return None
    box = maps["height"][yi - 1:yi + 2, xi - 1:xi + 2]
    if not np.isfinite(box).any() or not math.isfinite(float(maps["noise"][yi, xi])):
        return None
    return float(np.nanmax(box)), float(maps["noise"][yi, xi])


def come_and_go(sources: dict[int, list[dict]], maps: dict[int, dict[str, np.ndarray]]) -> list[dict]:
    """The sources that are missing from the same place in at least one other visit.

    Each gets `visit` (its own) and `elsewhere`: per other visit, the height found at its
    place, whether that counts as missing (`gone`) and whether the source is plainly still
    there (`there`); both None where that visit has no data at the place.
    Also sets `width_ratio`: the width measure over that of the picture's steady stars.
    """
    visits = sorted(sources)
    members = []
    for k in visits:
        steady_widths = []
        for s in sources[k]:
            s["visit"] = k
            s["elsewhere"] = {}
            for m in visits:
                if m == k:
                    continue
                got = _sample(maps[m], s["x"], s["y"])
                if got is None:
                    s["elsewhere"][m] = {"height": None, "gone": None, "there": None}
                    continue
                found, noise_there = got
                s["elsewhere"][m] = {
                    "height": found,
                    "gone": bool(found < GONE_SHARE * s["height"] and found < GONE_BELOW * noise_there),
                    "there": bool(found >= THERE_SHARE * s["height"] and found >= THERE_SIGMA * noise_there)}
            seen = [e["gone"] for e in s["elsewhere"].values() if e["gone"] is not None]
            s["comes_and_goes"] = any(seen)
            if seen and not any(seen) and s["strength"] >= BRIGHT_STAR_SIGMA:
                steady_widths.append(s["width"])
        usual = float(np.median(steady_widths)) if len(steady_widths) >= 5 else 0.4   # 0.4: a perfect star image
        for s in sources[k]:
            s["width_ratio"] = s["width"] / usual
            slack = SHAPE_SLACK / s["strength"]
            s["point_like"] = POINT_LIKE[0] - slack <= s["width_ratio"] <= POINT_LIKE[1] + slack
            if s["comes_and_goes"]:
                members.append(s)
    return members


def flux_mjy(height: float, sigma_px: float) -> float:
    """Rough flux of a point of light from the fitted height of its star image (MJy/sr to mJy)."""
    solid_angle = 2.0 * math.pi * sigma_px ** 2 * (pipeline.GRID_ARCSEC / ARCSEC_PER_RADIAN) ** 2
    return height * solid_angle * 1e9


# ---------------------------------------------------------------------------
# Catalogue: is a known, fixed infrared source at the place?
# ---------------------------------------------------------------------------

def catwise_field(ra: float, dec: float, fov: float) -> list[dict]:
    """CatWISE2020 sources over the picture (one query, kept on disk). Raises ArchiveError."""
    radius = round(fov * 0.7072 + 0.01, 4)

    def run() -> list[dict]:
        table = search._gator("catwise_2020", ra, dec, radius, "ra_pm,dec_pm,pmra,pmdec,w1mpro_pm,w2mpro_pm",
                              "w1mpro_pm<17.5 or w2mpro_pm<16.5")
        rows = []
        for d in table:
            sra, sdec = search._num(d["ra_pm"]), search._num(d["dec_pm"])
            if sra is None or sdec is None:
                continue
            rows.append({"ra": sra, "dec": sdec, "pmra": search._num(d["pmra"]), "pmdec": search._num(d["pmdec"]),
                         "w1": search._num(d["w1mpro_pm"]), "w2": search._num(d["w2mpro_pm"])})
        return rows

    return search._cached_query("catwise_field", f"{ra:.5f},{dec:.5f},{radius:.4f}", run)


def _catalogue_flux(row: dict) -> float:
    """The brighter of a catalogue source's two WISE fluxes, in mJy."""
    return max((WISE_ZERO_JY[b] * 10.0 ** (-0.4 * row[b]) * 1000.0 for b in ("w1", "w2") if row.get(b) is not None),
               default=0.0)


def mark_catalogued(members: list[dict], rows: list[dict], sigma_px: float, year: float = 2026.0) -> None:
    """Set `catalogued` on each source: a catalogue source within MATCH_ARCSEC of it that is at
    least CATALOGUE_SHARE as bright. Catalogue places are moved to `year` with their own motion."""
    if not rows:
        for s in members:
            s["catalogued"] = None
        return
    dt = year - float(Time(57170.0, format="mjd").jyear)      # CatWISE2020 positions are for MJD 57170
    cdec = np.array([r["dec"] + (r["pmdec"] or 0.0) * dt / 3600.0 for r in rows])
    cra = np.array([r["ra"] + (r["pmra"] or 0.0) * dt / 3600.0 / max(math.cos(math.radians(r["dec"])), 1e-6)
                    for r in rows])
    cflux = np.array([_catalogue_flux(r) for r in rows])
    for s in members:
        east = _wrap(cra - s["ra"]) * math.cos(math.radians(s["dec"])) * 3600.0
        north = (cdec - s["dec"]) * 3600.0
        near = (np.hypot(east, north) <= MATCH_ARCSEC) & (cflux >= CATALOGUE_SHARE * flux_mjy(s["height"], sigma_px))
        s["catalogued"] = None
        if near.any():
            i = int(np.argmax(np.where(near, cflux, -1.0)))
            s["catalogued"] = {"catalogue": "CatWISE2020",
                               "separation_arcsec": round(float(np.hypot(east[i], north[i])), 1),
                               "w1": rows[i]["w1"], "w2": rows[i]["w2"]}


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------

Strength = Callable[[int, float, float], "tuple[float, float] | None"]


def _loss(parallax_arcsec: float, visit: dict, psf_arcsec: float) -> float:
    """Share of its peak a body keeps in a visit's stack, given how far it moves while the visit lasts."""
    return 1.0 / math.sqrt(1.0 + (parallax_arcsec * visit["smear"] / psf_arcsec) ** 2)


def _separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    east = float(_wrap(ra2 - ra1)) * math.cos(math.radians(0.5 * (dec1 + dec2))) * 3600.0
    return math.hypot(east, (dec2 - dec1) * 3600.0)


def _judge(chosen: dict[int, dict], visits: list[dict], psf_arcsec: float, strength_at: Strength | None) -> dict | None:
    """Fit one source per visit as a single distant body; None unless every test passes."""
    order = sorted(chosen)
    ra = np.array([chosen[k]["ra"] for k in order])
    dec = np.array([chosen[k]["dec"] for k in order])
    err = np.array([chosen[k]["pos_err"] for k in order])
    fit = fit_body(ra, dec, err, [visits[k] for k in order])
    if fit is None or fit["chi2"] > chi2_dist.ppf(FIT_CONFIDENCE, fit["dof"]):
        return None
    body = fit["body"]
    plx = body["parallax"] / 1000.0
    if plx <= 0 or ARCSEC_PER_RADIAN / plx < NEAREST_AU:
        return None
    distance = ARCSEC_PER_RADIAN / plx
    drift = math.hypot(body["pmra"], body["pmdec"]) / 1000.0
    if drift > BOUND_FACTOR * circular_drift(distance) + DRIFT_SLACK + 3.0 * fit["drift_err_arcsec"]:
        return None
    places = {k: place_in_visit(body, visits[k]) for k in range(len(visits))}
    jump = max(_separation(*places[i], *places[j]) for i in order for j in order)
    if jump < MIN_JUMP_ARCSEC:
        return None
    # Steady brightness, after allowing for the smearing of each visit.
    bright = np.array([chosen[k]["height"] / _loss(plx, visits[k], psf_arcsec) for k in order])
    bright_err = np.array([chosen[k]["noise"] / _loss(plx, visits[k], psf_arcsec) for k in order])
    hi, lo = int(np.argmax(bright)), int(np.argmin(bright))
    if (bright[hi] > FLUX_RATIO * bright[lo]
            and bright[hi] - bright[lo] > FLUX_SIGMA * math.hypot(bright_err[hi], bright_err[lo])):
        return None
    if sum(1 for k in order if chosen[k]["strength"] >= DETECT_SIGMA) < 2:
        return None
    # Not still there in a visit in which the fit has moved the body well away.
    for k in order:
        for m, seen in chosen[k]["elsewhere"].items():
            away = _separation(chosen[k]["ra"], chosen[k]["dec"], *places[m]) >= AWAY_ARCSEC
            if away and seen["there"]:
                return None
    # A visit left out of the link must be one that could not have shown the object.
    skipped = []
    for m in range(len(visits)):
        if m in chosen:
            continue
        expected = float(np.median(bright)) * _loss(plx, visits[m], psf_arcsec)
        got = strength_at(m, *places[m]) if strength_at else None
        if got is not None and expected >= EXPECT_SIGMA * got[1] and got[0] < 0.5 * expected:
            return None
        skipped.append({"visit": m, "reason": "no data at the predicted place" if got is None
                        else "too faint to show there"})
    return {"members": chosen, "fit": fit, "body": body, "distance_au": distance, "drift_arcsec_per_year": drift,
            "jump_arcsec": jump, "places": places, "skipped": skipped}


def link(members: list[dict], visits: list[dict], psf_arcsec: float, strength_at: Strength | None = None,
         reverse: bool = False) -> list[dict]:
    """Every set of come-and-go sources, one per visit, that fits a single distant body.

    With `reverse` the Earth's motion is turned round. No real object can follow that, so
    whatever links then is the work of chance: the control the answer is quoted against.
    """
    if reverse:
        visits = [{**v, "earth": -v["earth"]} for v in visits]
    n_visits = len(visits)
    by_visit: dict[int, list[dict]] = {k: [] for k in range(n_visits)}
    for s in members:
        by_visit[s["visit"]].append(s)
    if n_visits < 3:
        return []
    found: dict[tuple, dict] = {}
    plx_max = ARCSEC_PER_RADIAN / NEAREST_AU

    def grow(chosen: dict[int, dict], rest: list[int], guess: dict) -> Iterator[dict[int, dict]]:
        if not rest:
            if len(chosen) >= 3:
                yield chosen
            return
        k = rest[0]
        if len(chosen) >= 3:
            fit = fit_body(np.array([c["ra"] for c in chosen.values()]), np.array([c["dec"] for c in chosen.values()]),
                           np.array([c["pos_err"] for c in chosen.values()]), [visits[j] for j in chosen])
            if fit is None:
                return
            centre, radius = place_in_visit(fit["body"], visits[k]), 12.0
        else:
            centre, radius = guess["place"](k), guess["radius"](k)
        for c in by_visit[k]:
            if _separation(c["ra"], c["dec"], *centre) <= radius:
                yield from grow({**chosen, k: c}, rest[1:], guess)
        if n_visits - 1 >= 3 and len(chosen) + len(rest) - 1 >= 3:
            yield from grow(chosen, rest[1:], guess)        # this visit may not show it; `_judge` checks that

    for i in range(n_visits):
        for j in range(i + 1, n_visits):
            for a in by_visit[i]:
                f_i = parallax_factor(visits[i]["earth"], a["ra"], a["dec"])
                f_j = parallax_factor(visits[j]["earth"], a["ra"], a["dec"])
                lever = f_j - f_i
                reach = float(np.hypot(*lever))
                if reach < SEED_LEVERAGE:
                    break
                dt = visits[j]["year"] - visits[i]["year"]
                cosd = math.cos(math.radians(a["dec"]))
                for b in by_visit[j]:
                    moved = np.array([float(_wrap(b["ra"] - a["ra"])) * cosd * 3600.0, (b["dec"] - a["dec"]) * 3600.0])
                    if np.hypot(*moved) < MIN_JUMP_ARCSEC:
                        continue
                    plx = float(moved @ lever) / reach ** 2
                    if not 0.0 < plx <= plx_max:
                        continue
                    fastest = BOUND_FACTOR * circular_drift(ARCSEC_PER_RADIAN / plx) + DRIFT_SLACK
                    if np.hypot(*(moved - plx * lever)) > fastest * abs(dt) + 3.0 * (a["pos_err"] + b["pos_err"]):
                        continue
                    plx_slack = fastest * abs(dt) / reach     # the drift may hide in the parallax, and back

                    def place(k: int, a: dict = a, f_i: np.ndarray = f_i, plx: float = plx) -> tuple[float, float]:
                        shift = plx * (parallax_factor(visits[k]["earth"], a["ra"], a["dec"]) - f_i)
                        return (a["ra"] + shift[0] / 3600.0 / math.cos(math.radians(a["dec"])),
                                a["dec"] + shift[1] / 3600.0)

                    def radius(k: int, a: dict = a, f_i: np.ndarray = f_i, fastest: float = fastest,
                               plx_slack: float = plx_slack, i: int = i) -> float:
                        lever_k = float(np.hypot(*(parallax_factor(visits[k]["earth"], a["ra"], a["dec"]) - f_i)))
                        return fastest * abs(visits[k]["year"] - visits[i]["year"]) + plx_slack * lever_k + 15.0

                    rest = [k for k in range(n_visits) if k not in (i, j)]
                    for chosen in grow({i: a, j: b}, rest, {"place": place, "radius": radius}):
                        key = tuple(sorted((k, c["xi"], c["yi"]) for k, c in chosen.items()))
                        if key in found:
                            continue
                        verdict = _judge(chosen, visits, psf_arcsec, strength_at)
                        if verdict is not None:
                            found[key] = verdict
    # One source belongs to one object: where links share a source, the best-fitting one is kept.
    kept: list[dict] = []
    used: set[tuple] = set()
    for verdict in sorted(found.values(), key=lambda v: (-len(v["members"]), v["fit"]["chi2"])):
        ids = {(k, c["xi"], c["yi"]) for k, c in verdict["members"].items()}
        if ids & used:
            continue
        used |= ids
        kept.append(verdict)
    return kept


# ---------------------------------------------------------------------------
# The limit: what would have been found
# ---------------------------------------------------------------------------

def in_view(distance_au: float, visits: list[dict], ra: float, dec: float, fov: float) -> float:
    """Share of the picture in which a body at this distance stays inside it in every visit."""
    shift = (ARCSEC_PER_RADIAN / distance_au) * np.array([parallax_factor(v["earth"], ra, dec) for v in visits])
    years = np.array([v["year"] for v in visits])
    drift = circular_drift(distance_au) * (years.max() - years.min())
    width = fov * 3600.0 - 2.0 * EDGE_PX * pipeline.GRID_ARCSEC
    span = shift.max(axis=0) - shift.min(axis=0) + drift
    return float(np.prod(np.clip(1.0 - span / width, 0.0, 1.0)))


def clear_share(maps: dict[int, dict[str, np.ndarray]]) -> float:
    """Share of the picture where every visit has data and no more than CLEAR_NOISE times its
    usual noise: the part the quoted limit holds for. The rest is edge, gaps, saturated stars
    and the glow around bright ones, where only a brighter object would show."""
    clear = None
    for m in maps.values():
        ok = np.isfinite(m["height"]) & (m["noise"] <= CLEAR_NOISE * float(np.nanmedian(m["noise"])))
        clear = ok if clear is None else clear & ok
    return float(clear.mean()) if clear is not None else 0.0


def limit_table(visits: list[dict], noise_mjy: dict[int, float], ra: float, dec: float, fov: float,
                psf_arcsec: float, clear: float = 1.0) -> list[dict]:
    """For each distance: the faintest object the search would have found, and where it could look."""
    rows = []
    for d in DISTANCES_AU:
        plx = ARCSEC_PER_RADIAN / d
        jump = plx * max(float(np.hypot(*(parallax_factor(a["earth"], ra, dec) - parallax_factor(b["earth"], ra, dec))))
                         for a in visits for b in visits)
        share = in_view(d, visits, ra, dec, fov) * clear
        if jump < MIN_JUMP_ARCSEC or share < MIN_IN_VIEW:
            continue
        noise = sorted(noise_mjy[k] / _loss(plx, v, psf_arcsec) for k, v in enumerate(visits))
        rows.append({"distance_au": d, "jump_arcsec": round(jump, 1), "share_of_picture": round(share, 2),
                     # Three visits must show it: two at DETECT_SIGMA and a third at MEMBER_SIGMA.
                     "faintest_mjy": round(max(DETECT_SIGMA * noise[1], MEMBER_SIGMA * noise[2]), 3),
                     "smear_arcsec": round(max(plx * v["smear"] for v in visits), 1)})
    return rows


# ---------------------------------------------------------------------------
# One detector
# ---------------------------------------------------------------------------

def search_stacks(grid: WCS, n: int, images: dict[int, np.ndarray], items: dict[int, list[dict]], detector: int,
                  ra: float, dec: float, fov: float, *, catalogue: list[dict] | None = None,
                  as_planted: bool = False) -> dict:
    """Search the stacked images of one detector. `images` and `items` are keyed by visit number
    (as `training.epoch_stacks` returns them); `catalogue` is `catwise_field(...)` or None."""
    sigma_px = training.PSF_SIGMA_PX[detector]
    psf_arcsec = sigma_px * pipeline.GRID_ARCSEC
    epochs = sorted(images)
    visits = visits_from({ep: items[ep] for ep in epochs}, ra, dec, as_planted)
    maps = {k: measure_visit(images[ep], sigma_px) for k, ep in enumerate(epochs)}
    sources = {k: find_sources(maps[k], grid) for k in maps}
    members = come_and_go(sources, maps)
    mark_catalogued(members, catalogue or [], sigma_px)
    usable = [s for s in members if s["point_like"] and not s["catalogued"]]

    def strength_at(k: int, sky_ra: float, sky_dec: float) -> tuple[float, float] | None:
        x, y = grid.all_world2pix(sky_ra, sky_dec, 0)
        return _sample(maps[k], float(x), float(y))

    levers = [float(np.hypot(*(parallax_factor(a["earth"], ra, dec) - parallax_factor(b["earth"], ra, dec))))
              for a in visits for b in visits]
    can_search = len(visits) >= 3 and max(levers) >= SEED_LEVERAGE
    links = link(usable, visits, psf_arcsec, strength_at) if can_search else []
    chance = link(usable, visits, psf_arcsec, strength_at, reverse=True) if can_search else []
    noise_mjy = {k: flux_mjy(float(np.nanmedian(maps[k]["noise"])), sigma_px) for k in maps}
    clear = clear_share(maps)
    return {"detector": detector, "visits": visits, "epochs": epochs, "maps": maps, "grid": grid, "n": n,
            "sigma_px": sigma_px, "psf_arcsec": psf_arcsec, "sources": sources, "members": members,
            "usable": usable, "links": links, "chance_links": chance, "can_search": can_search,
            "noise_mjy": noise_mjy, "catalogue_answered": catalogue is not None, "clear_share": clear,
            "limit": limit_table(visits, noise_mjy, ra, dec, fov, psf_arcsec, clear) if can_search else []}


def _planted_images(ra: float, dec: float, fov: float, detector: int, grid: WCS, n: int, stacks: dict[int, dict],
                    items: dict[int, list[dict]], level: str, seed: int) -> tuple[dict[int, np.ndarray], dict]:
    """The stacks with the practice round's made-up object added: the steps of
    `training.build_training`, in its order and with its random numbers, so that the same
    level and seed give the same object as the practice screen shows."""
    if level not in training.LEVELS:
        raise spherex.BadRequest(f"level must be one of {', '.join(training.LEVELS)}")
    mjds = {ep: float(np.average([it["mjd"] for it in items[ep]], weights=[it["weight"] for it in items[ep]]))
            for ep in stacks}
    stats = {ep: sigma_clipped_stats(st["image"][np.isfinite(st["image"])], sigma=3.0, maxiters=5)
             for ep, st in stacks.items()}
    noise = float(np.median([s[2] for s in stats.values()]))
    peak = training.LEVELS[level] * noise
    limits = {ep: float(stats[ep][1] + 0.5 * peak) for ep in stacks}
    rng = np.random.default_rng([training.VERSION, seed, detector, int(round(ra * 1e4)), int(round((dec + 90) * 1e4))])
    motion = training.plant_motion(ra, dec, fov, list(mjds.values()), rng)
    motion, spots = training.place(motion, grid, n, {ep: st["image"] for ep, st in stacks.items()}, mjds, limits, rng)
    sigma_px = training.PSF_SIGMA_PX[detector]
    images = {ep: training.add_source(st["image"], *spots[ep], peak, sigma_px) for ep, st in stacks.items()}
    truth = {"distance_au": motion["distance_au"], "drift_arcsec_per_year": motion["drift_arcsec_per_year"],
             "swing_arcsec": motion["swing_arcsec"], "level": level, "seed": seed, "detector": detector,
             "peak_over_noise": training.LEVELS[level], "flux_mjy": round(flux_mjy(peak, sigma_px), 3),
             "positions": [{"epoch": ep + 1, "ra": float(p[0]), "dec": float(p[1])}
                           for ep in stacks for p in [astrometry.position_at(motion, mjds[ep])]]}
    return images, truth


# ---------------------------------------------------------------------------
# The answer
# ---------------------------------------------------------------------------

def _support(candidate: dict, other: dict) -> dict:
    """How strongly another detector shows the candidate at the places its fit predicts there."""
    seen = []
    for k, visit in enumerate(other["visits"]):
        sky = place_in_visit(candidate["body"], visit)
        x, y = other["grid"].all_world2pix(sky[0], sky[1], 0)
        got = _sample(other["maps"][k], float(x), float(y))
        seen.append({"epoch": other["epochs"][k] + 1,
                     "times_noise": round(got[0] / got[1], 1) if got and got[1] > 0 else None})
    strong = sum(1 for s in seen if s["times_noise"] is not None and s["times_noise"] >= SUPPORT_SIGMA)
    return {"detector": other["detector"], "visits": seen, "seen": strong >= 2}


def _candidate(verdict: dict, field: dict, others: list[dict], truth: dict | None) -> dict:
    fit, body = verdict["fit"], verdict["body"]
    plx, plx_err = body["parallax"] / 1000.0, fit["parallax_err_arcsec"]
    distance = verdict["distance_au"]
    low = ARCSEC_PER_RADIAN / (plx + plx_err)
    high = ARCSEC_PER_RADIAN / (plx - plx_err) if plx > plx_err else None
    positions = []
    for k, s in sorted(verdict["members"].items()):
        positions.append({"epoch": field["epochs"][k] + 1,
                          "date": Time(field["visits"][k]["mjd"], format="mjd").iso[:10],
                          "ra": round(s["ra"], 6), "dec": round(s["dec"], 6),
                          "x": round(s["x"], 2), "y": round(field["n"] - 1 - s["y"], 2),     # y from the top (PNG)
                          "times_noise": round(s["strength"], 1),
                          "flux_mjy": round(flux_mjy(s["height"], field["sigma_px"]), 3),
                          "misfit_arcsec": round(fit["misfit_arcsec"][sorted(verdict["members"]).index(k)], 2),
                          "width_ratio": round(s["width_ratio"], 2)})
    support = [_support(verdict, o) for o in others]
    cautions = []
    if not field["catalogue_answered"]:
        cautions.append("The CatWISE2020 catalogue did not answer, so known infrared sources at these places were "
                        "not ruled out.")
    if others and not any(s["seen"] for s in support):
        cautions.append("It is seen in one detector only. A real object should show in the neighbouring detector.")
    if not others:
        cautions.append("Only one detector was searched, so nothing confirms it.")
    if len(field["chance_links"]) >= 1:
        cautions.append(f"The same search with the Earth's motion reversed made {len(field['chance_links'])} "
                        "link(s) in this picture, so a link here can be chance.")
    if verdict["skipped"]:
        cautions.append("Not every visit shows it: " + "; ".join(
            f"visit {field['epochs'][s['visit']] + 1}, {s['reason']}" for s in verdict["skipped"]) + ".")
    out = {"detector": field["detector"], "distance_au": round(distance),
           "distance_range_au": [round(low), round(high) if high else None],
           "parallax_arcsec": round(plx, 2), "jump_arcsec": round(verdict["jump_arcsec"], 1),
           "drift_arcsec_per_year": round(verdict["drift_arcsec_per_year"], 2),
           "circular_drift_arcsec_per_year": round(circular_drift(distance), 2),
           "chi2": round(fit["chi2"], 2), "dof": fit["dof"], "positions": positions, "support": support,
           # What /api/frames takes to follow it: the page can show the object with its marker.
           "follow": {"ra": round(body["ra"], 6), "dec": round(body["dec"], 6), "pmra": round(body["pmra"], 1),
                      "pmdec": round(body["pmdec"], 1), "parallax": round(body["parallax"], 1),
                      "pm_epoch": round(body["ref_epoch"], 4)},
           "verdict": "caution" if cautions else "clean", "cautions": cautions}
    if truth is not None:
        nearest = min(_separation(p["ra"], p["dec"], t["ra"], t["dec"])
                      for p in positions for t in truth["positions"] if t["epoch"] == p["epoch"])
        out["is_planted_object"] = bool(truth["detector"] == field["detector"]
                                        and nearest <= training.FOUND_WITHIN_ARCSEC)
    return out


def _answer(candidates: list[dict], fields: list[dict], best_limit: list[dict], truth: dict | None) -> str:
    if not any(f["can_search"] for f in fields):
        n = max(len(f["visits"]) for f in fields)
        return (f"This patch cannot be searched for a distant world yet: it has {n} visit(s), and the search needs "
                "at least three, from both sides of the Earth's orbit.")
    if truth is not None:
        got = [c for c in candidates if c.get("is_planted_object")]
        if got:
            return (f"SIMULATION. The search found the planted object and puts it {got[0]['distance_au']:,} times as "
                    f"far from the Sun as the Earth is. It was planted at {truth['distance_au']:,.0f}.")
        seen = sorted((p["times_noise"] for p in truth["positions"] if p.get("times_noise") is not None), reverse=True)
        why = ""
        if len(seen) >= 3 and (seen[1] < DETECT_SIGMA or seen[2] < MEMBER_SIGMA):
            why = (f" It stands {', '.join(str(v) for v in seen)} times above the noise in the visits; the search "
                   f"needs {DETECT_SIGMA:.0f} in two of them and {MEMBER_SIGMA:.0f} in a third.")
        return ("SIMULATION. The search did not find the planted object." + (why or " That happens when it lies "
                "in the glow of a star or on a catalogued source."))
    if candidates:
        c = candidates[0]
        return (f"{len(candidates)} candidate(s). The strongest fits an object about {c['distance_au']:,} times as far "
                "from the Sun as the Earth is. A candidate is not a detection: read the cautions with it.")
    if not best_limit:
        return "Nothing was found, and this picture is too small for an object at any distance to stay in view."
    near, far = best_limit[0], best_limit[-1]
    deepest = min(best_limit, key=lambda r: r["faintest_mjy"])
    return ("Nothing here moves the way a distant world must. An object between "
            f"{near['distance_au']:,} and {far['distance_au']:,} times the Earth-Sun distance would have been found "
            f"if it were brighter than about {deepest['faintest_mjy']} mJy (at the best distance; the table gives "
            "every distance) and stayed inside this picture.")


def distant_search(ra: float, dec: float, fov: float = 0.2, detectors: tuple[int, ...] = (5, 6), *,
                   planted: dict | None = None, catalogues: bool = True,
                   progress: Callable[[int], None] | None = None) -> dict:
    """Search a field for an object far out in the solar system. See the module text.

    `planted` = {"level": "easy" | "medium" | "hard", "seed": int, "detector": int}: the
    practice round's made-up object is added to that detector first. The answer then says
    SIMULATION, carries `planted` with the truth, and is kept apart from real answers.
    """
    if not 0.05 <= fov <= 0.5:
        raise spherex.BadRequest("fov must be between 0.05 and 0.5 degrees")
    if not detectors or any(d not in (1, 2, 3, 4, 5, 6) for d in detectors):
        raise spherex.BadRequest("detectors must be numbers from 1 to 6")
    simulated = planted is not None
    tag = f"d{VERSION},v{pipeline.VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{''.join(map(str, detectors))}"
    if planted is not None:
        if planted.get("detector") not in detectors:
            raise spherex.BadRequest("the planted object's detector must be one of the detectors searched")
        tag += f",t{training.VERSION},{planted['level']},{planted['seed']},{planted['detector']}"
    name = ("simulation-" if simulated else "real-") + hashlib.sha1(tag.encode()).hexdigest()[:16] + ".json"
    cache_file = DISTANT_DIR / name
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    catalogue: list[dict] | None = None
    catalogue_error = None
    if catalogues:
        try:
            catalogue = catwise_field(ra, dec, fov)
        except Exception as e:  # noqa: BLE001 - any failure means "the catalogue did not answer"
            catalogue_error = f"{type(e).__name__}: {e}"[:200]

    fields: list[dict] = []
    failures: list[str] = []
    truth: dict | None = None
    for det in detectors:
        if progress:
            progress(det)
        grid, n, stacks, items, failed = training.epoch_stacks(ra, dec, fov, det)
        failures += failed
        if not stacks:
            continue
        images = {ep: st["image"] for ep, st in stacks.items()}
        if planted is not None and planted["detector"] == det:
            if len(stacks) < 2:
                raise spherex.BadRequest("A planted object needs at least two visits of this position in this "
                                         "detector.")
            images, truth = _planted_images(ra, dec, fov, det, grid, n, stacks, items, planted["level"],
                                            int(planted["seed"]))
        fields.append(search_stacks(grid, n, images, items, det, ra, dec, fov, catalogue=catalogue,
                                    as_planted=simulated))
        if truth is not None and truth["detector"] == det:
            # How strongly each visit shows the planted object at its true place: why it was or was not found.
            for k, spot in enumerate(truth["positions"]):
                x, y = grid.all_world2pix(spot["ra"], spot["dec"], 0)
                got = _sample(fields[-1]["maps"][k], float(x), float(y))
                spot["times_noise"] = round(got[0] / got[1], 1) if got and got[1] > 0 else None
    if not fields:
        raise spherex.BadRequest("SPHEREx has no images of this position in the detectors asked for.")

    candidates = [_candidate(v, f, [o for o in fields if o is not f], truth) for f in fields for v in f["links"]]
    # The same object found in two detectors is one candidate: keep the stronger, name both.
    merged: list[dict] = []
    for c in sorted(candidates, key=lambda c: -sum(p["times_noise"] for p in c["positions"])):
        twin = next((m for m in merged if m["detector"] != c["detector"] and any(
            _separation(p["ra"], p["dec"], q["ra"], q["dec"]) <= 8.0 and p["epoch"] == q["epoch"]
            for p in c["positions"] for q in m["positions"])), None)
        if twin is not None:
            twin["also_found_in_detectors"] = sorted({*twin.get("also_found_in_detectors", []), c["detector"]})
        else:
            merged.append(c)
    merged.sort(key=lambda c: (c["verdict"] != "clean", -sum(p["times_noise"] for p in c["positions"])))

    # The limit at each distance: the better of the detectors searched.
    best: dict[int, dict] = {}
    for f in fields:
        for row in f["limit"]:
            if row["distance_au"] not in best or row["faintest_mjy"] < best[row["distance_au"]]["faintest_mjy"]:
                best[row["distance_au"]] = {**row, "detector": f["detector"]}
    best_limit = [best[d] for d in sorted(best)]

    result: dict[str, Any] = {
        "simulation": simulated, "ra": ra, "dec": dec, "fov": fov, "detectors": [f["detector"] for f in fields],
        "status": ("cannot_search" if not any(f["can_search"] for f in fields)
                   else "candidates" if merged else "nothing_found"),
        "answer": _answer(merged, fields, best_limit, truth),
        "candidates": merged, "limit": best_limit,
        "chance": {"links_with_earth_reversed": sum(len(f["chance_links"]) for f in fields),
                   "note": "Links found by the same search with the Earth's motion reversed. Nothing real can "
                           "follow that, so this is how many links chance alone makes in this picture."},
        "per_detector": [{
            "detector": f["detector"], "can_search": f["can_search"],
            "visits": [{"epoch": f["epochs"][k] + 1, "date": Time(v["mjd"], format="mjd").iso[:10],
                        "date_start": Time(v["mjd_start"], format="mjd").iso[:10],
                        "date_end": Time(v["mjd_end"], format="mjd").iso[:10], "n_exposures": v["n_exposures"],
                        "sources": len(f["sources"][k]),
                        "come_and_go": sum(1 for s in f["members"] if s["visit"] == k),
                        "faintest_mjy": round(DETECT_SIGMA * f["noise_mjy"][k], 3),      # 5 times this visit's noise
                        "smear_per_arcsec_of_parallax": round(v["smear"], 4)}
                       for k, v in enumerate(f["visits"])],
            "come_and_go": len(f["members"]),
            "set_aside_catalogued": sum(1 for s in f["members"] if s["catalogued"]),
            "set_aside_not_point_like": sum(1 for s in f["members"] if not s["point_like"] and not s["catalogued"]),
            "linked_from": len(f["usable"]), "links": len(f["links"]), "chance_links": len(f["chance_links"]),
            "clear_share": round(f["clear_share"], 2), "limit": f["limit"]} for f in fields],
        "catalogue": {"name": "CatWISE2020", "asked": catalogues, "answered": catalogue is not None,
                      "sources_in_field": len(catalogue) if catalogue is not None else None, "error": catalogue_error},
        "failures": failures, "limits": LIMITS_TEXT,
        "method": ("Sources are found in the stacked image of each visit. Those missing from the same place in "
                   "another visit are linked across visits wherever one object at one distance, drifting no faster "
                   "than a bound orbit allows, explains every place. The size of the jump between visits gives "
                   "the distance."),
        "credit": pipeline.CREDIT + "; CatWISE2020 (NASA/IPAC IRSA)",
    }
    if simulated:
        result["notice"] = training.NOTICE
        result["planted"] = truth
    if not failures and (catalogue is not None or not catalogues):      # only a complete answer is kept
        spherex.write_json(cache_file, result, indent=1)
    return result

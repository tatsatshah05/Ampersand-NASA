"""A sweep of the Milky Way's plane for infrared sources that appeared between SPHEREx visits.

The question: does a source exist that is bright in one SPHEREx visit and absent in
another, that no catalogue lists and that nobody has reported? In the plane of the Galaxy,
dust hides eruptions from optical surveys and SPHEREx is the only telescope watching the
whole infrared sky since NEOWISE ended (August 2024). `docs/sweep.md` explains the
reasoning and the results for readers who are not astronomers.

The method, one *tile* (a few images of detector 6, 4.4 to 5.0 micrometres) at a time:

1. `choose_images`: from the exposure list at the tile centre, per epoch (a run of visits
   with no gap longer than 30 days) the best centred image and a second one at least a day
   away where there is one.
2. `Img`: whole detector images (zodiacal light removed, flagged pixels masked, saturated
   pixels kept as lower limits), converted to millijanskys per pixel.
3. `detect`: bright point-like peaks in every image (robust block background, aperture sum
   in a circle of 2.5 pixels, the project's own photometry circle).
4. `Img.measure`: a forced measurement of every source at the same sky position in every
   image that covers it: no catalogue matching, so a faint counterpart is never mistaken
   for no counterpart.
5. `change_test` and `veto`: keep sources at least ten times brighter in one epoch than in
   another (or absent there) in every image of the epoch, and kill glitches, movers, edges,
   neighbours' light, saturation residue and ghost risk, counting each kill.
6. `classify`: ask AllWISE, CatWISE2020, 2MASS, Gaia DR3, SIMBAD and AAVSO VSX about the
   survivors (the query functions are those of `backend/search.py`).

A survivor with no catalogue counterpart is only ever a candidate.
"""
from __future__ import annotations

import io
import json
import logging
import math
import re
import time
import warnings
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning
from astropy.wcs.utils import proj_plane_pixel_area
from scipy.ndimage import correlate, label, map_coordinates, maximum_filter, uniform_filter
from scipy.spatial import cKDTree

from . import neowise, photometry, pipeline, search, spherex

warnings.simplefilter("ignore", FITSFixedWarning)
logging.getLogger("astropy").setLevel(logging.ERROR)

VERSION = 1
SWEEP_DIR = spherex.CACHE / "sweep_work"        # tile results, exposure lists, pictures in progress
DETECTOR = 6
FULL_SIZE_DEG = 4.2              # larger than the detector (3.5 degrees): the box is clipped to the image

# --- thresholds. Every number here is a choice, explained in docs/sweep.md ---------------------------------------
EPOCH_GAP_DAYS = 30.0
MIN_PARTNER_DAYS = 1.0          # the second image of an epoch should be at least this much later or earlier
MAX_CENTRE_SEP_DEG = 1.6        # an image whose centre is further than this from the tile centre is not used
APERTURE_PX = photometry.APERTURE_PX     # 2.5 native pixels
SKY_PX = photometry.SKY_PX               # ring 14 to 20 pixels
EDGE_PX = int(SKY_PX[1]) + 3             # no measurement nearer than this to the image edge
BLOCK_PX = 32
DETECT_MJY = 30.0               # peaks fainter than this are not looked for
DETECT_SIGMA = 8.0              # and must stand this far above the local scatter
MERGE_ARCSEC = 9.0              # detections in different images closer than this are one source
SAT_MERGE_PX = 3.0
SAT_SELF_PX = 2.0               # a saturated clump this close (12 arcsec) to a source is its own core
MAX_FLAGGED_SHARE = 0.2         # share of the aperture that may be flagged (left out and scaled up)
RATIO = 10.0                    # "at least ten times brighter"
ABSENT_SIGMA = 3.0              # "absent" means below this times the local noise
SYSTEMATIC = photometry.SYSTEMATIC
EDGE_VETO_PX = 30.0
NEIGHBOUR_PX = 3.0              # a much brighter neighbour this close (18 arcsec) swamps a source
NEIGHBOUR_RATIO = 2.0
SAT_RESIDUE_PX = 15.0           # saturated pixels this close (92 arcsec): bloom and wings
GHOST_RADIUS_PX = 300.0         # a very bright star this close could throw a reflection
GHOST_FLUX_MJY = 1000.0
GHOST_MOVE_PX = 100.0           # the star must sit this much elsewhere on the detector in the second image
SHAPE_RANGE = (0.45, 1.8)       # peak-to-flux ratio of the source relative to the median star of its image
CELL_DEG = 0.1
COVER_STEP_PX = 20
# SIMBAD object types (lower case) that mean an eruption or an accreting binary: novae, cataclysmic variables,
# dwarf novae, nova-likes, supernovae, X-ray binaries, eruptive variables, FU Ori stars, transient events.
KNOWN_ERUPTION_TYPES = frozenset(("no*", "cv*", "dn*", "nl*", "sn*", "xb*", "lxb", "hxb", "er*", "fu*", "ev"))
VSX_ERUPTIVE = re.compile(r"^(N|NA|NB|NC|NL|NR|UG|UGSS|UGSU|UGZ|UGWZ|SN|ZAND|IN|FU|EXOR|WD|AM|DQ|V838)(\b|[:/|+(])")


# --- exposure lists -----------------------------------------------------------------------------------------------

def exposure_list(ra: float, dec: float) -> list[dict[str, Any]]:
    """Detector 6 images that cover (ra, dec), oldest first, with each image's centre. Cached for a day."""
    key = f"{ra:.4f}_{dec:.4f}"
    cache = SWEEP_DIR / "lists" / f"d{DETECTOR}_{key}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return json.loads(cache.read_text())
    seen: dict[str, dict[str, Any]] = {}
    for coll in spherex.COLLECTIONS:
        raw = spherex.http_get(spherex.SIA_URL, {"COLLECTION": coll, "POS": f"circle {ra} {dec} 0.01"})
        table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
        for row in table:
            if int(str(row["energy_bandpassname"])[-1]) != DETECTOR:
                continue
            obs_id = str(row["obs_id"])
            seen.setdefault(obs_id, {
                "obs_id": obs_id, "detector": DETECTOR, "mjd": float(row["t_min"]), "exptime": float(row["t_exptime"]),
                "url": str(row["access_url"]), "collection": str(row["obs_collection"]),
                "wave_min": float(row["em_min"]) * 1e6, "wave_max": float(row["em_max"]) * 1e6,
                "s_ra": float(row["s_ra"]), "s_dec": float(row["s_dec"])})
    out = sorted(seen.values(), key=lambda e: e["mjd"])
    spherex.write_json(cache, out)
    return out


def sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Angular separation in degrees (haversine)."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    h = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(h))))


def visit_of(obs_id: str) -> str:
    """The pointing an exposure belongs to: its obs_id without the trailing exposure number."""
    return obs_id.rsplit("_", 1)[0]


def group_epochs(exposures: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Exposures (any order) split into epochs: a gap longer than EPOCH_GAP_DAYS starts a new one."""
    ordered = sorted(exposures, key=lambda e: e["mjd"])
    epochs: list[list[dict[str, Any]]] = []
    for e in ordered:
        if epochs and e["mjd"] - epochs[-1][-1]["mjd"] <= EPOCH_GAP_DAYS:
            epochs[-1].append(e)
        else:
            epochs.append([e])
    return epochs


def choose_images(exposures: list[dict[str, Any]], ra: float, dec: float,
                  max_sep: float = MAX_CENTRE_SEP_DEG) -> list[dict[str, Any]]:
    """The images one tile uses: per epoch the best centred image (role "anchor") and a second one.

    The second ("partner") is the best centred image at least MIN_PARTNER_DAYS from the anchor and
    no worse than 0.8 degrees further out. If there is none, the best centred one of another
    pointing; if there is none, the epoch has one image only. Epochs without an image within
    `max_sep` degrees of the centre are left out. Returns the exposures with `epoch`, `role`,
    `sep_deg` and `gap_days` added, in time order.
    """
    out: list[dict[str, Any]] = []
    for n, epoch in enumerate(group_epochs(exposures)):
        near = []
        for e in epoch:
            s = sep_deg(e["s_ra"], e["s_dec"], ra, dec)
            if s <= max_sep:
                near.append({**e, "sep_deg": s})
        if not near:
            continue
        near.sort(key=lambda e: e["sep_deg"])
        anchor = {**near[0], "epoch": n, "role": "anchor", "gap_days": 0.0}
        out.append(anchor)
        rest = [e for e in near[1:] if e["sep_deg"] <= anchor["sep_deg"] + 0.8]
        later = [e for e in rest if abs(e["mjd"] - anchor["mjd"]) >= MIN_PARTNER_DAYS]
        other = [e for e in rest if visit_of(e["obs_id"]) != visit_of(anchor["obs_id"])]
        pick = (later or other)[0] if (later or other) else None
        if pick is not None:
            out.append({**pick, "epoch": n, "role": "partner", "gap_days": pick["mjd"] - anchor["mjd"]})
    return sorted(out, key=lambda e: e["mjd"])


# --- one image ----------------------------------------------------------------------------------------------------

def _disk(radius: float) -> np.ndarray:
    n = int(math.ceil(radius))
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    return (np.hypot(xx, yy) <= radius).astype(np.float32)


_DISK = _disk(APERTURE_PX)
_SUB = (np.arange(4) + 0.5) / 4 - 0.5
_AP_HALF = 4


def aperture_weights(fx: float, fy: float, radius: float = APERTURE_PX) -> np.ndarray:
    """Fraction of each pixel of a 9 x 9 window inside a circle whose centre is (fx, fy) from the middle pixel."""
    o = np.arange(-_AP_HALF, _AP_HALF + 1)
    xx = o[None, :, None, None] + _SUB[None, None, None, :] - fx
    yy = o[:, None, None, None] + _SUB[None, None, :, None] - fy
    return ((xx ** 2 + yy ** 2) <= radius ** 2).mean(axis=(2, 3))


def clipped(values: np.ndarray, sigma: float = 3.0, rounds: int = 3) -> tuple[float, float]:
    """Median and scatter (1.4826 x median absolute deviation) after clipping at `sigma` scatters."""
    v = values[np.isfinite(values)]
    if v.size < 20:
        return float("nan"), float("nan")
    m, s = float(np.median(v)), float("nan")
    for _ in range(rounds):
        s = 1.4826 * float(np.median(np.abs(v - m)))
        if s <= 0:
            break
        keep = np.abs(v - m) < sigma * s
        if keep.all():
            break
        v = v[keep]
        m = float(np.median(v))
    return m, 1.4826 * float(np.median(np.abs(v - m)))


@dataclass
class Img:
    """One whole detector image in millijanskys per pixel, with its masks."""
    path: Path
    obs_id: str
    mjd: float
    epoch: int
    role: str
    wcs: WCS
    data: np.ndarray            # mJy per pixel, zodi removed; flagged pixels NaN; saturated pixels with a value kept
    sat: np.ndarray             # saturated by the photometry rule
    bkg: np.ndarray | None = None
    noise: np.ndarray | None = None
    roll_deg: float = 0.0
    centre: tuple[float, float] = (0.0, 0.0)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape

    @classmethod
    def load(cls, path: Path, exp: dict[str, Any]) -> Img:
        with fits.open(path) as h:
            header = h["IMAGE"].header
            image = h["IMAGE"].data.astype(np.float32)
            flags = h["FLAGS"].data.astype(np.int32)
            variance = h["VARIANCE"].data.astype(np.float32)
            zodi = h["ZODI"].data.astype(np.float32)
        wcs = WCS(header)
        data = image - zodi
        data[pipeline.impossible_pixels(image, variance)] = np.nan
        sat = photometry.saturated_pixels(flags, data)
        bad = ((flags & photometry.PHOTOMETRY_BAD) != 0) & ~sat
        data[bad] = np.nan
        data *= np.float32(proj_plane_pixel_area(wcs) * (np.pi / 180.0) ** 2 * 1e9)
        ny, nx = data.shape
        x0, y0 = nx / 2, ny / 2
        ra0, dec0 = (float(v) for v in wcs.all_pix2world(x0, y0, 0))
        x1, y1 = wcs.all_world2pix(ra0, dec0 + 0.05, 0)
        roll = math.degrees(math.atan2(float(x1) - x0, float(y1) - y0))
        return cls(path=path, obs_id=exp["obs_id"], mjd=float(header["MJD-AVG"]), epoch=int(exp["epoch"]),
                   role=str(exp["role"]), wcs=wcs, data=data, sat=sat, roll_deg=roll, centre=(ra0, dec0))

    def prepare(self) -> None:
        """Background and scatter maps from 32 x 32 pixel blocks (clipped median of the valid pixels)."""
        ny, nx = self.shape
        by, bx = ny // BLOCK_PX, nx // BLOCK_PX
        d = np.where(self.sat, np.nan, self.data)[:by * BLOCK_PX, :bx * BLOCK_PX]
        blocks = d.reshape(by, BLOCK_PX, bx, BLOCK_PX).transpose(0, 2, 1, 3).reshape(by, bx, BLOCK_PX ** 2)
        med = np.full((by, bx), np.nan, dtype=np.float32)
        sig = np.full((by, bx), np.nan, dtype=np.float32)
        for j in range(by):
            for i in range(bx):
                med[j, i], sig[j, i] = clipped(blocks[j, i])
        fill_m, fill_s = np.nanmedian(med), np.nanmedian(sig)
        med = np.where(np.isfinite(med), med, fill_m)
        sig = np.where(np.isfinite(sig), sig, fill_s)
        yy, xx = np.mgrid[0:ny, 0:nx]
        cy, cx = (yy - (BLOCK_PX - 1) / 2) / BLOCK_PX, (xx - (BLOCK_PX - 1) / 2) / BLOCK_PX
        self.bkg = map_coordinates(med, [cy, cx], order=1, mode="nearest").astype(np.float32)
        self.noise = map_coordinates(sig, [cy, cx], order=1, mode="nearest").astype(np.float32)

    def inside(self, x: float, y: float, margin: float = EDGE_PX) -> bool:
        ny, nx = self.shape
        return bool(margin <= x < nx - margin and margin <= y < ny - margin)

    def sky_to_pix(self, ra: np.ndarray | float, dec: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
        x, y = self.wcs.all_world2pix(ra, dec, 0, quiet=True)
        return np.atleast_1d(x), np.atleast_1d(y)

    def pix_to_sky(self, x: np.ndarray | float, y: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
        ra, dec = self.wcs.all_pix2world(x, y, 0)
        return np.atleast_1d(ra), np.atleast_1d(dec)

    def measure(self, ra: float, dec: float) -> dict[str, Any]:
        """Forced aperture brightness at a sky position: flux in mJy and its error, or why there is none.

        A circle of 2.5 pixels (as `photometry.measure`) minus the clipped median of a ring 14 to 20
        pixels out. Flagged pixels (up to MAX_FLAGGED_SHARE of the circle) are left out and the
        rest scaled up. `status`: "ok", "saturated" (a lower limit: the saturated pixels' light is
        missing or partly there), "flagged", "edge" (no room for the ring, or off the image).
        """
        x, y = (float(v[0]) for v in self.sky_to_pix(ra, dec))
        return self.measure_xy(x, y)

    def measure_xy(self, x: float, y: float) -> dict[str, Any]:
        out: dict[str, Any] = {"x": x, "y": y, "status": "edge", "flux": None, "err": None, "peak_ratio": None,
                               "sky": None}
        if not (np.isfinite(x) and np.isfinite(y)) or not self.inside(x, y, 0.0):
            out["status"] = "off"
            return out
        if not self.inside(x, y):
            return out
        xi, yi = int(round(x)), int(round(y))
        h = int(SKY_PX[1]) + 1
        win = self.data[yi - h:yi + h + 1, xi - h:xi + h + 1]
        swin = self.sat[yi - h:yi + h + 1, xi - h:xi + h + 1]
        gy, gx = np.mgrid[-h:h + 1, -h:h + 1]
        r = np.hypot(gx + xi - x, gy + yi - y)
        ring = (r >= SKY_PX[0]) & (r < SKY_PX[1]) & ~swin
        sky, sig = clipped(win[ring])
        if not np.isfinite(sky) or not np.isfinite(sig):
            out["status"] = "nodata"
            return out
        w = aperture_weights(x - xi, y - yi)
        core = win[h - _AP_HALF:h + _AP_HALF + 1, h - _AP_HALF:h + _AP_HALF + 1]
        score = swin[h - _AP_HALF:h + _AP_HALF + 1, h - _AP_HALF:h + _AP_HALF + 1]
        in_ap = w > 0
        empty = ~np.isfinite(core) & in_ap
        flagged_share = float(np.sum(w[empty])) / float(np.sum(w[in_ap]))
        saturated = bool((score & in_ap).any())
        out["sky"], out["sky_sigma"] = sky, sig
        if flagged_share > MAX_FLAGGED_SHARE:
            out["status"] = "saturated" if saturated else "flagged"
            if not saturated:
                return out
        use = in_ap & np.isfinite(core)
        scale = float(np.sum(w[in_ap])) / float(np.sum(w[use])) if not saturated else 1.0
        total = float(np.sum(w[use] * (core[use] - sky))) * scale
        n_eff = float(w[in_ap].sum())
        err = sig * math.sqrt(n_eff * (1.0 + n_eff / max(int(ring.sum()), 1)))
        out["flux"] = total
        out["err"] = float(math.hypot(err, SYSTEMATIC * abs(total)))
        out["status"] = "saturated" if saturated else "ok"
        sub = win[h - 1:h + 2, h - 1:h + 2] - sky
        peak = float(np.nanmax(sub)) if np.isfinite(sub).any() else float("nan")
        out["peak_ratio"] = peak / total if total > 0 and np.isfinite(peak) else None
        return out

    def detect(self, min_mjy: float = DETECT_MJY, sigma: float = DETECT_SIGMA) -> list[dict[str, Any]]:
        """Bright point-like peaks: the aperture sum above the local level of the surroundings.

        The surroundings are a box of 21 x 21 pixels without the central 9 x 9 (their mean, so a
        patch of diffuse glow raises both and cancels). A peak is a maximum within 5 x 5 pixels
        whose excess exceeds `min_mjy` and `sigma` times the local scatter. Saturated stars are
        found as clumps of saturated pixels (their cores hold no usable number) and listed with
        `saturated` true.
        """
        assert self.bkg is not None and self.noise is not None
        d = np.where(np.isfinite(self.data), self.data - self.bkg, 0.0).astype(np.float32)
        total = correlate(d, _DISK, mode="constant")
        big = uniform_filter(d, 21, mode="constant") * 441.0
        small = uniform_filter(d, 9, mode="constant") * 81.0
        local = (big - small) / (441.0 - 81.0)
        excess = total - float(_DISK.sum()) * local
        err = self.noise * math.sqrt(float(_DISK.sum()) * (1.0 + float(_DISK.sum()) / 360.0))
        edge = EDGE_PX
        peaks = (excess == maximum_filter(excess, size=5)) & (excess > min_mjy) & (excess > sigma * err)
        peaks[:edge], peaks[-edge:], peaks[:, :edge], peaks[:, -edge:] = False, False, False, False
        ys, xs = np.nonzero(peaks)
        found: list[dict[str, Any]] = []
        if xs.size:
            oy, ox = np.mgrid[-1:2, -1:2]
            patch = np.clip(d[ys[:, None, None] + oy, xs[:, None, None] + ox], 0, None)
            wsum = patch.sum(axis=(1, 2))
            good = wsum > 0
            cx = xs + (patch * ox).sum(axis=(1, 2)) / np.where(good, wsum, 1.0)
            cy = ys + (patch * oy).sum(axis=(1, 2)) / np.where(good, wsum, 1.0)
            found = [{"x": float(a), "y": float(b), "saturated": False, "excess": float(e)}
                     for a, b, e, g in zip(cx, cy, excess[ys, xs], good, strict=True) if g]
        # Saturated clumps: the cores are empty or flagged and their light is spread over many pixels.
        lab, n = label(self.sat)
        if n:
            sizes = np.bincount(lab.ravel(), minlength=n + 1)[1:]
            yy, xx = np.nonzero(lab)
            ids = lab[yy, xx]
            sx = np.bincount(ids, weights=xx, minlength=n + 1)[1:] / sizes
            sy = np.bincount(ids, weights=yy, minlength=n + 1)[1:] / sizes
            found += [{"x": float(a), "y": float(b), "saturated": True, "n_pixels": int(c)}
                      for a, b, c in zip(sx, sy, sizes, strict=True)
                      if EDGE_PX <= a < self.shape[1] - EDGE_PX and EDGE_PX <= b < self.shape[0] - EDGE_PX]
        # A peak on the bloom of a saturated clump is the clump's own.
        sat_xy = np.array([[f["x"], f["y"]] for f in found if f["saturated"]]).reshape(-1, 2)
        if sat_xy.size:
            tree = cKDTree(sat_xy)
            found = [f for f in found if f["saturated"] or tree.query([f["x"], f["y"]])[0] > SAT_MERGE_PX + 2]
        if found:
            ra, dec = self.pix_to_sky(np.array([f["x"] for f in found]), np.array([f["y"] for f in found]))
            for f, a, b in zip(found, ra, dec, strict=True):
                f["ra"], f["dec"] = float(a), float(b)
        return found


    def stamp(self, ra: float, dec: float, half: int = 12, step_arcsec: float = 6.15) -> np.ndarray:
        """A north-up square picture (mJy per pixel, local background removed) centred on a sky position."""
        o = (np.arange(-half, half + 1)) * step_arcsec / 3600.0
        dd = dec + o[:, None] * np.ones((1, o.size))
        rr = ra - (o[None, :] * np.ones((o.size, 1))) / max(math.cos(math.radians(dec)), 1e-3)
        x, y = self.sky_to_pix(rr.ravel(), dd.ravel())
        data = np.where(np.isfinite(self.data), self.data, np.nan)
        # NaN-aware bilinear sampling: sample the values and the validity separately.
        val = map_coordinates(np.nan_to_num(data), [y, x], order=1, mode="constant", cval=np.nan)
        ok = map_coordinates(np.isfinite(data).astype(np.float32), [y, x], order=1, mode="constant", cval=0.0)
        val = np.where(ok > 0.99, val, np.nan).reshape(o.size, o.size)
        return val - float(np.nanmedian(val))


# --- the pairing and change arithmetic ---------------------------------------------------------------------------

def merge_detections(per_image: list[list[dict[str, Any]]], merge_arcsec: float = MERGE_ARCSEC) -> list[dict[str, Any]]:
    """One list of sources from the detections of every image: positions closer than `merge_arcsec` are one.

    Greedy, in order of the image list, detections of the same image never merge with each other
    unless they are closer than the radius. A source's position is the mean of its detections;
    `members` keeps each detection's image index and position, so that a survivor can be placed where
    it is bright (`bright_position`) rather than at a mean that includes a neighbour seen in the faint images.
    """
    flat = [(i, d) for i, dets in enumerate(per_image) for d in dets]
    if not flat:
        return []
    dec0 = float(np.mean([d["dec"] for _, d in flat]))
    scale = math.cos(math.radians(dec0))
    xy = np.array([[d["ra"] * scale, d["dec"]] for _, d in flat])
    tree = cKDTree(xy)
    r = merge_arcsec / 3600.0
    group = -np.ones(len(flat), dtype=int)
    n = 0
    for k in range(len(flat)):
        if group[k] >= 0:
            continue
        stack = [k]
        group[k] = n
        while stack:
            j = stack.pop()
            for m in tree.query_ball_point(xy[j], r):
                if group[m] < 0:
                    group[m] = n
                    stack.append(m)
        n += 1
    sources = []
    for g in range(n):
        members = [flat[k] for k in np.nonzero(group == g)[0]]
        sources.append({"ra": float(np.mean([d["ra"] for _, d in members])),
                        "dec": float(np.mean([d["dec"] for _, d in members])),
                        "n_detections": len(members), "saturated_detected": any(d["saturated"] for _, d in members),
                        "members": [[i, d["ra"], d["dec"]] for i, d in members]})
    return sources


def bright_position(source: dict[str, Any], bright_images: list[int]) -> tuple[float, float, str]:
    """Where a source is in the images in which it is bright: the mean of its own detections there.

    The first sweep reported the mean over every image, so a neighbour detected in the faint
    images pulled A's and C's positions 3 arcsec off (ruling, method fault 2). Unsaturated detections
    are preferred; with none, the merged position is returned and said to be so.
    """
    mine = [(ra, dec) for i, ra, dec in source.get("members", []) if i in bright_images]
    if not mine:
        return float(source["ra"]), float(source["dec"]), "merged over all images"
    return (float(np.mean([m[0] for m in mine])), float(np.mean([m[1] for m in mine])),
            f"mean of {len(mine)} detections in the bright images")


def is_valid(m: dict[str, Any] | None) -> bool:
    """A usable brightness: measured, not flagged, not off the image."""
    return m is not None and m["status"] in ("ok", "saturated") and m["flux"] is not None


def change_test(bright: list[dict[str, Any]], faint: list[dict[str, Any]], min_mjy: float = DETECT_MJY,
                ratio: float = RATIO, absent_sigma: float = ABSENT_SIGMA, min_bright: int = 1) -> dict[str, Any]:
    """Is the source at least `ratio` times brighter in every image of `bright` than in every image of `faint`?

    Each list holds measurements (see `Img.measure`) of one source in the images of one epoch.
    The conservative reading: the faintest bright-side image must reach `min_mjy` and every
    faint-side image must be at most that image's brightness over `ratio`, or absent: below
    `absent_sigma` times its own noise while the bright side is also at least ten times that
    noise. An unusable measurement (flagged, off the image) is not used; with no usable one on
    a side the answer is "no data" and never a pass. On the faint side only fully measured images
    count: a saturated one gives a lower limit, which says nothing about being faint. `min_bright` is the
    number of usable images the
    bright side needs: 1 for a plain two-visit comparison, 2 to have the source confirmed by a second image.
    """
    b = [m for m in bright if is_valid(m)]
    # A saturated measurement is a lower limit: evidence that a source is bright, never that it is absent.
    f = [m for m in faint if is_valid(m) and m["status"] == "ok"]
    out: dict[str, Any] = {"passes": False, "n_bright": len(b), "n_faint": len(f), "ratio": None}
    if len(b) < min_bright or not f:
        out["reason"] = "no data"
        return out
    fa = min(m["flux"] for m in b)
    out["bright_mjy"] = fa
    out["faint_mjy"] = max(m["flux"] for m in f)
    if fa < min_mjy:
        out["reason"] = "too faint"
        return out
    for m in f:
        small = m["flux"] <= fa / ratio
        absent = m["flux"] < absent_sigma * m["err"] and fa >= 10.0 * m["err"]
        if not (small or absent):
            out["reason"] = "not faint enough"
            out["ratio"] = fa / m["flux"] if m["flux"] > 0 else None
            return out
    top = out["faint_mjy"]
    out["ratio"] = fa / top if top > 0 else None
    out["passes"] = True
    out["reason"] = "ok"
    return out


def best_pair(epochs: dict[int, list[dict[str, Any]]], min_mjy: float = DETECT_MJY,
              min_bright: int = 1) -> dict[str, Any] | None:
    """Over every ordered pair of epochs the passing `change_test` with the brightest bright side, or None."""
    best = None
    for a, ma in epochs.items():
        for b, mb in epochs.items():
            if a == b:
                continue
            t = change_test(ma, mb, min_mjy, min_bright=min_bright)
            if t["passes"] and (best is None or t["bright_mjy"] > best["bright_mjy"]):
                best = {**t, "bright_epoch": a, "faint_epoch": b}
    return best


def cell_of(l_deg: np.ndarray | float, b_deg: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Sky cell indices (CELL_DEG square in Galactic longitude and latitude)."""
    lon = (np.asarray(l_deg) + 180.0) % 360.0 - 180.0
    return np.floor(lon / CELL_DEG).astype(int), np.floor(np.asarray(b_deg) / CELL_DEG).astype(int)


def cell_area(ci: np.ndarray, cj: np.ndarray) -> float:
    """Total area (square degrees) of cells given by their indices."""
    b = (np.asarray(cj) + 0.5) * CELL_DEG
    return float(np.sum(np.cos(np.radians(b))) * CELL_DEG ** 2)


def nearest_centre(l_deg: np.ndarray, b_deg: np.ndarray, centres: list[tuple[float, float]]) -> np.ndarray:
    """Index of the tile centre (l, b) nearest each position: a tile answers only for its own region."""
    l_r, b_r = np.radians(l_deg), np.radians(b_deg)
    best = np.full(np.shape(l_deg), -1)
    best_cos = np.full(np.shape(l_deg), -2.0)
    for k, (cl, cb) in enumerate(centres):
        c = (np.sin(b_r) * math.sin(math.radians(cb))
             + np.cos(b_r) * math.cos(math.radians(cb)) * np.cos(l_r - math.radians(cl)))
        better = c > best_cos
        best[better], best_cos[better] = k, c[better]
    return best


def coverage_cells(images: list[Img]) -> dict[int, set[tuple[int, int]]]:
    """For each epoch, the sky cells where at least one of its images has data."""
    out: dict[int, set[tuple[int, int]]] = {}
    for im in images:
        ny, nx = im.shape
        ys, xs = np.mgrid[COVER_STEP_PX // 2:ny:COVER_STEP_PX, COVER_STEP_PX // 2:nx:COVER_STEP_PX]
        valid = np.isfinite(im.data[ys, xs]) | im.sat[ys, xs]
        inner = (xs >= EDGE_PX) & (xs < nx - EDGE_PX) & (ys >= EDGE_PX) & (ys < ny - EDGE_PX)
        ok = valid & inner
        ra, dec = im.pix_to_sky(xs[ok], ys[ok])
        g = SkyCoord(ra, dec, unit="deg").galactic
        ci, cj = cell_of(g.l.deg, g.b.deg)
        out.setdefault(im.epoch, set()).update(zip(ci.tolist(), cj.tolist(), strict=True))
    return out


def covered_by_images(images: list[Img]) -> dict[tuple[int, int], dict[int, int]]:
    """For each sky cell the number of images of each epoch that cover it."""
    out: dict[tuple[int, int], dict[int, int]] = {}
    for im in images:
        for cell in coverage_cells([im]).get(im.epoch, ()):
            out.setdefault(cell, {})
            out[cell][im.epoch] = out[cell].get(im.epoch, 0) + 1
    return out


def full_cells(cover: dict[tuple[int, int], dict[int, int]]) -> set[tuple[int, int]]:
    """Cells where at least two epochs are each covered by at least two images: the method works fully there."""
    return {c for c, per in cover.items() if sum(1 for n in per.values() if n >= 2) >= 2}


# --- the catalogue answer ----------------------------------------------------------------------------------------

def w2_mjy(mag: float | None) -> float | None:
    """A W2 (4.6 micrometre) magnitude as millijanskys."""
    return None if mag is None else neowise.to_mjy(float(mag), "w2")


def k_mjy(mag: float | None) -> float | None:
    """A 2MASS Ks magnitude (zero point 666.7 Jy) as millijanskys."""
    return None if mag is None else 666.7e3 * 10 ** (-0.4 * float(mag))


def irac2_mjy(mag: float | None) -> float | None:
    """A Spitzer IRAC 4.5 micrometre magnitude (zero point 179.7 Jy) as millijanskys."""
    return None if mag is None else 179.7e3 * 10 ** (-0.4 * float(mag))


def brightness_text(row: dict[str, Any]) -> str:
    """The infrared and optical brightness a catalogue row lists, in words ("W2 13.54 mag = 0.66 mJy, Ks 13.77").

    Always converted by `w2_mjy`, `irac2_mjy`, never by hand: the first write-up of candidate A gave W2 11.6 as
    0.4 mJy, and it is 3.9 (docs/sweep/vetting/ruling.json, method fault 4).
    """
    parts = []
    if row.get("w2") is not None:
        parts.append(f"W2 {row['w2']:.2f} mag = {w2_mjy(row['w2']):.2f} mJy")
    if row.get("irac2") is not None:
        parts.append(f"[4.5] {row['irac2']:.2f} mag = {irac2_mjy(row['irac2']):.2f} mJy")
    if row.get("k") is not None:
        parts.append(f"Ks {row['k']:.2f}")
    if row.get("gmag") is not None:
        parts.append(f"G {row['gmag']:.2f}")
    return ", ".join(parts) or "no brightness listed"


# How close a catalogued star must be to be "at the place" of a SPHEREx source. Bright-state SPHEREx centroids
# agree with catalogued control stars to 0.1-0.3 arcsec (the vetting, 7-12 control stars per field), so five
# times 0.3 arcsec. The first write-up used 6.2 arcsec and called stars 3.5-4.7 arcsec from B and 4.1 arcsec
# from C "counterparts"; they are other stars (ruling, method fault 3).
AT_PLACE_ARCSEC = 1.5
# An already bright catalogued star this close still makes a survivor a "known variable": calling a known
# star a candidate is the worse mistake, so this stays wide.
KNOWN_BRIGHT_ARCSEC = 6.2
# Catalogued stars whose light can fall in the measuring circle: its radius (2.5 pixels, 15.4 arcsec) plus one
# image width (SPHEREx's PSF is about 8 arcsec across). The 437 mJy star 17 arcsec from the first position of A
# and the 40 mJy star 10 arcsec from B were inside it and were never named (method fault 3).
CIRCLE_REACH_ARCSEC = APERTURE_PX * 6.15 + 8.0


def infrared_mjy(row: dict[str, Any]) -> tuple[str, float] | None:
    """A catalogue row's 4.6 micrometre brightness (WISE W2 or Spitzer [4.5]) in mJy, or its Ks if that is all."""
    if row.get("w2") is not None:
        return "W2", float(w2_mjy(row["w2"]) or 0.0)
    if row.get("irac2") is not None:
        return "[4.5]", float(irac2_mjy(row["irac2"]) or 0.0)
    if row.get("k") is not None:
        return "Ks", float(k_mjy(row["k"]) or 0.0)
    return None


def circle_census(rows: list[dict[str, Any]], offsets: list[float], reach_arcsec: float = CIRCLE_REACH_ARCSEC,
                  at_place_arcsec: float = AT_PLACE_ARCSEC, n: int = 3) -> dict[str, Any]:
    """What lies in and around the measuring circle: the nearest rows, and the brightest whose light reaches it.

    "brightest" is by the 4.6 micrometre brightness (W2 or [4.5]) when a row has one, else by Ks; a faint-state
    reading near one of these is most likely its light, which is what the first write-up missed.
    """
    pairs = sorted(zip(offsets, rows, strict=True), key=lambda p: p[0])

    def entry(off: float, row: dict[str, Any]) -> dict[str, Any]:
        ir = infrared_mjy(row)
        return {"name": row.get("name"), "catalogue": row.get("catalogue"), "offset_arcsec": round(off, 2),
                "band": ir[0] if ir else None, "mjy": round(ir[1], 3) if ir else None, "text": brightness_text(row)}

    inside = [(o, r) for o, r in pairs if o <= reach_arcsec]
    ranked = sorted((p for p in inside if infrared_mjy(p[1]) is not None),
                    key=lambda p: (infrared_mjy(p[1])[0] == "Ks", -infrared_mjy(p[1])[1]))  # type: ignore[index]
    return {"reach_arcsec": round(reach_arcsec, 1), "at_place_arcsec": at_place_arcsec,
            "at_place": [entry(o, r) for o, r in pairs if o <= at_place_arcsec],
            "nearest": [entry(o, r) for o, r in pairs[:n]],
            "brightest_in_reach": [entry(o, r) for o, r in ranked[:n]]}


def classify(bright_mjy: float, rows: list[dict[str, Any]], offsets: list[float],
             near_arcsec: float = AT_PLACE_ARCSEC, far_arcsec: float = 12.0,
             bright_arcsec: float = KNOWN_BRIGHT_ARCSEC) -> dict[str, Any]:
    """Sort a survivor by what the catalogues say at its position.

    `rows` are catalogue rows as `backend/search.py` returns them and `offsets` each row's
    distance in arcsec from the source (positions already brought to the same epoch or not:
    the caller says). Result `kind`:

    - "known_eruption": a row within `far_arcsec` that is a nova or another eruptive type in
      SIMBAD or the AAVSO VSX (the type decides, see KNOWN_ERUPTION_TYPES and VSX_ERUPTIVE);
    - "known_variable": a catalogued star within `bright_arcsec` that was already bright (4.6
      micrometres at least 1/5 of the bright brightness in WISE or GLIMPSE, Ks likewise, or any
      variable type in SIMBAD, VSX or Gaia) and that is not an eruption;
    - "candidate": otherwise. Only rows within `near_arcsec` (AT_PLACE_ARCSEC) are named as being at
      the place; rows further out are other stars and are listed as such, never as counterparts.

    "candidate" is never more than that. The reasons are returned, with `circle`: the brightest
    catalogued stars whose light reaches the measuring circle (`circle_census`).
    """
    reasons: list[str] = []
    pairs = sorted(zip(offsets, rows, strict=True), key=lambda p: p[0])
    census = circle_census(rows, offsets, at_place_arcsec=near_arcsec)
    for off, row in pairs:
        if off > far_arcsec:
            continue
        kind = (row.get("type") or "").lower()
        cat = row.get("catalogue")
        if cat == "SIMBAD" and kind.strip() in KNOWN_ERUPTION_TYPES:
            return {"kind": "known_eruption", "reasons": [f"SIMBAD {row['name']} is type {row.get('type')} "
                                                          f"({off:.1f} arcsec away)"], "by": row, "circle": census}
        if cat == "AAVSO VSX" and VSX_ERUPTIVE.match((row.get("type") or "").split(",")[0].strip()):
            return {"kind": "known_eruption", "reasons": [f"AAVSO VSX {row['name']} is {row.get('type')} "
                                                          f"({off:.1f} arcsec away)"], "by": row, "circle": census}
    pre = []
    for off, row in pairs:
        if off > bright_arcsec:
            continue
        cat = row.get("catalogue")
        w2 = row.get("w2") if cat in ("AllWISE", "CatWISE2020") else None
        flux = w2_mjy(w2)
        if flux is not None and flux >= bright_mjy / 5.0:
            pre.append(f"{row['name']} ({cat}) W2 {w2:.2f} mag = {flux:.0f} mJy, already bright")
        elif str(cat).startswith("GLIMPSE") and (gf := irac2_mjy(row.get("irac2"))) is not None \
                and gf >= bright_mjy / 5.0:
            pre.append(f"{row['name']} ({cat}) [4.5] {row['irac2']:.2f} mag = {gf:.0f} mJy, already bright")
        elif row.get("variable"):
            pre.append(f"{row['name']} ({cat}) is listed as variable ({row.get('type')})")
        elif cat == "2MASS" and (kf := k_mjy(row.get("k"))) is not None and kf >= bright_mjy / 5.0:
            pre.append(f"{row['name']} (2MASS) Ks {row['k']:.2f} mag = {kf:.0f} mJy, already bright")
    if pre:
        return {"kind": "known_variable", "reasons": pre, "circle": census}
    within = [(o, r) for o, r in pairs if o <= near_arcsec]
    if not within:
        reasons.append(f"no row within {near_arcsec:g} arcsec in any catalogue asked")
    else:
        for off, row in within:
            reasons.append(f"{row['name']} ({row.get('catalogue')}) at {off:.1f} arcsec: {brightness_text(row)}")
    others = [(o, r) for o, r in pairs if near_arcsec < o <= bright_arcsec]
    if others:
        reasons.append("nearby but not at the place (other stars): " + "; ".join(
            f"{r['name']} at {o:.1f} arcsec, {brightness_text(r)}" for o, r in others[:3]))
    for b in census["brightest_in_reach"][:1]:
        reasons.append(f"brightest catalogued star whose light reaches the measuring circle: {b['name']} at "
                       f"{b['offset_arcsec']:.1f} arcsec, {b['text']}")
    return {"kind": "candidate", "reasons": reasons, "circle": census}


# --- evaluating a tile --------------------------------------------------------------------------------------------

STAGES = ("sources", "comparable", "changed_anchors", "killed_second_image", "single_image_only", "changed_all_images",
          "killed_edge", "killed_shape", "killed_neighbour", "killed_saturation_residue", "killed_ghost_risk",
          "survivors", "single_image_killed", "survivors_single_image")


def _epoch_lists(meas: list[list[dict[str, Any]]], meta: list[dict[str, Any]], s: int,
                 only_anchors: bool = False) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for i, m in enumerate(meta):
        if only_anchors and m["role"] != "anchor":
            continue
        if meas[i][s]["status"] == "off":
            continue
        out.setdefault(m["epoch"], []).append(meas[i][s])
    return out


def evaluate(sources: list[dict[str, Any]], meas: list[list[dict[str, Any]]], meta: list[dict[str, Any]],
             clumps: list[np.ndarray], star_ratio: list[float], keep: np.ndarray | None = None,
             min_mjy: float = DETECT_MJY) -> dict[str, Any]:
    """Run the change test and the vetoes over every source of a tile; return the tallies and the survivors.

    `meas[i][s]` is the measurement of source s in image i (`Img.measure`), `meta[i]` the image's
    `epoch`, `role`, `mjd`, `obs_id` and `shape` (rows, columns). `clumps[i]` lists the saturated
    clumps of image i as an (n, 2) array of pixel positions; `star_ratio[i]` is the median
    peak-to-flux ratio of the ordinary bright stars of image i. `keep` says which sources this tile
    answers for.

    A source is counted at the first stage of `STAGES` that stops it (the keys of `killed` hold
    their indices). "comparable" means usable measurements in at least two epochs;
    "changed_anchors" is the two-visit comparison that uses only the best centred image of each
    epoch (what a plain comparison of two visits would give); "changed_all_images" requires the
    change in every image of the epochs, at least two in the bright one. A source that passes the
    two-visit comparison, whose second image in the bright epoch cannot be used (flagged, empty) and
    whose single usable image passes, is counted as "single_image_only": it cannot be confirmed, but
    nothing contradicts it, so it goes through the vetoes too; those that pass are listed as
    "survivors_single_image" (and are kept apart from "survivors"), those that do not as
    "single_image_killed".
    """
    n = len(sources)
    keep = np.ones(n, dtype=bool) if keep is None else keep
    tally = dict.fromkeys(STAGES, 0)
    killed: dict[str, list[int]] = {k: [] for k in STAGES if k.startswith("killed")}
    survivors: list[dict[str, Any]] = []
    flux = np.array([[m["flux"] if is_valid(m) else np.nan for m in row] for row in meas]).reshape(len(meta), n)
    px = np.array([[m["x"] for m in row] for row in meas]).reshape(len(meta), n)
    py = np.array([[m["y"] for m in row] for row in meas]).reshape(len(meta), n)
    saturated = np.array([[m["status"] == "saturated" for m in row] for row in meas]).reshape(len(meta), n)
    strength = np.where(saturated, np.inf, flux)     # for "is this a very bright star": a saturated one is
    tree = cKDTree(np.array([[s["ra"] * math.cos(math.radians(s["dec"])), s["dec"]] for s in sources])) if n else None
    r_nb = NEIGHBOUR_PX * 6.15 / 3600.0
    for s in range(n):
        if not keep[s]:
            continue
        tally["sources"] += 1
        epochs = _epoch_lists(meas, meta, s)
        usable = {e for e, ms in epochs.items() if any(is_valid(m) for m in ms)}
        if len(usable) < 2:
            continue
        tally["comparable"] += 1
        if best_pair(_epoch_lists(meas, meta, s, only_anchors=True), min_mjy) is None:
            continue
        tally["changed_anchors"] += 1
        pair = best_pair(epochs, min_mjy, min_bright=2)
        single = False
        if pair is None:
            pair = best_pair(epochs, min_mjy, min_bright=1)
            if pair is None:
                tally["killed_second_image"] += 1
                killed["killed_second_image"].append(s)
                continue
            single = True
            tally["single_image_only"] += 1
        else:
            tally["changed_all_images"] += 1
        a = pair["bright_epoch"]
        bright_images = [i for i, m in enumerate(meta)
                         if m["epoch"] == a and meas[i][s]["status"] in ("ok", "saturated")]
        why = veto(s, sources, meas, meta, bright_images, flux, strength, px, py, clumps, star_ratio, tree, r_nb)
        if why:
            if single:
                tally["single_image_killed"] += 1
            else:
                tally[f"killed_{why}"] += 1
                killed[f"killed_{why}"].append(s)
            continue
        tally["survivors_single_image" if single else "survivors"] += 1
        gaps = sorted({round(abs(meta[i]["mjd"] - meta[j]["mjd"]), 2) for i in bright_images for j in bright_images
                       if i < j})
        b_ra, b_dec, b_how = bright_position(sources[s], bright_images)
        survivors.append({"index": s, "ra": b_ra, "dec": b_dec, "position_from": b_how,
                          "measured_at": [sources[s]["ra"], sources[s]["dec"]], "l": sources[s].get("l"),
                          "b": sources[s].get("b"), "pair": pair,
                          "direction": "brightened" if pair["bright_epoch"] > pair["faint_epoch"] else "faded",
                          "bright_images": bright_images, "single_image_only": single,
                          "bright_gap_days": gaps, "same_day_only": not any(g >= 1.0 for g in gaps),
                          "saturated": any(meas[i][s]["status"] == "saturated" for i in bright_images),
                          "measurements": [{"obs_id": meta[i]["obs_id"], "epoch": meta[i]["epoch"],
                                            "mjd": meta[i]["mjd"], "status": meas[i][s]["status"],
                                            "flux_mjy": meas[i][s]["flux"], "err_mjy": meas[i][s]["err"]}
                                           for i in range(len(meta))]})
    return {"tally": tally, "killed": killed, "survivors": survivors}


def veto(s: int, sources: list[dict[str, Any]], meas: list[list[dict[str, Any]]], meta: list[dict[str, Any]],
         bright_images: list[int], flux: np.ndarray, strength: np.ndarray, px: np.ndarray, py: np.ndarray,
         clumps: list[np.ndarray], star_ratio: list[float], tree: cKDTree | None, r_nb: float) -> str | None:
    """Why a source that passed the change test is still not believed, or None.

    Checked in this order: "edge", "shape", "neighbour", "saturation_residue", "ghost_risk". Each is
    judged in the images of the epoch in which the source is bright.
    """
    for i in bright_images:
        ny, nx = meta[i]["shape"]
        x, y = px[i, s], py[i, s]
        if not (EDGE_VETO_PX <= x < nx - EDGE_VETO_PX and EDGE_VETO_PX <= y < ny - EDGE_VETO_PX):
            return "edge"
    for i in bright_images:
        m = meas[i][s]
        if m["status"] == "ok" and m["peak_ratio"] is not None and star_ratio[i] > 0:
            rel = m["peak_ratio"] / star_ratio[i]
            if not SHAPE_RANGE[0] <= rel <= SHAPE_RANGE[1]:
                return "shape"
    sra, sdec = sources[s]["ra"], sources[s]["dec"]
    near = tree.query_ball_point([sra * math.cos(math.radians(sdec)), sdec], r_nb) if tree is not None else []
    for i in bright_images:
        mine = flux[i, s]
        for t in near:
            if t == s:
                continue
            if meas[i][t]["status"] == "saturated" or (np.isfinite(flux[i, t]) and np.isfinite(mine)
                                                       and flux[i, t] >= NEIGHBOUR_RATIO * mine):
                return "neighbour"
    for i in bright_images:
        c = clumps[i]
        if c.size:
            d = np.hypot(c[:, 0] - px[i, s], c[:, 1] - py[i, s])
            # In an image where the source has a saturated core of its own (a clump within SAT_SELF_PX) the
            # other clumps around are its own bloom; otherwise any saturated clump within SAT_RESIDUE_PX
            # (a wing, bloom or glare) means the light may not be the source's.
            if not (d <= SAT_SELF_PX).any() and (d < SAT_RESIDUE_PX).any():
                return "saturation_residue"
    return ghost_risk(s, bright_images, strength, px, py)


def ghost_risk(s: int, bright_images: list[int], strength: np.ndarray, px: np.ndarray, py: np.ndarray) -> str | None:
    """"ghost_risk" if a very bright star is near and the source cannot be shown to be independent of it.

    A reflection sits at a fixed place relative to its star on the detector, so when the star lies
    somewhere else on the detector in the second image the reflection moves on the sky. A source
    that is at the same sky position in two images in which the bright star is at least
    GHOST_MOVE_PX apart on the detector is not that star's reflection. Near a very bright star
    (GHOST_FLUX_MJY or saturated, between SAT_RESIDUE_PX and GHOST_RADIUS_PX away: closer in is its own glare,
    which the saturation-residue check handles) and without such a pair of images, the
    source is set aside as "ghost_risk".
    """
    n = strength.shape[1]
    for i in bright_images:
        near = [t for t in range(n) if t != s and strength[i, t] >= GHOST_FLUX_MJY
                and SAT_RESIDUE_PX <= math.hypot(px[i, t] - px[i, s], py[i, t] - py[i, s]) < GHOST_RADIUS_PX]
        for t in near:
            if not any(j != i and math.hypot(px[j, t] - px[i, t], py[j, t] - py[i, t]) >= GHOST_MOVE_PX
                       for j in bright_images):
                return "ghost_risk"
    return None


# --- catalogues ---------------------------------------------------------------------------------------------------

CATALOGUE_RADIUS_ARCSEC = 30.0          # beyond CIRCLE_REACH_ARCSEC: the stars whose light is in the circle
SERVICE_PAUSE_S = 0.5


def _twomass(ra: float, dec: float, radius: float, fast_only: bool) -> list[dict[str, Any]]:
    table = search._gator("fp_psc", ra, dec, radius, "designation,ra,dec,j_m,h_m,k_m")
    rows = []
    for d in table:
        sra, sdec = search._num(d["ra"]), search._num(d["dec"])
        if sra is None or sdec is None:
            continue
        rows.append({"catalogue": "2MASS", "name": f"2MASS J{search._text(d['designation'])}", "ra": sra, "dec": sdec,
                     "j": search._num(d["j_m"]), "h": search._num(d["h_m"]), "k": search._num(d["k_m"]),
                     "type": None, "variable": False})
    return rows


def _glimpse_table(table_name: str, label: str, ra: float, dec: float, radius: float) -> list[dict[str, Any]]:
    table = search._gator(table_name, ra, dec, radius, "designation,ra,dec,mag4_5,mag3_6")
    rows = []
    for d in table:
        sra, sdec = search._num(d["ra"]), search._num(d["dec"])
        if sra is None or sdec is None:
            continue
        m45 = search._num(d["mag4_5"])
        rows.append({"catalogue": label, "name": f"GLIMPSE {search._text(d['designation'])}", "ra": sra,
                     "dec": sdec, "irac2": m45, "type": None, "variable": False})
    return rows


def _glimpse(ra: float, dec: float, radius: float, fast_only: bool) -> list[dict[str, Any]]:
    """Spitzer GLIMPSE I (3.6 to 8 micrometres, longitudes 10 to 65 degrees either side, 2004 to 2005), IRSA's Gator."""
    return _glimpse_table("glimpse_s07", "GLIMPSE", ra, dec, radius)


def _glimpse2(ra: float, dec: float, radius: float, fast_only: bool) -> list[dict[str, Any]]:
    """Spitzer GLIMPSE II, the inner Galaxy (longitudes within 10 degrees of the centre, 2005 to 2006).

    The first sweep asked GLIMPSE I only and wrote "GLIMPSE does not cover this longitude" for
    candidate A at l 6.7; GLIMPSE II does, with 55 rows within 30 arcsec (ruling, method fault 4).
    """
    return _glimpse_table("glimpse2_v2cat", "GLIMPSE II", ra, dec, radius)


def _gaia(ra: float, dec: float, radius: float, fast_only: bool) -> list[dict[str, Any]]:
    """Gaia DR3 from ESA's archive; when that does not answer, the same table at IRSA (without variability classes).

    ESA's service did not answer on 2026-11-15; the vetting's reviewers used IRSA's copy.
    """
    try:
        return search._gaia(ra, dec, radius, fast_only)
    except spherex.ArchiveError:
        table = search._gator("gaia_dr3_source", ra, dec, radius, "source_id,ra,dec,phot_g_mean_mag,phot_variable_flag")
    rows = []
    for d in table:
        sra, sdec = search._num(d["ra"]), search._num(d["dec"])
        if sra is None or sdec is None:
            continue
        flag = search._text(d["phot_variable_flag"])
        rows.append({"catalogue": "Gaia DR3", "name": f"Gaia DR3 {search._text(d['source_id'])}", "ra": sra,
                     "dec": sdec, "gmag": search._num(d["phot_g_mean_mag"]), "via": "IRSA",
                     "variable": flag == "VARIABLE", "type": "variable (flag)" if flag == "VARIABLE" else None})
    return rows


SERVICES = (("Gaia DR3", _gaia), ("SIMBAD", search._simbad), ("AAVSO VSX", search._vsx),
            ("CatWISE2020", search._catwise), ("AllWISE", search._allwise), ("2MASS", _twomass),
            ("GLIMPSE", _glimpse), ("GLIMPSE II", _glimpse2))


def ask_catalogues(ra: float, dec: float, radius_arcsec: float = CATALOGUE_RADIUS_ARCSEC,
                   services: tuple[tuple[str, Any], ...] = SERVICES, tries: int = 3) -> dict[str, Any]:
    """Every catalogue's rows within `radius_arcsec` of a position, one catalogue after another.

    Each answer is cached on disk (`search._cached_query`); one that fails after `tries` goes
    into `failed` with the reason and is never replaced by an empty list. A catalogue that does
    not cover the place (GLIMPSE outside the plane) answers with no rows, and that is recorded
    as what it is: no rows.
    """
    rows: list[dict[str, Any]] = []
    answers: dict[str, Any] = {}
    failed: dict[str, str] = {}
    radius = radius_arcsec / 3600.0
    for name, fn in services:
        err = "not asked"
        for attempt in range(tries):
            try:
                key = f"{name}|{ra:.5f}|{dec:.5f}|{radius_arcsec}"
                got = search._cached_query(f"sweep_{name.replace(' ', '')}", key, partial(fn, ra, dec, radius, False))
                answers[name] = len(got)
                rows += got
                err = ""
                break
            except Exception as e:  # noqa: BLE001 - recorded, and the source then cannot be called uncatalogued
                err = f"{type(e).__name__}: {e}"
                search._down.pop(name, None)
                time.sleep(3.0 * (attempt + 1))
        if err:
            failed[name] = err
        time.sleep(SERVICE_PAUSE_S)
    offsets = []
    for r in rows:
        dx = (r["ra"] - ra) * math.cos(math.radians(dec)) * 3600.0
        dy = (r["dec"] - dec) * 3600.0
        offsets.append(math.hypot(dx, dy))
    return {"rows": rows, "offsets": offsets, "answers": answers, "failed": failed}


def classify_with_catalogues(bright_mjy: float, cat: dict[str, Any]) -> dict[str, Any]:
    """`classify`, with the rule that a catalogue that did not answer stops the word "uncatalogued"."""
    result = classify(bright_mjy, cat["rows"], cat["offsets"])
    result["catalogues_failed"] = sorted(cat["failed"])
    if cat["failed"] and result["kind"] == "candidate":
        result["kind"] = "candidate_incomplete"
        result["reasons"].append("these catalogues did not answer: " + ", ".join(sorted(cat["failed"])))
    return result


# --- pictures -----------------------------------------------------------------------------------------------------

def _grey(a: np.ndarray, vmax: float) -> np.ndarray:
    soft = max(vmax / 12.0, 1e-3)
    v = np.arcsinh(np.nan_to_num(a, nan=0.0) / soft) / np.arcsinh(vmax / soft)
    return (np.clip(v, 0, 1) * 255).astype(np.uint8)


def strip_picture(ra: float, dec: float, images: list[Img], bright_epoch: int, faint_epoch: int, path: Path,
                  title: str = "") -> None:
    """A strip of small pictures: every image used, time ordered, then the bright epoch minus the faint one.

    Each is 25 x 25 SPHEREx pixels (2.6 arcmin), north up, east left, the local sky level removed,
    drawn with one scale shared by all (set by the brightest) so that "absent" looks dark. Pixels
    with no valid data are blue. The last panel is the mean of the bright epoch's stamps minus the
    mean of the faint epoch's, drawn with the same scale.
    """
    from PIL import Image, ImageDraw

    half, zoom = 12, 6
    stamps = [im.stamp(ra, dec, half) for im in images]
    peak = max((float(np.nanmax(s[half - 2:half + 3, half - 2:half + 3])) for s in stamps
                if np.isfinite(s[half - 2:half + 3, half - 2:half + 3]).any()), default=1.0)
    vmax = max(peak, 5.0)
    mean = {e: np.nanmean([s for s, im in zip(stamps, images, strict=True) if im.epoch == e], axis=0)
            for e in (bright_epoch, faint_epoch)}
    panels = list(zip(stamps, [f"{im.obs_id} {Time(im.mjd, format='mjd').iso[:10]}" for im in images], strict=True))
    panels.append((mean[bright_epoch] - mean[faint_epoch], "bright minus faint epoch"))
    size = (2 * half + 1) * zoom
    out = Image.new("RGB", (len(panels) * (size + 6) + 6, size + 56), (20, 20, 24))
    draw = ImageDraw.Draw(out)
    draw.text((6, 4), title, fill=(230, 230, 230))
    for k, (st, label_text) in enumerate(panels):
        grey = _grey(st, vmax)
        rgb = np.stack([grey, grey, grey], axis=-1)
        rgb[~np.isfinite(st)] = (40, 60, 200)
        tile = Image.fromarray(rgb).resize((size, size), Image.Resampling.NEAREST)
        x0 = 6 + k * (size + 6)
        out.paste(tile, (x0, 24))
        draw.rectangle([x0 + size // 2 - zoom * 2, 24 + size // 2 - zoom * 2, x0 + size // 2 + zoom * 2 + zoom,
                        24 + size // 2 + zoom * 2 + zoom], outline=(255, 190, 0))
        draw.text((x0, 24 + size + 3), label_text[:30], fill=(200, 200, 200))
        if k < len(images):
            draw.text((x0, 24 + size + 15), f"epoch {images[k].epoch}", fill=(150, 150, 150))
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


# --- running a tile -----------------------------------------------------------------------------------------------

TILE_DIR = SWEEP_DIR / "tiles"


def _median_peak_ratio(img_meas: list[dict[str, Any]]) -> float:
    r = [m["peak_ratio"] for m in img_meas if m["status"] == "ok" and m["peak_ratio"] is not None
         and 60.0 <= (m["flux"] or 0) <= 600.0]
    return float(np.median(r)) if len(r) >= 20 else 0.0


def fetch_images(chosen: list[dict[str, Any]], log: Any = print) -> list[Path]:
    """The whole detector image of each chosen exposure, from S3 (IRSA as the fallback), in the cache."""
    from concurrent.futures import ThreadPoolExecutor

    def one(exp: dict[str, Any]) -> Path:
        for attempt in range(4):
            try:
                return spherex.fetch_cutout(exp, exp["s_ra"], exp["s_dec"], FULL_SIZE_DEG)
            except Exception as e:  # noqa: BLE001
                log(f"  fetch of {exp['obs_id']} failed ({type(e).__name__}: {e}); try {attempt + 2}")
                time.sleep(5.0 * (attempt + 1))
        raise spherex.ArchiveError(f"could not fetch {exp['obs_id']}")

    with ThreadPoolExecutor(3) as pool:
        return list(pool.map(one, chosen))


def run_tile(name: str, ra: float, dec: float, centres: list[tuple[float, float]] | None = None,
             index: int | None = None, pictures_dir: Path | None = None, keep_images: bool = False,
             min_mjy: float = DETECT_MJY, log: Any = print) -> dict[str, Any]:
    """Run the whole method on one tile and write `tiles/<name>.json`. Returns the result.

    `centres` and `index` make the tile answer only for the sky nearer to its own centre than to
    any other planned centre (so that overlapping tiles never count a source twice).
    """
    t0 = time.time()
    exposures = exposure_list(ra, dec)
    chosen = choose_images(exposures, ra, dec)
    result: dict[str, Any] = {"name": name, "ra": ra, "dec": dec, "version": VERSION, "min_mjy": min_mjy,
                              "images": [{k: c[k] for k in ("obs_id", "epoch", "role", "mjd", "sep_deg", "gap_days")}
                                         for c in chosen]}
    if len({c["epoch"] for c in chosen}) < 2:
        result["status"] = "fewer than two epochs with an image near the centre"
        spherex.write_json(TILE_DIR / f"{name}.json", result, indent=1)
        return result
    log(f"[{name}] {len(chosen)} images in {len({c['epoch'] for c in chosen})} epochs; fetching")
    paths = fetch_images(chosen, log)
    images = []
    detections = []
    for p, c in zip(paths, chosen, strict=True):
        im = Img.load(p, c)
        im.prepare()
        images.append(im)
        detections.append(im.detect(min_mjy))
    log(f"[{name}] detections per image: {[len(d) for d in detections]} ({time.time() - t0:.0f} s)")
    sources = merge_detections(detections)
    ras = np.array([s["ra"] for s in sources])
    decs = np.array([s["dec"] for s in sources])
    gal = SkyCoord(ras, decs, unit="deg").galactic
    for s, lo, bo in zip(sources, gal.l.deg, gal.b.deg, strict=True):
        s["l"], s["b"] = float(lo), float(bo)
    cover = covered_by_images(images)
    fullc = full_cells(cover)
    ci, cj = cell_of(gal.l.deg, gal.b.deg)
    keep = np.array([(a, b) in fullc for a, b in zip(ci.tolist(), cj.tolist(), strict=True)])
    if centres is not None and index is not None:
        keep &= nearest_centre(gal.l.deg, gal.b.deg, centres) == index
    mine_cells = [c for c in fullc]
    if centres is not None and index is not None and mine_cells:
        cl = (np.array([c[0] for c in mine_cells]) + 0.5) * CELL_DEG
        cb = (np.array([c[1] for c in mine_cells]) + 0.5) * CELL_DEG
        mine_cells = [c for c, k in zip(mine_cells, nearest_centre(cl, cb, centres), strict=True) if k == index]
    area = cell_area(np.array([c[0] for c in mine_cells]), np.array([c[1] for c in mine_cells])) if mine_cells else 0.0
    log(f"[{name}] {len(sources)} sources, {int(keep.sum())} in this tile's covered region, area {area:.2f} sq deg")
    meas = [[im.measure(s["ra"], s["dec"]) for s in sources] for im in images]
    log(f"[{name}] measured ({time.time() - t0:.0f} s)")
    meta = [{"obs_id": im.obs_id, "epoch": im.epoch, "role": im.role, "mjd": im.mjd, "shape": im.shape,
             "roll_deg": im.roll_deg} for im in images]
    clumps = [np.array([[d["x"], d["y"]] for d in dets if d["saturated"]]).reshape(-1, 2) for dets in detections]
    star_ratio = [_median_peak_ratio(m) for m in meas]
    out = evaluate(sources, meas, meta, clumps, star_ratio, keep, min_mjy)
    # How faint a source this tile could see: the scatter of the aperture sum on the kept sources' surroundings.
    errs = [m["err"] for row in meas for m in row if m["status"] == "ok" and m["err"] is not None]
    result.update(status="done", area_sq_deg=area, n_sources_found=len(sources), tally=out["tally"],
                  killed_positions={k: [[round(sources[i]["ra"], 5), round(sources[i]["dec"], 5)] for i in v[:200]]
                                    for k, v in out["killed"].items()},
                  star_peak_ratio=star_ratio, err_percentiles_mjy=[float(v) for v in np.percentile(errs, [10, 50, 90])]
                  if errs else None,
                  cells_full=[list(c) for c in mine_cells])
    survivors = out["survivors"]
    for sv in survivors:
        sv["catalogues"] = ask_catalogues(sv["ra"], sv["dec"])
        sv["classification"] = classify_with_catalogues(sv["pair"]["bright_mjy"], sv["catalogues"])
        if sv["classification"]["kind"] != "known_variable":
            sv["follow_up"] = follow_up(sv, log, small_bodies=sv["classification"]["kind"] != "known_eruption")
            pts = sv["follow_up"].get("lightcurve", {}).get("points", [])
            if pictures_dir is not None and pts:
                lightcurve_picture(pts, pictures_dir / f"{name}_{sv['ra']:.4f}{sv['dec']:+.4f}_lightcurve.png",
                                   f"RA {sv['ra']:.5f} Dec {sv['dec']:+.5f}: every clean exposure, all detectors")
        if pictures_dir is not None:
            fname = f"{name}_{sv['ra']:.4f}{sv['dec']:+.4f}.png"
            strip_picture(sv["ra"], sv["dec"], images, sv["pair"]["bright_epoch"], sv["pair"]["faint_epoch"],
                          pictures_dir / fname,
                          f"{sv['classification']['kind']}  RA {sv['ra']:.5f} Dec {sv['dec']:+.5f}  "
                          f"l {sv['l']:.3f} b {sv['b']:+.3f}")
            sv["picture"] = fname
    result["survivors"] = survivors
    result["seconds"] = time.time() - t0
    spherex.write_json(TILE_DIR / f"{name}.json", result, indent=1)
    if not keep_images:
        for p in paths:
            p.unlink(missing_ok=True)
    log(f"[{name}] tally {result['tally']} ({result['seconds']:.0f} s)")
    return result


# --- follow-up of the survivors ----------------------------------------------------------------------------------

def _epoch_of(mjd: float, epochs: list[tuple[float, float]]) -> int:
    for k, (lo, hi) in enumerate(epochs):
        if lo - 1.0 <= mjd <= hi + 1.0:
            return k
    return -1


def follow_up(sv: dict[str, Any], log: Any = print, small_bodies: bool = True) -> dict[str, Any]:
    """The project's own tools on one survivor: every exposure and detector, NEOWISE, JPL's small bodies.

    - `photometry.lightcurve`: the brightness in every exposure of every detector (not just
      detector 6 and not just the three epochs), reduced to the median per epoch and detector;
    - `neowise.read_spot`: ten years of NEOWISE 3.4 and 4.6 micrometre measurements at the position;
    - `smallbodies.identify`: JPL's known asteroids and comets within 90 arcsec at the time of
      each bright image (only when `small_bodies`).
    """
    ra, dec = sv["ra"], sv["dec"]
    out: dict[str, Any] = {}
    try:
        lc = photometry.lightcurve(ra, dec)
        pts = [p for b in lc["bins"] for p in b["points"]]
        mj = sorted(p["mjd"] for p in pts)
        epochs: list[tuple[float, float]] = []
        for m in mj:
            if epochs and m - epochs[-1][1] <= EPOCH_GAP_DAYS:
                epochs[-1] = (epochs[-1][0], m)
            else:
                epochs.append((m, m))
        table: dict[str, Any] = {}
        for p in pts:
            if p["status"] != "ok":
                continue
            key = f"epoch {_epoch_of(p['mjd'], epochs)} D{p['detector']}"
            table.setdefault(key, []).append(p["flux_mjy"])
        out["lightcurve"] = {
            "status_counts": lc["status_counts"], "n_exposures": lc["n_exposures"],
            "epochs": [[Time(a, format="mjd").iso[:10], Time(b, format="mjd").iso[:10]] for a, b in epochs],
            "median_mjy_by_epoch_detector": {k: [round(float(np.median(v)), 2), len(v)]
                                             for k, v in sorted(table.items())},
            "points": [{"d": p["detector"], "um": round(p["wavelength_um"], 3) if p["wavelength_um"] else None,
                        "mjd": round(p["mjd"], 3), "mjy": round(p["flux_mjy"], 2), "err": round(p["flux_err_mjy"], 2)}
                       for p in pts if p["status"] == "ok"]}
    except Exception as e:  # noqa: BLE001
        out["lightcurve_error"] = f"{type(e).__name__}: {e}"
    try:
        out["neowise"] = neowise.read_spot(ra, dec)
    except Exception as e:  # noqa: BLE001
        out["neowise_error"] = f"{type(e).__name__}: {e}"
    if small_bodies:
        from . import smallbodies

        found = []
        failed = []
        times = sorted({m["mjd"] for m in sv["measurements"] if m["epoch"] == sv["pair"]["bright_epoch"]
                        and m["status"] in ("ok", "saturated")})
        for t in times[:3]:
            try:
                for body in smallbodies.identify(t, ra, dec, 0.03):
                    dx = (body["ra"] - ra) * math.cos(math.radians(dec)) * 3600.0
                    dy = (body["dec"] - dec) * 3600.0
                    found.append({"mjd": round(t, 3), "name": body["name"], "vmag": body["vmag"],
                                  "offset_arcsec": round(math.hypot(dx, dy), 1)})
            except Exception as e:  # noqa: BLE001
                failed.append(f"{type(e).__name__}: {e}")
        out["small_bodies"] = {"within_108_arcsec": found, "failed": failed, "mjds_asked": times[:3]}
    return out


def exposure_confirmation(sv: dict[str, Any], detectors: tuple[int, ...] = (5, 6), ratio: float = 5.0,
                          min_points: int = 3) -> dict[str, Any]:
    """Does the change survive in every clean exposure of detectors 5 and 6, not only in the tile's images?

    Uses the points saved by `follow_up`. Epochs are runs of exposures with no gap over 30 days; the
    bright and the faint epoch are the ones holding the tile's bright and faint measurements. Both
    medians are over the 3.8 to 5.0 micrometre exposures; the change is "confirmed" when the bright
    median reaches the detection limit, there are at least `min_points` clean exposures on each side,
    and the bright median is at least `ratio` times the faint one (floored at 1 mJy). The factor is
    lower than the tile's ten because medians over many exposures mix wavelengths and positions.
    """
    lc = sv.get("follow_up", {}).get("lightcurve")
    if not lc:
        return {"confirmed": None, "reason": "no light curve"}
    pts = [p for p in lc["points"] if p["d"] in detectors]
    pts.sort(key=lambda p: p["mjd"])
    groups: list[list[dict[str, Any]]] = []
    for p in pts:
        if groups and p["mjd"] - groups[-1][-1]["mjd"] <= EPOCH_GAP_DAYS:
            groups[-1].append(p)
        else:
            groups.append([p])

    def group_of(epoch: int) -> list[dict[str, Any]]:
        mj = [m["mjd"] for m in sv["measurements"] if m["epoch"] == epoch]
        lo, hi = min(mj) - 3.0, max(mj) + 3.0
        return [p for g in groups for p in g if lo - 20 <= p["mjd"] <= hi + 20]

    b, f = group_of(sv["pair"]["bright_epoch"]), group_of(sv["pair"]["faint_epoch"])
    if len(b) < min_points or len(f) < min_points:
        return {"confirmed": False, "reason": f"only {len(b)} and {len(f)} clean exposures", "n_bright": len(b),
                "n_faint": len(f)}
    mb, mf = float(np.median([p["mjy"] for p in b])), float(np.median([p["mjy"] for p in f]))
    r = mb / max(mf, 1.0)
    return {"confirmed": bool(mb >= DETECT_MJY and r >= ratio), "bright_median_mjy": round(mb, 1),
            "faint_median_mjy": round(mf, 1), "ratio": round(r, 1), "n_bright": len(b), "n_faint": len(f)}


def lightcurve_picture(points: list[dict[str, Any]], path: Path, title: str = "") -> None:
    """Brightness against date for every clean exposure, one colour per detector (a plain chart, drawn with PIL)."""
    from PIL import Image, ImageDraw

    if not points:
        return
    colours = {1: (120, 120, 255), 2: (80, 200, 255), 3: (80, 220, 140), 4: (230, 220, 80), 5: (255, 150, 60),
               6: (255, 70, 70)}
    w, h, ml, mb = 900, 420, 70, 40
    img = Image.new("RGB", (w, h), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    t0, t1 = min(p["mjd"] for p in points), max(p["mjd"] for p in points)
    top = max(max(p["mjy"] for p in points), 1.0)
    lo = 0.5
    ylog = lambda v: math.log10(max(v, lo))  # noqa: E731
    y0, y1 = ylog(lo), ylog(top * 1.3)

    def px(p: dict[str, Any]) -> tuple[float, float]:
        return (ml + (p["mjd"] - t0) / max(t1 - t0, 1.0) * (w - ml - 15),
                h - mb - (ylog(p["mjy"]) - y0) / (y1 - y0) * (h - mb - 30))

    dr.text((ml, 6), title, fill=(230, 230, 230))
    for v in (1, 10, 100, 1000, 10000):
        if lo <= v <= top * 1.3:
            y = h - mb - (ylog(v) - y0) / (y1 - y0) * (h - mb - 30)
            dr.line([(ml, y), (w - 10, y)], fill=(60, 60, 66))
            dr.text((8, y - 6), f"{v} mJy", fill=(170, 170, 170))
    for p in points:
        x, y = px(p)
        c = colours.get(p["d"], (255, 255, 255))
        dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=c)
    for k, (d, c) in enumerate(colours.items()):
        dr.rectangle([ml + k * 90, h - 22, ml + k * 90 + 10, h - 12], fill=c)
        dr.text((ml + k * 90 + 14, h - 24), f"detector {d}", fill=(200, 200, 200))
    dr.text((ml, h - mb + 2), f"{Time(t0, format='mjd').iso[:10]} to {Time(t1, format='mjd').iso[:10]}",
            fill=(170, 170, 170))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


# --- describing a survivor correctly (the fixes after the vetting of 2026-11-15) ---------------------------------
#
# The sweep found three real changes, but its description of each was wrong (docs/sweep/vetting/ruling.json,
# "method_faults"): the faint-state light in its measuring circle was a neighbour's (fault 1), its positions
# were blends of the source and its neighbours (2), and two bright readings of C fell on emission lines (5).
# `describe` measures a survivor again from its cached cutouts so that these cannot happen silently:
#
# - the position is the bright-state centroid of a fit in which the neighbours are fitted too;
# - every exposure is measured by a forced fit at that position with the neighbours modelled, and the old
#   measuring circle is kept beside it with two tests of whether its light is centred on the source
#   (`aperture_check`: the centroid of the light inside the circle and the 1.5 / 2.5 pixel concentration);
# - a bright tile image whose reading stands well above the same visit's other wavelengths is flagged as
#   possibly an emission line (`line_flag`).

NATIVE_ARCSEC = 6.15
PSF_FALLBACK_ARCSEC = 8.5        # if a cutout's header has no PSF_FWHM
FIT_RADIUS_PX = 4.5              # pixels used in a fit around the source
NEIGHBOUR_SEARCH_PX = 7.0        # peaks this close are fitted with the source
NEIGHBOUR_MIN_SEP_PX = 1.2       # a peak nearer than this (7.4 arcsec) is the source itself
NEIGHBOUR_SIGMA = 5.0            # a neighbour must stand this far above the pixel noise
SMALL_APERTURE_PX = 1.5
CENTROID_SHIFT_PX = 0.5          # light centred further than this (3 arcsec) from the source is not the source's
CONCENTRATION_SHARE = 0.6        # or less concentrated than this share of the source's own bright-state value
POSITION_CLIP_ARCSEC = 3.0       # a bright-state centroid this far from the median: the exposure's coordinates are off
BRIGHT_FIT_SNR = 10.0            # bright-state fits used for the position
BLANK_RING_PX = 5.0              # the blank-sky test: the same fit at empty places this far out
BLANK_PLACES = 12
LINE_FACTOR = 1.5                # a tile reading this many times the same visit's other wavelengths: a possible line
LINE_WIDTH_UM = 0.04             # "other wavelengths" are further than this from the reading's own (about a channel)


@dataclass
class Cutout:
    """One cached SPHEREx cutout in mJy per pixel, with its masks, wavelength map and PSF width."""
    path: Path
    obs_id: str
    detector: int
    mjd: float
    wcs: WCS
    data: np.ndarray              # mJy per pixel, zodi removed; empty pixels NaN
    var: np.ndarray               # mJy^2 per pixel
    bad: np.ndarray               # never used: photometry flags, empty, or saturated
    sat: np.ndarray               # saturated (the photometry rule)
    overflow: np.ndarray          # OVERFLOW: a valid but partial reading
    wave: np.ndarray              # micrometres
    sigma_px: float               # Gaussian sigma of the header's PSF_FWHM, in pixels

    @classmethod
    def load(cls, path: Path) -> Cutout:
        obs_id, det = path.stem.rsplit("_D", 1)
        with fits.open(path) as h:
            header = h["IMAGE"].header
            image = h["IMAGE"].data.astype(np.float64)
            flags = h["FLAGS"].data.astype(np.int64)
            variance = h["VARIANCE"].data.astype(np.float64)
            zodi = h["ZODI"].data.astype(np.float64)
            wave = h["WAVE"].data.astype(np.float64)
        wcs = WCS(header)
        to_mjy = float(proj_plane_pixel_area(wcs)) * (np.pi / 180.0) ** 2 * 1e9
        data = image - zodi
        data[pipeline.impossible_pixels(image, variance)] = np.nan
        sat = photometry.saturated_pixels(flags, data)
        bad = ((flags & photometry.PHOTOMETRY_BAD) != 0) | ~np.isfinite(data) | ~np.isfinite(variance) | sat
        fwhm = float(header.get("PSF_FWHM", PSF_FALLBACK_ARCSEC) or PSF_FALLBACK_ARCSEC)
        return cls(path=path, obs_id=obs_id, detector=int(det), mjd=float(header["MJD-AVG"]), wcs=wcs,
                   data=data * to_mjy, var=variance * to_mjy ** 2, bad=bad, sat=sat,
                   overflow=(flags & photometry.OVERFLOW) != 0, wave=wave,
                   sigma_px=fwhm / 2.3548 / NATIVE_ARCSEC)

    def xy(self, ra: float, dec: float) -> tuple[float, float]:
        x, y = self.wcs.all_world2pix(ra, dec, 0, quiet=True)
        return float(x), float(y)

    def radec(self, x: float, y: float) -> tuple[float, float]:
        ra, dec = self.wcs.all_pix2world(x, y, 0)
        return float(ra), float(dec)

    def wavelength(self, x: float, y: float) -> float | None:
        ny, nx = self.data.shape
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < nx and 0 <= yi < ny):
            return None
        w = float(self.wave[yi, xi])
        return w if np.isfinite(w) else None


def psf_model(xx: np.ndarray, yy: np.ndarray, x0: float, y0: float, sigma: float) -> np.ndarray:
    """A pixel-integrated circular Gaussian of unit total flux centred at (x0, y0)."""
    from scipy.special import erf

    s = sigma * math.sqrt(2.0)
    gx = 0.5 * (erf((xx + 0.5 - x0) / s) - erf((xx - 0.5 - x0) / s))
    gy = 0.5 * (erf((yy + 0.5 - y0) / s) - erf((yy - 0.5 - y0) / s))
    return gx * gy


def neighbour_peaks(c: Cutout, x0: float, y0: float, search_px: float = NEIGHBOUR_SEARCH_PX,
                    min_sep_px: float = NEIGHBOUR_MIN_SEP_PX,
                    nsigma: float = NEIGHBOUR_SIGMA) -> list[tuple[float, float]]:
    """Other sources near (x0, y0) in one cutout, as pixel positions.

    Local maxima (3 x 3) standing `nsigma` times the pixel noise above the clipped median of the box,
    between `min_sep_px` and `search_px` from (x0, y0), placed by the light-weighted centroid of their
    3 x 3 pixels; a clump of saturated pixels counts as one source at its centre. Found in each
    exposure separately, so a neighbour is placed by the image itself and not by a catalogue.
    """
    ny, nx = c.data.shape
    h = int(math.ceil(search_px)) + 2
    xi, yi = int(round(x0)), int(round(y0))
    y_lo, y_hi, x_lo, x_hi = max(yi - h, 1), min(yi + h + 1, ny - 1), max(xi - h, 1), min(xi + h + 1, nx - 1)
    box = np.where(c.bad, np.nan, c.data)[y_lo:y_hi, x_lo:x_hi]
    level, _ = clipped(box.ravel())
    if not np.isfinite(level):
        return []
    d = np.where(np.isfinite(box), box - level, -np.inf)
    noise = np.sqrt(np.where(np.isfinite(c.var[y_lo:y_hi, x_lo:x_hi]), c.var[y_lo:y_hi, x_lo:x_hi], np.inf))
    peaks = (d == maximum_filter(d, size=3, mode="nearest")) & (d > nsigma * noise)
    out = []
    for py_, px_ in zip(*np.nonzero(peaks), strict=True):
        if not (1 <= py_ < d.shape[0] - 1 and 1 <= px_ < d.shape[1] - 1):
            continue
        patch = np.clip(np.nan_to_num(d[py_ - 1:py_ + 2, px_ - 1:px_ + 2], neginf=0.0), 0, None)
        w = patch.sum()
        oy, ox = np.mgrid[-1:2, -1:2]
        cx = x_lo + px_ + (float((patch * ox).sum() / w) if w > 0 else 0.0)
        cy = y_lo + py_ + (float((patch * oy).sum() / w) if w > 0 else 0.0)
        r = math.hypot(cx - x0, cy - y0)
        if min_sep_px <= r <= search_px:
            out.append((cx, cy))
    lab, n = label(c.sat[y_lo:y_hi, x_lo:x_hi])
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        cx, cy = x_lo + float(xs.mean()), y_lo + float(ys.mean())
        if min_sep_px <= math.hypot(cx - x0, cy - y0) <= search_px + 2 \
                and all(math.hypot(cx - a, cy - b) > 1.5 for a, b in out):
            out.append((cx, cy))
    return out


def _fit_pixels(c: Cutout, x: float, y: float, radius: float) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                                         np.ndarray] | None:
    ny, nx = c.data.shape
    h = int(math.ceil(radius)) + 1
    xi, yi = int(round(x)), int(round(y))
    if not (h <= xi < nx - h and h <= yi < ny - h):
        return None
    yy, xx = np.mgrid[yi - h:yi + h + 1, xi - h:xi + h + 1]
    use = (np.hypot(xx - x, yy - y) <= radius) & ~c.bad[yy, xx]
    return xx[use].astype(np.float64), yy[use].astype(np.float64), c.data[yy, xx][use], c.var[yy, xx][use]


def _solve(c: Cutout, xx: np.ndarray, yy: np.ndarray, d: np.ndarray, v: np.ndarray, x: float, y: float,
           neighbours: list[tuple[float, float]], sigma: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Weighted linear least squares: source, neighbours, sky plane. Returns amplitudes, covariance, chi^2/dof."""
    cols = [psf_model(xx, yy, x, y, sigma)] + [psf_model(xx, yy, a, b, sigma) for a, b in neighbours]
    cols += [np.ones_like(xx), xx - x, yy - y]
    a = np.stack(cols, axis=1)
    w = 1.0 / np.sqrt(np.clip(v, 1e-12, None))
    aw, dw = a * w[:, None], d * w
    beta, *_ = np.linalg.lstsq(aw, dw, rcond=None)
    dof = max(len(d) - a.shape[1], 1)
    chi2 = float(np.sum((dw - aw @ beta) ** 2)) / dof
    try:
        cov = np.linalg.inv(aw.T @ aw) * max(chi2, 1.0)
    except np.linalg.LinAlgError:
        cov = np.full((a.shape[1], a.shape[1]), np.nan)
    return beta, cov, chi2


def forced_fit(c: Cutout, x: float, y: float, radius: float = FIT_RADIUS_PX) -> dict[str, Any]:
    """Brightness of a point source fixed at pixel (x, y), with its neighbours fitted at the same time.

    The source and every neighbour (`neighbour_peaks`) are pixel-integrated Gaussians of the
    exposure's own PSF width (header PSF_FWHM), with a sloping sky plane, fitted by weighted linear
    least squares to the usable pixels within `radius`. `flux` is the source's total in mJy. Status:
    "ok"; "saturated" (a saturated pixel within 1.5 pixels: those are left out, so the value rests on
    the wings and is uncertain); "flagged" (under 60 per cent of the pixels within 1.5 pixels usable);
    "edge". `overflow` counts OVERFLOW pixels within 1.5 pixels (a valid but partial reading).
    """
    out: dict[str, Any] = {"status": "edge", "flux": None, "err": None, "x": x, "y": y}
    got = _fit_pixels(c, x, y, radius)
    if got is None:
        return out
    xx, yy, d, v = got
    ny, nx = c.data.shape
    gy, gx = np.mgrid[0:ny, 0:nx]
    core = np.hypot(gx - x, gy - y) <= 1.5
    out["overflow"] = int((c.overflow & core).sum())
    if c.sat[core].any():
        out["status"] = "saturated"
    elif (~c.bad[core]).sum() < 0.6 * core.sum():
        out["status"] = "flagged"
        return out
    else:
        out["status"] = "ok"
    nb = neighbour_peaks(c, x, y)
    nb = [p for p in nb if math.hypot(p[0] - x, p[1] - y) <= radius + 2.0]
    beta, cov, chi2 = _solve(c, xx, yy, d, v, x, y, nb, c.sigma_px)
    out.update(flux=float(beta[0]), err=float(math.hypot(math.sqrt(max(cov[0, 0], 0.0)), SYSTEMATIC * abs(beta[0]))),
               chi2=round(chi2, 2), n_pixels=int(len(d)),
               neighbours=[{"dx_px": round(a - x, 2), "dy_px": round(b - y, 2), "mjy": round(float(f), 2)}
                           for (a, b), f in zip(nb, beta[1:1 + len(nb)], strict=True)])
    return out


def centroid_fit(c: Cutout, x0: float, y0: float, radius: float = FIT_RADIUS_PX) -> dict[str, Any] | None:
    """Position and brightness of the source near (x0, y0), its neighbours fitted too; None if not usable.

    Like `forced_fit`, but the source's place is free (within 2 pixels of the start). Used only where the
    source is bright and unsaturated, to place it.
    """
    from scipy.optimize import least_squares

    got = _fit_pixels(c, x0, y0, radius + 2.0)
    if got is None:
        return None
    ny, nx = c.data.shape
    gy, gx = np.mgrid[0:ny, 0:nx]
    if (c.sat & (np.hypot(gx - x0, gy - y0) <= 2.5)).any():
        return None
    nb = neighbour_peaks(c, x0, y0)
    xx_all, yy_all, d_all, v_all = got

    def resid(p: np.ndarray) -> np.ndarray:
        near = np.hypot(xx_all - p[0], yy_all - p[1]) <= radius
        xx, yy, d, v = xx_all[near], yy_all[near], d_all[near], v_all[near]
        others = [q for q in nb if math.hypot(q[0] - p[0], q[1] - p[1]) >= NEIGHBOUR_MIN_SEP_PX]
        beta, _, _ = _solve(c, xx, yy, d, v, float(p[0]), float(p[1]), others, c.sigma_px)
        cols = [psf_model(xx, yy, p[0], p[1], c.sigma_px)] + [psf_model(xx, yy, a, b, c.sigma_px) for a, b in others]
        cols += [np.ones_like(xx), xx - p[0], yy - p[1]]
        r = (d - np.stack(cols, axis=1) @ beta) / np.sqrt(np.clip(v, 1e-12, None))
        full = np.zeros(len(d_all))
        full[near] = r
        return full

    fit = least_squares(resid, np.array([x0, y0]), bounds=([x0 - 2, y0 - 2], [x0 + 2, y0 + 2]), diff_step=1e-3)
    x, y = float(fit.x[0]), float(fit.x[1])
    f = forced_fit(c, x, y, radius)
    if f["status"] != "ok" or f["flux"] is None or not f["err"]:
        return None
    ra, dec = c.radec(x, y)
    return {"x": x, "y": y, "ra": ra, "dec": dec, "flux": f["flux"], "err": f["err"],
            "snr": f["flux"] / f["err"]}


def aperture_check(c: Cutout, x: float, y: float) -> dict[str, Any]:
    """The sweep's measuring circle at (x, y) and whether its light is centred there.

    Sums in circles of 2.5 and 1.5 pixels minus the clipped median of the 14 to 20 pixel ring; their
    ratio (`concentration`); and `shift_px`, the distance from (x, y) of the centroid of the positive
    light inside the 2.5 pixel circle. A point source at (x, y) gives a small shift and its own
    concentration; a neighbour's wing gives a large shift and a low concentration (A and B in 2025).
    """
    ny, nx = c.data.shape
    h = int(SKY_PX[1]) + 1
    xi, yi = int(round(x)), int(round(y))
    out: dict[str, Any] = {"flux": None, "flux_small": None, "concentration": None, "shift_px": None}
    if not (h <= xi < nx - h and h <= yi < ny - h):
        return out
    win = np.where(c.bad, np.nan, c.data)[yi - h:yi + h + 1, xi - h:xi + h + 1]
    gy, gx = np.mgrid[-h:h + 1, -h:h + 1]
    r = np.hypot(gx + xi - x, gy + yi - y)
    sky, sig = clipped(win[(r >= SKY_PX[0]) & (r < SKY_PX[1])])
    if not np.isfinite(sky):
        return out
    core = win[h - _AP_HALF:h + _AP_HALF + 1, h - _AP_HALF:h + _AP_HALF + 1] - sky
    w_big = aperture_weights(x - xi, y - yi)
    w_small = aperture_weights(x - xi, y - yi, SMALL_APERTURE_PX)
    valid = np.isfinite(core)
    # As the sweep's own circle (`Img.measure_xy`): up to MAX_FLAGGED_SHARE of it may be flagged, the rest scaled up.
    if float(w_big[~valid].sum()) > MAX_FLAGGED_SHARE * float(w_big.sum()) or not (w_small[valid] > 0).any():
        return out
    big = float(np.nansum(w_big * core)) * float(w_big.sum()) / float(w_big[valid].sum())
    small = float(np.nansum(w_small * core)) * float(w_small.sum()) / float(w_small[valid].sum())
    o = np.arange(-_AP_HALF, _AP_HALF + 1)
    pos = np.clip(np.nan_to_num(core), 0, None) * w_big
    tot = float(pos.sum())
    if tot > 0:
        cx = float((pos * o[None, :]).sum() / tot) + xi - x
        cy = float((pos * o[:, None]).sum() / tot) + yi - y
        out["shift_px"] = math.hypot(cx, cy)
    out.update(flux=big, flux_small=small, concentration=small / big if big > 0 else None,
               err=float(sig * math.sqrt(float(w_big.sum()))) if np.isfinite(sig) else None)
    return out


def blank_test(cutouts: list[Cutout], ra: float, dec: float, ring_px: float = BLANK_RING_PX,
               places: int = BLANK_PLACES) -> dict[str, Any]:
    """How large a false signal the forced fit gives at empty places near the source, in the same exposures.

    The fit is repeated at `places` points on a circle of `ring_px` pixels around (ra, dec); each place
    gives the median over the exposures. `scatter_mjy` is the robust scatter of those medians (1.4826 x
    the median absolute deviation) and `largest_mjy` the largest. This, not the formal error, sets the
    faint-state limit: in a crowded field the neighbours' residuals dominate (the vetting found up to 14 mJy
    at 30 blank places near A).
    """
    meds = []
    for k in range(places):
        ang = 2.0 * math.pi * k / places
        vals = []
        for c in cutouts:
            x, y = c.xy(ra, dec)
            f = forced_fit(c, x + ring_px * math.cos(ang), y + ring_px * math.sin(ang))
            if f["status"] == "ok" and f["flux"] is not None:
                vals.append(f["flux"])
        if len(vals) >= 3:
            meds.append(float(np.median(vals)))
    if len(meds) < 5:
        return {"places": len(meds), "scatter_mjy": None, "largest_mjy": None}
    m = np.array(meds)
    return {"places": len(meds), "scatter_mjy": round(float(1.4826 * np.median(np.abs(m - np.median(m)))), 2),
            "largest_mjy": round(float(np.max(np.abs(m))), 2), "median_mjy": round(float(np.median(m)), 2)}


def group_by_time(mjds: list[float], gap: float = EPOCH_GAP_DAYS) -> list[int]:
    """Epoch number (0, 1, ...) of each time: a gap longer than `gap` days starts a new one."""
    order = sorted(range(len(mjds)), key=lambda k: mjds[k])
    out = [0] * len(mjds)
    n, last = -1, None
    for k in order:
        if last is None or mjds[k] - last > gap:
            n += 1
        out[k] = n
        last = mjds[k]
    return out


def _stats(values: list[float]) -> dict[str, Any]:
    v = np.array(values, dtype=float)
    if v.size == 0:
        return {"n": 0}
    med = float(np.median(v))
    sem = float(1.2533 * 1.4826 * np.median(np.abs(v - med)) / math.sqrt(v.size)) if v.size >= 3 else None
    return {"n": int(v.size), "median": round(med, 2), "min": round(float(v.min()), 2),
            "max": round(float(v.max()), 2), "sem": round(sem, 2) if sem is not None else None}


def line_flag(readings: list[dict[str, Any]], others: list[dict[str, Any]], factor: float = LINE_FACTOR,
              width_um: float = LINE_WIDTH_UM) -> dict[str, Any]:
    """Do the bright readings rest on one narrow wavelength that is much brighter than the rest of the visit?

    Every SPHEREx exposure sees one narrow wavelength at a given place. `readings` are the bright
    tile images ({"obs_id", "um", "mjy"}), `others` the same visit's other clean exposures of the same
    detector ({"um", "mjy"}, measured the same way). A reading `factor` or more times the median of the
    exposures further than `width_um` from its wavelength is flagged: "possibly an emission line", and
    the change should then be judged on the continuum (C's 178 and 300 mJy fell on lines at 4.739 and
    4.631 micrometres while its continuum was 85 to 110 mJy; ruling, method fault 5).
    """
    out: dict[str, Any] = {"possible_emission_line": False, "readings": []}
    for r in readings:
        if r.get("um") is None or r.get("mjy") is None:
            out["readings"].append({"note": "no wavelength or no value", **r, "continuum_mjy": None, "ratio": None})
            continue
        cont = [o["mjy"] for o in others if o.get("um") is not None and abs(o["um"] - r["um"]) > width_um]
        if len(cont) < 3:
            out["readings"].append({**r, "continuum_mjy": None, "ratio": None, "note": "too few other wavelengths"})
            continue
        c = float(np.median(cont))
        ratio = r["mjy"] / c if c > 0 else None
        flagged = ratio is not None and ratio >= factor
        out["readings"].append({**r, "continuum_mjy": round(c, 2), "n_continuum": len(cont),
                                "ratio": round(ratio, 2) if ratio is not None else None, "line": flagged})
        out["possible_emission_line"] |= flagged
    return out


def describe(cutouts: list[Cutout], ra: float, dec: float, tile_images: list[dict[str, Any]] | None = None,
             position_detectors: tuple[int, ...] = (3, 4, 5, 6), change_detector: int = 6) -> dict[str, Any]:
    """Measure a survivor again from its cutouts, without the faults the vetting found.

    1. The bright epochs: those whose median sweep-circle reading in `change_detector` at (ra, dec) is at least a
       quarter of the brightest epoch's and at least DETECT_MJY.
    2. The position: the mean of the bright-state `centroid_fit` positions (S/N at least BRIGHT_FIT_SNR, no
       saturated pixel near the core) in `position_detectors`, after dropping any further than
       POSITION_CLIP_ARCSEC from their median (an exposure whose sky coordinates are off).
    3. At that position, every exposure: `forced_fit` (neighbours modelled) and `aperture_check` (the old circle).
    4. Per epoch and detector, the forced-fit fluxes of clean exposures; per faint epoch whether the old circle's
       light was a neighbour's (`neighbour_light`: a reading above 3 times its error whose light is centred more
       than CENTROID_SHIFT_PX away or less concentrated than CONCENTRATION_SHARE of the bright state).
    5. `line_flag` for the tile's bright images (`tile_images`: {"obs_id", "mjy"} of `change_detector`).
    """
    if not cutouts:
        return {"error": "no cutouts"}
    epochs = group_by_time([c.mjd for c in cutouts])
    ep_of = {id(c): e for c, e in zip(cutouts, epochs, strict=True)}
    # 1. bright epochs, from the old circle at the old position (what the sweep saw)
    old: dict[int, list[float]] = {}
    for c in cutouts:
        if c.detector == change_detector:
            a = aperture_check(c, *c.xy(ra, dec))
            if a["flux"] is not None:
                old.setdefault(ep_of[id(c)], []).append(a["flux"])
    med_old = {e: float(np.median(v)) for e, v in old.items()}
    if not med_old:
        return {"error": f"no usable detector {change_detector} exposure"}
    top = max(med_old.values())
    bright = sorted(e for e, m in med_old.items() if m >= max(DETECT_MJY, 0.25 * top))
    # 2. the bright-state position
    fits_ = []
    for c in cutouts:
        if ep_of[id(c)] in bright and c.detector in position_detectors:
            f = centroid_fit(c, *c.xy(ra, dec))
            if f is not None and f["snr"] >= BRIGHT_FIT_SNR:
                fits_.append({**f, "obs_id": c.obs_id, "detector": c.detector})
    if not fits_:
        return {"error": "no clean bright-state exposure to place the source"}
    m_ra, m_dec = float(np.median([f["ra"] for f in fits_])), float(np.median([f["dec"] for f in fits_]))
    cosd = math.cos(math.radians(m_dec))
    for f in fits_:
        f["off_arcsec"] = math.hypot((f["ra"] - m_ra) * cosd, f["dec"] - m_dec) * 3600.0
    kept = [f for f in fits_ if f["off_arcsec"] <= POSITION_CLIP_ARCSEC]
    dropped = [{"obs_id": f["obs_id"], "detector": f["detector"], "off_arcsec": round(f["off_arcsec"], 1)}
               for f in fits_ if f["off_arcsec"] > POSITION_CLIP_ARCSEC]
    p_ra, p_dec = float(np.mean([f["ra"] for f in kept])), float(np.mean([f["dec"] for f in kept]))
    cosd = math.cos(math.radians(p_dec))
    scatter = float(np.std([math.hypot((f["ra"] - p_ra) * cosd, f["dec"] - p_dec) * 3600.0 for f in kept]))
    position = {"ra": round(p_ra, 6), "dec": round(p_dec, 6), "n": len(kept),
                "scatter_arcsec": round(scatter, 2), "error_arcsec": round(scatter / math.sqrt(len(kept)), 2),
                "moved_arcsec": round(math.hypot((p_ra - ra) * cosd, p_dec - dec) * 3600.0, 2),
                "dropped": dropped, "detectors": sorted({f["detector"] for f in kept})}
    # 3. every exposure at the new position
    rows = []
    for c in cutouts:
        x, y = c.xy(p_ra, p_dec)
        f = forced_fit(c, x, y)
        a = aperture_check(c, x, y)
        rows.append({"obs_id": c.obs_id, "detector": c.detector, "epoch": ep_of[id(c)], "mjd": round(c.mjd, 4),
                     "um": c.wavelength(x, y), "status": f["status"], "fit_mjy": f["flux"], "fit_err": f["err"],
                     "overflow": f.get("overflow", 0), "circle_mjy": a["flux"], "circle_err": a.get("err"),
                     "shift_px": a["shift_px"], "concentration": a["concentration"]})
    # 4. per epoch and detector
    table: dict[str, Any] = {}
    for e in sorted(set(epochs)):
        mj = [r["mjd"] for r in rows if r["epoch"] == e]
        entry: dict[str, Any] = {"dates": [Time(min(mj), format="mjd").iso[:10], Time(max(mj), format="mjd").iso[:10]],
                                 "bright": e in bright, "detectors": {}}
        for d in range(1, 7):
            mine = [r for r in rows if r["epoch"] == e and r["detector"] == d]
            if not mine:
                continue
            ok = [r["fit_mjy"] for r in mine if r["status"] == "ok" and r["fit_mjy"] is not None]
            entry["detectors"][str(d)] = {"fit": _stats(ok), "n_exposures": len(mine),
                                          "n_saturated": sum(r["status"] == "saturated" for r in mine),
                                          "n_overflow": sum(r["status"] == "ok" and r["overflow"] > 0 for r in mine)}
        table[str(e)] = entry
    conc_bright = [r["concentration"] for r in rows if r["epoch"] in bright and r["detector"] == change_detector
                   and r["status"] == "ok" and r["concentration"] is not None]
    c_ref = float(np.median(conc_bright)) if conc_bright else None
    faint: dict[str, Any] = {}
    for e in sorted(set(epochs) - set(bright)):
        mine = [r for r in rows if r["epoch"] == e and r["detector"] == change_detector and r["status"] == "ok"
                and r["circle_mjy"] is not None]
        if not mine:
            continue
        circ = float(np.median([r["circle_mjy"] for r in mine]))
        err = float(np.median([r["circle_err"] for r in mine if r["circle_err"] is not None] or [np.nan]))
        shifts = [r["shift_px"] for r in mine if r["shift_px"] is not None]
        concs = [r["concentration"] for r in mine if r["concentration"] is not None]
        shift = float(np.median(shifts)) if shifts else None
        conc = float(np.median(concs)) if concs else None
        significant = bool(np.isfinite(err) and circ > 3.0 * err)
        off_centre = (shift is not None and shift > CENTROID_SHIFT_PX) or \
                     (conc is not None and c_ref is not None and conc < CONCENTRATION_SHARE * c_ref)
        fit = _stats([r["fit_mjy"] for r in mine if r["fit_mjy"] is not None])
        blank = blank_test([c for c in cutouts if ep_of[id(c)] == e and c.detector == change_detector], p_ra, p_dec)
        limit, detected = None, None
        if fit["n"] >= 3 and blank["scatter_mjy"] is not None:
            noise = max(blank["scatter_mjy"], fit.get("sem") or 0.0)
            limit = round(max(fit["median"], 0.0) + 3.0 * noise, 2)
            detected = bool(fit["median"] > 3.0 * noise)
        faint[str(e)] = {"circle_mjy": round(circ, 2), "circle_err": round(err, 2) if np.isfinite(err) else None,
                         "shift_px": round(shift, 2) if shift is not None else None,
                         "concentration": round(conc, 3) if conc is not None else None,
                         "bright_concentration": round(c_ref, 3) if c_ref is not None else None,
                         "neighbour_light": bool(significant and off_centre), "fit": fit, "blank": blank,
                         "limit_3sigma": limit, "detected": detected}
    result: dict[str, Any] = {"position": position, "bright_epochs": bright, "epochs": table, "faint": faint,
                              "exposures": rows}
    # rise factor in the change detector: brightest bright-epoch median over the faintest faint-epoch limit
    bright_meds = [table[str(e)]["detectors"].get(str(change_detector), {}).get("fit", {}).get("median")
                   for e in bright]
    bright_meds = [m for m in bright_meds if m is not None]
    limits = [f["limit_3sigma"] for f in faint.values() if f["limit_3sigma"] is not None]
    if bright_meds and limits:
        result["rise_at_least"] = round(max(bright_meds) / max(min(limits), 1.0), 0)
    # 5. emission lines under the tile's bright images
    if tile_images:
        by_obs = {r["obs_id"]: r for r in rows if r["detector"] == change_detector}
        readings, used_epochs = [], set()
        for t in tile_images:
            r = by_obs.get(t["obs_id"])
            if r is None or r["status"] != "ok":
                readings.append({"obs_id": t["obs_id"], "um": r["um"] if r else None, "mjy": None,
                                 "tile_mjy": t.get("mjy"), "note": "not a clean exposure here"})
                continue
            readings.append({"obs_id": t["obs_id"], "um": r["um"], "mjy": r["fit_mjy"], "tile_mjy": t.get("mjy")})
            used_epochs.add(r["epoch"])
        others = [{"um": r["um"], "mjy": r["fit_mjy"]} for r in rows
                  if r["detector"] == change_detector and r["epoch"] in used_epochs and r["status"] == "ok"
                  and r["fit_mjy"] is not None and r["obs_id"] not in {t["obs_id"] for t in tile_images}]
        result["lines"] = line_flag(readings, others)
    return result


VETTING_DIR = Path(__file__).resolve().parent.parent / "docs" / "sweep" / "vetting"
VETTED_MATCH_ARCSEC = 5.0


def vetted_candidates(path: Path | None = None) -> list[dict[str, Any]]:
    """The ruled candidates (docs/sweep/vetting/candidates.json), or [] if the file is not there."""
    p = path or VETTING_DIR / "candidates.json"
    return json.loads(p.read_text())["candidates"] if p.exists() else []


def _vetted_for(sv: dict[str, Any], vetted: list[dict[str, Any]]) -> dict[str, Any] | None:
    for v in vetted:
        ra0, dec0 = v["first_run_position_withdrawn"]
        if sep_deg(sv["ra"], sv["dec"], ra0, dec0) * 3600.0 <= VETTED_MATCH_ARCSEC:
            return v
    return None


def summarise(include_proof: bool = False, vetted: list[dict[str, Any]] | None = None,
              rerun: dict[str, Any] | None = None) -> dict[str, Any]:
    """Totals over every finished tile: area, the tally at each stage, the survivors by kind.

    A survivor that the vetting ruled on (`vetted`, from `vetted_candidates`) is listed with the
    ruling's position and numbers only: the first run's position and brightness for it were wrong
    and are left out. `rerun` (docs/sweep/vetting/rerun.json) adds what the fixed follow-up found.
    An unexplained survivor that the all-exposure check did not confirm is "set_aside".
    """
    vetted = vetted_candidates() if vetted is None else vetted
    checks = (rerun or {}).get("candidates", {})
    tiles = []
    for p in sorted(TILE_DIR.glob("*.json")):
        if p.stem.startswith("proof") and not include_proof:
            continue
        tiles.append(json.loads(p.read_text()))
    done = [t for t in tiles if t.get("status") == "done"]
    total = dict.fromkeys(STAGES, 0)
    kinds: dict[str, int] = {}
    survivors = []
    for t in done:
        for k, v in t["tally"].items():
            total[k] += v
        for sv in t.get("survivors", []):
            k = sv["classification"]["kind"] + ("_single_image" if sv.get("single_image_only") else "")
            conf = exposure_confirmation(sv) if sv["classification"]["kind"].startswith("candidate") else None
            ruled = _vetted_for(sv, vetted) if k.startswith("candidate") else None
            if ruled is not None:
                entry = {"tile": t["name"], "label": ruled["label"], "kind": "candidate",
                         **{f: ruled[f] for f in ("ra", "dec", "sexagesimal", "position_error_arcsec", "l", "b",
                                                  "constellation", "allowed_sentence", "last_non_detection",
                                                  "first_detection", "visits_d6", "rise", "at_the_place",
                                                  "spectrum", "probably")},
                         "direction": "brightened", "source": "docs/sweep/vetting/ruling.json (2026-11-15)"}
                if ruled["label"] in checks:
                    entry["fixed_follow_up"] = checks[ruled["label"]]["summary"]
                survivors.append(entry)
                kinds["candidate"] = kinds.get("candidate", 0) + 1
                continue
            if k.startswith("candidate") and not (conf and conf["confirmed"]):
                k = "set_aside"
            kinds[k] = kinds.get(k, 0) + 1
            survivors.append({"tile": t["name"], "ra": round(sv["ra"], 5), "dec": round(sv["dec"], 5), "kind": k,
                              "confirmed_in_all_exposures": conf and conf["confirmed"],
                              "bright_mjy": round(sv["pair"]["bright_mjy"], 1), "direction": sv.get("direction")})
    return {"tiles_done": len(done), "tiles_skipped": len(tiles) - len(done),
            "area_sq_deg": round(sum(t["area_sq_deg"] for t in done), 2), "tally": total,
            "survivors_by_kind": kinds, "survivors": survivors,
            "note": ("'candidate' means a source we found in no catalogue or report we checked; nobody has confirmed "
                     "it and nothing has been reported. 'set_aside': looked at and not kept (docs/sweep.md).")}

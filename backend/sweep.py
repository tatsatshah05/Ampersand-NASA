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
    unless they are closer than the radius. A source's position is the mean of its detections.
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
                        "n_detections": len(members), "saturated_detected": any(d["saturated"] for _, d in members)})
    return sources


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
    a side the answer is "no data" and never a pass. `min_bright` is the number of usable images the
    bright side needs: 1 for a plain two-visit comparison, 2 to have the source confirmed by a second image.
    """
    b = [m for m in bright if is_valid(m)]
    f = [m for m in faint if is_valid(m)]
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


def classify(bright_mjy: float, rows: list[dict[str, Any]], offsets: list[float], near_arcsec: float = 6.2,
             far_arcsec: float = 12.0) -> dict[str, Any]:
    """Sort a survivor by what the catalogues say at its position.

    `rows` are catalogue rows as `backend/search.py` returns them and `offsets` each row's
    distance in arcsec from the source (positions already brought to the same epoch or not:
    the caller says). Result `kind`:

    - "known_eruption": a row within `far_arcsec` that is a nova or another eruptive type in
      SIMBAD or the AAVSO VSX (the type decides, see KNOWN_ERUPTION_TYPES and VSX_ERUPTIVE);
    - "known_variable": a catalogued star at the place that was already bright (4.6 micrometres
      at least 1/5 of the bright brightness in WISE, or any variable type in SIMBAD, VSX or
      Gaia) and that is not an eruption;
    - "candidate": no catalogue row within `near_arcsec`, or only rows far fainter than the
      brightness SPHEREx saw (the rule is on W2 and Ks; a row with no infrared brightness and no
      variable type cannot rule the source out, so the source is a candidate "with an optical
      counterpart that is far fainter at its brightest").

    "candidate" is never more than that. The reasons are returned.
    """
    reasons: list[str] = []
    pairs = sorted(zip(offsets, rows, strict=True), key=lambda p: p[0])
    for off, row in pairs:
        if off > far_arcsec:
            continue
        kind = (row.get("type") or "").lower()
        cat = row.get("catalogue")
        if cat == "SIMBAD" and kind.strip() in KNOWN_ERUPTION_TYPES:
            return {"kind": "known_eruption", "reasons": [f"SIMBAD {row['name']} is type {row.get('type')} "
                                                          f"({off:.1f} arcsec away)"], "by": row}
        if cat == "AAVSO VSX" and VSX_ERUPTIVE.match((row.get("type") or "").split(",")[0].strip()):
            return {"kind": "known_eruption", "reasons": [f"AAVSO VSX {row['name']} is {row.get('type')} "
                                                          f"({off:.1f} arcsec away)"], "by": row}
    pre = []
    for off, row in pairs:
        if off > near_arcsec:
            continue
        cat = row.get("catalogue")
        w2 = row.get("w2") if cat in ("AllWISE", "CatWISE2020") else None
        flux = w2_mjy(w2)
        if flux is not None and flux >= bright_mjy / 5.0:
            pre.append(f"{row['name']} ({cat}) W2 {w2:.2f} mag = {flux:.0f} mJy, already bright")
        elif row.get("variable"):
            pre.append(f"{row['name']} ({cat}) is listed as variable ({row.get('type')})")
        elif cat == "2MASS" and (kf := k_mjy(row.get("k"))) is not None and kf >= bright_mjy / 5.0:
            pre.append(f"{row['name']} (2MASS) Ks {row['k']:.2f} mag = {kf:.0f} mJy, already bright")
    if pre:
        return {"kind": "known_variable", "reasons": pre}
    within = [(o, r) for o, r in pairs if o <= near_arcsec]
    if not within:
        reasons.append(f"no row within {near_arcsec:g} arcsec in any catalogue asked")
    else:
        for off, row in within:
            reasons.append(f"{row['name']} ({row.get('catalogue')}) at {off:.1f} arcsec, far fainter or no infrared "
                           "brightness listed")
    return {"kind": "candidate", "reasons": reasons}


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
        survivors.append({"index": s, "ra": sources[s]["ra"], "dec": sources[s]["dec"], "l": sources[s].get("l"),
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
            if ((d > 2 * SAT_MERGE_PX) & (d < SAT_RESIDUE_PX)).any():
                return "saturation_residue"
    return ghost_risk(s, bright_images, strength, px, py)


def ghost_risk(s: int, bright_images: list[int], strength: np.ndarray, px: np.ndarray, py: np.ndarray) -> str | None:
    """"ghost_risk" if a very bright star is near and the source cannot be shown to be independent of it.

    A reflection sits at a fixed place relative to its star on the detector, so when the star lies
    somewhere else on the detector in the second image the reflection moves on the sky. A source
    that is at the same sky position in two images in which the bright star is at least
    GHOST_MOVE_PX apart on the detector is not that star's reflection. Near a very bright star
    (GHOST_FLUX_MJY or saturated, within GHOST_RADIUS_PX) and without such a pair of images, the
    source is set aside as "ghost_risk".
    """
    n = strength.shape[1]
    for i in bright_images:
        near = [t for t in range(n) if t != s and strength[i, t] >= GHOST_FLUX_MJY
                and math.hypot(px[i, t] - px[i, s], py[i, t] - py[i, s]) < GHOST_RADIUS_PX]
        for t in near:
            if not any(j != i and math.hypot(px[j, t] - px[i, t], py[j, t] - py[i, t]) >= GHOST_MOVE_PX
                       for j in bright_images):
                return "ghost_risk"
    return None


# --- catalogues ---------------------------------------------------------------------------------------------------

CATALOGUE_RADIUS_ARCSEC = 20.0
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


def _glimpse(ra: float, dec: float, radius: float, fast_only: bool) -> list[dict[str, Any]]:
    """Spitzer GLIMPSE (3.6 to 8 micrometres, |b| < 1 or so, 2003 to 2008), through IRSA's Gator."""
    table = search._gator("glimpse_s07", ra, dec, radius, "designation,ra,dec,mag4_5,mag3_6")
    rows = []
    for d in table:
        sra, sdec = search._num(d["ra"]), search._num(d["dec"])
        if sra is None or sdec is None:
            continue
        m45 = search._num(d["mag4_5"])
        rows.append({"catalogue": "GLIMPSE", "name": f"GLIMPSE {search._text(d['designation'])}", "ra": sra,
                     "dec": sdec, "irac2": m45, "type": None, "variable": False})
    return rows


SERVICES = (("Gaia DR3", search._gaia), ("SIMBAD", search._simbad), ("AAVSO VSX", search._vsx),
            ("CatWISE2020", search._catwise), ("AllWISE", search._allwise), ("2MASS", _twomass),
            ("GLIMPSE", _glimpse))


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


def summarise(include_proof: bool = False) -> dict[str, Any]:
    """Totals over every finished tile: area, the tally at each stage, the survivors by kind."""
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
            kinds[k] = kinds.get(k, 0) + 1
            survivors.append({"tile": t["name"], "ra": round(sv["ra"], 5), "dec": round(sv["dec"], 5), "kind": k,
                              "bright_mjy": round(sv["pair"]["bright_mjy"], 1), "direction": sv.get("direction")})
    return {"tiles_done": len(done), "tiles_skipped": len(tiles) - len(done),
            "area_sq_deg": round(sum(t["area_sq_deg"] for t in done), 2), "tally": total,
            "survivors_by_kind": kinds, "survivors": survivors}

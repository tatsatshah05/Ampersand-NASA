"""Follow one known comet or asteroid through the SPHEREx survey and measure its spectrum.

The reverse of `backend/smallbodies.py`: there, a patch of sky is fixed and the bodies that cross it are
listed; here one body is fixed and the exposures that contain it are found.

Every SPHEREx exposure looks through a different colour of infrared light (102 channels, 0.75 to 5 micrometres),
so the exposures that happen to contain a moving body add up to a spectrum of it, one wavelength per exposure.

How it works (each step keeps its answers on disk, so a repeat asks nobody anything):

1. JPL Horizons gives the body's path as seen from the SPHEREx spacecraft itself (-163182), one row a day
   for the whole mission, with predicted magnitude, distance from the Sun and from SPHEREx, solar elongation.
2. Days when the elongation is in the range SPHEREx observes (measured, see ELONGATION_RANGE) are cut into chunks
   over which the body moves less than CHUNK_DEG. IRSA's image search is asked for the exposures covering the
   chunk's two end positions in the chunk's time range. (IRSA times out on a search circle wider than 0.01 degree,
   so a search is always a point.)
3. Horizons gives the exact position at the middle of each exposure found; the ones whose image footprint contains it
   with room for the sky ring are the exposures of the body.
4. A cutout centred on the predicted position is read from each. In it, the light inside a small circle and a larger
   one is added up, with the sky taken from a ring around the body. The same is done at ring places 100 arcsec away
   (the noise), and at the same sky place in exposures of other days (a star that happens to be there is still there).
5. One point per exposure: time, detector, wavelength, brightness with error, and a status.

`band_excess` then measures the gas bands against a continuum fitted to neighbouring channels, and says how it
compares with the same arithmetic done at empty places in the spectrum.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area

from . import photometry, pipeline, s3fetch, smallbodies, spherex

VERSION = 3  # part of every cache key: raise it when an answer changes
CACHE_DIR = spherex.CACHE / "follow"
CUTOUT_DIR = CACHE_DIR / "cutouts"  # kept apart from the shared cutouts of the viewer
CREDIT = "Orbits: NASA/JPL Solar System Dynamics (Horizons). Images: NASA/JPL-Caltech SPHEREx, NASA/IPAC IRSA."

MISSION_START = "2025-05-01"
# Solar elongations the exposure lists of two positions span (Barnard's Star 81.9 to 128.4 degrees, 364 exposures;
# Vesta's patch 80.5 to 121.8, 394 exposures: measured 2026-11-14 with astropy's Sun). The window is a little wider.
ELONGATION_RANGE = (70.0, 140.0)
CHUNK_DEG = 0.7  # a body is looked for at the ends of a path stretch no longer than this
CHUNK_DAYS = 10.0
SIA_RADIUS_DEG = 0.01  # IRSA's image search times out with a larger circle
SIA_THREADS = 3
EDGE_MARGIN_DEG = 0.03  # the sky ring needs this much image around the body
HORIZONS_BATCH = 50

CUTOUT_DEG = 0.2  # cutout width: the body, its ring and the neighbouring noise places fit
SMALL_PX = 2.0  # small circle radius: 12.3 arcsec, the radius the 3I/ATLAS paper used
LARGE_PX = 6.0  # large circle radius: 36.9 arcsec
SKY_PX = (14.0, 24.0)  # sky ring (86 to 148 arcsec)
NOISE_RING_PX = 16.0  # the noise places lie on a ring this far from the body
NOISE_PLACES = 8
EDGE_PX = SKY_PX[1] + 1
KM_PER_ARCSEC_AU = 725.27  # kilometres across one arcsec at one au

OTHER_PER_DETECTOR = 4  # exposures of other days measured at the same sky place
OTHER_MIN_DAYS = 1.0
OTHER_MIN_ARCSEC = 150.0  # the body must have been this far from the place in those exposures
CLUSTER_ARCSEC = 100.0  # exposures this close together share their "other days" cutouts
FIXED_SIGMA = 3.0
MAX_THREADS = 8

# Horizons does not take every body by name.
COMMANDS = {
    "pluto": "999",
    "chiron": "2060;",
    "makemake": "136472;",
    "eris": "136199;",
    "haumea": "136108;",
    "ceres": "1;",
    "vesta": "4;",
    "4 vesta": "4;",
    "3i/atlas": "DES=3I;CAP",
    "3i": "DES=3I;CAP",
    "c/2025 n1": "DES=C/2025 N1;CAP",
}

# Gas bands: window in micrometres, and the neighbouring continuum windows either side.
BANDS: dict[str, dict] = {
    "H2O": {"label": "water", "centre": 2.70, "window": (2.62, 2.86), "left": (2.40, 2.58), "right": (2.90, 3.05)},
    "CO2": {
        "label": "carbon dioxide",
        "centre": 4.26,
        "window": (4.20, 4.31),
        "left": (4.02, 4.17),
        "right": (4.38, 4.52),
    },
    "CO": {
        "label": "carbon monoxide",
        "centre": 4.67,
        "window": (4.62, 4.74),
        "left": (4.45, 4.58),
        "right": (4.80, 4.95),
    },
}
DETECT_SIGMA = 5.0
MARGINAL_SIGMA = 3.0
CONTROL_FACTOR = 3.0  # a detection must also stand this many times above the control scatter
CONTROL_MAX = 8  # control windows used each side

STATUSES = ("ok", "saturated", "flagged", "star_in_the_way", "off_image", "no_sky", "no_data", "not_fetched")


class FollowError(RuntimeError):
    """The body cannot be followed (Horizons does not know it, or a service could not be reached)."""


# --- the path ------------------------------------------------------------------------------------------------------


def horizons_command(name: str) -> str:
    name = name.strip()
    if re.fullmatch(r"\d+[PCDI]", name):  # "29P": a comet's number, no name after it
        return f"DES={name};CAP"
    return COMMANDS.get(name.lower()) or smallbodies.horizons_command(name)


def _table(command: str, time_params: dict[str, str]) -> list[dict]:
    """Horizons rows for the body as seen from SPHEREx: ra, dec, vmag, rate, r, delta, elong (and the date)."""
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "CENTER": f"'@{smallbodies.SPHEREX_HORIZONS_ID}'",
        "EPHEM_TYPE": "OBSERVER",
        "QUANTITIES": "'1,3,9,19,20,23'",
        "ANG_FORMAT": "DEG",
        "CSV_FORMAT": "YES",
        "OBJ_DATA": "NO",
        **time_params,
    }
    try:
        text = json.loads(smallbodies._jpl_get(smallbodies.HORIZONS_URL, params)).get("result") or ""
    except json.JSONDecodeError as e:
        raise FollowError("Horizons sent something that is not JSON") from e
    if "$$SOE" not in text:
        raise FollowError(f"Horizons could not give a path for {command!r}: {text.strip()[:200]!r}")
    return parse_horizons(text)


def parse_horizons(text: str) -> list[dict]:
    """Rows of a Horizons CSV ephemeris reply. Raises FollowError when a column is missing."""
    head, rest = text.split("$$SOE", 1)
    header = [h.strip() for h in head.strip().splitlines()[-2].split(",")]
    rows = [r for r in rest.split("$$EOE")[0].strip().splitlines() if r.strip()]
    try:
        i_ra, i_dec = header.index("R.A._(ICRF)"), header.index("DEC_(ICRF)")
        i_r, i_delta, i_el = header.index("r"), header.index("delta"), header.index("S-O-T")
        i_dra, i_ddec = header.index("dRA*cosD"), header.index("d(DEC)/dt")
    except ValueError as e:
        raise FollowError(f"Horizons answered with columns this code does not know: {header}") from e
    i_mag = next((header.index(h) for h in ("T-mag", "APmag", "V") if h in header), -1)
    out = []
    for row in rows:
        f = [x.strip() for x in row.split(",")]
        try:
            vmag = float(f[i_mag]) if i_mag >= 0 else None
        except ValueError:
            vmag = None
        out.append(
            {
                "date": f[0],
                "ra": float(f[i_ra]),
                "dec": float(f[i_dec]),
                "vmag": vmag,
                "rate_arcsec_h": float(np.hypot(float(f[i_dra]), float(f[i_ddec]))),
                "r_au": float(f[i_r]),
                "delta_au": float(f[i_delta]),
                "elong": float(f[i_el]),
            }
        )
    return out


def daily_path(name: str, start: str = MISSION_START, stop: str | None = None) -> list[dict]:
    """One row a day from `start` to `stop` (default today, UTC). Each row also has its mjd."""
    stop = stop or Time.now().iso[:10]
    rows = _table(horizons_command(name), {"START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": "'1 d'"})
    t0 = Time(start + " 00:00:00").mjd
    for i, r in enumerate(rows):
        r["mjd"] = t0 + i
    return rows


def positions_at(name: str, mjds: list[float]) -> list[dict]:
    """The same rows at exact times (UTC, MJD), a Horizons request for every HORIZONS_BATCH of them."""
    out: list[dict] = []
    command = horizons_command(name)
    for s in range(0, len(mjds), HORIZONS_BATCH):
        chunk = mjds[s : s + HORIZONS_BATCH]
        rows = _table(command, {"TLIST": " ".join(f"'{m + 2400000.5:.6f}'" for m in chunk)})
        if len(rows) != len(chunk):
            raise FollowError(f"Horizons gave {len(rows)} positions for {len(chunk)} times")
        for m, r in zip(chunk, rows, strict=True):
            r["mjd"] = m
        out += rows
    return out


def sep_deg(ra1: float, dec1: float, ra2, dec2):
    """Angular distance in degrees (haversine); arrays allowed for the second position."""
    r1, d1, r2, d2 = np.radians(ra1), np.radians(dec1), np.radians(ra2), np.radians(dec2)
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin((r2 - r1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(a)))


def chunks(path: list[dict], elong_range: tuple[float, float] = ELONGATION_RANGE) -> list[dict]:
    """Stretches of the daily path inside the elongation range, each short enough to search from its two ends.

    Returns [{t1, t2, ra1, dec1, ra2, dec2}] (MJD and degrees). A stretch ends when the body has moved CHUNK_DEG
    from where it began or CHUNK_DAYS have passed. A day on which the body is outside the range closes the stretch.
    """
    lo, hi = elong_range
    out: list[dict] = []
    cur: list[dict] = []

    def close() -> None:
        if cur:
            out.append(
                {
                    "t1": cur[0]["mjd"],
                    "t2": cur[-1]["mjd"] + 1.0,
                    "ra1": cur[0]["ra"],
                    "dec1": cur[0]["dec"],
                    "ra2": cur[-1]["ra"],
                    "dec2": cur[-1]["dec"],
                }
            )
            cur.clear()

    for row in path:
        if not lo <= row["elong"] <= hi:
            close()
            continue
        if cur and (
            row["mjd"] - cur[0]["mjd"] >= CHUNK_DAYS
            or float(sep_deg(cur[0]["ra"], cur[0]["dec"], row["ra"], row["dec"])) > CHUNK_DEG
        ):
            close()
        cur.append(row)
    close()
    return out


# --- finding the exposures -----------------------------------------------------------------------------------------


def parse_region(text: str) -> list[tuple[float, float]]:
    """Corners (ra, dec) of an SIA `s_region` such as 'POLYGON ICRS 24.5 -0.7 21.3 -2.0 ...' (closing one dropped)."""
    nums = [float(x) for x in text.split()[2:]]
    corners = list(zip(nums[0::2], nums[1::2], strict=False))
    return corners[:-1] if len(corners) > 1 and corners[0] == corners[-1] else corners


def parse_sia(raw: bytes) -> list[dict]:
    """Exposures from an IRSA image-search answer (VOTable), with their footprint."""
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    out = []
    for row in table:
        out.append(
            {
                "obs_id": str(row["obs_id"]),
                "detector": int(str(row["energy_bandpassname"])[-1]),
                "mjd": float(row["t_min"]),
                "exptime": float(row["t_exptime"]),
                "url": str(row["access_url"]),
                "collection": str(row["obs_collection"]),
                "wave_min": float(row["em_min"]) * 1e6,
                "wave_max": float(row["em_max"]) * 1e6,
                "region": parse_region(str(row["s_region"])),
            }
        )
    return out


def _sia_point(ra: float, dec: float, t1: float, t2: float) -> list[dict]:
    """Exposures covering one point in a time range, in every collection. Cached."""
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f},{t1:.4f},{t2:.4f}".encode()).hexdigest()[:20]
    file = CACHE_DIR / "sia" / f"{key}.json"
    if file.exists():
        return json.loads(file.read_text())
    rows: list[dict] = []
    for coll in spherex.COLLECTIONS:
        raw = spherex.http_get(
            spherex.SIA_URL,
            {"COLLECTION": coll, "POS": f"circle {ra:.6f} {dec:.6f} {SIA_RADIUS_DEG}", "TIME": f"{t1:.4f} {t2:.4f}"},
            tries=6,
            timeout=60,
        )
        rows += parse_sia(raw)
    spherex.write_json(file, rows)
    return rows


def _retry(fn, *args, times: int = 4, pause: float = 60.0):
    """Call fn; when the archive cannot be reached, wait a minute and try again (the network may have dropped)."""
    for attempt in range(times):
        try:
            return fn(*args)
        except spherex.ArchiveError:
            if attempt == times - 1:
                raise
            time.sleep(pause)


def find_candidates(stretches: list[dict], progress: Callable[[str, int, int], None] | None = None) -> list[dict]:
    """Every exposure the image search lists for the ends of the stretches, once each, oldest first."""
    jobs = []
    for c in stretches:
        jobs.append((c["ra1"], c["dec1"], c["t1"], c["t2"]))
        if sep_deg(c["ra1"], c["dec1"], c["ra2"], c["dec2"]) > 0.05:
            jobs.append((c["ra2"], c["dec2"], c["t1"], c["t2"]))
    seen: dict[tuple[str, int], dict] = {}
    done = 0
    with ThreadPoolExecutor(SIA_THREADS) as pool:
        for rows in pool.map(lambda j: _retry(_sia_point, *j), jobs):
            for e in rows:
                seen.setdefault((e["obs_id"], e["detector"]), e)
            done += 1
            if progress:
                progress("searching the archive", done, len(jobs))
    return sorted(seen.values(), key=lambda e: e["mjd"])


def mid_mjd(exp: dict) -> float:
    return smallbodies.exposure_mid_mjd(exp)


def edge_distance_deg(corners: list[tuple[float, float]], ra: float, dec: float) -> float:
    """Distance from a point to the nearest edge of a footprint, positive inside and negative outside (flat sky)."""
    ra0 = float(np.mean([c[0] for c in corners]))
    dec0 = float(np.mean([c[1] for c in corners]))
    cos = np.cos(np.radians(dec0))

    def flat(r: float, d: float) -> tuple[float, float]:
        return ((r - ra0 + 180.0) % 360.0 - 180.0) * cos, d - dec0

    poly = [flat(*c) for c in corners]
    px, py = flat(ra, dec)
    inside = False
    best = np.inf
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            inside = not inside
        dx, dy = x2 - x1, y2 - y1
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        best = min(best, float(np.hypot(px - (x1 + t * dx), py - (y1 + t * dy))))
    return best if inside else -best


def select_exposures(candidates: list[dict], positions: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split candidates into (usable, near_edge): exposures whose footprint holds the body's predicted position
    with EDGE_MARGIN_DEG to spare, and those that hold it closer to the edge (or not at all: dropped).

    Each returned exposure carries `pred` (the Horizons row at its mid-time) and `edge_deg`.
    """
    usable, near = [], []
    for e, p in zip(candidates, positions, strict=True):
        d = edge_distance_deg(e["region"], p["ra"], p["dec"])
        if d >= EDGE_MARGIN_DEG:
            usable.append({**e, "pred": p, "edge_deg": d})
        elif d >= 0:
            near.append({**e, "pred": p, "edge_deg": d})
    return usable, near


# --- measuring -----------------------------------------------------------------------------------------------------


def load_cutout(path: Path) -> dict:
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype("float64")
        flags = hdul["FLAGS"].data
        variance = hdul["VARIANCE"].data.astype("float64")
        zodi = hdul["ZODI"].data.astype("float64")
        wave = hdul["WAVE"].data
        band = hdul["BANDWIDTH"].data
    wcs = WCS(header)
    data = image - zodi
    data[pipeline.impossible_pixels(image, variance)] = np.nan
    return {
        "wcs": wcs,
        "data": data,
        "flags": flags,
        "variance": variance,
        "wave": wave,
        "band": band,
        "mjd": float(header["MJD-AVG"]),
        "to_mjy": float(proj_plane_pixel_area(wcs)) * (np.pi / 180.0) ** 2 * 1e9,
    }


def measure_at(c: dict, ra: float, dec: float) -> dict:
    """Light at (ra, dec) in a loaded cutout: the small and the large circle, sky from the ring."""
    out: dict = {
        "status": "off_image",
        "wavelength_um": None,
        "bandwidth_um": None,
        "flags": [],
        "flux_mjy": None,
        "err_mjy": None,
        "flux_large_mjy": None,
        "err_large_mjy": None,
        "status_large": "off_image",
    }
    px, py = c["wcs"].all_world2pix(ra, dec, 0)
    x, y = float(px), float(py)
    ny, nx = c["data"].shape
    if not (EDGE_PX <= x < nx - EDGE_PX and EDGE_PX <= y < ny - EDGE_PX):
        return out
    xi, yi = int(round(x)), int(round(y))
    wavelength, bandwidth = float(c["wave"][yi, xi]), float(c["band"][yi, xi])
    if not (np.isfinite(wavelength) and np.isfinite(bandwidth)):
        out["status"] = out["status_large"] = "no_data"
        return out
    out["wavelength_um"], out["bandwidth_um"] = wavelength, bandwidth
    half = int(SKY_PX[1]) + 3
    x0, y0 = xi - half, yi - half
    sl = (slice(y0, yi + half + 1), slice(x0, xi + half + 1))
    data, flags, variance = c["data"][sl], c["flags"][sl], c["variance"][sl]
    yy, xx = np.mgrid[0 : data.shape[0], 0 : data.shape[1]]
    lx, ly = x - x0, y - y0
    r = np.hypot(xx - lx, yy - ly)
    ring = (r >= SKY_PX[0]) & (r < SKY_PX[1]) & np.isfinite(data)
    in_sky = ring & ((flags & photometry.SKY_BAD) == 0)
    if in_sky.sum() < 100:
        in_sky = ring & ((flags & (photometry.SKY_BAD & ~pipeline._mask("SOURCE", "OUTLIER"))) == 0)
    if in_sky.sum() < 100:
        out["status"] = out["status_large"] = "no_sky"
        return out
    _, sky, sky_sigma = sigma_clipped_stats(data[in_sky], sigma=3.0, maxiters=5)
    sky_var = float(sky_sigma) ** 2 / int(in_sky.sum())
    small = photometry._sum_region(
        photometry._coverage(xx, yy, lx, ly, 0.0, SMALL_PX), data, variance, flags, float(sky), sky_var, c["to_mjy"]
    )
    large = photometry._sum_region(
        photometry._coverage(xx, yy, lx, ly, 0.0, LARGE_PX),
        data,
        variance,
        flags,
        float(sky),
        sky_var,
        c["to_mjy"],
        max_flagged=photometry.WING_MAX_FLAGGED,
    )
    out.update(
        status=small["status"],
        flux_mjy=small["value"],
        err_mjy=small["error"],
        flags=small["flags"],
        flux_large_mjy=large["value"],
        err_large_mjy=large["error"],
        status_large=large["status"],
    )
    return out


def noise_places(ra: float, dec: float) -> list[tuple[float, float]]:
    d = NOISE_RING_PX * pipeline.NATIVE_ARCSEC / 3600.0
    return [
        (ra + d * np.cos(a) / max(np.cos(np.radians(dec)), 0.05), dec + d * np.sin(a))
        for a in 2.0 * np.pi * np.arange(NOISE_PLACES) / NOISE_PLACES
    ]


def local_noise(c: dict, ra: float, dec: float) -> dict:
    """Scatter (from the median absolute deviation) of the same two measurements at empty places round the body."""
    small, large = [], []
    for r, d in noise_places(ra, dec):
        m = measure_at(c, r, d)
        if m["status"] == "ok":
            small.append(m["flux_mjy"])
        if m["status_large"] == "ok":
            large.append(m["flux_large_mjy"])

    def mad(v: list[float]) -> float | None:
        return round(1.4826 * float(np.median(np.abs(np.asarray(v) - np.median(v)))), 5) if len(v) >= 5 else None

    return {"noise_mjy": mad(small), "noise_large_mjy": mad(large), "n_places": len(small)}


def fixed_source_verdict(flux: float | None, others: list[dict]) -> dict:
    """Is something fixed at this sky place? `others` are the same-place measurements in exposures of other days."""
    ok = [o for o in others if o["status"] == "ok" and o["flux_mjy"] is not None and o["err_mjy"]]
    n_src = sum(o["flux_mjy"] / o["err_mjy"] >= FIXED_SIGMA for o in ok)
    med = float(np.median([o["flux_mjy"] for o in ok])) if ok else None
    fixed = len(ok) >= 3 and n_src * 2 > len(ok)
    in_the_way = bool(fixed and flux and med is not None and med > 0.2 * flux)
    return {
        "n_measured": len(ok),
        "n_with_source": n_src,
        "median_flux_mjy": None if med is None else round(med, 4),
        "fixed": fixed,
        "star_in_the_way": in_the_way,
    }


# --- the whole thing -----------------------------------------------------------------------------------------------


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _cutout_file(slug: str, kind: str, exp: dict, ra: float, dec: float) -> Path:
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{CUTOUT_DEG}".encode()).hexdigest()[:8]
    return CUTOUT_DIR / slug / kind / f"{exp['obs_id']}_D{exp['detector']}_{tag}.fits"


def clusters(exposures: list[dict]) -> list[list[int]]:
    """Indexes of exposures (by time) that lie within CLUSTER_ARCSEC of the first of their group."""
    groups: list[list[int]] = []
    for i, e in enumerate(exposures):
        p = e["pred"]
        for g in groups:
            q = exposures[g[0]]["pred"]
            if (
                float(sep_deg(q["ra"], q["dec"], p["ra"], p["dec"])) * 3600.0 <= CLUSTER_ARCSEC
                and abs(exposures[g[0]]["mjd"] - e["mjd"]) < 30.0
            ):
                g.append(i)
                break
        else:
            groups.append([i])
    return groups


def interpolate(path: list[dict], mjd: float) -> tuple[float, float]:
    i = int(np.clip(np.searchsorted([r["mjd"] for r in path], mjd) - 1, 0, len(path) - 2))
    a, b = path[i], path[i + 1]
    f = (mjd - a["mjd"]) / (b["mjd"] - a["mjd"])
    d_ra = (b["ra"] - a["ra"] + 180.0) % 360.0 - 180.0
    return (a["ra"] + f * d_ra) % 360.0, a["dec"] + f * (b["dec"] - a["dec"])


def other_days(
    exps_here: list[dict], centre: tuple[float, float], detector: int, path: list[dict], here_mjd: float
) -> list[dict]:
    """Up to OTHER_PER_DETECTOR exposures of this detector, on other days, with the body far from this place."""
    lst = spherex.find_exposures(*centre)
    eligible = []
    for e in lst:
        if e["detector"] != detector or abs(e["mjd"] - here_mjd) < OTHER_MIN_DAYS:
            continue
        if "region" in e and edge_distance_deg(e["region"], centre[0], centre[1]) < EDGE_MARGIN_DEG + 0.02:
            continue  # near the edge of that image: the cutout would be cut short
        ra, dec = interpolate(path, e["mjd"])
        if float(sep_deg(centre[0], centre[1], ra, dec)) * 3600.0 > OTHER_MIN_ARCSEC:
            eligible.append(e)
    if len(eligible) <= OTHER_PER_DETECTOR:
        return eligible
    idx = np.linspace(0, len(eligible) - 1, OTHER_PER_DETECTOR).round().astype(int)
    return [eligible[i] for i in sorted(set(idx.tolist()))]


_reader: s3fetch.S3Reader | None = None
_reader_lock = threading.Lock()
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _shared_reader() -> s3fetch.S3Reader:
    """One connection pool to NASA's S3 copy for every cutout this module reads."""
    global _reader
    with _reader_lock:
        if _reader is None:
            _reader = s3fetch.S3Reader(s3fetch.DEFAULT_CONCURRENCY)
        return _reader


def _note_failure(exp: dict, file: Path, err: Exception, seconds: float) -> None:
    """Keep a line about each cutout S3 could not give (the reason, and how long it took to find out)."""
    with _reader_lock, (CACHE_DIR / "s3_failures.log").open("a") as f:
        f.write(
            f"{seconds:6.1f}s {exp['obs_id']} D{exp['detector']} {file.name}: {type(err).__name__}: {str(err)[:160]}\n"
        )


def _fetch(exp: dict, ra: float, dec: float, file: Path, quick: bool = False) -> Path | None:
    """The cutout, or None. Read from NASA's S3 copy; `quick` gives up there (an image whose edge cuts the cutout
    short is not asked of IRSA's slower service: for exposures of other days there are always others), otherwise
    IRSA's cutout service is the fallback."""
    started = time.monotonic()
    try:
        if spherex.use_s3():
            try:
                return s3fetch.fetch_cutout(exp, ra, dec, CUTOUT_DEG, file, reader=_shared_reader())
            except Exception as err:  # noqa: BLE001
                _note_failure(exp, file, err, time.monotonic() - started)
                if quick:
                    return None
        return spherex.fetch_cutout(exp, ra, dec, CUTOUT_DEG, path=file)
    except Exception:  # noqa: BLE001 - a cutout that cannot be had is reported as not_fetched, never replaced
        return None


STALL_S = 90.0  # cutouts still unread this long after the last one arrived are given up


def _fetch_all(
    jobs: list[tuple[dict, float, float, Path]], quick: bool, say: Callable[..., None], stage: str
) -> list[Path | None]:
    """Fetch the jobs MAX_THREADS at a time, reporting progress as each finishes. Results are in the order given.

    A few reads now and then hang on a half-dead connection; when nothing has arrived for STALL_S seconds the ones
    still outstanding are given up (they come back as None, and the point says `not_fetched`).
    """
    out: list[Path | None] = [None] * len(jobs)
    pool = ThreadPoolExecutor(MAX_THREADS)
    futures = {pool.submit(_fetch, e, ra, dec, f, quick): i for i, (e, ra, dec, f) in enumerate(jobs)}
    pending = set(futures)
    done = 0
    while pending:
        finished, pending = wait(pending, timeout=STALL_S, return_when=FIRST_COMPLETED)
        if not finished:
            say(stage + ": giving up on", len(pending), len(jobs))
            break
        for fut in finished:
            out[futures[fut]] = fut.result()
            done += 1
        say(stage, done, len(jobs))
    pool.shutdown(wait=False, cancel_futures=True)
    return out


def follow_body(
    name: str,
    stop: str | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    max_exposures: int | None = None,
) -> dict:
    """Follow `name` through the SPHEREx survey (see the module text). Cached as a whole on disk.

    Returns the points (one per exposure containing the body), the path summary, counts at every step and the
    band measurements. `max_exposures` keeps only that many exposures, spread evenly in time (for a quick look).
    """

    def say(stage: str, i: int = 0, n: int = 0) -> None:
        if progress:
            progress(stage, i, n)

    slug = _slug(name)
    stop = stop or Time.now().iso[:10]
    key = hashlib.sha1(f"v{VERSION},{slug},{stop},{max_exposures}".encode()).hexdigest()[:12]
    cache = CACHE_DIR / "results" / f"{slug}_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    say("asking JPL Horizons for the path")
    path = daily_path(name, MISSION_START, stop)
    stretches = chunks(path)
    say("searching the archive", 0, len(stretches))
    candidates = find_candidates(stretches, progress)
    say("asking Horizons for the position in each exposure")
    positions = positions_at(name, [mid_mjd(e) for e in candidates]) if candidates else []
    usable, near = select_exposures(candidates, positions)
    n_usable_all = len(usable)
    if max_exposures and len(usable) > max_exposures:
        idx = np.linspace(0, len(usable) - 1, max_exposures).round().astype(int)
        usable = [usable[i] for i in sorted(set(idx.tolist()))]
    result: dict = {
        "name": name,
        "version": VERSION,
        "credit": CREDIT,
        "observer": smallbodies.OBSERVER,
        "stop": stop,
        "path_days": len(path),
        "days_in_survey_range": sum(ELONGATION_RANGE[0] <= r["elong"] <= ELONGATION_RANGE[1] for r in path),
        "elongation_range": ELONGATION_RANGE,
        "stretches": len(stretches),
        "n_candidates": len(candidates),
        "n_in_footprint": n_usable_all + len(near),
        "n_near_edge": len(near),
        "n_followed": len(usable),
        "radii": {
            "small_arcsec": round(SMALL_PX * pipeline.NATIVE_ARCSEC, 1),
            "large_arcsec": round(LARGE_PX * pipeline.NATIVE_ARCSEC, 1),
            "sky_ring_arcsec": [round(SKY_PX[0] * pipeline.NATIVE_ARCSEC), round(SKY_PX[1] * pipeline.NATIVE_ARCSEC)],
        },
        "vmag_range": [None, None],
        "points": [],
        "problems": [],
    }
    mags = [
        p["vmag"] for p in path if p["vmag"] is not None and ELONGATION_RANGE[0] <= p["elong"] <= ELONGATION_RANGE[1]
    ]
    if mags:
        result["vmag_range"] = [round(min(mags), 1), round(max(mags), 1)]
    if not usable:
        spherex.write_json(cache, result)
        return result

    # cutouts of the exposures themselves
    say("reading the images", 0, len(usable))
    own_files = [_cutout_file(slug, "own", e, e["pred"]["ra"], e["pred"]["dec"]) for e in usable]
    got = _fetch_all(
        [(e, e["pred"]["ra"], e["pred"]["dec"], f) for e, f in zip(usable, own_files, strict=True)],
        False,
        say,
        "reading the images",
    )

    # the same sky place in exposures of other days
    groups = clusters(usable)

    def _list(c: tuple[float, float]) -> None:
        try:
            _retry(spherex.find_exposures, *c)
        except spherex.ArchiveError:
            pass  # reported below, where the list is needed

    say("asking the archive which exposures cover each place", 0, len(groups))
    with ThreadPoolExecutor(SIA_THREADS) as pool:  # each of these searches takes 20 s or more
        list(pool.map(_list, [(usable[g[0]]["pred"]["ra"], usable[g[0]]["pred"]["dec"]) for g in groups]))
    others_for: dict[int, list[tuple[dict, Path]]] = {}
    fetch_jobs: list[tuple[dict, float, float, Path]] = []
    for gi, g in enumerate(groups):
        first = usable[g[0]]["pred"]
        centre = (first["ra"], first["dec"])
        say("choosing exposures of other days", gi + 1, len(groups))
        by_det: dict[int, list[dict]] = {}
        for i in g:
            det = usable[i]["detector"]
            if det not in by_det:
                try:
                    by_det[det] = other_days(usable, centre, det, path, usable[i]["mjd"])
                except spherex.ArchiveError as exc:
                    by_det[det] = []
                    result["problems"].append(f"exposure list for {centre[0]:.3f},{centre[1]:.3f}: {exc}")
            others_for[i] = [(o, _cutout_file(slug, "other", o, *centre)) for o in by_det[det]]
            for o, f in others_for[i]:
                fetch_jobs.append((o, centre[0], centre[1], f))
    unique = {f: (o, ra, dec) for o, ra, dec, f in fetch_jobs}
    keys = list(unique)
    results = _fetch_all(
        [(unique[f][0], unique[f][1], unique[f][2], f) for f in keys], True, say, "reading images of other days"
    )
    fetched = dict(zip(keys, results, strict=True))

    say("measuring", 0, len(usable))
    for n, (e, f, ok) in enumerate(zip(usable, own_files, got, strict=True)):
        p = e["pred"]
        mid = mid_mjd(e)
        point: dict = {
            "obs_id": e["obs_id"],
            "detector": e["detector"],
            "mjd": round(mid, 6),
            "time": Time(mid, format="mjd").isot[:19] + "Z",
            "ra": round(p["ra"], 7),
            "dec": round(p["dec"], 7),
            "predicted_mag": p["vmag"],
            "r_au": p["r_au"],
            "delta_au": p["delta_au"],
            "elong_deg": p["elong"],
            "rate_arcsec_h": round(p["rate_arcsec_h"], 1),
            "edge_deg": round(e["edge_deg"], 3),
            "radius_small_km": round(SMALL_PX * pipeline.NATIVE_ARCSEC * KM_PER_ARCSEC_AU * p["delta_au"]),
            "radius_large_km": round(LARGE_PX * pipeline.NATIVE_ARCSEC * KM_PER_ARCSEC_AU * p["delta_au"]),
            "status": "not_fetched",
            "wavelength_um": None,
            "bandwidth_um": None,
            "flux_mjy": None,
            "err_mjy": None,
            "flux_large_mjy": None,
            "err_large_mjy": None,
            "noise_mjy": None,
            "noise_large_mjy": None,
            "sigma": None,
            "sigma_noise": None,
            "other_days": None,
            "flags": [],
            "file": str(f),
        }
        if ok is not None:
            try:
                c = load_cutout(ok)
                m = measure_at(c, p["ra"], p["dec"])
                point.update(
                    {
                        k: m[k]
                        for k in (
                            "status",
                            "wavelength_um",
                            "bandwidth_um",
                            "flux_mjy",
                            "err_mjy",
                            "flux_large_mjy",
                            "err_large_mjy",
                            "flags",
                        )
                    }
                )
                point["status_large"] = m["status_large"]
                if m["status"] == "ok":
                    point.update(local_noise(c, p["ra"], p["dec"]))
                    point["sigma"] = round(m["flux_mjy"] / m["err_mjy"], 2)  # over the full error (with 3% systematic)
                    noise = point["noise_mjy"]
                    point["sigma_noise"] = (
                        round(m["flux_mjy"] / noise, 1) if noise else None
                    )  # over the empty-place scatter
                    meas = []
                    point["other_files"] = []
                    for _o, of in others_for.get(n, []):
                        fp = fetched.get(of)
                        if fp:
                            point["other_files"].append(str(of))
                            mo = measure_at(load_cutout(fp), p["ra"], p["dec"])
                            meas.append({"status": mo["status"], "flux_mjy": mo["flux_mjy"], "err_mjy": mo["err_mjy"]})
                    v = fixed_source_verdict(m["flux_mjy"], meas)
                    point["other_days"] = v
                    if v["star_in_the_way"]:
                        point["status"] = "star_in_the_way"
            except Exception as err:  # noqa: BLE001 - say why this one point is empty and go on
                point["status"] = "not_fetched"
                point["problem"] = f"{type(err).__name__}: {err}"
        result["points"].append(point)
        say("measuring", n + 1, len(usable))
    result["counts"] = {s: sum(pt["status"] == s for pt in result["points"]) for s in STATUSES}
    result["bands"] = all_bands(result["points"])
    result["bands_large"] = all_bands(result["points"], "flux_large_mjy")
    spherex.write_json(cache, result, indent=1)
    return result


# --- the gas bands -------------------------------------------------------------------------------------------------


def visits(points: list[dict], gap_days: float = 4.0, span_days: float = 15.0) -> list[list[dict]]:
    """Points grouped into visits: a gap over gap_days or a span over span_days starts a new one."""
    pts = sorted(points, key=lambda p: p["mjd"])
    groups: list[list[dict]] = []
    for p in pts:
        if groups and p["mjd"] - groups[-1][-1]["mjd"] <= gap_days and p["mjd"] - groups[-1][0]["mjd"] <= span_days:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def band_excess(
    wave: np.ndarray,
    flux: np.ndarray,
    err: np.ndarray,
    window: tuple[float, float],
    left: tuple[float, float],
    right: tuple[float, float],
    one_sided: bool = False,
) -> dict:
    """Mean excess over a straight-line continuum fitted to the neighbouring channels.

    Points inside `window` are compared with a line (flux against wavelength) fitted, weighted by the errors, to the
    points inside `left` and `right`. The error adds the points' own errors and the fit's, the fit's error enlarged
    by the scatter about the line when that is larger than the errors say. Needs one point in the window, and at
    least three continuum points with some on each side; otherwise `ok` is False. With `one_sided`, channels on one
    side only (at least two) are enough, and the continuum is then a flat level (`one_sided` is True in the answer).
    Returns {ok, n_band, n_left, n_right, excess_mjy, err_mjy, sigma, reduced_chi2}.
    """
    wave, flux, err = (np.asarray(a, float) for a in (wave, flux, err))
    band = (wave >= window[0]) & (wave <= window[1])
    lo = (wave >= left[0]) & (wave <= left[1])
    hi = (wave >= right[0]) & (wave <= right[1])
    out: dict = {
        "ok": False,
        "n_band": int(band.sum()),
        "n_left": int(lo.sum()),
        "n_right": int(hi.sum()),
        "excess_mjy": None,
        "err_mjy": None,
        "sigma": None,
        "reduced_chi2": None,
    }
    side = lo | hi
    two_sided = lo.sum() >= 1 and hi.sum() >= 1 and side.sum() >= 3
    if band.sum() < 1 or not (two_sided or (one_sided and side.sum() >= 2)):
        return out
    out["one_sided"] = not two_sided
    x0 = 0.5 * (window[0] + window[1])
    n_par = 2 if two_sided else 1  # a line, or (with channels on one side only) a flat level

    def design(sel: np.ndarray) -> np.ndarray:
        cols = [np.ones(int(sel.sum()))] + ([wave[sel] - x0] if two_sided else [])
        return np.vstack(cols).T

    a = design(side)
    w = 1.0 / np.maximum(err[side], 1e-12) ** 2
    cov = np.linalg.inv(a.T @ (a * w[:, None]))
    beta = cov @ (a.T @ (w * flux[side]))
    resid = flux[side] - a @ beta
    dof = int(side.sum()) - n_par
    chi2 = float(np.sum(w * resid**2)) / dof if dof > 0 else 1.0
    cov = cov * max(chi2, 1.0)
    ab = design(band)
    cont = ab @ beta
    var_cont = float(np.mean(np.einsum("ij,jk,ik->i", ab, cov, ab)))
    excess = float(np.mean(flux[band] - cont))
    var = float(np.sum(err[band] ** 2)) / int(band.sum()) ** 2 + var_cont
    out.update(
        ok=True, excess_mjy=excess, err_mjy=float(np.sqrt(var)), sigma=excess / float(np.sqrt(var)), reduced_chi2=chi2
    )
    return out


def control_sigmas(wave, flux, err, window, left, right, lo=0.75, hi=5.0) -> list[float]:
    """The same arithmetic with the three windows (continuum, band, continuum) slid along the spectrum.

    The set is moved in steps of half its own width, and a place is used only when none of its three windows touches
    the real band window (0.02 micrometre of margin), and the arithmetic works there (a point in the band window and
    some on each side). A calibration feature, a star in the way or just noisy channels show up in these numbers.
    """
    total = right[1] - left[0]
    out = []
    for k in [i for i in range(-2 * CONTROL_MAX, 2 * CONTROL_MAX + 1) if i != 0]:
        s = k * total / 2.0
        wins = [(window[0] + s, window[1] + s), (left[0] + s, left[1] + s), (right[0] + s, right[1] + s)]
        if min(w[0] for w in wins) < lo or max(w[1] for w in wins) > hi:
            continue
        if any(w[0] < window[1] + 0.02 and w[1] > window[0] - 0.02 for w in wins):
            continue
        r = band_excess(wave, flux, err, wins[0], wins[1], wins[2])
        if r["ok"]:
            out.append(r["sigma"])
    return out


def classify(sigma: float | None, controls: list[float]) -> str:
    """ "detected", "marginal" or "not seen" (see DETECT_SIGMA, MARGINAL_SIGMA, CONTROL_FACTOR)."""
    if sigma is None:
        return "no measurement"
    scatter = (
        1.4826 * float(np.median(np.abs(np.asarray(controls) - np.median(controls)))) if len(controls) >= 4 else None
    )
    if sigma >= DETECT_SIGMA and scatter is not None and sigma >= CONTROL_FACTOR * max(scatter, 1.0):
        return "detected"
    if sigma >= MARGINAL_SIGMA:
        return "marginal"
    return "not seen"


def all_bands(points: list[dict], which: str = "flux_mjy") -> list[dict]:
    """For each visit and each gas band: excess over the neighbouring continuum, its error, and the verdict.

    Uses the ok points of the visit. `which` is "flux_mjy" (small circle) or "flux_large_mjy" (large circle).
    """
    errkey = "err_mjy" if which == "flux_mjy" else "err_large_mjy"
    out = []
    for g in visits([p for p in points if p["status"] == "ok" and p.get(which) is not None and p.get(errkey)]):
        w = np.array([p["wavelength_um"] for p in g])
        f = np.array([p[which] for p in g])
        e = np.array([p[errkey] for p in g])
        row = {
            "first": g[0]["time"],
            "last": g[-1]["time"],
            "n_points": len(g),
            "circle": which,
            "r_au": float(np.mean([p["r_au"] for p in g])),
            "delta_au": float(np.mean([p["delta_au"] for p in g])),
            "bands": {},
        }
        for key, b in BANDS.items():
            res = band_excess(w, f, e, b["window"], b["left"], b["right"])
            ctrl = control_sigmas(w, f, e, b["window"], b["left"], b["right"])
            res["controls"] = [round(c, 2) for c in ctrl]
            res["verdict"] = classify(res["sigma"], ctrl)
            res["integral_mjy_um"] = None if not res["ok"] else res["excess_mjy"] * (b["window"][1] - b["window"][0])
            row["bands"][key] = res
        out.append(row)
    return out


def band_by_night(points: list[dict], which: str = "flux_mjy") -> list[dict]:
    """The band arithmetic done separately for each stretch of observing (points less than 0.6 day apart, at most
    1.5 days in all), so a feature that shows on several separate days can be counted.

    Within one stretch the body is the same and consecutive exposures of a detector step along the spectrum within
    minutes, so neighbouring channels are a fair continuum. One-sided continua are allowed (flat level) and said so.
    Returns [{first, last, n_points, bands: {name: band_excess result}}]; there are no control windows at this scale,
    so nothing here is called a detection: `sigma` is the formal significance only.
    """
    errkey = "err_mjy" if which == "flux_mjy" else "err_large_mjy"
    ok = sorted(
        (p for p in points if p["status"] == "ok" and p.get(which) is not None and p.get(errkey)),
        key=lambda p: p["mjd"],
    )
    groups: list[list[dict]] = []
    for p in ok:
        if groups and p["mjd"] - groups[-1][-1]["mjd"] < 0.6 and p["mjd"] - groups[-1][0]["mjd"] <= 1.5:
            groups[-1].append(p)
        else:
            groups.append([p])
    out = []
    for g in groups:
        w = np.array([p["wavelength_um"] for p in g])
        f = np.array([p[which] for p in g])
        e = np.array([p[errkey] for p in g])
        bands = {k: band_excess(w, f, e, b["window"], b["left"], b["right"], one_sided=True) for k, b in BANDS.items()}
        out.append({"first": g[0]["time"], "last": g[-1]["time"], "n_points": len(g), "bands": bands})
    return out


SEQUENCE_GAP_DAYS = 15.0 / 1440.0  # exposures of one detector this close in time belong to one sequence
SCAN_WIDTH_UM = 0.11
SCAN_REACH_UM = 0.35
SCAN_STEP_UM = 0.036


def sequences(points: list[dict]) -> list[list[dict]]:
    """Runs of ok points of one detector taken less than 15 minutes apart. The detectors step through their
    wavelengths one exposure after another, so a run is a short stretch of the body's spectrum measured within minutes,
    the body, the sky and the detector all being the same."""
    ok = sorted(
        (p for p in points if p["status"] == "ok" and p.get("flux_mjy") is not None and p.get("err_mjy")),
        key=lambda p: (p["detector"], p["mjd"]),
    )
    runs: list[list[dict]] = []
    for p in ok:
        if runs and runs[-1][-1]["detector"] == p["detector"] and p["mjd"] - runs[-1][-1]["mjd"] < SEQUENCE_GAP_DAYS:
            runs[-1].append(p)
        else:
            runs.append([p])
    return [r for r in runs if len(r) >= 3]


def scan_sequences(points: list[dict], which: str = "flux_mjy") -> list[dict]:
    """In every sequence, slide a window of SCAN_WIDTH_UM along the wavelengths measured and compare the channels in
    it with the others of the sequence within SCAN_REACH_UM (a line through them, or a flat level when they are on one
    side only). One entry per window: {time, detector, centre, excess_mjy, err_mjy, sigma, one_sided}.

    The windows that fall on a gas band are the measurement; all the others, at wavelengths where no gas band is
    expected, say how often the same arithmetic gives a large number for no reason (a star, a change of the body's
    brightness during the sequence, a calibration step).
    """
    errkey = "err_mjy" if which == "flux_mjy" else "err_large_mjy"
    out = []
    for run in sequences(points):
        w = np.array([p["wavelength_um"] for p in run])
        f = np.array([p[which] if p.get(which) is not None else np.nan for p in run])
        e = np.array([p[errkey] if p.get(errkey) else np.nan for p in run])
        good = np.isfinite(f) & np.isfinite(e)
        if good.sum() < 3:
            continue
        w, f, e = w[good], f[good], e[good]
        for c in np.arange(w.min(), w.max() + 1e-9, SCAN_STEP_UM):
            lo, hi = c - SCAN_WIDTH_UM / 2, c + SCAN_WIDTH_UM / 2
            r = band_excess(w, f, e, (lo, hi), (c - SCAN_REACH_UM, lo - 1e-6), (hi + 1e-6, c + SCAN_REACH_UM), True)
            if r["ok"]:
                out.append(
                    {
                        "time": run[0]["time"],
                        "detector": run[0]["detector"],
                        "centre": float(c),
                        "excess_mjy": r["excess_mjy"],
                        "err_mjy": r["err_mjy"],
                        "sigma": r["sigma"],
                        "one_sided": r["one_sided"],
                        "n_band": r["n_band"],
                    }
                )
    return out


def scan_summary(scan: list[dict]) -> dict:
    """For each gas band: the sequences whose windows on the band reach 5 times their error, and how often windows
    away from every gas band (more than 0.2 micrometre from the three) reach it too."""
    centres = [b["centre"] for b in BANDS.values()]
    null = [s for s in scan if all(abs(s["centre"] - c) > 0.2 for c in centres)]
    out: dict = {
        "null_windows": len(null),
        "null_ge5": sum(s["sigma"] >= DETECT_SIGMA for s in null),
        "null_le_minus5": sum(s["sigma"] <= -DETECT_SIGMA for s in null),
        "bands": {},
    }
    for k, b in BANDS.items():
        on = [s for s in scan if abs(s["centre"] - b["centre"]) <= 0.05]
        times = sorted({s["time"][:10] for s in on if s["sigma"] >= DETECT_SIGMA})
        out["bands"][k] = {
            "windows_on_band": len(on),
            "nights_with_5_sigma": times,
            "best": max(on, key=lambda s: s["sigma"]) if on else None,
        }
    return out


def flux_ratio(a: dict, b: dict) -> dict | None:
    """Ratio of the band-integrated excess (mJy x micrometre) of a to b: a ratio of fluxes, not of production rates.

    Only when both bands are detected. `a` and `b` are entries of `all_bands()[i]["bands"]`.
    """
    if a["verdict"] != "detected" or b["verdict"] != "detected":
        return None
    ratio = a["integral_mjy_um"] / b["integral_mjy_um"]
    rel = float(np.hypot(a["err_mjy"] / a["excess_mjy"], b["err_mjy"] / b["excess_mjy"]))
    return {"ratio": ratio, "err": abs(ratio) * rel}


# --- absorption (a body that reflects light, such as Pluto, shows ice as dips, not gas as bumps) -------------------

ICE_BANDS: dict[str, dict] = {
    "CH4 1.7": {"window": (1.64, 1.74), "left": (1.52, 1.61), "right": (1.78, 1.88)},
    "CH4 2.3": {"window": (2.26, 2.36), "left": (2.12, 2.22), "right": (2.42, 2.54)},
    "CH4 3.3": {"window": (3.20, 3.40), "left": (2.98, 3.14), "right": (3.45, 3.62)},
}


def band_dip(
    points: list[dict],
    window: tuple[float, float],
    left: tuple[float, float],
    right: tuple[float, float],
    which: str = "flux_mjy",
) -> dict:
    """How far below a straight line through the neighbouring channels the channels inside `window` lie.

    Uses the ok points. The result is `band_excess` with the sign turned round: `depth_mjy` and `depth_sigma` are
    positive for a dip. `controls` is the same measurement at other places of the spectrum (see `control_sigmas`),
    turned round too, and `verdict` is "dip seen", "marginal" or "no dip seen" by the same rules as for a gas band.
    """
    errkey = "err_mjy" if which == "flux_mjy" else "err_large_mjy"
    ok = [p for p in points if p["status"] == "ok" and p.get(which) is not None and p.get(errkey)]
    w = np.array([p["wavelength_um"] for p in ok])
    f = np.array([p[which] for p in ok])
    e = np.array([p[errkey] for p in ok])
    res = band_excess(w, f, e, window, left, right)
    res["controls"] = [round(-c, 2) for c in control_sigmas(w, f, e, window, left, right)]
    if not res["ok"]:
        res.update(depth_mjy=None, depth_sigma=None, verdict="no measurement", mean_flux_mjy=None)
        return res
    res["depth_mjy"] = -res["excess_mjy"]
    res["depth_sigma"] = -res["sigma"]
    verdict = classify(res["depth_sigma"], res["controls"])
    res["verdict"] = {"detected": "dip seen", "marginal": "marginal", "not seen": "no dip seen"}.get(verdict, verdict)
    res["mean_flux_mjy"] = float(np.mean(f[(w >= window[0]) & (w <= window[1])]))
    return res

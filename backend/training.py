"""Training mode: real SPHEREx frames with one made-up moving object added to them.

A visitor can practise spotting a distant, slow-moving world. Everything this module
returns is a simulation and says so three times: in the response (`"simulation": true`
and a notice), in where the pictures are kept (their own `training-...` folders), and
in the pictures themselves, which carry the word SIMULATION. It has its own endpoint,
/api/training, and nothing it makes is ever read by /api/frames, /api/lightcurve,
/api/spectrum or the search, so a planted object cannot reach the real views.

What is planted is one point of light the shape of a SPHEREx star image. It moves the
way a body far beyond Neptune would: a slow drift along its orbit plus a yearly swing
(parallax) as the Earth goes round the Sun. `astrometry.position_at` does that sum for
real stars and is used unchanged here.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.coordinates import BarycentricMeanEcliptic, SkyCoord
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image, ImageDraw

from . import astrometry, pipeline, spherex

VERSION = 2

NOTICE = ("Simulation: one made-up moving object has been added to these real SPHEREx images. "
          "It is not a real detection, and nothing here is a discovery.")
STAMP = "SIMULATION"
STAMP_BOX = (62, 13)     # pixels the stamp covers in the bottom-right corner of each picture: the one
                         # corner the page leaves free (compass, zoom buttons and scale bar take the others)

# Height of the planted object's peak, in units of the frame's background scatter.
LEVELS = {"easy": 12.0, "medium": 7.0, "hard": 4.5}
MODES = ("normal", "difference")
MIN_FOV, MAX_FOV = 0.05, 0.5

# Width (Gaussian sigma, in 2 arcsec picture pixels) of a real, unsaturated star in the
# stacked frames of each detector: the median fitted width of isolated field stars around
# the five test targets (57 to 135 stars per detector, measured 2026-11-14 by
# scripts/check_training.py). As a full width at half maximum that is 9.2 to 10.5 arcsec.
PSF_SIGMA_PX = {1: 1.98, 2: 1.94, 3: 1.95, 4: 2.14, 5: 2.14, 6: 2.22}

SWING_FRACTION = (0.22, 0.38)   # the yearly swing, as a share of the picture's width
EDGE_MARGIN = 0.12              # keep the object this share of the width away from every edge
CLEAR_PX = 6                    # nothing brighter than half the object within this many pixels
PLACEMENT_TRIES = 400
ARCSEC_PER_RADIAN = 206264.806
FOUND_WITHIN_ARCSEC = 12.0      # a click this close to the object counts as finding it


def _ecliptic_east(ra: float, dec: float) -> tuple[float, float]:
    """Unit vector (east, north) on the sky that points along increasing ecliptic longitude:
    the way bodies in the plane of the planets drift."""
    here = SkyCoord(ra, dec, unit="deg", frame="icrs").transform_to(BarycentricMeanEcliptic())
    ahead = SkyCoord(here.lon.deg + 0.01, here.lat.deg, unit="deg", frame=BarycentricMeanEcliptic()).icrs
    east, north = astrometry.offset_arcsec(ra, dec, float(ahead.ra.deg), float(ahead.dec.deg))
    size = float(np.hypot(east, north))
    return east / size, north / size


def plant_motion(ra: float, dec: float, fov: float, visit_mjds: list[float], rng: np.random.Generator) -> dict:
    """A made-up object's motion, as the dictionary `astrometry.position_at` takes.

    Its distance is chosen so that the yearly swing is a fixed share of the picture and
    the object stays in view. The picture decides the distance, not the other way round:
    the response says which distance came out, and how much wider the swing of a planet
    at 500 times the Earth-Sun distance would be.
    """
    # How far apart the visits are on the sky for each arcsecond of parallax. About 2
    # when the visits are half a year apart and the field is near the plane of the planets.
    unit = {"ra": ra, "dec": dec, "pmra": 0.0, "pmdec": 0.0, "parallax": 1000.0, "ref_epoch": 2026.0}
    where = [astrometry.offset_arcsec(ra, dec, *astrometry.position_at(unit, m)) for m in visit_mjds]
    reach = max(float(np.hypot(a[0] - b[0], a[1] - b[1])) for a in where for b in where)
    if reach < 0.2:
        raise spherex.BadRequest("The visits here fall at the same time of year, so a distant object would not "
                         "swing between them. Try another position.")
    swing = rng.uniform(*SWING_FRACTION) * fov * 3600.0          # arcsec, across the visits
    parallax = swing / reach                                     # arcsec
    distance_au = ARCSEC_PER_RADIAN / parallax
    # A circular orbit at that distance: 2 pi / distance^1.5 radians a year.
    drift = ARCSEC_PER_RADIAN * 2.0 * np.pi / distance_au ** 1.5  # arcsec a year
    along_e, along_n = _ecliptic_east(ra, dec)
    tilt = np.radians(rng.uniform(-25.0, 25.0))                   # orbits are not exactly in the plane
    pm_e = drift * (along_e * np.cos(tilt) - along_n * np.sin(tilt))
    pm_n = drift * (along_e * np.sin(tilt) + along_n * np.cos(tilt))
    mid = Time(float(np.mean(visit_mjds)), format="mjd").jyear
    return {"ra": ra, "dec": dec, "pmra": float(pm_e * 1000.0), "pmdec": float(pm_n * 1000.0),
            "parallax": float(parallax * 1000.0), "ref_epoch": float(mid),
            "distance_au": float(distance_au), "drift_arcsec_per_year": float(drift),
            "swing_arcsec": float(swing)}


def _pixel(grid: WCS, ra: float, dec: float) -> tuple[float, float]:
    x, y = grid.all_world2pix(ra, dec, 0)
    return float(x), float(y)


def _clear(image: np.ndarray, x: float, y: float, limit: float) -> bool:
    """Is there data here, with nothing bright enough nearby to hide the object?"""
    n = image.shape[0]
    xi, yi = int(round(x)), int(round(y))
    if not (CLEAR_PX <= xi < n - CLEAR_PX and CLEAR_PX <= yi < n - CLEAR_PX):
        return False
    box = image[yi - CLEAR_PX:yi + CLEAR_PX + 1, xi - CLEAR_PX:xi + CLEAR_PX + 1]
    return bool(np.isfinite(box).all() and box.max() < limit)


def place(motion: dict, grid: WCS, n: int, images: dict[int, np.ndarray], mjds: dict[int, float],
          limits: dict[int, float], rng: np.random.Generator) -> tuple[dict, dict[int, tuple[float, float]]]:
    """Pick where the object is, so that in every visit it is inside the picture, clear of
    the stamp and of anything bright. Returns the motion with its position filled in and
    the object's pixel in each visit."""
    lo, hi = EDGE_MARGIN * n, (1.0 - EDGE_MARGIN) * n
    centre_ra, centre_dec = (float(v) for v in grid.wcs.crval)
    half = 0.5 * n * pipeline.GRID_ARCSEC / 3600.0
    for _ in range(PLACEMENT_TRIES):
        dec = centre_dec + rng.uniform(-half, half)
        ra = centre_ra + rng.uniform(-half, half) / np.cos(np.radians(centre_dec))
        trial = {**motion, "ra": float(ra), "dec": float(dec)}
        spots = {ep: _pixel(grid, *astrometry.position_at(trial, mjds[ep])) for ep in images}
        ok = all(lo <= x <= hi and lo <= y <= hi
                 and not (x > n - STAMP_BOX[0] - 8 and y < STAMP_BOX[1] + 8)   # y counts from the bottom
                 and _clear(images[ep], x, y, limits[ep])
                 for ep, (x, y) in spots.items())
        if ok:
            return trial, spots
    raise spherex.BadRequest("No clear place for a planted object was found in this field (too crowded, or too "
                     "little data). Try another position or a wider field.")


def add_source(image: np.ndarray, x: float, y: float, peak: float, sigma_px: float) -> np.ndarray:
    """The image with a star-shaped point of light added at (x, y). Pixels with no data stay empty."""
    yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    return image + peak * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2.0 * sigma_px ** 2))


def stamp(path: Path) -> None:
    """Write SIMULATION into the picture itself, so a saved copy cannot pass as real data."""
    with Image.open(path) as opened:
        picture = opened.convert("RGBA")
    draw = ImageDraw.Draw(picture)
    left, top = picture.width - STAMP_BOX[0] - 1, picture.height - STAMP_BOX[1] - 1
    draw.rectangle((left, top, picture.width - 1, picture.height - 1), fill=(0, 0, 0, 255))
    draw.text((left + 2, top + 1), STAMP, fill=(255, 150, 0, 255))
    picture.save(path)


def epoch_stacks(ra: float, dec: float, fov: float, detector: int, progress=None
                 ) -> tuple[WCS, int, dict[int, dict], dict[int, list[dict]], list[str]]:
    """The real stacked image of each visit, as pixels (pipeline.build_frames keeps only pictures)."""
    exposures = spherex.find_exposures(ra, dec)
    epoch_of = pipeline.assign_epochs(exposures)
    chosen = [(e, ep) for e, ep in zip(exposures, epoch_of, strict=True) if e["detector"] == detector]
    fetched = spherex.fetch_cutouts([e for e, _ in chosen], ra, dec, round(fov * 1.5, 4), progress=progress)
    failures = [f"{e['obs_id']} D{e['detector']}: {err}" for e, p, err in fetched if p is None]
    grid, n = pipeline.make_grid(ra, dec, fov)
    stackers: dict[int, pipeline.Stacker] = {}
    items: dict[int, list[dict]] = {}
    with pipeline._BUILD_LOCK:               # one memory-heavy build at a time, shared with /api/frames
        for (_, path, _), (_, ep) in zip(fetched, chosen, strict=True):
            if path is None:
                continue
            item = pipeline.prepare_cutout(path, grid, n, ra, dec)
            if item is None:
                continue
            stackers.setdefault(ep, pipeline.Stacker(n)).add(item.pop("data"), item.pop("saturated"), item["weight"])
            items.setdefault(ep, []).append(item)
        stacks = {ep: s.result() for ep, s in stackers.items()}
    return grid, n, stacks, items, failures


def build_training(ra: float, dec: float, fov: float = 0.1, detector: int = 5, mode: str = "normal",
                   level: str = "medium", seed: int = 1, progress=None) -> dict:
    """Frames of one detector with one made-up moving object added. See the module text."""
    if mode not in MODES:
        raise spherex.BadRequest(f"mode must be one of {', '.join(MODES)}")
    if level not in LEVELS:
        raise spherex.BadRequest(f"level must be one of {', '.join(LEVELS)}")
    if not 1 <= detector <= 6:
        raise spherex.BadRequest("detector must be 1 to 6")
    if not MIN_FOV <= fov <= MAX_FOV:
        raise spherex.BadRequest(f"fov must be between {MIN_FOV} and {MAX_FOV} degrees in training mode")

    key_text = f"t{VERSION},v{pipeline.VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{detector},{mode},{level},{seed}"
    key = "training-" + hashlib.sha1(key_text.encode()).hexdigest()[:16]
    out_dir = pipeline.FRAMES_DIR / key
    meta_file = out_dir / "training.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())

    grid, n, stacks, items, failures = epoch_stacks(ra, dec, fov, detector, progress)
    if len(stacks) < 2:
        raise spherex.BadRequest("Training needs at least two SPHEREx visits of this position in this detector, "
                         "because the planted object is found by how it moves between them.")

    def mean_mjd(ep: int) -> float:
        return float(np.average([it["mjd"] for it in items[ep]], weights=[it["weight"] for it in items[ep]]))

    mjds = {ep: mean_mjd(ep) for ep in stacks}
    stats = {ep: sigma_clipped_stats(st["image"][np.isfinite(st["image"])], sigma=3.0, maxiters=5)
             for ep, st in stacks.items()}
    noise = float(np.median([s[2] for s in stats.values()]))
    peak = LEVELS[level] * noise
    # "Bright" for the placement test: sky level plus half the object's own peak.
    limits = {ep: float(stats[ep][1] + 0.5 * peak) for ep in stacks}

    rng = np.random.default_rng([VERSION, seed, detector, int(round(ra * 1e4)), int(round((dec + 90) * 1e4))])
    motion = plant_motion(ra, dec, fov, list(mjds.values()), rng)
    motion, spots = place(motion, grid, n, {ep: st["image"] for ep, st in stacks.items()}, mjds, limits, rng)
    sigma_px = PSF_SIGMA_PX[detector]
    planted = {ep: {**st, "image": add_source(st["image"], *spots[ep], peak, sigma_px)} for ep, st in stacks.items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[dict] = []
    first = next(iter(planted))
    shown = list(planted) if mode == "normal" else [ep for ep in planted if ep != first]
    stretch: dict | None
    if mode == "normal":
        stretch = pipeline.stretch_limits([p["image"] for p in planted.values()])
        for ep in shown:
            pipeline.to_png(planted[ep], stretch, out_dir / f"epoch{ep + 1}.png")
        stretch = {"kind": "asinh", **stretch, "unit": "MJy/sr"}
    else:
        diffs = {ep: planted[ep]["image"] - planted[first]["image"] for ep in shown}
        limits_diff = pipeline.difference_limits(list(diffs.values()))
        if limits_diff is None:
            raise spherex.BadRequest("The visits do not overlap on valid pixels here, so no difference could be made.")
        for ep in shown:
            pipeline.to_difference_png(diffs[ep], limits_diff, out_dir / f"diff{ep + 1}.png")
        stretch = {"kind": "asinh-symmetric", **limits_diff, "unit": "MJy/sr"}

    def where(ep: int) -> dict:
        p_ra, p_dec = astrometry.position_at(motion, mjds[ep])
        x, y = spots[ep]
        return {"epoch": ep + 1, "ra": float(p_ra), "dec": float(p_dec), "x": x, "y": n - 1 - y}  # y from the top

    for ep in shown:
        name = f"epoch{ep + 1}.png" if mode == "normal" else f"diff{ep + 1}.png"
        stamp(out_dir / name)
        its = items[ep]
        waves = [it["wave_at_target"] for it in its if it["wave_at_target"] is not None]
        frame = {"epoch": ep + 1,
                 "date_start": Time(min(it["mjd"] for it in its), format="mjd").iso[:10],
                 "date_end": Time(max(it["mjd"] for it in its), format="mjd").iso[:10],
                 "mjd_mean": mjds[ep], "date_mean": Time(mjds[ep], format="mjd").iso[:10],
                 "n_exposures": len(its), "wavelength_um": [min(waves), max(waves)] if waves else None,
                 "image": f"/frames/{key}/{name}", "planted": where(ep)}
        if mode == "difference":
            frame["reference_epoch"] = first + 1
            frame["planted_in_reference"] = where(first)
        frames.append(frame)

    nine = ARCSEC_PER_RADIAN / 500.0 * (motion["swing_arcsec"] / (motion["parallax"] / 1000.0)) / 60.0
    meta = {
        "simulation": True, "notice": NOTICE,
        "key": key, "ra": ra, "dec": dec, "fov": fov, "detector": detector, "mode": mode,
        "level": level, "seed": seed, "size_px": n, "pixel_arcsec": pipeline.GRID_ARCSEC,
        "frames": frames, "stretch": stretch, "failures": failures,
        "found_within_arcsec": FOUND_WITHIN_ARCSEC,
        "planted": {
            "distance_au": motion["distance_au"],
            "parallax_arcsec": motion["parallax"] / 1000.0,
            "swing_arcsec": motion["swing_arcsec"],
            "drift_arcsec_per_year": motion["drift_arcsec_per_year"],
            "peak_over_noise": LEVELS[level], "peak_mjy_sr": peak, "noise_mjy_sr": noise,
            "fwhm_arcsec": sigma_px * 2.3548 * pipeline.GRID_ARCSEC,
            "positions": [where(ep) for ep in planted],
            "explanation": (
                f"The planted object is placed {motion['distance_au']:,.0f} times as far from the Sun as the "
                f"Earth is. From there it drifts {motion['drift_arcsec_per_year']:.1f} arcsec a year along its "
                f"orbit, and it appears to swing {motion['swing_arcsec']:.0f} arcsec between SPHEREx visits "
                "because the Earth moves round the Sun. That distance was chosen so the swing fits in this "
                f"picture. A planet 500 times the Earth-Sun distance away would swing about {nine:.0f} "
                "arcminutes between the same visits."),
        },
        "credit": pipeline.CREDIT + ". The planted object is made up.",
    }
    if mode == "difference":
        meta["reference_epoch"] = first + 1
    if not failures:                        # like /api/frames: only a complete result is kept
        spherex.write_json(meta_file, meta, indent=1)
    return meta

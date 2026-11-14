"""Turn SPHEREx exposures into one stacked frame per epoch for one detector.

Steps follow "Processing steps for /api/frames" in CLAUDE.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import warnings
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp
from scipy.ndimage import maximum_filter
from scipy.optimize import least_squares

from . import astrometry, spherex

logging.getLogger("astropy").setLevel(logging.ERROR)  # silence the per-file SIP notice

GRID_ARCSEC = 2.0        # output pixel size; native SPHEREx pixels are 6.15 arcsec
EPOCH_GAP_DAYS = 30.0    # a gap longer than this between exposures starts a new epoch
FRAMES_DIR = spherex.CACHE / "frames"

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
    bad = ((flags & ALWAYS_BAD) != 0) | (((flags & COSMIC_RAY) != 0) & ~bloom) | ~np.isfinite(data)
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


def stack(items: list[dict]) -> dict:
    """Weighted mean of the resampled exposures, ignoring missing pixels.

    Before averaging, single readings far from the per-pixel median are dropped.
    The archive's flags miss some glitches (seen: one pixel at -7 MJy/sr among 22
    readings near 0.01). The tolerance grows with the brightness of the brightest
    nearby pixel, because a star's reading at a fixed sky position legitimately
    swings by a factor of a few between exposures: the image is undersampled (PSF
    about 1.2 pixels wide) and every exposure is at a different wavelength.
    """
    cube = np.stack([it["data"] for it in items])
    weights = np.array([it["weight"] for it in items])
    rejected = 0
    if len(items) >= 5:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")          # all-NaN columns are expected
            median = np.nanmedian(cube, axis=0)
        local_peak = maximum_filter(np.nan_to_num(np.abs(median)), size=9)
        noise = (1.0 / np.sqrt(weights))[:, None, None]
        with np.errstate(invalid="ignore"):
            outlier = np.abs(cube - median) > 6.0 * noise + 1.0 * local_peak
        rejected = int(outlier.sum())
        cube = np.where(outlier, np.nan, cube)
    w = weights[:, None, None] * np.isfinite(cube)
    wsum = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.nansum(np.nan_to_num(cube) * w, axis=0) / wsum
    mean[wsum == 0] = np.nan
    n_valid = np.isfinite(cube).sum(axis=0)
    sat_count = np.sum([it["saturated"] for it in items], axis=0)
    return {"image": mean, "n_valid": n_valid, "rejected_readings": rejected,
            # No usable value in any exposure, and at least one of them overflowed here.
            "saturated": ~np.isfinite(mean) & (sat_count > 0)}


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


def build_frames(ra: float, dec: float, fov: float = 0.1, detector: int = 5,
                 mode: str = "normal", progress=None) -> dict:
    """Frames for the player: one stacked image per epoch for one detector."""
    if mode != "normal":
        raise NotImplementedError(f"mode '{mode}' is not built yet (build step 4)")
    if not 1 <= detector <= 6:
        raise ValueError("detector must be 1 to 6")

    key = hashlib.sha1(f"{ra:.5f},{dec:.5f},{fov:.4f},{detector},{mode}".encode()).hexdigest()[:16]
    out_dir = FRAMES_DIR / key
    meta_file = out_dir / "frames.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())

    all_exposures = spherex.find_exposures(ra, dec)
    if not all_exposures:
        return {"key": key, "frames": [], "message": "SPHEREx has no public images covering this position."}
    epoch_of = assign_epochs(all_exposures)
    chosen = [(e, ep) for e, ep in zip(all_exposures, epoch_of) if e["detector"] == detector]

    grid, n = make_grid(ra, dec, fov)
    # The detector can sit at any angle on the sky, so fetch the diagonal of the field.
    cutout_deg = round(fov * 1.5, 4)
    fetched = spherex.fetch_cutouts([e for e, _ in chosen], ra, dec, cutout_deg, progress=progress)
    failures = [f"{e['obs_id']} D{e['detector']}: {err}" for e, p, err in fetched if p is None]

    by_epoch: dict[int, list[dict]] = {}
    for (exp, path, _), (_, ep) in zip(fetched, chosen):
        if path is None:
            continue
        item = prepare_cutout(path, grid, n, ra, dec)
        if item is not None:
            by_epoch.setdefault(ep, []).append(item)

    stacks = {ep: stack(items) for ep, items in sorted(by_epoch.items())}
    if not stacks:
        return {"key": key, "frames": [], "failures": failures,
                "message": f"No usable detector {detector} exposures at this position."}
    limits = stretch_limits([s["image"] for s in stacks.values()])

    # The Gaia star nearest the centre, if there is one, is the target: it gives the
    # expected position in each frame to compare the measured one against.
    mid_mjd = float(np.mean([it["mjd"] for items in by_epoch.values() for it in items]))
    target, gaia_error = None, None
    try:
        nearby = astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06)
        best = None
        for src in nearby:
            sra, sdec = astrometry.position_at(src, mid_mjd)
            sep = float(np.hypot(*astrometry.offset_arcsec(ra, dec, sra, sdec)))
            if sep < 15.0 and (best is None or sep < best[0]):
                best = (sep, src)
        target = best[1] if best else None
    except spherex.ArchiveError as e:
        gaia_error = str(e)

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for ep, st in stacks.items():
        items = by_epoch[ep]
        mjds = np.array([it["mjd"] for it in items])
        weights = np.array([it["weight"] for it in items])
        mjd_mean = float(np.average(mjds, weights=weights))
        waves = [it["wave_at_target"] for it in items if it["wave_at_target"] is not None]
        name = f"epoch{ep + 1}.png"
        to_png(st, limits, out_dir / name)

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
        frames.append({
            "epoch": ep + 1,
            "date_start": Time(mjds.min(), format="mjd").iso[:10],
            "date_end": Time(mjds.max(), format="mjd").iso[:10],
            "mjd_mean": mjd_mean,
            "date_mean": Time(mjd_mean, format="mjd").iso[:10],
            "image": f"/frames/{key}/{name}",
            "n_exposures": len(items),
            "wavelength_um": [min(waves), max(waves)] if waves else None,
            "flagged_fraction": float(np.mean([it["masked_fraction"] for it in items])),
            "saturated_pixels": int(st["saturated"].sum()),
            "rejected_readings": st["rejected_readings"],
            "centroid": centroid,
            "predicted": predicted,
        })

    meta = {
        "key": key, "ra": ra, "dec": dec, "fov": fov, "detector": detector, "mode": mode,
        "size_px": n, "pixel_arcsec": GRID_ARCSEC, "stretch": {"kind": "asinh", **limits, "unit": "MJy/sr"},
        "target": target, "gaia_error": gaia_error,
        "exposures_total_all_detectors": len(all_exposures),
        "failures": failures, "frames": frames,
        "credit": "NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive (IRSA); ESA Gaia DR3",
    }
    meta_file.write_text(json.dumps(meta, indent=1))
    return meta

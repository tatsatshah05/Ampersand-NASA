"""Fitting helpers for the verify scripts: point-source fits on the native SPHEREx pixels.

Every fit works on the pixels of the individual exposures (no resampling, no stacking), with a
pixel-integrated round Gaussian as the star image and one free sky level per exposure.
"""
from __future__ import annotations

import numpy as np
import verify_common as vc
from scipy.optimize import least_squares


def region(c: dict, x: float, y: float, r_fit: float, bad: int = vc.BAD_FAINT):
    """Usable pixels within r_fit pixels of (x, y): coordinates, values, 1-sigma noise. None if off the image."""
    ny, nx = c["data"].shape
    if not (r_fit + 1 <= x < nx - r_fit - 2 and r_fit + 1 <= y < ny - r_fit - 2):
        return None
    x0, x1 = int(np.floor(x - r_fit)), int(np.ceil(x + r_fit)) + 1
    y0, y1 = int(np.floor(y - r_fit)), int(np.ceil(y + r_fit)) + 1
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d, v, f = c["data"][y0:y1, x0:x1], c["variance"][y0:y1, x0:x1], c["flags"][y0:y1, x0:x1]
    with np.errstate(invalid="ignore"):
        ok = (np.hypot(xx - x, yy - y) <= r_fit) & np.isfinite(d) & np.isfinite(v) & (v > 0) & ((f & bad) == 0)
    if ok.sum() < 0.6 * np.pi * r_fit ** 2:
        return None
    return xx[ok].astype(float), yy[ok].astype(float), d[ok], np.sqrt(v[ok])


def joint_fit(cuts: list[dict], sources: list, sigma_px: float, r_fit: float = 4.5,
              fixed: dict[int, float] | None = None, bad: int = vc.BAD_FAINT) -> dict | None:
    """Fluxes of point sources at KNOWN sky positions, shared by all the exposures given.

    sources: one function per source, mjd -> (ra, dec). The fit region of each exposure is centred
    on the first source. fixed: {source index: flux in mJy} for sources whose flux is not fitted.
    Model per exposure: sky level + sum of flux x Gaussian star image. Linear least squares,
    weighted by the archive's VARIANCE. Returns fluxes in mJy with their covariance.
    """
    fixed = fixed or {}
    free = [k for k in range(len(sources)) if k not in fixed]
    blocks = []
    for c in cuts:
        xy = [[float(v) for v in c["wcs"].all_world2pix(*s(c["mjd"]), 0)] for s in sources]
        reg = region(c, xy[0][0], xy[0][1], r_fit, bad)
        if reg is None:
            continue
        xx, yy, d, sig = reg
        cols = [vc.gauss_pixel(xx, yy, x, y, sigma_px) / c["mjy_per_unit"] for x, y in xy]   # MJy/sr per mJy
        y_vec = d - sum(fixed[k] * cols[k] for k in fixed)
        blocks.append((c, [cols[k] for k in free], y_vec, sig))
    if not blocks:
        return None
    n_exp, n_free = len(blocks), len(free)
    n_pix = sum(len(b[2]) for b in blocks)
    a = np.zeros((n_pix, n_free + n_exp))
    y = np.zeros(n_pix)
    w = np.zeros(n_pix)
    row = 0
    for j, (_, cols, y_vec, sig) in enumerate(blocks):
        m = len(y_vec)
        for k, col in enumerate(cols):
            a[row:row + m, k] = col
        a[row:row + m, n_free + j] = 1.0
        y[row:row + m], w[row:row + m] = y_vec, 1.0 / sig
        row += m
    aw, yw = a * w[:, None], y * w
    cov = np.linalg.pinv(aw.T @ aw)
    p = cov @ (aw.T @ yw)
    chi2 = float(np.sum((aw @ p - yw) ** 2))
    dof = n_pix - n_free - n_exp
    flux = np.zeros(len(sources))
    err = np.zeros(len(sources))
    for i, k in enumerate(free):
        flux[k], err[k] = p[i], np.sqrt(cov[i, i])
    for k, v in fixed.items():
        flux[k] = v
    return {"flux": flux, "err": err, "cov": cov[:n_free, :n_free], "free": free, "chi2": chi2, "dof": dof,
            "n_exp": n_exp, "n_pix": n_pix, "obs": [b[0]["obs_id"] for b in blocks],
            "sky": p[n_free:], "mjd": float(np.mean([b[0]["mjd"] for b in blocks]))}


def per_exposure(cuts: list[dict], sources: list, sigma_px: float, r_fit: float = 4.5,
                 fixed: dict[int, float] | None = None, bad: int = vc.BAD_FAINT) -> list[dict]:
    """The same fit, one exposure at a time (a flux per exposure, with its wavelength)."""
    out = []
    for c in cuts:
        res = joint_fit([c], sources, sigma_px, r_fit, fixed, bad)
        if res is None:
            continue
        x, y = [float(v) for v in c["wcs"].all_world2pix(*sources[0](c["mjd"]), 0)]
        out.append({"obs_id": c["obs_id"], "mjd": c["mjd"], "wave": float(c["wave"][int(round(y)), int(round(x))]),
                    "flux": res["flux"].tolist(), "err": res["err"].tolist()})
    return out


def fit_star(c: dict, ra: float, dec: float, half: int = 4, bad: int = vc.BAD_PHOT) -> dict | None:
    """Free fit of one bright star in one exposure: position, width, flux, sky. None if unusable."""
    ny, nx = c["data"].shape
    x, y = [float(v) for v in c["wcs"].all_world2pix(ra, dec, 0)]
    xi, yi = int(round(x)), int(round(y))
    if not (half + 1 <= xi < nx - half - 1 and half + 1 <= yi < ny - half - 1):
        return None
    sl = (slice(yi - half, yi + half + 1), slice(xi - half, xi + half + 1))
    d, v, f = c["data"][sl], c["variance"][sl], c["flags"][sl]
    yy, xx = np.mgrid[yi - half:yi + half + 1, xi - half:xi + half + 1]
    ok = np.isfinite(d) & np.isfinite(v) & (v > 0) & ((f & bad) == 0)
    core = f[half - 1:half + 2, half - 1:half + 2]
    core_values = d[half - 1:half + 2, half - 1:half + 2]
    if ok.sum() < 0.75 * ok.size or (core & bad).any() or not np.isfinite(core_values).all():
        return None
    sig = float(np.sqrt(np.median(v[ok])))
    base = float(np.median(d[ok]))

    def resid(p):
        amp, x0, y0, s, b = p
        return ((amp * vc.gauss_pixel(xx, yy, x0, y0, s) + b - d) / sig)[ok]

    p0 = [max(float(np.sum(d[ok] - base)), 1e-3), x, y, 0.6, base]
    fit = least_squares(resid, p0, bounds=([0, x - 2, y - 2, 0.25, -np.inf], [np.inf, x + 2, y + 2, 2.5, np.inf]))
    amp, x0, y0, s, b = fit.x
    ra_f, dec_f = [float(v) for v in c["wcs"].all_pix2world(x0, y0, 0)]
    de, dn = vc.offset_arcsec(ra, dec, ra_f, dec_f)
    return {"flux": float(amp * c["mjy_per_unit"]), "sigma_px": float(s), "east": float(de), "north": float(dn),
            "wave": float(c["wave"][yi, xi]), "obs_id": c["obs_id"], "mjd": c["mjd"], "peak": float(np.nanmax(d[ok]))}


def stack_image(cuts: list[dict], centre_fn, half_arcsec: float = 40.0, step: float = 2.0,
                bad: int = vc.BAD_FAINT) -> np.ndarray:
    """Plain stacked picture on a sky grid (north up, east LEFT), for looking at.

    Each grid point takes the value of the native pixel it falls in (no interpolation); each
    exposure has its clipped-median sky removed; exposures are averaged with one weight each.
    Written separately from backend/pipeline.py (which resamples bilinearly with `reproject`).
    """
    offs = np.arange(-half_arcsec, half_arcsec + step / 2, step)
    east, north = np.meshgrid(-offs, offs)          # east decreases to the right
    total = np.zeros(east.shape)
    weight = np.zeros(east.shape)
    for c in cuts:
        ra0, dec0 = centre_fn(c["mjd"])
        ras = ra0 + east / 3600.0 / np.cos(np.radians(dec0))
        decs = dec0 + north / 3600.0
        px, py = c["wcs"].all_world2pix(ras, decs, 0)
        xi, yi = np.round(px).astype(int), np.round(py).astype(int)
        ny, nx = c["data"].shape
        inside = (xi >= 0) & (xi < nx) & (yi >= 0) & (yi < ny)
        d, v, f = c["data"], c["variance"], c["flags"]
        with np.errstate(invalid="ignore"):
            good = np.isfinite(d) & np.isfinite(v) & (v > 0) & ((f & bad) == 0)
        if good.sum() < 100:
            continue
        vals = d[good]
        med = np.median(vals)
        for _ in range(4):                           # clipped median = sky level of this exposure
            sd = 1.4826 * np.median(np.abs(vals - med))
            vals = vals[np.abs(vals - med) < 3 * sd]
            med = np.median(vals)
        wexp = 1.0 / np.median(v[good])
        take = inside.copy()
        take[inside] = good[yi[inside], xi[inside]]
        total[take] += wexp * (d[yi[take], xi[take]] - med)
        weight[take] += wexp
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(weight > 0, total / weight, np.nan)


def clipped_median(vals: np.ndarray, n_iter: int = 5) -> tuple[float, float, int]:
    """Median after repeated 3-sigma clipping, its standard error, and how many values were kept."""
    med = float(np.median(vals))
    for _ in range(n_iter):
        sd = 1.4826 * float(np.median(np.abs(vals - med)))
        vals = vals[np.abs(vals - med) < 3 * max(sd, 1e-12)]
        med = float(np.median(vals))
    return med, 1.2533 * float(np.std(vals)) / np.sqrt(len(vals)), len(vals)


def saturated_mask(flags: np.ndarray, empty: np.ndarray) -> np.ndarray:
    """Pixels lost to saturation, following Table 16 of the Explanatory Supplement.

    OVERFLOW alone is a valid value (the ramp was cut at half of full well). Lost are: OVERFLOW with
    SUR_ERROR (overflow within the first seconds), BLOOM (charge from a saturated neighbour),
    NONLINEAR, and OVERFLOW pixels with no value.
    """
    overflow = (flags & vc.bits("OVERFLOW")) != 0
    return ((overflow & ((flags & vc.bits("SUR_ERROR")) != 0)) | ((flags & vc.bits("BLOOM", "NONLINEAR")) != 0)
            | (overflow & empty))


def aperture_flux(c: dict, ra: float, dec: float, r_ap: float = 3.0, sky_px: tuple[float, float] = (7.0, 11.0),
                  sub: int = 5) -> dict:
    """Aperture flux of a bright star in one exposure (mJy), with its status.

    Sum of the zodi-subtracted image in a circle of radius r_ap pixels (pixels on the edge counted
    by the share inside, from sub x sub sub-samples), minus a clipped-median sky from a ring.
    status: "ok", "saturated" (a pixel in the circle has SUR_ERROR, NONLINEAR or BLOOM, or is empty
    with OVERFLOW), "flagged" (another photometry flag or an empty pixel), "no_sky", "off_image".
    The radii differ on purpose from the backend's (2.5 px circle, 14-20 px ring).
    """
    ny, nx = c["data"].shape
    x, y = [float(v) for v in c["wcs"].all_world2pix(ra, dec, 0)]
    out = {"obs_id": c["obs_id"], "mjd": c["mjd"], "detector": c["detector"], "status": "off_image", "flux": None,
           "err": None, "wave": None, "overflow": 0, "x": x, "y": y, "peak": None}
    edge = sky_px[1] + 2
    if not (edge <= x < nx - edge and edge <= y < ny - edge):
        return out
    xi, yi = int(round(x)), int(round(y))
    out["wave"] = float(c["wave"][yi, xi])
    h = int(np.ceil(sky_px[1])) + 1
    sl = (slice(yi - h, yi + h + 1), slice(xi - h, xi + h + 1))
    d, v, f = c["data"][sl], c["variance"][sl], c["flags"][sl]
    yy, xx = np.mgrid[yi - h:yi + h + 1, xi - h:xi + h + 1]
    r = np.hypot(xx - x, yy - y)
    offs = (np.arange(sub) + 0.5) / sub - 0.5
    cover = np.zeros(d.shape)
    for dy in offs:
        for dx in offs:
            cover += np.hypot(xx + dx - x, yy + dy - y) < r_ap
    cover /= sub * sub
    inside = cover > 0
    overflow = (f & vc.bits("OVERFLOW")) != 0
    out["overflow"] = int((overflow & inside).sum())
    empty = ~np.isfinite(d) | ~np.isfinite(v)
    if saturated_mask(f, empty)[inside].any():
        out["status"] = "saturated"
        return out
    if ((f & vc.BAD_PHOT) != 0)[inside].any() or empty[inside].any():
        out["status"] = "flagged"
        return out
    ring = (r >= sky_px[0]) & (r < sky_px[1]) & ~empty & ((f & vc.BAD_PHOT) == 0)
    if ring.sum() < 40:
        out["status"] = "no_sky"
        return out
    med, sky_err, _ = clipped_median(d[ring])
    total = float(np.sum(cover[inside] * (d[inside] - med)))
    var = float(np.sum(cover[inside] ** 2 * v[inside])) + (cover.sum() * sky_err) ** 2
    out.update(status="ok", flux=total * c["mjy_per_unit"], err=float(np.sqrt(var)) * c["mjy_per_unit"],
               peak=float(np.nanmax(d[inside])), sky=med)
    return out


def ring_flux(c: dict, ra: float, dec: float, r_in: float, r_out: float, sky_px: tuple[float, float] = (14.0, 20.0),
              max_bad: float = 0.10) -> dict:
    """Sky-subtracted light in a ring around a (possibly saturated) star: a RELATIVE brightness only.

    Written independently of the "wing" of backend/photometry.py: hard-edged ring on pixel centres,
    flagged pixels replaced by the mean of the clean ones, unusable if a saturated pixel lies in the
    ring or more than max_bad of it is flagged.
    """
    ny, nx = c["data"].shape
    x, y = [float(v) for v in c["wcs"].all_world2pix(ra, dec, 0)]
    out = {"obs_id": c["obs_id"], "mjd": c["mjd"], "detector": c["detector"], "status": "off_image", "value": None,
           "err": None, "wave": None, "x": x, "y": y}
    edge = sky_px[1] + 1
    if not (edge <= x < nx - edge and edge <= y < ny - edge):
        return out
    xi, yi = int(round(x)), int(round(y))
    out["wave"] = float(c["wave"][yi, xi])
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - x, yy - y)
    d, v, f = c["data"], c["variance"], c["flags"]
    empty = ~np.isfinite(d) | ~np.isfinite(v)
    sel = (r >= r_in) & (r < r_out)
    sat = saturated_mask(f, empty)
    out["sat_radius"] = float(r[sat & (r < sky_px[0])].max()) if (sat & (r < sky_px[0])).any() else 0.0
    if sat[sel].any():
        out["status"] = "saturated"
        return out
    bad = (((f & vc.BAD_PHOT) != 0) | empty) & sel
    if bad.sum() > max_bad * sel.sum():
        out["status"] = "flagged"
        return out
    sky_sel = (r >= sky_px[0]) & (r < sky_px[1]) & ~empty & ((f & vc.BAD_PHOT) == 0)
    if sky_sel.sum() < 100:
        out["status"] = "no_sky"
        return out
    med, _, _ = clipped_median(d[sky_sel])
    good = sel & ~bad
    n = int(sel.sum())
    mean = float(np.mean(d[good] - med))
    err = float(np.sqrt(np.sum(v[good])) / good.sum() * n)
    out.update(status="ok", value=mean * n * c["mjy_per_unit"], err=err * c["mjy_per_unit"], n_pix=n,
               clean=float(good.sum() / n), sky=med)
    return out

"""Gaia stars in a view, placed on every frame of it: what the catalogue overlay draws.

Nothing here is cached on its own. The answer is put together from two things that
are already on disk after /api/frames has run for the same view: the frames metadata
(for the frames' dates) and the Gaia cone search that /api/frames makes around the
centre. Working out the positions takes milliseconds.
"""
from __future__ import annotations

import numpy as np

from . import astrometry, pipeline, spherex

DEFAULT_LIMIT = 300        # stars returned unless the request asks for another number
MAX_LIMIT = 2000
G_LIMIT = 17.0             # the magnitude limit of the cone search /api/frames makes
FAST_MAS_YR = 100.0        # stars moving faster than this are returned whatever the limit
SAME_OBJECT_ARCSEC = 1.5   # a Gaia star this close to the target's expected place in every frame is the target
CREDIT = "ESA Gaia DR3"


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def field_stars(ra: float, dec: float, fov: float = 0.1, detector: int = 5, mode: str = "normal", *,
                limit: int = DEFAULT_LIMIT, **options) -> dict:
    """Every Gaia star in the frames of a view, with its place in each frame.

    Takes what build_frames takes (so the frames it describes are exactly those of the
    same /api/frames request) plus `limit`. Positions are for each frame's mean date,
    with the star's own proper motion and parallax applied, in the pixel convention of
    `centroid` and `predicted`: x, y from the top-left of the PNG, whole numbers at
    pixel centres.

    Crowded fields: only stars brighter than G = 17 are searched for, a star must fall
    inside the picture on at least one frame's date, and at most `limit` are returned,
    brightest first. Stars moving faster than FAST_MAS_YR are kept whatever the limit,
    because they are the ones an overlay of motions is for.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise spherex.BadRequest(f"limit must be 1 to {MAX_LIMIT}")
    # Served from the frames cache when the view has been built. If it has not, this
    # builds it, which fetches exactly the cutouts /api/frames would fetch.
    meta = pipeline.build_frames(ra, dec, fov, detector, mode, **options)
    frames = [{"epoch": f["epoch"], "mjd_mean": f["mjd_mean"], "date_mean": f["date_mean"]}
              for f in meta.get("frames") or []]
    out: dict = {
        "ra": ra, "dec": dec, "fov": fov, "detector": detector, "mode": mode,
        "frames_key": meta.get("key"), "size_px": meta.get("size_px"), "pixel_arcsec": meta.get("pixel_arcsec"),
        "frames": frames, "stars": [],
        "n_in_field": 0, "n_returned": 0, "truncated": False, "limit": limit,
        "g_limit": G_LIMIT, "always_kept_above_mas_yr": FAST_MAS_YR,
        "selection": (f"Gaia DR3 stars brighter than G = {G_LIMIT:.0f} that are inside the picture on the date of at "
                      f"least one frame, brightest first. At most `limit` are returned; stars moving faster than "
                      f"{FAST_MAS_YR:.0f} mas/yr are returned whatever the limit. n_in_field counts them before "
                      "the cut. positions[i] is the star's place in frames[i]: ra, dec in degrees and x, y in PNG "
                      "pixels from the top-left, on that frame's mean date."),
        "target_source_id": None, "gaia_error": None, "failures": meta.get("failures") or [], "credit": CREDIT,
    }
    if meta.get("note") and mode == "sum":
        out["note"] = meta["note"]
    if not frames:
        out["message"] = meta.get("message") or "This view has no frames, so there are no dates to place stars on."
        return out

    try:
        # The same search /api/frames makes when it looks for a Gaia star at the centre,
        # so it is normally on disk already. Few retries: this is an overlay, not the picture.
        cone = astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06, G_LIMIT, tries=3, timeout=30)
    except spherex.ArchiveError as e:
        out["gaia_error"] = str(e)
        return out
    cone = sorted((s for s in cone if s.get("gmag") is not None), key=lambda s: s["gmag"])
    if not cone:
        return out

    grid, n = pipeline.make_grid(ra, dec, fov)
    shape = (len(frames), len(cone))
    ras, decs, xs, ys = np.empty(shape), np.empty(shape), np.empty(shape), np.empty(shape)
    for i, frame in enumerate(frames):
        ras[i], decs[i] = astrometry.positions_at(cone, frame["mjd_mean"])
        px, py = grid.all_world2pix(ras[i], decs[i], 0)
        xs[i], ys[i] = px, n - 1 - py                    # y counted from the top of the PNG
    inside = ((xs >= -0.5) & (xs < n - 0.5) & (ys >= -0.5) & (ys < n - 0.5)).any(axis=0)
    in_field = np.flatnonzero(inside)                    # still brightest first
    speed = np.array([np.hypot(s.get("pmra") or 0.0, s.get("pmdec") or 0.0) for s in cone])
    keep = set(in_field[:limit].tolist()) | set(in_field[speed[in_field] >= FAST_MAS_YR].tolist())
    chosen = [int(i) for i in in_field if int(i) in keep]

    target_index = _target_index(meta, cone, ras, decs, chosen)
    for i in chosen:
        src = cone[i]
        out["stars"].append({
            "source_id": src["source_id"], "gmag": _round(src["gmag"], 3),
            "pmra": _round(src.get("pmra"), 3), "pmdec": _round(src.get("pmdec"), 3),
            "parallax": _round(src.get("parallax"), 3), "is_target": i == target_index,
            "positions": [{"ra": round(float(ras[k, i]), 7), "dec": round(float(decs[k, i]), 7),
                           "x": round(float(xs[k, i]), 3), "y": round(float(ys[k, i]), 3)}
                          for k in range(len(frames))],
        })
    out.update(n_in_field=int(in_field.size), n_returned=len(chosen), truncated=len(chosen) < in_field.size,
               target_source_id=cone[target_index]["source_id"] if target_index is not None else None)
    return out


def _target_index(meta: dict, cone: list[dict], ras: np.ndarray, decs: np.ndarray, chosen: list[int]) -> int | None:
    """Which of the returned stars is the view's target, if any of them is.

    The target of /api/frames is either a Gaia star (then its identifier decides) or an
    object described by the request's own motion. In the second case a Gaia star counts
    as the target if it stays within SAME_OBJECT_ARCSEC of the target's expected place
    in every frame, which a different star cannot do when the target moves.
    """
    target = meta.get("target")
    if not target or not chosen:
        return None
    if target.get("source_id"):
        return next((i for i in chosen if cone[i]["source_id"] == target["source_id"]), None)
    predicted = [f.get("predicted") for f in meta["frames"]]
    if any(p is None for p in predicted):
        return None
    idx = np.array(chosen)
    worst = np.zeros(idx.size)
    for k, p in enumerate(predicted):
        d_ra = ras[k, idx] - p["ra"]
        d_ra = np.where(d_ra > 180.0, d_ra - 360.0, np.where(d_ra < -180.0, d_ra + 360.0, d_ra))   # across RA 0h
        east = d_ra * np.cos(np.radians(p["dec"])) * 3600.0
        north = (decs[k, idx] - p["dec"]) * 3600.0
        worst = np.maximum(worst, np.hypot(east, north))
    best = int(np.argmin(worst))
    return int(idx[best]) if worst[best] <= SAME_OBJECT_ARCSEC else None

"""Run the five test targets through the pipeline and write down what each one shows.

Run:  .venv/bin/python scripts/run_targets.py [--only SLUG ...] [--mode normal]

For every target and detector this builds the frames (from the cache if
scripts/warm_cache.py has been run) and records, per frame: dates, exposures, saturated
pixels, where the pipeline put its marker, and how bright the sky is at the place the
catalogue says the target should be. It also measures whether ordinary field stars
stay still between frames.

Writes, under docs/results/:
  <slug>_sheet.jpg      contact sheet: one row per detector, one column per epoch
  <slug>_modes_sheet.jpg     the same for the sum and difference frames
  <slug>_D<n>_epoch<k>.png   the frames themselves, as the site serves them
  measured.json         every number, for later passes
  measured_tables.md    the same as markdown tables, pasted into docs/results.md

Nothing here decides what counts as "visible": that is judged by eye from the sheets.
The expected position of each target on each date comes from the catalogue values
that backend.astrometry.resolve_name returns (Gaia DR3 or SIMBAD position, proper
motion, parallax), independent of the pipeline's own search for a Gaia star in the
frame, so the two can be compared.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from astropy.stats import sigma_clipped_stats
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import warm_cache  # noqa: E402

from backend import astrometry, pipeline, spherex  # noqa: E402

OUT = ROOT / "docs" / "results"
# Other places measured in every frame of a target, for comparison: (label, RA, Dec).
EXTRA_POINTS: dict[str, list[tuple[str, float, float]]] = {
    # An unrelated star that WISE 0855 passes within 4 arcsec of in 2026 (found on the
    # first pass: the pipeline's marker sat on it in detectors 1 to 4).
    "wise0855": [("field star", 133.758165, -7.241226)],
}
MAX_COLUMNS = 8       # epochs shown per contact-sheet row (evenly sampled if there are more)


def expected_position(pos: dict, mjd: float) -> tuple[float, float] | None:
    """Where the catalogue puts the target on a date: proper motion plus parallax.

    `pos` is resolve_name's answer. Its catalogue position, motion and parallax are
    used directly, so this does not depend on the pipeline's own search for a Gaia
    star near the centre of the frame, and the two can be compared.
    """
    cat = pos.get("catalogue")
    if not cat or pos.get("pmra") is None or pos.get("pmdec") is None:
        return None
    src = {"ra": cat["ra"], "dec": cat["dec"], "pmra": pos["pmra"], "pmdec": pos["pmdec"],
           "parallax": pos.get("parallax"), "ref_epoch": cat["epoch"]}
    return astrometry.position_at(src, mjd)


def plain_mean(items: list[dict]) -> np.ndarray:
    """The pipeline's weighted mean of resampled exposures, but with no reading thrown out.

    pipeline.stack first drops readings far from the per-pixel median. Comparing its
    result with this one shows how much of a source that step removed.
    """
    cube = np.stack([it["data"] for it in items])
    w = np.array([it["weight"] for it in items])[:, None, None] * np.isfinite(cube)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.nansum(np.nan_to_num(cube) * w, axis=0) / w.sum(axis=0)


def rebuild_stacks(ra: float, dec: float, fov: float, detector: int
                   ) -> tuple[dict[int, dict], dict[int, np.ndarray], object, int]:
    """The stacked images behind a view (not kept by the backend), from cached cutouts only.

    Returns the pipeline's stacks and, for comparison, plain means with nothing rejected.
    """
    exposures = spherex.find_exposures(ra, dec)
    epoch_of = pipeline.assign_epochs(exposures)
    grid, n = pipeline.make_grid(ra, dec, fov)
    by_epoch: dict[int, list[dict]] = {}
    for e, ep in zip(exposures, epoch_of, strict=True):
        if e["detector"] != detector:
            continue
        path = spherex._cutout_path(e, ra, dec, round(fov * 1.5, 4))
        if not path.exists():
            continue
        item = pipeline.prepare_cutout(path, grid, n, ra, dec)
        if item is not None:
            by_epoch.setdefault(ep + 1, []).append(item)     # +1: same numbering as the API
    by_epoch = dict(sorted(by_epoch.items()))
    return ({ep: pipeline.stack(items) for ep, items in by_epoch.items()},
            {ep: plain_mean(items) for ep, items in by_epoch.items()}, grid, n)


def brightness_at(image: np.ndarray, x: float, y: float, radius: int = 3) -> dict | None:
    """How bright the image is at (x, y), against the frame's background noise.

    `here`: mean of the 3 x 3 grid pixels on the spot (6 arcsec across, one native
    SPHEREx pixel) with the frame's median taken off. This is the number to trust for
    "is something exactly there". `peak`: brightest pixel within `radius` grid pixels,
    which also picks up a neighbour up to 6 arcsec away.
    """
    ny, nx = image.shape
    xi, yi = int(round(float(x))), int(round(float(y)))
    if not (radius <= xi < nx - radius and radius <= yi < ny - radius):
        return None
    finite = image[np.isfinite(image)]
    if finite.size < 100:
        return None
    _, median, sigma = sigma_clipped_stats(finite, sigma=3.0, maxiters=5)
    box = image[yi - radius:yi + radius + 1, xi - radius:xi + radius + 1]
    core = image[yi - 1:yi + 2, xi - 1:xi + 2]
    out: dict = {"background_sigma": float(sigma), "missing_pixels": int((~np.isfinite(box)).sum()),
                 "here_mjy_sr": None, "here_over_sigma": None, "peak_mjy_sr": None, "peak_over_sigma": None}
    if np.isfinite(core).any():
        out["here_mjy_sr"] = float(np.nanmean(core) - median)
        out["here_over_sigma"] = float(out["here_mjy_sr"] / sigma) if sigma > 0 else None
    if np.isfinite(box).any():
        out["peak_mjy_sr"] = float(np.nanmax(box))
        out["peak_over_sigma"] = float((out["peak_mjy_sr"] - median) / sigma) if sigma > 0 else None
    return out


def field_star_shifts(meta: dict, stacks: dict[int, dict], grid, n: int) -> dict | None:
    """How far ordinary Gaia stars move between the first frame and each later one.

    They should not move. Same selection as scripts/check_barnard.py: slow (under
    50 mas/yr), well inside the frame, cleanly fitted in every frame, not blended.
    """
    epochs = sorted(stacks)
    if len(epochs) < 2:
        return None
    mjd0 = meta["frames"][0]["mjd_mean"]
    target_id = (meta.get("target") or {}).get("source_id")
    gaia = astrometry.gaia_cone(meta["ra"], meta["dec"], meta["fov"] * 0.75 + 0.06)
    kept: list[list[dict]] = []
    for src in gaia:
        if src["source_id"] == target_id or src["gmag"] is None:
            continue
        if np.hypot(src["pmra"] or 0, src["pmdec"] or 0) > 50:
            continue
        x, y = grid.all_world2pix(*astrometry.position_at(src, mjd0), 0)
        if not (14 <= x < n - 14 and 14 <= y < n - 14):
            continue
        fits_ = [pipeline.fit_source(stacks[ep]["image"], float(x), float(y), search=3) for ep in epochs]
        if any(f is None or f["snr"] is None or f["snr"] < 15 or not 1.2 < f["sigma_px"] < 4.5 for f in fits_):
            continue
        if np.hypot(fits_[0]["x"] - x, fits_[0]["y"] - y) > 3:
            continue
        if all(np.hypot(fits_[0]["x"] - k[0]["x"], fits_[0]["y"] - k[0]["y"]) > 6 for k in kept):
            kept.append(fits_)
    if not kept:
        return {"n_stars": 0, "pairs": [], "positions": []}
    scale = meta["pixel_arcsec"]
    pairs = []
    for j in range(1, len(epochs)):
        d = np.array([np.hypot(f[j]["x"] - f[0]["x"], f[j]["y"] - f[0]["y"]) * scale for f in kept])
        pairs.append({"from": epochs[0], "to": epochs[j], "median_arcsec": float(np.median(d)),
                      "largest_arcsec": float(d.max())})
    return {"n_stars": len(kept), "pairs": pairs,
            "positions": [[f[0]["x"], n - 1 - f[0]["y"]] for f in kept]}   # PNG pixels, first frame


def measure_view(target: dict, pos: dict, fov: float, detector: int, mode: str) -> dict:
    """Build one view and measure it. Any backend error is recorded, not raised."""
    # With the motion from the name search, as the site requests it after a search.
    res = warm_cache.warm_view(pos["ra"], pos["dec"], fov, detector, mode, **warm_cache.motion_options(pos))
    view: dict = {"target": target["slug"], "detector": detector, "mode": mode, "status": res["status"],
                  "detail": res["detail"], "seconds": res["seconds"], "frames": []}
    meta = res["meta"]
    if meta is None or not meta.get("frames"):
        return view
    view.update(key=meta["key"], size_px=meta["size_px"], gaia_target=meta.get("target"),
                gaia_error=meta.get("gaia_error"), n_failures=len(meta.get("failures") or []))
    n = meta["size_px"]
    stacks: dict[int, dict] = {}
    plain: dict[int, np.ndarray] = {}
    try:
        stacks, plain, grid, _ = rebuild_stacks(pos["ra"], pos["dec"], fov, detector)
        view["field_stars"] = field_star_shifts(meta, stacks, grid, n)
    except Exception as e:  # noqa: BLE001 - the measurement leans on pipeline internals that may change
        view["field_stars_error"] = f"{type(e).__name__}: {e}"
        grid, _ = pipeline.make_grid(pos["ra"], pos["dec"], fov)

    for f in meta["frames"]:
        row = {k: f[k] for k in ("epoch", "date_start", "date_end", "date_mean", "mjd_mean", "n_exposures",
                                 "wavelength_um", "flagged_fraction", "saturated_pixels", "rejected_readings",
                                 "image", "centroid", "predicted")}
        expected = expected_position(pos, f["mjd_mean"])
        if expected:
            era, edec = expected
            ex, ey = grid.all_world2pix(era, edec, 0)
            row["expected"] = {"ra": era, "dec": edec, "x": float(ex), "y": float(n - 1 - ey)}
            if f["centroid"]:
                east, north = astrometry.offset_arcsec(era, edec, f["centroid"]["ra"], f["centroid"]["dec"])
                row["marker_minus_expected_arcsec"] = [east, north]
            if f["epoch"] in stacks:
                row["at_expected"] = brightness_at(stacks[f["epoch"]]["image"], float(ex), float(ey))
                row["at_expected_no_rejection"] = brightness_at(plain[f["epoch"]], float(ex), float(ey))
        for label, pra, pdec in EXTRA_POINTS.get(target["slug"], []):
            if f["epoch"] in stacks:
                px, py = grid.all_world2pix(pra, pdec, 0)
                row.setdefault("extra", {})[label] = brightness_at(stacks[f["epoch"]]["image"], float(px), float(py))
                if expected:
                    row["extra"][label]["offset_from_expected_arcsec"] = list(
                        astrometry.offset_arcsec(expected[0], expected[1], pra, pdec))
        view["frames"].append(row)
    return view


def gapped_cross(draw: ImageDraw.ImageDraw, x: float, y: float, colour: tuple, gap: int = 9, arm: int = 9) -> None:
    """Four ticks pointing at (x, y) that leave the spot itself uncovered."""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        draw.line([x + dx * gap, y + dy * gap, x + dx * (gap + arm), y + dy * (gap + arm)], fill=colour, width=2)


def contact_sheet(target: dict, views: list[dict], path: Path) -> None:
    """One row per detector; per epoch, the whole frame and a zoom on the expected position.

    Yellow ticks: where catalogue proper motion and parallax put the target that epoch.
    Red ticks (zoom only): the same for the first epoch shown, so motion can be judged.
    Cyan ring: where the pipeline put its marker. Green rings: field stars used for the
    stillness check. Purple: no data. Frames are shown exactly as the site serves them.
    """
    big, zoom_half, zoom = 2, 22, 8
    rows = []
    for v in views:
        if not v["frames"]:
            continue
        frames = v["frames"]
        if len(frames) > MAX_COLUMNS:
            frames = [frames[i] for i in np.linspace(0, len(frames) - 1, MAX_COLUMNS).round().astype(int)]
        n = v["size_px"]
        tiles = []
        first = frames[0].get("expected")
        for f in frames:
            png = Image.open(pipeline.FRAMES_DIR / v["key"] / Path(f["image"]).name).convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", png.size, (40, 0, 60, 255)), png).convert("RGB")
            full = im.resize((n * big, n * big), Image.LANCZOS)
            d = ImageDraw.Draw(full)
            for x, y in (v.get("field_stars") or {}).get("positions", []):
                d.ellipse([(x + 0.5) * big - 7, (y + 0.5) * big - 7, (x + 0.5) * big + 7, (y + 0.5) * big + 7],
                          outline=(0, 220, 90))
            exp = f.get("expected")
            if exp:
                gapped_cross(d, (exp["x"] + 0.5) * big, (exp["y"] + 0.5) * big, (255, 230, 0), gap=12, arm=10)
            d.text((5, 3), f"D{v['detector']} ep{f['epoch']} {f['date_mean']} n={f['n_exposures']} "
                   f"sat={f['saturated_pixels']}", fill=(255, 255, 0))
            tiles.append(full)

            # Zoom, centred on the first epoch's expected position (or the frame centre).
            cx = int(round(first["x"])) if first else n // 2
            cy = int(round(first["y"])) if first else n // 2
            cx, cy = min(max(cx, zoom_half), n - 1 - zoom_half), min(max(cy, zoom_half), n - 1 - zoom_half)
            side = (2 * zoom_half + 1) * zoom
            z = im.crop((cx - zoom_half, cy - zoom_half, cx + zoom_half + 1, cy + zoom_half + 1)).resize(
                (side, side), Image.NEAREST)
            d = ImageDraw.Draw(z)

            def spot(px: float, py: float, left: int = cx - zoom_half, top: int = cy - zoom_half) -> tuple:
                return (px - left + 0.5) * zoom, (py - top + 0.5) * zoom
            if first:
                gapped_cross(d, *spot(first["x"], first["y"]), (255, 60, 60), gap=30, arm=10)
            if exp:
                gapped_cross(d, *spot(exp["x"], exp["y"]), (255, 230, 0), gap=16, arm=10)
            if f["centroid"]:
                mx, my = spot(f["centroid"]["x"], f["centroid"]["y"])
                d.ellipse([mx - 22, my - 22, mx + 22, my + 22], outline=(0, 230, 255))
            d.text((5, 3), f"zoom {2 * zoom_half + 1} px = {(2 * zoom_half + 1) * 2} arcsec", fill=(255, 255, 0))
            tiles.append(z)
        rows.append(tiles)
    if not rows:
        return
    pad = 6
    width = max(sum(t.width + pad for t in r) for r in rows) + pad
    height = sum(max(t.height for t in r) + pad for r in rows) + pad + 16
    sheet = Image.new("RGB", (width, height), (20, 20, 20))
    ImageDraw.Draw(sheet).text((pad, 2), f"{target['name']}: north up, east left. yellow = expected (catalogue pm + "
                               "parallax), red = expected at first epoch, cyan = pipeline marker, green = field stars",
                               fill=(230, 230, 230))
    y = pad + 16
    for r in rows:
        x = pad
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + pad
        y += max(t.height for t in r) + pad
    sheet.save(path, quality=88)


def png_to_image(meta: dict, frame: dict) -> np.ndarray | None:
    """A served PNG turned back into MJy/sr (top row first), NaN where it is transparent.

    Only for the asinh stretch of normal and sum frames. Eight bits are enough for this:
    one grey level near the background is about a tenth of the background noise.
    Saturated pixels are drawn white, so they come back as the top of the scale.
    """
    stretch = meta.get("stretch") or {}
    if stretch.get("kind") != "asinh":
        return None
    rgba = np.asarray(Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name).convert("RGBA"))
    grey = rgba[..., 0].astype("float64") / 255.0
    top = np.arcsinh((stretch["vmax"] - stretch["vmin"]) / stretch["soft"])
    image = np.sinh(grey * top) * stretch["soft"] + stretch["vmin"]
    image[rgba[..., 3] == 0] = np.nan
    return image


def target_sum_no_rejection(pos: dict, fov: float, detector: int, out_png: Path) -> dict | None:
    """Every exposure shifted to follow the target and averaged with nothing rejected.

    A diagnostic, not something the site serves: the same shift-and-add as the
    backend's sum with track=target, minus its outlier rejection. Saves a PNG with the
    pipeline's own stretch and returns the brightness at the target's place.
    """
    motion = warm_cache.motion_options(pos)
    if not motion:
        return None
    src = {"ra": pos["ra"], "dec": pos["dec"], "pmra": motion["pmra"], "pmdec": motion["pmdec"],
           "parallax": motion["parallax"], "ref_epoch": motion["pm_epoch"]}
    exposures = [e for e in spherex.find_exposures(pos["ra"], pos["dec"]) if e["detector"] == detector]
    paths = [spherex._cutout_path(e, pos["ra"], pos["dec"], round(fov * 1.5, 4)) for e in exposures]
    grid, n = pipeline.make_grid(pos["ra"], pos["dec"], fov)
    first = [pipeline.prepare_cutout(p, grid, n, pos["ra"], pos["dec"]) if p.exists() else None for p in paths]
    used = [(p, it) for p, it in zip(paths, first, strict=True) if it is not None]
    if not used:
        return None
    ref_mjd = float(np.average([it["mjd"] for _, it in used], weights=[it["weight"] for _, it in used]))
    ref_ra, ref_dec = astrometry.position_at(src, ref_mjd)
    items = []
    for path, it in used:
        t_ra, t_dec = astrometry.position_at(src, it["mjd"])
        shifted, _ = pipeline.make_grid(pos["ra"] + (t_ra - ref_ra), pos["dec"] + (t_dec - ref_dec), fov)
        item = pipeline.prepare_cutout(path, shifted, n, pos["ra"], pos["dec"])
        if item is not None:
            items.append(item)
    image = plain_mean(items)
    x, y = grid.all_world2pix(ref_ra, ref_dec, 0)
    # Saturated pixels are marked the way the pipeline marks them (drawn white).
    saturated = ~np.isfinite(image) & (np.sum([it["saturated"] for it in items], axis=0) > 0)
    pipeline.to_png({"image": image, "saturated": saturated}, pipeline.stretch_limits([image]), out_png)
    result = brightness_at(image, float(x), float(y)) or {}
    result.update(n_exposures=len(items), x=float(x), y=float(n - 1 - y), image=out_png.name)
    return result


def measure_modes(target: dict, pos: dict, fov: float, detectors: list[int]) -> list[dict]:
    """Sum frames (on the sky, and following the target) and difference frames, per detector."""
    motion = warm_cache.motion_options(pos)
    out = []
    for det in detectors:
        row: dict = {"detector": det, "sum": {}, "difference": None}
        for track in ("sky", "target"):
            res = warm_cache.warm_view(pos["ra"], pos["dec"], fov, det, "sum", track=track, **motion)
            entry: dict = {"status": res["status"], "detail": res["detail"]}
            meta = res["meta"]
            if meta and meta.get("frames"):
                f = meta["frames"][0]
                entry.update(key=meta["key"], image=f["image"], size_px=meta["size_px"],
                             n_exposures=f.get("n_exposures"), epochs=f.get("epochs_combined"),
                             saturated_pixels=f.get("saturated_pixels"), centroid=f.get("centroid"),
                             predicted=f.get("predicted"), note=meta.get("note"))
                image = png_to_image(meta, f)
                pred = f.get("predicted")
                if image is not None and pred:
                    entry["at_predicted"] = brightness_at(image, pred["x"], pred["y"])
                if pred and f.get("centroid"):
                    entry["marker_minus_predicted_arcsec"] = list(astrometry.offset_arcsec(
                        pred["ra"], pred["dec"], f["centroid"]["ra"], f["centroid"]["dec"]))
            row["sum"][track] = entry
        try:
            row["sum"]["target_no_rejection"] = target_sum_no_rejection(
                pos, fov, det, OUT / f"{target['slug']}_D{det}_sum_target_no_rejection.png")
        except Exception as e:  # noqa: BLE001 - leans on pipeline internals that may change
            row["sum"]["target_no_rejection"] = {"error": f"{type(e).__name__}: {e}"}
        res = warm_cache.warm_view(pos["ra"], pos["dec"], fov, det, "difference", reference="first", **motion)
        meta = res["meta"]
        row["difference"] = {"status": res["status"], "detail": res["detail"], "key": (meta or {}).get("key"),
                             "frames": [{"epoch": f["epoch"], "reference_epoch": f.get("reference_epoch"),
                                         "image": f["image"], "predicted": f.get("predicted"),
                                         "valid_fraction": f.get("difference_valid_fraction")}
                                        for f in (meta or {}).get("frames", [])]}
        out.append(row)
        print(f"   D{det}: sum sky {row['sum']['sky']['status']}, sum target {row['sum']['target']['status']}, "
              f"difference {row['difference']['status']} ({len(row['difference']['frames'])} frames)", flush=True)
    return out


def modes_sheet(target: dict, modes: list[dict], path: Path) -> None:
    """One row per detector: sum on the sky, sum following the target (each whole and
    zoomed), then the difference frames (each later epoch minus the first).

    Yellow ticks: where the target should be (the pipeline's `predicted`, which comes
    from the motion passed in the request). Cyan ring: the pipeline's marker.
    """
    big, zoom_half, zoom = 2, 22, 8
    rows = []
    for m in modes:
        tiles = []
        for track in ("sky", "target"):
            e = m["sum"][track]
            if "key" not in e:
                continue
            n = e["size_px"]
            png = Image.open(pipeline.FRAMES_DIR / e["key"] / Path(e["image"]).name).convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", png.size, (40, 0, 60, 255)), png).convert("RGB")
            full = im.resize((n * big, n * big), Image.LANCZOS)
            d = ImageDraw.Draw(full)
            pred = e.get("predicted")
            if pred:
                gapped_cross(d, (pred["x"] + 0.5) * big, (pred["y"] + 0.5) * big, (255, 230, 0), gap=12, arm=10)
            d.text((5, 3), f"D{m['detector']} SUM track={track} n={e['n_exposures']}", fill=(255, 255, 0))
            tiles.append(full)
            cx = int(round(pred["x"])) if pred else n // 2
            cy = int(round(pred["y"])) if pred else n // 2
            cx, cy = min(max(cx, zoom_half), n - 1 - zoom_half), min(max(cy, zoom_half), n - 1 - zoom_half)
            side = (2 * zoom_half + 1) * zoom
            z = im.crop((cx - zoom_half, cy - zoom_half, cx + zoom_half + 1, cy + zoom_half + 1)).resize(
                (side, side), Image.NEAREST)
            d = ImageDraw.Draw(z)
            if pred:
                gapped_cross(d, (pred["x"] - cx + zoom_half + 0.5) * zoom, (pred["y"] - cy + zoom_half + 0.5) * zoom,
                             (255, 230, 0), gap=22, arm=12)
            if e.get("centroid"):
                mx = (e["centroid"]["x"] - cx + zoom_half + 0.5) * zoom
                my = (e["centroid"]["y"] - cy + zoom_half + 0.5) * zoom
                d.ellipse([mx - 30, my - 30, mx + 30, my + 30], outline=(0, 230, 255))
            d.text((5, 3), f"zoom {(2 * zoom_half + 1) * 2} arcsec, sum track={track}", fill=(255, 255, 0))
            tiles.append(z)
        raw = m["sum"].get("target_no_rejection") or {}
        if raw.get("image") and (OUT / raw["image"]).exists():
            png = Image.open(OUT / raw["image"]).convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", png.size, (40, 0, 60, 255)), png).convert("RGB")
            n = png.width
            cx = min(max(int(round(raw["x"])), zoom_half), n - 1 - zoom_half)
            cy = min(max(int(round(raw["y"])), zoom_half), n - 1 - zoom_half)
            side = (2 * zoom_half + 1) * zoom
            z = im.crop((cx - zoom_half, cy - zoom_half, cx + zoom_half + 1, cy + zoom_half + 1)).resize(
                (side, side), Image.NEAREST)
            d = ImageDraw.Draw(z)
            gapped_cross(d, (raw["x"] - cx + zoom_half + 0.5) * zoom, (raw["y"] - cy + zoom_half + 0.5) * zoom,
                         (255, 230, 0), gap=22, arm=12)
            d.text((5, 3), "zoom, sum track=target, NOTHING REJECTED (diagnostic)", fill=(255, 160, 0))
            tiles.append(z)
        diff = m["difference"]
        for f in diff["frames"][:MAX_COLUMNS]:
            png = Image.open(pipeline.FRAMES_DIR / diff["key"] / Path(f["image"]).name).convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", png.size, (40, 0, 60, 255)), png).convert("RGB")
            full = im.resize((png.width * big, png.height * big), Image.LANCZOS)
            d = ImageDraw.Draw(full)
            if f.get("predicted"):
                gapped_cross(d, (f["predicted"]["x"] + 0.5) * big, (f["predicted"]["y"] + 0.5) * big,
                             (255, 230, 0), gap=16, arm=10)
            d.text((5, 3), f"D{m['detector']} DIFF ep{f['epoch']} - ep{f['reference_epoch']}", fill=(255, 255, 0))
            tiles.append(full)
        if tiles:
            rows.append(tiles)
    if not rows:
        return
    pad = 6
    width = max(sum(t.width + pad for t in r) for r in rows) + pad
    height = sum(max(t.height for t in r) + pad for r in rows) + pad + 16
    sheet = Image.new("RGB", (width, height), (20, 20, 20))
    ImageDraw.Draw(sheet).text((pad, 2), f"{target['name']}: sum of all epochs (sky-registered, then following the "
                               "target), then difference frames. yellow = predicted place, cyan = pipeline marker",
                               fill=(230, 230, 230))
    y = pad + 16
    for r in rows:
        x = pad
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + pad
        y += max(t.height for t in r) + pad
    sheet.save(path, quality=88)


def modes_table(modes: list[dict]) -> str:
    lines = ["Sum of every exposure of every epoch, and difference frames:", "",
             "| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | "
             "Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |",
             "|---|---|---|---|---|---|---|---|"]
    for m in modes:
        for track in ("sky", "target"):
            e = m["sum"][track]
            label = "on the sky" if track == "sky" else "following the target"
            if "key" not in e:
                lines.append(f"| D{m['detector']} | {label} | {e['status']}: {e['detail'][:80]} | | | | | |")
                continue
            off = e.get("marker_minus_predicted_arcsec")
            lines.append(f"| D{m['detector']} | {label} | {e['n_exposures']} | {e['saturated_pixels']} | "
                         f"{here(e.get('at_predicted'))} | "
                         f"{f'{off[0]:+.1f}, {off[1]:+.1f}' if off else 'n/a'} | "
                         f"{fmt((e.get('centroid') or {}).get('snr'), '.0f')} | "
                         f"{len(m['difference']['frames']) if track == 'sky' else ''} |")
        raw = m["sum"].get("target_no_rejection")
        if raw and "here_mjy_sr" in raw:
            lines.append(f"| D{m['detector']} | following the target, nothing rejected (diagnostic, not served) | "
                         f"{raw['n_exposures']} | | {here(raw)} | | | |")
    return "\n".join(lines) + "\n"


def fmt(v: float | None, spec: str = ".1f") -> str:
    return "n/a" if v is None else format(v, spec)


def here(at: dict | None) -> str:
    """Table cell for brightness_at's on-the-spot number."""
    if not at or at.get("here_mjy_sr") is None:
        return "no data (saturated)" if at else "n/a"
    digits = ".3f" if abs(at["here_mjy_sr"]) < 10 else ".0f"
    return f"{at['here_mjy_sr']:{digits}}; {fmt(at.get('here_over_sigma'), '.0f')}"


def markdown_table(target: dict, pos: dict, views: list[dict]) -> str:
    lines = [f"### {target['name']}", "",
             f"Centre of every view: RA {pos['ra']:.6f}, Dec {pos['dec']:+.6f}, the position at "
             f"{pos.get('epoch', '?')} from `resolve_name` (SIMBAD `{pos.get('name', '?')}`, type "
             f"{pos.get('object_type', '?')}; astrometry from {pos.get('source', '?')}): proper motion "
             f"({fmt(pos.get('pmra'))}, {fmt(pos.get('pmdec'))}) mas/yr, parallax {fmt(pos.get('parallax'))} mas, "
             f"{fmt(pos.get('moved_since_2000_arcsec'))} arcsec from its J2000 place."]
    lines += ["", "| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | "
              "At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | "
              "Marker minus expected (E, N arcsec) | Marker S/N |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in views:
        if not v["frames"]:
            lines.append(f"| D{v['detector']} | none | {v['status']}: {v['detail'] or 'no frames'} | | | | | | | | |")
        for f in v["frames"]:
            at = f.get("at_expected") or {}
            raw = f.get("at_expected_no_rejection") or {}
            off = f.get("marker_minus_expected_arcsec")
            wl = f["wavelength_um"]
            lines.append(
                f"| D{v['detector']} | {f['epoch']} | {f['date_start']} to {f['date_end']} | {f['n_exposures']} | "
                f"{f'{wl[0]:.2f}-{wl[1]:.2f}' if wl else 'n/a'} | {f['saturated_pixels']} | "
                f"{here(at)} | {here(raw)} | {f['rejected_readings']} | "
                f"{f'{off[0]:+.1f}, {off[1]:+.1f}' if off else 'n/a'} | "
                f"{fmt((f['centroid'] or {}).get('snr'), '.0f')} |")
    for label, pra, pdec in EXTRA_POINTS.get(target["slug"], []):
        lines += ["", f"For comparison, the {label} at RA {pra:.6f}, Dec {pdec:+.6f} (same measure):", "",
                  "| Det | Epoch | Offset from the target's expected place (E, N arcsec) | "
                  "Brightness (MJy/sr; in sigma) |",
                  "|---|---|---|---|"]
        for v in views:
            for f in v["frames"]:
                e = (f.get("extra") or {}).get(label)
                if e:
                    off = e.get("offset_from_expected_arcsec")
                    lines.append(f"| D{v['detector']} | {f['epoch']} | "
                                 f"{f'{off[0]:+.1f}, {off[1]:+.1f}' if off else 'n/a'} | {here(e)} |")
    lines += ["", "Field stars between the first frame and each later one (they should not move):", ""]
    for v in views:
        fs = v.get("field_stars")
        if v.get("field_stars_error"):
            lines.append(f"- D{v['detector']}: check failed: {v['field_stars_error']}")
        elif fs is None:
            lines.append(f"- D{v['detector']}: fewer than two frames, nothing to compare")
        elif not fs["n_stars"]:
            lines.append(f"- D{v['detector']}: no isolated Gaia star was clean enough to measure in every frame")
        else:
            worst = max(fs["pairs"], key=lambda p: p["median_arcsec"])
            lines.append(f"- D{v['detector']}: {fs['n_stars']} stars; median shift at most {worst['median_arcsec']:.2f}"
                         f" arcsec (epoch {worst['from']} to {worst['to']}); largest single star "
                         f"{max(p['largest_arcsec'] for p in fs['pairs']):.2f} arcsec")
    tgt = next((v.get("gaia_target") for v in views if v.get("gaia_target")), None)
    origin = {"request": "the motion passed in the request (from the name search)",
              "gaia_nearest": "the nearest Gaia star within 15 arcsec of the centre"}
    lines += ["", "What the pipeline's marker follows: " + (
        f"{origin.get(tgt.get('origin'), tgt.get('origin'))}"
        + (f", Gaia DR3 {tgt['source_id']}, G = {fmt(tgt.get('gmag'), '.2f')}." if tgt.get("source_id") else ".")
        if tgt else "nothing (no motion given and no Gaia star near the centre).")]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", nargs="+", metavar="SLUG")
    parser.add_argument("--mode", default="normal")
    parser.add_argument("--fov", type=float, default=warm_cache.DEFAULT_FOV)
    parser.add_argument("--detectors", nargs="+", type=int, default=warm_cache.DETECTORS)
    parser.add_argument("--tag", default="", help="suffix for output files, e.g. _wide")
    parser.add_argument("--no-modes", action="store_true", help="skip the sum and difference frames")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    def git(*cmd: str) -> str:
        return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    # The code that actually ran: the commit, and a warning if backend/ differed from it.
    commit = git("rev-parse", "--short", "HEAD")
    dirty = [line.split()[-1] for line in git("status", "--porcelain", "--", "backend").splitlines()]
    if dirty:
        commit += " plus uncommitted " + ", ".join(dirty)
    record_path = OUT / f"measured{args.tag}.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else {"targets": {}}
    tables = []
    for t in warm_cache.TARGETS:
        if args.only and t["slug"] not in args.only:
            continue
        pos = warm_cache.resolve(t)
        print(f"\n{t['name']}  RA {pos['ra']:.6f} Dec {pos['dec']:+.6f}", flush=True)
        views = []
        for det in args.detectors:
            v = measure_view(t, pos, args.fov, det, args.mode)
            views.append(v)
            print(f"   D{det}: {v['status']}, {len(v['frames'])} frames, {v['seconds']:.1f} s  {v['detail'][:80]}",
                  flush=True)
            for f in v["frames"]:
                shutil.copy(pipeline.FRAMES_DIR / v["key"] / Path(f["image"]).name,
                            OUT / f"{t['slug']}{args.tag}_D{det}_epoch{f['epoch']}.png")
        contact_sheet(t, views, OUT / f"{t['slug']}{args.tag}_sheet.jpg")
        modes: list[dict] = []
        if not args.no_modes:
            modes = measure_modes(t, pos, args.fov, args.detectors)
            modes_sheet(t, modes, OUT / f"{t['slug']}{args.tag}_modes_sheet.jpg")
        record["targets"][t["slug"]] = {"name": t["name"], "position": pos, "fov": args.fov,
                                        "mode": args.mode, "commit": commit, "modes": modes,
                                        "run_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "views": views}
    record_path.write_text(json.dumps(record, indent=1))
    for t in warm_cache.TARGETS:          # every target on record, not only the ones run just now
        r = record["targets"].get(t["slug"])
        if r:
            tables.append(f"<!-- {t['slug']}: commit {r['commit']}, run {r['run_utc']} UTC -->\n"
                          + markdown_table(t, r["position"], r["views"])
                          + ("\n" + modes_table(r["modes"]) if r.get("modes") else ""))
    (OUT / f"measured_tables{args.tag}.md").write_text(
        "<!-- written by scripts/run_targets.py; do not edit by hand -->\n\n" + "\n".join(tables))
    print(f"\nwrote {record_path} and the sheets in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

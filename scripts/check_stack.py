"""Does stacking keep real light and drop glitches? Compare the pipeline's stack with a plain mean.

Run:  .venv/bin/python scripts/check_stack.py [name] [detector] [fov] [--keep-impossible]
      (default: "Epsilon Indi B", detector 1, fov 0.1)

For each visit, for all visits together on the sky and, when the target's motion is
known, for all visits following the target, prints:
- the brightness at the target's expected place (mean of the 3 x 3 grid pixels there,
  minus the frame's median) in the pipeline's stack and in a weighted mean of the same
  exposures with nothing dropped. They should agree: a difference is light thrown away.
- how many readings the pipeline dropped, and the darkest and brightest pixel of each
  image in units of the frame's noise. A glitch that got through shows as an extreme.
Writes scripts/out/<slug>_D<det>_stack.png: stack, plain mean, and where they differ.

--keep-impossible switches off pipeline.impossible_pixels (the mask for raw values far
below zero), to test the stacking rule alone on the negative glitches it was first
written for (Barnard's Star, detector 5, third visit).
"""
import re
import sys
from pathlib import Path

import numpy as np
from astropy.stats import sigma_clipped_stats
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, pipeline, spherex  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
NAME = args[0] if args else "Epsilon Indi B"
DET = int(args[1]) if len(args) > 1 else 1
FOV = float(args[2]) if len(args) > 2 else 0.1
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)
slug = re.sub(r"[^a-z0-9]+", "_", NAME.lower()).strip("_")
if "--keep-impossible" in sys.argv:
    pipeline.impossible_pixels = lambda image, variance: np.zeros(image.shape, bool)  # type: ignore[assignment]
    print("pipeline.impossible_pixels is switched off for this run")

pos = astrometry.resolve_name(NAME)
ra, dec = pos["ra"], pos["dec"]
target = None
if pos["pmra"] is not None and pos["pmdec"] is not None:
    target = {"ra": ra, "dec": dec, "pmra": pos["pmra"], "pmdec": pos["pmdec"], "parallax": pos["parallax"],
              "ref_epoch": pos["epoch"]}
print(f"{NAME}: RA {ra:.6f} Dec {dec:+.6f} at {pos['epoch']}, detector {DET}, fov {FOV}")

exposures = spherex.find_exposures(ra, dec)
epoch_of = pipeline.assign_epochs(exposures)
grid, n = pipeline.make_grid(ra, dec, FOV)
paths: dict[int, list[Path]] = {}
for e, ep in zip(exposures, epoch_of, strict=True):
    path = spherex._cutout_path(e, ra, dec, round(FOV * 1.5, 4))
    if e["detector"] == DET and path.exists():
        paths.setdefault(ep + 1, []).append(path)
if not paths:
    sys.exit("no cached cutouts for this view: request it through /api/frames first")


def plain_mean(items: list[dict]) -> np.ndarray:
    cube = np.stack([it["data"] for it in items])
    w = np.array([it["weight"] for it in items])[:, None, None] * np.isfinite(cube)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.nansum(np.nan_to_num(cube) * w, axis=0) / w.sum(axis=0)


def at_target(image: np.ndarray, x: float, y: float) -> float:
    xi, yi = int(round(x)), int(round(y))
    if not (1 <= xi < n - 1 and 1 <= yi < n - 1):
        return float("nan")
    return float(np.nanmean(image[yi - 1:yi + 2, xi - 1:xi + 2]) - np.nanmedian(image))


def report(label: str, items: list[dict], x: float, y: float) -> tuple[np.ndarray, np.ndarray]:
    st = pipeline.stack(items)
    plain = plain_mean(items)
    _, median, sigma = sigma_clipped_stats(plain[np.isfinite(plain)], sigma=3.0, maxiters=5)
    a, b = at_target(st["image"], x, y), at_target(plain, x, y)
    print(f"  {label:26s} {len(items):3d} exposures  at target: stack {a:9.3f}  nothing dropped {b:9.3f}  "
          f"ratio {a / b if b else float('nan'):5.3f}   dropped {st['rejected_readings']:5d} readings   "
          f"darkest/brightest pixel in sigma: stack {(np.nanmin(st['image']) - median) / sigma:+7.1f} / "
          f"{(np.nanmax(st['image']) - median) / sigma:+9.1f}, nothing dropped "
          f"{(np.nanmin(plain) - median) / sigma:+7.1f} / {(np.nanmax(plain) - median) / sigma:+9.1f}")
    return st["image"], plain


def place(mjd: float) -> tuple[float, float]:
    if target is None:
        return (n - 1) / 2.0, (n - 1) / 2.0
    px, py = grid.all_world2pix(*astrometry.position_at(target, mjd), 0)
    return float(px), float(py)


rows: list[tuple[str, np.ndarray, np.ndarray, float, float]] = []
every: list[dict] = []
print("brightness in MJy/sr; 'at target' is the 3 x 3 grid pixels on the expected place minus the frame median")
for ep, files in sorted(paths.items()):
    items = [it for it in (pipeline.prepare_cutout(p, grid, n, ra, dec) for p in files) if it is not None]
    if not items:
        continue
    mjd = float(np.average([it["mjd"] for it in items], weights=[it["weight"] for it in items]))
    x, y = place(mjd)
    rows.append((f"visit {ep}", *report(f"visit {ep}", items, x, y), x, y))
    every += items
mjd_all = float(np.average([it["mjd"] for it in every], weights=[it["weight"] for it in every]))
x, y = place(mjd_all)
rows.append(("all visits, on the sky", *report("all visits, on the sky", every, x, y), x, y))
if target is not None:
    # The backend's sum with track=target: each exposure resampled on a grid shifted by the target's motion.
    ref_ra, ref_dec = astrometry.position_at(target, mjd_all)
    moved = []
    for files in paths.values():
        for p in files:
            first = pipeline.prepare_cutout(p, grid, n, ra, dec)
            if first is None:
                continue
            t_ra, t_dec = astrometry.position_at(target, first["mjd"])
            shifted, _ = pipeline.make_grid(ra + (t_ra - ref_ra), dec + (t_dec - ref_dec), FOV)
            item = pipeline.prepare_cutout(p, shifted, n, ra, dec)
            if item is not None:
                moved.append(item)
    rows.append(("all visits, following", *report("all visits, following it", moved, x, y), x, y))

# ------------------------------------------------ sheet to look at
BIG = 3
tiles = []
for label, stacked, plain, x, y in rows:
    lim = pipeline.stretch_limits([plain])
    _, _, sigma = sigma_clipped_stats(plain[np.isfinite(plain)], sigma=3.0, maxiters=5)
    row = Image.new("RGB", (3 * n * BIG + 20, n * BIG), (20, 20, 20))
    for k, im in enumerate((stacked, plain)):
        s = np.arcsinh((im - lim["vmin"]) / lim["soft"]) / np.arcsinh((lim["vmax"] - lim["vmin"]) / lim["soft"])
        grey = (np.clip(np.nan_to_num(s), 0, 1)[::-1] * 255).astype("uint8")
        tile = Image.fromarray(grey).convert("RGB").resize((n * BIG, n * BIG), Image.NEAREST)
        row.paste(tile, (k * (n * BIG + 10), 0))
    diff = (stacked - plain)[::-1]
    vis = np.full((n, n, 3), 40, dtype="uint8")
    vis[diff > 3 * sigma / 5] = (255, 70, 70)          # the stack is brighter than the plain mean
    vis[diff < -3 * sigma / 5] = (70, 130, 255)        # the stack is fainter: something was dropped
    row.paste(Image.fromarray(vis).resize((n * BIG, n * BIG), Image.NEAREST), (2 * (n * BIG + 10), 0))
    d = ImageDraw.Draw(row)
    d.text((6, 4), f"{NAME} D{DET} {label}: pipeline stack", fill=(255, 255, 0))
    d.text((n * BIG + 16, 4), "same exposures, nothing dropped", fill=(255, 255, 0))
    d.text((2 * (n * BIG + 10) + 6, 4), "blue: stack fainter, red: brighter", fill=(255, 255, 0))
    for k in range(2):
        cx, cy = k * (n * BIG + 10) + (x + 0.5) * BIG, (n - 1 - y + 0.5) * BIG
        d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=(255, 230, 0))
    tiles.append(row)
sheet = Image.new("RGB", (tiles[0].width + 20, sum(t.height + 10 for t in tiles) + 10), (20, 20, 20))
ypos = 10
for t in tiles:
    sheet.paste(t, (10, ypos))
    ypos += t.height + 10
path = OUT / f"{slug}_D{DET}_stack.png"
sheet.save(path)
print(f"sheet: {path}")

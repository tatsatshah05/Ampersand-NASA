"""Build the Barnard's Star frames, then check them the way CLAUDE.md asks.

Run:  .venv/bin/python scripts/check_barnard.py [detector]

1. Builds one stacked frame per epoch (default detector 5).
2. Compares the star's measured shift between epochs with Gaia (proper motion + parallax).
3. Measures how far ordinary field stars move between epochs (they should not).
4. Writes a contact sheet to look at: scripts/out/barnard_D<det>_sheet.png
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, pipeline, spherex  # noqa: E402

RA, DEC = 269.446267, 4.768222   # Gaia DR3 position of Barnard's Star propagated to 2026.0
FOV = 0.1
DET = int(sys.argv[1]) if len(sys.argv) > 1 else 5
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)

meta = pipeline.build_frames(RA, DEC, FOV, DET)
frames = meta["frames"]
n = meta["size_px"]
print(f"detector {DET}: {len(frames)} frames, {n}x{n} px at {meta['pixel_arcsec']} arcsec/px, "
      f"failures: {len(meta['failures'])}")
print(f"target: Gaia DR3 {meta['target']['source_id']}  G={meta['target']['gmag']:.2f}  "
      f"pm=({meta['target']['pmra']:.1f}, {meta['target']['pmdec']:.1f}) mas/yr  "
      f"parallax={meta['target']['parallax']:.1f} mas")
for f in frames:
    c = f["centroid"]
    print(f"  epoch {f['epoch']}: {f['date_start']} to {f['date_end']} (mean {f['date_mean']})  "
          f"{f['n_exposures']:2d} exposures  {f['wavelength_um'][0]:.2f}-{f['wavelength_um'][1]:.2f} um  "
          f"flagged {100 * f['flagged_fraction']:.1f}%  saturated px {f['saturated_pixels']}  "
          f"centroid ({c['x']:.2f}, {c['y']:.2f}) +/- {c['err_arcsec']:.2f}\"  FWHM {c['fwhm_arcsec']:.1f}\"")

# ------------------------------------------------ measured shift against Gaia
print("\nShift of Barnard's Star between epochs (east, north in arcsec):")
print(f"  {'epochs':8s} {'years':>6s} {'measured':>18s} {'Gaia pm+parallax':>18s} {'Gaia pm only':>16s} "
      f"{'difference':>11s}")
pairs = [(i, j) for i in range(len(frames)) for j in range(i + 1, len(frames))]
for i, j in pairs:
    a, b = frames[i], frames[j]
    me, mn = astrometry.offset_arcsec(a["centroid"]["ra"], a["centroid"]["dec"],
                                      b["centroid"]["ra"], b["centroid"]["dec"])
    pe, pn = astrometry.offset_arcsec(a["predicted"]["ra"], a["predicted"]["dec"],
                                      b["predicted"]["ra"], b["predicted"]["dec"])
    ra1, dec1 = astrometry.position_at(meta["target"], a["mjd_mean"], parallax=False)
    ra2, dec2 = astrometry.position_at(meta["target"], b["mjd_mean"], parallax=False)
    qe, qn = astrometry.offset_arcsec(ra1, dec1, ra2, dec2)
    diff = np.hypot(me - pe, mn - pn)
    print(f"  {a['epoch']} -> {b['epoch']}   {(b['mjd_mean'] - a['mjd_mean']) / 365.25:6.3f} "
          f"({me:+7.2f}, {mn:+7.2f})  ({pe:+7.2f}, {pn:+7.2f})  ({qe:+6.2f}, {qn:+6.2f}) "
          f"{diff:8.2f}\" = {diff / 6.15:.2f} native px")
print("Absolute position, measured minus Gaia prediction:")
for f in frames:
    e, nn = astrometry.offset_arcsec(f["predicted"]["ra"], f["predicted"]["dec"],
                                     f["centroid"]["ra"], f["centroid"]["dec"])
    print(f"  epoch {f['epoch']}: ({e:+.2f}, {nn:+.2f}) arcsec")

# ------------------------------------------------ do field stars stay put?
# Rebuild the stacks (cached cutouts, so this is quick) and centroid Gaia field stars.
exps = spherex.find_exposures(RA, DEC)
epoch_of = pipeline.assign_epochs(exps)
grid, _ = pipeline.make_grid(RA, DEC, FOV)
by_epoch = {}
for e, ep in zip(exps, epoch_of):
    if e["detector"] != DET:
        continue
    item = pipeline.prepare_cutout(spherex._cutout_path(e, RA, DEC, round(FOV * 1.5, 4)), grid, n, RA, DEC)
    if item:
        by_epoch.setdefault(ep, []).append(item)
stacks = [pipeline.stack(v) for _, v in sorted(by_epoch.items())]
mjds = [f["mjd_mean"] for f in frames]

gaia = astrometry.gaia_cone(RA, DEC, FOV * 0.75 + 0.06)
field = []
for src in gaia:
    if src["source_id"] == meta["target"]["source_id"] or src["gmag"] is None:
        continue
    pm = np.hypot(src["pmra"] or 0, src["pmdec"] or 0)
    if pm > 50:      # mas/yr: keep only stars that should not move measurably
        continue
    x, y = grid.all_world2pix(*astrometry.position_at(src, mjds[0]), 0)
    if not (14 <= x < n - 14 and 14 <= y < n - 14):
        continue
    fits_ = [pipeline.fit_source(s["image"], float(x), float(y), search=3) for s in stacks]
    if any(f is None or f["snr"] is None or f["snr"] < 15 or not 1.2 < f["sigma_px"] < 4.5 for f in fits_):
        continue
    if np.hypot(fits_[0]["x"] - x, fits_[0]["y"] - y) > 3:   # fit wandered to a neighbour
        continue
    field.append((src, fits_))
# Drop stars that share a fit with a brighter neighbour (the list is brightest first).
kept = []
for src, fits_ in field:
    if all(np.hypot(fits_[0]["x"] - k[1][0]["x"], fits_[0]["y"] - k[1][0]["y"]) > 6 for k in kept):
        kept.append((src, fits_))
print(f"\nField stars: {len(kept)} isolated Gaia stars (pm < 50 mas/yr) measured in every frame")
for i, j in pairs:
    dx = np.array([(f[j]["x"] - f[i]["x"]) * -meta["pixel_arcsec"] for _, f in kept])  # east
    dy = np.array([(f[j]["y"] - f[i]["y"]) * meta["pixel_arcsec"] for _, f in kept])   # north
    print(f"  epoch {i + 1} -> {j + 1}: mean shift ({dx.mean():+.2f}, {dy.mean():+.2f}) arcsec, "
          f"median |shift| {np.median(np.hypot(dx, dy)):.2f}\", largest {np.hypot(dx, dy).max():.2f}\"")

# ------------------------------------------------ contact sheet to look at
BIG, ZOOM_HALF, ZOOM = 3, 30, 9          # full frame x3; central 61 px x9
key_dir = pipeline.FRAMES_DIR / meta["key"]
tiles_full, tiles_zoom = [], []
ref = frames[0]["centroid"]
for f in frames:
    png = Image.open(key_dir / Path(f["image"]).name).convert("RGBA")
    bg = Image.new("RGBA", png.size, (40, 0, 60, 255))     # purple shows where there is no data
    im = Image.alpha_composite(bg, png).convert("RGB")
    shutil.copy(key_dir / Path(f["image"]).name, OUT / f"barnard_D{DET}_epoch{f['epoch']}.png")

    full = im.resize((n * BIG, n * BIG), Image.LANCZOS)
    d = ImageDraw.Draw(full)
    for src, fits_ in kept:                                 # green rings: field stars, epoch-1 places
        x, y = (fits_[0]["x"] + 0.5) * BIG, (n - 1 - fits_[0]["y"] + 0.5) * BIG
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(0, 220, 90))
    d.text((6, 4), f"epoch {f['epoch']}  {f['date_mean']}  {f['n_exposures']} exposures  D{DET}", fill=(255, 255, 0))
    tiles_full.append(full)

    cx, cy = int(round(ref["x"])), int(round(ref["y"]))
    crop = im.crop((cx - ZOOM_HALF, cy - ZOOM_HALF, cx + ZOOM_HALF + 1, cy + ZOOM_HALF + 1))
    side = (2 * ZOOM_HALF + 1) * ZOOM
    z = crop.resize((side, side), Image.LANCZOS)
    d = ImageDraw.Draw(z)

    def spot(px, py):
        return (px - (cx - ZOOM_HALF) + 0.5) * ZOOM, (py - (cy - ZOOM_HALF) + 0.5) * ZOOM
    rx, ry = spot(ref["x"], ref["y"])                       # red cross: where the star was in epoch 1
    d.line([rx - 14, ry, rx + 14, ry], fill=(255, 60, 60), width=2)
    d.line([rx, ry - 14, rx, ry + 14], fill=(255, 60, 60), width=2)
    mx, my = spot(f["centroid"]["x"], f["centroid"]["y"])   # cyan ring: measured centre this epoch
    d.ellipse([mx - 9, my - 9, mx + 9, my + 9], outline=(0, 230, 255), width=2)
    gx, gy = spot(f["predicted"]["x"], f["predicted"]["y"])  # yellow dot: Gaia prediction this epoch
    d.ellipse([gx - 3, gy - 3, gx + 3, gy + 3], fill=(255, 230, 0))
    d.text((6, 4), f"zoom: 61 px = 122 arcsec  epoch {f['epoch']}", fill=(255, 255, 0))
    tiles_zoom.append(z)

w = max(sum(t.width for t in tiles_full), sum(t.width for t in tiles_zoom)) + 10 * (len(frames) + 1)
sheet = Image.new("RGB", (w, tiles_full[0].height + tiles_zoom[0].height + 30), (20, 20, 20))
x = 10
for t in tiles_full:
    sheet.paste(t, (x, 10)); x += t.width + 10
x = 10
for t in tiles_zoom:
    sheet.paste(t, (x, tiles_full[0].height + 20)); x += t.width + 10
sheet_path = OUT / f"barnard_D{DET}_sheet.png"
sheet.save(sheet_path)
print(f"\ncontact sheet: {sheet_path}")

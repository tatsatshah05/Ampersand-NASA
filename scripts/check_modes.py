"""Build difference and sum frames for a target and write contact sheets to look at.

Run:  .venv/bin/python scripts/check_modes.py [name] [detector] [fov]
      (default: "Barnard's Star", detector 5, fov 0.1)

Writes scripts/out/<slug>_D<det>_difference_first.png, ..._difference_mean.png and
..._sum.png (sky-registered next to target-tracked), each enlarged three times. In the
difference sheets the yellow dot is the catalogue position of the target in that epoch
and the red cross its position in the reference epoch.
"""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, pipeline  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "Barnard's Star"
DET = int(sys.argv[2]) if len(sys.argv) > 2 else 5
FOV = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
BIG = 3
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)
slug = re.sub(r"[^a-z0-9]+", "_", NAME.lower()).strip("_")

pos = astrometry.resolve_name(NAME)
motion = {"pmra": pos["pmra"], "pmdec": pos["pmdec"], "parallax": pos["parallax"]}
print(f"{NAME}: RA {pos['ra']:.6f} Dec {pos['dec']:+.6f} at {pos['epoch']}, motion {motion}")


def tile(meta: dict, frame: dict, label: str, marks: list[tuple[dict | None, str]]) -> Image.Image:
    n = meta["size_px"]
    png = Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name).convert("RGBA")
    bg = Image.new("RGBA", png.size, (40, 0, 60, 255))      # purple: no data
    im = Image.alpha_composite(bg, png).convert("RGB").resize((n * BIG, n * BIG), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for spot, kind in marks:
        if spot is None:
            continue
        x, y = (spot["x"] + 0.5) * BIG, (spot["y"] + 0.5) * BIG
        if kind == "dot":
            d.ellipse([x - 22, y - 22, x + 22, y + 22], outline=(255, 230, 0))
        else:
            d.line([x - 30, y, x - 16, y], fill=(255, 60, 60), width=2)
            d.line([x + 16, y, x + 30, y], fill=(255, 60, 60), width=2)
            d.line([x, y - 30, x, y - 16], fill=(255, 60, 60), width=2)
            d.line([x, y + 16, x, y + 30], fill=(255, 60, 60), width=2)
    d.text((6, 4), label, fill=(255, 255, 0))
    return im


def sheet(tiles: list[Image.Image], path: Path) -> None:
    out = Image.new("RGB", (sum(t.width for t in tiles) + 10 * (len(tiles) + 1), tiles[0].height + 20), (20, 20, 20))
    x = 10
    for t in tiles:
        out.paste(t, (x, 10))
        x += t.width + 10
    out.save(path)
    print(f"  wrote {path}")


def values(meta: dict, frame: dict) -> np.ndarray:
    """PNG grey levels as floats in 0..1, NaN where transparent, row 0 at the top."""
    rgba = np.asarray(Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name).convert("RGBA"))
    return np.where(rgba[..., 3] > 0, rgba[..., 0] / 255.0, np.nan)


for reference in pipeline.REFERENCES:
    meta = pipeline.build_frames(pos["ra"], pos["dec"], FOV, DET, "difference", reference=reference, **motion)
    print(f"\ndifference, reference={reference}: {len(meta['frames'])} frames; {meta.get('message') or ''}")
    if not meta["frames"]:
        continue
    print(f"  reference: {meta['reference_description']}; stretch {meta['stretch']}")
    ref = (meta.get("reference_frame") or {}).get("predicted")
    tiles = []
    for f in meta["frames"]:
        grey = values(meta, f)
        n = meta["size_px"]
        yy, xx = np.mgrid[0:n, 0:n]
        p = f["predicted"]
        near = np.hypot(xx - p["x"], yy - p["y"]) < 20 if p else np.zeros((n, n), bool)
        far = ~near & np.isfinite(grey)
        print(f"  epoch {f['epoch']} minus {f['reference_epoch'] or 'mean'}: grey level within 40 arcsec of the "
              f"target {np.nanmin(grey[near]) if near.any() else float('nan'):.2f} to "
              f"{np.nanmax(grey[near]) if near.any() else float('nan'):.2f}; elsewhere "
              f"{np.nanmin(grey[far]):.2f} to {np.nanmax(grey[far]):.2f} (0.50 is no change); "
              f"valid {100 * f['difference_valid_fraction']:.0f}%")
        tiles.append(tile(meta, f, f"D{DET} epoch {f['epoch']} minus {f['reference_epoch'] or 'mean of all'}",
                          [(p, "dot"), (ref, "cross")]))
    sheet(tiles, OUT / f"{slug}_D{DET}_difference_{reference}.png")

tiles = []
for track in pipeline.TRACKS:
    try:
        meta = pipeline.build_frames(pos["ra"], pos["dec"], FOV, DET, "sum", track=track, **motion)
    except ValueError as e:
        print(f"\nsum, track={track}: {e}")
        continue
    print(f"\nsum, track={track}: {len(meta['frames'])} frame; registration={meta.get('registration')}")
    for f in meta["frames"]:
        c = f["centroid"]
        print(f"  {f['n_exposures']} exposures, epochs {f['epochs_combined']}, {f['date_start']} to {f['date_end']}; "
              f"stretch {meta['stretch']}")
        if c:
            print(f"  source at the target: SNR {c['snr']:.0f}, FWHM {c['fwhm_arcsec']:.1f} arcsec")
        tiles.append(tile(meta, f, f"D{DET} sum, {meta['registration']}, {f['n_exposures']} exposures",
                          [(f["predicted"], "dot")]))
if tiles:
    sheet(tiles, OUT / f"{slug}_D{DET}_sum.png")

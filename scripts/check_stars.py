"""Check the Gaia field stars that /api/stars returns against the frames they are drawn on.

Run:  .venv/bin/python scripts/check_stars.py [name] [detector] [fov]
      (default: "Barnard's Star", detector 5, fov 0.1)

1. Asks for the stars of every kind of view (normal, difference, sum; with and without
   the target's motion) and prints how many came back, how long a repeat request takes
   and how big the answer is.
2. Checks the arithmetic: every position against astrometry.position_at(), and the
   target's entry against `predicted` in /api/frames.
3. Checks the stars against the pictures: fits the source nearest each isolated bright
   star in each normal frame and prints how far it is from the catalogue place.
4. Writes scripts/out/<slug>_D<det>_stars.png: each frame enlarged, a green ring on every
   star, a yellow ring on the target, and a red line showing 20 years of proper motion.
"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, pipeline, stars  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "Barnard's Star"
DET = int(sys.argv[2]) if len(sys.argv) > 2 else 5
FOV = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
BIG = 4
ARROW_YEARS = 20
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)
slug = re.sub(r"[^a-z0-9]+", "_", NAME.lower()).strip("_")

pos = astrometry.resolve_name(NAME)
motion = {"pmra": pos["pmra"], "pmdec": pos["pmdec"], "parallax": pos["parallax"]}
has_motion = pos["pmra"] is not None and pos["pmdec"] is not None
print(f"{NAME}: RA {pos['ra']:.6f} Dec {pos['dec']:+.6f} at {pos['epoch']}, detector {DET}, fov {FOV}")
problems: list[str] = []

# ------------------------------------------------ every kind of view
VIEWS = [("normal", {}), ("difference", {}), ("difference", {"reference": "mean"}), ("sum", {}),
         ("sum", {"track": "target"})]
print(f"\n{'view':34s} {'frames':>6s} {'in field':>8s} {'returned':>8s} {'target':>20s} {'repeat':>8s} {'size':>8s}")
for with_motion in (False, True):
    if with_motion and not has_motion:
        continue
    for mode, options in VIEWS:
        kw = {**options, **(motion if with_motion else {})}
        label = mode + "".join(f" {k}={v}" for k, v in options.items()) + (" +motion" if with_motion else "")
        try:
            first = stars.field_stars(pos["ra"], pos["dec"], FOV, DET, mode, **kw)
        except ValueError as e:
            print(f"{label:34s} not possible: {e}")
            continue
        t0 = time.time()
        again = stars.field_stars(pos["ra"], pos["dec"], FOV, DET, mode, **kw)
        repeat = time.time() - t0
        if again != first:
            problems.append(f"{label}: a repeat request gave a different answer")
        if first["gaia_error"]:
            problems.append(f"{label}: Gaia did not answer ({first['gaia_error']})")
        frames = pipeline.build_frames(pos["ra"], pos["dec"], FOV, DET, mode, **kw)
        if [f["mjd_mean"] for f in first["frames"]] != [f["mjd_mean"] for f in frames["frames"]]:
            problems.append(f"{label}: frames of /api/stars and /api/frames differ")
        print(f"{label:34s} {len(first['frames']):6d} {first['n_in_field']:8d} {first['n_returned']:8d} "
              f"{str(first['target_source_id']):>20s} {1000 * repeat:6.0f}ms {len(json.dumps(first)) / 1000:6.1f}kB")
        # The target's own entry must sit where /api/frames predicts the target.
        target = frames.get("target")
        mine = [s for s in first["stars"] if s["is_target"]]
        if target and target.get("source_id") and frames["frames"]:
            if len(mine) != 1 or mine[0]["source_id"] != target["source_id"]:
                problems.append(f"{label}: the target {target['source_id']} is not marked in the star list")
            else:
                worst = max(np.hypot(p["x"] - f["predicted"]["x"], p["y"] - f["predicted"]["y"])
                            for p, f in zip(mine[0]["positions"], frames["frames"], strict=True))
                if worst > 0.002:
                    problems.append(f"{label}: target entry is {worst:.4f} px from `predicted`")

# ------------------------------------------------ arithmetic and pictures, on the normal view
view = stars.field_stars(pos["ra"], pos["dec"], FOV, DET, "normal")
meta = pipeline.build_frames(pos["ra"], pos["dec"], FOV, DET, "normal")
if not view["frames"]:
    sys.exit(f"no frames: {view.get('message')}")
n, scale = view["size_px"], view["pixel_arcsec"]
cone = {s["source_id"]: s for s in astrometry.gaia_cone(pos["ra"], pos["dec"], FOV * 0.75 + 0.06)}
grid, _ = pipeline.make_grid(pos["ra"], pos["dec"], FOV)
worst_deg = worst_px = 0.0
for s in view["stars"]:
    for p, f in zip(s["positions"], view["frames"], strict=True):
        ra, dec = astrometry.position_at(cone[s["source_id"]], f["mjd_mean"])
        worst_deg = max(worst_deg, abs(ra - p["ra"]), abs(dec - p["dec"]))
        x, y = grid.all_world2pix(ra, dec, 0)
        worst_px = max(worst_px, abs(float(x) - p["x"]), abs(n - 1 - float(y) - p["y"]))
print(f"\n{len(view['stars'])} stars x {len(view['frames'])} frames against position_at(): largest difference "
      f"{worst_deg * 3.6e6:.3f} mas, {worst_px:.4f} px (values are rounded to 1e-7 deg and 0.001 px)")
if worst_deg > 1e-7 or worst_px > 0.001:
    problems.append("positions disagree with astrometry.position_at()")
outside = [s["source_id"] for s in view["stars"]
           if not any(-0.5 <= p["x"] < n - 0.5 and -0.5 <= p["y"] < n - 0.5 for p in s["positions"])]
if outside:
    problems.append(f"{len(outside)} returned stars are outside the picture in every frame")


def picture(frame: dict) -> np.ndarray:
    """A served PNG turned back into MJy/sr, row 0 at the bottom as the pipeline has it."""
    rgba = np.asarray(Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name).convert("RGBA"))
    st = meta["stretch"]
    top = np.arcsinh((st["vmax"] - st["vmin"]) / st["soft"])
    image = np.sinh(rgba[..., 0] / 255.0 * top) * st["soft"] + st["vmin"]
    image[rgba[..., 3] == 0] = np.nan
    return image[::-1]


print("\nCatalogue place against the source fitted in the picture (isolated stars, S/N > 15):")
for k, frame in enumerate(meta["frames"]):
    image = picture(frame)
    offsets, wandered = [], 0
    for s in view["stars"]:
        p = s["positions"][k]
        if not (14 <= p["x"] < n - 14 and 14 <= p["y"] < n - 14):
            continue
        others = [o["positions"][k] for o in view["stars"] if o is not s and o["gmag"] < s["gmag"] + 2.5]
        if any(np.hypot(o["x"] - p["x"], o["y"] - p["y"]) < 12 for o in others):
            continue                                  # a neighbour of similar brightness within 24 arcsec
        fit = pipeline.fit_source(image, p["x"], n - 1 - p["y"], search=3)
        if fit is None or fit["snr"] is None or fit["snr"] < 15 or not 1.2 < fit["sigma_px"] < 4.5:
            continue
        east, north = (fit["x"] - p["x"]) * -scale, ((n - 1 - fit["y"]) - p["y"]) * -scale
        if np.hypot(east, north) > 3 * scale:         # the fit slid onto the wing of a much brighter star
            wandered += 1
            continue
        offsets.append((east, north))
    if not offsets:
        print(f"  frame {k + 1} (epoch {frame['epoch']}): no isolated star bright enough to fit")
        continue
    east, north = np.array(offsets).T
    dist = np.hypot(east, north)
    print(f"  frame {k + 1} (epoch {frame['epoch']}, {frame['date_mean']}): {len(offsets)} stars, mean offset "
          f"({east.mean():+.2f}, {north.mean():+.2f}) arcsec east, north; median distance {np.median(dist):.2f}\", "
          f"largest {dist.max():.2f}\"; {wandered} more fits slid onto a brighter neighbour and are left out")
    if np.median(dist) > 3.0 or wandered > len(offsets):
        problems.append(f"frame {k + 1}: stars sit a median {np.median(dist):.1f} arcsec from the catalogue "
                        f"({wandered} fits slid away)")

# ------------------------------------------------ the limit
small = stars.field_stars(pos["ra"], pos["dec"], FOV, DET, "normal", limit=10)
fast = [s for s in view["stars"] if np.hypot(s["pmra"] or 0, s["pmdec"] or 0) >= stars.FAST_MAS_YR]
kept_fast = {s["source_id"] for s in small["stars"]} >= {s["source_id"] for s in fast}
mags = [s["gmag"] for s in small["stars"]]
print(f"\nlimit=10: {small['n_returned']} of {small['n_in_field']} returned, truncated={small['truncated']}; "
      f"{len(fast)} stars move faster than {stars.FAST_MAS_YR:.0f} mas/yr and all are kept: {kept_fast}; "
      f"G from {min(mags):.2f} to {max(mags):.2f}")
if not kept_fast or mags != sorted(mags) or small["n_returned"] > 10 + len(fast):
    problems.append("limit: fast stars dropped, order not brightest first, or too many returned")

# ------------------------------------------------ sheet to look at
tiles = []
for k, frame in enumerate(meta["frames"]):
    png = Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name).convert("RGBA")
    bg = Image.new("RGBA", png.size, (40, 0, 60, 255))
    im = Image.alpha_composite(bg, png).convert("RGB").resize((n * BIG, n * BIG), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for s in view["stars"]:
        p = s["positions"][k]
        x, y = (p["x"] + 0.5) * BIG, (p["y"] + 0.5) * BIG
        r = 5 + max(0.0, 14 - s["gmag"])                # brighter stars get bigger rings
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 230, 0) if s["is_target"] else (0, 220, 90))
        if s["pmra"] is not None and s["pmdec"] is not None:
            # East is left and north is up, so both components flip sign on the way to pixels.
            dx = -s["pmra"] / 1000 / scale * BIG * ARROW_YEARS
            dy = -s["pmdec"] / 1000 / scale * BIG * ARROW_YEARS
            if np.hypot(dx, dy) > 3:
                d.line([x, y, x + dx, y + dy], fill=(255, 70, 70), width=1)
    d.text((6, 4), f"epoch {frame['epoch']}  {frame['date_mean']}  D{DET}  {len(view['stars'])} Gaia stars "
           f"(of {view['n_in_field']})", fill=(255, 255, 0))
    tiles.append(im)
sheet = Image.new("RGB", (sum(t.width for t in tiles) + 10 * (len(tiles) + 1), tiles[0].height + 20), (20, 20, 20))
x = 10
for t in tiles:
    sheet.paste(t, (x, 10))
    x += t.width + 10
path = OUT / f"{slug}_D{DET}_stars.png"
sheet.save(path)
print(f"\nsheet: {path}")

print(f"\nPROBLEMS: {len(problems)}")
for p in problems:
    print("  - " + p)
sys.exit(1 if problems else 0)

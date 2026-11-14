"""Measure a target in every exposure and draw its spectrum and light curve to look at.

Run:  .venv/bin/python scripts/check_photometry.py [name]      (default: "RW Aurigae")

Prints how many exposures gave a flux, were saturated and so on, per detector, and the
wavelength bins with the largest change over time. Writes two charts to scripts/out/:
<slug>_spectrum.png (brightness against wavelength, one colour per epoch) and
<slug>_lightcurve.png (brightness relative to each wavelength bin's median, against date).
Filled dots are aperture fluxes; hollow squares are wing values (relative brightness from
unsaturated pixels of a saturated star, not fluxes), drawn only for the detectors in which
wing values are trusted (5 and 6).
"""
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, photometry  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "RW Aurigae"
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)
slug = re.sub(r"[^a-z0-9]+", "_", NAME.lower()).strip("_")
COLOURS = [(230, 80, 60), (60, 170, 90), (70, 130, 240), (200, 150, 30), (160, 80, 200), (60, 180, 190),
           (120, 120, 120), (240, 120, 180)]

pos = astrometry.resolve_name(NAME)
motion = {"pmra": pos["pmra"], "pmdec": pos["pmdec"], "parallax": pos["parallax"]}
print(f"{NAME}: RA {pos['ra']:.6f} Dec {pos['dec']:+.6f} at {pos['epoch']}")


def chart(path: Path, title: str, series: list[dict], xlabel: str, ylabel: str, logy: bool) -> None:
    """Scatter chart. Each series: {label, colour, hollow, x, y, err}."""
    w, h, left, right, top, bottom = 1500, 700, 90, 230, 40, 60
    xs = np.concatenate([np.asarray(s["x"], float) for s in series if len(s["x"])] or [np.array([0.0, 1.0])])
    ys = np.concatenate([np.asarray(s["y"], float) for s in series if len(s["y"])] or [np.array([0.1, 1.0])])
    if logy:
        ys = ys[ys > 0]
    x0, x1 = xs.min(), xs.max()
    y0, y1 = (np.log10(ys.min()), np.log10(ys.max())) if logy else (ys.min(), ys.max())
    x0, x1 = x0 - 0.03 * (x1 - x0 or 1), x1 + 0.03 * (x1 - x0 or 1)
    y0, y1 = y0 - 0.06 * (y1 - y0 or 1), y1 + 0.06 * (y1 - y0 or 1)

    def at(x, y):
        v = np.log10(y) if logy else y
        return left + (x - x0) / (x1 - x0) * (w - left - right), h - bottom - (v - y0) / (y1 - y0) * (h - top - bottom)

    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([left, top, w - right, h - bottom], outline=(0, 0, 0))
    d.text((left, 12), title, fill=(0, 0, 0))
    d.text(((left + w - right) // 2 - 60, h - 22), xlabel, fill=(0, 0, 0))
    d.text((6, top - 22), ylabel, fill=(0, 0, 0))
    for i in range(6):
        xv = x0 + (x1 - x0) * i / 5
        px = left + (w - left - right) * i / 5
        d.line([px, h - bottom, px, h - bottom + 5], fill=(0, 0, 0))
        d.text((px - 18, h - bottom + 8), f"{xv:.2f}" if abs(xv) < 1000 else f"{xv:.0f}", fill=(0, 0, 0))
        yv = y0 + (y1 - y0) * i / 5
        py = h - bottom - (h - top - bottom) * i / 5
        d.line([left - 5, py, left, py], fill=(0, 0, 0))
        d.line([left, py, w - right, py], fill=(225, 225, 225))
        d.text((8, py - 6), f"{10 ** yv:.3g}" if logy else f"{yv:.3g}", fill=(0, 0, 0))
    for k, s in enumerate(series):
        for x, y, e in zip(s["x"], s["y"], s["err"], strict=True):
            if logy and y <= 0:
                continue
            px, py = at(x, y)
            if e and (not logy or y - e > 0):
                d.line([px, at(x, y - e)[1], px, at(x, y + e)[1]], fill=s["colour"])
            if s["hollow"]:
                d.rectangle([px - 3, py - 3, px + 3, py + 3], outline=s["colour"])
            else:
                d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=s["colour"])
        ly = top + 10 + 18 * k
        if s["hollow"]:
            d.rectangle([w - right + 12, ly, w - right + 18, ly + 6], outline=s["colour"])
        else:
            d.ellipse([w - right + 12, ly, w - right + 18, ly + 6], fill=s["colour"])
        d.text((w - right + 26, ly - 3), f"{s['label']} ({len(s['x'])})", fill=(0, 0, 0))
    im.save(path)
    print(f"  wrote {path}")


spec = photometry.spectrum(pos["ra"], pos["dec"], **motion)
pts = spec["points"]
print(f"\n{spec['n_exposures']} exposures with a wavelength; failures: {len(spec['failures'])}; "
      f"target followed: {(spec['target'] or {}).get('origin')}")
print(f"aperture flux: {spec['status_counts']}; wing value for {spec['n_wing']}, of which "
      f"{spec['n_wing_trusted']} in trusted detectors; wing rings (px): {spec['wing_ring_px']}")
for det in range(1, 7):
    dp = [p for p in pts if p["detector"] == det]
    ok = [p for p in dp if p["status"] == "ok"]
    wg = [p for p in dp if p["wing_status"] == "ok"]
    line = f"  D{det}: {len(dp):3d} exposures, {dict(Counter(p['status'] for p in dp))}, wing ok {len(wg)}"
    if ok:
        f = np.array([p["flux_mjy"] for p in ok])
        snr = np.median([p["flux_mjy"] / p["flux_err_mjy"] for p in ok])
        line += f"; flux {f.min():.1f} to {f.max():.1f} mJy (median {np.median(f):.1f}), median S/N {snr:.0f}"
    print(line)
for e in spec["epochs"]:
    print(f"  epoch {e['epoch']}: {e['date_start']} to {e['date_end']}, {e['n_exposures']} exposures")

series = []
for e in spec["epochs"]:
    ok = [p for p in pts if p["epoch"] == e["epoch"] and p["status"] == "ok"]
    series.append({"label": f"flux, epoch {e['epoch']} ({e['date_start']})", "colour": COLOURS[(e["epoch"] - 1) % 8],
                   "hollow": False, "x": [p["wavelength_um"] for p in ok], "y": [p["flux_mjy"] for p in ok],
                   "err": [p["flux_err_mjy"] for p in ok]})
for e in spec["epochs"]:
    wg = [p for p in pts if p["epoch"] == e["epoch"] and p["wing_status"] == "ok" and p["wing_trusted"]
          and p["status"] != "ok"]
    series.append({"label": f"wing only, epoch {e['epoch']}", "colour": COLOURS[(e["epoch"] - 1) % 8], "hollow": True,
                   "x": [p["wavelength_um"] for p in wg], "y": [p["wing_mjy"] for p in wg],
                   "err": [p["wing_err_mjy"] for p in wg]})
chart(OUT / f"{slug}_spectrum.png", f"{NAME}: brightness against wavelength, one point per exposure "
      "(hollow = wing value of a saturated star, not a flux)", series, "wavelength (microns)", "mJy", True)

lc = photometry.lightcurve(pos["ra"], pos["dec"], **motion)
multi = [b for b in lc["bins"] if b["n_measured"] >= 2]
multi_w = [b for b in lc["bins"] if b["n_wing"] >= 2 and b["wing_trusted"]]
print(f"\n{len(lc['bins'])} wavelength bins; {len(multi)} have 2+ fluxes, {len(multi_w)} have 2+ trusted wing values")


def spread(b: dict, key: str) -> tuple[float, float, float]:
    rel = [p[key] for p in b["points"] if p[key] is not None]
    days = [p["mjd"] for p in b["points"] if p[key] is not None]
    return max(rel) / min(rel), max(days) - min(days), len(rel)


for label, bins, key in (("flux", multi, "relative_flux"), ("wing", multi_w, "relative_wing")):
    if not bins:
        continue
    ratios = np.array([spread(b, key)[0] for b in bins])
    print(f"  {label}: brightest/faintest within a bin: median {np.median(ratios):.2f}, largest {ratios.max():.2f}")
    for b in sorted(bins, key=lambda b: -spread(b, key)[0])[:5]:
        vals = ", ".join(f"{p['date'][:10]} {p[key]:.2f}" for p in b["points"] if p[key] is not None)
        lo, hi = b["wavelength_um"]
        print(f"    bin {b['bin']} (D{b['detector']}, {lo:.3f}-{hi:.3f} um): {vals}")

series = []
for det in range(1, 7):
    for key, hollow in (("relative_flux", False), ("relative_wing", True)):
        chosen = [p for b in (multi_w if hollow else multi) if b["detector"] == det
                  for p in b["points"] if p[key] is not None]
        if chosen:
            series.append({"label": f"D{det} {'wing' if hollow else 'flux'}", "colour": COLOURS[det - 1],
                           "hollow": hollow, "x": [p["mjd"] for p in chosen], "y": [p[key] for p in chosen],
                           "err": [None] * len(chosen)})
if series:
    chart(OUT / f"{slug}_lightcurve.png", f"{NAME}: brightness relative to the median of its own wavelength bin "
          "(bins with 2+ points)", series, "date (MJD)", "relative", False)

"""Compare aperture fluxes of ordinary field stars with the 2MASS catalogue.

Run:  .venv/bin/python scripts/check_flux_scale.py [name]     (default: "RW Aurigae")

Takes the 2MASS stars inside the cached cutouts of a target (not the target itself),
measures each in every exposure with backend.photometry.measure, and compares the
median SPHEREx flux near 1.24, 1.66 and 2.16 microns with the 2MASS J, H and Ks
fluxes. A ratio near 1 says the units, the pixel solid angle and the sky subtraction
are right. It will not be exactly 1: there is no aperture correction, and the 2MASS
bands are much wider than a SPHEREx channel.
"""
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, photometry, spherex  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "RW Aurigae"
BANDS = {"J": ("j_m", 1.235, 1594.0), "H": ("h_m", 1.662, 1024.0), "Ks": ("k_m", 2.159, 666.7)}  # micron, Jy at mag 0
HALF_WIDTH = 0.08     # microns either side of the band centre
LIMIT = 14.5          # faintest J magnitude used

pos = astrometry.resolve_name(NAME)
# 2MASS point sources from VizieR (CfA mirror; IRSA's own TAP timed out on this table on 2026-11-14).
raw = spherex.http_get("https://vizier.cfa.harvard.edu/viz-bin/asu-tsv",
                       {"-source": "II/246/out", "-c": f"{pos['ra']} {pos['dec']:+}", "-c.rs": "162",
                        "-out": ["RAJ2000", "DEJ2000", "Jmag", "Hmag", "Kmag", "Qflg"], "-out.max": "500"}, timeout=60)
cat = []
for text in raw.decode().splitlines():
    cells = text.split("\t")
    if len(cells) == 6 and cells[0][:1].isdigit():
        try:
            cat.append({"ra": float(cells[0]), "dec": float(cells[1]), "j_m": float(cells[2]), "h_m": float(cells[3]),
                        "k_m": float(cells[4]), "ph_qual": cells[5].strip()})
        except ValueError:
            continue      # a magnitude is missing
print(f"{NAME}: {len(cat)} 2MASS stars within 162 arcsec")

exposures = [e for e in spherex.find_exposures(pos["ra"], pos["dec"]) if e["detector"] in (2, 3)]
stars = []
for row in cat:
    sep = np.hypot(*astrometry.offset_arcsec(pos["ra"], pos["dec"], float(row["ra"]), float(row["dec"])))
    others = [np.hypot(*astrometry.offset_arcsec(float(row["ra"]), float(row["dec"]), float(o["ra"]), float(o["dec"])))
              for o in cat if o is not row and float(o["j_m"]) < float(row["j_m"]) + 3.0]
    # Not the target, bright enough to measure, and nothing comparable within the sky ring.
    if sep > 60 and float(row["j_m"]) < LIMIT and str(row["ph_qual"]).startswith("AAA") and min(others or [999]) > 45:
        stars.append(row)
print(f"{len(stars)} isolated stars brighter than J = {LIMIT}, more than 60 arcsec from the target\n")

ratios: dict[str, list[float]] = {b: [] for b in BANDS}
for row in stars:
    points = []
    for e in exposures:
        path = spherex._cutout_path(e, pos["ra"], pos["dec"], photometry.CUTOUT_DEG)
        if path.exists():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                points.append(photometry.measure(path, float(row["ra"]), float(row["dec"])))
    line = f"  star at {float(row['ra']):.4f} {float(row['dec']):+.4f}:"
    for band, (col, centre, zero) in BANDS.items():
        catalogue = zero * 10 ** (-0.4 * float(row[col])) * 1000.0   # mJy
        near = [p["flux_mjy"] for p in points if p["status"] == "ok" and abs(p["wavelength_um"] - centre) < HALF_WIDTH]
        if len(near) >= 3:
            ratio = float(np.median(near)) / catalogue
            ratios[band].append(ratio)
            line += (f"  {band} {catalogue:7.1f} mJy, SPHEREx {np.median(near):7.1f} ({len(near)} exp), "
                     f"ratio {ratio:.2f};")
        else:
            line += f"  {band} {catalogue:7.1f} mJy, too few clean exposures ({len(near)});"
    print(line)
print()
for band, values in ratios.items():
    if values:
        print(f"{band}: SPHEREx / 2MASS for {len(values)} stars: median {np.median(values):.2f}, "
              f"range {min(values):.2f} to {max(values):.2f}")

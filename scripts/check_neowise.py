"""Has NASA's NEOWISE mission seen this object change before? A check of a search candidate
against another telescope's archive.

    python scripts/check_neowise.py RA DEC [--name NAME] [--out FILE.png] [--radius 1.5]

The blind search (backend/search.py) compares SPHEREx with itself: two or three visits a
year apart. NEOWISE measured the whole sky at 3.4 and 4.6 micrometres about twice a year
from 2014 to 2024, and every single measurement is public at IRSA. So for any object the
search flags as changing we can ask two things that SPHEREx alone cannot answer:

1. Did it change in the ten years before SPHEREx? Then the change is real behaviour of
   the object and not an artefact of SPHEREx, and it is not a first-time event.
2. Do the two telescopes agree on how bright it is? NEOWISE's 4.6 micrometre band covers
   the same wavelengths as SPHEREx detectors 5 and 6.

What this does
- Asks IRSA for every NEOWISE single-exposure measurement within 8 arcsec (table
  `neowiser_p1bs_psd`), keeps those within `--radius` arcsec of the position on frames
  NEOWISE itself rates usable, groups them into visits and takes each visit's median.
- Converts magnitudes to millijanskys with the zero points of the WISE Explanatory
  Supplement, section IV.4.h, Table 1 (W1 309.540 Jy, W2 171.787 Jy; read 2026-11-14).
- Measures the same position in SPHEREx with the app's own brightness code
  (backend/photometry.py, the code behind /api/lightcurve, which shares nothing with the
  search's photometry) and takes each visit's median over 2.8 to 3.8 and 4.0 to 5.0
  micrometres, close to the two NEOWISE bands.
- Prints both tables and draws one chart.

Limits to keep in mind when reading the result
- NEOWISE saturates on bright objects (roughly magnitude 8 at 3.4 and 7 at 4.6
  micrometres). Its numbers for brighter states are biased; `sat` in the table is the
  share of saturated pixels NEOWISE reports. The faint states are not affected.
- Both telescopes blur about 6 arcsec. Several objects that close together are measured
  as one by both, so neither can say which of them changed.
- The band edges differ, so agreement to a few tens of per cent is all that can be asked.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import numpy as np
from astropy.table import Table
from astropy.time import Time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_plot as vp  # noqa: E402

from backend import astrometry, photometry, spherex  # noqa: E402

GATOR = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
ZERO_JY = {"w1": 309.540, "w2": 171.787}        # WISE Explanatory Supplement IV.4.h, Table 1
BAND_UM = {"w1": (2.8, 3.8), "w2": (4.0, 5.0)}  # SPHEREx wavelengths compared with each NEOWISE band
BAND_NAME = {"w1": "3.4 micrometres (NEOWISE W1)", "w2": "4.6 micrometres (NEOWISE W2)"}
VISIT_GAP_DAYS = 30.0
MIN_PER_VISIT = 3


def neowise_rows(ra: float, dec: float) -> Table:
    """Every NEOWISE single-exposure measurement within 8 arcsec. Cached like the other catalogue answers."""
    cache = spherex.CACHE / "queries" / f"neowise_{ra:.5f}_{dec:.5f}.tbl"
    if not cache.exists():
        raw = spherex.http_get(GATOR, {
            "catalog": "neowiser_p1bs_psd", "spatial": "cone", "objstr": f"{ra} {dec}", "radius": 8,
            "radunits": "arcsec", "outfmt": 1,
            "selcols": "ra,dec,mjd,w1mpro,w1sigmpro,w2mpro,w2sigmpro,w1sat,w2sat,qual_frame,cc_flags"},
            tries=5, timeout=120)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    return Table.read(io.BytesIO(cache.read_bytes()), format="ipac")


def to_mjy(mag: float, band: str) -> float:
    return ZERO_JY[band] * 10 ** (-0.4 * mag) * 1000.0


def neowise_visits(table: Table, ra: float, dec: float, radius: float) -> tuple[list[dict], dict]:
    def column(name: str) -> np.ndarray:
        return np.array(np.ma.filled(np.ma.array(table[name], dtype=float), np.nan))

    offsets = [astrometry.offset_arcsec(ra, dec, float(r), float(d)) for r, d in zip(table["ra"], table["dec"],
                                                                                     strict=True)]
    dist = np.array([np.hypot(e, n) for e, n in offsets])
    mjd, quality = column("mjd"), column("qual_frame")
    order = np.argsort(mjd)
    visit = np.empty(len(mjd), int)
    visit[order] = np.concatenate([[0], np.cumsum(np.diff(mjd[order]) > VISIT_GAP_DAYS)])
    near = (dist < radius) & (quality > 0)
    out = []
    for v in np.unique(visit):
        row: dict = {"mjd": float(np.mean(mjd[visit == v]))}
        for band in ("w1", "w2"):
            mag, err, sat = column(f"{band}mpro"), column(f"{band}sigmpro"), column(f"{band}sat")
            use = (visit == v) & near & np.isfinite(mag) & np.isfinite(err)
            if use.sum() < MIN_PER_VISIT:
                row[band] = None
                continue
            row[band] = {"n": int(use.sum()), "mag": float(np.median(mag[use])),
                         "scatter": float(np.std(mag[use])), "sat": float(np.median(sat[use])),
                         "mjy": to_mjy(float(np.median(mag[use])), band)}
        if row["w1"] or row["w2"]:
            out.append(row)
    counts = {"all": len(table), "near": int((dist < radius).sum()), "used_frames": int(near.sum()),
              "further": int((dist >= radius).sum())}
    return out, counts


def spherex_visits(ra: float, dec: float) -> tuple[list[dict], dict]:
    curve = photometry.lightcurve(ra, dec)
    points = [p for b in curve["bins"] for p in b["points"]]
    by_visit: dict[int, list[dict]] = {}
    for p in points:
        by_visit.setdefault(p["epoch"], []).append(p)
    out = []
    for ep in sorted(by_visit):
        row: dict = {"epoch": ep, "mjd": float(np.mean([p["mjd"] for p in by_visit[ep]]))}
        for band, (lo, hi) in BAND_UM.items():
            inside = [p for p in by_visit[ep] if lo <= p["wavelength_um"] <= hi]
            good = [p["flux_mjy"] for p in inside if p["status"] == "ok" and p["flux_mjy"] is not None]
            row[band] = {"n": len(good), "n_saturated": sum(p["status"] == "saturated" for p in inside),
                         "mjy": float(np.median(good)) if len(good) >= MIN_PER_VISIT else None,
                         "low": float(np.percentile(good, 16)) if len(good) >= MIN_PER_VISIT else None,
                         "high": float(np.percentile(good, 84)) if len(good) >= MIN_PER_VISIT else None}
        out.append(row)
    return out, {"measured": curve.get("measured"), "status_counts": curve.get("status_counts"),
                 "stars_in_circle": curve.get("stars_in_circle"), "failures": len(curve.get("failures") or [])}


def date(mjd: float) -> str:
    return Time(mjd, format="mjd").iso[:10]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ra", type=float)
    parser.add_argument("dec", type=float)
    parser.add_argument("--name", default=None)
    parser.add_argument("--out", type=Path, default=None, help="where to write the chart (PNG)")
    parser.add_argument("--radius", type=float, default=1.5, help="NEOWISE measurements this close count (arcsec)")
    args = parser.parse_args()
    name = args.name or f"RA {args.ra:.5f}, Dec {args.dec:+.5f}"

    neo, counts = neowise_visits(neowise_rows(args.ra, args.dec), args.ra, args.dec, args.radius)
    print(f"{name}\nNEOWISE single exposures within 8 arcsec: {counts['all']}; within {args.radius} arcsec: "
          f"{counts['near']} ({counts['used_frames']} on usable frames); further out, other objects or artefacts: "
          f"{counts['further']}")
    head = f"{'n':>3} {'mag':>7} {'mJy':>7} {'sat':>5}"
    print(f"\n{'NEOWISE visit':>13} {head}   {head}      (3.4 micrometres, then 4.6)")
    for row in neo:
        cells = []
        for band in ("w1", "w2"):
            b = row[band]
            cells.append(f"{b['n']:3d} {b['mag']:7.2f} {b['mjy']:7.0f} {b['sat']:5.2f}" if b
                         else f"{'-':>3} {'-':>7} {'-':>7} {'-':>5}")
        print(f"{date(row['mjd']):>13} {cells[0]}   {cells[1]}")
    for band in ("w1", "w2"):
        mjy = [row[band]["mjy"] for row in neo if row[band]]
        if len(mjy) >= 2:
            print(f"{BAND_NAME[band]}: {min(mjy):.0f} to {max(mjy):.0f} mJy over {len(mjy)} visits, "
                  f"a factor of {max(mjy) / min(mjy):.1f}")

    sph, about = spherex_visits(args.ra, args.dec)
    print(f"\nSPHEREx, the app's own brightness code: {about['status_counts']}, download failures {about['failures']}")
    if about["measured"]:
        print(f"  what was measured: {about['measured'].get('description')}")
    print(f"{'SPHEREx visit':>13} {'n':>3} {'2.8-3.8 um mJy':>15} {'(16-84%)':>13}   "
          f"{'n':>3} {'4.0-5.0 um mJy':>15} {'(16-84%)':>13} {'saturated':>9}")
    for row in sph:
        cells = []
        for band in ("w1", "w2"):
            b = row[band]
            if b["mjy"] is None:
                cells.append(f"{b['n']:3d} {'-':>15} {'-':>13}")
            else:
                spread = f"{b['low']:.0f}-{b['high']:.0f}"
                cells.append(f"{b['n']:3d} {b['mjy']:15.0f} {spread:>13}")
        print(f"{date(row['mjd']):>13} {cells[0]}   {cells[1]} {row['w2']['n_saturated']:9d}")

    if args.out:
        charts = []
        for band, colour in (("w2", vp.RED), ("w1", vp.BLUE)):
            chart = vp.Chart(title=f"{name}: brightness at {BAND_NAME[band]}, 2014 to 2026",
                             xlabel="date", ylabel="brightness (mJy, log scale)", xdate=True, logy=True, height=380)
            rows = [r for r in neo if r[band]]
            chart.scatter([r["mjd"] for r in rows], [r[band]["mjy"] for r in rows], color=vp.GREY,
                          label="NEOWISE, median of each visit (hollow: partly saturated)", size=5)
            partly = [r for r in rows if r[band]["sat"] > 0.2]
            if partly:
                chart.scatter([r["mjd"] for r in partly], [r[band]["mjy"] for r in partly], color=(255, 255, 255),
                              size=3)
            got = [r for r in sph if r[band]["mjy"] is not None]
            lo, hi = BAND_UM[band]
            chart.scatter([r["mjd"] for r in got], [r[band]["mjy"] for r in got], color=colour, marker="s", size=6,
                          label=f"SPHEREx, median of each visit, {lo} to {hi} micrometres")
            charts.append(chart.render())
        caption = vp.caption_block(charts[0].width, [
            "Each grey dot is the median of the NEOWISE single exposures of one visit (about twice a year); each "
            "square is one SPHEREx visit, measured by this project.",
            "NEOWISE saturates on bright objects, so its hollow points are less certain. Both telescopes blur about "
            "6 arcsec: close neighbours are measured together.",
            "Data: NEOWISE-R Single Exposure Source Table (NASA/IPAC IRSA); SPHEREx level-2 images "
            "(NASA/JPL-Caltech, IRSA)."])
        vp.save(vp.stack_vertical([*charts, caption]), args.out)


if __name__ == "__main__":
    main()

"""Proof that a cutout read from S3 is the cutout IRSA serves, how fast it arrives, and what
happens when the bucket misbehaves.

Run:  SPHEREX_CACHE_DIR=<cache with IRSA cutouts> .venv/bin/python scripts/check_s3.py [options]

The cache's `cutouts/` folder is the ground truth: slim copies of what IRSA's cutout
service returned (see `backend/spherex.py`). This script fetches the same exposures from
the public S3 bucket with `backend/s3fetch.py`, writes them to a folder of its own
(never into the cache) and compares the two files of each exposure:

- where each cutout sits on the detector (its "A" coordinates) and whether the S3 box
  covers IRSA's;
- IMAGE, FLAGS, VARIANCE, ZODI, WAVE and BANDWIDTH, pixel by pixel where the boxes
  overlap, bit for bit (so a NaN must be the same NaN);
- the sky position of every shared pixel through each file's own WCS;
- every header line, and the whole file byte for byte.

Every difference is printed. Exit status 1 if any pixel, header line or position differs.

  (no option)       a sample: per target, detector and visit two exposures, plus cutouts
                    clipped by a detector edge and exposures whose reference pixel is
                    not the detector centre. Targets: Barnard's Star (0.15 and 0.3
                    degrees), RW Aurigae, R Draconis.
  --all             every cached cutout of the chosen sets
  --sets a,b        which sets (see SETS below); "every" for all of them
  --skip-compare    leave the comparison out (with --speed or --faults)
  --speed           time ranged reads, single cutouts, a one-detector field, the
                    six-detector field and a 0.5 degree field through S3
  --sweep 4,8,16    with --speed: the one-detector field at each of these request caps
  --irsa N          with --speed: also fetch N cutouts through IRSA at 0.15 and at 0.5
                    degrees (N <= 6), for a same-day time and a check of the box rule at a
                    size the cache does not hold. IRSA is shared and fragile: keep N small.
  --faults          failure handling: three bad requests to the real bucket, then a
                    stand-in for the bucket on this machine that misbehaves on purpose
                    (it serves one real exposure file, downloaded whole once: 65 MB)
  --concurrency N   simultaneous S3 requests (default 16)
  --out DIR         where fetched files go (default scripts/out/s3)
"""
import argparse
import hashlib
import io
import json
import socket
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import requests
from astropy import log
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import s3fetch, spherex  # noqa: E402

# Building the wavelength WCS makes astropy print 14 lines about SIP keywords, per cutout.
log.setLevel("WARNING")

# Cutout sets in the project's cache: name, centre (position at 2026.0 from /api/resolve), size in degrees.
SETS = {
    "barnard": ("Barnard's Star", 269.446267, 4.768222, 0.15),
    "rwaur": ("RW Aurigae", 76.956587, 30.401291, 0.15),
    "rdra": ("R Draconis", 248.167233, 66.755024, 0.15),
    "barnard-0.3": ("Barnard's Star", 269.446267, 4.768222, 0.3),
    "epsindi": ("Epsilon Indi B", 331.096653, -56.800663, 0.15),
    "wise0855": ("WISE 0855", 133.759765, -7.242182, 0.15),
}
DEFAULT_SETS = "barnard,rwaur,rdra,barnard-0.3"
ARRAYS = ("IMAGE", "FLAGS", "VARIANCE", "ZODI", "WAVE", "BANDWIDTH")
DETECTOR_SIDE = 2040
CENTRE = (1020.5, 1020.5)   # CRPIX of nearly every full image


def name_of(exp: dict) -> tuple[str, int]:
    return exp["obs_id"], exp["detector"]


def detector_box(header: fits.Header) -> tuple[int, int, int, int]:
    """(x0, x1, y0, y1) of a cutout on the detector, read through its "A" coordinate system."""
    x, y = WCS(header, key="A").wcs_pix2world(0, 0, 0)
    x0, y0 = int(round(float(x))), int(round(float(y)))
    return x0, x0 + header["NAXIS1"], y0, y0 + header["NAXIS2"]


def placement(header: fits.Header) -> tuple[tuple[int, int, int, int], bool, tuple[float, float]]:
    """A cutout's box, whether a detector edge clipped it, and the CRPIX the full image has."""
    box = detector_box(header)
    clipped = box[0] == 0 or box[2] == 0 or box[1] == DETECTOR_SIDE or box[3] == DETECTOR_SIDE
    return box, clipped, (round(header["CRPIX1"] + box[0], 6), round(header["CRPIX2"] + box[2], 6))


def visits_of(exposures: list[dict]) -> dict[tuple[str, int], int]:
    """Visit number of each exposure: a gap of more than 30 days starts a new visit (as the pipeline does)."""
    out, visit, last = {}, 0, None
    for e in sorted(exposures, key=lambda e: e["mjd"]):
        if last is None or e["mjd"] - last > 30:
            visit += 1
        last = e["mjd"]
        out[name_of(e)] = visit
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(mine: Path, theirs: Path) -> dict:
    """Everything that differs between an S3 cutout and the IRSA cutout of the same exposure."""
    res: dict = {"differences": [], "file_identical": sha(mine) == sha(theirs)}
    with fits.open(mine) as a, fits.open(theirs) as b:
        ha, hb = a["IMAGE"].header, b["IMAGE"].header
        box_a = detector_box(ha)
        box_b, res["clipped"], res["ref_pixel"] = placement(hb)
        res["box_s3"], res["box_irsa"] = box_a, box_b
        res["same_box"] = box_a == box_b
        res["covers"] = box_a[0] <= box_b[0] and box_a[1] >= box_b[1] and box_a[2] <= box_b[2] and box_a[3] >= box_b[3]
        if not res["covers"]:
            res["differences"].append(f"the S3 box {box_a} does not cover IRSA's {box_b}")
        # The detector pixels both cutouts hold, and where they are in each array.
        x0, x1 = max(box_a[0], box_b[0]), min(box_a[1], box_b[1])
        y0, y1 = max(box_a[2], box_b[2]), min(box_a[3], box_b[3])
        if x0 >= x1 or y0 >= y1:
            res["differences"].append("the two cutouts share no pixel")
            res["pixels"] = 0
            return res
        sa = (slice(y0 - box_a[2], y1 - box_a[2]), slice(x0 - box_a[0], x1 - box_a[0]))
        sb = (slice(y0 - box_b[2], y1 - box_b[2]), slice(x0 - box_b[0], x1 - box_b[0]))
        res["pixels"] = (x1 - x0) * (y1 - y0)
        res["nan_pixels"] = int(np.isnan(a["IMAGE"].data[sa]).sum())

        for name in ARRAYS:
            da, db = a[name].data, b[name].data
            if da.dtype != db.dtype:
                res["differences"].append(f"{name}: stored as {da.dtype} in S3 cutout, {db.dtype} in IRSA cutout")
            va, vb = np.ascontiguousarray(da[sa]), np.ascontiguousarray(db[sb])
            # Bit for bit: the stored bytes of each pixel, so a NaN must be the same NaN.
            bits = va.view(f"u{va.dtype.itemsize}") != vb.view(f"u{vb.dtype.itemsize}") \
                if va.dtype.itemsize == vb.dtype.itemsize else np.ones(va.shape, bool)
            fa, fb = va.astype("float64"), vb.astype("float64")
            values = (fa != fb) & ~(np.isnan(fa) & np.isnan(fb))
            res[name] = {"bits": int(bits.sum()), "values": int(values.sum())}
            if bits.any():
                iy, ix = np.argwhere(bits)[0]
                both = np.isfinite(fa) & np.isfinite(fb)
                largest = float(np.abs(fa - fb)[both].max()) if both.any() else float("nan")
                res["differences"].append(
                    f"{name}: {int(bits.sum())} of {bits.size} pixels differ in their bytes, {int(values.sum())} in "
                    f"value (largest difference {largest:.6g}); first at detector x={x0 + ix} y={y0 + iy}: "
                    f"S3 {va[iy, ix]!r}, IRSA {vb[iy, ix]!r}")

        # Sky position of every shared pixel through each file's own WCS (SIP included).
        yy, xx = np.mgrid[y0:y1, x0:x1]
        wa, wb = WCS(ha), WCS(hb)
        ra_a, dec_a = wa.all_pix2world(xx - box_a[0], yy - box_a[2], 0)
        ra_b, dec_b = wb.all_pix2world(xx - box_b[0], yy - box_b[2], 0)
        sep = np.hypot((ra_a - ra_b) * np.cos(np.radians(dec_a)), dec_a - dec_b)
        res["sky_offset_px"] = float(sep.max() / proj_plane_pixel_scales(wa).mean())
        if res["sky_offset_px"] > 0:
            res["differences"].append(f"sky position of a pixel differs by up to {res['sky_offset_px']:.2e} pixel")

        # Header lines. With different boxes NAXIS and CRPIX must differ, so only then are they let through.
        res["header_lines"] = 0
        for name in ("PRIMARY", *ARRAYS):
            ca, cb = [str(c) for c in a[name].header.cards], [str(c) for c in b[name].header.cards]
            if not res["same_box"]:
                ca = [c for c in ca if not c.startswith(("NAXIS", "CRPIX"))]
                cb = [c for c in cb if not c.startswith(("NAXIS", "CRPIX"))]
            if ca != cb:
                only_a, only_b = [c.rstrip() for c in ca if c not in cb], [c.rstrip() for c in cb if c not in ca]
                res["header_lines"] += max(len(only_a), len(only_b), 1)
                res["differences"].append(f"{name} header: S3 only {only_a[:6]}, IRSA only {only_b[:6]}"
                                          + ("" if only_a or only_b else " (same lines, different order)"))
        if res["same_box"] and not res["differences"] and not res["file_identical"]:
            res["differences"].append("same pixels and header lines, but the files differ in their bytes")
    return res


def choose(exposures: list[dict], cached: dict, visit: dict, per_visit: int, clipped_max: int) -> list[dict]:
    """A sample spread over detectors and visits, plus the awkward cases.

    Awkward: cutouts that a detector edge clipped (a few), and every exposure whose
    reference pixel is not the detector centre (rare, and where CRPIX arithmetic shows).
    """
    groups = defaultdict(list)
    for e in exposures:
        groups[(e["detector"], visit[name_of(e)])].append(e)
    picked = []
    for _, group in sorted(groups.items()):
        for i in sorted({round(k * (len(group) - 1) / max(per_visit - 1, 1)) for k in range(per_visit)}):
            picked.append(group[i])
    clipped, off_centre = [], []
    for e in exposures:
        with fits.open(cached[name_of(e)]) as hdul:
            _, is_clipped, ref_pixel = placement(hdul["IMAGE"].header)
        if ref_pixel != CENTRE and e not in picked:
            off_centre.append(e)
        elif is_clipped and e not in picked:
            clipped.append(e)
    step = max(len(clipped) // max(clipped_max, 1), 1)
    return picked + clipped[::step][:clipped_max] + off_centre


def run_comparison(sets: list[str], out: Path, concurrency: int, everything: bool) -> tuple[int, list[dict]]:
    rows, bad = [], 0
    for key in sets:
        name, ra, dec, size = SETS[key]
        exposures = spherex.find_exposures(ra, dec, max_age_s=float("inf"))
        visit = visits_of(exposures)
        cached = {name_of(e): spherex._cutout_path(e, ra, dec, size) for e in exposures}
        have = [e for e in exposures if cached[name_of(e)].exists()]
        if not have:
            print(f"\n{name}, {size} degrees: no IRSA cutouts in {spherex.CACHE / 'cutouts'}; set SPHEREX_CACHE_DIR")
            continue
        chosen = have if everything else choose(have, cached, visit, per_visit=2, clipped_max=6)
        with s3fetch.S3Reader(concurrency) as reader:
            start = time.perf_counter()
            fetched = s3fetch.fetch_cutouts(chosen, ra, dec, size, out / "compare", reader=reader, overwrite=True)
            took = time.perf_counter() - start
            print(f"\n{name}, {size} degrees: {len(chosen)} of {len(have)} cached exposures fetched from S3 in "
                  f"{took:.1f}s ({concurrency} requests at a time, {reader.requests} requests, "
                  f"{reader.bytes_read / 1e6:.0f} MB, {reader.retries} retries)")
        print(f"  {'exposure':<20}{'det':>3} {'visit':>5}  {'date':<10}  {'IRSA box x0:x1 y0:y1':<22} {'S3 box':<8}"
              f"{'pixels':>7} {'NaN':>4}  IMAGE FLAGS VARIA  ZODI  WAVE BANDW  {'sky off (px)':>12}  hdr  file  note")
        for e, path, err in fetched:
            if path is None:
                bad += 1
                print(f"  {e['obs_id']:<20}{e['detector']:>3}  NOT FETCHED: {err}")
                rows.append({"set": key, "target": name, "size": size, "obs_id": e["obs_id"],
                             "detector": e["detector"], "error": err})
                continue
            r = compare(path, cached[name_of(e)])
            b = r["box_irsa"]
            with fits.open(path) as hdul:
                date = str(hdul["IMAGE"].header["DATE-AVG"])[:10]
            cells = "".join(f"{r.get(n, {}).get('bits', '-'):>5} " for n in ARRAYS)
            note = ", ".join(n for n in ("edge" if r["clipped"] else "",
                                         f"CRPIX {r['ref_pixel']}" if r["ref_pixel"] != CENTRE else "") if n)
            print(f"  {e['obs_id']:<20}{e['detector']:>3} {visit[name_of(e)]:>5}  {date:<10}  "
                  f"{f'{b[0]}:{b[1]} {b[2]}:{b[3]}':<22} {'same' if r['same_box'] else str(r['box_s3']):<8}"
                  f"{r['pixels']:>7} {r.get('nan_pixels', 0):>4}  {cells} "
                  f"{r.get('sky_offset_px', float('nan')):>12.1e}  "
                  f"{r.get('header_lines', '-'):>3}  {'same' if r['file_identical'] else 'DIFF'}  {note}")
            for d in r["differences"]:
                print(f"      DIFFERENCE: {d}")
            bad += bool(r["differences"])
            rows.append({"set": key, "target": name, "size": size, "obs_id": e["obs_id"], "detector": e["detector"],
                         "visit": visit[name_of(e)], "date": date, **r})
    return bad, rows


def summarise(rows: list[dict]) -> None:
    print("\nSummary. Differing pixels are counted bit for bit. 'edge': clipped by a detector edge. "
          "'off-centre': reference pixel (CRPIX) of the full image is not 1020.5, 1020.5.")
    print(f"  {'target':<16}{'size':>5} {'det':>3} {'visits':>6} {'exposures':>9} {'edge':>5} {'off-centre':>10} "
          f"{'pixels':>9} {'IMAGE':>6}{'FLAGS':>6}{'VARIA':>6}{'ZODI':>6}{'WAVE':>6}{'BANDW':>6} "
          f"{'max sky off (px)':>16} {'same box':>8} {'hdr lines':>9} {'files identical':>15}")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["target"], r["size"], r["detector"])].append(r)
    total: Counter = Counter()
    for (target, size, det), rs in sorted(groups.items()):
        ok = [r for r in rs if "error" not in r]
        clipped = sum(r["clipped"] for r in ok)
        off_centre = sum(tuple(r["ref_pixel"]) != CENTRE for r in ok)
        diffs = [sum(r.get(n, {}).get("bits", 0) for r in ok) for n in ARRAYS]
        pixels = sum(r["pixels"] for r in ok)
        print(f"  {target:<16}{size:>5} {det:>3} {len({r['visit'] for r in ok}):>6} {len(ok):>9} {clipped:>5} "
              f"{off_centre:>10} {pixels:>9} " + "".join(f"{d:>6}" for d in diffs)
              + f" {max((r.get('sky_offset_px', 0.0) for r in ok), default=0.0):>16.1e} "
              f"{sum(r['same_box'] for r in ok):>8} {sum(r.get('header_lines', 0) for r in ok):>9} "
              f"{sum(r['file_identical'] for r in ok):>15}")
        total.update(exposures=len(ok), failed=len(rs) - len(ok), clipped=clipped, off_centre=off_centre,
                     pixels=pixels, differing=sum(diffs), same_box=sum(r["same_box"] for r in ok),
                     covers=sum(r["covers"] for r in ok), identical=sum(r["file_identical"] for r in ok),
                     with_differences=sum(bool(r["differences"]) for r in ok))
    print(f"\n  {total['exposures']} exposures compared ({total['clipped']} clipped by a detector edge, "
          f"{total['off_centre']} with an off-centre reference pixel), {total['failed']} not fetched; "
          f"{total['pixels']} pixels in each of six arrays;")
    print(f"  {total['differing']} pixel values differ; same box as IRSA in {total['same_box']}, IRSA's box covered "
          f"in {total['covers']}; {total['identical']} files identical byte for byte; "
          f"{total['with_differences']} exposures with any difference.")


def irsa_cutout(exp: dict, ra: float, dec: float, size: float) -> tuple[fits.HDUList, float, float, int]:
    """One cutout through IRSA, slimmed with the same steps as spherex.fetch_cutout, kept in memory.

    Returns (cutout, seconds, megabytes downloaded, failed attempts). One request at a
    time and a generic client name: this is only for a handful of cutouts.
    """
    url = f"{exp['url']}?center={ra:.6f},{dec:.6f}&size={size:.5f}"
    start, failed = time.perf_counter(), 0
    while True:
        try:
            r = requests.get(url, headers={"User-Agent": s3fetch.USER_AGENT}, timeout=90)
            if r.status_code == 200:
                break
            problem = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            problem = type(e).__name__
        failed += 1
        if failed >= 10:
            raise RuntimeError(f"{problem} from {url}")
        time.sleep(min(0.8 * 1.6 ** failed, 12))
    seconds = time.perf_counter() - start
    with fits.open(io.BytesIO(r.content)) as hdul:
        header = hdul["IMAGE"].header
        ny, nx = hdul["IMAGE"].data.shape
        spectral = WCS(header, fobj=hdul, key="W")
        spectral.sip = None
        xx, yy = np.meshgrid(np.arange(nx), np.arange(ny))
        wave, band = spectral.wcs_pix2world(xx, yy, 0)
        out = fits.HDUList([fits.PrimaryHDU()])
        for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
            out.append(fits.ImageHDU(hdul[name].data, header=hdul[name].header, name=name))
        out.append(fits.ImageHDU(wave.astype("float32"), name="WAVE"))
        out.append(fits.ImageHDU(band.astype("float32"), name="BANDWIDTH"))
    return out, seconds, len(r.content) / 1e6, failed


def timed_field(label: str, exposures: list[dict], ra: float, dec: float, size: float, folder: Path,
                concurrency: int, truth: float | None = None) -> tuple[list, int]:
    """Fetch a field into a fresh folder and say how long it took. With `truth` (the size of the cached
    IRSA cutouts to hold the files against) also count the files that are not those cutouts byte for byte."""
    with s3fetch.S3Reader(concurrency) as reader:
        start = time.perf_counter()
        results = s3fetch.fetch_cutouts(exposures, ra, dec, size, folder, reader=reader, overwrite=True)
        took = time.perf_counter() - start
        failed = [(e["obs_id"], e["detector"], err) for e, p, err in results if p is None]
        print(f"  {label}: {len(results) - len(failed)} cutouts in {took:.1f}s = {took / len(results):.3f}s each, "
              f"{concurrency} requests at a time; {reader.requests} requests, {reader.bytes_read / 1e6:.0f} MB read "
              f"({reader.bytes_read / 1e6 / took:.0f} MB/s), {reader.retries} retries; {len(failed)} failed")
    for f in failed:
        print("    FAILED", f)
    bad = len(failed)
    if truth is not None:
        pairs = [(p, spherex._cutout_path(e, ra, dec, truth)) for e, p, _ in results if p]
        pairs = [(p, t) for p, t in pairs if t.exists()]
        same = sum(sha(p) == sha(t) for p, t in pairs)
        print(f"    {same} of {len(pairs)} files are byte for byte the cached IRSA cutouts")
        bad += len(pairs) - same
    return results, bad


def run_speed(out: Path, concurrency: int, n_irsa: int, sweep: list[int]) -> int:
    name, ra, dec, _ = SETS["barnard"]
    exposures = spherex.find_exposures(ra, dec, max_age_s=float("inf"))
    d5 = [e for e in exposures if e["detector"] == 5]
    print(f"\nSpeed, measured from this machine against {name} ({len(exposures)} exposures, {len(d5)} in detector 5)")

    # 1. Single ranged reads on one warm connection, a different file each time.
    row = DETECTOR_SIDE * 4
    with s3fetch.S3Reader(1) as reader:
        start = time.perf_counter()
        reader.read_many(s3fetch.s3_url(exposures[0]), [(0, s3fetch.BLOCK)])
        print(f"  first contact (DNS, TLS, 2880 bytes): {time.perf_counter() - start:.3f}s")
        for label, a, b in (("header read (first 40 kB: PRIMARY and IMAGE headers)", 0, s3fetch.FIRST_READ),
                            ("88 image rows (718 kB, a 0.15 degree cutout)", 25920 + 900 * row, 25920 + 988 * row),
                            ("293 image rows (2.4 MB, a 0.5 degree cutout)", 25920 + 900 * row, 25920 + 1193 * row)):
            times = []
            for e in exposures[1:11]:
                start = time.perf_counter()
                reader.read_many(s3fetch.s3_url(e), [(a, b)])
                times.append(time.perf_counter() - start)
            print(f"  {label}: median {statistics.median(times) * 1000:.0f} ms "
                  f"(fastest {min(times) * 1000:.0f}, slowest {max(times) * 1000:.0f}, 10 files)")

    # 2. One cutout at a time.
    for size in (0.15, 0.5):
        with s3fetch.S3Reader(concurrency) as reader:
            times = []
            for e in d5[:9]:
                start = time.perf_counter()
                s3fetch.fetch_cutout(e, ra, dec, size, s3fetch.cutout_path(out / "speed-single", e, ra, dec, size),
                                     reader=reader, overwrite=True)
                times.append(time.perf_counter() - start)
            print(f"  one {size} degree cutout, alone: median {statistics.median(times[1:]):.2f}s (fastest "
                  f"{min(times[1:]):.2f}, slowest {max(times[1:]):.2f}, 8 exposures; the one before them, which "
                  f"opened the connections, took {times[0]:.2f}s); {reader.requests / 9:.0f} requests and "
                  f"{reader.bytes_read / 9e6:.2f} MB per cutout")

    # 3. Whole fields.
    bad = 0
    for cap in sweep or [concurrency]:
        _, n = timed_field(f"detector 5 at 0.15 degrees ({len(d5)} exposures)", d5, ra, dec, 0.15, out / "speed-d5",
                           cap, truth=0.15)
        bad += n
    _, n = timed_field(f"all six detectors at 0.15 degrees ({len(exposures)} exposures)", exposures, ra, dec, 0.15,
                       out / "speed-all", concurrency, truth=0.15)
    bad += n
    wide, n = timed_field(f"detector 5 at 0.5 degrees ({len(d5)} exposures)", d5, ra, dec, 0.5, out / "speed-wide",
                          concurrency)
    bad += n
    # No IRSA cutout of 0.5 degrees is cached, but the 0.3 and 0.15 degree ones lie inside it.
    for inner in (0.3, 0.15):
        compared = pixels = differing = 0
        for e, p, _ in wide:
            theirs = spherex._cutout_path(e, ra, dec, inner)
            if p and theirs.exists():
                r = compare(p, theirs)
                compared += 1
                pixels += r["pixels"]
                differing += sum(r.get(a, {}).get("bits", 0) for a in ARRAYS) + (r.get("sky_offset_px", 0) > 0)
                for d in r["differences"]:
                    print(f"    DIFFERENCE {e['obs_id']} D{e['detector']} against the {inner} degree cutout: {d}")
                bad += bool(r["differences"])
        print(f"    against the cached {inner} degree IRSA cutouts of the same exposures: {compared} compared, "
              f"{pixels} shared pixels in each of six arrays, {differing} differ")

    # 4. The same through IRSA, a handful only.
    if n_irsa:
        print(f"\n  IRSA, {n_irsa} cutouts per size, one request at a time:")
        for size, folder in ((0.15, out / "speed-d5"), (0.5, out / "speed-wide")):
            step = max(len(d5) // n_irsa, 1)
            for e in d5[::step][:n_irsa]:
                cutout, seconds, megabytes, failed = irsa_cutout(e, ra, dec, size)
                theirs = out / "irsa" / f"{size}" / f"{e['obs_id']}_D{e['detector']}.fits"
                theirs.parent.mkdir(parents=True, exist_ok=True)
                cutout.writeto(theirs, overwrite=True)
                r = compare(s3fetch.cutout_path(folder, e, ra, dec, size), theirs)
                verdict = "the S3 file is identical byte for byte" if r["file_identical"] else "the S3 file DIFFERS"
                print(f"    {size} degrees {e['obs_id']} D{e['detector']}: {seconds:.2f}s, {megabytes:.1f} MB, "
                      f"{failed} failed attempts first; box {r['box_irsa']}; {verdict}")
                for d in r["differences"]:
                    print(f"      DIFFERENCE: {d}")
                bad += bool(r["differences"]) or not r["file_identical"]
    return bad


class StandIn:
    """A stand-in for the bucket on this machine. Serves one real exposure file and misbehaves on request."""

    def __init__(self, blob: bytes) -> None:
        self.blob, self.lock = blob, threading.Lock()
        self.reset("ok")
        stand = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802 - the name http.server looks for
                with stand.lock:
                    stand.served += 1
                    stand.in_flight += 1
                    stand.peak = max(stand.peak, stand.in_flight)
                    stand.seen[self.headers.get("Range")] += 1
                    nth, count = stand.seen[self.headers.get("Range")], stand.served
                try:
                    stand.answer(self, nth, count)
                except OSError:   # the client hung up, as some of these tests make it do
                    pass
                finally:
                    with stand.lock:
                        stand.in_flight -= 1

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda *args: None   # a client hanging up is part of the tests
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def reset(self, mode: str, delay: float = 0.0) -> None:
        self.mode, self.delay, self.etag = mode, delay, '"first"'
        self.seen: Counter = Counter()
        self.served = self.in_flight = self.peak = 0

    def answer(self, h: BaseHTTPRequestHandler, nth: int, count: int) -> None:
        """nth: how many times this very range has been asked for. count: requests so far."""
        def send(status: int, body: bytes = b"", declared: int | None = None, **headers: str) -> None:
            h.send_response(status)
            for k, v in headers.items():
                h.send_header(k.replace("_", "-"), v)
            h.send_header("Content-Length", str(len(body) if declared is None else declared))
            h.end_headers()
            h.wfile.write(body)
            h.wfile.flush()

        time.sleep(self.delay)
        a, b = (int(v) for v in h.headers["Range"].removeprefix("bytes=").split("-"))
        b = min(b, len(self.blob) - 1)
        whole = str(len(self.blob))
        if self.mode == "503 twice" and nth <= 2 or self.mode == "always 503":
            return send(503, b"<Error><Code>SlowDown</Code></Error>")
        if self.mode == "whole file":   # what S3 does with a two-range request
            return send(200, self.blob[:65536], declared=len(self.blob), ETag=self.etag)
        if self.mode == "dropped" and nth == 1:   # half the answer, then the connection goes
            send(206, self.blob[a:(a + b) // 2], declared=b - a + 1, Content_Range=f"bytes {a}-{b}/{whole}")
            h.connection.shutdown(socket.SHUT_RDWR)
            return None
        if self.mode == "silent" and nth == 1:    # half the answer, then nothing
            send(206, self.blob[a:(a + b) // 2], declared=b - a + 1, Content_Range=f"bytes {a}-{b}/{whole}")
            time.sleep(4)
            h.close_connection = True
            return None
        if self.mode == "wrong bytes" and nth == 1:
            return send(206, self.blob[a + 80:b + 81], Content_Range=f"bytes {a + 80}-{b + 80}/{whole}", ETag=self.etag)
        if self.mode == "replaced" and count == 4:   # the file changes in the bucket after three reads of it
            self.etag = '"second"'
        if h.headers.get("If-Match") not in (None, self.etag):
            return send(412, b"<Error><Code>PreconditionFailed</Code></Error>")
        return send(206, self.blob[a:b + 1], Content_Range=f"bytes {a}-{b}/{whole}", ETag=self.etag)


def run_faults(out: Path) -> int:
    name, ra, dec, size = SETS["barnard"]
    exp = [e for e in spherex.find_exposures(ra, dec, max_age_s=float("inf")) if e["detector"] == 5][0]
    truth = spherex._cutout_path(exp, ra, dec, size)
    if not truth.exists():
        print(f"\nFailure handling: skipped, no IRSA cutout at {truth}")
        return 1
    want = sha(truth)
    failed = 0
    folder = out / "faults"

    def check(label: str, passed: bool, detail: str) -> None:
        nonlocal failed
        failed += not passed
        print(f"  {'ok  ' if passed else 'FAIL'} {label}: {detail}")

    def attempt(label: str, reader: s3fetch.S3Reader, expect: type | None = None, e: dict = exp, where: float = ra,
                extra: Callable[[], str] = str) -> None:
        """Fetch one cutout. expect None: the file must be the IRSA cutout. Else: that error, and no file."""
        path = folder / "cutout.fits"
        path.unlink(missing_ok=True)
        start = time.perf_counter()
        try:
            s3fetch.fetch_cutout(e, where, dec, size, path, reader=reader)
            got = "the file is IRSA's byte for byte" if sha(path) == want else "THE FILE DIFFERS from IRSA's"
            passed = expect is None and sha(path) == want
        except Exception as err:  # noqa: BLE001 - the error is the result
            got = f"{type(err).__name__}: {err}"
            passed = expect is not None and type(err) is expect and not list(folder.glob("cutout.fits*"))
        took = time.perf_counter() - start
        check(label, passed, f"{got[:140]} [{took:.2f}s, {reader.requests} good answers, {reader.retries} retries"
                             f"{extra()}]")

    print(f"\nFailure handling ({exp['obs_id']} D{exp['detector']} of {name})")
    print(" The real bucket:")
    with s3fetch.S3Reader(4) as reader:
        attempt("a key that is not in the bucket", reader, s3fetch.S3KeyMissing,
                e=dict(exp, url=exp["url"].replace("level2_", "no_such_")))
        attempt("a file that is not FITS (the bucket's index.html)", reader, s3fetch.S3LayoutError,
                e=dict(exp, url=exp["url"].split(s3fetch.IRSA_DATA_PATH)[0] + s3fetch.IRSA_DATA_PATH + "index.html"))
        attempt("a position 5 degrees off the image", reader, s3fetch.S3Error, where=ra + 5)

    full = out / "full" / Path(s3fetch.s3_key(exp)).name
    if not full.exists():
        full.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        r = requests.get(s3fetch.s3_url(exp), headers={"User-Agent": s3fetch.USER_AGENT}, timeout=300)
        r.raise_for_status()
        full.write_bytes(r.content)
        print(f" (downloaded the whole exposure file once for the stand-in: {len(r.content) / 1e6:.0f} MB in "
              f"{time.perf_counter() - start:.0f}s)")
    stand = StandIn(full.read_bytes())
    print(f" A stand-in for the bucket at {stand.url}, serving that file:")

    def reader_for(mode: str, **options: object) -> s3fetch.S3Reader:
        stand.reset(mode)
        return s3fetch.S3Reader(**{"max_concurrent": 8, "bucket_url": stand.url, **options})

    with reader_for("ok") as reader:
        attempt("nothing wrong", reader, extra=lambda: f", {stand.served} requests")
    # Wrong guesses about where things are must cost requests, never correctness.
    saved = {k: getattr(s3fetch, k) for k in ("FIRST_READ", "TABLE_HEADER_READ", "HEADER_READ", "TAIL_READ")}
    guess = dict(s3fetch._header_guess)
    for k in saved:
        setattr(s3fetch, k, s3fetch.BLOCK)
    s3fetch._header_guess.update(VARIANCE=s3fetch.BLOCK, ZODI=s3fetch.BLOCK)
    with reader_for("ok") as reader:
        attempt("every first read too short and every guess of a header length wrong", reader,
                extra=lambda: f", {stand.served} requests instead of 9")
    for k, v in saved.items():
        setattr(s3fetch, k, v)
    s3fetch._header_guess.update(guess)
    with reader_for("503 twice") as reader:
        attempt("HTTP 503 twice for every request, then fine", reader)
    with reader_for("dropped") as reader:
        attempt("connection dropped half way through every answer, once", reader)
    with reader_for("silent", timeout=(1.0, 1.0)) as reader:
        attempt("half an answer then silence, once (1 s allowed)", reader)
    with reader_for("wrong bytes") as reader:
        attempt("an answer holding other bytes than asked for, once", reader)
    with reader_for("replaced") as reader:
        attempt("the file replaced in the bucket during the read", reader, extra=lambda: f", {stand.served} requests")
    with reader_for("whole file") as reader:
        attempt("the server ignores Range and offers the whole file", reader, s3fetch.S3Error,
                extra=lambda: f", {reader.bytes_read} bytes taken")
    with reader_for("always 503", tries=3, cooloff_s=2.0) as reader:
        attempt("HTTP 503 every time", reader, s3fetch.S3Error, extra=lambda: f", {stand.served} requests")
        before = stand.served
        attempt("the next cutout after that failure (fails at once, no request sent)", reader, s3fetch.S3Error,
                extra=lambda: f", {stand.served - before} requests")
        stand.mode = "ok"
        time.sleep(2.1)
        attempt("and once the 2 s pause is over", reader)
    with s3fetch.S3Reader(4, tries=3, bucket_url="http://127.0.0.1:9") as reader:
        attempt("nothing listening at the address", reader, s3fetch.S3Error)

    for cap in (1, 4):
        with reader_for("ok", max_concurrent=cap) as reader:
            stand.delay = 0.03
            copies = [dict(exp, obs_id=f"copy{i}") for i in range(8)]
            results = s3fetch.fetch_cutouts(copies, ra, dec, size, folder / f"cap{cap}", reader=reader, overwrite=True)
            good = sum(1 for _, p, _ in results if p and sha(p) == want)
            check(f"request cap of {cap}", stand.peak <= cap and good == 8,
                  f"at most {stand.peak} requests in flight at once over {stand.served}; {good} of 8 files are IRSA's")

    # A write that cannot finish: the destination is a folder with something in it.
    target = folder / "taken"
    (target / "inside").mkdir(parents=True, exist_ok=True)
    with reader_for("ok") as reader:
        try:
            s3fetch.fetch_cutout(exp, ra, dec, size, target, reader=reader, overwrite=True)
            got = "no error"
        except OSError as err:
            got = type(err).__name__
    left = sorted(p.name for p in folder.glob("taken*"))
    check("a write that cannot be finished", got != "no error" and left == ["taken"],
          f"{got}; nothing half-written left beside the destination ({left})")
    stand.server.shutdown()
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sets", default=DEFAULT_SETS)
    parser.add_argument("--skip-compare", action="store_true")
    parser.add_argument("--speed", action="store_true")
    parser.add_argument("--sweep", default="")
    parser.add_argument("--irsa", type=int, default=0)
    parser.add_argument("--faults", action="store_true")
    parser.add_argument("--concurrency", type=int, default=s3fetch.DEFAULT_CONCURRENCY)
    parser.add_argument("--out", type=Path, default=ROOT / "scripts" / "out" / "s3")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(spherex.CACHE.resolve()):
        parser.error(f"--out must not be inside the cache ({spherex.CACHE})")
    if args.irsa > 6:
        parser.error("--irsa: at most 6, IRSA is shared")
    sets = list(SETS) if args.sets == "every" else args.sets.split(",")
    print(f"IRSA cutouts (ground truth): {spherex.CACHE / 'cutouts'}\nS3 cutouts written to: {out}")

    bad, compared = 0, True
    if not args.skip_compare:
        bad, rows = run_comparison(sets, out, args.concurrency, args.all)
        compared = bool(rows)
        if rows:
            summarise(rows)
            (out / "comparison.json").write_text(json.dumps(rows, indent=1))
    if args.speed:
        bad += run_speed(out, args.concurrency, args.irsa, [int(n) for n in args.sweep.split(",") if n])
    if args.faults:
        bad += run_faults(out)
    print("\nRESULT:", "no difference and no failure" if not bad else f"{bad} differences or failures, listed above",
          "" if compared else "(nothing was compared: no IRSA cutouts found)")
    return 1 if bad or not compared else 0


if __name__ == "__main__":
    sys.exit(main())

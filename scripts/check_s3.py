"""Proof that a cutout read from S3 is the cutout IRSA serves, and how fast it arrives.

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
                    clipped by a detector edge. Targets: Barnard's Star (0.15 and 0.3
                    degrees), RW Aurigae, R Draconis.
  --all             every cached cutout of the chosen sets
  --sets a,b        which sets (see SETS below); "every" for all of them
  --speed           time ranged reads, single cutouts, a one-detector field, the
                    six-detector field and a 0.5 degree field through S3
  --irsa N          also fetch N cutouts through IRSA at 0.15 and at 0.5 degrees (N <= 6),
                    for a same-day time and a check of the box rule at a size the cache
                    does not hold. IRSA is shared and fragile: keep N small.
  --concurrency N   simultaneous S3 requests (default 16)
  --out DIR         where fetched files go (default scripts/out/s3)
"""
import argparse
import hashlib
import io
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
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


def name_of(exp: dict) -> tuple[str, int]:
    return exp["obs_id"], exp["detector"]


def detector_box(header: fits.Header) -> tuple[int, int, int, int]:
    """(x0, x1, y0, y1) of a cutout on the detector, read through its "A" coordinate system."""
    x, y = WCS(header, key="A").wcs_pix2world(0, 0, 0)
    x0, y0 = int(round(float(x))), int(round(float(y)))
    return x0, x0 + header["NAXIS1"], y0, y0 + header["NAXIS2"]


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
        box_a, box_b = detector_box(ha), detector_box(hb)
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
    """A sample spread over detectors and visits, plus cutouts that a detector edge clipped."""
    groups = defaultdict(list)
    for e in exposures:
        groups[(e["detector"], visit[name_of(e)])].append(e)
    picked = []
    for _, group in sorted(groups.items()):
        for i in sorted({round(k * (len(group) - 1) / max(per_visit - 1, 1)) for k in range(per_visit)}):
            picked.append(group[i])
    clipped = []
    for e in exposures:
        with fits.open(cached[name_of(e)]) as hdul:
            x0, x1, y0, y1 = detector_box(hdul["IMAGE"].header)
        if (x0 == 0 or y0 == 0 or x1 == DETECTOR_SIDE or y1 == DETECTOR_SIDE) and e not in picked:
            clipped.append(e)
    step = max(len(clipped) // max(clipped_max, 1), 1)
    return picked + clipped[::step][:clipped_max]


def run_comparison(sets: list[str], out: Path, concurrency: int, everything: bool) -> tuple[int, list[dict]]:
    rows, bad = [], 0
    for key in sets:
        name, ra, dec, size = SETS[key]
        exposures = spherex.find_exposures(ra, dec, max_age_s=float("inf"))
        visit = visits_of(exposures)
        cached = {name_of(e): spherex._cutout_path(e, ra, dec, size) for e in exposures}
        have = [e for e in exposures if cached[name_of(e)].exists()]
        if not have:
            print(f"{name} {size}: no IRSA cutouts in {spherex.CACHE / 'cutouts'}; set SPHEREX_CACHE_DIR")
            continue
        chosen = have if everything else choose(have, cached, visit, per_visit=2, clipped_max=6)
        reader_start = time.perf_counter()
        fetched = s3fetch.fetch_cutouts(chosen, ra, dec, size, out / "compare", max_concurrent=concurrency,
                                        overwrite=True)
        took = time.perf_counter() - reader_start
        print(f"\n{name}, {size} degrees: {len(chosen)} of {len(have)} cached exposures fetched from S3 "
              f"in {took:.1f}s ({concurrency} requests at a time)")
        print(f"  {'exposure':<22}{'det':>3} {'visit':>5}  {'date':<10}  {'IRSA box x0:x1 y0:y1':<22} {'S3 box':<10}"
              f"{'pixels':>7} {'NaN':>4}  IMAGE FLAGS VARIA ZODI  WAVE  BANDW  {'sky off (px)':>12}  hdr  file")
        for e, path, err in fetched:
            label = f"{e['obs_id']}"
            if path is None:
                bad += 1
                print(f"  {label:<22}{e['detector']:>3}  NOT FETCHED: {err}")
                rows.append({"set": key, "target": name, "size": size, "obs_id": e["obs_id"],
                             "detector": e["detector"], "error": err})
                continue
            r = compare(path, cached[name_of(e)])
            b = r["box_irsa"]
            with fits.open(path) as hdul:
                date = str(hdul["IMAGE"].header["DATE-AVG"])[:10]
            cells = "".join(f"{r.get(n, {}).get('bits', '-'):>5} " for n in ARRAYS)
            print(f"  {label:<22}{e['detector']:>3} {visit[name_of(e)]:>5}  {date:<10}  "
                  f"{f'{b[0]}:{b[1]} {b[2]}:{b[3]}':<22} {'same' if r['same_box'] else str(r['box_s3']):<10}"
                  f"{r['pixels']:>7} {r.get('nan_pixels', 0):>4}  {cells} "
                  f"{r.get('sky_offset_px', float('nan')):>12.1e}  "
                  f"{r.get('header_lines', '-'):>3}  {'same' if r['file_identical'] else 'DIFF'}")
            for d in r["differences"]:
                print(f"      DIFFERENCE: {d}")
            bad += bool(r["differences"])
            rows.append({"set": key, "target": name, "size": size, "obs_id": e["obs_id"], "detector": e["detector"],
                         "visit": visit[name_of(e)], "date": date, **r})
    return bad, rows


def summarise(rows: list[dict]) -> None:
    print("\nSummary (differing pixels are counted bit for bit; 'clipped' = cut by a detector edge)")
    print(f"  {'target':<16}{'size':>5} {'det':>3} {'visits':>6} {'exposures':>9} {'clipped':>7} {'pixels':>9} "
          f"{'IMAGE':>6}{'FLAGS':>6}{'VARIA':>6}{'ZODI':>6}{'WAVE':>6}{'BANDW':>6} {'max sky off (px)':>16} "
          f"{'same box':>8} {'hdr lines':>9} {'files identical':>15}")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["target"], r["size"], r["detector"])].append(r)
    total: Counter = Counter()
    for (target, size, det), rs in sorted(groups.items()):
        ok = [r for r in rs if "error" not in r]
        clipped = sum(1 for r in ok if 0 in r["box_irsa"] or DETECTOR_SIDE in r["box_irsa"])
        diffs = [sum(r.get(n, {}).get("bits", 0) for r in ok) for n in ARRAYS]
        pixels = sum(r["pixels"] for r in ok)
        print(f"  {target:<16}{size:>5} {det:>3} {len({r['visit'] for r in ok}):>6} {len(ok):>9} {clipped:>7} "
              f"{pixels:>9} " + "".join(f"{d:>6}" for d in diffs)
              + f" {max((r.get('sky_offset_px', 0.0) for r in ok), default=0.0):>16.1e} "
              f"{sum(r['same_box'] for r in ok):>8} {sum(r.get('header_lines', 0) for r in ok):>9} "
              f"{sum(r['file_identical'] for r in ok):>15}")
        total.update(exposures=len(ok), failed=len(rs) - len(ok), clipped=clipped, pixels=pixels,
                     differing=sum(diffs), same_box=sum(r["same_box"] for r in ok),
                     covers=sum(r["covers"] for r in ok), identical=sum(r["file_identical"] for r in ok),
                     with_differences=sum(bool(r["differences"]) for r in ok))
    print(f"\n  {total['exposures']} exposures compared ({total['clipped']} clipped by a detector edge), "
          f"{total['failed']} not fetched; {total['pixels']} pixels in each of six arrays;")
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
                concurrency: int) -> list[tuple[dict, Path | None, str | None]]:
    start = time.perf_counter()
    results = s3fetch.fetch_cutouts(exposures, ra, dec, size, folder, max_concurrent=concurrency, overwrite=True)
    took = time.perf_counter() - start
    failed = [(e["obs_id"], e["detector"], err) for e, p, err in results if p is None]
    megabytes = sum(p.stat().st_size for _, p, _ in results if p) / 1e6
    print(f"  {label}: {len(results) - len(failed)} cutouts in {took:.1f}s = {took / len(results):.3f}s each, "
          f"{concurrency} requests at a time; {megabytes:.0f} MB written; {len(failed)} failed")
    for f in failed:
        print("    FAILED", f)
    return results


def run_speed(out: Path, concurrency: int, n_irsa: int) -> int:
    name, ra, dec, _ = SETS["barnard"]
    exposures = spherex.find_exposures(ra, dec, max_age_s=float("inf"))
    d5 = [e for e in exposures if e["detector"] == 5]
    bad = 0
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
    with s3fetch.S3Reader(concurrency) as reader:
        times = []
        for e in d5[:8]:
            start = time.perf_counter()
            s3fetch.fetch_cutout(e, ra, dec, 0.15, s3fetch.cutout_path(out / "speed-single", e, ra, dec, 0.15),
                                 reader=reader, overwrite=True)
            times.append(time.perf_counter() - start)
        print(f"  one 0.15 degree cutout, alone: median {statistics.median(times):.2f}s (fastest {min(times):.2f}, "
              f"slowest {max(times):.2f}, 8 exposures; the first includes opening the connections); "
              f"{reader.requests / 8:.0f} requests and {reader.bytes_read / 8e6:.2f} MB per cutout")

    # 3. Whole fields.
    results = timed_field(f"detector 5 at 0.15 degrees ({len(d5)} exposures)", d5, ra, dec, 0.15,
                          out / "speed-d5", concurrency)
    same = sum(1 for e, p, _ in results if p and spherex._cutout_path(e, ra, dec, 0.15).exists()
               and sha(p) == sha(spherex._cutout_path(e, ra, dec, 0.15)))
    print(f"    {same} of {len(results)} files are byte for byte the cached IRSA cutouts")
    bad += same != len(results)
    results = timed_field(f"all six detectors at 0.15 degrees ({len(exposures)} exposures)", exposures, ra, dec,
                          0.15, out / "speed-all", concurrency)
    same = sum(1 for e, p, _ in results if p and spherex._cutout_path(e, ra, dec, 0.15).exists()
               and sha(p) == sha(spherex._cutout_path(e, ra, dec, 0.15)))
    print(f"    {same} of {len(results)} files are byte for byte the cached IRSA cutouts")
    bad += same != len(results)
    wide = timed_field(f"detector 5 at 0.5 degrees ({len(d5)} exposures)", d5, ra, dec, 0.5, out / "speed-wide",
                       concurrency)
    # No IRSA cutout of 0.5 degrees is cached, but the 0.3 and 0.15 degree ones are inside it.
    for inner in (0.3, 0.15):
        n = pixels = differing = 0
        for e, p, _ in wide:
            theirs = spherex._cutout_path(e, ra, dec, inner)
            if p and theirs.exists():
                r = compare(p, theirs)
                n += 1
                pixels += r["pixels"]
                differing += sum(r.get(a, {}).get("bits", 0) for a in ARRAYS) + (r.get("sky_offset_px", 0) > 0)
                for d in r["differences"]:
                    if not d.startswith("the S3 box"):
                        print(f"    DIFFERENCE {e['obs_id']} D{e['detector']} against the {inner} degree cutout: {d}")
        print(f"    against the cached {inner} degree IRSA cutouts of the same exposures: {n} compared, "
              f"{pixels} shared pixels in each of six arrays, {differing} differ")
        bad += bool(differing)

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sets", default=DEFAULT_SETS)
    parser.add_argument("--speed", action="store_true")
    parser.add_argument("--irsa", type=int, default=0)
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

    bad, rows = run_comparison(sets, out, args.concurrency, args.all)
    if rows:
        summarise(rows)
        (out / "comparison.json").write_text(json.dumps(rows, indent=1))
    if args.speed:
        bad += run_speed(out, args.concurrency, args.irsa)
    print("\nRESULT:", "no difference found" if not bad else f"{bad} exposures or checks with a difference or failure")
    return 1 if bad or not rows else 0


if __name__ == "__main__":
    sys.exit(main())

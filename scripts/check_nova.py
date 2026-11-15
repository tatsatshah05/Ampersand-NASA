"""Measure a nova in SPHEREx and try to break the result: python scripts/check_nova.py RA DEC --name NAME --max-jd JD

    python scripts/check_nova.py 156.30783 -53.52200 --name "V572 Vel" --max-jd 2460854.4 --out docs/novae
    python scripts/check_nova.py 156.30783 -53.52200 --name "V572 Vel" --max-jd 2460854.4 --offline   # no network

What it does, in order (each section prints its numbers):
 1. The measurement itself: backend/photometry.lightcurve, one point per exposure (the code behind the
    app's brightness chart), grouped into runs of dates (a gap of more than 10 days, or the day 10 days
    before maximum, starts a new run) and six wavelength bands (the six detectors).
 2. Like with like: the same wavelength channels on two dates, never two different colours.
 3. Saturation: which readings carry an OVERFLOW flag (a valid but partial reading, see backend/photometry.py),
    what the readings without it say, and whether the ring of unsaturated pixels around the object (the
    "wing") agrees with the core where the core is the only measurement.
 4. What else is inside the measuring circle: Gaia (from the measurement), 2MASS, AllWISE, CatWISE.
 5. Field stars measured in the same exposures with the same code: was the instrument steady?
 6. AAVSO optical magnitudes: is there a dip (dust forming in front of the nova)?
 7. The continuum: temperature of the excess with an error and how it depends on the choices made,
    against a power law.
 8. Emission-line candidates: channels far above their neighbours, with the nearest known lines.
Then it draws the pictures (--out): brightness against time, spectra of the runs, a map of what was
saturated, and the optical light curve. Saturated exposures are drawn as such, never given a value.

Everything is measured from the public archive: nothing is simulated or filled in. The network is used
for the SPHEREx cutouts (once, then cached), Gaia, IRSA catalogues and AAVSO; `--offline` skips 4 to 6
and uses the cache only. Needs SPHEREX_CACHE_DIR to point at the shared cache for speed.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from astropy.table import Table
from astropy.time import Time
from scipy.optimize import curve_fit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_common as vc  # noqa: E402
import verify_plot as vp  # noqa: E402

from backend import astrometry, photometry, pipeline, spherex  # noqa: E402

GATOR = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
RUN_GAP_DAYS = 10.0
SPLIT_BEFORE_MAX_DAYS = 10.0      # exposures earlier than this before maximum count as "before the eruption"
ZERO_JY = {"J": 1594.0, "H": 1024.0, "K": 666.7, "W1": 309.540, "W2": 171.787}   # 2MASS (Cohen+03), WISE (IV.4.h)
BAND_EDGES = {1: (0.75, 1.12), 2: (1.10, 1.65), 3: (1.63, 2.43), 4: (2.40, 3.85), 5: (3.81, 4.43), 6: (4.41, 5.01)}
LINE_NSIGMA = 5.0
LINE_FLOOR = 0.05                 # the scatter of neighbours is never taken as smaller than this share of them
LINE_MIN_RATIO = 1.25             # and a line stands at least this many times above the continuum
MIN_FIT_POINTS = 8

# Wavelengths in micrometres (vacuum). H I, He I/II, and the lines usually seen in novae at 0.7 to 5 micrometres.
LINES = [
    ("O I 0.7774", 0.7774), ("O I 0.8446", 0.8446), ("Ca II 0.8542", 0.8542), ("Pa-eta 0.9015", 0.9015),
    ("Pa-zeta 0.9229", 0.9229), ("Pa-epsilon 0.9546", 0.9546),
    ("[S VIII] 0.9915", 0.9915), ("Pa-delta 1.0049", 1.0049), ("He II 1.0124", 1.0124),
    ("Pa-gamma 1.0941", 1.0941), ("He I 1.0830", 1.0830), ("[Fe XIII] 1.0747", 1.0747),
    ("O I 1.1287", 1.1287), ("[S IX] 1.2523", 1.2523), ("Pa-beta 1.2822", 1.2822), ("O I 1.3164", 1.3164),
    ("[Si X] 1.4300", 1.4300), ("Br-12 1.6407", 1.6407), ("Br-11 1.6811", 1.6811), ("Br-10 1.7367", 1.7367),
    ("Pa-alpha 1.8751", 1.8751), ("Br-delta 1.9451", 1.9451), ("[Si VI] 1.9641", 1.9641),
    ("He I 2.0587", 2.0587), ("[Al IX] 2.0443", 2.0443), ("Br-gamma 2.1655", 2.1655), ("He II 2.1891", 2.1891),
    ("[Ca VIII] 2.3220", 2.3220), ("CO 2.2935 (band head)", 2.2935), ("[Si VII] 2.4807", 2.4807),
    ("Br-beta 2.6252", 2.6252), ("Pf-delta 3.2970", 3.2970), ("Pf-gamma 3.7395", 3.7395),
    ("Br-alpha 4.0523", 4.0523), ("[Mg IV] 4.4870", 4.4870), ("[Ar VI] 4.5290", 4.5290),
    ("Pf-beta 4.6538", 4.6538), ("CO fundamental 4.65", 4.65), ("[Ar VI] 4.5290", 4.5290),
]
BAND_COLOURS = {"0.75 to 1.8 micrometres": vp.BLUE, "2.0 to 3.0": vp.GREEN, "3.8 to 4.4": vp.ORANGE,
                "4.4 to 5.0": vp.RED}


# ---------------------------------------------------------------------------------------------------------
# 1. the measurement, runs, tables
# ---------------------------------------------------------------------------------------------------------
def flatten(curve: dict) -> list[dict]:
    """Every exposure of the light curve as one list; each point gets its detector and channel (bin) key."""
    out = []
    for b in curve["bins"]:
        for p in b["points"]:
            out.append({**p, "key": (b["detector"], p["channel"])})
    return out


def make_runs(points: list[dict], split_mjd: float) -> list[dict]:
    """Number the runs of dates in each point's 'run' and describe them."""
    prev = None
    run = -1
    for p in sorted(points, key=lambda q: q["mjd"]):
        if prev is None or p["mjd"] - prev > RUN_GAP_DAYS or prev < split_mjd <= p["mjd"]:
            run += 1
        p["run"] = run
        prev = p["mjd"]
    runs = []
    for r in range(run + 1):
        mem = [p for p in points if p["run"] == r]
        runs.append({"id": r, "start": min(p["mjd"] for p in mem), "end": max(p["mjd"] for p in mem),
                     "n": len(mem), "n_ok": sum(p["status"] == "ok" for p in mem)})
    return runs


def day(mjd: float) -> str:
    return Time(mjd, format="mjd").iso[:10]


def band_of(wavelength: float | None) -> int | None:
    if wavelength is None:
        return None
    for det, (lo, hi) in BAND_EDGES.items():
        if lo <= wavelength < hi:
            return det
    return None


def run_label(r: dict, max_mjd: float) -> str:
    a, b = (r["start"] - max_mjd), (r["end"] - max_mjd)
    return f"run {r['id']}: {day(r['start'])} to {day(r['end'])} (day {a:+.0f} to {b:+.0f} from maximum)"


def print_runs(points: list[dict], runs: list[dict], max_mjd: float) -> None:
    print("\n1. THE MEASUREMENT, by run of dates and detector (wavelength band)")
    print("   ok = a brightness; ok-OF = of those, with at least one OVERFLOW pixel in the circle (a partial "
          "reading, valid per the Supplement);\n   sat = saturated, no brightness; other = flagged, off the image, no "
          "sky. mJy columns are over the ok readings.")
    for r in runs:
        print(f"\n  {run_label(r, max_mjd)}")
        print(f"    {'det':>3} {'um':>11} {'n':>3} {'ok':>3} {'ok-OF':>5} {'sat':>3} {'other':>5}  "
              f"{'min':>7} {'median':>7} {'max':>7} (mJy)")
        for det in range(1, 7):
            mem = [p for p in points if p["run"] == r["id"] and p["detector"] == det]
            if not mem:
                continue
            ok = [p for p in mem if p["status"] == "ok"]
            flux = [p["flux_mjy"] for p in ok]
            wl = [p["wavelength_um"] for p in mem if p["wavelength_um"]]
            span = f"{min(wl):.2f}-{max(wl):.2f}" if wl else "-"
            of = sum(p["overflow_pixels"] > 0 for p in ok)
            sat = sum(p["status"] == "saturated" for p in mem)
            dash = f"{'-':>7}"
            nums = f"{min(flux):7.1f} {np.median(flux):7.1f} {max(flux):7.1f}" if flux else f"{dash} {dash} {dash}"
            print(f"    {det:>3} {span:>11} {len(mem):3d} {len(ok):3d} {of:5d} {sat:3d} {len(mem) - len(ok) - sat:5d}  "
                  f"{nums}")


# ---------------------------------------------------------------------------------------------------------
# 2. like with like
# ---------------------------------------------------------------------------------------------------------
def channel_table(points: list[dict], select) -> dict[tuple, dict]:
    """Per channel: median flux of the ok readings that `select` accepts, the wavelength and the dates."""
    group: dict[tuple, list[dict]] = defaultdict(list)
    for p in points:
        if p["status"] == "ok" and p["wavelength_um"] is not None and select(p):
            group[p["key"]].append(p)
    return {k: {"flux": float(np.median([p["flux_mjy"] for p in v])), "n": len(v),
                "wave": float(np.median([p["wavelength_um"] for p in v])),
                "mjd": float(np.mean([p["mjd"] for p in v])),
                "err": float(np.median([p["flux_err_mjy"] for p in v])),
                "overflow": any(p["overflow_pixels"] > 0 for p in v)} for k, v in group.items()}


def compare(points: list[dict], name_a: str, sel_a, name_b: str, sel_b, max_mjd: float, verbose: bool) -> list[dict]:
    a, b = channel_table(points, sel_a), channel_table(points, sel_b)
    rows = []
    for k in sorted(set(a) & set(b), key=lambda k: a[k]["wave"]):
        rows.append({"key": k, "wave": a[k]["wave"], "a": a[k]["flux"], "b": b[k]["flux"],
                     "ratio": b[k]["flux"] / a[k]["flux"],
                     "day_a": a[k]["mjd"] - max_mjd, "day_b": b[k]["mjd"] - max_mjd,
                     "of": a[k]["overflow"] or b[k]["overflow"], "err": float(np.hypot(a[k]["err"] / a[k]["flux"],
                                                                                       b[k]["err"] / b[k]["flux"]))})
    print(f"\n  {name_b} divided by {name_a}, {len(rows)} channels measured on both (same detector and channel)")
    if verbose:
        print(f"    {'um':>6} {'det':>3} {name_a[:10]:>10} {name_b[:10]:>10} {'ratio':>6} {'days':>13}  note")
        for r in rows:
            print(f"    {r['wave']:6.3f} {r['key'][0]:3d} {r['a']:10.1f} {r['b']:10.1f} {r['ratio']:6.2f} "
                  f"{r['day_a']:+6.0f}{r['day_b']:+6.0f}  {'overflow' if r['of'] else ''}")
    for det in range(1, 7):
        sub = [r["ratio"] for r in rows if r["key"][0] == det]
        if sub:
            lo, hi = np.percentile(sub, [16, 84])
            print(f"    detector {det}: {len(sub):2d} channels, median ratio {np.median(sub):.2f} "
                  f"(16 to 84 per cent: {lo:.2f} to {hi:.2f})")
    return rows


# ---------------------------------------------------------------------------------------------------------
# 3. saturation
# ---------------------------------------------------------------------------------------------------------
def saturation_check(points: list[dict], runs: list[dict], max_mjd: float) -> None:
    print("\n3. SATURATION: are the readings biased by being close to the level where others saturate?")
    for r in runs:
        mem = [p for p in points if p["run"] == r["id"] and p["status"] in ("ok", "saturated")]
        if sum(p["status"] == "ok" for p in mem) < 10:
            continue
        print(f"\n  {run_label(r, max_mjd)}")
        for det in range(1, 7):
            d = [p for p in mem if p["detector"] == det]
            ok = [p for p in d if p["status"] == "ok"]
            if not d:
                continue
            clean = [p["flux_mjy"] for p in ok if p["overflow_pixels"] == 0]
            part = [p["flux_mjy"] for p in ok if p["overflow_pixels"] > 0]
            text = (f"no-overflow readings {len(clean)}"
                    + (f" (median {np.median(clean):.0f}, max {max(clean):.0f} mJy)"
                                                           if clean else ""))
            text += f"; partial (OVERFLOW) readings {len(part)}" + (f" (median {np.median(part):.0f}, max "
                                                                     f"{max(part):.0f} mJy)" if part else "")
            text += f"; saturated {sum(p['status'] == 'saturated' for p in d)}"
            print(f"    detector {det}: {text}")
    # The ring of unsaturated pixels (the wing) against the core, detectors 5 and 6 only (backend: trusted there).
    print("\n  Wing against core, in the last run, in channels with both on two dates 10 or more days apart "
          "(detectors 5 and 6, the only ones where the wing repeats). If the core readings, which all carry an "
          "OVERFLOW pixel there, are right, the core and the wing must change by the same factor:")
    change_core, change_wing = [], []
    last_id = runs[-1]["id"] if runs else -1
    for det in (5, 6):
        by_key: dict[tuple, list[dict]] = defaultdict(list)
        for p in points:
            if (p["detector"] == det and p["status"] == "ok" and p["wing_status"] == "ok" and p["wing_trusted"]
                    and p["run"] == last_id):
                by_key[p["key"]].append(p)
        for _k, v in by_key.items():
            v.sort(key=lambda p: p["mjd"])
            if v[-1]["mjd"] - v[0]["mjd"] >= 10 and v[0]["wing_mjy"] > 0 and v[-1]["wing_mjy"] > 0:
                change_core.append(v[-1]["flux_mjy"] / v[0]["flux_mjy"])
                change_wing.append(v[-1]["wing_mjy"] / v[0]["wing_mjy"])
    if change_core:
        c, w = np.array(change_core), np.array(change_wing)
        print(f"    {len(c)} channels: later/earlier core brightness median {np.median(c):.2f}; the same from the wing "
              f"ring median {np.median(w):.2f}; ratio core/wing per channel median {np.median(c / w):.2f} "
              f"(16 to 84 per cent {np.percentile(c / w, 16):.2f} to {np.percentile(c / w, 84):.2f})")
    else:
        print("    no channel qualifies")


# ---------------------------------------------------------------------------------------------------------
# 4. catalogues
# ---------------------------------------------------------------------------------------------------------
def gator(catalog: str, ra: float, dec: float, columns: str, radius: float = 40.0) -> Table | None:
    cache = spherex.CACHE / "queries" / f"gator_{catalog}_{ra:.5f}_{dec:.5f}_{radius:g}.tbl"
    if not cache.exists():
        try:
            raw = spherex.http_get(GATOR, {"catalog": catalog, "spatial": "cone", "objstr": f"{ra} {dec}",
                                           "radius": radius, "radunits": "arcsec", "outfmt": 1, "selcols": columns},
                                   tries=5, timeout=120)
        except Exception as e:  # noqa: BLE001 - the check is reported as not done
            print(f"    {catalog}: IRSA did not answer ({type(e).__name__}); this check was not done")
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    try:
        return Table.read(io.BytesIO(cache.read_bytes()), format="ipac")
    except Exception:  # noqa: BLE001
        return None


def mjy(mag: float, band: str) -> float:
    return ZERO_JY[band] * 1000.0 * 10 ** (-0.4 * mag)


def catalogue_check(ra: float, dec: float, curve: dict) -> None:
    print("\n4. WHAT ELSE IS IN THE MEASURING CIRCLE (radius 15.4 arcsec)")
    circle = curve["stars_in_circle"]
    print(f"  Gaia DR3 stars brighter than G = 17 inside the circle: "
          f"{len(circle['stars']) if circle['known'] else 'Gaia did not answer'}"
          + ("".join(f"; G={s['gmag']:.1f} at {s['nearest_arcsec']:.1f} arcsec" for s in circle["stars"])
             if circle["known"] else ""))
    sources = [("2MASS", "fp_psc", "designation,ra,dec,j_m,h_m,k_m", ("J", "H", "K"), ("j_m", "h_m", "k_m")),
               ("AllWISE", "allwise_p3as_psd", "designation,ra,dec,w1mpro,w2mpro", ("W1", "W2"), ("w1mpro", "w2mpro")),
               ("CatWISE2020", "catwise_2020", "source_name,ra,dec,w1mpro,w2mpro", ("W1", "W2"), ("w1mpro", "w2mpro"))]
    for label, cat, cols, bands, colnames in sources:
        table = gator(cat, ra, dec, cols)
        if table is None:
            continue
        inside = []
        for row in table:
            e, n = astrometry.offset_arcsec(ra, dec, float(row["ra"]), float(row["dec"]))
            if np.hypot(e, n) < photometry.CIRCLE_ARCSEC:
                inside.append((float(np.hypot(e, n)), row))
        text = f"  {label}: {len(inside)} source(s) inside the circle"
        for band, col in zip(bands, colnames, strict=True):
            tot = sum(mjy(float(r[col]), band) for _, r in inside if not np.ma.is_masked(r[col]))
            text += f"; summed {band} {tot:.2f} mJy" if inside else ""
        print(text)
        for dist, row in sorted(inside, key=lambda t: t[0])[:4]:
            mags = ", ".join(f"{c}={float(row[c]):.2f}" for c in colnames if not np.ma.is_masked(row[c]))
            print(f"      {dist:4.1f} arcsec: {mags}")


# ---------------------------------------------------------------------------------------------------------
# 5. field stars in the same exposures
# ---------------------------------------------------------------------------------------------------------
def field_stars(ra: float, dec: float, curve: dict) -> list[dict]:
    """Isolated Gaia stars (G 10 to 15.5, within 125 arcsec, no other G<17 star within 16 arcsec) measured with
    the same code in the same exposures. Cached as JSON."""
    cache = spherex.CACHE / "queries" / f"novae_field_stars_{ra:.5f}_{dec:.5f}_v{photometry.VERSION}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    cone = astrometry.gaia_cone(ra, dec, 0.135)
    mjd0 = Time(2026.0, format="jyear").mjd
    placed = [(s, *astrometry.position_at(s, mjd0, parallax=False)) for s in cone]
    chosen = []
    for s, r, d in placed:
        e, n = astrometry.offset_arcsec(ra, dec, r, d)
        dist = float(np.hypot(e, n))
        if not (dist < 125 and 10 < s["gmag"] < 15.5):
            continue
        isolated = all(np.hypot(*astrometry.offset_arcsec(r, d, r2, d2)) >= 16 or o is s or o["gmag"] >= 17
                       for o, r2, d2 in placed)
        if isolated:
            chosen.append((s, dist))
    exposures = spherex.find_exposures(ra, dec)
    epoch_of = pipeline.assign_epochs(exposures)
    fetched = spherex.fetch_cutouts(exposures, ra, dec, photometry.CUTOUT_DEG)
    out = []
    for s, dist in chosen:
        pts = []
        for (exp, path, _err), _ep in zip(fetched, epoch_of, strict=True):
            if path is None:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tr, td = astrometry.position_at({**s, "ref_epoch": astrometry.GAIA_EPOCH}, exp["mjd"])
                p = photometry.measure(path, float(tr), float(td))
            p.pop("wings", None)
            lo, hi = curve["detector_ranges_um"][str(exp["detector"])]
            ch = None
            if p["wavelength_um"] is not None:
                edges = photometry.channel_edges(lo, hi)
                top = photometry.CHANNELS_PER_DETECTOR - 1
                ch = int(np.clip(np.searchsorted(edges, p["wavelength_um"]) - 1, 0, top))
            pts.append({"detector": exp["detector"], "channel": ch, "mjd": p["mjd"], "status": p["status"],
                        "wavelength_um": p["wavelength_um"], "flux_mjy": p["flux_mjy"],
                        "flux_err_mjy": p["flux_err_mjy"]})
        out.append({"source_id": s["source_id"], "gmag": s["gmag"], "distance_arcsec": dist, "points": pts})
    spherex.write_json(cache, out)
    return out


def field_star_check(ra: float, dec: float, curve: dict, windows: list[tuple[str, float, float]],
                     min_dist: float) -> None:
    print("\n5. FIELD STARS in the same exposures (Gaia stars of the field, isolated, measured with the same code)")
    stars = field_stars(ra, dec, curve)
    if not stars:
        print("  no isolated Gaia star (G 10 to 15.5, nothing else brighter than G = 17 within 16 arcsec) within "
              "125 arcsec: this check cannot be made in this field")
        return
    print(f"  {len(stars)} stars,G = {min(s['gmag'] for s in stars):.1f} to {max(s['gmag'] for s in stars):.1f}, "
          f"{min(s['distance_arcsec'] for s in stars):.0f} to {max(s['distance_arcsec'] for s in stars):.0f} arcsec "
          "from the object. Same channel on two windows, readings with signal to noise above 10 only.")

    def table(star: dict, lo: float, hi: float) -> dict:
        g: dict[tuple, list[float]] = defaultdict(list)
        for p in star["points"]:
            if (p["status"] == "ok" and p["wavelength_um"] is not None and lo <= p["mjd"] < hi
                    and p["flux_mjy"] / p["flux_err_mjy"] > 10):
                g[(p["detector"], p["channel"])].append(p["flux_mjy"])
        return {k: float(np.median(v)) for k, v in g.items()}

    for i in range(len(windows) - 1):
        (na, a0, a1), (nb, b0, b1) = windows[i], windows[i + 1]
        print(f"\n  {nb} divided by {na}:")
        for det in range(1, 7):
            per_star, near = [], []
            for s in stars:
                ta, tb = table(s, a0, a1), table(s, b0, b1)
                rr = [tb[k] / ta[k] for k in ta if k in tb and k[0] == det]
                if rr:
                    (per_star if s["distance_arcsec"] >= min_dist else near).append(float(np.median(rr)))
            if per_star:
                print(f"    detector {det}: {len(per_star):2d} stars at {min_dist:.0f} arcsec or more: median ratio "
                      f"{np.median(per_star):.2f}, range {min(per_star):.2f} to {max(per_star):.2f}"
                      + (f"; {len(near)} nearer stars: median {np.median(near):.2f}" if near else ""))
    # light of the nova itself (its halo) in nearer stars, long wavelengths only
    print("\n  Stars nearer the nova in detectors 4 to 6 pick up some of the nova's own halo while it is bright "
          "(flux in each window minus the same star's flux in the faintest window, same channels, mJy):")
    base = windows[0]
    for nb, b0, b1 in windows[1:]:
        rows = []
        for s in sorted(stars, key=lambda s: s["distance_arcsec"]):
            def tab(lo: float, hi: float, s=s) -> dict:
                g: dict[tuple, list[float]] = defaultdict(list)
                for p in s["points"]:
                    if (p["status"] == "ok" and p["wavelength_um"] is not None and p["detector"] >= 4
                            and lo <= p["mjd"] < hi):
                        g[(p["detector"], p["channel"])].append(p["flux_mjy"])
                return {k: float(np.median(v)) for k, v in g.items()}
            ta, tb = tab(base[1], base[2]), tab(b0, b1)
            diff = [tb[k] - ta[k] for k in ta if k in tb]
            if len(diff) >= 3:
                rows.append((s["distance_arcsec"], float(np.median(diff))))
        if rows:
            print(f"    {nb}: " + ", ".join(f"{d:.0f}\":{x:+.1f}" for d, x in rows))


# ---------------------------------------------------------------------------------------------------------
# 6. AAVSO
# ---------------------------------------------------------------------------------------------------------
def aavso_check(aavso_name: str, max_jd: float) -> list[dict] | None:
    print(f"\n6. AAVSO OPTICAL LIGHT CURVE of {aavso_name} (observations of the community, fetched from AAVSO)")
    folder = spherex.CACHE / "queries"      # the raw answer is several MB: kept in the cache, not in docs/
    rows = vc.aavso(aavso_name, max_jd - 30.0, max_jd + 520.0, folder / f"aavso_{aavso_name.replace(' ', '_')}.txt")
    if rows is None:
        print("  AAVSO did not answer: no optical comparison was made")
        return None
    rows = [r for r in rows if not r["fainter_than"]]
    print(f"  {len(rows)} observations (upper limits left out)")
    for band in ("V", "R", "I"):
        g: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            if r["band"] == band:
                g[int((r["jd"] - max_jd) // 10)].append(r["mag"])
        series = []
        for k in sorted(g):
            m = np.array(g[k])
            m = m[np.abs(m - np.median(m)) < 3]
            if len(m):
                series.append((10 * k + 5, float(np.median(m)), len(m)))
        if len(series) < 5:
            continue
        late = [s for s in series if s[0] > 15]
        faint = max(late, key=lambda s: s[1])
        after = [s for s in late if s[0] > faint[0]]
        bright = min(after, key=lambda s: s[1]) if after else None
        print(f"  {band}: {len(series)} ten-day medians. Faintest {faint[1]:.1f} mag around day {faint[0]:+d}"
              + (f"; afterwards back to {bright[1]:.1f} around day {bright[0]:+d} ({faint[1] - bright[1]:.1f} mag "
                 "brighter again)" if bright else "") + ".")
        gaps = [(a[0], b[0]) for a, b in zip(series, series[1:], strict=False) if b[0] - a[0] > 30]
        if gaps:
            print(f"     no observations between days {', '.join(f'{a:+d} and {b:+d}' for a, b in gaps)}")
        if band == "V":
            print("     V medians (day: mag): " + ", ".join(f"{d:+d}: {m:.1f}" for d, m, _ in series[::2]))
    return rows


def optical_vs_spherex(rows: list[dict], points: list[dict], runs: list[dict], max_mjd: float) -> None:
    """SPHEREx at 0.75 to 0.95 micrometres against AAVSO's I band (0.8 micrometres, zero point 2416 Jy) in each run."""
    print("  SPHEREx 0.75 to 0.95 micrometres against AAVSO I band (zero point 2416 Jy; roughly the same colour, "
          "different apertures):")
    for r in runs:
        s = [p["flux_mjy"] for p in points if p["run"] == r["id"] and p["status"] == "ok" and p["wavelength_um"]
             and p["wavelength_um"] < 0.95]
        i = [x["mag"] for x in rows if x["band"] == "I" and r["start"] <= x["mjd"] <= r["end"]]
        if len(s) >= 2 and len(i) >= 3:
            mj = 2416000.0 * 10 ** (-0.4 * float(np.median(i)))
            print(f"    day {r['start'] - max_mjd:+.0f} to {r['end'] - max_mjd:+.0f}: SPHEREx {np.median(s):.0f} mJy "
                  f"({len(s)} readings); AAVSO I = {np.median(i):.2f} ({len(i)} obs) = {mj:.0f} mJy; "
                  f"SPHEREx / AAVSO = {np.median(s) / mj:.2f}")


# ---------------------------------------------------------------------------------------------------------
# 7. continuum
# ---------------------------------------------------------------------------------------------------------
def planck(lam: np.ndarray, temp: float) -> np.ndarray:
    """Blackbody brightness per unit frequency, up to a constant, at wavelength lam (micrometres)."""
    return lam ** -3 / np.expm1(14387.77 / (lam * temp))


def fit_blackbody(lam: np.ndarray, flux: np.ndarray, err: np.ndarray) -> tuple[float, float, float] | None:
    """Temperature, its 1-sigma error and the reduced chi-squared of S * planck(lam, T)."""
    if len(lam) < MIN_FIT_POINTS:
        return None
    best = None
    for t0 in (300.0, 600.0, 1000.0, 2000.0):
        def model(x: np.ndarray, log_s: float, temp: float) -> np.ndarray:
            return np.exp(log_s) * planck(x, temp)
        try:
            guess = np.log(np.median(flux) / planck(np.median(lam), t0))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt, pcov = curve_fit(model, lam, flux, p0=[guess, t0], sigma=err, absolute_sigma=True,
                                       bounds=([-50, 100], [50, 6000]), maxfev=5000)
        except (RuntimeError, ValueError):
            continue
        chi = float(np.sum(((flux - model(lam, *popt)) / err) ** 2) / (len(lam) - 2))
        if best is None or chi < best[2]:
            best = (float(popt[1]), float(np.sqrt(pcov[1, 1])), chi)
    return best


def fit_powerlaw(lam: np.ndarray, flux: np.ndarray, err: np.ndarray) -> tuple[float, float, float] | None:
    if len(lam) < MIN_FIT_POINTS:
        return None
    w = err / flux
    coef, cov = np.polyfit(np.log(lam), np.log(flux), 1, w=1 / w, cov="unscaled")
    model = np.exp(np.polyval(coef, np.log(lam)))
    chi = float(np.sum(((flux - model) / err) ** 2) / (len(lam) - 2))
    return float(coef[0]), float(np.sqrt(cov[0, 0])), chi


def continuum_points(points: list[dict], lines: list[dict], run: int, day_lo: float | None = None,
                     day_hi: float | None = None, max_mjd: float = 0.0) -> list[dict]:
    """Readings of one run that are not in a line candidate (any channel within a line's channels)."""
    skip = {(f["detector"], c) for f in lines for c in f["channels"]}
    out = []
    for p in points:
        if (p["run"] == run and p["status"] == "ok" and p["wavelength_um"] is not None
                and (p["detector"], p["channel"]) not in skip):
            d = p["mjd"] - max_mjd
            if (day_lo is None or d >= day_lo) and (day_hi is None or d <= day_hi):
                out.append(p)
    return out


def temperature_check(points: list[dict], run: int, lines: list[dict], max_mjd: float, label: str) -> dict | None:
    print(f"\n7. CONTINUUM of {label}: a blackbody (warm dust) fitted to the channels that are not line candidates")
    cont = continuum_points(points, lines, run, max_mjd=max_mjd)
    if len(cont) < 20:
        print("  too few readings")
        return None
    lam = np.array([p["wavelength_um"] for p in cont])
    flux = np.array([p["flux_mjy"] for p in cont])
    err = np.hypot(np.array([p["flux_err_mjy"] for p in cont]), 0.05 * flux)   # 5 per cent: bandpass, fading
    days = np.array([p["mjd"] - max_mjd for p in cont])
    short = (lam >= 1.0) & (lam < 1.8)
    level = float(np.median(flux[short])) if short.sum() >= 3 else 0.0
    print(f"  {len(cont)} continuum readings, days {days.min():+.0f} to {days.max():+.0f}; level at 1.0 to 1.8 "
          f"micrometres {level:.1f} mJy ({short.sum()} readings). Errors include 5 per cent for bandpass and "
          "fading within the run.")
    variants = {
        "A: no subtraction, 2.0 to 5.0 um": (lam >= 2.0, flux, err),
        "B: subtract the short-wavelength level (constant), 2.0 to 5.0 um": (lam >= 2.0, flux - level, err),
        "C: subtract it as a hot star's tail (lambda^-2), 2.0 to 5.0 um": (lam >= 2.0,
                                                                         flux - level * (1.5 / lam) ** 2, err),
        "D: no subtraction, 3.8 to 5.0 um only": (lam >= 3.8, flux, err),
        "E: subtract the level (constant), 3.0 to 5.0 um": (lam >= 3.0, flux - level, err),
    }
    result: dict = {"level_mjy": level, "variants": {}}
    temps = []
    for name, (sel, f, e) in variants.items():
        good = sel & (f > 0)
        bb = fit_blackbody(lam[good], f[good], e[good])
        pl = fit_powerlaw(lam[good], f[good], e[good])
        if bb is None or pl is None:
            print(f"  {name}: too few readings")
            continue
        temps.append(bb[0])
        scaled = bb[1] * max(1.0, np.sqrt(bb[2]))      # error as if the misfit were noise
        print(f"  {name}: {good.sum()} readings; blackbody T = {bb[0]:.0f} +- {scaled:.0f} K (formal {bb[1]:.0f}; "
              f"reduced chi2 {bb[2]:.1f}); power law index {pl[0]:+.2f} +- {pl[1] * max(1.0, np.sqrt(pl[2])):.2f} "
              f"(reduced chi2 {pl[2]:.1f})")
        result["variants"][name] = {"T": bb[0], "T_err": scaled, "chi2_bb": bb[2], "alpha": pl[0], "chi2_pl": pl[2]}
    if temps:
        print(f"  Temperature across the choices above: {min(temps):.0f} to {max(temps):.0f} K")
        result["T_range"] = (min(temps), max(temps))
    # The same, using only the first and last third of the dates in the run, because the nova fades during a run.
    cut = np.percentile(days, [33, 67])
    for name, sel_t in (("earlier third of the run", days <= cut[0]), ("later third of the run", days >= cut[1])):
        good = (lam >= 2.0) & sel_t & (flux - level > 0)
        bb = fit_blackbody(lam[good], (flux - level)[good], err[good])
        if bb:
            print(f"  B, {name} (days {days[sel_t].min():+.0f} to {days[sel_t].max():+.0f}, {good.sum()} readings): "
                  f"T = {bb[0]:.0f} +- {bb[1] * max(1.0, np.sqrt(bb[2])):.0f} K (reduced chi2 {bb[2]:.1f})")
    return result


# ---------------------------------------------------------------------------------------------------------
# 8. lines
# ---------------------------------------------------------------------------------------------------------
def find_features(points: list[dict], run: int) -> list[dict]:
    """Channels of one run standing LINE_NSIGMA times the scatter of their neighbours above them."""
    ok = [p for p in points if p["run"] == run and p["status"] == "ok" and p["wavelength_um"] is not None]
    flagged = []
    for p in ok:
        near = [q for q in ok if q["detector"] == p["detector"] and q is not p
                and 0.008 < abs(q["wavelength_um"] / p["wavelength_um"] - 1) < 0.07]
        if len(near) < 2:
            continue
        f = np.array([q["flux_mjy"] for q in near])
        cont = float(np.median(f))
        # Scatter from the neighbours at or below the median only, so that other lines nearby do not widen it.
        low = f[f <= cont]
        scatter = max(1.4826 * float(np.median(cont - low)), LINE_FLOOR * cont,
                      float(np.median([q["flux_err_mjy"] for q in near])))
        if cont > 0 and p["flux_mjy"] > cont + LINE_NSIGMA * scatter and p["flux_mjy"] > LINE_MIN_RATIO * cont:
            flagged.append({**p, "cont": cont, "scatter": scatter, "nsig": (p["flux_mjy"] - cont) / scatter})
    flagged.sort(key=lambda p: (p["detector"], p["wavelength_um"]))
    features: list[dict] = []
    for p in flagged:
        lo, hi = BAND_EDGES_RANGE[p["detector"]]
        width = (hi / lo) ** (1 / photometry.CHANNELS_PER_DETECTOR) - 1
        last = features[-1] if features else None
        if last and last["detector"] == p["detector"] and p["wavelength_um"] / last["last_wave"] - 1 < 2.2 * width:
            last["points"].append(p)
            last["last_wave"] = p["wavelength_um"]
        else:
            features.append({"detector": p["detector"], "points": [p], "last_wave": p["wavelength_um"]})
    out = []
    for f in features:
        pts = f["points"]
        peak = max(pts, key=lambda p: p["flux_mjy"])
        channels = sorted({p["channel"] for p in pts})
        days_seen = sorted({p["date"][:10] for p in pts})
        bw = peak["bandwidth_um"] or 0.03 * peak["wavelength_um"]
        cands = sorted(((abs(w - peak["wavelength_um"]), n) for n, w in LINES), key=lambda t: t[0])
        names = [f"{n} ({peak['wavelength_um'] - 0 - w:+.3f})" for d, n in cands[:2] for w in [dict(LINES)[n]]
                 if d < 1.0 * bw]
        out.append({"detector": f["detector"], "wave": peak["wavelength_um"],
                    "wave_lo": min(p["wavelength_um"] for p in pts),
                    "wave_hi": max(p["wavelength_um"] for p in pts), "flux": peak["flux_mjy"], "cont": peak["cont"],
                    "nsig": max(p["nsig"] for p in pts), "n_points": len(pts), "channels": channels,
                    "days": days_seen, "ids": names, "overflow": any(p["overflow_pixels"] > 0 for p in pts),
                    "firm": len(channels) >= 2 and len(days_seen) >= 2})
    return out


BAND_EDGES_RANGE = {1: (0.7455, 1.1167), 2: (1.1033, 1.6499), 3: (1.6301, 2.4346), 4: (2.4027, 3.8473),
                    5: (3.8113, 4.43), 6: (4.4115, 5.0096)}


def saturated_among_ok(points: list[dict], run: int) -> list[dict]:
    """Saturated exposures whose neighbours in wavelength all have a brightness: a line is one reason."""
    pts = [p for p in points if p["run"] == run and p["wavelength_um"] is not None]
    out = []
    for p in pts:
        if p["status"] != "saturated":
            continue
        near = [q for q in pts if q["detector"] == p["detector"] and q is not p
                and 0.008 < abs(q["wavelength_um"] / p["wavelength_um"] - 1) < 0.07]
        if len(near) >= 4 and all(q["status"] == "ok" for q in near):
            cands = sorted(((abs(w - p["wavelength_um"]), n) for n, w in LINES), key=lambda t: t[0])
            out.append({"wave": p["wavelength_um"], "date": p["date"][:10],
                        "ids": [n for d, n in cands[:1] if d < (p["bandwidth_um"] or 0.03 * p["wavelength_um"])]})
    return out


def print_features(feats: list[dict], sat: list[dict], other: list[list[dict]]) -> None:
    for f in sorted(feats, key=lambda f: f["wave"]):
        again = any(abs(g["wave"] / f["wave"] - 1) < 0.02 for o in other for g in o)
        tag = "FIRM" if f["firm"] else "tentative"
        why = []
        if len(f["channels"]) < 2:
            why.append("one channel")
        if len(f["days"]) < 2:
            why.append("one day")
        print(f"    {f['wave']:6.3f} um (det {f['detector']}, {f['n_points']} reading(s) in {len(f['channels'])} "
              f"channel(s) on {len(f['days'])} day(s)): {f['flux']:7.1f} mJy against {f['cont']:6.1f} around it "
              f"({f['nsig']:.0f} sigma){', partial reading' if f['overflow'] else ''}; "
              f"{tag}{' (' + ', '.join(why) + ')' if why else ''}{'; also in another run' if again else ''}; "
              f"nearest: {', '.join(f['ids']) if f['ids'] else 'none within one channel width'}")
    if sat:
        print("    saturated exposures with all neighbours measured (cannot be tested, a line is one possible reason): "
              + "; ".join(f"{s['wave']:.3f} um {s['date']}" + (f" ({s['ids'][0]})" if s["ids"] else "") for s in sat))


# ---------------------------------------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------------------------------------
def colour_of(wavelength: float) -> tuple[str, tuple]:
    if wavelength < 1.8:
        return "0.75 to 1.8 micrometres", vp.BLUE
    if 2.0 <= wavelength < 3.0:
        return "2.0 to 3.0", vp.GREEN
    if 3.8 <= wavelength < 4.4:
        return "3.8 to 4.4", vp.ORANGE
    if wavelength >= 4.4:
        return "4.4 to 5.0", vp.RED
    return "other", vp.GREY


def draw_time(points: list[dict], max_mjd: float, name: str, ylim_low: float) -> vp.Image.Image:
    chart = vp.Chart(title=f"{name}: brightness in every SPHEREx exposure, by colour", xlabel="date",
                     ylabel="brightness (mJy, log scale)", xdate=True, logy=True, height=470, legend_width=300)
    chart.vline(max_mjd, color=vp.GREY, label="optical maximum")
    for label, col in BAND_COLOURS.items():
        sel = [p for p in points
               if p["status"] == "ok" and p["wavelength_um"] and colour_of(p["wavelength_um"])[0] == label]
        chart.scatter([p["mjd"] for p in sel], [p["flux_mjy"] for p in sel], color=col, size=3,
                      label=f"{label} micrometres, measured" if "micro" not in label else f"{label}, measured")
    sat = [p for p in points if p["status"] == "saturated"]
    chart.scatter([p["mjd"] for p in sat], [ylim_low * 1.5] * len(sat), color=vp.GREY, marker="x", size=3,
                  label="saturated exposure: no brightness, drawn at the bottom of the chart")
    all_ok = [p["flux_mjy"] for p in points if p["status"] == "ok" and p["flux_mjy"] > 0]
    chart.ylim = (ylim_low, max(all_ok) * 1.5)
    chart.xlim = (min(p["mjd"] for p in points) - 8, max(p["mjd"] for p in points) + 8)
    return chart.render()


def draw_spectrum(points: list[dict], run: dict, feats: list[dict], max_mjd: float, name: str) -> vp.Image.Image:
    mem = [p for p in points if p["run"] == run["id"] and p["wavelength_um"]]
    ok = [p for p in mem if p["status"] == "ok"]
    chart = vp.Chart(title=f"{name}: spectrum, {day(run['start'])} to {day(run['end'])} "
                           f"(day {run['start'] - max_mjd:+.0f} "
                     f"to {run['end'] - max_mjd:+.0f})", xlabel="wavelength (micrometres)", ylabel="brightness (mJy)",
                     logx=True, logy=True, height=430, legend_width=300)
    for hollow, text in ((False, "measured"), (True, "measured, partial (OVERFLOW pixel in the circle)")):
        sel = [p for p in ok if (p["overflow_pixels"] > 0) == hollow]
        chart.scatter([p["wavelength_um"] for p in sel], [p["flux_mjy"] for p in sel],
                      yerr=[p["flux_err_mjy"] for p in sel],
                      color=vp.RED if hollow else vp.BLUE, hollow=hollow, size=3, label=text)
    positive = [p["flux_mjy"] for p in ok if p["flux_mjy"] > 0]
    if len(positive) < len(ok):
        print(f"  note: {len(ok) - len(positive)} readings at or below zero are not drawn on the log chart "
              f"({day(run['start'])} run)")
    lo = min(positive) / 1.6
    sat = [p for p in mem if p["status"] == "saturated"]
    chart.scatter([p["wavelength_um"] for p in sat], [lo * 1.3] * len(sat), color=vp.GREY, marker="x", size=3,
                  label="saturated exposure: no brightness, drawn at the bottom")
    chart.ylim = (lo, max(positive) * 1.6)
    chart.xlim = (0.72, 5.1)
    for f in feats:
        if f["ids"]:
            chart.note(f["wave"] * 0.992, f["flux"] * 1.12, f["ids"][0].split(" (")[0] + ("" if f["firm"] else "?"),
                       vp.PURPLE if f["firm"] else vp.GREY)
    return chart.render()


def draw_map(points: list[dict], max_mjd: float, name: str) -> vp.Image.Image:
    chart = vp.Chart(title=f"{name}: what each exposure gave, by wavelength and day from maximum",
                     xlabel="wavelength (micrometres)", ylabel="days after optical maximum", logx=True, height=430,
                     legend_width=300, xlim=(0.72, 5.1))
    kinds = [("measured, no OVERFLOW pixel", lambda p: p["status"] == "ok" and p["overflow_pixels"] == 0,
              vp.GREEN, "o"),
             ("measured, partial (OVERFLOW pixel)", lambda p: p["status"] == "ok" and p["overflow_pixels"] > 0,
              vp.ORANGE, "o"),
             ("saturated, no brightness", lambda p: p["status"] == "saturated", vp.RED, "x"),
             ("flagged or other, no brightness", lambda p: p["status"] not in ("ok", "saturated"), vp.GREY, "^")]
    for label, test, col, marker in kinds:
        sel = [p for p in points if p["wavelength_um"] and test(p)]
        chart.scatter([p["wavelength_um"] for p in sel], [p["mjd"] - max_mjd for p in sel], color=col, marker=marker,
                      size=3, label=f"{label} ({len(sel)})")
    return chart.render()


def draw_optical(rows: list[dict], points: list[dict], max_jd: float, name: str) -> vp.Image.Image:
    chart = vp.Chart(title=f"{name}: AAVSO optical magnitudes (brighter is up)", xlabel="days after optical maximum",
                     ylabel="magnitude", invert_y=True, height=380, legend_width=260)
    for band, col in (("V", vp.GREEN), ("R", vp.ORANGE), ("I", vp.RED)):
        g: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            if r["band"] == band:
                g[int((r["jd"] - max_jd) // 5)].append(r["mag"])
        xs, ys = [], []
        for k in sorted(g):
            m = np.array(g[k])
            m = m[np.abs(m - np.median(m)) < 3]
            if len(m):
                xs.append(5 * k + 2.5)
                ys.append(float(np.median(m)))
        chart.scatter(xs, ys, color=col, size=3, label=f"{band} band, median of 5 days")
    days = sorted({int(round(p["mjd"] + 2400000.5 - max_jd)) for p in points})
    for d in days[::3]:
        chart.vline(d, color=(200, 200, 200))
    chart.vline(0, color=vp.GREY, label="optical maximum; pale lines: SPHEREx exposures")
    return chart.render()


# ---------------------------------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ra", type=float)
    parser.add_argument("dec", type=float)
    parser.add_argument("--name", default=None)
    parser.add_argument("--max-jd", type=float, required=True, help="Julian date of the optical maximum")
    parser.add_argument("--aavso-name", default=None, help="name for AAVSO if it differs from --name")
    parser.add_argument("--out", type=Path, default=None, help="folder for the pictures (PNG)")
    parser.add_argument("--offline", action="store_true", help="skip sections 4 to 6 (network)")
    parser.add_argument("--verbose", action="store_true", help="print every channel of the like-with-like tables")
    parser.add_argument("--min-star-distance", type=float, default=80.0,
                        help="field stars nearer than this (arcsec) are reported separately (the nova's halo)")
    args = parser.parse_args()
    name = args.name or f"RA {args.ra:.5f}, Dec {args.dec:+.5f}"
    slug = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
    max_mjd = args.max_jd - 2400000.5

    curve = photometry.lightcurve(args.ra, args.dec)
    points = flatten(curve)
    runs = make_runs(points, max_mjd - SPLIT_BEFORE_MAX_DAYS)
    print(f"{name}  RA {args.ra:.5f} Dec {args.dec:+.5f}  maximum JD {args.max_jd} = {day(max_mjd)}")
    print(f"{len(points)} exposures measured: {curve['status_counts']}; "
          f"download failures: {len(curve.get('failures') or [])}")
    print(f"what was measured: {curve['measured']['description']}")
    print_runs(points, runs, max_mjd)

    # runs with a measured brightness after the eruption
    after = [r for r in runs if r["end"] > max_mjd - SPLIT_BEFORE_MAX_DAYS and r["n_ok"] >= 10]
    print("\n2. LIKE WITH LIKE: the same detector and channel on two dates")
    windows: list[tuple[str, float, float]] = []
    before = [r for r in runs if r["end"] < max_mjd - SPLIT_BEFORE_MAX_DAYS and r["n_ok"] > 0]
    if before:
        windows.append(("before the eruption", min(r["start"] for r in before), max(r["end"] for r in before) + 1))
    for r in after[-2:]:
        windows.append((f"run {r['id']}", r["start"], r["end"] + 1))
    last = after[-1] if after else None
    pairs = [(r, last) for r in runs if last and r["id"] != last["id"] and r["end"] > max_mjd - SPLIT_BEFORE_MAX_DAYS
             and r["n_ok"] >= 1]
    if last:
        dates = sorted(p["mjd"] for p in points if p["run"] == last["id"] and p["status"] == "ok")
        mid = dates[len(dates) // 2]
    for ra_, rb_ in pairs:
        compare(points, f"run {ra_['id']}", lambda p, r=ra_: p["run"] == r["id"], f"run {rb_['id']}",
                lambda p, r=rb_: p["run"] == r["id"], max_mjd, args.verbose)
    if last:
        compare(points, f"run {last['id']} first half", lambda p: p["run"] == last["id"] and p["mjd"] < mid,
                f"run {last['id']} second half", lambda p: p["run"] == last["id"] and p["mjd"] >= mid, max_mjd, True)
        windows_halves = [(f"run {last['id']} first half", last["start"], mid), (f"run {last['id']} second half", mid,
                                                                               last["end"] + 1)]
    saturation_check(points, after, max_mjd)

    if not args.offline:
        catalogue_check(args.ra, args.dec, curve)
        try:
            field_star_check(args.ra, args.dec, curve, windows, args.min_star_distance)
            if last:
                field_star_check(args.ra, args.dec, curve, windows_halves, args.min_star_distance)
        except Exception as e:  # noqa: BLE001 - say so, do not skip silently
            print(f"  field stars could not be measured ({type(e).__name__}: {e}); this check was not done")
    else:
        print("\n4 and 5 skipped (--offline): catalogues and field stars were not checked this time")
    optical = None
    if not args.offline:
        optical = aavso_check(args.aavso_name or name, args.max_jd)
        if optical:
            optical_vs_spherex(optical, points, after, max_mjd)
    else:
        print("\n6 skipped (--offline): AAVSO was not fetched this time")

    print("\n8. EMISSION-LINE CANDIDATES: channels more than 5 times the scatter of their neighbours above them "
          f"(the scatter is never counted as less than {LINE_FLOOR:.0%}, and the excess must be at least "
          f"{LINE_MIN_RATIO:.2f} times)")
    all_feats: dict[int, list[dict]] = {}
    for r in after:
        all_feats[r["id"]] = find_features(points, r["id"])
    for r in after:
        print(f"\n  {run_label(r, max_mjd)}: {len(all_feats[r['id']])} candidate(s)")
        print_features(all_feats[r["id"]], saturated_among_ok(points, r["id"]),
                       [v for k, v in all_feats.items() if k != r["id"]])
    fits = {}
    for r in after:
        feats_as_channels = [{"detector": f["detector"], "channels": f["channels"]} for f in all_feats[r["id"]]]
        # the lines found in any run are left out of every run's continuum
        for k, v in all_feats.items():
            if k != r["id"]:
                feats_as_channels += [{"detector": f["detector"], "channels": f["channels"]} for f in v]
        fits[r["id"]] = temperature_check(points, r["id"], feats_as_channels, max_mjd, run_label(r, max_mjd))

    if args.out:
        print("\nPictures")
        ok = [p["flux_mjy"] for p in points if p["status"] == "ok" and p["flux_mjy"] > 0]
        out = args.out
        n_neg = sum(p["status"] == "ok" and p["flux_mjy"] <= 0 for p in points)
        if n_neg:
            print(f"  note: {n_neg} readings at or below zero are not drawn on the log charts")
        vp.save(draw_time(points, max_mjd, name, min(ok) / 1.5), out / f"{slug}_time.png")
        for r in after:
            if r["n_ok"] >= 15:
                vp.save(draw_spectrum(points, r, all_feats[r["id"]], max_mjd, name),
                        out / f"{slug}_spectrum_run{r['id']}.png")
        vp.save(draw_map(points, max_mjd, name), out / f"{slug}_saturation.png")
        if optical:
            vp.save(draw_optical(optical, points, args.max_jd, name), out / f"{slug}_optical.png")


if __name__ == "__main__":
    main()

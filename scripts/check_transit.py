"""Known-answer test and measurements of planets crossing their stars in SPHEREx deep-field exposures.

Order, stopping at the first failure of A1 or A2 (nothing after a failed test is presented):
  A1  WASP-62 b, detector 5, against its published depth (Rp/Rs)^2 = 1.23 per cent
  A2  steady Gaia comparison stars in the same exposures, fitted with WASP-62 b's ephemeris
  A3  WASP-100 b, every detector with enough in-transit readings (reported, never tuned)
  A4  colour test: is a planet's depth the same in two detectors? (validated only if a planet
      measured at 3 sigma or more in two detectors gives chi-squared p above 0.01)
  A5  TOI-4055.01 (a TESS candidate), per-detector depths with errors and the smallest depth and
      depth difference the data could show. No planet-or-blend verdict is ever printed.
Everything that needs no network is rerun from the cache; cutouts that are not on disk are read
from the public S3 bucket (about 1.2 GB in all). Real data only.

usage: python scripts/check_transit.py [--cache-dir DIR] [--probe-dir DIR] [--no-fetch] [--only A1,A3]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import transits as T  # noqa: E402
from scripts.verify_plot import BLUE, GREEN, GREY, LIGHT, ORANGE, RED, Chart  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "transits"

WASP62 = dict(ra=87.13982, dec=-63.98833, period_d=4.41193868, t0_bjd_tdb=2458851.099338, t14_h=3.79, rprs=0.1109,
              name="WASP-62 b")
WASP100 = dict(ra=68.9598159, dec=-64.0270390, period_d=2.84938224, t0_bjd_tdb=2458853.880674, t14_h=3.75, rprs=0.087,
               name="WASP-100 b")
TOI4055 = dict(ra=269.179221, dec=64.766624, period_d=4.5679250, t0_bjd_tdb=2459853.406756, t14_h=3.047, rprs=0.1358,
               name="TOI-4055.01 (TESS candidate)")


def bin_curve(h: np.ndarray, f: np.ndarray, width: float, lim: float) -> tuple[list, list, list]:
    edges = np.arange(-lim, lim + 1e-9, width)
    c, m, e = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:], strict=False):
        q = (h >= lo) & (h < hi)
        if q.sum() >= 5:
            c.append(0.5 * (lo + hi))
            m.append(float(np.mean(f[q])))
            e.append(T.robust_std(f[q]) / np.sqrt(q.sum()))
    return c, m, e


def plot_fold(res: dict, det: str, path: Path, title: str) -> None:
    d = res["detectors"][det]
    h = np.array(d["folded"]["hours"])
    f = np.array(d["folded"]["flux"])
    sel = np.abs(h) < 9
    c = Chart(title, "hours from mid-transit (published ephemeris)", "brightness / the star's own spectrum", width=1100, height=480)
    c.scatter(h[sel], f[sel], color=(170, 170, 170), label=f"single readings ({int(sel.sum())})", size=2)
    bc, bm, be = bin_curve(h, f, 0.75, 9)
    c.scatter(bc, bm, yerr=be, color=BLUE, label="45-minute means")
    hh = np.linspace(-9, 9, 400)
    shape = T.trapezoid(hh / 24, res["t14_h"], res["rprs"])
    c.line(hh, 1 - res["expected_depth"] * shape, color=GREEN, label=f"published depth {100 * res['expected_depth']:.2f}%")
    c.line(hh, 1 - d["depth"] * shape, color=RED, label=f"fitted {100 * d['depth']:.2f}% +/- {100 * d['empirical_err']:.2f}%")
    c.render().save(path)


def plot_slide(res: dict, det: str, path: Path) -> None:
    d = res["detectors"][det]
    s = d["time_slide"]
    c = Chart("Depth against the assumed transit time (peak must sit at zero)", "assumed time minus published mid-transit (hours)",
              "fitted depth (fraction of the star's light)", width=900, height=420)
    c.scatter([x["offset_h"] for x in s], [x["depth"] for x in s], yerr=[x["formal_err"] for x in s], color=BLUE,
              label="detector " + det)
    c.hline(0.0, color=GREY)
    c.vline(0.0, color=LIGHT)
    c.render().save(path)


def plot_depths(blocks: list[tuple[str, dict]], path: Path, title: str) -> None:
    c = Chart(title, "detector", "depth (per cent of the star's light)", width=900, height=420)
    colors = [BLUE, ORANGE, GREEN, RED]
    for (label, r), col in zip(blocks, colors, strict=False):
        use = T.usable_detectors(r)
        if not use:
            continue
        c.scatter(list(use), [100 * v["depth"] for v in use.values()], yerr=[100 * v["empirical_err"] for v in use.values()],
                  color=col, label=label)
        c.hline(100 * r["expected_depth"], color=col, label=None)
    c.hline(0.0, color=GREY)
    c.render().save(path)


def summarise(res: dict) -> dict:
    """Result without the large arrays (the folded readings), for results.json."""
    out = json.loads(json.dumps(res, default=float))
    for d in out["detectors"].values():
        if "folded" in d:
            h = np.array(d["folded"]["hours"])
            f = np.array(d["folded"]["flux"])
            bc, bm, be = bin_curve(h, f, 0.75, 9)
            d["folded"] = {"bin_hours": bc, "bin_mean": bm, "bin_err": be}
    return out


def run(spec: dict, detectors, args, probe: dict, size: float, **kw) -> dict:
    return T.transit_check(detectors=detectors, size_deg=size, cache_dir=args.cache_dir, fetch=not args.no_fetch,
                           cutout_roots=probe.get("roots", []), exposure_seed=probe.get("seed"), **spec, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=Path, default=T.CACHE)
    ap.add_argument("--probe-dir", type=Path, default=None, help="folder holding earlier cutouts and exposure lists, reused if given")
    ap.add_argument("--no-fetch", action="store_true", help="measure only what is already on disk")
    ap.add_argument("--only", default="A1,A2,EB,A3,A4,A5")
    args = ap.parse_args()
    wanted = set(args.only.split(","))
    DOCS.mkdir(parents=True, exist_ok=True)
    pd = args.probe_dir

    def probe(cut: str, exp: str) -> dict:
        if pd is None:
            return {}
        return {"roots": [pd / cut], "seed": pd / "data" / f"exposures_{exp}.json"}

    results: dict = {"version": T.VERSION, "acceptance": {}}
    ok = True

    # ---- A1
    w62 = run(WASP62, (1, 2, 3, 4, 5, 6), args, probe("cutouts", "WASP-62"), 0.1)
    w62h = run(WASP62, (5,), args, probe("cutouts", "WASP-62"), 0.1, accept_halo=True)
    d5 = w62["detectors"]["5"]
    exp = w62["expected_depth"]
    a1 = {
        "depth": d5["depth"], "formal_err": d5["formal_err"], "empirical_err": d5["empirical_err"],
        "within_2_sigma_of_published": abs(d5["depth"] - exp) < 2 * d5["empirical_err"],
        "empirical_sigma_at_least_3.5": d5["empirical_sigma"] >= 3.5,
        "fake_share_under_1pc": d5["fake_share_as_deep"] < 0.01,
        "time_slide_peak_at_zero": abs(d5["slide_peak_h"]) <= 1.5,
        "both_years_over_3_formal_sigma": all(y["depth"] / y["formal_err"] > 3 for y in d5["years"].values()) and len(d5["years"]) == 2,
    }
    a1["passed"] = all(v for k, v in a1.items() if isinstance(v, bool))
    results["acceptance"]["A1"] = a1
    results["wasp62"] = summarise(w62)
    results["wasp62_halo_accepted"] = summarise(w62h)
    plot_fold(w62, "5", DOCS / "wasp62b_folded_D5.png", "WASP-62 b in SPHEREx detector 5 (3.8 to 4.4 um), deep-field exposures folded")
    plot_slide(w62, "5", DOCS / "wasp62b_time_slide_D5.png")
    print("A1", json.dumps(a1, indent=1))
    ok = a1["passed"]

    # ---- A2
    if ok:
        comps = d5.get("comparison", [])
        a2 = {"stars": [{"gmag": c["gmag"], "distance_arcsec": c["distance_arcsec"], "n_in": c["n_in"], "depth": c["depth"],
                         "empirical_err": c["empirical_err"], "within_2_sigma_of_zero": abs(c["depth"]) < 2 * c["empirical_err"]}
                        for c in comps]}
        a2["passed"] = bool(comps) and all(s["within_2_sigma_of_zero"] for s in a2["stars"])
        results["acceptance"]["A2"] = a2
        print("A2", json.dumps(a2, indent=1))
        ok = a2["passed"]

    # ---- EB: a known eclipsing binary, the known answer for the colour test
    if ok and "EB" in wanted:
        eb_in = json.loads((DOCS / "eb_tic233532554_rows.json").read_text())
        eb: dict = {"expected_primary_depth_tess": 0.817, "assumed_flat_part": {}}
        keys = ("n_ok", "n_overflow", "n_in", "depth", "formal_err", "empirical_err", "empirical_sigma",
                "fake_share_as_deep", "overflow_affected", "status", "wl_min", "wl_max")
        for k in (0.5, 0.8):
            r = T.eclipse_by_detector(eb_in, rprs=k)
            clean = {"detectors": {d: v for d, v in r["detectors"].items() if not v.get("overflow_affected")}}
            eb["assumed_flat_part"][str(k)] = {
                "detectors": {d: {key: v.get(key) for key in keys} for d, v in r["detectors"].items()},
                "colour_all_six": T.colour_test(r, min_in_transit=6),
                "colour_without_overflow_detectors": T.colour_test(clean, min_in_transit=6)}
        results["eclipsing_binary"] = eb
        ch = Chart("Eclipsing binary TIC 233532554: primary-eclipse depth by detector", "wavelength (micrometres)",
                   "depth (fraction of the light)", width=900, height=420)
        for k, col in ((0.5, BLUE), (0.8, ORANGE)):
            dd = eb["assumed_flat_part"][str(k)]["detectors"]
            good = [(0.5 * (v["wl_min"] + v["wl_max"]), v["depth"], v["empirical_err"])
                    for v in dd.values() if v.get("depth") is not None]
            ch.scatter([g[0] for g in good], [g[1] for g in good], yerr=[g[2] for g in good], color=col,
                       label=f"SPHEREx, eclipse flat part {k}")
        ch.hline(0.817, color=GREEN, label="TESS depth 0.817")
        ch.render().save(DOCS / "eb_depths.png")
        print("EB", json.dumps(eb, indent=1, default=float)[:3000])

    if ok and "A3" in wanted:
        w100 = run(WASP100, (2, 3, 5, 6), args, probe("cutouts_w100", "WASP-100"), 0.05)
        comb = T.combine_detectors(w100)
        a3 = {"per_detector": {d: {k: r.get(k) for k in ("n", "n_in", "depth", "formal_err", "empirical_err", "empirical_sigma",
                                                          "fake_share_as_deep", "scatter", "photon", "excluded")}
                               for d, r in w100["detectors"].items()}, "combined": comb, "expected": w100["expected_depth"]}
        if comb:
            a3["passed"] = abs(comb["depth"] - w100["expected_depth"]) < 2 * comb["error"]
        results["acceptance"]["A3"] = a3
        results["wasp100"] = summarise(w100)
        plot_depths([("WASP-100 b", w100)], DOCS / "wasp100b_depths.png", "WASP-100 b: depth by detector (line = published)")
        print("A3", json.dumps(a3, indent=1, default=float))

    # ---- A4: has any planet been measured at 3 sigma or more in two detectors with the same depth?
    if ok and "A4" in wanted:
        a4 = {}
        for key, r in (("WASP-62 b", w62), ("WASP-100 b", results.get("wasp100"))):
            if r is None:
                continue
            ct = T.colour_test(r)
            sig = ct.get("n_sigma_each", {})
            a4[key] = {**ct, "two_detectors_at_3_sigma": sum(v >= 3 for v in sig.values()) >= 2}
        a4["validated"] = any(v["two_detectors_at_3_sigma"] and v.get("tested") and v["p_value"] > 0.01 for v in a4.values())
        results["acceptance"]["A4"] = a4
        print("A4", json.dumps(a4, indent=1, default=float))

    # ---- A5
    if ok and "A5" in wanted:
        toi = run(TOI4055, (1, 2, 3, 4, 5, 6), args, probe("cutouts_toi4055", "TOI-4055.01"), 0.05, comparison_stars=False)
        results["toi4055"] = summarise(toi)
        results["toi4055"]["colour_test_validated"] = results["acceptance"].get("A4", {}).get("validated", False)
        results["toi4055"]["limits"] = T.detection_limits(toi)
        results["toi4055"]["colour_measurement"] = T.colour_test(toi)
        plot_depths([("TOI-4055.01", toi)], DOCS / "toi4055_depths.png", "TOI-4055.01: measured depth by detector (line = TESS)")
        print("A5", json.dumps({k: results["toi4055"][k] for k in ("limits", "colour_measurement")}, indent=1, default=float))

    (DOCS / "results.json").write_text(json.dumps(results, indent=1, default=float))
    print("wrote", DOCS / "results.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

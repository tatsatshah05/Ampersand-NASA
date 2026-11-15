# ruff: noqa: E501
"""Repeat every colour-walk test from what is on disk (and the archive, for hosts not yet cached).

Run:  SPHEREX_CACHE_DIR=backend/cache .venv/bin/python scripts/check_colourwalk.py [step ...]

Steps, in the order they must pass (the script stops at the first failure):
  null      the Barnard field (b=+14): isolated stars do not walk, blended stars walk toward their neighbours;
            plus a high-latitude field (b=-48): the false-walk rate no Gaia neighbour explains
  vhs       VHS 1256-1257 b: the walk, its direction, its flux ratios and the rotated controls
  identity  2MASS J0219-3925 B: its Gaia counterpart against the discovery paper's separation and angle
  2m0219    the second known answer, only if the identification matches
Results are merged into docs/colourwalk/results.json; charts go to docs/colourwalk/.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from verify_plot import BLACK, BLUE, GREEN, GREY, ORANGE, RED, Chart  # noqa: E402

from backend import astrometry, spherex  # noqa: E402
from backend import colourwalk as cw  # noqa: E402

OUT = ROOT / "docs" / "colourwalk"
RESULTS = OUT / "results.json"
CUTOUTS = spherex.CACHE / "cutouts"
BARNARD = "01e6af5d45"
HIGH_LAT = "e5ab28dff8"          # RA 331.09, Dec -56.80, b = -48, six detectors, 467 exposures
VHS_DIR = "11f6028523"           # VHS 1256-1257, cutouts 0.06 deg
VHS_GAIA = "3526198184723289472"
VHS_B = (8.06, 218.1)            # Gauza et al. 2015: separation arcsec, position angle degrees

# Acceptance, written down before any run (from the build brief).
NULL_MEDIAN_LIMIT = 0.06
NULL_MIN_STARS = 10
NULL_WALK_FRACTION = 0.90
BLEND_COS = 0.9
VHS_PA = (218.0, 15.0)
VHS_ALONG_MIN = 0.15
VHS_RATIO_KS = (0.010, 0.030)
VHS_RATIO_RED = (0.040, 0.100)
VHS_BLUE_ZERO = 0.010
CONTROL_LIMIT = 0.02


def load() -> dict:
    return json.loads(RESULTS.read_text()) if RESULTS.exists() else {}


def save(key: str, value: dict) -> None:
    data = load()
    data[key] = value
    OUT.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(data, indent=1, default=float))


def field_centre(directory: str) -> tuple[float, float, list[Path]]:
    paths = sorted((CUTOUTS / directory).glob("*.fits"))
    with fits.open(paths[0]) as h:
        ny, nx = h["IMAGE"].data.shape
        ra, dec = WCS(h["IMAGE"].header).all_pix2world(nx / 2, ny / 2, 0)
    return float(ra), float(dec), paths


def blend_calibration(table, stars, rE, rN, ok) -> dict:
    """Short-wavelength offset (detector 1) against the offset the Gaia neighbours predict; fits the response width."""
    rows = table
    k, det = rows[:, 0].astype(int), rows[:, 2]
    mjd0 = float(np.median(rows[:, 1]))
    ra, dec = astrometry.positions_at(stars, mjd0)
    meas = {}
    for s in np.unique(k[ok]):
        m = ok & (k == s) & (det == 1)
        if m.sum() < 6:
            continue
        meas[int(s)] = (float(np.median(rE[m])), float(np.median(rN[m])))
    def neighbours(s):
        e = (ra - ra[s]) * np.cos(np.radians(dec[s])) * 3600
        n = (dec - dec[s]) * 3600
        sep = np.hypot(e, n)
        sel = (sep > 0.3) & (sep < 15)
        f = cw.rp_flux_ratios(stars[s], [stars[j] for j in np.flatnonzero(sel)])
        return e[sel], n[sel], f
    nb = {s: neighbours(s) for s in meas}

    def stats(scale):
        pred = {s: cw.predicted_shift(*nb[s], scale) for s in meas}
        big = [s for s in meas if np.hypot(*pred[s]) > 0.1]
        if len(big) < 4:
            return None
        m = np.array([meas[s] for s in big])
        p = np.array([pred[s] for s in big])
        slope = float(np.sum(m * p) / np.sum(p * p))
        cos = np.sum(m * p, axis=1) / (np.hypot(*m.T) * np.hypot(*p.T))
        resid = float(np.sqrt(np.mean(np.sum((m - p) ** 2, axis=1))))
        return {"scale": scale, "n": len(big), "slope": slope, "median_cos": float(np.median(cos)), "rms_residual": resid}
    grid = [stats(s) for s in np.arange(1.5, 12.01, 0.5)]
    grid = [g for g in grid if g]
    nominal = stats(cw.RESPONSE_SCALE_ARCSEC)
    best = min(grid, key=lambda g: g["rms_residual"]) if grid else None
    return {"nominal": nominal, "best": best, "grid": grid}


def field_test(directory: str, label: str, do_catalogues: bool = False) -> dict:
    ra, dec, paths = field_centre(directory)
    stars = cw.gaia_neighbours(ra, dec, 400.0, 21.0)
    print(f"[{label}] {len(paths)} exposures, {len(stars)} Gaia stars with G<21", flush=True)
    cache = spherex.CACHE / "queries" / f"cwfield_{directory}_{len(paths)}_{len(stars)}.npy"
    if cache.exists():
        table = np.load(cache)
    else:
        table = cw.measure_field(paths, stars, 17.5, workers=6)
        np.save(cache, table)
    print(f"[{label}] {len(table)} star fits", flush=True)
    mjd0 = float(np.median(table[:, 1]))
    ref_iso = cw.isolated_mask(stars, mjd0, (0.0, 17.5))
    min_ref = 5
    rE, rN, ok = cw.remove_frame_offsets(table, ref_iso, min_ref)
    if ok.sum() < 500:
        min_ref = 3          # a sparse field: fewer reference stars per exposure, said in the results
        rE, rN, ok = cw.remove_frame_offsets(table, ref_iso, min_ref)
    test_iso = cw.isolated_mask(stars, mjd0, (11.5, 15.0))
    k, det = table[:, 0].astype(int), table[:, 2]
    # per-detector medians of isolated stars
    good_stars, all_stars, all_meds = [], [], []
    for s in np.flatnonzero(test_iso):
        meds = []
        for d in range(1, 7):
            m = ok & (k == s) & (det == d)
            if m.sum() >= 8:
                meds.append((d, float(np.median(rE[m])), float(np.median(rN[m])), int(m.sum())))
        if len(meds) >= 4:
            all_stars.append(int(s))
            all_meds.extend((e, n) for _, e, n, _ in meds)
            if all(abs(e) <= NULL_MEDIAN_LIMIT and abs(n) <= NULL_MEDIAN_LIMIT for _, e, n, _ in meds):
                good_stars.append(int(s))
    w_floor = cw.star_walks(table, rE, rN, ok, cw.FLOOR_ARCSEC)
    w_none = cw.star_walks(table, rE, rN, ok, 0.0)
    iso_walk = [w_floor[s]["sigma"] for s in all_stars if s in w_floor]
    iso_walk_nofloor = [w_none[s]["sigma"] for s in all_stars if s in w_none]
    res: dict = {"directory": directory, "ra": ra, "dec": dec, "n_exposures": len(paths), "n_gaia_g21": len(stars),
                 "n_star_fits": int(len(table)), "min_reference_stars_per_exposure": min_ref, "n_rows_usable": int(ok.sum()),
                 "star_to_star_rms_of_detector_medians": {
                     "east": float(1.4826 * np.median(np.abs(np.array(all_meds)[:, 0]))) if all_meds else None,
                     "north": float(1.4826 * np.median(np.abs(np.array(all_meds)[:, 1]))) if all_meds else None,
                     "n_values": len(all_meds)},
                 "isolated_G11p5_15": {"n": len(all_stars), "n_all_detector_medians_within_0p06": len(good_stars),
                                       "frac_walk_below_3sigma_with_floor": float(np.mean(np.array(iso_walk) < 3)) if iso_walk else None,
                                       "frac_walk_below_3sigma_no_floor": float(np.mean(np.array(iso_walk_nofloor) < 3)) if iso_walk_nofloor else None,
                                       "n_walk": len(iso_walk)}}
    # calibration against Gaia neighbours (short-wavelength offset)
    res["blend_calibration"] = blend_calibration(table, stars, rE, rN, ok)
    # false-walk rate: stars with no Gaia neighbour (G<21) within 15 arcsec at all
    ra_s, dec_s = astrometry.positions_at(stars, mjd0)
    g = np.array([s["gmag"] for s in stars])
    clean = []
    for s in w_floor:
        if not 11.5 <= g[s] < 17.5:
            continue
        sep = np.hypot((ra_s - ra_s[s]) * np.cos(np.radians(dec_s[s])), dec_s - dec_s[s]) * 3600
        if not ((sep > 0.01) & (sep < 15)).any():
            clean.append(s)
    sig = np.array([w_floor[s]["sigma"] for s in clean])
    sig0 = np.array([w_none[s]["sigma"] for s in clean if s in w_none])
    res["false_walk"] = {"n_clean_stars_no_gaia_g21_within_15": len(clean),
                         "frac_over_3sigma": float(np.mean(sig > 3)) if len(sig) else None,
                         "frac_over_5sigma": float(np.mean(sig > 5)) if len(sig) else None,
                         "n_over_5sigma": int((sig > 5).sum()), "n_over_3sigma": int((sig > 3).sum()),
                         "frac_over_5sigma_no_floor": float(np.mean(sig0 > 5)) if len(sig0) else None,
                         "by_magnitude": {f"{lo}-{hi}": {"n": int(sum(lo <= g[s] < hi for s in clean)),
                                                         "over_5sigma": int(sum(lo <= g[s] < hi and w_floor[s]["sigma"] > 5 for s in clean))}
                                          for lo, hi in [(11.5, 14.5), (14.5, 16.0), (16.0, 17.5)]}}
    # every walking star: Gaia neighbour along the walk? (and catalogue neighbours when asked)
    walkers = []
    for s, w in sorted(w_floor.items(), key=lambda kv: -kv[1]["sigma"]):
        if w["sigma"] <= 4 or g[s] >= 17.5:
            continue
        pa = cw.position_angle(w["walk_east"], w["walk_north"])
        host = {**stars[s], "ra": float(ra_s[s]), "dec": float(dec_s[s]), "pmra": 0.0, "pmdec": 0.0, "parallax": 0.0,
                "ref_epoch": 2016.0}
        near = cw.gaia_explains(pa, host, [stars[j] for j in range(len(stars)) if j != s])
        entry = {"index": int(s), "source_id": stars[s]["source_id"], "G": g[s], "sigma": w["sigma"],
                 "walk_arcsec": float(np.hypot(w["walk_east"], w["walk_north"])), "pa": pa, "gaia_neighbour_on_walk": near}
        if do_catalogues:
            cats = cw.catalogue_sources(float(ra_s[s]), float(dec_s[s]), 20.0)
            entry["catalogue_lookup_failed"] = cw.catalogues_failed(cats)
            hits = {}
            for name, rows in cats.items():
                for r in rows:
                    if "east" not in r:
                        break          # a failed lookup is recorded above and is never an explanation
                    sep = float(np.hypot(r["east"], r["north"]))
                    if 2.0 <= sep <= 20.0 and cw.angle_difference(cw.position_angle(r["east"], r["north"]), pa) <= 30:
                        hits[name] = {"sep": round(sep, 1), "pa": round(cw.position_angle(r["east"], r["north"]), 0)}
                        break
            entry["catalogue_neighbour_on_walk"] = hits
        walkers.append(entry)
    res["walkers_over_4sigma"] = {"n": len(walkers),
                                  "n_explained_by_gaia_neighbour": sum(1 for w in walkers if w["gaia_neighbour_on_walk"]),
                                  "n_explained_by_catalogue": sum(1 for w in walkers if w.get("catalogue_neighbour_on_walk")),
                                  "n_catalogue_lookups_failed": sum(1 for w in walkers if w.get("catalogue_lookup_failed")),
                                  "n_unexplained": sum(1 for w in walkers if not w["gaia_neighbour_on_walk"] and not w.get("catalogue_neighbour_on_walk")),
                                  "stars": walkers}
    return res


def step_null() -> bool:
    out = {}
    for directory, label, cats in [(BARNARD, "Barnard b=+14", True), (HIGH_LAT, "high latitude b=-48", True)]:
        out[label] = field_test(directory, label, do_catalogues=cats)
        r = out[label]
        iso = r["isolated_G11p5_15"]
        print(json.dumps({"isolated": iso, "calibration_best": r["blend_calibration"]["best"],
                          "calibration_nominal": r["blend_calibration"]["nominal"], "false_walk": r["false_walk"],
                          "walkers": {k: v for k, v in r["walkers_over_4sigma"].items() if k != "stars"}}, default=float, indent=1))
    b = out["Barnard b=+14"]
    iso, best = b["isolated_G11p5_15"], b["blend_calibration"]["best"]
    nom = b["blend_calibration"]["nominal"]
    checks = {
        "at_least_10_isolated_stars_within_0p06": iso["n_all_detector_medians_within_0p06"] >= NULL_MIN_STARS,
        "90_percent_walk_below_3sigma": (iso["frac_walk_below_3sigma_with_floor"] or 0) >= NULL_WALK_FRACTION,
        "blended_median_cos_at_least_0p9_at_calibrated_width": best["median_cos"] >= BLEND_COS,
    }
    out["acceptance"] = {"checks": checks, "passed": all(checks.values()), "calibrated_scale_arcsec": best["scale"],
                         "median_cos_at_nominal_scale": (nom or {}).get("median_cos"), "slope_at_nominal_scale": (nom or {}).get("slope"), "slope_at_best_scale": best["slope"]}
    save("null", out)
    print("NULL", checks)
    return all(checks.values())


def vhs_charts(res: dict, tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    aa = [b for b in res["along_across"] if b["along"] is not None]
    mid = [0.5 * (b["lo"] + b["hi"]) for b in aa]
    c = Chart(f"{tag}: offset along and across the walk (bars include the 0.05-0.07 arcsec floor; across chi2 {res['across_chi2']['chi2']:.1f} for {res['across_chi2']['n_bins']} bins)",
              "wavelength (micrometres)", "offset from Gaia (arcsec)", width=980, height=420)
    c.hline(0.0)
    c.scatter(mid, [b["along"] for b in aa], yerr=[b["err"] for b in aa], color=RED, label="along the walk")
    c.scatter(mid, [b["across"] for b in aa], yerr=[b["err_across"] for b in aa], color=BLUE, label="across the walk")
    c.render().save(OUT / f"{tag}_offsets.png")
    nr = [b for b in res["net_ratio"] if b["net"] is not None]
    mid = [0.5 * (b["lo"] + b["hi"]) for b in nr]
    c = Chart(f"{tag}: companion / host flux ratio against wavelength", "wavelength (micrometres)",
              "flux ratio", width=980, height=420)
    c.hline(0.0)
    c.hline(CONTROL_LIMIT, color=ORANGE, label="0.02 control limit")
    c.scatter(mid, [b["ratio"] for b in nr], yerr=[b["err"] for b in nr], color=GREY, label="fit at the walk direction")
    c.scatter(mid, [b["control"] for b in nr], color=ORANGE, label="median of the three rotated controls", marker="s")
    c.scatter(mid, [b["net"] for b in nr], yerr=[b["net_err"] for b in nr], color=GREEN, label="net (difference)")
    c.render().save(OUT / f"{tag}_ratio.png")


def step_vhs() -> bool:
    g = astrometry.gaia_source(VHS_GAIA)
    paths = sorted((CUTOUTS / VHS_DIR).glob("*.fits"))
    common = dict(pmra=g["pmra"], pmdec=g["pmdec"], parallax=g["parallax"], source_id=g["source_id"], paths=paths, workers=6)
    blind = cw.colour_walk(g["ra"], g["dec"], **common)
    print("blind verdict", blind["verdict"], blind["reasons"], "catalogues failed:", blind.get("catalogues_failed"))
    known = cw.colour_walk(g["ra"], g["dec"], companion=VHS_B, **common)
    for r in (blind, known):
        r.pop("rows", None)
    walk = blind["walk"]["all"]
    pa_ok = cw.angle_difference(walk["pa"], VHS_PA[0]) <= VHS_PA[1]
    along, across = cw.components(walk["east"], walk["north"], VHS_B[1])
    along_ok = along >= VHS_ALONG_MIN
    nets = {f"{b['lo']:g}-{b['hi']:g}": b for b in known["net_ratio"] if b["net"] is not None}
    ks = nets["2-2.43"]["net"]
    red = [b["net"] for b in known["net_ratio"] if b["net"] is not None and b["lo"] >= 3.4]
    blue = [(b["net"], b["net_err"]) for b in known["net_ratio"] if b["net"] is not None and b["hi"] <= 1.4]
    ctrl_all = [b["control_max"] for b in known["net_ratio"] if b.get("control_max") is not None]
    # per-bin maximum of each individual control, read from the plan rows
    checks = {
        "pa_within_15_of_218": pa_ok,
        "along_walk_at_least_0p15": along_ok,
        "ratio_2p0_2p43_in_0p010_0p030": VHS_RATIO_KS[0] <= ks <= VHS_RATIO_KS[1],
        "ratio_3p4_5p0_in_0p04_0p10": all(VHS_RATIO_RED[0] <= v <= VHS_RATIO_RED[1] for v in red),
        "ratio_0p75_1p4_consistent_with_0_within_0p01": all(abs(n) <= VHS_BLUE_ZERO for n, _ in blue),
        "every_individual_control_at_most_0p02": max(ctrl_all) <= CONTROL_LIMIT,
        "control_median_at_most_0p02": max(b["control"] for b in known["net_ratio"] if b["control"] is not None) <= CONTROL_LIMIT,
    }
    per_det = {k: blind["walk"][k] for k in ("D4", "D5", "D6")}
    sky_ok = {v["visit"]: (v["sky"]["angle_deg"], v["detector"]["angle_deg"]) for v in blind["visit_walks"]}
    out = {"development_object_note": "VHS 1256 was seen by the inventor's probe first: a calibration object, not a blind test",
           "per_visit_sky_and_detector_angles": sky_ok, "blind_scan": blind, "known_place": known, "acceptance": {"checks": checks, "passed": all(checks.values())},
           "along_at_218_all_detectors": along, "across_at_218": across, "per_detector_walks": per_det}
    save("vhs1256", out)
    vhs_charts(blind, "vhs1256_blind")
    vhs_charts(known, "vhs1256_known_place")
    print(json.dumps(checks, indent=1))
    print("walk", json.dumps(walk, default=float))
    print("blind best separation", blind["best_separation_arcsec"], "gain", blind["gain_by_separation"])
    return all(checks.values())


def main() -> int:
    steps = sys.argv[1:] or ["null", "vhs"]
    table = {"null": step_null, "vhs": step_vhs}
    for s in steps:
        ok = table[s]()
        print(f"STEP {s}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            print("stopping at the first failure: the method is not proven; nothing further is run")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

_ = glob  # noqa: F841
_ = BLACK, GREEN  # noqa: F841

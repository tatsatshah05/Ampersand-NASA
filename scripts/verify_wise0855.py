"""Independent check of claim 1: WISE 0855-0714 is detected by SPHEREx and seen moving.

Run:  SPHEREX_CACHE_DIR=<cache> .venv/bin/python scripts/verify_wise0855.py

Works on the cached cutouts only (no SPHEREx download). What it does, all on native pixels:
  1. Star image width and flux scale of each detector from bright field stars (Gaia positions,
     AllWISE W2 fluxes).
  2. Forced two-source fit per visit and detector: one source at WISE 0855's predicted place, one
     at the Gaia star beside it (DR3 5756956644387831296). Gives each one's flux and error.
  3. The same fit at blank places in the same exposures: the real noise, and what chance gives.
  4. Flux against wavelength for both objects (0.75 to 5 microns).
  5. Position of the moving source per visit with the star's light removed, and its motion.
  6. An "empty place" test: is anything left where the object was in an earlier visit?
  7. Catalogue values for both objects, and CatWISE2020's own 2015 position against the prediction.
  8. The backend's own stack and centroid fit, at the target and at blank places, for comparison.
Writes figures to docs/verification/ and all numbers to scripts/out/verify/wise0855.json.
Outside catalogues (AllWISE, 2MASS through VizieR; CatWISE2020 through IRSA Gator) are asked once
and kept in scripts/out/verify/. If one cannot be reached the script says so and skips that part.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import verify_common as vc
import verify_fit as vf
import verify_plot as vp

OUT = ROOT / "scripts" / "out" / "verify"
OUT.mkdir(parents=True, exist_ok=True)

# Cutout centre = the backend's resolved position for 2026.0 (what the cache is keyed on).
RA0, DEC0 = 133.759765, -7.242182
# WISE 0855: SIMBAD's entry (Kirkpatrick et al. 2021), position for epoch 2000.0.
W = {"ra": 133.81890825, "dec": -7.247048, "epoch": 2000.0, "pmra": -8123.7, "pmdec": 673.2, "parallax": 439.0}
# The Gaia star beside the track: DR3 5756956644387831296 (VizieR I/355, epoch 2016.0).
STAR = {"ra": 133.75818250494, "dec": -7.24115590697, "epoch": 2016.0, "pmra": -6.188, "pmdec": 1.931,
        "parallax": 0.2859, "G": 16.31}
DETECTORS = (1, 2, 3, 4, 5, 6)


def w_pos(mjd: float) -> tuple[float, float]:
    return vc.apparent_position(W["ra"], W["dec"], W["epoch"], W["pmra"], W["pmdec"], W["parallax"], mjd)


def s_pos(mjd: float) -> tuple[float, float]:
    return vc.apparent_position(STAR["ra"], STAR["dec"], STAR["epoch"], STAR["pmra"], STAR["pmdec"],
                                STAR["parallax"], mjd)


def centre_wave(c: dict) -> float:
    """Wavelength at the middle of a cutout (microns)."""
    return float(c["wave"][c["wave"].shape[0] // 2, c["wave"].shape[1] // 2])


def fixed_pos(ra: float, dec: float):
    return lambda mjd: (ra, dec)


def shifted(fn, east: float, north: float):
    def f(mjd):
        return vc.shift_radec(*fn(mjd), east, north)
    return f


def catalogues() -> dict:
    """AllWISE and 2MASS around the field (VizieR), CatWISE2020 (IRSA Gator). None where unreachable."""
    cat: dict = {}
    cat["allwise"] = vc.vizier("II/328/allwise", RA0, DEC0, 330,
                               "AllWISE,RAJ2000,DEJ2000,W1mag,e_W1mag,W2mag,e_W2mag,ccf,ex,qph",
                               save_as=OUT / "wise0855_allwise.json")
    cat["twomass"] = vc.vizier("II/246/out", RA0, DEC0, 60, "2MASS,RAJ2000,DEJ2000,Jmag,e_Jmag,Hmag,e_Hmag,Kmag,e_Kmag",
                               save_as=OUT / "wise0855_2mass.json")
    cat["gaia"] = vc.vizier("I/355/gaiadr3", RA0, DEC0, 330,
                            "Source,RA_ICRS,DE_ICRS,Plx,pmRA,pmDE,Gmag,BP-RP,Teff", save_as=OUT / "wise0855_gaia.json")
    saved = OUT / "wise0855_catwise.json"
    if saved.exists():
        cat["catwise"] = json.loads(saved.read_text())
    else:
        r = vc.http_get("https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query",
                        {"catalog": "catwise_2020", "spatial": "cone", "radius": 150, "radunits": "arcsec",
                         "objstr": "133.7730 -7.2435", "outfmt": 1,
                         "selcols": "source_name,ra,dec,ra_pm,dec_pm,meanobsmjd,w1mpro_pm,w1sigmpro_pm,w2mpro_pm,"
                                    "w2sigmpro_pm,pmra,sigpmra,pmdec,sigpmdec,w1snr_pm,w2snr_pm"}, tries=2, timeout=120)
        rows, cols = [], None
        for ln in (r.text.splitlines() if r is not None else []):
            if ln.startswith("|") and cols is None:
                cols = [c.strip() for c in ln.strip().strip("|").split("|")]
            elif cols and not ln.startswith(("\\", "|")) and ln.strip():
                rows.append(dict(zip(cols, ln.split(), strict=False)))
        cat["catwise"] = rows or None
        if rows:
            saved.write_text(json.dumps(rows))
    for k, v in cat.items():
        print(f"  {k}: {'not reachable' if v is None else f'{len(v)} rows'}")
    return cat


def field_stars(cat: dict) -> list[dict]:
    """Isolated AllWISE stars with a Gaia position, for the star-image width and the flux scale."""
    if not cat["allwise"] or not cat["gaia"]:
        return []
    stars = []
    for r in cat["allwise"]:
        w2, e2 = vc.num(r["W2mag"]), vc.num(r["e_W2mag"])
        if w2 is None or e2 is None or e2 > 0.12 or r["ex"] != "0":
            continue
        ra, dec = float(r["RAJ2000"]), float(r["DEJ2000"])
        if np.hypot(*vc.offset_arcsec(RA0, DEC0, ra, dec)) > 215:      # must be inside every cutout
            continue
        sep, g = min(((float(np.hypot(*vc.offset_arcsec(ra, dec, float(q["RA_ICRS"]), float(q["DE_ICRS"])))), q)
                      for q in cat["gaia"]), key=lambda t: t[0])
        if sep > 1.5:
            continue
        near = [q for q in cat["allwise"] if q is not r and (vc.num(q["W2mag"]) or 99) < w2 + 2.5
                and np.hypot(*vc.offset_arcsec(ra, dec, float(q["RAJ2000"]), float(q["DEJ2000"]))) < 22]
        if near:
            continue
        stars.append({"name": r["AllWISE"], "w1": vc.num(r["W1mag"]), "w2": w2, "e_w2": e2,
                      "ra": float(g["RA_ICRS"]), "dec": float(g["DE_ICRS"]), "pmra": vc.num(g["pmRA"]) or 0.0,
                      "pmdec": vc.num(g["pmDE"]) or 0.0, "parallax": max(vc.num(g["Plx"]) or 0.0, 0.0),
                      "G": vc.num(g["Gmag"])})
    return stars


def star_fn(s: dict):
    return lambda mjd: vc.apparent_position(s["ra"], s["dec"], 2016.0, s["pmra"], s["pmdec"], s["parallax"], mjd)


def psf_width(cuts: list[dict], stars: list[dict]) -> tuple[float, list[dict]]:
    """Median fitted width (pixels) of bright field stars in one detector, and the individual fits."""
    fits = []
    for c in cuts:
        for s in stars:
            if s["w2"] > 12.8:
                continue
            f = vf.fit_star(c, *star_fn(s)(c["mjd"]))
            if f is not None and f["flux"] > 0:
                fits.append({**f, "star": s["name"]})
    if len(fits) < 10:
        return 0.48, fits
    return float(np.median([f["sigma_px"] for f in fits])), fits


def blank_places(cat: dict, step: float = 22.0, reach: float = 190.0) -> list[tuple[float, float]]:
    """Sky positions with no catalogued infrared source nearby, for the noise test."""
    known = []
    for r in cat["allwise"] or []:
        w1, w2 = vc.num(r["W1mag"]) or 99, vc.num(r["W2mag"]) or 99
        if w1 < 17.0 or w2 < 16.5:
            known.append((float(r["RAJ2000"]), float(r["DEJ2000"]), min(w1, w2)))
    for r in cat["catwise"] or []:
        w1, w2 = vc.num(r["w1mpro_pm"]) or 99, vc.num(r["w2mpro_pm"]) or 99
        if w1 < 17.0 or w2 < 16.5:
            known.append((float(r["ra"]), float(r["dec"]), min(w1, w2)))
    # WISE 0855's own 2025-26 track and the star are not blank either.
    for mjd in (60800.0, 60995.0, 61160.0):
        known.append((*w_pos(mjd), 13.9))
    out = []
    offs = np.arange(-reach, reach + 1, step)
    for dn in offs:
        for de in offs:
            ra, dec = vc.shift_radec(RA0, DEC0, float(de), float(dn))
            ok = True
            for kra, kdec, mag in known:
                d = np.hypot(*vc.offset_arcsec(ra, dec, kra, kdec))
                if d < (45.0 if mag < 11.5 else 28.0 if mag < 13.5 else 16.0):
                    ok = False
                    break
            if ok:
                out.append((ra, dec))
    return out


def robust_sigma(x: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def fit_offset(cuts_by_det: dict[int, list[dict]], sigma: dict[int, float], star_flux: dict[int, float],
               start=(0.0, 0.0)) -> dict | None:
    """Offset (east, north, arcsec) of the moving source from its predicted place in one visit.

    All exposures of the detectors given are fitted together; the source has one flux per
    detector; the Gaia star is held at its own place with the flux measured in the other visits.
    """
    sets = [(d, c) for d, c in cuts_by_det.items() if c]

    def model(off):
        chi2, dof, fluxes, errs = 0.0, 0, {}, {}
        res = []
        for det, cuts in sets:
            # Region centred on the predicted place (source 0, flux fixed to zero), so the pixels
            # used do not change while the trial position moves.
            r = vf.joint_fit(cuts, [w_pos, shifted(w_pos, off[0], off[1]), s_pos], sigma[det],
                             fixed={0: 0.0, 2: star_flux[det]})
            if r is None:
                continue
            chi2 += r["chi2"]
            dof += r["dof"]
            fluxes[det], errs[det] = float(r["flux"][1]), float(r["err"][1])
            res.append(r)
        return chi2, dof, fluxes, errs

    grid = np.arange(-6.0, 6.01, 1.0)
    best = min(((model((e, n))[0], e, n) for e in grid for n in grid), key=lambda t: t[0])
    cur = np.array([best[1], best[2]]) if start == (0.0, 0.0) else np.array(start)
    step = 0.5
    cur_chi = model(cur)[0]
    while step > 0.02:                                   # simple pattern search: robust, no derivatives
        moved = False
        for d in ((step, 0), (-step, 0), (0, step), (0, -step)):
            trial = cur + np.array(d)
            c = model(trial)[0]
            if c < cur_chi - 1e-9:
                cur, cur_chi, moved = trial, c, True
        if not moved:
            step /= 2
    chi2, dof, fluxes, errs = model(cur)
    scale = max(chi2 / max(dof - 2, 1), 1.0)
    # Curvature of chi-square around the minimum gives the 1-sigma errors.
    h = 0.4
    cxx = (model(cur + [h, 0])[0] - 2 * chi2 + model(cur - [h, 0])[0]) / h ** 2
    cyy = (model(cur + [0, h])[0] - 2 * chi2 + model(cur - [0, h])[0]) / h ** 2
    cxy = (model(cur + [h, h])[0] - model(cur + [h, -h])[0] - model(cur + [-h, h])[0]
           + model(cur - [h, h])[0]) / (4 * h * h)
    hess = 0.5 * np.array([[cxx, cxy], [cxy, cyy]]) / scale
    try:
        cov = np.linalg.inv(hess)
        err = (float(np.sqrt(max(cov[0, 0], 0))), float(np.sqrt(max(cov[1, 1], 0))))
    except np.linalg.LinAlgError:
        err = (float("nan"), float("nan"))
    null = sum(vf.joint_fit(c, [w_pos, s_pos], sigma[d], fixed={0: 0.0, 1: star_flux[d]})["chi2"] for d, c in sets)
    at_pred = model((0.0, 0.0))[0]
    mjd = float(np.mean([c["mjd"] for _, cuts in sets for c in cuts]))
    return {"east": float(cur[0]), "north": float(cur[1]), "east_err": err[0], "north_err": err[1],
            "chi2": chi2, "dof": dof, "chi2_no_source": float(null), "chi2_at_prediction": float(at_pred),
            "flux": fluxes, "flux_err": errs, "mjd": mjd, "n_exp": sum(len(c) for _, c in sets)}


def main() -> None:
    print("Catalogues")
    cat = catalogues()
    stars = field_stars(cat)
    print(f"  {len(stars)} isolated AllWISE stars with a Gaia position inside every cutout")
    starts = vc.epoch_edges(RA0, DEC0)
    print("Visits start:", [vc.iso(s) for s in starts])

    cuts = {d: [vc.read_cutout(p) for p in vc.list_cutouts(RA0, DEC0, d)] for d in DETECTORS}
    by = {d: {ep: [c for c in cuts[d] if vc.epoch_of(c["mjd"], starts) == ep] for ep in (1, 2, 3)} for d in DETECTORS}
    summary: dict = {"visits": {}, "detectors": {}, "catalogue": {}}
    for ep in (1, 2, 3):
        mj = [c["mjd"] for d in DETECTORS for c in by[d][ep]]
        summary["visits"][ep] = {"start": vc.iso(min(mj)), "end": vc.iso(max(mj)),
                                 "n_exposures": {d: len(by[d][ep]) for d in DETECTORS}}
        mid = float(np.mean([c["mjd"] for c in by[6][ep]]))
        se, sn = vc.offset_arcsec(*w_pos(mid), *s_pos(mid))
        summary["visits"][ep]["star_offset_from_prediction"] = [float(se), float(sn)]
        print(f"  visit {ep}: {vc.iso(min(mj))} to {vc.iso(max(mj))}; exposures per detector "
              f"{summary['visits'][ep]['n_exposures']}; star is {np.hypot(se, sn):.1f} arcsec from the predicted place "
              f"(east {se:+.1f}, north {sn:+.1f})")

    # ---- 1. star image width and flux scale -------------------------------------------------
    print("\n1. Star image width and flux scale (bright field stars)")
    sigma: dict[int, float] = {}
    for d in DETECTORS:
        sigma[d], fits = psf_width(cuts[d], stars)
        de = np.array([f["east"] for f in fits])
        dn = np.array([f["north"] for f in fits])
        summary["detectors"][d] = {"sigma_px": sigma[d], "fwhm_arcsec": sigma[d] * 2.3548 * 6.15,
                                   "n_star_fits": len(fits),
                                   "astrometry_mean": [float(de.mean()), float(dn.mean())] if len(fits) else None,
                                   "astrometry_sd": [float(de.std()), float(dn.std())] if len(fits) else None}
        if len(fits):
            print(f"  D{d}: width sigma {sigma[d]:.3f} px (FWHM {sigma[d] * 2.3548 * 6.15:.1f} arcsec before pixel "
                  f"smoothing), "
                  f"{len(fits)} star fits; star positions minus Gaia: east {de.mean():+.2f} (sd {de.std():.2f}), "
                  f"north {dn.mean():+.2f} (sd {dn.std():.2f}) arcsec")

    ladder = []
    for s in stars:
        r6 = vf.joint_fit(cuts[6], [star_fn(s)], sigma[6])
        r5 = vf.joint_fit(cuts[5], [star_fn(s)], sigma[5])
        if r6 is None or r5 is None:
            continue
        ladder.append({"name": s["name"], "w1": s["w1"], "w2": s["w2"],
                       "w2_mjy": vc.vega_to_mjy(s["w2"], vc.ZERO_JY["W2"]),
                       "d6": float(r6["flux"][0]), "d6_err": float(r6["err"][0]),
                       "d5": float(r5["flux"][0]), "d5_err": float(r5["err"][0])})
    if ladder:
        ratio = np.array([row["d6"] / row["w2_mjy"] for row in ladder])
        bright = np.array([row["w2"] < 14.0 for row in ladder])
        print(f"  D6 forced flux / AllWISE W2 flux for {len(ladder)} field stars: median {np.median(ratio):.2f} "
              f"(W2 < 14: {np.median(ratio[bright]):.2f}, n={bright.sum()}; fainter: {np.median(ratio[~bright]):.2f}, "
              f"n={(~bright).sum()})")
        summary["flux_scale"] = {"n": len(ladder), "median_d6_over_w2": float(np.median(ratio)),
                                 "median_bright": float(np.median(ratio[bright])) if bright.any() else None,
                                 "median_faint": float(np.median(ratio[~bright])) if (~bright).any() else None}
    summary["ladder"] = ladder

    # ---- 2. forced two-source fit --------------------------------------------------------------
    print("\n2. Forced fit: flux at WISE 0855's predicted place and at the Gaia star (mJy)")
    forced: dict = {}
    for d in DETECTORS:
        forced[d] = {}
        for ep in (1, 2, 3):
            sub = by[d][ep]
            res = vf.joint_fit(sub, [w_pos, s_pos], sigma[d]) if sub else None
            if res is None:
                continue
            f, e = res["flux"], res["err"]
            one = vf.joint_fit(sub, [w_pos], sigma[d])
            forced[d][ep] = {"n_exp": res["n_exp"], "w": float(f[0]), "w_err": float(e[0]), "star": float(f[1]),
                             "star_err": float(e[1]), "corr": float(res["cov"][0, 1] / (e[0] * e[1])),
                             "chi2_dof": res["chi2"] / res["dof"], "single": float(one["flux"][0]),
                             "single_err": float(one["err"][0]), "mjd": res["mjd"],
                             "wave": [float(min(centre_wave(c) for c in sub)), float(max(centre_wave(c) for c in sub))]}
            print(f"  D{d} visit {ep} ({res['n_exp']:2d} exp): WISE 0855 {f[0]:+.3f} +- {e[0]:.3f} (formal S/N "
                  f"{f[0] / e[0]:5.1f}); "
                  f"star {f[1]:+.3f} +- {e[1]:.3f}; correlation {forced[d][ep]['corr']:+.2f}; chi2/dof "
                  f"{res['chi2'] / res['dof']:.2f}; "
                  f"if the star is ignored: {one['flux'][0]:+.3f}")
    # The star's flux per detector from visits 1 and 2, where it is well separated (8 to 11 arcsec).
    star_flux = {}
    for d in DETECTORS:
        v = [(forced[d][ep]["star"], forced[d][ep]["star_err"]) for ep in (1, 2) if ep in forced[d]]
        wts = np.array([1 / e ** 2 for _, e in v])
        star_flux[d] = float(np.sum(wts * np.array([f for f, _ in v])) / wts.sum())
    print("  star flux from visits 1+2 (mJy):", {d: round(v, 3) for d, v in star_flux.items()})
    for d in (5, 6):
        for ep in (3,):
            res = vf.joint_fit(by[d][ep], [w_pos, s_pos], sigma[d], fixed={1: star_flux[d]})
            forced[d][ep]["w_star_fixed"] = float(res["flux"][0])
            forced[d][ep]["w_star_fixed_err"] = float(res["err"][0])
            share = star_flux[d] / (star_flux[d] + res["flux"][0])
            forced[d][ep]["star_share"] = float(share)
            print(f"  D{d} visit 3 with the star held at {star_flux[d]:.3f}: WISE 0855 {res['flux'][0]:.3f} +- "
                  f"{res['err'][0]:.3f}; "
                  f"star's share of the blended light {100 * share:.0f} per cent")
    summary["forced"] = forced
    summary["star_flux"] = star_flux

    # ---- 3. blank places: the real noise ----------------------------------------------------
    print("\n3. The same fit at blank places (no catalogued source within 16 arcsec)")
    blanks = blank_places(cat) if cat["allwise"] else []
    print(f"  {len(blanks)} blank places")
    noise: dict = {}
    for d in (5, 6):
        noise[d] = {}
        for ep in (1, 2, 3):
            vals, errs = [], []
            for ra, dec in blanks:
                r = vf.joint_fit(by[d][ep], [fixed_pos(ra, dec)], sigma[d])
                if r is not None and r["n_exp"] == len(by[d][ep]):
                    vals.append(r["flux"][0])
                    errs.append(r["err"][0])
            vals, errs = np.array(vals), np.array(errs)
            if len(vals) < 20:
                continue
            sd = robust_sigma(vals)
            f = forced[d][ep]
            noise[d][ep] = {"n": len(vals), "median": float(np.median(vals)), "robust_sd": sd, "sd": float(vals.std()),
                            "formal": float(np.median(errs)), "max": float(vals.max()), "min": float(vals.min()),
                            "values": [float(v) for v in vals], "snr_empirical": f["w"] / max(sd, f["w_err"]),
                            "n_above_target": int((vals >= f["w"]).sum())}
            print(f"  D{d} visit {ep}: {len(vals)} places; flux median {np.median(vals):+.3f}, scatter {sd:.3f} "
                  f"(robust) / "
                  f"{vals.std():.3f} (plain) mJy against formal {np.median(errs):.3f}; largest {vals.max():+.3f}; "
                  f"target {f['w']:+.3f} -> S/N {noise[d][ep]['snr_empirical']:.1f}; blank places as bright: "
                  f"{noise[d][ep]['n_above_target']}")
    summary["noise"] = noise

    # ---- 4. flux against wavelength -------------------------------------------------------------
    print("\n4. Flux against wavelength (all visits together, per-exposure fits averaged in bins)")
    spectrum = []
    for d in DETECTORS:
        pe = vf.per_exposure(cuts[d], [w_pos, s_pos], sigma[d])
        waves = np.array([p["wave"] for p in pe])
        edges = np.linspace(waves.min() - 1e-6, waves.max() + 1e-6, 5 if d < 5 else 6)
        for a, b in zip(edges[:-1], edges[1:], strict=True):
            sel = [p for p in pe if a <= p["wave"] < b]
            if len(sel) < 3:
                continue
            row = {"detector": d, "wave": float(np.mean([p["wave"] for p in sel])), "lo": float(a), "hi": float(b),
                   "n": len(sel)}
            for k, name in ((0, "w"), (1, "star")):
                f = np.array([p["flux"][k] for p in sel])
                e = np.array([p["err"][k] for p in sel])
                wts = 1 / e ** 2
                row[name], row[f"{name}_err"] = float(np.sum(wts * f) / wts.sum()), float(1 / np.sqrt(wts.sum()))
            spectrum.append(row)
            print(f"  D{d} {a:.2f}-{b:.2f} um ({len(sel):2d} exp): at WISE 0855's place {row['w']:+.3f} +- "
                  f"{row['w_err']:.3f}; "
                  f"star {row['star']:+.3f} +- {row['star_err']:.3f}")
    summary["spectrum"] = spectrum

    # ---- 5. where is the moving source, and how far did it move --------------------------------
    print("\n5. Position of the moving source, star removed (offset from the predicted place, arcsec)")
    positions: dict = {}
    for label, dets in (("D6", (6,)), ("D5", (5,)), ("D5+D6", (5, 6))):
        positions[label] = {}
        for ep in (1, 2, 3):
            r = fit_offset({d: by[d][ep] for d in dets}, sigma, star_flux)
            positions[label][ep] = r
            print(f"  {label:5s} visit {ep} ({r['n_exp']:2d} exp): east {r['east']:+.2f} +- {r['east_err']:.2f}, "
                  f"north {r['north']:+.2f} "
                  f"+- {r['north_err']:.2f}; chi2 drops by {r['chi2_no_source'] - r['chi2']:.0f} when the source is "
                  f"added "
                  f"({r['chi2_no_source'] - r['chi2_at_prediction']:.0f} at exactly the predicted place)")
    summary["positions"] = positions
    # Motion between visit 1 and visit 3 (D5+D6), against the catalogue motion.
    p1, p3 = positions["D5+D6"][1], positions["D5+D6"][3]
    pred = vc.offset_arcsec(*w_pos(p1["mjd"]), *w_pos(p3["mjd"]))
    years = (p3["mjd"] - p1["mjd"]) / 365.25
    meas = (float(pred[0]) + p3["east"] - p1["east"], float(pred[1]) + p3["north"] - p1["north"])
    merr = (float(np.hypot(p1["east_err"], p3["east_err"])), float(np.hypot(p1["north_err"], p3["north_err"])))
    print(f"  visit 1 to 3 ({years:.3f} yr): measured move east {meas[0]:+.2f} +- {merr[0]:.2f}, north {meas[1]:+.2f} "
          f"+- {merr[1]:.2f}; "
          f"predicted {pred[0]:+.2f}, {pred[1]:+.2f} (proper motion plus parallax)")
    summary["motion_1_to_3"] = {"years": years, "measured": meas, "err": merr,
                                "predicted": [float(pred[0]), float(pred[1])]}
    # Straight-line fit through the three visits, parallax taken from the catalogue.
    t = np.array([(positions["D5+D6"][ep]["mjd"] - 51544.5) / 365.25 + 2000.0 for ep in (1, 2, 3)])
    fit = {}
    for axis, key in (("east", "pmra"), ("north", "pmdec")):
        off = np.array([positions["D5+D6"][ep][axis] for ep in (1, 2, 3)])
        err = np.array([positions["D5+D6"][ep][f"{axis}_err"] for ep in (1, 2, 3)])
        a = np.vstack([np.ones(3), t - t.mean()]).T / err[:, None]
        cov = np.linalg.inv(a.T @ a)
        p = cov @ (a.T @ (off / err))
        fit[axis] = {"pm": W[key] / 1000.0 + float(p[1]), "pm_err": float(np.sqrt(cov[1, 1])),
                     "offset": float(p[0]), "offset_err": float(np.sqrt(cov[0, 0])),
                     "chi2": float(np.sum(((off - a @ p * err) / err) ** 2))}
        print(f"  motion {axis}: {fit[axis]['pm']:+.2f} +- {fit[axis]['pm_err']:.2f} arcsec/yr (catalogue "
              f"{W[key] / 1000:+.2f}); "
              f"mean offset from the prediction {fit[axis]['offset']:+.2f} +- {fit[axis]['offset_err']:.2f} arcsec")
    summary["motion_fit"] = fit

    # ---- 6. is the place it left empty? ---------------------------------------------------------
    print("\n6. Empty-place test: three sources fitted in each visit (D5 and D6): where the object was predicted "
          "in visit 1, where in visit 3, and the star")
    m1 = float(np.mean([c["mjd"] for d in (5, 6) for c in by[d][1]]))
    m3 = float(np.mean([c["mjd"] for d in (5, 6) for c in by[d][3]]))
    place1, place3 = fixed_pos(*w_pos(m1)), fixed_pos(*w_pos(m3))
    sep13 = float(np.hypot(*vc.offset_arcsec(*w_pos(m1), *w_pos(m3))))
    print(f"  the two places are {sep13:.1f} arcsec apart")
    empty: dict = {"separation": sep13}
    for d in (5, 6):
        empty[d] = {}
        for ep in (1, 3):
            r = vf.joint_fit(by[d][ep], [place1, place3, s_pos], sigma[d], fixed={2: star_flux[d]})
            empty[d][ep] = {"at_place1": float(r["flux"][0]), "at_place1_err": float(r["err"][0]),
                            "at_place3": float(r["flux"][1]), "at_place3_err": float(r["err"][1])}
            print(f"  D{d} visit {ep}: flux at the visit-1 place {r['flux'][0]:+.3f} +- {r['err'][0]:.3f}; "
                  f"at the visit-3 place {r['flux'][1]:+.3f} +- {r['err'][1]:.3f} mJy")
    summary["empty_place"] = empty

    # Static-source alternative: one source that does not move, fitted to visits 1 and 3 together.
    for d in (5, 6):
        both = by[d][1] + by[d][3]
        moving = vf.joint_fit(both, [w_pos, s_pos], sigma[d], fixed={1: star_flux[d]})
        best = None
        for de in np.arange(-10, 4.01, 1.0):
            for dn in np.arange(-4, 4.01, 1.0):
                r = vf.joint_fit(both, [fixed_pos(*w_pos(m1)), fixed_pos(*vc.shift_radec(*w_pos(m1), de, dn)), s_pos],
                                 sigma[d], fixed={0: 0.0, 2: star_flux[d]})
                if best is None or r["chi2"] < best[0]:
                    best = (r["chi2"], de, dn)
        # the region differs slightly (centred on the visit-1 place), so compare like with like
        mv = vf.joint_fit(both, [fixed_pos(*w_pos(m1)), w_pos, s_pos], sigma[d], fixed={0: 0.0, 2: star_flux[d]})
        empty[d]["static_vs_moving"] = {"chi2_static_best": float(best[0]), "chi2_moving": float(mv["chi2"]),
                                        "static_offset": [float(best[1]), float(best[2])], "dof": mv["dof"]}
        print(f"  D{d} visits 1+3: best single source that does NOT move: chi2 {best[0]:.0f} (at east {best[1]:+.0f}, "
              f"north "
              f"{best[2]:+.0f} of the visit-1 place); source moving as catalogued: chi2 {mv['chi2']:.0f}; "
              f"difference {best[0] - mv['chi2']:+.0f} for {mv['dof']} degrees of freedom; flux "
              f"{moving['flux'][0]:.3f}")

    # ---- catalogue values used in the write-up ----------------------------------------------------
    print("\n7. Catalogue values")
    if cat["catwise"]:
        # Where the SIMBAD position and motion put the object at CatWISE's reference date (MJD 57170),
        # without parallax: an outside check of the prediction ten years before the SPHEREx visits.
        eph = vc.apparent_position(W["ra"], W["dec"], W["epoch"], W["pmra"], W["pmdec"], 0.0, 57170.0)
        cols = ("source_name", "w2mpro_pm", "w2sigmpro_pm", "pmra", "pmdec", "ra_pm", "dec_pm")
        for r in cat["catwise"]:
            if abs(float(r["pmra"])) > 5:
                de, dn = vc.offset_arcsec(eph[0], eph[1], float(r["ra_pm"]), float(r["dec_pm"]))
                print(f"  CatWISE2020 {r['source_name']}: W2 {r['w2mpro_pm']} +- {r['w2sigmpro_pm']}, motion "
                      f"({r['pmra']}, {r['pmdec']}) arcsec/yr; its position for 2015.4 is east {de:+.2f}, north "
                      f"{dn:+.2f} arcsec from where the SIMBAD motion puts WISE 0855 then")
                summary["catalogue"].setdefault("catwise_w0855", []).append(
                    {**{k: r[k] for k in cols}, "offset_from_ephemeris": [float(de), float(dn)]})
            near = [np.hypot(*vc.offset_arcsec(*w_pos(m), float(r["ra"]), float(r["dec"])))
                    for m in (60800.0, 60995.0, 61160.0)]
            if min(near) < 6 and abs(float(r["pmra"])) < 5:
                print(f"  CatWISE2020 source within 6 arcsec of a predicted place: {r['source_name']}, W1 "
                      f"{r['w1mpro_pm']}, W2 {r['w2mpro_pm']} (error {r['w2sigmpro_pm']}), {min(near):.1f} arcsec "
                      f"away at closest")
                summary["catalogue"].setdefault("catwise_near_track", []).append(
                    {**{k: r[k] for k in ("source_name", "w1mpro_pm", "w2mpro_pm", "w2sigmpro_pm")},
                     "closest_arcsec": float(min(near))})
            if np.hypot(*vc.offset_arcsec(STAR["ra"], STAR["dec"], float(r["ra"]), float(r["dec"]))) < 2:
                summary["catalogue"]["catwise_star"] = {k: r[k] for k in ("source_name", "w1mpro_pm", "w1sigmpro_pm",
                                                                         "w2mpro_pm", "w2sigmpro_pm")}
                print(f"  CatWISE2020 star {r['source_name']}: W1 {r['w1mpro_pm']}, W2 {r['w2mpro_pm']} +- "
                      f"{r['w2sigmpro_pm']}")
    if cat["allwise"]:
        for r in cat["allwise"]:
            if np.hypot(*vc.offset_arcsec(STAR["ra"], STAR["dec"], float(r["RAJ2000"]), float(r["DEJ2000"]))) < 2:
                summary["catalogue"]["allwise_star"] = r
                print(f"  AllWISE star {r['AllWISE']}: W1 {r['W1mag']} +- {r['e_W1mag']}, W2 {r['W2mag']} +- "
                      f"{r['e_W2mag']}")
    if cat["twomass"]:
        for r in cat["twomass"]:
            if np.hypot(*vc.offset_arcsec(STAR["ra"], STAR["dec"], float(r["RAJ2000"]), float(r["DEJ2000"]))) < 2:
                summary["catalogue"]["twomass_star"] = r
                print(f"  2MASS star {r['2MASS']}: J {r['Jmag']}, H {r['Hmag']}, Ks {r['Kmag']}")

    summary["backend"] = backend_check(by, blanks)
    (OUT / "wise0855.json").write_text(json.dumps(summary, indent=1, default=float))
    print(f"\nwrote {OUT / 'wise0855.json'}")
    figures(by, sigma, summary, cat)


def backend_check(by: dict, blanks: list[tuple[float, float]]) -> dict:
    """What the backend's own stack and centroid fit report, at the target and at blank places.

    Uses pipeline.prepare_cutout, stack and fit_source directly (nothing is written to the cache).
    fit_source starts from the brightest pixel within 14 arcsec of the place it is given, so on
    empty sky it locks onto the highest noise peak: this shows how often that looks like a source.
    """
    from backend import astrometry, pipeline

    print("\n8. The backend's own stack and centroid fit (detector 6, field 0.1 degree)")
    grid, n = pipeline.make_grid(RA0, DEC0, 0.1)
    target = {"ra": RA0, "dec": DEC0, "pmra": W["pmra"], "pmdec": W["pmdec"], "parallax": W["parallax"],
              "ref_epoch": 2026.0}
    out: dict = {}
    for ep in (1, 2, 3):
        items = [pipeline.prepare_cutout(c["path"], grid, n, RA0, DEC0) for c in by[6][ep]]
        items = [it for it in items if it is not None]
        st = pipeline.stack(items)
        mjd = float(np.average([it["mjd"] for it in items], weights=[it["weight"] for it in items]))
        pra, pdec = astrometry.position_at(target, mjd)
        x0, y0 = [float(v) for v in grid.all_world2pix(pra, pdec, 0)]
        fit = pipeline.fit_source(st["image"], x0, y0)
        east = -(fit["x"] - x0) * pipeline.GRID_ARCSEC
        north = (fit["y"] - y0) * pipeline.GRID_ARCSEC
        snrs, seps = [], []
        for ra, dec in blanks:
            bx, by_ = [float(v) for v in grid.all_world2pix(ra, dec, 0)]
            f = pipeline.fit_source(st["image"], bx, by_)
            if f is None or f["snr"] is None:
                continue
            snrs.append(f["snr"])
            seps.append(float(np.hypot(f["x"] - bx, f["y"] - by_) * pipeline.GRID_ARCSEC))
        snrs, seps = np.array(snrs), np.array(seps)
        sep_t = float(np.hypot(east, north))
        as_good = int(((snrs >= fit["snr"]) & (seps <= max(sep_t, 1.3))).sum())
        out[ep] = {"east": float(east), "north": float(north), "snr": fit["snr"],
                   "fwhm": fit["sigma_px"] * 2.3548 * 2.0,
                   "n_blank": len(snrs), "blank_snr_median": float(np.median(snrs)),
                   "blank_snr_ge_target": int((snrs >= fit["snr"]).sum()), "blank_snr_ge_5": int((snrs >= 5).sum()),
                   "blank_within_1p3": int((seps <= 1.3).sum()), "blank_as_good": as_good}
        print(f"  visit {ep}: centroid minus prediction east {east:+.1f}, north {north:+.1f} arcsec; its 'snr' "
              f"{fit['snr']:.1f}. "
              f"At {len(snrs)} blank places the same fit returns snr median {np.median(snrs):.1f}, >= 5 in "
              f"{(snrs >= 5).sum()}, "
              f">= the target's in {(snrs >= fit['snr']).sum()}; centroid within 1.3 arcsec of the place asked for in "
              f"{(seps <= 1.3).sum()}; both as good as the target in {as_good}")
    return out


def figures(by: dict, sigma: dict, summary: dict, cat: dict) -> None:
    print("\nFigures")
    # --- pictures: plain stacks per visit, D6 / D5 / D3 --------------------------------------------
    half, step, scale = 36.0, 2.0, 7
    n = int(round(2 * half / step)) + 1
    rows = []
    for det, vmax in ((6, 0.10), (5, 0.10), (3, 0.10)):
        tiles = []
        for ep in (1, 2, 3):
            cuts = by[det][ep]
            mid = float(np.mean([c["mjd"] for c in cuts]))
            centre = fixed_pos(*s_pos(mid))                 # the star stays at the centre of every panel
            img = vf.stack_image(cuts, centre, half, step)
            de, dn = vc.offset_arcsec(*s_pos(mid), *w_pos(mid))
            marks = [{"x": (n - 1) / 2 - de / step, "y": (n - 1) / 2 + dn / step, "kind": "circle", "r": 3.2,
                      "color": (255, 220, 0)},
                     {"x": (n - 1) / 2, "y": (n - 1) / 2, "kind": "plus", "r": 3.6, "color": (0, 220, 255)}]
            tiles.append(vp.image_panel(img, -0.02, vmax, scale, title=f"D{det}, visit {ep}, {len(cuts)} exposures",
                                        marks=marks))
        rows.append(vp.stack_horizontal(tiles, pad=8))
    sheet = vp.stack_vertical(rows, pad=8)
    v = summary["visits"]
    cap = vp.caption_block(sheet.width, [
        "Stacked SPHEREx pictures, 74 arcsec across, north up, east left, one grey scale (-0.02 to 0.10 MJy/sr).",
        f"Columns: visit 1 ({v[1]['start']}), visit 2 ({v[2]['start']} to {v[2]['end'][5:]}), visit 3 "
        f"({v[3]['start']} to {v[3]['end'][5:]}).",
        "Rows: detector 6 (4.4-5.0 microns), detector 5 (3.8-4.4), detector 3 (1.6-2.4).",
        "Blue cross: the Gaia star, at the centre of every panel. Yellow circle: where WISE 0855 is predicted to be.",
        "The star is in every row. The source in the yellow circle is only in detectors 5 and 6, and it moves west."])
    vp.save(vp.stack_vertical([sheet, cap], pad=2), vc.DOCS / "wise0855_images.png")

    # --- spectrum ---------------------------------------------------------------------------------
    sp = summary["spectrum"]
    ch = vp.Chart(title="Flux against wavelength: the place WISE 0855 should be, and the Gaia star beside it",
                  xlabel="wavelength (microns)", ylabel="flux (mJy)", width=1100, height=430, legend_width=290,
                  ylim=(-0.15, 1.45))
    ch.hline(0.0, vp.GREY)
    ch.scatter([r["wave"] for r in sp], [r["star"] for r in sp], [r["star_err"] for r in sp], color=vp.BLUE,
               label="Gaia star (SPHEREx, this check)", marker="s", size=4)
    ch.scatter([r["wave"] for r in sp], [r["w"] for r in sp], [r["w_err"] for r in sp], color=vp.RED,
               label="at WISE 0855's predicted place (SPHEREx, this check)", size=5)
    c = summary["catalogue"]
    if "twomass_star" in c and "allwise_star" in c:
        tm, aw = c["twomass_star"], c["allwise_star"]
        xs = [vc.EFF_UM[b] for b in ("J", "H", "Ks", "W1", "W2")]
        ys = [vc.vega_to_mjy(float(tm["Jmag"]), vc.ZERO_JY["J"]), vc.vega_to_mjy(float(tm["Hmag"]), vc.ZERO_JY["H"]),
              vc.vega_to_mjy(float(tm["Kmag"]), vc.ZERO_JY["Ks"]), vc.vega_to_mjy(float(aw["W1mag"]), vc.ZERO_JY["W1"]),
              vc.vega_to_mjy(float(aw["W2mag"]), vc.ZERO_JY["W2"])]
        ch.scatter(xs, ys, color=vp.BLUE, label="Gaia star in 2MASS (J, H, Ks) and AllWISE (W1, W2)", marker="^",
                   hollow=True, size=7)
    if "catwise_w0855" in c:
        w2 = [float(r["w2mpro_pm"]) for r in c["catwise_w0855"]]
        ch.scatter([vc.EFF_UM["W2"]] * len(w2), [vc.vega_to_mjy(m, vc.ZERO_JY["W2"]) for m in w2], color=vp.RED,
                   label="WISE 0855 in CatWISE2020 (W2, 4.0-5.3 microns, 2010-2018)", marker="^", hollow=True, size=7)
    vp.save(ch.render(), vc.DOCS / "wise0855_spectrum.png")

    # --- track ------------------------------------------------------------------------------------
    pos = summary["positions"]
    ch = vp.Chart(title="Where the moving source is, measured from the Gaia star (arcsec). East is to the left, as on "
                        "the sky.",
                  xlabel="arcsec west of the Gaia star (negative: east of it)", ylabel="arcsec north of the star",
                  width=1100, height=430, legend_width=300, xlim=(-13.5, 2.5), ylim=(-7.5, 2.5))
    mj = np.linspace(60780, 61190, 200)
    track = [vc.offset_arcsec(*s_pos(m), *w_pos(m)) for m in mj]
    ch.line([-float(t[0]) for t in track], [float(t[1]) for t in track], color=vp.GREY,
            label="predicted path, May 2025 to May 2026 (catalogue motion + parallax)")
    for label, col, marker in (("D6", vp.RED, "o"), ("D5", vp.ORANGE, "s")):
        xs, ys, es, ex = [], [], [], []
        for ep in (1, 2, 3):
            p = pos[label][ep]
            base = vc.offset_arcsec(*s_pos(p["mjd"]), *w_pos(p["mjd"]))
            xs.append(-(float(base[0]) + p["east"]))
            ys.append(float(base[1]) + p["north"])
            es.append(p["north_err"])
            ex.append(p["east_err"])
        ch.scatter(xs, ys, es, color=col, label=f"measured in {label}, visits 1, 2, 3, star's light removed (bars: 1 "
                                                f"sigma)",
                   marker=marker, size=5, xerr=ex)
    bk = summary.get("backend") or {}
    if bk:
        bx, by_ = [], []
        for ep in (1, 2, 3):
            m = pos["D6"][ep]["mjd"]
            base = vc.offset_arcsec(*s_pos(m), *w_pos(m))
            bx.append(-(float(base[0]) + bk[ep]["east"]))
            by_.append(float(base[1]) + bk[ep]["north"])
        ch.scatter(bx, by_, color=vp.PURPLE, label="backend centroid (stack, star not removed), D6", marker="^",
                   hollow=True, size=6)
    px, py = [], []
    for ep in (1, 2, 3):
        m = pos["D5+D6"][ep]["mjd"]
        base = vc.offset_arcsec(*s_pos(m), *w_pos(m))
        px.append(-float(base[0]))
        py.append(float(base[1]))
        ch.note(-float(base[0]) - 0.3, float(base[1]) - 0.5, f"visit {ep}", vp.BLACK)
    ch.scatter(px, py, color=vp.BLACK, label="predicted place at each visit", marker="x", size=5)
    ch.scatter([0], [0], color=vp.BLUE, label="Gaia star DR3 5756956644387831296 (G = 16.3)", marker="^", size=7)
    vp.save(ch.render(), vc.DOCS / "wise0855_track.png")

    # --- flux ladder ------------------------------------------------------------------------------
    lad = summary.get("ladder") or []
    if lad:
        ch = vp.Chart(title="Detector 6 flux measured here against the AllWISE catalogue flux (4.6 microns)",
                      xlabel="AllWISE W2 flux (mJy)", ylabel="SPHEREx D6 flux (mJy)", width=1100, height=430,
                      legend_width=300, logx=True, logy=True, xlim=(0.05, 30), ylim=(0.05, 30))
        ch.line([0.05, 30], [0.05, 30], color=vp.GREY, label="equal")
        ch.scatter([r["w2_mjy"] for r in lad], [r["d6"] for r in lad], [r["d6_err"] for r in lad], color=vp.BLUE,
                   label=f"{len(lad)} isolated field stars (all visits)", size=4)
        f = summary["forced"]
        aw = summary["catalogue"].get("allwise_star")
        if aw:
            ch.scatter([vc.vega_to_mjy(float(aw["W2mag"]), vc.ZERO_JY["W2"])], [summary["star_flux"][6]],
                       color=vp.GREEN,
                       label="the Gaia star beside WISE 0855", marker="s", size=6)
        cw = summary["catalogue"].get("catwise_w0855")
        if cw:
            w2 = float(np.median([float(r["w2mpro_pm"]) for r in cw]))
            ch.scatter([vc.vega_to_mjy(w2, vc.ZERO_JY["W2"])], [f[6][2]["w"]], [f[6][2]["w_err"]], color=vp.RED,
                       label="WISE 0855 (visit 2; catalogue value is CatWISE2020 W2)", marker="^", size=7)
        vp.save(ch.render(), vc.DOCS / "wise0855_fluxscale.png")


if __name__ == "__main__":
    main()

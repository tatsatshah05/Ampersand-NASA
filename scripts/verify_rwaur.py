"""Independent check of claim 2: RW Aurigae changed brightness between the SPHEREx visits.

Run:  SPHEREX_CACHE_DIR=<cache> .venv/bin/python scripts/verify_rwaur.py

Works on the cached cutouts only. What it does:
  1. Own aperture photometry (3-pixel circle, sky from a 7-11 pixel ring) of RW Aur and of the
     comparison stars in the same exposures; own ring brightness (3.5-6.5 pixels) for saturated ones.
  2. Visit-to-visit ratios from pairs of exposures at the same wavelength (within 1.2 per cent),
     for RW Aur and for the comparison stars (which should stay at 1).
  3. Ring against aperture flux where both exist (is the ring a fair stand-in when saturated?).
  4. AAVSO observations for the same dates (V, R, I), fetched from AAVSO's VSX interface.
Writes figures to docs/verification/ and numbers to scripts/out/verify/rwaur.json.
RW Aur is a close pair (1.5 arcsec); SPHEREx and the AAVSO observers both measure the two together.
"""
import json
import sys
from collections import Counter, defaultdict
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

RA0, DEC0 = 76.956587, 30.401291          # cutout centre: the backend's resolved position for 2026.0
RW = {"ra": 76.956587, "dec": 30.401291, "epoch": 2026.0, "pmra": 7.23, "pmdec": -20.33, "parallax": 15.42}
MATCH = 0.012                              # two exposures count as "same wavelength" within 1.2 per cent
RING = (3.5, 6.5)
I_ZERO_JY = 2416.0                         # Cousins I zero point (Bessell et al. 1998), used for one sanity check only


def rw_pos(mjd: float) -> tuple[float, float]:
    return vc.apparent_position(RW["ra"], RW["dec"], RW["epoch"], RW["pmra"], RW["pmdec"], RW["parallax"], mjd)


def comparison_stars() -> list[dict]:
    gaia = vc.vizier("I/355/gaiadr3", RA0, DEC0, 300, "Source,RA_ICRS,DE_ICRS,Plx,pmRA,pmDE,Gmag,BP-RP,RUWE,VarFlag",
                     save_as=OUT / "rwaur_gaia.json")
    if gaia is None:
        return []
    out = []
    for g in gaia:
        gmag, r = vc.num(g["Gmag"]), float(g["_r"])
        if gmag is None or gmag > 13.0 or r < 30 or r > 200:
            continue
        out.append({"id": g["Source"], "ra": float(g["RA_ICRS"]), "dec": float(g["DE_ICRS"]),
                    "pmra": vc.num(g["pmRA"]) or 0.0,
                    "pmdec": vc.num(g["pmDE"]) or 0.0, "plx": max(vc.num(g["Plx"]) or 0.0, 0.0), "G": gmag, "r": r})
    return out


def pairs(rows: list[dict], a_ep: int, b_ep: int, key: str = "flux") -> list[dict]:
    """Same-wavelength pairs of measurements from two visits: ratio b/a with the wavelength."""
    out = []
    for a in rows:
        if a["epoch"] != a_ep or a.get(key) is None:
            continue
        for b in rows:
            if b["epoch"] == b_ep and b.get(key) is not None and abs(np.log(b["wave"] / a["wave"])) < MATCH:
                out.append({"wave": float(np.sqrt(a["wave"] * b["wave"])), "ratio": b[key] / a[key], "a": a, "b": b})
    return out


def med_range(v) -> str:
    v = np.asarray(v, float)
    if len(v) == 0:
        return "no pairs"
    if len(v) < 3:
        return f"n={len(v)}: " + ", ".join(f"{x:.2f}" for x in v)
    return f"n={len(v)}: median {np.median(v):.2f} (range {v.min():.2f} to {v.max():.2f})"


def main() -> None:
    starts = vc.epoch_edges(RA0, DEC0)
    cuts = [vc.read_cutout(p) for p in vc.list_cutouts(RA0, DEC0)]
    comps = comparison_stars()
    print(f"{len(cuts)} cached exposures; visits start {[vc.iso(s) for s in starts]}; {len(comps)} comparison stars "
          f"(Gaia G {min(c['G'] for c in comps):.1f} to {max(c['G'] for c in comps):.1f}, 30 to 200 arcsec away)")
    rows = []
    for c in cuts:
        ep = vc.epoch_of(c["mjd"], starts)
        ra, dec = rw_pos(c["mjd"])
        a = vf.aperture_flux(c, ra, dec)
        ring = vf.ring_flux(c, ra, dec, *RING)
        rows.append({**a, "epoch": ep, "star": "RW Aur", "ring": ring["value"], "ring_err": ring["err"],
                     "ring_status": ring["status"]})
        for s in comps:
            ra, dec = vc.apparent_position(s["ra"], s["dec"], 2016.0, s["pmra"], s["pmdec"], s["plx"], c["mjd"])
            rows.append({**vf.aperture_flux(c, ra, dec), "epoch": ep, "star": s["id"]})
    rw = [r for r in rows if r["star"] == "RW Aur" and r["wave"] is not None]
    summary: dict = {"n_exposures": len(cuts), "n_with_wavelength": len(rw),
                     "status": dict(Counter(r["status"] for r in rw)), "visits": {}, "per_detector": {}}

    print(f"\n1. RW Aur: {len(rw)} exposures with a wavelength; aperture flux "
          f"{dict(Counter(r['status'] for r in rw))}; "
          f"ring value in {sum(r['ring_status'] == 'ok' for r in rw)}")
    for ep in (1, 2, 3):
        mj = [r["mjd"] for r in rw if r["epoch"] == ep]
        summary["visits"][ep] = {"start": vc.iso(min(mj)), "end": vc.iso(max(mj))}
    for det in range(1, 7):
        line = f"  D{det}:"
        summary["per_detector"][det] = {}
        for ep in (1, 2, 3):
            d = [r for r in rw if r["detector"] == det and r["epoch"] == ep]
            n_ok = sum(r["status"] == "ok" for r in d)
            n_sat = sum(r["status"] == "saturated" for r in d)
            days = sorted({vc.iso(r["mjd"]) for r in d})
            summary["per_detector"][det][ep] = {"n": len(d), "ok": n_ok, "saturated": n_sat, "first": days[0],
                                                "last": days[-1]}
            line += f"  visit {ep} ({days[0]} to {days[-1][5:]}): {n_ok} flux, {n_sat} saturated of {len(d)};"
        print(line)

    # ---- 2. visit-to-visit ratios ---------------------------------------------------------------
    print("\n2. Comparison stars, same exposures: visit 3 / visit 1 and visit 2 / visit 1 (should be 1)")
    comp_ratios = []
    summary["comparison"] = {}
    for det in range(1, 7):
        all31, all21 = [], []
        for s in comps:
            d = [r for r in rows if r["star"] == s["id"] and r["detector"] == det and r["status"] == "ok"]
            # leave out measurements with fewer than 20 sigma: they only add noise
            d = [r for r in d if r["flux"] > 20 * r["err"]]
            p31, p21 = pairs(d, 1, 3), pairs(d, 1, 2)
            for p in p31:
                comp_ratios.append({"wave": p["wave"], "ratio": p["ratio"], "star": s["id"]})
            all31 += [p["ratio"] for p in p31]
            all21 += [p["ratio"] for p in p21]
        if all31:
            summary["comparison"][det] = {"n31": len(all31), "median31": float(np.median(all31)),
                                          "p16_31": float(np.percentile(all31, 16)),
                                          "p84_31": float(np.percentile(all31, 84)),
                                          "n21": len(all21), "median21": float(np.median(all21)) if all21 else None}
            print(f"  D{det}: visit 3/1 {len(all31)} pairs, median {np.median(all31):.3f} (16-84 per cent: "
                  f"{np.percentile(all31, 16):.3f} to {np.percentile(all31, 84):.3f}); visit 2/1 {len(all21)} pairs, "
                  f"median {np.median(all21):.3f}")
        else:
            print(f"  D{det}: no comparison star bright enough")

    print("\n   RW Aur, same-wavelength pairs of aperture fluxes")
    ok = [r for r in rw if r["status"] == "ok"]
    bands = [("0.75-0.84 um (the claim)", 0.74, 0.84), ("0.84-0.90 um (Ca II lines)", 0.84, 0.90),
             ("0.90-1.12 um", 0.90, 1.125), ("1.1-1.65 um (D2)", 1.125, 1.64), ("1.65-2.45 um (D3)", 1.64, 2.44),
             ("2.4-3.85 um (D4)", 2.44, 3.83), ("3.8-4.4 um (D5)", 3.83, 4.42), ("4.4-5.0 um (D6)", 4.42, 5.02)]
    det_of = {b[0]: d for b, d in zip(bands, (1, 1, 1, 2, 3, 4, 5, 6), strict=True)}
    summary["ratios"] = {}
    rw_pairs31, rw_pairs21 = [], []
    for name, lo, hi in bands:
        d = [r for r in ok if lo <= r["wave"] < hi and r["detector"] == det_of[name]]
        p31, p21, p32 = pairs(d, 1, 3), pairs(d, 1, 2), pairs(d, 2, 3)
        rw_pairs31 += p31
        rw_pairs21 += p21
        summary["ratios"][name] = {"v3_v1": [p["ratio"] for p in p31], "v2_v1": [p["ratio"] for p in p21],
                                   "v3_v2": [p["ratio"] for p in p32]}
        print(f"  {name:26s} visit 3/1 {med_range([p['ratio'] for p in p31])}; visit 2/1 "
              f"{med_range([p['ratio'] for p in p21])}; "
              f"visit 3/2 {med_range([p['ratio'] for p in p32])}")
    print("   the individual pairs behind 0.75-0.84 um, visit 3 / visit 1:")
    claim_pairs = []
    for p in sorted(pairs([r for r in ok if r["detector"] == 1 and r["wave"] < 0.845], 1, 3), key=lambda p: p["wave"]):
        a, b = p["a"], p["b"]
        claim_pairs.append({"wave1": a["wave"], "wave3": b["wave"], "date1": vc.iso(a["mjd"]),
                            "date3": vc.iso(b["mjd"]), "mjd1": a["mjd"], "mjd3": b["mjd"], "flux1": a["flux"],
                            "flux3": b["flux"], "ratio": p["ratio"]})
        print(f"     {a['wave']:.3f} um on {vc.iso(a['mjd'])} (MJD {a['mjd']:.2f}): {a['flux']:6.1f} mJy   ->   "
              f"{b['wave']:.3f} um on "
              f"{vc.iso(b['mjd'])} (MJD {b['mjd']:.2f}): {b['flux']:6.1f} mJy   ratio {p['ratio']:.2f}")
    summary["claim_pairs"] = claim_pairs

    # ---- 3. ring against flux -------------------------------------------------------------------
    print("\n3. Ring brightness (3.5-6.5 px) against aperture flux, exposures of RW Aur that have both")
    summary["ring"] = {}
    ring_pairs31 = []
    for det in (5, 6):
        both = [r for r in rw if r["detector"] == det and r["status"] == "ok" and r["ring_status"] == "ok"]
        frac = np.array([r["ring"] / r["flux"] for r in both])
        by_ep = {ep: np.array([r["ring"] / r["flux"] for r in both if r["epoch"] == ep]) for ep in (1, 2, 3)}
        d_ring = [r for r in rw if r["detector"] == det and r["ring_status"] == "ok"]
        pr31, pr21 = pairs(d_ring, 1, 3, "ring"), pairs(d_ring, 1, 2, "ring")
        ring_pairs31 += pr31
        pf31 = pairs([r for r in rw if r["detector"] == det and r["status"] == "ok"], 1, 3)
        summary["ring"][det] = {"n_both": len(both), "ring_over_flux_median": float(np.median(frac)),
                                "ring_over_flux_sd": float(np.std(frac)),
                                "by_visit": {ep: (float(np.median(v)) if len(v) else None) for ep, v in by_ep.items()},
                                "ring31": [p["ratio"] for p in pr31], "ring21": [p["ratio"] for p in pr21],
                                "flux31": [p["ratio"] for p in pf31]}
        print(f"  D{det}: ring/flux in {len(both)} exposures: median {np.median(frac):.4f}, scatter "
              f"{np.std(frac) / np.median(frac) * 100:.0f} "
              f"per cent; by visit " + ", ".join(f"{ep}: {np.median(v):.4f} "
                                                 f"(n={len(v)})" for ep, v in by_ep.items() if len(v)))
        print(f"      ring visit 3/1: {med_range([p['ratio'] for p in pr31])}; ring visit 2/1: "
              f"{med_range([p['ratio'] for p in pr21])}; "
              f"aperture flux visit 3/1: {med_range([p['ratio'] for p in pf31])}")

    # ---- 4. AAVSO ---------------------------------------------------------------------------------
    print("\n4. AAVSO (ground-based observers), fetched from vsx.aavso.org")
    aav = vc.aavso("RW Aur", 2460800.0, 2461360.0, OUT / "rwaur_aavso.txt")
    summary["aavso"] = None
    nightly: dict[str, list[tuple[float, float, int]]] = {}
    if aav is None:
        print("  AAVSO could not be reached: no outside comparison")
    else:
        aav = [a for a in aav if not a["fainter_than"]]
        print(f"  {len(aav)} observations, {len({a['observer'] for a in aav})} observers, bands "
              f"{dict(Counter(a['band'] for a in aav).most_common(6))}")
        monthly = {}
        for band in ("B", "V", "R", "I"):
            for label, lo, hi in (("2025-09", 60919.0, 60949.0), ("2026-03", 61100.0, 61131.0),
                                  ("2026-09", 61284.0, 61314.0)):
                m = np.array([a["mag"] for a in aav if a["band"] == band and lo <= a["mjd"] < hi])
                # drop the handful of impossible values (several magnitudes off) that a few uploads contain
                m = m[np.abs(m - np.median(m)) < 1.5] if len(m) else m
                monthly[(band, label)] = (float(np.median(m)), len(m), float(np.percentile(m, 10)),
                                          float(np.percentile(m, 90)))
            d = monthly[(band, "2025-09")][0] - monthly[(band, "2026-09")][0]
            print(f"  {band}: Sep 2025 median {monthly[(band, '2025-09')][0]:.2f} (n={monthly[(band, '2025-09')][1]}, "
                  f"10-90 per cent "
                  f"{monthly[(band, '2025-09')][2]:.2f} to {monthly[(band, '2025-09')][3]:.2f}); Mar 2026 "
                  f"{monthly[(band, '2026-03')][0]:.2f}; "
                  f"Sep 2026 {monthly[(band, '2026-09')][0]:.2f} (n={monthly[(band, '2026-09')][1]}); Sep to Sep: "
                  f"{d:+.2f} mag = "
                  f"{10 ** (0.4 * d):.2f} times brighter")
        summary["aavso"] = {"n": len(aav), "monthly": {f"{b} {m}": v for (b, m), v in monthly.items()}}
        for band in ("V", "I", "R"):
            groups = defaultdict(list)
            for a in aav:
                if a["band"] == band:
                    groups[round(a["mjd"] * 2) / 2].append(a["mag"])
            nightly[band] = sorted((t, float(np.median(v)), len(v)) for t, v in groups.items()
                                   if abs(np.median(v) - 12.0) < 3)
        print("  I-band nights around the SPHEREx detector-1 exposures at 0.75-0.84 um:")
        for lo, hi in ((60915.0, 60925.0), (61289.0, 61299.0)):
            print("     " + "; ".join(f"{vc.iso(t)} (MJD {t:.1f}) "
                                      f"I={m:.2f}" for t, m, _ in nightly["I"] if lo <= t <= hi))
        # What the SPHEREx pairs imply for the I magnitude on the first-visit dates, taking the AAVSO
        # I magnitude nearest the third-visit exposure as the anchor. Uses ratios only: no zero point.
        print("  SPHEREx ratios turned into an I magnitude for the first-visit dates (anchor: AAVSO I nearest the "
              "visit-3 exposure):")
        implied = []
        for p in claim_pairs:
            near = min(nightly["I"], key=lambda n: abs(n[0] - p["mjd3"]))
            mag = near[1] + 2.5 * np.log10(p["ratio"])
            implied.append({"mjd": p["mjd1"], "mag": float(mag), "wave": p["wave1"], "anchor_mjd": near[0],
                            "anchor_mag": near[1]})
            print(f"     {p['date1']} (MJD {p['mjd1']:.2f}), {p['wave1']:.3f} um: I about {mag:.2f} "
                  f"(anchor I={near[1]:.2f} on MJD {near[0]:.1f}, {abs(near[0] - p['mjd3']):.1f} d from the exposure)")
        summary["aavso"]["implied_I"] = implied
        # One absolute sanity check: SPHEREx flux near 0.80 um against the AAVSO I flux (needs a zero point).
        for label, lo, hi in (("visit 2", 61100.0, 61112.0), ("visit 3", 61290.0, 61293.5)):
            sp = [r for r in ok if r["detector"] == 1 and 0.775 <= r["wave"] <= 0.83 and lo <= r["mjd"] <= hi]
            for r in sp:
                near = min(nightly["I"], key=lambda n: abs(n[0] - r["mjd"]))
                fl = I_ZERO_JY * 1e3 * 10 ** (-0.4 * near[1])
                print(f"  absolute check, {label}: SPHEREx {r['flux']:.0f} mJy at {r['wave']:.3f} um on MJD "
                      f"{r['mjd']:.2f}; AAVSO I={near[1]:.2f} "
                      f"on MJD {near[0]:.1f} = {fl:.0f} mJy (zero point 2416 Jy); SPHEREx/AAVSO {r['flux'] / fl:.2f}")
                summary["aavso"].setdefault("absolute", []).append(
                    {"mjd": r["mjd"], "wave": r["wave"], "spherex": r["flux"], "aavso_mag": near[1],
                     "aavso_mjd": near[0], "ratio": r["flux"] / fl})

    keep = ("mjd", "detector", "epoch", "wave", "status", "flux", "err", "overflow", "ring", "ring_status")
    summary["rows"] = [{k: r[k] for k in keep} for r in rw]
    (OUT / "rwaur.json").write_text(json.dumps(summary, indent=1, default=float))
    print(f"\nwrote {OUT / 'rwaur.json'}")

    # ---- figures ----------------------------------------------------------------------------------
    cols = {1: vp.BLUE, 2: vp.GREEN, 3: vp.RED}
    ch = vp.Chart(title="RW Aurigae: SPHEREx flux against wavelength, one point per exposure (this check's own "
                        "photometry)",
                  xlabel="wavelength (microns)", ylabel="flux (mJy), log scale", width=1100, height=440,
                  legend_width=300,
                  logy=True, ylim=(50, 6000))
    for ep in (1, 2, 3):
        d = [r for r in ok if r["epoch"] == ep]
        v = summary["visits"][ep]
        ch.scatter([r["wave"] for r in d], [r["flux"] for r in d], color=cols[ep], size=3,
                   label=f"visit {ep}: {v['start']} to {v['end'][5:]} (measured flux)")
    # Saturated exposures in D5/D6: ring value scaled by the median ring/flux ratio of that detector.
    for ep in (1, 2, 3):
        xs, ys = [], []
        for det in (5, 6):
            scale = summary["ring"][det]["ring_over_flux_median"]
            for r in rw:
                if r["detector"] == det and r["epoch"] == ep and r["status"] != "ok" and r["ring_status"] == "ok":
                    xs.append(r["wave"])
                    ys.append(r["ring"] / scale)
        ch.scatter(xs, ys, color=cols[ep], size=3, hollow=True, marker="s",
                   label=f"visit {ep}: saturated, estimated from the ring (not a measured flux)")
    vp.save(ch.render(), vc.DOCS / "rwaur_spectrum.png")

    ch = vp.Chart(title="RW Aurigae: brightness in visit 3 (Sep 2026) divided by visit 1 (Sep 2025), same-wavelength "
                        "pairs",
                  xlabel="wavelength (microns)", ylabel="visit 3 / visit 1, log scale", width=1100, height=440,
                  legend_width=300, logy=True, ylim=(0.3, 4.0))
    ch.hline(1.0, vp.GREY, "no change")
    ch.scatter([p["wave"] for p in comp_ratios], [p["ratio"] for p in comp_ratios], color=(150, 150, 150), size=2,
               label=f"comparison stars in the same exposures ({len(comp_ratios)} pairs)")
    ch.scatter([p["wave"] for p in ring_pairs31], [p["ratio"] for p in ring_pairs31], color=vp.ORANGE, size=4,
               hollow=True,
               marker="s", label="RW Aur, ring brightness (works when saturated)")
    ch.scatter([p["wave"] for p in rw_pairs31], [p["ratio"] for p in rw_pairs31], color=vp.RED, size=5,
               label="RW Aur, measured flux")
    vp.save(ch.render(), vc.DOCS / "rwaur_ratio.png")

    if nightly:
        ch = vp.Chart(title="RW Aurigae from the ground (AAVSO), with the SPHEREx 0.75-0.84 micron result on the same "
                            "scale",
                      xlabel="date", ylabel="magnitude (up = brighter)", width=1100, height=440,
                      legend_width=300, xdate=True,
                      invert_y=True, xlim=(60880.0, 61330.0), ylim=(9.9, 13.6))
        for ep in (1, 2, 3):
            d1 = [r["mjd"] for r in rw if r["detector"] == 1 and r["epoch"] == ep]
            ch.span(min(d1) - 1.5, max(d1) + 1.5, (255, 240, 200))
        ch.scatter([t for t, _, _ in nightly["V"]], [m for _, m, _ in nightly["V"]], color=vp.GREEN, size=2,
                   label="AAVSO V band (0.55 microns), half-night medians")
        ch.scatter([t for t, _, _ in nightly["I"]], [m for _, m, _ in nightly["I"]], color=vp.BLUE, size=2,
                   label="AAVSO I band (0.80 microns), half-night medians")
        imp = summary["aavso"]["implied_I"]
        ch.scatter([p["mjd"] for p in imp], [p["mag"] for p in imp], color=vp.RED, size=5, marker="^",
                   label="SPHEREx 0.75-0.84 microns, visit 1, as an I magnitude (from the visit 3 / visit 1 ratios)")
        anchors = sorted({(p["anchor_mjd"], p["anchor_mag"]) for p in imp})
        ch.scatter([a[0] for a in anchors], [a[1] for a in anchors], color=vp.RED, size=5, marker="^", hollow=True,
                   label="anchor: AAVSO I at the SPHEREx visit 3 date")
        ch.note(60884, 13.35, "shaded: dates of the SPHEREx detector-1 exposures", vp.BROWN)
        vp.save(ch.render(), vc.DOCS / "rwaur_aavso.png")

        ch = vp.Chart(title="Close-up of the first SPHEREx visit: a short dip, seen from the ground and by SPHEREx",
                      xlabel="date (MJD; 60919 = 1 Sep 2025)", ylabel="I magnitude (up = brighter)",
                      width=1100, height=380,
                      legend_width=300, invert_y=True, xlim=(60914.0, 60927.0), ylim=(10.5, 11.6))
        ch.scatter([t for t, _, _ in nightly["I"]], [m for _, m, _ in nightly["I"]], color=vp.BLUE, size=5,
                   label="AAVSO I band")
        ch.scatter([p["mjd"] for p in imp], [p["mag"] for p in imp], color=vp.RED, size=6, marker="^",
                   label="SPHEREx 0.75-0.84 microns as an I magnitude")
        vp.save(ch.render(), vc.DOCS / "rwaur_dip.png")


if __name__ == "__main__":
    main()

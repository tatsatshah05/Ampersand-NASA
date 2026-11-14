"""Independent check of claim 3: R Draconis fades and recovers on its ~245-day cycle (saturated star).

Run:  SPHEREX_CACHE_DIR=<cache> .venv/bin/python scripts/verify_rdra.py

R Dra is saturated in every exposure, so there is no flux. The backend charts a "wing" value: light
in a ring of unsaturated pixels around the star. This script
  1. confirms the saturation count with its own aperture photometry;
  2. measures its own ring brightness (9.5-12.5 pixels, sky from 20-26 pixels) in detectors 5 and 6;
  3. applies the SAME code to Barnard's Star, which is saturated too but does not vary: the control;
  4. turns the ring values into a relative light curve: every wavelength channel gets its own level,
     every date its own brightness (least squares), separately for four wavelength groups because
     the star's spectrum changes shape through the cycle;
  5. compares the result with AAVSO visual observations for the same dates.
Writes figures to docs/verification/ and numbers to scripts/out/verify/rdra.json.
"""
import json
import sys
from collections import Counter
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

# Cutout centres (the backend's resolved positions for 2026.0) and Gaia DR3 astrometry (epoch 2016.0).
RDRA = {"centre": (248.167233, 66.755024), "ra": 248.1673783672889, "dec": 66.75500674547219,
        "pmra": -20.6428, "pmdec": 6.1488, "parallax": 1.2509}
BARNARD = {"centre": (269.446267, 4.768222), "ra": 269.44850252543836, "dec": 4.739420051112412,
           "pmra": -801.5509783684709, "pmdec": 10362.394206546573, "parallax": 546.975939730948}
RING = (9.5, 12.5)
RING_INNER = (6.5, 9.5)
SKY = (20.0, 26.0)
GROUPS = [("3.81-4.15 um (D5)", 5, 3.80, 4.15), ("4.15-4.43 um (D5)", 5, 4.15, 4.44),
          ("4.41-4.72 um (D6)", 6, 4.40, 4.72), ("4.72-5.01 um (D6)", 6, 4.72, 5.02)]
CHANNEL = 0.0089          # width of a wavelength channel in ln(wavelength): 17 per detector, as SPHEREx defines them


def measure(star: dict, detectors=(5, 6), with_aperture: bool = False) -> list[dict]:
    ra0, dec0 = star["centre"]
    starts = vc.epoch_edges(ra0, dec0)
    rows = []
    for det in detectors:
        for p in vc.list_cutouts(ra0, dec0, det):
            c = vc.read_cutout(p)
            ra, dec = vc.apparent_position(star["ra"], star["dec"], 2016.0, star["pmra"], star["pmdec"],
                                           star["parallax"],
                                           c["mjd"])
            r = vf.ring_flux(c, ra, dec, *RING, sky_px=SKY)
            r2 = vf.ring_flux(c, ra, dec, *RING_INNER, sky_px=SKY)
            row = {"obs_id": c["obs_id"], "mjd": c["mjd"], "detector": det, "epoch": vc.epoch_of(c["mjd"], starts),
                   "wave": r["wave"], "ring": r["value"], "ring_status": r["status"], "ring_inner": r2["value"],
                   "ring_inner_status": r2["status"], "sat_radius": r.get("sat_radius")}
            if with_aperture:
                ap = vf.aperture_flux(c, ra, dec)
                row["ap_status"] = ap["status"]
            rows.append(row)
    return rows


def solve(points: list[dict], key: str = "ring") -> dict | None:
    """Relative light curve from ring values: log10(value) = level of its channel + brightness of its date.

    Dates closer than one day are one date. Only dates linked to the others through a shared
    channel are kept. Returns the dates with relative brightness in magnitudes (mean zero) and
    the scatter of single exposures about the solution.
    """
    pts = sorted([p for p in points if p.get(key) is not None and p[key] > 0], key=lambda p: p["mjd"])
    if len(pts) < 6:
        return None
    gid, cur = [], 0
    for i, p in enumerate(pts):
        if i and p["mjd"] - pts[i - 1]["mjd"] > 1.0:
            cur += 1
        gid.append(cur)
    chan = [int(np.floor(np.log(p["wave"]) / CHANNEL)) for p in pts]
    # largest set of dates connected through shared channels
    parent = list(range(cur + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    first: dict[int, int] = {}
    for g, ch in zip(gid, chan, strict=True):
        if ch in first:
            parent[find(g)] = find(first[ch])
        else:
            first[ch] = g
    roots = Counter(find(g) for g in gid)
    main = roots.most_common(1)[0][0]
    keep = [i for i, g in enumerate(gid) if find(g) == main]
    dropped = len(pts) - len(keep)
    pts, gid, chan = [pts[i] for i in keep], [gid[i] for i in keep], [chan[i] for i in keep]
    groups, chans = sorted(set(gid)), sorted(set(chan))
    a = np.zeros((len(pts) + 1, len(chans) + len(groups)))
    y = np.zeros(len(pts) + 1)
    for i, p in enumerate(pts):
        a[i, chans.index(chan[i])] = 1.0
        a[i, len(chans) + groups.index(gid[i])] = 1.0
        y[i] = np.log10(p[key])
    a[-1, len(chans):] = 1.0                  # the date terms sum to zero: fixes the arbitrary level
    sol, *_ = np.linalg.lstsq(a, y, rcond=None)
    res = (a @ sol - y)[:-1]
    dof = max(len(pts) - len(chans) - len(groups) + 1, 1)
    rms = float(np.sqrt(np.sum(res ** 2) / dof))
    cov = np.linalg.pinv(a.T @ a) * rms ** 2
    dates = []
    for k, g in enumerate(groups):
        mj = [p["mjd"] for p, gg in zip(pts, gid, strict=True) if gg == g]
        j = len(chans) + k
        dates.append({"mjd": float(np.mean(mj)), "n": len(mj), "mag": float(-2.5 * sol[j]),
                      "mag_err": float(2.5 * np.sqrt(max(cov[j, j], 0.0)))})
    return {"dates": dates, "rms_dex": rms, "scatter_percent": float(100 * (10 ** rms - 1)), "n_points": len(pts),
            "n_channels": len(chans), "dropped": dropped,
            "residual_percent": [float(100 * (10 ** r - 1)) for r in res]}


def binned_visual(aav: list[dict], width: float = 10.0) -> list[tuple[float, float, int]]:
    vis = [a for a in aav if a["band"] in ("Vis.", "V") and not a["fainter_than"]]
    t = np.array([a["mjd"] for a in vis])
    m = np.array([a["mag"] for a in vis])
    out = []
    for lo in np.arange(np.floor(t.min()), t.max(), width):
        s = (t >= lo) & (t < lo + width)
        if s.sum() >= 2:
            out.append((float(np.mean(t[s])), float(np.median(m[s])), int(s.sum())))
    return out


def main() -> None:
    summary: dict = {}
    print("1. R Dra: saturation and ring brightness")
    rd_all = measure(RDRA, detectors=(1, 2, 3, 4, 5, 6), with_aperture=True)
    with_wave = [r for r in rd_all if r["wave"] is not None]
    counts = Counter(r["ap_status"] for r in with_wave)
    print(f"  {len(rd_all)} cached exposures, {len(with_wave)} with a wavelength; own aperture photometry: "
          f"{dict(counts)}")
    summary["aperture_status"] = dict(counts)
    summary["n_exposures"] = len(rd_all)
    rd = [r for r in with_wave if r["detector"] in (5, 6)]
    ok = [r for r in rd if r["ring_status"] == "ok"]
    print(f"  detectors 5 and 6: {len(rd)} exposures, ring {RING} px usable in {len(ok)} "
          f"({dict(Counter(r['ring_status'] for r in rd))}); saturated out to a median "
          f"{np.median([r['sat_radius'] for r in rd]):.1f} px")
    for ep in (1, 2, 3):
        for det in (5, 6):
            d = [r for r in ok if r["epoch"] == ep and r["detector"] == det]
            if d:
                print(f"    visit {ep} D{det}: {len(d)} values, {vc.iso(min(r['mjd'] for r in d))} to "
                      f"{vc.iso(max(r['mjd'] for r in d))}, "
                      f"{len({round(r['mjd']) for r in d})} separate days")
    summary["n_ring_ok"] = len(ok)

    print("\n2. Control: Barnard's Star (saturated, does not vary), same code, same detectors, same ring")
    bn = [r for r in measure(BARNARD) if r["wave"] is not None]
    bn_ok = [r for r in bn if r["ring_status"] == "ok"]
    print(f"  {len(bn)} exposures, ring usable in {len(bn_ok)}; visits "
          + ", ".join(f"{ep}: {vc.iso(min(r['mjd'] for r in bn if r['epoch'] == ep))} to "
                      f"{vc.iso(max(r['mjd'] for r in bn if r['epoch'] == ep))}" for ep in (1, 2, 3)))

    print("\n3. Relative light curves (each wavelength channel its own level, each date its own brightness)")
    curves: dict = {"R Dra": {}, "Barnard": {}, "R Dra inner ring": {}}
    for name, det, lo, hi in GROUPS:
        for star, rows, key in (("R Dra", ok, "ring"), ("Barnard", bn_ok, "ring"),
                                ("R Dra inner ring", [r for r in rd if r["ring_inner_status"] == "ok"], "ring_inner")):
            sol = solve([r for r in rows if r["detector"] == det and lo <= r["wave"] < hi], key)
            curves[star][name] = sol
            if sol is None:
                print(f"  {star:17s} {name}: too few points")
                continue
            mags = np.array([d["mag"] for d in sol["dates"]])
            print(f"  {star:17s} {name}: {sol['n_points']} exposures on {len(sol['dates'])} dates ({sol['dropped']} "
                  f"unlinked dropped); "
                  f"single exposures scatter {sol['scatter_percent']:.1f} per cent about the solution; date-to-date "
                  f"range "
                  f"{mags.max() - mags.min():.2f} mag = factor {10 ** (0.4 * (mags.max() - mags.min())):.2f}; "
                  f"sd of the dates {np.std(mags):.3f} mag")
    summary["curves"] = curves
    # Control in one number: how much do Barnard's dates scatter, all groups together?
    bmag = np.array([d["mag"] for g in curves["Barnard"].values() if g for d in g["dates"]])
    rmag = np.array([d["mag"] for g in curves["R Dra"].values() if g for d in g["dates"]])
    print(f"  all groups: Barnard's Star dates scatter by {np.std(bmag):.3f} mag (largest deviation "
          f"{np.abs(bmag).max():.2f} mag = "
          f"{100 * (10 ** (0.4 * np.abs(bmag).max()) - 1):.0f} per cent); R Dra dates by {np.std(rmag):.3f} mag "
          f"(range {rmag.max() - rmag.min():.2f} mag)")
    summary["control"] = {"barnard_sd_mag": float(np.std(bmag)), "barnard_max_abs_mag": float(np.abs(bmag).max()),
                          "rdra_sd_mag": float(np.std(rmag)), "rdra_range_mag": float(rmag.max() - rmag.min())}

    print("\n   R Dra by date (magnitudes relative to the mean of each wavelength group; smaller = brighter)")
    for name, *_ in GROUPS:
        sol = curves["R Dra"][name]
        if sol:
            print(f"   {name}: " + "; ".join(f"{vc.iso(d['mjd'])} {d['mag']:+.2f}" for d in sol["dates"]))

    # ---- 4. AAVSO -------------------------------------------------------------------------------
    print("\n4. AAVSO visual observations")
    aav = vc.aavso("R Dra", 2460400.0, 2461360.0, OUT / "rdra_aavso.txt")
    vsx = vc.http_get(vc.AAVSO_API, {"view": "api.object", "ident": "R Dra", "format": "json"}, tries=2, timeout=60)
    period = None
    if vsx is not None:
        try:
            obj = vsx.json()["VSXObject"]
            period = float(obj["Period"])
            print(f"  AAVSO VSX: type {obj['VariabilityType']}, period {obj['Period']} d, range {obj['MaxMag']} to "
                  f"{obj['MinMag']}")
            summary["vsx"] = obj
        except (ValueError, KeyError):
            pass
    summary["aavso"] = None
    binned = []
    if aav is None:
        print("  AAVSO could not be reached: no outside comparison")
    else:
        print(f"  {len(aav)} observations by {len({a['observer'] for a in aav})} observers: "
              f"{dict(Counter(a['band'] for a in aav).most_common(4))}")
        binned = binned_visual(aav)
        tb = np.array([b[0] for b in binned])
        mb = np.array([b[1] for b in binned])
        extremes = []
        for i in range(2, len(binned) - 2):
            window = mb[i - 2:i + 3]
            if mb[i] == window.min() and mb[i] < 9.0:
                extremes.append(("maximum", tb[i], mb[i]))
            if mb[i] == window.max() and mb[i] > 11.5:
                extremes.append(("minimum", tb[i], mb[i]))
        for kind, t, m in extremes:
            if t > 60700:
                print(f"    visual {kind} near {vc.iso(t)} (MJD {t:.0f}), magnitude {m:.1f} (10-day medians)")
        summary["aavso"] = {"n": len(aav), "extremes": [(k, float(t), float(m)) for k, t, m in extremes],
                            "binned": binned}

        def visual_at(t):
            return np.interp(t, tb, mb)

        print("  SPHEREx relative brightness against the visual magnitude on the same dates:")
        summary["correlation"] = {}
        for name, *_ in GROUPS:
            sol = curves["R Dra"][name]
            if not sol:
                continue
            t = np.array([d["mjd"] for d in sol["dates"]])
            m = np.array([d["mag"] for d in sol["dates"]])
            best = (-2.0, 0.0)
            r0 = float(np.corrcoef(m, visual_at(t))[0, 1])
            for lag in np.arange(0.0, 90.1, 5.0):          # infrared behind visual by `lag` days
                r = float(np.corrcoef(m, visual_at(t - lag))[0, 1])
                if r > best[0]:
                    best = (r, float(lag))
            slope = np.polyfit(visual_at(t - best[1]), m, 1)[0]
            summary["correlation"][name] = {"r_no_lag": r0, "r_best": best[0], "lag_days": best[1],
                                            "slope": float(slope),
                                            "n_dates": len(t)}
            print(f"    {name}: {len(t)} dates; correlation with the visual curve {r0:+.2f}; best {best[0]:+.2f} with "
                  f"the infrared "
                  f"{best[1]:.0f} d behind; {slope:.2f} mag of infrared change per visual magnitude")

    keep = ("mjd", "detector", "epoch", "wave", "ring", "ring_status", "ring_inner")
    rows_out = [{k: r[k] for k in keep} for r in rd]
    (OUT / "rdra.json").write_text(json.dumps({**summary, "rows": rows_out, "period": period}, indent=1, default=float))
    print(f"\nwrote {OUT / 'rdra.json'}")

    # ---- figures ----------------------------------------------------------------------------------
    cols = [vp.BLUE, vp.TEAL, vp.ORANGE, vp.RED]
    t0, t1 = 60780.0, 61260.0
    visits = [(min(r["mjd"] for r in rd if r["epoch"] == ep), max(r["mjd"] for r in rd if r["epoch"] == ep))
              for ep in (1, 2, 3)]
    panels = []
    if binned:
        ch = vp.Chart(title="R Draconis seen by eye from the ground (AAVSO): one cycle is about 246 days",
                      xlabel="", ylabel="visual magnitude (up = brighter)", width=1100, height=300, legend_width=290,
                      xdate=True, invert_y=True, xlim=(t0, t1), ylim=(6.0, 13.8))
        for a, b in visits:
            ch.span(a, b, (255, 240, 200))
        vis = [a for a in aav if a["band"] in ("Vis.", "V") and not a["fainter_than"] and t0 <= a["mjd"] <= t1]
        ch.scatter([a["mjd"] for a in vis], [a["mag"] for a in vis], color=(150, 150, 150), size=2,
                   label=f"AAVSO visual and V-band observations ({len(vis)})")
        ch.line([b[0] for b in binned], [b[1] for b in binned], color=vp.BLACK, label="10-day medians")
        ch.note(t0 + 4, 13.2, "shaded: the three SPHEREx visits", vp.BROWN)
        panels.append(ch.render())
    ch = vp.Chart(title="R Draconis in SPHEREx detectors 5 and 6: relative brightness from the ring of unsaturated "
                        "pixels",
                  xlabel="date", ylabel="relative magnitude (up = brighter)", width=1100, height=360, legend_width=290,
                  xdate=True, invert_y=True, xlim=(t0, t1), ylim=(-0.75, 0.75))
    for a, b in visits:
        ch.span(a, b, (255, 240, 200))
    ch.hline(0.0, vp.GREY)
    for (name, *_), col in zip(GROUPS, cols, strict=True):
        sol = curves["R Dra"][name]
        if sol:
            ch.scatter([d["mjd"] for d in sol["dates"]], [d["mag"] for d in sol["dates"]],
                       [d["mag_err"] for d in sol["dates"]], color=col, size=4, label=f"R Dra, {name}")
    panels.append(ch.render())
    ch = vp.Chart(title="Control: Barnard's Star (saturated, does not vary), same code, same detectors, same scale",
                  xlabel="date", ylabel="relative magnitude", width=1100, height=300, legend_width=290,
                  xdate=True, invert_y=True, xlim=(60890.0, 61320.0), ylim=(-0.75, 0.75))
    ch.hline(0.0, vp.GREY)
    for (name, *_), col in zip(GROUPS, cols, strict=True):
        sol = curves["Barnard"][name]
        if sol:
            ch.scatter([d["mjd"] for d in sol["dates"]], [d["mag"] for d in sol["dates"]],
                       [d["mag_err"] for d in sol["dates"]], color=col, size=4, label=f"Barnard's Star, {name}")
    panels.append(ch.render())
    vp.save(vp.stack_vertical(panels, pad=4), vc.DOCS / "rdra_lightcurve.png")

    # ring value against wavelength per visit: shows the raw numbers and the change of spectral shape
    ch = vp.Chart(title="R Draconis: raw ring brightness against wavelength (not a flux: well under 1 per cent of the "
                        "star's light)",
                  xlabel="wavelength (microns)", ylabel="ring brightness (mJy)", width=1100, height=380,
                  legend_width=290,
                  ylim=(0, 1150))
    for ep, col in zip((1, 2, 3), (vp.BLUE, vp.GREEN, vp.RED), strict=True):
        d = [r for r in ok if r["epoch"] == ep]
        ch.scatter([r["wave"] for r in d], [r["ring"] for r in d], color=col, size=3,
                   label=f"visit {ep}: {vc.iso(min(r['mjd'] for r in d))} to {vc.iso(max(r['mjd'] for r in d))}")
    vp.save(ch.render(), vc.DOCS / "rdra_rings.png")


if __name__ == "__main__":
    main()

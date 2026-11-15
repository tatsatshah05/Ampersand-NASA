"""Re-run the colour-of-change analysis from the data on disk and re-draw its pictures.

    python scripts/colour_of_change.py [--out docs/colour] [--db FILE] [--force] [--fast]

What it does (see docs/colour-of-change.md):
  1. reads every brightness-changing object of the watchlist (needs-eyes and already-known groups),
     measures it, and the steady control stars of its patch, in every exposure whose cutout is already
     on disk (nothing is downloaded; a patch with missing cutouts has them counted and left out);
  2. the spectrum of the change for every pair of visits, the four shapes fitted, the ice bands, the
     principal components;
  3. the checks on known objects (RW Aurigae, the Serpens South star, V371 Ser, the novae V462 Lup and
     V7994 Sgr, from the viewer's cached photometry, and the steady stars);
  4. writes docs/colour/change_spectra.json (the table for every object and pair), summary.json (every
     number the write-up quotes), objects.md (one line per object) and the pictures.
`--fast` skips the ice break tests' slowest part and the per-object pictures.
Set SPHEREX_CACHE_DIR to the shared cache. The watchlist database is only read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from astropy.time import Time
from scipy.ndimage import median_filter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_plot import BLACK, BLUE, GREEN, GREY, ORANGE, PURPLE, RED, TEAL, Chart, save  # noqa: E402

from backend import colour, photometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DET_COLOURS = {1: (90, 140, 230), 2: (60, 170, 200), 3: (60, 170, 90), 4: (225, 170, 40), 5: (230, 100, 50),
               6: (160, 60, 160)}
CLASS_COLOURS = {"grey": GREY, "dust": BLUE, "warm": ORANGE, "hot": RED, "cannot_tell": TEAL,
                 "none_of_these": PURPLE, "no_clear_change": (190, 190, 190)}
KNOWN = {"RW Aurigae": "changer-076.9564n30.4012", "Serpens South star": "changer-277.5055s02.0620",
         "V371 Ser": "changer-277.4633n01.2778"}
NOVAE = {"V462 Lup": (227.01362, -40.14308), "V7994 Sgr": (270.96983, -31.45739)}


def iso(mjd: float) -> str:
    return Time(mjd, format="mjd").iso[:10]


def visit_dates(r: dict[str, Any], v: int) -> str:
    lo, hi = r["visit_mjd"][v]
    return iso(lo) if iso(lo) == iso(hi) else f"{iso(lo)} to {iso(hi)}"


def nominal_centre(det: int, ch: int) -> float:
    lo, hi = colour.DETECTOR_RANGE_UM[det]
    e = np.geomspace(lo, hi, colour.CHANNELS + 1)
    return float(np.sqrt(e[ch] * e[ch + 1]))


# --------------------------------------------------------------------------- pictures

def model_curves(fit: dict[str, Any], ch: list[dict[str, Any]], alpha: float = colour.DUST_ALPHA) -> dict[str, Any]:
    """Wavelengths and ratio curves of the four fitted shapes, for drawing."""
    w = np.geomspace(min(c["wave_um"] for c in ch), max(c["wave_um"] for c in ch), 120)
    cw = np.array([c["wave_um"] for c in ch])
    early = np.array([c["early"] for c in ch])
    order = np.argsort(cw)
    smooth = median_filter(early[order], size=7, mode="nearest")     # the earlier spectrum, smoothed for the drawing
    e_i = np.interp(w, cw[order], smooth)
    out: dict[str, Any] = {"wave": w}
    f = fit["fits"]
    out["grey"] = np.full_like(w, f["grey"]["params"]["factor"])
    out["dust"] = colour.dust_ratio(w, f["dust"]["params"]["tau_1"], alpha)
    for k in ("warm", "hot"):
        if k in f:
            p = f[k]["params"]
            out[k] = 1.0 + p["amplitude_mjy_at_ref"] * colour.planck_shape(w, p["temperature_k"], f[k]["ref_um"]) / e_i
    return out


def ratio_chart(r: dict[str, Any], pair: str, title: str, scale: float, *, width: int = 1000, height: int = 440,
                curves: bool = True) -> Any:
    """Ratio later / earlier against wavelength, log axes, error bars, saturated channels marked at the bottom."""
    p = r["pairs"][pair]
    ch = p["table"]["channels"]
    fit = p["fit"]
    v0, v1 = p["visits"]
    ratios = np.array([c["ratio"] for c in ch])
    lo = max(0.02, float(np.min(ratios - np.array([c["ratio_err"] for c in ch]) * scale).clip(0.02, None)) * 0.7)
    hi = float(np.max(ratios + np.array([c["ratio_err"] for c in ch]) * scale)) * 1.3
    ylim = (min(lo, 0.5), max(hi, 2.0))
    chart = Chart(title=title, xlabel="wavelength (micrometres)", ylabel=f"brightness, visit {v1 + 1} / visit {v0 + 1}",
                  width=width, height=height, logx=True, logy=True, xlim=(0.72, 5.2), ylim=ylim, legend_width=270)
    chart.hline(1.0, color=(150, 150, 150))
    for d in range(1, 7):
        sel = [c for c in ch if c["detector"] == d]
        if sel:
            chart.scatter([c["wave_um"] for c in sel], [c["ratio"] for c in sel],
                          yerr=[c["ratio_err"] * scale for c in sel], color=DET_COLOURS[d], label=f"detector {d}")
    sat = p["table"]["saturated_channels"]
    if sat:
        chart.scatter([nominal_centre(s["detector"], s["channel"]) for s in sat], [ylim[0] * 1.15] * len(sat),
                      color=(120, 120, 120), marker="x", label=f"saturated ({len(sat)}): no value")
    if curves and fit.get("fits"):
        mc = model_curves(fit, ch)
        for k, col in (("grey", GREY), ("dust", BLUE), ("warm", ORANGE), ("hot", RED)):
            if k in mc:
                f = fit["fits"][k]
                mark = "fits" if f["fits"] else "no"
                chart.line(mc["wave"], np.clip(mc[k], ylim[0], ylim[1]), color=col,
                           label=f"{k}: chi2/dof {f['chi2'] / f['dof']:.1f} ({mark})", width=2)
    return chart.render()


def pca_pictures(pca: dict[str, Any], res_obj: dict[str, Any], out: Path) -> None:
    ids = pca["ids"]
    sc = pca["uncentred"]["scores"]
    names = [colour.CLASS_NAMES.get(res_obj[i]["pairs"][res_obj[i]["headline"]]["fit"]["verdict"], "?") for i in ids]
    verdicts = [res_obj[i]["pairs"][res_obj[i]["headline"]]["fit"]["verdict"] for i in ids]
    for (a, b, name) in ((0, 1, "pca_1_2.png"), (0, 2, "pca_1_3.png"), (1, 2, "pca_2_3.png")):
        ch = Chart(title=f"Objects in the space of components {a + 1} and {b + 1} (coloured by class from step 2)",
                   xlabel=f"component {a + 1}", ylabel=f"component {b + 1}", width=900, height=560, legend_width=300)
        ch.hline(0.0)
        ch.vline(0.0)
        for v in sorted(set(verdicts)):
            m = [k for k, x in enumerate(verdicts) if x == v]
            ch.scatter([sc[a][k] for k in m], [sc[b][k] for k in m], color=CLASS_COLOURS[v],
                       label=f"{colour.CLASS_NAMES[v]} ({len(m)})", size=5)
        for o in pca.get("outliers", []):
            k = ids.index(o["id"])
            ch.note(sc[a][k], sc[b][k], " " + o["id"].replace("changer-", ""), BLACK)
        save(ch.render(), out / name)
    del names
    ch = Chart(title="What the first components look like (loading against wavelength)",
               xlabel="wavelength (micrometres)",
               ylabel="loading (change in ln brightness per unit score)", width=900, height=460, logx=True,
               legend_width=250)
    ch.hline(0.0)
    for k, col in enumerate((BLUE, ORANGE, GREEN, PURPLE)):
        share = pca["uncentred"]["variance_share"][k]
        ch.line(pca["band_centres_um"], pca["uncentred"]["components"][k], color=col,
                label=f"component {k + 1} ({share * 100:.0f}% of the signal)")
        ch.scatter(pca["band_centres_um"], pca["uncentred"]["components"][k], color=col, size=3)
    save(ch.render(), out / "pca_components.png")
    ch = Chart(title="Singular values: data against the noise of steady stars", xlabel="component",
               ylabel="singular value",
               width=700, height=380, logy=True, legend_width=260)
    sv = pca["uncentred"]["singular_values"]
    ch.scatter(list(range(1, len(sv) + 1)), sv, color=BLUE, size=5, label="objects")
    ch.hline(pca["noise_singular_value"], color=RED, label="noise level from steady stars")
    save(ch.render(), out / "pca_scree.png")


def ice_picture(ice: dict[str, Any], out: Path) -> None:
    ch = Chart(title="Change in ice-band depth, in units of the real error (steady stars grey, objects blue)",
               xlabel="band (1 water 3.05, 2 CO2 4.27, 3 CO 4.67)", ylabel="change / real error", width=860, height=460,
               legend_width=260, xlim=(0.4, 3.6))
    rng = np.random.default_rng(1)
    bands = list(colour.ICE_BANDS)
    for hits, col, lab in ((ice["control_hits"], (140, 140, 140), "steady stars"),
                           (ice["objects"]["hits"], BLUE, "objects")):
        x = [bands.index(h["band"]) + 1 + rng.uniform(-0.3, 0.3) for h in hits]
        y = [float(np.clip(h["sigma_real"], -25, 25)) for h in hits]
        ch.scatter(x, y, color=col, size=3, label=f"{lab} ({len(hits)})")
    for lvl in (-5, 5):
        ch.hline(lvl, color=RED)
    ch.hline(0.0)
    save(ch.render(), out / "ice_changes.png")


# --------------------------------------------------------------------------- the pieces of the report

def class_gallery(res_obj: dict[str, Any], scale: float, out: Path) -> dict[str, str]:
    """The clearest example of each class: the largest change among those with many channels (not saturated rings)."""
    best: dict[str, tuple[float, str]] = {}
    for i, r in res_obj.items():
        h = r["headline"]
        if not h or r["ring"]:
            continue
        f = r["pairs"][h]["fit"]
        if f["n_channels"] < 12:
            continue
        v = f["verdict"]
        if v == "none_of_these":
            score = f["change_sigma"]
        else:
            score = f["change_sigma"] if f["fits"][v if v in f["fits"] else "grey"]["p"] > 0.01 else 0
        if v not in best or score > best[v][0]:
            best[v] = (score, i)
    shown = {}
    for v, (_s, i) in best.items():
        if v == "no_clear_change":
            continue
        r = res_obj[i]
        h = r["headline"]
        title = (f"{i.replace('changer-', '')}: {colour.CLASS_NAMES[v]}  "
                 f"({visit_dates(r, r['pairs'][h]['visits'][0])} to {visit_dates(r, r['pairs'][h]['visits'][1])})")
        save(ratio_chart(r, h, title, scale), out / f"gallery_{v}.png")
        shown[v] = i
    return shown


def per_object(res_obj: dict[str, Any], scale: float, out: Path) -> None:
    for i, r in res_obj.items():
        h = r["headline"]
        if not h:
            continue
        v = r["pairs"][h]["fit"]["verdict"]
        title = f"{i.replace('changer-', '')}: {colour.CLASS_NAMES.get(v, v)}"
        im = ratio_chart(r, h, title, scale, width=780, height=380)
        im.save(out / "objects" / f"{i}.png", optimize=True)


def object_row(r: dict[str, Any], info: dict[str, Any], scale: float) -> dict[str, Any]:
    h = r["headline"]
    row: dict[str, Any] = {"id": r["id"], "ra": r["ra"], "dec": r["dec"], "group": info.get("group"),
                           "catalogue": info.get("category"), "ring": r["ring"], "headline_pair": h}
    if h:
        p = r["pairs"][h]
        f = p["fit"]
        ch = p["table"]["channels"]
        row.update(visits=[visit_dates(r, v) for v in p["visits"]], n_channels=f["n_channels"], verdict=f["verdict"],
                   sigma=f["change_sigma"], sentence=colour.plain_sentence(r),
                   ratios={"0.75-1.1": colour.ratio_at(ch, 0.75, 1.1), "1.1-1.65": colour.ratio_at(ch, 1.1, 1.65),
                           "1.65-2.4": colour.ratio_at(ch, 1.65, 2.42), "2.4-3.8": colour.ratio_at(ch, 2.42, 3.82),
                           "3.8-4.4": colour.ratio_at(ch, 3.82, 4.42), "4.4-5.0": colour.ratio_at(ch, 4.42, 5.1)},
                   reduced_chi2={k: v["chi2"] / v["dof"] for k, v in f["fits"].items()},
                   tilt=r.get("tilt"), readings_left_out=p["table"]["readings"],
                   n_saturated_channels=len(p["table"]["saturated_channels"]),
                   two_part_that_fit=f.get("two_part_that_fit"))
        for k in ("warm", "hot", "dust", "grey"):
            if k in f["fits"]:
                row[f"fit_{k}"] = {"params": f["fits"][k]["params"], "errors": f["fits"][k]["errors"],
                                   "fits": f["fits"][k]["fits"], "p": f["fits"][k]["p"]}
    return row


def round_floats(x: Any, nd: int = 5) -> Any:
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: round_floats(v, nd) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [round_floats(v, nd) for v in x]
    return x


def spectra_json(res_obj: dict[str, Any], infos: dict[str, dict[str, Any]], scale: float) -> dict[str, Any]:
    cols = ["detector", "channel", "wave_um", "early_mjy", "early_err", "late_mjy", "late_err", "ratio", "ratio_err",
            "n_early", "n_late"]
    out = {}
    for i, r in res_obj.items():
        pairs = {}
        for name, p in r["pairs"].items():
            t = p["table"]
            f = p["fit"]
            pairs[name] = {
                "visits": [{"visit": v + 1, "dates": visit_dates(r, v)} for v in p["visits"]],
                "columns": cols,
                "channels": [[c["detector"], c["channel"], c["wave_um"], c["early"], c["early_err"], c["late"],
                              c["late_err"], c["ratio"], c["ratio_err"], c["n_early"], c["n_late"]]
                             for c in t["channels"]],
                "saturated_channels_no_value": t["saturated_channels"], "readings_by_status": t["readings"],
                "calibration_removed": t.get("common_shift"),
                "verdict": f.get("verdict"), "verdict_text": f.get("verdict_text"),
                "change_sigma": f.get("change_sigma"),
                "n_channels": f["n_channels"],
                "fits": {k: {"params": v["params"], "errors": v["errors"], "chi2": v["chi2"], "dof": v["dof"],
                             "p": v["p"], "fits_within_errors": v["fits"]} for k, v in f.get("fits", {}).items()},
                "two_part_that_fit": f.get("two_part_that_fit")}
        out[i] = {"id": i, "ra": r["ra"], "dec": r["dec"], "group": infos[i].get("group"),
                  "catalogue_category": infos[i].get("category"), "headline_pair": r["headline"],
                  "plain_sentence": colour.plain_sentence(r), "pairs": pairs}
    return round_floats(out)


def objects_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Every object: the colour of its change", "",
             "Generated by `scripts/colour_of_change.py`. One line per brightness-changing object of the watchlist "
             "(needs-eyes and already-known groups). The pair of visits is the one with the largest change. "
             "Ratios are later / earlier, the median of the channels in that range; `-` means none measured in both "
             "visits. `sigma` is the size of the change as the square root of how much the best shape improves "
             "chi-square over no change. A class is a description of the colours, not a proven cause.", "",
             "| object | catalogue | visits compared | channels | class | sigma | 0.75-1.1 | 1.1-1.65 | 1.65-2.4 | "
             "2.4-3.8 | 3.8-4.4 | 4.4-5.0 | what it says |", "|" + "---|" * 13]
    for r in sorted(rows, key=lambda r: (r.get("verdict") or "", -(r.get("sigma") or 0))):
        if "verdict" not in r:
            lines.append(f"| {r['id'].replace('changer-', '')} | {r['catalogue']} | | | no pair | | | | | | | | "
                         "too few shared channels |")
            continue
        rt = r["ratios"]
        cells = " | ".join("-" if rt[k] is None else f"{rt[k]:.2f}" for k in rt)
        two = f" (a two-part shape fits: {', '.join(r['two_part_that_fit'])})" if r.get("two_part_that_fit") else ""
        lines.append(f"| {r['id'].replace('changer-', '')} | {r['catalogue']} | {r['visits'][0]} / {r['visits'][1]} | "
                     f"{r['n_channels']} | {colour.CLASS_NAMES[r['verdict']]} | {r['sigma']:.0f} | {cells} | "
                     f"{r['sentence']}{two} |")
    return "\n".join(lines) + "\n"


def known_checks(res: dict[str, Any], out: Path, scale: float, thr: float) -> dict[str, Any]:
    """RW Aurigae, the Serpens South star, V371 Ser, two novae, and the steady stars."""
    known: dict[str, Any] = {}
    for name, oid in KNOWN.items():
        r = res["objects"][oid]
        for pair, p in r["pairs"].items():
            if p["fit"]["n_channels"] < colour.MIN_COMMON_CHANNELS:
                continue
            ch = p["table"]["channels"]
            per_det = {}
            for d in range(1, 7):
                v = [c["ratio"] for c in ch if c["detector"] == d]
                if v:
                    per_det[d] = {"median_ratio": float(np.median(v)), "n": len(v)}
            known.setdefault(name, {})[pair] = {
                "verdict": p["fit"]["verdict"], "sigma": p["fit"]["change_sigma"], "per_detector": per_det,
                "dates": [visit_dates(r, v) for v in p["visits"]],
                "reduced_chi2": {k: f["chi2"] / f["dof"] for k, f in p["fit"]["fits"].items()},
                "two_part_that_fit": p["fit"].get("two_part_that_fit")}
        h = r["headline"]
        save(ratio_chart(r, h, f"{name}: {colour.CLASS_NAMES[r['pairs'][h]['fit']['verdict']]}", scale),
             out / f"known_{name.lower().replace(' ', '_')}.png")
    for name, (ra, dec) in NOVAE.items():
        d = photometry.measure_all(ra, dec)
        rec = colour.points_to_record(d["points"], d["detector_ranges_um"], name)
        a = colour.analyse_record(rec)
        r = colour.object_result(a, {}, scale, min_sigma=thr)
        for pair, p in r["pairs"].items():
            if p["fit"]["n_channels"] < colour.MIN_COMMON_CHANNELS:
                known.setdefault(name, {})[pair] = {"n_channels": p["fit"]["n_channels"], "verdict": "too_few_channels"}
                continue
            ch = p["table"]["channels"]
            per_det = {dd: {"median_ratio": float(np.median([c["ratio"] for c in ch if c["detector"] == dd])),
                            "n": sum(c["detector"] == dd for c in ch)}
                       for dd in range(1, 7) if any(c["detector"] == dd for c in ch)}
            known.setdefault(name, {})[pair] = {
                "verdict": p["fit"]["verdict"], "sigma": p["fit"]["change_sigma"], "per_detector": per_det,
                "reduced_chi2": {k: f["chi2"] / f["dof"] for k, f in p["fit"]["fits"].items()},
                "two_part_that_fit": p["fit"].get("two_part_that_fit"),
                "dates": [f"{iso(a['visit_mjd'][v][0])} to {iso(a['visit_mjd'][v][1])}" for v in p["visits"]]}
        scored = [(p["fit"].get("change_sigma", 0.0), n) for n, p in r["pairs"].items()
                  if p["fit"]["n_channels"] >= colour.MIN_COMMON_CHANNELS]
        if scored:
            r["headline"] = max(scored)[1]
            head = r["headline"]
            word = colour.CLASS_NAMES[r["pairs"][head]["fit"]["verdict"]]
            save(ratio_chart(r, head, f"{name}: {word}", scale), out / f"known_{name.lower().replace(' ', '_')}.png")
    return known


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "colour")
    ap.add_argument("--db", type=Path, default=None, help="watchlist database (read only)")
    ap.add_argument("--force", action="store_true", help="measure the cutouts again")
    ap.add_argument("--fast", action="store_true", help="no per-object pictures")
    args = ap.parse_args()
    out: Path = args.out
    (out / "objects").mkdir(parents=True, exist_ok=True)

    objects = colour.watchlist_objects(args.db)
    infos = {o["id"]: o for o in objects}
    print(f"{len(objects)} brightness-changing objects on the watchlist")
    paths = colour.build_dataset(objects, force=args.force)
    recs = colour.load_dataset(paths)
    missing = {colour.patch_key(r["patch"]): r["missing"] for r in recs}
    print("exposures without a cutout on disk, by patch:", {k: v for k, v in missing.items() if v})
    res = colour.analyse_all(recs)
    scale = res["error_scale"]["scale"]
    thr = res["threshold"]
    res_obj = res["objects"]

    rows = [object_row(r, infos[i], scale) for i, r in res_obj.items()]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("verdict", "no_pair")] = counts.get(r.get("verdict", "no_pair"), 0) + 1
    print("classes:", counts)

    shown = class_gallery(res_obj, scale, out)
    if not args.fast:
        per_object(res_obj, scale, out)
    known = known_checks(res, out, scale, thr)
    if res["pca"]["ok"]:
        pca_pictures(res["pca"], res_obj, out)
    ice_picture(res["ice"], out)

    # saturated and excluded readings, over every object's headline pair
    sat_total = sum(r.get("n_saturated_channels", 0) for r in rows)
    excl = {"saturated": 0, "flagged_or_other": 0, "clean": 0}
    for r in rows:
        for k, v in (r.get("readings_left_out") or {}).items():
            excl[k] += v
    summary = {
        "n_objects": len(objects), "n_ring_objects": sum(o["ring"] for o in objects),
        "n_with_headline_pair": sum(1 for r in rows if r["headline_pair"]), "classes": counts,
        "classes_by_catalogue": {c: _by_category(rows, c) for c in sorted({r["catalogue"] for r in rows})},
        "exposures_without_cutout": missing, "error_scale": res["error_scale"], "threshold_sigma": thr,
        "validation_half_of_controls": res["validation"], "control_classes": colour._count(res["controls"].values()),
        "n_control_stars": len(res["controls"]), "calibration_groups": len(res["shifts"]),
        "alpha_check": res["alpha_check"], "smallest_colour": res["smallest_colour"], "known": known,
        "gallery": shown, "readings_in_headline_pairs": excl, "saturated_channels_in_headline_pairs": sat_total,
        "pca": {k: v for k, v in res["pca"].items() if k not in ("ids",)} if res["pca"]["ok"] else res["pca"],
        "pca_ids": res["pca"].get("ids"),
        "ice": {"controls": res["ice"]["controls"], "control_depth": res["ice"]["control_depth"],
                "bands": res["ice"]["bands"],
                "objects": {k: v for k, v in res["ice"]["objects"].items() if k != "hits"},
                "hits_over_5": [h for h in res["ice"]["objects"]["hits"] if "tests" in h],
                "control_hits_over_5": [h for h in res["ice"]["control_hits"] if "tests" in h],
                "n_control_measurements": len(res["ice"]["control_hits"])},
        "none_of_these": [r for r in rows if r.get("verdict") == "none_of_these"],
        "rows": rows}
    (out / "summary.json").write_text(json.dumps(round_floats(summary, 4), indent=1, default=float))
    (out / "change_spectra.json").write_text(json.dumps(spectra_json(res_obj, infos, scale), default=float,
                                                         separators=(",", ":")))
    (out / "objects.md").write_text(objects_markdown(rows))
    print(f"wrote {out}/summary.json, change_spectra.json, objects.md")


def _by_category(rows: list[dict[str, Any]], cat: str) -> dict[str, int]:
    o: dict[str, int] = {}
    for r in rows:
        if r["catalogue"] == cat:
            v = r.get("verdict", "no_pair")
            o[v] = o.get(v, 0) + 1
    return o


if __name__ == "__main__":
    main()

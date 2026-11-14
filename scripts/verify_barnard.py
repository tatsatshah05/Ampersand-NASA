"""Optional fourth check: why does Barnard's Star sit 1.45 arcsec east of its prediction in the first visit?

Run:  SPHEREX_CACHE_DIR=<cache> .venv/bin/python scripts/verify_barnard.py [detector, default 5]

Three position measurements per exposure, all against the Gaia DR3 prediction (proper motion plus
parallax):
  A. the backend's own fit (pipeline.prepare_cutout, stack of one exposure, fit_source), which
     includes the pixels of the saturated core because their values are finite;
  B. this check's fit from the unsaturated pixels only: the centre about which the star's outer
     light is most nearly round (no assumption about its exact shape);
  C. an ordinary full fit of the unsaturated field stars in the same exposure, which tests the image
     registration (WCS) of every exposure.
Method test for B: the same wings-only fit on RW Aurigae in the same detector, in the exposures where
it is not saturated, with its core left out on purpose, against an ordinary fit that uses the core.
Experiment D: the backend's per-visit stack and fit, unchanged, on temporary copies of the cutouts
in which the pixels lost to saturation are blanked. If the offset goes away, those pixels cause it.
Nothing is written to the cache. Figure: docs/verification/barnard_offsets_d<detector>.png.
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import verify_common as vc
import verify_fit as vf
import verify_plot as vp

from backend import astrometry, pipeline

OUT = ROOT / "scripts" / "out" / "verify"
OUT.mkdir(parents=True, exist_ok=True)
RA0, DEC0 = 269.446267, 4.768222            # cutout centre: the backend's resolved position for 2026.0
BARNARD = {"ra": 269.44850252543836, "dec": 4.739420051112412, "pmra": -801.5509783684709,
           "pmdec": 10362.394206546573, "parallax": 546.975939730948, "ref_epoch": 2016.0}
DET = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def predicted(mjd: float) -> tuple[float, float]:
    return vc.apparent_position(BARNARD["ra"], BARNARD["dec"], 2016.0, BARNARD["pmra"], BARNARD["pmdec"],
                                BARNARD["parallax"], mjd)


def wing_centre(c: dict, ra: float, dec: float, r_in: float = 0.0, r_out: float = 6.5, mask_saturated: bool = True):
    """Centre of symmetry of a star's outer light: offset (east, north) in arcsec from (ra, dec).

    For each trial centre the pixel values are described by a smooth function of distance from that
    centre only (cubic in radius, fitted to log brightness). The right centre is the one about which
    the light is most nearly round, i.e. with the smallest misfit. Saturated pixels are not used.
    r_in > 0 also leaves out the core (to test the method on unsaturated stars).
    """
    ny, nx = c["data"].shape
    x, y = [float(v) for v in c["wcs"].all_world2pix(ra, dec, 0)]
    xi, yi = int(round(x)), int(round(y))
    h = int(np.ceil(r_out)) + 3
    if not (h + 1 <= xi < nx - h - 1 and h + 1 <= yi < ny - h - 1):
        return None
    sl = (slice(yi - h, yi + h + 1), slice(xi - h, xi + h + 1))
    d, v, f = c["data"][sl], c["variance"][sl], c["flags"][sl]
    yy, xx = np.mgrid[yi - h:yi + h + 1, xi - h:xi + h + 1]
    empty = ~np.isfinite(d) | ~np.isfinite(v)
    sat = vf.saturated_mask(f, empty) if mask_saturated else np.zeros(d.shape, bool)
    r0 = np.hypot(xx - x, yy - y)
    far = (r0 > r_out + 0.5) & ~empty & ~sat
    if far.sum() < 30:
        return None
    sky, _, _ = vf.clipped_median(d[far])
    usable = ~empty & ~sat & ((f & vc.BAD_PHOT) == 0) & (d - sky > 5 * np.sqrt(v))
    best = None
    steps = np.arange(-1.5, 1.501, 0.05)
    for dy in steps:
        for dx in steps:
            r = np.hypot(xx - x - dx, yy - y - dy)
            sel = usable & (r >= r_in) & (r <= r_out)
            if sel.sum() < 25:
                continue
            a = np.vander(r[sel], 4)
            lv = np.log(d[sel] - sky)
            coef, res, *_ = np.linalg.lstsq(a, lv, rcond=None)
            misfit = float(np.sum((a @ coef - lv) ** 2) / (sel.sum() - 4))
            if best is None or misfit < best[0]:
                best = (misfit, dx, dy, int(sel.sum()))
    if best is None or abs(best[1]) > 1.45 or abs(best[2]) > 1.45:
        return None
    ra_f, dec_f = [float(vv) for vv in c["wcs"].all_pix2world(x + best[1], y + best[2], 0)]
    de, dn = vc.offset_arcsec(ra, dec, ra_f, dec_f)
    return {"east": float(de), "north": float(dn), "dx": best[1], "dy": best[2], "n_pix": best[3],
            "n_sat": int(sat.sum()),
            "frac_x": x - np.floor(x + 0.5), "frac_y": y - np.floor(y + 0.5)}


def blanked_copy(path: Path, folder: Path) -> tuple[Path, int, int]:
    """Temporary copy of a cached cutout with the pixels lost to saturation set to "no value".

    Also returns how many such pixels lie within 5 pixels of the cutout centre, and how many of
    those the backend's own mask (pipeline.prepare_cutout) would have kept.
    """
    with fits.open(path) as hdul:
        image = hdul["IMAGE"].data.astype("float32").copy()
        flags = hdul["FLAGS"].data.astype("int64")
        variance = hdul["VARIANCE"].data.astype("float64")
        sat = vf.saturated_mask(flags, ~np.isfinite(image))
        bloom = (flags & pipeline.BLOOM) != 0
        backend_bad = (((flags & pipeline.ALWAYS_BAD) != 0) | (((flags & pipeline.COSMIC_RAY) != 0) & ~bloom)
                       | ~np.isfinite(image) | pipeline.impossible_pixels(image.astype("float64"), variance))
        ny, nx = image.shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        near = np.hypot(xx - (nx - 1) / 2, yy - (ny - 1) / 2) < 5
        n_sat, n_kept = int((sat & near).sum()), int((sat & near & ~backend_bad).sum())
        image[sat] = np.nan
        hdus = [fits.PrimaryHDU()]
        for h in hdul[1:]:
            hdus.append(fits.ImageHDU(image if h.name == "IMAGE" else h.data, header=h.header, name=h.name))
        target = folder / path.name
        fits.HDUList(hdus).writeto(target)
    return target, n_sat, n_kept


def stack_offset(paths: list[Path], grid, n: int) -> tuple[float, float, float] | None:
    """The backend's stack of these exposures: its centroid minus the prediction (east, north; arcsec)
    and the uncertainty the fit itself reports (arcsec)."""
    items = [it for it in (pipeline.prepare_cutout(p, grid, n, RA0, DEC0) for p in paths) if it is not None]
    if not items:
        return None
    st = pipeline.stack(items)
    mjd = float(np.average([it["mjd"] for it in items], weights=[it["weight"] for it in items]))
    bra, bdec = astrometry.position_at(BARNARD, mjd)
    x0, y0 = [float(v) for v in grid.all_world2pix(bra, bdec, 0)]
    fit = pipeline.fit_source(st["image"], x0, y0)
    if fit is None:
        return None
    err = fit["err_px"] * pipeline.GRID_ARCSEC if fit["err_px"] is not None else float("nan")
    return -(fit["x"] - x0) * pipeline.GRID_ARCSEC, (fit["y"] - y0) * pipeline.GRID_ARCSEC, err


def method_test() -> np.ndarray:
    """Wings-only centre (core left out) minus ordinary fit, for a bright star in the exposures where it is
    not saturated: RW Aur, same detector as the one being checked."""
    ra0, dec0 = 76.956587, 30.401291
    out = []
    for p in vc.list_cutouts(ra0, dec0, DET):
        c = vc.read_cutout(p)
        ra, dec = vc.apparent_position(ra0, dec0, 2026.0, 7.23, -20.33, 15.42, c["mjd"])
        full = vf.fit_star(c, ra, dec)
        if full is None:
            continue
        w = wing_centre(c, ra, dec, r_in=1.5, r_out=6.5, mask_saturated=False)
        if w is not None:
            out.append((w["east"] - full["east"], w["north"] - full["north"]))
    return np.array(out)


def main() -> None:
    starts = vc.epoch_edges(RA0, DEC0)
    # The backend's cached Gaia rows for this field.
    gaia = json.loads((vc.CACHE / "queries" / "gaia_5ab9fecc1107b2b0.json").read_text())
    field = [g for g in gaia if g["source_id"] != "4472832130942575872" and g["gmag"] is not None and g["gmag"] < 13.5
             and 40 < np.hypot(*vc.offset_arcsec(RA0, DEC0, g["ra"], g["dec"])) < 200]
    print(f"detector {DET}; {len(field)} Gaia field stars (G < 13.5) in the cutouts; visits start "
          f"{[vc.iso(s) for s in starts]}")
    grid, n = pipeline.make_grid(RA0, DEC0, 0.1)
    rows = []
    for p in vc.list_cutouts(RA0, DEC0, DET):
        c = vc.read_cutout(p)
        ep = vc.epoch_of(c["mjd"], starts)
        ra, dec = predicted(c["mjd"])
        row = {"obs_id": c["obs_id"], "mjd": c["mjd"], "epoch": ep}
        # A. the backend's fit on this exposure alone
        item = pipeline.prepare_cutout(p, grid, n, RA0, DEC0)
        if item is not None:
            st = pipeline.stack([item])
            bra, bdec = astrometry.position_at(BARNARD, c["mjd"])
            x0, y0 = [float(v) for v in grid.all_world2pix(bra, bdec, 0)]
            fit = pipeline.fit_source(st["image"], x0, y0)
            if fit is not None:
                row["backend_east"] = -(fit["x"] - x0) * pipeline.GRID_ARCSEC
                row["backend_north"] = (fit["y"] - y0) * pipeline.GRID_ARCSEC
        # B. wings only
        w = wing_centre(c, ra, dec)
        if w is not None:
            row.update(wing_east=w["east"], wing_north=w["north"], n_sat=w["n_sat"], frac_x=w["frac_x"],
                       frac_y=w["frac_y"])
        # C. field stars: ordinary full fit (tests the registration of this exposure)
        full = []
        for g in field:
            gra, gdec = vc.apparent_position(g["ra"], g["dec"], 2016.0, g["pmra"] or 0.0, g["pmdec"] or 0.0,
                                             max(g["parallax"] or 0.0, 0.0), c["mjd"])
            fs = vf.fit_star(c, gra, gdec)
            if fs is not None and fs["flux"] > 5:
                full.append((fs["east"], fs["north"]))
        if full:
            row["field_east"], row["field_north"] = [float(v) for v in np.median(np.array(full), axis=0)]
            row["n_field"] = len(full)
        rows.append(row)

    summary: dict = {"detector": DET, "visits": {}}
    tests = method_test()
    if len(tests):
        print(f"method test (RW Aur, detector {DET}, {len(tests)} unsaturated exposures): wings-only centre with the "
              f"core left out, "
              f"minus the ordinary fit: median east {np.median(tests[:, 0]):+.2f}, north "
              f"{np.median(tests[:, 1]):+.2f}; "
              f"scatter (sd) east {tests[:, 0].std():.2f}, north {tests[:, 1].std():.2f} arcsec")
        summary["method_test"] = {"n": len(tests),
                                  "median": [float(np.median(tests[:, 0])), float(np.median(tests[:, 1]))],
                                  "sd": [float(tests[:, 0].std()), float(tests[:, 1].std())]}
    for ep in (1, 2, 3):
        d = [r for r in rows if r["epoch"] == ep]
        out = {"n": len(d), "start": vc.iso(min(r["mjd"] for r in d)), "end": vc.iso(max(r["mjd"] for r in d))}
        line = f"visit {ep} ({out['start']} to {out['end']}, {len(d)} exposures):"
        for key, label in (("backend", "backend fit (core "
                                       "included)"), ("wing", "wings only"), ("field", "field stars")):
            e = np.array([r[f"{key}_east"] for r in d if f"{key}_east" in r])
            nn = np.array([r[f"{key}_north"] for r in d if f"{key}_north" in r])
            if len(e):
                out[key] = {"n": len(e), "east_median": float(np.median(e)), "east_mean": float(e.mean()),
                            "east_sd": float(e.std()), "east_min": float(e.min()), "east_max": float(e.max()),
                            "north_median": float(np.median(nn)),
                            "north_sd": float(nn.std())}
                line += (f"\n    {label:28s} east median {np.median(e):+.2f}, mean {e.mean():+.2f}, sd {e.std():.2f}, "
                         f"range {e.min():+.2f} to "
                         f"{e.max():+.2f}; north median {np.median(nn):+.2f}, sd {nn.std():.2f}")
        summary["visits"][ep] = out
        print(line)
    # D. the backend's stack and fit per visit: as it is, and with the saturated pixels blanked
    print("experiment: the backend's per-visit stack and fit, with and without the pixels lost to saturation")
    mjds = vc.all_mjds(RA0, DEC0)
    with tempfile.TemporaryDirectory() as tmp:
        for ep in (1, 2, 3):
            paths = [p for p in vc.list_cutouts(RA0, DEC0, DET) if vc.epoch_of(mjds[p.name], starts) == ep]
            copies = [blanked_copy(p, Path(tmp)) for p in paths]
            as_is = stack_offset(paths, grid, n)
            blanked = stack_offset([c[0] for c in copies], grid, n)
            n_sat = float(np.median([c[1] for c in copies]))
            n_kept = float(np.median([c[2] for c in copies]))
            summary["visits"][ep].update(stack_as_is=as_is, stack_saturated_blanked=blanked,
                                         saturated_core_pixels_median=n_sat, of_which_backend_keeps_median=n_kept)
            text = "no fit" if blanked is None else f"east {blanked[0]:+.2f}, north {blanked[1]:+.2f}"
            print(f"  visit {ep}: as it is: east {as_is[0]:+.2f}, north {as_is[1]:+.2f} (the fit's own uncertainty: "
                  f"{as_is[2]:.2f}); pixels lost to saturation blanked: {text} (per exposure a median of {n_sat:.0f} "
                  f"pixels lost to saturation near the star, of which the backend's mask keeps {n_kept:.0f})")
    # Does the backend's offset follow the position of the star within its pixel?
    for ep in (1, 2, 3):
        d = [r for r in rows if r["epoch"] == ep and "backend_east" in r and "frac_x" in r]
        if len(d) > 5:
            fx = np.array([r["frac_x"] for r in d])
            be = np.array([r["backend_east"] for r in d])
            cc = float(np.corrcoef(fx, be)[0, 1])
            summary["visits"][ep]["corr_backend_east_vs_pixel_phase"] = cc
            print(f"visit {ep}: correlation of the backend's east offset with where the star sits inside its pixel "
                  f"(x): {cc:+.2f}")
    print("\nper exposure, visit 1 (east offsets in arcsec): backend fit | wings only | field stars | star's place "
          "inside its pixel (x)")
    for r in sorted([r for r in rows if r["epoch"] == 1], key=lambda r: r["mjd"]):
        print(f"   {r['obs_id']} {vc.iso(r['mjd'])}: {r.get('backend_east', float('nan')):+5.2f} | "
              f"{r.get('wing_east', float('nan')):+5.2f} | "
              f"{r.get('field_east', float('nan')):+5.2f} | {r.get('frac_x', float('nan')):+5.2f}")
    (OUT / f"barnard_d{DET}.json").write_text(json.dumps({**summary, "rows": rows}, indent=1, default=float))

    title = f"Barnard's Star, detector {DET}: east-west offset from the Gaia prediction, one point per exposure"
    ch = vp.Chart(title=title, xlabel="exposure number in time order (visit 1 | visit 2 | visit 3)",
                  ylabel="arcsec east of the prediction", width=1100, height=420, legend_width=300, ylim=(-4.5, 4.5))
    ch.hline(0.0, vp.GREY)
    order = sorted(rows, key=lambda r: r["mjd"])
    idx = {r["obs_id"]: i for i, r in enumerate(order)}
    for ep in (1, 2):
        last = max(idx[r["obs_id"]] for r in order if r["epoch"] == ep)
        ch.vline(last + 0.5, vp.LIGHT)
    series = (("field", (150, 150, 150), "field stars in the same exposure (median)", "s", False),
              ("backend", vp.RED, "backend fit, saturated core included", "o", False),
              ("wing", vp.BLUE, "this check: unsaturated pixels only", "^", True))
    for key, col, label, marker, hollow in series:
        sel = [r for r in order if f"{key}_east" in r]
        ch.scatter([idx[r["obs_id"]] for r in sel], [r[f"{key}_east"] for r in sel], color=col, label=label,
                   marker=marker, hollow=hollow, size=4)
    vp.save(ch.render(), vc.DOCS / f"barnard_offsets_d{DET}.png")


if __name__ == "__main__":
    main()

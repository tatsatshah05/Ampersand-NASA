"""Follow one known comet or asteroid through the SPHEREx survey and measure its spectrum.

Run:  .venv/bin/python scripts/follow_body.py NAME [--out DIR] [--max N] [--stop YYYY-MM-DD] [--strip N]

NAME is anything JPL Horizons knows: "4 Vesta", "3I/ATLAS", "C/2025 R2", "13P", "Pluto".
Writes into DIR (default docs/comets/): <name>.json (every point), <name>_spectrum.png, and with --strip N a strip of
N small single-exposure pictures (<name>_strip.png): the body at its predicted place on top, the same sky place in an
exposure of another day underneath. Needs the network the first time (JPL Horizons, IRSA, NASA's S3 bucket); every
answer is kept under $SPHEREX_CACHE_DIR/follow, so a repeat asks nobody anything.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from verify_plot import (
    BLUE,
    GREEN,
    GREY,
    ORANGE,
    PURPLE,
    RED,
    TEAL,
    Chart,
    caption_block,
    save,
    stack_horizontal,
    stack_vertical,
)  # noqa: E402

from backend import follow, pipeline, smallbodies  # noqa: E402

BAND_COLOURS = {"H2O": (200, 225, 245), "CO2": (245, 225, 200), "CO": (225, 245, 215)}
METHANE_ICE_UM = (1.7, 2.3, 3.3)


def spectrum_chart(
    res: dict, title: str, large: bool = False, xlim: tuple[float, float] | None = None, mark_methane: bool = False
) -> Chart:
    key, ekey = ("flux_large_mjy", "err_large_mjy") if large else ("flux_mjy", "err_mjy")
    ok = [p for p in res["points"] if p["status"] == "ok" and p.get(key) is not None]
    other = [p for p in res["points"] if p["status"] == "star_in_the_way" and p.get(key) is not None]
    radius = res["radii"]["large_arcsec" if large else "small_arcsec"]
    ch = Chart(
        title=title,
        xlabel="wavelength (micrometres)",
        ylabel=f"brightness in {radius:g} arcsec circle (mJy)",
        width=1150,
        height=480,
        xlim=xlim or (0.7, 5.1),
    )
    for k, b in follow.BANDS.items():
        ch.span(*b["window"], color=BAND_COLOURS[k])
    if mark_methane:
        for w in METHANE_ICE_UM:
            ch.vline(w, color=ORANGE)
    if other:
        ch.scatter(
            [p["wavelength_um"] for p in other],
            [p[key] for p in other],
            color=GREY,
            hollow=True,
            label="a fixed source is also there",
        )
    if ok:
        ch.scatter(
            [p["wavelength_um"] for p in ok],
            [p[key] for p in ok],
            yerr=[p[ekey] for p in ok],
            color=BLUE,
            label=f"{len(ok)} exposures",
        )
    ch.hline(0.0, color=GREY)
    return ch


def visits_chart(res: dict, title: str, large: bool = True) -> Chart:
    """The spectrum drawn on a logarithmic scale with each visit (a few days of observing) in its own colour, so that
    the same body at different times can be compared. Visits with fewer than 15 usable points are left out."""
    key, ekey = ("flux_large_mjy", "err_large_mjy") if large else ("flux_mjy", "err_mjy")
    radius = res["radii"]["large_arcsec" if large else "small_arcsec"]
    ok = [p for p in res["points"] if p["status"] == "ok" and (p.get(key) or 0) > 0]
    ch = Chart(
        title=title,
        xlabel="wavelength (micrometres)",
        ylabel=f"brightness in {radius:g} arcsec circle (mJy)",
        width=1150,
        height=480,
        xlim=(0.7, 5.1),
        logy=True,
    )
    for k, b in follow.BANDS.items():
        ch.span(*b["window"], color=BAND_COLOURS[k])
    colours = [BLUE, ORANGE, RED, GREEN, PURPLE, TEAL]
    shown = [g for g in follow.visits(ok) if len(g) >= 15]
    for g, colour in zip(shown, colours, strict=False):
        ch.scatter(
            [p["wavelength_um"] for p in g],
            [p[key] for p in g],
            yerr=[p[ekey] for p in g],
            color=colour,
            label=f"{g[0]['time'][:10]} to {g[-1]['time'][:10]} (r {g[0]['r_au']:.1f} au)",
            size=3,
        )
    return ch


def table(res: dict) -> str:
    lines = [
        f"{res['name']}: {res['n_in_footprint']} exposures contain it "
        f"({res['n_near_edge']} too near an image edge), {res['n_followed']} measured; "
        f"circles {res['radii']['small_arcsec']} and {res['radii']['large_arcsec']} arcsec; "
        f"predicted magnitude {res['vmag_range']}",
        "counts: " + ", ".join(f"{k} {v}" for k, v in res.get("counts", {}).items() if v),
    ]
    for v in res.get("bands", []) + res.get("bands_large", []):
        lines.append(
            f"visit {v['first'][:10]} to {v['last'][:10]} ({v['n_points']} points, r {v['r_au']:.2f} au, "
            f"delta {v['delta_au']:.2f} au, {'large' if 'large' in v['circle'] else 'small'} circle)"
        )
        for k, b in v["bands"].items():
            if b["ok"]:
                lines.append(
                    f"   {k}: excess {b['excess_mjy']:+.3f} +- {b['err_mjy']:.3f} mJy "
                    f"({b['sigma']:+.1f} x error, {b['n_band']} in band, {b['n_left']}+{b['n_right']} continuum) "
                    f"-> {b['verdict']}; controls {b['controls']}"
                )
            else:
                lines.append(
                    f"   {k}: not enough exposures in the band or beside it "
                    f"({b['n_band']} in band, {b['n_left']}+{b['n_right']} continuum)"
                )
    for key, label in (("scan", "12.3 arcsec"), ("scan_large", "36.9 arcsec")):
        s = res.get(key)
        if not s:
            continue
        lines.append(
            f"sequence scan ({label} circle): windows away from the gas bands: {s['null_windows']}, "
            f"{s['null_ge5']} at +5 times the error or more, {s['null_le_minus5']} at -5 or less"
        )
        for k, b in s["bands"].items():
            best = b["best"]
            lines.append(
                f"   {k}: {b['windows_on_band']} windows on the band; nights with +5 or more: "
                f"{', '.join(b['nights_with_5_sigma']) or 'none'}"
                + (
                    f"; best {best['excess_mjy']:+.2f} +- {best['err_mjy']:.2f} mJy ({best['sigma']:+.1f}x)"
                    if best
                    else ""
                )
            )
    return "\n".join(lines)


def _panel(
    file: Path, ra: float, dec: float, out: Path, label: str, lim: tuple[float, float] | None
) -> tuple[Image.Image, tuple[float, float]]:
    """One 120 arcsec single-exposure picture, with a caption."""
    wide_n = int(round(smallbodies.PICTURE_ARCSEC * 5 / pipeline.GRID_ARCSEC))
    wide, wn = pipeline.make_grid(ra, dec, wide_n * pipeline.GRID_ARCSEC / 3600.0)
    small, n = pipeline.make_grid(ra, dec, smallbodies.PICTURE_ARCSEC / 3600.0)
    item = pipeline.prepare_cutout(file, small, n, ra, dec)
    item_wide = pipeline.prepare_cutout(file, wide, wn, ra, dec)
    if item is None or item_wide is None:
        raise ValueError("no usable pixels")
    use = lim or pipeline.stretch_limits([item_wide["data"]])
    pipeline.to_png({"image": item["data"], "saturated": item["saturated"]}, use, out)
    im = Image.open(out).convert("RGB")
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST) if im.width < 200 else im
    return stack_vertical([im, caption_block(im.width, [label], size=11)], pad=2), use


def strip(res: dict, outdir: Path, slug: str, n: int) -> Path | None:
    """Pictures: top row, the body's own exposures from n different dates; bottom row, the same sky place in an
    exposure of another day (no body there). Both pictures of a pair use the same brightness stretch,
    set from the sky round the body in its own exposure."""
    pts = [p for p in res["points"] if p["status"] in ("ok", "star_in_the_way") and p.get("other_files")]
    days: dict[str, dict] = {}
    for p in pts:  # one picture per day: the exposure in which the body stands out most
        day = p["time"][:10]
        if day not in days or (p.get("sigma_noise") or 0) > (days[day].get("sigma_noise") or 0):
            days[day] = p
    chosen = sorted(days.values(), key=lambda p: p["mjd"])
    if len(chosen) > n:
        chosen = [chosen[i] for i in np.linspace(0, len(chosen) - 1, n).round().astype(int)]
    cols = []
    tmp = outdir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(chosen):
        try:
            top, lim = _panel(
                Path(p["file"]),
                p["ra"],
                p["dec"],
                tmp / f"a{i}.png",
                f"{p['time'][:10]}  {p['wavelength_um']:.2f} um",
                None,
            )
            of = next(f for f in p["other_files"] if Path(f).exists())
            # the same stretch for both: take the limits from the body's own picture's surroundings
            bottom, _ = _panel(
                Path(of),
                p["ra"],
                p["dec"],
                tmp / f"b{i}.png",
                f"same place, other day ({Path(of).name.split('_')[0][:8]})",
                lim,
            )
        except Exception as e:  # noqa: BLE001
            print(f"  no picture for {p['time']}: {e}")
            continue
        cols.append(stack_vertical([top, bottom], pad=4))
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    if not cols:
        return None
    path = outdir / f"{slug}_strip.png"
    save(stack_horizontal(cols, pad=8), path)
    return path


def sequence_strip(res: dict, outdir: Path, slug: str, prefix: str) -> Path | None:
    """Consecutive exposures of one detector (the points whose time starts with `prefix`, for example
    "2025-12-25T19:4") side by side, each centred on the body, all with one brightness stretch (the first one's)."""
    prefix, _, det = prefix.partition("@")  # "2026-01-02T10:2@5": only detector 5
    pts = sorted(
        (
            p
            for p in res["points"]
            if p["time"].startswith(prefix)
            and p["status"] in ("ok", "star_in_the_way")
            and (not det or p["detector"] == int(det))
        ),
        key=lambda p: p["mjd"],
    )
    if not pts:
        return None
    tmp = outdir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    cols, lim = [], None
    for i, p in enumerate(pts):
        label = f"{p['time'][5:16]} D{p['detector']} {p['wavelength_um']:.3f} um {p['flux_mjy']:.1f} mJy"
        try:
            im, used = _panel(Path(p["file"]), p["ra"], p["dec"], tmp / f"s{i}.png", label, lim)
        except Exception as e:  # noqa: BLE001
            print(f"  no picture for {p['time']}: {e}")
            continue
        lim = lim or used
        cols.append(im)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    if not cols:
        return None
    tag = prefix.replace(":", "").replace("-", "") + (f"_D{det}" if det else "")
    path = outdir / f"{slug}_sequence_{tag}.png"
    save(stack_horizontal(cols, pad=8), path)
    return path


FIELD_ARCSEC = 200.0


def moving_strip(res: dict, outdir: Path, slug: str, n: int) -> tuple[Path, list[str]] | None:
    """The same patch of sky (fixed on the sky, not on the body) in n exposures of one visit, one per day, with a ring
    at the body's predicted place: the stars stay, the ring moves. Returns the file and one line per picture."""
    pts = [p for p in res["points"] if p["status"] == "ok" and p.get("sigma_noise")]
    if not pts:
        return None
    visit = max(follow.visits(pts), key=len)
    best: dict[str, dict] = {}
    for p in visit:
        day = p["time"][:10]
        if day not in best or p["sigma_noise"] > best[day]["sigma_noise"]:
            best[day] = p
    chosen = sorted(best.values(), key=lambda p: p["mjd"])
    if len(chosen) > n:
        chosen = [chosen[i] for i in np.linspace(0, len(chosen) - 1, n).round().astype(int)]
    ra0 = float(np.mean([p["ra"] for p in chosen]))
    dec0 = float(np.mean([p["dec"] for p in chosen]))
    grid, size = pipeline.make_grid(ra0, dec0, FIELD_ARCSEC / 3600.0)
    tmp = outdir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    cols, notes = [], []
    for i, p in enumerate(chosen):
        item = pipeline.prepare_cutout(Path(p["file"]), grid, size, ra0, dec0)
        if item is None:
            continue
        lim = pipeline.stretch_limits([item["data"]])
        pipeline.to_png({"image": item["data"], "saturated": item["saturated"]}, lim, tmp / f"m{i}.png")
        im = Image.open(tmp / f"m{i}.png").convert("RGB")
        im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
        px, py = grid.all_world2pix(p["ra"], p["dec"], 0)
        x, y = float(px) * im.width / size, (size - 1 - float(py)) * im.height / size
        r = 7.0 * im.width / size  # a ring 14 arcsec in radius: it leaves the body itself visible
        ImageDraw.Draw(im).ellipse((x - r, y - r, x + r, y + r), outline=(230, 60, 60), width=2)
        label = f"{p['time'][:10]}  {p['wavelength_um']:.2f} um"
        cols.append(stack_vertical([im, caption_block(im.width, [label], size=11)], pad=2))
        notes.append(
            f"{p['time']} RA {p['ra']:.5f} Dec {p['dec']:.5f} ({p['wavelength_um']:.2f} um, "
            f"{p['sigma_noise']:.0f} x noise)"
        )
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    if not cols:
        return None
    path = outdir / f"{slug}_moving.png"
    save(stack_horizontal(cols, pad=6), path)
    first, last = chosen[0], chosen[-1]
    d_ra = (last["ra"] - first["ra"]) * np.cos(np.radians(first["dec"])) * 3600.0
    d_dec = (last["dec"] - first["dec"]) * 3600.0
    notes.append(
        f"moved {np.hypot(d_ra, d_dec):.0f} arcsec ({d_ra:+.0f} in RA direction, {d_dec:+.0f} in Dec) "
        f"between {first['time'][:10]} and {last['time'][:10]}"
    )
    return path, notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("name")
    ap.add_argument("--out", default=str(ROOT / "docs" / "comets"))
    ap.add_argument("--stop", default=None, help="last day of the path (default today)")
    ap.add_argument("--max", type=int, default=None, help="measure only this many exposures, spread over time")
    ap.add_argument(
        "--moving", type=int, default=0, help="draw a strip of this many pictures of one fixed patch of sky"
    )
    ap.add_argument("--strip", type=int, default=0, help="draw a strip of this many single-exposure pictures")
    ap.add_argument(
        "--sequence", action="append", default=[], help="time prefix such as 2025-12-25T19:4: draw those exposures"
    )
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    last = [""]

    def prog(stage: str, i: int = 0, n: int = 0) -> None:
        if stage != last[0] or (n and (i == n or i % 50 == 0)):
            print(
                f"[{time.time() - t0:5.0f}s] {stage} {i}/{n}" if n else f"[{time.time() - t0:5.0f}s] {stage}",
                flush=True,
            )
        last[0] = stage

    res = follow.follow_body(a.name, stop=a.stop, progress=prog, max_exposures=a.max)
    res["bands"] = follow.all_bands(res["points"])  # always from the points, so a change to the
    res["bands_large"] = follow.all_bands(res["points"], "flux_large_mjy")  # band arithmetic needs no new download
    res["scan"] = follow.scan_summary(follow.scan_sequences(res["points"]))
    res["scan_large"] = follow.scan_summary(follow.scan_sequences(res["points"], "flux_large_mjy"))
    slug = follow._slug(a.name)
    (out / f"{slug}.json").write_text(json.dumps(res, indent=1))
    print(table(res))
    if res["n_followed"]:
        spectrum_chart(res, f"{res['name']}: spectrum from SPHEREx exposures").render().save(
            out / f"{slug}_spectrum.png"
        )
        visits_chart(res, f"{res['name']}: each visit in its own colour (36.9 arcsec circle)").render().save(
            out / f"{slug}_visits.png"
        )
        if a.strip:
            print("strip:", strip(res, out, slug, a.strip))
        for prefix in a.sequence:
            print("sequence strip:", sequence_strip(res, out, slug, prefix))
        if a.moving:
            m = moving_strip(res, out, slug, a.moving)
            if m:
                print("moving strip:", m[0])
                print("\n".join(m[1]))
    print(follow.CREDIT)


if __name__ == "__main__":
    main()

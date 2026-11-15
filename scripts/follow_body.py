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
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from verify_plot import BLUE, GREY, ORANGE, Chart, caption_block, save, stack_horizontal, stack_vertical  # noqa: E402

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


def table(res: dict) -> str:
    lines = [
        f"{res['name']}: {res['n_in_footprint']} exposures contain it "
        f"({res['n_near_edge']} too near an image edge), {res['n_followed']} measured; "
        f"circles {res['radii']['small_arcsec']} and {res['radii']['large_arcsec']} arcsec; "
        f"predicted magnitude {res['vmag_range']}",
        "counts: " + ", ".join(f"{k} {v}" for k, v in res.get("counts", {}).items() if v),
    ]
    for v in res.get("bands", []):
        lines.append(
            f"visit {v['first'][:10]} to {v['last'][:10]} ({v['n_points']} points, r {v['r_au']:.2f} au, "
            f"delta {v['delta_au']:.2f} au, {v['circle']})"
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
    return "\n".join(lines)


def _panel(file: Path, ra: float, dec: float, out: Path, label: str, lim: tuple[float, float] | None) -> Image.Image:
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
    return stack_vertical([im, caption_block(im.width, [label], size=11)], pad=2)


def strip(res: dict, outdir: Path, slug: str, n: int) -> Path | None:
    """Pictures: top row, the body's own exposures from n different dates; bottom row, the same sky place in an
    exposure of another day (no body there). Each pair shares one stretch, set from the body's exposure's
    surroundings."""
    pts = [p for p in res["points"] if p["status"] in ("ok", "star_in_the_way") and p.get("other_files")]
    days = {}
    for p in pts:
        days.setdefault(p["time"][:10], p)
    chosen = list(days.values())
    if len(chosen) > n:
        chosen = [chosen[i] for i in np.linspace(0, len(chosen) - 1, n).round().astype(int)]
    cols = []
    tmp = outdir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(chosen):
        try:
            top = _panel(
                Path(p["file"]),
                p["ra"],
                p["dec"],
                tmp / f"a{i}.png",
                f"{p['time'][:10]}  {p['wavelength_um']:.2f} um",
                None,
            )
            of = next(f for f in p["other_files"] if Path(f).exists())
            # the same stretch for both: take the limits from the body's own picture's surroundings
            bottom = _panel(
                Path(of),
                p["ra"],
                p["dec"],
                tmp / f"b{i}.png",
                f"same place, other day ({Path(of).name.split('_')[0][:8]})",
                None,
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("name")
    ap.add_argument("--out", default=str(ROOT / "docs" / "comets"))
    ap.add_argument("--stop", default=None, help="last day of the path (default today)")
    ap.add_argument("--max", type=int, default=None, help="measure only this many exposures, spread over time")
    ap.add_argument("--strip", type=int, default=0, help="draw a strip of this many single-exposure pictures")
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
    slug = follow._slug(a.name)
    (out / f"{slug}.json").write_text(json.dumps(res, indent=1))
    print(table(res))
    if res["n_followed"]:
        spectrum_chart(res, f"{res['name']}: spectrum from SPHEREx exposures").render().save(
            out / f"{slug}_spectrum.png"
        )
        if a.strip:
            print("strip:", strip(res, out, slug, a.strip))
    print(follow.CREDIT)


if __name__ == "__main__":
    main()

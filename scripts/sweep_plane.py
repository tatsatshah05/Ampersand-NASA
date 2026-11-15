"""Run the sweep of the Milky Way's plane (backend/sweep.py) over a list of tiles. Resumable.

    SPHEREX_CACHE_DIR=backend/cache/sweep python scripts/sweep_plane.py            # next tiles, in order
    SPHEREX_CACHE_DIR=backend/cache/sweep python scripts/sweep_plane.py --max-tiles 5
    SPHEREX_CACHE_DIR=backend/cache/sweep python scripts/sweep_plane.py --summary   # tallies so far
    SPHEREX_CACHE_DIR=backend/cache/sweep python scripts/sweep_plane.py --proof     # the V7994 Sgr test tile

Each tile writes `<cache>/sweep_work/tiles/<name>.json` when it is done; a tile with a file is
skipped, so an interrupted run loses at most the tile in progress and the same command carries on.
Pictures of survivors go to `docs/sweep/`. The whole-detector images a tile downloads are deleted
when it is done, so the disk use stays near one tile's worth (about 0.6 GB) plus small files.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time

from backend import photometry, spherex, sweep

PICTURES = ROOT / "docs" / "sweep"
# Tile centres in Galactic coordinates (degrees). A tile answers for the sky nearer to its centre
# than to any other planned centre, so the order below only decides what is done first.
LONGITUDES = [0.0] + [s * v for v in range(3, 31, 3) for s in (1, -1)]
ROWS = (0.0, -2.5, 2.5)
CENTRES = [(float(lo) % 360.0, b) for b in ROWS for lo in LONGITUDES]
GB_MAX_DISK_GB = 6.0
MIN_FREE_GB = 14.0      # stop when the disk would have less than 12 GB free: a tile needs about 0.7 GB in flight


def tile_name(index: int) -> str:
    lo, b = CENTRES[index]
    return f"l{lo:05.1f}_b{b:+04.1f}"


def tile_position(index: int) -> tuple[float, float]:
    lo, b = CENTRES[index]
    c = SkyCoord(lo, b, unit="deg", frame="galactic").icrs
    return float(c.ra.deg), float(c.dec.deg)


def free_gb() -> float:
    return shutil.disk_usage(spherex.CACHE).free / 1e9


def disk_gb() -> float:
    total = sum(f.stat().st_size for f in spherex.CACHE.rglob("*") if f.is_file())
    return total / 1e9


RERUN = PICTURES / "vetting" / "rerun.json"


def summary() -> dict:
    """Totals over every finished tile, with the ruled candidates and the fixed follow-up's checks."""
    rerun = json.loads(RERUN.read_text()) if RERUN.exists() else None
    return sweep.summarise(rerun=rerun)


def _sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    return sweep.sep_deg(ra1, dec1, ra2, dec2) * 3600.0


def describe_candidates(log=print) -> dict:
    """The follow-up of the three ruled candidates again, with the fixed code; nothing else is rerun.

    Uses the first run's cached cutouts (found by the first run's position, which is not reported) and
    asks the catalogues again at the new position. Compares the result with the ruling.
    """
    out: dict = {"made": Time.now().iso[:19] + " UTC", "code": "backend/sweep.py describe, classify",
                 "candidates": {}}
    for v in sweep.vetted_candidates():
        ra0, dec0 = v["first_run_position_withdrawn"]
        folder = spherex._cutout_path({"obs_id": "x", "detector": 0}, ra0, dec0, photometry.CUTOUT_DEG).parent
        paths = sorted(folder.glob("*.fits"))
        tile = json.loads((sweep.TILE_DIR / f"{v['tile']}.json").read_text())
        sv = next(s for s in tile["survivors"] if _sep_arcsec(s["ra"], s["dec"], ra0, dec0) < 1.0)
        tile_images = [{"obs_id": m["obs_id"], "mjy": m["flux_mjy"]} for m in sv["measurements"]
                       if m["epoch"] == sv["pair"]["bright_epoch"] and m["status"] in ("ok", "saturated")]
        log(f"[{v['label']}] {len(paths)} cached cutouts; describing")
        d = sweep.describe([sweep.Cutout.load(p) for p in paths], ra0, dec0, tile_images=tile_images)
        pos = d["position"]
        log(f"[{v['label']}] position {pos['ra']:.5f} {pos['dec']:+.5f}; asking the catalogues")
        cat = sweep.ask_catalogues(pos["ra"], pos["dec"])
        bright = max(e["detectors"]["6"]["fit"]["median"] for k, e in d["epochs"].items()
                     if e["bright"] and e["detectors"].get("6", {}).get("fit", {}).get("median") is not None)
        cls = sweep.classify_with_catalogues(bright, cat)
        off = _sep_arcsec(pos["ra"], pos["dec"], v["ra"], v["dec"])
        faint = d["faint"].get("0", {})
        summary_ = {
            "position_offset_from_ruling_arcsec": round(off, 2),
            "position_within_half_arcsec": off <= 0.5,
            "position_n_exposures": pos["n"], "position_scatter_arcsec": pos["scatter_arcsec"],
            "first_visit_fit_mjy": faint.get("fit", {}).get("median"),
            "first_visit_limit_3sigma_mjy": faint.get("limit_3sigma"),
            "first_visit_old_circle_was_neighbour_light": faint.get("neighbour_light"),
            "first_visit_absent": faint.get("detected") is False,
            "rise_at_least": d.get("rise_at_least"),
            "bright_d6_medians_mjy": {e["dates"][0]: e["detectors"].get("6", {}).get("fit", {}).get("median")
                                      for e in d["epochs"].values() if e["bright"]},
            "catalogue_kind": cls["kind"], "catalogues_failed": cls["catalogues_failed"],
            "at_the_place": cls["circle"]["at_place"],
            "no_false_counterpart": not cls["circle"]["at_place"],
            "brightest_in_reach": cls["circle"]["brightest_in_reach"][:2],
            "possible_emission_line": (d.get("lines") or {}).get("possible_emission_line"),
        }
        points = [{"d": r["detector"], "mjd": r["mjd"], "mjy": r["fit_mjy"]} for r in d["exposures"]
                  if r["status"] == "ok" and r["fit_mjy"] is not None]
        sweep.lightcurve_picture(points, PICTURES / f"candidate_{v['label']}_lightcurve.png",
                                 f"Candidate {v['label']}, RA {v['ra']:.5f} Dec {v['dec']:+.5f}: every clean exposure, "
                                 "fitted with its neighbours modelled (mJy, log scale)")
        out["candidates"][v["label"]] = {"summary": summary_, "describe": d, "classification": cls,
                                         "catalogue_answers": cat["answers"], "catalogue_failed": cat["failed"]}
        log(f"[{v['label']}] {json.dumps(summary_)}")
    RERUN.parent.mkdir(parents=True, exist_ok=True)
    RERUN.write_text(json.dumps(out, indent=1, default=float) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tiles", type=int, default=len(CENTRES), help="stop after this many tiles in this run")
    ap.add_argument("--only", help="run just this tile name (see --list), even if it is done")
    ap.add_argument("--list", action="store_true", help="list the planned tiles and which are done")
    ap.add_argument("--summary", action="store_true", help="print the tallies over finished tiles and exit")
    ap.add_argument("--write", action="store_true", help="with --summary: also save it as docs/sweep/summary.json")
    ap.add_argument("--describe", action="store_true",
                    help="rerun only the follow-up of the three ruled candidates with the fixed code "
                         "(writes docs/sweep/vetting/rerun.json)")
    ap.add_argument("--proof", action="store_true", help="run the proof tile around V7994 Sgr (not part of the sweep)")
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes the tiles whose number is i modulo n")
    ap.add_argument("--min-mjy", type=float, default=sweep.DETECT_MJY)
    args = ap.parse_args()

    done = {p.stem for p in (sweep.TILE_DIR).glob("*.json")}
    if args.list:
        for i in range(len(CENTRES)):
            print(i, tile_name(i), "done" if tile_name(i) in done else "")
        return 0
    log = lambda *a: print(*a, flush=True)  # noqa: E731
    if args.describe:
        describe_candidates(log)
        return 0
    if args.summary:
        s = summary()
        print(json.dumps(s, indent=1))
        if args.write:
            (PICTURES / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
        return 0
    if args.proof:
        # The tile is centred 0.4 degrees from the nova, not on it; nothing tells the method where it is.
        sweep.run_tile("proof_v7994", 270.7, -31.2, pictures_dir=PICTURES, min_mjy=args.min_mjy, log=log)
        print(json.dumps(summary(), indent=1))
        return 0
    todo = [i for i in range(len(CENTRES)) if (tile_name(i) == args.only if args.only else tile_name(i) not in done)]
    k, n_shards = (int(v) for v in args.shard.split("/"))
    todo = [i for i in todo if i % n_shards == k]
    ran = 0
    for i in todo[:args.max_tiles]:
        if disk_gb() > GB_MAX_DISK_GB:
            log(f"the sweep's cache is over {GB_MAX_DISK_GB} GB: stopping")
            break
        if free_gb() < MIN_FREE_GB:
            log(f"only {free_gb():.1f} GB of disk is free (limit {MIN_FREE_GB} GB): stopping; rerun to resume")
            break
        ra, dec = tile_position(i)
        try:
            sweep.run_tile(tile_name(i), ra, dec, centres=[(c[0], c[1]) for c in CENTRES], index=i,
                           pictures_dir=PICTURES, min_mjy=args.min_mjy, log=log)
            ran += 1
        except Exception:  # noqa: BLE001 - one bad tile must not stop the sweep; it is retried on the next run
            log(f"[{tile_name(i)}] FAILED, will be retried on the next run:\n{traceback.format_exc()}")
    print(json.dumps(summary(), indent=1))
    print(f"tiles run now: {ran}; the sweep's cache is {disk_gb():.2f} GB; planned tiles: {len(CENTRES)}")
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    raise SystemExit(main())

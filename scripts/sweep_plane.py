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

from backend import spherex, sweep

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


def summary() -> dict:
    """Totals over every finished tile."""
    return sweep.summarise()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tiles", type=int, default=len(CENTRES), help="stop after this many tiles in this run")
    ap.add_argument("--only", help="run just this tile name (see --list), even if it is done")
    ap.add_argument("--list", action="store_true", help="list the planned tiles and which are done")
    ap.add_argument("--summary", action="store_true", help="print the tallies over finished tiles and exit")
    ap.add_argument("--proof", action="store_true", help="run the proof tile around V7994 Sgr (not part of the sweep)")
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes the tiles whose number is i modulo n")
    ap.add_argument("--min-mjy", type=float, default=sweep.DETECT_MJY)
    args = ap.parse_args()

    done = {p.stem for p in (sweep.TILE_DIR).glob("*.json")}
    if args.list:
        for i in range(len(CENTRES)):
            print(i, tile_name(i), "done" if tile_name(i) in done else "")
        return 0
    if args.summary:
        print(json.dumps(summary(), indent=1))
        return 0
    log = lambda *a: print(*a, flush=True)  # noqa: E731
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

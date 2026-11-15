"""Put the finds of searches already on disk into the watchlist.

    python scripts/watchlist_ingest.py [--fields FILE ...] [--neowise] [--db FILE]

Fields: the five challenge targets at 0.1 degrees (named in warm_cache.py, positions from the
name resolver), the four fields of the first hunt at 0.2 degrees (docs/search.md), and every
field of each --fields file ("name, ra, dec, fov" per line). A field whose search is not on disk
is SKIPPED and named: this script never starts a fresh search (nothing is downloaded for the
missing ones; a search whose catalogue answers are cached finishes in seconds).
--neowise then asks NEOWISE about every brightness change, one request at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend import astrometry, search, watchlist  # noqa: E402

CHALLENGE = ["Barnard's Star", "Epsilon Indi B", "WISE 0855-0714", "RW Aurigae", "R Draconis"]
FIRST_HUNT = [("NGC 1333", 52.265, 31.31), ("Serpens Main", 277.485, 1.23), ("Serpens South", 277.51, -2.05),
              ("Chamaeleon I", 167.4, -77.0)]
DETECTORS = (1, 2, 3, 4, 5, 6)


def on_disk(ra: float, dec: float, fov: float) -> bool:
    """True if the search of this field, in every detector, is already cached (as `search.search` asks for it)."""
    for det in DETECTORS:
        key_text = f"v{search.VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{det},None,True,{search.COMBINE_SIGMA},False"
        key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
        if not (search.SEARCH_DIR / "results" / f"{key}.json").exists():
            return False
    return True


def read_fields(path: Path) -> list[tuple[str, float, float, float]]:
    out = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, ra, dec, fov = (p.strip() for p in line.split(","))
        out.append((name, float(ra), float(dec), float(fov)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fields", type=Path, action="append", default=[])
    parser.add_argument("--neowise", action="store_true", help="then ask NEOWISE about every brightness change")
    parser.add_argument("--db", type=Path, default=None, help="watchlist database (default: the cache's)")
    args = parser.parse_args()
    if args.db:
        os.environ[watchlist.DB_ENV] = str(args.db)

    fields: list[tuple[str, float, float, float]] = []
    for name in CHALLENGE:
        try:
            r = astrometry.resolve_name(name)
            fields.append((name, float(r["ra"]), float(r["dec"]), 0.1))
        except Exception as e:  # noqa: BLE001 - reported and skipped
            print(f"SKIPPED {name}: could not resolve the name ({e})")
    fields += [(n, ra, dec, 0.2) for n, ra, dec in FIRST_HUNT]
    for path in args.fields:
        fields += read_fields(path)

    skipped = []
    for name, ra, dec, fov in fields:
        if not on_disk(ra, dec, fov):
            skipped.append(name)
            print(f"SKIPPED {name} ({ra}, {dec}, {fov}): its search is not on disk")
            continue
        result = search.search(ra, dec, fov, DETECTORS, fetch=search.fetch_to_own_cache)
        got = watchlist.ingest(result, queue_neowise=False)
        print(f"{name}: {len(result['objects'])} objects, {len(result['rejected'])} set aside, "
              f"{got['added']} new rows")
    print(f"skipped: {', '.join(skipped) if skipped else 'none'}")
    if args.neowise:
        print(f"NEOWISE asked about {watchlist.neowise_now()} brightness changes")
    counts = watchlist.list_rows(limit=1)
    print("rows per group:", counts["counts"], "patches:", counts["patches_searched"])


if __name__ == "__main__":
    main()

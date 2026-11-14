"""Resolve the five test targets and print where each one is at 2026.0.

Run:  .venv/bin/python scripts/check_resolve.py [name ...]

Barnard's Star must come back within a few arcsec of RA 269.4463, Dec +4.7682.
Results are cached in backend/cache/queries/resolve_*.json; delete those to ask again.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry  # noqa: E402

NAMES = sys.argv[1:] or ["Barnard's Star", "Epsilon Indi B", "WISE 0855-0714", "RW Aurigae", "R Draconis"]

for name in NAMES:
    try:
        r = astrometry.resolve_name(name)
    except (astrometry.NameNotFound, astrometry.ArchiveError) as e:
        print(f"{name}: FAILED  {type(e).__name__}: {e}")
        continue

    def fmt(v, spec="+.2f"):
        return "unknown" if v is None else format(v, spec)
    print(f"{name}  ->  {r['name']} ({r['object_type']}), from {r['source']}"
          + (f" {r['gaia_source_id']}" if r["source"] == "Gaia DR3" else ""))
    print(f"   RA {r['ra']:.6f}  Dec {r['dec']:+.6f}  at {r['epoch']}   "
          f"pm ({fmt(r['pmra'])}, {fmt(r['pmdec'])}) mas/yr  parallax {fmt(r['parallax'], '.2f')} mas  "
          f"moved {r['moved_since_2000_arcsec']:.1f} arcsec since 2000")
    for note in r["notes"]:
        print(f"   note: {note}")
    if r["name"] == "NAME Barnard's star":
        east, north = astrometry.offset_arcsec(269.4463, 4.7682, r["ra"], r["dec"])
        print(f"   check: {np.hypot(east, north):.2f} arcsec from RA 269.4463, Dec +4.7682")

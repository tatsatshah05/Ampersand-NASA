"""Fetch every SPHEREx cutout covering Barnard's Star and time it.

Run:  .venv/bin/python scripts/download_barnard.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import spherex  # noqa: E402

RA, DEC = 269.446267, 4.768222   # Gaia DR3 position propagated to 2026.0
SIZE = 0.15                      # degrees: 0.1 deg field plus margin for detector rotation

t = time.time()
exposures = spherex.find_exposures(RA, DEC)
print(f"{len(exposures)} exposures found in {time.time() - t:.1f}s")
t = time.time()
results = spherex.fetch_cutouts(
    exposures, RA, DEC, SIZE,
    progress=lambda n, total: print(f"  {n}/{total}  {time.time() - t:5.0f}s", flush=True) if n % 40 == 0 else None)
dt = time.time() - t
failed = [(e["obs_id"], e["detector"], err) for e, p, err in results if p is None]
print(f"{len(results) - len(failed)} cutouts in {dt:.0f}s ({dt / len(results):.2f}s each, "
      f"{spherex.MAX_CONCURRENT} at a time); {len(failed)} failed")
for f in failed:
    print("  FAILED", f)

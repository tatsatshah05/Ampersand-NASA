"""Print the table of followed bodies (for docs/comets.md) from the JSON files that scripts/follow_body.py wrote.

Run:  .venv/bin/python scripts/comets_table.py [DIR]       (DIR defaults to docs/comets)

One row per body: how many exposures contain it, how many gave a usable measurement, and for each gas band the
best visit (the one with the largest excess over its error) in the large circle, with the verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def best_visit(res: dict, band: str, key: str = "bands_large") -> str:
    best = None
    for v in res.get(key, []):
        b = v["bands"][band]
        if b["ok"] and (best is None or b["sigma"] > best[1]["sigma"]):
            best = (v, b)
    if best is None:
        return "no usable channels in the band"
    v, b = best
    return (
        f"{b['excess_mjy']:+.2f} +- {b['err_mjy']:.2f} mJy ({b['sigma']:+.1f}x), {b['verdict']}, "
        f"visit {v['first'][:10]} ({b['n_band']} in band)"
    )


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "comets"
    print("| Body | Exposures containing it | Measured | Usable | Predicted mag | H2O 2.7 | CO2 4.26 | CO 4.67 |")
    print("|---|---|---|---|---|---|---|---|")
    for f in sorted(folder.glob("*.json")):
        res = json.loads(f.read_text())
        if "points" not in res:
            continue
        counts = res.get("counts", {})
        mag = res["vmag_range"]
        mags = "?" if mag[0] is None else f"{mag[0]} to {mag[1]}"
        print(
            f"| {res['name']} | {res['n_in_footprint']} | {res['n_followed']} | {counts.get('ok', 0)} | {mags} | "
            f"{best_visit(res, 'H2O')} | {best_visit(res, 'CO2')} | {best_visit(res, 'CO')} |"
        )


if __name__ == "__main__":
    main()

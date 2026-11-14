"""Numbers for docs/search.md from the output of scripts/search_fields.py.

Run:  .venv/bin/python scripts/search_report.py <out folder> [<out folder> ...]

Prints, from the field.json files it finds: how many sources were found, set aside and
tested in each field and detector; how many candidates came out and of which grade; and
how small a motion or a change the tested sources could have shown, by brightness. No
network access: it only reads the files.
"""
import json
import sys
from pathlib import Path

import numpy as np

# With the errors the search reports, a source is a 5 sigma mover when its speed is
# about 5.4 times its speed error (two directions), and a 5 sigma changer when the
# change between two visits is about 5.5 to 6 times its error (few channels, so the
# t distribution, not the Gaussian). These are used only to turn errors into "smallest
# detectable" figures for the table.
SPEED_FACTOR = 5.4
CHANGE_FACTOR = 5.8


def main() -> None:
    files = sorted(p for folder in sys.argv[1:] for p in Path(folder).glob("*/field.json"))
    if not files:
        sys.exit("no field.json found: pass the --out folder of scripts/search_fields.py")
    total = {"runs": 0, "sources": 0, "glow": 0, "position": 0, "brightness": 0, "seconds": 0.0}
    speed: list[tuple[float, float, float]] = []      # (flux, speed error, median position error)
    change: list[tuple[float, float]] = []            # (flux, smallest change error over the pairs)
    faint: dict[str, list[float]] = {}                # detector -> brightness of every tested source
    print(f"{'field':<14s} det visits(exposures)        found glow moved? changed? refs  5-sigma candidates")
    for path in files:
        field = json.loads(path.read_text())
        for det, r in field["per_detector"].items():
            if "sources" not in r:
                print(f"{field['name']:<14s} D{det}  {r.get('message')}")
                continue
            total["runs"] += 1
            total["sources"] += r["n_sources"]
            total["glow"] += r["n_sources_on_glow_not_tested"]
            total["position"] += r["n_sources_position_tested"]
            total["brightness"] += r["n_sources_brightness_tested"]
            total["seconds"] += r["seconds"]
            passed = [f"{c['id']} {c['kind']} {c['sigma']} {c['grade']}" for c in r["candidates"] if c["passes"]]
            print(f"{field['name']:<14s} D{det}  {str([v['n_exposures'] for v in r['visits']]):<24s} "
                  f"{r['n_sources']:5d} {r['n_sources_on_glow_not_tested']:4d} {r['n_sources_position_tested']:6d} "
                  f"{r['n_sources_brightness_tested']:8d} {r['position_errors']['n_reference_stars']:4d}  "
                  + ("; ".join(passed) or "-"))
            for s in r["sources"]:
                if ("halo" in s["flags"] or s["typical_flux_mjy"] is None or s["typical_flux_mjy"] <= 0
                        or s.get("measure") == "ring"):
                    continue
                if "saturated" not in s["flags"]:
                    faint.setdefault(det, []).append(s["typical_flux_mjy"])
                errs = [e for e in s["position_err_arcsec"] if e is not None]
                if s["speed_err"] is not None and errs and not s["flags"]:
                    speed.append((s["typical_flux_mjy"], s["speed_err"], float(np.median(errs))))
                pairs = [c[3] for c in s["changes"] if c[6] >= 6]
                if pairs and not s["flags"]:
                    change.append((s["typical_flux_mjy"], min(pairs)))
    print(f"\n{total['runs']} searches (field x detector): {total['sources']} sources found, {total['glow']} set aside "
          f"(on the glow of a brighter star), {total['position']} tested for motion, {total['brightness']} tested "
          f"for brightness change; {total['seconds'] / max(total['runs'], 1):.1f} s per search on average")
    objects = [(f, o) for f in (json.loads(p.read_text()) for p in files) for o in f["objects"]]
    n_clean = sum(o["grade"] == "clean" for _, o in objects)
    print(f"{len(objects)} objects reported: {n_clean} clean, {len(objects) - n_clean} caution")
    for f, o in objects:
        alone = "".join(map(str, o["detectors_at_5_sigma"])) or "-"
        print(f"   {f['name']:<14s} {o['id']} {o['kind']:<7s} {o['grade']:<7s} best {o['sigma_best']:5.1f} "
              f"in D{o['best_detector']} combined {o['sigma_combined']:5.1f}  5-sigma in D{alone}  "
              f"{o['category']}  {o['flags'] or ''}")

    print("\nFaintest sources found and tested (aperture brightness, mJy), by detector:")
    for det in sorted(faint):
        values = np.sort(np.array(faint[det]))
        print(f"   D{det}: {values.size} sources; faintest {values[0]:.3f}, 5th percentile "
              f"{np.percentile(values, 5):.3f}, median {np.median(values):.2f}")

    print("\nSmallest motion a clean source could have shown at 5 sigma, by brightness:")
    table(speed, lambda rows: f"position error per visit {np.median([r[2] for r in rows]):.2f} arcsec, speed error "
                              f"{np.median([r[1] for r in rows]):.2f}, so about "
                              f"{SPEED_FACTOR * np.median([r[1] for r in rows]):.1f} arcsec/yr")
    print("\nSmallest brightness change a clean source could have shown at 5 sigma, by brightness:")
    table(change, lambda rows: f"error of the change {100 * np.median([r[1] for r in rows]):.1f} per cent, so about "
                               f"{100 * CHANGE_FACTOR * np.median([r[1] for r in rows]):.0f} per cent")


def table(rows: list[tuple], describe) -> None:
    edges = [0.0, 0.5, 2.0, 10.0, 100.0, float("inf")]
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        part = [r for r in rows if lo <= r[0] < hi]
        if part:
            top = f"{hi:g}" if np.isfinite(hi) else "more"
            print(f"   {lo:g} to {top} mJy ({len(part)} sources): {describe(part)}")


if __name__ == "__main__":
    main()

"""Run the distant-world search on real fields and count how many planted objects it finds.

    python scripts/check_distant.py                 # the fields below, 0.2 degrees, detectors 5 and 6
    python scripts/check_distant.py --fov 0.5 --fields wise0855,rwaur
    python scripts/check_distant.py --seeds 40

For each field it prints (and writes to docs/distant/results.json):
1. The real answer of `distant.distant_search`: candidates, the limit at each distance,
   and the number of links the same search makes with the Earth's motion reversed.
2. A recovery count. The practice round's made-up object (`training.py`) is added to the
   real stacks of detector 5, at each level and for many seeds, and searched for. This is
   the only use of planted objects: counting what the search can find. Nothing planted is
   written to the cache or to any real answer.

Needs the data cache and the network (cutouts not yet on disk are read from NASA's archive,
CatWISE2020 from IRSA). Results: docs/distant.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.simplefilter("ignore")

from backend import distant, spherex, training  # noqa: E402

FIELDS = {
    "wise0855": ("WISE 0855-0714", 133.759765, -7.242182),
    "barnard": ("Barnard's Star", 269.446267, 4.768222),
    "epsindib": ("Epsilon Indi B", 331.096653, -56.800663),
    "rwaur": ("RW Aurigae", 76.956587, 30.401291),
    "rdra": ("R Draconis", 248.167233, 66.755024),
    "ngc1333": ("NGC 1333", 52.265, 31.31),
    "serpmain": ("Serpens Main", 277.485, 1.23),
    "serpsouth": ("Serpens South", 277.51, -2.05),
    "chami": ("Chamaeleon I", 167.4, -77.0),
}
OUT = Path(__file__).resolve().parent.parent / "docs" / "distant" / "results.json"


def recovery(ra: float, dec: float, fov: float, detector: int, seeds: int, catalogue: list[dict] | None) -> dict:
    """Plant the practice object many times and count how often the search finds it."""
    grid, n, stacks, items, _ = training.epoch_stacks(ra, dec, fov, detector)
    out: dict = {"detector": detector, "seeds": seeds, "levels": {}}
    if len(stacks) < 3:
        out["note"] = f"{len(stacks)} visit(s): cannot be searched"
        return out
    for level in training.LEVELS:
        found = bright_enough = bright_found = wrong = unplaced = 0
        flux = None
        for seed in range(1, seeds + 1):
            try:
                images, truth = distant._planted_images(ra, dec, fov, detector, grid, n, stacks, items, level, seed)
            except spherex.BadRequest:
                unplaced += 1
                continue
            flux = truth["flux_mjy"]
            field = distant.search_stacks(grid, n, images, items, detector, ra, dec, fov, catalogue=catalogue,
                                          as_planted=True)
            strengths = []
            for k, spot in enumerate(truth["positions"]):
                x, y = grid.all_world2pix(spot["ra"], spot["dec"], 0)
                got = distant._sample(field["maps"][k], float(x), float(y))
                strengths.append(got[0] / got[1] if got and got[1] > 0 else 0.0)
            strengths.sort(reverse=True)
            hit = any(abs(link["distance_au"] / truth["distance_au"] - 1.0) < 0.15 for link in field["links"])
            enough = strengths[1] >= distant.DETECT_SIGMA and strengths[2] >= distant.MEMBER_SIGMA
            found += hit
            bright_enough += enough
            bright_found += hit and enough
            wrong += len(field["links"]) - int(hit)
        out["levels"][level] = {"flux_mjy": flux, "planted": seeds - unplaced, "found": found,
                                "bright_enough": bright_enough, "bright_enough_and_found": bright_found,
                                "other_links": wrong}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fields", default=",".join(FIELDS), help="comma-separated keys: " + ", ".join(FIELDS))
    parser.add_argument("--fov", type=float, default=0.2)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--detectors", default="56")
    args = parser.parse_args()
    detectors = tuple(int(c) for c in args.detectors)
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for key in args.fields.split(","):
        name, ra, dec = FIELDS[key]
        started = time.time()
        try:
            answer = distant.distant_search(ra, dec, args.fov, detectors)
        except Exception as e:  # noqa: BLE001 - one field failing must not stop the others
            print(f"\n## {name}: FAILED {type(e).__name__}: {e}", flush=True)
            continue
        print(f"\n## {name} ({ra}, {dec}), {args.fov} degrees, {time.time() - started:.0f} s", flush=True)
        print(answer["answer"])
        print(f"links with the Earth's motion reversed: {answer['chance']['links_with_earth_reversed']}; "
              f"catalogue answered: {answer['catalogue']['answered']}; failures: {len(answer['failures'])}")
        for d in answer["per_detector"]:
            print(f"  detector {d['detector']}: sources {[v['sources'] for v in d['visits']]}, come and go "
                  f"{d['come_and_go']}, catalogued {d['set_aside_catalogued']}, not point-like "
                  f"{d['set_aside_not_point_like']}, tried {d['linked_from']}, links {d['links']}, "
                  f"clear sky {d['clear_share']}")
        for row in answer["limit"]:
            print(f"  {row['distance_au']:>6} AU: jump {row['jump_arcsec']:>6} arcsec, brighter than "
                  f"{row['faintest_mjy']} mJy (detector {row['detector']}), {row['share_of_picture']:.0%} of the "
                  f"picture, smear {row['smear_arcsec']} arcsec")
        for c in answer["candidates"]:
            print(f"  CANDIDATE detector {c['detector']}: {c['distance_au']} AU {c['distance_range_au']}, "
                  f"{c['verdict']}: {c['cautions']}")
            for p in c["positions"]:
                print(f"     visit {p['epoch']} {p['date']}: {p['ra']}, {p['dec']}  {p['times_noise']} x noise, "
                      f"{p['flux_mjy']} mJy")
        try:
            catalogue = distant.catwise_field(ra, dec, args.fov)
        except Exception:  # noqa: BLE001
            catalogue = None
        counts = recovery(ra, dec, args.fov, detectors[0], args.seeds, catalogue)
        for level, c in counts.get("levels", {}).items():
            print(f"  planted {level} ({c['flux_mjy']} mJy): found {c['found']} of {c['planted']}; bright enough in "
                  f"three visits {c['bright_enough']}, of which found {c['bright_enough_and_found']}; other links "
                  f"{c['other_links']}", flush=True)
        results[f"{key}@{args.fov}"] = {
            "name": name, "ra": ra, "dec": dec, "fov": args.fov, "status": answer["status"],
            "answer": answer["answer"], "candidates": answer["candidates"], "limit": answer["limit"],
            "chance_links": answer["chance"]["links_with_earth_reversed"],
            "per_detector": [{k: d[k] for k in ("detector", "exposures", "come_and_go", "set_aside_catalogued",
                                                "set_aside_not_point_like", "linked_from", "links", "chance_links",
                                                "clear_share", "visits")} for d in answer["per_detector"]],
            "catalogue_answered": answer["catalogue"]["answered"], "failures": len(answer["failures"]),
            "recovery": counts}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()

"""Search a list of sky fields for sources that move or change brightness, unattended.

Run (from the project root):

  .venv/bin/python scripts/search_fields.py --field "Barnard,269.446267,4.768222" --detectors 56
  .venv/bin/python scripts/search_fields.py --fields fields.txt --detectors 123456 --out scripts/out/search --jobs 3

A fields file has one field per line: name, ra, dec in degrees, and optionally the field
of view in degrees (default --fov, at most 0.5), separated by commas. Lines starting
with # are skipped.

For every field this writes, under <out>/<name>/:
  field.json     everything: one entry per object with its evidence and catalogue check,
                 and under "per_detector" the full result of each detector, including
                 every source that was tested and why it was or was not a candidate
  D5-01_mover.png, ...   one small picture per candidate of each detector
and, for all fields together, <out>/summary.json: every object of every field in one
list, the cleanest and most significant first, with the path of its pictures.

Nothing is asked of you while it runs. A field that fails (archive down, no coverage)
is recorded in summary.json with the reason and the others carry on. Catalogue answers
and SPHEREx cutouts are cached, so a second run of the same field is much faster.

--fetch module:function swaps the way cutouts are fetched (same arguments and return
value as backend.spherex.fetch_cutouts), for instance a direct read from the AWS bucket.
"""
import argparse
import importlib
import json
import re
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import search  # noqa: E402

# How the three kinds of result the hunt is after are told apart (see docs/search.md).
HEADLINES = {
    "known_variable": "a. known variable that changed in this data",
    "changer_not_listed_as_variable": "b. changed; counterpart not listed as variable",
    "changer_no_counterpart": "b. changed; no catalogue counterpart at all",
    "mover_no_counterpart": "c. moved; no catalogue counterpart",
    "mover_motion_not_in_catalogues": "c. moved; no catalogue object has this motion",
    "known_mover": "known mover (catalogue motion agrees)",
}


def parse_field(text: str, default_fov: float) -> dict:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) not in (3, 4):
        raise ValueError(f"a field is 'name, ra, dec[, fov]': got '{text}'")
    return {"name": parts[0], "ra": float(parts[1]), "dec": float(parts[2]),
            "fov": float(parts[3]) if len(parts) == 4 else default_fov}


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "field"


def run_field(job: dict) -> dict:
    """Search one field in the chosen detectors and write its files. Never raises."""
    field, out = job["field"], Path(job["out"])
    folder = out / slug(field["name"])
    started = time.time()
    try:
        fetch = None
        if job["fetch"]:
            module, _, function = job["fetch"].partition(":")
            fetch = getattr(importlib.import_module(module), function)
        result = search.search_detectors(
            field["ra"], field["dec"], field["fov"], tuple(job["detectors"]), figures_dir=folder,
            catalogues=job["catalogues"], bin_days=job["bin_days"], fetch=fetch, offline=job["offline"])
        result["name"] = field["name"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "field.json").write_text(json.dumps(result, indent=1))
        tested = sum(r.get("n_sources", 0) - r.get("n_sources_on_glow_not_tested", 0)
                     for r in result["per_detector"].values())
        return {"name": field["name"], "ok": True, "folder": str(folder), "seconds": round(time.time() - started, 1),
                "sources_tested": tested, "objects": result["objects"],
                "failures": {d: r["failures"] for d, r in result["per_detector"].items() if r.get("failures")},
                "messages": {d: r["message"] for d, r in result["per_detector"].items() if r.get("message")},
                "catalogue_failures": {d: r["catalogues"]["failed"] for d, r in result["per_detector"].items()
                                       if r.get("catalogues", {}).get("failed")}}
    except Exception as e:  # noqa: BLE001 - one bad field must not stop the list
        return {"name": field["name"], "ok": False, "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(limit=6), "seconds": round(time.time() - started, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--field", action="append", default=[], help="'name,ra,dec[,fov]' in degrees; repeatable")
    parser.add_argument("--fields", help="text file with one 'name, ra, dec[, fov]' per line")
    parser.add_argument("--detectors", default="123456", help="detectors to search, as digits (default 123456)")
    parser.add_argument("--fov", type=float, default=0.1, help="field of view in degrees when a field gives none")
    parser.add_argument("--out", default=str(ROOT / "scripts" / "out" / "search"), help="output folder")
    parser.add_argument("--bin-days", type=float, default=None,
                        help="split each visit at gaps longer than this many days for the brightness test")
    parser.add_argument("--jobs", type=int, default=1, help="fields searched at the same time")
    parser.add_argument("--fetch", default=None, help="module:function to fetch cutouts with")
    parser.add_argument("--no-catalogues", action="store_true", help="skip the catalogue check")
    parser.add_argument("--offline", action="store_true",
                        help="use only cutouts already in the cache and the cached list of exposures (no download)")
    args = parser.parse_args()

    fields = [parse_field(text, args.fov) for text in args.field]
    if args.fields:
        for line in Path(args.fields).read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                fields.append(parse_field(line, args.fov))
    if not fields:
        parser.error("give --field or --fields")
    detectors = sorted({int(ch) for ch in args.detectors})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [{"field": f, "out": str(out), "detectors": detectors, "bin_days": args.bin_days, "fetch": args.fetch,
             "catalogues": not args.no_catalogues, "offline": args.offline} for f in fields]

    started = time.time()
    if args.jobs > 1:
        with ProcessPoolExecutor(args.jobs) as pool:
            done = list(pool.map(run_field, jobs))
    else:
        done = []
        for job in jobs:
            done.append(run_field(job))
            last = done[-1]
            state = f"{len(last['objects'])} objects" if last["ok"] else "FAILED: " + last["error"]
            print(f"[{len(done)}/{len(jobs)}] {last['name']}: {state} in {last['seconds']} s", flush=True)

    rows = []
    for d in done:
        for obj in d.get("objects", []):
            rows.append({
                "field": d["name"], "id": obj["id"], "kind": obj["kind"], "grade": obj["grade"], "flags": obj["flags"],
                "headline": HEADLINES.get(obj["category"], obj["category"]), "label": obj["label"],
                "category": obj["category"], "ra": obj["ra"], "dec": obj["dec"],
                "sigma_best": obj["sigma_best"], "sigma_combined": obj["sigma_combined"],
                "found_by": obj["found_by"], "detectors_at_5_sigma": obj["detectors_at_5_sigma"],
                "detectors_at_3_sigma": obj["detectors_at_3_sigma"], "summary": obj["summary"],
                "catalogues_answered": obj["catalogue"]["answered"],
                "catalogues_failed": sorted(obj["catalogue"]["failed"]),
                "pictures": [str(Path(d["folder"]) / m["figure"]) for m in obj["by_detector"].values()
                             if m.get("figure")]})
    rows.sort(key=lambda r: (r["grade"] != "clean", r["headline"], -r["sigma_combined"]))
    summary = {"fields": [{k: v for k, v in d.items() if k != "objects"} | {"n_objects": len(d.get("objects", []))}
                          for d in done],
               "detectors": detectors, "objects": rows, "seconds": round(time.time() - started, 1)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))

    print(f"\n{len(fields)} fields, {sum(d['ok'] for d in done)} searched, {len(rows)} objects, "
          f"{summary['seconds']} s. Wrote {out / 'summary.json'}")
    for r in rows:
        where = "".join(str(x) for x in r["detectors_at_5_sigma"]) or "-"
        print(f"  {r['grade']:7s} {r['field']:<16s} {r['id']} {r['kind']:<7s} {r['sigma_combined']:5.1f} sigma "
              f"(5 sigma in D{where}; 3 sigma in D{''.join(str(x) for x in r['detectors_at_3_sigma']) or '-'}) "
              f"RA {r['ra']:.5f} Dec {r['dec']:+.5f}  {r['headline']}"
              + (f"  [{', '.join(r['flags'])}]" if r["flags"] else ""))
    for d in done:
        if not d["ok"]:
            print(f"  FAILED {d['name']}: {d['error']}")
        elif d["failures"] or d["catalogue_failures"] or d["messages"]:
            print(f"  note {d['name']}: download failures {sum(len(v) for v in d['failures'].values())}; "
                  f"catalogues not reached {sorted({k for v in d['catalogue_failures'].values() for k in v})}; "
                  f"messages {d['messages']}")


if __name__ == "__main__":
    main()

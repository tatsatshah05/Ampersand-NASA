"""Export what the "Observe anomalies" screen reads about the sweep of the Milky Way's plane:
frontend/public/anomalies/sweep.json.

    python scripts/export_anomalies.py            # write it (reads the sweep's tile records from the cache)
    python scripts/export_anomalies.py --check    # offline: exit 1 if sweep.json is out of date with the docs

The docs folder is not shipped with the app (the Docker build leaves it out), so the screen cannot read
docs/sweep/summary.json or docs/sweep.md itself. This script copies what it needs, unchanged:

- from docs/sweep/summary.json: the tallies, the area, and each of the 14 survivors' tile, position, kind,
  direction and brightness; for the three candidates, the ruling's corrected position in both notations, its
  error, the allowed sentence, the last non-detection, the first detection, the rise and the visits;
- from docs/sweep.md: the date the sweep was written up and the date it was rewritten from the vetting ruling, the
  area as the write-up rounds it, the three visits, the names and evidence of the two known eruptions ("Known
  eruptions recovered") and the reason each of the three set-aside survivors was set aside ("Looked at and set
  aside"), matched to the survivors by position;
- from the sweep's own tile records (<cache>/sweep_work/tiles/<tile>.json, which are not in git): the catalogue
  rows that explain the six known variables and the two known eruptions (`catalogue_*` fields). They are read only
  for those two kinds: a candidate's tile record holds the sweep's first, withdrawn position and must never be shown.

It computes one thing: the constellation each survivor lies in (astropy's boundaries, backend.watchlist).

`--check` builds the same file again from the docs and compares; the tile-record fields are compared too when the
tile records are on disk (`--tiles`, by default <SPHEREX_CACHE_DIR>/sweep/sweep_work/tiles), and otherwise said to be
unchecked. Nothing is typed in: a value the docs do not give is left out, never made up.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
SUMMARY = "docs/sweep/summary.json"
WRITEUP = "docs/sweep.md"
OUT = ROOT / "frontend" / "public" / "anomalies" / "sweep.json"
KINDS = ("candidate", "known_eruption", "known_variable", "set_aside")
# Fields that come from the tile records in the cache; --check compares them only when those are on disk.
TILE_FIELDS = ("catalogue_name", "catalogue", "catalogue_text", "catalogue_reasons")
# The catalogue whose name stands for a known variable, in this order of preference: the infrared ones first.
CATALOGUE_ORDER = ("AllWISE", "CatWISE2020", "GLIMPSE", "2MASS", "AAVSO VSX", "SIMBAD", "Gaia DR3")
MATCH_ARCSEC = 3.0  # a write-up table row is this survivor when their positions agree this well
FIELDS_ON_EVERY_SURVIVOR = ("kind", "tile", "ra", "dec", "constellation", "direction")
FIELDS_BY_KIND = {
    "candidate": ("label", "sexagesimal", "position_error_arcsec", "allowed_sentence", "last_non_detection",
                  "first_detection", "rise", "visits_d6"),
    "known_eruption": ("known_as", "bright_text", "evidence"),
    "known_variable": ("bright_mjy",),
    "set_aside": ("bright_mjy", "why"),
}


def default_tiles() -> Path:
    cache = Path(os.environ.get("SPHEREX_CACHE_DIR") or ROOT / "backend" / "cache")
    return cache / "sweep" / "sweep_work" / "tiles"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Angular distance in arcseconds (small angles, the short way round in right ascension)."""
    dra = (ra2 - ra1 + 180.0) % 360.0 - 180.0
    east = dra * math.cos(math.radians((dec1 + dec2) / 2.0))
    return math.hypot(east, dec2 - dec1) * 3600.0


# ------------------------------------------------------------------------------------------- the write-up


def _match(pattern: str, text: str, what: str) -> re.Match[str]:
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"{WRITEUP}: cannot find {what}")
    return m


def table_after(heading: str, text: str) -> list[list[str]]:
    """The rows (cells stripped) of the first Markdown table after a heading, without its header and rule."""
    start = _match(r"(?m)^#+ " + re.escape(heading) + r".*$", text, f"the heading '{heading}'").end()
    rows: list[list[str]] = []
    started = False
    for line in text[start:].splitlines():
        if line.startswith("|"):
            started = True
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif started:
            break
    if len(rows) < 3:
        raise ValueError(f"{WRITEUP}: the table after '{heading}' has no rows")
    return rows[2:]


def position_in(cell: str) -> tuple[float, float]:
    m = _match(r"RA (\d+\.\d+), Dec ([+-]?\d+\.\d+)", cell, f"a position in '{cell[:40]}'")
    return float(m.group(1)), float(m.group(2))


def from_writeup(text: str) -> dict[str, Any]:
    """What the screen needs from docs/sweep.md, as the write-up words it."""
    eruptions = [{"known_as": r[0], "position": position_in(r[1]), "bright_text": r[2], "evidence": r[3]}
                 for r in table_after("Known eruptions recovered", text)]
    set_aside = [{"position": position_in(r[0]), "why": r[1]} for r in table_after("Looked at and set aside", text)]
    return {
        "swept": _match(r"Written (\d{4}-\d{2}-\d{2})", text, "the date it was written").group(1),
        "ruled": _match(r"rewritten on\s+(\d{4}-\d{2}-\d{2})", text, "the date it was rewritten").group(1),
        "area_text": _match(r"\*\*Area: all \d+ planned tiles are done, ([\d.,]+) square degrees\*\*", text,
                            "the area").group(1),
        "visits": " ".join(_match(r"three times\s*\(([^)]*)\)", text, "the three visits").group(1).split()),
        "eruptions": eruptions,
        "set_aside": set_aside,
    }


# ------------------------------------------------------------------------------------------- the tile records


def _reason_parts(reason: str) -> tuple[str, str, str] | None:
    """'WISEA J175109.30-263700.0 (AllWISE) W2 9.76 mag = 21 mJy, already bright' -> name, catalogue, the rest."""
    m = re.match(r"^(.+?) \(([^()]+)\) (.+)$", reason)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def catalogue_fields(classification: dict[str, Any]) -> dict[str, Any]:
    """The catalogue rows a tile record gives for a known variable or eruption, and the one that names it."""
    reasons = [str(r) for r in classification.get("reasons") or []]
    out: dict[str, Any] = {"catalogue_reasons": reasons}
    by = classification.get("by")
    if by:  # a known eruption: the variable-star catalogue's row
        out.update(catalogue_name=by["name"], catalogue=by["catalogue"], catalogue_text=reasons[0] if reasons else None)
        return out
    parsed = [(p, r) for r in reasons if (p := _reason_parts(r))]
    if parsed:
        rank = {c: i for i, c in enumerate(CATALOGUE_ORDER)}
        (name, catalogue, _), text = min(parsed, key=lambda x: rank.get(x[0][1], len(rank)))
        out.update(catalogue_name=name, catalogue=catalogue, catalogue_text=text)
    return out


def from_tiles(tiles: Path, survivors: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """The tile-record fields of each known variable and eruption, by its index in `survivors`."""
    out: dict[int, dict[str, Any]] = {}
    for i, s in enumerate(survivors):
        if s["kind"] not in ("known_variable", "known_eruption"):
            continue  # never a candidate's or a set-aside source's tile record (see the module's docstring)
        record = json.loads((tiles / f"{s['tile']}.json").read_text())
        near = [t for t in record.get("survivors", []) if sep_arcsec(s["ra"], s["dec"], t["ra"], t["dec"]) < 1.0]
        if len(near) != 1:
            raise ValueError(f"{s['tile']}: {len(near)} tile survivors at {s['ra']}, {s['dec']}")
        called = near[0]["classification"]["kind"]
        if called != s["kind"]:
            raise ValueError(f"{s['tile']}: the tile record calls {s['ra']}, {s['dec']} {called}")
        out[i] = catalogue_fields(near[0]["classification"])
    return out


# ------------------------------------------------------------------------------------------- the export


def build(root: Path = ROOT, tiles: Path | None = None) -> dict[str, Any]:
    """The export, from the docs under `root` and (when given) the tile records in `tiles`."""
    sys.path.insert(0, str(ROOT))
    from backend.watchlist import constellations

    summary_path = root / SUMMARY
    summary = json.loads(summary_path.read_text())
    words = from_writeup((root / WRITEUP).read_text())
    raw = summary["survivors"]
    names = constellations([(s["ra"], s["dec"]) for s in raw])
    tile_parts = from_tiles(tiles, raw) if tiles is not None else {}
    survivors = []
    for i, (s, constellation) in enumerate(zip(raw, names, strict=True)):
        kind = s["kind"]
        if kind not in KINDS:
            raise ValueError(f"{SUMMARY}: unknown kind {kind}")
        out: dict[str, Any] = {"kind": kind, "tile": s["tile"], "ra": s["ra"], "dec": s["dec"],
                               "constellation": constellation, "direction": s["direction"]}
        if kind == "candidate":
            out.update({k: s[k] for k in FIELDS_BY_KIND["candidate"]})
            out["constellation_ruled"] = s["constellation"]
        else:
            out["bright_mjy"] = s["bright_mjy"]
        if kind == "known_eruption":
            row = [e for e in words["eruptions"] if sep_arcsec(s["ra"], s["dec"], *e["position"]) <= MATCH_ARCSEC]
            if len(row) != 1:
                raise ValueError(f"{WRITEUP}: no single known eruption at {s['ra']}, {s['dec']}")
            out.update(known_as=row[0]["known_as"], bright_text=row[0]["bright_text"], evidence=row[0]["evidence"])
        if kind == "set_aside":
            row = [e for e in words["set_aside"] if sep_arcsec(s["ra"], s["dec"], *e["position"]) <= MATCH_ARCSEC]
            if len(row) != 1:
                raise ValueError(f"{WRITEUP}: no single set-aside row at {s['ra']}, {s['dec']}")
            out["why"] = row[0]["why"]
        out.update(tile_parts.get(i, {}))
        survivors.append(out)
    order = {k: n for n, k in enumerate(KINDS)}
    survivors.sort(key=lambda s: (order[s["kind"]], s.get("label") or "", s["ra"]))
    counts = {k: sum(s["kind"] == k for s in survivors) for k in KINDS}
    if counts != {k: summary["survivors_by_kind"][k] for k in KINDS}:
        raise ValueError(f"{SUMMARY}: survivors_by_kind does not match its list of survivors")
    return {
        "schema": SCHEMA,
        "about": "The sweep of the Milky Way's plane for infrared sources that appeared between SPHEREx's visits: "
                 "its 14 survivors, copied from docs/sweep/summary.json and docs/sweep.md by "
                 "scripts/export_anomalies.py. 'candidate' means a source we found in no catalogue or report we "
                 "checked; nobody has confirmed it and nothing has been reported.",
        "source": {
            "summary": SUMMARY,
            "summary_sha256": sha256_file(summary_path),
            "writeup": WRITEUP,
            "tiles": "<SPHEREX_CACHE_DIR>/sweep/sweep_work/tiles (catalogue_* fields of the known objects)"
            if tiles is not None else None,
            "export_script": "scripts/export_anomalies.py",
        },
        "swept": words["swept"],
        "ruled": words["ruled"],
        "area_sq_deg": summary["area_sq_deg"],
        "area_text": words["area_text"],
        "tiles_done": summary["tiles_done"],
        "sources_compared": summary["tally"]["sources"],
        "visits": words["visits"],
        "counts": {**counts, "total": len(survivors)},
        "survivors": survivors,
    }


def _without_tile_fields(doc: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(doc))
    out["source"].pop("tiles", None)
    out["source"].pop("exported_utc", None)
    for s in out["survivors"]:
        for k in TILE_FIELDS:
            s.pop(k, None)
    return out


def check(out: Path = OUT, root: Path = ROOT, tiles: Path | None = None) -> tuple[list[str], list[str]]:
    """(problems, notes): problems make sweep.json out of date with the docs (empty: up to date)."""
    problems: list[str] = []
    notes: list[str] = []
    if not out.exists():
        return [f"{out.name}: missing (run scripts/export_anomalies.py)"], notes
    doc = json.loads(out.read_text())
    have_tiles = tiles is not None and tiles.is_dir()
    want = build(root, tiles if have_tiles else None)
    if doc.get("source", {}).get("summary_sha256") != want["source"]["summary_sha256"]:
        problems.append(f"{out.name}: made from a different {SUMMARY}")
    a, b = _without_tile_fields(doc), _without_tile_fields(want)
    for key in sorted(set(a) | set(b)):
        if key == "survivors":
            continue
        if json.dumps(a.get(key), sort_keys=True) != json.dumps(b.get(key), sort_keys=True):
            problems.append(f"{out.name}: {key} is {json.dumps(a.get(key))[:80]}, "
                            f"the docs say {json.dumps(b.get(key))[:80]}")
    got, wanted = a.get("survivors", []), b["survivors"]
    if len(got) != len(wanted):
        problems.append(f"{out.name}: {len(got)} survivors, the docs list {len(wanted)}")
    for g, w in zip(got, wanted, strict=False):
        for k in sorted(set(g) | set(w)):
            if json.dumps(g.get(k), sort_keys=True) != json.dumps(w.get(k), sort_keys=True):
                problems.append(f"{out.name}: survivor at {w['ra']}, {w['dec']}: {k} is {json.dumps(g.get(k))[:60]}, "
                                f"the docs say {json.dumps(w.get(k))[:60]}")
    for s in doc.get("survivors", []):
        for k in (*FIELDS_ON_EVERY_SURVIVOR, *FIELDS_BY_KIND.get(s.get("kind", ""), ())):
            if s.get(k) is None:
                problems.append(f"{out.name}: survivor at {s.get('ra')}, {s.get('dec')} has no {k}")
        if s.get("kind") == "known_variable" and not s.get("catalogue_name"):
            problems.append(f"{out.name}: known variable at {s.get('ra')}, {s.get('dec')} has no catalogue_name")
    if have_tiles:
        for g, w in zip(doc.get("survivors", []), want["survivors"], strict=False):
            for k in TILE_FIELDS:
                if json.dumps(g.get(k)) != json.dumps(w.get(k)):
                    problems.append(f"{out.name}: survivor at {w['ra']}, {w['dec']}: {k} differs from its tile record")
    else:
        notes.append(f"the tile records are not on this machine ({tiles}): the catalogue_* fields were not re-checked")
    return problems, notes


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    stamp = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    doc = {**doc, "source": {**doc["source"], "exported_utc": stamp}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(doc['survivors'])} survivors)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="offline: compare sweep.json with the docs")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--root", type=Path, default=ROOT, help="checkout whose docs/ to read")
    ap.add_argument("--tiles", type=Path, default=None, help="the sweep's tile records (default: in the cache)")
    args = ap.parse_args(argv)
    tiles = args.tiles or default_tiles()
    if args.check:
        problems, notes = check(args.out, args.root, tiles)
        for p in problems:
            print("OUT OF DATE  " + p)
        for n in notes:
            print("NOTE  " + n)
        if not problems:
            print("anomalies/sweep.json is up to date with docs/sweep/summary.json and docs/sweep.md")
        return 1 if problems else 0
    if not tiles.is_dir():
        print(f"the sweep's tile records are not at {tiles}: set SPHEREX_CACHE_DIR or pass --tiles", file=sys.stderr)
        return 2
    write(build(args.root, tiles), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

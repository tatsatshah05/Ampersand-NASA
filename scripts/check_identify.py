"""Run the "What is it?" lookup (/api/identify) for the test places and print what it found.

Run:  .venv/bin/python scripts/check_identify.py [key ...] [--save]

With --save, the catalogue answers it used (cache files queries/identify_*.json) and the
full answers are copied into tests/data/identify/, where tests/test_identify.py reads
them, and the answers into frontend/src/fixtures/identify/ for the card's tests.
Answers are cached in backend/cache/queries/identify_*.json; delete those to ask again.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import identify  # noqa: E402

# key: (ra, dec, what must come out). Positions are for 2026.0, the date the page uses.
PLACES = {
    "barnard": (269.446267, 4.768222, "red dwarf, about 6 light-years, about 3,100-3,200 K, a fifth of the Sun"),
    "epsindib": (331.096653, -56.800663, "the brown-dwarf pair, never Epsilon Indi A's numbers"),
    "wise0855": (133.759765, -7.242182, "not in Gaia; SIMBAD's parallax, motion and spectral type only"),
    "rwaur": (76.956587, 30.401291, "a young variable star, a close pair"),
    "rdra": (248.167233, 66.755024, "a pulsating red giant"),
    "faint": (269.448524, 4.762903, "an ordinary faint star in Barnard's Star's field"),
    "candidate": (253.18038, -44.67697, "nothing listed; a star about 10 arcsec away as a neighbour"),
}


def show(key: str, answer: dict) -> None:
    ra, dec, expect = PLACES[key]
    print(f"\n=== {key}  ({ra}, {dec})  expected: {expect}")
    print(f"  unreachable: {answer['unreachable']}  nothing_catalogued: {answer['nothing_catalogued']}  "
          f"via: {answer['services']['gaia']['via']} / {answer['services']['simbad']['via']}")
    g, s = answer["gaia"], answer["simbad"]
    if g:
        print(f"  Gaia {g['source_id']} at {g['separation_arcsec']} arcsec")
        for v in g["values"]:
            err = f" +/- {v['error']:.4g}" if v["error"] is not None else ""
            rng = f" [{v['lower']}, {v['upper']}]" if v["lower"] is not None else ""
            print(f"     {v['column']:52s} {v['value']}{err}{rng} {v['unit']}")
    if s:
        print(f"  SIMBAD {s['main_id']} at {s['separation_arcsec']} arcsec: {s['type']}  sp {s['spectral_type']}  "
              f"refs {s['references']}  Gaia ids {s['gaia_dr3_ids']}")
        temps = s["temperatures"] and {k: s["temperatures"][k] for k in ("n", "median", "min", "max")}
        print(f"     parents {[p['name'] for p in s['parents'] or []]}  "
              f"planets {[p['name'] for p in s['planets'] or []]}  temperatures {temps}")
        for v in s.get("values") or []:
            print(f"     {v['column']:52s} {v['value']} +/- {v['error']} {v['unit']}  ({v['reference']})")
    print(f"  match: {answer['match']}")
    d = answer["derived"]
    if d["distance"]:
        print(f"  distance: {d['distance']['status']}  {d['distance']['pc']} pc  {d['distance']['ly']} ly "
              f"+/- {d['distance']['ly_error']}")
    if d["distance_estimate"]:
        print(f"  Gaia's distance estimate: {d['distance_estimate']['ly']} ly")
    if d["motion"]:
        print(f"  motion: {d['motion']['arcsec_per_year']:.4f} +/- {d['motion']['arcsec_per_year_error']} arcsec/yr = "
              f"{d['motion']['pixels_per_year']:.3f} px/yr")
    if d["speed"]:
        print(f"  speed: {d['speed']['km_s']:.2f} +/- {d['speed']['km_s_error']} km/s")
    p = answer["portrait"]
    print(f"  portrait: T {p['temperature'] and (p['temperature']['value'], p['temperature']['column'])}  "
          f"R {p['radius'] and (p['radius']['value'], p['radius']['column'])}")
    print(f"  nearest: {answer['nearest_catalogued']}")
    for n in answer["neighbours"][:12]:
        print(f"     neighbour {n['catalogue']:8s} {n['name']:30s} {n['separation_arcsec']:6.2f} arcsec  "
              f"G {n['g_mag']}  same pixel {n['same_pixel']}  {n['simbad_name'] or ''}")
    for note in answer["notes"]:
        print(f"  note: {note}")


def main() -> None:
    save = "--save" in sys.argv
    keys = [a for a in sys.argv[1:] if not a.startswith("--")] or list(PLACES)
    used: set[Path] = set()
    real_tap = identify._tap

    def noting_tap(kind: str, adql: str):
        out = real_tap(kind, adql)
        used.add(identify._cache_file(kind, adql))
        return out

    identify._tap = noting_tap   # type: ignore[assignment]
    answers = {}
    for key in keys:
        ra, dec, _ = PLACES[key]
        answers[key] = identify.identify(ra, dec)
        show(key, answers[key])
    if save:
        data = ROOT / "tests" / "data" / "identify"
        (data / "cache").mkdir(parents=True, exist_ok=True)
        for path in sorted(used):
            if path.exists():
                shutil.copyfile(path, data / "cache" / path.name)
        front = ROOT / "frontend" / "src" / "fixtures" / "identify"
        front.mkdir(parents=True, exist_ok=True)
        for key, answer in answers.items():
            (front / f"{key}.json").write_text(json.dumps(answer, indent=1) + "\n")
        print(f"\nsaved {len(used)} catalogue answers to {data / 'cache'} and {len(answers)} answers to {front}")


if __name__ == "__main__":
    main()

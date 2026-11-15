"""Known-answer checks of the Earth-reflex search (backend/reflex.py) on real SPHEREx data.

    python scripts/check_reflex.py eris        # blind recovery of Eris in its visit of 2025-07-10 to 07-25
    python scripts/check_reflex.py eris_shift  # same, field centre moved 2 arcmin east and 1.5 north
    python scripts/check_reflex.py sedna       # faint end: Sedna must NOT be found blind
    python scripts/check_reflex.py null       # null field-visits (no body expected): false-alarm census
    python scripts/check_reflex.py blank       # the false-alarm fields, from a list given in FALSE_ALARM_FIELDS
    python scripts/check_reflex.py all         # eris, eris_shift, sedna, null

The search never sees the ephemeris. JPL Horizons (observer SPHEREx, -163182) is asked only after
the search, to score it. Exit code 1 if an Eris criterion fails. Results go to docs/reflex/results.json.
Needs the network for the exposure lists and cutouts unless they are cached; set SPHEREX_CACHE_DIR to reuse them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import reflex, smallbodies  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "reflex" / "results.json"
ERIS = {"name": "136199 Eris", "centre": (27.37815, -0.11998), "visit": (60866.0, 60882.0), "true_au": 95.51}
SEDNA = {"name": "90377 Sedna", "visit": (60905.0, 60923.0)}
FALSE_ALARM_FIELDS = [(190.0, 5.0), (330.0, -12.0), (215.0, -5.0)]


def _load() -> dict:
    return json.loads(OUT.read_text()) if OUT.exists() else {}


def _save(key: str, value: dict) -> None:
    data = _load()
    data[key] = value
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, default=str))


def _jpl(name: str, mjds: list[float]) -> tuple[np.ndarray, np.ndarray]:
    eph = smallbodies.ephemeris(name, list(mjds))
    return np.array([p["ra"] for p in eph]), np.array([p["dec"] for p in eph])


def _observer_distance(command: str, mjd: float) -> float:
    text = smallbodies._jpl_get(
        smallbodies.HORIZONS_URL,
        {
            "format": "json",
            "COMMAND": f"'{command};'",
            "CENTER": "'@-163182'",
            "EPHEM_TYPE": "OBSERVER",
            "TLIST": f"'{mjd + 2400000.5:.6f}'",
            "QUANTITIES": "'20'",
            "CSV_FORMAT": "YES",
            "OBJ_DATA": "NO",
        },
    )
    row = json.loads(text)["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
    return float(row.split(",")[3])


def run_eris(shift: bool = False) -> bool:
    ra, dec = ERIS["centre"]
    if shift:
        ra, dec = ra + (2.0 / 60) / np.cos(np.radians(dec)), dec - 1.5 / 60
    r = reflex.reflex_search(ra, dec, 0.13, (1, 2, 3), ERIS["visit"], 50.0)
    print(r["answer"])
    cands = [
        c
        for c in r["candidates"]
        if c["basic_vetting_passed"]
        and (c["verdict"].startswith("candidate") or c["verdict"].startswith("known distant"))
    ]
    checks: dict[str, bool] = {}
    jpl: dict = {}
    info: dict = {}
    if cands:
        c = cands[0]
        t0 = c["mjd_t0"]
        jra, jdec = _jpl(ERIS["name"], [t0])
        sep = float(np.hypot((c["ra"] - jra[0]) * np.cos(np.radians(dec)), c["dec"] - jdec[0]) * 3600)
        mids = [
            reflex.smallbodies.exposure_mid_mjd(e)
            for e in reflex.spherex.find_exposures(ra, dec)
            if ERIS["visit"][0] <= e["mjd"] <= ERIS["visit"][1] and e["detector"] in (1, 2, 3)
        ]
        era, edec = _jpl(ERIS["name"], mids)
        east = (era - jra[0]) * np.cos(np.radians(dec)) * 3600
        north = (edec - jdec[0]) * 3600
        dm = np.array(mids) - t0
        jv = (float(np.polyfit(dm, east, 1)[0]), float(np.polyfit(dm, north, 1)[0]))
        d_obs = _observer_distance("136199", t0)
        eb = c.get("epoch_resampling") or {}
        lo68, hi68 = eb.get("bootstrap_distance_au_68", (None, None))
        jpl = {
            "separation_arcsec": round(sep, 2),
            "observer_distance_au": d_obs,
            "jpl_linear_drift": [round(x, 3) for x in jv],
        }
        others = [p for p in r["top_unthresholded_peaks"][1:] if p["snr"] >= reflex.CANDIDATE_SNR]
        checks = {
            "A1 within 4 arcsec of JPL": sep <= 4.0,
            "A2 S/N >= 12": c["snr"] >= 12.0,
            "A4 epoch-bootstrap 68% range contains JPL distance, best within 25%": bool(c.get("distance_au"))
            and lo68 is not None
            and lo68 <= d_obs <= (hi68 if hi68 is not None else 1e9)
            and abs(c["distance_au"] - d_obs) / d_obs <= 0.25,
            "A5 delta S^2 vs infinity >= 25 (all exposures)": c["delta_s2_infinite"] >= 25.0,
            "A5b delta S^2 vs infinity >= 9 with any one epoch left out": bool(
                eb and eb["leave_one_epoch_out_min_delta_s2"] >= 9.0
            ),
            "A6 drift within 0.5 arcsec/day of JPL's": max(
                abs(c["drift_arcsec_day"][0] - jv[0]), abs(c["drift_arcsec_day"][1] - jv[1])
            )
            <= 0.5,
        }
        # information only (not a pass/fail line): the raw S/N 8 threshold is not calibrated; null runs exceed it
        info = {
            "other_peaks_at_or_above_8": [round(p["snr"], 2) for p in others],
            "best_reversed_earth_snr_away_from_it": r["control"]["best_reversed_snr"],
            "bootstrap_95_range_au": eb.get("bootstrap_distance_au_95"),
            "bootstrap_95_contains_jpl": bool(
                eb
                and eb["bootstrap_distance_au_95"][0] is not None
                and eb["bootstrap_distance_au_95"][0] <= d_obs <= (eb["bootstrap_distance_au_95"][1] or 1e9)
            ),
            "reversed_peaks_vetted": r.get("reversed_earth_peaks_vetted", []),
        }
    else:
        checks = {"a candidate was found": False}
    ok = all(checks.values())
    for k, v in checks.items():
        print(("PASS  " if v else "FAIL  ") + k)
    c0 = dict(cands[0]) if cands else None
    _save(
        "eris_shift" if shift else "eris",
        {
            "centre": [ra, dec],
            "answer": r["answer"],
            "visit": r["visit"],
            "n_trials": r["n_trials"],
            "control": r["control"],
            "limit": r["limit"],
            "top_peaks": r["top_unthresholded_peaks"],
            "candidate": c0,
            "scored_against_jpl": jpl,
            "checks": checks,
            "information_not_scored": info if cands else None,
            "passed": ok,
            "runtime_s": r["runtime_s"],
        },
    )
    return ok


def run_sedna() -> bool:
    exp0 = reflex.spherex.find_exposures(*_sedna_centre())
    mids = [
        smallbodies.exposure_mid_mjd(e)
        for e in exp0
        if SEDNA["visit"][0] <= e["mjd"] <= SEDNA["visit"][1] and e["detector"] in (1, 2, 3)
    ]
    ra, dec = _sedna_centre()
    r = reflex.reflex_search(ra, dec, 0.13, (1, 2, 3), SEDNA["visit"], 50.0)
    forced = reflex.forced_along(ra, dec, 0.13, (1, 2, 3), SEDNA["visit"], lambda t: _jpl(SEDNA["name"], list(t)))
    print(r["answer"], "\nforced S/N along JPL's track:", forced)
    ok = (
        not [c for c in r["candidates"] if c["verdict"].startswith("candidate")]
        and forced["all"]["snr"] < reflex.CANDIDATE_SNR
    )
    print(
        ("PASS  " if ok else "FAIL  ")
        + "A7 Sedna not found blind as a vetted candidate; forced S/N below the threshold"
    )
    _save(
        "sedna",
        {
            "centre": [ra, dec],
            "answer": r["answer"],
            "n_trials": r["n_trials"],
            "top_peaks": r["top_unthresholded_peaks"],
            "control": r["control"],
            "forced_along_jpl": forced,
            "n_candidates": len(r["candidates"]),
            "passed": ok,
            "n_exposures_in_visit": len(mids),
        },
    )
    return ok


def _sedna_centre() -> tuple[float, float]:
    """Median of JPL's Sedna track over the visit: only picks the patch. Cached in results.json."""
    cached = _load().get("sedna_centre")
    if cached:
        return tuple(cached)  # type: ignore[return-value]
    mids = list(np.linspace(SEDNA["visit"][0], SEDNA["visit"][1], 12))
    ra, dec = _jpl(SEDNA["name"], mids)
    centre = (round(float(np.median(ra)), 5), round(float(np.median(dec)), 5))
    _save("sedna_centre", centre)  # type: ignore[arg-type]
    return centre


def _visit_ranges(ra: float, dec: float) -> list[tuple[float, float, int]]:
    exps = [e for e in reflex.spherex.find_exposures(ra, dec) if e["detector"] in (1, 2, 3)]
    return [(v[0]["mjd"], v[-1]["mjd"], len(v)) for v in reflex.split_visits(exps)]


def run_null(only: set[int] | None = None) -> None:
    """Null field-visits: every run is a search of a visit in which the field is known to hold no body
    we are looking for (the Eris field in its two other visits, the Sedna field in all three, Eris's own
    visit with the exposure times shuffled). Reports every raw peak and what vetting does to it."""
    eris_c = ERIS["centre"]
    sedna_c = _sedna_centre()
    plan = []
    for name, c, hide in (("Eris field", eris_c, (60866.0, 60882.0)), ("Sedna field", sedna_c, SEDNA["visit"])):
        for lo, hi, n in _visit_ranges(*c):
            real = lo - 1 <= 0.5 * (hide[0] + hide[1]) <= hi + 1
            plan.append((name, c, (lo, hi), n, None if not real else 7, real))
    rows = []
    for idx, (name, c, vis, n, shuf, real) in enumerate(plan):
        if only is not None and idx not in only:
            continue
        if n < reflex.MIN_VISIT_EXPOSURES:
            continue
        r = reflex.reflex_search(c[0], c[1], 0.13, (1, 2, 3), vis, 50.0, shuffle_seed=shuf, label=False)
        top = r.get("top_unthresholded_peaks") or [{"snr": None}]
        rev = r.get("reversed_earth_peaks_vetted", [])
        rows.append(
            {
                "plan_index": idx,
                "field": name,
                "visit_mjd": [round(vis[0], 2), round(vis[1], 2)],
                "n_exposures": n,
                "shuffled_times_control_of_the_real_visit": real,
                "status": r["status"],
                "duration_days": (r.get("visit") or {}).get("duration_days"),
                "max_forward_raw_snr": top[0]["snr"],
                "max_reversed_raw_snr": (r.get("control") or {}).get("best_reversed_snr"),
                "n_forward_peaks_at_or_above_threshold": len(r.get("candidates", [])),
                "forward_verdicts": [c2["verdict"][:70] for c2 in r.get("candidates", [])],
                "forward_distance_measured": [c2["distance_measured"] for c2 in r.get("candidates", [])],
                "reversed_peaks_at_or_above_threshold": rev,
                "n_reversed_surviving_vetting": sum(1 for x in rev if x["survives_the_vetting_a_candidate_gets"]),
                "searched_area_deg2": r.get("searched_area_deg2"),
            }
        )
        print(rows[-1]["field"], rows[-1]["visit_mjd"], rows[-1]["max_forward_raw_snr"], rows[-1]["status"], flush=True)
        _save("null_runs" if only is None else "null_runs_" + ",".join(map(str, sorted(only))), {"rows": rows})


def run_blank() -> None:
    rows = []
    for ra, dec in FALSE_ALARM_FIELDS:
        for shuf in (None, 7):
            r = reflex.reflex_search(ra, dec, 0.13, (1, 2, 3), None, 50.0, shuffle_seed=shuf, label=False)
            top = r.get("top_unthresholded_peaks") or [{"snr": None}]
            rows.append(
                {
                    "ra": ra,
                    "dec": dec,
                    "shuffled_times": shuf is not None,
                    "status": r["status"],
                    "visit": r.get("visit"),
                    "n_trials": r.get("n_trials"),
                    "max_forward_snr": top[0]["snr"],
                    "max_reversed_snr": (r.get("control") or {}).get("best_reversed_snr"),
                    "n_above_threshold": len(r.get("candidates", [])),
                    "limit": r.get("limit"),
                }
            )
            print(
                rows[-1]["ra"],
                rows[-1]["dec"],
                rows[-1]["shuffled_times"],
                rows[-1]["max_forward_snr"],
                rows[-1]["max_reversed_snr"],
            )
    _save("blank_fields", {"rows": rows})


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    good = True
    if what in ("eris", "all"):
        good &= run_eris()
    if what in ("eris_shift", "all"):
        good &= run_eris(shift=True)
    if what in ("sedna", "all"):
        good &= run_sedna()
    if what in ("null", "all"):
        run_null({int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None)
    if what == "blank":
        run_blank()
    sys.exit(0 if good else 1)

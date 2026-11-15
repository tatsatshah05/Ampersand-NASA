"""Export what the "Three tools, three known worlds" screen reads: frontend/public/lab/*.json and *.png.

    python scripts/export_lab.py                 # all three tools (needs the cached cutouts; JPL once for Eris)
    python scripts/export_lab.py --tool reflex   # one tool: reflex, colourwalk or transits
    python scripts/export_lab.py --check         # offline: exit 1 if a lab file is out of date with a results file

Set SPHEREX_CACHE_DIR to the folder that holds the cutouts the three methods used (backend/cache):
the reflex search used its sub-folder invent-P3, the transit check invent-P1, the colour walk the
shared folders. Nothing is downloaded from IRSA: a cutout that is not on disk is reported, never fetched.
JPL Horizons is asked once, for Eris's distance from the Sun (its answer is cached like every JPL answer).

Every number in a lab file is either copied unchanged from the method's results file (the "headline"
part, which `--check` compares again) or computed here by the method's own code on the same real
exposures (profiles, tracks, pictures, readings). A quantity that cannot be computed is null with a
`why`. Nothing is typed in, simulated or approximated. The screen turns the numbers into words.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
TOOLS = ("reflex", "colourwalk", "transits")
RESULTS = {
    "reflex": "docs/reflex/results.json",
    "colourwalk": "docs/colourwalk/results.json",
    "transits": "docs/transits/results.json",
}
WRITEUPS = {"reflex": "docs/reflex.md", "colourwalk": "docs/colourwalk.md", "transits": "docs/transits.md"}
CODE = {
    "reflex": ["backend/reflex.py", "scripts/check_reflex.py"],
    "colourwalk": ["backend/colourwalk.py", "scripts/check_colourwalk.py"],
    "transits": ["backend/transits.py", "scripts/check_transit.py"],
}
# A write-up counts as final (its review fixes applied) when it says so in one of these words.
FINAL_EVIDENCE = {
    "reflex": r"finalisation|review fixes (are )?applied",
    "colourwalk": r"What the review changed",
    "transits": r"reviewed by three skeptics and corrected",
}
PIXEL_ARCSEC = 6.15  # one SPHEREx pixel ("square" on the screen)

# Choices of this export (display only; none of them changes a measured number).
REFLEX_STOP_DISTANCES = (500.0, 200.0, 140.0, None, 70.0, 50.0)  # None: the method's best distance
REFLEX_STOP_INV_D = (0.0, 0.002, 0.005, 1 / 140, None, 1 / 70, 0.02)  # spec 5.1; None: 1 / best
REFLEX_DEMO_PX = 48
SKETCH_EXAGGERATION = 5  # spec 7.1: the bend drawn this many times bigger in sketch 1-d
TRANSIT_STOPS_D = (4.00, 4.30, None, 4.55, 4.80)  # None: the published period
TRANSIT_WINDOW_H = 9.0
COLOUR_CROP_PX = 9
TRANSIT_CROP_PX = 15
MAGNIFICATIONS = (10, 20, 25, 40, 50)
INSET_PX_PER_SQUARE = 358 / 9  # spec 5.2: the 9-square crop drawn 358 px wide on a phone
INSET_MIN_PX = 40.0


# ------------------------------------------------------------------------------------------- small helpers


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return out.stdout.strip()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sig(x: Any, n: int = 12) -> Any:
    """Round floats to n significant figures for transport, recursively; NaN and inf become None.

    12 figures keep a BJD to about 0.1 s and a position in degrees to well under a milliarcsecond.
    """
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            return None
        if x == 0:
            return 0.0
        return float(f"{x:.{n}g}")
    if isinstance(x, dict):
        return {k: sig(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [sig(v, n) for v in x]
    try:  # numpy scalars and arrays
        import numpy as np

        if isinstance(x, np.ndarray):
            return [sig(v, n) for v in x.tolist()]
        if isinstance(x, np.bool_):
            return bool(x)
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return sig(float(x), n)
    except ImportError:  # pragma: no cover
        pass
    raise TypeError(f"cannot export {type(x).__name__}")


def deep_merge(a: dict, b: dict) -> dict:
    """b on top of a (b wins), recursively."""
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def leaves(d: Any, prefix: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """(path as a tuple of keys, value) for every non-dict value; lists are values. Keys may hold dots."""
    if isinstance(d, dict):
        for k, v in d.items():
            yield from leaves(v, (*prefix, str(k)))
    else:
        yield prefix, d


def get_path(d: Any, path: str | tuple[str, ...]) -> Any:
    """The value at a path: a tuple of keys, or a dotted string when no key holds a dot."""
    for part in path.split(".") if isinstance(path, str) else path:
        if not isinstance(d, dict) or part not in d:
            raise KeyError(path)
        d = d[part]
    return d


def unavailable(why: str) -> dict:
    return {"available": False, "why": why}


def iso_date(mjd: float) -> str:
    return (dt.datetime(1858, 11, 17, tzinfo=dt.UTC) + dt.timedelta(days=float(mjd))).date().isoformat()


def iso_from_jd(jd: float) -> str:
    return iso_date(jd - 2400000.5)


def final_flag(tool: str, root: Path) -> tuple[bool, str | None]:
    """Is the write-up final? True only if it says so (FINAL_EVIDENCE); returns the line that says it."""
    text = (root / WRITEUPS[tool]).read_text()
    for line in text.splitlines():
        if re.search(FINAL_EVIDENCE[tool], line):
            return True, line.strip()[:300]
    return False, None


def provenance(tool: str, root: Path = ROOT) -> dict:
    res = root / RESULTS[tool]
    return {
        "results_file": RESULTS[tool],
        "results_sha256": sha256_file(res),
        "results_commit": git("log", "-1", "--format=%H", "--", RESULTS[tool]) or None,
        "writeup": WRITEUPS[tool],
        "code_files": CODE[tool],
        "code_commit": git("log", "-1", "--format=%H", "--", *CODE[tool]) or None,
        "export_script": "scripts/export_lab.py",
        "export_commit": git("rev-parse", "HEAD") or None,
        "exported_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
    }


# ------------------------------------------------------------------------------------------- headline parts
# Pure functions: results.json in, the values the lab file copies unchanged out. `--check` recomputes them.


def headline_reflex(r: dict) -> dict:
    e, s = r["eris"], r["eris_shift"]
    c, sc = e["candidate"], s["candidate"]
    er, ser = c.get("epoch_resampling") or {}, sc.get("epoch_resampling") or {}
    return {
        "visit": {
            k: e["visit"][k] for k in ("n_used", "n_exposures", "duration_days", "mjd_first", "mjd_last", "mjd_t0")
        },
        "field": {"ra": e["centre"][0], "dec": e["centre"][1], "searched_area_deg2": e["limit"]["searched_area_deg2"]},
        "candidate": {
            "ra": c["ra"],
            "dec": c["dec"],
            "mjd_t0": c["mjd_t0"],
            "offset_arcsec": c["offset_arcsec"],
            "separation_arcsec": e["scored_against_jpl"]["separation_arcsec"],
            "distance_measured": c["distance_measured"],
            "distance_au": c.get("distance_au"),
            "range_68_au": er.get("bootstrap_distance_au_68"),
            "range_95_au": er.get("bootstrap_distance_au_95"),
            "bootstrap_share_unbounded": er.get("bootstrap_share_unbounded"),
            "n_bootstrap": er.get("n_bootstrap"),
            "interval_2sigma_au_statistical_only": c.get("interval_2sigma_au_statistical_only"),
            "snr": c["snr"],
            "coarse_snr": c["coarse_snr"],
            "snr_at_infinity": c["snr_at_infinity"],
            "delta_s2_infinite": c["delta_s2_infinite"],
            "leave_one_epoch_out_delta_s2": er.get("leave_one_epoch_out_delta_s2"),
            "leave_one_epoch_out_min_delta_s2": er.get("leave_one_epoch_out_min_delta_s2"),
            "n_epochs": er.get("n_epochs"),
            "reversed_earth_snr_mirror_distance": c["reversed_earth_snr_mirror_distance"],
            "drift_arcsec_day": c["drift_arcsec_day"],
            "mean_flux_mjy": c["mean_flux_mjy_matched_filter_scale"],
            "per_detector": c["per_detector"],
            "profile": c["profile"],
            "known_distant_body": c.get("known_distant_body"),
            "verdict": c["verdict"],
        },
        "jpl": {
            "observer_distance_au": e["scored_against_jpl"]["observer_distance_au"],
            "linear_drift_arcsec_day": e["scored_against_jpl"]["jpl_linear_drift"],
        },
        "shifted": {
            "centre": s["centre"],
            "distance_au": sc.get("distance_au"),
            "range_68_au": ser.get("bootstrap_distance_au_68"),
            "range_95_au": ser.get("bootstrap_distance_au_95"),
            "interval_2sigma_au_statistical_only": sc.get("interval_2sigma_au_statistical_only"),
            "separation_arcsec": s["scored_against_jpl"]["separation_arcsec"],
            "snr": sc["snr"],
            "delta_s2_infinite": sc["delta_s2_infinite"],
            "leave_one_epoch_out_min_delta_s2": ser.get("leave_one_epoch_out_min_delta_s2"),
            "passed": s["passed"],
            "checks": s["checks"],
            "edge_reversed_peak": s["control"]["best_reversed_snr"],
        },
        "still_there": [
            {
                "mjd_first": x["mjd"][0],
                "mjd_last": x["mjd"][1],
                "flux_mjy": x.get("flux_mjy"),
                "error_mjy": x.get("error_mjy"),
                "there": x["there"],
            }
            for x in c["still_there"]
        ],
        "limit": {
            "faintest_mean_flux_mjy": e["limit"]["faintest_mean_flux_mjy_matched_filter_scale"],
            "faintest_mean_flux_mjy_aperture_scale": e["limit"]["faintest_mean_flux_mjy_aperture_scale"],
            "threshold_snr": e["limit"]["threshold_snr"],
            "searched_area_deg2": e["limit"]["searched_area_deg2"],
        },
        "sedna": {
            "forced_snr": r["sedna"]["forced_along_jpl"]["all"]["snr"],
            "passed": r["sedna"]["passed"],
            "raw_top_peak_snr": r["sedna"]["top_peaks"][0]["snr"],
        },
        "checks": e["checks"],
        "passed": e["passed"],
        "foldout": {
            "n_trials": e["n_trials"],
            "leverage_arcsec_per_inv_au": e["visit"]["distance_leverage_arcsec_per_inv_au"],
            "next_source_snr": e["top_peaks"][1]["snr"],
            "reversed_best_away_snr": e["control"]["best_reversed_snr"],
            "usable_span_days": c["track_checks"]["usable_span_days"],
            "n_on_track": c["track_checks"]["n_usable"],
        },
    }


def headline_colourwalk(r: dict) -> dict:
    v = r["vhs1256"]
    b, k = v["blind_scan"], v["known_place"]
    null = r["null"]["Barnard b=+14"]
    w = b["walk"]["all"]
    return {
        "development_object_note": v.get("development_object_note"),
        "verdict": b["verdict"],
        "host": {
            "gaia_id": b["host"]["source_id"],
            "ra": b["host"]["ra"],
            "dec": b["host"]["dec"],
            "pm": [b["host"]["pmra"], b["host"]["pmdec"]],
            "parallax": b["host"]["parallax"],
            "gmag": b["host"]["gmag"],
        },
        "known": {"sep_arcsec": k["pa_scan"]["separation"], "pa_deg": k["pa_scan"]["walk_pa"]},
        "n_exposures": b["n_exposures"],
        "n_clean_fits": b["n_clean_fits"],
        "walk": {
            "all": {
                key: w[key]
                for key in (
                    "east",
                    "north",
                    "pa",
                    "size",
                    "sigma",
                    "p_false",
                    "pa_error_deg",
                    "err_east",
                    "err_north",
                    "n_short",
                    "n_long",
                )
            },
            "per_detector": {
                d: {key: v["per_detector_walks"][d][key] for key in ("pa", "size", "sigma")} for d in ("D4", "D5", "D6")
            },
        },
        "visit_walks": [
            {
                "visit": x["visit"],
                "mjd": x["mjd"],
                "sky_angle": x["sky"]["angle_deg"],
                "sky_size": x["sky"]["size"],
                "detector_angle": x["detector"]["angle_deg"],
                "detector_size": x["detector"]["size"],
                "detector_x": x["detector"]["a"],
                "detector_y": x["detector"]["b"],
            }
            for x in b["visit_walks"]
        ],
        "acceptance": {"checks": v["acceptance"]["checks"], "passed": v["acceptance"]["passed"]},
        "null": {
            "scatter_east": null["star_to_star_rms_of_detector_medians"]["east"],
            "scatter_north": null["star_to_star_rms_of_detector_medians"]["north"],
            "n_within": null["isolated_G11p5_15"]["n_all_detector_medians_within_0p06"],
            "n_isolated": null["isolated_G11p5_15"]["n"],
            "n_exposures": null["n_exposures"],
            "n_star_fits": null["n_star_fits"],
            "walkers_over_4sigma": [
                {
                    "gaia_id": s["source_id"],
                    "gmag": s["G"],
                    "sigma": s["sigma"],
                    "walk_arcsec": s["walk_arcsec"],
                    "pa": s["pa"],
                    "neighbour_kind": (s.get("gaia_neighbour_on_walk") or {}).get("kind"),
                }
                for s in null["walkers_over_4sigma"]["stars"]
            ],
            "acceptance": {"checks": r["null"]["acceptance"]["checks"], "passed": r["null"]["acceptance"]["passed"]},
        },
        "known_place": {
            "net_ratio": [
                {key: x.get(key) for key in ("lo", "hi", "net", "net_err", "control", "control_max")}
                for x in k["net_ratio"]
            ],
        },
        "blind_ratio_best_separation_arcsec": b["best_separation_arcsec"],
    }


def headline_transits(r: dict) -> dict:
    w = r["wasp62"]
    d5 = w["detectors"]["5"]
    acc = r["acceptance"]
    h = r["wasp62_halo_accepted"]["detectors"]["5"]
    a3 = acc["A3"]
    return {
        "planet": {k: w[k] for k in ("name", "ra", "dec", "period_d", "t0_bjd_tdb", "t14_h", "rprs", "expected_depth")},
        "coverage": {k: w["coverage"][k] for k in ("exposures", "per_detector", "mjd_first", "mjd_last")},
        "detectors": {
            d: {
                "status": x.get("status"),
                "excluded": x.get("excluded"),
                "n_in": x.get("n_in"),
                "n_ok": x.get("n_ok"),
                "n_overflow": x.get("n_overflow"),
            }
            for d, x in w["detectors"].items()
        },
        "d5": {
            **{
                k: d5[k]
                for k in (
                    "n",
                    "n_in",
                    "n_transits",
                    "depth",
                    "formal_err",
                    "empirical_err",
                    "empirical_sigma",
                    "noise_factor",
                    "n_fake",
                    "fake_share_as_deep",
                    "scatter",
                    "photon",
                    "n_cutouts",
                    "slide_peak_h",
                    "jackknife_min",
                    "jackknife_max",
                    "wl_min",
                    "wl_max",
                )
            },
            "years": d5["years"],
            "folded": d5["folded"],
            "choices": {label: x["depth"] for label, x in d5["choices"].items()},
        },
        "aperture_radius_px": {a: x["depth"] for a, x in r["wasp62_aperture_radius_px"].items()},
        "halo": {k: h[k] for k in ("depth", "empirical_err", "empirical_sigma", "n_in")},
        "comparison": {
            "gmag": acc["A2"]["stars"][0]["gmag"],
            "distance_arcsec": acc["A2"]["stars"][0]["distance_arcsec"],
            "depth": acc["A2"]["stars"][0]["depth"],
            "err": acc["A2"]["stars"][0]["empirical_err"],
            "n_in": acc["A2"]["stars"][0]["n_in"],
        },
        "acceptance": {
            "A1": acc["A1"]["passed"],
            "A2": acc["A2"]["passed"],
            "A3": a3.get("passed"),
            "A4_validated": acc["A4"]["validated"],
        },
        "wasp100": {
            "expected_depth": a3["expected"],
            "combined": a3["combined"],
            "per_detector": {
                d: {
                    k: x.get(k)
                    for k in ("depth", "empirical_err", "empirical_sigma", "n_in", "fake_share_as_deep", "excluded")
                }
                for d, x in a3["per_detector"].items()
            },
        },
    }


HEADLINES = {"reflex": headline_reflex, "colourwalk": headline_colourwalk, "transits": headline_transits}

# Fields the screen needs (section 7 of the spec, as adapted; see the report). `--check` and the tests ask for them.
REQUIRED = {
    "reflex": [
        "final",
        "status.chip_key",
        "visit.n_used",
        "visit.duration_days",
        "visit.mjd_first",
        "visit.mjd_last",
        "visit.date_first",
        "visit.date_last",
        "field.ra",
        "field.dec",
        "field.size_deg",
        "candidate.separation_arcsec",
        "candidate.distance_au",
        "candidate.range_95_au",
        "candidate.range_68_au",
        "candidate.interval_2sigma_au_statistical_only",
        "candidate.snr",
        "candidate.snr_at_infinity",
        "candidate.delta_s2_infinite",
        "candidate.reversed_earth_snr_mirror_distance",
        "candidate.drift_arcsec_day",
        "candidate.mean_flux_mjy",
        "candidate.profile.inv_d",
        "candidate.profile.snr",
        "jpl.observer_distance_au",
        "jpl.helio_distance_au",
        "jpl.positions",
        "jpl.mid",
        "shifted.distance_au",
        "shifted.range_95_au",
        "shifted.separation_arcsec",
        "shifted.snr",
        "shifted.passed",
        "shifted.edge_reversed_peak",
        "still_there",
        "limit.faintest_mean_flux_mjy",
        "limit.searched_area_deg2",
        "limit.distance_range_au",
        "limit.min_visit_days",
        "limit.injection_tested",
        "sedna.found_blind",
        "sedna.forced_snr",
        "sedna.threshold",
        "demo.crop_px",
        "demo.pixel_arcsec",
        "demo.stretch",
        "demo.single.png",
        "demo.single.mjd",
        "demo.plain_mean.png",
        "demo.slid.png",
        "demo.marks.tool_dot_px",
        "demo.marks.nasa_single_px",
        "demo.marks.nasa_mid_px",
        "demo.marks.nasa_path_px",
        "demo.eris_motion_squares",
        "stops",
        "wrong_way",
        "sketch_exaggeration",
        "foldout.n_trials",
        "foldout.leverage_arcsec_per_inv_au",
        "foldout.next_source_snr",
        "foldout.reversed_best_away_snr",
        "source.results_sha256",
        "files",
    ],
    "colourwalk": [
        "final",
        "status.chip_key",
        "status.verdict",
        "development_object_note",
        "host.gaia_id",
        "host.ra",
        "host.dec",
        "host.pm",
        "host.gmag",
        "known.sep_arcsec",
        "known.pa_deg",
        "known.ref",
        "n_exposures",
        "n_clean_fits",
        "walk.all.east",
        "walk.all.north",
        "walk.all.pa",
        "walk.all.size",
        "walk.all.sigma",
        "walk.all.p_false",
        "walk.all.pa_error_deg",
        "walk.all.err_east",
        "walk.all.err_north",
        "walk.sigma_guessed_floor",
        "walk.per_detector",
        "visit_walks",
        "walk.detector_fixed_arcsec",
        "acceptance.checks",
        "acceptance.passed",
        "null.acceptance.checks",
        "null.acceptance.passed",
        "known_place.net_ratio",
        "known_place.control_max",
        "null.scatter_east",
        "null.scatter_north",
        "null.n_within",
        "null.n_isolated",
        "groups",
        "picture",
        "lone_star",
        "magnification",
        "rule_sigma",
        "source.results_sha256",
        "files",
    ],
    "transits": [
        "final",
        "status.chip_key",
        "development_object",
        "planet.period_d",
        "planet.t0_bjd_tdb",
        "planet.t14_h",
        "planet.rprs",
        "planet.expected_depth",
        "refs",
        "coverage.exposures",
        "d5.n",
        "d5.n_in",
        "d5.n_transits",
        "d5.depth",
        "d5.formal_err",
        "d5.empirical_err",
        "d5.empirical_sigma",
        "d5.noise_factor",
        "d5.n_fake",
        "d5.fake_share_as_deep",
        "d5.n_fake_as_deep",
        "d5.scatter",
        "d5.n_cutouts",
        "d5.slide_peak_h",
        "d5.years",
        "d5.folded",
        "halo.depth",
        "halo.empirical_err",
        "halo.empirical_sigma",
        "halo.n_in",
        "readings",
        "stops",
        "comparison.gmag",
        "comparison.distance_arcsec",
        "comparison.depth",
        "comparison.err",
        "wasp100.expected_depth",
        "wasp100.combined",
        "wasp100.per_detector",
        "wasp100.n_clear",
        "picture",
        "dates.first",
        "dates.last",
        "source.results_sha256",
        "files",
    ],
}


# ------------------------------------------------------------------------------------------- pictures


def stretch_asinh(values, lo: float, hi: float, soft: float):
    """Grey levels 0..255: 255 * clip(asinh((v - lo) / soft) / asinh((hi - lo) / soft), 0, 1); NaN gives 0."""
    import numpy as np

    v = np.asarray(values, float)
    g = np.arcsinh((v - lo) / soft) / np.arcsinh((hi - lo) / soft)
    g = np.clip(np.nan_to_num(g, nan=0.0), 0.0, 1.0)
    return np.round(255.0 * g).astype(np.uint8)


def stretch_linear(values, lo: float, hi: float):
    """Grey levels 0..255: 255 * clip((v - lo) / (hi - lo), 0, 1); NaN gives 0."""
    import numpy as np

    g = np.clip(np.nan_to_num((np.asarray(values, float) - lo) / (hi - lo), nan=0.0), 0.0, 1.0)
    return np.round(255.0 * g).astype(np.uint8)


def png_bytes(grey) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(grey, mode="L").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def north_up_grid(n: int, centre_east: float, centre_north: float, step: float = PIXEL_ARCSEC):
    """Offsets (east, north, arcsec) of the centres of an n x n picture, north up and east LEFT.

    Pixel (row j, column i) has its centre at picture coordinates (i + 0.5, j + 0.5) from the top-left corner.
    """
    import numpy as np

    k = (n / 2 - 0.5) - np.arange(n)  # +n/2-0.5 at column 0 (east edge, left) and row 0 (north edge, top)
    east = centre_east + np.tile(k, (n, 1)) * step
    north = centre_north + np.tile(k[:, None], (1, n)) * step
    return east, north


def to_picture_px(east: float, north: float, centre_east: float, centre_north: float, n: int) -> list[float]:
    """Picture coordinates (x right, y down, origin the top-left corner) of an (east, north) offset."""
    return [n / 2 - (east - centre_east) / PIXEL_ARCSEC, n / 2 - (north - centre_north) / PIXEL_ARCSEC]


def sample(image, valid, wcs, ra, dec):
    """Bilinear samples of an image at sky positions (NaN where a sampled pixel is not valid), as the
    reflex module samples its maps (map_coordinates, order 1)."""
    import numpy as np
    from scipy.ndimage import map_coordinates

    x, y = wcs.all_world2pix(ra, dec, 0)
    val = map_coordinates(np.nan_to_num(image), [y, x], order=1, mode="constant", cval=0.0)
    ok = map_coordinates(valid.astype(float), [y, x], order=1, mode="constant", cval=0.0) > 0.99
    return np.where(ok, val, np.nan)


@contextlib.contextmanager
def cache_folder(path: Path) -> Iterator[None]:
    """Point the backend at one cache folder for a while (the methods each used their own)."""
    from backend import colourwalk, smallbodies, spherex

    saved = (spherex.CACHE, smallbodies.CACHE_DIR, colourwalk.CACHE)
    spherex.CACHE, smallbodies.CACHE_DIR, colourwalk.CACHE = path, path / "smallbodies", path
    try:
        yield
    finally:
        spherex.CACHE, smallbodies.CACHE_DIR, colourwalk.CACHE = saved


def frozen_exposure_lists() -> None:
    """Exposure lists are read from disk whatever their age: the export reproduces what the methods ran on."""
    from backend import spherex

    if getattr(spherex.find_exposures, "_frozen", False):
        return
    original = spherex.find_exposures

    def find(ra: float, dec: float, max_age_s: float = float("inf")) -> list[dict]:
        return original(ra, dec, max_age_s=float("inf"))

    setattr(find, "_frozen", True)  # noqa: B010 - a marker on the wrapper
    spherex.find_exposures = find


def log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------------------------------------------------------------------- tool 1: reflex


def jpl_distances(mjd: float) -> dict:
    """Eris's distance from the Sun (r) and from SPHEREx (delta) at one time: JPL Horizons, observer SPHEREx."""
    from backend import smallbodies

    text = smallbodies._jpl_get(
        smallbodies.HORIZONS_URL,
        {
            "format": "json",
            "COMMAND": "'136199;'",
            "CENTER": f"'@{smallbodies.SPHEREX_HORIZONS_ID}'",
            "EPHEM_TYPE": "OBSERVER",
            "TLIST": f"'{mjd + 2400000.5:.6f}'",
            "QUANTITIES": "'19,20'",
            "CSV_FORMAT": "YES",
            "OBJ_DATA": "NO",
        },
    )
    result = json.loads(text)["result"]
    header = [h.strip() for h in result.split("$$SOE")[0].strip().splitlines()[-2].split(",")]
    row = [x.strip() for x in result.split("$$SOE")[1].split("$$EOE")[0].strip().split(",")]
    return {
        "helio_distance_au": float(row[header.index("r")]),
        "observer_distance_au": float(row[header.index("delta")]),
    }


def export_reflex(cache_root: Path) -> tuple[dict, dict[str, bytes]]:
    import numpy as np
    from astropy.io import fits
    from astropy.stats import sigma_clipped_stats
    from astropy.wcs import WCS

    from backend import photometry, pipeline, reflex, smallbodies, spherex
    from scripts import check_reflex

    res = json.loads((ROOT / RESULTS["reflex"]).read_text())
    e = res["eris"]
    c_res = e["candidate"]
    ra, dec = cast(tuple[float, float], check_reflex.ERIS["centre"])
    visit = cast(tuple[float, float], check_reflex.ERIS["visit"])
    eris_name = cast(str, check_reflex.ERIS["name"])
    fov, dets, nearest = 0.13, (1, 2, 3), 50.0
    out: dict[str, Any] = {}
    pngs: dict[str, bytes] = {}
    checks: dict[str, Any] = {}
    frozen_exposure_lists()
    with cache_folder(cache_root / "invent-P3"):
        exposures = [x for x in spherex.find_exposures(ra, dec) if x["detector"] in dets]
        visits = reflex.split_visits(exposures)
        iv = reflex.pick_visit(visits, visit)
        if iv is None:
            raise RuntimeError("the Eris visit is not in the cached exposure list")
        chosen = visits[iv]
        paths = {}
        missing = 0
        for x in exposures:
            p = spherex._cutout_path(x, ra, dec, fov + reflex.CUTOUT_MARGIN_DEG)
            if p.exists():
                paths[(x["obs_id"], x["detector"])] = p
            else:
                missing += 1
        log(f"reflex: {len(exposures)} exposures, {missing} cutouts not on disk (never fetched here)")
        cube = reflex.build_cube(exposures, paths, chosen, ra, dec, fov, reflex.COARSE_ARCSEC, dets)
        t0 = float(np.median(cube["T"]))
        fnl, flin = reflex.parallax_curve(cube["T"], ra, dec, t0)
        dtf = cube["T"] - t0
        slope = (float(np.polyfit(dtf, flin[:, 0], 1)[0]), float(np.polyfit(dtf, flin[:, 1], 1)[0]))
        log("reflex: coarse search (the module's own, about 3 minutes)")
        coarse = reflex.coarse_search(cube, fnl, slope, t0, nearest)
        pos = [t for t in coarse["trials"] if t[1] > -1e-9]
        peak = reflex.merge_peaks(pos)[0]
        cube_f = reflex.build_cube(exposures, paths, chosen, ra, dec, fov, reflex.FINE_ARCSEC, dets)
        keep = [i for i, k in enumerate(cube_f["keys"]) if k in set(cube["keys"])]
        tf = cube_f["T"][keep]
        fnl_f, _ = reflex.parallax_curve(tf, ra, dec, t0)
        track = reflex.Track(cube_f["D"][keep], cube_f["W"][keep], tf - t0, fnl_f, reflex.FINE_ARCSEC)
        half = fov / 2 * 3600.0 - 10

        def limit_fn(inv: float) -> tuple[float, float, float]:
            return reflex.drift_box(inv, slope[0], slope[1], nearest)

        log("reflex: refined profile (the module's refine)")
        rf = reflex.refine(
            track, (peak["east"], peak["north"], peak["ve"], peak["vn"]), peak["inv_d"], nearest, half, limit=limit_fn
        )
        snr = rf["snr"]
        mine = [None if not np.isfinite(v) else round(float(v), 2) for v in snr[::2]]
        diffs = [
            abs(a - b) for a, b in zip(mine, c_res["profile"]["snr"], strict=True) if a is not None and b is not None
        ]
        checks["profile_reproduced_max_abs_diff"] = round(max(diffs), 4) if diffs else None
        checks["best_snr_reproduced"] = round(rf["best_snr"], 2)
        checks["coarse_peak_reproduced"] = round(peak["snr"], 3)
        best_inv = rf["best_inv_d"]
        ib = rf["best_index"]
        med, scale = rf["noise_median"], rf["noise_scale"]
        fnl0 = np.array([np.interp(0.0, track.dt, track.fnl[:, k]) for k in range(2)])
        pe, pn, ve, vn = rf["params"][ib]
        place_t0 = (pe + best_inv * fnl0[0], pn + best_inv * fnl0[1])
        checks["place_at_t0_reproduced_arcsec"] = [round(place_t0[0], 2), round(place_t0[1], 2)]
        d_best = float(c_res["distance_au"])

        # ---- slider stops: S with the drift free at each 1/d (as the module's straight-track test), and the
        # module's own bounded-drift profile interpolated, for comparison
        start = (pe, pn, ve, vn)
        inv_stops = [x if x is not None else 1.0 / d_best for x in REFLEX_STOP_INV_D]
        dist_stops = [None] + [x if x is not None else d_best for x in REFLEX_STOP_DISTANCES]
        prof_inv = np.array(c_res["profile"]["inv_d"], float)
        prof_snr = np.array([np.nan if v is None else v for v in c_res["profile"]["snr"]], float)

        def free_snr(inv: float) -> tuple[float, np.ndarray]:
            vals, pars = reflex.profile(track, start, np.array([inv]), None, None, n_starts=2)
            return float((vals[0] - med) / scale), pars[0]

        def track_arrays(inv: float, pars: np.ndarray) -> dict:
            te, tn = reflex.track_offsets((pars[0], pars[1]), (pars[2], pars[3]), inv, track.dt, track.fnl)
            le, ln = pars[0] + pars[2] * track.dt, pars[1] + pars[3] * track.dt
            return {"track_east": te, "track_north": tn, "linear_east": le, "linear_north": ln}

        s0_free, _ = free_snr(0.0)
        checks["straight_free_drift_snr_reproduced"] = round(s0_free, 2)
        s0_mod = float(c_res["snr_at_infinity"])  # the module's S/N of the best straight track, any drift
        s0 = s0_free  # the same, recomputed here unrounded: every free-drift delta is measured from it
        stops = []
        labels = ["No bend"] + [f"{d:g}" for d in dist_stops[1:]]
        for lab, inv, dist in zip(labels, inv_stops, dist_stops, strict=True):
            s_free, pars = free_snr(inv)
            s_mod = float(np.interp(inv, prof_inv, prof_snr)) if inv != 0.0 else s0_mod
            stops.append(
                {
                    "label": lab,
                    "inv_d": inv,
                    "distance_au": dist,
                    "snr": s_free,
                    "delta": s_free**2 - s0**2,
                    "snr_module_profile": s_mod,
                    "delta_module_profile": s_mod**2 - s0_mod**2,
                    **track_arrays(inv, pars),
                }
            )
        wrong_inv = -1.0 / d_best
        s_w, pars_w = free_snr(wrong_inv)
        s_w_mod = float(np.interp(wrong_inv, prof_inv, prof_snr))
        wrong = {
            "inv_d": wrong_inv,
            "distance_au": d_best,
            "snr": s_w,
            "delta": s_w**2 - s0**2,
            "snr_module_profile": s_w_mod,
            "delta_module_profile": s_w_mod**2 - s0_mod**2,
            **track_arrays(wrong_inv, pars_w),
        }
        best_s2 = float(c_res["snr"]) ** 2
        keep_control = bool(wrong["delta"] < 0 and best_s2 - s0**2 >= reflex.MEASURED_DELTA_S2)
        wrong["keep_control"] = keep_control
        wrong["rule"] = "kept while delta(wrong way) < 0 and S^2(best) - S^2(no bend) >= MEASURED_DELTA_S2 (9)"
        checks["wrong_way_snr_module_profile_vs_mirror"] = [
            round(s_w_mod, 2),
            c_res["reversed_earth_snr_mirror_distance"],
        ]
        bend = np.hypot(
            best_inv * (track.fnl[:, 0] - track.fnl[:, 0].mean()), best_inv * (track.fnl[:, 1] - track.fnl[:, 1].mean())
        )
        drift_len = float(np.hypot(ve, vn) * np.ptp(track.dt))

        # ---- JPL: positions at the exposure times (cached by check_reflex), distance from the Sun (fetched once)
        mids = [smallbodies.exposure_mid_mjd(x) for x in exposures if visit[0] <= x["mjd"] <= visit[1]]
        jpl_pos = smallbodies.ephemeris(eris_name, mids)
        jpl_mid = smallbodies.ephemeris(eris_name, [t0])[0]
        try:
            dists = jpl_distances(t0)
            jpl_extra: dict[str, Any] = {**dists, "available": True}
        except Exception as err:  # noqa: BLE001 - JPL down: said so, never filled in
            jpl_extra = {"helio_distance_au": None, "available": False, "why": f"JPL Horizons not reached: {err}"}
        cosd = math.cos(math.radians(dec))

        def offs(p_ra: float, p_dec: float) -> tuple[float, float]:
            return (p_ra - ra) * cosd * 3600.0, (p_dec - dec) * 3600.0

        # ---- demo pictures: the 57 exposures resampled onto one north-up grid around Eris's place at t0
        n = REFLEX_DEMO_PX
        ce, cn = place_t0
        ge, gn = north_up_grid(n, ce, cn)
        keys_f = [cube_f["keys"][i] for i in keep]
        templates_f = [cube_f["templates"][i] for i in keep]
        loaded: dict[tuple, tuple] = {}

        def load(key: tuple) -> tuple:
            """IMAGE minus ZODI minus the clipped median sky, as mf_map prepares it (flagged pixels NaN)."""
            if key not in loaded:
                with fits.open(paths[key]) as h:
                    img = h["IMAGE"].data.astype(float)
                    var = h["VARIANCE"].data.astype(float)
                    fl = h["FLAGS"].data
                    z = h["ZODI"].data.astype(float)
                    w = WCS(h["IMAGE"].header)
                    mjd_k = float(h["IMAGE"].header["MJD-AVG"])
                d = img - z
                bad = (
                    ((fl & photometry.PHOTOMETRY_BAD) != 0)
                    | ~np.isfinite(d)
                    | ~np.isfinite(var)
                    | pipeline.impossible_pixels(img, var)
                )
                sky = ~bad & ((fl & photometry.SKY_BAD) == 0)
                _, med_sky, _ = sigma_clipped_stats(d[sky] if sky.sum() > 200 else d[~bad], sigma=3, maxiters=5)
                loaded[key] = (np.where(bad, np.nan, d - med_sky), ~bad, w, mjd_k)
            return loaded[key]

        def template(key: tuple) -> tuple[Any, Any, Any]:
            d_t, good_t, w_t, _ = load(key)
            return d_t, good_t, w_t

        # the search's own fixed-sky removal, applied to raw pixels: minus the mean of the same two other-visit
        # exposures it used, blanked where its 3 arcsec difference map is blank (bright fixed stars, no data)
        coarse_i = {key: j for j, key in enumerate(cube["keys"])}
        n_c = cube["ge"].shape[0]

        def module_mask(j_c: int, east_: np.ndarray, north_: np.ndarray) -> np.ndarray:
            ix = np.round(east_ / reflex.COARSE_ARCSEC).astype(int) + n_c // 2
            iy = np.round(north_ / reflex.COARSE_ARCSEC).astype(int) + n_c // 2
            inside = (ix >= 0) & (ix < n_c) & (iy >= 0) & (iy < n_c)
            out_ = np.zeros(ix.shape, bool)
            out_[inside] = np.isfinite(cube["D"][j_c][iy[inside], ix[inside]])
            return out_

        stacks_plain: list = []
        stacks_slid: list = []
        diff_plain: list = []
        diff_slid: list = []
        frames: list[tuple[float, int, str]] = []
        for i, key in enumerate(keys_f):
            d, good, w, mjd_i = load(key)
            de = pe + ve * track.dt[i] + best_inv * track.fnl[i, 0] - place_t0[0]
            dn = pn + vn * track.dt[i] + best_inv * track.fnl[i, 1] - place_t0[1]
            tkeys = [(o, key[1]) for o in templates_f[i]]
            for east_, north_, raw_list, diff_list in (
                (ge, gn, stacks_plain, diff_plain),
                (ge + de, gn + dn, stacks_slid, diff_slid),
            ):
                s_ra, s_dec = reflex._sky(ra, dec, east_, north_)
                here = sample(d, good, w, s_ra, s_dec)
                raw_list.append(here)
                with np.errstate(invalid="ignore"), warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    tmpl = np.nanmean([sample(*template(t), s_ra, s_dec) for t in tkeys], axis=0)
                mask = module_mask(coarse_i[key], east_, north_)
                diff_list.append(np.where(mask, here - tmpl, np.nan))
            frames.append((mjd_i, int(key[1]), key[0]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            plain = np.nanmean(stacks_plain, axis=0)
            slid = np.nanmean(stacks_slid, axis=0)
            plain_diff = np.nanmean(diff_plain, axis=0)
            slid_diff = np.nanmean(diff_slid, axis=0)
        mid_visit = 0.5 * (e["visit"]["mjd_first"] + e["visit"]["mjd_last"])
        i_single = int(np.argmin([abs(f[0] - mid_visit) for f in frames]))
        single = stacks_plain[i_single]
        # star-trail rule (spec 7.1): slide the plain mean (stars only, Eris smeared) the same way; if its trail
        # light within one square of Eris's place exceeds 3 x the slid picture's noise, a trail crosses Eris
        from scipy.ndimage import map_coordinates

        def at(img_, east_, north_):
            x = n / 2 - (east_ - ce) / PIXEL_ARCSEC - 0.5
            y = n / 2 - (north_ - cn) / PIXEL_ARCSEC - 0.5
            return map_coordinates(np.nan_to_num(img_), [y, x], order=1, mode="constant", cval=0.0)

        trail = np.nanmean(
            [
                at(
                    plain,
                    ge + (pe + ve * track.dt[i] + best_inv * track.fnl[i, 0] - place_t0[0]),
                    gn + (pn + vn * track.dt[i] + best_inv * track.fnl[i, 1] - place_t0[1]),
                )
                for i in range(len(keys_f))
            ],
            axis=0,
        )
        noise_slid = float(1.4826 * np.nanmedian(np.abs(slid - np.nanmedian(slid))))
        noise_plain = float(1.4826 * np.nanmedian(np.abs(plain - np.nanmedian(plain))))
        yy, xx = np.mgrid[0:n, 0:n]
        near_eris = np.hypot(xx + 0.5 - n / 2, yy + 0.5 - n / 2) <= 1.0
        trail_light = float(np.nanmax(trail[near_eris] - np.nanmedian(trail)))
        crosses = bool(trail_light > 3.0 * noise_slid)
        eris_peak = float(np.nanmax(slid[near_eris]) - np.nanmedian(slid))
        stretch: dict[str, Any]
        if crosses:  # spec 7.1: all three frames from the search's difference images
            single, plain, slid = diff_plain[i_single], plain_diff, slid_diff
            n_blank = [int(np.isnan(x).sum()) for x in (single, plain, slid)]
            noise_plain = float(1.4826 * np.nanmedian(np.abs(plain - np.nanmedian(plain))))
            background = float(np.nanmedian(plain))
            lo, hi = background - 2.0 * noise_plain, background + 8.0 * noise_plain
            stretch = {
                "kind": "linear",
                "formula": "grey = 255 * clip((v - lo) / (hi - lo), 0, 1); blank pixels (no data, or blanked by the "
                "search) are drawn at the grey of the plain mean's median",
                "rule": "lo = the plain mean's median - 2 robust sigma, hi = its median + 8 robust sigma; the same "
                "for all three pictures",
            }
            single, plain, slid = (np.where(np.isnan(x), background, x) for x in (single, plain, slid))
            grey = {
                name: stretch_linear(x, lo, hi)
                for name, x in (("single", single), ("plain_mean", plain), ("slid", slid))
            }
        else:
            n_blank = [int(np.isnan(x).sum()) for x in (single, plain, slid)]
            lo, hi, soft = float(np.nanmedian(plain)) - noise_plain, float(np.nanpercentile(plain, 99.5)), noise_plain
            stretch = {
                "kind": "asinh",
                "soft": soft,
                "formula": "grey = 255 * clip(asinh((v - lo) / soft) / asinh((hi - lo) / soft), 0, 1); no data = 0",
                "rule": "lo = median - 1 robust sigma of the plain mean; soft = 1 robust sigma; hi = its 99.5th "
                "percentile; the same for all three pictures",
            }
            grey = {
                name: stretch_asinh(x, lo, hi, soft)
                for name, x in (("single", single), ("plain_mean", plain), ("slid", slid))
            }
        for name, g_ in grey.items():
            pngs[f"reflex_{name}.png"] = png_bytes(g_)
        jpl_off = [offs(p["ra"], p["dec"]) for p in jpl_pos]
        mid_off = offs(jpl_mid["ra"], jpl_mid["dec"])
        # the JPL time nearest the single exposure (same exposure: mids are 0.7 s before MJD-AVG)
        j_single = int(np.argmin([abs(m - frames[i_single][0]) for m in mids]))
        months = []
        mid_search = mid_visit
        for x in c_res["still_there"]:
            m_other = 0.5 * (x["mjd"][0] + x["mjd"][1])
            months.append((m_other - mid_search) / 30.4375)
        drift = c_res["drift_arcsec_day"]
        motion_sq = math.hypot(*drift) * e["visit"]["duration_days"] / PIXEL_ARCSEC

        out = {
            "visit": {
                "date_first": iso_date(e["visit"]["mjd_first"]),
                "date_last": iso_date(e["visit"]["mjd_last"]),
                "mjd_mid": mid_visit,
            },
            "field": {"size_deg": fov, "detectors": list(dets)},
            "candidate": {"place_at_t0_arcsec_recomputed": list(place_t0)},
            "jpl": {
                "observer": "SPHEREx (JPL Horizons -163182)",
                "helio_distance_au": jpl_extra.get("helio_distance_au"),
                "observer_distance_au_fetched": jpl_extra.get("observer_distance_au"),
                "distances_at_mjd": t0,
                **({} if jpl_extra.get("available") else {"why": jpl_extra.get("why")}),
                "mid": {"mjd": t0, "ra": jpl_mid["ra"], "dec": jpl_mid["dec"]},
                "positions": [{"mjd": m, "ra": p["ra"], "dec": p["dec"]} for m, p in zip(mids, jpl_pos, strict=True)],
                "sunlight_seconds_per_au": 499.004784,
            },
            "still_there_months_from_search": months,
            "limit": {
                "flux_scale": "matched filter (Eris's mean_flux_mjy is on the same scale)",
                "distance_range_au": [nearest, grid_far_limit(nearest)],
                "distance_range_note": "the near end is where the search starts; the far end is the nearest non-zero "
                "1/d of the coarse grid: beyond it a body is found but cannot be told from one "
                "at infinity. It is NOT the ranging limit (see ranging_limit_au).",
                "ranging_limit_au": ranging_limits(reflex.RANGING_NOTE),
                "min_visit_days": reflex.MIN_DISTANCE_DAYS,
                "injection_tested": any("injection" in ".".join(k) for k, _ in leaves(res)),
                "injection_why": "docs/reflex/results.json holds no injection-recovery test; the limit is the S/N "
                "threshold times the measured noise, a 50 per cent level",
            },
            "sedna": {
                "threshold": reflex.CANDIDATE_SNR,
                "found_blind": False if res["sedna"]["passed"] else None,
                "found_blind_rule": "false while the module's Sedna check passed (no vetted candidate and forced "
                "S/N below the threshold); null otherwise",
            },
            "demo": {
                "crop_px": n,
                "pixel_arcsec": PIXEL_ARCSEC,
                "made_from": "difference_images" if crosses else "raw_exposures",
                "made_from_note": (
                    "each exposure (IMAGE minus ZODI minus its clipped median sky, flagged pixels left out) minus the "
                    "mean of the same two other-visit exposures the search subtracted, blank where the search's own "
                    "difference map is blank (bright fixed stars)"
                    if crosses
                    else "raw exposures: IMAGE minus ZODI minus each exposure's clipped median sky, flagged pixels "
                    "left out"
                ),
                "blank_pixels": dict(zip(("single", "plain_mean", "slid"), n_blank, strict=True)),
                "resampling": "bilinear, onto one north-up east-left grid of 6.15 arcsec squares "
                "(as the module samples its maps)",
                "centre_offset_arcsec": [ce, cn],
                "north_up_east_left": True,
                "stretch": {"unit": "MJy/sr", "lo": lo, "hi": hi, **stretch},
                "single": {
                    "png": "reflex_single.png",
                    "mjd": frames[i_single][0],
                    "detector": frames[i_single][1],
                    "obs_id": frames[i_single][2],
                    "rule": "the used exposure nearest the middle of the visit",
                },
                "plain_mean": {"png": "reflex_plain_mean.png", "n": len(frames)},
                "slid": {
                    "png": "reflex_slid.png",
                    "n": len(frames),
                    "inv_d": best_inv,
                    "rule": "each exposure sampled at its own place on the module's best track (place, drift and "
                    "1/d of the refined fit), so Eris piles up at its place at the reference time",
                },
                "star_trail_crosses_eris": crosses,
                "star_trail_rule": "the plain mean slid along the same track; a trail crosses Eris if that picture "
                "exceeds 3 x the slid picture's robust noise within 1 square of Eris's place",
                "star_trail_light": trail_light,
                "slid_noise": noise_slid,
                "eris_peak_in_slid": eris_peak,
                "marks": {
                    "tool_dot_px": to_picture_px(ce, cn, ce, cn, n),
                    "nasa_single_px": to_picture_px(*jpl_off[j_single], ce, cn, n),
                    "nasa_mid_px": to_picture_px(*mid_off, ce, cn, n),
                    "nasa_path_px": [to_picture_px(a, b, ce, cn, n) for a, b in jpl_off],
                    "units": "picture pixels, x right and y down from the top-left corner; pixel (0, 0) spans 0..1",
                },
                "eris_motion_squares": motion_sq,
            },
            "track_mjd": (track.dt + t0).tolist(),
            "stops": stops,
            "best_s2": best_s2,
            "no_bend_snr": s0,
            "meter_basis": "snr and delta: S/N with place and drift free at each 1/d (reflex.profile with no drift "
            "box), the same rule as the module's straight-track test; *_module_profile: the module's "
            "published profile (drift box per 1/d) interpolated, except No bend, which is the "
            "module's straight track",
            "wrong_way": wrong,
            "sketch_exaggeration": SKETCH_EXAGGERATION,
            "sketch_bend_at_best_arcsec": float(np.max(bend)),
            "sketch_drift_length_arcsec": drift_len,
            "foldout": {"blank_field_raw_peaks": null_run_peaks(res)},
            "checks": checks,
        }
    return out, pngs


def grid_far_limit(nearest_au: float) -> float:
    """1 / the smallest positive 1/d of the reflex coarse grid (from -1/nearest in INVD_STEP steps)."""
    import numpy as np

    from backend import reflex

    invds = np.arange(-1.0 / nearest_au, 1.0 / nearest_au + 1e-9, reflex.INVD_STEP)
    return float(round(1.0 / float(np.min(invds[invds > 1e-9])), 1))


def ranging_limits(note: str) -> dict:
    m = re.search(r"within about (\d+) AU at the S/N 8 threshold and about (\d+) AU for an Eris-bright body", note)
    if not m:
        return unavailable("the module's RANGING_NOTE no longer states the two ranging distances")
    return {
        "available": True,
        "at_threshold_au": float(m.group(1)),
        "eris_bright_au": float(m.group(2)),
        "visit_days": 15,
        "source": "backend/reflex.py RANGING_NOTE (scaled from the measured Eris profile)",
    }


def null_run_peaks(res: dict) -> dict:
    rows = []
    for k, v in res.items():
        if k.startswith("null_runs"):
            rows += v.get("rows", [])
    seen = {(tuple(r["visit_mjd"]), r["field"]): r for r in rows}
    fwd = [r["max_forward_raw_snr"] for r in seen.values() if r.get("max_forward_raw_snr") is not None]
    rev = [r["max_reversed_raw_snr"] for r in seen.values() if r.get("max_reversed_raw_snr") is not None]
    surv = sum(r.get("n_reversed_surviving_vetting", 0) for r in seen.values())
    if not fwd:
        return unavailable("results.json holds no null runs")
    return {
        "available": True,
        "n_field_visits": len(seen),
        "max_forward": fwd,
        "max_reversed": rev,
        "n_reversed_surviving_vetting": surv,
        "note": "raw peaks; every one at 8 or more was removed by the other-visit test or the vetoes",
    }


# ------------------------------------------------------------------------------------------- tool 2: colour walk


def export_colourwalk(cache_root: Path) -> tuple[dict, dict[str, bytes]]:
    import numpy as np

    from backend import astrometry
    from backend import colourwalk as cw
    from scripts import check_colourwalk

    res = json.loads((ROOT / RESULTS["colourwalk"]).read_text())
    b = res["vhs1256"]["blind_scan"]
    host = dict(b["host"])
    pngs: dict[str, bytes] = {}
    checks: dict[str, Any] = {}
    with cache_folder(cache_root):
        paths = sorted((cache_root / "cutouts" / check_colourwalk.VHS_DIR).glob("*.fits"))
        log(f"colourwalk: {len(paths)} VHS 1256 cutouts; fitting the host in each (the module's measure_host)")
        rows = cw.measure_host(paths, host, None, workers=4)
        w_all = cw.walks(rows)["all"]
        checks["walk_reproduced"] = {k: round(w_all[k], 4) for k in ("east", "north", "pa", "size", "sigma")}
        checks["n_clean_fits_reproduced"] = len(rows)
        saved = (cw.FLOOR_EAST, cw.FLOOR_NORTH)
        cw.FLOOR_EAST = cw.FLOOR_NORTH = cw.FLOOR_ARCSEC
        try:
            sigma_guess = cw.walks(rows)["all"]["sigma"]
        finally:
            cw.FLOOR_EAST, cw.FLOOR_NORTH = saved
        groups_def = [
            ("Bluer", cw.SHORT[0], cw.SHORT[1]),
            ("Middle", cw.SHORT[1], cw.LONG[0]),
            ("Redder", cw.LONG[0], cw.LONG[1]),
        ]
        groups, medians = measure_groups(rows, host, groups_def, "colourwalk_vhs1256")
        lo_s, hi_s, soft = shape_stretch(medians)
        for g, m in zip(groups, medians, strict=True):
            pngs[g["png"]] = png_bytes(stretch_asinh(m, lo_s, hi_s, soft))
        n = COLOUR_CROP_PX
        sep, pa = (
            res["vhs1256"]["known_place"]["pa_scan"]["separation"],
            res["vhs1256"]["known_place"]["pa_scan"]["walk_pa"],
        )
        pe, pn = cw.offset_at(sep, pa)
        red = groups[2]
        blue = groups[0]
        walk_px = (
            math.hypot(red["east"] - blue["east"], red["north"] - blue["north"]) / PIXEL_ARCSEC * INSET_PX_PER_SQUARE
        )
        mag = next((m for m in MAGNIFICATIONS if walk_px * m >= INSET_MIN_PX), MAGNIFICATIONS[-1])
        # the part of the walk fixed on the detector: half the sum of the two spacecraft orientations' mean
        # detector-frame walks (orientation = detector angle within 90 degrees of the first visit's, or not)
        vw = b["visit_walks"]
        first = vw[0]["detector"]["angle_deg"]
        grp_a = [x for x in vw if cw.angle_difference(x["detector"]["angle_deg"], first) < 90]
        grp_b = [x for x in vw if cw.angle_difference(x["detector"]["angle_deg"], first) >= 90]
        if grp_a and grp_b:
            fx = 0.5 * (np.mean([x["detector"]["a"] for x in grp_a]) + np.mean([x["detector"]["a"] for x in grp_b]))
            fy = 0.5 * (np.mean([x["detector"]["b"] for x in grp_a]) + np.mean([x["detector"]["b"] for x in grp_b]))
            det_fixed: dict[str, Any] = {
                "available": True,
                "x": float(fx),
                "y": float(fy),
                "size": float(np.hypot(fx, fy)),
                "rule": "half the sum of the mean detector-frame walks of the two spacecraft "
                "orientations (visits grouped by detector-frame angle)",
            }
        else:
            det_fixed = unavailable("every visit had the same spacecraft orientation")
        lone = lone_star(cache_root, cw, astrometry, check_colourwalk, w_all["size"], pngs, (lo_s, hi_s, soft))
        red_ctrl = [
            x["control_max"]
            for x in res["vhs1256"]["known_place"]["net_ratio"]
            if x.get("control_max") is not None and x["lo"] >= cw.LONG[0]
        ]
        out = {
            "walk": {
                "sigma_guessed_floor": sigma_guess,
                "guessed_floor_arcsec": cw.FLOOR_ARCSEC,
                "measured_floor_arcsec": {"east": cw.FLOOR_EAST, "north": cw.FLOOR_NORTH},
                "detector_fixed_arcsec": det_fixed,
            },
            "known": {"ref": "Gauza et al. 2015"},
            "known_place": {"control_max": max(red_ctrl) if red_ctrl else None},
            "rule_sigma": cw.WALK_SIGMA,
            "groups": groups,
            "picture": {
                "crop_px": n,
                "pixel_arcsec": PIXEL_ARCSEC,
                "north_up_east_left": True,
                "host_px": [n / 2, n / 2],
                "partner_px": to_picture_px(pe, pn, 0.0, 0.0, n),
                "partner_offset_arcsec": [pe, pn],
                "made_from": "each clean exposure of the group, resampled bilinearly onto a north-up grid centred on "
                "the host's Gaia-predicted place at that exposure's date, divided by the host's fitted "
                "flux in that exposure; the picture is the per-pixel median",
                "stretch": {
                    "kind": "asinh",
                    "unit": "share of the host's fitted light in one square",
                    "lo": lo_s,
                    "hi": hi_s,
                    "soft": soft,
                    "formula": "grey = 255 * clip(asinh((v - lo) / soft) / asinh((hi - lo) / soft), 0, 1)",
                    "rule": "lo = 0; hi = the brightest pixel of the three medians; soft = hi / 20; the same "
                    "for the three groups",
                },
                "units": "picture pixels, x right and y down from the top-left corner",
            },
            "magnification": mag,
            "magnification_rule": {
                "choices": list(MAGNIFICATIONS),
                "min_px": INSET_MIN_PX,
                "px_per_square": INSET_PX_PER_SQUARE,
                "rule": "smallest choice that puts the Redder dot at least min_px from the Bluer cross",
            },
            "lone_star": lone,
            "checks": checks,
        }
    return out, pngs


def measure_groups(rows: list[dict], host: dict, groups_def, prefix: str):
    """Per colour group: the module's group_offset (median East/North offset from Gaia, errors with the measured
    floors) and the median picture of the same exposures re-registered on the host's predicted place."""
    import numpy as np

    from backend import astrometry
    from backend import colourwalk as cw

    n = COLOUR_CROP_PX
    groups, medians = [], []
    for name, lo, hi in groups_def:
        g = cw.group_offset(rows, lo, hi)
        use = [r for r in rows if lo <= r["lam"] < hi and r["eE"] < 0.5]
        stack = []
        for r in use:
            cut = cw.read_cutout(r["path"])
            h_ra, h_dec = astrometry.position_at(host, cut["mjd"])
            ge, gn = north_up_grid(n, 0.0, 0.0)
            cosd = math.cos(math.radians(h_dec))
            s_ra, s_dec = h_ra + ge / 3600.0 / cosd, h_dec + gn / 3600.0
            img = np.where(cut["bad"], np.nan, cut["data"])
            stack.append(sample(img, ~cut["bad"], cut["wcs"], s_ra, s_dec) / (r["flux"] / cw.MJY_PER_PIXEL_SR))
        medians.append(np.nanmedian(stack, axis=0))
        groups.append(
            {
                "name": name,
                "lo_um": lo,
                "hi_um": hi,
                "png": f"{prefix}_{name.lower()}.png",
                "east": g["east"],
                "north": g["north"],
                "err_east": g["err_east"],
                "err_north": g["err_north"],
                "n": g["n"],
                "n_in_picture": len(stack),
            }
        )
    return groups, medians


def shape_stretch(medians) -> tuple[float, float, float]:
    import numpy as np

    hi = float(max(np.nanmax(m) for m in medians))
    return 0.0, hi, hi / 20.0


def lone_star(cache_root, cw, astrometry, check_colourwalk, vhs_walk: float, pngs: dict, stretch) -> dict:
    """'Compare: a star on its own' (spec 5.2). The rule, written here before any star is measured: in the Barnard
    field, the brightest isolated star (G 11.5 to 15, no Gaia star brighter than G + 3 within 12 arcsec) that has at
    least one clean fit in each of the six detectors, measured exactly as VHS 1256 is (raw offsets from Gaia)."""
    import numpy as np

    rule = (
        "Barnard field: the brightest isolated star (G 11.5 to 15, no Gaia star brighter than G + 3 within "
        "12 arcsec, colourwalk.isolated_mask at the field's median date) with at least one clean fit in each of "
        "the six detectors, measured as VHS 1256 (colourwalk.measure_host, raw offsets from Gaia); shown "
        "whatever it looks like"
    )
    log("colourwalk lone-star rule (logged before any star is measured): " + rule)
    directory = check_colourwalk.BARNARD
    ra0, dec0, paths = check_colourwalk.field_centre(directory)
    try:
        stars = cw.gaia_neighbours(ra0, dec0, 400.0, 21.0)
    except Exception as err:  # noqa: BLE001
        return {**unavailable(f"Gaia stars of the Barnard field not on disk: {err}"), "rule": rule}
    table_file = cache_root / "queries" / f"cwfield_{directory}_{len(paths)}_{len(stars)}.npy"
    if not table_file.exists():
        return {**unavailable("the Barnard fit table is not on disk"), "rule": rule}
    mjd0 = float(np.median(np.load(table_file)[:, 1]))
    iso = cw.isolated_mask(stars, mjd0, (11.5, 15.0))
    order = sorted(np.flatnonzero(iso), key=lambda i: stars[i]["gmag"])
    for i in order:
        s = stars[int(i)]
        host = {
            "ra": s["ra"],
            "dec": s["dec"],
            "pmra": s["pmra"] or 0.0,
            "pmdec": s["pmdec"] or 0.0,
            "parallax": s["parallax"] or 0.0,
            "source_id": s["source_id"],
            "gmag": s["gmag"],
        }
        rows = cw.measure_host(paths, host, None, workers=4)
        dets = {int(r["det"]) for r in rows}
        log(
            f"colourwalk lone star: Gaia DR3 {s['source_id']} G {s['gmag']:.2f}: "
            f"{len(rows)} fits in detectors {sorted(dets)}"
        )
        if dets != {1, 2, 3, 4, 5, 6}:
            continue
        w = cw.walks(rows)["all"]
        groups_def = [
            ("Bluer", cw.SHORT[0], cw.SHORT[1]),
            ("Middle", cw.SHORT[1], cw.LONG[0]),
            ("Redder", cw.LONG[0], cw.LONG[1]),
        ]
        groups, medians = measure_groups(rows, host, groups_def, "colourwalk_lone")
        for g, m in zip(groups, medians, strict=True):
            pngs[g["png"]] = png_bytes(stretch_asinh(m, *stretch))
        return {
            "available": True,
            "rule": rule,
            "gaia_id": s["source_id"],
            "gmag": s["gmag"],
            "n_clean_fits": len(rows),
            "walk": {k: w[k] for k in ("east", "north", "pa", "size", "sigma", "p_false", "err_east", "err_north")},
            "walk_size": w["size"],
            "ratio_to_vhs_walk": w["size"] / vhs_walk,
            "groups": groups,
            "picture_note": "same crop, resampling and stretch as VHS 1256's pictures",
        }
    return {**unavailable("no isolated star in the Barnard field has a clean fit in all six detectors"), "rule": rule}


# ------------------------------------------------------------------------------------------- tool 3: transits


def export_transits(cache_root: Path) -> tuple[dict, dict[str, bytes]]:
    import numpy as np

    from backend import transits as T
    from scripts import check_transit

    res = json.loads((ROOT / RESULTS["transits"]).read_text())
    w = res["wasp62"]
    d5 = w["detectors"]["5"]
    spec = check_transit.WASP62
    ra, dec = cast(float, spec["ra"]), cast(float, spec["dec"])
    P, t0 = cast(float, spec["period_d"]), cast(float, spec["t0_bjd_tdb"])
    t14, k = cast(float, spec["t14_h"]), cast(float, spec["rprs"])
    cache_dir = cache_root / "invent-P1"
    size = 0.1
    comps = [s["source_id"] for s in w["comparison_stars"]]
    tag = hashlib.sha1(f"{ra:.5f},{dec:.5f},{size},{T.APERTURE_PX},{False},{comps}".encode()).hexdigest()[:10]
    found = sorted((cache_dir / "results").glob(f"rows_v{T.VERSION}_{tag}_5_*.json"))
    if len(found) != 1:
        raise RuntimeError(f"expected one cached detector-5 reading file for WASP-62, found {len(found)}")
    rows = json.loads(found[0].read_text())
    log(f"transits: {found[0].name}: {len(rows)} cutouts measured")
    pngs: dict[str, bytes] = {}
    checks: dict[str, Any] = {}
    c = T.columns(rows, 0, ra, dec)
    full = T.analyse_detector(c, P, t0, t14, k, extras=True)
    for key in ("depth", "formal_err", "empirical_err", "n", "n_in", "n_fake"):
        checks[f"{key}_reproduced"] = [full[key], d5[key]]
    # the module's steps up to the final fit, to know which readings it kept (verified against its own output)
    bjd = c["bjd"]
    shape0 = T.trapezoid(T.time_from_mid(bjd, P, t0), t14, k)
    okm = c["ok"] & np.isfinite(c["flux"])
    rel = np.full(len(bjd), np.nan)
    rel[okm] = T.template_divide(c["wl"][okm], c["flux"][okm], (shape0 == 0)[okm], T.TEMPLATE_NEIGHBOURS)
    m = okm & (np.abs(rel - 1) < 0.15)
    sub = {key: v[m] for key, v in c.items()}
    _, _, resid = T.fit_depth(rel[m], T.design(sub, shape0[m]), 1.0)
    sig0 = T.robust_std(resid)
    keep = m.copy()
    keep[m] = np.abs(resid) < T.CLIP_SIGMA * sig0
    sub = {key: v[keep] for key, v in c.items()}
    A = T.design(sub, shape0[keep])
    depth, _, resid = T.fit_depth(rel[keep], A, sig0)
    sig = T.robust_std(resid)
    checks["depth_by_mirror_equals_module"] = bool(abs(depth - full["depth"]) < 1e-12)
    hours = T.time_from_mid(bjd[keep], P, t0) * 24
    checks["readings_align_with_module_fold"] = bool(np.allclose(hours, full["folded"]["hours"]))
    corr = np.array(full["folded"]["flux"])
    idx = np.flatnonzero(keep)
    readings = [
        {
            "bjd_tdb": float(bjd[i]),
            "rel_flux": float(corr[j]),
            "err": float(c["err"][i] / c["flux"][i]),
            "wl_um": float(c["wl"][i]),
        }
        for j, i in enumerate(idx)
    ]
    # dial stops. depth: the module's own analyse_detector at that period and the same T0 (null where the module
    # refuses: fewer than MIN_IN_TRANSIT readings inside a crossing). depth_fixed_model: the module's model on the
    # same kept readings with the same template and sigma, only the trapezoid's period changed (a reference only).
    stops = []
    for p_stop in TRANSIT_STOPS_D:
        per = P if p_stop is None else p_stop
        sh = T.trapezoid(T.time_from_mid(bjd[keep], per, t0), t14, k)
        dep, err, _ = T.fit_depth(rel[keep], T.design(sub, sh), sig)
        refit = T.analyse_detector(c, per, t0, t14, k, extras=False)
        ok_fit = refit.get("status") == "ok"
        ratio_ok = min(abs(per / P - q) for q in T.FAKE_EXCLUDE) >= T.FAKE_EXCLUDE_TOL
        steps = (per - T.FAKE_PERIODS[0]) / T.FAKE_PERIODS[2]
        on_grid = abs(steps - round(steps)) < 1e-6
        stop: dict[str, Any] = {
            "period_d": per,
            "known": p_stop is None,
            "depth": refit["depth"] if ok_fit else None,
            "err": refit["formal_err"] if ok_fit else None,
            "n_in": refit.get("n_in"),
            "readings_in_window": int((np.abs(T.time_from_mid(bjd[keep], per, t0)) * 24 <= TRANSIT_WINDOW_H).sum()),
            "depth_fixed_model": dep,
            "err_fixed_model": err,
            "readings_in_crossing_fixed_model": int((sh > 0).sum()),
            "allowed_by_fake_exclude": p_stop is None or bool(ratio_ok and on_grid),
        }
        if not ok_fit:
            stop["why"] = (
                f"only {refit.get('n_in')} readings fall inside a crossing on this timetable; the module fits a "
                f"depth only with at least {T.MIN_IN_TRANSIT}"
            )
        stops.append(stop)
    # fakes as deep, and the deepest fake (the module's own fake machinery, rerun on the same readings)
    out_m = keep & (shape0 == 0)
    base_cols = {key: v[out_m] for key, v in c.items()}
    nul = []
    for pf, off in T.fake_ephemerides(P):
        sf = T.trapezoid(T.time_from_mid(bjd[out_m] - off * pf, pf, t0), t14, k)
        if (sf > 0).sum() < T.MIN_FAKE_IN_TRANSIT:
            continue
        nul.append(T.fit_depth(rel[out_m], T.design(base_cols, sf), sig)[0])
    nul_a = np.array(nul)
    checks["n_fake_reproduced"] = [len(nul), d5["n_fake"]]
    # per-transit sign test (the write-up's reviewer check): transits with flat-bottom readings whose mean
    # corrected brightness is below 1
    flat = T.trapezoid(T.time_from_mid(bjd[keep], P, t0), t14, k) >= 1.0
    epoch = np.round((bjd[keep] - t0) / P).astype(int)
    eps = sorted(set(epoch[flat].tolist()))
    dips = sum(1 for ep in eps if np.mean(corr[flat & (epoch == ep)]) < 1.0)
    from scipy.stats import binomtest

    sign = {
        "available": True,
        "n_transits": len(eps),
        "n_below_baseline": dips,
        "p_value": float(binomtest(dips, len(eps), 0.5, alternative="greater").pvalue),
        "rule": "transits with readings in the flat bottom of the trapezoid; a transit dips when the mean of those "
        "corrected readings is below 1",
    }
    # picture: of the kept readings whose cutout is on disk, the one nearest the median time of the kept readings
    kept_rows = [r for r in rows if r["m"][0] is not None]
    exps = {(x["obs_id"], x["detector"]): x for x in T.exposure_list(ra, dec, cache_dir)}
    picture: dict[str, Any] = unavailable("no kept detector-5 reading has its cutout on disk")
    got: dict = {}
    j_pic, r_pic = -1, {}
    for j in idx[np.argsort(np.abs(bjd[idx] - np.median(bjd[keep])), kind="stable")]:
        exp = exps.get((kept_rows[j]["obs_id"], 5))
        got, _ = T.get_cutouts([exp], ra, dec, size, cache_dir, fetch=False) if exp else ({}, [])
        if got:
            j_pic, r_pic = int(j), kept_rows[j]
            break
    if got:
        picture = transit_picture(next(iter(got.values())), ra, dec, pngs)
        picture.update(
            {
                "mjd": r_pic["mjd"],
                "obs_id": r_pic["obs_id"],
                "wl_um": float(c["wl"][j_pic]),
                "in_transit": bool(shape0[j_pic] > 0),
                "rule": "of the kept detector-5 readings whose cutout is on disk, the one nearest the median time of "
                "the kept readings",
            }
        )
    years = sorted({int(iso_from_jd(x)[:4]) for x in bjd[keep]})
    a3 = res["acceptance"]["A3"]
    n_clear = sum(
        1 for x in a3["per_detector"].values() if not x.get("excluded") and (x.get("empirical_sigma") or 0) >= 3
    )
    text = (ROOT / WRITEUPS["transits"]).read_text()
    refs = {
        "planet": "Hellier et al. 2012" if "Hellier" in text else None,
        "timetable_and_depth": "Kokori et al. 2023" if "Kokori et al. 2023" in text else None,
    }
    w100_fake = {
        d: {
            "n_fake": x.get("n_fake"),
            "n_fake_as_deep": round(x["fake_share_as_deep"] * x["n_fake"]) if x.get("n_fake") else None,
        }
        for d, x in res["wasp100"]["detectors"].items()
        if x.get("status") == "ok"
    }
    out = {
        "development_object": "not a blind test" in text,
        "development_object_evidence": next((ln.strip() for ln in text.splitlines() if "not a blind test" in ln), None),
        "refs": refs,
        "d5": {
            "n_fake_as_deep": int(round(d5["fake_share_as_deep"] * d5["n_fake"])),
            "deepest_fake_depth": float(nul_a.max()) if len(nul_a) else None,
            "sign_test": sign,
        },
        "readings": readings,
        "readings_note": "the module's kept detector-5 readings: each divided by the star's own spectrum and corrected "
        "by its detector-position and sub-pixel terms (fitted on the published timetable); err is the "
        "reading's own statistical error as a fraction; the fit itself gives every reading the "
        "same error, d5.scatter",
        "stops": stops,
        "stops_note": "depth and err: the module's analyse_detector rerun at that period with the published T0 (null, "
        "with why, where it refuses); depth_fixed_model: the module's model on the same kept readings with only the "
        "trapezoid's period changed, a reference only",
        "min_in_transit": T.MIN_IN_TRANSIT,
        "window_h": TRANSIT_WINDOW_H,
        "wasp100": {
            "n_clear": n_clear,
            "n_clear_rule": "usable detectors at 3 or more empirical sigma",
            "fakes": w100_fake,
        },
        "picture": picture,
        "dates": {"first": iso_from_jd(float(bjd[keep].min())), "last": iso_from_jd(float(bjd[keep].max()))},
        "years_present": years,
        "checks": checks,
    }
    return out, pngs


def transit_picture(path: Path, ra: float, dec: float, pngs: dict) -> dict:
    import numpy as np
    from astropy.io import fits
    from astropy.wcs import WCS

    from backend import pipeline

    with fits.open(path) as h:
        raw = h["IMAGE"].data.astype(float)
        img = raw - h["ZODI"].data.astype(float)
        var = h["VARIANCE"].data.astype(float)
        flags = h["FLAGS"].data
        wcs = WCS(h["IMAGE"].header)
    bad = pipeline.impossible_pixels(raw, var) | ~np.isfinite(img)
    data = np.where(bad, np.nan, img - np.nanmedian(img[~bad]))
    n = TRANSIT_CROP_PX
    ge, gn = north_up_grid(n, 0.0, 0.0)
    cosd = math.cos(math.radians(dec))
    c_ra, c_dec = ra + ge / 3600.0 / cosd, dec + gn / 3600.0
    pic = sample(data, ~bad, wcs, c_ra, c_dec)
    px, py = (np.round(v).astype(int) for v in wcs.all_world2pix(c_ra, c_dec, 0))
    inside = (px >= 0) & (px < raw.shape[1]) & (py >= 0) & (py < raw.shape[0])
    ovf_mask = (flags & pipeline._mask("OVERFLOW")) != 0
    ovf = int(len({(int(a), int(b)) for a, b in zip(px[inside], py[inside], strict=True) if ovf_mask[b, a]}))
    noise = float(1.4826 * np.nanmedian(np.abs(pic - np.nanmedian(pic))))
    lo, hi = float(np.nanmedian(pic)) - noise, float(np.nanmax(pic))
    soft = noise
    pngs["transits_wasp62.png"] = png_bytes(stretch_asinh(pic, lo, hi, soft))
    return {
        "available": True,
        "png": "transits_wasp62.png",
        "crop_px": n,
        "pixel_arcsec": PIXEL_ARCSEC,
        "north_up_east_left": True,
        "star_px": [n / 2, n / 2],
        "overflow_pixels_in_crop": ovf,
        "made_from": "one detector-5 cutout, IMAGE minus ZODI minus its median, resampled bilinearly onto a north-up "
        "grid centred on the star",
        "stretch": {
            "kind": "asinh",
            "unit": "MJy/sr",
            "lo": lo,
            "hi": hi,
            "soft": soft,
            "formula": "grey = 255 * clip(asinh((v - lo) / soft) / asinh((hi - lo) / soft), 0, 1)",
            "rule": "lo = median - 1 robust sigma; soft = 1 robust sigma; hi = the brightest pixel",
        },
    }


# ------------------------------------------------------------------------------------------- status words (keys)


def status_reflex(h: dict) -> dict:
    ch = h["checks"]
    found = bool(ch.get("A1 within 4 arcsec of JPL") and ch.get("A2 S/N >= 12"))
    return {
        "chip_key": "found_test_world_distance_rough" if found else "test_world_not_found",
        "found_test_world": found,
        "passed_all_checks": h["passed"],
        "chip": "Found its test world. Distance only rough." if found else None,
        "headline": "Result: the tool found Eris, a world known since 2005, and measured its distance roughly."
        if found
        else None,
        "source": "the module's checks A1 and A2 (place within 4 arcsec, S/N at least 12); the spec's words",
    }


def status_colourwalk(h: dict) -> dict:
    proven = h["acceptance"]["passed"] and h["null"]["acceptance"]["passed"] and h["verdict"] != "nothing_found"
    return {
        "chip_key": "proven" if proven else "not_proven",
        "method_proven": bool(proven),
        "verdict": h["verdict"],
        "chip": None if proven else "Not proven yet",
        "source": "results.json: the blind verdict, the 7 pre-set checks and the null test; docs/colourwalk.md "
        "status 'method not proven'",
    }


def status_transits(h: dict, n_clear: int) -> dict:
    a = h["acceptance"]
    if a["A1"] and n_clear == 1:
        key = "one_dip_mixed_second"
    elif a["A1"] and n_clear >= 2:
        key = "one_dip_second_passed"
    elif a["A1"]:
        key = "one_dip_second_not_seen"
    else:
        key = "no_clear_dip"
    return {
        "chip_key": key,
        **a,
        "chip": "Showed one known planet's dip. Mixed on a second." if key == "one_dip_mixed_second" else None,
        "headline": "Result: lined up, SPHEREx's readings show the dip that the known planet WASP-62 b makes as it "
        "crosses its star."
        if a["A1"]
        else None,
        "source": "acceptance A1 and the number of WASP-100 b detectors at 3 empirical sigma",
    }


# ------------------------------------------------------------------------------------------- write and check


EXPORTERS = {"reflex": export_reflex, "colourwalk": export_colourwalk, "transits": export_transits}


def build(tool: str, cache_root: Path) -> tuple[dict, dict[str, bytes]]:
    res = json.loads((ROOT / RESULTS[tool]).read_text())
    head = HEADLINES[tool](res)
    computed, pngs = EXPORTERS[tool](cache_root)
    final, evidence = final_flag(tool, ROOT)
    doc = deep_merge(sig(computed), head)
    if tool == "reflex":
        status = status_reflex(head)
    elif tool == "colourwalk":
        status = status_colourwalk(head)
    else:
        status = status_transits(head, computed["wasp100"]["n_clear"])
    doc = {
        "schema": SCHEMA,
        "tool": tool,
        "source": provenance(tool),
        "final": final,
        "final_evidence": evidence,
        "status": status,
        **doc,
        "files": {name: sha256_bytes(b) for name, b in sorted(pngs.items())},
    }
    return doc, pngs


def write(tool: str, doc: dict, pngs: dict[str, bytes], lab: Path) -> None:
    lab.mkdir(parents=True, exist_ok=True)
    for old in lab.glob(f"{tool}_*.png"):
        if old.name not in pngs:
            old.unlink()
    for name, b in pngs.items():
        (lab / name).write_bytes(b)
    (lab / f"{tool}.json").write_text(json.dumps(doc, indent=1, allow_nan=False) + "\n")
    log(f"wrote {lab / (tool + '.json')} ({(lab / (tool + '.json')).stat().st_size} bytes) and {len(pngs)} pictures")


def check(lab: Path, root: Path) -> list[str]:
    """Problems that make a lab file out of date with the results files (empty list: all up to date)."""
    problems = []
    for tool in TOOLS:
        f = lab / f"{tool}.json"
        if not f.exists():
            problems.append(f"{f.name}: missing")
            continue
        doc = json.loads(f.read_text())
        res_path = root / RESULTS[tool]
        if doc.get("source", {}).get("results_sha256") != sha256_file(res_path):
            problems.append(
                f"{f.name}: made from a different {RESULTS[tool]} (run scripts/export_lab.py --tool {tool})"
            )
        head = HEADLINES[tool](json.loads(res_path.read_text()))
        for path, value in leaves(head):
            try:
                got = get_path(doc, path)
            except KeyError:
                problems.append(f"{f.name}: {'.'.join(path)} missing")
                continue
            if json.dumps(got, sort_keys=True) != json.dumps(value, sort_keys=True):
                problems.append(
                    f"{f.name}: {'.'.join(path)} is {json.dumps(got)[:80]}, results say {json.dumps(value)[:80]}"
                )
        for path in REQUIRED[tool]:
            try:
                get_path(doc, path)
            except KeyError:
                problems.append(f"{f.name}: required field {path} missing")
        for name, digest in doc.get("files", {}).items():
            p = lab / name
            if not p.exists():
                problems.append(f"{name}: missing")
            elif sha256_file(p) != digest:
                problems.append(f"{name}: not the picture {f.name} was written with")
        final, _ = final_flag(tool, root)
        if doc.get("final") != final:
            problems.append(f"{f.name}: final is {doc.get('final')}, {WRITEUPS[tool]} now says {final}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tool", choices=[*TOOLS, "all"], default="all")
    ap.add_argument("--check", action="store_true", help="offline: compare the lab files with the results files")
    ap.add_argument("--lab-dir", type=Path, default=ROOT / "frontend" / "public" / "lab")
    ap.add_argument("--root", type=Path, default=ROOT, help="checkout whose docs/*/results.json --check reads")
    args = ap.parse_args(argv)
    if args.check:
        problems = check(args.lab_dir, args.root)
        for p in problems:
            print("OUT OF DATE  " + p)
        if not problems:
            print("lab files are up to date with the results files")
        return 1 if problems else 0
    import os

    cache_root = Path(os.environ.get("SPHEREX_CACHE_DIR") or ROOT / "backend" / "cache")
    sys.path.insert(0, str(ROOT))
    for tool in TOOLS if args.tool == "all" else (args.tool,):
        doc, pngs = build(tool, cache_root)
        write(tool, doc, pngs, args.lab_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Request every view the demo will use, so nothing is downloaded in front of the judges.

Run:  .venv/bin/python scripts/warm_cache.py                  warm everything
      .venv/bin/python scripts/warm_cache.py --check          prove the cache is warm, network blocked
      .venv/bin/python scripts/warm_cache.py --only barnard --detectors 5

Views: the five test targets x six detectors x every display mode and option the backend
has (normal; difference against the first epoch and against the mean; sum on the sky
and following the target), at the backend's default field of view, plus the brightness
chart and spectrum (all detectors together and each alone). Each is requested twice:
with the target's proper motion and parallax, as a name search on the site passes
them, and without, as a plain coordinate link asks. The backend caches the two
separately.

The pipeline functions are called directly (no HTTP), one view at a time; the backend
already runs six downloads in parallel and this script adds none. Finished work is
skipped because the backend caches on disk, so it is safe to run again.

Target positions come from backend.astrometry.resolve_name, the same function the
site's name search uses, so the views warmed here are the views the site asks for.
"""
from __future__ import annotations

import argparse
import inspect
import resource
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import astrometry, pipeline, spherex  # noqa: E402

try:                                    # the brightness chart and spectrum, once they exist
    from backend import photometry  # noqa: E402
except ImportError:
    photometry = None  # type: ignore[assignment]

# `query` is the name handed to the resolver. `also` lists other spellings a person is
# likely to type in the demo: the name search caches its answer per spelling, so each
# one is asked once here.
TARGETS: list[dict] = [
    {"slug": "barnard", "name": "Barnard's Star", "query": "Barnard's Star", "also": ["Barnards Star"]},
    {"slug": "eps_indi_b", "name": "Epsilon Indi B", "query": "Epsilon Indi B", "also": ["eps Ind B"]},
    {"slug": "wise0855", "name": "WISE 0855-0714", "query": "WISE 0855-0714",
     "also": ["WISE 0855", "WISE J085510.83-071442.5"]},
    {"slug": "rw_aur", "name": "RW Aurigae", "query": "RW Aurigae", "also": ["RW Aur"]},
    {"slug": "r_dra", "name": "R Draconis", "query": "R Draconis", "also": ["R Dra"]},
]
DETECTORS = [1, 2, 3, 4, 5, 6]
# (label, mode, options). A mode or option the backend does not have is skipped.
VARIANTS: list[tuple[str, str, dict]] = [
    ("normal", "normal", {}),
    ("difference (first)", "difference", {"reference": "first"}),
    ("difference (mean)", "difference", {"reference": "mean"}),
    ("sum (sky)", "sum", {"track": "sky"}),
    ("sum (target)", "sum", {"track": "target"}),
]
_PARAMS = inspect.signature(pipeline.build_frames).parameters
DEFAULT_FOV: float = _PARAMS["fov"].default
PAUSE_S = 60          # wait this long after archive trouble before trying a view again
ATTEMPTS = 3          # tries per view


def resolve(target: dict) -> dict:
    """Where a target is now, exactly as the site's name search reports it.

    Returns resolve_name's whole answer: "ra" and "dec" (degrees, ICRS, moved to a fixed
    recent date with the proper motion), plus the motion and where it came from.
    """
    fn = getattr(astrometry, "resolve_name", None)
    if fn is None:
        raise RuntimeError("backend.astrometry.resolve_name does not exist")
    return fn(target["query"])


def motion_options(pos: dict) -> dict:
    """The motion parameters a name search hands to /api/frames, or {} if none are known."""
    if pos.get("pmra") is None or pos.get("pmdec") is None or "pmra" not in _PARAMS:
        return {}
    return {"pmra": pos["pmra"], "pmdec": pos["pmdec"], "parallax": pos.get("parallax"),
            "pm_epoch": pos.get("epoch", _PARAMS["pm_epoch"].default)}


def cache_megabytes() -> dict[str, float]:
    """Size of each folder under backend/cache, in MB."""
    sizes = {}
    for sub in sorted(p for p in spherex.CACHE.iterdir() if p.is_dir()):
        sizes[sub.name] = sum(f.stat().st_size for f in sub.rglob("*") if f.is_file()) / 1e6
    return sizes


def warm_view(ra: float, dec: float, fov: float, detector: int, mode: str,
              attempts: int = ATTEMPTS, pause_s: float = PAUSE_S, **options) -> dict:
    """Build one view, retrying after a pause if the archive let us down.

    `options` go to build_frames as they are (pmra, pmdec, parallax, pm_epoch,
    reference, track). Returns {"status", "frames", "seconds", "detail", "meta"}.
    Status is one of: ok; skipped (the backend has no such mode or option, or it does
    not apply to this target); empty (no frames: a result, not an error); partial
    (some cutouts never arrived or Gaia did not answer: the backend does not cache
    such a result, so the view is not warm); failed.
    """
    start = time.time()
    out: dict = {"status": "failed", "frames": 0, "detail": "", "meta": None}
    unknown = [k for k in options if k not in _PARAMS]
    if unknown:
        out.update(status="skipped", detail=f"build_frames has no option {', '.join(unknown)}", seconds=0.0)
        return out
    for attempt in range(1, attempts + 1):
        try:
            meta = pipeline.build_frames(ra, dec, fov=fov, detector=detector, mode=mode, **options)
        except (NotImplementedError, ValueError) as e:
            # Not built, or not possible here (for example following a target with no known motion).
            out.update(status="skipped", detail=str(e))
            break
        except spherex.ArchiveError as e:
            out.update(status="failed", detail=f"archive: {e}")
        except Exception as e:  # noqa: BLE001 - a backend bug must not stop the other views
            out.update(status="failed", detail=f"{type(e).__name__}: {e}")
            break
        else:
            frames = meta.get("frames", [])
            missing = meta.get("failures") or []
            out.update(frames=len(frames), meta=meta)
            if missing or meta.get("gaia_error"):
                # Incomplete: the backend returns it but does not cache it, so this view
                # is NOT warm. Trying again fetches what is missing.
                why = [f"{len(missing)} cutouts could not be fetched, e.g. {missing[0]}"] if missing else []
                why += [f"Gaia did not answer: {meta['gaia_error']}"] if meta.get("gaia_error") else []
                out.update(status="partial", detail="; ".join(why))
            elif not frames:
                out.update(status="empty", detail=meta.get("message", "no frames"))
                break
            else:
                out.update(status="ok", detail="")
                break
        if attempt < attempts:
            print(f"      archive trouble ({out['detail'][:90]}); waiting {pause_s:.0f} s before retry "
                  f"{attempt + 1}/{attempts}", flush=True)
            time.sleep(pause_s)
    out["seconds"] = time.time() - start
    return out


def warm_series(ra: float, dec: float, detector: int | None, attempts: int = ATTEMPTS,
                pause_s: float = PAUSE_S, **motion) -> dict:
    """Build the brightness measurements behind /api/lightcurve and /api/spectrum.

    Both endpoints read one cached set of per-exposure measurements, so one call of
    each warms both. Returns {"status", "points", "counts", "seconds", "detail"}; seconds
    is the slower of the two calls.
    """
    out: dict = {"status": "skipped", "points": 0, "counts": {}, "seconds": 0.0,
                 "detail": "backend.photometry does not exist"}
    if photometry is None:
        return out
    for attempt in range(1, attempts + 1):
        try:
            t0 = time.time()
            curve = photometry.lightcurve(ra, dec, detector, **motion)
            t1 = time.time()
            photometry.spectrum(ra, dec, None, detector, **motion)
            out["seconds"] = max(t1 - t0, time.time() - t1)
        except spherex.ArchiveError as e:
            out.update(status="failed", detail=f"archive: {e}")
        except Exception as e:  # noqa: BLE001 - a backend bug must not stop the other views
            out.update(status="failed", detail=f"{type(e).__name__}: {e}")
            break
        else:
            missing = curve.get("failures") or []
            out.update(points=curve.get("n_exposures", 0), counts=curve.get("status_counts", {}))
            if not missing and not curve.get("gaia_error"):
                out.update(status="ok" if out["points"] else "empty", detail=curve.get("message", ""))
                break
            # Incomplete results are not cached by the backend, so this one is not warm; try again.
            why = [f"{len(missing)} cutouts could not be fetched, e.g. {missing[0]}"] if missing else []
            why += [f"Gaia did not answer: {curve['gaia_error']}"] if curve.get("gaia_error") else []
            out.update(status="partial", detail="; ".join(why))
        if attempt < attempts:
            print(f"      archive trouble ({out['detail'][:90]}); waiting {pause_s:.0f} s before retry "
                  f"{attempt + 1}/{attempts}", flush=True)
            time.sleep(pause_s)
    return out


def block_network() -> None:
    """Make every new network connection fail, to prove a view needs none."""
    def refuse(*_args, **_kwargs):
        raise OSError("network blocked by warm_cache.py --check")
    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", nargs="+", metavar="SLUG", help="targets to do: " +
                        ", ".join(t["slug"] for t in TARGETS))
    parser.add_argument("--detectors", nargs="+", type=int, default=DETECTORS, metavar="N")
    parser.add_argument("--fov", type=float, default=DEFAULT_FOV, help=f"degrees (default {DEFAULT_FOV})")
    parser.add_argument("--check", action="store_true",
                        help="block the network and time every view; exit 1 unless all load in under a second")
    args = parser.parse_args()
    targets = [t for t in TARGETS if not args.only or t["slug"] in args.only]

    if args.check:
        block_network()
    started = time.time()
    positions: dict[str, dict] = {}
    problems: list[str] = []
    for t in targets:
        try:
            positions[t["slug"]] = resolve(t)
            for spelling in t.get("also", []):
                other = astrometry.resolve_name(spelling)
                if (other["ra"], other["dec"]) != (positions[t["slug"]]["ra"], positions[t["slug"]]["dec"]):
                    problems.append(f"{t['name']}: the name '{spelling}' resolves to a different position "
                                    f"({other['ra']}, {other['dec']}), which is not warmed")
        except Exception as e:  # noqa: BLE001 - report and carry on with the other targets
            problems.append(f"{t['name']}: could not resolve the name ({type(e).__name__}: {e})")

    before = cache_megabytes()
    rows: list[tuple[dict, int, str, dict]] = []      # (target, detector, variant label, result)
    series: list[tuple[dict, int | None, str, dict]] = []   # the same for lightcurve and spectrum
    slow = 0
    for t in targets:
        if t["slug"] not in positions:
            continue
        pos = positions[t["slug"]]
        motion = motion_options(pos)
        print(f"\n{t['name']}  RA {pos['ra']:.6f}  Dec {pos['dec']:+.6f}  "
              f"({pos.get('source', '?')}, moved to {pos.get('epoch', '?')})", flush=True)
        for det in args.detectors:
            for label, mode, options in VARIANTS:
                for with_motion in (False, True):
                    if with_motion and not motion:
                        continue
                    name = label + (" +motion" if with_motion else "")
                    # With the network blocked a missing view cannot be fetched: try once only.
                    res = warm_view(pos["ra"], pos["dec"], args.fov, det, mode,
                                    attempts=1 if args.check else ATTEMPTS,
                                    **options, **(motion if with_motion else {}))
                    rows.append((t, det, name, res))
                    if res["status"] == "skipped":
                        continue
                    print(f"   D{det} {name:28s} {res['status']:8s} {res['frames']:2d} frames  "
                          f"{res['seconds']:6.1f} s  {res['detail'][:90]}", flush=True)
                    if args.check and (res["status"] not in ("ok", "empty") or res["seconds"] >= 1.0):
                        slow += 1
                        if slow >= 3 and res["status"] in ("failed", "partial"):
                            print("\nNOT WARM: views needed the network. Run without --check first.")
                            return 1

        # Brightness chart and spectrum: all detectors together, and each one alone.
        if photometry is not None:
            for det in [None, *args.detectors]:
                for with_motion in (False, True):
                    if with_motion and not motion:
                        continue
                    name = "lightcurve+spectrum" + (" +motion" if with_motion else "")
                    res = warm_series(pos["ra"], pos["dec"], det, attempts=1 if args.check else ATTEMPTS,
                                      **(motion if with_motion else {}))
                    series.append((t, det, name, res))
                    print(f"   {'all' if det is None else 'D' + str(det):3s} {name:27s} {res['status']:8s} "
                          f"{res['points']:3d} exposures {res['seconds']:6.1f} s  {res['counts']}  "
                          f"{res['detail'][:60]}", flush=True)

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 78)
    print("check (network blocked)" if args.check else "warm-up", "summary: frames built per view")
    labels = list(dict.fromkeys(name for _, _, name, _ in rows))
    for t in targets:
        print(f"\n{t['name']:30s}" + " ".join(f"{'D' + str(d):>5s}" for d in args.detectors))
        for name in labels:
            cells = []
            for det in args.detectors:
                r = next((r for tt, d, m, r in rows if tt is t and d == det and m == name), None)
                if r is None or r["status"] == "skipped":
                    cells.append("    -")
                else:
                    cells.append(f"{r['frames']:4d}{' ' if r['status'] == 'ok' else '!'}")
            if any(c.strip() != "-" for c in cells):
                print(f"  {name:28s}" + " ".join(cells))
    print("\n('-' = not available for this target or not built; '!' = see the list below)")

    notes: list[str] = []
    for t, det, name, r in rows:
        where = f"{t['name']} D{det} {name}"
        if r["status"] in ("failed", "partial"):
            problems.append(f"{where}: {r['status']}: {r['detail']}")
        elif r["status"] == "empty":
            notes.append(f"{where}: no frames: {r['detail']}")
        if args.check and r["status"] in ("ok", "empty") and r["seconds"] >= 1.0:
            problems.append(f"{where}: took {r['seconds']:.1f} s with the network blocked")
    if series:
        print("\nbrightness chart and spectrum (all detectors together, name-search motion): exposures by status")
        for t, sdet, name, r in series:
            where = f"{t['name']} {'all detectors' if sdet is None else 'D' + str(sdet)} {name}"
            if sdet is None and (name.endswith("+motion") or not motion_options(positions[t["slug"]])):
                print(f"  {t['name']:18s} {r['points']:4d} exposures  {r['counts']}")
            if r["status"] in ("failed", "partial"):
                problems.append(f"{where}: {r['status']}: {r['detail']}")
            elif r["status"] == "empty":
                notes.append(f"{where}: no measurements: {r['detail']}")
            if args.check and r["status"] in ("ok", "empty") and r["seconds"] >= 1.0:
                problems.append(f"{where}: took {r['seconds']:.1f} s with the network blocked")
    skipped = sorted({f"{name}: {r['detail']}" for _, _, name, r in rows if r["status"] == "skipped"})
    for label, items in (("skipped", skipped), ("no frames (a result, not an error)", notes),
                         ("PROBLEMS", problems)):
        print(f"\n{label}: {len(items)}")
        for item in items:
            print("  - " + item)

    after = cache_megabytes()
    done = [r for _, _, _, r in [*rows, *series] if r["status"] != "skipped"]
    print(f"\nviews requested: {len(done)}   slowest: {max((r['seconds'] for r in done), default=0):.2f} s   "
          f"total time: {(time.time() - started) / 60:.1f} min")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1e6 if sys.platform == "darwin" else 1e3)
    print(f"peak memory of this process: {peak:.0f} MB")
    print("cache on disk (MB): " + ", ".join(f"{k} {v:.0f} (+{v - before.get(k, 0):.0f})" for k, v in after.items())
          + f"   total {sum(after.values()):.0f}")
    if args.check:
        print("RESULT: " + ("every view loaded from disk in under a second, network blocked" if not problems
                            else "NOT all views are warm"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

"""Known asteroids and comets that crossed a view, from NASA JPL's small-body services.

What is reported is a prediction: JPL says where each known body was when SPHEREx took
an exposure. Whether SPHEREx recorded it is measured separately, in that one exposure
(`_measure`), and reported as what it is: a source at N sigma, or nothing.

How the lookup works (the request times are in docs/smallbodies.md):

1. Exposures of the view's detector are grouped into bursts of at most CLUSTER_DAYS.
2. For each burst, JPL's Small-Body Identification API (sb_ident) lists the known bodies
   in a field around the view widened to cover the motion of a body during the burst.
   One call takes 20 to 40 s whatever the field size, so a call per exposure is not an
   option. The call is made for the geocentre.
3. A body whose straight-line path (position and rate from sb_ident) never comes close
   to the field during the burst is dropped.
4. For each body that is left, JPL Horizons gives its position at the middle of every
   exposure of the burst, seen from SPHEREx itself (Horizons knows the spacecraft as
   -163182). Those inside the field are the crossings.

Every JPL answer is kept on disk as it arrives, so an interrupted or repeated lookup
does not ask JPL the same thing twice.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from astropy.time import Time

from . import astrometry, photometry, pipeline, spherex

SB_IDENT_URL = "https://ssd-api.jpl.nasa.gov/sb_ident.api"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
SPHEREX_HORIZONS_ID = "-163182"      # JPL Horizons' identifier for the SPHEREx spacecraft
OBSERVER = "SPHEREx spacecraft (JPL Horizons -163182)"
CREDIT = "NASA/JPL Solar System Dynamics (Small-Body Identification API and Horizons)"

VERSION = 3                         # part of the cache key: raise it when the answer changes
CACHE_DIR = spherex.CACHE / "smallbodies"
PICTURES_DIR = pipeline.FRAMES_DIR / "smallbodies"   # served at /frames/smallbodies/...

MAX_AT_ONCE = 2                      # requests to JPL in flight
TIMEOUT_S = 120                      # sb_ident takes 20 to 40 s
TRIES = 4
PAUSE_S = 8.0                        # first pause between tries; doubles
HORIZONS_TIMES_PER_CALL = 60         # exposure times in one Horizons request (they go in the URL)

CLUSTER_DAYS = 5.0                   # longest burst of exposures one sb_ident call stands for
CLUSTER_GAP_DAYS = 0.75              # a longer pause between exposures starts a new burst
MAX_RATE_DEG_DAY = 0.4               # bodies faster than this across the sky can be missed (see LIMITS)
VMAG_LIMIT = 21.0                    # predicted visual magnitude: fainter bodies are not looked for
PRUNE_MARGIN_DEG = 0.1               # slack on the straight-line path used to drop sb_ident candidates

SEEN_SIGMA = 5.0                     # a source at least this strong is "seen"
POSSIBLE_SIGMA = 3.0                 # between this and SEEN_SIGMA: "possible, not secure"
STAR_NEAR_ARCSEC = 12.0              # a Gaia star this close to the position could be what was measured
STAR_G_LIMIT = 17.0
PICTURE_ARCSEC = 120.0               # width of the single-exposure picture
LIMITS = (
    "Predictions only come from JPL's catalogue of known bodies. A body faster than "
    f"{MAX_RATE_DEG_DAY} degrees a day across the sky, fainter than magnitude {VMAG_LIMIT:g}, or not in the catalogue "
    "is not listed. The list says nothing about unknown objects."
)

_gate = threading.Semaphore(MAX_AT_ONCE)
_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-change-viewer (hackathon project)"


class JplError(spherex.ArchiveError):
    """JPL's small-body services could not be reached or returned something unusable."""


# --- talking to JPL ---------------------------------------------------------------------------------------------

def _jpl_get(url: str, params: dict[str, str]) -> str:
    """One JPL answer, from disk if it has been asked before, otherwise from JPL (with retries)."""
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:20]
    path = CACHE_DIR / "jpl" / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["text"]
    err = "no attempt made"
    for attempt in range(TRIES):
        with _gate:
            try:
                r = _session.get(url, params=params, timeout=TIMEOUT_S)
                if r.status_code == 200:
                    spherex.write_json(path, {"url": url, "params": params, "text": r.text})
                    return r.text
                err = f"HTTP {r.status_code}"
                if r.status_code in (400, 404):
                    break
            except requests.RequestException as e:
                err = type(e).__name__
        time.sleep(PAUSE_S * 2 ** attempt)
    raise JplError(f"{err} from {url}")


def _parse_ra(text: str) -> float:
    h, m, s = (float(x) for x in text.split(":"))
    return 15.0 * (h + m / 60.0 + s / 3600.0)


def _parse_dec(text: str) -> float:
    m = re.match(r"^([+-])(\d+) (\d+)'([\d.]+)\"$", text.strip())
    if m is None:
        raise ValueError(f"cannot read declination {text!r}")
    value = int(m.group(2)) + int(m.group(3)) / 60.0 + float(m.group(4)) / 3600.0
    return -value if m.group(1) == "-" else value


def _hms(deg: float) -> str:
    """Right ascension in the hh-mm-ss form sb_ident asks for."""
    total = (deg % 360.0) / 15.0
    h = int(total)
    m = int((total - h) * 60.0)
    return f"{h:02d}-{m:02d}-{(total - h - m / 60.0) * 3600.0:05.2f}"


def _dms(deg: float) -> str:
    """Declination in the dd-mm-ss form sb_ident asks for (M for a minus sign)."""
    sign = "M" if deg < 0 else ""
    a = abs(deg)
    d = int(a)
    m = int((a - d) * 60.0)
    return f"{sign}{d:02d}-{m:02d}-{(a - d - m / 60.0) * 3600.0:05.2f}"


def identify(mjd: float, ra: float, dec: float, half_width: float) -> list[dict]:
    """Known bodies in a box around (ra, dec) at time mjd, as the geocentre sees them (sb_ident, numerical orbits).

    half_width is in degrees on the sky; the right-ascension limit is widened by 1 / cos(dec)
    because sb_ident counts it in degrees of right ascension.
    """
    ra_half = min(half_width / max(np.cos(np.radians(dec)), 0.05), 90.0)
    params = {
        "mpc-code": "500", "obs-time": f"{Time(mjd, format='mjd').jd:.6f}",
        "fov-ra-center": _hms(ra), "fov-dec-center": _dms(dec),
        "fov-ra-hwidth": f"{ra_half:.4f}", "fov-dec-hwidth": f"{half_width:.4f}",
        "vmag-lim": f"{VMAG_LIMIT:g}", "mag-required": "true", "two-pass": "true", "suppress-first-pass": "true",
    }
    try:
        reply = json.loads(_jpl_get(SB_IDENT_URL, params))
    except json.JSONDecodeError as e:
        raise JplError("the small-body identification service sent something that is not JSON") from e
    if "data_second_pass" not in reply:
        if reply.get("warning") == "no matching records" or reply.get("n_second_pass") == 0:
            return []
        raise JplError(f"the small-body identification service answered without a list: {str(reply)[:200]}")
    columns = [c.split(" (")[0] for c in reply["fields_second"]]
    out = []
    for row in reply["data_second_pass"]:
        rec = dict(zip(columns, row, strict=True))
        out.append({
            "name": rec["Object name"], "ra": _parse_ra(rec["Astrometric RA"]),
            "dec": _parse_dec(rec["Astrometric Dec"]), "vmag": float(rec["Visual magnitude"]),
            "rate_ra_arcsec_h": float(rec["RA rate"]), "rate_dec_arcsec_h": float(rec["Dec rate"]),
        })
    return out


# --- naming -----------------------------------------------------------------------------------------------------

_COMET = re.compile(r"^(?:\d+[PCDI](?:-[A-Z]+)?|[PCDXAI])/")
_COMET_ID = re.compile(r"^(\d+[PCDI](?:-[A-Z]+)?(?=/)|[PCDXAI]/\d{4} [A-Z]+\d*)")
_PROVISIONAL = re.compile(r"^\(?(\d{4} [A-Z]{1,2}\d*)\)?$")


def kind_of(name: str) -> str:
    """"comet" or "asteroid", from the way the Minor Planet Center writes the name."""
    return "comet" if _COMET.match(name.strip().lstrip("(")) else "asteroid"


def split_name(name: str) -> tuple[str, str | None]:
    """(what to show, designation) from sb_ident's "433 Eros (A898 PA)", "(2000 SW60)" or "C/2025 R2 (SWAN)".

    The designation is the provisional one in brackets for a named or numbered asteroid;
    for a comet the name is the designation.
    """
    name = name.strip()
    m = re.match(r"^(\S.*?) \((.+)\)$", name)
    if m and kind_of(name) == "asteroid":
        return m.group(1), m.group(2)
    if name.startswith("(") and name.endswith(")"):
        return name[1:-1], None
    return name, None


def horizons_command(name: str) -> str:
    """The COMMAND Horizons needs to pick exactly this body."""
    name = name.strip()
    if kind_of(name) == "comet":
        m = _COMET_ID.match(name)
        return f"DES={m.group(1) if m else name};CAP"      # CAP: the apparition nearest in time
    m = _PROVISIONAL.match(name)
    if m:                                  # an unnumbered asteroid: "2024 YR4"
        return f"DES={m.group(1)};"
    m = re.match(r"^(\d+) ", name)         # a numbered one: "433 Eros (A898 PA)", "32455 (2000 SW60)"
    if m:
        return f"{m.group(1)};"
    return f"DES={name.strip('()')};"


def ephemeris(name: str, mjds: list[float]) -> list[dict]:
    """Where JPL Horizons puts a body at each time (UTC, MJD), as SPHEREx sees it.

    Returns one dict per time: ra, dec (degrees, astrometric ICRF), vmag (None when Horizons
    gives no magnitude), rate (arcsec/hour, on the sky, including the spacecraft's own motion).
    """
    out: list[dict] = []
    for start in range(0, len(mjds), HORIZONS_TIMES_PER_CALL):
        chunk = mjds[start:start + HORIZONS_TIMES_PER_CALL]
        params = {
            "format": "json", "COMMAND": f"'{horizons_command(name)}'", "CENTER": f"'@{SPHEREX_HORIZONS_ID}'",
            "EPHEM_TYPE": "OBSERVER", "TLIST": " ".join(f"'{m + 2400000.5:.6f}'" for m in chunk),
            "QUANTITIES": "'1,3,9'", "ANG_FORMAT": "DEG", "CSV_FORMAT": "YES", "OBJ_DATA": "NO",
        }
        try:
            text = json.loads(_jpl_get(HORIZONS_URL, params)).get("result") or ""
        except json.JSONDecodeError as e:
            raise JplError("Horizons sent something that is not JSON") from e
        if "$$SOE" not in text:
            raise JplError(f"Horizons could not give a position for {name}: {text.strip()[:160]!r}")
        header = [h.strip() for h in text.split("$$SOE")[0].strip().splitlines()[-2].split(",")]
        rows = [r for r in text.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines() if r.strip()]
        if len(rows) != len(chunk):
            raise JplError(f"Horizons gave {len(rows)} positions for {len(chunk)} times for {name}")
        i_ra, i_dec = header.index("R.A._(ICRF)"), header.index("DEC_(ICRF)")
        i_rate, i_rate_dec = header.index("dRA*cosD"), header.index("d(DEC)/dt")
        # APmag for an asteroid; for a comet the total magnitude, T-mag.
        i_mag = next((header.index(h) for h in ("APmag", "T-mag") if h in header), -1)
        for row in rows:
            f = [x.strip() for x in row.split(",")]
            try:
                vmag: float | None = float(f[i_mag]) if i_mag >= 0 else None
            except ValueError:
                vmag = None
            out.append({"ra": float(f[i_ra]), "dec": float(f[i_dec]), "vmag": vmag,
                        "rate": float(np.hypot(float(f[i_rate]), float(f[i_rate_dec])))})
    return out


# --- finding the crossings --------------------------------------------------------------------------------------

def exposure_mid_mjd(exp: dict) -> float:
    """Middle of the exposure. SPHEREx's own header MJD-AVG is 0.7 s later than this."""
    return exp["mjd"] + exp["exptime"] / 2.0 / 86400.0


def clusters(mids: list[float]) -> list[list[int]]:
    """Indexes of exposures (times sorted) grouped into bursts."""
    groups: list[list[int]] = []
    for i, t in enumerate(mids):
        if groups and t - mids[groups[-1][-1]] <= CLUSTER_GAP_DAYS and t - mids[groups[-1][0]] <= CLUSTER_DAYS:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def _separation_deg(ra1: float, dec1: float, ra2: np.ndarray | float, dec2: np.ndarray | float) -> np.ndarray:
    d_ra = (np.asarray(ra2) - ra1 + 180.0) % 360.0 - 180.0
    return np.hypot(d_ra * np.cos(np.radians(dec1)), np.asarray(dec2) - dec1)


def could_reach_field(cand: dict, t0: float, times: list[float], ra: float, dec: float, reach_deg: float) -> bool:
    """Does the straight-line path of an sb_ident candidate come within reach_deg of the field centre?"""
    dt_h = (np.asarray(times) - t0) * 24.0
    c = np.cos(np.radians(cand["dec"]))
    ras = cand["ra"] + cand["rate_ra_arcsec_h"] * dt_h / 3600.0 / max(c, 0.05)
    decs = cand["dec"] + cand["rate_dec_arcsec_h"] * dt_h / 3600.0
    return bool((_separation_deg(ra, dec, ras, decs) <= reach_deg).any())


def find_crossings(exposures: list[dict], ra: float, dec: float, fov: float,
                   progress=None) -> tuple[list[dict], list[str]]:
    """Every known body predicted inside the field at the middle of any of these exposures.

    `exposures` are SIA rows (one detector). Returns (crossings, problems): a crossing is
    {name, designation, kind, exposure index, ra, dec, vmag, rate} and `problems` lists
    each body or burst JPL could not answer for, so the result can say it is incomplete.
    """
    grid, n = pipeline.make_grid(ra, dec, fov)
    mids = [exposure_mid_mjd(e) for e in exposures]
    crossings: list[dict] = []
    problems: list[str] = []
    bursts = clusters(mids)
    reach = fov / 2.0 * 1.5 + PRUNE_MARGIN_DEG

    def ask(burst: list[int]) -> tuple[float, list[float], list[dict] | str]:
        times = [mids[i] for i in burst]
        t0 = (min(times) + max(times)) / 2.0
        half_width = fov / 2.0 * 1.5 + PRUNE_MARGIN_DEG + MAX_RATE_DEG_DAY * (max(times) - min(times)) / 2.0
        try:
            return t0, times, identify(t0, ra, dec, half_width)
        except JplError as e:
            return t0, times, f"{Time(t0, format='mjd').iso[:10]}: {e}"

    # The bursts are independent and each call is slow, so MAX_AT_ONCE of them go at once.
    with ThreadPoolExecutor(MAX_AT_ONCE) as pool:
        for done, (burst, (t0, times, found)) in enumerate(zip(bursts, pool.map(ask, bursts), strict=True), 1):
            if isinstance(found, str):
                problems.append(found)
                continue
            for cand in found:
                if not could_reach_field(cand, t0, times, ra, dec, reach):
                    continue
                try:
                    eph = ephemeris(cand["name"], times)
                except JplError as e:
                    problems.append(str(e))
                    continue
                for i, pos in zip(burst, eph, strict=True):
                    px, py = grid.all_world2pix(pos["ra"], pos["dec"], 0)
                    if -0.5 <= float(px) < n - 0.5 and -0.5 <= float(py) < n - 0.5:
                        shown, designation = split_name(cand["name"])
                        crossings.append({"name": shown, "designation": designation, "sb_name": cand["name"],
                                          "kind": kind_of(cand["name"]), "exposure": i, **pos,
                                          # a comet's T-mag in Horizons often disagrees with sb_ident's total magnitude
                                          "vmag": cand["vmag"] if kind_of(cand["name"]) == "comet"
                                          or pos["vmag"] is None else pos["vmag"]})
            if progress:
                progress(done, len(bursts))
    if bursts and len(problems) >= len(bursts) and not crossings:
        raise JplError(f"every request to JPL failed (first: {problems[0]})")   # nothing to show, so say it plainly
    crossings.sort(key=lambda c: (mids[c["exposure"]], c["name"]))
    return crossings, problems


# --- measuring what SPHEREx recorded ----------------------------------------------------------------------------

LOCAL_RING_ARCSEC = 60.0             # radius of the ring of nearby places that shows the real scatter
LOCAL_RING_POINTS = 8


def _measure(path: Path, ra: float, dec: float) -> dict:
    """Light at a predicted position in one exposure, against the noise around it.

    `sigma` is the measured flux over its statistical error (photometry.measure: the exposure's own variance
    and the scatter of the sky ring). `local_sigma` is the same flux over the scatter of the same measurement
    at LOCAL_RING_POINTS places on a ring LOCAL_RING_ARCSEC away, which includes whatever else is round about.
    """
    point = photometry.measure(path, ra, dec)
    flux, err = point.get("flux_mjy"), point.get("flux_err_stat_mjy")
    out = {"status": point["status"], "flux_mjy": flux, "flux_err_mjy": err, "sigma": None,
           "local_noise_mjy": None, "local_sigma": None,
           "wavelength_um": point.get("wavelength_um"), "flags": point.get("flags", [])}
    if point["status"] != "ok" or flux is None or not err:
        return out
    out["sigma"] = round(float(flux) / float(err), 2)
    ring = []
    for k in range(LOCAL_RING_POINTS):
        angle = 2.0 * np.pi * k / LOCAL_RING_POINTS
        d_dec = LOCAL_RING_ARCSEC / 3600.0 * np.sin(angle)
        d_ra = LOCAL_RING_ARCSEC / 3600.0 * np.cos(angle) / max(np.cos(np.radians(dec)), 0.05)
        other = photometry.measure(path, ra + d_ra, dec + d_dec)
        if other["status"] == "ok" and other.get("flux_mjy") is not None:
            ring.append(float(other["flux_mjy"]))
    if len(ring) >= 5:
        # median absolute deviation: one star on the ring does not count
        noise = 1.4826 * float(np.median(np.abs(np.asarray(ring) - np.median(ring))))
        if noise > 0:
            out["local_noise_mjy"] = round(noise, 4)
            out["local_sigma"] = round(float(flux) / noise, 2)
    return out


def verdict(m: dict) -> tuple[str, str]:
    """("seen" | "possible" | "not_seen" | "unmeasurable", the sentence a visitor reads)."""
    sigma = m["sigma"]
    if sigma is None:
        reasons = {"off_image": "the predicted place is too near the edge of this exposure's image to measure",
                   "no_sky": "there are too few clean pixels around the place to measure the background",
                   "no_data": "this exposure has no usable data at the place",
                   "saturated": "the pixels there are saturated",
                   "flagged": "a pixel at the place is flagged as bad in this exposure"}
        return "unmeasurable", f"Not measured: {reasons.get(m['status'], 'the place could not be measured')}."
    if sigma >= SEEN_SIGMA:
        return "seen", f"A source is seen here at {sigma:.0f} sigma." if sigma >= 10 else \
            f"A source is seen here at {sigma:.1f} sigma."
    if sigma >= POSSIBLE_SIGMA:
        return "possible", f"A faint source may be here ({sigma:.1f} sigma), not strong enough to be sure."
    return "not_seen", (f"Nothing is seen here ({sigma:.1f} sigma): the body is too faint for this exposure, "
                        "or its prediction is off.")


def _near_star(cone: list[dict], ra: float, dec: float, mjd: float) -> dict | None:
    """The closest Gaia star, on the exposure's date, within STAR_NEAR_ARCSEC of the place (or None)."""
    if not cone:
        return None
    sra, sdec = astrometry.positions_at(cone, mjd)
    sep = _separation_deg(ra, dec, sra, sdec) * 3600.0
    k = int(np.argmin(sep))
    if sep[k] > STAR_NEAR_ARCSEC:
        return None
    return {"source_id": cone[k]["source_id"], "gmag": cone[k].get("gmag"), "distance_arcsec": round(float(sep[k]), 1)}


def picture(path: Path, ra: float, dec: float, out_file: Path) -> None:
    """PNG of one exposure, PICTURE_ARCSEC across, north up, centred on (ra, dec), with the pipeline's own
    reprojection and stretch.

    The stretch is set from a patch five times wider, so the sky around the body decides what counts as faint.
    """
    wide_n = int(round(PICTURE_ARCSEC * 5 / pipeline.GRID_ARCSEC))
    wide, wn = pipeline.make_grid(ra, dec, wide_n * pipeline.GRID_ARCSEC / 3600.0)
    small, n = pipeline.make_grid(ra, dec, PICTURE_ARCSEC / 3600.0)
    item_wide = pipeline.prepare_cutout(path, wide, wn, ra, dec)
    item = pipeline.prepare_cutout(path, small, n, ra, dec)
    if item is None or item_wide is None:
        raise ValueError("the exposure has no usable pixels here")
    lim = pipeline.stretch_limits([item_wide["data"]])
    pipeline.to_png({"image": item["data"], "saturated": item["saturated"]}, lim, out_file)


OTHER_EXPOSURES = 12                 # exposures of other days measured at the same place
OTHER_MIN_DAYS = 1.0                 # "other days": a body is long gone from a 0.1 degree field after this
MIN_OTHERS = 3                       # fewer measurements than this cannot say a source is fixed


def _elsewhere(exposures: list[dict], index: int, view_ra: float, view_dec: float, cutout_deg: float,
               ra: float, dec: float) -> dict:
    """Measure the same sky place in up to OTHER_EXPOSURES exposures taken on other days."""
    here = exposures[index]["mjd"]
    far = [e for e in exposures if abs(e["mjd"] - here) > OTHER_MIN_DAYS]
    step = max(len(far) // OTHER_EXPOSURES, 1)
    fluxes: list[float] = []
    sigmas: list[float] = []
    for e in far[::step][:OTHER_EXPOSURES]:
        try:
            m = photometry.measure(spherex.fetch_cutout(e, view_ra, view_dec, cutout_deg), ra, dec)
        except Exception:  # noqa: BLE001 - an exposure that cannot be had or measured is left out
            continue
        if m["status"] == "ok" and m.get("flux_mjy") is not None and m.get("flux_err_stat_mjy"):
            fluxes.append(float(m["flux_mjy"]))
            sigmas.append(float(m["flux_mjy"]) / float(m["flux_err_stat_mjy"]))
    return {"n_measured": len(fluxes), "n_with_source": sum(s >= POSSIBLE_SIGMA for s in sigmas),
            "median_flux_mjy": round(float(np.median(fluxes)), 4) if fluxes else None}


def fixed_source(flux: float | None, others: dict) -> bool:
    """Is what was measured here a fixed source: one that most exposures of other days show at this place too?"""
    return bool(flux and others["n_measured"] >= MIN_OTHERS and others["n_with_source"] * 2 > others["n_measured"])


def describe(exposures: list[dict], crossings: list[dict], ra: float, dec: float, fov: float, detector: int,
             key: str) -> list[dict]:
    """Add to each crossing what the view needs: exposure, visit, place in the frame, measurement, picture."""
    grid, n = pipeline.make_grid(ra, dec, fov)
    visit_of = pipeline.assign_epochs(spherex.find_exposures(ra, dec))
    visit_by_obs = {e["obs_id"]: v + 1 for e, v in zip(spherex.find_exposures(ra, dec), visit_of, strict=True)}
    cutout_deg = round(fov * 1.5, 4)
    try:
        cone = astrometry.gaia_cone(ra, dec, fov * 0.75 + 0.06, STAR_G_LIMIT, tries=3, timeout=30)
    except spherex.ArchiveError:
        cone = []
    out = []
    for number, c in enumerate(crossings, 1):
        exp = exposures[c["exposure"]]
        mid = exposure_mid_mjd(exp)
        px, py = grid.all_world2pix(c["ra"], c["dec"], 0)
        item = {
            "id": f"{number:03d}", "name": c["name"], "designation": c["designation"], "kind": c["kind"],
            "exposure": {"obs_id": exp["obs_id"], "detector": exp["detector"], "mjd": round(mid, 6),
                         "time": Time(mid, format="mjd").isot[:19] + "Z", "visit": visit_by_obs.get(exp["obs_id"]),
                         "wavelength_um": [round(exp["wave_min"], 3), round(exp["wave_max"], 3)]},
            "predicted": {"ra": round(c["ra"], 7), "dec": round(c["dec"], 7),
                          "x": round(float(px), 2), "y": round(n - 1 - float(py), 2),
                          "observer": OBSERVER},
            "vmag": None if c["vmag"] is None else round(c["vmag"], 1),
            "rate_arcsec_per_hour": round(c["rate"], 1),
            "measurement": None, "verdict": None, "summary": None, "nearby_gaia_star": None, "picture": None,
        }
        try:
            path = spherex.fetch_cutout(exp, ra, dec, cutout_deg)
        except Exception as e:  # noqa: BLE001 - say why this one could not be measured, keep the rest
            item["summary"] = f"The exposure could not be fetched, so nothing was measured: {type(e).__name__}."
            item["verdict"] = "unmeasurable"
            out.append(item)
            continue
        m = _measure(path, c["ra"], c["dec"])
        item["measurement"] = m
        item["verdict"], item["summary"] = verdict(m)
        if item["verdict"] in ("seen", "possible"):
            # A moving body is only at this place in this exposure. A source that is here in the others too is not it.
            others = _elsewhere(exposures, c["exposure"], ra, dec, cutout_deg, c["ra"], c["dec"])
            item["elsewhere"] = others
            if fixed_source(m["flux_mjy"], others):
                item["verdict"] = "fixed_source"
                item["summary"] = (f"A source is here ({m['sigma']:.0f} sigma), but it is also here in "
                                   f"{others['n_with_source']} of {others['n_measured']} exposures of other days, "
                                   "so it is a fixed source (a star or galaxy), not this body.")
        item["nearby_gaia_star"] = _near_star(cone, c["ra"], c["dec"], mid)
        star = item["nearby_gaia_star"]
        if star and item["verdict"] in ("seen", "possible"):
            item["summary"] += (f" A Gaia star (G = {star['gmag']:.1f}) lies {star['distance_arcsec']:.0f} arcsec from "
                                "the predicted place and could be what was measured.")
        try:
            file = PICTURES_DIR / key / f"{item['id']}.png"
            file.parent.mkdir(parents=True, exist_ok=True)
            picture(path, c["ra"], c["dec"], file)
            item["picture"] = f"/frames/smallbodies/{key}/{item['id']}.png"
        except Exception as e:  # noqa: BLE001 - the list is still worth returning without its picture
            item["picture_error"] = f"{type(e).__name__}: {e}"
        out.append(item)
    return out


def known_bodies(ra: float, dec: float, fov: float = 0.1, detector: int = 5, progress=None) -> dict:
    """Known asteroids and comets predicted inside the field of a view at the time of one of its exposures.

    Takes the position, field of view and detector of an /api/frames request. Nothing is
    returned for a body JPL does not know, and every crossing is a prediction until its
    `verdict` says what the exposure itself shows.
    """
    if not 0.02 < fov <= 0.5:
        raise ValueError("fov must be above 0.02 and at most 0.5 degrees")
    if not 1 <= detector <= 6:
        raise ValueError("detector must be 1 to 6")
    all_exposures = spherex.find_exposures(ra, dec)
    exposures = [e for e in all_exposures if e["detector"] == detector]
    last = exposures[-1]["mjd"] if exposures else 0
    key_text = f"v{VERSION},{ra:.5f},{dec:.5f},{fov:.4f},{detector},{len(exposures)},{last}"
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    result: dict = {
        "key": key, "ra": ra, "dec": dec, "fov": fov, "detector": detector, "n_exposures_checked": len(exposures),
        "observer": OBSERVER, "limits": LIMITS, "credit": CREDIT, "problems": [], "bodies": [],
        "observer_note": ("Positions are for the SPHEREx spacecraft's own position, from JPL Horizons. "
                          "Sky motion includes the spacecraft's orbital motion."),
        "wording": "Each position is a prediction; the 'verdict' of an entry is what its exposure itself shows.",
    }
    if not exposures:
        result["message"] = "SPHEREx has no public images of this position in this detector."
        return result
    crossings, problems = find_crossings(exposures, ra, dec, fov, progress)
    result["bodies"] = describe(exposures, crossings, ra, dec, fov, detector, key)
    result["problems"] = problems
    result["n_crossings"] = len(result["bodies"])
    if not problems:           # an incomplete answer is not kept: the next request tries the missing parts again
        spherex.write_json(cache_file, result, indent=1)
    return result

"""Name lookup (SIMBAD), Gaia DR3 lookups, and moving a catalogue position to a date."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import warnings

import astropy.units as u
import numpy as np
from astropy.coordinates import Distance, SkyCoord, get_body_barycentric
from astropy.io.votable import parse_single_table
from astropy.time import Time

from .spherex import CACHE, ArchiveError, http_get, write_json

GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
GAIA_EPOCH = 2016.0  # reference epoch of Gaia DR3 positions (Julian year)
# SIMBAD's TAP service. The CfA mirror is first because the Strasbourg original was
# answering every request with HTTP 404 "Page unavailable" on 2026-11-14.
SIMBAD_TAP = ("https://simbad.harvard.edu/simbad/sim-tap/sync",
              "https://simbad.cds.unistra.fr/simbad/sim-tap/sync")
SIMBAD_EPOCH = 2000.0   # SIMBAD positions are ICRS at epoch J2000
# Positions returned by resolve_name are for this fixed date, not "today": a fixed date
# gives the same coordinates on every call, so the cutout cache is hit every time.
RESOLVE_EPOCH = 2026.0
# Short names people use that SIMBAD does not list as identifiers.
ALIASES = {"wise 0855": "WISE J085510.83-071442.5", "w0855": "WISE J085510.83-071442.5",
           "barnards star": "Barnard's Star", "barnard star": "Barnard's Star"}


class NameNotFound(LookupError):
    """SIMBAD has no single object with this name."""


def _num(v) -> float | None:
    return None if v is None or np.ma.is_masked(v) or not np.isfinite(v) else float(v)


def gaia_cone(ra: float, dec: float, radius_deg: float, g_limit: float = 17.0, *,
              tries: int = 10, timeout: float = 90) -> list[dict]:
    """Gaia DR3 sources within radius_deg of (ra, dec), brightest first. Cached on disk.

    Positions are at epoch 2016.0. A fast star can be arcminutes from where it is
    today, so callers should search wider than the field they want to cover.
    `tries` and `timeout` only matter when the answer is not cached yet.
    """
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f},{radius_deg:.4f},{g_limit}".encode()).hexdigest()[:16]
    cache_file = CACHE / "queries" / f"gaia_{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    query = (
        "SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag "
        "FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {ra}, {dec}, {radius_deg})) AND phot_g_mean_mag < {g_limit} "
        "ORDER BY phot_g_mean_mag")
    raw = http_get(GAIA_TAP, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query},
                   tries=tries, timeout=timeout)
    sources = _gaia_rows(raw)
    write_json(cache_file, sources)
    return sources


def _gaia_rows(raw: bytes) -> list[dict]:
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    return [{"source_id": str(r["source_id"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
             "pmra": _num(r["pmra"]), "pmdec": _num(r["pmdec"]), "parallax": _num(r["parallax"]),
             "gmag": _num(r["phot_g_mean_mag"])} for r in table]


def gaia_source(source_id: str) -> dict | None:
    """One Gaia DR3 source by its identifier (position at epoch 2016.0), or None."""
    if not source_id.isdigit():
        raise ValueError("a Gaia source identifier is all digits")
    query = ("SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag, radial_velocity "
             f"FROM gaiadr3.gaia_source WHERE source_id = {source_id}")
    raw = http_get(GAIA_TAP, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query},
                   tries=4, timeout=40)
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    rows = _gaia_rows(raw)
    if not rows:
        return None
    return {**rows[0], "radial_velocity": _num(table[0]["radial_velocity"])}


def propagate(src: dict, epoch: float) -> tuple[float, float]:
    """Barycentric position of a source at a Julian year: rigorous space motion.

    Uses the radial velocity and distance when known. For Barnard's Star over ten
    years that differs from a straight-line proper motion by 0.06 arcsec (perspective
    acceleration); for almost everything else the two agree. No parallax offset.
    """
    if src.get("pmra") is None or src.get("pmdec") is None:
        return src["ra"], src["dec"]
    extra = {}
    if (src.get("parallax") or 0.0) > 0 and src.get("radial_velocity") is not None:
        extra = {"distance": Distance(parallax=src["parallax"] * u.mas),
                 "radial_velocity": src["radial_velocity"] * u.km / u.s}
    start = SkyCoord(ra=src["ra"] * u.deg, dec=src["dec"] * u.deg, pm_ra_cosdec=src["pmra"] * u.mas / u.yr,
                     pm_dec=src["pmdec"] * u.mas / u.yr, frame="icrs",
                     obstime=Time(src.get("ref_epoch") or GAIA_EPOCH, format="jyear"), **extra)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # erfa notes that no distance was given
        end = start.apply_space_motion(Time(epoch, format="jyear"))
    return float(end.ra.deg), float(end.dec.deg)


def position_at(src: dict, mjd: float, parallax: bool = True) -> tuple[float, float]:
    """Where a source appears at the given date: proper motion plus parallax.

    `src` holds ra, dec (degrees), pmra, pmdec (mas/yr, pmra already multiplied by
    cos dec), parallax (mas) and optionally ref_epoch, the Julian year its position is
    for (default 2016.0, as in Gaia DR3). The position must be the barycentric one,
    with no parallax offset in it.

    Linear proper motion from the reference epoch. That ignores perspective acceleration,
    which for Barnard's Star amounts to about 0.06 arcsec by 2026, a hundredth of a
    SPHEREx pixel. Parallax uses the Earth's barycentric position (SPHEREx is in low
    Earth orbit, so the difference is negligible).
    """
    ra, dec = src["ra"], src["dec"]
    t = Time(mjd, format="mjd")
    dt = t.jyear - (src.get("ref_epoch") or GAIA_EPOCH)
    d_ra = (src.get("pmra") or 0.0) * dt      # mas, already multiplied by cos(dec)
    d_dec = (src.get("pmdec") or 0.0) * dt
    plx = src.get("parallax") or 0.0
    if parallax and plx > 0:
        earth = get_body_barycentric("earth", t).xyz.to_value("au")
        a, d = np.radians(ra), np.radians(dec)
        d_ra += plx * (earth[0] * np.sin(a) - earth[1] * np.cos(a))
        d_dec += plx * (earth[0] * np.cos(a) * np.sin(d) + earth[1] * np.sin(a) * np.sin(d)
                        - earth[2] * np.cos(d))
    mas = 1.0 / 3.6e6
    return ra + d_ra * mas / np.cos(np.radians(dec)), dec + d_dec * mas


def _apparent(ra, dec, pmra, pmdec, plx, ref_epoch, t: Time, parallax: bool) -> tuple[np.ndarray, np.ndarray]:
    """The arithmetic of position_at() on arrays; the source fields and the dates broadcast."""
    dt = t.jyear - ref_epoch
    d_ra = pmra * dt
    d_dec = pmdec * dt
    if parallax:
        ex, ey, ez = get_body_barycentric("earth", t).xyz.to_value("au")
        a, d = np.radians(ra), np.radians(dec)
        d_ra = d_ra + plx * (ex * np.sin(a) - ey * np.cos(a))
        d_dec = d_dec + plx * (ex * np.cos(a) * np.sin(d) + ey * np.sin(a) * np.sin(d) - ez * np.cos(d))
    mas = 1.0 / 3.6e6
    return ra + d_ra * mas / np.cos(np.radians(dec)), dec + d_dec * mas


def _columns(sources: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """ra, dec, pmra, pmdec, parallax and reference epoch of many sources, as position_at() reads them."""
    def column(key: str, default: float) -> np.ndarray:
        return np.array([s.get(key) or default for s in sources], dtype=float)

    plx = column("parallax", 0.0)
    return (np.array([s["ra"] for s in sources], dtype=float), np.array([s["dec"] for s in sources], dtype=float),
            column("pmra", 0.0), column("pmdec", 0.0), np.where(plx > 0, plx, 0.0), column("ref_epoch", GAIA_EPOCH))


def positions_at(sources: list[dict], mjd: float, parallax: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """position_at() for many sources on one date: arrays of ra and dec, in the order given."""
    if not sources:
        return np.zeros(0), np.zeros(0)
    ra, dec, pmra, pmdec, plx, ref = _columns(sources)
    return _apparent(ra, dec, pmra, pmdec, plx, ref, Time(mjd, format="mjd"), parallax)


def path_of(src: dict, mjds, parallax: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """position_at() for one source on many dates: arrays of ra and dec, one per date."""
    ra, dec, pmra, pmdec, plx, ref = (c[0] for c in _columns([src]))
    return _apparent(ra, dec, pmra, pmdec, plx, ref, Time(np.atleast_1d(np.asarray(mjds, dtype=float)), format="mjd"),
                     parallax)


def stars_near(ra: float, dec: float, sources: list[dict], mjd: float, radius_arcsec: float, *,
               same_arcsec: float = 1.5, exclude_id: str | None = None) -> list[dict]:
    """Catalogue stars within radius_arcsec of (ra, dec) on the date, nearest first.

    Each is {source_id, gmag, distance_arcsec, east_arcsec, north_arcsec, index} (index
    into `sources`). A star closer than same_arcsec, or with the identifier exclude_id,
    is the object at (ra, dec) itself and is left out.
    """
    if not sources:
        return []
    sra, sdec = positions_at(sources, mjd)
    out = []
    for i, src in enumerate(sources):
        east, north = offset_arcsec(ra, dec, float(sra[i]), float(sdec[i]))
        distance = float(np.hypot(east, north))
        if distance > radius_arcsec or distance < same_arcsec or (exclude_id and src.get("source_id") == exclude_id):
            continue
        gmag = src.get("gmag")
        out.append({"source_id": src.get("source_id"), "gmag": round(gmag, 2) if gmag is not None else None,
                    "distance_arcsec": round(distance, 2),
                    "east_arcsec": round(east, 2), "north_arcsec": round(north, 2), "index": i})
    return sorted(out, key=lambda s: s["distance_arcsec"])


def offset_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> tuple[float, float]:
    """Small-angle offset of point 2 from point 1: (east, north) in arcseconds."""
    d_ra = ra2 - ra1
    if d_ra > 180.0:            # the short way round: the two points are either side of RA 0h
        d_ra -= 360.0
    elif d_ra < -180.0:
        d_ra += 360.0
    east = d_ra * np.cos(np.radians(0.5 * (dec1 + dec2))) * 3600.0
    north = (dec2 - dec1) * 3600.0
    return float(east), float(north)


def _simbad(adql: str) -> list[list]:
    """Run one ADQL query on SIMBAD and return its rows, trying each mirror in turn.

    A mirror that answers HTTP 400 has read the query and refused it: the name is not
    one it can look up. That is "not found", not "service down", even when the other
    mirror is down at the same moment.
    """
    last: Exception | None = None
    refused = False
    for url in SIMBAD_TAP:
        try:
            raw = http_get(url, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql},
                           tries=3, timeout=30)
            return json.loads(raw)["data"]
        except (ArchiveError, ValueError, KeyError) as e:
            refused = refused or str(e).startswith("HTTP 400")
            last = e
    if refused:
        raise NameNotFound("SIMBAD could not read this as an object name.")
    raise ArchiveError(f"SIMBAD did not answer ({last})")


# What people type and paste, in the plain characters SIMBAD's identifiers use.
_PLAIN = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "′": "'", "`": "'", "´": "'", "“": '"', "”": '"', "″": '"',
                        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-"})
# Greek letters as SIMBAD abbreviates them in star names ("* eps Ind B", "* alf Ori").
_GREEK = {"α": "alf", "β": "bet", "γ": "gam", "δ": "del", "ε": "eps", "ζ": "zet", "η": "eta", "θ": "tet",
          "ι": "iot", "κ": "kap", "λ": "lam", "μ": "mu", "ν": "nu", "ξ": "ksi", "ο": "omi", "π": "pi", "ρ": "rho",
          "σ": "sig", "ς": "sig", "τ": "tau", "υ": "ups", "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "ome"}
_SIMBAD_PREFIX = re.compile(r"^(NAME|V\*|EM\*|\*\*|\*)\s+")


def clean_name(name: str) -> str:
    """An object name as typed, reduced to plain characters: straight quotes, a hyphen
    for every kind of dash and minus sign, no accents, Greek letters as SIMBAD's
    three-letter abbreviations, single spaces, no invisible characters."""
    text = unicodedata.normalize("NFKC", name).translate(_PLAIN)
    text = "".join(" " if unicodedata.category(c) in ("Cc", "Cf") else c for c in text)   # tabs, zero-width space
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    text = "".join(f" {_GREEK[c.lower()]} " if c.lower() in _GREEK else c for c in text)
    return " ".join(text.split())


def _display_name(main_id: str) -> str:
    """SIMBAD's identifier without its catalogue prefix and doubled spaces: "NAME Barnard's
    star" becomes "Barnard's star", "* eps Ind B" "eps Ind B", "M  31" "M 31"."""
    return " ".join(_SIMBAD_PREFIX.sub("", main_id).split())


def _presented(result: dict) -> dict:
    """A resolve result as it is returned. Applied to cached answers too, so answers
    cached before these fields existed come back the same as new ones."""
    out = dict(result)
    out["display_name"] = _display_name(str(result.get("name") or ""))
    if not result.get("moved_to_epoch"):
        out["moved_since_2000_arcsec"] = None      # no motion known: "has not moved" would be a claim
    return out


_BASIC = ("SELECT DISTINCT b.oid, b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.otype, "
          "b.coo_bibcode, b.pm_bibcode FROM basic AS b JOIN ident AS i ON i.oidref = b.oid WHERE ")
# "WISE 0855-0714", "2MASS J0415-0935": a survey name with a shortened coordinate.
_SHORT_DESIGNATION = re.compile(r"^([A-Za-z0-9]+?)\s*J?(\d{4})([+-])(\d{4})$")


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _simbad_object(query: str) -> list:
    """The SIMBAD `basic` row for a name. Raises NameNotFound if there is not exactly one."""
    for candidate in dict.fromkeys([query, ALIASES.get(query.lower(), query)]):
        # SIMBAD normalises the name itself: "Epsilon Indi B" matches "* eps Ind B".
        rows = _simbad(_BASIC + f"i.id = {_quote(candidate)}")
        if rows:
            return rows[0]
    short = _SHORT_DESIGNATION.match(query)
    if short:
        survey, hhmm, sign, ddmm = short.groups()
        rows = _simbad(_BASIC + f"i.id LIKE {_quote(f'{survey.upper()}% J{hhmm}%{sign}{ddmm}%')}")
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            names = ", ".join(str(r[1]) for r in rows[:8])
            raise NameNotFound(f"'{query}' matches {len(rows)} objects in SIMBAD: {names}. Use the full name.")
    raise NameNotFound(f"SIMBAD does not know an object called '{query}'.")


def resolve_name(name: str) -> dict:
    """Object name to coordinates at RESOLVE_EPOCH (2026.0), with its motion when known.

    SIMBAD turns the name into an object. If SIMBAD lists a Gaia DR3 identifier for
    it, position and motion come from Gaia DR3 (epoch 2016.0); otherwise from SIMBAD
    itself (epoch 2000.0), which is how objects too faint for Gaia, such as
    WISE 0855-0714, get a motion. The position is then moved to 2026.0 with the proper
    motion (and the radial velocity, when Gaia has one). Parallax is returned but not
    applied: it shifts the object by at most `parallax` mas around this position over
    a year, and position_at() adds it for a given date.

    The name is cleaned first (clean_name), and the cache is keyed on the cleaned name,
    so "Barnard’s Star" with a curly apostrophe is the same lookup as "Barnard's Star".

    Raises NameNotFound if SIMBAD has no such object, ArchiveError if SIMBAD is down.
    """
    query = clean_name(name)
    if not query or len(query) > 80:
        raise NameNotFound("Give an object name of 1 to 80 characters.")
    if not (query.isascii() and query.isprintable()):
        # SIMBAD's identifiers are plain ASCII; its service refuses anything else.
        odd = "".join(sorted({c for c in query if not (c.isascii() and c.isprintable())}))
        raise NameNotFound(f"'{query}' has characters that object names do not use ({odd}).")
    key = hashlib.sha1(query.lower().encode()).hexdigest()[:16]
    cache_file = CACHE / "queries" / f"resolve_{key}.json"
    if cache_file.exists():
        return _presented(json.loads(cache_file.read_text()))

    oid, main_id, ra0, dec0, pmra, pmdec, plx, otype, coo_ref, pm_ref = _simbad_object(query)
    if ra0 is None or dec0 is None:
        raise NameNotFound(f"SIMBAD knows '{main_id}' but has no coordinates for it.")
    ra_2000, dec_2000 = float(ra0), float(dec0)
    simbad = {"ra": ra_2000, "dec": dec_2000, "pmra": _num(pmra), "pmdec": _num(pmdec),
              "parallax": _num(plx), "ref_epoch": SIMBAD_EPOCH}
    notes: list[str] = []
    src, source, gaia_id, complete = simbad, "SIMBAD", None, True

    ids = _simbad(f"SELECT id FROM ident WHERE oidref = {int(oid)} AND id LIKE 'Gaia DR3 %'")
    if ids:
        gaia_id = str(ids[0][0]).split()[-1]
        try:
            gaia = gaia_source(gaia_id)
            if gaia and gaia["pmra"] is not None and gaia["pmdec"] is not None:
                src, source = {**gaia, "ref_epoch": GAIA_EPOCH}, "Gaia DR3"
            else:
                notes.append("Gaia DR3 lists this object without a proper motion; SIMBAD values used.")
        except ArchiveError as e:
            complete = False   # do not cache: Gaia may answer next time
            notes.append(f"Gaia did not answer ({e}); SIMBAD values used.")
    else:
        notes.append("SIMBAD lists no Gaia DR3 identifier for this object; SIMBAD values used.")

    has_motion = src["pmra"] is not None and src["pmdec"] is not None
    if not has_motion:
        notes.append("No proper motion known: the position is the catalogue one, not moved to 2026.")
    ra, dec = propagate(src, RESOLVE_EPOCH)
    east, north = offset_arcsec(ra_2000, dec_2000, ra, dec)
    result = {
        "query": query, "name": str(main_id), "object_type": otype,
        "ra": round(float(ra) % 360.0, 6), "dec": round(float(dec), 6), "epoch": RESOLVE_EPOCH,
        "pmra": src["pmra"], "pmdec": src["pmdec"], "parallax": src["parallax"],
        "radial_velocity_km_s": src.get("radial_velocity"),
        "pm_unit": "mas/yr (pmra includes cos dec)", "parallax_unit": "mas",
        "moved_to_epoch": has_motion,
        "source": source, "gaia_source_id": gaia_id,
        "catalogue": {"ra": src["ra"], "dec": src["dec"], "epoch": src["ref_epoch"]},
        "j2000": {"ra": ra_2000, "dec": dec_2000},
        "moved_since_2000_arcsec": round(float(np.hypot(east, north)), 2),
        "references": {"simbad_position": coo_ref, "simbad_proper_motion": pm_ref},
        "notes": notes,
        "credit": "SIMBAD (CDS, Strasbourg); ESA Gaia DR3",
    }
    if complete:
        write_json(cache_file, result)
    return _presented(result)

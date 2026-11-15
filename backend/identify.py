"""What is known about the thing at a place on the sky: the "What is it?" card's lookup.

GET /api/identify?ra=&dec=&radius=&epoch= (backend/app.py) calls identify(). For a
position it returns

- the nearest Gaia DR3 source within `radius` arcsec at the date of the SPHEREx
  pictures (positions moved there with astrometry.propagate), with its parallax,
  proper motion, G magnitude, BP-RP colour and, where Gaia's astrophysical parameters
  give them, temperature, radius, luminosity and distance: every value with its error
  or range and the table and column it was read from;
- the nearest SIMBAD object within the radius: its main name, object type and
  spectral type, both turned into plain words by the tables below, and its number of
  references (how well studied it is); for an object Gaia does not list, SIMBAD's own
  parallax and proper motion and nothing more;
- every other catalogued source within 15 arcsec, with its brightness, because a
  SPHEREx pixel is 6.15 arcsec wide and the blur seen on the picture can hold several;
- `nothing_catalogued` true when neither catalogue lists anything within the radius,
  with the nearest thing they do list;
- a few values derived from the measured ones, each with its formula and its
  uncertainty carried through.

Nothing is filled in. A value a catalogue does not give is absent, and a service that
does not answer is named in `unreachable` while the rest of the answer stands.

Every catalogue answer is cached on disk under queries/identify_*.json, keyed by the
query text; a failed query is never cached. The column names were checked against the
services' own TAP_SCHEMA lists (saved in tests/data/identify/schema/).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import requests
from astropy.io.votable import parse_single_table

from . import astrometry, spherex

# --------------------------------------------------------------------------- settings

DEFAULT_RADIUS_ARCSEC = 4.0     # "the object at this place": catalogue entries this close
MAX_RADIUS_ARCSEC = 30.0
NEIGHBOUR_ARCSEC = 15.0         # the other sources listed around it
PIXEL_ARCSEC = 6.15             # one SPHEREx pixel
SAME_PLACE_ARCSEC = 1.5         # a SIMBAD object that names no Gaia source is taken as the Gaia source this close
MIN_PARALLAX_OVER_ERROR = 5.0   # a distance is 1 / parallax only when the parallax is this many times its error
# Catalogue positions are for 2016.0 (Gaia) and 2000.0 (SIMBAD), so a fast star can be far
# from where it is on the SPHEREx pictures. Each cone search therefore takes everything
# moving slower than SLOW_ARCSEC_YR within the reach plus that drift, and only the fast
# movers out to the drift of the fastest star: Barnard's Star, 10.39 arcsec/yr in Gaia DR3,
# has the largest proper motion of any star known.
SLOW_ARCSEC_YR = 2.0
FASTEST_ARCSEC_YR = 10.5

GAIA_TAPS = (("ESA Gaia archive", astrometry.GAIA_TAP),
             # The ESA archive timed out on every connection on 2026-11-15; the Astronomisches
             # Rechen-Institut (Heidelberg) serves the same gaiadr3 tables under the same names.
             ("ARI Heidelberg Gaia mirror", "https://gaia.ari.uni-heidelberg.de/tap/sync"))
SIMBAD_TAPS = (("SIMBAD (CfA mirror)", astrometry.SIMBAD_TAP[0]), ("SIMBAD (Strasbourg)", astrometry.SIMBAD_TAP[1]))
SERVICE_NAMES = {"gaia": "Gaia DR3", "simbad": "SIMBAD"}
RETRY_AFTER_S = 600.0           # a mirror that failed is skipped for this long

# Physical constants for the derived values.
# 1 au per Julian year in km/s: 149,597,870.7 km / (365.25 x 86,400 s). A proper motion of
# mu arcsec/yr at d parsecs is a speed across the line of sight of 4.74047 x mu x d km/s.
KM_S_PER_AU_PER_YR = 149_597_870.7 / 31_557_600.0
# Light-years in a parsec: (648,000 / pi) au x 149,597,870,700 m, over c x 1 Julian year
# (299,792,458 m/s x 31,557,600 s), both by IAU definition.
LY_PER_PC = (648_000.0 / math.pi) * 149_597_870_700.0 / (299_792_458.0 * 31_557_600.0)
# Magnitudes from a flux: m = -2.5 log10(F) + const, so an error of dF/F in flux is
# 2.5 / ln(10) x dF/F in magnitude.
MAG_PER_RELATIVE_FLUX = 2.5 / math.log(10.0)

GAIA_SOURCE = "gaiadr3.gaia_source"
GAIA_AP = "gaiadr3.astrophysical_parameters"
GAIA_SOURCE_COLUMNS = (
    "source_id", "ref_epoch", "ra", "dec", "parallax", "parallax_error", "pm", "pmra", "pmra_error", "pmdec",
    "pmdec_error", "pmra_pmdec_corr", "parallax_pmra_corr", "parallax_pmdec_corr", "radial_velocity",
    "radial_velocity_error", "phot_g_mean_mag", "phot_g_mean_flux_over_error", "bp_rp",
    "phot_bp_mean_flux_over_error", "phot_rp_mean_flux_over_error", "ruwe", "phot_variable_flag")
GAIA_AP_COLUMNS = (
    "teff_gspphot", "teff_gspphot_lower", "teff_gspphot_upper", "teff_espucd", "teff_espucd_uncertainty",
    "teff_esphs", "teff_esphs_uncertainty", "teff_gspspec", "teff_gspspec_lower", "teff_gspspec_upper",
    "radius_flame", "radius_flame_lower", "radius_flame_upper", "radius_gspphot", "radius_gspphot_lower",
    "radius_gspphot_upper", "lum_flame", "lum_flame_lower", "lum_flame_upper", "distance_gspphot",
    "distance_gspphot_lower", "distance_gspphot_upper")
# Not asked for: spectraltype_esphs, Gaia's one-letter class from the BP/RP spectra. It gives
# "B" for RW Aur B (a K2 T Tauri star) and "F" for a 4,800 K star, so it cannot be put into
# plain words without saying something false.
SIMBAD_BASIC_COLUMNS = (
    "oid", "main_id", "ra", "dec", "pmra", "pmdec", "pm_err_maj", "pm_err_min", "pm_err_angle", "pm_bibcode",
    "plx_value", "plx_err", "plx_bibcode", "otype", "sp_type", "sp_bibcode", "nbref")

# Which Gaia temperature and radius the picture is drawn from: the first that exists, in
# this order. GSP-Phot (from the BP/RP spectra) covers the most stars and is the one FLAME's
# radius and luminosity are built on; ESP-UCD is Gaia's own for ultracool dwarfs, ESP-HS for
# hot stars; GSP-Spec (RVS spectra) is last because it fails for cool dwarfs (4,250 K for
# Barnard's Star, against 3,100 K from GSP-Phot and 3,083 to 3,530 K in SIMBAD's list).
TEMPERATURE_ORDER = ("teff_gspphot", "teff_espucd", "teff_esphs", "teff_gspspec")
RADIUS_ORDER = ("radius_flame", "radius_gspphot")


class _Unanswered(spherex.ArchiveError):
    """No mirror of a service answered."""


# --------------------------------------------------------------------------- talking to the services

_session = requests.Session()
_session.headers["User-Agent"] = "catalogue-client/1.0"     # generic: no person or project named
_down: dict[str, float] = {}
_down_lock = threading.Lock()


def _get(url: str, params: dict[str, str], *, tries: int = 2, timeout: tuple[float, float] = (6.0, 60.0)) -> bytes:
    """GET with retries and backoff; raises spherex.ArchiveError when it never works."""
    err = "no attempt made"
    for attempt in range(tries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.content
            err = f"HTTP {r.status_code}"
            if r.status_code in (400, 404):
                break
        except requests.RequestException as e:
            err = type(e).__name__
        if attempt + 1 < tries:
            time.sleep(min(0.8 * 1.6 ** attempt, 6.0))
    raise spherex.ArchiveError(f"{err} from {url}")


def _clean(value: Any) -> Any:
    """A table cell as plain JSON: None for masked or not-a-number, Python numbers and text."""
    if value is None or np.ma.is_masked(value):
        return None
    if isinstance(value, (bytes, np.bytes_)):
        value = value.decode()
    if isinstance(value, (str, np.str_)):
        text = str(value).strip()
        return text or None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    out = float(value)
    return out if math.isfinite(out) else None


def _votable_rows(raw: bytes) -> list[dict[str, Any]]:
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)
    return [{name: _clean(row[name]) for name in table.colnames} for row in table]


def _json_rows(raw: bytes) -> list[dict[str, Any]]:
    answer = json.loads(raw)
    names = [m["name"] for m in answer["metadata"]]
    return [{n: _clean(v) for n, v in zip(names, row, strict=True)} for row in answer["data"]]


def _cache_file(kind: str, adql: str) -> Path:
    key = hashlib.sha1(f"{kind}\n{adql}".encode()).hexdigest()[:16]
    return spherex.CACHE / "queries" / f"identify_{kind}_{key}.json"


def _tap(kind: str, adql: str) -> tuple[list[dict[str, Any]], str]:
    """Rows of one ADQL query on Gaia ("gaia") or SIMBAD ("simbad"), and which mirror gave them.

    Read from the cache when it is there; otherwise each mirror is asked in turn (one
    that failed in the last ten minutes is skipped) and the answer is cached.
    """
    cache_file = _cache_file(kind, adql)
    if cache_file.exists():
        saved = json.loads(cache_file.read_text())
        return saved["rows"], saved["via"]
    mirrors, fmt, parse = ((GAIA_TAPS, "votable", _votable_rows) if kind == "gaia"
                           else (SIMBAD_TAPS, "json", _json_rows))
    errors: list[str] = []
    for name, url in mirrors:
        with _down_lock:
            if time.time() - _down.get(url, 0.0) < RETRY_AFTER_S:
                errors.append(f"{name}: did not answer a few minutes ago")
                continue
        try:
            raw = _get(url, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": fmt, "QUERY": adql})
            rows = parse(raw)
        except (spherex.ArchiveError, ValueError, KeyError) as e:   # ValueError: an error page, not a table
            with _down_lock:
                _down[url] = time.time()
            errors.append(f"{name}: {e}"[:200])
            continue
        spherex.write_json(cache_file, {"service": SERVICE_NAMES[kind], "via": name, "query": adql,
                                        "asked": time.strftime("%Y-%m-%d"), "rows": rows})
        return rows, name
    raise _Unanswered(f"{SERVICE_NAMES[kind]} did not answer ({'; '.join(errors)})")


# --------------------------------------------------------------------------- the queries

def _circle(ra: float, dec: float, radius_arcsec: float, ra_col: str, dec_col: str) -> str:
    return (f"1 = CONTAINS(POINT('ICRS', {ra_col}, {dec_col}), "
            f"CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_arcsec / 3600.0:.6f}))")


def _reaches(reach_arcsec: float, years: float) -> tuple[float, float]:
    """Search radii (arcsec) for slow and for fast movers whose catalogue position is `years` away."""
    years = abs(years)
    return reach_arcsec + years * SLOW_ARCSEC_YR + 1.0, reach_arcsec + years * FASTEST_ARCSEC_YR + 1.0


def gaia_query(ra: float, dec: float, epoch: float, reach_arcsec: float) -> str:
    """ADQL for every Gaia DR3 source that can be within reach_arcsec of (ra, dec) on `epoch`."""
    slow, fast = _reaches(reach_arcsec, epoch - astrometry.GAIA_EPOCH)
    columns = ", ".join([f"g.{c}" for c in GAIA_SOURCE_COLUMNS] + [f"a.{c}" for c in GAIA_AP_COLUMNS])
    return (f"SELECT {columns} FROM {GAIA_SOURCE} AS g LEFT OUTER JOIN {GAIA_AP} AS a ON a.source_id = g.source_id "
            f"WHERE {_circle(ra, dec, fast, 'g.ra', 'g.dec')} "
            f"AND (g.pm > {SLOW_ARCSEC_YR * 1000.0:.0f} OR {_circle(ra, dec, slow, 'g.ra', 'g.dec')})")


def simbad_query(ra: float, dec: float, epoch: float, reach_arcsec: float) -> str:
    """ADQL for every SIMBAD object that can be within reach_arcsec of (ra, dec) on `epoch`."""
    slow, fast = _reaches(reach_arcsec, epoch - astrometry.SIMBAD_EPOCH)
    limit = (SLOW_ARCSEC_YR * 1000.0) ** 2
    return (f"SELECT {', '.join(SIMBAD_BASIC_COLUMNS)} FROM basic WHERE {_circle(ra, dec, fast, 'ra', 'dec')} "
            f"AND (pmra * pmra + pmdec * pmdec > {limit:.0f} OR {_circle(ra, dec, slow, 'ra', 'dec')})")


def _oid_list(oids: list[int]) -> str:
    return ", ".join(str(int(o)) for o in sorted(set(oids)))


def simbad_gaia_ids_query(oids: list[int]) -> str:
    return f"SELECT oidref, id FROM ident WHERE oidref IN ({_oid_list(oids)}) AND id LIKE 'Gaia DR3 %'"


def simbad_family_query(oid: int) -> str:
    return ("SELECT h.parent, p.main_id AS parent_id, p.otype AS parent_otype, p.nbref AS parent_nbref, "
            "h.child, c.main_id AS child_id, c.otype AS child_otype, c.nbref AS child_nbref "
            "FROM h_link AS h JOIN basic AS p ON p.oid = h.parent JOIN basic AS c ON c.oid = h.child "
            f"WHERE h.parent = {int(oid)} OR h.child = {int(oid)}")


def simbad_temperature_query(oid: int) -> str:
    return f"SELECT teff, bibcode FROM mesFe_h WHERE oidref = {int(oid)} AND teff IS NOT NULL"


# --------------------------------------------------------------------------- plain words

# SIMBAD object types (the `otype` codes of its otypedef table, read 2026-11-15), each as
# (SIMBAD's own name for the type, what it is in plain words). Written for readers of
# about eleven; each describes the type, never this particular object.
OBJECT_TYPES: dict[str, tuple[str, str]] = {
    "*": ("star", "a star"),
    "**": ("double or multiple star", "two or more stars close together"),
    "PM*": ("high proper-motion star", "a star that moves quickly across the sky"),
    "MS*": ("main-sequence star", "an ordinary star, steadily shining like the Sun"),
    "LM*": ("low-mass star", "a star with much less mass than the Sun"),
    "BD*": ("brown dwarf", "bigger than a planet, too small to shine like a star"),
    "WD*": ("white dwarf", "the small, dense leftover core of a star that has died"),
    "V*": ("variable star", "a star whose brightness changes"),
    "BY*": ("BY Draconis variable", "a cool star whose brightness changes a little as it spins"),
    "RS*": ("RS Canum Venaticorum variable", "a close pair of stars whose brightness changes as they spin"),
    "Ro*": ("rotating variable", "a star whose brightness changes as it spins"),
    "Er*": ("eruptive variable", "a star with sudden outbursts of light"),
    "Pu*": ("pulsating variable", "a star that swells and shrinks"),
    "Mi*": ("Mira variable", "a cool giant star that swells and shrinks over many months"),
    "LP*": ("long-period variable", "a cool giant star whose brightness changes over months"),
    "RR*": ("RR Lyrae variable", "an old star that pulses, brightening in less than a day"),
    "Ce*": ("Cepheid variable", "a giant star that pulses over days to weeks"),
    "cC*": ("classical Cepheid", "a giant star that pulses over days to weeks"),
    "dS*": ("delta Scuti variable", "a star that pulses within hours"),
    "EB*": ("eclipsing binary", "two stars that pass in front of each other"),
    "SB*": ("spectroscopic binary", "two stars too close together to see apart"),
    "El*": ("ellipsoidal variable", "two close stars pulled into egg shapes"),
    "CV*": ("cataclysmic binary", "a white dwarf pulling gas from a partner star"),
    "XB*": ("X-ray binary", "a pair of stars that gives off X-rays"),
    "TT*": ("T Tauri star", "a very young star, still forming"),
    "Or*": ("Orion variable", "a young star whose brightness changes unevenly"),
    "Y*O": ("young stellar object", "a star still forming"),
    "Ae*": ("Herbig Ae/Be star", "a young star heavier than the Sun"),
    "Em*": ("emission-line star", "a star with gas around it that glows"),
    "Be*": ("Be star", "a hot star with a disc of gas around it"),
    "Ev*": ("evolved star", "an aging star"),
    "RG*": ("red giant branch star", "an aging star that has swollen into a giant"),
    "AB*": ("asymptotic giant branch star", "a giant star late in its life"),
    "HB*": ("horizontal branch star", "an old star that burns helium in its core"),
    "C*": ("carbon star", "a cool giant star with much carbon in its outer layers"),
    "S*": ("S star", "a cool giant star of an unusual make-up"),
    "OH*": ("OH/IR star", "a dying giant star wrapped in dust"),
    "pA*": ("post-AGB star", "a star that has just thrown off its outer layers"),
    "sg*": ("supergiant", "one of the biggest, brightest kinds of star"),
    "s*r": ("red supergiant", "one of the biggest, brightest kinds of star"),
    "s*b": ("blue supergiant", "one of the biggest, brightest kinds of star"),
    "s*y": ("yellow supergiant", "one of the biggest, brightest kinds of star"),
    "Ma*": ("massive star", "a star many times heavier than the Sun"),
    "WR*": ("Wolf-Rayet star", "a very hot, heavy star losing its outer layers"),
    "HS*": ("hot subdwarf", "a small, very hot star"),
    "Pe*": ("chemically peculiar star", "a star of an unusual make-up"),
    "HV*": ("high-velocity star", "a star moving unusually fast through the Galaxy"),
    "No*": ("nova", "a white dwarf that had a sudden outburst"),
    "SN*": ("supernova", "a star that exploded"),
    "Sy*": ("symbiotic star", "a giant star and a hot partner sharing gas"),
    "Pl": ("planet", "a planet around another star"),
    "Cl*": ("star cluster", "a group of stars born together"),
    "OpC": ("open cluster", "a loose group of young stars born together"),
    "GlC": ("globular cluster", "a ball of hundreds of thousands of old stars"),
    "As*": ("association of stars", "a loose group of young stars"),
    "MGr": ("moving group", "stars that travel through space together"),
    "G": ("galaxy", "a galaxy: billions of stars, far beyond our own"),
    "QSO": ("quasar", "the very bright centre of a distant galaxy"),
    "AGN": ("active galaxy nucleus", "the bright centre of a galaxy"),
    "PN": ("planetary nebula", "a glowing shell of gas from a dying star"),
    "HII": ("HII region", "a cloud of gas lit up by hot young stars"),
    "MoC": ("molecular cloud", "a cold, dark cloud of gas and dust"),
    "SFR": ("star-forming region", "a place where stars are being born"),
    "DNe": ("dark cloud", "a cloud of dust that blocks the light behind it"),
    "RNe": ("reflection nebula", "a cloud of dust lit by nearby stars"),
    "GNe": ("nebula", "a cloud of gas or dust"),
    "HH": ("Herbig-Haro object", "a glowing jet of gas from a young star"),
    "X": ("X-ray source", "something seen in X-rays; what it is, is not known"),
    "IR": ("infrared source", "something seen in infrared light; what it is, is not known"),
    "NIR": ("near-infrared source", "something seen in infrared light; what it is, is not known"),
    "MIR": ("mid-infrared source", "something seen in infrared light; what it is, is not known"),
    "FIR": ("far-infrared source", "something seen in infrared light; what it is, is not known"),
    "Rad": ("radio source", "something seen in radio waves; what it is, is not known"),
    "UV": ("ultraviolet source", "something seen in ultraviolet light; what it is, is not known"),
    "gam": ("gamma-ray source", "something seen in gamma rays; what it is, is not known"),
    "Opt": ("optical source", "something seen in visible light; what it is, is not known"),
    "mul": ("blend", "several objects seen as one"),
    "?": ("object of unknown nature", "something whose nature is not known"),
}
# Candidate types SIMBAD writes with a "?" whose base is not simply the code without it.
_CANDIDATE_BASE = {"Y*?": "Y*O", "Q?": "QSO", "AG?": "AGN"}


def object_type_words(code: str | None) -> dict[str, Any] | None:
    """A SIMBAD object type as {code, label, plain, candidate}; plain is None for a type not in the table."""
    if not code:
        return None
    candidate = code.endswith("?") and code not in OBJECT_TYPES
    base = code
    if candidate:
        base = _CANDIDATE_BASE.get(code) or next(
            (b for b in (code[:-1] + "*", code[:-1], code[:-1] + "O") if b in OBJECT_TYPES), code)
    known = OBJECT_TYPES.get(base)
    if known is None:
        return {"code": code, "label": f"SIMBAD type {code}", "plain": None, "candidate": candidate}
    label, plain = known
    if candidate:
        return {"code": code, "label": f"{label} (candidate)", "plain": f"possibly {plain}", "candidate": True}
    return {"code": code, "label": label, "plain": plain, "candidate": False}


# Spectral classes (Morgan-Keenan and the brown-dwarf classes L, T and Y) in plain words,
# first without a luminosity class, then for the dwarfs (V) and giants (III, II) that
# change the meaning. D is a white dwarf (DA, DB, DC, ...).
SPECTRAL_CLASSES: dict[str, tuple[str, str]] = {
    "O": ("O-type star", "the hottest, bluest kind of star"),
    "B": ("B-type star", "a very hot, blue-white star"),
    "A": ("A-type star", "a hot, white star"),
    "F": ("F-type star", "a white star a little hotter than the Sun"),
    "G": ("G-type star", "a yellow-white star like the Sun"),
    "K": ("K-type star", "an orange star a little cooler than the Sun"),
    "M": ("M-type star", "a cool, red star"),
    "L": ("L dwarf", "a very cool, dim object: a tiny star or a brown dwarf"),
    "T": ("T dwarf", "a cool brown dwarf"),
    "Y": ("Y dwarf", "the coldest kind of brown dwarf known"),
    "D": ("white dwarf", "the small, dense leftover core of a star that has died"),
    "C": ("carbon star", "a cool giant star with much carbon in its outer layers"),
    "S": ("S-type star", "a cool giant star of an unusual make-up"),
    "W": ("Wolf-Rayet star", "a very hot, heavy star losing its outer layers"),
}
SPECTRAL_DWARFS: dict[str, tuple[str, str]] = {
    "M": ("M dwarf", "a small, cool, red star"),
    "K": ("K dwarf", "an orange star, a little smaller and cooler than the Sun"),
    "G": ("G dwarf", "a star much like the Sun"),
}
SPECTRAL_GIANTS: dict[str, tuple[str, str]] = {
    "M": ("M giant", "a huge, cool, red star late in its life"),
    "K": ("K giant", "a swollen orange star late in its life"),
    "G": ("G giant", "a swollen yellow star late in its life"),
}
_SPECTRAL = re.compile(r"^\s*(?:sd|esd|usd|d|g)?\s*(O|B|A|F|G|K|M|L|T|Y|D[ABCOQZX]?|C|S|W[NCO]?)"
                       r"(?:[0-9.]+(?:\s*[-/]\s*[0-9.]+)?)?\s*(?:[-/]?\s*[OBAFGKMLTY][0-9.]*)?\s*"
                       r"(Ia\+|Iab|Ia|Ib|III|II|IV|VI|V|I)?")


def _luminosity_class(text: str) -> str | None:
    """The luminosity class written after a spectral type: the first roman numeral group."""
    m = re.search(r"(?<![A-Za-z])(Ia\+|Iab|Ia|Ib|III|II|IV|VI|V|I)(?![A-Za-z])", text)
    return m.group(1) if m else None


def spectral_words(sp_type: str | None) -> dict[str, Any] | None:
    """A spectral type as {text, class, luminosity_class, label, plain, pair, parts}.

    `pair` is true when the type names two objects, as "T1V+T6V" does (Epsilon Indi B,
    two brown dwarfs seen as one). A "+" not followed by a class letter, as in "M4.5-6+e",
    is part of one type.
    """
    if not sp_type:
        return None
    text = sp_type.strip()
    parts = [p.strip() for p in text.split("+")]
    typed = [p for p in parts if p and _SPECTRAL.match(p)]
    pair = len(typed) >= 2
    first = _SPECTRAL.match(parts[0]) if parts and parts[0] else None
    if first is None:
        return {"text": text, "class": None, "luminosity_class": None, "label": None, "plain": None, "pair": pair,
                "parts": typed}
    letter = first.group(1)[0]
    lum = _luminosity_class(parts[0])
    label, plain = SPECTRAL_CLASSES[letter]
    if lum in ("V", "VI") and letter in SPECTRAL_DWARFS:
        label, plain = SPECTRAL_DWARFS[letter]
    elif lum in ("III", "II") and letter in SPECTRAL_GIANTS:
        label, plain = SPECTRAL_GIANTS[letter]
    elif lum in ("I", "Ia", "Ia+", "Iab", "Ib") and letter in "OBAFGKM":
        label, plain = f"{letter} supergiant", "one of the biggest, brightest kinds of star"
    elif lum == "IV" and letter in "OBAFGKM":
        label, plain = f"{letter} subgiant", "a star that has begun to swell as it ages"
    return {"text": text, "class": letter, "luminosity_class": lum, "label": label, "plain": plain, "pair": pair,
            "parts": typed}


# --------------------------------------------------------------------------- measured values

def _quantity(key: str, label: str, value: float | None, unit: str, catalogue: str, column: str, *,
              error: float | None = None, error_column: str | None = None, lower: float | None = None,
              upper: float | None = None, range_columns: list[str] | None = None, reference: str | None = None,
              note: str | None = None) -> dict[str, Any] | None:
    """One measured value as the card shows it, or None when the catalogue gives no value.

    `error` is a one-sigma error; `lower` and `upper` a range (for Gaia's astrophysical
    parameters, the 16th and 84th percentiles of its own posterior).
    """
    if value is None:
        return None
    return {"key": key, "label": label, "value": value, "error": error, "lower": lower, "upper": upper,
            "unit": unit, "catalogue": catalogue, "column": column, "error_column": error_column,
            "range_columns": range_columns, "reference": reference, "note": note}


def _gaia_quantity(row: dict[str, Any], column: str, label: str, unit: str, *, table: str = GAIA_SOURCE,
                   error: str | None = None, ranged: bool = False, note: str | None = None) -> dict[str, Any] | None:
    lower = upper = None
    range_columns = None
    if ranged:
        lower, upper = row.get(f"{column}_lower"), row.get(f"{column}_upper")
        range_columns = [f"{column}_lower", f"{column}_upper"]
    return _quantity(column, label, row.get(column), unit, "Gaia DR3", f"{table}.{column}",
                     error=row.get(error) if error else None, error_column=error, lower=lower, upper=upper,
                     range_columns=range_columns, note=note)


def _gaia_values(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Every value Gaia DR3 gives for one source, in the order the expert table lists them."""
    def snr_to_mag(*snrs: float | None) -> float | None:
        if any(s is None or s <= 0 for s in snrs):
            return None
        # Magnitude error from the flux signal-to-noise; for a colour the two add in quadrature.
        # The photometric zero-point uncertainty (a few thousandths of a magnitude) is not included.
        return MAG_PER_RELATIVE_FLUX * math.sqrt(sum(1.0 / float(s) ** 2 for s in snrs if s is not None))

    g = _quantity("phot_g_mean_mag", "G magnitude (visible light)", row.get("phot_g_mean_mag"), "mag", "Gaia DR3",
                  f"{GAIA_SOURCE}.phot_g_mean_mag", error=snr_to_mag(row.get("phot_g_mean_flux_over_error")),
                  error_column="from phot_g_mean_flux_over_error")
    colour = _quantity("bp_rp", "BP-RP colour", row.get("bp_rp"), "mag", "Gaia DR3", f"{GAIA_SOURCE}.bp_rp",
                       error=snr_to_mag(row.get("phot_bp_mean_flux_over_error"),
                                        row.get("phot_rp_mean_flux_over_error")),
                       error_column="from phot_bp_mean_flux_over_error and phot_rp_mean_flux_over_error")
    ap = GAIA_AP
    values = [
        _gaia_quantity(row, "parallax", "Parallax", "mas", error="parallax_error"),
        _gaia_quantity(row, "pmra", "Proper motion, east (includes cos dec)", "mas/yr", error="pmra_error"),
        _gaia_quantity(row, "pmdec", "Proper motion, north", "mas/yr", error="pmdec_error"),
        _gaia_quantity(row, "radial_velocity", "Radial velocity", "km/s", error="radial_velocity_error"),
        g, colour,
        _gaia_quantity(row, "ruwe", "RUWE (about 1 for a well-fitted single star)", ""),
        _gaia_quantity(row, "teff_gspphot", "Temperature, GSP-Phot", "K", table=ap, ranged=True),
        _gaia_quantity(row, "teff_espucd", "Temperature, ESP-UCD (ultracool dwarfs)", "K", table=ap,
                       error="teff_espucd_uncertainty"),
        _gaia_quantity(row, "teff_esphs", "Temperature, ESP-HS (hot stars)", "K", table=ap,
                       error="teff_esphs_uncertainty"),
        _gaia_quantity(row, "teff_gspspec", "Temperature, GSP-Spec (RVS spectra)", "K", table=ap, ranged=True),
        _gaia_quantity(row, "radius_flame", "Radius, FLAME", "solar radii", table=ap, ranged=True),
        _gaia_quantity(row, "radius_gspphot", "Radius, GSP-Phot", "solar radii", table=ap, ranged=True),
        _gaia_quantity(row, "lum_flame", "Luminosity, FLAME", "solar luminosities", table=ap, ranged=True),
        _gaia_quantity(row, "distance_gspphot", "Distance, GSP-Phot (model estimate)", "pc", table=ap,
                       ranged=True),
    ]
    flag = row.get("phot_variable_flag")
    if flag == "VARIABLE":     # the other values, NOT_AVAILABLE and CONSTANT (unused in DR3), say nothing
        values.append({"key": "phot_variable_flag", "label": "Photometric variability flag", "value": flag,
                       "error": None, "lower": None, "upper": None, "unit": "", "catalogue": "Gaia DR3",
                       "column": f"{GAIA_SOURCE}.phot_variable_flag", "error_column": None, "range_columns": None,
                       "reference": None, "note": None})
    return [v for v in values if v is not None]


def _simbad_values(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """SIMBAD's own parallax and proper motion, for an object Gaia does not list."""
    pm_error = _simbad_pm_error(obj)
    values = [
        _quantity("plx_value", "Parallax", obj.get("plx_value"), "mas", "SIMBAD", "basic.plx_value",
                  error=obj.get("plx_err"), error_column="plx_err", reference=obj.get("plx_bibcode")),
        _quantity("pmra", "Proper motion, east (includes cos dec)", obj.get("pmra"), "mas/yr", "SIMBAD",
                  "basic.pmra", error=pm_error[0] if pm_error else None, error_column="pm_err_maj/min/angle",
                  reference=obj.get("pm_bibcode")),
        _quantity("pmdec", "Proper motion, north", obj.get("pmdec"), "mas/yr", "SIMBAD", "basic.pmdec",
                  error=pm_error[1] if pm_error else None, error_column="pm_err_maj/min/angle",
                  reference=obj.get("pm_bibcode")),
    ]
    return [v for v in values if v is not None]


def _simbad_pm_covariance(obj: dict[str, Any]) -> np.ndarray | None:
    """SIMBAD's proper-motion error ellipse as a covariance matrix in (east, north).

    SIMBAD gives the ellipse's semi-axes (pm_err_maj, pm_err_min, mas/yr) and the position
    angle of the major axis (pm_err_angle, degrees from north through east). With u the
    unit vector along the major axis, (sin a, cos a), and v along the minor one,
    (cos a, -sin a): covariance = maj^2 u u' + min^2 v v'.
    """
    a, b = obj.get("pm_err_maj"), obj.get("pm_err_min")
    if a is None or b is None:
        return None
    angle = math.radians(obj.get("pm_err_angle") or 0.0)
    u = np.array([math.sin(angle), math.cos(angle)])
    v = np.array([math.cos(angle), -math.sin(angle)])
    return a * a * np.outer(u, u) + b * b * np.outer(v, v)


def _simbad_pm_error(obj: dict[str, Any]) -> tuple[float, float] | None:
    cov = _simbad_pm_covariance(obj)
    return None if cov is None else (float(math.sqrt(cov[0, 0])), float(math.sqrt(cov[1, 1])))


# --------------------------------------------------------------------------- derived values

def distance_from_parallax(parallax_mas: float, error_mas: float | None) -> dict[str, Any]:
    """Distance as 1 / parallax, when that is safe.

    d [pc] = 1000 / parallax [mas]; its error to first order is 1000 x error / parallax^2.
    Inverting is only fair when the parallax is at least MIN_PARALLAX_OVER_ERROR times its
    error (below that the inverse is biased and its error is not symmetric); then the
    status says so and no distance is given. No parallax zero-point correction is applied
    (Gaia DR3: about -0.02 mas, Lindegren et al. 2021), which matters only below about
    1 mas. Light-years = parsecs x LY_PER_PC.
    """
    if parallax_mas <= 0:
        return {"status": "negative_parallax", "pc": None, "pc_error": None, "ly": None, "ly_error": None,
                "parallax_over_error": None if not error_mas else parallax_mas / error_mas}
    if not error_mas or error_mas <= 0:
        return {"status": "parallax_has_no_error", "pc": None, "pc_error": None, "ly": None, "ly_error": None,
                "parallax_over_error": None}
    ratio = parallax_mas / error_mas
    if ratio < MIN_PARALLAX_OVER_ERROR:
        return {"status": "parallax_too_uncertain", "pc": None, "pc_error": None, "ly": None, "ly_error": None,
                "parallax_over_error": ratio}
    pc = 1000.0 / parallax_mas
    pc_error = 1000.0 * error_mas / parallax_mas ** 2
    return {"status": "from_parallax", "pc": pc, "pc_error": pc_error, "ly": pc * LY_PER_PC,
            "ly_error": pc_error * LY_PER_PC, "parallax_over_error": ratio}


def total_motion(pmra: float, pmdec: float, cov: np.ndarray | None) -> tuple[float, float | None]:
    """Total proper motion mu = sqrt(pmra^2 + pmdec^2) (mas/yr) and its error.

    To first order, with g = (pmra, pmdec) / mu the gradient of mu, the variance is
    g' C g, where C is the 2 x 2 covariance of (pmra, pmdec). For Gaia, C holds
    pmra_error^2, pmdec_error^2 and pmra_pmdec_corr x pmra_error x pmdec_error.
    """
    mu = math.hypot(pmra, pmdec)
    if cov is None or mu == 0:
        return mu, None
    g = np.array([pmra, pmdec]) / mu
    return mu, float(math.sqrt(max(float(g @ cov @ g), 0.0)))


def tangential_speed(parallax: float, pmra: float, pmdec: float, cov3: np.ndarray | None) -> tuple[float, float | None]:
    """Speed across the line of sight in km/s, and its error.

    v = KM_S_PER_AU_PER_YR x mu / parallax (mu in mas/yr, parallax in mas: the mas cancel,
    leaving au per year, then km/s). Error to first order from the 3 x 3 covariance C of
    (parallax, pmra, pmdec): with the gradient J = (-v / parallax, k pmra / (mu parallax),
    k pmdec / (mu parallax)), variance = J' C J. Gaia gives the three correlations; for
    SIMBAD values none is known and they are taken as zero.
    """
    mu = math.hypot(pmra, pmdec)
    k = KM_S_PER_AU_PER_YR
    v = k * mu / parallax
    if cov3 is None or mu == 0:
        return v, None
    jac = np.array([-v / parallax, k * pmra / (mu * parallax), k * pmdec / (mu * parallax)])
    return v, float(math.sqrt(max(float(jac @ cov3 @ jac), 0.0)))


def _gaia_covariance(row: dict[str, Any]) -> np.ndarray | None:
    """Covariance of (parallax, pmra, pmdec) from Gaia's errors and correlations."""
    errs = [row.get("parallax_error"), row.get("pmra_error"), row.get("pmdec_error")]
    if any(e is None for e in errs):
        return None
    s = np.array(errs, dtype=float)
    corr = np.eye(3)
    for (i, j), col in {(0, 1): "parallax_pmra_corr", (0, 2): "parallax_pmdec_corr",
                        (1, 2): "pmra_pmdec_corr"}.items():
        corr[i, j] = corr[j, i] = row.get(col) or 0.0
    return corr * np.outer(s, s)


def _derived(astro: dict[str, Any] | None, gaia_row: dict[str, Any] | None) -> dict[str, Any]:
    """Distance, speed across the sky and yearly motion, from Gaia's values or SIMBAD's."""
    out: dict[str, Any] = {"from": None, "distance": None, "distance_estimate": None, "motion": None, "speed": None}
    if astro is None:
        return out
    cat, cols = astro["catalogue"], astro["columns"]
    out["from"] = cat
    plx, plx_err, pmra, pmdec, cov3 = (astro["parallax"], astro["parallax_error"], astro["pmra"], astro["pmdec"],
                                       astro["cov3"])
    if plx is not None:
        d = distance_from_parallax(plx, plx_err)
        d.update({"catalogue": cat, "inputs": [cols["parallax"], cols["parallax_error"]],
                  "formula": "distance [pc] = 1000 / parallax [mas]; light-years = pc x 3.26156; "
                             "error = 1000 x parallax_error / parallax^2",
                  "reference": astro.get("parallax_reference")})
        out["distance"] = d
    if gaia_row is not None and (out["distance"] is None or out["distance"]["status"] != "from_parallax"):
        est = gaia_row.get("distance_gspphot")
        if est is not None:
            lo, hi = gaia_row.get("distance_gspphot_lower"), gaia_row.get("distance_gspphot_upper")
            out["distance_estimate"] = {
                "pc": est, "pc_lower": lo, "pc_upper": hi, "ly": est * LY_PER_PC,
                "ly_lower": lo * LY_PER_PC if lo is not None else None,
                "ly_upper": hi * LY_PER_PC if hi is not None else None,
                "catalogue": "Gaia DR3", "inputs": [f"{GAIA_AP}.distance_gspphot", "distance_gspphot_lower",
                                                    "distance_gspphot_upper"],
                "note": "Gaia's own estimate from the star's colours, brightness and parallax (GSP-Phot)."}
    if pmra is not None and pmdec is not None:
        cov2 = None if cov3 is None else cov3[1:, 1:]
        mu, mu_err = total_motion(pmra, pmdec, cov2)
        out["motion"] = {
            "mas_per_year": mu, "mas_per_year_error": mu_err,
            "arcsec_per_year": mu / 1000.0, "arcsec_per_year_error": None if mu_err is None else mu_err / 1000.0,
            "pixels_per_year": mu / 1000.0 / PIXEL_ARCSEC,
            "pixels_per_year_error": None if mu_err is None else mu_err / 1000.0 / PIXEL_ARCSEC,
            # Years to cross one SPHEREx pixel: 6.15 arcsec / (mu / 1000 arcsec per year).
            "years_per_pixel": PIXEL_ARCSEC / (mu / 1000.0) if mu > 0 else None,
            "catalogue": cat, "inputs": [cols["pmra"], cols["pmdec"]],
            "formula": "mu = sqrt(pmra^2 + pmdec^2); pixels a year = mu [arcsec/yr] / 6.15",
            "reference": astro.get("pm_reference")}
        if out["distance"] is not None and out["distance"]["status"] == "from_parallax" and plx is not None:
            v, v_err = tangential_speed(plx, pmra, pmdec, cov3)
            out["speed"] = {"km_s": v, "km_s_error": v_err, "catalogue": cat,
                            "inputs": [cols["parallax"], cols["pmra"], cols["pmdec"]],
                            "formula": "speed across the sky [km/s] = 4.74047 x mu [mas/yr] / parallax [mas]"}
    return out


# --------------------------------------------------------------------------- putting it together

def _place(row: dict[str, Any], ref_epoch: float, epoch: float) -> tuple[float, float]:
    """Where a catalogue entry is on `epoch` (barycentric, no parallax offset)."""
    src = {"ra": row["ra"], "dec": row["dec"], "pmra": row.get("pmra"), "pmdec": row.get("pmdec"),
           "parallax": row.get("parallax", row.get("plx_value")), "radial_velocity": row.get("radial_velocity"),
           "ref_epoch": ref_epoch}
    ra, dec = astrometry.propagate(src, epoch)
    return ra % 360.0, dec


def _locate(rows: list[dict[str, Any]], ref_epoch: float, epoch: float, ra: float, dec: float) -> None:
    """Add each entry's place on `epoch` and its offset from (ra, dec), in place."""
    for r in rows:
        r["_ra"], r["_dec"] = _place(r, r.get("ref_epoch") or ref_epoch, epoch)
        east, north = astrometry.offset_arcsec(ra, dec, r["_ra"], r["_dec"])
        r["_east"], r["_north"], r["_sep"] = east, north, math.hypot(east, north)


def _separation(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(*astrometry.offset_arcsec(a["_ra"], a["_dec"], b["_ra"], b["_dec"]))


def _service(kind: str) -> dict[str, Any]:
    return {"name": SERVICE_NAMES[kind], "answered": False, "via": None, "error": None, "partial": []}


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _gaia_entry(row: dict[str, Any], epoch: float) -> dict[str, Any]:
    return {"source_id": str(row["source_id"]), "name": f"Gaia DR3 {row['source_id']}",
            "separation_arcsec": _r(row["_sep"], 2), "east_arcsec": _r(row["_east"], 2),
            "north_arcsec": _r(row["_north"], 2),
            "position": {"ra": _r(row["_ra"], 7), "dec": _r(row["_dec"], 7), "epoch": epoch},
            "catalogue_position": {"ra": row["ra"], "dec": row["dec"], "epoch": row.get("ref_epoch")},
            "values": _gaia_values(row)}


def _family(rows: list[dict[str, Any]], oid: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """SIMBAD's parents (systems, clusters the object belongs to) and children (its planets, components)."""
    parents: dict[int, dict[str, Any]] = {}
    children: dict[int, dict[str, Any]] = {}
    for r in rows:
        if r.get("child") == oid and r.get("parent") is not None:
            parents[int(r["parent"])] = {"oid": int(r["parent"]), "name": r.get("parent_id"),
                                         "display_name": astrometry._display_name(str(r.get("parent_id") or "")),
                                         "type": object_type_words(r.get("parent_otype")),
                                         "references": r.get("parent_nbref")}
        if r.get("parent") == oid and r.get("child") is not None:
            children[int(r["child"])] = {"oid": int(r["child"]), "name": r.get("child_id"),
                                         "display_name": astrometry._display_name(str(r.get("child_id") or "")),
                                         "type": object_type_words(r.get("child_otype")),
                                         "references": r.get("child_nbref")}
    order = sorted(parents.values(), key=lambda p: -(p["references"] or 0))
    return order, sorted(children.values(), key=lambda c: str(c["name"]))


def _simbad_entry(obj: dict[str, Any], epoch: float, gaia_ids: dict[int, list[str]]) -> dict[str, Any]:
    return {"oid": int(obj["oid"]), "main_id": obj["main_id"],
            "display_name": astrometry._display_name(str(obj["main_id"])),
            "separation_arcsec": _r(obj["_sep"], 2), "east_arcsec": _r(obj["_east"], 2),
            "north_arcsec": _r(obj["_north"], 2),
            "position": {"ra": _r(obj["_ra"], 7), "dec": _r(obj["_dec"], 7), "epoch": epoch},
            "type": object_type_words(obj.get("otype")),
            "spectral_type": spectral_words(obj.get("sp_type")),
            "spectral_type_reference": obj.get("sp_bibcode"),
            "references": obj.get("nbref"),
            "gaia_dr3_ids": gaia_ids.get(int(obj["oid"]), []),
            "parents": None, "children": None, "planets": None, "temperatures": None}


def _pick(values: list[dict[str, Any]], order: tuple[str, ...]) -> dict[str, Any] | None:
    by_key = {v["key"]: v for v in values}
    return next((dict(by_key[k]) for k in order if k in by_key), None)


def identify(ra: float, dec: float, radius_arcsec: float = DEFAULT_RADIUS_ARCSEC,
             epoch: float = astrometry.RESOLVE_EPOCH) -> dict[str, Any]:
    """What Gaia DR3 and SIMBAD know about the thing at (ra, dec) on `epoch` (Julian year).

    (ra, dec) is where the object is on the SPHEREx pictures; the default epoch, 2026.0,
    is the date /api/resolve gives positions for.
    """
    if not 0 < radius_arcsec <= MAX_RADIUS_ARCSEC:
        raise spherex.BadRequest(f"radius must be between 0 and {MAX_RADIUS_ARCSEC:g} arcsec")
    reach = max(radius_arcsec, NEIGHBOUR_ARCSEC)
    services = {"gaia": _service("gaia"), "simbad": _service("simbad")}
    notes: list[str] = []

    def ask(kind: str, adql: str) -> list[dict[str, Any]] | None:
        try:
            rows, via = _tap(kind, adql)
        except _Unanswered as e:
            services[kind]["error"] = str(e)
            return None
        services[kind]["answered"], services[kind]["via"] = True, via
        return rows

    with ThreadPoolExecutor(2) as pool:
        gaia_job = pool.submit(ask, "gaia", gaia_query(ra, dec, epoch, reach))
        simbad_job = pool.submit(ask, "simbad", simbad_query(ra, dec, epoch, reach))
        gaia_rows, simbad_rows = gaia_job.result(), simbad_job.result()

    gaia_near: list[dict[str, Any]] = []
    if gaia_rows is not None:
        rows = [dict(r) for r in gaia_rows]
        _locate(rows, astrometry.GAIA_EPOCH, epoch, ra, dec)
        gaia_near = sorted((r for r in rows if r["_sep"] <= reach), key=lambda r: r["_sep"])
    simbad_near: list[dict[str, Any]] = []
    if simbad_rows is not None:
        rows = [dict(r, parallax=r.get("plx_value")) for r in simbad_rows if r.get("ra") is not None]
        _locate(rows, astrometry.SIMBAD_EPOCH, epoch, ra, dec)
        simbad_near = sorted((r for r in rows if r["_sep"] <= reach), key=lambda r: r["_sep"])

    def follow_up(adql: str, what: str) -> list[dict[str, Any]] | None:
        try:
            return _tap("simbad", adql)[0]
        except _Unanswered as e:
            services["simbad"]["partial"].append(f"{what}: {e}")
            return None

    # Which SIMBAD objects are which Gaia sources: SIMBAD lists the Gaia DR3 identifier among an object's names.
    gaia_ids: dict[int, list[str]] = {}
    ids_known = True
    if simbad_near:
        id_rows = follow_up(simbad_gaia_ids_query([int(s["oid"]) for s in simbad_near]), "Gaia identifiers")
        ids_known = id_rows is not None
        for r in id_rows or []:
            gaia_ids.setdefault(int(r["oidref"]), []).append(str(r["id"]).split()[-1])

    # The object at the place. Planets are listed at their star's position and are not candidates.
    g_in = [g for g in gaia_near if g["_sep"] <= radius_arcsec]
    s_in = [s for s in simbad_near if s["_sep"] <= radius_arcsec and s.get("otype") not in ("Pl", "Pl?")]
    g0 = g_in[0] if g_in else None
    s0 = s_in[0] if s_in else None
    main_g, main_s, match = g0, None, None
    if g0 is not None:
        sid = str(g0["source_id"])
        named = next((s for s in s_in if sid in gaia_ids.get(int(s["oid"]), [])), None)
        if named is not None:
            main_s, match = named, {"same": True, "how": "identifier",
                                    "text": f"SIMBAD lists Gaia DR3 {sid} among the names of {named['main_id']}."}
        elif s0 is not None and not gaia_ids.get(int(s0["oid"])) and _separation(s0, g0) <= SAME_PLACE_ARCSEC:
            main_s, match = s0, {"same": True, "how": "position",
                                 "text": f"SIMBAD names no Gaia DR3 source for {s0['main_id']}; it is "
                                         f"{_separation(s0, g0):.1f} arcsec from the Gaia source, so the two are "
                                         "taken as one object by position alone."}
        elif s0 is not None and s0["_sep"] < g0["_sep"]:
            # The nearer of the two is the object; the other is a different one nearby.
            main_g, main_s = None, s0
            match = {"same": False, "how": "different",
                     "text": f"The nearest Gaia source is not {s0['main_id']}; it is listed among the neighbours."}
        elif s0 is not None:
            match = {"same": False, "how": "different",
                     "text": f"The nearest SIMBAD object, {s0['main_id']}, is not this Gaia source; it is listed "
                             "among the neighbours."}
    else:
        main_s = s0

    gaia: dict[str, Any] | None = _gaia_entry(main_g, epoch) if main_g is not None else None
    simbad: dict[str, Any] | None = None
    if main_s is not None:
        simbad = _simbad_entry(main_s, epoch, gaia_ids)
        oid = int(main_s["oid"])
        with ThreadPoolExecutor(2) as pool:
            fam_job = pool.submit(follow_up, simbad_family_query(oid), "parents and children")
            temp_job = pool.submit(follow_up, simbad_temperature_query(oid), "temperatures")
            family_rows, temp_rows = fam_job.result(), temp_job.result()
        if family_rows is not None:
            parents, children = _family(family_rows, oid)
            simbad["parents"] = parents
            simbad["children"] = [c for c in children if not (c["type"] and c["type"]["code"] in ("Pl", "Pl?"))]
            simbad["planets"] = [c for c in children if c["type"] and c["type"]["code"] in ("Pl", "Pl?")]
        if temp_rows is not None:
            teffs = [float(t["teff"]) for t in temp_rows if t.get("teff") is not None]
            simbad["temperatures"] = {
                "n": len(teffs), "median": statistics.median(teffs) if teffs else None,
                "min": min(teffs) if teffs else None, "max": max(teffs) if teffs else None,
                "column": "mesFe_h.teff", "references": sorted({str(t["bibcode"]) for t in temp_rows
                                                                if t.get("bibcode")})}
        if main_g is None:
            simbad["values"] = _simbad_values(main_s)

    # Astrometry for the derived values: Gaia's when the object is a Gaia source, else SIMBAD's.
    astro: dict[str, Any] | None = None
    if main_g is not None:
        astro = {"catalogue": "Gaia DR3", "parallax": main_g.get("parallax"),
                 "parallax_error": main_g.get("parallax_error"), "pmra": main_g.get("pmra"),
                 "pmdec": main_g.get("pmdec"), "cov3": _gaia_covariance(main_g),
                 "columns": {"parallax": f"{GAIA_SOURCE}.parallax", "parallax_error": "parallax_error",
                             "pmra": f"{GAIA_SOURCE}.pmra", "pmdec": f"{GAIA_SOURCE}.pmdec"}}
    elif main_s is not None:
        cov2 = _simbad_pm_covariance(main_s)
        cov3 = None
        if cov2 is not None and main_s.get("plx_err") is not None:
            cov3 = np.zeros((3, 3))
            cov3[0, 0] = float(main_s["plx_err"]) ** 2
            cov3[1:, 1:] = cov2
        astro = {"catalogue": "SIMBAD", "parallax": main_s.get("plx_value"), "parallax_error": main_s.get("plx_err"),
                 "pmra": main_s.get("pmra"), "pmdec": main_s.get("pmdec"), "cov3": cov3,
                 "parallax_reference": main_s.get("plx_bibcode"), "pm_reference": main_s.get("pm_bibcode"),
                 "columns": {"parallax": "basic.plx_value", "parallax_error": "plx_err", "pmra": "basic.pmra",
                             "pmdec": "basic.pmdec"}}
    derived = _derived(astro, main_g)

    # What the picture is drawn from: only values measured for this object.
    temperature = _pick(gaia["values"], TEMPERATURE_ORDER) if gaia else None
    if temperature is None and simbad and simbad["temperatures"] and simbad["temperatures"]["n"]:
        t = simbad["temperatures"]
        temperature = {"key": "mesFe_h.teff", "label": "Temperature, median of the values SIMBAD lists",
                       "value": t["median"], "error": None, "lower": t["min"], "upper": t["max"], "unit": "K",
                       "catalogue": "SIMBAD", "column": "mesFe_h.teff", "error_column": None,
                       "range_columns": ["lowest and highest listed"], "reference": None,
                       "note": f"median of {t['n']} published values"}
    radius = _pick(gaia["values"], RADIUS_ORDER) if gaia else None
    luminosity = _pick(gaia["values"], ("lum_flame",)) if gaia else None

    # Everything else within reach, nearest first. A SIMBAD object that is one of the Gaia
    # neighbours (by identifier) is named on that neighbour instead of being listed twice.
    main_ids = {str(main_g["source_id"])} if main_g is not None else set()
    family_oids = set()
    if simbad:
        family_oids = {p["oid"] for p in simbad["parents"] or []} | {c["oid"] for c in (simbad["children"] or [])
                                                                      + (simbad["planets"] or [])}
    name_of_gaia = {gid: s for s in simbad_near for gid in gaia_ids.get(int(s["oid"]), [])}
    centre = {"_ra": (main_g or main_s or {"_ra": ra})["_ra"], "_dec": (main_g or main_s or {"_dec": dec})["_dec"]}
    neighbours: list[dict[str, Any]] = []
    for g in gaia_near:
        sid = str(g["source_id"])
        if sid in main_ids:
            continue
        named_s = name_of_gaia.get(sid)
        neighbours.append({
            "catalogue": "Gaia DR3", "name": f"Gaia DR3 {sid}", "source_id": sid,
            "simbad_name": named_s["main_id"] if named_s else None,
            "simbad_type": object_type_words(named_s.get("otype")) if named_s else None,
            "separation_arcsec": _r(g["_sep"], 2), "east_arcsec": _r(g["_east"], 2), "north_arcsec": _r(g["_north"], 2),
            "from_object_arcsec": _r(_separation(centre, g), 2),
            "g_mag": _r(g.get("phot_g_mean_mag"), 2), "bp_rp": _r(g.get("bp_rp"), 2),
            "parallax": _r(g.get("parallax"), 3), "parallax_error": _r(g.get("parallax_error"), 3)})
    named_oids = {int(s["oid"]) for s in name_of_gaia.values()}
    for s in simbad_near:
        oid = int(s["oid"])
        if (main_s is not None and oid == int(main_s["oid"])) or oid in family_oids or oid in named_oids \
                or s.get("otype") in ("Pl", "Pl?"):
            continue
        neighbours.append({
            "catalogue": "SIMBAD", "name": s["main_id"], "oid": oid, "simbad_name": s["main_id"],
            "simbad_type": object_type_words(s.get("otype")),
            "separation_arcsec": _r(s["_sep"], 2), "east_arcsec": _r(s["_east"], 2), "north_arcsec": _r(s["_north"], 2),
            "from_object_arcsec": _r(_separation(centre, s), 2), "g_mag": None, "bp_rp": None,
            "parallax": s.get("plx_value"), "parallax_error": s.get("plx_err"),
            "gaia_dr3_ids": gaia_ids.get(oid, [])})
    neighbours.sort(key=lambda n: n["separation_arcsec"])
    for n in neighbours:
        n["same_pixel"] = n["from_object_arcsec"] <= PIXEL_ARCSEC

    found = gaia is not None or simbad is not None
    both_answered = services["gaia"]["answered"] and services["simbad"]["answered"]
    nothing = False if found else (True if both_answered else None)
    nearest = None
    if not found and neighbours:
        n = neighbours[0]
        nearest = {k: n[k] for k in ("catalogue", "name", "simbad_name", "separation_arcsec", "g_mag")}
    unreachable = [s["name"] for s in services.values() if not s["answered"]]
    if services["simbad"]["partial"]:
        notes.append("SIMBAD answered only in part: " + "; ".join(services["simbad"]["partial"]))
    if not ids_known and main_s is not None:
        notes.append("SIMBAD's list of Gaia identifiers did not come back, so Gaia and SIMBAD were matched by "
                     "position only.")
    if services["gaia"]["via"] and services["gaia"]["via"] != GAIA_TAPS[0][0]:
        notes.append(f"Gaia DR3 was read from the {services['gaia']['via']}: the same tables as ESA's archive.")
    notes.append("Positions are moved to the date asked for with each catalogue's own proper motion (and Gaia's "
                 "radial velocity), without the yearly parallax shift.")
    if gaia:
        notes.append("Gaia's ranges for temperature, radius, luminosity and distance are the 16th to 84th "
                     "percentiles of its own fit; they are known to understate the real uncertainty.")

    return {
        "query": {"ra": ra, "dec": dec, "radius_arcsec": radius_arcsec, "epoch": epoch,
                  "neighbour_radius_arcsec": reach, "pixel_arcsec": PIXEL_ARCSEC},
        "services": services,
        "unreachable": unreachable,
        "nothing_catalogued": nothing,
        "nearest_catalogued": nearest,
        "searched_arcsec": reach,
        "gaia": gaia,
        "simbad": simbad,
        "match": match,
        "derived": derived,
        "portrait": {"temperature": temperature, "radius": radius, "luminosity": luminosity},
        "neighbours": neighbours,
        "notes": notes,
        "credit": "ESA Gaia DR3; SIMBAD (CDS, Strasbourg)",
    }

"""Gaia DR3 lookups and moving a catalogue position to an observation date."""
from __future__ import annotations

import hashlib
import io
import json

import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.io.votable import parse_single_table
from astropy.time import Time

from .spherex import CACHE, http_get

GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
GAIA_EPOCH = 2016.0  # reference epoch of Gaia DR3 positions (Julian year)


def gaia_cone(ra: float, dec: float, radius_deg: float, g_limit: float = 17.0) -> list[dict]:
    """Gaia DR3 sources within radius_deg of (ra, dec), brightest first. Cached on disk.

    Positions are at epoch 2016.0. A fast star can be arcminutes from where it is
    today, so callers should search wider than the field they want to cover.
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
    raw = http_get(GAIA_TAP, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query})
    table = parse_single_table(io.BytesIO(raw)).to_table(use_names_over_ids=True)

    def num(v):
        return None if np.ma.is_masked(v) or not np.isfinite(v) else float(v)

    sources = [{"source_id": str(r["source_id"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
                "pmra": num(r["pmra"]), "pmdec": num(r["pmdec"]), "parallax": num(r["parallax"]),
                "gmag": num(r["phot_g_mean_mag"])} for r in table]
    cache_file.write_text(json.dumps(sources))
    return sources


def position_at(src: dict, mjd: float, parallax: bool = True) -> tuple[float, float]:
    """Where a Gaia source appears at the given date: proper motion plus parallax.

    Linear proper motion from epoch 2016.0. That ignores perspective acceleration,
    which for Barnard's Star amounts to about 0.06 arcsec by 2026, a hundredth of a
    SPHEREx pixel. Parallax uses the Earth's barycentric position (SPHEREx is in low
    Earth orbit, so the difference is negligible).
    """
    ra, dec = src["ra"], src["dec"]
    t = Time(mjd, format="mjd")
    dt = t.jyear - GAIA_EPOCH
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


def offset_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> tuple[float, float]:
    """Small-angle offset of point 2 from point 1: (east, north) in arcseconds."""
    east = (ra2 - ra1) * np.cos(np.radians(0.5 * (dec1 + dec2))) * 3600.0
    north = (dec2 - dec1) * 3600.0
    return float(east), float(north)

"""NEOWISE as a second opinion: has another telescope seen this spot change before?

NEOWISE measured the whole sky at 3.4 and 4.6 micrometres about twice a year from 2014
to 2024, and every single measurement is public at IRSA. This module asks the archive for
those measurements around a position, groups them into visits and takes each visit's
median. `scripts/check_neowise.py` (which also re-measures SPHEREx) and the watchlist
(`backend/watchlist.py`) both use it.

What the reading means, and does not. NEOWISE ended in 2024 and SPHEREx began in 2025, so
NEOWISE never saw the change SPHEREx found. It speaks to one thing: whether this object
is the kind that varies. A reading is one of three:

- "changed":    at least MIN_VISITS visits in a band and the faintest and brightest visit
                differ by a factor of CHANGE_FACTOR or more ("NEOWISE also saw this spot change").
- "steady":     at least MIN_VISITS visits in a band, and no band changes by that factor.
- "cannot_say": too few measurements in both bands, or nothing there.

Limits kept in the sentence: NEOWISE saturates on bright objects (roughly magnitude 8 at
3.4 and 7 at 4.6 micrometres), so its brightest values are less certain, and it blurs about
6 arcsec like SPHEREx, so a tight group of objects is measured as one.
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
from astropy.table import Table
from astropy.time import Time

from . import astrometry, spherex

GATOR = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
ZERO_JY = {"w1": 309.540, "w2": 171.787}        # WISE Explanatory Supplement IV.4.h, Table 1
BAND_UM = {"w1": 3.4, "w2": 4.6}                # NEOWISE bands, micrometres
VISIT_GAP_DAYS = 30.0
MIN_PER_VISIT = 3                               # exposures a visit needs in a band to count
DEFAULT_RADIUS_ARCSEC = 1.5
MIN_VISITS = 6                                  # visits needed in a band before steady or changed can be said
CHANGE_FACTOR = 1.5                             # faintest to brightest visit at least this: it varies
SATURATED_SHARE = 0.2                           # a visit with this share of saturated pixels is "partly saturated"
ENDED = "NEOWISE ended in 2024, so it speaks to whether this object varies, not to this particular change."


def neowise_rows(ra: float, dec: float) -> Table:
    """Every NEOWISE single-exposure measurement within 8 arcsec. Cached like the other catalogue answers."""
    cache = spherex.CACHE / "queries" / f"neowise_{ra:.5f}_{dec:.5f}.tbl"
    if not cache.exists():
        raw = spherex.http_get(GATOR, {
            "catalog": "neowiser_p1bs_psd", "spatial": "cone", "objstr": f"{ra} {dec}", "radius": 8,
            "radunits": "arcsec", "outfmt": 1,
            "selcols": "ra,dec,mjd,w1mpro,w1sigmpro,w2mpro,w2sigmpro,w1sat,w2sat,qual_frame,cc_flags"},
            tries=5, timeout=120)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    return read_table(cache.read_bytes())


def read_table(raw: bytes) -> Table:
    return Table.read(io.BytesIO(raw), format="ipac")


def to_mjy(mag: float, band: str) -> float:
    return ZERO_JY[band] * 10 ** (-0.4 * mag) * 1000.0


def neowise_visits(table: Table, ra: float, dec: float,
                   radius: float = DEFAULT_RADIUS_ARCSEC) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """One row per NEOWISE visit (a run of exposures; a gap over 30 days starts the next), and counts."""

    def column(name: str) -> np.ndarray:
        return np.array(np.ma.filled(np.ma.array(table[name], dtype=float), np.nan))

    offsets = [astrometry.offset_arcsec(ra, dec, float(r), float(d)) for r, d in zip(table["ra"], table["dec"],
                                                                                     strict=True)]
    dist = np.array([np.hypot(e, n) for e, n in offsets])
    mjd, quality = column("mjd"), column("qual_frame")
    order = np.argsort(mjd)
    visit = np.empty(len(mjd), int)
    if len(mjd):
        visit[order] = np.concatenate([[0], np.cumsum(np.diff(mjd[order]) > VISIT_GAP_DAYS)])
    near = (dist < radius) & (quality > 0)
    out: list[dict[str, Any]] = []
    for v in np.unique(visit):
        row: dict[str, Any] = {"mjd": float(np.mean(mjd[visit == v]))}
        for band in ("w1", "w2"):
            mag, err, sat = column(f"{band}mpro"), column(f"{band}sigmpro"), column(f"{band}sat")
            use = (visit == v) & near & np.isfinite(mag) & np.isfinite(err)
            if use.sum() < MIN_PER_VISIT:
                row[band] = None
                continue
            row[band] = {"n": int(use.sum()), "mag": float(np.median(mag[use])),
                         "scatter": float(np.std(mag[use])), "sat": float(np.median(sat[use])),
                         "mjy": to_mjy(float(np.median(mag[use])), band)}
        if row["w1"] or row["w2"]:
            out.append(row)
    counts = {"all": len(table), "near": int((dist < radius).sum()), "used_frames": int(near.sum()),
              "further": int((dist >= radius).sum())}
    return out, counts


def date(mjd: float) -> str:
    return str(Time(mjd, format="mjd").iso[:10])


def _band(visits: list[dict[str, Any]], band: str) -> dict[str, Any] | None:
    rows = [v for v in visits if v[band]]
    if not rows:
        return None
    mjy = [v[band]["mjy"] for v in rows]
    faint, bright = min(mjy), max(mjy)
    return {"micrometres": BAND_UM[band], "n_visits": len(rows), "faintest_mjy": round(faint, 2),
            "brightest_mjy": round(bright, 2), "factor": round(bright / faint, 2) if faint > 0 else None,
            "saturated_share_max": round(max(v[band]["sat"] for v in rows), 2),
            "visits_partly_saturated": sum(v[band]["sat"] > SATURATED_SHARE for v in rows)}


def reading(visits: list[dict[str, Any]], counts: dict[str, int] | None = None) -> dict[str, Any]:
    """The three-way reading, the numbers behind it and one plain sentence."""
    bands = {b: _band(visits, b) for b in ("w1", "w2")}
    usable = {b: x for b, x in bands.items() if x and x["n_visits"] >= MIN_VISITS and x["factor"] is not None}
    changed = {b: x for b, x in usable.items() if x["factor"] >= CHANGE_FACTOR}
    if changed:
        verdict = "changed"
    elif usable:
        verdict = "steady"
    else:
        verdict = "cannot_say"
    n_visits = len(visits)
    out: dict[str, Any] = {
        "reading": verdict, "n_visits": n_visits,
        "first_date": date(min(v["mjd"] for v in visits)) if visits else None,
        "last_date": date(max(v["mjd"] for v in visits)) if visits else None,
        "w1": bands["w1"], "w2": bands["w2"], "radius_arcsec": DEFAULT_RADIUS_ARCSEC,
        "measurements_within_radius": counts["near"] if counts else None}
    out["sentence"] = sentence(out)
    return out


def sentence(r: dict[str, Any]) -> str:
    """The reading as one plain sentence (the page adds that NEOWISE ended in 2024)."""
    n = r["n_visits"]
    if r["reading"] == "cannot_say":
        if n == 0:
            return ("NEOWISE cannot say: it has no usable measurement of anything at this spot "
                    f"(within {r['radius_arcsec']} arcsec).")
        return (f"NEOWISE cannot say: it has only {n} {'visit' if n == 1 else 'visits'} here, and at least "
                f"{MIN_VISITS} are needed in one of its two bands.")
    bands = [r[b] for b in ("w2", "w1") if r[b] and r[b]["n_visits"] >= MIN_VISITS and r[b]["factor"] is not None]
    # The band that speaks: the one with the largest factor.
    best = max(bands, key=lambda x: x["factor"])
    span = f"{best['n_visits']} visits from {r['first_date'][:4]} to {r['last_date'][:4]}"
    numbers = (f"between {best['faintest_mjy']:,.0f} and {best['brightest_mjy']:,.0f} mJy at "
               f"{best['micrometres']} micrometres, a factor of {best['factor']:.1f}")
    head = ("NEOWISE also saw this spot change" if r["reading"] == "changed" else "NEOWISE saw it steady")
    text = f"{head}: {span}, {numbers}."
    if best["visits_partly_saturated"]:
        text += (f" In {best['visits_partly_saturated']} of those visits the object was partly too bright for NEOWISE, "
                 "so its brightest values are less certain.")
    return text


def read_spot(ra: float, dec: float) -> dict[str, Any]:
    """Ask the archive (cached) and give the reading for one position."""
    visits, counts = neowise_visits(neowise_rows(ra, dec), ra, dec)
    return reading(visits, counts)

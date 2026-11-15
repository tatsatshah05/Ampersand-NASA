"""The shared watchlist: what the blind searches found, kept in one SQLite file, with votes.

Everything here is a CANDIDATE. A vote is an opinion, never a confirmation. Nothing is
invented: the list holds only what `search.search()` returned for fields somebody searched.

The three groups are decided by the machine and never by votes
------------------------------------------------------------
- needs_eyes  ("needs eyes"): passed every artefact test of the search and is not explained
  by a catalogue: a mover whose motion no catalogue object has, or a brightness change in
  something not listed as variable (or with nothing there at all).
- known       ("already known"): a catalogued mover or a listed variable. Kept as examples
  of what real ones look like, and so that votes on them show how well people agree with
  the machine.
- artefact    ("set aside as artefacts"): the search's rejected list, with its reasons.

The order of "needs eyes" (shown on the page and in the export as `rank_in_group`)
-----------------------------------------------------------------------------------
1. clean before caution (a caution has flags a person must look at first);
2. then the more detectors that put it at 5 times the noise or more, first;
3. then the stronger first: times the noise with the detectors put together;
4. then the stronger in its best detector, then the identifier, so the order never wobbles.
"Already known" uses the same order. "Set aside" goes by strength alone. Votes never change
the order: they are shown beside the machine's evidence, as a separate number.

One row per object
------------------
The id is made from the kind and the position the first time the object is seen
(`changer-277.5055s02.0620`). The same object found again, or from a neighbouring patch,
is the same row: a new sighting of the same kind within MATCH_ARCSEC (the search's own
duplicate radius) of a stored row updates it instead of adding another. The evidence kept
is that of the patch where it was strongest; every patch that saw it is listed.

Voters
------
A voter is a random string the browser makes and keeps. Only its SHA-256 is stored, with the
answer, the note and the time. No name, no account, no address. One vote per voter per
candidate; voting again replaces it. A voter id may cast MAX_VOTES votes per VOTE_WINDOW_S
seconds; the count is kept in memory only.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import astrometry, neowise, spherex

log = logging.getLogger("backend.watchlist")

DB_ENV = "SPHEREX_WATCHLIST_DB"
MATCH_ARCSEC = 12.0                  # the search's own DUPLICATE_ARCSEC: the same object found again
GROUPS = ("eyes", "known", "artefact")
GROUP_NAMES = {"eyes": "needs_eyes", "known": "already_known", "artefact": "set_aside_as_artefact"}
KNOWN_CATEGORIES = frozenset(("known_mover", "known_variable"))
ANSWERS = ("real", "artefact", "unsure")
NOTE_MAX = 280
MAX_VOTES = 10                       # per voter id ...
VOTE_WINDOW_S = 60.0                 # ... per this many seconds
NEOWISE_RETRY_S = 3600.0             # a NEOWISE question that failed is asked again after this long
VIEWER_FOV = 0.1                     # the field of view the "look at it in the viewer" link asks for

ABOUT = (
    "Candidates found by a blind search of SPHEREx infrared images for things that moved or changed brightness, "
    "checked against catalogues. Every row is a CANDIDATE, not a discovery or a confirmed object. A vote is a "
    "volunteer's opinion, not a confirmation. The machine's group and order do not depend on votes. NEOWISE ended "
    "in 2024: it speaks to whether the object varies, not to this particular change."
)

_lock = threading.Lock()
_recent: dict[str, deque[float]] = defaultdict(deque)
_neowise_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="neowise")
_neowise_queued: set[str] = set()


class WatchlistError(Exception):
    """A request the watchlist refuses; `status` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------- the database

def db_path() -> Path:
    env = os.environ.get(DB_ENV)
    return Path(env) if env else spherex.CACHE / "watchlist" / "watchlist.sqlite3"


SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, grp TEXT NOT NULL, ra REAL NOT NULL, dec REAL NOT NULL,
    verdict TEXT, category TEXT, sigma_best REAL, sigma_combined REAL, n_detectors_5 INTEGER,
    machine TEXT NOT NULL, patches TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS candidates_group ON candidates (grp, kind);
CREATE TABLE IF NOT EXISTS votes (
    candidate_id TEXT NOT NULL, voter TEXT NOT NULL, answer TEXT NOT NULL, note TEXT, at TEXT NOT NULL,
    PRIMARY KEY (candidate_id, voter));
CREATE TABLE IF NOT EXISTS neowise (
    candidate_id TEXT PRIMARY KEY, state TEXT NOT NULL, reading TEXT, message TEXT, checked_at REAL NOT NULL,
    ra REAL, dec REAL);
"""


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- ingest

def candidate_id(kind: str, ra: float, dec: float, rejected: bool = False) -> str:
    """Stable id from the kind and the position of the first sighting."""
    place = f"{ra:08.4f}{'n' if dec >= 0 else 's'}{abs(dec):07.4f}"
    return f"{'set-aside-' if rejected else ''}{kind}-{place}"


def group_of(obj: dict[str, Any]) -> str:
    """The machine's group for an object the search reported as passed."""
    return "known" if obj["catalogue_status"]["category"] in KNOWN_CATEGORIES else "eyes"


_EVIDENCE_KEYS = ("detector", "id", "kind", "sigma", "grade", "flags", "reasons", "found_in",
                  "times_noise_all_visits", "typical_flux_mjy", "measure", "change", "two_out", "motion")
_VISIT_KEYS = ("epoch", "date_mean", "n_exposures", "times_noise", "empty_places_as_bright", "ra", "dec")
_OBJECT_KEYS = ("kind", "verdict", "flags", "ra", "dec", "sigma_best", "best_detector", "sigma_combined", "found_by",
                "detectors_at_5_sigma", "detectors_at_3_sigma", "motion_all_detectors")


def _trim_object(obj: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """What the page and the export need of one object the search found."""
    out: dict[str, Any] = {k: obj.get(k) for k in _OBJECT_KEYS}
    out["flags"] = list(obj.get("flags") or [])
    out["detectors_at_5_sigma"] = list(obj.get("detectors_at_5_sigma") or [])
    out["detectors_at_3_sigma"] = list(obj.get("detectors_at_3_sigma") or [])
    cat = dict(obj["catalogue_status"])
    cat["nearest"] = list(cat.get("nearest") or [])[:3]
    out["catalogue_status"] = cat
    ev = obj.get("evidence") or {}
    evidence = {k: ev[k] for k in _EVIDENCE_KEYS if k in ev}
    evidence["visits"] = [{k: v.get(k) for k in _VISIT_KEYS} for v in ev.get("visits") or []]
    out["evidence"] = evidence
    out["patch"] = patch
    return out


def _trim_rejected(item: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    return {"kind": item["kind"], "ra": item["ra"], "dec": item["dec"], "detector": item["detector"],
            "sigma": item["sigma"], "reasons": list(item.get("reasons") or []), "flags": list(item.get("flags") or []),
            "detectors": [item["detector"]], "patch": patch}


def _arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    e, n = astrometry.offset_arcsec(ra1, dec1, ra2, dec2)
    return math.hypot(e, n)


def _strength(machine: dict[str, Any]) -> float:
    value = machine.get("sigma_combined")
    if value is None:
        value = machine.get("sigma")
    return float(value or 0.0)


def _find_match(con: sqlite3.Connection, kind: str, rejected: bool, ra: float, dec: float) -> sqlite3.Row | None:
    margin = MATCH_ARCSEC / 3600.0 * 2
    rows = con.execute("SELECT * FROM candidates WHERE kind=? AND (grp='artefact')=? AND ABS(dec-?)<?",
                       (kind, int(rejected), dec, margin)).fetchall()
    near = [(r, _arcsec(ra, dec, r["ra"], r["dec"])) for r in rows]
    near = [(r, d) for r, d in near if d <= MATCH_ARCSEC]
    return min(near, key=lambda x: x[1])[0] if near else None


def _same_patch(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (abs(a["ra"] - b["ra"]) < 1e-6 and abs(a["dec"] - b["dec"]) < 1e-6 and abs(a["fov"] - b["fov"]) < 1e-6)


def _upsert(con: sqlite3.Connection, now: str, group: str, machine: dict[str, Any], patch: dict[str, Any]) -> str:
    kind, ra, dec = machine["kind"], float(machine["ra"]), float(machine["dec"])
    rejected = group == "artefact"
    seen = {"ra": patch["ra"], "dec": patch["dec"], "fov": patch["fov"], "detectors": patch["detectors"],
            "last_seen": now}
    row = _find_match(con, kind, rejected, ra, dec)
    if row is None:
        cid = candidate_id(kind, ra, dec, rejected)
        con.execute("INSERT INTO candidates (id, kind, grp, ra, dec, verdict, category, sigma_best, sigma_combined, "
                    "n_detectors_5, machine, patches, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, kind, group, ra, dec, machine.get("verdict"), _category(machine), machine.get("sigma_best"),
                     _strength(machine), len(machine.get("detectors_at_5_sigma") or []), json.dumps(machine),
                     json.dumps([seen]), now, now))
        return cid
    old = json.loads(row["machine"])
    patches = json.loads(row["patches"])
    again = next((p for p in patches if _same_patch(p, seen)), None)
    if again is not None:
        again.update(last_seen=now, detectors=seen["detectors"])
    else:
        patches.append(seen)
    if rejected:
        machine["detectors"] = sorted(set(old.get("detectors") or []) | set(machine["detectors"]))
        merged = machine if _strength(machine) >= _strength(old) else {**old, "detectors": machine["detectors"]}
        con.execute("UPDATE candidates SET machine=?, patches=?, sigma_combined=?, last_seen=? WHERE id=?",
                    (json.dumps(merged), json.dumps(patches), _strength(merged), now, row["id"]))
        return str(row["id"])
    # A search of the same patch again replaces what was stored; another patch only if it saw it more strongly.
    if again is not None or _strength(machine) >= _strength(old):
        con.execute("UPDATE candidates SET grp=?, ra=?, dec=?, verdict=?, category=?, sigma_best=?, sigma_combined=?, "
                    "n_detectors_5=?, machine=?, patches=?, last_seen=? WHERE id=?",
                    (group, ra, dec, machine.get("verdict"), _category(machine), machine.get("sigma_best"),
                     _strength(machine), len(machine.get("detectors_at_5_sigma") or []), json.dumps(machine),
                     json.dumps(patches), now, row["id"]))
    else:
        con.execute("UPDATE candidates SET patches=?, last_seen=? WHERE id=?", (json.dumps(patches), now, row["id"]))
    return str(row["id"])


def _category(machine: dict[str, Any]) -> str | None:
    return (machine.get("catalogue_status") or {}).get("category")


def ingest(result: dict[str, Any], *, queue_neowise: bool = True) -> dict[str, Any]:
    """Add or update one row per object and per rejected candidate of a finished `search.search()` result."""
    field = result["field"]
    patch = {"ra": float(field["ra"]), "dec": float(field["dec"]), "fov": float(field["fov"]),
             "detectors": [int(d) for d in field["detectors"]]}
    now = _now()
    ids: list[str] = []
    with _lock, _db() as con:
        before = con.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        for obj in result.get("objects", []):
            ids.append(_upsert(con, now, group_of(obj), _trim_object(obj, patch), patch))
        for item in result.get("rejected", []):
            ids.append(_upsert(con, now, "artefact", _trim_rejected(item, patch), patch))
        added = con.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] - before
    if queue_neowise:
        queue_neowise_checks()
    return {"ids": ids, "added": added, "seen": len(ids)}


def ingest_safely(result: dict[str, Any]) -> None:
    """For the search's own job: a failure here is logged and never fails the search."""
    try:
        ingest(result)
    except Exception:  # noqa: BLE001 - the search must finish whatever happens to the list
        log.exception("could not add a finished search to the watchlist")


# --------------------------------------------------------------------------- reading

def _order_key(row: dict[str, Any]) -> tuple[Any, ...]:
    if row["group"] == "artefact":
        return (-(row["sigma"] or 0.0), row["id"])
    return (row["verdict"] != "clean", -len(row["detectors_at_5_sigma"]), -(row["sigma_combined"] or 0.0),
            -(row["sigma_best"] or 0.0), row["id"])


def _tallies(con: sqlite3.Connection) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in con.execute("SELECT candidate_id, answer, COUNT(*) AS n FROM votes GROUP BY candidate_id, answer"):
        out.setdefault(r["candidate_id"], {})[r["answer"]] = r["n"]
    return out


def _votes(counts: dict[str, int] | None) -> dict[str, int]:
    counts = counts or {}
    out = {a: counts.get(a, 0) for a in ANSWERS}
    out["total"] = sum(out.values())
    return out


def _row(r: sqlite3.Row, tallies: dict[str, dict[str, int]], neo: dict[str, dict[str, Any]],
         mine: dict[str, str], notes: dict[str, list[str]]) -> dict[str, Any]:
    machine = json.loads(r["machine"])
    patches = json.loads(r["patches"])
    group = r["grp"]
    row: dict[str, Any] = {**machine, "id": r["id"], "group": group, "ra": r["ra"], "dec": r["dec"],
                           "first_seen": r["first_seen"], "last_seen": r["last_seen"], "patches": patches,
                           "votes": _votes(tallies.get(r["id"])), "my_vote": mine.get(r["id"]),
                           "notes": notes.get(r["id"], [])}
    if group != "artefact" and r["kind"] == "changer":
        row["neowise"] = neo.get(r["id"]) or {"state": "waiting"}
    if group == "artefact":
        row["best_detector"] = machine.get("detector")
    return row


def _neowise_all(con: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in con.execute("SELECT * FROM neowise"):
        if r["state"] == "ok":
            out[r["candidate_id"]] = {"state": "ok", **json.loads(r["reading"])}
        else:
            out[r["candidate_id"]] = {"state": "error", "message": r["message"]}
    return out


def _recent_notes(con: sqlite3.Connection, per: int = 3) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in con.execute("SELECT candidate_id, note FROM votes WHERE note IS NOT NULL AND note != '' ORDER BY at DESC"):
        got = out.setdefault(r["candidate_id"], [])
        if len(got) < per:
            got.append(r["note"])
    return out


def _mine(con: sqlite3.Connection, voter: str | None) -> dict[str, str]:
    if not voter:
        return {}
    return {r["candidate_id"]: r["answer"] for r in
            con.execute("SELECT candidate_id, answer FROM votes WHERE voter=?", (_hash(voter),))}


def _all_rows(con: sqlite3.Connection, voter: str | None, group: str | None, kind: str | None) -> list[dict[str, Any]]:
    sql, args = "SELECT * FROM candidates WHERE 1=1", []  # type: tuple[str, list[Any]]
    if group:
        sql, args = sql + " AND grp=?", [*args, group]
    if kind:
        sql, args = sql + " AND kind=?", [*args, kind]
    tallies, neo, mine, notes = _tallies(con), _neowise_all(con), _mine(con, voter), _recent_notes(con)
    rows = [_row(r, tallies, neo, mine, notes) for r in con.execute(sql, args)]
    for g in GROUPS:
        ranked = sorted((r for r in rows if r["group"] == g), key=_order_key)
        for n, r in enumerate(ranked, 1):
            r["rank_in_group"] = n
    return sorted(rows, key=lambda r: (GROUPS.index(r["group"]), r["rank_in_group"]))


def list_rows(group: str | None = None, kind: str | None = None, limit: int = 20, offset: int = 0,
              voter: str | None = None) -> dict[str, Any]:
    if group is not None and group not in GROUPS:
        raise WatchlistError(400, f"group must be one of {', '.join(GROUPS)}")
    if kind is not None and kind not in ("mover", "changer"):
        raise WatchlistError(400, "kind must be mover or changer")
    with _db() as con:
        rows = _all_rows(con, voter, group, kind)
        counts = {g: con.execute("SELECT COUNT(*) FROM candidates WHERE grp=?" + (" AND kind=?" if kind else ""),
                                 (g, kind) if kind else (g,)).fetchone()[0] for g in GROUPS}
        patches = {(p["ra"], p["dec"], p["fov"]) for r in con.execute("SELECT patches FROM candidates")
                   for p in json.loads(r["patches"])}
    return {"counts": counts, "total": len(rows), "offset": offset, "limit": limit, "patches_searched": len(patches),
            "rows": rows[offset:offset + limit], "about": ABOUT}


def get_row(cid: str, voter: str | None = None) -> dict[str, Any]:
    with _db() as con:
        if not con.execute("SELECT 1 FROM candidates WHERE id=?", (cid,)).fetchone():
            raise WatchlistError(404, "There is no such candidate on the list.")
        rows = _all_rows(con, voter, None, None)
    return next(r for r in rows if r["id"] == cid)


# --------------------------------------------------------------------------- votes

def _hash(voter: str) -> str:
    return hashlib.sha256(voter.encode()).hexdigest()


_VOTER = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def clean_note(note: str | None) -> str | None:
    """Plain text: control characters become spaces, at most NOTE_MAX characters, empty becomes none."""
    if note is None:
        return None
    text = re.sub(r"\s+", " ", "".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in note)).strip()
    if len(text) > NOTE_MAX:
        raise WatchlistError(400, f"A note can be at most {NOTE_MAX} characters.")
    return text or None


def vote(cid: str, answer: str, note: str | None, voter: str, *, now: float | None = None) -> dict[str, Any]:
    """Record a voter's opinion on a candidate, replacing their earlier one. Returns the new tallies."""
    if answer not in ANSWERS:
        raise WatchlistError(400, f"The answer must be one of: {', '.join(ANSWERS)}.")
    if not _VOTER.match(voter or ""):
        raise WatchlistError(400, "The voter id must be 16 to 64 letters, digits, dashes or underscores.")
    text = clean_note(note)
    stamp = time.monotonic() if now is None else now
    key = _hash(voter)
    with _lock:
        recent = _recent[key]
        while recent and stamp - recent[0] > VOTE_WINDOW_S:
            recent.popleft()
        if len(recent) >= MAX_VOTES:
            raise WatchlistError(429, f"That is a lot of votes at once: please wait a minute (at most {MAX_VOTES} "
                                      f"votes per {int(VOTE_WINDOW_S)} seconds).")
        with _db() as con:
            if not con.execute("SELECT 1 FROM candidates WHERE id=?", (cid,)).fetchone():
                raise WatchlistError(404, "There is no such candidate on the list.")
            con.execute("INSERT INTO votes (candidate_id, voter, answer, note, at) VALUES (?,?,?,?,?) "
                        "ON CONFLICT (candidate_id, voter) DO UPDATE SET answer=excluded.answer, note=excluded.note, "
                        "at=excluded.at", (cid, key, answer, text, _now()))
            tally = _tallies(con).get(cid)
        recent.append(stamp)
    return {"id": cid, "votes": _votes(tally), "my_vote": answer, "note": text}


# --------------------------------------------------------------------------- NEOWISE in the background

def _changers_to_check(con: sqlite3.Connection) -> list[sqlite3.Row]:
    done = {r["candidate_id"]: r for r in con.execute("SELECT * FROM neowise")}
    out = []
    for r in con.execute("SELECT id, ra, dec FROM candidates WHERE kind='changer' AND grp IN ('eyes','known')"):
        old = done.get(r["id"])
        if old is None or (old["state"] != "ok" and time.time() - old["checked_at"] > NEOWISE_RETRY_S):
            out.append(r)
    return out


def check_neowise(cid: str) -> dict[str, Any]:
    """Ask NEOWISE about one candidate now (one request) and store the answer or the failure."""
    with _db() as con:
        r = con.execute("SELECT ra, dec FROM candidates WHERE id=?", (cid,)).fetchone()
    if r is None:
        raise WatchlistError(404, "There is no such candidate on the list.")
    try:
        got = neowise.read_spot(r["ra"], r["dec"])
        state, message, payload = "ok", None, json.dumps(got)
    except Exception as e:  # noqa: BLE001 - the archive being down is stored as "could not ask", not raised
        log.warning("NEOWISE question for %s failed: %s", cid, e)
        state, message, payload = "error", f"NEOWISE's archive did not answer: {e}", None
    with _lock, _db() as con:
        con.execute("INSERT INTO neowise (candidate_id, state, reading, message, checked_at, ra, dec) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT (candidate_id) DO UPDATE SET state=excluded.state, "
                    "reading=excluded.reading, message=excluded.message, checked_at=excluded.checked_at, "
                    "ra=excluded.ra, dec=excluded.dec", (cid, state, payload, message, time.time(), r["ra"], r["dec"]))
    return {"state": state, "message": message}


def _neowise_task(cid: str) -> None:
    try:
        check_neowise(cid)
    except Exception:  # noqa: BLE001 - a background question must never raise into the pool
        log.exception("NEOWISE check of %s failed", cid)
    finally:
        _neowise_queued.discard(cid)


def queue_neowise_checks() -> int:
    """Queue, one at a time in the background, every changer that has no NEOWISE answer yet."""
    with _db() as con:
        todo = [r["id"] for r in _changers_to_check(con)]
    queued = 0
    for cid in todo:
        if cid not in _neowise_queued:
            _neowise_queued.add(cid)
            _neowise_pool.submit(_neowise_task, cid)
            queued += 1
    return queued


def neowise_now(limit: int | None = None) -> int:
    """Ask NEOWISE about every changer still without an answer, in this thread, one at a time."""
    with _db() as con:
        todo = [r["id"] for r in _changers_to_check(con)]
    for cid in todo[:limit]:
        check_neowise(cid)
    return len(todo[:limit])


# --------------------------------------------------------------------------- export

COLUMNS: dict[str, str] = {
    "id": "Stable identifier of the candidate (its kind and the position where it was first seen)",
    "list_group": "needs_eyes, already_known or set_aside_as_artefact: decided by the machine, never by votes",
    "rank_in_group": "Position in its group by the machine's order (clean before caution, more detectors at 5 times "
                     "the noise first, then strength)",
    "kind": "moved (changed position between visits) or changed_brightness",
    "ra_deg": "Right ascension in degrees (ICRS), measured by the search",
    "dec_deg": "Declination in degrees (ICRS), measured by the search",
    "machine_verdict": "clean (no caution flag), caution (flags a person should look at) or rejected (artefact)",
    "machine_flags": "The search's caution flags (for example saturated, blended, halo), separated by spaces",
    "strength_best_detector_times_noise": "Strength in its best detector, as times the noise of empty places in the "
                                          "same picture",
    "strength_all_detectors_times_noise": "Strength with the detectors put together, in times the noise",
    "best_detector": "SPHEREx detector (1 to 6, 0.75 to 5.0 micrometres) in which it was strongest",
    "detectors_at_5_times_noise": "Detectors in which it reached 5 times the noise or more on its own",
    "speed_arcsec_per_year": "Movers: measured speed in arcseconds a year",
    "direction_deg_east_of_north": "Movers: heading, degrees east of north",
    "brightness_ratio_later_over_earlier": "Brightness changes: how many times as bright it was in the later of the "
                                           "two compared visits (below 1 means fainter)",
    "change_earlier_visit": "Brightness changes: date of the earlier visit compared",
    "change_later_visit": "Brightness changes: date of the later visit compared",
    "catalogue_status": "What the catalogues that answered say, as a category (for example known_variable, "
                        "changer_not_listed_as_variable)",
    "catalogue_summary": "The same in words",
    "catalogues_answered": "Catalogues that answered",
    "catalogues_did_not_answer": "Catalogues that did not answer (nothing was checked against them)",
    "nearest_catalogue_object": "Nearest catalogued object: catalogue, name and separation",
    "set_aside_reasons": "Set aside as artefacts: why the search rejected it",
    "neowise_reading": "NEOWISE's second opinion on brightness changes: changed, steady, cannot_say, or "
                       "not_checked_yet (NEOWISE ended in 2024: it speaks to whether the object varies, not to this "
                       "change)",
    "neowise_visits": "Number of NEOWISE visits within 1.5 arcsec, 2014 to 2024",
    "neowise_4p6um_faintest_mjy": "Faintest NEOWISE visit at 4.6 micrometres, millijanskys",
    "neowise_4p6um_brightest_mjy": "Brightest NEOWISE visit at 4.6 micrometres, millijanskys",
    "neowise_4p6um_factor": "Brightest divided by faintest at 4.6 micrometres",
    "neowise_3p4um_faintest_mjy": "Faintest NEOWISE visit at 3.4 micrometres, millijanskys",
    "neowise_3p4um_brightest_mjy": "Brightest NEOWISE visit at 3.4 micrometres, millijanskys",
    "neowise_3p4um_factor": "Brightest divided by faintest at 3.4 micrometres",
    "neowise_max_saturated_share": "Largest share of saturated pixels NEOWISE reported in a visit (0 to 1)",
    "neowise_sentence": "The reading in one sentence",
    "votes_real": "Volunteers who voted real (an opinion, not a confirmation)",
    "votes_artefact": "Volunteers who voted artefact",
    "votes_unsure": "Volunteers who voted unsure",
    "votes_total": "All votes",
    "first_seen_by_search": "When a search first reported it (UTC)",
    "last_seen_by_search": "When a search last reported it (UTC)",
    "patches_searched": "How many searched patches of sky reported it",
    "viewer_link": "Opens the SPHEREx viewer centred on it, in its best detector",
}


def _join(items: Any) -> str:
    return " ".join(str(i) for i in items or [])


def export_rows(base_url: str = "") -> list[dict[str, Any]]:
    """One flat row per candidate, in the order of the page (needs eyes, already known, set aside)."""
    with _db() as con:
        rows = _all_rows(con, None, None, None)
    return [_flat(r, base_url.rstrip("/")) for r in rows]


def _flat(r: dict[str, Any], base: str) -> dict[str, Any]:
    cat = r.get("catalogue_status") or {}
    ev = r.get("evidence") or {}
    neo = r.get("neowise") or {}
    ok = neo.get("state") == "ok"
    w1, w2 = (neo.get("w1") or {}) if ok else {}, (neo.get("w2") or {}) if ok else {}
    motion, change = ev.get("motion") or {}, ev.get("change") or {}
    visits = ev.get("visits") or []
    bins = change.get("bins") or []
    nearest = (cat.get("nearest") or [None])[0]
    best = r.get("best_detector") or 5
    detectors_at_5 = r.get("detectors_at_5_sigma")
    if r["kind"] == "changer":
        reading = neo["reading"] if ok else "not_checked_yet" if r["group"] != "artefact" else ""
    else:
        reading = ""
    out: dict[str, Any] = {
        "id": r["id"], "list_group": GROUP_NAMES[r["group"]], "rank_in_group": r["rank_in_group"],
        "kind": "moved" if r["kind"] == "mover" else "changed_brightness",
        "ra_deg": round(r["ra"], 6), "dec_deg": round(r["dec"], 6),
        "machine_verdict": "rejected" if r["group"] == "artefact" else r.get("verdict"),
        "machine_flags": _join(r.get("flags")),
        "strength_best_detector_times_noise": r.get("sigma_best") if r["group"] != "artefact" else r.get("sigma"),
        "strength_all_detectors_times_noise": r.get("sigma_combined"),
        "best_detector": best, "detectors_at_5_times_noise": _join(detectors_at_5),
        "speed_arcsec_per_year": motion.get("speed"),
        "direction_deg_east_of_north": motion.get("direction_deg_east_of_north"),
        "brightness_ratio_later_over_earlier": change.get("ratio"),
        "change_earlier_visit": visits[bins[0]]["date_mean"] if len(bins) == 2 and len(visits) > max(bins) else None,
        "change_later_visit": visits[bins[1]]["date_mean"] if len(bins) == 2 and len(visits) > max(bins) else None,
        "catalogue_status": cat.get("category"), "catalogue_summary": cat.get("summary"),
        "catalogues_answered": _join(cat.get("answered")),
        "catalogues_did_not_answer": _join((cat.get("did_not_answer") or {}).keys()),
        "nearest_catalogue_object": (f"{nearest.get('catalogue')}: {nearest.get('name')} "
                                     f"({nearest.get('separation_arcsec')} arcsec)") if nearest else None,
        "set_aside_reasons": " | ".join(r.get("reasons") or []) if r["group"] == "artefact" else None,
        "neowise_reading": reading, "neowise_visits": neo.get("n_visits") if ok else None,
        "neowise_4p6um_faintest_mjy": w2.get("faintest_mjy"), "neowise_4p6um_brightest_mjy": w2.get("brightest_mjy"),
        "neowise_4p6um_factor": w2.get("factor"),
        "neowise_3p4um_faintest_mjy": w1.get("faintest_mjy"), "neowise_3p4um_brightest_mjy": w1.get("brightest_mjy"),
        "neowise_3p4um_factor": w1.get("factor"),
        "neowise_max_saturated_share": max([b["saturated_share_max"] for b in (w1, w2) if b], default=None),
        "neowise_sentence": neo.get("sentence") if ok else None,
        "votes_real": r["votes"]["real"], "votes_artefact": r["votes"]["artefact"],
        "votes_unsure": r["votes"]["unsure"], "votes_total": r["votes"]["total"],
        "first_seen_by_search": r["first_seen"], "last_seen_by_search": r["last_seen"],
        "patches_searched": len(r["patches"]),
        "viewer_link": f"{base}/?ra={r['ra']:.6f}&dec={r['dec']:.6f}&fov={VIEWER_FOV}&det={best}&mode=normal",
    }
    assert list(out) == list(COLUMNS), "export columns and their descriptions must match"
    return out


def export_csv(base_url: str = "") -> str:
    """The whole list as CSV, with a header of comment lines (starting with #) saying what it is."""
    buf = io.StringIO()
    buf.write(f"# {ABOUT}\n# Exported {_now()}. One row per candidate. Columns:\n")
    for name, text in COLUMNS.items():
        buf.write(f"#   {name}: {text}\n")
    buf.write("# Read with a '#' comment character, for example pandas.read_csv(path, comment='#').\n")
    writer = csv.DictWriter(buf, fieldnames=list(COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in export_rows(base_url):
        writer.writerow({k: "" if v is None else v for k, v in row.items()})
    return buf.getvalue()


def export_json(base_url: str = "") -> dict[str, Any]:
    return {"about": ABOUT, "exported": _now(), "columns": COLUMNS, "candidates": export_rows(base_url)}

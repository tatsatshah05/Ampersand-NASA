"""Keeping an eye on a patch of sky.

A patch (a centre and a width, exactly as a blind search was asked for them) is watched once
it has been searched. A small note says when that was and how many exposures NASA's archive
listed for the place at that moment. When the archive lists a different number, there are
pictures the last search did not have: `state` then says `new_pictures`, and the next request
to /api/search for the patch searches it again (backend/jobs.py).

Nothing runs on a timer. The question is asked whenever somebody opens the patch, and
`spherex.list_changed` asks the archive at most once a day and never makes a visitor wait for
its answer. SPHEREx returns to a patch about every six months, so new pictures are rare.

The notes are files under cache/search2/watch/, one per patch, named by the patch's key (the
same key /api/watchlist/regions uses). A patch searched before notes were kept, which is every
patch in the deployed site's pre-built results, gets its note the first time it is looked at:
from then on new pictures are noticed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from astropy.time import Time

from . import search, spherex, watchlist

log = logging.getLogger("backend.watch")

WATCH_DIR = search.SEARCH_DIR / "watch"


def key(ra: float, dec: float, fov: float) -> str:
    return watchlist.region_key({"ra": ra, "dec": dec, "fov": fov})


def _file(ra: float, dec: float, fov: float) -> Path:
    return WATCH_DIR / f"{key(ra, dec, fov)}.json"


def record(ra: float, dec: float, fov: float, last_searched: str | None = None,
           listed: list[dict] | None = None) -> dict[str, Any]:
    """Note that the patch has been searched (now, unless told when) and how many pictures the archive listed.

    Without `listed` the list is `spherex.find_exposures`, the call the search itself made a moment ago and
    the one `spherex.list_changed` will compare the count with: counted from anything else, a patch whose
    two counts differ would be searched again on every request.
    """
    if listed is None:
        listed = spherex.find_exposures(ra, dec)
    note = {"key": key(ra, dec, fov), "ra": ra, "dec": dec, "fov": fov,
            "last_searched": last_searched or watchlist._now(),
            "pictures_until": Time(max(e["mjd"] for e in listed), format="mjd").iso[:10] if listed else None,
            "exposures": len(listed) or None}
    spherex.write_json(_file(ra, dec, fov), note)
    return note


def record_safely(ra: float, dec: float, fov: float) -> None:
    """For the search's own job: a failure here is logged and never fails the search."""
    try:
        record(ra, dec, fov)
    except Exception:  # noqa: BLE001 - the search must finish whatever happens to the note
        log.exception("could not note that the patch %s was searched", key(ra, dec, fov))


def _note(ra: float, dec: float, fov: float) -> dict[str, Any] | None:
    """The patch's note; made now for a patch that is in the list of finds without one; None if never searched."""
    file = _file(ra, dec, fov)
    if file.exists():
        try:
            return json.loads(file.read_text())
        except ValueError:
            log.warning("unreadable note %s: made again", file.name)
    patch = watchlist.searched_patch(key(ra, dec, fov))
    if not patch:
        return None
    # A visitor is waiting, so the archive is not asked: the list as it is on disk, whatever its age.
    return record(ra, dec, fov, patch["last_searched"], search._exposures(ra, dec, offline=True))


def state(ra: float, dec: float, fov: float) -> dict[str, Any]:
    """Whether the patch is watched, when it was last searched, and whether the archive has new pictures of it."""
    note = _note(ra, dec, fov)
    if note is None:
        return {"key": key(ra, dec, fov), "ra": ra, "dec": dec, "fov": fov, "searched": False,
                "last_searched": None, "pictures_until": None, "exposures": None, "new_pictures": False}
    return {**note, "searched": True, "new_pictures": spherex.list_changed(ra, dec, note["exposures"])}


def patches() -> dict[str, dict[str, Any]]:
    """Every watched patch by key: centre, width and when it was last searched. Unreadable notes are left out."""
    out: dict[str, dict[str, Any]] = {}
    for file in sorted(WATCH_DIR.glob("*.json")):
        try:
            note = json.loads(file.read_text())
            out[str(note["key"])] = {"ra": float(note["ra"]), "dec": float(note["dec"]), "fov": float(note["fov"]),
                                     "last_searched": note.get("last_searched")}
        except (ValueError, KeyError, TypeError):
            log.warning("unreadable note %s: left out of the list of patches", file.name)
    return out


def new_pictures(ra: float, dec: float, fov: float) -> bool:
    """Does the archive list pictures of this watched patch that its last search did not have? Never raises."""
    try:
        return bool(state(ra, dec, fov)["new_pictures"])
    except Exception:  # noqa: BLE001 - a broken note must not stop a search from being answered
        log.exception("could not tell whether the patch %s has new pictures", key(ra, dec, fov))
        return False

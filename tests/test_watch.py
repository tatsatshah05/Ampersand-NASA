"""Keeping an eye on a patch of sky: backend/watch.py, /api/watch and the search job, offline.

A patch is watched once it has been searched. What is checked here: the note made after a
search (when, and how many pictures the archive listed), that more pictures in the archive
are noticed, that the next request then searches the patch again with them, and that a patch
searched before these notes existed (every patch in the deployed site's pre-built results) is
taken on from the list of finds.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import jobs, search, spherex, watch, watchlist

FIXTURES = Path(__file__).resolve().parent.parent / "frontend" / "src" / "fixtures" / "search"
NOBODY = {"last_searched": None, "pictures_until": None, "exposures": None, "new_pictures": False}


@pytest.fixture(autouse=True)
def own_list_and_no_old_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> None:
    """Each test has its own list of finds, and starts with no note and no finished search of any patch."""
    monkeypatch.setenv(watchlist.DB_ENV, str(tmp_path / "w.sqlite3"))
    monkeypatch.setattr(jobs, "_jobs", {})
    for old in [*(cache_dir / "search2" / "watch").glob("*.json"), *(cache_dir / "search2" / "results").glob("*.json")]:
        old.unlink()


def the_archive_lists(monkeypatch: pytest.MonkeyPatch, exposures: list[dict]) -> None:
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec, *_, **__: exposures)
    monkeypatch.setattr(search, "_exposures", lambda ra, dec, offline: exposures)


def without_the_last_visit_of_detector_5(barnard: SimpleNamespace) -> list[dict]:
    """The exposures on disk as the archive would have listed them before detector 5's third visit."""
    newest = sorted((e for e in barnard.exposures_on_disk if e["detector"] == 5), key=lambda e: e["mjd"])[-3:]
    return [e for e in barnard.exposures_on_disk if e not in newest]


def search_until_done(client: TestClient, params: dict) -> tuple[dict, list[dict]]:
    """Ask /api/search until it has finished. Returns the last answer and every answer on the way."""
    answers = []
    deadline = time.time() + 120
    while time.time() < deadline:
        answers.append(client.get("/api/search", params=params).json())
        if answers[-1]["status"] in ("done", "failed"):
            break
        time.sleep(0.3)
    assert answers[-1]["status"] == "done", answers[-1].get("error")
    return answers[-1], answers


def test_a_patch_nobody_has_searched_is_not_watched(client: TestClient):
    body = client.get("/api/watch", params={"ra": 10.0, "dec": 10.0}).json()
    assert body == {"key": "10.000000_10.000000_0.1000", "ra": 10.0, "dec": 10.0, "fov": 0.1, "searched": False, **NOBODY}


def test_the_note_after_a_search_says_when_and_with_which_pictures(barnard: SimpleNamespace,
                                                                  monkeypatch: pytest.MonkeyPatch):
    the_archive_lists(monkeypatch, barnard.exposures_on_disk)
    before = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    watch.record(barnard.ra, barnard.dec, 0.1)
    state = watch.state(barnard.ra, barnard.dec, 0.1)
    assert state["searched"] is True and state["new_pictures"] is False
    assert state["exposures"] == 311             # 364 listed, less the 53 detector 5 cutouts not in the repository
    assert state["pictures_until"] == "2026-09-22"      # the last exposure of Barnard's Star in the archive's list
    assert before <= state["last_searched"] <= time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def test_more_pictures_in_the_archive_are_noticed(barnard: SimpleNamespace, monkeypatch: pytest.MonkeyPatch):
    the_archive_lists(monkeypatch, without_the_last_visit_of_detector_5(barnard))
    watch.record(barnard.ra, barnard.dec, 0.1)
    assert watch.state(barnard.ra, barnard.dec, 0.1)["new_pictures"] is False
    the_archive_lists(monkeypatch, barnard.exposures_on_disk)          # three more exposures have arrived
    state = watch.state(barnard.ra, barnard.dec, 0.1)
    assert state["new_pictures"] is True
    assert state["exposures"] == 308             # still what the last search had


def test_the_next_request_searches_again_with_the_new_pictures(client: TestClient, barnard: SimpleNamespace,
                                                              monkeypatch: pytest.MonkeyPatch):
    params = {"ra": barnard.ra, "dec": barnard.dec, "detectors": "5"}
    the_archive_lists(monkeypatch, without_the_last_visit_of_detector_5(barnard))
    first, answers = search_until_done(client, params)
    assert first["result"]["summary"]["exposures"] == {"5": 6}
    assert not any(a["searching_again"] for a in answers)
    watched = client.get("/api/watch", params=params).json()
    assert (watched["searched"], watched["exposures"], watched["new_pictures"]) == (True, 308, False)

    the_archive_lists(monkeypatch, barnard.exposures_on_disk)          # the third visit has arrived
    assert client.get("/api/watch", params=params).json()["new_pictures"] is True
    second, answers = search_until_done(client, params)
    assert all(a["searching_again"] for a in answers)
    assert second["result"]["summary"]["exposures"] == {"5": 9}       # searched afresh, not answered from the old result
    watched = client.get("/api/watch", params=params).json()
    assert (watched["exposures"], watched["new_pictures"]) == (311, False)

    # Nothing new since: the finished search answers at once, and no third one is started.
    third, answers = search_until_done(client, params)
    assert len(answers) == 1 and third["seconds"] == second["seconds"] and third["result"] == second["result"]


def test_a_patch_searched_before_notes_were_kept_is_taken_on(client: TestClient, barnard: SimpleNamespace,
                                                             monkeypatch: pytest.MonkeyPatch):
    """The deployed site's pre-built results hold the list of finds but no notes: the first look makes one."""
    result = copy.deepcopy(json.loads((FIXTURES / "barnard.json").read_text())["result"])
    watchlist.ingest(result, queue_neowise=False)
    field = result["field"]
    params = {"ra": field["ra"], "dec": field["dec"], "fov": field["fov"]}
    the_archive_lists(monkeypatch, without_the_last_visit_of_detector_5(barnard))
    taken_on = client.get("/api/watch", params=params).json()
    assert taken_on["searched"] is True and taken_on["new_pictures"] is False
    assert taken_on["exposures"] == 308 and taken_on["last_searched"] is not None

    the_archive_lists(monkeypatch, barnard.exposures_on_disk)          # from then on, new pictures are noticed
    assert client.get("/api/watch", params=params).json()["new_pictures"] is True


def test_a_watched_patch_with_no_finds_stays_in_the_list_of_patches(client: TestClient, barnard: SimpleNamespace,
                                                                   monkeypatch: pytest.MonkeyPatch):
    """Somebody picked a quiet patch: it must still be there to come back to, with nothing in it."""
    the_archive_lists(monkeypatch, barnard.exposures_on_disk)
    watch.record(200.0, 30.0, 0.1)
    regions = client.get("/api/watchlist/regions").json()
    assert regions["patches_searched"] == 1
    (mine,) = regions["regions"]
    assert (mine["key"], mine["ra"], mine["dec"], mine["fov"]) == ("200.000000_30.000000_0.1000", 200.0, 30.0, 0.1)
    assert mine["count"] == 0 and mine["counts"] == {"eyes": 0, "known": 0, "artefact": 0}
    assert mine["last_searched"] is not None and mine["constellation"]
    rows = client.get("/api/watchlist", params={"region": mine["key"]}).json()
    assert (rows["total"], rows["rows"], rows["region"]) == (0, [], mine["key"])
    # A patch nobody has searched is still refused.
    assert client.get("/api/watchlist", params={"region": "1.000000_1.000000_0.1000"}).status_code == 404

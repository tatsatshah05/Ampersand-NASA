"""The background runner behind /api/search, on the real Barnard's Star cutouts, offline.

With the network blocked no catalogue answers, so what the search concludes is not
checked here (docs/search.md records that, from runs against the live services). These
tests check the plumbing: a search starts once, reports where it stands, ends as "done"
with the documented parts, and bad requests are explained.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import jobs, spherex


@pytest.mark.parametrize("text, expected", [("123456", (1, 2, 3, 4, 5, 6)), ("5", (5,)), ("6,5", (5, 6)), ("55", (5,))])
def test_detector_lists_are_read(text: str, expected: tuple[int, ...]):
    assert jobs.parse_detectors(text) == expected


@pytest.mark.parametrize("text", ["", "7", "5a", "0"])
def test_a_bad_detector_list_is_explained(client: TestClient, text: str):
    response = client.get("/api/search", params={"ra": 10.0, "dec": 10.0, "detectors": text})
    assert response.status_code == 400 and "detectors must be" in response.json()["detail"]


def test_a_search_starts_once_and_ends_with_the_documented_parts(client: TestClient, barnard: SimpleNamespace,
                                                                 monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)
    params = {"ra": barnard.ra, "dec": barnard.dec, "detectors": "5"}
    seen = []
    deadline = time.time() + 120
    while time.time() < deadline:
        body = client.get("/api/search", params=params).json()
        seen.append(body["status"])
        if body["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert body["status"] == "done", body.get("error")
    assert set(seen) <= {"queued", "running", "done"}
    assert body["detectors_done"] == body["detectors_total"] == 1
    result = body["result"]
    assert {"field", "objects", "rejected", "summary", "limits"} <= set(result)
    assert result["summary"]["exposures"] == {"5": 9}          # the nine cutouts in the repository
    # Nothing answered, and the result says so instead of calling anything uncatalogued.
    assert result["summary"]["catalogues_answered"] == []
    again = client.get("/api/search", params=params).json()      # the same search, not a second one
    assert again["status"] == "done" and again["result"] == result

"""backend/app.py through FastAPI's test client: what is refused, and what a caller is told
when the archive is down.

A refused request must be a client error (400 or 422; which of the two is not pinned,
because FastAPI's own checks answer 422 and the pipeline's answer 400) and must be turned
away before anything is asked of the archive. Successful requests on real data are in
test_end_to_end.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import astrometry

HERE = {"ra": 269.446267, "dec": 4.768222}       # a valid position (Barnard's Star)


def test_the_documented_endpoints_exist(client: TestClient):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/api/resolve", "/api/frames", "/api/lightcurve", "/api/spectrum"} <= paths


BAD_REQUESTS: list[tuple[str, dict[str, object]]] = [
    # /api/frames: the position
    ("/api/frames", {}),
    ("/api/frames", {"ra": 269.446267}),
    ("/api/frames", {"dec": 4.768222}),
    ("/api/frames", {**HERE, "ra": -0.1}),
    ("/api/frames", {**HERE, "ra": 360}),
    ("/api/frames", {**HERE, "ra": "17h57m"}),            # sexagesimal is for the page to convert
    ("/api/frames", {**HERE, "dec": -90.1}),
    ("/api/frames", {**HERE, "dec": 90.1}),
    # /api/frames: field of view (more than 0.02, at most 0.5 degrees) and detector (1 to 6)
    ("/api/frames", {**HERE, "fov": 0}),
    ("/api/frames", {**HERE, "fov": 0.02}),
    ("/api/frames", {**HERE, "fov": 0.51}),
    ("/api/frames", {**HERE, "detector": 0}),
    ("/api/frames", {**HERE, "detector": 7}),
    ("/api/frames", {**HERE, "detector": 2.5}),
    # /api/frames: options
    ("/api/frames", {**HERE, "mode": "blink"}),
    ("/api/frames", {**HERE, "mode": "difference", "reference": "median"}),
    ("/api/frames", {**HERE, "mode": "sum", "track": "comet"}),
    ("/api/frames", {**HERE, "pmra": -801.55}),            # a proper motion needs both components
    ("/api/frames", {**HERE, "pmdec": 10362.39}),
    ("/api/frames", {**HERE, "pmra": -801.55, "pmdec": 10362.39, "pm_epoch": 1900}),
    # /api/lightcurve and /api/spectrum
    ("/api/lightcurve", {"ra": 269.446267}),
    ("/api/lightcurve", {**HERE, "dec": 91}),
    ("/api/lightcurve", {**HERE, "detector": 0}),
    ("/api/lightcurve", {**HERE, "detector": 7}),
    ("/api/lightcurve", {**HERE, "pmdec": 10362.39}),
    ("/api/spectrum", {"dec": 4.768222}),
    ("/api/spectrum", {**HERE, "epoch": 0}),
    ("/api/spectrum", {**HERE, "epoch": "first"}),
    ("/api/spectrum", {**HERE, "detector": 9}),
    # /api/resolve: a name of 1 to 80 characters
    ("/api/resolve", {}),
    ("/api/resolve", {"name": ""}),
    ("/api/resolve", {"name": "x" * 81}),
]


def as_typed(case: tuple[str, dict[str, object]]) -> str:
    """A bad request the way it would be typed, to name its test: frames?ra=...&dec=..."""
    path, params = case
    return f"{path.removeprefix('/api/')}?{'&'.join(f'{k}={v}' for k, v in params.items())}"[:70]


@pytest.mark.parametrize(("path", "params"), BAD_REQUESTS, ids=[as_typed(case) for case in BAD_REQUESTS])
def test_bad_requests_are_refused_before_the_archive_is_asked(client: TestClient, network: list[str],
                                                              path: str, params: dict):
    response = client.get(path, params=params)
    assert response.status_code in (400, 422), response.text
    assert response.json()["detail"], "the caller should be told what was wrong"
    assert network == []


@pytest.mark.parametrize(("path", "params"), [
    ("/api/frames", {"ra": 0, "dec": -90, "fov": 0.5, "detector": 1}),
    ("/api/frames", {"ra": 359.999, "dec": 90, "fov": 0.021, "detector": 6, "mode": "sum", "track": "target",
                     "pmra": 0, "pmdec": 0, "pm_epoch": 1990}),
    ("/api/lightcurve", {"ra": 0, "dec": 90, "detector": 6}),
    ("/api/spectrum", {"ra": 123.4, "dec": -56.7, "epoch": 1, "detector": 1}),
])
def test_requests_at_the_limits_are_accepted_and_a_dead_archive_is_a_502(client: TestClient, network: list[str],
                                                                         path: str, params: dict):
    """Nothing is cached for these positions, so the request gets as far as asking the archive."""
    response = client.get(path, params=params)
    assert response.status_code == 502, response.text
    assert response.json()["detail"]
    assert network, "the archive should have been asked"


@pytest.mark.parametrize(("path", "module", "function"), [
    ("/api/frames", "pipeline", "build_frames"),
    ("/api/stars", "stars", "field_stars"),
    ("/api/lightcurve", "photometry", "lightcurve"),
    ("/api/spectrum", "photometry", "spectrum"),
    ("/api/resolve", "astrometry", "resolve_name"),
])
def test_a_fault_of_the_server_is_a_500_with_a_plain_message(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                             caplog: pytest.LogCaptureFixture,
                                                             path: str, module: str, function: str):
    """A numerical failure inside the server is not the caller's fault: not a 400, and no raw message."""
    import backend

    def broken(*args: object, **kwargs: object) -> None:
        raise ValueError("Singular matrix: numpy.linalg.LinAlgError in lstsq")

    monkeypatch.setattr(getattr(backend, module), function, broken)
    params = {"name": "Barnard's Star"} if path == "/api/resolve" else HERE
    with caplog.at_level("ERROR", logger="backend.app"):
        response = client.get(path, params=params)
    assert response.status_code == 500, response.text
    detail = response.json()["detail"]
    assert "went wrong on the server" in detail and "numpy" not in detail and "Singular" not in detail
    assert "Singular matrix" in caplog.text                    # the full story is in the server's log


def test_an_impossible_request_is_a_400_with_its_reason(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from backend import photometry, spherex

    def refuse(*args: object, **kwargs: object) -> None:
        raise spherex.BadRequest("epoch must be one of [1, 2, 3]")

    monkeypatch.setattr(photometry, "spectrum", refuse)
    response = client.get("/api/spectrum", params={**HERE, "epoch": 9})
    assert response.status_code == 400 and response.json()["detail"] == "epoch must be one of [1, 2, 3]"
    # Still a ValueError, so code that called the backend directly and caught that keeps working.
    assert issubclass(spherex.BadRequest, ValueError)


def test_resolve_answers_from_the_cache(client: TestClient, network: list[str], barnard):
    """The real answer for "Barnard's Star" is in the test cache; spelling it differently finds it too."""
    response = client.get("/api/resolve", params={"name": "Barnard's Star"}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    # The page may be served from somewhere else (Vite's dev server, or a file opened from disk).
    assert response.headers["access-control-allow-origin"] == "*"
    found = response.json()
    assert (found["ra"], found["dec"], found["epoch"]) == (barnard.ra, barnard.dec, 2026.0)
    assert (found["pmra"], found["pmdec"], found["parallax"]) == pytest.approx((-801.551, 10362.394, 546.976), abs=1e-3)
    assert found["source"] == "Gaia DR3"
    for field in ("catalogue", "j2000", "moved_since_2000_arcsec", "notes"):
        assert field in found

    assert client.get("/api/resolve", params={"name": "  barnard's   STAR "}).json() == found
    assert network == []


def test_resolve_says_404_for_a_name_simbad_does_not_know(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(astrometry, "_simbad", lambda adql: [])
    response = client.get("/api/resolve", params={"name": "No Such Star 12345"})
    assert response.status_code == 404
    assert "No Such Star 12345" in response.json()["detail"]


def test_resolve_says_502_when_simbad_is_down(client: TestClient, network: list[str]):
    response = client.get("/api/resolve", params={"name": "Epsilon Indi B"})
    assert response.status_code == 502
    assert set(network) == set(astrometry.SIMBAD_TAP)          # both mirrors were tried

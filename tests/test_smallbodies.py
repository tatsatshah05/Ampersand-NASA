"""backend/smallbodies.py and /api/smallbodies, offline, from real JPL answers kept in tests/data.

The saved answers were fetched on 2026-11-14 for three real SPHEREx detector 5 exposures of
the field around asteroid 4 Vesta (view centre RA 23.35591, Dec 1.50056, field 0.1 degree),
by calling find_crossings with an empty cache:
  tests/data/cache/smallbodies/jpl/*.json   one sb_ident answer (7 known bodies in the widened
                                            field) and five Horizons ephemerides, as JPL sent them
  tests/data/smallbodies_exposures.json     the three exposures (IRSA's own rows)
  tests/data/cache/queries/sia_4a58...json  IRSA's detector 5 exposure list for the field
  tests/data/cache/cutouts/41302e8fb3/      three real cutouts: two in which Vesta is predicted
                                            (2026-07-16) and one of an earlier visit (2025-07-15)
The code reads those answers from the cache exactly as it reads its own, so no request is made.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient
from PIL import Image

from backend import pipeline, smallbodies, spherex

DATA_CACHE = Path(__file__).parent / "data" / "cache"
VIEW = {"ra": 23.35591, "dec": 1.50056, "fov": 0.1, "detector": 5}
VISIT_1_EXPOSURE = "2025W29_1A_0220_3"     # detector 5, July 2025: Vesta is nowhere near this place then


@pytest.fixture(scope="module")
def vesta(cache_dir: Path) -> SimpleNamespace:
    shutil.copytree(DATA_CACHE, cache_dir, dirs_exist_ok=True, copy_function=shutil.copyfile)
    exposures = json.loads((Path(__file__).parent / "data" / "smallbodies_exposures.json").read_text())
    return SimpleNamespace(exposures=exposures, **VIEW)


# --- names ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, kind, shown, designation, command", [
    ("4 Vesta (A807 FA)", "asteroid", "4 Vesta", "A807 FA", "4;"),
    ("32455 (2000 SW60)", "asteroid", "32455", "2000 SW60", "32455;"),
    ("(2000 SW60)", "asteroid", "2000 SW60", None, "DES=2000 SW60;"),
    ("2024 YR4", "asteroid", "2024 YR4", None, "DES=2024 YR4;"),     # a year, not asteroid number 2024
    ("13P/Olbers", "comet", "13P/Olbers", None, "DES=13P;CAP"),
    ("C/2025 R2 (SWAN)", "comet", "C/2025 R2 (SWAN)", None, "DES=C/2025 R2;CAP"),
    ("3I/ATLAS", "comet", "3I/ATLAS", None, "DES=3I;CAP"),
])
def test_names_are_read_the_way_jpl_writes_them(name: str, kind: str, shown: str, designation: str | None,
                                                command: str):
    assert smallbodies.kind_of(name) == kind
    assert smallbodies.split_name(name) == (shown, designation)
    assert smallbodies.horizons_command(name) == command


# --- sb_ident: parsing ------------------------------------------------------------------------------------------

def test_sb_ident_answer_is_parsed(vesta: SimpleNamespace, network: list[str]):
    mids = [smallbodies.exposure_mid_mjd(e) for e in vesta.exposures]
    t0 = (min(mids) + max(mids)) / 2
    half_span = (max(mids) - min(mids)) / 2
    half_width = vesta.fov / 2 * 1.5 + smallbodies.PRUNE_MARGIN_DEG + smallbodies.MAX_RATE_DEG_DAY * half_span
    found = smallbodies.identify(t0, vesta.ra, vesta.dec, half_width)
    assert not network
    by_name = {c["name"]: c for c in found}
    assert len(found) == 7 and "4 Vesta (A807 FA)" in by_name
    v = by_name["4 Vesta (A807 FA)"]
    assert v["vmag"] == pytest.approx(7.7, abs=0.1)
    assert v["ra"] == pytest.approx(vesta.ra, abs=0.05) and v["dec"] == pytest.approx(vesta.dec, abs=0.05)
    assert 20 < (v["rate_ra_arcsec_h"] ** 2 + v["rate_dec_arcsec_h"] ** 2) ** 0.5 < 60      # arcsec per hour


def test_horizons_answer_for_a_comet_is_parsed(vesta: SimpleNamespace, network: list[str]):
    """Comet 13P/Olbers on 2026-03-01 12:00 UT as seen from SPHEREx (not one of the Vesta field's bodies)."""
    (pos,) = smallbodies.ephemeris("13P/Olbers", [61100.5])
    assert not network
    assert pos["ra"] == pytest.approx(289.99712) and pos["dec"] == pytest.approx(-34.45334)
    assert pos["rate"] == pytest.approx(20.4, abs=0.1)        # arcsec per hour
    assert pos["vmag"] == pytest.approx(26.0, abs=0.1)        # Horizons' T-mag; the page uses sb_ident's magnitude


# --- the in-field test ------------------------------------------------------------------------------------------

def test_only_bodies_inside_the_field_are_returned(vesta: SimpleNamespace, network: list[str]):
    crossings, problems = smallbodies.find_crossings(vesta.exposures, vesta.ra, vesta.dec, vesta.fov)
    assert not network and not problems
    # Six other known bodies were candidates in the widened field; Horizons puts none of them in the field.
    assert {c["name"] for c in crossings} == {"4 Vesta"}
    assert [c["exposure"] for c in crossings] == [0, 1]       # the third exposure is 6 hours later: Vesta has left
    first = crossings[0]
    assert first["kind"] == "asteroid" and first["designation"] == "A807 FA"
    assert first["ra"] == pytest.approx(23.35607, abs=1e-5) and first["dec"] == pytest.approx(1.50052, abs=1e-5)
    assert first["vmag"] == pytest.approx(7.71, abs=0.01)
    assert first["rate"] == pytest.approx(40.4, abs=0.5)


def test_a_burst_is_at_most_a_few_days_and_split_at_gaps():
    day = 1.0
    mids = [0.0, 0.0015, 0.003, 0.5, 0.501, 2 * day, 2.001, 9.0, 9.001, 14.0]
    assert smallbodies.clusters(mids) == [[0, 1, 2, 3, 4], [5, 6], [7, 8], [9]]
    assert smallbodies.clusters([]) == []


# --- what the exposure shows -------------------------------------------------------------------------------------

def test_each_crossing_is_measured_in_its_own_exposure_and_pictured(vesta: SimpleNamespace, network: list[str]):
    crossings, _ = smallbodies.find_crossings(vesta.exposures, vesta.ra, vesta.dec, vesta.fov)
    exposure_list = [e for e in vesta.exposures]
    bodies = smallbodies.describe(exposure_list, crossings, vesta.ra, vesta.dec, vesta.fov, vesta.detector, "test")
    assert [b["name"] for b in bodies] == ["4 Vesta", "4 Vesta"]
    for b in bodies:
        assert b["kind"] == "asteroid" and b["exposure"]["detector"] == 5
        assert b["exposure"]["visit"] == 3                      # July 2026 is the third visit /api/frames shows
        assert b["exposure"]["time"].startswith("2026-07-16T22:0")
        assert b["measurement"]["status"] == "ok" and b["measurement"]["sigma"] > 100
        assert b["verdict"] == "seen" and b["summary"].startswith("A source is seen here at")
        assert b["predicted"]["observer"] == smallbodies.OBSERVER
        assert 0 <= b["predicted"]["x"] < 180 and 0 <= b["predicted"]["y"] < 180     # the 0.1 degree frame grid
        picture = pipeline.FRAMES_DIR / "smallbodies" / "test" / f"{b['id']}.png"
        assert b["picture"] == f"/frames/smallbodies/test/{b['id']}.png" and picture.exists()
        with Image.open(picture) as im:
            assert im.size == (60, 60)                          # 120 arcsec at 2 arcsec a pixel


def test_nothing_is_seen_where_the_body_was_not(vesta: SimpleNamespace):
    """The same sky place in an exposure of July 2025, when Vesta was elsewhere: no source, and it says so."""
    crossings, _ = smallbodies.find_crossings(vesta.exposures, vesta.ra, vesta.dec, vesta.fov)
    exp = next(e for e in json.loads((DATA_CACHE / "queries" / "sia_4a58287a0e93970e.json").read_text())
               if e["obs_id"] == VISIT_1_EXPOSURE)
    path = spherex.fetch_cutout(exp, vesta.ra, vesta.dec, round(vesta.fov * 1.5, 4))
    m = smallbodies._measure(path, crossings[0]["ra"], crossings[0]["dec"])
    assert m["status"] == "ok" and abs(m["sigma"]) < smallbodies.POSSIBLE_SIGMA
    kind, sentence = smallbodies.verdict(m)
    assert kind == "not_seen" and sentence.startswith("Nothing is seen here")


def test_a_source_that_is_there_on_other_days_is_a_fixed_source_not_the_body():
    """Real case, 2026-11-14: asteroid 66654 was predicted in a WISE 0855 field exposure with a 27 sigma source at
    the place; 29 exposures of other days measured there gave a median of 28 sigma. A star, not the asteroid."""
    star = {"n_measured": 29, "n_with_source": 29, "median_flux_mjy": 4.6}
    assert smallbodies.fixed_source(4.66, star)
    # Vesta's place in the exposures of other days (real, from the test cutouts): nothing there
    moving = {"n_measured": 4, "n_with_source": 0, "median_flux_mjy": 0.05}
    assert not smallbodies.fixed_source(1442.9, moving)
    assert not smallbodies.fixed_source(1442.9, {"n_measured": 1, "n_with_source": 1, "median_flux_mjy": 3.0})
    assert not smallbodies.fixed_source(None, star)


def test_the_verdict_words():
    assert smallbodies.verdict({"sigma": 12.0, "status": "ok"})[0] == "seen"
    assert smallbodies.verdict({"sigma": 4.0, "status": "ok"})[0] == "possible"
    assert smallbodies.verdict({"sigma": -1.0, "status": "ok"})[0] == "not_seen"
    kind, sentence = smallbodies.verdict({"sigma": None, "status": "off_image"})
    assert kind == "unmeasurable" and "edge" in sentence


# --- JPL not answering -------------------------------------------------------------------------------------------

class _Reply:
    def __init__(self, status: int, text: str = ""):
        self.status_code, self.text = status, text


class _Session:
    def __init__(self, replies: list[object]):
        self.replies, self.calls = replies, 0

    def get(self, url: str, params: dict | None = None, timeout: float = 0) -> _Reply:
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if isinstance(reply, Exception):
            raise reply
        return reply  # type: ignore[return-value]


def test_an_unreachable_jpl_is_retried_and_then_reported(monkeypatch: pytest.MonkeyPatch):
    session = _Session([requests.ConnectionError("down")])
    monkeypatch.setattr(smallbodies, "_session", session)
    monkeypatch.setattr(smallbodies, "PAUSE_S", 0.0)
    with pytest.raises(smallbodies.JplError, match="ConnectionError"):
        smallbodies._jpl_get(smallbodies.SB_IDENT_URL, {"unique": "unreachable"})
    assert session.calls == smallbodies.TRIES


def test_a_jpl_error_status_is_retried_and_a_later_success_is_kept(monkeypatch: pytest.MonkeyPatch):
    session = _Session([_Reply(503), _Reply(200, '{"ok": 1}')])
    monkeypatch.setattr(smallbodies, "_session", session)
    monkeypatch.setattr(smallbodies, "PAUSE_S", 0.0)
    assert smallbodies._jpl_get(smallbodies.SB_IDENT_URL, {"unique": "recovers"}) == '{"ok": 1}'
    assert session.calls == 2
    assert smallbodies._jpl_get(smallbodies.SB_IDENT_URL, {"unique": "recovers"}) == '{"ok": 1}'
    assert session.calls == 2                                    # the second time comes from disk


def test_horizons_that_cannot_place_a_body_says_which(monkeypatch: pytest.MonkeyPatch):
    reply = json.dumps({"result": "No matches found."})
    monkeypatch.setattr(smallbodies, "_jpl_get", lambda url, params: reply)
    with pytest.raises(smallbodies.JplError, match="could not give a position for 99999 Nobody"):
        smallbodies.ephemeris("99999 Nobody (2000 XX)", [61000.0])


def test_when_every_request_fails_there_is_nothing_to_show(vesta: SimpleNamespace, monkeypatch: pytest.MonkeyPatch):
    def refuse(url: str, params: dict) -> str:
        raise smallbodies.JplError("HTTP 503 from sb_ident")
    monkeypatch.setattr(smallbodies, "_jpl_get", refuse)
    with pytest.raises(smallbodies.JplError, match="every request to JPL failed"):
        smallbodies.find_crossings(vesta.exposures, vesta.ra + 1.0, vesta.dec, vesta.fov)


def test_a_view_without_exposures_says_so(cache_dir: Path):
    # IRSA's answer for a position SPHEREx has not covered is an empty list; the cache holds it like any other.
    key = hashlib.sha1(b"200.00000,-40.00000").hexdigest()[:16]
    spherex.write_json(cache_dir / "queries" / f"sia_{key}.json", [])
    out = smallbodies.known_bodies(200.0, -40.0, 0.1, 5)
    assert out["bodies"] == [] and "no public images" in out["message"]


# --- the endpoint -----------------------------------------------------------------------------------------------

def test_endpoint_answers_with_what_the_module_returns(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def fake(ra: float, dec: float, fov: float, detector: int, progress=None) -> dict:
        seen.update(ra=ra, dec=dec, fov=fov, detector=detector)
        return {"bodies": [], "problems": []}
    monkeypatch.setattr(smallbodies, "known_bodies", fake)
    r = client.get("/api/smallbodies", params={"ra": 10, "dec": -5, "fov": 0.2, "detector": 3})
    assert r.status_code == 200 and r.json() == {"bodies": [], "problems": []}
    assert seen == {"ra": 10, "dec": -5, "fov": 0.2, "detector": 3}


def test_endpoint_turns_a_jpl_failure_into_a_502_with_a_plain_message(client: TestClient,
                                                                      monkeypatch: pytest.MonkeyPatch):
    def down(*_: object, **__: object) -> dict:
        raise smallbodies.JplError("ReadTimeout from https://ssd-api.jpl.nasa.gov/sb_ident.api")
    monkeypatch.setattr(smallbodies, "known_bodies", down)
    r = client.get("/api/smallbodies", params={"ra": 10, "dec": -5})
    assert r.status_code == 502
    assert r.json()["detail"].startswith("NASA/JPL's small-body services did not respond")


def test_endpoint_turns_an_irsa_failure_into_a_502(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def down(*_: object, **__: object) -> dict:
        raise spherex.ArchiveError("HTTP 502 from the image search")
    monkeypatch.setattr(smallbodies, "known_bodies", down)
    r = client.get("/api/smallbodies", params={"ra": 10, "dec": -5})
    assert r.status_code == 502 and "IRSA" in r.json()["detail"]


@pytest.mark.parametrize("params", [{}, {"ra": 10}, {"ra": 360, "dec": 0}, {"ra": 10, "dec": 91},
                                    {"ra": 10, "dec": 0, "fov": 0.02}, {"ra": 10, "dec": 0, "fov": 0.6},
                                    {"ra": 10, "dec": 0, "detector": 7}])
def test_endpoint_refuses_bad_requests_before_asking_anyone(client: TestClient, network: list[str], params: dict):
    assert client.get("/api/smallbodies", params=params).status_code in (400, 422)
    assert not network

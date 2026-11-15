"""The watchlist: grouping, stable ids, votes, export and the NEOWISE reading, offline.

The search results are the real (trimmed) responses saved for the frontend's tests in
frontend/src/fixtures/search/; the NEOWISE table is the real one for Serpens South, saved
in tests/data/. Nothing is made up. The database is a fresh file per test.
"""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import neowise, watchlist

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "frontend" / "src" / "fixtures" / "search"
VOTER = "abcdefghij0123456789"


def real(name: str) -> dict[str, Any]:
    return copy.deepcopy(json.loads((FIXTURES / f"{name}.json").read_text())["result"])


@pytest.fixture(autouse=True)
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(watchlist.DB_ENV, str(tmp_path / "w.sqlite3"))
    watchlist._recent.clear()


def ingest(name: str) -> dict[str, Any]:
    return watchlist.ingest(real(name), queue_neowise=False)


def by_group(group: str) -> list[dict[str, Any]]:
    return watchlist.list_rows(group=group, limit=200)["rows"]


def test_grouping_follows_the_catalogues_and_the_artefact_tests() -> None:
    for name in ("barnard", "epsindib", "rwaur", "serpsouth", "wise0855"):
        ingest(name)
    counts = watchlist.list_rows()["counts"]
    # Serpens South: 6 changers not listed as variable, 3 listed variables. The three catalogued movers and the
    # RW Aurigae variable are known. Epsilon Indi B's ghost ring is set aside.
    assert counts == {"eyes": 6, "known": 7, "artefact": 1}
    ghost = by_group("artefact")[0]
    assert ghost["kind"] == "mover" and ghost["reasons"] and ghost["id"].startswith("set-aside-mover-")
    assert {r["catalogue_status"]["category"] for r in by_group("known")} == {"known_mover", "known_variable"}


def test_order_of_needs_eyes_is_the_documented_one() -> None:
    ingest("serpsouth")
    rows = by_group("eyes")
    assert rows[0]["id"] == "changer-277.5055s02.0620"          # the Serpens South young star
    keys = [(r["verdict"] != "clean", -len(r["detectors_at_5_sigma"]), -r["sigma_combined"]) for r in rows]
    assert keys == sorted(keys)
    assert rows[-1]["verdict"] == "caution"
    assert [r["rank_in_group"] for r in rows] == list(range(1, len(rows) + 1))


def test_same_object_found_again_or_from_a_neighbouring_patch_is_one_row() -> None:
    first = ingest("serpsouth")
    again = ingest("serpsouth")
    assert again["added"] == 0 and again["ids"] == first["ids"]
    neighbour = real("serpsouth")
    neighbour["field"].update(ra=277.55, dec=-2.0)               # another patch, the same sources (a little off)
    for obj in neighbour["objects"]:
        obj["ra"] += 0.00001
        obj["sigma_combined"] -= 1.0                              # it saw them less strongly
    got = watchlist.ingest(neighbour, queue_neowise=False)
    assert got["added"] == 0 and got["ids"] == first["ids"]
    row = watchlist.get_row("changer-277.5055s02.0620")
    assert len(row["patches"]) == 2
    assert row["sigma_combined"] == 13.4                         # the stronger sighting's evidence is kept
    assert row["first_seen"] <= row["last_seen"]


def test_a_mover_and_a_changer_at_one_place_are_two_rows() -> None:
    ingest("barnard")
    ingest("rwaur")
    kinds = {r["kind"] for r in watchlist.list_rows(limit=50)["rows"]}
    assert kinds == {"mover", "changer"}


def test_votes_one_per_voter_replace_and_validate() -> None:
    ingest("rwaur")
    cid = by_group("known")[0]["id"]
    out = watchlist.vote(cid, "real", "  a <b>note</b>\n with a line break ", VOTER)
    assert out["votes"] == {"real": 1, "artefact": 0, "unsure": 0, "total": 1}
    assert out["note"] == "a <b>note</b> with a line break"        # plain text: stored as it is, escaped by the page
    watchlist.vote(cid, "artefact", None, VOTER)                    # replaces
    watchlist.vote(cid, "unsure", None, "zyxwvutsrq9876543210")
    row = watchlist.get_row(cid, VOTER)
    assert row["votes"] == {"real": 0, "artefact": 1, "unsure": 1, "total": 2}
    assert row["my_vote"] == "artefact"
    with pytest.raises(watchlist.WatchlistError) as e:
        watchlist.vote(cid, "confirmed", None, VOTER)
    assert e.value.status == 400
    with pytest.raises(watchlist.WatchlistError):
        watchlist.vote(cid, "real", "x" * 281, VOTER)
    with pytest.raises(watchlist.WatchlistError):
        watchlist.vote(cid, "real", None, "short")
    with pytest.raises(watchlist.WatchlistError) as e:
        watchlist.vote("no-such-candidate", "real", None, VOTER)
    assert e.value.status == 404


def test_the_voter_id_is_not_stored_and_no_other_identity_is() -> None:
    ingest("rwaur")
    cid = by_group("known")[0]["id"]
    watchlist.vote(cid, "real", None, VOTER)
    raw = b"".join(p.read_bytes() for p in watchlist.db_path().parent.iterdir())
    assert VOTER.encode() not in raw


def test_votes_are_limited_per_voter() -> None:
    ingest("rwaur")
    cid = by_group("known")[0]["id"]
    for k in range(watchlist.MAX_VOTES):
        watchlist.vote(cid, "real", None, VOTER, now=100.0 + k)
    with pytest.raises(watchlist.WatchlistError) as e:
        watchlist.vote(cid, "unsure", None, VOTER, now=120.0)
    assert e.value.status == 429
    watchlist.vote(cid, "unsure", None, VOTER, now=100.0 + watchlist.VOTE_WINDOW_S + 20)   # later: allowed again
    watchlist.vote(cid, "unsure", None, "another-voter-1234567", now=120.0)                 # another voter: allowed


def test_votes_never_reorder_the_machine() -> None:
    ingest("serpsouth")
    before = [r["id"] for r in by_group("eyes")]
    for r in by_group("eyes")[-3:]:
        for n in range(5):
            watchlist.vote(r["id"], "real", None, f"voter-number-{n:02d}-abcdef")
    assert [r["id"] for r in by_group("eyes")] == before


def test_export_has_every_candidate_readable_columns_and_a_header() -> None:
    for name in ("serpsouth", "epsindib", "barnard"):
        ingest(name)
    cid = by_group("eyes")[0]["id"]
    watchlist.vote(cid, "real", None, VOTER)
    text = watchlist.export_csv("https://example.org/")
    assert text.startswith("# ") and "CANDIDATE" in text.splitlines()[0]
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    rows = list(csv.DictReader(io.StringIO(body)))
    assert len(rows) == 9 + 1 + 1 + 1
    assert list(rows[0]) == list(watchlist.COLUMNS)
    top = rows[0]
    assert top["id"] == cid and top["list_group"] == "needs_eyes" and top["rank_in_group"] == "1"
    assert top["kind"] == "changed_brightness" and top["votes_real"] == "1" and top["votes_total"] == "1"
    assert top["catalogues_answered"].startswith("Gaia DR3") and top["catalogues_did_not_answer"] == ""
    assert top["viewer_link"].startswith("https://example.org/?ra=277.505473&dec=-2.061979&fov=0.1&det=6")
    assert top["neowise_reading"] == "not_checked_yet"
    assert {r["list_group"] for r in rows} == {"needs_eyes", "already_known", "set_aside_as_artefact"}
    ghost = next(r for r in rows if r["list_group"] == "set_aside_as_artefact")
    assert ghost["set_aside_reasons"] and ghost["machine_verdict"] == "rejected"
    as_json = watchlist.export_json()
    assert len(as_json["candidates"]) == len(rows) and "CANDIDATE" in as_json["about"]


# ---- NEOWISE ---------------------------------------------------------------------------------------

SERPS = (277.50547, -2.06198)


def serpens_table() -> Any:
    return neowise.read_table((ROOT / "tests" / "data" / "neowise_serpens_south.tbl").read_bytes())


def test_neowise_reading_for_serpens_south_matches_docs_search() -> None:
    visits, counts = neowise.neowise_visits(serpens_table(), *SERPS)
    got = neowise.reading(visits, counts)
    assert got["reading"] == "changed"
    assert got["w2"]["n_visits"] == 21
    assert 8.5 < got["w2"]["factor"] < 9.6                      # "a factor of 9" at 4.6 micrometres
    assert round(got["w2"]["faintest_mjy"]) == 177 and 1500 < got["w2"]["brightest_mjy"] < 1700
    assert 6.5 < got["w1"]["factor"] < 7.5                      # "a factor of 7" at 3.4 micrometres
    assert got["w2"]["saturated_share_max"] > 0.3               # NEOWISE saturates on it
    assert got["sentence"].startswith("NEOWISE also saw this spot change")
    assert "21 visits" in got["sentence"] and "partly too bright" in got["sentence"]


def test_neowise_three_way_reading() -> None:
    visits, _ = neowise.neowise_visits(serpens_table(), *SERPS)
    steady = copy.deepcopy(visits)
    for v in steady:
        for band in ("w1", "w2"):
            if v[band]:
                v[band]["mjy"] = 100.0 + (v["mjd"] % 7)          # 100 to 107 mJy: a factor of 1.07
    assert neowise.reading(steady)["reading"] == "steady"
    assert neowise.reading(steady)["sentence"].startswith("NEOWISE saw it steady")
    few = neowise.reading(visits[:3])
    assert few["reading"] == "cannot_say" and "only 3 visits" in few["sentence"]
    nothing = neowise.reading([])
    assert nothing["reading"] == "cannot_say" and "no usable measurement" in nothing["sentence"]


def test_neowise_answer_is_stored_with_the_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    ingest("serpsouth")
    monkeypatch.setattr(neowise, "neowise_rows", lambda ra, dec: serpens_table())
    cid = "changer-277.5055s02.0620"
    assert watchlist.check_neowise(cid)["state"] == "ok"
    row = watchlist.get_row(cid)
    assert row["neowise"]["state"] == "ok" and row["neowise"]["reading"] == "changed"
    flat = next(r for r in watchlist.export_rows() if r["id"] == cid)
    assert flat["neowise_reading"] == "changed" and flat["neowise_visits"] == 21
    assert 8.5 < float(flat["neowise_4p6um_factor"]) < 9.6


def test_a_neowise_failure_is_recorded_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    ingest("serpsouth")

    def down(ra: float, dec: float) -> Any:
        raise RuntimeError("archive down")

    monkeypatch.setattr(neowise, "neowise_rows", down)
    assert watchlist.check_neowise("changer-277.5055s02.0620")["state"] == "error"
    row = watchlist.get_row("changer-277.5055s02.0620")
    assert row["neowise"]["state"] == "error" and "did not answer" in row["neowise"]["message"]


def test_a_failure_to_ingest_never_fails_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(result: Any, **kw: Any) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(watchlist, "ingest", broken)
    watchlist.ingest_safely(real("barnard"))                   # must not raise


# ---- the web routes --------------------------------------------------------------------------------

def test_routes(client: TestClient) -> None:
    ingest("serpsouth")
    page = client.get("/api/watchlist", params={"group": "eyes", "limit": 2}).json()
    assert page["counts"]["eyes"] == 6 and len(page["rows"]) == 2 and "CANDIDATE" in page["about"]
    cid = page["rows"][0]["id"]
    assert client.get(f"/api/watchlist/{cid}").json()["id"] == cid
    assert client.get("/api/watchlist/none").status_code == 404
    assert client.get("/api/watchlist", params={"group": "x"}).status_code == 400
    posted = client.post(f"/api/watchlist/{cid}/vote", json={"answer": "real", "voter": VOTER, "note": "<i>x</i>"})
    assert posted.status_code == 200 and posted.json()["votes"]["real"] == 1
    assert client.post(f"/api/watchlist/{cid}/vote", json={"answer": "bad", "voter": VOTER}).status_code == 400
    assert client.post(f"/api/watchlist/{cid}/vote", json={"answer": "real", "voter": "x"}).status_code == 400
    mine = client.get(f"/api/watchlist/{cid}", headers={"X-Voter": VOTER}).json()
    assert mine["my_vote"] == "real" and mine["notes"] == ["<i>x</i>"]
    csv_answer = client.get("/api/watchlist/export.csv")
    assert csv_answer.status_code == 200 and csv_answer.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_answer.headers["content-disposition"]
    assert client.get("/api/watchlist/export.json").json()["candidates"][0]["id"] == cid
    cors = client.options("/api/watchlist/x/vote", headers={"Origin": "http://a.example",
                                                            "Access-Control-Request-Method": "POST"})
    assert cors.status_code == 200
    # No images of this patch are on this test server: a plain "no picture", not a download.
    nope = client.get(f"/api/watchlist/{cid}/picture.png")
    assert nope.status_code == 404 and "No picture" in nope.json()["detail"]

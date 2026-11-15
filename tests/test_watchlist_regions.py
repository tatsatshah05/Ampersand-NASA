"""The watchlist's regions (the patches the blind searches covered) and the region filter, on a small real copy.

tests/data/watchlist/small.sqlite3 is a copy of the shared watchlist database as it stood on 2026-11-15 (10:11
UTC), cut down to the 21 rows that the searches of five patches reported, with their NEOWISE answers and no votes
(there were none): Candidate B's patch (253.18038, -44.67697, 0.1 degrees), Barnard's Star's (0.1), the Serpens
South young star's (0.1), one Ophiuchus patch and one Chamaeleon patch (0.2). Rows keep every patch they were
seen from, so the Serpens South rows also bring the neighbouring 0.2-degree patch they were seen from. Nothing in
it was edited. Each test works on its own copy of the file.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import watchlist

SMALL = Path(__file__).resolve().parent / "data" / "watchlist" / "small.sqlite3"
B_PATCH = "253.180380_-44.676970_0.1000"
BARNARD = "269.446267_4.768222_0.1000"
SERPENS = "277.505470_-2.061980_0.1000"


@pytest.fixture(autouse=True)
def small_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "small.sqlite3"
    shutil.copy(SMALL, db)
    monkeypatch.setenv(watchlist.DB_ENV, str(db))
    return db


def test_the_regions_are_the_searched_patches_with_their_constellations() -> None:
    got = watchlist.regions()
    keys = [r["key"] for r in got["regions"]]
    assert sorted(keys) == sorted([B_PATCH, BARNARD, SERPENS, "277.510000_-2.050000_0.2000",
                                   "246.790000_-24.470000_0.2000", "167.400000_-77.000000_0.2000"])
    by_key = {r["key"]: r for r in got["regions"]}
    assert by_key[B_PATCH]["constellation"] == "Scorpius"
    assert by_key[SERPENS]["constellation"] == "Serpens"
    # astropy's table spells these "Ophiucus" and "Chamaleon"; the page uses the IAU's spelling.
    assert by_key[BARNARD]["constellation"] == "Ophiuchus"
    assert by_key["167.400000_-77.000000_0.2000"]["constellation"] == "Chamaeleon"
    assert by_key[B_PATCH]["fov"] == 0.1 and by_key[B_PATCH]["area_sq_deg"] == 0.01
    assert by_key[B_PATCH]["last_searched"] == "2026-11-15T10:11:15Z"
    assert got["patches_searched"] == 6 and got["total"] == 21
    assert got["first_searched"] == "2026-11-15T01:09:01Z" and got["last_searched"] == "2026-11-15T10:11:15Z"
    # Sorted by constellation, so a list of them reads in order.
    names = [r["constellation"] for r in got["regions"]]
    assert names == sorted(names)


def test_each_regions_count_is_what_the_filtered_list_holds() -> None:
    for region in watchlist.regions()["regions"]:
        page = watchlist.list_rows(region=region["key"], limit=200)
        assert page["total"] == region["count"] == len(page["rows"])
        assert page["counts"] == region["counts"]
        assert sum(page["counts"].values()) == region["count"]
        for g in watchlist.GROUPS:
            assert watchlist.list_rows(group=g, region=region["key"], limit=200)["total"] == region["counts"][g]
        for row in page["rows"]:
            assert any(watchlist.region_key(p) == region["key"] for p in row["patches"])


def test_candidate_bs_patch_holds_what_its_search_reported() -> None:
    page = watchlist.list_rows(region=B_PATCH, limit=200)
    assert page["counts"] == {"eyes": 2, "known": 3, "artefact": 2}
    assert page["region"] == B_PATCH
    ids = [r["id"] for r in page["rows"]]
    # The steady 40 mJy star 10 arcsec north-east of B, which the patch search flagged as "changed".
    assert "changer-253.1838s44.6755" in ids
    # The machine's order and rank are those of the whole list, whatever the region.
    everything = {r["id"]: r["rank_in_group"] for r in watchlist.list_rows(limit=200)["rows"]}
    assert all(r["rank_in_group"] == everything[r["id"]] for r in page["rows"])
    assert [r["group"] for r in page["rows"]] == sorted((r["group"] for r in page["rows"]), key=watchlist.GROUPS.index)


def test_a_row_seen_from_two_patches_is_in_both() -> None:
    row = watchlist.get_row("changer-277.5055s02.0620")
    keys = {watchlist.region_key(p) for p in row["patches"]}
    assert keys == {SERPENS, "277.510000_-2.050000_0.2000"}
    for key in keys:
        assert row["id"] in [r["id"] for r in watchlist.list_rows(region=key, limit=200)["rows"]]


def test_without_a_region_nothing_changes() -> None:
    page = watchlist.list_rows(limit=200)
    assert page["total"] == 21 and page["counts"] == {"eyes": 5, "known": 11, "artefact": 5}
    assert page["region"] is None and page["patches_searched"] == 6


def test_an_unknown_region_is_refused() -> None:
    with pytest.raises(watchlist.WatchlistError) as e:
        watchlist.list_rows(region="1.000000_2.000000_0.1000")
    assert e.value.status == 404


def test_region_key_is_the_patch_as_asked() -> None:
    assert watchlist.region_key({"ra": 253.18038, "dec": -44.67697, "fov": 0.1}) == B_PATCH
    assert watchlist.region_key({"ra": 52.265, "dec": 31.31, "fov": 0.2}) == "52.265000_31.310000_0.2000"


def test_constellations_of_the_five_challenge_targets_and_the_three_candidates() -> None:
    points = [(269.446267, 4.768222), (331.096653, -56.800663), (133.759765, -7.242182), (76.956587, 30.401291),
              (248.167233, 66.755024), (270.80408, -23.46818), (253.18038, -44.67697), (241.70906, -52.20564)]
    assert watchlist.constellations(points) == ["Ophiuchus", "Indus", "Hydra", "Auriga", "Draco",
                                                "Sagittarius", "Scorpius", "Norma"]
    assert watchlist.constellations([]) == []


def test_routes(client: TestClient) -> None:
    got = client.get("/api/watchlist/regions")
    assert got.status_code == 200
    regions = got.json()["regions"]
    assert {r["key"] for r in regions} >= {B_PATCH, BARNARD}
    page = client.get("/api/watchlist", params={"region": B_PATCH, "group": "eyes", "limit": 10}).json()
    assert page["counts"]["eyes"] == 2 and page["total"] == 2 and len(page["rows"]) == 2
    assert client.get("/api/watchlist", params={"region": "nowhere"}).status_code == 404
    # "regions" is a route of its own, never taken for a candidate's id.
    assert "regions" in got.json() and client.get("/api/watchlist/changer-253.1838s44.6755").status_code == 200

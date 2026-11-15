"""The distant-world search (backend/distant.py) on made-up pictures.

No real object of this kind is known that SPHEREx could see, so the search is tested the
way surveys test theirs: a picture is built with ordinary stars, noise and one body that
moves the way the Earth's motion says a distant body must, and the search has to find
that body, give its distance, and find nothing when it is not there. Nothing here is
SPHEREx data and nothing is written to the cache.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from astropy.time import Time

from backend import astrometry, distant, pipeline, training

RA, DEC, FOV, DETECTOR = 270.0, 5.0, 0.2, 5
SIGMA_PX = training.PSF_SIGMA_PX[DETECTOR]
NOISE = 0.01                                    # MJy/sr per pixel
# Three visits half a year apart, a few days long each, as SPHEREx makes them away from the poles.
VISIT_DATES = ("2025-09-20", "2026-03-22", "2026-09-18")
FLARE = (200.0, 90.0)                           # pixel of a star that is seen in the second visit only


def _items() -> dict[int, list[dict]]:
    items = {}
    for ep, date in enumerate(VISIT_DATES):
        start = Time(date).mjd
        items[ep] = [{"mjd": float(start + day), "weight": 1.0} for day in (0.0, 1.0, 2.0, 3.0)]
    return items


def _body(distance_au: float, ra: float = RA + 0.01, dec: float = DEC - 0.01) -> dict:
    drift = distant.circular_drift(distance_au)
    return {"ra": ra, "dec": dec, "pmra": 0.8 * drift * 1000.0, "pmdec": 0.3 * drift * 1000.0,
            "parallax": distant.ARCSEC_PER_RADIAN / distance_au * 1000.0, "ref_epoch": 2026.2}


def _pictures(body: dict | None, height: float = 0.04, seed: int = 3, variable: bool = True
              ) -> tuple[object, int, dict[int, np.ndarray], dict[int, list[dict]]]:
    """Three visits of one made-up field: noise, 40 steady stars, optionally one star seen in
    a single visit only, and optionally the moving body."""
    grid, n = pipeline.make_grid(RA, DEC, FOV)
    items = _items()
    visits = distant.visits_from(items, RA, DEC)
    rng = np.random.default_rng(seed)
    stars = [(rng.uniform(15, n - 15), rng.uniform(15, n - 15), 10 ** rng.uniform(-1.3, 0.5)) for _ in range(40)]
    stars = [s for s in stars if math.hypot(s[0] - FLARE[0], s[1] - FLARE[1]) > 25.0]    # keep the flare in the clear
    images = {}
    for k, ep in enumerate(sorted(items)):
        image = rng.normal(0.2, NOISE, (n, n))
        for x, y, h in stars:
            image = training.add_source(image, x, y, h, SIGMA_PX)
        if variable and k == 1:
            image = training.add_source(image, *FLARE, 0.06, SIGMA_PX)     # a flare, not a mover
        if body is not None:
            x, y = grid.all_world2pix(*distant.place_in_visit(body, visits[k]), 0)
            image = training.add_source(image, float(x), float(y), height, SIGMA_PX)
        images[ep] = image
    return grid, n, images, items


def test_parallax_factor_is_the_arithmetic_of_position_at():
    mjd = Time("2026-03-22").mjd
    unit = {"ra": RA, "dec": DEC, "pmra": 0.0, "pmdec": 0.0, "parallax": 1000.0, "ref_epoch": 2026.0}
    east, north = astrometry.offset_arcsec(RA, DEC, *astrometry.position_at(unit, mjd))
    f = distant.parallax_factor(distant._earth(np.array([mjd]))[0], RA, DEC)
    assert f == pytest.approx([east, north], abs=1e-4)


def test_a_visit_at_one_instant_places_a_body_where_position_at_does():
    body = _body(700.0)
    items = {0: [{"mjd": Time("2026-03-22").mjd, "weight": 1.0}]}
    visit = distant.visits_from(items, RA, DEC, as_planted=True)[0]
    assert distant.place_in_visit(body, visit) == pytest.approx(astrometry.position_at(body, visit["mjd"]), abs=1e-9)
    assert visit["smear"] == 0.0


def test_visits_half_a_year_apart_swing_a_body_by_about_twice_its_parallax():
    visits = distant.visits_from(_items(), RA, DEC)
    f = [distant.parallax_factor(v["earth"], RA, DEC) for v in visits]
    assert np.hypot(*(f[1] - f[0])) == pytest.approx(2.0, abs=0.15)
    assert np.hypot(*(f[2] - f[0])) < 0.1          # a year apart: the same side of the orbit
    assert all(0.0 < v["smear"] < 0.05 for v in visits)


def test_circular_drift():
    assert distant.circular_drift(500.0) == pytest.approx(115.9, abs=0.1)
    assert distant.circular_drift(10000.0) == pytest.approx(1.296, abs=0.01)


@pytest.mark.parametrize("distance_au", [400.0, 2000.0, 20000.0])
def test_fit_recovers_the_distance_from_three_places(distance_au):
    body = _body(distance_au)
    visits = distant.visits_from(_items(), RA, DEC)
    places = np.array([distant.place_in_visit(body, v) for v in visits])
    fit = distant.fit_body(places[:, 0], places[:, 1], np.ones(3), visits)
    assert fit is not None
    assert distant.ARCSEC_PER_RADIAN / (fit["body"]["parallax"] / 1000.0) == pytest.approx(distance_au, rel=2e-3)
    assert fit["chi2"] < 1e-3
    assert max(fit["misfit_arcsec"]) < 0.05


def test_fit_refuses_visits_all_on_one_side_of_the_orbit():
    days = ("2025-09-20", "2025-09-21", "2025-09-22")
    items = {ep: [{"mjd": Time(d).mjd, "weight": 1.0}] for ep, d in enumerate(days)}
    visits = distant.visits_from(items, RA, DEC)
    body = _body(2000.0)
    places = np.array([distant.place_in_visit(body, v) for v in visits])
    fit = distant.fit_body(places[:, 0], places[:, 1], np.ones(3), visits)
    # Three days cannot tell parallax from drift: either no answer, or one with a useless error.
    assert fit is None or fit["parallax_err_arcsec"] > 50.0


@pytest.mark.parametrize("distance_au", [1500.0, 2500.0, 8000.0])
def test_the_search_finds_a_moving_body_and_its_distance(distance_au):
    body = _body(distance_au)
    grid, n, images, items = _pictures(body)
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV)
    assert field["can_search"]
    assert len(field["links"]) == 1
    found = field["links"][0]
    assert found["distance_au"] == pytest.approx(distance_au, rel=0.08)
    assert len(found["members"]) == 3
    visits = field["visits"]
    for k, s in found["members"].items():
        true_ra, true_dec = distant.place_in_visit(body, visits[k])
        assert distant._separation(s["ra"], s["dec"], true_ra, true_dec) < 2.0
    assert field["chance_links"] == []


def test_the_search_finds_nothing_in_a_field_without_a_mover():
    grid, n, images, items = _pictures(None)
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV)
    assert field["links"] == []
    assert field["chance_links"] == []
    # The one-visit flare is noticed as a source that comes and goes, and is linked to nothing.
    assert any(abs(s["x"] - FLARE[0]) < 1.5 and abs(s["y"] - FLARE[1]) < 1.5 for s in field["members"])
    # Ordinary stars are not: nearly every source is seen in all three visits.
    assert len(field["members"]) <= 6
    assert sum(len(v) for v in field["sources"].values()) > 60
    assert all(s["point_like"] for s in field["members"])


def test_a_body_too_faint_for_one_visit_is_not_claimed():
    grid, n, images, items = _pictures(_body(2000.0), height=0.006)      # about twice the noise
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV)
    assert field["links"] == []


def test_a_catalogued_source_at_the_place_sets_the_source_aside():
    body = _body(2000.0)
    grid, n, images, items = _pictures(body)
    visits = distant.visits_from(items, RA, DEC)
    ra1, dec1 = distant.place_in_visit(body, visits[1])
    bright = {"ra": ra1, "dec": dec1, "pmra": 0.0, "pmdec": 0.0, "w1": 12.0, "w2": 12.0}
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV, catalogue=[bright])
    assert field["links"] == []
    assert sum(1 for s in field["members"] if s["catalogued"]) == 1
    # A catalogue source far too faint to be the SPHEREx source does not count.
    faint = {**bright, "w1": 19.5, "w2": 19.5}
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV, catalogue=[faint])
    assert len(field["links"]) == 1


def test_two_visits_cannot_be_searched():
    grid, n, images, items = _pictures(_body(2000.0))
    del images[2], items[2]
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV)
    assert not field["can_search"]
    assert field["links"] == [] and field["limit"] == []


def test_the_limit_table():
    grid, n, images, items = _pictures(None)
    field = distant.search_stacks(grid, n, images, items, DETECTOR, RA, DEC, FOV)
    rows = {r["distance_au"]: r for r in field["limit"]}
    # A 0.2 degree picture is 720 arcsec wide: at 500 AU the 825 arcsec jump leaves it.
    assert 500 not in rows and 2000 in rows and 20000 in rows
    assert rows[2000]["jump_arcsec"] == pytest.approx(2.0 * distant.ARCSEC_PER_RADIAN / 2000.0, rel=0.08)
    assert rows[20000]["share_of_picture"] > rows[2000]["share_of_picture"] > rows[1000]["share_of_picture"]
    # 5 times the noise of the matched filter, as a flux: the planted 0.04 MJy/sr body is well above it.
    expected = 5.0 * distant.flux_mjy(NOISE / math.sqrt(math.pi * SIGMA_PX ** 2), SIGMA_PX)
    assert rows[20000]["faintest_mjy"] == pytest.approx(expected, rel=0.35)
    assert rows[1000]["faintest_mjy"] >= rows[20000]["faintest_mjy"]      # a near object smears within a visit


def test_in_view_falls_to_nothing_for_a_near_object():
    visits = distant.visits_from(_items(), RA, DEC)
    assert distant.in_view(200.0, visits, RA, DEC, FOV) == 0.0
    assert distant.in_view(30000.0, visits, RA, DEC, FOV) > 0.9


# ---------------------------------------------------------------------------
# On real SPHEREx images (the nine Barnard's Star cutouts kept in the repository)
# ---------------------------------------------------------------------------

def _wait(client, params: dict) -> dict:
    import time
    deadline = time.time() + 120
    body: dict = {}
    while time.time() < deadline:
        body = client.get("/api/distant", params=params).json()
        if body["status"] in ("done", "failed"):
            break
        time.sleep(0.3)
    return body


def test_the_endpoint_searches_real_images_and_reports_a_limit(client, barnard, monkeypatch):
    from backend import spherex
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)
    body = _wait(client, {"ra": barnard.ra, "dec": barnard.dec, "fov": 0.1, "detectors": "5"})
    assert body["status"] == "done", body.get("error")
    assert body["simulation"] is False
    result = body["result"]
    assert result["simulation"] is False and "planted" not in result
    assert result["status"] in ("nothing_found", "candidates")
    assert [v["n_exposures"] for v in result["per_detector"][0]["visits"]] == [3, 3, 3]
    # The catalogue could not be asked (no network in tests), and the answer says so.
    assert result["catalogue"]["answered"] is False
    # A 0.1 degree picture is 360 arcsec wide: the 412 arcsec jump of an object at 1,000 AU leaves it.
    assert result["limit"] and result["limit"][0]["distance_au"] > 1000
    assert result["limit"][0]["share_of_picture"] < result["limit"][-1]["share_of_picture"]
    assert all(row["faintest_mjy"] > 0 for row in result["limit"])
    assert "candidate" not in result["answer"].lower() or result["candidates"]


def test_planted_practice_objects_are_found_when_bright_enough_and_always_labelled(client, barnard, monkeypatch):
    from backend import spherex
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)
    found_seed = None
    for seed in range(1, 9):
        result = distant.distant_search(barnard.ra, barnard.dec, 0.1, (5,), catalogues=False,
                                        planted={"level": "easy", "seed": seed, "detector": 5})
        assert result["simulation"] is True and result["notice"] == training.NOTICE
        assert result["answer"].startswith("SIMULATION")
        truth = result["planted"]
        # The same object the practice screen shows for this level and seed.
        shown = training.build_training(barnard.ra, barnard.dec, 0.1, 5, "normal", "easy", seed)["planted"]
        assert truth["distance_au"] == pytest.approx(shown["distance_au"])
        for mine, theirs in zip(truth["positions"], shown["positions"], strict=True):
            assert (mine["ra"], mine["dec"]) == pytest.approx((theirs["ra"], theirs["dec"]), abs=1e-9)
        hits = [c for c in result["candidates"] if c.get("is_planted_object")]
        seen = sorted((p["times_noise"] for p in truth["positions"]), reverse=True)
        if seen[1] >= distant.DETECT_SIGMA + 0.5 and seen[2] >= distant.MEMBER_SIGMA + 0.5:
            # Bright enough in three visits: it must be found, with its distance.
            assert len(hits) == 1, (seed, seen, result["answer"])
        if hits:
            assert hits[0]["distance_au"] == pytest.approx(truth["distance_au"], rel=0.1)
            assert "found the planted object" in result["answer"]
            found_seed = found_seed or seed
        else:
            assert "did not find" in result["answer"]
    assert found_seed is not None, "none of eight easy practice objects was found"

    # The same through the endpoint, and a real search of the field never sees the planted object.
    params = {"ra": barnard.ra, "dec": barnard.dec, "fov": 0.1, "detectors": "5"}
    body = _wait(client, {**params, "plant": "easy", "seed": found_seed, "plant_detector": 5})
    assert body["status"] == "done", body.get("error")
    assert body["simulation"] is True and body["result"]["simulation"] is True
    assert any(c.get("is_planted_object") for c in body["result"]["candidates"])
    real = _wait(client, params)["result"]
    assert real["simulation"] is False and "planted" not in real
    assert not any("is_planted_object" in c for c in real["candidates"])


def test_a_bad_plant_level_is_explained(client):
    response = client.get("/api/distant", params={"ra": 10.0, "dec": 10.0, "plant": "impossible"})
    assert response.status_code == 400
    assert "easy" in response.json()["detail"]

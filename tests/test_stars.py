"""The warning about very bright stars near a view (ghost rings), on real catalogue answers.

tests/data/cache/queries/gaia_00a3f4c6e70b723e.json is Gaia's answer, copied unchanged from
backend/cache on 2026-11-14, to "stars brighter than G = 7 within 0.25 degrees of Epsilon
Indi B": one star, its primary Epsilon Indi A (G = 4.32). Around Barnard's Star the same
question was never asked, so with the network blocked Gaia "does not answer" there.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from astropy.time import Time

from backend import spherex, stars

EPS_INDI_B = (331.096653, -56.800663)       # what /api/resolve gives for "Epsilon Indi B" at 2026.0
MID_2026 = float(Time("2026-06-01").mjd)


def test_the_bright_primary_of_epsilon_indi_b_is_found_outside_the_picture(barnard: SimpleNamespace,
                                                                           network: list[str]):
    (star,) = stars.bright_nearby(*EPS_INDI_B, 0.1, MID_2026) or []
    assert star["source_id"] == "6412595290592307840" and star["gmag"] == pytest.approx(4.32)
    # 7.4 arcmin apart in Gaia's 2016 positions; the pair moves together but the stored
    # position of B is for 2026, so on a 2026 date they are 6.7 arcmin apart.
    assert star["distance_arcmin"] == pytest.approx(6.7, abs=0.15)
    assert star["inside_picture"] is False and star["east_arcsec"] < 0
    assert network == []                                  # served from the saved answer


def test_the_note_says_where_the_star_is_and_does_not_claim_a_ring_is_there(barnard: SimpleNamespace):
    note = stars.bright_note(stars.bright_nearby(*EPS_INDI_B, 0.1, MID_2026) or [])
    assert note is not None
    assert "Gaia magnitude 4.3" in note and "6.7 arcminutes from the centre" in note and "outside the picture" in note
    assert "can leave rings" in note and "most likely" in note and "not a change on the sky" in note


def test_no_bright_star_means_no_note():
    assert stars.bright_note([]) is None


def test_a_bright_star_at_the_centre_is_described_as_such():
    # R Draconis itself, as Gaia lists it (G = 6.37), is the centre of its own view.
    note = stars.bright_note([{"source_id": "1648328016354496384", "gmag": 6.37, "distance_arcmin": 0.0,
                               "east_arcsec": 0.0, "north_arcsec": 0.0, "inside_picture": True}])
    assert note is not None and "Gaia magnitude 6.4, at the centre of this view" in note


def test_when_gaia_does_not_answer_the_stars_still_come_back_without_a_verdict(barnard: SimpleNamespace,
                                                                             monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)
    out = stars.field_stars(barnard.ra, barnard.dec)
    assert out["n_returned"] > 0                          # the ordinary overlay is unaffected
    assert out["bright_nearby"] is None and out["bright_note"] is None   # unknown, not "none"

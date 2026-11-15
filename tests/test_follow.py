"""backend/follow.py, offline, from real answers kept in tests/data/follow.

  horizons_vesta_tlist.json   the first four rows of a real JPL Horizons reply (4 Vesta as seen from SPHEREx, five
                              Aug 2025 times), exactly as JPL sent them; the request is stored beside the answer.
  sia_vesta_2026-07-16.xml    a real IRSA image-search answer: the SPHEREx exposures covering the place Vesta was on
                              15 July 2026, in one 29-minute window (8 images, with their footprints).
  points_*.json               real measured points of a body (from scripts/follow_body.py) for the band arithmetic.
  tests/data/cache/cutouts    the Barnard's Star cutouts the other tests use.

The geometry tests move a real exposure's own footprint centre or corners; nothing is invented about the sky.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from backend import follow, smallbodies, spherex

DATA = Path(__file__).parent / "data"
FOLLOW = DATA / "follow"


@pytest.fixture(scope="module")
def sia_rows() -> list[dict]:
    return follow.parse_sia((FOLLOW / "sia_vesta_2026-07-16.xml").read_bytes())


# --- names and the Horizons reply -------------------------------------------------------------------------------

@pytest.mark.parametrize("name, command", [
    ("Pluto", "999"), ("pluto", "999"), ("3I/ATLAS", "DES=3I;CAP"), ("4 Vesta", "4;"),
    ("C/2025 R2 (SWAN)", "DES=C/2025 R2;CAP"), ("13P/Olbers", "DES=13P;CAP"), ("Makemake", "136472;"),
])
def test_horizons_command(name: str, command: str) -> None:
    assert follow.horizons_command(name) == command


def test_parse_horizons_reads_the_real_reply() -> None:
    saved = json.loads((FOLLOW / "horizons_vesta_tlist.json").read_text())
    rows = follow.parse_horizons(json.loads(saved["text"])["result"])
    assert len(rows) == 4
    first = rows[0]
    assert (first["ra"], first["dec"]) == (223.02473, -11.99229)
    assert first["vmag"] == 7.272                       # APmag for an asteroid
    assert first["r_au"] == pytest.approx(2.148884610981)
    assert first["delta_au"] == pytest.approx(1.86490575786135)
    assert first["elong"] == pytest.approx(91.6844)
    assert first["rate_arcsec_h"] == pytest.approx(np.hypot(45.39803, -4.16983))


def test_parse_horizons_names_what_is_missing() -> None:
    with pytest.raises(follow.FollowError, match="columns"):
        follow.parse_horizons("header, only\nline two\n$$SOE\n1,2\n$$EOE")


def test_positions_at_asks_horizons_in_the_stored_way(cache_dir: Path, network: list[str]) -> None:
    """The saved reply is put in the cache under the key the code would use; no request goes out."""
    saved = json.loads((FOLLOW / "horizons_vesta_tlist.json").read_text())
    key = hashlib.sha1((saved["url"] + json.dumps(saved["params"], sort_keys=True)).encode()).hexdigest()[:20]
    target = smallbodies.CACHE_DIR / "jpl" / f"{key}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FOLLOW / "horizons_vesta_tlist.json", target)
    mjds = [float(t) - 2400000.5 for t in saved["params"]["TLIST"].replace("'", "").split()]
    rows = follow.positions_at("4 Vesta", mjds)
    assert [r["mjd"] for r in rows] == mjds
    assert rows[0]["dec"] == -11.99229
    assert network == []


# --- the path in chunks -------------------------------------------------------------------------------------------

def _path() -> list[dict]:
    saved = json.loads((FOLLOW / "horizons_vesta_tlist.json").read_text())
    rows = follow.parse_horizons(json.loads(saved["text"])["result"])
    for r, t in zip(rows, saved["params"]["TLIST"].replace("'", "").split(), strict=True):
        r["mjd"] = float(t) - 2400000.5
    return rows


def test_chunks_follow_the_elongation_and_the_distance_moved() -> None:
    path = _path()                                   # 3 days apart at most, elongation about 91 degrees
    assert follow.chunks(path, (0.0, 20.0)) == []     # nothing is in the range: no stretch
    every = follow.chunks(path, (70.0, 140.0))
    assert every[0]["t1"] == path[0]["mjd"]
    # the rows at 2460893.047815 are the same time twice: they are never split from each other
    covered = [(c["t1"], c["t2"]) for c in every]
    assert all(t2 > t1 for t1, t2 in covered)
    assert every[-1]["t2"] == path[-1]["mjd"] + 1.0
    # a body that moved more than CHUNK_DEG between two rows is searched from both ends, in separate stretches
    moved = float(follow.sep_deg(path[0]["ra"], path[0]["dec"], path[-1]["ra"], path[-1]["dec"]))
    assert moved > follow.CHUNK_DEG
    assert len(every) >= 2


# --- the exposure list ------------------------------------------------------------------------------------------

def test_parse_sia_reads_exposures_and_footprints(sia_rows: list[dict]) -> None:
    assert len(sia_rows) == 8
    first = sia_rows[0]
    assert first["obs_id"].startswith("2026W29_")
    assert 1 <= first["detector"] <= 6
    assert first["exptime"] == pytest.approx(113.58, abs=0.1)
    assert len(first["region"]) == 4                  # the closing corner is dropped
    assert 0.7 < first["wave_min"] < first["wave_max"] < 5.1
    assert first["url"].startswith("https://irsa.ipac.caltech.edu/")


def test_parse_region() -> None:
    corners = follow.parse_region("POLYGON ICRS 24.5 -0.7 21.3 -2.0 20.1 1.1 23.3 2.5 24.5 -0.7")
    assert corners == [(24.5, -0.7), (21.3, -2.0), (20.1, 1.1), (23.3, 2.5)]


def test_edge_distance_is_positive_inside_negative_outside(sia_rows: list[dict]) -> None:
    corners = sia_rows[0]["region"]
    ra = float(np.mean([c[0] for c in corners]))
    dec = float(np.mean([c[1] for c in corners]))
    inside = follow.edge_distance_deg(corners, ra, dec)
    assert 1.0 < inside < 2.0                          # a 3.5 degree image: the centre is about 1.7 degrees from the edge
    assert follow.edge_distance_deg(corners, ra + 5.0, dec) < 0
    assert follow.edge_distance_deg(corners, ra, dec + 3.0) == pytest.approx(-(3.0 - 1.74), abs=0.2)


def test_select_exposures_keeps_those_with_room_for_the_sky_ring(sia_rows: list[dict]) -> None:
    exp = sia_rows[:3]
    centres = [(float(np.mean([c[0] for c in e["region"]])), float(np.mean([c[1] for c in e["region"]]))) for e in exp]
    first = exp[0]["region"]
    # a point 0.01 degree inside the first corner's edge (on the segment from corner 0 to corner 1)
    ra_e = (first[0][0] + first[1][0]) / 2 + 0.01 * np.sign(centres[0][0] - first[0][0])
    dec_e = (first[0][1] + first[1][1]) / 2
    positions = [{"ra": centres[0][0], "dec": centres[0][1]}, {"ra": ra_e, "dec": dec_e},
                 {"ra": centres[2][0] + 20.0, "dec": centres[2][1]}]
    usable, near = follow.select_exposures(exp, positions)
    assert [u["obs_id"] for u in usable] == [exp[0]["obs_id"]]
    assert usable[0]["edge_deg"] > follow.EDGE_MARGIN_DEG
    assert near == [] or near[0]["obs_id"] == exp[1]["obs_id"]      # the edge point is near the edge, or just outside
    assert all(e["obs_id"] != exp[2]["obs_id"] for e in usable + near)   # a position far outside is dropped


def test_clusters_group_nearby_positions() -> None:
    def e(ra: float, mjd: float) -> dict:
        return {"mjd": mjd, "pred": {"ra": ra, "dec": 0.0}}
    # positions are only labels for the grouping rule here: 0.01 deg is 36 arcsec, 0.1 deg is 360 arcsec
    groups = follow.clusters([e(10.0, 1.0), e(10.01, 1.1), e(10.1, 1.2), e(10.0, 100.0)])
    assert groups == [[0, 1], [2], [3]]


# --- measuring in a real cutout -----------------------------------------------------------------------------------

BARNARD_CUTOUT = "cutouts/01e6af5d45/2026W11_2A_0501_1_D5.fits"


def test_measure_at_empty_place_and_noise_in_a_real_cutout() -> None:
    cut = follow.load_cutout(DATA / "cache" / BARNARD_CUTOUT)
    ny, nx = cut["data"].shape
    ra, dec = (float(v) for v in cut["wcs"].all_pix2world(nx / 2 + 8, ny / 2 - 6, 0))
    m = follow.measure_at(cut, ra, dec)
    assert m["status"] in ("ok", "saturated", "flagged", "no_sky")
    assert m["wavelength_um"] is not None and 3.8 < m["wavelength_um"] < 5.1      # detector 5
    if m["status"] == "ok":
        assert m["err_mjy"] > 0 and m["err_large_mjy"] > 0
        noise = follow.local_noise(cut, ra, dec)
        assert noise["n_places"] <= follow.NOISE_PLACES
    # far off the image: said so, nothing measured
    off = follow.measure_at(cut, ra + 1.0, dec)
    assert off["status"] == "off_image" and off["flux_mjy"] is None


def test_the_circles_are_the_stated_size() -> None:
    assert follow.SMALL_PX * 6.15 == pytest.approx(12.3)
    assert follow.LARGE_PX * 6.15 == pytest.approx(36.9)


def test_fixed_source_verdict() -> None:
    def o(flux: float, err: float) -> dict:
        return {"status": "ok", "flux_mjy": flux, "err_mjy": err}
    seen = follow.fixed_source_verdict(1.0, [o(0.9, 0.1), o(1.1, 0.1), o(0.2, 0.1), o(1.0, 0.1)])
    assert seen["fixed"] and seen["star_in_the_way"] and seen["n_with_source"] == 3
    faint = follow.fixed_source_verdict(100.0, [o(0.9, 0.1), o(1.1, 0.1), o(1.0, 0.1)])
    assert faint["fixed"] and not faint["star_in_the_way"]          # there, but 1% of what was measured
    none = follow.fixed_source_verdict(1.0, [o(0.0, 0.1), o(-0.1, 0.1), o(0.1, 0.1)])
    assert not none["fixed"]
    few = follow.fixed_source_verdict(1.0, [o(1.0, 0.1), o(1.0, 0.1)])
    assert not few["fixed"]                                          # fewer than three: no verdict

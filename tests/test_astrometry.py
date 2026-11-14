"""Where a star is on a given date: backend/astrometry.py against hand-computed values and astropy."""
from __future__ import annotations

import io

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Distance, SkyCoord, get_body_barycentric
from astropy.io.votable import from_table
from astropy.table import MaskedColumn, Table
from astropy.time import Time

from backend import astrometry

J2026_MJD = 51544.5 + 26 * 365.25   # Julian year 2026.0 as a Modified Julian Date (61041.0)


@pytest.fixture
def barnard_gaia(barnard_resolved: dict) -> dict:
    """Barnard's Star as Gaia DR3 lists it (epoch 2016.0), taken from the cached /api/resolve answer."""
    r = barnard_resolved
    return {"source_id": r["gaia_source_id"], "ra": r["catalogue"]["ra"], "dec": r["catalogue"]["dec"],
            "pmra": r["pmra"], "pmdec": r["pmdec"], "parallax": r["parallax"],
            "radial_velocity": r["radial_velocity_km_s"]}


def separation(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Angle between two (ra, dec) positions in arcseconds, by astropy."""
    return float(SkyCoord(a[0] * u.deg, a[1] * u.deg).separation(SkyCoord(b[0] * u.deg, b[1] * u.deg)).arcsec)


# ----------------------------------------------------------------- offset_arcsec

def test_offset_is_east_and_north_in_arcseconds():
    assert astrometry.offset_arcsec(10.0, 20.0, 10.0, 20.0 + 1 / 3600) == pytest.approx((0.0, 1.0), abs=1e-9)
    # One arcsecond of right ascension is half an arcsecond on the sky at declination 60.
    assert astrometry.offset_arcsec(10.0, 60.0, 10.0 + 1 / 3600, 60.0) == pytest.approx((0.5, 0.0), abs=1e-9)
    # Smaller right ascension is west, so negative.
    assert astrometry.offset_arcsec(10.0, 0.0, 10.0 - 2 / 3600, 0.0) == pytest.approx((-2.0, 0.0), abs=1e-9)


@pytest.mark.parametrize("dec", [-70.0, 0.0, 4.77, 45.0, 66.755, 85.0])
def test_offset_agrees_with_astropy(dec: float):
    start = SkyCoord(100.0 * u.deg, dec * u.deg)
    end = start.spherical_offsets_by(-3.0 * u.arcsec, 4.0 * u.arcsec)
    offset = astrometry.offset_arcsec(start.ra.deg, start.dec.deg, end.ra.deg, end.dec.deg)
    assert offset == pytest.approx((-3.0, 4.0), abs=1e-3)   # worst measured: 0.0003 arcsec at declination 85


@pytest.mark.xfail(reason="offset_arcsec does not wrap right ascension at 0/360: points 0.7 arcsec apart come out "
                          "1.3 million arcsec apart, so _find_target misses a star just across RA 0h")
def test_offset_across_ra_zero():
    east, north = astrometry.offset_arcsec(359.9999, 10.0, 0.0001, 10.0)
    assert (east, north) == pytest.approx((0.0002 * 3600 * np.cos(np.radians(10.0)), 0.0), abs=1e-3)


# --------------------------------------------------------------------- propagate

def test_barnards_star_at_2026(barnard_gaia: dict):
    """Gaia DR3 (epoch 2016.0) moved to 2026.0 is RA 269.446267, Dec +4.768222.

    Those six decimals are also the centre the cached cutouts were fetched for, so a
    change here would leave the warmed cache unused.
    """
    ra, dec = astrometry.propagate(barnard_gaia, 2026.0)
    assert (round(ra, 6), round(dec, 6)) == (269.446267, 4.768222)


def test_propagate_is_straight_line_motion_in_space(barnard_gaia: dict):
    """The same ten years by hand: position vector plus velocity vector times time."""
    a, d = np.radians(barnard_gaia["ra"]), np.radians(barnard_gaia["dec"])
    distance = 1.0 / np.radians(barnard_gaia["parallax"] / 3.6e6)                # au
    to_star = np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])
    east = np.array([-np.sin(a), np.cos(a), 0.0])
    north = np.array([-np.sin(d) * np.cos(a), -np.sin(d) * np.sin(a), np.cos(d)])
    mas_per_year = np.radians(1.0 / 3.6e6) * distance                            # au per year across the sky
    km_per_s = 31_557_600 / 149_597_870.7                                        # au per Julian year
    velocity = (mas_per_year * (barnard_gaia["pmra"] * east + barnard_gaia["pmdec"] * north)
                + km_per_s * barnard_gaia["radial_velocity"] * to_star)
    x, y, z = distance * to_star + 10.0 * velocity
    by_hand = (np.degrees(np.arctan2(y, x)) % 360.0, np.degrees(np.arcsin(z / np.sqrt(x * x + y * y + z * z))))

    assert separation(astrometry.propagate(barnard_gaia, 2026.0), by_hand) < 0.001   # measured: 0.00001 arcsec


def test_radial_velocity_matters_for_barnards_star(barnard_gaia: dict):
    """Without Gaia's radial velocity the star lands 0.06 arcsec south, on a different cache key (CLAUDE.md)."""
    no_rv = {k: v for k, v in barnard_gaia.items() if k != "radial_velocity"}
    ra, dec = astrometry.propagate(no_rv, 2026.0)
    assert round(dec, 6) == 4.768204
    east, north = astrometry.offset_arcsec(ra, dec, *astrometry.propagate(barnard_gaia, 2026.0))
    assert north == pytest.approx(0.064, abs=0.005)
    assert abs(east) < 0.01


def test_propagate_starts_from_the_catalogue_epoch():
    """WISE 0855 comes from SIMBAD, whose positions are for 2000.0, not Gaia's 2016.0 (numbers in CLAUDE.md)."""
    simbad = {"ra": 133.81890825, "dec": -7.247048, "pmra": -8123.7, "pmdec": 673.2, "parallax": 439.0,
              "ref_epoch": 2000.0}
    assert astrometry.propagate(simbad, 2026.0) == pytest.approx((133.759765, -7.242182), abs=1e-6)


def test_no_proper_motion_means_no_move():
    still = {"ra": 10.0, "dec": -5.0, "pmra": None, "pmdec": None, "parallax": None}
    assert astrometry.propagate(still, 2026.0) == (10.0, -5.0)
    assert astrometry.position_at(still, J2026_MJD) == (10.0, -5.0)
    # A zero or negative parallax counts as unknown, as /api/frames documents.
    assert astrometry.position_at({**still, "parallax": -3.0}, J2026_MJD) == (10.0, -5.0)


# ------------------------------------------------------------------- position_at

def test_position_at_is_linear_proper_motion(barnard_gaia: dict):
    ra, dec = astrometry.position_at(barnard_gaia, J2026_MJD, parallax=False)
    # 10362.394 mas/yr for 10 years is 103.62394 arcsec = 0.02878443 degrees north of 4.73942005.
    assert dec == pytest.approx(4.76820448, abs=1e-8)
    # -801.551 mas/yr for 10 years is 8.01551 arcsec west on the sky; divide by cos(dec) = 0.996581 for RA.
    assert ra == pytest.approx(269.44626836, abs=1e-8)


@pytest.mark.parametrize(("when", "ra", "expected"), [
    # March equinox: the Sun is at RA 0h on the equator, 0.996 au away. A star at RA 6h
    # on the equator is pulled straight towards it: west by its parallax, not north or south.
    ("2026-03-20T14:46:00", 90.0, (-1.00, 0.00)),
    # June solstice: the Sun is at RA 6h, Dec +23.4, 1.016 au away. A star at RA 0h on the equator
    # is pulled east by 1.016 * cos(23.4 deg) and north by 1.016 * sin(23.4 deg) parallaxes.
    ("2026-06-21T08:25:00", 0.0, (0.93, 0.40)),
])
def test_parallax_pulls_a_star_towards_the_sun(when: str, ra: float, expected: tuple[float, float]):
    star = {"ra": ra, "dec": 0.0, "pmra": 0.0, "pmdec": 0.0, "parallax": 1000.0}   # one arcsecond
    shift = astrometry.offset_arcsec(ra, 0.0, *astrometry.position_at(star, Time(when, scale="utc").mjd))
    assert shift == pytest.approx(expected, abs=0.03)   # measured: (-0.998, -0.000) and (0.937, 0.406)


def seen_from_earth(src: dict, mjd: float, radial_velocity: float = 0.0) -> tuple[float, float]:
    """Reference: astropy moves the star through space, then it is looked at from where the Earth is."""
    when = Time(mjd, format="mjd")
    star = SkyCoord(ra=src["ra"] * u.deg, dec=src["dec"] * u.deg, distance=Distance(parallax=src["parallax"] * u.mas),
                    pm_ra_cosdec=src["pmra"] * u.mas / u.yr, pm_dec=src["pmdec"] * u.mas / u.yr,
                    radial_velocity=radial_velocity * u.km / u.s, obstime=Time(2016.0, format="jyear"))
    x, y, z = (star.apply_space_motion(when).cartesian.xyz.to_value(u.au)
               - get_body_barycentric("earth", when).xyz.to_value(u.au))
    return float(np.degrees(np.arctan2(y, x)) % 360.0), float(np.degrees(np.arcsin(z / np.sqrt(x * x + y * y + z * z))))


@pytest.mark.parametrize("mjd", [60910.64, 61114.03, 61270.87])   # mean dates of the three SPHEREx visits
def test_position_at_agrees_with_astropy(barnard_gaia: dict, mjd: float):
    got = astrometry.position_at(barnard_gaia, mjd)
    # Same physics (proper motion and parallax): measured agreement 0.0004 arcsec.
    assert separation(got, seen_from_earth(barnard_gaia, mjd)) < 0.002
    # Full physics. position_at leaves out the radial velocity, which for this star is worth
    # 0.06 to 0.07 arcsec in 2025-26: a hundredth of a SPHEREx pixel, as its docstring says.
    assert separation(got, seen_from_earth(barnard_gaia, mjd, barnard_gaia["radial_velocity"])) < 0.1
    # Parallax is not a detail for this star: it moves it by about half an arcsecond.
    assert 0.4 < separation(got, astrometry.position_at(barnard_gaia, mjd, parallax=False)) < 0.56


# --------------------------------------------------- Gaia rows and the name lookup

def test_gaia_cone_turns_missing_values_into_none_and_caches(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """A star without a proper motion must come back with None, not NaN (NaN is not valid JSON)."""
    table = Table({
        "source_id": np.array([4472832130942575872, 4472832130942575999], dtype="int64"),
        "ra": [269.4485, 269.4600], "dec": [4.7394, 4.7700],
        "pmra": MaskedColumn([-801.55, 0.0], mask=[False, True]),
        "pmdec": MaskedColumn([10362.39, 0.0], mask=[False, True]),
        "parallax": MaskedColumn([546.98, 0.0], mask=[False, True]),
        "phot_g_mean_mag": [8.19, 16.5],
    })
    answer = io.BytesIO()
    from_table(table).to_xml(answer)
    asked: list[str] = []

    def fake_http_get(url: str, params: dict | None = None, **_: object) -> bytes:
        asked.append(url)
        return answer.getvalue()

    monkeypatch.setattr(astrometry, "http_get", fake_http_get)
    monkeypatch.setattr(astrometry, "CACHE", tmp_path)

    stars = astrometry.gaia_cone(269.4463, 4.7682, 0.01)
    assert [s["source_id"] for s in stars] == ["4472832130942575872", "4472832130942575999"]
    assert stars[0]["pmdec"] == pytest.approx(10362.39)
    assert (stars[1]["pmra"], stars[1]["pmdec"], stars[1]["parallax"]) == (None, None, None)
    # The second call is answered from the file the first one wrote.
    assert astrometry.gaia_cone(269.4463, 4.7682, 0.01) == stars
    assert len(asked) == 1
    assert len(list((tmp_path / "queries").glob("gaia_*.json"))) == 1


# SIMBAD's `basic` row for an object, in the column order of astrometry._BASIC.
BARNARD_IN_SIMBAD = [1, "NAME Barnard's star", 269.4520769586187, 4.693364966576667, -801.551, 10362.394, 546.9759,
                     "BY*", "2020yCat.1350....0G", "2020yCat.1350....0G"]
WISE0855_IN_SIMBAD = [2, "WISEA J085510.74-071442.5", 133.81890825, -7.247048000000001, -8123.7, 673.2, 439.0,
                      "BD*", "2021ApJS..253....7K", "2021ApJS..253....7K"]


def simbad_knowing(objects: dict[str, list], gaia_ids: dict[int, str]):
    """A stand-in for astrometry._simbad that knows the given names (as quoted in the query)."""
    def fake(adql: str) -> list[list]:
        if "FROM ident WHERE oidref" in adql:
            return [[gaia_id] for oid, gaia_id in gaia_ids.items() if f"oidref = {oid} " in adql]
        return [row for name, row in objects.items() if f"i.id = {name}" in adql]
    return fake


def test_resolve_uses_gaia_when_simbad_points_to_it(monkeypatch: pytest.MonkeyPatch, tmp_path,
                                                    barnard_gaia: dict, barnard_resolved: dict):
    """Fed the catalogue rows of 2026-11-14, resolve_name gives the answer cached that day."""
    # The apostrophe must arrive doubled: the name goes into an ADQL query.
    monkeypatch.setattr(astrometry, "_simbad", simbad_knowing({"'Barnard''s Star'": BARNARD_IN_SIMBAD},
                                                              {1: "Gaia DR3 4472832130942575872"}))
    monkeypatch.setattr(astrometry, "gaia_source", lambda source_id: dict(barnard_gaia))
    monkeypatch.setattr(astrometry, "CACHE", tmp_path)

    got = astrometry.resolve_name("  Barnard's   Star ")
    for field in ("ra", "dec", "epoch", "pmra", "pmdec", "parallax", "source", "gaia_source_id", "catalogue",
                  "j2000", "moved_since_2000_arcsec", "notes"):
        assert got[field] == barnard_resolved[field], field
    assert (got["ra"], got["dec"], got["source"]) == (269.446267, 4.768222, "Gaia DR3")
    assert len(list((tmp_path / "queries").glob("resolve_*.json"))) == 1


def test_resolve_falls_back_to_simbad_for_objects_gaia_does_not_list(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """WISE 0855: found through the alias table, no Gaia identifier, 26 years of SIMBAD's motion applied."""
    monkeypatch.setattr(astrometry, "_simbad", simbad_knowing({"'WISE J085510.83-071442.5'": WISE0855_IN_SIMBAD}, {}))
    monkeypatch.setattr(astrometry, "CACHE", tmp_path)

    got = astrometry.resolve_name("WISE 0855")
    assert (got["ra"], got["dec"]) == (133.759765, -7.242182)   # the position CLAUDE.md records
    assert (got["source"], got["gaia_source_id"], got["catalogue"]["epoch"]) == ("SIMBAD", None, 2000.0)
    assert (got["pmra"], got["pmdec"], got["parallax"]) == (-8123.7, 673.2, 439.0)
    assert any("no Gaia DR3 identifier" in note for note in got["notes"])


def test_resolve_does_not_cache_an_answer_made_without_gaia(monkeypatch: pytest.MonkeyPatch, tmp_path,
                                                            network: list[str]):
    """Gaia is unreachable (the network is blocked): SIMBAD's values are used, and the next call tries again."""
    monkeypatch.setattr(astrometry, "_simbad", simbad_knowing({"'Barnard''s Star'": BARNARD_IN_SIMBAD},
                                                              {1: "Gaia DR3 4472832130942575872"}))
    monkeypatch.setattr(astrometry, "CACHE", tmp_path)

    got = astrometry.resolve_name("Barnard's Star")
    assert got["source"] == "SIMBAD"
    assert any("Gaia did not answer" in note for note in got["notes"])
    assert network == [astrometry.GAIA_TAP]
    assert not list((tmp_path / "queries").glob("resolve_*.json"))


def test_resolve_rejects_unknown_and_unusable_names(monkeypatch: pytest.MonkeyPatch, tmp_path):
    asked: list[str] = []

    def simbad_knows_nothing(adql: str) -> list[list]:
        asked.append(adql)
        return []

    monkeypatch.setattr(astrometry, "_simbad", simbad_knows_nothing)
    monkeypatch.setattr(astrometry, "CACHE", tmp_path)

    with pytest.raises(astrometry.NameNotFound):
        astrometry.resolve_name("No Such Star 12345")
    assert asked, "SIMBAD should have been asked"

    asked.clear()
    for unusable in ("", "   ", "x" * 81):
        with pytest.raises(astrometry.NameNotFound):
            astrometry.resolve_name(unusable)
    assert asked == [], "an empty or over-long name is refused without asking SIMBAD"

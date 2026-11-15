"""The "What is it?" lookup (backend/identify.py, /api/identify) on saved real catalogue answers.

tests/data/identify/cache holds the answers Gaia DR3 (from the ARI Heidelberg mirror; the
ESA archive did not answer that night) and SIMBAD (CfA mirror) gave on 2026-11-15 for the
seven test places, saved unchanged by `scripts/check_identify.py --save`. They are copied
into the test cache, so nothing here reaches the network. tests/data/identify/schema holds
the services' own column lists (TAP_SCHEMA.columns), against which the columns asked for
are checked.
"""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

from backend import identify, spherex

DATA = Path(__file__).parent / "data" / "identify"
FRONT = Path(__file__).parents[1] / "frontend" / "src" / "fixtures" / "identify"
# (ra, dec, epoch): the places on the pictures, as scripts/check_identify.py lists them.
PLACES = {
    "barnard": (269.446267, 4.768222, 2026.0),
    "epsindib": (331.096653, -56.800663, 2026.0),
    "wise0855": (133.759765, -7.242182, 2026.0),
    "rwaur": (76.956587, 30.401291, 2026.0),
    "rdra": (248.167233, 66.755024, 2026.0),
    "faint": (269.448524, 4.762903, 2026.0),
    "candidate": (253.18038, -44.67697, 2026.0),
    "barnard_visit3": (269.446116, 4.770171, 2026.676),
    "rdra_offset": (248.16885, 66.755363, 2026.0),
}


@pytest.fixture(scope="session")
def saved(cache_dir: Path) -> Path:
    """The saved catalogue answers, in the test cache where identify() looks for them."""
    queries = cache_dir / "queries"
    queries.mkdir(parents=True, exist_ok=True)
    for f in (DATA / "cache").glob("identify_*.json"):
        shutil.copyfile(f, queries / f.name)
    return queries


@pytest.fixture(scope="session")
def answers(saved: Path, network_log: list[str]) -> dict[str, dict]:
    network_log.clear()
    out = {key: identify.identify(ra, dec, epoch=epoch) for key, (ra, dec, epoch) in PLACES.items()}
    assert network_log == [], "every answer must come from the saved files"
    return out


def values_by_column(entry: dict) -> dict[str, dict]:
    return {v["column"]: v for v in entry["values"]}


def column_list(name: str) -> set[str]:
    with (DATA / "schema" / f"{name}.csv").open() as f:
        return {row["column_name"] for row in csv.DictReader(f)}


# ----------------------------------------------------------------- the columns asked for exist

def test_gaia_columns_are_in_the_archive_own_lists():
    assert set(identify.GAIA_SOURCE_COLUMNS) <= column_list("gaiadr3.gaia_source")
    assert set(identify.GAIA_AP_COLUMNS) <= column_list("gaiadr3.astrophysical_parameters")
    for key in identify.TEMPERATURE_ORDER + identify.RADIUS_ORDER:
        assert key in identify.GAIA_AP_COLUMNS


def test_simbad_columns_are_in_simbad_own_lists():
    assert set(identify.SIMBAD_BASIC_COLUMNS) <= column_list("simbad.basic")
    assert {"oidref", "teff", "bibcode"} <= column_list("simbad.mesFe_h")
    assert {"parent", "child"} <= column_list("simbad.h_link")
    assert {"oidref", "id"} <= column_list("simbad.ident")


def test_every_object_type_in_the_table_is_a_simbad_type():
    with (DATA / "schema" / "simbad.otypedef.csv").open() as f:
        codes = {row["otype"] for row in csv.DictReader(f)}
    assert set(identify.OBJECT_TYPES) <= codes, set(identify.OBJECT_TYPES) - codes


# ----------------------------------------------------------------- plain words

@pytest.mark.parametrize(("code", "label", "plain"), [
    ("BY*", "BY Draconis variable", "a cool star whose brightness changes a little as it spins"),
    ("BD*", "brown dwarf", "heavier than a planet, too light to burn hydrogen like a star"),
    ("Mi*", "Mira variable", "a cool giant star that swells and shrinks over many months"),
    ("Or*", "Orion variable", "a young star whose brightness changes unevenly"),
    ("TT*", "T Tauri star", "a very young star, still forming"),
    ("PM*", "high proper-motion star", "a star that moves quickly across the sky"),
])
def test_object_types_in_plain_words(code: str, label: str, plain: str):
    assert identify.object_type_words(code) == {"code": code, "label": label, "plain": plain, "candidate": False}


def test_candidate_types_say_possibly():
    assert identify.object_type_words("BD?") == {
        "code": "BD?", "label": "brown dwarf (candidate)",
        "plain": "possibly heavier than a planet, too light to burn hydrogen like a star", "candidate": True}


def test_no_type_words_name_a_colour():
    """The colour on the card is the one computed from a measured temperature; a type that said
    "red" beside a disc computed as orange would contradict it."""
    colours = re.compile(r"\b(red|orange|yellow|white|blue|bluest)\b")
    for words in [*identify.SPECTRAL_CLASSES.values(), *identify.SPECTRAL_DWARFS.values(),
                  *identify.SPECTRAL_GIANTS.values()]:
        assert not colours.search(words[1].replace("red dwarfs", "")), words
    assert identify.object_type_words("Y*?")["label"] == "young stellar object (candidate)"
    assert identify.object_type_words("Q?")["label"] == "quasar (candidate)"


def test_an_unknown_type_gets_no_invented_words():
    assert identify.object_type_words("zz9") == {"code": "zz9", "label": "SIMBAD type zz9", "plain": None,
                                                 "candidate": False}
    assert identify.object_type_words(None) is None


@pytest.mark.parametrize(("sp", "cls", "lum", "label", "pair"), [
    ("M4V", "M", "V", "M dwarf", False),
    ("T1V+T6V", "T", "V", "T dwarf", True),       # Epsilon Indi B: two brown dwarfs seen as one
    ("M4.5-6+e", "M", None, "M-type star", False),  # R Draconis: "+e" is part of one type
    ("K1/5e+K5e", "K", None, "K-type star", True),  # RW Aurigae, the system
    ("Y2", "Y", None, "Y dwarf", False),
    ("K2", "K", None, "K-type star", False),
    ("G2V", "G", "V", "G dwarf", False),
    ("K0III", "K", "III", "K giant", False),
    ("B1Ia", "B", "Ia", "B supergiant", False),
    ("F5IV", "F", "IV", "F subgiant", False),
    ("DA2.5", "D", None, "white dwarf", False),
    ("sdM1", "M", None, "M-type star", False),
])
def test_spectral_types_in_plain_words(sp: str, cls: str, lum: str | None, label: str, pair: bool):
    words = identify.spectral_words(sp)
    assert (words["class"], words["luminosity_class"], words["label"], words["pair"]) == (cls, lum, label, pair)
    assert words["plain"]


def test_no_spectral_type_no_words():
    assert identify.spectral_words(None) is None
    assert identify.spectral_words("") is None
    odd = identify.spectral_words("unknown")
    assert odd["class"] is None and odd["plain"] is None


# ----------------------------------------------------------------- derived values and their errors

def test_constants():
    assert identify.LY_PER_PC == pytest.approx(3.261563777, rel=1e-9)        # IAU parsec over the Julian light-year
    assert identify.KM_S_PER_AU_PER_YR == pytest.approx(4.740470464, rel=1e-9)
    assert identify.MAG_PER_RELATIVE_FLUX == pytest.approx(1.0857362, rel=1e-7)


def test_distance_from_parallax():
    d = identify.distance_from_parallax(546.975939730948, 0.040116355)        # Barnard's Star, Gaia DR3
    assert d["status"] == "from_parallax"
    assert d["pc"] == pytest.approx(1.828234, abs=1e-6)
    assert d["ly"] == pytest.approx(5.96290, abs=1e-5)
    assert d["pc_error"] == pytest.approx(1000 * 0.040116355 / 546.975939730948 ** 2, rel=1e-12)
    assert identify.distance_from_parallax(1.0, 0.25)["status"] == "parallax_too_uncertain"   # 4 times its error
    assert identify.distance_from_parallax(1.0, 0.2)["status"] == "from_parallax"            # 5 times
    assert identify.distance_from_parallax(-0.3, 0.2)["status"] == "negative_parallax"
    assert identify.distance_from_parallax(2.0, None)["pc"] is None


def test_total_motion_and_its_error():
    mu, err = identify.total_motion(3.0, 4.0, np.diag([0.3 ** 2, 0.4 ** 2]))
    assert mu == 5.0
    # By hand: g = (0.6, 0.8); variance = 0.36 x 0.09 + 0.64 x 0.16 = 0.1348.
    assert err == pytest.approx(math.sqrt(0.1348), rel=1e-12)
    rho = 0.5
    cov = np.array([[0.09, rho * 0.3 * 0.4], [rho * 0.3 * 0.4, 0.16]])
    assert identify.total_motion(3.0, 4.0, cov)[1] == pytest.approx(math.sqrt(0.1348 + 2 * 0.6 * 0.8 * 0.06), rel=1e-12)


def test_speed_error_without_correlations_is_the_quadrature_sum():
    plx, pmra, pmdec = 10.0, 300.0, -400.0
    s = np.array([0.5, 2.0, 3.0])
    v, err = identify.tangential_speed(plx, pmra, pmdec, np.diag(s ** 2))
    mu, mu_err = identify.total_motion(pmra, pmdec, np.diag(s[1:] ** 2))
    assert v == pytest.approx(4.740470464 * 500.0 / 10.0, rel=1e-9)
    assert err == pytest.approx(v * math.hypot(mu_err / mu, 0.5 / 10.0), rel=1e-12)


def test_speed_error_matches_a_numerical_derivative():
    """The analytic Jacobian against finite differences, with all three correlations set."""
    x0 = np.array([546.975939730948, -801.5509783684709, 10362.394206546573])
    sig = np.array([0.04, 0.032, 0.036])
    corr = np.array([[1.0, -0.06, 0.56], [-0.06, 1.0, 0.03], [0.56, 0.03, 1.0]])
    cov = corr * np.outer(sig, sig)
    _, err = identify.tangential_speed(*x0, cov)
    jac = np.zeros(3)
    for i in range(3):
        h = np.zeros(3)
        h[i] = 1e-4
        jac[i] = (identify.tangential_speed(*(x0 + h), None)[0] - identify.tangential_speed(*(x0 - h), None)[0]) / 2e-4
    assert err == pytest.approx(math.sqrt(jac @ cov @ jac), rel=1e-6)


def test_light_at_place_weights_flux_by_a_one_pixel_blur():
    at_place = identify._light_at_place({"phot_g_mean_mag": 15.0, "_sep": 0.0})
    assert at_place == pytest.approx(10 ** -6.0, rel=1e-12)
    # At half the FWHM the weight is one half, by definition of the FWHM.
    half = identify._light_at_place({"phot_g_mean_mag": 15.0, "_sep": identify.CHOOSE_FWHM_ARCSEC / 2})
    assert half == pytest.approx(at_place / 2, rel=1e-12)
    # A star at the place beats one 2.5 times brighter 4 arcsec away; one 2 arcsec away 5 times brighter wins.
    brighter_far = identify._light_at_place({"phot_g_mean_mag": 15.0 - 2.5 * math.log10(2.5), "_sep": 4.0})
    assert brighter_far < at_place
    brighter_near = identify._light_at_place({"phot_g_mean_mag": 15.0 - 2.5 * math.log10(5.0), "_sep": 2.0})
    assert brighter_near > at_place
    assert identify._light_at_place({"phot_g_mean_mag": None, "_sep": 0.0}) == 0.0


def test_temperature_choice_prefers_gaias_own_for_ultracool_and_hot_stars():
    def q(key: str, value: float) -> dict:
        return {"key": key, "value": value}
    assert identify._choose_temperature([q("teff_gspphot", 3000), q("teff_espucd", 2400)])["key"] == "teff_espucd"
    assert identify._choose_temperature([q("teff_gspphot", 3000), q("teff_espucd", 2900)])["key"] == "teff_gspphot"
    assert identify._choose_temperature([q("teff_gspphot", 9000), q("teff_esphs", 15000)])["key"] == "teff_esphs"
    assert identify._choose_temperature([q("teff_gspspec", 4250)])["key"] == "teff_gspspec"
    assert identify._choose_temperature([]) is None


def test_the_last_mirror_of_a_service_is_always_asked(saved: Path, network: list[str], monkeypatch):
    """One failure must not take a service away from every visitor for ten minutes."""
    def down(url: str, params: dict, **_: object) -> bytes:
        network.append(url)
        raise spherex.ArchiveError("down (test)")

    monkeypatch.setattr(identify, "_get", down)
    monkeypatch.setattr(identify, "_down", {})
    with pytest.raises(identify._Unanswered):
        identify._tap("gaia", "SELECT 1 -- first")
    network.clear()
    with pytest.raises(identify._Unanswered):
        identify._tap("gaia", "SELECT 1 -- second")
    # The ESA archive failed a moment ago and is skipped; the last mirror is asked again.
    assert network == [identify.GAIA_TAPS[-1][1]]


def test_simbad_error_ellipse():
    east, north = identify._simbad_pm_error({"pm_err_maj": 2.0, "pm_err_min": 1.0, "pm_err_angle": 90})
    assert (east, north) == pytest.approx((2.0, 1.0))         # major axis pointing east
    east, north = identify._simbad_pm_error({"pm_err_maj": 2.0, "pm_err_min": 1.0, "pm_err_angle": 0})
    assert (east, north) == pytest.approx((1.0, 2.0))
    assert identify._simbad_pm_error({"pm_err_maj": None, "pm_err_min": None}) is None


# ----------------------------------------------------------------- the test places, on real answers

def test_barnards_star(answers: dict[str, dict]):
    a = answers["barnard"]
    assert a["unreachable"] == [] and a["nothing_catalogued"] is False
    g, s = a["gaia"], a["simbad"]
    assert g["source_id"] == "4472832130942575872" and g["separation_arcsec"] < 0.1
    assert s["main_id"] == "NAME Barnard's star" and s["display_name"] == "Barnard's star"
    assert a["match"]["same"] is True and a["match"]["how"] == "identifier"
    assert "NAME" not in a["match"]["text"]
    assert a["choice"]["how"] == "named"
    assert s["type"]["code"] == "BY*" and s["spectral_type"]["label"] == "M dwarf"
    assert s["spectral_type"]["plain"] == "a small, cool star (astronomers call these red dwarfs)"
    assert g["resolve_position"] == {"ra": pytest.approx(269.4462669), "dec": pytest.approx(4.7682223), "epoch": 2026.0}
    assert s["references"] == 924
    assert [p["display_name"] for p in s["planets"]] == ["Barnard's Star b", "Barnard's Star c", "Barnard's Star d",
                                                        "Barnard's Star e"]
    t, r = a["portrait"]["temperature"], a["portrait"]["radius"]
    assert t["column"] == "gaiadr3.astrophysical_parameters.teff_gspphot"
    assert t["value"] == pytest.approx(3099.6, abs=0.1)
    assert (t["lower"], t["upper"]) == pytest.approx((3098.76, 3101.63), abs=0.01)
    assert r["column"] == "gaiadr3.astrophysical_parameters.radius_flame"
    assert r["value"] == pytest.approx(0.2022, abs=1e-4)
    assert a["portrait"]["luminosity"]["value"] == pytest.approx(0.003398, abs=1e-6)
    d = a["derived"]
    assert d["distance"]["status"] == "from_parallax" and d["distance"]["ly"] == pytest.approx(5.963, abs=1e-3)
    assert d["motion"]["arcsec_per_year"] == pytest.approx(10.393, abs=1e-3)
    assert d["motion"]["pixels_per_year"] == pytest.approx(1.690, abs=1e-3)
    assert d["speed"]["km_s"] == pytest.approx(90.08, abs=0.01)
    v = values_by_column(g)
    assert v["gaiadr3.gaia_source.parallax"]["error"] == pytest.approx(0.040116, abs=1e-6)
    assert v["gaiadr3.gaia_source.phot_g_mean_mag"]["value"] == pytest.approx(8.194, abs=1e-3)
    assert v["gaiadr3.gaia_source.bp_rp"]["value"] == pytest.approx(2.834, abs=1e-3)
    # Gaia's model values say so, and carry their quality flags.
    assert t["model"] is True and v["gaiadr3.gaia_source.parallax"]["model"] is False
    assert r["flags"] == {"column": "gaiadr3.astrophysical_parameters.flags_flame", "value": "20", "meaning": None,
                          "lowest_quality": False}
    assert v["gaiadr3.astrophysical_parameters.teff_gspspec"]["flags"]["value"].startswith("1000013")
    # A parallax this large needs no zero-point remark.
    assert not any("offset" in n for n in a["notes"])
    # SIMBAD's own list of published temperatures: shown to experts, not drawn (Gaia's is there).
    assert s["temperatures"]["n"] == 55 and s["temperatures"]["median"] == 3243
    # A faint background star shares the pixel; nothing else does.
    same = [n for n in a["neighbours"] if n["same_pixel"]]
    assert [(n["source_id"], n["g_mag"]) for n in same] == [("4472835979229621248", 20.9)]


def test_barnard_on_a_visit_3_picture_is_still_barnard(answers: dict[str, dict]):
    """Pressed on a picture of 2026-09-04, where it is 7 arcsec from its 2026.0 place."""
    a = answers["barnard_visit3"]
    assert a["query"]["epoch"] == 2026.676 and a["nothing_catalogued"] is False
    assert a["gaia"]["source_id"] == "4472832130942575872" and a["gaia"]["separation_arcsec"] < 0.1
    assert a["simbad"]["main_id"] == "NAME Barnard's star"
    # Its place at 2026.0, for "Look at this one", is the same as the 2026.0 lookup's.
    assert a["gaia"]["resolve_position"] == answers["barnard"]["gaia"]["resolve_position"]


def test_epsilon_indi_b_never_gets_the_bright_stars_numbers(answers: dict[str, dict]):
    a = answers["epsindib"]
    g, s = a["gaia"], a["simbad"]
    assert g["source_id"] == "6412596012146801152" and s["main_id"] == "* eps Ind B"
    assert s["spectral_type"]["pair"] is True and s["spectral_type"]["parts"] == ["T1V", "T6V"]
    assert s["type"]["code"] == "BD*"
    assert s["type"]["plain"] == "heavier than a planet, too light to burn hydrogen like a star"
    t = a["portrait"]["temperature"]
    assert t["column"] == "gaiadr3.astrophysical_parameters.teff_espucd"
    assert (t["value"], t["error"]) == pytest.approx((1417.0, 98.1), abs=0.1)
    # ESP-UCD's own quality class for it is the lowest of three.
    assert t["flags"]["value"] == "20" and t["flags"]["lowest_quality"] is True
    assert t["model"] is True
    assert a["portrait"]["radius"] is None
    assert a["derived"]["distance"]["ly"] == pytest.approx(12.05, abs=0.01)
    # Epsilon Indi A (G = 4.3, 6.7 arcmin away) is nowhere in the answer.
    text = json.dumps(a)
    assert "eps Ind A" not in text and "* eps Ind\"" not in text
    assert all(n["g_mag"] is None or n["g_mag"] > 15 for n in a["neighbours"])
    assert values_by_column(g)["gaiadr3.gaia_source.phot_g_mean_mag"]["value"] == pytest.approx(18.03, abs=0.01)


def test_wise_0855_has_simbad_numbers_only(answers: dict[str, dict]):
    a = answers["wise0855"]
    assert a["gaia"] is None
    s = a["simbad"]
    assert s["main_id"] == "WISEA J085510.74-071442.5" and s["spectral_type"]["class"] == "Y"
    assert s["gaia_dr3_ids"] == []
    assert [(v["column"], v["value"], v["error"]) for v in s["values"]] == [
        ("basic.plx_value", 439, 2.4), ("basic.pmra", -8123.7, pytest.approx(1.3)), ("basic.pmdec", 673.2,
                                                                                   pytest.approx(1.3))]
    assert {v["reference"] for v in s["values"]} == {"2021ApJS..253....7K"}
    # No temperature is in either catalogue, so nothing may say how cold it is.
    assert a["portrait"] == {"temperature": None, "radius": None, "luminosity": None}
    assert s["temperatures"]["n"] == 0
    d = a["derived"]
    assert d["from"] == "SIMBAD" and d["distance"]["ly"] == pytest.approx(7.430, abs=1e-3)
    assert d["motion"]["arcsec_per_year"] == pytest.approx(8.15, abs=0.01)
    # The G = 16.3 star (docs: 11.4, 8.1 and 4.3 arcsec away in visits 1 to 3) is a neighbour, not the object.
    first = a["neighbours"][0]
    assert first["source_id"] == "5756956644387831296" and first["g_mag"] == 16.31
    assert first["separation_arcsec"] == pytest.approx(6.81, abs=0.01) and first["same_pixel"] is False


def test_rw_aurigae_is_a_close_pair_and_the_brighter_star_is_the_object(answers: dict[str, dict]):
    """The place is SIMBAD's entry for the system, V* RW Aur, which names no Gaia source. Of the two
    stars in the blur, A (G 12.18, 1.65 arcsec) puts more light there than B (G 13.04, 0.18 arcsec)."""
    a = answers["rwaur"]
    assert a["gaia"]["source_id"] == "156430822114424576" and a["simbad"]["main_id"] == "V* RW Aur A"
    assert a["choice"]["how"] == "light" and a["match"]["how"] == "identifier"
    assert a["simbad"]["type"]["code"] == "Or*" and a["simbad"]["references"] == 45
    system = next(p for p in a["simbad"]["parents"] if p["name"] == "V* RW Aur")
    assert system["references"] == 828
    pair = [n for n in a["neighbours"] if n["same_pixel"]]
    assert [(n["simbad_name"], n["display_name"], n["g_mag"]) for n in pair] == [("V* RW Aur B", "RW Aur B", 13.04)]
    assert pair[0]["separation_arcsec"] == pytest.approx(0.18, abs=0.02)
    assert pair[0]["from_object_arcsec"] == pytest.approx(1.52, abs=0.02)
    # A's own parallax: 509 light-years, not B's 598 from a RUWE-16 fit.
    assert a["derived"]["distance"]["ly"] == pytest.approx(509.1, abs=0.1)
    assert values_by_column(a["gaia"])["gaiadr3.gaia_source.ruwe"]["value"] == pytest.approx(1.50, abs=0.01)
    assert a["portrait"]["temperature"] is None and a["portrait"]["radius"] is None


def test_r_draconis_has_no_gaia_temperature_or_radius(answers: dict[str, dict]):
    a = answers["rdra"]
    assert a["gaia"]["source_id"] == "1648328016354496384" and a["simbad"]["main_id"] == "V* R Dra"
    assert a["simbad"]["type"]["code"] == "Mi*"
    assert a["portrait"] == {"temperature": None, "radius": None, "luminosity": None}
    v = values_by_column(a["gaia"])
    assert v["gaiadr3.gaia_source.phot_variable_flag"]["value"] == "VARIABLE"
    # Its G "error" is the spread of a variable star's measurements, and says so.
    assert "variable" in v["gaiadr3.gaia_source.phot_g_mean_mag"]["note"]
    assert a["derived"]["distance"]["ly"] == pytest.approx(2607, abs=1)
    # The two faint sources 4 arcsec away have only 2-parameter solutions from 3 and 4 visibility
    # periods beside a star 13 magnitudes brighter: marked as possibly not real.
    assert [(n["source_id"], n["possibly_spurious"]) for n in a["neighbours"]] == [
        ("1648328016354500352", True), ("1648328016354504064", True)]


def test_a_press_beside_r_draconis_is_still_r_draconis(answers: dict[str, dict]):
    """2.6 arcsec off R Dra and 1.5 arcsec from a faint false-looking source: the star wins."""
    a = answers["rdra_offset"]
    assert a["gaia"]["source_id"] == "1648328016354496384" and a["simbad"]["main_id"] == "V* R Dra"
    assert a["gaia"]["separation_arcsec"] == pytest.approx(2.6, abs=0.05)
    assert a["choice"]["how"] == "light"
    assert a["neighbours"][0]["separation_arcsec"] == pytest.approx(1.53, abs=0.02)


def test_an_ordinary_faint_star(answers: dict[str, dict]):
    a = answers["faint"]
    assert a["simbad"] is None and a["gaia"]["source_id"] == "4472835876142910336"
    assert a["portrait"]["temperature"]["value"] == pytest.approx(4800, abs=1)
    assert a["portrait"]["radius"]["value"] == pytest.approx(1.158, abs=1e-3)
    assert a["derived"]["distance"]["parallax_over_error"] == pytest.approx(7.80, abs=0.01)
    assert a["derived"]["distance"]["ly"] == pytest.approx(6629, abs=1)
    # Gaia's two radius models disagree; both are in the answer.
    v = values_by_column(a["gaia"])
    assert v["gaiadr3.astrophysical_parameters.radius_gspphot"]["value"] == pytest.approx(0.8916, abs=1e-4)
    # A parallax of 0.49 mas: the uncorrected zero-point offset is said, with its size.
    assert any("offset" in n and "4% closer" in n for n in a["notes"])


def test_the_candidate_place_has_nothing_catalogued(answers: dict[str, dict]):
    a = answers["candidate"]
    assert a["nothing_catalogued"] is True and a["unreachable"] == []
    assert a["gaia"] is None and a["simbad"] is None and a["derived"]["distance"] is None
    assert a["portrait"] == {"temperature": None, "radius": None, "luminosity": None}
    # The sweep notes a G = 19.35 star 3.5 to 4.7 arcsec away; it is the nearest catalogued thing.
    assert a["nearest_catalogued"] == {"catalogue": "Gaia DR3", "name": "Gaia DR3 5964332607636528768",
                                       "display_name": "Gaia DR3 5964332607636528768", "simbad_name": None,
                                       "separation_arcsec": 4.9, "g_mag": 19.35, "bp_rp": 3.6, "same_pixel": True,
                                       "possibly_spurious": False}
    near_ten = [n for n in a["neighbours"] if 9.5 < n["separation_arcsec"] < 11]
    assert [n["source_id"] for n in near_ten] == ["5964332607629792768"]


def test_saved_frontend_answers_are_what_identify_returns(answers: dict[str, dict]):
    """frontend/src/fixtures/identify holds the same answers, for the card's tests."""
    for key, a in answers.items():
        assert json.loads((FRONT / f"{key}.json").read_text()) == json.loads(json.dumps(a)), key


# ----------------------------------------------------------------- services that do not answer

def test_a_catalogue_that_does_not_answer_is_named_and_nothing_is_filled_in(saved: Path, monkeypatch):
    real = identify._tap

    def gaia_down(kind: str, adql: str):
        if kind == "gaia":
            raise identify._Unanswered("Gaia DR3 did not answer (test)")
        return real(kind, adql)

    monkeypatch.setattr(identify, "_tap", gaia_down)
    a = identify.identify(*PLACES["barnard"][:2])
    assert a["unreachable"] == ["Gaia DR3"] and a["services"]["gaia"]["error"]
    assert a["gaia"] is None and a["simbad"]["main_id"] == "NAME Barnard's star"
    # SIMBAD's own values are what is shown; the temperature is SIMBAD's, labelled so.
    assert {v["catalogue"] for v in a["simbad"]["values"]} == {"SIMBAD"}
    assert a["portrait"]["temperature"]["catalogue"] == "SIMBAD" and a["portrait"]["radius"] is None
    a = identify.identify(*PLACES["candidate"][:2])
    assert a["nothing_catalogued"] is None       # not "nothing there": Gaia was not asked
    assert a["neighbours"] == []


def test_nothing_reachable_and_nothing_cached(saved: Path, network: list[str], monkeypatch):
    def down(url: str, params: dict, **_: object) -> bytes:
        network.append(url)
        raise spherex.ArchiveError("down (test)")

    monkeypatch.setattr(identify, "_get", down)
    monkeypatch.setattr(identify, "_down", {})
    before = set(saved.glob("identify_*.json"))
    a = identify.identify(10.0, 10.0)
    assert sorted(a["unreachable"]) == ["Gaia DR3", "SIMBAD"]
    assert a["nothing_catalogued"] is None and a["gaia"] is None and a["simbad"] is None
    assert {u for u in network} == {u for _, u in identify.GAIA_TAPS + identify.SIMBAD_TAPS}
    assert set(saved.glob("identify_*.json")) == before        # a failed query is never cached


# ----------------------------------------------------------------- the route

def test_route(client, saved: Path):
    r = client.get("/api/identify", params={"ra": 269.446267, "dec": 4.768222})
    assert r.status_code == 200
    assert r.json()["gaia"]["source_id"] == "4472832130942575872"
    assert r.json()["query"]["radius_arcsec"] == identify.DEFAULT_RADIUS_ARCSEC
    for bad in ({"ra": 10, "dec": 10, "radius": 0}, {"ra": 10, "dec": 10, "radius": 31}, {"ra": 10, "dec": 95},
                {"ra": 360, "dec": 0}, {"ra": 10, "dec": 10, "epoch": 1900}):
        assert client.get("/api/identify", params=bad).status_code == 422, bad

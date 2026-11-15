"""Offline tests of the colour-walk rules added after review. Inputs are MADE UP to test logic; no result uses them."""
import numpy as np

from backend import colourwalk as cw


def _walk(sigma, pa=218.0):
    return {"pa": pa, "sigma": sigma, "p_false": float(np.exp(-0.5 * sigma**2))}


def test_verdict_never_candidate_when_a_catalogue_failed():
    det = {k: _walk(3.0) for k in ("D4", "D5", "D6")}
    v, _ = cw.verdict(_walk(5.0), det, 0.01, False, False, ["2MASS"])
    assert v == "catalogue_check_failed"
    v, _ = cw.verdict(_walk(5.0), det, 0.01, False, False, [])
    assert v == "candidate"


def test_failed_catalogue_lookup_is_listed_not_empty():
    ok_row = {"east": 1.0, "north": 2.0, "mag": 3.0}
    failed = cw.catalogues_failed({"A": [{"error": "HTTP 404"}], "B": [], "C": [ok_row]})
    assert failed == ["A"]


def test_walk_significance_is_rayleigh():
    short = {"east": 0.0, "north": 0.0, "err_east": 0.1, "err_north": 0.1, "n": 50}
    long = {"east": 0.3, "north": 0.4, "err_east": 0.1, "err_north": 0.1, "n": 50}
    w = cw.walk_between(short, long)
    r = np.hypot(0.3, 0.4) / np.hypot(0.1, 0.1)
    assert abs(w["sigma"] - r) < 1e-9 and abs(w["p_false"] - np.exp(-0.5 * r * r)) < 1e-12


def _star(sid, e_arcsec, n_arcsec, g, bp_rp):
    # neighbour placed by its offset in arcsec from a host at (10, 0) degrees
    return {"source_id": sid, "ra": 10.0 + e_arcsec / 3600.0, "dec": n_arcsec / 3600.0, "pmra": 0.0, "pmdec": 0.0,
            "parallax": 0.0, "gmag": g, "bp": 10.0 + bp_rp, "rp": 10.0}


def test_gaia_explains_bluer_neighbour_on_the_opposite_side():
    host = _star("h", 0, 0, 14.4, 1.4)
    blue_opposite = _star("n", -5.0, 0.0, 14.5, 1.0)           # West of the host, the walk points East
    assert cw.gaia_explains(90.0, host, [blue_opposite])["kind"] == "opposite_bluer"
    red_opposite = _star("n", -5.0, 0.0, 19.0, 1.8)             # faint and redder: not an explanation
    assert cw.gaia_explains(90.0, host, [red_opposite]) is None
    along = _star("m", 5.0, 0.0, 17.8, 1.8)
    assert cw.gaia_explains(90.0, host, [along])["kind"] == "along"
    assert cw.gaia_explains(90.0, host, [_star("f", 13.0, 0.0, 19.6, 1.5)]) is None   # 5 magnitudes fainter
    side_bright = _star("s", 0.0, 5.0, 14.5, 1.4)               # at right angles and bright: the width-change case
    assert cw.gaia_explains(90.0, host, [side_bright])["kind"] == "bright_any_angle"


def test_visit_labels_split_on_gaps():
    lab = cw.visit_labels(np.array([100.0, 101.0, 290.0, 291.0, 480.0]))
    assert list(lab) == [0, 0, 1, 1, 2]

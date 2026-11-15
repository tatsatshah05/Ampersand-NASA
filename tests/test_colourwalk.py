"""Offline tests of the colour-walk arithmetic. Arrays here are MADE UP to test arithmetic; no result uses them."""
import numpy as np
from astropy.wcs import WCS

from backend import colourwalk as cw


def test_erf_gaussian_centroid_recovered():
    # made-up image: a Gaussian of known centre, flux and width on a flat background
    yy, xx = np.mgrid[0:15, 0:15]
    truth = (100.0, 7.3, 6.8, 0.6)
    data = truth[0] * cw.psf(truth[1], truth[2], truth[3], xx, yy) + 2.0
    var = np.full(data.shape, 0.01)
    bad = np.zeros(data.shape, bool)
    r = cw.fit_star(data - 2.0 * 0, var, bad, 7.0, 7.0)
    assert r is not None
    p = r[0]
    assert abs(p[1] - truth[1]) < 0.01 and abs(p[2] - truth[2]) < 0.01
    assert abs(p[0] - truth[0]) < 0.5 and abs(p[3] - truth[3]) < 0.01


def test_two_source_fit_recovers_ratio():
    yy, xx = np.mgrid[0:21, 0:21]
    data = 100.0 * cw.psf(10.0, 10.0, 0.6, xx, yy) + 5.0 * cw.psf(11.0, 12.0, 0.6, xx, yy)
    r = cw.fit_star(data, np.full(data.shape, 0.01), np.zeros(data.shape, bool), 10.0, 10.0, comp=(1.0, 2.0))
    assert r is not None
    assert abs(r[0][5] / r[0][0] - 0.05) < 0.002


def test_jacobian_east_is_negative_ra_pixel_direction():
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [10.0, 0.0]
    w.wcs.crpix = [50.0, 50.0]
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]       # standard sky image: RA grows to the left
    J = cw.local_jacobian(w, 50.0, 50.0)
    assert J[0, 0] < 0 and abs(J[0, 0]) > 6.0        # a step in +x is toward the West
    assert J[1, 1] > 0 and abs(J[0, 1]) < 1e-6


def test_position_angle_convention():
    assert cw.position_angle(0, 1) == 0.0
    assert abs(cw.position_angle(1, 0) - 90.0) < 1e-9
    assert abs(cw.position_angle(0, -1) - 180.0) < 1e-9
    assert abs(cw.position_angle(-1, 0) - 270.0) < 1e-9
    assert 0 <= cw.position_angle(-1, -1) < 360


def test_components_and_offset_round_trip():
    e, n = cw.offset_at(8.0, 218.0)
    assert abs(cw.position_angle(e, n) - 218.0) < 1e-9
    along, across = cw.components(e, n, 218.0)
    assert abs(along - 8.0) < 1e-9 and abs(across) < 1e-9


def test_photocentre_arithmetic():
    e, n = cw.photocentre([1.0, 0.1], [0.0, 0.0], [0.0, 8.0])   # made up: companion of 10 per cent, 8 arcsec North
    assert abs(e) < 1e-12 and abs(n - 0.8 / 1.1) < 1e-12
    pe, pn = cw.predicted_shift([0.0], [8.0], [0.1], scale=1e6)  # no response loss: same number
    assert abs(pn - 0.8 / 1.1) < 1e-6 and abs(pe) < 1e-9
    assert cw.predicted_shift([], [], []) == (0.0, 0.0)


def test_control_angle_bookkeeping():
    assert cw.control_angles(218.1) == [(218.1 + 90) % 360, (218.1 + 180) % 360, (218.1 + 270) % 360]
    assert all(0 <= a < 360 for a in cw.control_angles(350.0))
    assert cw.angle_difference(350.0, 10.0) == 20.0


def test_net_ratio_subtracts_median_of_controls():
    t = [{"lo": 3.0, "hi": 4.0, "ratio": 0.08, "err": 0.01, "n": 20}]
    c = [[{"ratio": 0.01}], [{"ratio": 0.02}], [{"ratio": 0.03}]]
    out = cw.net_ratio(t, c)
    assert abs(out[0]["net"] - 0.06) < 1e-12 and out[0]["control_max"] == 0.03


def _walk(sigma=6.0, across_sigma=0.5, pa=200.0):
    return {"pa": pa, "sigma": sigma, "across_sigma": across_sigma}


def _dets(pas):
    return {f"D{i + 4}": {"pa": p, "sigma": 3.0} for i, p in enumerate(pas)}


def test_verdict_rules():
    v = cw.verdict
    assert v(_walk(), _dets([195, 205, 210]), 0.01, False, False)[0] == "candidate"
    assert v(_walk(sigma=3.0), _dets([195, 205, 210]), 0.01, False, False)[0] == "nothing_found"
    assert v(_walk(), _dets([100, 205, 210]), 0.01, False, False)[0] == "nothing_found"
    assert v(_walk(), _dets([195, 205, 210]), 0.03, False, False)[0] == "nothing_found"
    assert v(_walk(), _dets([195, 205, 210]), 0.01, True, False)[0] == "explained_by_gaia_neighbour"
    assert v(_walk(), _dets([195, 205, 210]), 0.01, False, True)[0] == "known_source_at_walk"
    assert v({"pa": None, "sigma": None}, {}, None, False, False)[0] == "nothing_found"


def test_robust_median_and_walk_between():
    m, e, n = cw.robust([1, 2, 3, 4, 100])
    assert m == 3.0 and n == 5 and e > 0
    short = {"east": 0.0, "north": 0.0, "err_east": 0.04, "err_north": 0.04, "n": 10}
    long = {"east": -0.1, "north": -0.1, "err_east": 0.04, "err_north": 0.04, "n": 10}
    w = cw.walk_between(short, long)
    assert abs(w["pa"] - 225.0) < 1e-9 and abs(w["size"] - np.hypot(0.1, 0.1)) < 1e-12
    assert abs(w["sigma"] - np.hypot(0.1, 0.1) / (0.04 * np.sqrt(2))) < 1e-9

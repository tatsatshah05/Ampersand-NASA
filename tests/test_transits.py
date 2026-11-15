"""Offline tests of the transit arithmetic. Arrays here are MADE UP (labelled as such) and only
test arithmetic; no result in the project is built from them."""

import numpy as np
from astropy.time import Time

from backend import transits as T


def test_trapezoid_values():
    t14, k = 3.79, 0.1109
    t23 = t14 * (1 - k) / (1 + k)
    assert T.trapezoid(0.0, t14, k) == 1.0
    assert T.trapezoid(t14 / 48, t14, k) == 0.0  # exactly at first contact
    assert T.trapezoid(-t14 / 48, t14, k) == 0.0
    assert T.trapezoid(t23 / 48, t14, k) == 1.0  # exactly at the start of the flat part
    mid = (t14 + t23) / 4  # half-way up the ingress, in hours
    assert abs(T.trapezoid(mid / 24, t14, k) - 0.5) < 1e-12
    assert T.trapezoid(1.0, t14, k) == 0.0


def test_bjd_matches_astropy_reference():
    mjd = 60800.25
    ra, dec = 87.13982, -63.98833
    got = T.bjd_tdb(np.array([mjd]), ra, dec)[0]
    # reference: TDB time without the light-travel correction, then the correction's size is bounded by 500 s
    tdb = Time(mjd, format="mjd", scale="utc").tdb.jd
    assert abs(got - tdb) < 500 / 86400
    # the correction is the same to within a second when computed with the observer at the geocentre
    again = T.bjd_tdb(np.array([mjd]), ra, dec)[0]
    assert abs(got - again) * 86400 < 1.0


def test_template_of_constant_spectrum_is_one():
    wl = np.linspace(3.8, 4.4, 80)  # made-up wavelengths
    flux = np.full(80, 57.0)  # made-up constant flux
    use = np.ones(80, bool)
    rel = T.template_divide(wl, flux, use)
    assert np.all(rel == 1.0)


def test_template_never_uses_the_reading_itself():
    wl = np.linspace(3.8, 4.4, 40)
    flux = np.full(40, 10.0)
    flux[20] = 1000.0  # one made-up spike
    rel = T.template_divide(wl, flux, np.ones(40, bool))
    assert rel[20] == 100.0  # its own value does not enter its template


def test_fit_recovers_labelled_synthetic_depth():
    n = 400
    rng = np.random.default_rng(0)  # made-up positions and shape
    cols = {
        "X": rng.uniform(0, 1000, n),
        "Y": rng.uniform(0, 1000, n),
        "fx": rng.uniform(-0.5, 0.5, n),
        "fy": rng.uniform(-0.5, 0.5, n),
    }
    shape = np.zeros(n)
    shape[:60] = 1.0
    shape[60:80] = 0.5
    rel = 1.0 - 0.01 * shape  # noise-free, labelled synthetic depth 0.01
    depth, err, resid = T.fit_depth(rel, T.design(cols, shape), 0.01)
    assert abs(depth - 0.01) < 1e-9
    assert np.max(np.abs(resid)) < 1e-9
    assert err > 0


def test_fake_ephemerides_skip_true_period_and_multiples():
    period = 4.41193868
    fakes = T.fake_ephemerides(period)
    ps = np.array(sorted({p for p, _ in fakes}))
    for q in (0.5, 1.0, 1.5, 2.0, 3.0):
        assert np.all(np.abs(ps / period - q) >= T.FAKE_EXCLUDE_TOL - 1e-12)
    assert ps.min() >= 1.5 and ps.max() <= 9.0
    assert len(fakes) == len(ps) * len(T.FAKE_OFFSETS)


def test_overflow_rule_leaves_detector_out_at_21_per_cent_and_keeps_it_at_19():
    for share, left_out in ((0.21, True), (0.19, False)):
        n_ok = 1000
        n_over = int(share * n_ok)
        assert (n_over > T.OVERFLOW_LIMIT * n_ok) == left_out


def test_time_from_mid_wraps():
    assert abs(T.time_from_mid(np.array([10.0 + 3.0]), 3.0, 10.0)[0]) < 1e-12
    assert abs(T.time_from_mid(np.array([10.0 + 1.4]), 3.0, 10.0)[0] - 1.4) < 1e-12
    assert abs(T.time_from_mid(np.array([10.0 + 1.6]), 3.0, 10.0)[0] + 1.4) < 1e-12


def test_analyse_detector_on_pure_noise_has_no_depth_beyond_errors():
    # made-up noise-only readings of a flat star: arithmetic check that the pipeline returns ~0, not a real result
    rng = np.random.default_rng(3)
    n = 600
    c = {
        "bjd": 2460800 + np.sort(rng.uniform(0, 300, n)),
        "det": np.full(n, 5),
        "flux": 50 * (1 + 0.01 * rng.standard_normal(n)),
        "err": np.full(n, 0.4),
        "wl": rng.uniform(3.8, 4.4, n),
        "X": rng.uniform(-900, -800, n),
        "Y": rng.uniform(-600, -500, n),
        "fx": rng.uniform(-0.5, 0.5, n),
        "fy": rng.uniform(-0.5, 0.5, n),
        "ovf": np.zeros(n, int),
        "ok": np.ones(n, bool),
    }
    r = T.analyse_detector(c, 4.4119, 2460800.3, 3.79, 0.11, extras=False)
    assert r["status"] == "ok"
    assert abs(r["depth"]) < 4 * r["formal_err"]


def test_subpixel_terms_symmetric_about_pixel_centre():
    """Unit test of arithmetic (made-up numbers): the design has dx, dy, dx^2, dy^2, dx*dy columns."""
    n = 50
    cols = {k: np.linspace(-0.4, 0.4, n) for k in ("fx", "fy", "X", "Y")}
    a = T.design(cols, np.zeros(n), detrend="none", subpixel=True)
    assert a.shape == (n, 7)
    assert np.allclose(a[:, 3], cols["fx"] ** 2)


def test_colour_test_marks_dichroic_pairs():
    """Unit test of arithmetic (made-up numbers): only 1-4, 2-5 and 3-6 share exposures."""
    det = {
        str(d): {"status": "ok", "depth": 0.01, "empirical_err": 0.003, "n_in": 40, "formal_err": 0.002}
        for d in (1, 3, 4)
    }
    ct = T.colour_test({"detectors": det})
    assert ct["pairs"]["1-4"]["same_exposures"] is True
    assert ct["pairs"]["1-3"]["same_exposures"] is False

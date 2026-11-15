"""Earth-reflex stacking (backend/reflex.py): arithmetic checks, offline.

Every made-up input below is labelled 'synthetic arithmetic test, not data'. Nothing here is
SPHEREx data, nothing is written to the cache, and no result of the project rests on it.
The real-data known answer (Eris) is scripts/check_reflex.py.
"""

from __future__ import annotations

import numpy as np

from backend import reflex

RA, DEC = 27.37815, -0.11998


def _mjds() -> np.ndarray:
    # synthetic arithmetic test, not data: 57 times spread over a 15.35-day visit starting at Eris's real one
    return np.sort(60866.09 + np.random.default_rng(0).uniform(0, 15.35, 57))


def test_fit_recovers_distance_from_parallax_track():
    """synthetic arithmetic test, not data: a track built from the parallax model at 95.5 AU is fitted back."""
    t = _mjds()
    t0 = float(np.median(t))
    f = reflex.distant.parallax_factor(reflex.distant._earth(t), RA, DEC) * reflex.ARCSEC_PER_RADIAN
    east = 2.0 + 3.9 * (t - t0) + f[:, 0] / 95.5
    north = -1.0 - 3.6 * (t - t0) + f[:, 1] / 95.5
    fit = reflex.fit_track(t, east, north, RA, DEC)
    assert abs(fit["distance_au"] - 95.5) / 95.5 < 0.005
    assert abs(fit["drift"][0] - 3.9) < 0.01 and fit["rms_arcsec"] < 1e-6


def test_integer_shift_stack_puts_all_weight_in_one_pixel():
    """synthetic arithmetic test, not data: a delta image moving by known whole pixels stacks into one pixel."""
    n_exp, n = 12, 41
    ie = np.arange(n_exp) - 6
    jn = np.round(0.5 * np.arange(n_exp)).astype(int) - 3
    cube = np.zeros((n_exp, n, n))
    for i in range(n_exp):
        cube[i, 20 + jn[i], 20 + ie[i]] = 1.0  # value at (y + jn, x + ie) for the stack pixel (20, 20)
    num, den = reflex.stack_integer(cube, np.ones_like(cube), ie, jn)
    assert num[20, 20] == n_exp
    assert num.sum() == n_exp  # nothing anywhere else
    assert den[20, 20] == n_exp


def test_straight_line_removed_from_parallax_curve():
    """synthetic arithmetic test, not data: only the times are made up; Fnl is orthogonal to [1, t]."""
    t = _mjds()
    t0 = float(np.median(t))
    fnl, flin = reflex.parallax_curve(t, RA, DEC, t0)
    basis = np.column_stack([np.ones_like(t), t - t0])
    for k in range(2):
        assert np.all(np.abs(basis.T @ fnl[:, k]) < 1e-6 * np.abs(fnl[:, k]).max() * len(t) + 1e-9)
    f = reflex.distant.parallax_factor(reflex.distant._earth(t), RA, DEC) * reflex.ARCSEC_PER_RADIAN
    assert np.allclose(fnl + flin, f)
    assert np.ptp(fnl[:, 0]) > 500  # the lever on distance: arcsec per 1/AU (Eris's visit: 1580)


def test_snr_normalisation_of_pure_noise():
    """synthetic arithmetic test, not data: Gaussian noise comes out with robust sigma 1 and median 0."""
    rng = np.random.default_rng(5)
    num = rng.normal(0, 3.0, (150, 150))
    den = np.full((150, 150), 9.0)
    snr = reflex.normalise_snr(num, den, 9.0)
    vals = snr[np.isfinite(snr)]
    mad_sigma = 1.4826 * np.median(np.abs(vals - np.median(vals)))
    assert abs(mad_sigma - 1.0) < 0.05 and abs(np.median(vals)) < 0.05


def test_visits_split_on_gap_and_default_is_longest():
    """synthetic arithmetic test, not data: made-up exposure dates."""
    exps = [{"mjd": 100.0 + 0.2 * i} for i in range(40)] + [{"mjd": 300.0 + 0.5 * i} for i in range(50)]
    visits = reflex.split_visits(exps)
    assert [len(v) for v in visits] == [40, 50]
    assert reflex.pick_visit(visits, None) == 1
    assert reflex.pick_visit(visits, (100.0, 108.0)) == 0


def test_drift_box_is_centred_on_the_reflex_rate():
    """synthetic arithmetic test, not data: the box centre follows 1/d times the straight-line part of the parallax."""
    ce, cn, rad = reflex.drift_box(0.01, 400.0, -300.0, 50.0)
    assert (ce, cn) == (4.0, -3.0)
    assert 1.0 < rad <= reflex.DRIFT_RADIUS_MAX
    ce2, cn2, _ = reflex.drift_box(-0.01, 400.0, -300.0, 50.0)  # reversed Earth: reversed centre
    assert (ce2, cn2) == (-4.0, 3.0)

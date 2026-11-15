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


def test_interval_ignores_negative_and_missing_signal():
    """synthetic arithmetic test, not data: a profile with NaN and large negative points (the old -1e9
    sentinel, squared, used to count as 'inside' the interval)."""
    grid = np.arange(-0.01, 0.0201, 0.001)
    snr = 12.0 - 2000.0 * (grid - 0.01) ** 2 * 100  # peak 12 at 1/d = 0.01
    snr[grid < -0.004] = -9.3e8
    snr[3] = np.nan
    ib = int(np.nanargmax(snr))
    near, far = reflex._interval(grid, snr, ib, 4.0)
    assert near is not None and far is not None and near < 100.0 < far


def test_interval_far_end_is_none_when_the_profile_stays_flat_to_infinity():
    """synthetic arithmetic test, not data: S/N flat at 10 for every 1/d."""
    grid = np.arange(-0.01, 0.0201, 0.001)
    snr = np.full(len(grid), 10.0)
    snr[0] = 9.0
    near, far = reflex._interval(grid, snr, 5, 4.0)
    assert far is None


def test_null_visit_never_gives_a_measured_distance():
    """Real recorded results (docs/reflex/results.json, written by check_reflex.py null): the Eris field in its
    other visits used to print 'distance measured' for a noise peak; now no null run may."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "reflex" / "results.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    rows = [r for k, v in data.items() if k.startswith("null_runs") for r in v["rows"]]
    assert rows, "run scripts/check_reflex.py null"
    for r in rows:
        assert not any(r["forward_distance_measured"])
        assert r["n_reversed_surviving_vetting"] == 0
        assert not any(v.startswith("candidate") for v in r["forward_verdicts"])


def test_epochs_group_exposures_of_one_detector_within_a_fraction_of_a_day():
    """synthetic arithmetic test, not data: made-up times and detectors."""
    t = np.array([0.0, 0.05, 0.1, 3.0, 3.1, 0.02, 3.05])
    det = np.array([1, 1, 1, 1, 1, 2, 2])
    groups = reflex.epochs_of(t, det)
    assert sorted(len(g) for g in groups) == [1, 1, 2, 3]

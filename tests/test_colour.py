"""Offline tests of the arithmetic in backend/colour.py.

Every spectrum below is MADE UP, as a test input of the fitting arithmetic only (a known answer is put in and
must come out). Nothing here is, or stands for, a measurement.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from backend import colour, photometry

RNG = np.random.default_rng(7)


def channels(wave: np.ndarray, ratio: np.ndarray, err: np.ndarray, early: np.ndarray | None = None) -> list[dict]:
    """Channel rows in the form `colour.channel_table` makes (test input)."""
    early = np.full_like(wave, 10.0) if early is None else early
    return [{"detector": 1, "channel": i, "wave_um": float(w), "early": float(e), "early_err": 0.1,
             "late": float(e * r), "late_err": 0.1, "ratio": float(r), "ratio_err": float(s), "n_early": 3, "n_late": 3}
            for i, (w, r, s, e) in enumerate(zip(wave, ratio, err, early, strict=True))]


WAVE = np.geomspace(0.8, 4.9, 40)


def test_ratio_with_error():
    r, e = colour.ratio_with_error(10.0, 1.0, 20.0, 1.0)
    assert r == pytest.approx(2.0)
    assert e == pytest.approx(2.0 * math.hypot(0.1, 0.05))


def test_grey_fit_recovers_factor_and_error():
    err = np.full(40, 0.02)
    f = colour.fit_grey(np.full(40, 0.6), err)
    assert f["params"]["factor"] == pytest.approx(0.6)
    assert f["errors"]["factor"] == pytest.approx(0.02 / math.sqrt(40))
    assert f["chi2"] == pytest.approx(0.0, abs=1e-12)


def test_dust_ratio_is_stronger_at_short_wavelengths():
    r = colour.dust_ratio(np.array([0.8, 2.0, 4.8]), 0.5)
    assert r[0] < r[1] < r[2] < 1.0
    assert colour.dust_ratio(np.array([1.0]), 0.0)[0] == pytest.approx(1.0)
    assert colour.dust_ratio(np.array([1.0]), -0.5)[0] > 1.0           # dust removed: brighter


def test_dust_fit_recovers_tau():
    truth = 0.8
    err = np.full(40, 0.01)
    f = colour.fit_dust(WAVE, colour.dust_ratio(WAVE, truth), err)
    assert f["params"]["tau_1"] == pytest.approx(truth, abs=1e-3)
    assert f["interval"]["tau_1"][0] < truth < f["interval"]["tau_1"][1]


def test_planck_shape_is_one_at_reference_and_peaks_bluer_when_hotter():
    s = colour.planck_shape(np.array([4.5]), 600.0, 4.5)
    assert s[0] == pytest.approx(1.0)
    cool = colour.planck_shape(np.array([1.0, 4.5]), 500.0, 4.5)
    hot = colour.planck_shape(np.array([1.0, 4.5]), 1400.0, 4.5)
    assert cool[0] < hot[0]                     # more short-wavelength light when hotter


def test_glow_fit_recovers_temperature_and_sign():
    early = np.full(40, 5.0)
    for amp, temp in ((20.0, 700.0), (-3.0, 400.0)):
        ratio = 1.0 + amp * colour.planck_shape(WAVE, temp, 4.5) / early
        ratio = np.maximum(ratio, 0.05)
        f = colour.fit_glow("warm", WAVE, ratio, np.full(40, 0.01), early)
        assert f["params"]["temperature_k"] == pytest.approx(temp, rel=0.05)
        assert f["params"]["amplitude_mjy_at_ref"] == pytest.approx(amp, rel=0.1)
        assert f["sign"] == ("added" if amp > 0 else "removed")


def test_verdict_grey():
    ratio = np.full(40, 0.7) + RNG.normal(0, 0.01, 40)
    out = colour.fit_shapes(channels(WAVE, ratio, np.full(40, 0.01)), min_sigma=3.0)
    assert out["verdict"] in ("grey", "cannot_tell")
    assert out["fits"]["grey"]["fits"]
    assert out["fits"]["grey"]["params"]["factor"] == pytest.approx(0.7, abs=0.01)


def test_verdict_dust_beats_grey():
    truth = 0.9
    ratio = colour.dust_ratio(WAVE, truth) + RNG.normal(0, 0.005, 40)
    out = colour.fit_shapes(channels(WAVE, ratio, np.full(40, 0.005)), min_sigma=3.0)
    assert out["verdict"] == "dust"
    assert not out["fits"]["grey"]["fits"]


def test_verdict_none_of_these_for_structure_no_shape_has():
    # brighter at short and fainter at long wavelengths (the RW Aurigae pattern), made up: no simple shape does that
    ratio = np.where(WAVE < 2.0, 1.6, 0.5) + RNG.normal(0, 0.01, 40)
    out = colour.fit_shapes(channels(WAVE, ratio, np.full(40, 0.01)), min_sigma=3.0)
    assert out["verdict"] == "none_of_these"


def test_verdict_no_change_and_cannot_tell():
    ratio = 1.0 + RNG.normal(0, 0.02, 40)
    out = colour.fit_shapes(channels(WAVE, ratio, np.full(40, 0.02)), min_sigma=6.0)
    assert out["verdict"] == "no_clear_change"
    # a small change with large errors: several shapes fit equally well
    ratio = np.full(8, 1.1)
    out = colour.fit_shapes(channels(WAVE[::5], ratio, np.full(8, 0.15)), min_sigma=0.5)
    assert out["verdict"] == "cannot_tell"
    assert len(out["tied"]) >= 2


def test_too_few_channels():
    out = colour.fit_shapes(channels(WAVE[:4], np.ones(4), np.full(4, 0.1)))
    assert out["verdict"] == "too_few_channels"


def test_combo_fit_finds_grey_plus_warm():
    early = np.full(40, 5.0)
    ratio = 0.3 + 12.0 * colour.planck_shape(WAVE, 800.0, 4.5) / early
    f = colour.fit_combo("grey_warm", WAVE, ratio, np.full(40, 0.01), early)
    assert f["fits"] and f["params"]["factor"] == pytest.approx(0.3, abs=0.02)


def readings(levels: dict[tuple[int, int], float], n: int = 3) -> dict:
    """Made-up readings of one object in two visits (visit 0: level, visit 1: level x factor), n per channel."""
    det, ep, wave, flux, err, status = [], [], [], [], [], []
    edges = photometry.channel_edges(0.75, 1.09)
    for (visit, ch), level in levels.items():
        for k in range(n):
            det.append(1)
            ep.append(visit)
            wave.append(float(np.sqrt(edges[ch] * edges[ch + 1])) * (1 + 0.001 * k))
            flux.append(level)
            err.append(0.05)
            status.append(colour.OK)
    return {"detector": np.array(det), "epoch": np.array(ep), "wave": np.array(wave), "flux": np.array(flux, float),
            "err": np.array(err), "status": np.array(status), "edges": {1: edges}}


def test_levels_and_ratios_use_the_same_channel_in_both_visits_only():
    # visit 0 has channels 0..9, visit 1 has channels 5..14: only 5..9 may be compared
    lv = {(0, c): 10.0 for c in range(10)} | {(1, c): 5.0 for c in range(5, 15)}
    rec = readings(lv)
    out = colour.visit_channel_levels(rec["flux"], rec["err"], rec["status"], rec["wave"], rec["detector"],
                                      rec["epoch"], rec["edges"])
    table = colour.channel_table(out, 0, 1)
    assert [c["channel"] for c in table["channels"]] == [5, 6, 7, 8, 9]
    assert all(c["ratio"] == pytest.approx(0.5) for c in table["channels"])


def test_saturated_readings_are_counted_and_never_become_values():
    lv = {(0, c): 10.0 for c in range(8)} | {(1, c): 20.0 for c in range(8)}
    rec = readings(lv)
    rec["status"] = rec["status"].copy()
    sel = (rec["epoch"] == 1) & (np.arange(len(rec["epoch"])) % 1 == 0)
    first_channel = photometry.channel_edges(0.75, 1.09)
    in_ch0 = (rec["wave"] < first_channel[1]) & sel
    rec["status"][in_ch0] = colour.SATURATED
    rec["flux"][in_ch0] = np.nan
    out = colour.visit_channel_levels(rec["flux"], rec["err"], rec["status"], rec["wave"], rec["detector"],
                                      rec["epoch"], rec["edges"])
    table = colour.channel_table(out, 0, 1)
    assert 0 not in [c["channel"] for c in table["channels"]]
    assert {"detector": 1, "channel": 0} in table["saturated_channels"]
    assert table["readings"]["saturated"] == int(in_ch0.sum())


def test_calibration_line_is_removed():
    # made-up steady stars whose second visit is 0.9 x the first plus 0.2 mJy
    x = np.geomspace(0.5, 20.0, 60)
    y = 0.9 * x + 0.2
    f, b = colour._line_fit(x, y, np.full(60, 0.01), np.full(60, 0.01))
    assert f == pytest.approx(0.9, abs=1e-3)
    assert b == pytest.approx(0.2, abs=1e-2)


def test_band_depth_and_change_use_matching_channels():
    cfg = colour.ICE_BANDS["co2"]
    edges = photometry.channel_edges(3.82, 4.42)
    centres = np.sqrt(edges[:-1] * edges[1:])
    rec: dict = {"detector": [], "epoch": [], "wave": [], "flux": [], "err": [], "status": [], "edges": {5: edges}}

    def add(visit: int, depth: float) -> None:
        for w in centres:
            for _ in range(3):
                f = 10.0 * (1 - depth) if abs(w - cfg["centre"]) <= cfg["half"] else 10.0
                rec["detector"].append(5)
                rec["epoch"].append(visit)
                rec["wave"].append(float(w))
                rec["flux"].append(f)
                rec["err"].append(0.1)
                rec["status"].append(colour.OK)

    add(0, 0.2)
    add(1, 0.5)
    r = {k: np.array(v) if k != "edges" else v for k, v in rec.items()}
    out = colour.ice_change(r, "co2", 0, 1)
    assert out is not None
    assert out["depth_early"] == pytest.approx(0.2, abs=0.02)
    assert out["depth_late"] == pytest.approx(0.5, abs=0.02)
    assert out["change"] == pytest.approx(0.3, abs=0.03)
    assert colour.ice_change(r, "co", 0, 1) is None          # that band's channels are outside this detector


def test_principal_components_finds_two_kinds_in_made_up_spectra():
    ids = [f"o{i}" for i in range(60)]
    waves = np.geomspace(0.8, 4.9, 80)
    spectra = {}
    for i in ids:
        a, b = RNG.normal(0, 1), RNG.normal(0, 1)
        y = a * 0.5 + b * 0.4 * np.log(waves / 2.0)             # two made-up kinds of change
        spectra[i] = [(float(w), float(v + RNG.normal(0, 0.01)), 0.01) for w, v in zip(waves, y, strict=True)]
    out = colour.principal_components(spectra, noise_sigma=0.02)
    assert out["ok"]
    assert out["uncentred"]["n_above_noise"] == 2
    assert sum(out["uncentred"]["variance_share"][:2]) > 0.98


def test_colour_tilt_is_one_for_grey_and_not_for_dust():
    grey = colour.colour_tilt(channels(WAVE, np.full(40, 0.7), np.full(40, 0.01)))
    assert grey is not None and grey[0] == pytest.approx(1.0, abs=1e-6)
    dusty = colour.colour_tilt(channels(WAVE, colour.dust_ratio(WAVE, 0.5), np.full(40, 0.01)))
    assert dusty is not None and dusty[0] > 1.2


def test_plain_sentences():
    grey = {"headline": "0-1", "pairs": {"0-1": {"fit": {"verdict": "grey"}}}}
    assert "same at every colour" in colour.plain_sentence(grey)
    none = {"headline": "0-1", "pairs": {"0-1": {"fit": {"verdict": "none_of_these"}}}}
    assert "none of the simple shapes" in colour.plain_sentence(none)
    assert "Too few" in colour.plain_sentence({"headline": None})

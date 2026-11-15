"""backend/sweep.py: choosing images, measuring, the ten-times rule, the vetoes and the classification.

Everything here uses real pieces saved in tests/data/sweep (nothing is invented):

- `exposures_d6_v7994_tile.json`: the archive's list of the 56 detector 6 images that cover a tile
  of the proof run (centre RA 270.7, Dec -31.2), as `sweep.exposure_list` returns it;
- six 0.12 degree cutouts of the nova V7994 Sagittarii (RA 270.96983, Dec -31.45739), the images
  the proof run chose (two from August 2025, two from March and April 2026, two from August and
  September 2026), copied unchanged from the cache;
- `survivors_v7994.json`: what the proof run recorded for its two survivors, the nova and a
  bright variable star, including every catalogue's real answer at their positions.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from backend import sweep

DATA = Path(__file__).parent / "data" / "sweep"
NOVA = (270.96983, -31.45739)
TILE = (270.7, -31.2)


@pytest.fixture(scope="module")
def exposures() -> list[dict]:
    return json.loads((DATA / "exposures_d6_v7994_tile.json").read_text())


@pytest.fixture(scope="module")
def images() -> list[sweep.Img]:
    chosen = json.loads((DATA / "chosen_images.json").read_text())
    out = []
    for name, exp in sorted(chosen.items(), key=lambda kv: kv[1]["mjd"]):
        im = sweep.Img.load(DATA / name, exp)
        im.prepare()
        out.append(im)
    return out


@pytest.fixture(scope="module")
def measured(images: list[sweep.Img]) -> list[dict]:
    return [im.measure(*NOVA) for im in images]


# ------------------------------------------------------------------ choosing images

def test_epochs_are_runs_of_visits_without_a_long_gap(exposures):
    epochs = sweep.group_epochs(exposures)
    assert len(epochs) == 3
    assert sum(len(e) for e in epochs) == len(exposures) == 56
    for a, b in zip(epochs, epochs[1:], strict=False):
        assert b[0]["mjd"] - a[-1]["mjd"] > sweep.EPOCH_GAP_DAYS
    for e in epochs:
        assert e[-1]["mjd"] - e[0]["mjd"] <= sweep.EPOCH_GAP_DAYS + 1


def test_the_images_chosen_for_the_proof_tile(exposures):
    chosen = sweep.choose_images(exposures, *TILE)
    assert [c["epoch"] for c in chosen] == [0, 0, 1, 1, 2, 2]
    anchors = {c["epoch"]: c for c in chosen if c["role"] == "anchor"}
    assert [anchors[e]["obs_id"] for e in (0, 1, 2)] == ["2025W35_2A_0209_2", "2026W14_1A_0223_2",
                                                         "2026W35_2A_0657_3"]
    # Each epoch's anchor is the image whose centre is nearest the tile centre.
    for epoch in sweep.group_epochs(exposures):
        best = min(epoch, key=lambda e: sweep.sep_deg(e["s_ra"], e["s_dec"], *TILE))
        if best["obs_id"] in {c["obs_id"] for c in chosen}:
            assert anchors[chosen[[c["obs_id"] for c in chosen].index(best["obs_id"])]["epoch"]]["obs_id"] \
                == best["obs_id"]
    # A second image is at least a day from its anchor wherever the epoch has one (epoch 1's best centred
    # second image is six days away), and a different pointing from it.
    for c in chosen:
        if c["role"] == "partner":
            assert abs(c["gap_days"]) >= sweep.MIN_PARTNER_DAYS
            assert sweep.visit_of(c["obs_id"]) != sweep.visit_of(anchors[c["epoch"]]["obs_id"])
    assert all(c["sep_deg"] <= sweep.MAX_CENTRE_SEP_DEG for c in chosen)


def test_an_epoch_with_nothing_near_the_centre_is_left_out(exposures):
    far = sweep.choose_images(exposures, 10.0, 80.0)
    assert far == []


def test_separation_and_pointing_name():
    assert sweep.sep_deg(10.0, 0.0, 11.0, 0.0) == pytest.approx(1.0)
    assert sweep.sep_deg(359.5, 0.0, 0.5, 0.0) == pytest.approx(1.0)
    assert sweep.visit_of("2026W14_1A_0223_2") == "2026W14_1A_0223"


# ------------------------------------------------------------------ measuring

def test_the_nova_is_absent_in_2025_bright_in_spring_2026_and_fading_by_autumn(measured, images):
    by_epoch: dict[int, list[float]] = {}
    for m, im in zip(measured, images, strict=True):
        assert m["status"] == "ok"
        by_epoch.setdefault(im.epoch, []).append(m["flux"])
    assert all(abs(f) < 10 for f in by_epoch[0])                      # nothing there in August 2025
    assert all(1000 < f < 1700 for f in by_epoch[1])                  # the project measured 1,070 to 1,420 mJy
    assert all(100 < f < 260 for f in by_epoch[2])                    # 96 to 177 mJy in the project's circles
    assert all(m["err"] > 0 for m in measured)


def test_the_nova_is_found_by_detection_in_the_images_where_it_shines(images):
    for im in images:
        found = [d for d in im.detect() if not d["saturated"]]
        hit = []
        for d in found:
            x, y = (float(v[0]) for v in im.sky_to_pix(*NOVA))
            if np.hypot(d["x"] - x, d["y"] - y) < 1.5:
                hit.append(d)
        assert bool(hit) == (im.epoch in (1, 2)), im.obs_id


def test_detections_of_the_same_star_in_two_images_become_one_source(images):
    dets = [im.detect() for im in images if im.epoch == 1]
    merged = sweep.merge_detections(dets)
    both = [s for s in merged if s["n_detections"] == 2]
    assert both
    assert len(merged) <= len(dets[0]) + len(dets[1]) - len(both)
    near = [s for s in merged if abs(s["ra"] - NOVA[0]) < 0.003 and abs(s["dec"] - NOVA[1]) < 0.003]
    assert len(near) == 1 and near[0]["n_detections"] == 2


def test_a_position_off_the_image_is_not_measured(images):
    m = images[0].measure(NOVA[0] + 5.0, NOVA[1])
    assert m["status"] == "off" and m["flux"] is None
    near_edge = images[0].measure_xy(5.0, 30.0)
    assert near_edge["status"] == "edge" and near_edge["flux"] is None


def test_aperture_weights_add_up_to_the_area_of_the_circle():
    for fx, fy in ((0.0, 0.0), (0.3, -0.2), (-0.5, 0.5)):
        w = sweep.aperture_weights(fx, fy)
        assert w.sum() == pytest.approx(np.pi * sweep.APERTURE_PX ** 2, rel=0.02)


# ------------------------------------------------------------------ the ten-times rule

def _epochs(measured, images):
    out: dict[int, list[dict]] = {}
    for m, im in zip(measured, images, strict=True):
        out.setdefault(im.epoch, []).append(m)
    return out


def test_the_nova_passes_in_the_right_direction_only(measured, images):
    e = _epochs(measured, images)
    assert sweep.change_test(e[1], e[0], min_bright=2)["passes"]
    assert sweep.change_test(e[2], e[0], min_bright=2)["passes"]
    backwards = sweep.change_test(e[0], e[1], min_bright=2)
    assert not backwards["passes"] and backwards["reason"] == "too faint"


def test_ten_times_is_a_rule_about_the_faintest_bright_image_and_the_brightest_faint_one(measured, images):
    e = _epochs(measured, images)
    spring_over_autumn = sweep.change_test(e[1], e[2])
    assert spring_over_autumn["reason"] == "not faint enough"
    assert 5 < spring_over_autumn["ratio"] < 10                      # about 7: a fade, not a disappearance
    assert sweep.change_test(e[1], e[2], ratio=5.0)["passes"]        # the rule is the threshold, nothing else
    assert sweep.change_test(e[1], e[2], ratio=10.0)["passes"] is False
    assert sweep.change_test(e[1], e[0])["bright_mjy"] == min(m["flux"] for m in e[1])


def test_a_source_must_reach_the_minimum_brightness(measured, images):
    e = _epochs(measured, images)
    assert sweep.change_test(e[2], e[0], min_mjy=500.0)["reason"] == "too faint"


def test_one_image_cannot_confirm_when_two_are_asked_for(measured, images):
    e = _epochs(measured, images)
    one = sweep.change_test(e[1][:1], e[0], min_bright=2)
    assert not one["passes"] and one["reason"] == "no data"
    assert sweep.change_test(e[1][:1], e[0], min_bright=1)["passes"]


def test_an_unusable_measurement_is_never_a_pass(measured, images):
    e = _epochs(measured, images)
    broken = [{**m, "status": "flagged", "flux": None, "err": None} for m in e[0]]
    result = sweep.change_test(e[1], broken)
    assert not result["passes"] and result["reason"] == "no data"


def test_best_pair_takes_the_brightest_pass(measured, images):
    e = _epochs(measured, images)
    pair = sweep.best_pair(e, min_bright=2)
    assert pair is not None and (pair["bright_epoch"], pair["faint_epoch"]) == (1, 0)
    assert sweep.best_pair({0: e[0], 2: e[2]}, min_bright=2)["bright_epoch"] == 2
    assert sweep.best_pair({0: e[0]}) is None


# ------------------------------------------------------------------ a tile's tallies

def test_evaluate_counts_the_nova_through_every_stage(images, measured):
    sources = [{"ra": NOVA[0], "dec": NOVA[1], "l": 359.81, "b": -4.68}]
    meas = [[m] for m in measured]
    meta = [{"obs_id": im.obs_id, "epoch": im.epoch, "role": im.role, "mjd": im.mjd, "shape": im.shape}
            for im in images]
    clumps = [np.zeros((0, 2)) for _ in images]
    out = sweep.evaluate(sources, meas, meta, clumps, [0.0] * len(images))
    assert out["tally"]["sources"] == out["tally"]["comparable"] == 1
    assert out["tally"]["changed_anchors"] == out["tally"]["changed_all_images"] == out["tally"]["survivors"] == 1
    assert out["survivors"][0]["pair"]["bright_epoch"] == 1
    assert out["survivors"][0]["direction"] == "brightened"
    assert out["survivors"][0]["same_day_only"] is False
    # Not this tile's source: counted nowhere.
    none = sweep.evaluate(sources, meas, meta, clumps, [0.0] * len(images), keep=np.array([False]))
    assert none["tally"]["sources"] == 0


def test_a_second_image_that_disagrees_kills_the_source(images, measured):
    """Only the 2025 and spring 2026 images, and the spring partner shows nothing: the two-visit comparison
    passes, the confirmed one does not."""
    keep = [i for i, im in enumerate(images) if im.epoch in (0, 1)]
    sources = [{"ra": NOVA[0], "dec": NOVA[1]}]
    meas = [[dict(measured[i])] for i in keep]
    meta = [{"obs_id": images[i].obs_id, "epoch": images[i].epoch, "role": images[i].role, "mjd": images[i].mjd,
             "shape": images[i].shape} for i in keep]
    clumps, ratios = [np.zeros((0, 2))] * len(keep), [0.0] * len(keep)
    assert sweep.evaluate(sources, meas, meta, clumps, ratios)["tally"]["survivors"] == 1
    partner = next(k for k, m in enumerate(meta) if m["epoch"] == 1 and m["role"] == "partner")
    donor = next(k for k, m in enumerate(meta) if m["epoch"] == 0)
    meas[partner] = [dict(meas[donor][0])]     # the real "nothing there" measurement of an August 2025 image
    out = sweep.evaluate(sources, meas, meta, clumps, ratios)
    assert out["tally"]["changed_anchors"] == 1 and out["tally"]["killed_second_image"] == 1
    assert out["tally"]["survivors"] == 0


def test_a_source_whose_second_image_is_unusable_is_listed_apart(images, measured):
    """The spring partner image is flagged at the source: nothing contradicts the anchor, but nothing confirms it."""
    keep = [i for i, im in enumerate(images) if im.epoch in (0, 1)]
    sources = [{"ra": NOVA[0], "dec": NOVA[1]}]
    meas = [[dict(measured[i])] for i in keep]
    meta = [{"obs_id": images[i].obs_id, "epoch": images[i].epoch, "role": images[i].role, "mjd": images[i].mjd,
             "shape": images[i].shape} for i in keep]
    partner = next(k for k, m in enumerate(meta) if m["epoch"] == 1 and m["role"] == "partner")
    meas[partner] = [{**meas[partner][0], "status": "flagged", "flux": None, "err": None}]
    out = sweep.evaluate(sources, meas, meta, [np.zeros((0, 2))] * len(keep), [0.0] * len(keep))
    assert out["tally"]["single_image_only"] == 1 and out["tally"]["survivors_single_image"] == 1
    assert out["tally"]["survivors"] == 0 and out["survivors"][0]["single_image_only"] is True


def test_the_vetoes_in_order(images, measured):
    meta = [{"obs_id": im.obs_id, "epoch": im.epoch, "role": im.role, "mjd": im.mjd, "shape": im.shape}
            for im in images]
    bright = [i for i, m in enumerate(meta) if m["epoch"] == 1]
    sources = [{"ra": NOVA[0], "dec": NOVA[1]}]
    meas = [[m] for m in measured]
    flux = np.array([[m["flux"]] for m in measured])
    px = np.array([[m["x"]] for m in measured])
    py = np.array([[m["y"]] for m in measured])
    strength = flux.copy()
    clumps = [np.zeros((0, 2)) for _ in images]
    args = (0, sources, meas, meta, bright, flux, strength, px, py, clumps, [0.0] * 6, None, 0.005)
    assert sweep.veto(*args) is None
    # edge: the same source seen 10 pixels from the border
    close = np.array(py)
    close[bright[0], 0] = 10.0
    assert sweep.veto(0, sources, meas, meta, bright, flux, strength, px, close, clumps, [0.0] * 6, None, 0.005) \
        == "edge"
    # shape: a star whose own peak-to-flux ratio is a third of what the nova shows in these images
    typical = [m["peak_ratio"] * 3.0 if m["peak_ratio"] else 0.0 for m in measured]
    assert sweep.veto(0, sources, meas, meta, bright, flux, strength, px, py, clumps, typical, None, 0.005) == "shape"
    # saturation residue: a clump of saturated pixels 8 pixels away
    near = [np.array([[px[i, 0] + 8.0, py[i, 0]]]) for i in range(6)]
    assert sweep.veto(0, sources, meas, meta, bright, flux, strength, px, py, near, [0.0] * 6, None, 0.005) \
        == "saturation_residue"


# ------------------------------------------------------------------ sky cells

def test_a_cell_at_the_equator_is_a_hundredth_of_a_square_degree():
    ci, cj = sweep.cell_of(np.array([10.05]), np.array([0.05]))
    assert (ci[0], cj[0]) == (100, 0)
    assert sweep.cell_area(ci, cj) == pytest.approx(0.01, rel=1e-3)
    ci2, _ = sweep.cell_of(np.array([359.95]), np.array([0.0]))
    assert ci2[0] == -1                       # longitude wraps through zero


def test_a_tile_answers_for_the_sky_nearest_its_centre():
    centres = [(0.0, 0.0), (3.0, 0.0), (357.0, 0.0)]
    pick = sweep.nearest_centre(np.array([0.5, 1.7, 359.0, 3.4]), np.array([0.0, 0.0, 0.0, 0.2]), centres)
    assert pick.tolist() == [0, 1, 0, 1]


# ------------------------------------------------------------------ what the catalogues say

@pytest.fixture(scope="module")
def survivors() -> dict:
    return json.loads((DATA / "survivors_v7994.json").read_text())


def test_the_nova_is_a_known_eruption(survivors):
    s = survivors["nova"]
    result = sweep.classify(s["bright_mjy"], s["catalogues"]["rows"], s["catalogues"]["offsets"])
    assert result["kind"] == "known_eruption"
    assert "V7994 Sgr" in result["reasons"][0]


def test_a_catalogued_bright_variable_is_a_known_variable(survivors):
    s = survivors["variable"]
    result = sweep.classify(s["bright_mjy"], s["catalogues"]["rows"], s["catalogues"]["offsets"])
    assert result["kind"] == "known_variable"
    assert any("W2" in r or "variable" in r for r in result["reasons"])


def test_without_the_eruption_row_the_nova_has_no_bright_counterpart(survivors):
    """Take the VSX and SIMBAD rows away: AllWISE, CatWISE and Gaia show only a star far fainter than 1,289 mJy."""
    s = survivors["nova"]
    rows = [(o, r) for o, r in zip(s["catalogues"]["offsets"], s["catalogues"]["rows"], strict=True)
            if r["catalogue"] not in ("AAVSO VSX", "SIMBAD")]
    result = sweep.classify(s["bright_mjy"], [r for _, r in rows], [o for o, _ in rows])
    assert result["kind"] == "candidate"


def test_nothing_in_any_catalogue_is_a_candidate_and_never_more():
    result = sweep.classify(500.0, [], [])
    assert result["kind"] == "candidate" and "no row within" in result["reasons"][0]


def test_a_catalogue_that_did_not_answer_stops_the_word_uncatalogued():
    cat = {"rows": [], "offsets": [], "answers": {}, "failed": {"AAVSO VSX": "ArchiveError: down"}}
    result = sweep.classify_with_catalogues(500.0, cat)
    assert result["kind"] == "candidate_incomplete" and result["catalogues_failed"] == ["AAVSO VSX"]


def test_infrared_magnitudes_to_millijanskys():
    assert sweep.w2_mjy(0.0) == pytest.approx(171787.0)             # zero magnitude: 171.787 Jy
    assert sweep.w2_mjy(None) is None
    assert sweep.k_mjy(0.0) == pytest.approx(666700.0)

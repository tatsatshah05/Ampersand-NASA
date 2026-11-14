"""Training mode: one made-up moving object added to real frames of Barnard's Star.

The frames are the real ones from tests/data/cache; only the planted object is made up,
which is the whole point of the mode. These tests check that it is planted where the
response says, that it moves, that every picture carries the word SIMULATION, and that
nothing of it reaches /api/frames.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import astrometry, pipeline, spherex, training


@pytest.fixture
def complete(barnard: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """List only the detector 5 exposures whose cutouts are on disk, so nothing is missing."""
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)


def picture(meta: dict, frame: dict) -> np.ndarray:
    assert frame["image"].startswith(f"/frames/{meta['key']}/")
    return np.asarray(Image.open(pipeline.FRAMES_DIR / meta["key"] / Path(frame["image"]).name))


def test_a_round_is_marked_as_a_simulation_everywhere(complete: None, barnard: SimpleNamespace):
    meta = training.build_training(barnard.ra, barnard.dec, level="easy", seed=3)
    assert meta["simulation"] is True
    assert "made-up" in meta["notice"] and "not a real detection" in meta["notice"]
    assert meta["key"].startswith("training-")
    assert len(meta["frames"]) == 3
    for frame in meta["frames"]:
        image = picture(meta, frame)
        corner = image[:training.STAMP_BOX[1], :training.STAMP_BOX[0], :3].reshape(-1, 3)
        orange = (corner[:, 0] > 200) & (corner[:, 1] > 100) & (corner[:, 2] < 50)
        assert orange.sum() > 40, "the word SIMULATION should be drawn in the corner of every picture"


def test_the_object_is_where_the_response_says_and_it_moves(complete: None, barnard: SimpleNamespace):
    meta = training.build_training(barnard.ra, barnard.dec, level="easy", seed=3)
    grid, n, stacks, _, _ = training.epoch_stacks(barnard.ra, barnard.dec, 0.1, 5)
    plain = pipeline.stretch_limits([s["image"] for s in stacks.values()])
    spots = meta["planted"]["positions"]
    assert [p["epoch"] for p in spots] == [1, 2, 3]
    for frame, spot in zip(meta["frames"], spots, strict=True):
        assert frame["planted"] == spot
        x, y = int(round(spot["x"])), int(round(spot["y"]))
        assert 0.1 * n < x < 0.9 * n and 0.1 * n < y < 0.9 * n
        # The planted picture is brighter there than the real one drawn with the same stretch.
        real = stacks[spot["epoch"] - 1]
        real_png = pipeline.FRAMES_DIR / meta["key"] / "real.png"
        pipeline.to_png(real, {k: meta["stretch"][k] for k in ("vmin", "vmax", "soft")}, real_png)
        before = int(np.asarray(Image.open(real_png))[y, x, 0])
        real_png.unlink()
        assert int(picture(meta, frame)[y, x, 0]) > before + 20
    assert plain["vmax"] == pytest.approx(meta["stretch"]["vmax"])     # a faint object does not change the scale
    # It swings between visits by the amount the response states, well over a SPHEREx pixel.
    steps = [float(np.hypot(*astrometry.offset_arcsec(a["ra"], a["dec"], b["ra"], b["dec"])))
             for a, b in zip(spots, spots[1:], strict=False)]
    assert max(steps) > 30
    assert max(steps) <= meta["planted"]["swing_arcsec"] * 1.05
    assert meta["planted"]["peak_over_noise"] == training.LEVELS["easy"]


def test_the_same_seed_gives_the_same_round_and_another_seed_another(complete: None, barnard: SimpleNamespace):
    one = training.build_training(barnard.ra, barnard.dec, seed=11)
    again = training.build_training(barnard.ra, barnard.dec, seed=11)
    other = training.build_training(barnard.ra, barnard.dec, seed=12)
    assert one["planted"]["positions"] == again["planted"]["positions"]
    assert one["planted"]["positions"] != other["planted"]["positions"]


def test_the_planted_object_never_reaches_the_real_frames(complete: None, barnard: SimpleNamespace):
    real_before = pipeline.build_frames(barnard.ra, barnard.dec)
    pixels_before = [picture(real_before, f).copy() for f in real_before["frames"]]
    meta = training.build_training(barnard.ra, barnard.dec, level="easy", seed=5)
    real_after = pipeline.build_frames(barnard.ra, barnard.dec)
    assert real_after == real_before
    assert "simulation" not in real_after and not real_after["key"].startswith("training-")
    for old, frame in zip(pixels_before, real_after["frames"], strict=True):
        assert np.array_equal(old, picture(real_after, frame))
    assert meta["key"] != real_after["key"]


def test_difference_frames_show_the_object_leaving_and_arriving(complete: None, barnard: SimpleNamespace):
    meta = training.build_training(barnard.ra, barnard.dec, mode="difference", level="easy", seed=3)
    assert [f["epoch"] for f in meta["frames"]] == [2, 3] and meta["reference_epoch"] == 1
    for frame in meta["frames"]:
        image = picture(meta, frame)
        here, there = frame["planted"], frame["planted_in_reference"]
        assert int(image[int(round(here["y"])), int(round(here["x"])), 0]) > 150       # arrived: brighter than grey
        assert int(image[int(round(there["y"])), int(round(there["x"])), 0]) < 105     # left: darker than grey


def test_the_endpoint_answers_and_serves_the_pictures(client: TestClient, complete: None, barnard: SimpleNamespace):
    response = client.get("/api/training", params={"ra": barnard.ra, "dec": barnard.dec, "level": "hard", "seed": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["simulation"] is True and body["level"] == "hard"
    assert client.get(body["frames"][0]["image"]).headers["content-type"] == "image/png"


@pytest.mark.parametrize("params, words", [
    ({"level": "impossible"}, "level must be"),
    ({"mode": "sum"}, "mode must be"),
])
def test_bad_requests_are_explained(client: TestClient, complete: None, barnard: SimpleNamespace,
                                    params: dict, words: str):
    response = client.get("/api/training", params={"ra": barnard.ra, "dec": barnard.dec, **params})
    assert response.status_code == 400 and words in response.json()["detail"]


def test_one_visit_is_not_enough(barnard: SimpleNamespace, monkeypatch: pytest.MonkeyPatch):
    first_visit = [e for e in barnard.exposures_on_disk if e["mjd"] < barnard.exposures_on_disk[0]["mjd"] + 30]
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: first_visit)
    with pytest.raises(ValueError, match="at least two SPHEREx visits"):
        training.build_training(barnard.ra, barnard.dec, seed=1)

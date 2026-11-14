"""New SPHEREx data reaches views that are already on disk, without making anyone wait.

A cached view records how many exposures the archive listed when it was built. When the
archive's list for that position changes, the view is built again. The real Barnard's
Star cutouts are used; "the archive lists something else" is played by handing the
backend a list with one exposure fewer, which needs no made-up data.
"""
from __future__ import annotations

import os
import time
from types import SimpleNamespace

import pytest

from backend import photometry, pipeline, spherex


def test_a_view_is_built_again_when_the_archives_list_changes(barnard: SimpleNamespace,
                                                              monkeypatch: pytest.MonkeyPatch):
    listed = list(barnard.exposures_on_disk)
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: listed)
    first = pipeline.build_frames(barnard.ra, barnard.dec)
    assert first["exposures_total_all_detectors"] == len(listed)
    assert pipeline.build_frames(barnard.ra, barnard.dec) == first          # same list: served from disk

    last_d5 = [e for e in listed if e["detector"] == 5][-1]
    other = [e for e in listed if e is not last_d5]
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: other)
    rebuilt = pipeline.build_frames(barnard.ra, barnard.dec)
    assert rebuilt["key"] == first["key"]                                   # the same view, built again
    assert rebuilt["exposures_total_all_detectors"] == len(other)
    assert rebuilt["frames"][-1]["n_exposures"] == first["frames"][-1]["n_exposures"] - 1


def test_brightness_is_measured_again_when_the_list_changes(barnard: SimpleNamespace,
                                                            monkeypatch: pytest.MonkeyPatch):
    listed = list(barnard.exposures_on_disk)
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: listed)
    first = photometry.lightcurve(barnard.ra, barnard.dec, 5)
    assert first["exposures_listed"] == len(listed)
    assert photometry.lightcurve(barnard.ra, barnard.dec, 5) == first

    other = [e for e in listed if e is not [x for x in listed if x["detector"] == 5][-1]]
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: other)
    again = photometry.lightcurve(barnard.ra, barnard.dec, 5)
    assert again["exposures_listed"] == len(other)
    assert sum(b["n_points"] for b in again["bins"]) == sum(b["n_points"] for b in first["bins"]) - 1


def test_an_old_list_never_holds_up_a_view_that_is_on_disk(barnard: SimpleNamespace, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(spherex, "find_exposures", lambda ra, dec: barnard.exposures_on_disk)
    first = pipeline.build_frames(barnard.ra, barnard.dec)
    list_file = spherex._list_file(barnard.ra, barnard.dec)
    asked: list[tuple[float, float]] = []
    monkeypatch.setattr(spherex, "_refresh_list", lambda ra, dec: asked.append((ra, dec)))
    monkeypatch.setattr(spherex, "_list_refresh", {})
    long_ago = time.time() - 2 * spherex.LIST_MAX_AGE_S
    os.utime(list_file, (long_ago, long_ago))
    try:
        # Too old to trust, so no verdict yet: the view on disk is served as it is ...
        assert spherex.list_changed(barnard.ra, barnard.dec, 1) is False
        assert pipeline.build_frames(barnard.ra, barnard.dec) == first
        # ... and the archive is asked in the background, once, not once per request.
        deadline = time.time() + 5
        while not asked and time.time() < deadline:
            time.sleep(0.02)
        assert asked == [(barnard.ra, barnard.dec)]
    finally:
        os.utime(list_file, None)


def test_a_result_with_no_count_is_kept():
    assert spherex.list_changed(10.0, 10.0, None) is False      # built before counts were recorded
    assert spherex.list_changed(11.0, 11.0, 5) is False         # a position the archive was never asked about

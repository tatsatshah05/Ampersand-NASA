"""backend/spherex.py: the cache writer, the exposure list and where cutouts are filed.

The archive itself is never contacted. Where a test needs an answer from IRSA it hands
spherex.http_get a small made-up table in the same format (a VOTable).
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import time

import pytest
from astropy.io.votable import from_table
from astropy.table import Table

from backend import spherex

# ------------------------------------------------------------ the cache writer


def test_write_json_creates_folders_and_leaves_nothing_else_behind(tmp_path):
    target = tmp_path / "frames" / "abc123" / "frames.json"
    entry = {"frames": [1, 2.5, None], "message": "text"}
    spherex.write_json(target, entry)
    assert json.loads(target.read_text()) == entry
    assert [p.name for p in target.parent.iterdir()] == ["frames.json"]      # the temporary file is gone

    spherex.write_json(target, {"frames": []}, indent=1)                     # replacing a longer entry
    assert json.loads(target.read_text()) == {"frames": []}


def test_write_json_replaces_the_file_instead_of_rewriting_it(tmp_path):
    """Write to a temporary name, then rename: a reader has either the old file or the new one."""
    target = tmp_path / "entry.json"
    spherex.write_json(target, {"version": 1})
    before = os.stat(target).st_ino
    spherex.write_json(target, {"version": 2})
    assert os.stat(target).st_ino != before, "the file was rewritten in place, so a reader could see half of it"


def test_write_json_keeps_the_old_entry_when_the_new_one_cannot_be_written(tmp_path):
    target = tmp_path / "entry.json"
    spherex.write_json(target, {"complete": True})
    with pytest.raises(TypeError):
        spherex.write_json(target, {"frames": {1, 2, 3}})                    # a set is not JSON
    assert json.loads(target.read_text()) == {"complete": True}
    assert [p.name for p in tmp_path.iterdir()] == ["entry.json"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows refuses to replace a file that a reader has open")
def test_readers_never_see_half_an_entry(tmp_path):
    """The server and the warm-up script can write the same entry while a request reads it."""
    target = tmp_path / "frames.json"
    entries = [{"writer": i, "rows": list(range(20_000))} for i in range(4)]   # about 130 kB each
    spherex.write_json(target, entries[0])
    problems: list[str] = []
    done = threading.Event()

    def write(entry: dict) -> None:
        try:
            for _ in range(25):
                spherex.write_json(target, entry)
        except Exception as e:  # noqa: BLE001 - any failure in a writer is what this test looks for
            problems.append(f"writer: {e!r}")

    def read() -> None:
        while not done.is_set():
            try:
                assert len(json.loads(target.read_text())["rows"]) == 20_000
            except Exception as e:  # noqa: BLE001 - half a file shows up as a JSON error here
                problems.append(f"reader: {e!r}")
                return

    reader = threading.Thread(target=read)
    writers = [threading.Thread(target=write, args=(entry,)) for entry in entries]
    reader.start()
    for w in writers:
        w.start()
    for w in writers:
        w.join()
    done.set()
    reader.join()

    assert problems == []
    assert json.loads(target.read_text()) in entries
    assert [p.name for p in tmp_path.iterdir()] == ["frames.json"]


# ----------------------------------------------------------- the exposure list

def sia_answer(rows: list[tuple[str, int, float, str]]) -> bytes:
    """A made-up SIA2 answer: (obs_id, detector, start MJD, collection) per row, as a VOTable."""
    table = Table({
        "obs_id": [r[0] for r in rows],
        "energy_bandpassname": [f"SPHEREx-D{r[1]}" for r in rows],
        "t_min": [r[2] for r in rows],
        "t_exptime": [113.5826] * len(rows),
        "access_url": [f"https://irsa.example/{r[3]}/{r[0]}D{r[1]}.fits" for r in rows],
        "obs_collection": [r[3] for r in rows],
        "em_min": [3.8113e-6] * len(rows),     # metres, as the service gives them
        "em_max": [4.43e-6] * len(rows),
    })
    out = io.BytesIO()
    from_table(table).to_xml(out)
    return out.getvalue()


@pytest.fixture
def archive(monkeypatch: pytest.MonkeyPatch, tmp_path) -> list[dict]:
    """A stand-in for IRSA with three exposures, one of them present in both data releases."""
    answers = {
        "spherex_dr1": sia_answer([("2026W11_2A_0501_1", 5, 61114.03, "spherex_dr1"),
                                   ("2025W34_2B_0090_4", 5, 60908.98, "spherex_dr1"),
                                   ("2025W34_2B_0090_4", 3, 60908.98, "spherex_dr1")]),
        "spherex_qr3": sia_answer([("2026W34_1A_0363_1", 5, 61270.87, "spherex_qr3"),
                                   ("2026W11_2A_0501_1", 5, 61114.03, "spherex_qr3")]),
    }
    asked: list[dict] = []

    def fake_http_get(url: str, params: dict | None = None, **_: object) -> bytes:
        assert url == spherex.SIA_URL and params is not None
        asked.append(params)
        return answers[params["COLLECTION"]]

    monkeypatch.setattr(spherex, "http_get", fake_http_get)
    monkeypatch.setattr(spherex, "CACHE", tmp_path)
    return asked


def test_exposure_list_is_merged_sorted_and_cached(archive: list[dict], tmp_path):
    exposures = spherex.find_exposures(269.446267, 4.768222)
    assert [a["COLLECTION"] for a in archive] == spherex.COLLECTIONS
    assert all(a["POS"] == "circle 269.446267 4.768222 0.01" for a in archive)

    # Oldest first; the exposure that is in both releases counts once, and the same
    # exposure seen by two detectors counts twice.
    assert [(e["obs_id"], e["detector"]) for e in exposures] == [
        ("2025W34_2B_0090_4", 5), ("2025W34_2B_0090_4", 3), ("2026W11_2A_0501_1", 5), ("2026W34_1A_0363_1", 5)]
    newest = exposures[-1]
    assert newest["collection"] == "spherex_qr3" and newest["mjd"] == 61270.87
    assert (newest["wave_min"], newest["wave_max"]) == pytest.approx((3.8113, 4.43))     # microns
    assert newest["url"].endswith("2026W34_1A_0363_1D5.fits")

    # A second call within the day is answered from the file the first one wrote.
    assert spherex.find_exposures(269.446267, 4.768222) == exposures
    assert len(archive) == 2
    assert len(list((tmp_path / "queries").glob("sia_*.json"))) == 1


def test_exposure_list_is_asked_for_again_after_a_day(archive: list[dict], tmp_path):
    """New exposures keep arriving, so the cached list expires (the cutouts themselves never do)."""
    spherex.find_exposures(269.446267, 4.768222)
    (cached,) = (tmp_path / "queries").glob("sia_*.json")
    two_days_ago = time.time() - 2 * 86400
    os.utime(cached, (two_days_ago, two_days_ago))
    spherex.find_exposures(269.446267, 4.768222)
    assert len(archive) == 4


def test_an_expired_exposure_list_is_still_used_when_the_archive_is_down(
        archive: list[dict], monkeypatch: pytest.MonkeyPatch, tmp_path):
    """A day-old list only lacks the newest exposures; refusing the view would be worse."""
    first = spherex.find_exposures(269.446267, 4.768222)
    (cached,) = (tmp_path / "queries").glob("sia_*.json")
    two_days_ago = time.time() - 2 * 86400
    os.utime(cached, (two_days_ago, two_days_ago))

    def archive_is_down(url: str, params: dict | None = None, **_: object) -> bytes:
        raise spherex.ArchiveError("HTTP 502 from the archive")

    monkeypatch.setattr(spherex, "http_get", archive_is_down)
    assert spherex.find_exposures(269.446267, 4.768222) == first
    # With nothing cached for a position, the failure is still reported.
    with pytest.raises(spherex.ArchiveError):
        spherex.find_exposures(10.0, 10.0)


# ------------------------------------------------------- where cutouts are filed

def test_cutouts_are_filed_by_centre_size_exposure_and_detector():
    exposure = {"obs_id": "2025W34_2B_0090_4", "detector": 5}
    path = spherex._cutout_path(exposure, 269.446267, 4.768222, 0.15)
    assert path.name == "2025W34_2B_0090_4_D5.fits"
    assert path.parent.parent == spherex.CACHE / "cutouts"
    # The folder Barnard's Star has in the cache warmed for the demo. If this changes,
    # every cutout already downloaded is ignored and fetched again.
    assert path.parent.name == "01e6af5d45"
    assert spherex._cutout_path(exposure, 269.4462674, 4.7682221, 0.15) == path           # same to five decimals
    assert spherex._cutout_path(exposure, 269.446267, 4.768222, 0.30).parent != path.parent
    assert spherex._cutout_path(exposure, 269.446367, 4.768222, 0.15).parent != path.parent
    assert spherex._cutout_path({**exposure, "detector": 6}, 269.446267, 4.768222, 0.15).name.endswith("_D6.fits")


def test_s3_is_tried_first_and_irsa_is_the_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """A cutout comes from S3 when S3 answers, and from IRSA when it does not."""
    exposure = {"obs_id": "2099W01_1A_0001_1", "detector": 5, "url": "https://irsa.example/a.fits"}
    routes: list[str] = []

    def s3_answers(exp, ra, dec, size_deg, path, **_):
        routes.append("s3")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"from s3")
        return path

    def s3_is_down(exp, ra, dec, size_deg, path, **_):
        routes.append("s3 failed")
        raise spherex.s3fetch.S3Error("the bucket did not answer")

    def irsa(url: str, params: dict | None = None, **_: object) -> bytes:
        routes.append("irsa")
        raise spherex.ArchiveError("stop here: the test only needs to see IRSA being asked")

    monkeypatch.setenv("SPHEREX_USE_S3", "1")
    monkeypatch.setattr(spherex, "http_get", irsa)
    monkeypatch.setattr(spherex.s3fetch, "fetch_cutout", s3_answers)
    assert spherex.fetch_cutout(exposure, 40.0, 20.0, 0.15).read_bytes() == b"from s3"
    assert routes == ["s3"]

    routes.clear()
    monkeypatch.setattr(spherex.s3fetch, "fetch_cutout", s3_is_down)
    with pytest.raises(spherex.ArchiveError):
        spherex.fetch_cutout({**exposure, "detector": 6}, 40.0, 20.0, 0.15)
    assert routes == ["s3 failed", "irsa"]

    routes.clear()
    monkeypatch.setenv("SPHEREX_USE_S3", "0")
    with pytest.raises(spherex.ArchiveError):
        spherex.fetch_cutout({**exposure, "detector": 4}, 40.0, 20.0, 0.15)
    assert routes == ["irsa"]


def test_a_cutout_that_cannot_be_fetched_is_reported_not_raised(network: list[str]):
    exposures = [{"obs_id": "2099W01_1A_0001_1", "detector": 5, "url": "https://irsa.example/a.fits"},
                 {"obs_id": "2099W01_1A_0001_2", "detector": 5, "url": "https://irsa.example/b.fits"}]
    progress: list[tuple[int, int]] = []
    results = spherex.fetch_cutouts(exposures, 12.5, -3.25, 0.15,
                                    progress=lambda done, total: progress.append((done, total)))
    assert [(exp["obs_id"], path) for exp, path, _ in results] == [("2099W01_1A_0001_1", None),
                                                                   ("2099W01_1A_0001_2", None)]
    assert all(error is not None and error.startswith("ArchiveError") for _, _, error in results)
    assert sorted(network) == ["https://irsa.example/a.fits?center=12.500000,-3.250000&size=0.15000",
                               "https://irsa.example/b.fits?center=12.500000,-3.250000&size=0.15000"]
    assert progress == [(1, 2), (2, 2)]

"""The sweep data behind the "Observe anomalies" screen (frontend/public/anomalies/sweep.json), checked offline.

sweep.json is made by scripts/export_anomalies.py from docs/sweep/summary.json, docs/sweep.md and the sweep's tile
records in the cache. tests/data/sweep_export/tiles/ holds pieces of those tile records, copied unchanged: for the
seven tiles that hold a known variable or a known eruption, only those survivors' positions and classifications
(never a candidate's record, which carries the sweep's withdrawn position). These tests need neither the cache nor
the network.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import export_anomalies as X  # noqa: E402

PIECES = ROOT / "tests" / "data" / "sweep_export" / "tiles"
NO_TILES = ROOT / "tests" / "data" / "sweep_export" / "no-such-folder"


def exported() -> dict:
    return json.loads(X.OUT.read_text())


def checkout(tmp_path: Path) -> Path:
    """A copy of the two docs files the export reads, to change in a test."""
    root = tmp_path / "root"
    (root / "docs" / "sweep").mkdir(parents=True)
    shutil.copy(ROOT / X.SUMMARY, root / X.SUMMARY)
    shutil.copy(ROOT / X.WRITEUP, root / X.WRITEUP)
    return root


def test_the_committed_export_is_up_to_date_with_the_docs_and_the_tile_records() -> None:
    problems, notes = X.check(X.OUT, ROOT, PIECES)
    assert problems == [] and notes == []


def test_without_the_tile_records_the_rest_is_still_checked() -> None:
    problems, notes = X.check(X.OUT, ROOT, NO_TILES)
    assert problems == [] and len(notes) == 1 and "not re-checked" in notes[0]


def test_the_fourteen_survivors_by_kind() -> None:
    doc = exported()
    assert doc["counts"] == {"candidate": 3, "known_eruption": 2, "known_variable": 6, "set_aside": 3, "total": 14}
    assert [s["kind"] for s in doc["survivors"]] == ["candidate"] * 3 + ["known_eruption"] * 2 + \
        ["known_variable"] * 6 + ["set_aside"] * 3
    assert doc["area_sq_deg"] == 472.64 and doc["area_text"] == "472.6" and doc["tiles_done"] == 63
    assert doc["swept"] == "2026-11-14" and doc["ruled"] == "2026-11-15"
    assert doc["visits"] == "August to September 2025, February to April 2026, August to September 2026"


def test_the_candidates_are_the_rulings_at_their_corrected_places() -> None:
    doc = exported()
    vetted = json.loads((ROOT / "docs" / "sweep" / "vetting" / "candidates.json").read_text())["candidates"]
    by_label = {c["label"]: c for c in vetted}
    cands = [s for s in doc["survivors"] if s["kind"] == "candidate"]
    assert [c["label"] for c in cands] == ["A", "B", "C"]
    for c in cands:
        v = by_label[c["label"]]
        assert (c["ra"], c["dec"], c["sexagesimal"]) == (v["ra"], v["dec"], v["sexagesimal"])
        assert c["allowed_sentence"] == v["allowed_sentence"]
        assert c["constellation"] == c["constellation_ruled"] == v["constellation"]
    # The sweep's first, withdrawn positions appear nowhere in the file.
    text = X.OUT.read_text()
    for v in vetted:
        ra, dec = v["first_run_position_withdrawn"]
        assert str(ra) not in text and str(abs(dec)) not in text


def test_what_the_known_objects_are_known_as() -> None:
    doc = exported()
    eruptions = {s["known_as"]: s for s in doc["survivors"] if s["kind"] == "known_eruption"}
    assert set(eruptions) == {"V7994 Sagittarii (nova, 2025)", "V0691 Serpentis (nova)"}
    assert eruptions["V7994 Sagittarii (nova, 2025)"]["catalogue_name"] == "V7994 Sgr"
    assert eruptions["V0691 Serpentis (nova)"]["evidence"].startswith("AAVSO VSX type NA, 2.7 arcsec away")
    variables = [s for s in doc["survivors"] if s["kind"] == "known_variable"]
    assert all(s["catalogue"] == "AllWISE" and s["catalogue_name"].startswith("WISEA J") for s in variables)
    assert all(s["catalogue_text"].endswith("already bright") for s in variables)
    nebula = next(s for s in doc["survivors"] if s["kind"] == "set_aside" and s["ra"] == 272.10809)
    assert "planetary nebula PN M 1-40" in nebula["why"]


def test_check_fails_when_the_summary_changes(tmp_path: Path) -> None:
    root = checkout(tmp_path)
    summary = json.loads((root / X.SUMMARY).read_text())
    summary["survivors"][1]["bright_mjy"] = 99.9
    (root / X.SUMMARY).write_text(json.dumps(summary, indent=1) + "\n")
    problems, _ = X.check(X.OUT, root, PIECES)
    assert any("made from a different" in p for p in problems)
    assert any("bright_mjy" in p for p in problems)


def test_check_fails_when_the_writeup_changes(tmp_path: Path) -> None:
    root = checkout(tmp_path)
    md = root / X.WRITEUP
    md.write_text(md.read_text().replace("the catalogued planetary nebula PN M 1-40", "the nebula PN M 1-40"))
    problems, _ = X.check(X.OUT, root, PIECES)
    assert any("why" in p for p in problems)


def test_check_fails_when_the_export_is_edited_or_missing(tmp_path: Path) -> None:
    doc = exported()
    doc["survivors"][5]["catalogue_name"] = "WISEA J000000.00-000000.0"
    doc["counts"]["total"] = 15
    edited = tmp_path / "sweep.json"
    edited.write_text(json.dumps(doc))
    problems, _ = X.check(edited, ROOT, PIECES)
    assert any("counts" in p for p in problems)
    assert any("catalogue_name differs from its tile record" in p for p in problems)
    missing = X.check(tmp_path / "missing.json", ROOT, PIECES)[0]
    assert missing == ["missing.json: missing (run scripts/export_anomalies.py)"]


def test_the_command_line_check_falls_back_to_the_repositorys_tile_pieces(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # No tile records in the cache: the catalogue_* fields are still checked, against tests/data/sweep_export/tiles.
    monkeypatch.setenv("SPHEREX_CACHE_DIR", str(tmp_path / "empty-cache"))
    assert X.main(["--check"]) == 0
    assert "checked against the repository's copy, tests/data/sweep_export/tiles" in capsys.readouterr().out
    # So a hand-edited catalogue_name is caught even there.
    doc = json.loads(X.OUT.read_text())
    edited = next(s for s in doc["survivors"] if s["kind"] == "known_variable")
    edited["catalogue_name"] = "WISEA J000000.00-000000.0"
    out = tmp_path / "sweep.json"
    out.write_text(json.dumps(doc))
    assert X.main(["--check", "--out", str(out)]) == 1
    assert "catalogue_name differs from its tile record" in capsys.readouterr().out


def test_the_command_line_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert X.main(["--check", "--tiles", str(PIECES)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert X.main(["--check", "--tiles", str(PIECES), "--out", str(tmp_path / "none.json")]) == 1


def test_reading_the_writeup() -> None:
    words = X.from_writeup((ROOT / X.WRITEUP).read_text())
    assert [e["known_as"] for e in words["eruptions"]] == ["V7994 Sagittarii (nova, 2025)", "V0691 Serpentis (nova)"]
    assert words["eruptions"][0]["position"] == (270.96982, -31.45708)
    assert [s["position"] for s in words["set_aside"]] == [(267.49549, -27.56803), (272.10809, -22.28134),
                                                           (279.73756, -3.86269), (261.92881, -35.29494)]
    with pytest.raises(ValueError):
        X.table_after("No such heading", "# Title\n")


def test_choosing_the_name_of_a_known_variable() -> None:
    got = X.catalogue_fields({"kind": "known_variable", "reasons": [
        "CWISE J175109.20-263709.1 (CatWISE2020) W2 9.96 mag = 18 mJy, already bright",
        "WISEA J175109.30-263700.0 (AllWISE) W2 9.76 mag = 21 mJy, already bright",
    ]})
    assert got["catalogue_name"] == "WISEA J175109.30-263700.0" and got["catalogue"] == "AllWISE"
    assert got["catalogue_text"] == "WISEA J175109.30-263700.0 (AllWISE) W2 9.76 mag = 21 mJy, already bright"
    assert len(got["catalogue_reasons"]) == 2
    assert X.sep_arcsec(0.0, 0.0, 359.9999, 0.0) == pytest.approx(0.36, abs=0.01)

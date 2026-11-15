"""The data behind the "Three tools" screen (frontend/public/lab/), checked offline.

The lab files are made by scripts/export_lab.py from the three methods' results files and the cached
cutouts. These tests need neither the cache nor the network:
- tests/data/lab/*_results_piece.json are small pieces of the real results files (only the keys the
  export copies), saved unchanged; the export's headline functions must give the same numbers from them
  as from the full files, and those numbers must be what the lab files hold;
- the lab files must have the fields the screen reads (section 7 of the build spec, as adapted);
- `python scripts/export_lab.py --check` must exit non-zero as soon as a lab file is out of date.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import export_lab as X  # noqa: E402

LAB = ROOT / "frontend" / "public" / "lab"
PIECES = ROOT / "tests" / "data" / "lab"


def lab(tool: str) -> dict:
    return json.loads((LAB / f"{tool}.json").read_text(), parse_constant=_no_nan)


def _no_nan(name: str):
    raise ValueError(f"{name} in a lab file")


def piece(tool: str) -> dict:
    return json.loads((PIECES / f"{tool}_results_piece.json").read_text())


@pytest.mark.parametrize("tool", X.TOOLS)
def test_pieces_are_faithful_to_the_results_files(tool):
    full = json.loads((ROOT / X.RESULTS[tool]).read_text())
    assert X.HEADLINES[tool](piece(tool)) == X.HEADLINES[tool](full)


@pytest.mark.parametrize("tool", X.TOOLS)
def test_every_headline_number_is_the_results_files_number(tool):
    doc = lab(tool)
    for path, value in X.leaves(X.HEADLINES[tool](piece(tool))):
        assert json.dumps(X.get_path(doc, path), sort_keys=True) == json.dumps(value, sort_keys=True), path


def test_headline_numbers_read_from_the_pieces():
    r = X.headline_reflex(piece("reflex"))
    assert r["candidate"]["distance_au"] == 111.1
    assert r["candidate"]["range_95_au"] == [76.5, None]  # unbounded on the far side
    assert r["candidate"]["separation_arcsec"] == 1.24
    assert r["shifted"]["distance_au"] == 117.6
    c = X.headline_colourwalk(piece("colourwalk"))
    assert round(c["walk"]["all"]["size"], 3) == 0.182 and round(c["walk"]["all"]["sigma"], 2) == 2.05
    assert c["verdict"] == "nothing_found"
    assert sum(not v for v in c["acceptance"]["checks"].values()) == 2
    t = X.headline_transits(piece("transits"))
    assert round(100 * t["d5"]["depth"], 3) == 1.175 and round(100 * t["d5"]["empirical_err"], 3) == 0.263
    assert t["d5"]["n"] == 484 and t["d5"]["n_in"] == 65 and t["d5"]["n_fake"] == 598


@pytest.mark.parametrize("tool", X.TOOLS)
def test_lab_files_have_the_fields_the_screen_reads(tool):
    doc = lab(tool)
    for path in X.REQUIRED[tool]:
        X.get_path(doc, path)
    assert doc["schema"] == X.SCHEMA and doc["tool"] == tool
    assert doc["source"]["results_file"] == X.RESULTS[tool]
    for name in doc["files"]:
        assert (LAB / name).exists(), name


def test_reflex_shapes():
    doc = lab("reflex")
    n = doc["visit"]["n_used"]
    assert len(doc["jpl"]["positions"]) == n and len(doc["track_mjd"]) == n
    assert len(doc["demo"]["marks"]["nasa_path_px"]) == n
    assert [s["label"] for s in doc["stops"]][0] == "No bend" and len(doc["stops"]) == 7
    for s in [*doc["stops"], doc["wrong_way"]]:
        for key in ("inv_d", "snr", "delta", "track_east", "track_north", "linear_east", "linear_north"):
            assert key in s, key
        assert len(s["track_east"]) == n
    assert doc["stops"][0]["delta"] == 0.0
    assert doc["wrong_way"]["delta"] < 0  # the wrong-way control is only kept while this holds
    assert doc["jpl"]["helio_distance_au"] != doc["jpl"]["observer_distance_au"]
    assert doc["limit"]["injection_tested"] is False
    for name in ("single", "plain_mean", "slid"):
        assert doc["demo"][name]["png"] in doc["files"]
    for x, y in [doc["demo"]["marks"]["tool_dot_px"], doc["demo"]["marks"]["nasa_mid_px"]]:
        assert 0 <= x <= doc["demo"]["crop_px"] and 0 <= y <= doc["demo"]["crop_px"]


def test_colourwalk_shapes():
    doc = lab("colourwalk")
    assert [g["name"] for g in doc["groups"]] == ["Bluer", "Middle", "Redder"]
    for g in doc["groups"]:
        for key in ("lo_um", "hi_um", "png", "east", "north", "err_east", "err_north"):
            assert key in g
        assert g["err_east"] >= doc["walk"]["measured_floor_arcsec"]["east"]  # the floors are in the errors
    assert doc["status"]["method_proven"] is False and doc["status"]["chip_key"] == "not_proven"
    assert doc["walk"]["sigma_guessed_floor"] > doc["walk"]["all"]["sigma"]
    assert doc["magnification"] in X.MAGNIFICATIONS
    if doc["lone_star"].get("available"):
        assert [g["name"] for g in doc["lone_star"]["groups"]] == ["Bluer", "Middle", "Redder"]


def test_transits_shapes():
    doc = lab("transits")
    assert len(doc["readings"]) == doc["d5"]["n"]
    assert set(doc["readings"][0]) == {"bjd_tdb", "rel_flux", "err", "wl_um"}
    periods = [s["period_d"] for s in doc["stops"]]
    assert periods == sorted(periods) and sum(s["known"] for s in doc["stops"]) == 1
    known = next(s for s in doc["stops"] if s["known"])
    assert known["depth"] == pytest.approx(doc["d5"]["depth"], rel=1e-10)  # rounded to 12 figures for transport
    for s in doc["stops"]:
        assert s["allowed_by_fake_exclude"]
        assert (s["depth"] is None) == ("why" in s)
    assert doc["development_object"] is True
    assert doc["wasp100"]["n_clear"] == 1


def test_transport_sizes():
    json_bytes = sum((LAB / f"{t}.json").stat().st_size for t in X.TOOLS)
    png_bytes = sum(p.stat().st_size for p in LAB.glob("*.png"))
    assert json_bytes < 600_000 and png_bytes < 300_000


def _copy_checkout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "root"
    for tool in X.TOOLS:
        for rel in (X.RESULTS[tool], X.WRITEUPS[tool]):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, root / rel)
    lab_copy = tmp_path / "lab"
    shutil.copytree(LAB, lab_copy)
    return root, lab_copy


def _run_check(root: Path, lab_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "export_lab.py"),
            "--check",
            "--root",
            str(root),
            "--lab-dir",
            str(lab_dir),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def test_check_passes_on_the_lab_files_as_committed(tmp_path):
    root, lab_dir = _copy_checkout(tmp_path)
    out = _run_check(root, lab_dir)
    assert out.returncode == 0, out.stdout + out.stderr


def test_check_fails_when_a_results_file_changes(tmp_path):
    root, lab_dir = _copy_checkout(tmp_path)
    f = root / X.RESULTS["reflex"]
    data = json.loads(f.read_text())
    data["eris"]["candidate"]["distance_au"] = 99.9
    f.write_text(json.dumps(data, indent=1))
    out = _run_check(root, lab_dir)
    assert out.returncode != 0
    assert "candidate.distance_au" in out.stdout and "reflex.json" in out.stdout


def test_check_fails_when_a_picture_or_field_is_missing(tmp_path):
    root, lab_dir = _copy_checkout(tmp_path)
    doc = json.loads((lab_dir / "transits.json").read_text())
    del doc["readings"]
    (lab_dir / "transits.json").write_text(json.dumps(doc))
    (lab_dir / "reflex_slid.png").write_bytes(b"not the picture")
    out = _run_check(root, lab_dir)
    assert out.returncode != 0
    assert "readings" in out.stdout and "reflex_slid.png" in out.stdout


def test_check_fails_when_a_writeups_final_status_changes(tmp_path):
    root, lab_dir = _copy_checkout(tmp_path)
    doc = json.loads((lab_dir / "reflex.json").read_text())
    # flip what the write-up says: a final write-up loses its words, a draft gains them
    (root / X.WRITEUPS["reflex"]).write_text("Nothing here says so.\n" if doc["final"] else "In this finalisation.\n")
    out = _run_check(root, lab_dir)
    assert out.returncode != 0 and "final" in out.stdout

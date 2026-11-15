"""The pre-built demo results: pack them on a laptop, unpack them into a deployed image.

A host with a slow processor or no disk of its own (Render's free plan) would otherwise build
every view from NASA's archive on a visitor's first click. This puts the finished results of
the demo (the views of the eleven buttons and the answers of their tools) in the cache folder
when the image is built. It holds results only: no cutouts, so anything else a visitor asks
for is still fetched from the archive, as always. Steps: docs/deploy-render.md.

    python scripts/seed_cache.py pack  <archive.tar.gz>          on the laptop, from backend/cache
    python scripts/seed_cache.py fetch <url> <cache folder>       in the Dockerfile
    python scripts/seed_cache.py copy  <from> <cache folder>      when the container starts
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Finished results, a few hundred megabytes in all. Left out on purpose: the cutouts (cutouts/,
# search2/cutouts/, many gigabytes) and the working folders of the write-ups (sweep/, follow/, ...).
PARTS = ["frames", "queries", "photometry", "smallbodies", "distant", "search", "colour", "watchlist",
         "search2/results", "search2/catalogues"]


def pack(archive: Path, cache: Path) -> None:
    """Write `archive` from the finished results under `cache`, with an empty vote list."""
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "cache"
        for part in PARTS:
            if (cache / part).is_dir():
                shutil.copytree(cache / part, staged / part)
            else:
                print(f"not there, left out: {part}")
        votes = staged / "watchlist" / "watchlist.sqlite3"
        if votes.exists():            # a public copy starts with nobody's votes
            with sqlite3.connect(votes) as db:
                db.execute("DELETE FROM votes")
            sqlite3.connect(votes).execute("VACUUM").close()
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(staged, arcname=".")
    files = sum(1 for _ in tarfile.open(archive))
    print(f"{archive}: {archive.stat().st_size / 1e6:.0f} MB, {files} entries")


def fetch(url: str, cache: Path) -> None:
    """Download the archive at `url` and unpack it into `cache`. No url: nothing to do."""
    if not url:
        print("no SEED_URL given: the image is built without the pre-built demo results")
        return
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - an https address we wrote
                    shutil.copyfileobj(response, tmp)
                break
            except OSError as error:
                print(f"try {attempt} of 3 failed: {error}")
                tmp.seek(0)
                tmp.truncate()
                if attempt == 3:
                    raise SystemExit(f"could not download the pre-built demo results from {url}") from error
                time.sleep(5 * attempt)
        tmp.flush()
        with tarfile.open(tmp.name) as tar:
            tar.extractall(cache, filter="data")
    print(f"pre-built demo results unpacked into {cache}: {sum(1 for p in cache.rglob('*') if p.is_file())} files")


def copy(source: Path, cache: str) -> None:
    """A cache folder on a mounted disk that is still empty gets the image's copy, once."""
    if not cache or not source.is_dir():
        return
    target = Path(cache)
    if target.resolve() == source.resolve() or (target / "frames").exists():
        return
    shutil.copytree(source, target, dirs_exist_ok=True)
    print(f"pre-built demo results copied to {target}")


def main(argv: list[str]) -> None:
    if len(argv) == 2 and argv[0] == "pack":
        pack(Path(argv[1]), ROOT / "backend" / "cache")
    elif len(argv) == 3 and argv[0] == "fetch":
        fetch(argv[1], Path(argv[2]))
    elif len(argv) == 3 and argv[0] == "copy":
        copy(Path(argv[1]), argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

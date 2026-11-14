# SPHEREx sky-change viewer

Team Ampersand's entry for NASA Space Apps 2026, "Planet X and SPHEREx".

SPHEREx is a NASA space telescope that photographs the whole sky in infrared light and
comes back to the same patch about every six months. This tool shows those images of one
patch of sky, one visit after another like a short film, so that anything that moved or
changed brightness stands out. Everything shown comes from real SPHEREx data, except one
clearly marked practice mode.

Words used throughout: a **visit** is one of SPHEREx's passes over a patch of sky (each
visit is many exposures, stacked into one frame). A **detector** is one of the six
infrared cameras, together covering 0.75 to 5.0 micrometres.

## What it can do

- **Player.** Play, pause, step, blink the first and last frame, change speed, zoom and
  drag. Pick the detector and the field of view (0.05, 0.1, 0.2 or 0.5 degrees).
- **Name or coordinate search.** Type a star name or a position. The tool looks up the
  object and moves its catalogue position to where it is now (Barnard's Star has moved
  about 4.5 arcminutes since the year 2000). Buttons for the five challenge targets and
  for the candidate described below.
- **Three views.** Normal (one frame per visit); Difference (each visit minus the first:
  what did not change is grey, a brighter patch is white, a fainter one black); Sum (all
  exposures added, optionally shifted to follow a moving object).
- **Gaia overlay.** Marks where the Gaia star catalogue says the object should be, and
  prints measured shift next to Gaia's predicted shift.
- **Spectrum on click.** Click a spot, or press "Spectrum of the target": brightness
  against wavelength, one dot per exposure, with a CSV download.
- **Brightness chart.** "Brightness over time": measurements grouped by wavelength so
  that only like is compared with like, with a plain verdict ("brighter", "fainter" or
  "too few bins").
- **Flags.** Shows pixels with no data and pixels too bright to measure. The page also
  states how sure a detection is (times the background scatter) and warns when the core
  is overexposed, when a neighbouring star is blended in, or when a very bright star
  nearby can leave ghost rings.
- **Sky context.** The same patch in other surveys (WISE, 2MASS, optical) from the Aladin
  sky atlas. It depends on outside servers; if they are down the panel says so and the
  rest of the page still works.
- **Blind search.** The button "Search this patch for anything that moved or changed" (the
  endpoint is `/api/search`) looks at every source in a field for anything that moves
  or changes brightness between visits, without being told what to look for, and checks
  each candidate against known artefacts and five catalogues. Results are in
  [docs/search.md](docs/search.md).
- **Practice mode.** "Practise: find a planted object" adds ONE made-up moving object to
  real frames so a visitor can learn what a mover looks like. It is a simulation: a banner
  that cannot be closed and the word SIMULATION in every picture say so, and it has its
  own endpoint, so it never reaches the real views or any measurement.

A view can be shared through the address, for example
`/?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal`.

## What it found

Each paragraph is the short version; the linked document has the numbers and the checks.
Measured 2026-11-14 on real data; independently re-measured by a second session.

- **Barnard's Star** (fastest-moving star). Three visits, August 2025 to September 2026.
  It moves north about 10 arcseconds over the year. In detector 5 the measured shift
  (10.2 north, 2.2 west) agrees with Gaia's prediction (10.3 north, 0.8 west) to within
  1.4 arcseconds, 0.23 of a SPHEREx pixel. The star overloads the detectors, so its
  position is only good to about 1 arcsecond (2 in detectors 1 to 4).
  [docs/results.md](docs/results.md), [docs/verification.md](docs/verification.md) section 4.
- **Epsilon Indi B** (a pair of brown dwarfs). Visible in all six detectors, moving
  6.3 arcseconds south-east between April 2025 and October 2026, on the catalogue's track
  (detector 5: 5.0 east, 3.8 south measured; 5.1 east, 3.7 south predicted).
  [docs/results.md](docs/results.md). Two known faults there are listed in that file.
- **WISE 0855-0714** (a very cold brown dwarf). Seen only in detectors 5 and 6 (3.8 to
  5.0 micrometres). In detector 6 the detection strength is 3.4, 14.6 and 11.2 times the
  background scatter in the three visits: marginal in visit 1 (three exposures), then
  clear. It moves 8.4 +- 0.4 arcseconds west in a year (catalogue: 8.0). By visit 3 an
  unrelated star 4 arcseconds away supplies about a quarter of the light at 4.4 to 5
  micrometres. [docs/verification.md](docs/verification.md) section 1.
- **RW Aurigae** (a young variable star). Between September 2025 and September 2026 it
  became about 1.7 times brighter at the shortest wavelengths and about half as bright at
  3.9 to 5 micrometres. Ground-based AAVSO observers record the same brightening
  (1.7 times in the I band); the fading at 3.9 to 5 micrometres has no outside check. The
  2025 exposures fell in a dip lasting a few days. It is a close pair that SPHEREx measures
  as one. [docs/verification.md](docs/verification.md) section 2.
- **R Draconis** (a bright long-period variable). It overloads the detectors in every
  exposure, so no brightness can be given. The relative brightness of the star's outer
  light in detectors 5 and 6 rises and falls by a factor of about 2 to 3 in step with the
  246-day cycle AAVSO observers record; the same measure on the non-varying Barnard's
  Star stays flat to about 5 per cent. [docs/verification.md](docs/verification.md) section 3.
- **Blind search.** Given only field centres, it found Barnard's Star, WISE 0855 and
  Epsilon Indi B moving and RW Aurigae changing, each labelled already known. In 30
  searches on the five challenge fields it reported 5 objects, all of them the targets,
  with no false alarm; it rejected one convincing 7-sigma "mover" that was a reflection of
  a bright star. Five objects in 30 searches is a small sample: the false-mover rate is
  below about 1 in 230 sources (95 per cent confidence), not zero.
  [docs/search.md](docs/search.md).
- **A candidate in Serpens South.** In four young star clusters the search flagged 17
  listed variable stars, 2 candidates that survived every test and 9 changes it could
  neither confirm nor rule out. The strongest candidate is a young star at RA 277.50547,
  Dec -2.06198 that became about five times brighter at 2.4 to 5 micrometres between
  September 2025 and March 2026. It is not listed as variable in the catalogues we
  asked (Gaia DR3, AAVSO's variable star index, SIMBAD's object type, AllWISE's flag). Checked against ten years
  of NEOWISE measurements, it is a star that swings by a factor of 7 to 9; SPHEREx watched
  it come back from the faintest state NEOWISE saw. It is a candidate, not a new kind of
  event. SPHEREx cannot tell which star of a tight group is the one changing. Chart:
  [docs/search/serpsouth_neowise_spherex.png](docs/search/serpsouth_neowise_spherex.png).
  The other candidate, HH 17 in NGC 1333, is a smaller change with moderate confidence.
  [docs/search.md](docs/search.md).

Known limits: SPHEREx pixels are 6.15 arcseconds across, so two objects closer than that
blur into one; only three or four visits exist per target; a new position takes about 15
seconds to load for the first time (about a minute if NASA's S3 copy is unavailable and the
fallback is used); very bright stars saturate. Longer lists of faults are in
[docs/results.md](docs/results.md).

## When SPHEREx releases new data

The tool keeps no copy of the survey. For every position it asks NASA's archive which
exposures cover it, and builds its pictures from those.

- **New exposures of a position reach the page by themselves.** The archive's list for a
  position is asked for again once it is a day old. A view or a brightness chart that is
  already on disk records how many exposures it was built from, and is built again when the
  list changes. Nobody waits for the archive on a view that is on disk: it is served at once
  and the list is refreshed in the background.
- **A new data release is one setting.** The archive groups its images into named
  collections (today `spherex_dr1` and `spherex_qr3`). Set `SPHEREX_COLLECTIONS` on the
  server to the new list, comma-separated, and restart. No code changes.
- After a release, `python scripts/warm_cache.py` rebuilds the demo views ahead of visitors.
- Results of the blind search are a dated snapshot and are not refreshed automatically.

## Run it locally

Needs Python 3.11 or newer and Node.js (the Docker build uses Node 22; the build here was run with Node 24).

```
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.app:app
```

Then open http://localhost:8000/. The backend serves the built app from `frontend/dist`.
For development, run `uvicorn backend.app:app --reload` and, in `frontend/`, `npm run dev`
(http://localhost:5173).

The first request for a new position reads about 60 image cutouts per detector, straight
from NASA's public copy of the archive on Amazon S3, with the archive's own cutout service
at IRSA as the automatic fallback. They are kept in `backend/cache/` (override with
`SPHEREX_CACHE_DIR`), so a repeat is instant. `scripts/warm_cache.py` prepares the views for
the five challenge targets ahead of time. Deploying is described in
[docs/deploy.md](docs/deploy.md); nothing is deployed yet.

The earlier single-file viewer is still served at `/viewer.html`
(`frontend/public/viewer.html`).

## Run the checks

```
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest                    # 192 tests, about 10 seconds, no network
ruff check .
mypy
cd frontend
npm run lint
npm run typecheck
npm test                  # 240 tests
```

The Python tests use real SPHEREx images kept in `tests/data/` and block every outgoing
request. GitHub runs these checks on every push and pull request to `Dev` and `main`.
Scripts that repeat the measurements behind the results (they need the data cache and the
network): `scripts/check_barnard.py`, `scripts/run_targets.py`, `scripts/verify_*.py`,
`scripts/search_fields.py`, `scripts/check_neowise.py`; how to run each is in the
document it supports.

## The API

All endpoints are `GET`. Positions are in degrees; `detector` is 1 to 6.

| Endpoint | What it returns |
|---|---|
| `/api/resolve?name=` | A name looked up (SIMBAD, Gaia) and moved to 2026: position, proper motion, parallax |
| `/api/frames?ra=&dec=&fov=&detector=&mode=` | One frame per visit: `mode` is `normal`, `difference` or `sum`; optional `pmra`, `pmdec`, `parallax` follow a moving object; frame images are served under `/frames/` |
| `/api/stars` | The Gaia stars in a view, placed on each frame, and a note when a very bright star is near |
| `/api/lightcurve` | Brightness of an object against time, grouped by wavelength bin |
| `/api/spectrum` | Brightness of an object against wavelength, one point per exposure |
| `/api/search?ra=&dec=&fov=&detectors=` | The blind search, run in the background one at a time: ask again every few seconds until `status` is `done` or `failed` (until then it is `queued` or `running`) |
| `/api/training` | SIMULATION: real frames with one made-up moving object, for practice. Never mixed into `/api/frames` |

## Where the documents are

| Document | What is in it |
|---|---|
| [CLAUDE.md](CLAUDE.md) | The project brief, the pipeline, and "Verified facts" on how the SPHEREx archive behaves |
| [docs/results.md](docs/results.md) | The five test targets, frame by frame, with the problems found |
| [docs/verification.md](docs/verification.md) | Independent re-measurement of WISE 0855, RW Aurigae, R Draconis and Barnard's Star; it corrects some earlier claims |
| [docs/search.md](docs/search.md) | The blind search: method, false alarms, candidates, the NEOWISE check, what it cannot find |
| [docs/deploy.md](docs/deploy.md) | How to deploy |
| [docs/project-page.md](docs/project-page.md) | Text for the Space Apps project page |
| [docs/demo-script.md](docs/demo-script.md) | Shot list for the demo video |
| [documentation/SPHEREx-viewer-explained.pdf](documentation/SPHEREx-viewer-explained.pdf) | Where the data comes from and what the app does, for teammates (made by `scripts/make_explainer_pdf.py`) |
| [plan.md](plan.md) | Who does what, and the lint and typecheck rules |

## Data credits

SPHEREx images: NASA/JPL-Caltech. Served by the NASA/IPAC Infrared Science Archive (IRSA)
and read from NASA's public S3 bucket. Star positions and motions: ESA Gaia DR3. Name
lookup: SIMBAD (CDS, Strasbourg). Brightness checks: NEOWISE (NASA/IPAC IRSA) and AAVSO
observers. Sky context: Aladin Lite (CDS). Inspired by WiseView and the Backyard Worlds:
Planet 9 project.

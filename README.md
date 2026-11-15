# SPHEREx sky-change viewer

Team Ampersand's entry for NASA Space Apps 2026, "Planet X and SPHEREx".

NASA's SPHEREx telescope photographs the whole sky in infrared light about every six months. This web tool shows
its real pictures of any patch, one visit after another like a short film, and searches them for what moved or
changed, in plain words (Beginner) or a scientist's (Expert). Our first sweep of the Milky Way's plane found two
known novae by itself and three sources that we found in no catalogue or report we checked: candidates, which
nobody has confirmed. All data shown are real (SPHEREx, and the catalogues and older surveys it is compared with),
except the clearly marked made-up object of the practice round, which the Planet X search can also plant, marked
as a simulation; the drawings in What is it? say that they are drawings.

Words used: a **visit** is one pass of SPHEREx over a patch of sky (its photos are added up into one picture). A
**detector** is one of the six infrared cameras, together covering 0.75 to 5.0 micrometres.

## What is in the app

A bar across the top of every screen lists every feature, in this order (Beginner name, then Expert name). The
**Beginner | Expert** switch is at the bottom right.

| # | Beginner | Expert | What it is | Address |
|---|---|---|---|---|
| 1 | Watch | Viewer | The pictures of the patch, one per visit, played like a short film, with a side column (one sentence about the whole run, one table of all visits) that holds still while they play. A row of buttons opens Candidates A, B and C, the five challenge targets and three more objects; the search box takes a name or a position. Expert adds the detector, field of view, Normal / Difference / Sum, markers, flags and two folds, Catalogue notes and Visit details. | `/` |
| 2 | Brightness | Light curve | Brightness at each visit, compared only within one colour of infrared light | `tool=brightness` |
| 3 | Colours | Spectrum | Brightness in each colour, one dot per photo, with a CSV download | `tool=spectrum` |
| 4 | Find changes | Blind search | A search of the patch for anything that moved or changed, checked against artefacts and five catalogues | `tool=search` |
| 5 | Far-off planet | Planet X search | The search for a distant world by its jump between visits; Expert can try it on a planted object, marked as a simulation | `tool=distant` |
| 6 | Asteroids | Small bodies | Known asteroids and comets that JPL predicts in the patch | `tool=smallbodies` |
| 7 | What is it? | Object card | What Gaia DR3 and SIMBAD know about the object, a drawing made from their numbers ("Illustration drawn from measurements. Not a photograph."), and the patch in older surveys | `tool=context` |
| 8 | Practise | Training | SIMULATION: real pictures with one made-up moving object, to practise on | `?train=<seed>` |
| 9 | Observe anomalies | Anomalies | What the searches found, for people to look at and vote on: first the three candidates ("Not reported anywhere we could find"), then "Choose a region" (everywhere, the Milky Way's plane, or one searched patch), then the chosen region's groups: the patch searches' "Not listed as changing", "Already known" and "Set aside as false alarms" (Expert: "Needs eyes", "Already known", "Set aside as artefacts"), with votes, and the sweep's 14 survivors in four groups | `?watchlist=1` (`&region=` keeps the choice) |
| 10 | Three tools | Methods | "Three tools, three known worlds": three planet-finding methods, each tested on a known world | `?tools=1` |

The page opens on Candidate B. A view is shared through its address, for example
`/?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal`; `ui=expert` or `ui=beginner` sets the level and
`tool=<key>` opens a tool under the picture.

## Where the results are written up

| Result | Write-up |
|---|---|
| The sweep of the Milky Way's plane, the three candidates and their vetting | [docs/sweep.md](docs/sweep.md), evidence in [docs/sweep/vetting/](docs/sweep/vetting/) |
| Every search for an earlier report of the candidates, and the checklist for a person | [docs/sweep/searches-for-earlier-reports.md](docs/sweep/searches-for-earlier-reports.md) |
| Draft reports for the candidates (NOT sent) | [docs/sweep/report-draft.md](docs/sweep/report-draft.md) |
| The five challenge targets, frame by frame | [docs/results.md](docs/results.md) |
| The independent re-measurement of WISE 0855, RW Aurigae, R Draconis and Barnard's Star | [docs/verification.md](docs/verification.md) |
| The blind search (Find changes) and its two hunts in young-star fields | [docs/search.md](docs/search.md) |
| The watchlist and its NEOWISE second opinion | [docs/watchlist.md](docs/watchlist.md) |
| The distant-world (Planet X) search | [docs/distant.md](docs/distant.md) |
| Follow the bend: Eris found in one visit (a known-answer test) | [docs/reflex.md](docs/reflex.md) |
| Line up the dips: the transit of WASP-62 b (a re-measurement, not a blind test) | [docs/transits.md](docs/transits.md) |
| Off-centre in red: the colour walk (not proven) | [docs/colourwalk.md](docs/colourwalk.md) |
| Four novae of 2025 | [docs/novae.md](docs/novae.md) |
| Known asteroids and comets in a patch | [docs/smallbodies.md](docs/smallbodies.md) |
| Following a comet or asteroid and its spectrum | [docs/comets.md](docs/comets.md) |
| The colour of a change | [docs/colour-of-change.md](docs/colour-of-change.md) |
| Text for the project page, and the demo video's shot list | [docs/project-page.md](docs/project-page.md), [docs/demo-script.md](docs/demo-script.md) |
| How to deploy, and the warm-up after deploying | [docs/deploy.md](docs/deploy.md); on Render: [docs/deploy-render.md](docs/deploy-render.md) |
| The project brief and the verified facts about the SPHEREx archive | [CLAUDE.md](CLAUDE.md) |
| Who does what, and the lint and typecheck rules | [plan.md](plan.md) |

## Run it locally

Needs Python 3.11 or newer and Node.js (the Docker build uses Node 22).

```
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.app:app
```

Then open http://localhost:8000/. The backend serves the built app from `frontend/dist`. For development, run
`uvicorn backend.app:app --reload` and, in `frontend/`, `npm run dev` (http://localhost:5173).

The first request for a new position reads about 60 image cutouts per detector from NASA's public copy of the
archive on Amazon S3, with IRSA's cutout service as the automatic fallback. They are kept in `backend/cache/`
(`SPHEREX_CACHE_DIR` moves it), so a repeat is instant. Deploying, and the warm-up that prepares every view the
page opens or links to, are in [docs/deploy.md](docs/deploy.md); the short path for Render is
[docs/deploy-render.md](docs/deploy-render.md).

## Run the checks

```
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest                    # no network; uses real SPHEREx images kept in tests/data/
ruff check .
mypy
cd frontend
npm run lint
npm run typecheck
npm test
```

The browser checks that guard the page (the words hold still while the pictures play; the bar and the switch
work at both levels) are in [scripts/checks/](scripts/checks/README.md) and run against a running server.
GitHub runs the tests above on every push and pull request to `Dev` and `main`. Scripts that repeat the
measurements behind each result are named in its write-up.

## When SPHEREx releases new data

The tool keeps no copy of the survey. For every position it asks NASA's archive which exposures cover it, and
builds its pictures from those.

- **New exposures of a position reach the page by themselves.** The archive's list for a position is asked for
  again once it is a day old. A view or a brightness chart on disk records how many exposures it was built from,
  and is built again when the list changes. Nobody waits for the archive: the view on disk is served at once and
  the list is refreshed in the background.
- **A new data release is one setting.** The archive groups its images into named collections (today
  `spherex_dr1` and `spherex_qr3`). Set `SPHEREX_COLLECTIONS` on the server to the new list, comma-separated,
  and restart. No code changes.
- After a release, run the warm-up again (`docs/deploy.md`) so that visitors do not wait.
- **Dated snapshots, not refreshed by themselves:** the blind searches and the watchlist, the sweep of the Milky
  Way's plane and its three candidates (their numbers are the reviewers', from the visits of 2025 and 2026), and
  the three methods' files in `frontend/public/lab/` (made by `scripts/export_lab.py`). A new visit of the
  candidates' places, expected about February to April 2027, will show in their views once the archive lists it
  in a collection the server asks for; their write-up will not change by itself.

## The API

All endpoints are `GET` unless marked. Positions are in degrees; `detector` is 1 to 6.

| Endpoint | What it returns |
|---|---|
| `/api/resolve?name=` | A name looked up (SIMBAD, Gaia) and moved to 2026: position, proper motion, parallax |
| `/api/identify?ra=&dec=` | What Gaia DR3 and SIMBAD know about the object at a place, for What is it? |
| `/api/frames?ra=&dec=&fov=&detector=&mode=` | One frame per visit (`normal`, `difference` or `sum`); optional `pmra`, `pmdec`, `parallax` follow a moving object; images under `/frames/` |
| `/api/stars` | The Gaia stars in a view, placed on each frame |
| `/api/lightcurve`, `/api/spectrum` | Brightness against time (grouped by wavelength) and against wavelength |
| `/api/search?ra=&dec=&fov=&detectors=` | The blind search, run in the background: ask again until `status` is `done` or `failed` |
| `/api/distant?ra=&dec=&fov=&detectors=` | The distant-world search, run the same way; with `plant=` it is a SIMULATION |
| `/api/smallbodies` | Known asteroids and comets predicted in a view |
| `/api/training` | SIMULATION: real frames with one made-up moving object. Never mixed into `/api/frames` |
| `/api/watchlist`, `/api/watchlist/{id}`, `/api/watchlist/{id}/picture.png`, `POST /api/watchlist/{id}/vote`, `/api/watchlist/export.csv`, `/api/watchlist/export.json` | The shared list of what the searches found, its pictures, votes, and the whole list for scientists |

## Data credits

SPHEREx images: NASA/JPL-Caltech, served by the NASA/IPAC Infrared Science Archive (IRSA) and read from NASA's
public S3 bucket. Star positions and motions: ESA Gaia DR3. Names: SIMBAD (CDS, Strasbourg). Catalogues:
AAVSO VSX, CatWISE2020, AllWISE, 2MASS, Spitzer GLIMPSE (IRSA). Brightness checks: NEOWISE (IRSA) and AAVSO
observers. Asteroids, comets and Eris: NASA/JPL Solar System Dynamics. Older surveys: Aladin Lite (CDS).
Inspired by WiseView and the Backyard Worlds: Planet 9 project.

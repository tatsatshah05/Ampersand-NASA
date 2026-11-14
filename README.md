# SPHEREx sky-change viewer

Team Ampersand's entry for NASA Space Apps 2026, "Planet X and SPHEREx".

Type a star name or sky coordinates and see SPHEREx images of that patch of sky played
one after another like a short video, so anything that moved or changed brightness
stands out.

**Status:** the backend builds frames from real SPHEREx data, and the React app in
`frontend/` plays them with a Gaia overlay (see "Open the viewer" below). The search box
and the brightness chart are not built yet. See [plan.md](plan.md) for who is doing what and the team's lint and typecheck
rules, and the [issues](https://github.com/tatsatshah05/Ampersand-NASA/issues) for the
work itself.

## Run the backend

Needs Python 3.11 or newer. The newest code is on the `Dev` branch: `git checkout Dev`.

```
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload
```

Then open
http://localhost:8000/api/frames?ra=269.446267&dec=4.768222&fov=0.1&detector=5

That is Barnard's Star, the fastest-moving star in the sky. You should get three
frames, one per SPHEREx visit. Each frame's `image` is a PNG path on the same server,
for example `http://localhost:8000/frames/<key>/epoch1.png`.

The very first start of the server can take 20 seconds or so. The first request for a
new position reads about 60 image cutouts and takes about 15 seconds. They come straight
from NASA's public copy of the archive on Amazon S3, with the archive's own cutout
service (about a minute, less reliable) as the automatic fallback. After that it is served from `backend/cache/`
instantly.

## Open the viewer

The frontend is the React app in `frontend/` (Vite + TypeScript). With the backend
running on port 8000:

```
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. It shows Barnard's Star by default, with play/pause, a
frame slider, the Gaia overlay (where Gaia predicts the star against where it was
measured) and the details of the frame on screen. A view can be shared through the
address: `?ra=269.446267&dec=4.768222&fov=0.1&detector=5`.

To have the backend serve the app itself at http://localhost:8000/, build it once with
`npm run build`. `backend/app.py` serves `frontend/dist` whenever that folder exists.

### The earlier single-file viewer

The first viewer is kept next to the app, at `/viewer.html` (the file is
`frontend/public/viewer.html`). It has what the app does not have yet: zoom and pan,
blink, a trail of the measured positions, three views (normal, difference and sum) and
the spectrum of the target (click the star, or press "Spectrum of the target").

Its options go in the address too:
`/viewer.html?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal`. For an object whose
motion is known, add the `pmra`, `pmdec` and `parallax` that `/api/resolve?name=...`
returns, so the backend follows that object. Example, the cold brown dwarf WISE 0855 in
detector 6:
`/viewer.html?ra=133.759765&dec=-7.242182&det=6&pmra=-8123.7&pmdec=673.2&parallax=439`

It is one plain file with no build step, so it can also be opened straight from disk.
It then looks for the backend at `http://localhost:8000`, or at
`&api=http://that-address`. Like the app, it shows only what the backend returns.

## Check the pipeline

```
python scripts/check_barnard.py
```

Builds the Barnard's Star frames, compares the star's measured shift with the Gaia
catalogue, checks that the other stars stay still, and writes a picture to look at in
`scripts/out/`.

## Run the tests

```
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest
```

About 150 tests in about 5 seconds. They need no network and never touch
`backend/cache`: they use nine real Barnard's Star images kept in `tests/data/` and
block every outgoing request. GitHub runs them, with the lint and typecheck below, on
every push and pull request to `Dev` and `main`. "1 xfailed" is a known bug, not a new
failure.

## Before you push

```
pip install -r backend/requirements-dev.txt
ruff check .
mypy
```

and, if you changed anything in `frontend/`:

```
cd frontend
npm run lint
npm run typecheck
```

All of them must pass. Details are in [plan.md](plan.md).

## More

- [CLAUDE.md](CLAUDE.md): the full project brief, the pipeline steps, and a "Verified
  facts" section on how the SPHEREx archive really behaves.

## Data credits

SPHEREx images: NASA/JPL-Caltech. Served by the NASA/IPAC Infrared Science Archive
(IRSA). Star positions and motions: ESA Gaia DR3.

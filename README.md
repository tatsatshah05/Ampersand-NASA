# SPHEREx sky-change viewer

Team Ampersand's entry for NASA Space Apps 2026, "Planet X and SPHEREx".

Type a star name or sky coordinates and see SPHEREx images of that patch of sky played
one after another like a short video, so anything that moved or changed brightness
stands out.

**Status:** the backend builds frames from real SPHEREx data, and a first page plays
them (see "Open the viewer" below). Search, charts and overlays are not built yet. See [plan.md](plan.md) for who is doing what and the team's lint and typecheck
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
new position downloads about 60 image cutouts from NASA's archive and takes around a
minute. After that it is served from `backend/cache/`
instantly.

## Open the viewer

With the backend running, open http://localhost:8000/. It shows Barnard's Star by
default, with play/pause, blink, a trail of the measured positions, zoom and pan, and
three views: normal, difference (what changed since the first visit) and sum (every
visit added into one deeper image).

Options go in the address, so a view can be shared:
`?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal`. For an object whose motion is
known, add the `pmra`, `pmdec` and `parallax` that `/api/resolve?name=...` returns, so
the backend follows that object. Example, the cold brown dwarf WISE 0855 in detector 6:
`?ra=133.759765&dec=-7.242182&det=6&pmra=-8123.7&pmdec=673.2&parallax=439`

The page file can also be opened straight from disk (`frontend/index.html`); it then
looks for the backend at `http://localhost:8000`, or at `&api=http://that-address`.

The page is one plain file with no build step. It shows only what the backend returns.

## Check the pipeline

```
python scripts/check_barnard.py
```

Builds the Barnard's Star frames, compares the star's measured shift with the Gaia
catalogue, checks that the other stars stay still, and writes a picture to look at in
`scripts/out/`.

## Before you push

```
pip install -r backend/requirements-dev.txt
ruff check .
mypy
```

Both must pass. Details are in [plan.md](plan.md).

## More

- [CLAUDE.md](CLAUDE.md): the full project brief, the pipeline steps, and a "Verified
  facts" section on how the SPHEREx archive really behaves.

## Data credits

SPHEREx images: NASA/JPL-Caltech. Served by the NASA/IPAC Infrared Science Archive
(IRSA). Star positions and motions: ESA Gaia DR3.

# SPHEREx sky-change viewer

Team Ampersand's entry for NASA Space Apps 2026, "Planet X and SPHEREx".

Type a star name or sky coordinates and see SPHEREx images of that patch of sky played
one after another like a short video, so anything that moved or changed brightness
stands out.

**Status:** the backend builds frames from real SPHEREx data. The frontend is not built
yet. See [plan.md](plan.md) for who is doing what and the team's lint and typecheck
rules, and the [issues](https://github.com/tatsatshah05/Ampersand-NASA/issues) for the
work itself.

## Run the backend

Needs Python 3.11 or newer.

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

The first request for a new position downloads about 60 image cutouts from NASA's
archive and takes around a minute. After that it is served from `backend/cache/`
instantly.

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

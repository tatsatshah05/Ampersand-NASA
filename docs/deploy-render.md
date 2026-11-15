# Deploying on Render

The general notes on hosting are in `docs/deploy.md`. This page is the short path for
Render (render.com), chosen by the team on 2026-11-15.

## What is in the repository for it

- `render.yaml`: a Render blueprint. One web service, built from the `Dockerfile`, on the
  free plan, in Oregon (next to NASA's public copy of the archive on Amazon), health check
  `/openapi.json`, redeployed on every push to the branch it was made from.
- The `Dockerfile` downloads the **pre-built demo results** and unpacks them into the cache
  folder while the image is built (`scripts/seed_cache.py fetch`). They are a release file
  of this repository, `demo-cache-1` (81 MB packed; about 240 MB and 8,260 files unpacked):
  the finished views of the eleven buttons in every detector and mode, their brightness
  tables, the answers of their tools that were on the laptop's disk, and the list behind
  Observe anomalies with its pictures and no votes. Results only, no cutouts.

Why they are needed: the free plan has a tenth of a processor and no disk. Without them
the first visitor would wait minutes while the opening view was built from the archive,
and again after every restart.

## Steps (in a browser, about five minutes of clicking, then the build)

1. Sign in at https://dashboard.render.com with the GitHub account that owns the repository.
2. **New**, then **Blueprint**. Choose the repository `Ampersand-NASA` and the branch
   `main`, and press **Apply** (Render reads `render.yaml`). The same thing in one link:
   https://render.com/deploy?repo=https://github.com/tatsatshah05/Ampersand-NASA
3. Wait for the first build. It installs the Python libraries, builds the frontend and
   downloads the demo results.
4. The address is at the top of the service's page: `https://spherex-sky-change-viewer.onrender.com`,
   or the same with a few letters added if that name is taken.
5. Open it and check: the page opens on Candidate B, blinking; the buttons Candidate A and
   Candidate C, and the five targets; `/?tools=1`; `/?watchlist=1`; What is it? on Barnard's Star.
6. Put the address in `docs/project-page.md` (it is marked there) and in the submission.

## What the free plan means

- **It sleeps.** After 15 minutes without a visitor the service stops, and the next visitor
  waits about a minute while it starts (our server alone needs 37 seconds on a tenth of a
  processor). For the days of judging, change **Instance type**
  to Starter in the service's Settings (always on; it needs a card; we believe about US$7
  a month, charged for the time used: check Render's price list) and change it back
  afterwards.
- **512 MB of memory and a tenth of a processor.** The pre-built views open at once. A
  position nobody has asked for is fetched from NASA's archive and built on that small
  processor: expect minutes where a laptop takes 15 seconds. A new search of a patch
  (Find changes, Far-off planet) may be slower still or run out of memory: not tried.
- **No disk.** Everything fetched after the build, and every vote, is lost when the
  service restarts or is deployed again. The pre-built results come back with every build.

## Tested, and not tested

Tested on a laptop on 2026-11-15:

- `scripts/seed_cache.py` pack, fetch and copy: 8,260 files out, 142 rows in the list, no
  votes. The release file downloads.
- With only the unpacked results as its cache and the network blocked,
  `scripts/warm_cache.py --check` loaded from disk at once all 74 requests for Barnard's
  Star (its 60 views and 14 brightness and spectrum requests) and the first 17 for
  Epsilon Indi B. The run was stopped at the next one, which is not kept on disk (Epsilon
  Indi B, detector 1, Sum following the target with no motion given: it is built from
  cutouts each time, so a deployed copy fetches them from the archive).
- The image built with Docker (1.08 GB, the demo results downloaded from the release
  during the build). Run with the free plan's limits (`--memory=512m --cpus=0.1`, `PORT`
  set as Render sets it), the server was ready 37 seconds after the container started,
  used about 130 MB, and answered the opening view (Candidate B) in 0.4 seconds from the
  pre-built results.

Not tested: Render itself. Nobody on the team had deployed there when this was written.

## Refreshing the pre-built demo results

After a change to the pipeline's version, a new button, or new searches worth keeping, on
the laptop that holds the warm cache:

```
python scripts/warm_cache.py
python scripts/warm_cache.py --check
python scripts/seed_cache.py pack /tmp/spherex-demo-cache.tar.gz
gh release create demo-cache-2 /tmp/spherex-demo-cache.tar.gz --prerelease \
  --title "Pre-built demo views (for deployment)" --notes "Results only; see docs/deploy-render.md"
```

Then put the new release's name in `SEED_URL` in the `Dockerfile` and push: Render builds
again by itself. What goes in is the list `PARTS` in `scripts/seed_cache.py`; the vote list
is emptied in the packed copy.

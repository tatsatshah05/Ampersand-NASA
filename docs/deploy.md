# Deploying the viewer

Status on 2026-11-14: **nothing is deployed.** No hosting account has been created and
nothing has been paid for; choosing a host and paying for it is the team's decision.
This page is what a teammate needs to do it in a few minutes once that is decided.

Everything under "Tested" was run on a laptop with Docker. Everything about a hosting
service is written from that service's documentation and has **not** been tried.

## What gets deployed

One container, built from the `Dockerfile` in the repo root. Building it also builds
the frontend (`npm ci` and `npm run build` in `frontend/`), so nothing has to be built
by hand first. The container runs `uvicorn backend.app:app`, which serves everything
on one address:

| Address | What |
|---|---|
| `/` | the web app (the build output of `frontend/`) |
| `/viewer.html` | the earlier single-page viewer |
| `/api/...` | the API: `resolve`, `frames`, `lightcurve`, `spectrum` |
| `/frames/...` | the frame images the API names |

What the host must provide:

| Need | Why |
|---|---|
| A persistent disk of a few GB | Everything fetched from NASA's archive is kept on it. Without it every restart starts from nothing. Size: see "Disk". |
| `SPHEREX_CACHE_DIR` set to a folder on that disk | This tells the backend where to keep its cache. Without it the cache goes to `/app/backend/cache` inside the container and is lost on redeploy (unless the disk is mounted exactly there, which also works). |
| No short request timeout (allow 5 minutes) | The first request for a new sky position downloads about 60 cutouts and takes about a minute, longer when the archive is having a bad spell. |
| An always-on instance, exactly one | A host that puts the service to sleep adds a start-up wait, and the disk can only be attached to one instance. |
| Outbound HTTPS | To `irsa.ipac.caltech.edu` (images), `gea.esac.esa.int` (Gaia) and `simbad.harvard.edu` / `simbad.cds.unistra.fr` (name lookup). |
| 1 GB of memory or more | Measured: the warm-up process peaked at 390 to 420 MB while building every demo view, on top of the server's own 115 to 150 MB. On 512 MB, warm one target at a time (see "Warm the cache"). |

There is no database, no login, no secret. The only setting is `SPHEREX_CACHE_DIR`.
The container listens on `$PORT` if the host sets it, otherwise on 8000.

Plain serverless functions (Vercel, Netlify, AWS Lambda and the like) do not fit: no
disk, and request limits shorter than a first load.

## Tested, and not tested

Tested on a laptop (Docker 29 on Colima, Apple silicon, 2026-11-14), image built from
the repo at commit `67557b5`:

- `docker build` succeeded. It took 46 seconds, which included installing the Python
  libraries and building the frontend, but not `npm ci` (that layer was already on
  this machine from an earlier build). The image is 742 MB.
- `/` returned the built app's page (HTTP 200) and the script and stylesheet it names
  were served. `/viewer.html` returned the single-page viewer, byte for byte the file
  in the repo (`frontend/public/viewer.html`).
- With a volume mounted at `/data` and `SPHEREX_CACHE_DIR=/data`: the cache folders
  appeared on the volume and nothing was written to `/app/backend/cache`. A first
  request for Barnard's Star
  (`/api/frames?ra=269.446267&dec=4.768222&fov=0.1&detector=5`) took 43 seconds and
  returned three frames with no failed downloads; 62 cutouts were on the volume
  afterwards. The same request took 37 milliseconds after `docker restart`, and 33
  milliseconds from a brand-new container attached to the same volume. The frame
  image it names was served.
- With a volume mounted at `/app/backend/cache` instead and no variable set, a cache
  made earlier was found there and the same request answered in 2 milliseconds.
- The same image run against the laptop's warmed cache, mounted read-only
  (`-v "$PWD/backend/cache":/data:ro -e SPHEREX_CACHE_DIR=/data`), served every view
  that was asked for from that cache; so a cache warmed elsewhere can be copied onto
  the server's disk instead of warming it there.
- Earlier the same day, on an image without the frontend build (backend at `89acb9d`):
  `/api/resolve`, `/api/frames` in normal and difference mode, `/api/lightcurve` and
  `/api/spectrum` all answered 200 for Barnard's Star and an unknown mode answered 400;
  `python scripts/warm_cache.py --only barnard` inside the container built all 74
  Barnard's Star views in 2.9 minutes with no problems, and `--check` then passed.

Not tested:

- **Using the pages.** Both pages were loaded from the container in headless Chrome
  and screenshotted for the five targets, and both drew their frames (see
  `docs/results.md`, "The two pages"). Nobody clicked anything, and no phone was tried.
- **Any hosting service.** The Render and Fly.io steps below come from their
  documentation (read 2026-11-14).
- **An x86 build.** Hosts build for x86-64. The Python and Node dependencies all
  publish x86-64 packages, but the build was only run on Apple silicon.
- **A build from nothing**, with no layer cached: how long it takes was not measured.
- **A full five-target warm-up inside a container.** Barnard's Star was run there;
  the full warm-up was run outside Docker.
- **A full disk** (see "Disk").

## Run it with Docker anywhere (the tested path)

On any machine with Docker: a laptop, or a small cloud server.

```
git clone https://github.com/tatsatshah05/Ampersand-NASA.git
cd Ampersand-NASA
git checkout Dev
docker build -t spherex-viewer .
docker run -d --name spherex-viewer --restart unless-stopped \
    -p 8000:8000 \
    -v spherex-cache:/data -e SPHEREX_CACHE_DIR=/data \
    spherex-viewer
```

Check it worked:

1. `http://<address>:8000/` shows the app. `http://<address>:8000/viewer.html` shows
   the single-page viewer, which asks for Barnard's Star by default: about a minute
   the first time, instant afterwards.
2. `docker exec spherex-viewer ls /data` lists `cutouts`, `frames`, `queries`.
3. `docker restart spherex-viewer`, then load the same page again: it must be instant.

Then warm the cache (next section):

```
docker exec spherex-viewer python scripts/warm_cache.py
docker exec spherex-viewer python scripts/warm_cache.py --check
```

To update after new commits: `git pull`, `docker build` again, `docker rm -f
spherex-viewer`, then the same `docker run`. The volume `spherex-cache` survives.

Without Docker, for development: `cd frontend && npm ci && npm run build`, then from
the repo root `uvicorn backend.app:app`. Set `SPHEREX_CACHE_DIR` to share one cache
between checkouts; otherwise it is `backend/cache`.

## Warm the cache

`scripts/warm_cache.py` requests every view of the five test targets so that nothing
is downloaded in front of the judges: six detectors, the default field of view (0.1
degrees), normal, difference and sum modes with their options, and the brightness
measurements behind the chart and the spectrum. Each is requested twice, with and
without the target's motion values, because the backend caches the two separately.
It is safe to run again: finished views are skipped, and a view whose download failed
is retried (the backend does not keep incomplete results).

Measured on a laptop on 2026-11-14:

- Downloading: 1,973 cutouts for the five targets. The four targets that were not
  already cached took 17.6 minutes; expect 20 to 30 minutes from nothing. Not one
  cutout failed in any run, although the archive answers many requests with an error
  first (the backend retries).
- Building the 364 views once the cutouts are there: 14.8 minutes. A small shared
  server will be slower; how much was not measured.
- `--check` blocks the network inside the script and loads all 364 views again. It
  passed in 16 seconds, slowest view under 0.01 seconds, and prints
  `RESULT: every view loaded from disk in under a second, network blocked`.
  It exits with an error if any view is missing or slow.

Things to know:

- **Only the 0.1 degree field of view is warmed.** Another size needs different
  cutouts and downloads for about a minute per detector. To warm one more size for one
  target: `python scripts/warm_cache.py --only barnard --fov 0.2`.
- On a 512 MB instance, warm one target at a time:
  `python scripts/warm_cache.py --only barnard`, then `eps_indi_b`, `wise0855`,
  `rw_aur`, `r_dra`. One target peaked at 250 MB in the container.
- Run it again after a backend update. Cached results carry a code version, so results
  from older code are never served, but they are not rebuilt until asked for. A
  re-run takes about 15 minutes on a laptop because the cutouts are kept.
- If the summary lists `PROBLEMS`, read them: each line names the view and the reason.
  Run the script again; if the archive is having a bad hour, wait and retry.
- `--check` proves the backend needs no network for those views. It calls the backend
  directly, not through the web server, so also open each target once in the browser.

## Recommended host: Render

Why this one, out of the hosts that can run a Docker container:

- A paid web service can have a **persistent disk** at a path you choose; that is the
  one thing this app cannot do without.
- It builds straight from the GitHub repo using the repo's `Dockerfile`, and
  everything is done in a browser. No command-line tool to install.
- It gives a public `https://<name>.onrender.com` address that works on a phone.
- Paid services have a shell in the dashboard, which is where the warm-up is run.

What it costs: a disk requires a **paid** instance. Render's free web services cannot
attach a disk, lose their files on every restart and are put to sleep after 15 minutes
without traffic (their documentation, read 2026-11-14), so the free tier does not
fit. Their price list could not be read by the tool used to write this page. From
memory, and **not checked**: about 7 US dollars a month for the smallest paid instance
(512 MB of memory), about 25 for the next one (2 GB), and about 0.25 dollars per GB a
month for the disk. Look at https://render.com/pricing before deciding. The service
can be deleted after judging.

Steps:

1. Make sure GitHub has what you want live: `git status -sb` must not say "ahead".
   Render builds from GitHub, not from your laptop.
2. On https://dashboard.render.com choose **New**, then **Web Service**, and connect
   the repository `tatsatshah05/Ampersand-NASA`.
3. Settings:
   - Branch: `Dev`
   - Language: `Docker` (it finds the `Dockerfile` in the repo root)
   - Instance type: a paid one. 2 GB if the budget allows; 512 MB works only if you
     warm one target at a time.
   - Health check path: `/openapi.json`
   - Under **Advanced**, **Add Disk**: mount path `/var/data`, size 2 GB or more (see
     "Disk"; it can be made larger later but never smaller).
   - Environment variable: `SPHEREX_CACHE_DIR` = `/var/data`
   - Nothing else. Render sets `PORT` itself and the container obeys it.
4. Create the service and wait for the first build (several minutes: it installs the
   scientific Python libraries and builds the frontend).
5. Open `https://<name>.onrender.com/viewer.html`. It asks for Barnard's Star; expect
   about a minute the first time. Then open `https://<name>.onrender.com/`.
6. Warm the cache: open the service's **Shell** tab and run
   `python scripts/warm_cache.py`, then `python scripts/warm_cache.py --check`.
   The shell shares the instance's memory with the running server.
7. Check it worked:
   - `--check` printed `RESULT: every view loaded from disk in under a second`.
   - In the shell, `ls /var/data` lists `cutouts`, `frames`, `photometry`, `queries`.
   - From a phone, the site opens Barnard's Star at once.
   - A position nobody has asked for works after about a minute. Look at the
     service's log for errors afterwards.

Things to know:

- With a disk attached, every redeploy has a short gap, because the old instance is
  stopped before the new one starts. Do not redeploy during judging. Turn off
  automatic deploys once the site is ready, or a push to `Dev` will redeploy it.
- The disk is not available while the image is being built. That is fine: the image
  does not need it.
- Not checked: whether Render limits how long one request may take. The documentation
  pages read for this guide state no limit. A first load of a new position takes about
  a minute.
- Not checked: that the dashboard shell works with this image. Render's documentation
  says shells are for paid services and do not work with minimal ("distroless")
  images; this image is a full Debian-based one.

## Alternative: Fly.io

Similar in capability and usually cheaper for one small machine, but it needs the
`fly` command-line tool and a payment card. Its pricing page on 2026-11-14 listed a
shared machine with 1 GB of memory at 6.70 US dollars a month, volumes at 0.15 dollars
per GB a month, and no free allowance for new accounts.

Read from the same page a second time on 2026-11-14: that is about 7.45 dollars a month
for a 1 GB machine with a 5 GB volume, billed by the second, so a few days around the
judging costs well under two dollars. A new account gets a trial with 1 dollar of
credit for 7 days and no card; after that a card is required. A monthly bill under 5
dollars is waived. This is the only host whose full price could be confirmed from its
own page today, which makes it the safer choice on cost; Render's steps above are still
the simpler ones to follow.

Not an option: Hugging Face Spaces. Its documentation on 2026-11-14 says Docker Spaces
need a paid plan (9 dollars a month) and the free hardware sleeps when idle, with a
disk that is lost on restart.

One thing to check before relying on it: Fly's proxy may cut a request that stays
silent for a long time, and a first load here sends nothing for about a minute. This
was not tested. Warming the cache avoids it for the five demo targets, but a judge's
brand-new position could be affected.

1. Install the tool and sign in: https://fly.io/docs/flyctl/install/ then `fly auth login`.
2. In the repo root create `fly.toml` (pick your own app name and nearest region):

   ```toml
   app = "ampersand-spherex"
   primary_region = "sea"

   [env]
     SPHEREX_CACHE_DIR = "/data"

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = "off"
     auto_start_machines = true
     min_machines_running = 1

   [mounts]
     source = "spherex_cache"
     destination = "/data"
     initial_size = "3gb"

   [[vm]]
     cpu_kind = "shared"
     cpus = 1
     memory = "1gb"
   ```

3. `fly launch --copy-config --no-deploy` (answer no to databases), then `fly deploy`.
   Fly builds from the folder on your laptop, so what is deployed is what you have
   checked out.
4. `fly ssh console -C "python scripts/warm_cache.py"`, then the same with `--check`.
5. `fly scale count 1` if it created two machines: the volume belongs to one.

## Disk

Measured on 2026-11-14 after warming the five targets (six detectors, field of view
0.1 degrees):

| Target | Exposures (all detectors) | Cutouts on disk |
|---|---|---|
| Barnard's Star | 364 | 95 MB |
| Epsilon Indi B | 467 | 121 MB |
| WISE 0855-0714 | 258 | 68 MB |
| RW Aurigae | 336 | 88 MB |
| R Draconis | 548 | 140 MB |
| **Five targets** | **1,973** | **511 MB** |

Built frames (13 MB), brightness measurements (11 MB) and catalogue answers (1 MB)
bring the demo set to about 540 MB.

Every new position a visitor tries adds about 260 kB per exposure at the default field
of view: roughly 10 to 25 MB for each detector they look at, 70 to 140 MB for all six.
A wider field of view costs more: one detector of Epsilon Indi B at 0.3 degrees took
about 140 MB. Nothing is ever deleted automatically. So:

- **2 GB** holds the demo set and about ten more positions looked at in every detector.
- **5 GB** is comfortable for a judging period.
- If the disk fills up, new positions should fail while cached ones keep working. That
  follows from how the cache is written; a full disk was not tested. To make room,
  delete folders under `cutouts/` on the disk other than the five demo targets'.

## After deploying: the acceptance test from issue #15

- The public link opens Barnard's Star instantly from a phone.
- A position that has never been requested works after a wait of about a minute.

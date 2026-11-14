# Team plan: SPHEREx sky-change viewer

NASA Space Apps 2026, "Planet X and SPHEREx" challenge. Team Ampersand: Anu, Yatri,
Swara, Tatsat (scrum master).

**Submission closes Sunday 15 November, at night (Edmonton time).**

## What we are building

A web app. A visitor types a star name or sky coordinates and sees SPHEREx images of
that patch of sky played one after another like a short video, so anything that moved
or changed brightness stands out.

- **Backend:** a Python (FastAPI) service that fetches SPHEREx images from NASA's
  archive, stacks them into one frame per visit, and measures how far the target moved.
- **Frontend:** a single page (Vite + React + TypeScript) that plays the frames and
  draws the overlays and charts.

Judges are NASA experts. They will test the five targets named in the challenge and
will likely compare us with WiseView, the existing tool that does this for WISE data.

## Where we are (Saturday 14 November)

Working today, on real data:

- `GET /api/frames` returns three stacked frames for Barnard's Star, one per SPHEREx
  visit (August 2025, March 2026, August 2026).
- The star's measured shift matches the Gaia catalogue to within a quarter of a
  SPHEREx pixel, and the other stars in the field stay still.

Not built yet: the frontend, name search, difference and sum modes, the brightness
chart, the spectrum, deployment.

## Who owns what

Issues are in https://github.com/tatsatshah05/Ampersand-NASA/issues. Each issue says what
to build and how to tell it is done.

| Person | Area | Issues |
|---|---|---|
| Tatsat | Backend, scrum, final submission | #1, #2, #3, #4, #17 |
| Anu | Frontend player, search, selectors | #5, #6, #7, #8 |
| Swara | Charts, Gaia overlay, spectrum, details panel | #9, #10, #11, #12 |
| Yatri | Testing the five targets, cache warm-up, deploy, demo | #13, #14, #15, #16 |
| Unassigned | Stretch goals | #18 |

If you are blocked or finish early, say so in the team chat and pick up the next open
issue. Found a bug or thought of something new? Open an issue for it.

## Order of work

| When | What should be true |
|---|---|
| Saturday evening | Backend is in the repo and runs on everyone's laptop (#1). The player shows Barnard's Star moving (#5). |
| Sunday morning | Name search works (#2, #6). All five targets have been run and the results written down (#13). Difference and sum modes work (#3). |
| Sunday midday | Brightness chart shows the two variable stars (#4, #9). Selectors, overlay and details panel are in (#7, #10, #12). |
| Sunday afternoon | Deployed, with the cache warmed for the five targets (#14, #15). Demo recorded from the live site (#16). |
| Sunday evening | Submitted, with time to spare (#17). |

The five targets come first. Anything else waits until they work from start to finish.

## The five targets (our acceptance test)

| Target | What a good result looks like |
|---|---|
| Barnard's Star | Star steps across the frames; measured shift matches Gaia. Done in the backend. |
| Epsilon Indi B | Faint companion visible, moving with the bright star next to it |
| WISE 0855 (RA 08h55m10.831s, Dec -07d14m42.53s) | Seen only after summing all frames, in the longest-wavelength detector |
| RW Aurigae | Brightness chart shows change over time |
| R Draconis | Brightness chart shows change over time |

A feature is done when it works on these, on real SPHEREx data.

## How you work is up to you

Use any library, framework, tool, editor or AI assistant you like. Structure your part
of the code however you think best. Work on a branch or straight on `main`, with or
without pull requests. Nobody needs permission for any of that.

## The only rules: lint and typecheck

Code pushed to `main` must pass the checks below. Run them before you push. That is
the whole rulebook.

### Python (`backend/`, `scripts/`)

```
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
ruff check .
mypy
```

- `ruff check .` must report "All checks passed!". It catches unused or undefined
  names, unsorted imports, likely bugs and lines over 120 characters.
  `ruff check . --fix` repairs most findings for you.
- `mypy` must report "Success". Functions in `backend/` should have type hints on
  their arguments and return value.
- Settings live in `pyproject.toml`. The current backend passes both.

### TypeScript (`frontend/`)

```
npm run lint
npm run typecheck
```

- `npm run lint` runs ESLint with the configuration that the Vite React + TypeScript
  template creates. No errors.
- `npm run typecheck` runs `tsc --noEmit`. Keep `"strict": true` in `tsconfig.json`.
  No errors.
- Whoever scaffolds the frontend (#5) adds these two scripts to `package.json`.

### If a check is wrong for your case

Silence that one line (`# noqa: <code>`, `# type: ignore[<code>]`,
`// eslint-disable-next-line <rule>`) and add a few words saying why. Do not switch a
check off for a whole file or change the shared settings without telling the team.

## Running the backend

```
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload
```

Then open
http://localhost:8000/api/frames?ra=269.446267&dec=4.768222&fov=0.1&detector=5

Good to know:

- The first request for a new position downloads about 60 image cutouts and takes
  around a minute. After that it is served from `backend/cache/` instantly.
- NASA's archive (IRSA) drops about one request in three. The backend retries on its
  own, so a slow first load is normal.
- `CLAUDE.md` holds the full project brief and a "Verified facts" section on how the
  SPHEREx data really behaves. Read it before changing the pipeline.
- Credit on every page that shows data: NASA/JPL-Caltech SPHEREx and NASA/IPAC IRSA.

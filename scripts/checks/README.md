# Browser checks that guard the page

Two checks that load the running app in a headless Chromium and fail when the page breaks a rule the team set.
They were written on 14 and 15 November 2026 in temporary folders and copied here so that they survive. Each
copy is the latest version as of 15 November, 05:30: `stilltext_check.js` from 04:45 (its "FINDER REPAIRED
(15 Nov, finish-page)" notes) and `features_check.js` from 04:32. Both latest versions were written for two
branches that were not yet merged into `Dev` when they were copied: `agent/finish-page` (commit `49de312`) and
`agent/anomalies` (commit `674b595`, the Observe anomalies screen). The next section says how each behaves on
`Dev` before those merges.

| Check | The rule it guards |
|---|---|
| `stilltext_check.js` | The words on the page hold still while the visits play. While the pictures play or blink, no visible word changes, in Beginner and in Expert, with every fold of the side column open and with each Beginner "i" explanation open. Words change only when the visitor does something. Also: in Expert the measured-against-Gaia comparison (on Barnard's Star, reached by pressing its button) is in the window without scrolling, every control of the side column is in view at 1440 x 900, stepping by hand moves the mark of the visit on screen, and with a tool panel open and the picture scrolled out of sight the visits stop playing and start again when the picture comes back. |
| `features_check.js` | Every feature is in one bar at the top, in the order of `frontend/src/features.ts`, in the words of the level in use; the Beginner \| Expert switch is fixed at the bottom right and covers nothing; each tool opens from the bar in its level's words, and a Beginner panel shows none of the words a newcomer should not meet (sigma, flux, epoch, detector, centroid, mJy and others) outside a closed fold; the switch rewrites the bar; the screens of their own (practice, the watchlist, the three tools) carry the same bar and keep the level. |

## How they behave on `Dev` before the two branches are merged

Run on 15 November 2026 against `Dev` at `0221046` (with this documentation merged in), at port 8113, on the
shared cache:

- `stilltext_check.js` (this copy): every test passes except two, "the measured-against-Gaia comparison is inside
  the window without scrolling (not found in the side column)", at 1440 x 900 and at 1280 x 720 (`2 FAILED`).
  The comparison is there, at the top of the side column, but on `Dev` it reads "the given motion predicts
  10.3″" when Barnard's Star is opened by its button, and the check looks for the word Gaia. `agent/finish-page`
  makes it read "Gaia DR3 predicts". The earlier copy of this check (in this folder's history, commit
  `62e1f28`), which opens Barnard's Star by its address instead of its button, passed in full on the same build.
- `features_check.js` (this copy): on a build without the Observe anomalies screen it reports three failures
  (the bar's order and words, Expert's words in the bar, and the ninth item, "'Observe anomalies' is in the
  bar") and then stops with a TimeoutError at line 143, so the tests after it do not run and it never prints
  `<n> FAILED`. To check such a build, change line 27 back to `beginner: 'Vote', expert: 'Watchlist'`; with that
  one change it was run on the same build and printed `ALL PASS` (189 tests, at 1440 x 900, 1280 x 720 and
  390 x 844). The copy as it is here, unchanged, printed `ALL PASS` (189 tests) on a build of `agent/anomalies`
  at `674b595`.

A third check, `layout_check.js` (the page fits the window, and nothing moves when the visit or the star
changes), takes the same three arguments. It was not copied here; it passed in full (37 tests) on the same build.
See `CLAUDE.md`, "Checks that guard the page".

## How to run them

They need Node.js, the `playwright-core` package and a Chromium that it can launch (for example one installed
with `npx playwright install chromium`). They do not use the project's `frontend/node_modules`.

1. Build the frontend and start the server on a port of your own, from the repository root:

   ```
   cd frontend && npm ci && npm run build && cd ..
   SPHEREX_CACHE_DIR=<a warmed cache> .venv/bin/uvicorn backend.app:app --port 8111
   ```

   Use a cache in which the landing view (Candidate B) and Barnard's Star are already built, or the first load
   waits for the archive (the checks allow two minutes).

2. Run each check with three arguments: the path of the `playwright-core` package, the address of the server,
   and a folder for its screenshots:

   ```
   node scripts/checks/stilltext_check.js <path>/node_modules/playwright-core http://127.0.0.1:8111 /tmp/checks/still
   node scripts/checks/features_check.js  <path>/node_modules/playwright-core http://127.0.0.1:8111 /tmp/checks/features
   ```

   Each prints one `PASS` or `FAIL` line per test and ends with `ALL PASS` (exit 0) or `<n> FAILED` (exit 1),
   unless it stops on an error first (exit 1). They take a few minutes each.

## When the page changes

- `features_check.js` keeps its own copy of the bar's ten labels (`FEATURES`, at the top). When the bar changes,
  change that list to match `frontend/src/features.ts`, in the same commit.
- A check that fails is a finding about the page, not about the check. Change a check only when the rule itself
  has changed, and say so in its comments (they already mark their repairs as "FINDER REPAIRED (15 Nov)").

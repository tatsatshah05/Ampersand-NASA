# Browser checks that guard the page

Two checks that load the running app in a headless Chromium and fail when the page breaks a rule the team set.
They were written on 14 and 15 November 2026 in temporary folders and copied here so that they survive. Each
copy is the latest version as of 15 November, 05:30: `stilltext_check.js` from 04:45 (its "FINDER REPAIRED
(15 Nov, finish-page)" notes) and `features_check.js` from 04:32. Both were written for the page as it now is:
the joined page of `agent/finish-page` (commit `49de312`, merged into `Dev`) and the Observe anomalies screen
(`agent/anomalies`, finished on `agent/anomalies-final`). The next section says how each behaves.

| Check | The rule it guards |
|---|---|
| `stilltext_check.js` | The words on the page hold still while the visits play. While the pictures play or blink, no visible word changes, in Beginner and in Expert, with every fold of the side column open and with each Beginner "i" explanation open. Words change only when the visitor does something. Also: in Expert the measured-against-Gaia comparison (on Barnard's Star, reached by pressing its button) is in the window without scrolling, every control of the side column is in view at 1440 x 900, stepping by hand moves the mark of the visit on screen, and with a tool panel open and the picture scrolled out of sight the visits stop playing and start again when the picture comes back. |
| `features_check.js` | Every feature is in one bar that stays in view (a list down the left edge of a window 1000 px or wider, a strip along the top of a narrower one; since 15 Nov), in the order of `frontend/src/features.ts`, in the words of the level in use; the Beginner \| Expert switch is fixed at the bottom right and covers nothing; each tool opens from the bar in its level's words, and a Beginner panel shows none of the words a newcomer should not meet (sigma, flux, epoch, detector, centroid, mJy and others) outside a closed fold; the switch rewrites the bar; the screens of their own (practice, the watchlist, the three tools) carry the same bar and keep the level. |

## How they behave

Run on 15 November 2026 against a build of `agent/anomalies-final` (the Observe anomalies screen with its
reviews applied, merged with `Dev` at `ac9f4a1`), at port 8131, on the shared cache:

- `stilltext_check.js`: `ALL PASS` (60 tests). The measured-against-Gaia comparison on Barnard's Star, reached by
  its button, reads "Gaia DR3 predicts" now that `agent/finish-page` is merged, so the two failures it gave on
  `Dev` before that merge (where it read "the given motion predicts") are gone.
- `features_check.js`: `ALL PASS` (189 tests, at 1440 x 900, 1280 x 720 and 390 x 844, in Beginner and Expert).
  It expects Observe anomalies / Anomalies as the ninth item (line 27). On a build without that screen (any
  commit of `Dev` before it was merged) it reports three failures (the bar's order and words, Expert's words in
  the bar, and "'Observe anomalies' is in the bar") and then stops with a TimeoutError at line 143; to check such
  a build, change line 27 back to `beginner: 'Vote', expert: 'Watchlist'`.

Neither check's finders or rules were changed for this run.

A third check, `layout_check.js` (the page fits the window, and nothing moves when the visit or the star
changes), takes the same three arguments. It was not copied here; it passed in full (37 tests) on `Dev` at
`0221046`. It was not run on the build above: by then its temporary folder had been cleared (the machine was
restarted). See `CLAUDE.md`, "Checks that guard the page".

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

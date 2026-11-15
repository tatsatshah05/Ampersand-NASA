# Browser checks that guard the page

Two checks that load the running app in a headless Chromium and fail when the page breaks a rule the team set.
They were written on 14 and 15 November 2026 in temporary folders and are copied here unchanged, so that they
survive. Both passed on `Dev` at commit `500e7fd` (2026-11-15, at 1440 x 900 and 1280 x 720, the bar check also
at 390 x 844), with the bar check's ninth item then expected as Vote / Watchlist. The copy here is the later one
(15 November, 04:32), which expects the new names, **Observe anomalies / Anomalies**: on a build without that
screen it fails on that one item, and it passes once the screen is merged.

| Check | The rule it guards |
|---|---|
| `stilltext_check.js` | The words on the page hold still while the visits play. While the pictures play or blink, no visible word changes, in Beginner and in Expert, with every fold of the side column open and with each Beginner "i" explanation open. Words change only when the visitor does something. Also: in Expert the measured-against-Gaia comparison (on Barnard's Star) is in the window without scrolling, every control of the side column is in view at 1440 x 900, stepping by hand moves the mark of the visit on screen, and with a tool panel open and the picture scrolled out of sight the visits stop playing and start again when the picture comes back. |
| `features_check.js` | Every feature is in one bar at the top, in the order of `frontend/src/features.ts`, in the words of the level in use; the Beginner \| Expert switch is fixed at the bottom right and covers nothing; each tool opens from the bar in its level's words, and a Beginner panel shows none of the words a newcomer should not meet (sigma, flux, epoch, detector, centroid, mJy and others) outside a closed fold; the switch rewrites the bar; the screens of their own (practice, the watchlist, the three tools) carry the same bar and keep the level. |

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

   Each prints one `PASS` or `FAIL` line per test and ends with `ALL PASS` (exit 0) or `<n> FAILED` (exit 1).
   They take a few minutes each.

## When the page changes

- `features_check.js` keeps its own copy of the bar's ten labels (`FEATURES`, at the top). When the bar changes,
  change that list to match `frontend/src/features.ts`, in the same commit. (Its ninth line already reads
  Observe anomalies / Anomalies; to run it on a build that still says Vote / Watchlist, change that line back.)
- A check that fails is a finding about the page, not about the check. Change a check only when the rule itself
  has changed, and say so in its comments (they already mark two repairs as "FINDER REPAIRED (15 Nov)").

A third check, `layout_check.js` (the page fits the window, and nothing moves when the visit or the star
changes), takes the same three arguments. It was not copied here; see `CLAUDE.md`, "Checks that guard the page".

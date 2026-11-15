# The watchlist: a shared, ranked list of candidates for people and scientists to check

Written 2026-11-14 for teammates and judges.

## The problem, in the challenge's own words

> There will be too much data for any one person or even computer code to completely
> comprehend... We need your creative new tools to make the most of this treasure trove and
> help as many people as possible pitch in to make discoveries.

Our blind search (`docs/search.md`) already finds things in a patch of sky that moved or changed
brightness. What a scientist still lacks is a short, trustworthy list instead of a billion
sources, and a way to use many volunteers' eyes on it. The watchlist is that list.

## What it does

1. **Machine finds.** Every finished search is added to one shared list (a SQLite file), one row
   per object, and one per candidate the search set aside as an artefact. Nothing is invented:
   the list holds only what real searches reported, and starts with the fields already searched
   (`scripts/watchlist_ingest.py`).
2. **A second opinion** from another telescope's archive (NEOWISE) for brightness changes.
3. **People look and vote** on the Observe anomalies screen (`?watchlist=1`, the ninth item of the
   bar at the top of every screen: "Observe anomalies" in Beginner and "Anomalies" in Expert). Under
   "Pick a patch of sky" and the sweep's three candidates, the patch searches' groups ("Found by
   searching small patches") hold a card for each row: a picture strip, what the machine saw in
   plain words, what the catalogues say, the NEOWISE sentence, and three buttons. A row within 5
   arcseconds of one of the sweep's candidates, whatever its group, says first whose place it is,
   with a link to that candidate's card (at B's patch the search set aside a "mover" 0.7 arcseconds
   from B); a brightness change within 25 arcseconds of one gets a caution that its light reaches
   that place's measurement.
4. **Scientists download the list** (`/api/watchlist/export.csv` or `.json`) with all the evidence.

Everything on the list is a **candidate**. Nothing is called a discovery or a new object.

## The three groups, and the order

The groups are decided by the machine and never by votes. The screen names them in Expert as
below; in Beginner they are "Not listed as changing", "Already known" and "Set aside as false
alarms".

| Group | Rule |
|---|---|
| **Needs eyes** | Passed every artefact test of the search and no catalogue that answered explains it: a mover whose motion no catalogue object has, or a change in something not listed as variable (or with nothing there). |
| **Already known** | A catalogued mover or a listed variable star. Kept as examples of what real ones look like; voting on them shows how well people agree with the machine. |
| **Set aside as artefacts** | The search's rejected list (reflections, blends, patches of nebula), with its reasons. Kept as examples. |

The order inside "needs eyes" (and "already known"), shown on the page and in the export as
`rank_in_group`:

1. clean before caution (a caution has flags a person should look at first);
2. then more detectors at 5 times the noise or more, first;
3. then stronger first (times the noise with the detectors put together);
4. then strength in the best detector, then the identifier, so the order never wobbles.

Votes never change this order. They are shown beside the machine's evidence, as a separate number.
"Set aside" goes by strength alone.

## One row per object

The id is made from the kind and the position when it is first seen (`changer-277.5055s02.0620`).
The same object found again, or from a neighbouring patch, is the same row: a new sighting of the
same kind within 12 arcseconds (the search's own duplicate radius) of a stored row updates it. The
evidence kept is that of the patch where it was strongest; every patch that saw it is listed, with
when a search first and last reported it.

## What a vote means, and does not

A vote is an opinion about what the pictures show: looks real, looks like an artefact, or not
sure, with an optional note (plain text, at most 280 characters, shown escaped). It is **not a
confirmation**. One vote per voter per candidate; voting again replaces it. A voter can cast at most
10 votes a minute.

What is stored about a voter: a random id the browser makes and keeps in its local storage, and of
that only a SHA-256 hash. No name, no account, no address. The answer, note and time go with it.

## The picture strip

Each visit side by side on one brightness scale, then the last visit minus the first (white is
brighter later), about 80 arcseconds across, north up and east left, centred on the candidate
(four ticks around the middle), in its best detector. It is built from the cutouts the field's
search already has on disk with the viewer's own steps (`pipeline.make_grid`, `prepare_cutout`,
`Stacker`, `to_png`, `to_difference_png`), so it shows what the viewer would show. Strips are cached.
If the images are not on the server the page says there is no picture; nothing is fetched on request.

## The NEOWISE second opinion

NEOWISE measured the whole sky at 3.4 and 4.6 micrometres about twice a year from 2014 to 2024.
For every brightness change in "needs eyes" and "already known", one request at a time in the
background and cached, we take the NEOWISE measurements within 1.5 arcseconds, group them into
visits and record: how many visits, the faintest and brightest visit in each band (millijanskys),
the factor between them, and how saturated NEOWISE was. The three-way reading:

- **NEOWISE also saw this spot change**: a factor of at least 1.5 with at least 6 visits;
- **NEOWISE saw it steady**: at least 6 visits and no band changes by that factor;
- **NEOWISE cannot say**: too few measurements, or nothing there.

Limits, stated on the page: NEOWISE ended in 2024, so it speaks to whether the object **varies**,
not to this particular change. It saturates on bright objects, so its brightest values are less
certain, and it blurs about 6 arcseconds like SPHEREx, so a tight group is measured as one.
Known check: the Serpens South candidate (RA 277.50547, Dec -2.06198) gives a factor of 9.0 at 4.6
micrometres over 21 visits (177 to 1,603 mJy), as in `docs/search.md`. The code is shared with
`scripts/check_neowise.py` in `backend/neowise.py`.

## For scientists: the export

`GET /api/watchlist/export.csv` (one row per candidate, with a header of `#` comment lines that
says what each column is; read it with `pandas.read_csv(path, comment="#")`) and `export.json`
(with the same column descriptions). Columns include: position, kind, group and rank, the machine's
verdict, flags and strength (times the noise, best detector and combined), detectors at 5 times the
noise, speed or brightness ratio and the two dates compared, catalogue status and which catalogues
answered, the NEOWISE reading with its numbers, vote tallies, when a search first and last saw it,
and a link that opens the viewer on it. These are candidates.

## Honest limits

- **No accounts, so votes can be gamed.** A person can clear their storage and vote again, or a
  script can. Treat the tallies as a rough poll, not as evidence. The machine's order ignores them.
- **The list covers only patches someone has searched.** It is not a survey of the sky. A search of
  a new patch takes minutes (a few more if the images must be fetched), and is added when it finishes.
- At the time of writing, 8 of the 15 requested fields (R Draconis at 0.1 degrees, whose cached
  searches are from older versions of the search, and seven of the second hunt's fields, which a
  network outage cut short) are not on the list for that reason.
- NEOWISE's reading is about whether the object varies, not about SPHEREx's change.
- A vote on an "already known" or "set aside" example says how well people agree with the machine;
  it does not change the machine's group.

## How to run it

```
export SPHEREX_CACHE_DIR=<the shared cache>
export SPHEREX_WATCHLIST_DB=<optional: where the list is kept; default <cache>/watchlist/watchlist.sqlite3>
.venv/bin/python scripts/watchlist_ingest.py --fields docs/search/hunt2_fields.txt --neowise
```

Fields whose searches are not on disk are skipped and named; the script never starts a fresh
search. A search started from the page is added automatically when it finishes (a failure to add it
never fails the search).

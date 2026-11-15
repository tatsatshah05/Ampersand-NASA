# Distant-world search: the "Planet X" case

Code: `backend/distant.py`. Endpoint: `GET /api/distant`. On the page: the button "Search for a
distant world (Planet X)", in Expert view. Numbers on this page were measured on 2026-11-14 with
`scripts/check_distant.py` and are kept in `docs/distant/results.json`.

## The short version

- The ordinary blind search (`docs/search.md`) follows an object only if it moves less than 8 arcsec
  between two visits. An object far out in the solar system moves much more than that, in a way
  that is known in advance, so the ordinary search could not see the very thing the challenge is
  named after. This search can.
- It has found **no real candidate** in the fields searched so far, and that is the expected
  answer. What it gives for every field is a limit: how bright an object at each distance would
  have had to be for the search to find it.
- It does find made-up objects planted in real images, and gets their distance right to about a
  per cent. @@RECOVERY_SENTENCE@@
- It has made no false link: none in the real fields, none with the Earth's motion reversed (the
  control described below), and none besides the planted object in @@N_PLANTS@@ planted runs.

## Why a distant object jumps

SPHEREx looks at one patch of sky about every six months, and it always looks roughly at right
angles to the Sun. So two visits half a year apart see the patch from opposite sides of the
Earth's orbit, 2 astronomical units apart (1 AU is the Earth-Sun distance). A nearby object
appears to shift against the far background, the same way a finger held up shifts when you
switch eyes. The shift between the two visits is about twice the object's parallax:

| Distance (AU) | Jump between visits | What is out there |
|---|---|---|
| 40 | 2.9 degrees | Pluto, the Kuiper belt: leaves any picture, not searched for |
| 500 | 825 arcsec (14 arcmin) | where the proposed "Planet Nine" would be |
| 2,000 | 206 arcsec | |
| 10,000 | 41 arcsec | inner Oort cloud |
| 30,000 | 14 arcsec | the smallest jump this search takes on |

Measured on the real exposure dates of seven fields, the Earth moved 1.8 to 2.0 AU across the line
of sight between visits half a year apart, as expected. A visit a year after another is back on the same
side, so the object is back near its first place, moved on only by its own slow orbit (116 arcsec
a year at 500 AU, 1.3 at 10,000 AU).

That gives a strict rule. An object's place in every visit is fixed by five numbers: where it is
(two), its slow drift along its orbit (two) and its distance (one). The direction of the jump is
known before looking, because the Earth's position at every exposure is known. Three visits give
six measurements for five unknowns, so three unrelated sources do not fit by accident very often,
and the size of the jump gives the distance.

## What the search does

1. **Stacks each visit**, exactly as the player does, for detectors 5 and 6 (3.8 to 5.0 microns,
   where a cold body's own heat would show; Luhman's 2014 search for a cold companion of the Sun
   used the WISE 4.6 micron band for the same reason).
2. **Finds the points of light in each visit on its own**, with a filter the width of a star image,
   against a locally measured background and noise. A source is listed from 4 times the noise.
3. **Keeps the sources that come and go**: seen in one visit, missing at the same place in another.
   Ordinary stars are in every visit and drop out here.
4. **Sets aside what the catalogues explain.** A source with a CatWISE2020 source within 5 arcsec,
   at least a quarter as bright, is a known fixed object that flickered or sits at the edge of
   detection. A body that moves was somewhere else when WISE looked.
5. **Links** one source per visit wherever a single distant body explains all of them: the places
   must fit the five numbers, the drift may not be faster than a bound orbit at that distance
   allows (1.5 times the circular speed, a little more than escape), the brightness must be steady,
   two of the sources must reach 5 times the noise, and the source must not still be there in a
   visit that puts the body well away.
6. **Does it all twice**: with every exposure of each visit (deepest for a far object), and with
   only the densest few days of each visit. See "Smearing" below.
7. **Runs a control**: the same linking with the Earth's motion reversed. No real object can follow
   that, so whatever links then was made by chance. The count is shown with every answer.
8. **Answers** with candidates (distance, places, what the other detector shows, cautions) or with
   the limit table.

A candidate carries the five numbers in the form the player takes, so "Open a view that follows
it" shows the pictures with the predicted place marked in each visit, and the player's own
measurement says how strongly each visit shows something there.

### Smearing, and the second pass

A visit is not an instant. It lasts from a few hours to five weeks, and the Earth keeps moving. An
object at 500 AU moves up to 7 arcsec a day on the sky, so stacked over a five-week visit it is a
streak, not a point. Measured on the real dates, the rms spread within a visit is 0.001 to 0.28
arcsec per arcsec of parallax: nothing for some visits, 100 arcsec at 500 AU for the worst.

Most of a visit's exposures usually come within a few days, though: 18 of 25 within three days in
the second visit of WISE 0855, with a spread 60 times smaller than the whole visit's. So the second
pass stacks only the densest window (3, 6 or 10 days, the shortest that holds at least half the
exposures and at least five). It is a little shallower and far sharper for a near object. In the
0.5 degree field around WISE 0855 it took the limit at 500 AU from 2.1 mJy to 0.23 mJy. The limit
table uses the better pass at each distance and says which.

## Testing it

No real object exists to test it on. Every known body beyond Neptune is within about 135 AU of
the Sun, where the jump between visits is 50 arcminutes or more, so none would stay inside a
picture. The search is therefore tested the way surveys test theirs, by planting.

**Made-up pictures** (`tests/test_distant.py`, no SPHEREx data): noise, 40 steady stars, a flare
that is seen in one visit only, and a body placed where the Earth's motion says it must be. The
search finds the body at 1,500, 2,500 and 8,000 AU with the distance right to 8 per cent or
better, links the flare to nothing, finds nothing when the body is left out or is too faint, and
refuses a field with two visits.

**Planted objects in real images.** The practice mode's made-up object (`backend/training.py`) is
added to the real stacks of detector 5, twenty times at each of its three levels, and searched for
with the catalogue check on. The object is exactly the one the practice screen shows for the same
level and seed (a test checks the positions agree to a billionth of a degree). These runs are the
only use of planted objects. They are kept in their own files, marked `simulation`, and never
reach a real answer or the watchlist.

@@RECOVERY_TABLE@@

"Bright enough" means the object stands 5 times above the noise in two visits and 4 times in a
third, at its true places. Of those, @@BRIGHT_FOUND@@ of @@BRIGHT@@ were found. The rest landed on
a catalogued source and were set aside with it: in the field around Barnard's Star, which has
3,639 catalogued sources in 0.2 degrees, that happened to 4 of 15. Objects that were not bright
enough were not found, and should not be: the practice levels are set by eye, and "medium" and
"hard" are usually below what this search accepts. In all @@N_PLANTS@@ runs the search linked
nothing except the planted object.

## What it found in real fields

Nothing: no link in any field, in either detector or either pass, and none with the Earth's motion
reversed.

@@COUNTS_TABLE@@

The limits, at 0.2 degrees (an object at 500 AU does not fit in a picture this small):

@@LIMITS_02@@

And at 0.5 degrees, which holds the jump of an object from about 500 AU:

@@LIMITS_05@@

"Share of the picture" is where an object at that distance would stay in view in every visit,
clear of the glow of bright stars, with no catalogued source at any of its three places. A limit
of 0.2 mJy at 4 to 5 microns is roughly magnitude 14.8 in the WISE 4.6 micron band.

### How this compares with what is already known

It does not go deeper than existing searches, and nobody should read it as a new limit on
Planet Nine. Catalogues built from ten years of WISE data reach well over a magnitude
fainter than one SPHEREx visit at these wavelengths, and dedicated searches of the WISE data have
already ruled out a Saturn-sized companion of the Sun out to about 10,000 AU (Luhman 2014) and
looked for Planet Nine itself over most of the sky (Meisner et al. 2017, 2018). What this adds is
the tool: anyone can point it at a patch, it uses a second, independent telescope and years
(2025 and 2026), and it states plainly what it would have seen. SPHEREx keeps observing; every new
visit adds a fourth and fifth place, which makes a chance link far less likely and lets fainter
sources count.

## What it cannot find, and why

- **Fewer than three visits**, or visits all on one side of the Earth's orbit: the answer says the
  patch cannot be searched yet.
- **Too faint.** The object must reach 5 times the noise in two visits and 4 in a third. The limit
  table gives the figure for each distance.
- **Too near.** Nearer than about 400 AU the jump leaves a 0.5 degree picture, the largest the tool
  makes. Nearer than 100 AU nothing is tried.
- **Too far.** Beyond about 34,000 AU the jump is under 12 arcsec and the object overlaps its own
  image in the other visit. Up to 8 arcsec the ordinary search follows it, if it also drifts.
- **In the wrong place.** In the glow of a bright star, on saturated pixels, within 12 arcsec of
  the edge, or with a catalogued source within 5 arcsec of any of its three places.
- **Changing brightness.** A link whose brightest visit is more than 2.5 times its faintest is
  dropped, unless the difference is within the errors.
- **Long visits with no dense few days** (some fields near the ecliptic poles): a near object is
  smeared in both passes, and the limit table shows the weaker figure.
- A link is a candidate. With three visits one coincidence in a crowded picture is possible, which
  is what the reversed-motion control is for. A real object should also show in the neighbouring
  detector and be there again at the next visit, at a place the fit predicts to a few arcsec.

## Words for the demo

> The challenge is called Planet X. An object that far away does not creep across the picture: it
> jumps, by a quarter of the Moon's width or more, because we look at it from opposite sides of
> the Earth's orbit. This button looks for exactly that jump, and the size of the jump tells us
> how far away the object is. Here it is on a made-up object we planted, clearly marked as a
> simulation: planted at 2,559 times the Earth-Sun distance, and the search says 2,558. On the
> real sky it finds nothing here, and it says what that means: anything brighter than about a
> fifth of a millijansky between 1,000 and 30,000 times the Earth-Sun distance would have shown.

Do not say: that a planet was found, that this rules Planet Nine in or out, or that the limit is
deeper than WISE's. Say "candidate" for anything the search links, and read out its cautions.

## How to run it

```
python scripts/check_distant.py                      # nine fields at 0.2 degrees, with the planted runs
python scripts/check_distant.py --fov 0.5 --fields wise0855,epsindib,ngc1333
```

```python
from backend import distant
answer = distant.distant_search(133.759765, -7.242182, fov=0.5, detectors=(5, 6))
answer["answer"], answer["candidates"], answer["limit"], answer["chance"]
# A practice round (SIMULATION, kept apart from real answers):
distant.distant_search(133.759765, -7.242182, 0.2, (5, 6), planted={"level": "easy", "seed": 1, "detector": 5})
```

`GET /api/distant?ra=&dec=&fov=&detectors=56` runs it in the background like `/api/search`: ask
again every few seconds until `status` is `done` or `failed`. With `plant=easy|medium|hard`,
`seed=` and `plant_detector=` the answer is a simulation and says so. A first search of a new
patch reads its cutouts from NASA's archive (one to four minutes); after that the answer is kept
in `backend/cache/distant/`.

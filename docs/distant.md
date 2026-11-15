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
  per cent. Of 205 planted objects that were bright enough in three visits, it found 177.
- It has made no false link: none in the real fields, none with the Earth's motion reversed (the
  control described below), and none besides the planted object in 539 planted runs.

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
0.5 degree field around WISE 0855 it took the limit at 500 AU from 1.7 mJy to 0.23 mJy. The limit
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

| Field (0.2 degrees, detector 5) | Level | Brightness (mJy) | Planted | Bright enough | Found | Bright enough and found |
|---|---|---|---|---|---|---|
| WISE 0855-0714 | easy | 0.289 | 20 | 18 | 17 | 17 |
| WISE 0855-0714 | medium | 0.168 | 20 | 0 | 0 | 0 |
| WISE 0855-0714 | hard | 0.108 | 20 | 0 | 0 | 0 |
| Barnard's Star | easy | 1.031 | 20 | 15 | 11 | 11 |
| Barnard's Star | medium | 0.601 | 20 | 3 | 2 | 2 |
| Barnard's Star | hard | 0.387 | 20 | 0 | 0 | 0 |
| Epsilon Indi B | easy | 0.55 | 20 | 20 | 20 | 20 |
| Epsilon Indi B | medium | 0.321 | 20 | 20 | 20 | 20 |
| Epsilon Indi B | hard | 0.206 | 20 | 16 | 12 | 12 |
| RW Aurigae | easy | 0.776 | 20 | 12 | 12 | 12 |
| RW Aurigae | medium | 0.453 | 20 | 2 | 0 | 0 |
| RW Aurigae | hard | 0.291 | 20 | 0 | 0 | 0 |
| R Draconis | easy | 3.813 | 20 | 15 | 13 | 13 |
| R Draconis | medium | 2.224 | 20 | 13 | 10 | 10 |
| R Draconis | hard | 1.43 | 20 | 13 | 10 | 9 |
| NGC 1333 | easy | 4.84 | 20 | 5 | 5 | 5 |
| NGC 1333 | medium | 2.823 | 20 | 0 | 0 | 0 |
| NGC 1333 | hard | 1.815 | 20 | 0 | 0 | 0 |
| Serpens Main | easy | 5.509 | 20 | 7 | 7 | 7 |
| Serpens Main | medium | 3.213 | 20 | 3 | 2 | 2 |
| Serpens Main | hard | 2.066 | 20 | 0 | 0 | 0 |
| Serpens South | easy | 7.036 | 20 | 15 | 14 | 14 |
| Serpens South | medium | 4.104 | 20 | 9 | 8 | 8 |
| Serpens South | hard | 2.638 | 19 | 7 | 7 | 7 |
| Chamaeleon I | easy | 0.508 | 20 | 12 | 8 | 8 |
| Chamaeleon I | medium | 0.296 | 20 | 0 | 0 | 0 |
| Chamaeleon I | hard | 0.191 | 20 | 0 | 0 | 0 |
| **All** | | | **539** | **205** | **178** | **177** |

"Bright enough" means the object stands 5 times above the noise in two visits and 4 times in a
third, at its true places. Of those, 177 of 205 were found. Every one of the 28
that were missed was traced. Twelve had a catalogued source at one of their three places and were
set aside with it (5 of them in the field of Barnard's Star, which has 3,639 catalogued sources in
0.2 degrees). Fifteen lay on top of something that is there in every visit, a faint star or the
glow of a bright one (8 of them around R Draconis), and could not be told from it. One came out
too wide to count as a point of light. None was lost by the linking itself.

Objects that were not bright enough were not found, with one exception that sat at the limit, and
they should not be. The practice levels are set against the scatter of the whole picture, not
against what this search needs: in NGC 1333 only 5 of 20 "easy" objects were bright enough, and
around Epsilon Indi B 16 of 20 "hard" ones were. In all 539 runs the search linked nothing
except the planted object.

## What it found in real fields

Nothing: no link in any field, in either detector or either pass, and none with the Earth's motion
reversed.

| Field | Width | Visits | Detector, pass | Sources per visit | Come and go | On a catalogued source | Tried for linking | Links | Links, Earth reversed |
|---|---|---|---|---|---|---|---|---|---|
| WISE 0855-0714 | 0.2 | 3 | D5, every exposure | 100 to 111 | 0 | 0 | 0 | 0 | 0 |
| WISE 0855-0714 | 0.2 | 3 | D5, densest days | 100 to 109 | 0 | 0 | 0 | 0 | 0 |
| WISE 0855-0714 | 0.2 | 3 | D6, every exposure | 36 to 90 | 8 | 5 | 3 | 0 | 0 |
| WISE 0855-0714 | 0.2 | 3 | D6, densest days | 36 to 87 | 10 | 9 | 1 | 0 | 0 |
| Barnard's Star | 0.2 | 3 | D5, every exposure | 115 to 119 | 0 | 0 | 0 | 0 | 0 |
| Barnard's Star | 0.2 | 3 | D5, densest days | 115 to 118 | 0 | 0 | 0 | 0 | 0 |
| Barnard's Star | 0.2 | 3 | D6, every exposure | 104 to 106 | 0 | 0 | 0 | 0 | 0 |
| Barnard's Star | 0.2 | 3 | D6, densest days | 102 to 106 | 0 | 0 | 0 | 0 | 0 |
| Epsilon Indi B | 0.2 | 4 | D5, every exposure | 73 to 89 | 4 | 3 | 1 | 0 | 0 |
| Epsilon Indi B | 0.2 | 4 | D5, densest days | 73 to 86 | 4 | 2 | 2 | 0 | 0 |
| Epsilon Indi B | 0.2 | 4 | D6, every exposure | 54 to 75 | 10 | 2 | 8 | 0 | 0 |
| Epsilon Indi B | 0.2 | 4 | D6, densest days | 54 to 69 | 10 | 2 | 7 | 0 | 0 |
| RW Aurigae | 0.2 | 3 | D5, every exposure | 117 to 122 | 0 | 0 | 0 | 0 | 0 |
| RW Aurigae | 0.2 | 3 | D5, densest days | 116 to 118 | 0 | 0 | 0 | 0 | 0 |
| RW Aurigae | 0.2 | 3 | D6, every exposure | 101 to 103 | 0 | 0 | 0 | 0 | 0 |
| RW Aurigae | 0.2 | 3 | D6, densest days | 97 to 102 | 0 | 0 | 0 | 0 | 0 |
| R Draconis | 0.2 | 3 | D5, every exposure | 42 to 50 | 0 | 0 | 0 | 0 | 0 |
| R Draconis | 0.2 | 3 | D5, densest days | 42 to 46 | 3 | 0 | 3 | 0 | 0 |
| R Draconis | 0.2 | 3 | D6, every exposure | 28 to 49 | 4 | 1 | 2 | 0 | 0 |
| R Draconis | 0.2 | 3 | D6, densest days | 25 to 49 | 4 | 1 | 3 | 0 | 0 |
| NGC 1333 | 0.2 | 3 | D5, every exposure | 85 to 86 | 0 | 0 | 0 | 0 | 0 |
| NGC 1333 | 0.2 | 3 | D5, densest days | 83 to 86 | 0 | 0 | 0 | 0 | 0 |
| NGC 1333 | 0.2 | 3 | D6, every exposure | 73 to 76 | 0 | 0 | 0 | 0 | 0 |
| NGC 1333 | 0.2 | 3 | D6, densest days | 74 to 76 | 0 | 0 | 0 | 0 | 0 |
| Serpens Main | 0.2 | 3 | D5, every exposure | 124 to 127 | 0 | 0 | 0 | 0 | 0 |
| Serpens Main | 0.2 | 3 | D5, densest days | 125 to 129 | 0 | 0 | 0 | 0 | 0 |
| Serpens Main | 0.2 | 3 | D6, every exposure | 108 to 114 | 0 | 0 | 0 | 0 | 0 |
| Serpens Main | 0.2 | 3 | D6, densest days | 107 to 111 | 0 | 0 | 0 | 0 | 0 |
| Serpens South | 0.2 | 4 | D5, every exposure | 112 to 113 | 0 | 0 | 0 | 0 | 0 |
| Serpens South | 0.2 | 4 | D5, densest days | 108 to 114 | 0 | 0 | 0 | 0 | 0 |
| Serpens South | 0.2 | 4 | D6, every exposure | 95 to 105 | 0 | 0 | 0 | 0 | 0 |
| Serpens South | 0.2 | 4 | D6, densest days | 95 to 107 | 1 | 0 | 1 | 0 | 0 |
| Chamaeleon I | 0.2 | 3 | D5, every exposure | 121 to 128 | 0 | 0 | 0 | 0 | 0 |
| Chamaeleon I | 0.2 | 3 | D5, densest days | 121 to 125 | 0 | 0 | 0 | 0 | 0 |
| Chamaeleon I | 0.2 | 3 | D6, every exposure | 97 to 98 | 5 | 1 | 4 | 0 | 0 |
| Chamaeleon I | 0.2 | 3 | D6, densest days | 92 to 101 | 3 | 0 | 3 | 0 | 0 |
| WISE 0855-0714 | 0.5 | 3 | D5, every exposure | 556 to 677 | 3 | 3 | 0 | 0 | 0 |
| WISE 0855-0714 | 0.5 | 3 | D5, densest days | 556 to 661 | 4 | 4 | 0 | 0 | 0 |
| WISE 0855-0714 | 0.5 | 3 | D6, every exposure | 255 to 494 | 58 | 39 | 19 | 0 | 0 |
| WISE 0855-0714 | 0.5 | 3 | D6, densest days | 255 to 482 | 53 | 43 | 10 | 0 | 0 |
| Epsilon Indi B | 0.5 | 4 | D5, every exposure | 488 to 626 | 17 | 9 | 7 | 0 | 0 |
| Epsilon Indi B | 0.5 | 4 | D5, densest days | 475 to 604 | 15 | 3 | 12 | 0 | 0 |
| Epsilon Indi B | 0.5 | 4 | D6, every exposure | 358 to 483 | 98 | 22 | 72 | 0 | 0 |
| Epsilon Indi B | 0.5 | 4 | D6, densest days | 337 to 440 | 79 | 13 | 61 | 0 | 0 |
| NGC 1333 | 0.5 | 3 | D5, every exposure | 576 to 591 | 1 | 0 | 1 | 0 | 0 |
| NGC 1333 | 0.5 | 3 | D5, densest days | 532 to 591 | 5 | 2 | 3 | 0 | 0 |
| NGC 1333 | 0.5 | 3 | D6, every exposure | 474 to 482 | 10 | 4 | 6 | 0 | 0 |
| NGC 1333 | 0.5 | 3 | D6, densest days | 412 to 482 | 16 | 13 | 3 | 0 | 0 |

The limits, at 0.2 degrees (an object at 500 AU does not fit in a picture this small):

| Field | 1,000 AU | 2,000 AU | 5,000 AU | 10,000 AU | 30,000 AU |
|---|---|---|---|---|---|
| WISE 0855-0714 | 0.20 mJy, 20% | 0.20 mJy, 42% | 0.20 mJy, 57% | 0.20 mJy, 62% | 0.18 mJy, 64% |
| Barnard's Star | 0.69 mJy, 18% | 0.60 mJy, 37% | 0.57 mJy, 48% | 0.56 mJy, 52% | 0.54 mJy, 54% |
| Epsilon Indi B | 0.23 mJy, 16% | 0.20 mJy, 35% | 0.19 mJy, 50% | 0.19 mJy, 55% | 0.18 mJy, 56% |
| RW Aurigae | 0.53 mJy, 18% | 0.53 mJy, 38% | 0.52 mJy, 50% | 0.51 mJy, 54% | 0.51 mJy, 56% |
| R Draconis | 1.79 mJy, 17% | 0.92 mJy, 35% | 0.43 mJy, 46% | 0.31 mJy, 50% | 0.28 mJy, 54% |
| NGC 1333 | 1.91 mJy, 15% | 1.89 mJy, 31% | 1.89 mJy, 42% | 1.88 mJy, 46% | 1.87 mJy, 48% |
| Serpens Main | 4.25 mJy, 20% | 3.70 mJy, 38% | 3.53 mJy, 49% | 3.49 mJy, 52% | 3.49 mJy, 55% |
| Serpens South | 3.85 mJy, 19% | 3.73 mJy, 37% | 3.70 mJy, 48% | 3.69 mJy, 52% | 3.69 mJy, 54% |
| Chamaeleon I | 0.45 mJy, 16% | 0.41 mJy, 34% | 0.39 mJy, 47% | 0.38 mJy, 52% | 0.38 mJy, 55% |

And at 0.5 degrees, which holds the jump of an object from about 500 AU:

| Field | 500 AU | 700 AU | 1,000 AU | 2,000 AU | 10,000 AU | 30,000 AU |
|---|---|---|---|---|---|---|
| WISE 0855-0714 | 0.23 mJy, 26% | 0.23 mJy, 37% | 0.22 mJy, 46% | 0.22 mJy, 56% | 0.21 mJy, 65% | 0.20 mJy, 64% |
| Epsilon Indi B | 0.23 mJy, 23% | 0.22 mJy, 34% | 0.20 mJy, 43% | 0.18 mJy, 55% | 0.17 mJy, 64% | 0.16 mJy, 64% |
| NGC 1333 | 0.28 mJy, 22% | 0.28 mJy, 31% | 0.27 mJy, 38% | 0.27 mJy, 47% | 0.27 mJy, 53% | 0.27 mJy, 54% |

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

## Pictures

- [docs/distant/panel_real.png](distant/panel_real.png): the panel after a real search of the
  0.2 degree patch around WISE 0855. Nothing found, the limit at each distance, the control.
- [docs/distant/panel_simulation.png](distant/panel_simulation.png): the same patch with the
  practice round's object planted (easy level, seed 1). The banner cannot be closed; the search
  puts the object at 2,558 AU and it was planted at 2,559.

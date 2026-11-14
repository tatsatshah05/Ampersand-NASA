# Known asteroids and comets that crossed a patch

All of this was run on real data on 14 November 2026. Small-body data: NASA/JPL Solar System
Dynamics (Small-Body Identification API and Horizons). Code: `backend/smallbodies.py`,
`GET /api/smallbodies`, panel `frontend/src/components/SmallBodiesPanel.tsx`.

## What it does

For a view (ra, dec, field, detector) it lists the known asteroids and comets that JPL predicts
inside the field at the middle of any exposure of that detector, and for each one:

- the exposure (time, detector, visit number as `/api/frames` numbers it, wavelength range),
- the predicted RA/Dec and position on the frame grid, predicted magnitude, sky motion,
- a measurement in that one exposure ("a source is seen here at N sigma", "possible", "nothing is
  seen", "not measured"), a check whether the same source is also there on other days, and a note
  when a Gaia star is within 12 arcsec,
- a 120 arcsec picture of that exposure centred on the predicted place.

A prediction is only a prediction: the word "seen" is used only for what the exposure shows.

## How, and how long the JPL calls take

Measured with real requests:

| Request | Time |
|---|---|
| Horizons, one body, a few times (observer = SPHEREx, id -163182) | 0.4 s |
| sb_ident, first pass only (two-body orbits) | 18 s |
| sb_ident, two passes (numerical orbits) | 35 to 37 s alone, 20 to 30 s per call when two run at once |
| sb_ident, field 0.2 or 1.0 degrees wide | the same: the time is the catalogue scan, not the field |

One sb_ident call per exposure (100+ per view) is out of the question, so:

1. Exposures of the view's detector are grouped into bursts (a gap over 0.75 day starts a new one,
   at most 5 days per burst).
2. One two-pass sb_ident call per burst, for a field widened by 0.4 degree per day of half-burst,
   vmag limit 21, geocentre (MPC 500). Two calls at once, no more.
3. Candidates whose straight-line path (sb_ident position and rate) never comes within reach of the
   field are dropped.
4. Horizons gives each remaining body's position at each exposure's mid-time as seen from SPHEREx;
   the ones inside the frame grid are the crossings.
5. Every JPL answer is kept on disk (`<cache>/smallbodies/jpl/`), and a finished view is cached too.
   A view whose lookup had a failed request is not cached, and says so (`problems`).

First lookup of a view, measured: RW Aurigae 283 s (before the two-at-once change and with 3-day
bursts), 4 Vesta patch 182 s, WISE 0855 139 s, Barnard's Star 273 s, R Draconis 294 s, Epsilon Indi
465 s (17 bursts: it has exposures spread over 4 visits). After that: under 4 s. This is slow for a
first visitor (the panel says so while it waits); it is bound by JPL's catalogue scan. Warm the
cache for the demo targets before showing them.

Horizons does know SPHEREx (`horizons_lookup.api?sstr=SPHEREx` gives id -163182, "2025-047E") and
has its trajectory for all dates used here, so positions are for the spacecraft itself, not the
geocentre. The difference, for 4 Vesta on 2026-07-16: 0.4 to 2.2 arcsec (it changes through the
98-minute orbit), so under one SPHEREx pixel (6.15 arcsec), not the several pixels expected for a
near-Earth object. For a near-Earth object it would be larger; those are exactly the bodies the
spacecraft position matters for, and that is why it is used.

## Validation: 4 Vesta, 16 July 2026

Choosing the case: Horizons daily positions (SPHEREx as observer) for ten bright main-belt asteroids
from 1 May 2025 to 10 Nov 2026; days with solar elongation 80 to 100 degrees (SPHEREx looks about 90
degrees from the Sun); IRSA's image search (SIA, with a time range) for exposures covering the
predicted position that day. 196 asteroid-days had exposures. Chosen: Vesta (V 7.7), 16 July 2026,
detector 5. The view is centred on Vesta's predicted position at 22:04 UT (RA 23.35591, Dec 1.50056,
field 0.1 degree), which the field then leaves within about 9 hours. The field has three visits:
July 2025, January 2026, July 2026.

Result of `known_bodies(23.35591, 1.50056, 0.1, 5)`: 13 crossings, three bodies, 0 problems:

| Body | Exposures | Result |
|---|---|---|
| 4 Vesta, V 7.7 | 7 (16 July 2026, 18:46 to 18:53 and 22:03 to 22:08 UTC, visit 3) | source at 460 to 493 sigma in the 5 that could be measured; 2 not measured (a bad pixel flag in the measuring circle) |
| 4959 Niinoama, V 17.0 | 4 (11 July 2025, visit 1) | 4.2, 3.5, not measured, 5.2 sigma: faint, not secure |
| 78146, V 20.2 | 2 (10 Jan 2026, visit 2) | 1.7 sigma and not measured: nothing seen |

Vesta, predicted against seen. In each of the 7 exposures a Gaussian was fitted to the exposure on a
2 arcsec grid centred on the predicted place; the fitted centre minus the predicted place:

| Exposure (UTC) | Offset (arcsec) |
|---|---|
| 18:46:54 | 0.33 |
| 18:49:03 | 0.36 |
| 18:51:12 | 0.86 |
| 18:53:21 | 0.42 |
| 22:03:33 | 1.17 |
| 22:05:42 | 0.25 |
| 22:07:51 | 0.46 |

Median 0.42 arcsec, largest 1.2 arcsec (0.2 of a SPHEREx pixel; the star-like image is about 11
arcsec wide, and the fit is on a 2 arcsec grid, so a good part of this is fit error). Flux in the
measuring circle 1.44 to 1.63 Jy at 4.2 to 4.4 micron. Local scatter at ring positions 60 arcsec away
was 0.2 mJy where it could be measured.

Absent from the other visits: the same sky place (RA 23.35607, Dec 1.50052) measured in the detector
5 exposures of other days: visit 1 (15 exposures) median 0.0 sigma, largest 1.8; visit 2 (13)
median -0.4, largest 0.9; visit 3 on other days (4) median 0.3, largest 2.0. So a 1.4 Jy source in
the exposure and nothing in 32 others. Picture (same stretch for all four panels, the Vesta
exposure and the exposure of each visit nearest in wavelength): `docs/smallbodies/vesta_2026-07-16.png`.
The page as a visitor sees it: `docs/smallbodies/panel_vesta_patch.png`.

Not done: stacked-frame comparison. `/api/frames` drops a reading that stands alone, so whether the
visit 3 stack still shows Vesta was not checked here.

## The five test targets (detector 5, field 0.1 degree, default)

| Target | Crossings | First lookup |
|---|---|---|
| Barnard's Star | none | 273 s |
| Epsilon Indi (B) | none | 465 s |
| WISE 0855 | 66654 (1999 SF12), V 18.7, 2 exposures on 2 May 2026: a source at 27 sigma, but see below | 139 s |
| RW Aurigae | 103643 (2000 CW34), V 19.8, 3 exposures on 15 Sep 2026: nothing seen (-0.9 to 0.4 sigma) | 283 s |
| R Draconis | none | 294 s |

A false positive that was caught. For WISE 0855 the first version said asteroid 66654 was "seen" at
27 sigma. The same sky place measured in 29 exposures of other days gave a median of 28 sigma: it is
a fixed source, not the asteroid (the asteroid is faint at V 18.7 and not shown by the exposure).
Since then a source that most exposures of other days also show is reported as "a fixed source (a
star or galaxy), not this body". Same test for the others in the table: Vesta and Niinoama are not
fixed. 4959 Niinoama at 3.5 to 5.2 sigma has not been shown to be the asteroid beyond being at the
predicted place and not a fixed source.

## Limits (read before relying on it)

- Only bodies in JPL's catalogue of known bodies. Nothing here says anything about unknown objects.
- Bodies moving faster than 0.4 degree a day across the sky (some near-Earth objects) can be
  missed: the candidate field is only widened by that much. Fainter than predicted V 21 are not
  looked for; SPHEREx rarely shows those in one exposure anyway.
- Candidates come from sb_ident for the geocentre; the final positions are for the spacecraft. The
  candidate field has 0.1 degree of margin; for a very close object the difference could exceed it.
- sb_ident answers with `mag-required=true`: bodies without a magnitude in JPL's database are skipped.
- Comets: names and Horizons look-up were checked on real answers (13P, 31P, 123P, C/2025 R2, 3I)
  but no comet crossed any field tried, so the crossing and measurement path has run only on
  asteroids. A comet's predicted magnitude is sb_ident's total magnitude, which can be far from
  what a diffuse coma gives per pixel.
- Measurement: flux in a 2.5 pixel circle against the exposure's own noise (`photometry.measure`).
  A source on a flagged pixel is "not measured" (2 of Vesta's 7). A saturated Vesta is not
  handled specially. "Seen" means a source of at least 5 sigma at that place that is not also there on
  other days; 3 to 5 sigma is "possible". A star within 12 arcsec is mentioned. A fixed faint
  source in only one or two other exposures would not be noticed, and fewer than 3 measurable
  other exposures gives no fixed-source check.
- The sky motion shown includes SPHEREx's own motion (up to about 18 arcsec/hour for a body 2 au away).
- The first lookup of a view takes minutes (see the table). JPL has no stated rate limit; the code
  keeps to two requests at once, four tries with doubling pauses, 120 s timeout.

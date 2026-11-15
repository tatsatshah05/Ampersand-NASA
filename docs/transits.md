# A planet crossing its star, seen in SPHEREx deep-field exposures

Built 2026-11-14. Code: `backend/transits.py` (entry function `transit_check`), `scripts/check_transit.py`
(repeats everything), `tests/test_transits.py` (offline). Numbers: `docs/transits/results.json`.
Pictures: `docs/transits/`.

## The idea in three sentences

Near the two ecliptic poles SPHEREx looks at the same stars thousands of times, one colour per
exposure. When a planet with a known orbit passes in front of its star, the star dims by a few per
cent; we divide every reading by the star's own brightness at that colour, line the readings up by the
planet's published orbit, and measure the dip. If a dip shows up at the published time, with the
published depth, and not at wrong times, SPHEREx has seen the planet cross its star.

## The proof (known-answer test): WASP-62 b

WASP-62 b is a hot Jupiter. Published: period 4.41193868 d, mid-transit 2458851.099338 (BJD, TDB;
Kokori et al. 2023), transit length 3.79 h, (Rp/Rs)^2 = 0.1109^2 = **1.23 per cent** (Patel and
Espinoza 2022). The acceptance numbers were written down before the run (`scripts/check_transit.py`,
stage A1) and none was tuned.

Result, detector 5 (3.8 to 4.4 micrometres), 8,326 exposures of the star in the archive, 757 read,
484 usable, 65 of them inside a transit, 29 different transits:

| Check | Required | Measured |
|---|---|---|
| Depth against the published 1.23 | within 2 empirical sigma | **1.21 +/- 0.26 per cent** (formal error 0.18) |
| Significance | at least 3.5 empirical sigma | **4.6** |
| Fake ephemerides as deep | under 1 per cent | **0 of 598** |
| Time slide: peak of depth against assumed transit time | at 0 +/- 1.5 h | **0 h** |
| Each year on its own, over 3 formal sigma | both | **1.35 +/- 0.27 (2025, 30 readings in transit) and 1.15 +/- 0.25 (2026, 35)** |
| Steady comparison star (Gaia G = 12.4, 109 arcsec away) fitted with WASP-62 b's ephemeris | within 2 sigma of 0 | **-0.25 +/- 0.42 per cent** |

Picture that matters: `docs/transits/wasp62b_folded_D5.png` (every reading folded on the published
orbit, with 45-minute means, the published transit and the fitted one). Second picture:
`docs/transits/wasp62b_time_slide_D5.png` (depth against the assumed transit time: it peaks at zero).

"Empirical error" is the spread of the depth fitted at 598 fake ephemerides (periods 1.5 to 9 d in
steps of 0.005 d, four phase offsets, the real transits removed, periods near 1/2, 1, 3/2, 2 and 3
times the real one skipped). It is 1.5 times the formal error, because the readings' noise is
correlated, so we always quote the larger one.

## How it works, in short

1. Every exposure covering the star in all four archive collections, including the two deep-field
   collections that `spherex.find_exposures` does not ask for (it asks only `spherex_dr1` and
   `spherex_qr3`; at WASP-62 those hold 1,021 exposures and the deep collections another 7,305).
2. Mid-exposure time converted to BJD (TDB) at the Earth's centre (error under 25 ms).
3. Aperture photometry of the star in each cutout read from NASA's public bucket (2.5 pixel
   circle, sky from a 6 to 10 pixel ring, zodiacal light removed), reusing the project's
   `photometry` internals.
4. Each reading divided by the median of the 30 nearest out-of-transit readings in wavelength: the
   star's own spectrum.
5. A fit: constant, a quadratic in detector position, sub-pixel position, minus the transit shape
   (trapezoid, T23 from the radius ratio). Readings more than 5 sigma away are clipped once.
6. A detector is left out if more than 20 per cent of its usable readings have an OVERFLOW pixel
   (the star is too bright there).

## Results

### WASP-62 b: only detector 5 can show it

| Detector | Readings in transit | Verdict of the method |
|---|---|---|
| 1 (0.75 to 1.1 um) | 8 usable | too few |
| 2 (1.1 to 1.6 um) | 50 usable | left out: 397 of 398 usable readings have an OVERFLOW pixel (star is 300 mJy there); for the record only, 0.65 +/- 0.98 per cent |
| 3, 4, 6 | 6, 9, 4 | too few |
| **5 (3.8 to 4.4 um)** | **65** | **1.21 +/- 0.26 per cent, 4.6 sigma** |

So **one detector of one planet**. That is the honest size of the proof. The colour test cannot be
checked on this planet.

How the answer moves with each analysis choice (same readings, detector 5; formal errors, about 0.18):

| Choice | Depth (per cent) |
|---|---|
| Default (quadratic detector position, sub-pixel, 30 neighbours, clip 5 sigma) | 1.21 |
| No detector-position terms | 1.33 +/- 0.22 |
| Linear detector-position terms | 1.28 +/- 0.21 |
| No sub-pixel terms | 1.18 |
| Template from 14 / 60 neighbours | 1.24 / 1.21 |
| Clip at 4 sigma / no clipping | 1.22 / 1.21 |
| HALO-flagged pixels accepted in the circle (78 readings in transit, 901 fakes, 0 as deep) | 1.06 +/- 0.25 (empirical), 4.2 sigma |

All choices lie between 1.06 and 1.33, within one empirical sigma of the published 1.23. The choice
of accepting HALO pixels moves it most (0.15), and we report both.

Leaving out the most helpful transits (greedy, one after another): 1.14, 1.08, 1.03, 0.99, 0.95 per
cent after leaving out 1 to 5 of the 29 transits. Leaving out any single one: 1.14 to 1.31 per cent. The
depth is not carried by a few transits, but it does shrink steadily, as it would if the signal is real and
the noise is large: with five out it is still 0.95 per cent (about 5 formal sigma, 3.6 empirical).

### WASP-100 b (second known planet, reported without tuning)

Published: period 2.84938224 d, mid-transit 2458853.880674, 3.75 h, (Rp/Rs)^2 = 0.757 per cent.
7,677 exposures, 51 to 108 inside a transit per detector. Cutouts read: 680 to 706 per detector.

| Detector | In transit | Depth (per cent) | Empirical sigma | Fakes as deep |
|---|---|---|---|---|
| 2 | 49 | 1.02 +/- 0.54 | left out (280 of 421 have an OVERFLOW pixel) | |
| 3 (1.6 to 2.4 um) | 70 | 0.13 +/- 0.32 | 0.4 | 38 per cent |
| **5 (3.8 to 4.4 um)** | **48** | **1.24 +/- 0.34** | **3.6** | **0 of 434** |
| 6 (4.4 to 5.0 um) | 70 | 0.61 +/- 0.45 | 1.4 | 10 per cent |

Combined over 3, 5 and 6 with inverse-variance weights: **0.64 +/- 0.21 per cent against the published
0.757: inside 2 sigma, so the test passes** (stage A3). But look at what it is made of. Detector 5
alone shows the transit (3.6 sigma, peak of the time slide at 0 h, both years positive: 1.37 +/- 0.34
and 0.93 +/- 0.40). Detector 3 does not show it: 0.13 +/- 0.32, two sigma below the published value, and
the 3-to-5 difference is 1.11 +/- 0.47 per cent (chi-squared p = 0.06 for one depth in all three). The
combined test passes largely because the errors are large. We do not call detector 3 a detection and
we did not try to rescue it. WASP-100 b is a second, weaker, detector-5 recovery, and the first probe's
"not recovered" was a detector-3 statement.

### Colour test: a limit, not a verdict

The colour test asks whether a transit is as deep at every wavelength (a planet's should be; a
blended eclipsing binary's usually is not). It would need a known planet measured at 3 sigma or more in
two detectors with one depth (A4). **No planet has done that**: WASP-62 b is in one detector,
WASP-100 b in one. So **the colour test is not validated, and no object in this document is called a
planet or a blend**.

A known eclipsing binary as a second known answer: TIC 233532554 (TESS eclipsing-binary catalogue,
period 2.8312777 d, primary depth 0.817 in TESS), measured by another inventor from real standard-
collection exposures (`docs/transits/eb_tic233532554_rows.json`, 477 readings). Its primary eclipse
**is recovered in all six detectors** (3.1 to 12.5 empirical sigma, 0 to 0.5 per cent of fake
ephemerides as deep), with the flat part of the eclipse taken as 0.5 of its width (an assumption; 0.8
changes every depth by 10 to 30 per cent):

| Detector | Depth (fraction of the light) | Note |
|---|---|---|
| 1 | 0.76 +/- 0.07 | star too bright: OVERFLOW pixels in 32 of 34 readings |
| 2 | 0.62 +/- 0.07 | same, 31 of 38 |
| 3 | 0.51 +/- 0.12 | same, 48 of 72 |
| 4 | 0.50 +/- 0.16 | same, 18 of 47 |
| 5 (3.8 to 4.4 um) | 0.47 +/- 0.07 | clean |
| 6 (4.4 to 5.0 um) | 0.43 +/- 0.12 | clean |

The depth falls from 0.76 at 0.9 micrometres to 0.43 at 4.7 micrometres, and one depth for all six is
rejected (chi-squared p = 0.024; 0.0007 with the 0.8 flat part). But detectors 1 to 4 are exactly the
ones with OVERFLOW pixels, the same rule that removes them for the planets applies, and the two clean
detectors (5 and 6) agree with each other (0.47 and 0.43, p = 0.79). So the data show the eclipse in
every detector and a plausible colour trend, **but a colour difference that survives the saturation
rule has not been shown**: the colour test stays unproven. The picture is `docs/transits/eb_depths.png`.

### TOI-4055.01 (a TESS candidate), as measurements

TESS candidate on the north-pole deep field (TIC 233053554, 1.8 degrees from the pole): period
4.5679250 d, mid-transit 2459853.406756, 3.047 h, TESS depth 1.84 per cent. 24,917 exposures of it
exist; 87 to 126 fall in a transit per detector (62 to 84 of them usable). This run read 648 to 700 cutouts in each of detectors 1
to 4 (detectors 5 and 6 were not downloaded in the time available; `scripts/check_transit.py` fetches
them).

| Detector | Readings in transit | Depth (per cent) | Empirical sigma | Fakes as deep | Smallest depth shown (3 sigma) |
|---|---|---|---|---|---|
| 1 (0.75 to 1.1 um) | 63 | 1.51 +/- 0.36 | 4.2 | 0 of 281 | 1.09 |
| 2 (1.1 to 1.6 um) | 84 | 1.64 +/- 0.45 | 3.6 | 0 of 174 | 1.36 |
| 3 (1.6 to 2.4 um) | 78 | 1.50 +/- 0.52 | 2.9 | 0.2 per cent of 471 | 1.56 |
| 4 (2.4 to 3.8 um) | 62 | 1.31 +/- 0.40 | 3.3 | 0 of 303 | 1.20 |

What can be said: the transit that TESS reports **is also present in SPHEREx exposures** at the TESS
time, in the four detectors that were read (time slide peaks at 0 h in detectors 1, 2 and 3; in
detector 4 the slide peaks 10.5 h away, so that check fails there), each 2.9 to 4.2 sigma, mean depth
1.48 +/- 0.21 per cent (TESS 1.84). The per-detector depths agree with one another (chi-squared
0.32 for 3 degrees of freedom, p = 0.96) and with no change of depth with colour.

What cannot be said: that this makes the candidate a planet. The colour test is not validated (no known
planet has passed it in two detectors), and the smallest difference in depth between two detectors that
these data could show at 3 sigma is **1.6 to 2.1 per cent**, as large as the whole depth. That excludes a
transit that is more than about twice as deep in one of these colours than in another, and nothing
smaller. TOI-4055.01 has five ground-based time-series follow-ups listed on ExoFOP, so its nature may be
settled already; this is at most an independent look. No Gaia DR3 star brighter than G = 17 lies inside
the 15.4 arcsec measuring circle of this star, WASP-62 or WASP-100 (so none of their depths is diluted by
a catalogued neighbour of that brightness; fainter ones are not excluded).

The smallest transit this data can show, for a star like TOI-4055 (about 15 mJy at 1 micrometre, Tmag
13.2): about 1.1 to 1.6 per cent at 3 sigma in one detector. Per reading the scatter is 1.5 to 2.2 per
cent against 0.9 to 1.5 per cent of photon noise, and correlated noise makes the real error 1.4 to 1.8
times the formal one. Giant-planet transits only.

## Every control and how it came out

| Control | Result |
|---|---|
| Fake ephemerides (wrong periods and phases) | WASP-62 b D5: 0 of 598 as deep. TOI-4055.01: 0 to 0.2 per cent. WASP-100 b D3: 38 per cent (nothing there) |
| Depth against time offset from mid-transit | peaks at 0 h for WASP-62 b D5, WASP-100 b D5, TOI-4055.01 D1 to D3; not for TOI-4055.01 D4 |
| Each year on its own | WASP-62 b both years over 4 formal sigma; WASP-100 b D5 both positive; TOI-4055.01: all four detectors positive in both years |
| Each detector | only D5 for WASP-62 b; D5 and weakly D6 for WASP-100 b; D1 to D4 for TOI-4055.01 |
| Leave out the most helpful transits | WASP-62 b: 1.14 to 0.95 per cent after 1 to 5 left out |
| Steady comparison star in the same exposures | one star qualified (G = 12.4): -0.25 +/- 0.42 per cent, consistent with 0. Only one: a thin control |
| Analysis choices (position terms, sub-pixel, template size, clipping, HALO) | 1.06 to 1.33 per cent |
| Saturation rule | WASP-62 b D2 and WASP-100 b D2 left out |
| Known eclipsing binary | eclipse recovered in six detectors; colour trend only in detectors the saturation rule removes |

## What was searched in the literature, and found

Searches on 2026-11-14: "SPHEREx exoplanet transit light curve deep field"; "SPHEREx time-domain photometry
variability deep fields"; "SPHEREx eclipsing binary / transiting planet / hot Jupiter"; "SPHEREx WASP-62";
"astronomerstelegram SPHEREx eclipse/transit/light curve"; "SPHEREx deep field stars variability
photometric precision". We found no SPHEREx transit, eclipse or exoplanet light-curve result, paper or
telegram. Nearest work: Lisse et al. 2026 (a 3I/ATLAS light curve made by dividing SPHEREx fluxes by a
JWST spectrum: the same normalising idea on a comet); the SPLICES ices overview (flags variable sources,
no transits); Rustamkulov, ExSoCal 2025 (transit-host star spectra, not light curves); Kim et al. 2026
(mid-infrared variables at the ecliptic poles, from NEOWISE). The same fold-on-a-known-period idea on
sparse data of other missions: Hipparcos recovered HD 209458 b (Robichon and Arenou 2000; Castellano et
al. 2000). **We do not know of this having been done with SPHEREx data.** That is a statement about what
we searched, not about the literature.

## Limits

- One detector of one planet is the proof; the precision is about 0.3 per cent per planet and detector.
- Only giant-planet depths (about 1 per cent) of stars in the cores of the deep fields (the deep
  field is patchy, not a circle around the pole) can be shown.
- Bright stars saturate (OVERFLOW above about 100 to 300 mJy in detectors 1 to 3).
- The noise is correlated (1.4 to 1.8 times the formal error): always use the empirical error.
- The depth depends by about 1 sigma on analysis choices (above).
- Ephemerides are the published ones, so this recovers known transits; it does not search for new ones.
- Neighbours fainter than G = 17 inside the circle are not excluded.
- The colour test is unproven.

## What would confirm more

- A known planet with a bright enough, unsaturated star in several detectors (the inventor's list:
  Qatar-10 b, TOI-4468 b near the north pole; not checked here) measured at 3 sigma or more in two
  detectors with one depth. Only then does the colour test count.
- For TOI-4055.01: detectors 5 and 6 (download them), and a repeat after the next deep-field visits.
- For the eclipsing binary: a version without OVERFLOW (a fainter binary).

## Words for the demo

Say: "SPHEREx was not built to watch planets cross their stars, but near the poles it looks at the same
stars thousands of times. We folded those readings on WASP-62 b's published orbit and the star dims by
1.2 per cent at the right time: the planet's shadow, 4.6 sigma, in one detector." "The same method sees
WASP-100 b in one detector and the TESS candidate TOI-4055.01's transit in four." "Our checks:
fake orbits, shifted times, each year alone, leaving out the best transits, a steady star measured in the
same exposures." "We do not know of this having been done with SPHEREx data."

Do not say: a new planet; a discovery; a first; that TOI-4055.01 is a planet or is confirmed or validated;
that the colour test works; that SPHEREx can find transiting planets (it recovers known ones at 1 per
cent depth, in one or a few detectors); that a blend is ruled out; "exoplanet imaging" (the pixels are
6 arcseconds).

# A planet crossing its star, seen in SPHEREx deep-field exposures

Built 2026-11-14, reviewed by three skeptics and corrected the same day. Code: `backend/transits.py`
(entry function `transit_check`), `scripts/check_transit.py` (repeats everything), `tests/test_transits.py`
(offline). Numbers: `docs/transits/results.json`. Pictures: `docs/transits/`.

Numbers marked "reviewer" were measured by an independent reviewer with their own code or scripts and are
**not** repeated by `scripts/check_transit.py`; everything else is.

## The idea in three sentences

Near the two ecliptic poles SPHEREx looks at the same stars thousands of times, one colour per
exposure. When a planet with a known orbit passes in front of its star, the star dims by a few per
cent; we divide every reading by the star's own brightness at that colour, line the readings up by the
planet's published orbit, and measure the dip. If a dip shows up at the published time, with about the
published depth, and not at wrong times, SPHEREx has seen the planet cross its star.

## What this is, and is not

- It **recovers known transits**. It is not a search; it does not find planets.
- It is a **re-measurement, not a blind test**. The method was developed on the same WASP-62 detector-5
  readings in an exploratory probe that had already measured 1.37 per cent (no detector-position terms),
  1.23 (with them) and 1.07 (HALO pixels accepted), each at 4.2 empirical sigma. The choice of detector 5,
  the detector-position correction and the HALO policy were made there. The acceptance numbers of stage A1
  were written down after that probe. This rebuild fixed all choices and measured again; it did not tune
  them afterwards, but the data had been seen. WASP-100 b in detector 5 is the only planet result on
  readings the method had not seen (it passes there and fails in detector 3).
- The depth moves by about one sigma with analysis choices (below), so we quote the range, not one number.

## The proof (known-answer test): WASP-62 b

WASP-62 b is a hot Jupiter. Published: period 4.41193868 d, mid-transit 2458851.099338 (BJD, TDB;
Kokori et al. 2023), transit length 3.79 h, (Rp/Rs)^2 = 0.1109^2 = **1.23 per cent** (Kokori et al. 2023;
Patel and Espinoza 2022 give 0.1111). Published depths of this planet range from 1.13 to 1.47 per cent
(Brown 2017 1.13, Maciejewski 2020 1.22, Hellier 2012 1.23, ExoFOP TESS 1.47), so "1.18 against 1.23" is
agreement within the spread of the references, not a precise match.

Result, detector 5 (3.8 to 4.4 micrometres), 8,326 exposures of the star in the archive, 757 read,
484 usable, 65 of them inside a transit (HALO pixels rejected), 29 different transits:

| Check | Required | Measured |
|---|---|---|
| Depth against the published 1.23 | within 2 empirical sigma | **1.18 +/- 0.26 per cent** (formal error 0.18); **1.05 +/- 0.25** with HALO pixels accepted (78 readings in transit) |
| Significance | at least 3.5 empirical sigma | **4.5** (4.2 with HALO accepted): depth over the spread of the fake-orbit depths |
| Fake ephemerides as deep | under 1 per cent | **0 of 598** shown directly (p below 0.002). The fakes overlap (88 per cent of pairs share a reading); the reviewer counts about **140 independent**, so p is below about 0.7 per cent. Deepest fake 0.99 per cent |
| Time slide: peak of depth over error against assumed transit time | at 0 +/- 1.5 h | **-0.5 h** |
| Each year on its own, over 3 formal sigma | both | **1.33 +/- 0.28 (2025, 30 readings in transit) and 1.10 +/- 0.25 (2026, 35)**, formal errors; with the empirical error (x1.42) these are 1.33 +/- 0.40 and 1.10 +/- 0.36, 3.3 and 3.1 sigma |
| Steady comparison star (Gaia G = 12.4, 109 arcsec away) fitted with WASP-62 b's ephemeris | within 2 sigma of 0 | **-0.32 +/- 0.42 per cent** |

Quote the depth as **1.05 to 1.18 +/- 0.25 per cent (HALO pixels accepted / rejected), 4.2 to 4.5 sigma,
against a published 1.23 (references 1.13 to 1.47)**, never one number alone.

Pictures: `docs/transits/wasp62b_folded_D5.png` (every reading folded on the published orbit, with
45-minute means, the published transit and the fitted one) and `docs/transits/wasp62b_time_slide_D5.png`
(depth against assumed transit time, only boxes with at least 15 readings and inside the window where
readings were kept).

**Empirical error.** It is the spread of the depth fitted at 598 fake ephemerides (periods 1.5 to 9 d in
steps of 0.005 d, four phase offsets, the real transits removed, periods near 1/2, 1, 3/2, 2 and 3 times
the real one skipped). It is 1.42 times the formal error, mostly because a typical fake transit holds
about 36 readings against the real 65 (reviewer): fakes with 50 to 80 readings give a spread of 0.22 per
cent, a block bootstrap by visit gives 0.18, a delete-one-visit jackknife 0.19. We quote the largest, so
the 4.5 sigma is conservative. The "4.5 sigma" is the depth divided by that spread, a Gaussian
extrapolation; what is shown directly is 0 of 598 as deep. A reviewer's null rebuilt with the same
treatment as the real transit (template excluding each fake's own readings) gave a spread of 0.255 per
cent and a near-Gaussian shape, which supports the extrapolation.

**Checks robust to correlated noise (reviewer).** 26 of 27 transits with flat-bottom readings dip below
their baseline (sign test p = 2e-7); the same test on six windows shifted 4.5 to 7.5 h away from the
transit gives 9 to 19 of 19 to 31 positive (p 0.14 to 0.92). Taking out the ten most helpful single
readings leaves 0.87 per cent. Boxes of the same width 4.5 to 8 h from mid-transit, with at least 15
readings, show nothing beyond 0.94 formal sigma (against 6.9 at 0 h).

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
5. A fit: constant, a quadratic in detector position, sub-pixel offset terms (dx, dy, dx^2, dy^2, dx*dy
   about the nearest pixel centre), minus the transit shape (trapezoid, T23 from the radius ratio).
   Readings more than 5 sigma away are clipped once.
6. A detector is left out if more than 20 per cent of its usable readings have an OVERFLOW pixel
   (the star is too bright there).

**Detectors work in pairs (verified).** Detectors 1/4, 2/5 and 3/6 sit behind a dichroic and take the
same exposures at the same moment (same obs_id and start time: at WASP-62, 780, 3,031 and 229 shared
obs_ids; none shared across pairs; the same at WASP-100 and TOI-4055; SPHEREx mission papers arXiv
2404.11017 and 2511.02985). Detectors of different pairs never observed the same transit, so comparing
them mixes epoch with wavelength. Between paired detectors the noise is nearly independent (reviewer:
residual correlation on shared exposures +0.01 to +0.10; correlation of depths at the same fake ephemerides
-0.08 to +0.08), so combined errors stand.

**Detector position, and what the correction is.** Wavelength changes along detector y, so wavelength and
y are the same variable (correlation 1.00) and the quadratic y terms duplicate the wavelength template. The
real correction is along detector x: out-of-transit readings drift by about 2.7 per cent peak to peak,
twice the transit depth. The depth survives the model (reviewer): cubic terms 1.24 +/- 0.26, 6x6 step
functions 1.31 +/- 0.28, none 1.35 +/- 0.35; the two halves in detector x give 1.57 +/- 0.39 and 0.79 +/-
0.39 (1.4 sigma apart). The sub-pixel terms in the first build were defined from a wrapped coordinate that
could not model a response symmetric about the pixel centre; fixed here (offset from the nearest pixel
centre, quadratic terms), and a proper model gave the same depth.

## Results

### WASP-62 b: only detector 5 can show it

| Detector | Readings in transit | Verdict of the method |
|---|---|---|
| 1 (0.75 to 1.1 um) | 8 usable | too few |
| 2 (1.1 to 1.6 um) | 50 usable | left out: 397 of 398 usable readings have an OVERFLOW pixel (star is 300 mJy there); the detector that takes the same exposures as detector 5 is therefore unusable; for the record only, 0.65 +/- 0.98 per cent |
| 3, 4, 6 | 6, 9, 4 | too few |
| **5 (3.8 to 4.4 um)** | **65** | **1.18 +/- 0.26 per cent, 4.5 sigma** |

So **one detector of one planet**. That is the honest size of the proof. The colour test cannot be
checked on this planet.

How the answer moves with each analysis choice (same readings, detector 5; formal errors about 0.18):

| Choice | Depth (per cent) |
|---|---|
| Default (quadratic detector position, sub-pixel, 30 neighbours, clip 5 sigma, radius 2.5 px) | 1.18 |
| No detector-position terms | 1.33 +/- 0.22 |
| Linear detector-position terms | 1.26 +/- 0.20 |
| No sub-pixel terms | 1.18 |
| Template from 14 / 60 neighbours | 1.20 / 1.18 |
| Clip at 4 sigma / no clipping | 1.19 / 1.18 |
| Aperture radius 1.5 / 2.0 / 3.0 / 3.5 px (each re-measured, all 0 fakes as deep, slide peak 0 to -0.5 h) | 0.93 / 1.14 / 1.19 / 1.29 (3.9 / 4.7 / 4.5 / 4.5 empirical sigma) |
| HALO-flagged pixels accepted in the circle (78 readings in transit, 901 fakes, 0 as deep) | 1.05 +/- 0.25 (empirical), 4.2 sigma |

All choices lie between **0.93 and 1.33**, within 1.2 empirical sigma of the published 1.23. Aperture
radius and the HALO flag move it most. The depth grows with the aperture; the ratio of the 3.5 px to the
1.5 px flux dips at the transit at 2.2 sigma (reviewer, 0.8 per cent of fakes), not explained by sky level,
star width or centroid at the transit; most likely noise, and it is an analysis choice that was not fixed
in advance. The 91 readings that HALO alone removes are not biased bright (median +0.05 per cent out of
transit against -0.03 for clean readings), so the 1.18 versus 1.05 difference is noise, not cosmic-ray
residue.

Leaving out the most helpful transits (greedy): 1.12, 1.06, 1.00, 0.97, 0.93 per cent after leaving out
1 to 5 of the 29 transits. Leaving out any single one: 1.12 to 1.28 per cent. It is not carried by a few
transits but shrinks steadily, as it would if the signal is real and the noise large.

### Steady-star controls

The first build had one steady star (G 12.4: -0.32 +/- 0.42 per cent, which already rules out a
common-mode dip as deep as WASP-62 b's at about 3 sigma). Reviewers added more, fitted with WASP-62 b's
ephemeris in the same detector-5 exposures (reviewer, not repeated by the script):

- Five bright isolated Gaia stars, G 9.7 to 11.4, 8 to 18 arcmin away, in the 457 exposures within 0.35 d of
  a transit: +0.06, -0.60, -0.09, -0.21, -0.19 per cent (formal errors 0.18 to 0.30). Chi-squared about zero
  7.1 for 5 dof (p = 0.21), weighted mean -0.17 +/- 0.10. On the same selection WASP-62 gives +1.18 +/- 0.31.
- Gaia DR3 4756651025913241728 (G 10.97, 171 arcsec, 33 mJy): -0.13 +/- 0.29 per cent formal, 69 readings in
  transit; WASP-62 divided by it on 118 shared exposures: 1.30 +/- 0.40 (the dip does not cancel).

So no dip above about 0.15 per cent is shared by these exposures.

### WASP-100 b (second known planet, reported without tuning)

Published: period 2.84938224 d, mid-transit 2458853.880674, 3.75 h, (Rp/Rs)^2 = 0.757 per cent.
7,677 exposures, 48 to 70 inside a transit per usable detector. Cutouts read: 680 to 706 per detector.

| Detector | In transit | Depth (per cent) | Empirical sigma | Fakes as deep |
|---|---|---|---|---|
| 2 | 49 | 0.84 +/- 0.55 | left out (280 of 421 have an OVERFLOW pixel) | |
| 3 (1.6 to 2.4 um) | 70 | 0.12 +/- 0.34 | 0.4 | 36 per cent |
| **5 (3.8 to 4.4 um)** | **48** | **1.23 +/- 0.34** | **3.6** | **1 of 434 (0.2 per cent)** |
| 6 (4.4 to 5.0 um) | 70 | 0.63 +/- 0.45 | 1.4 | 9 per cent |

Combined over 3, 5 and 6 with inverse-variance weights: 0.66 +/- 0.21 per cent against the published
0.757: inside 2 sigma, so stage A3 passes. **But it passes on averaging, and no single detector matches the
published depth**: detector 5 is 1.4 sigma deeper than published (1.23 against 0.757) and detector 3 is
about 1.9 sigma shallower (chi-squared of 3, 5 and 6 about 0.757 is about 6 for 3 dof, p about 0.1).
Detector 6 is not a detection (1.4 sigma, 9 per cent of fakes as deep, time slide peaks at -5 h).
Detector 5 alone shows the transit (3.6 sigma, slide peak at 0 h, both years positive: 1.41 +/- 0.33 and 0.91
+/- 0.38, formal). We call it a **detector-5 recovery of a known planet, not a second confirmation of
the method**.

**The detector 3 versus detector 5 difference is not a colour result.** Detectors 3 and 5 never observed the
same transit (0 shared transits of 22 and 19). Detectors 3 and 6 take the same exposures and both read low
(0.12 and 0.63; the pair difference is -0.50 +/- 0.56 per cent); detectors 2 and 5 take the same exposures
and both read high (0.84, left out for OVERFLOW, and 1.23). The disagreement is between two sets of
transits (one pair of detectors against the other), not between wavelengths, and it is not evidence about
colour. Leaving out detector 3's 25 OVERFLOW readings gives 0.20 +/- 0.34 (reviewer), so saturation does not
explain it.

### Colour test: a limit, not a verdict

The colour test asks whether a transit is as deep at every wavelength (a planet's should be; a blended
eclipsing binary's usually is not). The clean version compares the two detectors of one dichroic pair on
their shared exposures (1 with 4, 2 with 5, 3 with 6); any other comparison mixes epoch and wavelength, and
`colour_test` now marks each pair with `same_exposures`. Validation needs a known planet measured at 3
sigma or more in two detectors with one depth (A4). **No planet has done that**: WASP-62 b is in one
detector, WASP-100 b in one. So **the colour test is not validated, and no object in this document is
called a planet or a blend**.

A known eclipsing binary as another known answer: TIC 233532554 (TESS eclipsing-binary catalogue, period
2.8312777 d, primary depth 0.817 in the polyfit and 0.921 in the two-Gaussian measure, Tmag 9.6), measured
by another inventor from real standard-collection exposures (`docs/transits/eb_tic233532554_rows.json`, 477
readings; the rows were not re-measured from cutouts in this build). Its primary eclipse **is recovered in
all six detectors** (3.1 to 11.3 empirical sigma, 0 to 0.5 per cent of fake ephemerides as deep; 12.5 with
a flat part of 0.8), with the flat part of the eclipse taken as 0.5 of its width (an assumption; 0.8 changes
every depth by 10 to 30 per cent):

| Detector | Depth (fraction of the light) | Note |
|---|---|---|
| 1 | 0.76 +/- 0.07 | star too bright: OVERFLOW pixels in 32 of 34 readings |
| 2 | 0.62 +/- 0.07 | same, 31 of 38 |
| 3 | 0.51 +/- 0.12 | same, 48 of 72 |
| 4 | 0.50 +/- 0.16 | same, 18 of 47 |
| 5 (3.8 to 4.4 um) | 0.47 +/- 0.07 | clean |
| 6 (4.4 to 5.0 um) | 0.43 +/- 0.12 | clean |

The depth falls from 0.76 at 0.9 micrometres to 0.43 at 4.7 micrometres, and one depth for all six is
rejected (chi-squared p = 0.024; 0.0007 with the 0.8 flat part). But detectors 1 to 4 are exactly the ones
with OVERFLOW pixels, which the same rule that removes them for the planets would remove here, and the two
clean detectors (5 and 6, which are different pairs and so different exposures) agree (0.47 and 0.43,
p = 0.79). So the data show the eclipse in every detector and a plausible colour trend, **but a colour
difference that survives the saturation rule has not been shown**: the colour test stays unproven. Picture:
`docs/transits/eb_depths.png`.

### TOI-4055.01 (a TESS candidate), as measurements

TESS candidate on the north-pole deep field (TIC 233053554, 1.8 degrees from the pole): period 4.5679250 d,
mid-transit 2459853.406756, 3.047 h, TESS depth 1.84 per cent. 24,917 exposures of it exist; 87 to 126 fall
in a transit per detector (62 to 84 usable). This run read 648 to 700 cutouts in each of detectors 1 to 4;
detectors 5 and 6 were **not downloaded** (the script fetches them).

| Detector | Readings in transit | Depth (per cent) | Empirical sigma | Fakes as deep | Independent fakes (reviewer) | Smallest depth shown (3 sigma) |
|---|---|---|---|---|---|---|
| 1 (0.75 to 1.1 um) | 63 | 1.48 +/- 0.37 | 4.1 | 0 of 281 | about 104 | 1.10 |
| 2 (1.1 to 1.6 um) | 84 | 1.60 +/- 0.43 | 3.7 | 0 of 176 | about 89 | 1.30 |
| 3 (1.6 to 2.4 um) | 78 | 1.48 +/- 0.53 | 2.8 | 0.2 per cent of 471 | about 133 | 1.59 |
| 4 (2.4 to 3.8 um) | 62 | 1.33 +/- 0.40 | 3.3 | 0 of 303 | about 113 | 1.20 |

Time slide (peak of depth over error): 0 h in all four detectors (an earlier version of the check took the
largest depth, ignored the errors and ran past the window where readings were kept; it picked a 1.58 +/-
1.30 point at -10.5 h in detector 4 and that "failure" was an artefact). All four detectors are positive in
both years (D1 1.29 and 1.80, D2 1.64 and 1.47, D3 1.73 and 1.44, D4 1.00 and 1.44, formal errors 0.33 to
0.45). Mean depth 1.47 +/- 0.21 per cent.

What can be said: **a dip at the TESS times of the candidate TOI-4055.01 is present in SPHEREx exposures.**
It passes the same checks as WASP-62 b detector 5 in detectors 1 and 2 (4.1 and 3.7 empirical sigma, slide
peak at 0 h, both years over 3.9 formal sigma). Detectors 3 and 4 give positive depths (2.8 and 3.3 sigma)
below the 3.5-sigma bar. Detectors 1 to 4 have **no known planet that passed in them** (WASP-62 b has under
10 in-transit readings there or is saturated; WASP-100 b failed in detector 3), so these numbers are
raw measurements in unvalidated detectors. Block bootstraps (reviewer) give 4.0 to 6.5 sigma per
detector, 18 of 20, 23 of 24, 17 of 22 and 17 of 21 transits dip in detectors 1 to 4, and detector 2 has
real correlated noise (beta 1.45 to 1.73).

Independence: detectors 1 and 4 share 20 of 21 transits, so "four detectors" are **three independent sets
of transits**: 1 and 4 are the same transits seen at two wavelengths at once; 2 and 3 saw other
transits. The per-detector depths agree with one another (chi-squared 0.22 for 3 dof, p = 0.97), but that p
and the 1.6 to 2.0 per cent smallest detectable depth difference between detectors rest on empirical
errors that are probably 1.3 to 1.8 times too large (fakes with few readings), so they are conservative the
wrong way for the "consistent" claim and should be read loosely. The smallest depth difference that could be
shown at 3 sigma is 1.6 to 2.0 per cent, as large as the whole depth: **at 3 sigma these depths still
allow one detector's depth to be from about 0.2 to about 4 times another's** (reviewer: D2/D1 0.18 to 4.35;
D4/D3 up to 8), so only extreme colour differences could be seen.

What cannot be said: that this makes the candidate a planet. The colour test is not validated. **Prior
work**: ExoFOP carries a "high-probability planet" flag from the RAVEN team (Lafarga et al. 2026,
arXiv 2603.22597, MNRAS 548) with depth 1.62 +/- 0.05 per cent, five ground time series including MuSCAT2 g,
r, i, z_s, B and i band, Keck/HIRES and Palomar AO imaging; these are far more precise for a colour or blend
check than SPHEREx. The SPHEREx mean 1.47 +/- 0.21 is 0.7 sigma from RAVEN's 1.62 and 1.8 sigma from the TOI's
1.84. It is not among the 14 candidates of the TRICERATOPS+ paper (arXiv 2508.02782); the NASA Exoplanet
Archive still lists it as a candidate. So this is at most an independent look.

Controls missing for TOI-4055.01: **no steady comparison star** was measured (the 0.05 degree cutouts are
too small to hold comparison stars) and detectors 5 and 6 were not read. No Gaia DR3 star brighter than
G = 17 lies inside the 15.4 arcsec measuring circle of this star, WASP-62 or WASP-100 (fainter ones are
not excluded).

The smallest transit this data can show, for a star like TOI-4055 (about 15 mJy at 1 micrometre, Tmag
13.2): about 1.1 to 1.6 per cent at 3 sigma in one detector. Per reading the scatter is 1.5 to 2.2 per cent
against 0.9 to 1.5 per cent of photon noise. Giant-planet transits only. Picture:
`docs/transits/toi4055_depths.png`.

## Every control and how it came out

| Control | Result |
|---|---|
| Fake ephemerides (wrong periods and phases) | WASP-62 b D5: 0 of 598 as deep (about 140 independent, p below about 0.7 per cent). TOI-4055.01: 0 to 0.2 per cent (about 90 to 130 independent). WASP-100 b D3: 36 per cent (nothing there). Aliases of 1 day and of the 98-minute orbit are not excluded from the fakes: this only makes the test conservative |
| Depth against time offset from mid-transit (peak of depth over error, boxes with at least 15 readings, within the readings' window) | peaks at 0 to -0.5 h for WASP-62 b D5, WASP-100 b D5 and TOI-4055.01 D1 to D4 |
| Each year on its own | WASP-62 b both years positive (3.3 and 3.1 empirical sigma); WASP-100 b D5 both positive; TOI-4055.01 all four detectors positive in both years |
| Per-transit sign test (reviewer) | WASP-62 b: 26 of 27 transits dip (p = 2e-7); shifted windows 9 to 19 of 19 to 31 (p 0.14 to 0.92) |
| Each detector | only D5 for WASP-62 b; D5 only for WASP-100 b; D1 to D4 for TOI-4055.01 (three independent sets of transits), none of them validated by a known planet |
| Leave out the most helpful transits | WASP-62 b: 1.12 to 0.93 per cent after 1 to 5 left out |
| Steady comparison stars in the same exposures | G 12.4 star: -0.32 +/- 0.42; reviewer's six more stars: -0.60 to +0.06, none above 0.15 per cent shared. None for TOI-4055.01 |
| Analysis choices (position terms, sub-pixel, template size, clipping, aperture radius, HALO) | 0.93 to 1.33 per cent |
| Saturation rule | WASP-62 b D2 and WASP-100 b D2 left out |
| Known eclipsing binary | eclipse recovered in six detectors; colour trend only in detectors the saturation rule removes |

## What was searched in the literature, and found

Searches on 2026-11-14 (arXiv API, web search, astronomer's telegram search; **not** ADS full text): "SPHEREx
exoplanet transit light curve deep field"; "SPHEREx time-domain photometry variability deep fields";
"SPHEREx eclipsing binary / transiting planet / hot Jupiter"; "SPHEREx WASP-62"; "astronomerstelegram SPHEREx
eclipse/transit/light curve"; "SPHEREx deep field stars variability photometric precision"; "SPHEREx
dichroic detector arrays simultaneous field of view"; and arXiv queries 'SPHEREx' AND each of transit,
exoplanet, eclipsing, variability, light curve, time domain, deep fields. We found no SPHEREx transit,
eclipse or exoplanet light-curve result, paper or telegram. Nearest work: Lisse et al. 2026 (a 3I/ATLAS
light curve made by dividing SPHEREx fluxes by a JWST spectrum: the same normalising idea on a comet); the
SPHEREx ices overview (Melnick et al. 2026, arXiv 2603.22135; flags variable sources, no transits); Rustamkulov,
ExSoCal 2025 (transit-host star spectra, not light curves); Kim et al. 2026 (arXiv 2604.05332; mid-infrared
variables at the ecliptic poles, from NEOWISE). The SPHEREx mission paper (arXiv 2511.02985) says the deep
fields are observed every orbit and that the team measures the relative flux of about 100,000 bright
deep-field stars to monitor gain, so **unpublished SPHEREx-internal time series of these stars exist**. The
same fold-on-a-known-period idea on sparse data of other missions: Hipparcos recovered HD 209458 b (Robichon
and Arenou 2000; Castellano et al. 2000), Gaia sparse photometry (Panahi et al. 2022, arXiv 2205.10197).
**We do not know of this having been done with SPHEREx data.** That is a statement about the published
papers, preprints and telegrams we searched, not about the literature or the team's internal work.

## Limits

- One detector of one planet is the proof; the precision is about 0.3 per cent per planet and detector.
- It is a re-measurement after an exploratory look at the same data, not a blind test.
- Only giant-planet depths (about 1 per cent) of stars in the cores of the deep fields (the deep
  field is patchy, not a circle around the pole) can be shown.
- Bright stars saturate (OVERFLOW above about 100 to 300 mJy in detectors 1 to 3).
- The depth depends by about 1 sigma on analysis choices, aperture radius most (0.93 to 1.33).
- Ephemerides are the published ones, so this recovers known transits; it does not search for new ones.
- Neighbours fainter than G = 17 inside the circle are not excluded.
- The colour test is unproven, and detectors 1 to 4 have no known-planet validation.
- Eclipse depths depend on an assumed eclipse shape (flat part 0.5 against 0.8 changes them by 10 to 30 per
  cent).

## What would confirm more

- A known planet with a bright enough, unsaturated star in detectors 1 to 4: Qatar-10 b (RA 284.4439, Dec
  +69.5708; P 1.645321 d; depth 1.931 per cent; the reviewer counted 5,380 exposures and 44 to 79 in-transit
  readings per detector over 14 to 20 transits; about 2,500 cutouts, roughly 270 MB). **Not run**: no time.
  If recovered at 3.5 sigma or more in detector 1, 3 or 4 within 2 sigma of its depth, the TOI-4055.01
  numbers in those detectors would have a known answer. TOI-4468 b has only 26 to 27 readings per detector
  and none in detectors 2 and 5, so it is not usable.
- For TOI-4055.01: detectors 5 and 6 (download them), a steady comparison star with larger cutouts, and a
  repeat after the next deep-field visits.
- For the eclipsing binary: a version without OVERFLOW (a fainter binary).

## Words for the demo

Say: "SPHEREx was not built to watch planets cross their stars, but near the poles it looks at the same
stars thousands of times. We folded those readings on the known hot Jupiter WASP-62 b's published orbit
and in one detector the star dims by about 1.1 to 1.2 per cent at the right time, against a published 1.2:
4 to 4.5 sigma, none of 598 wrong orbits as deep. It is a recovery of a known planet in one detector, and
we had looked at that data before fixing the method." "The same method shows WASP-100 b in that detector
too, not in the other." "At the TESS times of the candidate TOI-4055.01 there is a dip of about 1.5 per
cent in detectors 1 to 4, three independent sets of transits; that is a measurement, not a verdict, and
better ground data already exist." "Our checks: fake orbits, shifted times, each year alone, single transits,
leaving out the best transits, other steady stars measured in the same exposures." "We do not know of this
having been done with SPHEREx data (we searched published papers, preprints and telegrams, not the team's
internal calibration work)."

Do not say: a new planet; a discovery; a first; blind; that the test was passed before looking; that
TOI-4055.01 is a planet or is confirmed or validated; that detectors 1 to 4 were tested on a known planet;
that the colour test works or that two detectors "agree in colour"; that the WASP-100 b detector 3 versus 5
difference is a colour effect; that SPHEREx can find transiting planets (it recovers known ones at 1 per
cent depth, in one or a few detectors); that a blend is ruled out; "exoplanet imaging" (the pixels are
6 arcseconds); a single depth for WASP-62 b without its range.

## Rerun

From a checkout root:

```
SPHEREX_CACHE_DIR=<repo>/backend/cache python scripts/check_transit.py --cache-dir <repo>/backend/cache/invent-P1 --probe-dir <scratchpad>/invent/transits --no-fetch
```

About 15 minutes from cached cutouts (the first build said 8; the aperture re-measurements add four more
passes of detector 5). Omit `--no-fetch` to download what is missing (TOI-4055 detectors 5 and 6; about 1.2
GB for a clean start). `--only A1,A2` runs the proof alone. Offline tests: `python -m pytest -q
tests/test_transits.py`.

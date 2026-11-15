# Following a comet or asteroid through SPHEREx, and measuring its spectrum

All of this was run on real data on 14 November 2026. Orbits: NASA/JPL Solar System Dynamics (JPL Horizons).
Images: NASA/JPL-Caltech SPHEREx, NASA/IPAC IRSA. Code: `backend/follow.py`, command line
`scripts/follow_body.py`, tests `tests/test_follow.py`. Pictures and the measured points of every body are in
`docs/comets/` (one `.json` per body, with every exposure's measurement).

## In one minute

- **It works.** `follow_body("name")` finds every public SPHEREx exposure that contains a known body at its predicted place
  (Horizons, seen from the spacecraft), measures it there against noise measured the same way at empty places, and gives one
  point per exposure: a spectrum, one colour per exposure.
- **Vesta**: 34 usable measurements of 312 (the rest are saturated). A smooth spectrum with heat rising toward 5 micrometres,
  no gas band, agrees with the earlier measurement of the project.
- **3I/ATLAS**: finds the carbon dioxide band the SPHEREx team published (detected in August 2025) and the December 2025
  rise of water, carbon monoxide and carbon dioxide. **It does not recover the published carbon dioxide absolute number:
  2.3 times lower at the peak channel**; the reasons tried and not tried are listed.
- **Pluto (with Charon)**: 229 exposures contain it; a picture of the same patch of sky on six days shows Pluto moving 113
  arcsec in 7 days against fixed stars. The spectrum has a methane-like shape, but **no methane dip is established** by the
  rules used here (2.3 micrometres is 7 times its error and marginal).
- **Comets**: carbon dioxide band measured in C/2025 R2, C/2025 A6, 24P, C/2025 T1, 10P and 29P; water but no carbon
  dioxide in C/2025 K1; carbon monoxide and carbon dioxide in 29P (already published by JWST). Several are measured only
  by comparing channels taken minutes apart, and none is checked against a published spectrum of the same body; I did not
  check the literature beyond the web searches written down below.
- **Not done**: stacking of the faint bodies, the web endpoint and panel, a reduction of the SPHEREx calibration
  features, and any confirmation from an independent pipeline.

## What it does, in plain words

SPHEREx looks at the whole sky through a filter that changes colour across each image, so every exposure sees a
patch of sky in a different colour of infrared light (102 colours, 0.75 to 5 micrometres). One exposure of a comet
therefore gives one colour of it. A comet that crosses the survey is caught in hundreds of exposures, each in a
different colour, and put together they make a spectrum of the comet.

Why a comet is the prize: gas in its cloud (the coma) glows at colours that tell what it is made of: water at 2.7
micrometres, carbon dioxide at 4.26, carbon monoxide at 4.67. Carbon dioxide cannot be seen from the ground at all.

`follow_body("name")` does this for one named body:

1. Asks JPL Horizons where the body was, as seen from the SPHEREx spacecraft itself, every day from 1 May 2025 to
   today (564 rows), with its predicted brightness, distance from the Sun and from SPHEREx, and the angle between the
   Sun and the body (the elongation).
2. Keeps the days when the elongation is in the range SPHEREx looks at. That range was measured, not assumed: the
   exposure lists of two positions (Barnard's Star, 364 exposures, and the patch around 4 Vesta, 394 exposures) span
   81.9 to 128.4 degrees and 80.5 to 121.8 degrees from the Sun (astropy's Sun position at each exposure's time). The
   search window is 70 to 140 degrees.
3. Cuts those days into stretches over which the body moves less than 0.7 degree and asks IRSA's image search which
   exposures cover the two ends of each stretch in the stretch's time range. IRSA's image search times out for any
   search circle wider than 0.01 degree, so every search is a point. Every answer is cached, which is what makes a
   repeat free.
4. Asks Horizons for the exact position at the middle of each exposure found, and keeps the exposures whose image
   footprint (IRSA gives it as a polygon) holds that position with 0.03 degree to spare (the sky ring needs the room).
5. Reads a small cutout (0.2 degree) of each exposure, centred on the predicted position, from NASA's public S3 copy of
   the archive (the cutouts are kept apart in `<cache>/follow/cutouts/`).
6. In each cutout adds up the light in two circles, **12.3 arcsec** and **36.9 arcsec** in radius (the body's distance
   from SPHEREx turns these into kilometres at the body: 3I/ATLAS in August was 2.7 au away, so 24,000 and 72,000 km),
   with the sky level taken from a ring 86 to 148 arcsec out. The 12.3 arcsec circle is the 12 arcsec radius the
   3I/ATLAS paper used. A comet is fuzzy, so the larger circle is there too.
7. Measures the same two things at 8 empty places on a ring 100 arcsec round the body. Their scatter is the noise,
   measured the same way as the body.
8. Measures the same sky place in up to 4 exposures of other days (same detector, taken when the body was elsewhere).
   A star at that place is still there on the other days. If most of them show a source and it is at least a fifth as
   bright as what was measured, the point is marked `star_in_the_way`.
9. Writes one point per exposure: time, detector, wavelength and bandwidth, brightness with error (3 per cent added in
   quadrature as the SPHEREx Explanatory Supplement does for the calibration), status (`ok`, `saturated`, `flagged`,
   `star_in_the_way`, `off_image`, `no_sky`, `not_fetched`), predicted magnitude, distances.

**Gas bands.** For each of water (2.62 to 2.86 micrometres), carbon dioxide (4.20 to 4.31) and carbon monoxide
(4.62 to 4.74) the excess is the mean of the channels inside the band minus a straight line fitted to the channels
beside it (2.40 to 2.58 and 2.90 to 3.05; 4.02 to 4.17 and 4.38 to 4.52; 4.45 to 4.58 and 4.80 to 4.95), weighted by
the errors, with the line's own error added (enlarged when the channels scatter more than their errors say). It is
done separately for each visit (a few days of observing). A band is called

- **detected** if the excess is at least 5 times its error **and** at least 3 times the scatter of the same
  arithmetic done at other places of the spectrum (the three windows slid along it, never touching the real band)
  **and** larger than every one of those other places, with at least four of them to compare with;
- **marginal** if it is at least 3 times its error but fails those tests, or there are too few other places to
  test it;
- **not seen** otherwise.

Nothing is called a detection because it is large compared with its own error: the error of one exposure is small, and
the real scatter between exposures (the comet changes, stars, calibration) is larger. When two bands are both
detected, `flux_ratio` gives their ratio of band-integrated excess: **a ratio of fluxes, not of production rates**.

The numbers below are measurements of what the exposures show. Where the word "seen" appears it means: measured, and
compared with the same measurement at empty places or in neighbouring channels.

## Proof 1: asteroid 4 Vesta (V 6 to 8, much too bright for most of SPHEREx's range)

![4 Vesta spectrum](comets/4_vesta_spectrum.png)

`python scripts/follow_body.py "4 Vesta" --strip 6`: 320 exposures contain Vesta's predicted position (8 more are too
close to an image edge), 312 were measured. **34 gave a measurement; 258 are saturated; 6 are flagged; 14 are off the
image.** Vesta is so bright that every exposure of detector 1 to 4 (0.75 to 3.8 micrometres) saturates, and
detectors 5 and 6 (3.8 to 5.0 micrometres) saturate in all 50 measurable exposures of June to August 2025 (V 6.5 to 7.4; 7 more are off the
image) and in 14 of 55 in July 2026 (V 7.7). The 34 measurements are all from 11 to 20 July 2026: 26 in detector 5 and 8 in detector 6.

What the spectrum shows (12.3 arcsec circle): 1.2 to 1.5 Jy at 3.8 to 4.4 micrometres (the scatter is Vesta's rotation),
1.6 to 1.7 Jy at 4.5 to 4.6, then **3.1 and 2.9 Jy at 4.96 and 5.0 micrometres**. That is what an asteroid should give at these wavelengths: sunlight it
reflects falls off with wavelength, its own heat takes over from about 4 micrometres and rises steeply. Rough check by
hand, not a calibration: a body of Vesta's size (radius 262 km) at 2.14 au from SPHEREx, as a 230 K black body, gives
about 2.5 Jy at 5 micrometres; 2.9 to 3.1 Jy corresponds to about 235 K. There is no gas band, as there should not be.

![Vesta in six exposures and the same sky place on other days](comets/4_vesta_strip.png)

The strip: top, Vesta at its predicted place in exposures of six different days (same date and wavelength in the
caption); bottom, the same sky place in an exposure of another day, with the same brightness stretch: nothing is
there.

Against what was measured before: `docs/smallbodies.md` measured 1.44 to 1.63 Jy at 4.2 to 4.4 micrometres on 16 July
2026 in a 15.4 arcsec circle. Here, on 16 July 2026, 4.23 to 4.30 micrometres, 12.3 arcsec circle: 1.57, 1.58, 1.52
Jy. Same data, a different circle and a different code path: the numbers agree.

**A warning that the Vesta result gives for free.** The gas-band arithmetic, run on Vesta's 34 points, reports a
carbon dioxide "excess" of 119 mJy, 4.2 times its error (marginal). Vesta has no gas. The "excess" is Vesta's own
brightness changing between exposures (it rotates every 5.3 hours, and its distance changed over the 9 days). This is
why a bump of a few times its error is never called a detection here, and why the rule above also asks for the
other-places test.

What it does not show: the sunlight part (below 3.8 micrometres) because every exposure there is saturated.

## Proof 2: interstellar comet 3I/ATLAS, against the SPHEREx team's own papers

![3I/ATLAS, each visit in its own colour](comets/3i_atlas_visits.png)

`python scripts/follow_body.py "3I/ATLAS" --strip 6` (Horizons knows it as C/2025 N1): 364 exposures contain it, 357
measured: **237 ok, 57 `star_in_the_way`, 57 flagged, 1 saturated, 5 off the image.** The fields it crossed in August
2025 are in the Milky Way's crowded Sagittarius, which is why so many points have a star in the way. The visits
(2025 August 6 to 15, December 8 to 9, December 14 to 15, 2026 March 17 to 23 and March 28 to April 6, besides 7 points
on 1 August) are the sets of exposures with enough points. Each colour above is one visit; the shaded bands are water, carbon dioxide and
carbon monoxide.

What the SPHEREx team published (searched: "SPHEREx 3I/ATLAS spectrum Lisse carbon dioxide coma water ice arXiv").
Lisse et al., "SPHEREx Pre-Perihelion Mapping of H2O, CO2, and CO in Interstellar Object 3I/ATLAS", arXiv:2512.07318
(ApJ Letters 2026): 1 to 15 August 2025, 12 arcsec radius, sky from an annulus 1 to 3 arcmin, gas emission fluxes of
58 (H2O at 2.7 to 2.8), 8610 (12CO2 at 4.25), 70 (13CO2) and 59 mJy (CO at 4.7) "corrected for 3I's relative position
to rhel = 1 au, robs = 1 au" by assuming flux goes as rhel^-2 robs^-2; Q(H2O) 3.2e26, Q(CO2) 1.6e27, Q(CO) 1.0e26
molecules per second. Lisse et al., arXiv:2601.06759: in December 2025 "the H2O gas-emission is 40x times brighter", CO
and CO2 comae circular, CO2 coma 3 arcmin in radius; (from a news summary of the same paper, not checked in the
paper itself: CO2 up about 33 per cent, CO about 20 times, CO/CO2 about 15-fold).

What this tool gets, 12.3 arcsec circle, August 6 to 15 visit (r 3.19 au, delta 2.70 au; scale factor
r^2 delta^2 = 74):

| Band | Measured here (mean excess over the channels in the band) | Scaled to 1 au the paper's way | Published | Verdict by the rules above |
|---|---|---|---|---|
| H2O 2.62 to 2.86 | 0.592 +- 0.051 mJy (11.6 times the error), 2 channels | 44 mJy | 58 mJy | marginal: other places of the spectrum give up to 36 times |
| CO2 4.20 to 4.31 | 20.4 +- 0.5 mJy (43.6 times), 4 channels | 1510 mJy | 8610 mJy | **detected**: 9 other places, the largest 9.5 times |
| CO 4.62 to 4.74 | 0.57 +- 0.16 mJy (3.5 times), 1 channel | 42 mJy | 59 mJy | marginal |

The highest single channel at 4.26 micrometres in August (14 August, 4.261 micrometres, 54.8 +- 1.7 mJy) scales to
3670 mJy, **0.43 of the published 8610 mJy**. H2O (peak channel 1.2 mJy at 2.66 micrometres, scaled 82) and CO (0.8 mJy at
4.63, scaled 65) are within 40 and 10 per cent of the published values; carbon dioxide is 2.3 times lower. **So the
tool finds a bump at each of the three places the paper reports, with water and carbon monoxide near the published
values; but under this project's strict rule only carbon dioxide is a detection in August (water and carbon monoxide
are marginal: the channels are few, and the arithmetic gives equally large numbers at other places), and the carbon
dioxide absolute number is 2.3 times lower than published.** What was checked: moving the sky ring from 86 to 148
arcsec out to 221 to 295 arcsec changes the 4.26 micrometre flux by less than 3 per cent (so the sky ring being inside
the coma does not explain it); the circle is the paper's radius; the cutouts' flux scale is the archive's (the project
compared field stars with 2MASS, `scripts/check_flux_scale.py`). What was not checked and could explain it: the
paper's early SPHEREx processing against the archive's current one (the images here are processed version `l2b-v27`,
2026), what exactly the paper's "mJy" is (peak, band mean or best frame), its simulated-field subtraction, and its
"effective aperture" that depends on position in the field.

The change between visits (large circle, 36.9 arcsec, so the whole inner coma is in it):

| | Aug 6 to 15 | Dec 14 to 15 | Change as measured | The paper |
|---|---|---|---|---|
| CO2 4.26 | 34.6 +- 1.2 mJy | 477 +- 13 mJy | x13.8 (x2.8 after scaling by r^2 delta^2) | about x1.3 |
| CO 4.67 | 3.0 +- 0.6 mJy (marginal) | 89.9 +- 4.0 mJy (detected) | x30 (x6 after scaling) | about x20 |
| H2O 2.7 (small circle; Dec 8 to 9; marginal in both, too few other places to test) | 0.59 mJy | 25.8 +- 0.7 mJy | x44 (x8 scaled) | x40 |

The pattern is the published one: water brightens most, carbon monoxide much more than carbon dioxide. The
magnitudes are the published order but not equal (carbon dioxide rose by more here than the 33 per cent quoted, and
the carbon monoxide rise is smaller). The ratio of band-integrated excess CO2 to CO in the December 14 to 15 visit is
**4.9 +- 0.2** (a ratio of fluxes, not of production rates).

One more number, not a result: in the 2026 March 17 to 23 visit (r = 5.2 au) the carbon dioxide band is 5.2 times its
error in the large circle (2.0 +- 0.4 mJy; 3.8 times in the small one), and only one other place could be tested, so it
is marginal. I did not find a report of SPHEREx 3I/ATLAS data from March 2026 (one web search).

![3I/ATLAS in six exposures](comets/3i_atlas_strip.png)

(The comet at its predicted place on six dates, and nothing at the same sky place on other days.)

## Pluto (and Charon), through the survey

The challenge text says Pluto was found by comparing two images in which a point of light had shifted. SPHEREx
exposures show the same thing for Pluto.

![Pluto in the same patch of sky on six days](comets/pluto_moving.png)

Six exposures of one fixed patch of sky (200 arcsec across, centred on the mean predicted place, one exposure a day,
the one in which Pluto stood out most), 25 April to 2 May 2026. The red ring is Horizons' predicted place of Pluto
(14 arcsec radius; Pluto is inside it every time); the stars stay where they are and the ring moves. Pluto moved
**113 arcsec** (97 arcsec in the right-ascension direction, 58 arcsec in declination) in those 7 days (16 arcsec a
day). RA 308.52308, Dec -22.89059 on 25 April (0.90 micrometre, 76 times the noise) to RA 308.55232, Dec -22.90679 on 2
May (2.00 micrometres, 130 times the noise). Between the October 2025 visit (RA 304.14) and the April 2026 visit
(RA 308.52) it moved 4.4 degrees of right ascension.

![Pluto at its predicted place and the same place on other days](comets/pluto_strip.png)

How many exposures: **229 contain Pluto, 224 were measured: 175 ok, 37 flagged, 9 with a star in the way, 3 off the
image.** (Pluto and Charon are under 1 arcsec apart on the sky, far less than one pixel, so everything here is Pluto and
Charon measured together.) Pluto is at V 14.5, so each exposure shows it at 7 to 10 mJy near 1 micrometre. The
second picture's top row is each exposure centred on Pluto; the bottom row is the same sky place on another day, same
stretch.

![Pluto spectrum](comets/pluto_spectrum.png)

The spectrum (12.3 arcsec circle, all 175 measurements from the October 2025 and April to May 2026 visits and the
smaller ones): about 7 to 10 mJy at 0.8 to 1.3 micrometres, falling to 1 to 2 mJy at 2.3 and 0.5 to 1 mJy beyond 3.
**Methane ice**, which dominates Pluto's surface, absorbs at 1.7, 2.3 and 3.3 micrometres. Measured against
neighbouring channels, same rules as for gas (the dip's depth below a line through the channels beside it, the same
arithmetic at other places in the spectrum):

| Methane band | Window / beside it (micrometres) | Depth below the neighbours | Verdict |
|---|---|---|---|
| 1.7 | 1.64 to 1.74 / 1.52 to 1.61 and 1.78 to 1.88 | not measurable: one channel on the short side | no measurement |
| 2.3 | 2.26 to 2.36 / 2.12 to 2.22 and 2.42 to 2.54 | 0.83 +- 0.12 mJy of about 2.2 (7.0 times the error) | **marginal**: 7.0 times its error, but other places scatter as much (largest dip elsewhere 5.2 times, robust scatter 3.5, so 10 needed) |
| 3.3 | 3.20 to 3.40 / 2.98 to 3.14 and 3.45 to 3.62 | 0.06 +- 0.32 mJy (0.2 times) | **no dip seen** |

So: **no methane dip is established by these rules.** The curve has the broad shape of a methane-ice-rich surface
(a fall from 1 to 2 micrometres with a trough at about 2.2 to 2.35), and the 2.3 micrometre trough is 7 times its
error, but the channels scatter far more than their errors (reduced chi-squared 11 to 100: Pluto rotates every 6.4
days and changes by tens of per cent, the 12.3 arcsec circle in this crowded field catches stars, and each channel
comes from a different exposure on a different day), so a trough that size can also arise at other places (other places of the spectrum give dips of up to 5.2 times
the error and bumps of up to 7.7 times). I did not
check the published Pluto spectrum for these channels; the band positions are the ones given in the brief. No gas band is
seen for Pluto: water, carbon dioxide and carbon monoxide are all "not seen" (0.0 to 1.0 times their error).

Searched: "SPHEREx Pluto spectrum methane ice 0.75-5 micron observation": no SPHEREx paper on Pluto came back. That
does not show that none exists; it is one web search.

## Looking where it may not have been looked: the comets

**How the bodies were chosen.** For each candidate Horizons gave the path seen from SPHEREx; I kept the days inside the
SPHEREx elongation range and read off the brightest predicted total magnitude (Horizons' formula) in that range. The
brief's threshold was "about 14 or brighter":

| Body | Brightest predicted, inside SPHEREx's range | What was done |
|---|---|---|
| C/2025 R2 (SWAN) | 10.8 (19 Oct 2025, 0.26 au from SPHEREx, 776 arcsec/h) | followed |
| C/2025 K1 (ATLAS) | 12.5 (22 Nov 2025; main body, Horizons record 90004925, not the fragments K1-B, -C, -D) | followed |
| 10P/Tempel 2 | 13.1 (25 Jun 2026) | followed (all 319 exposures) |
| C/2025 T1 | 13.4 (11 Nov 2025) | followed |
| 24P/Schaumasse | 14.1 (6 Jan 2026) | followed |
| C/2025 A6 (Lemmon) | 14.4 (13 Feb 2026) | followed |
| 29P/Schwassmann-Wachmann | 17.4 (formula; it outbursts) | followed because it is known for carbon monoxide |
| 240P/NEAT | 14.6 (24 Dec 2025; Horizons needs record 90001213) | not followed: fainter than the threshold |
| C/2023 A3 | 14.7 (1 May 2025) | not followed: fainter, and at the very start |
| C/2024 E1 (Wierzchos) | 15.4 (12 Sep 2025) | not followed: no day at 14.5 or brighter in range |
| C/2024 G3 15.0, 88P 15.4, C/2026 A1 17.2, C/2025 F2 17.1, C/2025 J1 17.1, 12P/Pons-Brooks 18.3, C/2025 L2 17.9, C/2025 R3 17.3, 13P/Olbers 20.4, 41P 22.3, C/2024 S1 22.3, C/2025 D1 20.3, C/2025 V1 19.1 | all fainter than 15 | not followed |
| 3I/ATLAS (C/2025 N1) | 15.2 | followed: it is the proof above (Horizons' formula is far from what SPHEREx saw) |

Horizons did not take "C/2025 K1" and "240P" at first: it lists several records with those designations and asks for a
record number (`COMMANDS` in `backend/follow.py`).

**The SPHEREx exposures of a comet are not at the time it was brightest.** C/2025 T1 was 13.4 on 11 November 2025, and its
SPHEREx exposures are from May to September 2026 at r 2.6 to 4.1 au; C/2025 A6 was at 4th magnitude in October and November
2025, at an elongation under 70 degrees, and has exposures only from 22 February 2026 (r 2.1 au) onwards.

### Results (the best visit for each band, large circle 36.9 arcsec; "detected / marginal / not seen" by the rules above)

| Body | Exposures containing it | Measured | Usable | Predicted mag | H2O 2.7 | CO2 4.26 | CO 4.67 |
|---|---|---|---|---|---|---|---|
| 10P | 319 | 313 | 178 | 13.1 to 20.1 | -5.01 +- 13.39 mJy (-0.4x), not seen, visit 2026-03-13 (1 in band) | +56.94 +- 1.48 mJy (+38.5x), marginal, visit 2026-03-13 (3 in band) | +11.22 +- 5.24 mJy (+2.1x), not seen, visit 2026-05-09 (1 in band) |
| 24P | 823 | 786 | 520 | 14.1 to 20.7 | +3.64 +- 0.20 mJy (+18.3x), marginal, visit 2026-06-26 (3 in band) | +19.42 +- 1.32 mJy (+14.8x), marginal, visit 2025-09-18 (7 in band) | +5.30 +- 6.21 mJy (+0.9x), not seen, visit 2025-12-13 (6 in band) |
| 29P | 178 | 173 | 150 | 17.4 to 17.8 | no usable channels in the band | +16.82 +- 0.46 mJy (+36.4x), detected, visit 2025-12-14 (6 in band) | +47.21 +- 1.08 mJy (+43.8x), detected, visit 2025-12-14 (4 in band) |
| 3I/ATLAS | 364 | 357 | 237 | 15.2 to 25.8 | +68.72 +- 2.03 mJy (+33.9x), marginal, visit 2025-12-08 (4 in band) | +477.29 +- 12.66 mJy (+37.7x), detected, visit 2025-12-14 (2 in band) | +89.93 +- 3.95 mJy (+22.7x), detected, visit 2025-12-14 (3 in band) |
| 4 Vesta | 320 | 312 | 34 | 6.2 to 8.0 | no usable channels in the band | +140.45 +- 31.91 mJy (+4.4x), marginal, visit 2026-07-11 (5 in band) | no usable channels in the band |
| C/2025 A6 | 222 | 221 | 127 | 14.4 to 18.7 | +1.00 +- 28.70 mJy (+0.0x), not seen, visit 2026-02-22 (1 in band) | no usable channels in the band | +5.19 +- 0.76 mJy (+6.8x), marginal, visit 2026-05-19 (1 in band) |
| C/2025 K1 | 434 | 423 | 285 | 12.5 to 20.8 | +2.45 +- 0.15 mJy (+16.4x), marginal, visit 2025-12-21 (3 in band) | +0.26 +- 0.44 mJy (+0.6x), not seen, visit 2025-05-25 (1 in band) | -0.10 +- 0.42 mJy (-0.2x), not seen, visit 2025-05-25 (3 in band) |
| C/2025 R2 | 331 | 296 | 202 | 10.8 to 24.4 | -1.47 +- 0.49 mJy (-3.0x), not seen, visit 2026-09-07 (2 in band) | +0.93 +- 0.35 mJy (+2.7x), not seen, visit 2026-09-07 (3 in band) | -0.57 +- 0.66 mJy (-0.9x), not seen, visit 2026-09-07 (2 in band) |
| C/2025 T1 | 156 | 154 | 91 | 13.4 to 27.4 | -0.81 +- 0.41 mJy (-2.0x), not seen, visit 2026-08-20 (1 in band) | no usable channels in the band | -0.41 +- 0.48 mJy (-0.9x), not seen, visit 2026-08-20 (2 in band) |
| Chiron | 373 | 367 | 267 | 18.3 to 18.6 | +0.30 +- 0.14 mJy (+2.2x), not seen, visit 2025-12-31 (3 in band) | -0.86 +- 0.64 mJy (-1.3x), not seen, visit 2025-12-31 (1 in band) | +0.69 +- 0.37 mJy (+1.9x), not seen, visit 2025-12-31 (7 in band) |
| Eris | 336 | 329 | 277 | 18.6 to 18.7 | -0.04 +- 0.13 mJy (-0.3x), not seen, visit 2026-07-11 (3 in band) | -0.17 +- 0.32 mJy (-0.5x), not seen, visit 2025-07-19 (2 in band) | +0.80 +- 0.55 mJy (+1.5x), not seen, visit 2026-01-03 (2 in band) |
| Haumea | 349 | 346 | 278 | 17.2 to 17.3 | +0.33 +- 0.16 mJy (+2.1x), not seen, visit 2025-06-20 (2 in band) | +0.13 +- 0.43 mJy (+0.3x), not seen, visit 2026-01-16 (1 in band) | +0.09 +- 0.32 mJy (+0.3x), not seen, visit 2025-06-20 (3 in band) |
| Makemake | 362 | 358 | 270 | 17.1 to 17.1 | +0.54 +- 0.89 mJy (+0.6x), not seen, visit 2026-05-30 (4 in band) | +0.41 +- 0.26 mJy (+1.6x), not seen, visit 2026-05-30 (3 in band) | +0.30 +- 0.42 mJy (+0.7x), not seen, visit 2025-05-30 (2 in band) |
| Pluto | 229 | 224 | 175 | 14.5 to 14.6 | +0.38 +- 0.39 mJy (+1.0x), not seen, visit 2026-04-25 (3 in band) | +0.36 +- 0.47 mJy (+0.8x), not seen, visit 2025-10-03 (1 in band) | -1.33 +- 0.69 mJy (-1.9x), not seen, visit 2026-04-25 (1 in band) |

Nights on which the per-sequence scan reached 5 times its error on a band:

| Body | H2O | CO2 | CO |
|---|---|---|---|
| 10P | 2026-03-05 | 2026-03-22, 2026-03-24 | none |
| 24P | 2025-09-19, 2026-07-07 | none | none |
| 29P | none | 2025-12-16, 2025-12-18 | 2025-12-21 |
| 3I/ATLAS | 2025-12-08 | 2025-12-14 | none |
| 4 Vesta | none | none | none |
| C/2025 A6 | none | 2026-06-16 | none |
| C/2025 K1 | 2026-01-02, 2026-01-07 | none | none |
| C/2025 R2 | 2026-01-07 | 2026-01-02 | none |
| C/2025 T1 | none | 2026-05-18 | none |
| Chiron | none | none | 2026-07-26 |
| Eris | none | none | none |
| Haumea | none | none | none |
| Makemake | none | none | none |
| Pluto | none | none | none |

The first table gives, for each band, the visit with the largest excess over its error. When a band has no channel on one side of it in a
visit the rule cannot be applied and the cell says "no usable channels": that is the case for the best carbon dioxide results of
C/2025 R2 and C/2025 A6, which are described below from the comparison of channels taken minutes apart (second table: the nights on
which such a comparison reached 5 times its error; these have no control windows of their own, so they are not detections by
the rule above).

### What stands out

**C/2025 R2 (SWAN): a carbon dioxide band in December 2025 and January 2026.** In exposures of detector 5 on three
separate dates the comet is bright at 4.24 to 4.29 micrometres and faint in the channels next to them (12.3 arcsec circle):

| Date (UTC) | 4.17 to 4.21 | 4.215 to 4.25 | 4.25 to 4.29 | 4.33 to 4.37 | r, delta (au) |
|---|---|---|---|---|---|
| 22 Dec 2025 | | | 9.8 +- 0.4 mJy (at 4.293) | 2.2 (4.329), 1.4 (4.366) | 1.99, 1.51 |
| 25 Dec 2025 | | 4.0 +- 0.2 (4.215) | 13.1 +- 0.5 (4.252), 9.9 +- 0.4 (4.288) | | 2.04, 1.59 |
| 2 Jan 2026 | 0.8 (4.168), 1.5 (4.204) | 8.5 +- 0.3 (4.240) | 8.9 +- 0.3 (4.276) | | 2.15, 1.79 |

In the large circle: 35.0, 34.9 and 25.8 mJy at the strongest channel. Every one is `ok`, 39 to 172 times the noise at
empty places beside it, and the same sky place in 2 to 4 exposures of other days shows nothing (on 2 January one of two shows
a source of 0.12 to 0.15 mJy). The per-sequence scan gives +7.6 +- 0.4 mJy (17.5 times its error; 8.6 times in the large
circle) on 2 January, with 55 windows away from the gas bands, 3 of which reach 5 times (5 per cent). In September 2026
(r = 5.1 au) the same channels are 0.0 to 0.35 mJy: the band is gone.

![C/2025 R2 on 25 December 2025: three consecutive exposures of detector 5 at 4.215, 4.252 and 4.288 micrometres, the same stretch](comets/c_2025_r2_sequence_20251225T19_D5.png)

The coma, a glow round the predicted place, brightens in the 4.25 micrometre exposure and fades in the next (other dates:
`docs/comets/c_2025_r2_sequence_20251222T16_D5.png` and `..._20260102T10_D5.png`).

What it is and is not: a feature 0.05 micrometre wide at the place of the carbon dioxide band, in a comet, on three
separate dates, absent at r = 5 au, and seen as a glow in the images, not a point. Checks that tried to kill it: a star
(the other-day check, and the glow is extended); the detector (Vesta and Pluto in detector 5 are smooth through 4.26
micrometres); a one-day fluke (three dates); dust (it is narrow). The visit rule cannot call it "detected" (the 4.38 to
4.52 side is missing in these exposures; the rule needs both sides), so the table says "not enough exposures" for it and
this paragraph rests on the comparison of channels taken minutes apart, which has no control windows of its own at this
wavelength. **What would confirm it:** the same band in the SPHEREx team's own spectra of these exposures; the shape
across 4.1 to 4.45 micrometres from a sequence that covers the whole band (these step 0.036 micrometre and reach 3
channels); JWST or ground-based infrared spectra of C/2025 R2 of the same weeks. **Searched for:** "comet C/2025 R2 (SWAN)
CO2 carbon dioxide infrared spectroscopy JWST OR SPHEREx OR NEOWISE detection": no report of a carbon dioxide detection
for it came back (one web search; only a ground-based optical spectrum of C2 and NH2 from 18 October 2025). That does not
show it is unreported.

**C/2025 A6 (Lemmon): carbon dioxide at 3.5 au, and a carbon monoxide hint.** On 11 June 2026 detector 5 gives 15.4 +- 0.5
mJy at 4.261 micrometres, 3.5 at 4.297 and 0.6 at 4.334; on 16 June 7.9 +- 0.3 and 10.7 +- 0.4 mJy at 4.236 and 4.273
with 0.5 at 4.20 (r 3.48 to 3.55 au, delta 3.2 to 3.3 au; large circle 40 and 31 mJy). The 16 June scan is +8.8 +- 0.25 mJy
(34.8 times; large circle 27.9, 25.9 times), 28 windows away from the gas bands, none at 5 times. On 23 May 2026
detector 6 reads 2.2 and 2.5 mJy at 4.645 and 4.679 micrometres against 0.6 and 0.9 at 4.58 and 4.61: by the visit rule
the carbon monoxide band is 13.5 times its error in the small circle (1.9 +- 0.14 mJy), **marginal** (3 other places
only). Water: not seen. **Searched for:** "comet C/2025 A6 Lemmon carbon dioxide CO2 4.3 micron detected outbound
2026": nothing on carbon dioxide (only visual magnitudes). What would confirm: the same two features in the SPHEREx
team's spectra; the whole spectrum of one visit.

**24P/Schaumasse: carbon dioxide going in and coming out.** 5.6 +- 0.25 mJy at 4.247 micrometres on 20 September 2025
(0.7 at 4.211, 3.3 at 4.284) and 4.2 at 4.284 on 27 September (r 1.8 au, delta 1.5 au), and **9.6 +- 0.3 mJy at 4.246
micrometres on 1 July 2026** (0.4 at 4.210, 6.5 at 4.282, 0.7 at 4.319; r 2.35, delta 1.71). The 12.3 arcsec circle holds
more carbon dioxide emission at 2.35 au going out than at 1.8 au coming in, although the comet is farther from the Sun and
from SPHEREx; scaled by r^2 delta^2 as the 3I/ATLAS paper does, the later one is 3.4 times larger (that scaling is an
assumption, and the circle is 13,300 to 13,800 km in radius in September, 15,300 in July). By the visit rule: 18 September to 3
October, marginal (+2.9 +- 0.1 mJy, 27 times; only 3 controls); 26 June to 7 July 2026, **detected** (+5.1 +- 0.2 mJy,
29.9 times; 6 other places, the largest 3.4; large circle +12.3 +- 1.2 mJy, detected). On 24 September 2025 the same place
has a star in the way (3 of 3 other-day exposures, median 1.06 mJy): left out. What would confirm a rise: the same
aperture in kilometres, the SPHEREx team's own photometry. No web search was made for 24P.

**C/2025 T1: a faint carbon dioxide line.** 2.4 +- 0.15 mJy at 4.249 micrometres and 1.4 +- 0.13 at 4.288 on 18 May 2026
against 0.1 mJy at 4.14 to 4.18 and 4.33 to 4.36; one night, r 2.67 au. Scan: +2.25 +- 0.17 mJy (13 times; large circle
6.1, 12.5 times). Too little to say more. No web search made.

**C/2025 K1 (ATLAS): water, and no carbon dioxide.** For 21 December 2025 to 5 January 2026 (r 1.8 au, delta 1.2 au) the
water band is **detected** in the small circle (+0.57 +- 0.05 mJy, 11.8 times; 7 other places, the largest 7.5), the
carbon dioxide band is 0.005 +- 0.133 mJy (0.0 times) and carbon monoxide -0.36 +- 0.14 mJy. The three channels in the
carbon dioxide band are as faint as their neighbours, where C/2025 R2 at a similar distance gave 8 to 13 mJy in one
channel. The comet was breaking up (HST imaged at least five fragments; "Sequential Fragmentation of C/2025 K1 (ATLAS)",
arXiv:2511.19707, which I did not read beyond the search result), and the 12.3 arcsec circle may hold only one piece.
**Searched for:** "C/2025 K1 ATLAS comet carbon dioxide OR CO2 infrared observations fragmentation 2025 2026": JWST
program 12488 is described as aimed at the volatile content of the fragments and I found no published carbon dioxide
abundance; a Wikipedia mirror's title calls the comet "deeply depleted" in carbon-bearing species, but I could not see
its text, so I do not rely on it. What would confirm the absence: a deeper limit in the same channels from stacking,
and the same band in the other fragments.

**29P/Schwassmann-Wachmann: carbon monoxide and carbon dioxide, after an outburst.** 14 to 23 December 2025 (r 6.3 au): carbon
monoxide **detected** at +13.7 +- 0.34 mJy (40 times; large circle 47.2 +- 1.1 mJy, 44 times; the largest other place
15) and carbon dioxide **detected** at +4.3 +- 0.19 mJy (23 times; large circle 16.8 +- 0.5). The ratio of band-integrated
excess, carbon dioxide to carbon monoxide, is **0.33 +- 0.01** in the large circle (0.29 +- 0.01 in the small): a ratio of
fluxes, not of production rates (the errors are formal). The 14 to 23 December exposures are 2.3 times brighter at 1
micrometre than those of 8 December (40 against 17 mJy in the large circle). Wikipedia lists outbursts of 29P on 4 and 11
December 2025 (a secondary source, one web search): SPHEREx's 8 December visit follows the first, its 14 to 23 December visit
the second. This is **not new**: Faggi et al., JWST NIRSpec of 20 February 2023 (Nature Astronomy 2024), reported carbon
monoxide and carbon dioxide in 29P. It shows that the tool finds both gases in a comet 6 au away.

### 10P, the dwarf planets and Chiron

**10P/Tempel 2: carbon dioxide in March 2026.** On 22 March 2026 detector 5 reads 2.8, **36.1 +- 1.1** and **28.4 +- 0.9** mJy
at 4.208, 4.244 and 4.281 micrometres (2.0 at 4.172), and on 24 March 7.4 mJy at 4.304 (r 1.94 au, delta 1.6 au). The
scan gives +29.9 +- 0.8 mJy (36 times; large circle +81 +- 3 mJy, 26 times) with 37 windows away from the gas bands, 1
at +5 times and 2 at -5 times. The visit rule calls it **marginal** (+16.3 +- 0.4 mJy, 41.6 times, in the 13 to 27 March
visit: only 3 other places could be tested). A fixed source of about 1 mJy lies at that sky place in the 3 exposures of
other days (a star), 3 per cent of the flux: it does not make the band, but it is in the number. The comet was run on all
319 exposures (the 350 limit given is above that count). Searched: nothing made for 10P.

**Makemake, Haumea, Chiron (and Eris, below): stacking was not done.** These bodies are V 17 to 19 and far from the Sun, so
they show no gas bands and only a surface spectrum. For each, `follow_body` measured every exposure on its own, and the
claim here is only about individual exposures, each compared with the scatter of the same measurement at 8 empty places
beside it ("times the noise"). A stack along the body's path, with channels of similar wavelength together, was not
built.

| Body | V (Horizons) | Exposures (contain, usable) | Individual measurements at 5 times the noise or more, by wavelength |
|---|---|---|---|
| Makemake | 17.1 | 362, 270 | 34 of 45 at 0.75 to 1.1 micrometres (median 0.61 mJy, noise 0.07); 23 of 44 at 1.1 to 1.6; 3 of 43 at 1.6 to 2.4; 5 of 46 at 2.4 to 3.8; 3 of 90 at 3.8 to 5.0 |
| Haumea | 17.2 | 349, 278 | 33 of 40 at 0.75 to 1.1 (median 0.55 mJy); 29 of 43 at 1.1 to 1.6; 15 of 49 at 1.6 to 2.4; 3 of 43 at 2.4 to 3.8; 0 of 83 at 3.8 to 5.0 |
| Chiron | 18.3 to 18.6 | 373, 267 | 11 of 40 at 0.75 to 1.1 (median 0.24 mJy); 6 of 36 at 1.1 to 1.6; 7 of 53 at 1.6 to 2.4; 1 of 36 at 2.4 to 3.8; 6 of 89 at 3.8 to 5.0 |
| Eris | 18.6 to 18.7 | 336, 277 | 7 of 42 at 0.75 to 1.1 (median 0.17 mJy, noise 0.07); 3 of 38 at 1.1 to 1.6; 2 of 48 at 1.6 to 2.4; 1 of 40 at 2.4 to 3.8; 2 of 92 at 3.8 to 5.0: **15 of 260 in all, so only the shortest wavelengths are measured at all** |

![Makemake](comets/makemake_spectrum.png)

![Haumea](comets/haumea_spectrum.png)

**Makemake** and **Haumea** are measured, exposure by exposure, at 0.75 to about 2.4 micrometres, where most
measurements stand 5 or more times above the noise, and fade into it beyond 2.4. Makemake's spectrum has peaks at about 0.8,
1.2 to 1.3, 1.5 and 1.9 to 2.0 micrometres and dips between them, the pattern of a surface covered in methane ice
(Pluto's is the same kind); Haumea's falls steadily from 0.55 mJy at 0.75 micrometre to 0.1 to 0.2 mJy near 2.0 and about
zero at 2.7 to 3.5 micrometres, the shape of a water-ice surface. I did not run the dip test on these. Their gas-band
"results" in the table are not gas: they have no coma at 50 au, and the arithmetic reads the surface spectrum (for
Makemake the water window gets +0.17 +- 0.03 mJy, "detected" by the rule, in the 30 May to 13 June 2026 visit: the
bright channels between methane bands beside it. This is a false alarm of the method and a warning that the rule is
only meant for comets). Points that have a fixed source at the same sky place on other days are drawn as open circles.

Makemake across the sky: `docs/comets/makemake_moving.png` (the same patch of sky on four days, the ring is the
predicted place; Makemake moved 481 arcsec in 14 days, so the field loses it in the later panels).

![Makemake in one patch of sky on four days](comets/makemake_moving.png)

**Chiron (95P): one exposure at the carbon monoxide wavelength.** On 26 July 2026, 19:57 UTC, detector 6 at 4.685
micrometres reads **2.05 +- 0.19 mJy** at Chiron's predicted place (14 times the noise at empty places beside it; the
same place in 4 exposures of other days shows nothing), while the channels around it read 0.36 (4.651), 0.18 (4.719), 0.0
(4.753) and the others about 0.2 or less. The visit rule calls the carbon monoxide band **detected** in that visit (+0.75
+- 0.14 mJy, 5.3 times, 8 other places, the largest 1.6); the January 2026 visit (7 channels in the band) gives
-0.001 +- 0.09 mJy. The picture shows a faint star-like source at the centre in the 4.685 micrometre exposure and nothing in
the 4.719 micrometre exposure two minutes later (`docs/comets/chiron_sequence_20260726T195_D6.png`). This is **one exposure**,
one date, and not established: a narrow feature at the carbon monoxide wavelength in a body with known carbon monoxide
production is the expected thing, but a single point-like brightening at the predicted place that is gone two minutes
later could also be an instrumental or chance event; I have no second exposure that shows it. What would confirm it: the
band in other exposures of the same visit at neighbouring wavelengths (none in this one), a repeat in the next SPHEREx
visit, the published Chiron carbon monoxide production. Not searched in the literature.

![Chiron, two consecutive exposures of detector 6: 4.685 and 4.719 micrometres](comets/chiron_sequence_20260726T195_D6.png)



## Limits (read before relying on any number)

- **The measuring circle.** A comet's coma is bigger than the 12.3 arcsec circle (3I/ATLAS' carbon dioxide coma
  reaches 3 arcmin), so the small circle holds only the inner part, and the 36.9 arcsec circle holds more but also more
  stars. The sky ring (86 to 148 arcsec) lies inside such a coma, so it takes some of the coma away with the sky; for
  3I/ATLAS moving it to 221 to 295 arcsec changed the 4.26 micrometre flux by less than 3 per cent, but for a brighter
  or closer comet it could matter. In kilometres at the body the circles are 12.3 x 725 x delta km and 36.9 x 725 x
  delta km (delta in au): every point in the JSON files carries `radius_small_km` and `radius_large_km`.
- **Saturation.** A body bright enough to saturate pixels in the circle is given no number (Vesta: 258 of 312
  exposures; every exposure at 0.75 to 3.8 micrometres). Nothing is made up for them.
- **Stars in the way.** The check measures the same sky place in up to 4 exposures of other days of the same
  detector. A star that is faint at the wavelength of those exposures but bright at the body's (or the reverse) is
  not caught; a body that sits on a bright star in all exposures is `star_in_the_way`, but whether the star's flux can be
  taken away, I did not try. In crowded fields (3I/ATLAS in August 2025, Pluto) this removes 4 to 17 per cent of
  the exposures.
- **Calibration features.** The six detectors meet at 1.09, 1.63, 2.42, 3.82 and 4.42 micrometres. A step in
  the calibration between two detectors would put a false bump or dip there. The carbon dioxide continuum (4.02 to
  4.52) spans the boundary between detectors 5 and 6 at 4.42; I did not test for a step there beyond the other-places
  test, and I did not check the SPHEREx Explanatory Supplement for channels with known problems.
- **Time changes between the exposures of a "spectrum".** Each channel of a spectrum comes from a different exposure
  at a different time. A rotating body (Vesta 5.3 hours, Pluto 6.4 days) or a comet that brightens or outbursts changes
  between them. The gas-band arithmetic is done within a visit (a few days) to limit this, and its other-places test
  is what shows the remaining scatter; the per-night scan (`scan_sequences`) compares channels taken within 15 minutes
  of each other.
- **Fast bodies.** A body moving faster than about 300 arcsec an hour (C/2025 R2 at its closest, 776 arcsec an hour;
  C/2025 K1, 630) moves 4 pixels during one 113-second exposure: it is smeared along its path beyond the 12.3 arcsec
  circle, and only the large circle is dependable. The exposure search looks at the two ends of every stretch of
  at most 0.7 degree, so a body that crosses an image between the two ends could be missed for such a fast body.
- **Too close to the Sun.** SPHEREx observed 80 to 128 degrees from the Sun in the lists measured; a body outside 70
  to 140 degrees is not searched for. C/2025 A6 (Lemmon) was at 4 magnitude in October and November 2025 but at
  elongation under 70 degrees: SPHEREx did not observe it then.
- **Predicted magnitudes.** The predicted magnitude is Horizons' formula; for a comet it can be off by several
  magnitudes (3I/ATLAS "15 to 26"; it was about 100 times brighter than a plain formula would say in December). It
  is only used to choose bodies to look at.
- **Pluto and Charon** are measured together. A body fainter than about V 17 gives one-exposure measurements too
  noisy to use (see Makemake and the others below).
- **Archive coverage.** Only public SPHEREx exposures: the later data are released in batches. Exposures newer than
  the archive's last release do not exist for this tool.
- **Network.** The first run of a body takes 10 to 30 minutes (hundreds of IRSA searches and cutouts); the second takes
  seconds. If JPL or IRSA cannot be reached the run stops with the reason, and nothing is filled in.

## Repeat any of it

```
.venv/bin/python scripts/follow_body.py "C/2025 R2" --strip 6
.venv/bin/python scripts/follow_body.py Pluto --strip 6 --moving 6
.venv/bin/python scripts/follow_body.py "C/2025 R2" --sequence "2025-12-25T19:@5"
.venv/bin/python scripts/comets_table.py
```

Needs the project's Python environment and the network the first time; `SPHEREX_CACHE_DIR` points to the cache (the
cutouts and answers of this feature are in its `follow/` folder: about 2 GB for everything in this document).
Tests: `pytest tests/test_follow.py` (from saved real JPL and IRSA answers and real measured points in
`tests/data/follow/`; no network).

## What is not done, or not verified

- The web endpoint (`/api/follow?name=`) and the panel "Follow a comet or asteroid" in the app were **not built**: the
  measurements and their write-up came first, and a first run of a body takes 10 to 30 minutes, which would need the
  background-job route of `backend/jobs.py`. `backend/app.py` and `frontend/src/App.tsx` are untouched.
- Stacking of faint bodies along their own path (Eris, Chiron, and the longer wavelengths of Makemake and Haumea) was not
  built. Only single exposures are claimed.
- 3I/ATLAS's carbon dioxide absolute flux is 2.3 times lower than the paper's; the reason is not found (see above).
- Calibration features of SPHEREx's channels were not checked beyond the other-places test; the detector boundaries at
  1.09, 1.63, 2.42, 3.82 and 4.42 micrometres are possible places for steps.
- None of the "stands out" results was compared with a published spectrum of the same body; the web searches were one each,
  written beside each result. No search at all was made for 24P, C/2025 T1, 10P and Chiron, and none for the dwarf planets.
- Most results from a single night rest on the comparison of channels taken minutes apart, which has no control windows of
  its own at that scale.
- The 29P and 10P runs passed `--max 250` and `--max 350`; both numbers were above the count found, so every exposure was
  measured. Runs of other bodies: no limit.
- Horizons' magnitude for a comet is a formula, and the SPHEREx exposures are not at the time of the comet's peak.

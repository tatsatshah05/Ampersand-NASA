# A sweep of the Milky Way's plane for infrared sources that newly appeared

Written 2026-11-14 for teammates who are not astronomers. Everything below was measured on real SPHEREx
images with the code in `backend/sweep.py`; nothing was simulated, injected or filled in. The numbers
come from `scripts/sweep_plane.py --summary` (saved as `docs/sweep/summary.json`) and the per-tile files
it writes. Pictures are in `docs/sweep/`.

**Read this first.** The sweep found three sources that appear in 2025 to 2026, that are in none of the
catalogues we asked, and that we found in no report. They are **candidates**: sources that appear in 2026
and that we found in no catalogue or report we checked. That is not the same as new, and it is not
confirmed. A person has to look (see "What would confirm it"). The sweep also recovered two known novae
without being told where they were, which is the evidence that the method works.

## Why this is the one place a newly appeared object can be found

A star or planet that was always there is in deeper catalogues than SPHEREx's. A thing that *changed* is
different, and an eruption hidden behind the dust of the Milky Way's plane is invisible to optical
surveys: the dust blocks visible light and glows in the infrared. Between 2010 and August 2024 the
NEOWISE telescope watched the whole infrared sky twice a year. It stopped in August 2024. SPHEREx is now the
only telescope watching the whole infrared sky, and it has seen each part of the plane three times
(August to September 2025, February to April 2026, August to September 2026). So a source that is bright in
one SPHEREx visit and absent in another, in a place where no catalogue lists anything that bright, is the
honest route to "something nobody has reported". Most such sources are ordinary variable stars or
measurement artefacts, which is why the method is mostly about killing those.

## The method in plain words

For each *tile* (a patch of the plane about 3 by 2.5 degrees):

1. **Choose images.** SPHEREx's detector 6 sees 4.4 to 5.0 micrometres, where dust-hidden eruptions
   shine brightest. From the archive's list we take, for each visit period ("epoch": a run of
   observations with no gap longer than 30 days), the image whose centre is nearest the tile centre and a
   second image of another pointing at least a day away where there is one. Usually 6 whole detector
   images (3 epochs times 2), up to 8.
2. **Find bright point sources** in every image: the light in a circle of 2.5 pixels (15 arcseconds
   across) above the glow around it, at least 30 millijanskys (a star of magnitude 9.4 at 4.6
   micrometres) and at least 8 times the local scatter. Flagged and edge pixels are skipped; a saturated
   star (its core overflowed the detector) is kept as "bright, at least this much".
3. **Compare like with like.** Every source found in any image is measured again, at the same sky
   position, in every other image that covers it (a "forced measurement", not a catalogue match, so a faint
   counterpart is never mistaken for nothing).
4. **Keep the changes.** A source must be at least ten times brighter in one epoch than in another,
   or absent there (below three times the local noise), in *every* image of both epochs and with
   two usable images in the bright epoch. A saturated image never counts as "absent".
5. **Kill the artefacts**, in this order, counting each: a glitch or a moving body (they fail the
   second image); the image edge; a shape that is not a star (cosmic-ray hits, smears); a much brighter
   neighbour within 3 pixels; leftovers around saturated stars within 15 pixels; and the reflection of
   a very bright star ("ghost risk", see the limits).
6. **Ask every catalogue** at the survivor's position: AllWISE, CatWISE2020, 2MASS, Spitzer GLIMPSE, Gaia DR3,
   SIMBAD and the AAVSO Variable Star Index. A survivor is then (a) a catalogued star already bright before,
   which is an ordinary variable; (b) a known eruption (a nova or similar in SIMBAD or the Variable Star
   Index), which is a success of the method; or (c) a candidate: nothing within 6 arcseconds, or only a
   counterpart far fainter than what SPHEREx saw.
7. **Follow up every (b) and (c)** with the project's own tools: the brightness in every exposure of
   every detector (`photometry.lightcurve`), ten years of NEOWISE (`neowise.read_spot`), JPL's known
   asteroids and comets, a strip of small pictures, and web searches. For (c), the change must also show
   in the median of all clean 3.8 to 5 micrometre exposures (at least 5 times); otherwise it is set aside.

## The proof: V7994 Sagittarii, found without being told

V7994 Sgr (RA 270.96983, Dec -31.45739) erupted in September 2025. The proof tile was centred 0.4 degrees
away, at RA 270.7, Dec -31.2, and the method knew nothing about the nova.

| Stage in the proof tile (10.7 square degrees, 6 images in 3 epochs) | Sources |
|---|---|
| Bright point sources compared (30 mJy and up) | 29,424 |
| Measurable in at least two epochs | 28,875 |
| Changed by ten times between two epochs, comparing one image per epoch | 113 |
| ... killed because the second image disagrees (glitches, movers, noise) | 98 |
| ... changed in one usable image only and killed by the neighbour or ghost checks | 13 |
| Changed in every image, two or more in the bright epoch | 2 |
| Killed by edge, shape, neighbour, saturation or ghost checks | 0 |
| **Survivors** | **2** |

The two survivors: the nova (1,289 mJy at 4.4 to 5.0 micrometres in spring 2026, absent in August 2025 at
-2 mJy, AAVSO VSX lists it as type NA 1.1 arcseconds away: **known eruption**) and a long-period variable
star in the same tile (AllWISE W2 3.1 magnitude, VSX variable: **known variable**). Nothing else in the
tile survived, so the false-alarm rate there is zero in 29,424 sources. All 98 plus 13 other two-visit
"changes" were artefacts or noise, which is why the second-image rule is the most important check: a
plain comparison of two visits would have given 113 alarms for one real object. The picture is
`docs/sweep/proof_v7994_270.9698-31.4571.png`, its brightness chart `..._lightcurve.png`: all detectors,
absent in August 2025 (-3.5 mJy at 4.4 to 5.0 micrometres), 1,422 mJy in March to April 2026, 176 mJy in
August to September 2026, matching the 1,070 to 1,420 and 96 to 177 mJy of `docs/novae.md`.

![V7994 Sgr](sweep/proof_v7994_270.9698-31.4571.png)
![V7994 Sgr all exposures](sweep/proof_v7994_270.9698-31.4571_lightcurve.png)

It was found a second time, in the real sweep, in tile `l000.0_b-2.5`, again blind, again as a known
eruption (1,612 mJy).

## What was swept

- **Area:** 42 tiles, 301 square degrees of the sky counted where at least two epochs are each covered by
  at least two images (the cells are 0.1 degree squares; each tile answers only for the sky nearer its own
  centre than any other planned tile's, so nothing is counted twice). All 21 tiles of the row at
  Galactic latitude 0 (longitudes 330 to 360 to 30 degrees, every 3 degrees), 18 of the 21 tiles at
  latitude -2.5 (missing: l 27, 330, 339) and 3 of the 21 at +2.5 (l 354, 0, 3). 21 of the planned 63 tiles are
  not done (see "How to resume").
- **Sources compared:** 818,618, from 2,024,926 detections of the images (the rest lie in the overlaps
  belonging to other tiles).
- **Brightness limit actually reached:** a source of 30 mJy and at least 8 times the local scatter in
  its aperture. The typical error of one measurement is 4.1 mJy (median over the tiles; 2 mJy at the
  10th percentile, 11 to 25 mJy at the 90th, where the 3 per cent calibration term on bright stars
  dominates), so 30 mJy is a 7 sigma source in an ordinary field and fainter than that in the crowded
  centre is not looked for. Eruptions fainter than 30 mJy at 4.6 micrometres (magnitude 9.4) are not seen.

## The tallies, every stage (42 tiles)

| Stage | Sources |
|---|---|
| Sources compared | 818,618 |
| Measurable in at least two epochs | 810,220 |
| Changed by ten times, one image per epoch | 3,706 |
| Killed: second image disagrees or is missing (glitches, movers, noise) | 3,104 |
| Passed in one usable image only (cannot be confirmed) | 535 |
| ... all 535 then killed by the ghost or neighbour check (by hand in the proof tile: 14 ghost risk, 1 neighbour) | 535 |
| Changed in every image, two or more in the bright epoch | 67 |
| Killed: image edge | 0 |
| Killed: not a star shape | 29 |
| Killed: much brighter neighbour | 3 |
| Killed: saturated-star residue | 16 |
| Killed: reflection risk | 1 |
| **Survivors** | **18** |
| ... known variables (catalogued, already bright) | 8 |
| ... known eruptions | 2 |
| ... candidates before the all-exposure check | 8 |

Of the 8 "candidates", 4 are shown not to be what they seemed (below), 4 remain (3 clear, 1 weak).
Counting them as false alarms, the sweep's false-alarm rate after every check is 4 in 818,618.

Tile by tile (`area` in square degrees; "naive" is the one-image-per-epoch changes):

| Tile | Area | Sources | Naive | Survivors |
|---|---|---|---|---|
| l000.0_b+0.0 | 6.08 | 20,753 | 109 | 2 |
| l000.0_b+2.5 | 8.33 | 25,760 | 70 | 0 |
| l000.0_b-2.5 | 8.86 | 29,154 | 69 | 1 |
| l003.0_b+0.0 | 5.84 | 19,693 | 69 | 2 |
| l003.0_b+2.5 | 5.97 | 19,295 | 63 | 0 |
| l003.0_b-2.5 | 8.94 | 28,083 | 81 | 0 |
| l006.0_b+0.0 | 6.16 | 20,768 | 64 | 1 |
| l006.0_b-2.5 | 5.33 | 15,549 | 61 | 0 |
| l009.0_b+0.0 | 6.64 | 20,848 | 63 | 1 |
| l009.0_b-2.5 | 9.39 | 23,925 | 107 | 0 |
| l012.0_b+0.0 | 5.39 | 16,876 | 52 | 0 |
| l012.0_b-2.5 | 6.26 | 14,863 | 72 | 0 |
| l015.0_b+0.0 | 6.46 | 18,945 | 71 | 1 |
| l015.0_b-2.5 | 9.15 | 19,464 | 124 | 0 |
| l018.0_b+0.0 | 3.74 | 11,735 | 68 | 1 |
| l018.0_b-2.5 | 11.54 | 23,174 | 167 | 0 |
| l021.0_b+0.0 | 6.71 | 21,954 | 99 | 0 |
| l021.0_b-2.5 | 9.29 | 18,638 | 124 | 0 |
| l024.0_b+0.0 | 7.06 | 22,915 | 107 | 2 |
| l024.0_b-2.5 | 5.96 | 12,543 | 76 | 0 |
| l027.0_b+0.0 | 6.97 | 20,212 | 79 | 2 |
| l030.0_b+0.0 | 7.58 | 21,739 | 86 | 0 |
| l030.0_b-2.5 | 10.70 | 16,980 | 118 | 0 |
| l330.0_b+0.0 | 6.10 | 17,815 | 93 | 1 |
| l333.0_b+0.0 | 6.77 | 20,296 | 105 | 1 |
| l333.0_b-2.5 | 9.40 | 16,123 | 122 | 0 |
| l336.0_b+0.0 | 7.02 | 21,228 | 77 | 0 |
| l336.0_b-2.5 | 7.78 | 15,091 | 111 | 0 |
| l339.0_b+0.0 | 6.89 | 22,431 | 127 | 1 |
| l342.0_b+0.0 | 6.60 | 19,318 | 86 | 1 |
| l342.0_b-2.5 | 8.18 | 15,629 | 94 | 0 |
| l345.0_b+0.0 | 6.18 | 17,458 | 69 | 0 |
| l345.0_b-2.5 | 8.29 | 15,632 | 109 | 0 |
| l348.0_b+0.0 | 2.32 | 7,260 | 36 | 0 |
| l348.0_b-2.5 | 7.42 | 15,648 | 96 | 0 |
| l351.0_b+0.0 | 5.93 | 18,764 | 83 | 0 |
| l351.0_b-2.5 | 5.86 | 14,283 | 71 | 0 |
| l354.0_b+0.0 | 6.92 | 24,115 | 78 | 1 |
| l354.0_b+2.5 | 8.92 | 22,736 | 93 | 0 |
| l354.0_b-2.5 | 9.35 | 26,879 | 116 | 0 |
| l357.0_b+0.0 | 5.41 | 18,999 | 74 | 0 |
| l357.0_b-2.5 | 7.76 | 25,047 | 67 | 0 |

Tile `l348.0_b+0.0` has only 2.3 square degrees: fewer of its images overlap the tile in two epochs.

## Known eruptions recovered (successes of the method)

| Object | Position | Bright | Evidence |
|---|---|---|---|
| V7994 Sagittarii (nova, 2025) | RA 270.96982, Dec -31.45708 | 1,289 mJy (proof tile), 1,612 mJy (sweep tile) | AAVSO VSX type NA, 1.1 arcsec away; absent in August 2025 |
| V0691 Serpentis (nova) | RA 279.74438, Dec -3.86389 | 11,766 mJy, saturated, in September 2025 | AAVSO VSX type NA, 2.7 arcsec away; faded to 173 mJy by spring 2026 |

Pictures: `docs/sweep/l000.0_b-2.5_270.9697-31.4573.png`, `docs/sweep/l027.0_b+0.0_279.7444-3.8639.png`
and their `_lightcurve.png`. A second "candidate" 24 arcseconds from V0691 Ser
(`l027.0_b+0.0_279.7376-3.8627.png`) is the wing of that very bright nova: it is saturated in the same images, it is
absent in the other epochs, and every exposure of detectors 1 to 4 shows nothing there, so it is set aside
as part of the nova's glare. (The neighbour check looks 3 pixels out and the saturation-residue check
ignores a clump within 6 pixels as "the source itself"; this one lay 4 pixels from the core and slipped
between them. It is a hole in the checks, found by looking at the pictures.)

Eight survivors are catalogued stars that were already bright (AllWISE, CatWISE or a variable type in
VSX, SIMBAD or Gaia): long-period variables and similar. They are not what the sweep is after and are counted
only (`docs/sweep/summary.json` lists their positions).

## The candidates

For each: the position, the brightness in every epoch (median of all clean exposures of each detector
across the whole archive: `follow_up`, `docs/sweep/*_lightcurve.png`), every catalogue's answer, the
checks that tried to kill it, and what was searched. "Searched" lists exactly what was tried; a search
that finds nothing does not prove nobody has reported it.

Colours of the detectors: D1 0.75 to 1.1, D2 1.1 to 1.65, D3 1.65 to 2.4, D4 2.4 to 3.8, D5 3.8 to 4.4,
D6 4.4 to 5.0 micrometres. "Aug 2025", "Mar 2026", "Aug 2026" are the three SPHEREx visits.

### Candidate A: RA 270.80362, Dec -23.46745 (18h03m12.87s, -23d28m02.8s), l 6.713, b -0.634

**Appears in 2025, brightens ninefold in 2026**, deep red.

| Epoch | D6 (4.4 to 5.0) | D5 | D4 | D3 | D2 | D1 |
|---|---|---|---|---|---|---|
| Aug to Sep 2025 | 153 mJy | 187 | none clean | none clean | 17 | 0.2 |
| Mar to Apr 2026 | 2,915 mJy (partly saturated: at least 2,576 and 3,272 in the tile images) | 1,903 | 729 | 644 | 42 | 0.9 |
| Aug to Sep 2026 | 870 | 790 | 306 | 150 | 11 | 0.5 |

- Tile images: 157 and 154 mJy (August 2025), 2,576 and 3,272 (saturated lower limits, spring 2026), 912 and
  867 (August 2026): the ten-times rule is passed by 16 times. Detectors 5 and 6 show the rise in every clean
  exposure (12 to 16 per epoch), and detectors 3 and 4 see it bright in 2026 (644 and 729 mJy; they have no clean
  2025 reading). Each detector looks at a different part of the sky in each exposure, so it is not a defect of one.
- Catalogues: nothing within 6.2 arcseconds in Gaia DR3, 2MASS, AllWISE, CatWISE2020, SIMBAD (nothing
  within 20 arcseconds), AAVSO VSX (nothing within 20 arcseconds). The nearest AllWISE and CatWISE2020 sources are
  11.6 and 12.4 arcseconds away, W2 11.6 magnitude (0.4 mJy). A 153 mJy source at 4.6 micrometres is W2 7.6
  magnitude and would be in AllWISE if it had been there in 2010. GLIMPSE does not cover this longitude
  (it returned no rows; its first release spans l 10 to 65). The VVV near-infrared catalogue (VizieR II/348, ground-based, 2010 to 2015) lists only faint stars,
  K 13.9 to 16, within 4 arcseconds (a catalogue query; its variability tables were not searched).
- NEOWISE (2014 to 2024): no measurement within 1.5 arcseconds, one at 7.5 arcseconds. So nothing at this place was
  detected in ten years, and by August 2025 it was 153 mJy.
- Killed? Not a glitch or mover (two images per epoch of different pointings agree; JPL's nearest known
  body, 730055 (2011 UR279), V 20.5, was 106 arcseconds away). It passed the ghost check, and five detectors see it
  in 2026. Not a detector defect for the same reason. Picture:
  `docs/sweep/l006.0_b+0.0_270.8036-23.4674.png` and `_lightcurve.png`.
- Searched: SIMBAD and VSX through their services (nothing within 20 arcseconds); Transient Name Server
  coordinate search, 60 arcseconds, 2026-11-14 (a table with headers and no rows);
  web searches for the position in three notations, for "SPHEREx" with ATel and TNS, for the nearby
  catalogue names, and the one SPHEREx transient paper found (Karambelkar et al. 2026, arXiv 2602.07129, which gives positions for only
  three objects, none here); 
  Not checked: a human search of ATel and VVV variability tables (VVV-WIT), the paper in A&A 2026 June on
  four young-star outbursts (the page refused the request).

### Candidate B: RA 253.18044, Dec -44.67687 (16h52m43.31s, -44d40m36.7s), l 341.089, b -0.416

**Rises steadily through 2025 and 2026 to a thousand times its old brightness.**

| Epoch | D6 | D5 | D4 | D3 | D1 |
|---|---|---|---|---|---|
| Aug to Sep 2025 | 24 mJy | 39 | 38 | 27 | 0.9 |
| Feb to Mar 2026 | 468 | 198 | 73 | 86 | 1.1 |
| Aug 2026 | 1,125 | 816 | 185 | 53 | 0.9 |

- Tile images: 27.4 and 27.5 mJy (Aug 2025), 515 and 512 (March 2026), 1,008 and 976 (August 2026); ratio 35.
- Catalogues: a faint star lies 3.5 to 4.7 arcseconds away in every catalogue: CatWISE2020 W2 13.54 (0.66 mJy),
  Spitzer GLIMPSE [4.5] 12.47 (1.8 mJy, observed in the mid-2000s), 2MASS Ks 13.77, Gaia G 19.35. Nothing is listed as
  variable; SIMBAD and VSX have no row within 12 arcseconds. So this is class (c): a counterpart far fainter
  (1,000 times) than the 2026 brightness. It could be a pre-existing red star that erupted (a young star
  or a slow nova). Nothing says which.
- NEOWISE (2014 to 2024): nothing within 1.5 arcseconds. Not a mover (nothing in JPL's list within 108 arcseconds).
  Not a ghost, defect or glitch (4 detectors, 6 images, monotonic rise). Picture:
  `docs/sweep/l342.0_b+0.0_253.1804-44.6769.png`, `_lightcurve.png`.
- Searched: Transient Name Server (60 arcseconds, empty), two web searches by catalogue name
  (G341.089-00.416, SSTGLMC G341.0893-00.4165) and by position and by "outburst young star Norma 2026": no hit.

### Candidate C: RA 241.70931, Dec -52.20484 (16h06m50.2s, -52d12m17.4s), l 330.413, b -0.081

**A flare of about half a year in 2026, back to nearly nothing by August 2026**, on a faint star embedded in
a cold dust clump.

| Epoch | D6 | D5 | D4 | D3 |
|---|---|---|---|---|
| Jul to Aug 2025 | 3.9 mJy | 8.4 | 9.3 | 8.5 |
| Feb to Mar 2026 | 110 | 124 | 83 | 54 |
| Jul to Sep 2026 | 8.0 | 12.3 | 7.9 | 8.5 |

- Tile images: 5.3 (July 2025; the second image of the epoch does not cover the place), 178 and 300 (February and March 2026),
  9.5 mJy (September 2026; the other 2026 image is flagged). So this one has only a single image in the faint epochs
  (it passes because the rule wants at least one clean image there), so the all-exposure check carries the
  weight: 8 to 20 clean exposures per detector and epoch agree (D5 and D6).
- Catalogues: GLIMPSE [4.5] 13.80 (0.54 mJy) 4.1 arcseconds away; Herschel Hi-GAL clump HIGALBM G330.4120-00.0823 (SIMBAD type
  "smm", a submillimetre clump) 6.6 arcseconds away; a Gaia star G 20.1 and 2MASS Ks 13 at 9 arcseconds. Nothing
  variable. A flare on a young star embedded in a dust clump is the natural reading, and the Hi-GAL clump says
  star formation is there. It is not an assertion.
- NEOWISE: nothing within 1.5 arcseconds. JPL: no known body near. Picture
  `docs/sweep/l330.0_b+0.0_241.7093-52.2048.png`.
- Searched: Transient Name Server (60 arcseconds, empty); web search by catalogue names and position (one
  result about CX330, a different Galactic Centre object, not this one): no report found.

### Candidate D (weak): RA 250.48507, Dec -46.02356, l 338.837, b +0.158

D6 14 mJy, 66, 52; D5 9, 76, 43 (Aug 2025, Mar 2026, Aug 2026): a fourfold brightening of a counterpart
that is already 15 mJy at 4.6 micrometres, against a GLIMPSE [4.5] of 13.31 (0.85 mJy). It passes only
through the "absent" rule (15 mJy is under three times its noise) and not the ten-times ratio (3.6), and
the bright images are partly saturated. Reported for completeness; it would not be called a candidate on the
ten-times rule. `docs/sweep/l339.0_b+0.0_250.4851-46.0236.png`. Transient Name Server (60 arcseconds): empty.

### Looked at and set aside

| Position | Why it passed the tile and what stopped it |
|---|---|
| RA 267.49549, Dec -27.56803 (l 1.668, b -0.115) | its brightness in the tile images swung (136, 126, 23, 116, 125) but the median of all 3.8 to 5 micrometre exposures is 143, 135 and 157 mJy in D5 and 111, 96 and 118 in D6: steady. One tile image was measured on a crowded background. |
| RA 272.10809, Dec -22.28134 | the catalogued planetary nebula PN M 1-40 lies 0.7 arcseconds away; NEOWISE saw it steady (21 visits, 1.05 times); all-exposure medians 96, 86, 178 mJy in D6. A bright nebula, not a transient. |
| RA 279.73756, Dec -3.86269 | the glare of V0691 Ser, above. |
| RA 261.92881, Dec -35.29494 | 39 mJy against 1.4 in a 4-image comparison, but the all-exposure medians of D6 are 4, 15 and 2 mJy and D5 negative: 5 sigma at most, not confirmed. A methanol maser and sub-millimetre clump lie 8 arcseconds away, so it may be worth a look by someone who knows that region. |

An earlier run of the sweep, before the faint side was required to be a full measurement and not a saturated
lower limit, gave three more "candidates" and eight "known variables" in tiles l345 and l348 that rested on one
saturated-flagged image. The rule was fixed and every tile rerun; they no longer pass (commit history).

## What would confirm it

None of A, B or C is confirmed, and none should be called a discovery. To go further:

1. **A person reports it.** Only a person can file with the IAU's Transient Name Server or write an
   Astronomer's Telegram; a team member with an account should check the positions again at that moment
   (TNS coordinate search, ATel, AAVSO VSX, SIMBAD) and report the SPHEREx measurements above.
2. **A spectrum or an image from a larger telescope**: near-infrared imaging at the position (an
   extremely red source would show up in K band for A and B), then a spectrum: a nova, a young-star outburst
   (FU Orionis or EXor type) and a dust-enshrouded giant look different in the CO and hydrogen lines.
3. **Other data on the same place**: VVV and VVVX near-infrared light curves (2010 to 2023), the next SPHEREx visits
   (A and B are still bright; C faded), NEOWISE's last months.

## Limits

- **Bright sources only**: 30 mJy at 4.4 to 5.0 micrometres and at least 8 times the local scatter. Fainter eruptions
  are not looked for.
- **Two or three visits, one detector**: the sweep compares three epochs, 6 months apart; anything that
  rose and fell between visits, or that changed by less than ten times, is missed. Only detector 6's whole
  images are used in the sweep; the other detectors enter only in the follow-up.
- **Crowding near the Galactic centre**: sky levels are taken from a ring 14 to 20 pixels out and are
  imperfect when the field is full of stars, so a source below about 10 mJy cannot be measured
  as absent and a faint change next to a brighter star is lost.
- **Hidden by a saturated star**: a change within 3 pixels of a much brighter neighbour, or within 15 of a
  saturated one, is killed rather than examined.
- **Ghosts are not understood**: the check is a heuristic (a source within 300 pixels of a very bright star
  must be seen at the same sky position in two images where that star sits at least 100 pixels apart on the
  detector). It killed 1 survivor in the sweep and made every single-image case fail; it is not a model of
  SPHEREx's reflections, which the archive does not flag.
- **Single-image sources are lost**: 535 sources passed the two-visit rule with only one usable image in the
  bright epoch and all were killed by the ghost or neighbour check. Real eruptions near very bright stars
  are among them.
- **Gaps**: a tile counts only the sky where two epochs are each covered by two images. Tiles cover 4 to 12
  square degrees of their 7 to 12 and the part not covered is not examined. The plane within 2.5 degrees of
  latitude 0 is covered only in part: the +2.5 row and three tiles of the -2.5 row are not done.
- **Catalogue searches are positions only**: the catalogues are asked at the sweep's centroid within 20
  arcseconds, and the 6.2 arcsecond "at the place" rule can call a blended pair a counterpart or miss a high-motion
  star.
- **Name searches prove nothing by being empty.**

## How to run and resume

```
SPHEREX_CACHE_DIR="backend/cache/sweep" python scripts/sweep_plane.py            # all remaining tiles, skips finished ones
SPHEREX_CACHE_DIR="backend/cache/sweep" python scripts/sweep_plane.py --shard 0/3 # three of these in parallel: 0/3, 1/3, 2/3
SPHEREX_CACHE_DIR="backend/cache/sweep" python scripts/sweep_plane.py --summary   # the tallies so far
SPHEREX_CACHE_DIR="backend/cache/sweep" python scripts/sweep_plane.py --proof     # the V7994 Sgr proof tile
```

Each tile downloads six whole detector images (about 100 MB each, about 20 seconds each from NASA's
public S3 bucket), measures them (about 1 to 3 minutes), asks the catalogues, and deletes the images. The
whole run, three at a time, takes about 12 minutes per three tiles. A tile that is finished has a file in
`<cache>/sweep_work/tiles/`; delete a file to redo that tile.

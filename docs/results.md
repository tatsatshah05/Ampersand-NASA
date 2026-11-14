# Results on the five test targets

For issue #13. This is what the tool shows on real SPHEREx data for the five targets
named in the challenge, written down after looking at every frame.

- **When:** 2026-11-14.
- **Code:** repo at commit `67557b5`. The code that makes the pictures and the numbers
  (`backend/pipeline.py`, `photometry.py`, `astrometry.py`, `spherex.py`) was last
  changed in `e287a08` and `c46075d`; `pipeline.VERSION` 2, `photometry.VERSION` 6.
  `backend/cache/frames/` was deleted and every view rebuilt before this run.
- **How:** `python scripts/warm_cache.py` (builds every view), then
  `python scripts/run_targets.py` (measures them and makes the contact sheets), then
  every contact sheet and chart was opened and looked at. Re-run both to check.
- **Views:** field of view 0.1 degrees (180 x 180 pixels of 2 arcsec), all six
  detectors, requested with each target's position at 2026.0 and its motion, exactly
  as `/api/resolve` returns them.
- **The pages:** what was looked at frame by frame are the images the pages show and
  the numbers the API returns. The two pages themselves (`/` and `/viewer.html`) were
  loaded once per target in a headless browser and screenshotted, with no clicking;
  see "The two pages" below.

Nothing here is simulated or filled in. Where a target shows nothing, it says so.

## Summary

| Target | A good result, per the challenge | What the data shows | Verdict |
|---|---|---|---|
| Barnard's Star | Star steps across frames; shift matches Gaia | Three frames in every detector. The star steps north by about 10 arcsec in a year. Marker within 1.5 arcsec of the catalogue track in all 18 frames. | **Met** |
| Epsilon Indi B | Faint companion visible, moving with the primary | Visible in all six detectors (faint in detector 1), moving 6.3 arcsec south-east in 17 months on the catalogue track. The primary is outside the default frame; in a wider view both leave the same kind of mark in the difference image. | **Met**, with the wider view |
| WISE 0855-0714 | Seen only after stacking, in the longest-wavelength detector | Seen in detectors 5 and 6 in each visit's stacked frame (weak in the first visit), not in detectors 1 to 4. Moves 7.8 arcsec west in a year, as predicted. By 2026 it is 4 arcsec from an unrelated star and blends with it. | **Met**, and better than expected: summing all visits is not needed. Read the caveats. |
| RW Aurigae | Brightness chart shows change | Between September 2025 and September 2026: brighter by a factor of 1.6 at 0.75 to 1.1 microns, and fainter at 3.8 to 5 microns (to about half where the first visit could be measured). Visible in the difference frames and in the measurements. | **Met** in the data. The chart on the page was not checked. |
| R Draconis | Brightness chart shows change | Saturated in every exposure of every detector: no flux can be measured. The unsaturated outer light in detectors 5 and 6 fell to 0.5 to 0.6 of its first value in a year. | **Partly met**: a change is seen, but only in a relative measure, and only in two detectors. |

Field stars: in every target and detector where ordinary stars could be measured, their
median shift between frames is 0.7 arcsec or less (a ninth of a SPHEREx pixel). No
jitter between frames was found anywhere.

## Problems found

Each of these was seen in the images or numbers of this run. None has been fixed by
this session (the backend is not its to change).

1. **The stacking step removes real light from objects whose brightness changes
   steeply with wavelength.** Before averaging, `pipeline.stack` throws out readings far
   from the per-pixel median. A brown dwarf is hundreds of times brighter at one end
   of detector 1 than at the other, so its brightest readings are thrown out as
   glitches. Epsilon Indi B, detector 1: at the target's place the frame of visit 2
   has 0.24 MJy/sr; the same exposures averaged with nothing thrown out give 1.23.
   Visit 3: 0.82 against 1.89. Detector 2, visit 3 (7 exposures): 4.8 against 7.7.
   In the sum of all visits in detector 1: 0.51 against 1.53. On screen the target
   becomes a dim ring with a hollow middle.
   Images: `results/eps_indi_b_D1_epoch2.png`, and
   `results/eps_indi_b_D1_sum_target.png` beside
   `results/eps_indi_b_D1_sum_target_no_rejection.png` (the second is a diagnostic
   made by `scripts/run_targets.py`, not something the site serves).
   It did not hurt WISE 0855 in detectors 5 and 6 (same value with and without).
2. **A visit with very few exposures can give a patchy frame.** Detector 1 has a first
   visit of only 4 exposures at Epsilon Indi B and at WISE 0855. Both frames are a
   patchwork of blocks of different brightness with small holes
   (`results/eps_indi_b_D1_epoch1.png`, `results/wise0855_D1_epoch1.png`). Because the
   difference view subtracts the first visit, both of that detector's difference
   frames inherit the blocks (`results/eps_indi_b_D1_diff_epoch2_minus_1.png`).
   Other visits with 3 to 8 exposures, in detectors 2 to 6, are noisier but not patchy.
3. **At WISE 0855 the marker sits on the wrong object in detectors 1 to 4.** An
   unrelated star, Gaia DR3 5756956644387831296 (G = 16.3), lies 4 to 11 arcsec from
   where the brown dwarf is in the three visits. With the motion values passed,
   `predicted` is right, but the measured marker (`centroid`) locks onto that star in
   every frame of detectors 1 to 4, because it starts from the brightest pixel within
   14 arcsec of the predicted place. Without the motion values (a coordinates-only
   request) the backend also takes that star as the `target`, and `predicted` then
   points at it in every frame.
   Seen with `build_frames(133.759765, -7.242182, detector=6)`: target origin
   `gaia_nearest`, that source id. Image: `results/wise0855_sheet.jpg`, rows 1 to 4.
4. **Artefacts that differ from frame to frame are not removed, and look like
   changes.** At Epsilon Indi B: a ring near the top of the frame in detector 6,
   visits 1 and 3, in two different places, and in detector 5, visit 4; a broad
   diagonal streak through the target in detector 6, visit 2; a glow along the west
   edge in detectors 1 to 3 from the bright primary just outside the frame. All of
   them show up in the difference frames
   (`results/eps_indi_b_D6_epoch1.png`, `results/eps_indi_b_D6_epoch2.png`,
   `results/eps_indi_b_D6_diff_epoch2_minus_1.png`).
5. **Holes with no data in detector 1.** RW Aurigae: two in visit 1, three in visit 3,
   one of them about 30 by 40 arcsec (`results/rw_aur_D1_epoch3.png`). Barnard's Star:
   one in visit 2. They are drawn transparent, as intended, but there are more of
   them in detector 1 than anywhere else.
6. **Two meanings of "saturated".** For RW Aurigae every frame reports
   `saturated_pixels` 0, while `/api/lightcurve` marks 167 of its 336 exposures as
   saturated. The frames count only pixels that have no value at all; the brightness
   measurement uses the stricter flag rule. A visitor sees "0 saturated" on the frame
   and "saturated" on the chart for the same star.
7. **Barnard's Star, first visit: the marker is about 1 arcsec east of the catalogue
   position in all six detectors** (+0.9 to +1.4 arcsec east; the other two visits are
   within 0.3 arcsec in detectors 2 to 6). `CLAUDE.md` already notes this for detector
   5. It is the same in every detector, so it is not noise.
8. **Brightness at the WISE 0855 position includes the neighbouring star.** The
   measuring circle is 15 arcsec in radius and the star is 4 to 11 arcsec away, so
   short of 4 microns the "spectrum of WISE 0855" is that star's light. See the
   WISE 0855 section.
9. **The front page asks for frames without the motion values, and at WISE 0855 it
   then reports the detection as a disagreement.** Its request carries position, field
   of view, detector and `mode=normal` only (commit `67557b5`; the page was still
   being changed). At WISE 0855, detector 6, it reads: "Gaia DR3 5756956644387831296:
   moves 0.01 arcsec per year. Since frame 1: measured shift 1.1 north, 7.8 west. Gaia
   predicts 0.0 north, 0.0 west. They differ by 7.8 arcsec, which is 1.27 of a SPHEREx
   pixel." The measured shift is right (it is the brown dwarf's); the prediction is
   for the unrelated star of problem 3. At Epsilon Indi B it reads "No Gaia star near
   the centre, so there is no predicted motion to compare with", because that object
   is too faint for the backend's Gaia search and no motion was passed.
   Image: `results/page_front_other_targets.png`.
10. **The saturation hint is wrong for R Draconis.** The front page says "star too
    bright here; try detector 5 or 6". For R Draconis detectors 5 and 6 are saturated
    too (27 to 81 pixels).

Not a fault, but it matters for the demo: only the 0.1 degree field of view is
warmed. Any other size downloads for about a minute per detector.

## Barnard's Star

Centre: RA 269.446267, Dec +4.768222 (Gaia DR3 4472832130942575872 moved to 2026.0;
270 arcsec from its J2000 place). 364 exposures, three visits.

| Detector | Frames | Dates of each frame | Exposures per frame | Saturated pixels per frame | Target visible? | Does it move? | Anything wrong |
|---|---|---|---|---|---|---|---|
| D1 | 3 | 2025-08-27 to 2025-10-01<br>2026-03-11 to 2026-03-11<br>2026-08-23 to 2026-09-02 | 24, 18, 18 | 0, 0, 16 | Yes, bright | Yes, north | Saturated core in frame 3. One small hole (no data) in frame 2, left of and below the star. |
| D2 | 3 | 2025-08-21 to 2025-08-30<br>2026-03-15 to 2026-03-22<br>2026-08-18 to 2026-09-22 | 18, 19, 25 | 19, 30, 29 | Yes, bright | Yes, north | Saturated core in every frame, drawn as a flat white patch. |
| D3 | 3 | 2025-08-15 to 2025-08-27<br>2026-03-19 to 2026-05-05<br>2026-08-16 to 2026-08-20 | 18, 24, 17 | 22, 30, 23 | Yes, bright | Yes, north | Saturated core in every frame. |
| D4 | 3 | 2025-08-27 to 2025-10-01<br>2026-03-11 to 2026-03-11<br>2026-08-23 to 2026-09-02 | 23, 18, 18 | 14, 25, 34 | Yes, bright | Yes, north | Saturated core in every frame; a square-edged white patch in frame 3. |
| D5 | 3 | 2025-08-21 to 2025-08-30<br>2026-03-15 to 2026-03-22<br>2026-08-18 to 2026-09-22 | 18, 19, 25 | 0, 0, 0 | Yes, bright | Yes, north | Nothing. |
| D6 | 3 | 2025-08-15 to 2025-08-27<br>2026-03-19 to 2026-05-05<br>2026-08-16 to 2026-09-22 | 17, 24, 19 | 0, 0, 0 | Yes, bright | Yes, north | Nothing. |

- **Motion.** Between the first and third visits the catalogue (proper motion plus
  parallax) predicts 0.8 arcsec west and 10.3 arcsec north. Measured in detector 5:
  2.2 west, 10.2 north; detector 6: 1.7 west, 10.2 north; detector 2: 1.9 west, 9.4
  north. In all 18 frames the marker is within 1.5 arcsec of the predicted place.
- **Field stars.** 11 to 13 stars per detector; median shift between frames 0.15 to
  0.38 arcsec, largest single star 0.77.
- **Difference.** In every detector: a white patch north of a black one at the star,
  and only faint speckle at the other stars. In detectors 1 to 4 a notch with no data
  where the core is saturated.
- **Sum.** Added on the sky the star is stretched north to south, and in detectors 1
  to 4 its saturated core gives a blocky pattern. Added following the star it is
  round and the field stars become short streaks, as they should.
- **Brightness.** 350 of 364 exposures are saturated for measurement, in all six
  detectors (4 gave a flux). The outer-light measure in detectors 5 and 6 did not
  change between visits (last over first: 1.01 and 0.98), which is what a steady star
  should give and is the comparison for R Draconis below.

Images: `results/barnard_sheet.jpg` (every frame), `results/barnard_modes_sheet.jpg`
(sum and difference), `results/barnard_D5_epoch1.png` to `_epoch3.png`,
`results/barnard_D5_diff_epoch3_minus_1.png`, `results/barnard_D5_sum_target.png`.

## Epsilon Indi B

Centre: RA 331.096653, Dec -56.800663 (Gaia DR3 6412596012146801152, G = 18.0, moved
to 2026.0; 122 arcsec from its J2000 place). 467 exposures. Detectors 2, 3, 5 and 6
have four visits (April 2025 to October 2026); detectors 1 and 4 have three.

| Detector | Frames | Dates of each frame | Exposures per frame | Saturated pixels per frame | Target visible? | Does it move? | Anything wrong |
|---|---|---|---|---|---|---|---|
| D1 | 3 | 2025-04-25 to 2025-04-27<br>2025-10-03 to 2025-11-12<br>2026-04-18 to 2026-05-03 | 4, 24, 20 | 3, 0, 0 | Faint. Clear in frame 1; in frames 2 and 3 a dim, hollow-looking spot | Too faint to judge by eye; the marker follows the catalogue track | Frame 1 (4 exposures) is patchy: blocks of different brightness, a diagonal bright band, small holes. Frames 2 and 3: the stacking step removes most of the target's light (problem 1). Glow along the west edge. |
| D2 | 4 | 2025-04-24 to 2025-06-07<br>2025-10-01 to 2025-11-08<br>2026-04-24 to 2026-04-30<br>2026-09-28 to 2026-10-02 | 32, 30, 7, 24 | 0, 0, 0, 0 | Yes, bright | Yes, south-east | Glow along the west edge (from Epsilon Indi A, outside the frame). |
| D3 | 4 | 2025-04-29 to 2025-06-10<br>2025-09-28 to 2025-11-04<br>2026-04-29 to 2026-05-04<br>2026-09-22 to 2026-09-28 | 25, 23, 12, 36 | 0, 0, 0, 0 | Yes, bright | Yes, south-east | Glow along the west edge. |
| D4 | 3 | 2025-04-25 to 2025-04-27<br>2025-10-03 to 2025-11-12<br>2026-04-18 to 2026-05-03 | 3, 23, 18 | 0, 0, 0 | Yes, bright | Yes, south-east | Frame 1 (3 exposures) is noisier and has two small holes. |
| D5 | 4 | 2025-04-24 to 2025-06-07<br>2025-10-02 to 2025-11-08<br>2026-04-24 to 2026-04-30<br>2026-09-28 to 2026-10-02 | 31, 24, 7, 24 | 0, 0, 0, 0 | Yes, brightest here | Yes, south-east | Frame 3 (7 exposures) is noisier. A faint ring near the top of frame 4 (an artefact). |
| D6 | 4 | 2025-04-29 to 2025-06-10<br>2025-09-28 to 2025-11-04<br>2026-04-29 to 2026-05-04<br>2026-09-22 to 2026-09-28 | 26, 22, 11, 36 | 0, 0, 0, 0 | Yes, bright | Yes, south-east | Ring artefacts near the top of frames 1 and 3, in different places. A broad diagonal streak through the target in frame 2. |

- **Motion.** Between the first and fourth visits the catalogue predicts 5.1 arcsec
  east and 3.7 south (6.3 arcsec in all). Measured: detector 2, 4.9 east and 3.6
  south; detector 5, 5.0 and 3.8; detector 6, 4.9 and 3.9. The marker is within 1.1
  arcsec of the predicted place in every frame except detector 1, visit 1 (2.9, the
  patchy frame).
- **Field stars.** 3 to 9 per detector; median shift 0.25 to 0.52 arcsec.
- **Difference.** Detectors 2 to 6: a clean white (south-east) and black
  (north-west) pair at the target. Detector 1: unusable (problem 2). Detector 6: the
  streak and the rings also show.
- **Sum.** Following the target it is sharp in detectors 2 to 6. Detector 1 is dimmed
  by problem 1.
- **Brightness.** 298 of 467 exposures gave a flux. Together they trace the object's
  spectrum from 0.75 to 5 microns: from 0.05 mJy at 0.78 microns up to about 40 mJy
  at 1.27, deep dips near 1.4 and 1.8 to 1.9 microns, peaks near 1.6 and 2.1, and a
  broad maximum of about 55 mJy near 4 microns (`results/eps_indi_b_brightness.png`).
  The four visits lie on the same curve: in detectors 3, 5 and 6 the last visit over
  the first is 0.97 to 1.00. So this object is steady, which makes it the comparison
  for RW Aurigae below.
- **With the primary.** Epsilon Indi A is 6.7 arcminutes west, outside a 0.1 degree
  frame. One extra view was made at 0.3 degrees in detector 5 (86 more cutouts, about
  140 MB; not part of the warm-up). Both stars are in it, A heavily saturated. In the
  difference of the last visit against the first, A and B each leave a white patch
  to the south-east of a black one: the same direction. A's own shift was not
  measured (its core has no data). 37 field stars in that view moved by a median of
  0.31 arcsec or less.

Images: `results/eps_indi_b_sheet.jpg`, `results/eps_indi_b_modes_sheet.jpg`,
`results/eps_indi_b_brightness.png`, `results/eps_indi_b_D5_epoch1.png` to
`_epoch4.png`, `results/eps_indi_b_wide_D5_epoch1.png`,
`results/eps_indi_b_wide_D5_diff_epoch4_minus_1.png`, `results/eps_indi_b_wide_sheet.jpg`.

## WISE 0855-0714

Centre: RA 133.759765, Dec -7.242182. Not in Gaia. Position, motion (-8123.7, +673.2
mas/yr) and parallax (439 mas) are SIMBAD's, from Kirkpatrick et al. 2021, moved 26
years to 2026.0; that is 212 arcsec from its J2000 place and 127 arcsec from the
coordinates in the challenge text. 258 exposures, three visits (May 2025, late
October to December 2025, April to May 2026). The first visit is thin: 3 to 8
exposures per detector.

| Detector | Frames | Dates of each frame | Exposures per frame | Saturated pixels per frame | Target visible? | Does it move? | Anything wrong |
|---|---|---|---|---|---|---|---|
| D1 | 3 | 2025-05-06 to 2025-05-06<br>2025-10-31 to 2025-11-03<br>2026-05-01 to 2026-05-05 | 4, 18, 14 | 0, 0, 0 | No. Nothing at the expected place in frame 1; the light there in frames 2 and 3 is the neighbouring star's | Not applicable | Frame 1 (4 exposures) is patchy, with a brightness gradient and a hole. The marker sits on the neighbouring star in every frame. |
| D2 | 3 | 2025-05-06 to 2025-05-06<br>2025-11-07 to 2025-12-13<br>2026-05-01 to 2026-05-14 | 8, 25, 15 | 0, 0, 0 | No (as D1) | Not applicable | The marker sits on the neighbouring star. |
| D3 | 3 | 2025-05-05 to 2025-05-05<br>2025-11-10 to 2025-12-13<br>2026-04-21 to 2026-05-11 | 3, 21, 21 | 0, 0, 0 | No (as D1) | Not applicable | Frame 1 (3 exposures) is noisy. The marker sits on the neighbouring star. |
| D4 | 3 | 2025-05-06 to 2025-05-06<br>2025-10-31 to 2025-11-03<br>2026-05-01 to 2026-05-05 | 4, 18, 14 | 0, 0, 0 | No (as D1) | Not applicable | The marker sits on the neighbouring star. |
| D5 | 3 | 2025-05-06 to 2025-05-06<br>2025-11-07 to 2025-12-13<br>2026-05-01 to 2026-05-14 | 8, 25, 15 | 0, 0, 0 | Yes, faint, in all three frames | Yes, west | Merges with the neighbouring star by frame 3. |
| D6 | 3 | 2025-05-05 to 2025-05-05<br>2025-11-10 to 2025-12-13<br>2026-04-21 to 2026-05-11 | 3, 21, 21 | 0, 0, 0 | Yes, faint: marginal in frame 1, clear in frames 2 and 3 | Yes, west | Frame 1 (3 exposures) is very noisy. Merges with the neighbouring star in frame 3. |

What is at the predicted place, visit by visit (mean of the 3 x 3 pixels there with
the frame's background removed, in MJy/sr, and in units of the background noise):

| Detector | Visit 1 (target 11 arcsec from the star) | Visit 2 (8 arcsec) | Visit 3 (4 arcsec) |
|---|---|---|---|
| D1 | 0.007 (0) | 0.063 (10) | 0.265 (42) |
| D2 | -0.001 (0) | 0.068 (9) | 0.270 (36) |
| D3 | 0.010 (1) | 0.044 (6) | 0.175 (23) |
| D4 | 0.003 (0) | 0.026 (4) | 0.086 (13) |
| D5 | 0.114 (10) | 0.103 (13) | 0.144 (17) |
| D6 | 0.093 (3) | 0.156 (14) | 0.187 (18) |

- **Is it there?** In detectors 1 to 4 there is nothing at the predicted place in
  visit 1, and what appears there later grows exactly as the path closes in on the
  neighbouring star: that light is the star's. In detectors 5 and 6 there is a source
  at the predicted place already in visit 1, when the star is 11 arcsec away and
  contributes little (the star itself measures 0.07 in detector 5 and 0.01 in
  detector 6 that visit). Detector 6, visit 1 has only 3 exposures and is marginal on
  its own (3 times the noise); detector 5, visit 1 (8 exposures) is clear (10 times).
- **Does it move?** In detector 6 the marker moves 7.8 arcsec west and 1.1 north
  between visits 1 and 3; the catalogue predicts 7.9 west and 0.6 north. Detector 5:
  6.9 west. In detector 2 the marker does not move (0.2 arcsec): it is on the star.
- **The neighbouring star.** 0.38 to 0.41 MJy/sr in detectors 1 and 2, 0.23 to 0.26 in
  detector 3, 0.08 to 0.13 in detector 4: it fades toward long wavelengths while the
  target appears. By visit 3 the two are 4 arcsec apart, less than one SPHEREx pixel,
  and cannot be told apart in the frame. Visit 2 in detector 6 is the cleanest single
  frame: a source at the predicted place, 8 arcsec from the star
  (`results/wise0855_D6_epoch2.png`).
- **Sum.** All 45 detector 6 exposures added following the target: 0.163 MJy/sr at the
  predicted place, 20 times the noise, marker 1.1 arcsec away. Added on the sky: 0.140,
  17 times. Detector 5 following the target: 0.112, 17 times. In detectors 1 to 3 the
  sum following the target also shows light at the predicted place (0.09 to 0.10):
  that is the star, smeared along the track.
- **Difference.** Detector 5: a dark spot where the target was in visit 1. Detectors 1
  to 4: nothing at the target. Detector 1's are patchy (problem 2).
- **Brightness.** 196 of 258 exposures gave a flux, but the measuring circle includes
  the star (problem 8). The values fall from about 1.1 mJy at 1 micron to about 0.2
  mJy between 3 and 3.9 microns (the star), then rise to 0.5 to 1 mJy between 4.1 and
  4.8 microns (`results/wise0855_brightness.png`). The rise beyond 4 microns is the
  brown dwarf. No change over time can be claimed: the ratios scatter by 30 per cent
  or more.
- **Against the plan.** The plan expected this object "only after summing all frames".
  It is visible without that, in each visit's own stack, in two detectors rather
  than one. The summed frame shows it more clearly.

Images: `results/wise0855_sheet.jpg`, `results/wise0855_modes_sheet.jpg`,
`results/wise0855_D6_epoch1.png` to `_epoch3.png`, `results/wise0855_D2_epoch2.png`
(nothing at the target), `results/wise0855_D6_sum_target.png`,
`results/wise0855_brightness.png`.

## RW Aurigae

Centre: RA 76.956587, Dec +30.401291 (SIMBAD `V* RW Aur`, a T Tauri star; SIMBAD lists
no Gaia identifier for it, the motion is Hipparcos's). 336 exposures, three visits:
September 2025, February to March 2026, September 2026.

| Detector | Frames | Dates of each frame | Exposures per frame | Saturated pixels per frame | Target visible? | Does it move? | Anything wrong |
|---|---|---|---|---|---|---|---|
| D1 | 3 | 2025-09-01 to 2025-09-04<br>2026-03-04 to 2026-03-12<br>2026-09-02 to 2026-09-09 | 19, 19, 18 | 0, 0, 0 | Yes, bright | No (not expected to) | Holes (no data) in frame 1 (two) and frame 3 (three, one of them about 30 by 40 arcsec). The star is visibly brighter in later frames. |
| D2 | 3 | 2025-09-08 to 2025-09-10<br>2026-03-01 to 2026-03-09<br>2026-09-10 to 2026-09-15 | 18, 19, 19 | 0, 0, 0 | Yes, bright | No | Nothing. |
| D3 | 3 | 2025-09-11 to 2025-09-20<br>2026-02-20 to 2026-03-02<br>2026-09-13 to 2026-09-16 | 19, 18, 18 | 0, 0, 0 | Yes, bright | No | Nothing. |
| D4 | 3 | 2025-09-01 to 2025-09-04<br>2026-03-04 to 2026-03-12<br>2026-09-02 to 2026-09-09 | 19, 19, 18 | 0, 0, 0 | Yes, bright | No | Nothing. |
| D5 | 3 | 2025-09-08 to 2025-09-10<br>2026-03-01 to 2026-03-09<br>2026-09-10 to 2026-09-15 | 18, 19, 19 | 0, 0, 0 | Yes, bright | No | Nothing wrong. The star is visibly fainter in frame 3. |
| D6 | 3 | 2025-09-11 to 2025-09-20<br>2026-02-20 to 2026-03-02<br>2026-09-13 to 2026-09-16 | 19, 19, 18 | 0, 0, 0 | Yes, bright | No | Nothing wrong. The star is visibly fainter in frames 2 and 3. |

- **Position.** The marker is between 1.5 arcsec west and 0.2 arcsec east of the
  catalogue position in every frame. The star does not move, as expected.
- **Field stars.** 5 to 10 per detector; median shift 0.15 to 0.44 arcsec.
- **Difference** (later visit minus the first). Detectors 1 and 2: the star is a round
  white patch, brighter than in September 2025. Detectors 5 and 6: a round black
  patch, fainter, and darker in the third visit than in the second. Detectors 3 and
  4: mixed. The other stars in the frame leave only faint speckle. This is a
  brightness change you can see in one image
  (`results/rw_aur_D1_diff_epoch3_minus_1.png`,
  `results/rw_aur_D6_diff_epoch3_minus_1.png`).
- **Brightness.** 131 of 336 exposures gave a flux; 167 are saturated (most of
  detectors 2 to 4). Comparing only inside the same wavelength bin, last visit over
  first: detector 1 (0.75 to 1.1 microns) a median factor of 1.64 (1.28 to 2.86 over
  13 bins); detector 6 (4.4 to 5 microns) 0.47 (2 bins), and 0.74 against the second
  visit (10 bins); detector 5 (3.8 to 4.4 microns) 0.60 against the second visit (9
  bins; the first visit is saturated there). Epsilon Indi B, measured the same way,
  gives 0.97 to 1.00 in detectors 3, 5 and 6, so this is not an effect of the method.
  Chart: `results/rw_aur_brightness.png`.

Images: `results/rw_aur_sheet.jpg`, `results/rw_aur_modes_sheet.jpg`,
`results/rw_aur_brightness.png`, and the two difference frames above.

## R Draconis

Centre: RA 248.167233, Dec +66.755024 (Gaia DR3 1648328016354496384; SIMBAD type Mira
variable). 548 exposures, three visits, each spread over two to three months: May to
July 2025, October 2025 to January 2026, April to July 2026.

| Detector | Frames | Dates of each frame | Exposures per frame | Saturated pixels per frame | Target visible? | Does it move? | Anything wrong |
|---|---|---|---|---|---|---|---|
| D1 | 3 | 2025-06-06 to 2025-07-22<br>2025-10-17 to 2025-11-20<br>2026-07-06 to 2026-07-16 | 23, 45, 24 | 20, 0, 28 | Yes, very bright | No (not expected to) | Saturated core in frames 1 and 3, ragged; none in frame 2. |
| D2 | 3 | 2025-06-08 to 2025-07-02<br>2025-11-18 to 2025-12-14<br>2026-06-21 to 2026-06-23 | 36, 37, 19 | 110, 95, 84 | Yes, very bright | No | Saturated core in every frame. |
| D3 | 3 | 2025-05-16 to 2025-06-12<br>2025-12-26 to 2026-01-13<br>2026-04-22 to 2026-06-12 | 23, 24, 44 | 179, 142, 78 | Yes, very bright | No | Saturated core in every frame; its outline changes from frame to frame. |
| D4 | 3 | 2025-06-06 to 2025-07-22<br>2025-10-17 to 2025-11-20<br>2026-07-06 to 2026-07-16 | 21, 44, 23 | 271, 175, 191 | Yes, very bright | No | The largest saturated patch, about 30 arcsec across. |
| D5 | 3 | 2025-06-08 to 2025-07-02<br>2025-11-18 to 2025-12-14<br>2026-06-21 to 2026-06-23 | 36, 38, 19 | 81, 70, 67 | Yes, very bright | No | Saturated core in every frame. |
| D6 | 3 | 2025-05-16 to 2025-06-12<br>2025-12-26 to 2026-01-13<br>2026-04-22 to 2026-06-12 | 22, 24, 45 | 46, 46, 27 | Yes, very bright | No | Saturated core in every frame (the smallest). |

- **What the frames look like.** The star and its glow fill the picture. Because the
  brightness scale runs up to the brightest pixel, almost nothing else is visible:
  two or three field stars in detectors 1 and 2 (median shift 0.18 arcsec or less),
  none that could be measured in detectors 3 to 6.
- **Difference.** A hole with no data at the saturated core, and around it a dark
  ring: the star's outer light is fainter in the third visit than in the first, in
  every detector (`results/r_dra_D6_diff_epoch3_minus_1.png`). Second minus first is
  mixed in detectors 3 and 6.
- **Brightness.** No exposure gave a flux: 496 saturated, 52 too close to the detector
  edge. The backend's relative measure of the unsaturated outer light, which it
  trusts in detectors 5 and 6 only: last visit over first, 0.61 in detector 5 (0.45 to
  0.77 over 13 bins) and 0.51 in detector 6 (0.36 to 0.60 over 8 bins). Barnard's
  Star, measured the same way, gives 1.01 and 0.98. So R Draconis faded at 3.8 to 5
  microns between mid-2025 and mid-2026, but this is not a flux, and nothing can be
  said at shorter wavelengths. Chart: `results/r_dra_brightness.png`.

Images: `results/r_dra_sheet.jpg`, `results/r_dra_modes_sheet.jpg`,
`results/r_dra_D4_epoch1.png`, `results/r_dra_brightness.png`.

## The two pages

Loaded in headless Chrome 157 from a container built at commit `67557b5`, reading the
warmed cache; one screenshot per address, about 12 seconds after loading, nothing
clicked.

- **Front page (`/`)**, Barnard's Star, detector 5: the frame, a details box (dates,
  25 exposures, 3.80 to 4.43 microns, saturated pixels 0), play controls, and the
  line "Since frame 1: measured shift 10.2 north, 2.2 west. Gaia predicts 10.3 north,
  0.8 west. They differ by 1.4 arcsec, which is 0.23 of a SPHEREx pixel." Those are
  the numbers in this file. Data credits are on the page.
  (`results/page_front_barnard_D5.png`)
- **Front page, the other four targets** (`results/page_front_other_targets.png`):
  WISE 0855 and Epsilon Indi B as in problem 9; RW Aurigae detector 1 shows the three
  no-data holes as black squares; R Draconis detector 4 shows "Saturated pixels 191"
  with the hint of problem 10.
- **Single-page viewer (`/viewer.html`)**: Barnard's Star detector 5 in normal mode,
  RW Aurigae detector 6 in difference mode and WISE 0855 detector 6 in sum mode all
  drew a frame with the marker, the caption for that visit and the mode's
  explanation line (`results/page_viewer_barnard_D5.png`,
  `results/page_viewer_rw_aur_difference_wise0855_sum.png`).

## What was not checked

- Using the pages: buttons, menus, zoom, the spectrum panel, a phone. Only the
  screenshots above. The brightness chart and the spectrum were judged from the
  API's numbers and from charts drawn by `scripts/run_targets.py`, not from a page.
- Of the cached views, the ones looked at are: normal, difference against the first
  visit, and sum (on the sky and following the target), all requested with the motion
  values. Difference against the mean of all visits, and the views requested
  without motion values, were built and load, but were not looked at one by one.
- Epsilon Indi A in the wide view: seen to move the same way, not measured.
- Detector 6 at WISE 0855, visit 1, on its own: marginal (3 exposures).

## The warm-up, for the record (issue #14)

- 1,973 cutouts for the five targets at the default field of view; 511 MB on disk.
  Not one failed to download in any run.
- Downloading the four targets that were not already cached took 17.6 minutes.
  Building all 364 views from cached cutouts took 14.8 minutes on a laptop.
- `python scripts/warm_cache.py --check` then loaded all 364 with the network blocked
  inside the script: every one in under 0.01 seconds, 16 seconds in all.
- That check calls the backend's functions directly. Separately, every view was
  requested once through a local web server (network connected): 325 API requests
  (name lookups, frames in every mode with and without motion values, brightness
  chart, spectrum) and the 618 frame images they name. All answered correctly; the
  slowest took 0.02 seconds. It was not repeated with the network cable out.

## Files

- `results/<target>_sheet.jpg`: every normal frame of a target, one row per detector,
  whole frame and a 90 arcsec zoom. Yellow ticks: where the catalogue puts the target
  that visit. Red ticks: where it put it at the first visit. Cyan ring: the backend's
  marker. Green rings: field stars used for the stillness check. Purple: no data.
- `results/<target>_modes_sheet.jpg`: the sum frames (on the sky, following the
  target, and the diagnostic with nothing thrown out) and the difference frames.
- `results/<target>_brightness.png`: brightness against wavelength per visit, and each
  visit against the same wavelength bin's average.
- `results/<target>_D<n>_...png`: the frames themselves, exactly as the site serves them.
- `results/measured_tables.md` and `results/measured.json`: every number, per frame.
  `results/measured_tables_wide.md` and `measured_wide.json`: the wide Epsilon Indi view.

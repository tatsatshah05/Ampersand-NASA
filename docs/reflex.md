# Earth-reflex stacking: a distant world in one SPHEREx visit

Code: `backend/reflex.py` (entry `reflex_search`), checks `scripts/check_reflex.py`, pictures `scripts/plot_reflex.py`,
tests `tests/test_reflex.py`, numbers `docs/reflex/results.json`. The probe scripts the module was rebuilt from are in
`docs/reflex/probe/` (text copies, not run).

## What this is, and what it is not
A search that adds up all the exposures of ONE SPHEREx visit (10 to 17 days) along trial tracks that include the curve the
Earth's motion puts in the path of a distant body, after removing the fixed sky with the other visits. The track that gives
the brightest point gives the place, the drift and, from the size of the bend, a distance. No ephemeris is used in the
search; JPL is asked afterwards.

It is a **known-answer test on one known dwarf planet (Eris) in one sparse field**. It is not a discovery, it does not find
anything new, it cannot test Planet Nine or Planet X, and its false-alarm rate is only roughly measured (see below).
Distance from the parallax bend of a short arc is old (Bernstein and Khushalani 2000); shift-and-stack along
distance-dependent tracks is old (Bernstein et al. 2004, Rice and Laughlin 2020, KBMOD, heliostack). What we know of that
is new: we do not know of this having been done with SPHEREx data.

## The idea in three sentences
A body 50 to a few hundred AU away barely moves on its own, but the Earth's velocity turns as it orbits the Sun (its
acceleration toward the Sun is across SPHEREx's line of sight, which looks about 90 degrees from the Sun), so over a visit
the body's path on the sky is bent by a few to tens of arcseconds, and a straight line cannot imitate that bend. We add up
all the exposures along every possible bent path and take the one with the brightest point. The size of the bend is the
distance.

## The known-answer test: Eris
Eris (95.5 AU from SPHEREx in July 2025). Visit 2025-07-10 to 07-25: 57 usable D1-D3 exposures over 15.35 days, of which
46 are on the data along Eris's track (13.66 days). The search was given a field centre and 0.13 degrees (0.0169 square
degrees). **The patch was centred on Eris's JPL position (median over the visit)**, so this is not "searching the sky"; the
second row of the table moves the patch 2.5 arcmin away.

| Result | Centred on JPL's Eris | Moved 2 arcmin east, 1.5 north |
|---|---|---|
| Place of the strongest track vs JPL (SPHEREx observer), middle of visit | 1.2 arcsec | 1.1 arcsec |
| S/N | 14.8 | 15.6 |
| Drift (arcsec/day), JPL apparent linear drift (3.91, -3.61) | (4.11, -3.33) | (3.85, -3.44) |
| Best distance (AU), JPL 95.5 | 111 | 118 |
| Epoch-bootstrap 68% range (AU) | 100 to 143 (misses 95.5) | 91 to 138 (contains it) |
| Epoch-bootstrap 95% range (AU) | 77 to unbounded | 53 to unbounded |
| Statistical-only profile 2 sigma (AU, 2 to 3 times too narrow) | 82 to 156 | 89 to 147 |
| Straight track (free drift) rejected: delta S^2 | 48 | 55 |
| ... with any one epoch removed (14 epochs) | at least 17.2 | at least 22.8 |
| Highest other forward peak (raw S/N) | 6.8 | 7.9 |
| Highest reversed-Earth peak (raw S/N) | 6.4 | 8.35 (at the field edge, vetoed) |
| Other visits at Eris's place (mJy) | -0.0005 and -0.0018, errors 0.004: not there | same |

Lines scored by `scripts/check_reflex.py` (A1, A2, A5, A6 are the builder's; A4 was changed after the reviews to the
bootstrap 68% range, a strict choice, and A5b was added after them):
A1 place within 4 arcsec, A2 S/N at least 12, A4 the epoch-bootstrap 68% range contains JPL's distance and the best is
within 25%, A5 delta S^2 vs a straight track at least 25, A5b delta S^2 at least 9 with any one epoch left out, A6 drift
within 0.5 arcsec/day of JPL's.
**Centred run: all lines pass except A4** (the 68% range 100 to 143 AU misses 95.5 by 4.5 AU; the best, 111 AU, is 16% high;
the 95% range contains it). **Moved run: all lines pass.** The earlier line "no other track at S/N 8 or above, reversed Earth
below 8" is no longer a pass/fail line: see the false-alarm section.

So, honestly: **the detection, the place, the drift and the presence of the bend pass in both runs; the distance is right
to within about 15 to 25% but its interval is wide and one of the two 68% intervals misses the truth** (expected
about one time in three for an honest 68% interval). The bootstrap used 40 resamples, so the 95% range is crude.

Pictures: `docs/reflex/eris_profile.png` (S/N against 1/distance; the left half is the Earth's motion reversed, which no
real body follows) and `docs/reflex/eris_spectrum.png`.

### How much of the bend rests on one epoch
Leave-one-epoch-out (an epoch is the exposures of one detector within 0.2 day; 14 epochs), delta S^2 against a straight
track, centred run: 17.2 (the first epoch, the D1 exposures of 2025-07-10), then 40.3, 46.7, 39.0, 47.3, 45.5, 49.7, 51.6,
47.6, 43.3, 53.8, 47.8, 36.3, 47.8. Moved run: 22.8 for the same epoch, the rest 36 to 60. **With all exposures a straight
track is rejected at delta S^2 of 48 to 55 (about 7 sigma); without that one epoch it is rejected at 17 to 23 (about 4 to
5 sigma); A5 (at least 25) fails without it.** The review also found that 63% of the 1/d information sits in three exposures
of that first day, where Eris is 3.7 arcsec from a fixed star as bright as itself (review measurement, not re-run here).

### Spectrum: three band fluxes only
The module measures three band-averaged fluxes, in D1, D2 and D3 (0.75 to 2.4 micrometres), from the same exposures.
It does NOT give a 0.75 to 5 micrometre spectrum (D4 to D6 are not searched). Matched-filter flux along the blind track,
Eris: D1 0.105 +- 0.009, D2 0.066 +- 0.009, D3 0.049 +- 0.008 mJy (S/N 11.9, 7.7, 6.4). These are on the matched-filter scale,
about 0.68 of the aperture scale (13 static stars in the same exposures, review measurement; the ratio is the same in
the three detectors to a few per cent, so ratios between bands are not biased by it, but absolute values are low by about
1.5). On the aperture scale that is about 0.15, 0.10, 0.07 mJy. The probe's earlier aperture photometry (0.187, 0.096,
0.057) is not used as a reference: its D1 aperture takes in two fixed stars 3.7 and 9 arcsec away.
D3/D1 is 0.47 with the matched filter. A solar-coloured reflector also falls from D1 to D3 (about 1 : 0.95 : 0.72 in
F_nu, an approximate figure from solar colours, drawn as open circles in the picture), so the fall alone says nothing about
methane; Eris falls somewhat more steeply than that, which is as expected for its known methane ice, but three broad
bands cannot confirm methane (Eris's J-H also varies with rotation).

## What was searched
D1-D3, 0.13 degree square, 1/d from -0.02 to +0.02 per AU (distances from 50 AU outward), drift box centred on the
Earth's reflex rate with a radius of 1.5 times a circular orbit's speed plus 1 arcsec/day, at most 25 (24,439 trials in
Eris's field; the proposal's box would have given 44,649). The analysis choices (3 and 1.5 arcsec grids, drift step,
template of two exposures, 0.5 mJy mask, the drift box, the noise calibration and the acceptance lines) were made **after
a probe had already found Eris**; they are not blind to the answer.

## Controls and how each came out
- Earth's motion reversed (1/d < 0): best raw peak 6.4 (centred) and 8.35 (moved, at the field edge, with no detector
  at 2 sigma, still present in another visit, 58% of its signal in 3 exposures: all vetoes fire).
- Time-shuffled exposures (real visit of the Eris field): Eris drops from 14.8 to a best of 7.2, nothing survives.
- Other visits at Eris's place: not there.
- The review's real-data controls (their scripts are not in this repository; numbers quoted, not re-run): with east and north
  curvature fitted separately the best fit is (0.011, 0.014) per AU against JPL's 0.0105, delta S^2 0.11; ten stationary stars
  in the same exposures give 1/d = -0.00005 +- 0.00007 per AU and per-detector offsets of at most 0.11 arcsec; static-star frame
  offsets would move Eris's distance by under 1%; the Earth's position shifted by +-91 days, the sky position moved by 90
  degrees, or the sign reversed, removes the bend (delta S^2 1.5 to 8).
- **Not controls:** reversing the time order and shifting the Earth's position by +-30 days give the same answer (the review
  measured a correlation of +1.00 with the true curve), so they cannot show the bend is specifically the Earth's.
- Grid phase: the matched-filter maps are bilinearly resampled twice although the PSF is under-sampled, so S is kinked.
  Moving the grid by 0.5 to 1 arcsec with the same data gave 95 to 105 AU and S/N 14.2 to 15.4 (review). This, with the
  different templates that the shifted field centre selects for 40 of 57 exposures, is why the profile intervals are too narrow and
  why we quote the epoch bootstrap.
- Faint end, Sedna (visit 2025-08-18 to 09-07, 20.6 days, 56 of 58 exposures within 7.1 days, V about 20.8): no vetted candidate.
  Forced along JPL's track: S/N 7.5 combined (D1 3.9, D2 5.0, D3 3.1), at the threshold of 8. A raw 10.4 peak at (78, 183)
  arcsec is a fixed-star residual that is still there in other visits. The review found a sub-threshold peak of 7.1
  2.2 arcsec from JPL's Sedna: no stronger than noise peaks elsewhere (6.4 to 9). Not claimed as a recovery.

## False alarms (the threshold is NOT calibrated)
`CANDIDATE_SNR = 8` was set before the false-alarm rate was known and is **not derived from a blank-field distribution**.
Six null field-visits were searched with the full vetting (`python scripts/check_reflex.py null`; the Eris field in its
real visit with shuffled times and in its two other visits, the Sedna field the same way; 0.10 square degrees in total):

| Field, visit | Raw forward max | What vetting did | Raw reversed-Earth max |
|---|---|---|---|
| Eris field, visit 1 shuffled | 7.2 | nothing above 8 | 7.0 |
| Eris field, visit 2 (24.5 d, two merged groups) | 9.8 | 2 peaks, fixed star, still there elsewhere | 7.3 |
| Eris field, visit 3 (10.5 d) | 7.2 | nothing above 8 | 8.25, 8.1: both edge, still there, rejected |
| Sedna field, visit 1 shuffled | 8.0 | 1 peak, still there elsewhere | 7.3 |
| Sedna field, visit 2 (31.8 d merged) | 17.9 | 5 peaks, all fixed stars | 8.4: one detector, still there, rejected |
| Sedna field, visit 3 (13.4 d) | 11.2 | 2 peaks, fixed stars | 7.5 |

Raw peaks of 8 or more occurred in 4 of 6 forward maxima and 2 of 6 reversed maxima (3 peaks); **every one was removed by the
other-visit test or the new vetoes (edge, signal from three exposures, detectors), none survived**. So raw S/N 8 is not a
decision line; the vetting is. Vetted false candidates: 0 in 6 field-visits (0.10 square degrees), which only says the rate is
below about 0.5 per field-visit (95%, zero counts), not that it is zero. The earlier (190, +5) field gave raw peaks of 22
and 21 from a fixed star (vetoed) and a reversed-Earth peak of 9.2, with a 43-day merged "visit" where distance leverage
is meaningless. The review counted that 3 of 11 non-star raw maxima reached 8, consistent with the threshold sitting in the noise.
Not done: the blank-field distribution that would set the threshold; Makemake; a second visit of Eris; the predicted
place of Eris in the next visit; an Earth- or Mars-size limit.

## Limits
- **Depth.** On the matched-filter scale the S/N 8 mean flux over D1-D3 is 0.033 mJy (measured noise 1.03 times the formal
  noise); on the aperture scale about 0.05 mJy by the 0.68 ratio, and about 0.06 mJy by scaling Eris itself (0.113 mJy aperture
  mean at S/N 14.8 down to 8). That is a 50% completeness level, not a hard limit. It is about 0.6 magnitudes fainter than Eris
  (V 18.7): about V 19.3 for an Eris-coloured body and about V 20.7 for a Sedna-coloured one (scaled from Eris and from
  Sedna's forced S/N 7.5; the V values are not computed in the module). About 2 magnitudes shallower than Pan-STARRS (V 21.5),
  than the TESS shift-stack, and than Planet Nine's predicted brightness. This does not test Planet Nine or Planet X.
- **Ranging range.** The search detects movers from 50 AU outward. It gives a distance only where S/N x (1/d) is large
  enough: scaled from the measured Eris profile (arithmetic on measured numbers, not a simulation), delta S^2 of at least 9
  needs a body within about 120 AU at S/N 8 and about 200 AU at Eris's brightness, in a 15-day visit; the information
  goes as duration to the fourth power, so in a 10.5-day visit about 55 AU at S/N 8. Beyond that the search detects
  but does not range. It does not "cover 50 to 400 AU".
- **Distance precision.** About 15 to 25% best-value error in the two Eris runs, an epoch-bootstrap 68% range of about 90 to
  145 AU and a 95% range that is unbounded on the far side. The profile interval is statistical only, 2 to 3 times too narrow.
  The shifted run (118 AU) is a partly independent noise draw (different templates for 40 of 57 exposures), not a systematic.
- A limit is quoted with its area, 0.0169 square degrees per field.
- Tested positive on one object, one field, low ecliptic latitude, sparse sky. Not tested in crowded or Galactic-plane fields.
- A distance needs at least 8 days of exposures on the data along the track, a source seen on its best straight track
  (S/N 5), and delta S^2 of at least 9 with any one epoch left out.
- Visits that merge two real observations (field 190, +5: 43 days) are not meaningful for distance; check `visit.duration_days`.
- The known-body label is weak for distant bodies: JPL `sb_ident` did not list Eris in its own field. The module therefore also
  asks Horizons about a short list of named dwarf planets (Eris, Makemake, Haumea, Sedna, Gonggong, Quaoar, Orcus, Pluto), and
  with that Eris is labelled "known distant body", which is what it is; without it the verdict was "candidate". Neither list covers
  every known TNO: a real run should also be checked with the Minor Planet Center. "Blind" means the search did not use
  the ephemeris; the label is applied afterwards.
- Bodies nearer than 50 AU are not searched.

## What would confirm a candidate
A second visit: the fit from one visit predicts where the body is in the next (Eris jumps about 1.2 degrees), and a body at
100 AU should be at that place with a consistent distance. Then CatWISE and optical archives at that place.

## Literature (searched 2026-11-14)
Searches made by the builder and the reviewers (not repeated in this finalisation):
- Web and arXiv: SPHEREx with each of Neptunian, Kuiper belt, Eris, Sedna, "dwarf planet", "moving object", "solar system
  object": three entries (2402.08705, planetary-defence use of the SPHEREx solar-system catalogue; 2602.08037, asteroid light
  curves; 2511.02985, the mission paper), none on trans-Neptunian objects or a blind moving-object search.
- arXiv: SPHEREx with asteroid, comet, Centaur, Pluto, moving: ten entries (3I/ATLAS papers including 2512.07318, an ultracool-dwarf
  pipeline 2604.22012, others), none on TNOs. EPSC2026-797 (Mahlke et al., Year 1 asteroid census): asteroids only.
- The builder's queries: "SPHEREx trans-Neptunian / Kuiper belt", "SPHEREx Planet Nine shift-and-stack", "SPHEREx Eris Makemake
  Sedna Haumea", "SPHEREx solar system moving targets pipeline": spectra of known asteroids and a Centaur projection, nothing on
  a blind search.
- GitHub (other Space Apps 2026 teams): lzphellipe/spherex has a linear shift-and-stack but reports results only on a synthetic
  sky and does no ranging; Razor573/spectralx is an epoch-blinking viewer.

Prior work for the method: Bernstein and Khushalani 2000 (AJ 120, 3323, astro-ph/0008348): distance from the apparent
parallax acceleration of a one-week arc; Bernstein et al. 2004 (AJ 128, 1364): HST shift-and-stack on a grid in 1/d; Rice and
Laughlin 2020 (arXiv 2010.13791): TESS shift-stacking at 70 to 800 AU, Sedna blind-recovered at 93.3 AU; Stetzler et al. 2025
(arXiv 2509.26279): shift-and-stack on detection catalogues; heliostack (arXiv 2604.16731): 15 days of HST data with distance
fitted; the ACT Planet 9 stack (Naess et al. 2021); KBMOD. Planet Nine limits that are deeper over far larger areas: Meisner
et al. (WISE), Brown and Batygin 2021 (ZTF), Brown, Holman and Batygin 2024 (Pan-STARRS1).
**"We do not know of this having been done with real SPHEREx data" is the strongest statement allowed. It is not "never done".**

## Words for the demo
Say: "We tested a shift-and-stack search on real SPHEREx data. It adds up all the exposures of one 15-day visit along paths
that include the curve the Earth's motion puts in the path of a distant body, and it does not use the ephemeris. In a
0.13-degree patch centred on the dwarf planet Eris, and again with the patch moved 2.5 arcmin, it finds Eris about 1 to 2
arcsec from where JPL puts it, at S/N 15, and the bend in its track gives a distance of about 110 to 120 AU; JPL says 95.5,
and the honest range is roughly 90 to 145 AU, unbounded on the far side at 95%. A straight track is rejected at about 7 sigma
with all exposures and about 4 sigma if the first day is dropped. It also gives three band fluxes from 0.75 to 2.4 micrometres
from the same exposures. This is one known object in one sparse field: a known-answer test, not a discovery. Ranging a
body from one short arc is standard (Bernstein and Khushalani 2000) and shift-and-stack has been done with TESS and Hubble;
we do not know of it having been done with SPHEREx data."
Do not say: discovery, first, new planet, Planet Nine search or test, "finds Planet X"; "without being told where Eris is"
(the patch was centred on it); that it beats WISE or Pan-STARRS; that the distance is precise, or "105 AU, 1 sigma 91 to
111"; "6.8 sigma" without "and 4 sigma with the first day removed"; "a 0.75 to 5 micrometre spectrum"; "covers 50 to 400 AU";
"V 19 for a grey body"; "no other source above S/N 8" as if S/N 8 were a calibrated limit; "the false-alarm rate is
measured"; that it works anywhere in the sky.

## Repeat everything
```
cd <checkout root>
SPHEREX_CACHE_DIR=<cache holding the Eris and Sedna cutouts> .venv/bin/python scripts/check_reflex.py all && .venv/bin/python scripts/plot_reflex.py
```
`all` runs Eris (centred and shifted), Sedna and the six null field-visits (exit code 1 if an Eris line fails, which today
means A4 of the centred run). Tests, offline: `.venv/bin/python -m pytest -q tests/test_reflex.py`.

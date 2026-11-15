# Colour walk: does a star's image centre move with wavelength?

Status: **method not proven.** It passed most of its known-answer test on VHS 1256-1257 b but failed two checks that were written down before the run, and its null test did not meet its bar. Per the rules we set, no sample of hosts was run and no walk is presented as a finding. This page records exactly what was measured.

## The idea in three sentences
SPHEREx sees every star through one narrow colour per exposure, so a lone star sits at the same place in every colour. A star with a cool, red companion a few arcseconds away has its image centre pulled toward the companion at long wavelengths, where the companion is bright, and not at short ones, where it is dark. The direction of that pull points at the companion, and a two-source fit along that direction gives the companion's brightness in each colour.

Code: `backend/colourwalk.py` (entry `colour_walk`), repeat everything with `scripts/check_colourwalk.py`, results in `docs/colourwalk/results.json`, pictures in `docs/colourwalk/`.

## Analysis choices (fixed before any run)
7 x 7 pixel fit box, central 3 x 3 clean; pixel-integrated Gaussian, width 0.25 to 1.6 pixel; bins 0.75, 0.95, 1.12, 1.4, 1.65, 2.0, 2.43, 2.9, 3.4, 3.85, 4.15, 4.43, 4.7, 5.02 micrometres; walk = median at 2.9-5.02 minus median at 0.75-1.65, 0.04 arcsec added in quadrature to each group; separations 2-12 arcsec in 0.5 steps; controls at the walk angle plus 90, 180, 270 degrees; the pass bars below. Raw offsets from Gaia are used (no reference-star subtraction) for a host.

## The proof on a known object: VHS 1256-1257 b (Gauza et al. 2015: 8.06 arcsec, PA 218.1)
404 exposures, 351 clean fits, no download. The method was not told where b is.

| Check | Required | Measured | Pass |
|---|---|---|---|
| Walk direction | 218 +/- 15 | 218.4 | yes |
| Walk along PA 218 | at least 0.15 arcsec | 0.18 arcsec | yes |
| Across component | under 3 sigma | consistent with 0 | yes |
| Net ratio 2.0-2.43 um | 0.010-0.030 | 0.021 +/- 0.003 (2MASS Ks 0.0155) | yes |
| Net ratio 3.4-5.0 um | 0.04-0.10 | 0.052, 0.058, 0.063, 0.063, 0.072 (AllWISE W1 0.071, W2 0.101) | yes |
| Net ratio 0.75-1.4 um within 0.01 of 0 | 0 +/- 0.01 | -0.004, -0.016 +/- 0.007, +0.001 | **no** (the 0.95-1.12 bin) |
| Every individual control at most 0.02 | 0.02 | 0.025 in 4.43-4.7 um (control at PA 308); the median of the three controls is 0.004 | **no** |

Blind scan (companion placed along the walk, separation scanned): best separation 9.0 arcsec (true 8.06); the fit gain is flat from 8 to 9.5 arcsec, so separation is poorly pinned. Walk significance with the 0.04 floor: 2.7 sigma, below the 4 sigma the verdict rule asks for, so the verdict for VHS 1256 is "nothing_found". The two-source ratio is far more significant than the walk alone, but the rule was set on the walk and we did not change it after seeing the result. D4, D5, D6 walks separately: PA 223, 205, 225 degrees; sizes 0.17, 0.21, 0.21 arcsec at 2.3 to 2.9 sigma each.

The 0.025 control is not new: the inventor's own probe file for that control gives 0.025 too; the probe write-up said "0.004 to 0.016", which was wrong for that bin. Pictures: `docs/colourwalk/vhs1256_blind_offsets.png`, `vhs1256_blind_ratio.png`, `vhs1256_known_place_*.png`.

## The null test: Barnard's Star field (b = +14)
364 exposures, 58,897 star fits against Gaia (G<17.5, frame offsets removed per exposure using isolated stars).

- Isolated stars (G 11.5-15, no Gaia star brighter than G+3 within 12 arcsec) with usable data: 19. **Only 2 have every per-detector median within +/-0.06 arcsec** (needed: 10). The star-to-star scatter of per-detector medians is 0.049 arcsec East and 0.066 North (robust, 106 values). That is larger than the 0.04 floor, especially North. **This is the main measured limit: the floor is about 0.05 to 0.07, not 0.04.**
- All 19 isolated stars walk at under 3 sigma (needed 90 per cent): passes.
- Blended stars: with the first response guess (width 4.5 arcsec) the measured offset points along the Gaia-predicted direction (median cos 0.995, 9 stars) but is 1.61 times too large. Calibrating the response width to 8.5 arcsec gives slope 1.08 on 25 stars, with median cos 0.87 (below 0.9). So the neighbour model is directionally right and the size is calibrated only roughly.
- Walkers above 4 sigma: 2; both have a catalogued source (Gaia, 2MASS, AllWISE or CatWISE2020) along the walk direction at 2 to 12 arcsec.
- The false-walk rate in a clean field could not be measured: the Barnard field has no star with no Gaia neighbour within 15 arcsec, and the one high-latitude six-detector field in the cache (b = -48, 254 Gaia stars) had only 3 usable isolated stars. A quiet high-latitude field with more stars is needed, and was not available on disk.

Acceptance result: 2 of 3 null checks pass, so the null test fails.

## Second known answer: 2MASS J0219-3925 B
Our guess (Gaia DR3 4963614887043331072, 3.91 arcsec, PA 176) was checked against the discovery paper (Artigau et al. 2015, ApJ 806, 254, Table 2: 3.96 +/- 0.02 arcsec, PA 173.9 +/- 0.2). It matches, so it is an independent identification. The test was **not run**: the method had already failed an earlier step.

## What was not done, and why
Sample of hosts, 2M0219 fit, common-motion checks and mass statements: not run, by the stop-at-first-failure rule. No candidate exists.

## Literature searched
Web: SPHEREx with astrometry, centroid, photocentre, spectroastrometry, colour-induced displacement, binary companion; colour-dependent photocentre shifts in Gaia, WISE, SDSS; VHS 1256 b with SPHEREx; IRSA SPHEREx tools. Found: colour-induced displacement (Wielen 1996; Pourbaix et al. 2004, SDSS, five broad bands); spectroastrometry of binaries; IRSA's Tractor forced photometry at a known position (an existing capability). We do not know of SPHEREx data being used to detect companions from colour-dependent centroid shifts. The second halves of the SPIFF and SUDA papers were not read. VHS 1256 b is in 2MASS and deblended in AllWISE, so WISE does see it; do not say it cannot.

## Words for the demo
Say: "On a known planetary-mass companion (about 12-16 Jupiter masses) the SPHEREx image centre moves toward it at long wavelengths, in the right direction, by the size the method predicts; the test is not fully clean and we publish where it fails."
Do not say: first, discovery, new planet, exoplanet found by SPHEREx; any mass; that WISE cannot see wide companions; that a walk is a companion (a background red source does the same); any claim about hosts never run.

## What would confirm a candidate
No Gaia, 2MASS, AllWISE, CatWISE or Legacy Survey source at the inferred place; same direction in D4, D5 and D6; all rotated controls under 0.02; and a common-motion check (older catalogue position against SPHEREx's) for a host moving more than about 100 mas/yr.

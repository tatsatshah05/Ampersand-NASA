<!-- written by scripts/run_targets.py; do not edit by hand -->

<!-- eps_indi_b: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:24 UTC -->
### Epsilon Indi B

Centre of every view: RA 331.096653, Dec -56.800663, the position at 2026.0 from `resolve_name` (SIMBAD `* eps Ind B`, type BD*; astrometry from Gaia DR3): proper motion (3982.0, -2466.8) mas/yr, parallax 270.7 mas, 121.8 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D5 | 1 | 2025-04-24 to 2025-06-07 | 31 | 3.83-4.42 | 25 | 14; 560 | 14; 560 | 1573 | +0.2, -0.5 | 149 |
| D5 | 2 | 2025-10-02 to 2025-11-08 | 24 | 3.83-4.40 | 29 | 16; 585 | 16; 584 | 723 | +0.2, -0.4 | 101 |
| D5 | 3 | 2026-04-24 to 2026-04-30 | 7 | 3.83-4.32 | 45 | 15; 599 | 15; 592 | 605 | +0.5, -0.2 | 60 |
| D5 | 4 | 2026-09-28 to 2026-10-02 | 24 | 3.81-4.42 | 42 | 15; 606 | 15; 593 | 3214 | +0.1, -0.7 | 161 |

Field stars between the first frame and each later one (they should not move):

- D5: 37 stars; median shift at most 0.31 arcsec (epoch 1 to 3); largest single star 1.19 arcsec

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D5 | on the sky | 86 | 7 | 12; 481 | +0.4, -0.7 | 60 | 3 |
| D5 | following the target | 86 | 20 | 14; 549 | +0.2, -0.5 | 215 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 86 | | 14; 561 | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 467 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 46 | 32 | 0 | 14 | flux | no bin has a value in two epochs |
| D2 | 92 | 54 | 0 | 38 | flux | epoch 4/1: x1.00; 0.39 to 1.19; 12<br>epoch 4/2: x1.13; 0.42 to 1.39; 7<br>epoch 4/3: x1.14; 0.40 to 1.19; 3 |
| D3 | 95 | 72 | 0 | 23 | flux | epoch 4/1: x1.00; 0.91 to 1.05; 11<br>epoch 4/2: x0.97; 0.75 to 1.25; 13<br>epoch 4/3: x0.97; 0.83 to 1.01; 8 |
| D4 | 44 | 25 | 0 | 19 | flux | no bin has a value in two epochs |
| D5 | 84 | 52 | 2 | 30 | flux | epoch 4/1: x0.97; 0.94 to 1.03; 10<br>epoch 4/2: x0.98; 0.88 to 1.04; 8<br>epoch 4/3: x0.96; 0.89 to 0.98; 3 |
| D6 | 92 | 63 | 2 | 27 | flux | epoch 4/1: x0.98; 0.92 to 1.05; 8<br>epoch 4/2: x0.92; 0.88 to 1.07; 14<br>epoch 4/3: x1.02; 0.95 to 1.11; 8 |

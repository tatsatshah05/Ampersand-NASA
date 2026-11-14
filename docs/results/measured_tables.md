<!-- written by scripts/run_targets.py; do not edit by hand -->

<!-- barnard: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:20 UTC -->
### Barnard's Star

Centre of every view: RA 269.446267, Dec +4.768222, the position at 2026.0 from `resolve_name` (SIMBAD `NAME Barnard's star`, type BY*; astrometry from Gaia DR3): proper motion (-801.6, 10362.4) mas/yr, parallax 547.0 mas, 270.3 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 2025-08-27 to 2025-10-01 | 24 | 0.75-1.11 | 0 | 985; 6896 | 985; 6896 | 15 | +1.1, +0.9 | 26 |
| D1 | 2 | 2026-03-11 to 2026-03-11 | 18 | 0.74-1.09 | 0 | 1194; 8479 | 1194; 8335 | 11074 | -0.8, -1.0 | 25 |
| D1 | 3 | 2026-08-23 to 2026-09-02 | 18 | 0.74-1.10 | 16 | no data (saturated) | no data (saturated) | 3151 | +0.5, -0.0 | 23 |
| D2 | 1 | 2025-08-21 to 2025-08-30 | 18 | 1.10-1.63 | 19 | no data (saturated) | no data (saturated) | 98 | +1.2, +0.3 | 24 |
| D2 | 2 | 2026-03-15 to 2026-03-22 | 19 | 1.12-1.63 | 30 | no data (saturated) | no data (saturated) | 501 | -0.1, +0.4 | 63 |
| D2 | 3 | 2026-08-18 to 2026-09-22 | 25 | 1.09-1.66 | 29 | no data (saturated) | no data (saturated) | 288 | +0.2, -0.6 | 67 |
| D3 | 1 | 2025-08-15 to 2025-08-27 | 18 | 1.63-2.41 | 22 | no data (saturated) | no data (saturated) | 12 | +0.9, +0.1 | 38 |
| D3 | 2 | 2026-03-19 to 2026-05-05 | 24 | 1.62-2.41 | 30 | no data (saturated) | no data (saturated) | 11 | -0.3, +0.3 | 50 |
| D3 | 3 | 2026-08-16 to 2026-08-20 | 17 | 1.65-2.38 | 23 | no data (saturated) | no data (saturated) | 11 | +0.3, -0.5 | 36 |
| D4 | 1 | 2025-08-27 to 2025-10-01 | 23 | 2.44-3.80 | 14 | 915; 9412 | 915; 9357 | 214 | +0.9, -0.1 | 40 |
| D4 | 2 | 2026-03-11 to 2026-03-11 | 18 | 2.43-3.74 | 25 | no data (saturated) | no data (saturated) | 189 | -0.1, +0.1 | 51 |
| D4 | 3 | 2026-08-23 to 2026-09-02 | 18 | 2.42-3.76 | 34 | no data (saturated) | no data (saturated) | 450 | -0.1, -0.4 | 86 |
| D5 | 1 | 2025-08-21 to 2025-08-30 | 18 | 3.82-4.41 | 0 | 1264; 18499 | 1264; 18489 | 41 | +1.4, -0.0 | 62 |
| D5 | 2 | 2026-03-15 to 2026-03-22 | 19 | 3.81-4.41 | 0 | 1443; 21136 | 1443; 21119 | 67 | -0.1, +0.2 | 87 |
| D5 | 3 | 2026-08-18 to 2026-09-22 | 25 | 3.80-4.43 | 0 | 1366; 20936 | 1374; 20953 | 299 | +0.0, -0.1 | 77 |
| D6 | 1 | 2025-08-15 to 2025-08-27 | 17 | 4.42-5.00 | 0 | 942; 18610 | 942; 18518 | 104 | +0.9, -0.0 | 68 |
| D6 | 2 | 2026-03-19 to 2026-05-05 | 24 | 4.41-5.00 | 0 | 982; 19565 | 982; 19305 | 364 | -0.1, +0.2 | 64 |
| D6 | 3 | 2026-08-16 to 2026-09-22 | 19 | 4.43-4.98 | 0 | 1030; 19782 | 1030; 19116 | 541 | -0.0, -0.2 | 67 |

Field stars between the first frame and each later one (they should not move):

- D1: 12 stars; median shift at most 0.25 arcsec (epoch 1 to 3); largest single star 0.41 arcsec
- D2: 13 stars; median shift at most 0.38 arcsec (epoch 1 to 2); largest single star 0.62 arcsec
- D3: 13 stars; median shift at most 0.25 arcsec (epoch 1 to 3); largest single star 0.54 arcsec
- D4: 13 stars; median shift at most 0.16 arcsec (epoch 1 to 3); largest single star 0.36 arcsec
- D5: 13 stars; median shift at most 0.15 arcsec (epoch 1 to 2); largest single star 0.59 arcsec
- D6: 11 stars; median shift at most 0.23 arcsec (epoch 1 to 2); largest single star 0.77 arcsec

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D1 | on the sky | 60 | 0 | 841; 6280 | -0.3, -0.2 | 17 | 2 |
| D1 | following the target | 60 | 0 | 1077; 7589 | +0.5, +0.0 | 33 |  |
| D1 | following the target, nothing rejected (diagnostic, not served) | 60 | | 1092; 7547 | | | |
| D2 | on the sky | 62 | 0 | 1253; 6680 | +0.4, -1.4 | 14 | 2 |
| D2 | following the target | 62 | 15 | 2101; 10711 | +0.9, -0.0 | 39 |  |
| D2 | following the target, nothing rejected (diagnostic, not served) | 62 | | no data (saturated) | | | |
| D3 | on the sky | 59 | 2 | 1226; 7454 | -0.3, -0.5 | 14 | 2 |
| D3 | following the target | 59 | 18 | 1921; 10715 | +0.5, -0.4 | 37 |  |
| D3 | following the target, nothing rejected (diagnostic, not served) | 59 | | no data (saturated) | | | |
| D4 | on the sky | 59 | 0 | 696; 7395 | -0.6, -0.4 | 14 | 2 |
| D4 | following the target | 59 | 11 | 1453; 13783 | +0.8, -0.3 | 33 |  |
| D4 | following the target, nothing rejected (diagnostic, not served) | 59 | | no data (saturated) | | | |
| D5 | on the sky | 62 | 0 | 912; 14404 | -0.4, +0.5 | 25 | 2 |
| D5 | following the target | 62 | 0 | 1368; 20941 | +0.4, -0.1 | 84 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 62 | | 1390; 20209 | | | |
| D6 | on the sky | 60 | 0 | 698; 14480 | -0.5, +0.4 | 26 | 2 |
| D6 | following the target | 60 | 0 | 974; 18905 | +0.2, -0.0 | 84 |  |
| D6 | following the target, nothing rejected (diagnostic, not served) | 60 | | 994; 18772 | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 364 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 60 | 0 | 60 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D2 | 59 | 0 | 59 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D3 | 58 | 0 | 58 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D4 | 59 | 0 | 59 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D5 | 60 | 1 | 59 | 0 | wing (relative, not a flux) | epoch 3/1: x1.01; 0.97 to 1.07; 14<br>epoch 3/2: x1.00; 0.93 to 1.06; 16 |
| D6 | 58 | 3 | 55 | 0 | wing (relative, not a flux) | epoch 3/1: x0.98; 0.73 to 1.06; 14<br>epoch 3/2: x1.00; 0.92 to 1.10; 15 |

<!-- eps_indi_b: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:21 UTC -->
### Epsilon Indi B

Centre of every view: RA 331.096653, Dec -56.800663, the position at 2026.0 from `resolve_name` (SIMBAD `* eps Ind B`, type BD*; astrometry from Gaia DR3): proper motion (3982.0, -2466.8) mas/yr, parallax 270.7 mas, 121.8 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 2025-04-25 to 2025-04-27 | 4 | 0.76-1.09 | 3 | 5.608; 42 | 5.608; 42 | 0 | +1.0, -2.7 | 18 |
| D1 | 2 | 2025-10-03 to 2025-11-12 | 24 | 0.75-1.10 | 0 | 0.241; 3 | 1.228; 15 | 3632 | +0.3, -0.4 | 14 |
| D1 | 3 | 2026-04-18 to 2026-05-03 | 20 | 0.76-1.09 | 0 | 0.818; 10 | 1.885; 23 | 40102 | -0.0, -0.1 | 22 |
| D2 | 1 | 2025-04-24 to 2025-06-07 | 32 | 1.11-1.65 | 0 | 8.652; 171 | 9.322; 183 | 422 | +0.3, -0.5 | 94 |
| D2 | 2 | 2025-10-01 to 2025-11-08 | 30 | 1.11-1.62 | 0 | 6.151; 138 | 7.408; 167 | 175 | +0.1, -0.6 | 89 |
| D2 | 3 | 2026-04-24 to 2026-04-30 | 7 | 1.11-1.54 | 0 | 4.842; 102 | 7.712; 161 | 67 | +0.8, +0.1 | 25 |
| D2 | 4 | 2026-09-28 to 2026-10-02 | 24 | 1.09-1.64 | 0 | 6.973; 188 | 8.596; 224 | 10083 | +0.1, -0.5 | 57 |
| D3 | 1 | 2025-04-29 to 2025-06-10 | 25 | 1.65-2.38 | 0 | 7.411; 161 | 7.592; 165 | 98 | +0.2, -0.4 | 145 |
| D3 | 2 | 2025-09-28 to 2025-11-04 | 23 | 1.64-2.40 | 0 | 5.616; 162 | 6.083; 174 | 2901 | +0.2, -0.8 | 78 |
| D3 | 3 | 2026-04-29 to 2026-05-04 | 12 | 1.64-2.32 | 0 | 7.961; 180 | 8.087; 182 | 61 | +0.2, -1.0 | 68 |
| D3 | 4 | 2026-09-22 to 2026-09-28 | 36 | 1.62-2.42 | 0 | 6.245; 183 | 6.753; 198 | 94 | +0.1, -0.5 | 105 |
| D4 | 1 | 2025-04-25 to 2025-04-27 | 3 | 2.46-3.74 | 0 | 7.966; 481 | 7.966; 481 | 0 | +0.5, -0.6 | 37 |
| D4 | 2 | 2025-10-03 to 2025-11-12 | 23 | 2.44-3.79 | 0 | 4.000; 204 | 4.578; 233 | 403 | -0.0, -0.7 | 67 |
| D4 | 3 | 2026-04-18 to 2026-05-03 | 18 | 2.46-3.74 | 0 | 4.041; 213 | 4.736; 248 | 388 | +0.2, -0.5 | 66 |
| D5 | 1 | 2025-04-24 to 2025-06-07 | 31 | 3.83-4.42 | 0 | 14; 1067 | 14; 1060 | 319 | +0.2, -0.5 | 150 |
| D5 | 2 | 2025-10-02 to 2025-11-08 | 24 | 3.83-4.40 | 0 | 16; 979 | 16; 976 | 135 | +0.2, -0.4 | 100 |
| D5 | 3 | 2026-04-24 to 2026-04-30 | 7 | 3.83-4.32 | 0 | 15; 949 | 15; 949 | 8 | +0.5, -0.2 | 60 |
| D5 | 4 | 2026-09-28 to 2026-10-02 | 24 | 3.81-4.42 | 0 | 15; 1057 | 15; 1048 | 331 | +0.1, -0.7 | 161 |
| D6 | 1 | 2025-04-29 to 2025-06-10 | 26 | 4.43-4.98 | 0 | 5.913; 502 | 5.913; 500 | 73 | +0.5, -0.5 | 92 |
| D6 | 2 | 2025-09-28 to 2025-11-04 | 22 | 4.42-4.99 | 0 | 5.885; 412 | 5.885; 410 | 157 | +0.4, -0.8 | 86 |
| D6 | 3 | 2026-04-29 to 2026-05-04 | 11 | 4.43-4.94 | 0 | 5.647; 355 | 5.647; 353 | 203 | +0.6, -0.7 | 75 |
| D6 | 4 | 2026-09-22 to 2026-09-28 | 36 | 4.41-5.01 | 0 | 5.747; 498 | 5.779; 484 | 1187 | +0.3, -0.7 | 97 |

Field stars between the first frame and each later one (they should not move):

- D1: 4 stars; median shift at most 0.51 arcsec (epoch 1 to 3); largest single star 1.22 arcsec
- D2: 9 stars; median shift at most 0.25 arcsec (epoch 1 to 3); largest single star 0.40 arcsec
- D3: 8 stars; median shift at most 0.52 arcsec (epoch 1 to 3); largest single star 0.82 arcsec
- D4: 7 stars; median shift at most 0.41 arcsec (epoch 1 to 2); largest single star 0.87 arcsec
- D5: 6 stars; median shift at most 0.32 arcsec (epoch 1 to 4); largest single star 0.44 arcsec
- D6: 3 stars; median shift at most 0.30 arcsec (epoch 1 to 3); largest single star 0.86 arcsec

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D1 | on the sky | 48 | 0 | 0.563; 7 | +1.2, -0.7 | 30 | 2 |
| D1 | following the target | 48 | 0 | 0.513; 6 | +0.4, -0.5 | 24 |  |
| D1 | following the target, nothing rejected (diagnostic, not served) | 48 | | 1.533; 18 | | | |
| D2 | on the sky | 93 | 0 | 5.556; 125 | +0.3, -0.4 | 52 | 3 |
| D2 | following the target | 93 | 0 | 7.055; 158 | +0.2, -0.5 | 106 |  |
| D2 | following the target, nothing rejected (diagnostic, not served) | 93 | | 8.201; 180 | | | |
| D3 | on the sky | 96 | 0 | 5.199; 135 | +0.1, -0.8 | 52 | 3 |
| D3 | following the target | 96 | 0 | 6.725; 172 | +0.2, -0.6 | 141 |  |
| D3 | following the target, nothing rejected (diagnostic, not served) | 96 | | 7.150; 182 | | | |
| D4 | on the sky | 44 | 0 | 3.578; 191 | +0.4, -0.6 | 71 | 2 |
| D4 | following the target | 44 | 0 | 3.853; 204 | +0.1, -0.6 | 74 |  |
| D4 | following the target, nothing rejected (diagnostic, not served) | 44 | | 4.694; 248 | | | |
| D5 | on the sky | 86 | 0 | 12; 885 | +0.4, -0.7 | 60 | 3 |
| D5 | following the target | 86 | 0 | 14; 1071 | +0.2, -0.5 | 215 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 86 | | 14; 1056 | | | |
| D6 | on the sky | 95 | 0 | 5.035; 486 | +0.5, -0.9 | 46 | 3 |
| D6 | following the target | 95 | 0 | 5.875; 560 | +0.4, -0.7 | 111 |  |
| D6 | following the target, nothing rejected (diagnostic, not served) | 95 | | 5.950; 552 | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 467 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 46 | 32 | 0 | 14 | flux | no bin has a value in two epochs |
| D2 | 92 | 54 | 0 | 38 | flux | epoch 4/1: x1.00; 0.39 to 1.19; 12<br>epoch 4/2: x1.13; 0.42 to 1.39; 7<br>epoch 4/3: x1.14; 0.40 to 1.19; 3 |
| D3 | 95 | 72 | 0 | 23 | flux | epoch 4/1: x1.00; 0.91 to 1.05; 11<br>epoch 4/2: x0.97; 0.75 to 1.25; 13<br>epoch 4/3: x0.97; 0.83 to 1.01; 8 |
| D4 | 44 | 25 | 0 | 19 | flux | no bin has a value in two epochs |
| D5 | 84 | 52 | 2 | 30 | flux | epoch 4/1: x0.97; 0.94 to 1.03; 10<br>epoch 4/2: x0.98; 0.88 to 1.04; 8<br>epoch 4/3: x0.96; 0.89 to 0.98; 3 |
| D6 | 92 | 63 | 2 | 27 | flux | epoch 4/1: x0.98; 0.92 to 1.05; 8<br>epoch 4/2: x0.92; 0.88 to 1.07; 14<br>epoch 4/3: x1.02; 0.95 to 1.11; 8 |

<!-- wise0855: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:22 UTC -->
### WISE 0855-0714

Centre of every view: RA 133.759765, Dec -7.242182, the position at 2026.0 from `resolve_name` (SIMBAD `WISEA J085510.74-071442.5`, type BD*; astrometry from SIMBAD): proper motion (-8123.7, 673.2) mas/yr, parallax 439.0 mas, 211.9 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 2025-05-06 to 2025-05-06 | 4 | 0.99-1.07 | 0 | 0.007; 0 | 0.007; 0 | 0 | -10.5, +4.3 | 41 |
| D1 | 2 | 2025-10-31 to 2025-11-03 | 18 | 0.75-1.11 | 0 | 0.063; 10 | 0.060; 4 | 24885 | -7.6, +4.0 | 59 |
| D1 | 3 | 2026-05-01 to 2026-05-05 | 14 | 0.74-1.09 | 0 | 0.265; 42 | 0.266; 33 | 7386 | -2.6, +3.6 | 48 |
| D2 | 1 | 2025-05-06 to 2025-05-06 | 8 | 1.28-1.63 | 0 | -0.001; -0 | -0.001; -0 | 1 | -10.7, +4.0 | 53 |
| D2 | 2 | 2025-11-07 to 2025-12-13 | 25 | 1.10-1.63 | 0 | 0.068; 9 | 0.064; 5 | 10012 | -7.1, +3.7 | 56 |
| D2 | 3 | 2026-05-01 to 2026-05-14 | 15 | 1.11-1.59 | 0 | 0.270; 36 | 0.270; 36 | 0 | -2.7, +3.1 | 54 |
| D3 | 1 | 2025-05-05 to 2025-05-05 | 3 | 2.21-2.41 | 0 | 0.010; 1 | 0.010; 1 | 0 | -10.6, +4.2 | 35 |
| D3 | 2 | 2025-11-10 to 2025-12-13 | 21 | 1.63-2.39 | 0 | 0.044; 6 | 0.044; 6 | 9 | -7.1, +3.8 | 42 |
| D3 | 3 | 2026-04-21 to 2026-05-11 | 21 | 1.64-2.36 | 0 | 0.175; 23 | 0.175; 23 | 1 | -2.6, +3.4 | 39 |
| D4 | 1 | 2025-05-06 to 2025-05-06 | 4 | 3.36-3.64 | 0 | 0.003; 0 | 0.003; 0 | 0 | -10.7, +3.2 | 12 |
| D4 | 2 | 2025-10-31 to 2025-11-03 | 18 | 2.44-3.83 | 0 | 0.026; 4 | 0.026; 4 | 200 | -7.1, +3.6 | 25 |
| D4 | 3 | 2026-05-01 to 2026-05-05 | 14 | 2.43-3.74 | 0 | 0.086; 13 | 0.086; 13 | 494 | -2.5, +3.2 | 22 |
| D5 | 1 | 2025-05-06 to 2025-05-06 | 8 | 4.04-4.41 | 0 | 0.114; 10 | 0.114; 10 | 39 | -2.2, +1.2 | 9 |
| D5 | 2 | 2025-11-07 to 2025-12-13 | 25 | 3.82-4.41 | 0 | 0.103; 13 | 0.103; 13 | 50 | -2.6, +1.5 | 18 |
| D5 | 3 | 2026-05-01 to 2026-05-14 | 15 | 3.83-4.37 | 0 | 0.144; 17 | 0.144; 17 | 98 | -1.0, +1.4 | 30 |
| D6 | 1 | 2025-05-05 to 2025-05-05 | 3 | 4.86-5.00 | 0 | 0.093; 3 | 0.093; 3 | 0 | -0.7, +0.5 | 5 |
| D6 | 2 | 2025-11-10 to 2025-12-13 | 21 | 4.42-4.98 | 0 | 0.156; 14 | 0.156; 14 | 198 | -1.2, +0.5 | 19 |
| D6 | 3 | 2026-04-21 to 2026-05-11 | 21 | 4.42-4.97 | 0 | 0.187; 18 | 0.186; 17 | 621 | -0.6, +0.9 | 27 |

For comparison, the field star at RA 133.758165, Dec -7.241226 (same measure):

| Det | Epoch | Offset from the target's expected place (E, N arcsec) | Brightness (MJy/sr; in sigma) |
|---|---|---|---|
| D1 | 1 | -10.6, +3.8 | 0.396; 9 |
| D1 | 2 | -7.5, +3.7 | 0.402; 62 |
| D1 | 3 | -2.6, +3.1 | 0.380; 61 |
| D2 | 1 | -10.6, +3.8 | 0.384; 44 |
| D2 | 2 | -7.1, +3.7 | 0.392; 53 |
| D2 | 3 | -2.5, +3.1 | 0.414; 55 |
| D3 | 1 | -10.6, +3.8 | 0.232; 22 |
| D3 | 2 | -7.1, +3.7 | 0.259; 34 |
| D3 | 3 | -2.7, +3.1 | 0.239; 32 |
| D4 | 1 | -10.6, +3.8 | 0.078; 10 |
| D4 | 2 | -7.5, +3.7 | 0.110; 17 |
| D4 | 3 | -2.6, +3.1 | 0.127; 19 |
| D5 | 1 | -10.6, +3.8 | 0.072; 6 |
| D5 | 2 | -7.1, +3.7 | 0.096; 12 |
| D5 | 3 | -2.5, +3.1 | 0.141; 16 |
| D6 | 1 | -10.6, +3.8 | 0.014; 0 |
| D6 | 2 | -7.1, +3.7 | 0.089; 8 |
| D6 | 3 | -2.7, +3.2 | 0.169; 16 |

Field stars between the first frame and each later one (they should not move):

- D1: 6 stars; median shift at most 0.35 arcsec (epoch 1 to 3); largest single star 0.40 arcsec
- D2: 6 stars; median shift at most 0.27 arcsec (epoch 1 to 2); largest single star 0.42 arcsec
- D3: 5 stars; median shift at most 0.70 arcsec (epoch 1 to 3); largest single star 1.12 arcsec
- D4: 5 stars; median shift at most 0.31 arcsec (epoch 1 to 3); largest single star 0.39 arcsec
- D5: 5 stars; median shift at most 0.47 arcsec (epoch 1 to 2); largest single star 1.08 arcsec
- D6: 4 stars; median shift at most 0.49 arcsec (epoch 1 to 3); largest single star 0.59 arcsec

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D1 | on the sky | 36 | 0 | 0.067; 12 | -5.9, +4.0 | 81 | 2 |
| D1 | following the target | 36 | 0 | 0.098; 17 | -5.6, +3.8 | 33 |  |
| D1 | following the target, nothing rejected (diagnostic, not served) | 36 | | 0.098; 14 | | | |
| D2 | on the sky | 48 | 0 | 0.058; 8 | -6.7, +3.7 | 64 | 2 |
| D2 | following the target | 48 | 0 | 0.098; 13 | -6.2, +3.5 | 25 |  |
| D2 | following the target, nothing rejected (diagnostic, not served) | 48 | | 0.096; 9 | | | |
| D3 | on the sky | 45 | 0 | 0.082; 12 | -5.2, +3.7 | 42 | 2 |
| D3 | following the target | 45 | 0 | 0.094; 12 | -4.9, +3.6 | 26 |  |
| D3 | following the target, nothing rejected (diagnostic, not served) | 45 | | 0.095; 13 | | | |
| D4 | on the sky | 36 | 0 | 0.024; 4 | -5.9, +3.6 | 29 | 2 |
| D4 | following the target | 36 | 0 | 0.032; 5 | -5.3, +3.3 | 18 |  |
| D4 | following the target, nothing rejected (diagnostic, not served) | 36 | | 0.032; 5 | | | |
| D5 | on the sky | 48 | 0 | 0.089; 14 | -3.2, +1.8 | 22 | 2 |
| D5 | following the target | 48 | 0 | 0.112; 17 | -1.7, +1.3 | 27 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 48 | | 0.113; 17 | | | |
| D6 | on the sky | 45 | 0 | 0.140; 17 | -1.4, +1.0 | 24 | 2 |
| D6 | following the target | 45 | 0 | 0.163; 20 | -0.8, +0.7 | 32 |  |
| D6 | following the target, nothing rejected (diagnostic, not served) | 45 | | 0.164; 19 | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 258 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 36 | 31 | 0 | 5 | flux | epoch 3/2: x1.08; 0.89 to 1.17; 9 |
| D2 | 48 | 38 | 0 | 10 | flux | epoch 3/1: x1.28; 1.28 to 1.28; 1<br>epoch 3/2: x0.95; 0.86 to 1.28; 8 |
| D3 | 45 | 39 | 0 | 6 | flux | epoch 3/1: x1.25; 0.96 to 1.54; 2<br>epoch 3/2: x1.04; 0.81 to 1.48; 12 |
| D4 | 36 | 29 | 0 | 7 | flux | epoch 3/2: x0.90; 0.46 to 1.62; 10 |
| D5 | 48 | 29 | 0 | 19 | flux | epoch 3/1: x1.19; 1.19 to 1.19; 1<br>epoch 3/2: x0.73; 0.47 to 1.49; 5 |
| D6 | 45 | 30 | 0 | 15 | flux | epoch 3/1: x1.22; 1.22 to 1.22; 1<br>epoch 3/2: x0.62; -0.10 to 2.46; 7 |

<!-- rw_aur: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:22 UTC -->
### RW Aurigae

Centre of every view: RA 76.956587, Dec +30.401291, the position at 2026.0 from `resolve_name` (SIMBAD `V* RW Aur`, type TT*; astrometry from SIMBAD): proper motion (7.2, -20.3) mas/yr, parallax 15.4 mas, 0.6 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 2025-09-01 to 2025-09-04 | 19 | 0.75-1.12 | 0 | 42; 1625 | 42; 1566 | 26086 | -0.8, -0.6 | 74 |
| D1 | 2 | 2026-03-04 to 2026-03-12 | 19 | 0.74-1.11 | 0 | 67; 2496 | 67; 2480 | 2709 | -0.7, -0.3 | 71 |
| D1 | 3 | 2026-09-02 to 2026-09-09 | 18 | 0.75-1.10 | 0 | 80; 2916 | 80; 2916 | 13 | -0.7, -0.4 | 77 |
| D2 | 1 | 2025-09-08 to 2025-09-10 | 18 | 1.11-1.62 | 0 | 80; 2324 | 81; 2351 | 6 | -1.3, -0.3 | 95 |
| D2 | 2 | 2026-03-01 to 2026-03-09 | 19 | 1.09-1.65 | 0 | 135; 3625 | 135; 3598 | 2622 | -1.1, -0.3 | 116 |
| D2 | 3 | 2026-09-10 to 2026-09-15 | 19 | 1.12-1.65 | 0 | 121; 3293 | 122; 3323 | 6 | -1.1, -0.2 | 102 |
| D3 | 1 | 2025-09-11 to 2025-09-20 | 19 | 1.62-2.41 | 0 | 141; 4053 | 141; 4053 | 33 | -1.5, -0.4 | 74 |
| D3 | 2 | 2026-02-20 to 2026-03-02 | 18 | 1.64-2.38 | 0 | 192; 5525 | 192; 5525 | 1 | -0.7, -0.3 | 119 |
| D3 | 3 | 2026-09-13 to 2026-09-16 | 18 | 1.64-2.38 | 0 | 169; 4937 | 169; 4937 | 1 | -0.7, -0.3 | 142 |
| D4 | 1 | 2025-09-01 to 2025-09-04 | 19 | 2.43-3.85 | 0 | 295; 9471 | 297; 9497 | 108 | -1.5, -0.1 | 52 |
| D4 | 2 | 2026-03-04 to 2026-03-12 | 19 | 2.42-3.82 | 0 | 332; 10840 | 332; 10686 | 382 | +0.0, -0.2 | 68 |
| D4 | 3 | 2026-09-02 to 2026-09-09 | 18 | 2.45-3.79 | 0 | 248; 8796 | 248; 8653 | 409 | -0.6, +0.0 | 73 |
| D5 | 1 | 2025-09-08 to 2025-09-10 | 18 | 3.83-4.40 | 0 | 542; 17287 | 542; 17173 | 65 | -1.0, -0.1 | 55 |
| D5 | 2 | 2026-03-01 to 2026-03-09 | 19 | 3.81-4.42 | 0 | 518; 18037 | 518; 17861 | 169 | -0.2, -0.2 | 111 |
| D5 | 3 | 2026-09-10 to 2026-09-15 | 19 | 3.81-4.42 | 0 | 330; 13843 | 330; 13375 | 385 | -0.2, -0.2 | 134 |
| D6 | 1 | 2025-09-11 to 2025-09-20 | 19 | 4.41-5.00 | 0 | 628; 17906 | 628; 17532 | 360 | -0.8, +0.0 | 54 |
| D6 | 2 | 2026-02-20 to 2026-03-02 | 19 | 4.42-5.01 | 0 | 479; 16188 | 479; 15523 | 444 | -0.3, -0.2 | 87 |
| D6 | 3 | 2026-09-13 to 2026-09-16 | 18 | 4.43-4.98 | 0 | 366; 13640 | 366; 12873 | 688 | +0.2, -0.1 | 62 |

Field stars between the first frame and each later one (they should not move):

- D1: 8 stars; median shift at most 0.43 arcsec (epoch 1 to 3); largest single star 0.71 arcsec
- D2: 10 stars; median shift at most 0.38 arcsec (epoch 1 to 2); largest single star 0.57 arcsec
- D3: 7 stars; median shift at most 0.16 arcsec (epoch 1 to 3); largest single star 0.33 arcsec
- D4: 7 stars; median shift at most 0.15 arcsec (epoch 1 to 3); largest single star 0.34 arcsec
- D5: 7 stars; median shift at most 0.29 arcsec (epoch 1 to 2); largest single star 0.38 arcsec
- D6: 5 stars; median shift at most 0.44 arcsec (epoch 1 to 2); largest single star 0.62 arcsec

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D1 | on the sky | 56 | 0 | 66; 2593 | -0.7, -0.4 | 96 | 2 |
| D1 | following the target | 56 | 0 | 66; 2590 | -0.8, -0.4 | 95 |  |
| D1 | following the target, nothing rejected (diagnostic, not served) | 56 | | 67; 2585 | | | |
| D2 | on the sky | 56 | 0 | 119; 3381 | -1.1, -0.3 | 130 | 2 |
| D2 | following the target | 56 | 0 | 119; 3380 | -1.1, -0.3 | 130 |  |
| D2 | following the target, nothing rejected (diagnostic, not served) | 56 | | 123; 3433 | | | |
| D3 | on the sky | 55 | 0 | 178; 5217 | -0.9, -0.3 | 152 | 2 |
| D3 | following the target | 55 | 0 | 178; 5225 | -0.9, -0.3 | 152 |  |
| D3 | following the target, nothing rejected (diagnostic, not served) | 55 | | 182; 5298 | | | |
| D4 | on the sky | 56 | 0 | 304; 10061 | -0.7, -0.1 | 73 | 2 |
| D4 | following the target | 56 | 0 | 305; 10103 | -0.7, -0.1 | 72 |  |
| D4 | following the target, nothing rejected (diagnostic, not served) | 56 | | 312; 10345 | | | |
| D5 | on the sky | 56 | 0 | 476; 17901 | -0.5, -0.1 | 106 | 2 |
| D5 | following the target | 56 | 0 | 476; 17882 | -0.5, -0.2 | 106 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 56 | | 486; 17257 | | | |
| D6 | on the sky | 56 | 0 | 491; 16969 | -0.3, -0.1 | 85 | 2 |
| D6 | following the target | 56 | 0 | 491; 17004 | -0.3, -0.1 | 85 |  |
| D6 | following the target, nothing rejected (diagnostic, not served) | 56 | | 506; 16432 | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 336 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 55 | 42 | 2 | 11 | flux | epoch 3/1: x1.64; 1.28 to 2.86; 13<br>epoch 3/2: x1.32; 1.04 to 1.59; 10 |
| D2 | 54 | 19 | 28 | 7 | none | core saturated and the wing value is not trusted in this detector |
| D3 | 55 | 8 | 46 | 1 | none | core saturated and the wing value is not trusted in this detector |
| D4 | 54 | 3 | 51 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D5 | 54 | 29 | 22 | 3 | flux | epoch 3/2: x0.60; 0.55 to 0.68; 9 |
| D6 | 54 | 30 | 18 | 6 | flux | epoch 3/1: x0.47; 0.45 to 0.50; 2<br>epoch 3/2: x0.74; 0.62 to 0.84; 10 |

<!-- r_dra: commit 67557b5 (pipeline, photometry, astrometry and archive code last changed in c46075d), run 2026-11-14 20:23 UTC -->
### R Draconis

Centre of every view: RA 248.167233, Dec +66.755024, the position at 2026.0 from `resolve_name` (SIMBAD `V* R Dra`, type Mi*; astrometry from Gaia DR3): proper motion (-20.6, 6.1) mas/yr, parallax 1.3 mas, 0.6 arcsec from its J2000 place.

| Det | Epoch | Dates | Exposures | Wavelength at target (um) | Saturated px | At the expected place (MJy/sr; in sigma) | Same, nothing rejected | Rejected readings | Marker minus expected (E, N arcsec) | Marker S/N |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 2025-06-06 to 2025-07-22 | 23 | 0.74-1.12 | 20 | no data (saturated) | no data (saturated) | 28192 | +1.5, -1.8 | 14 |
| D1 | 2 | 2025-10-17 to 2025-11-20 | 45 | 0.74-1.11 | 0 | 1231; 5407 | 1231; 4854 | 65904 | +0.1, -0.4 | 20 |
| D1 | 3 | 2026-07-06 to 2026-07-16 | 24 | 0.74-1.12 | 28 | no data (saturated) | no data (saturated) | 9568 | +0.9, -0.5 | 10 |
| D2 | 1 | 2025-06-08 to 2025-07-02 | 36 | 1.11-1.62 | 110 | no data (saturated) | no data (saturated) | 17678 | -0.9, -0.0 | 15 |
| D2 | 2 | 2025-11-18 to 2025-12-14 | 37 | 1.11-1.66 | 95 | no data (saturated) | no data (saturated) | 23012 | -1.0, -0.1 | 29 |
| D2 | 3 | 2026-06-21 to 2026-06-23 | 19 | 1.09-1.64 | 84 | no data (saturated) | no data (saturated) | 21723 | -0.4, -0.4 | 25 |
| D3 | 1 | 2025-05-16 to 2025-06-12 | 23 | 1.62-2.40 | 179 | no data (saturated) | no data (saturated) | 314 | -2.8, -0.7 | 66 |
| D3 | 2 | 2025-12-26 to 2026-01-13 | 24 | 1.63-2.38 | 142 | no data (saturated) | no data (saturated) | 456 | +0.1, -2.4 | 32 |
| D3 | 3 | 2026-04-22 to 2026-06-12 | 44 | 1.63-2.41 | 78 | no data (saturated) | no data (saturated) | 12283 | +0.7, -0.6 | 12 |
| D4 | 1 | 2025-06-06 to 2025-07-22 | 21 | 2.43-3.76 | 271 | no data (saturated) | no data (saturated) | 115 | +1.6, -1.2 | 81 |
| D4 | 2 | 2025-10-17 to 2025-11-20 | 44 | 2.45-3.81 | 175 | no data (saturated) | no data (saturated) | 337 | -0.3, -0.5 | 55 |
| D4 | 3 | 2026-07-06 to 2026-07-16 | 23 | 2.43-3.80 | 191 | no data (saturated) | no data (saturated) | 478 | -0.5, -0.7 | 55 |
| D5 | 1 | 2025-06-08 to 2025-07-02 | 36 | 3.83-4.40 | 81 | no data (saturated) | no data (saturated) | 125 | -0.2, -1.0 | 48 |
| D5 | 2 | 2025-11-18 to 2025-12-14 | 38 | 3.83-4.43 | 70 | no data (saturated) | no data (saturated) | 35 | +0.4, -0.2 | 79 |
| D5 | 3 | 2026-06-21 to 2026-06-23 | 19 | 3.81-4.42 | 67 | no data (saturated) | no data (saturated) | 118 | -0.5, -0.2 | 42 |
| D6 | 1 | 2025-05-16 to 2025-06-12 | 22 | 4.41-4.99 | 46 | no data (saturated) | no data (saturated) | 760 | -0.7, -0.8 | 34 |
| D6 | 2 | 2025-12-26 to 2026-01-13 | 24 | 4.42-4.98 | 46 | no data (saturated) | no data (saturated) | 1275 | +0.6, -0.1 | 63 |
| D6 | 3 | 2026-04-22 to 2026-06-12 | 45 | 4.42-5.00 | 27 | no data (saturated) | no data (saturated) | 1271 | -0.0, -0.5 | 64 |

Field stars between the first frame and each later one (they should not move):

- D1: 3 stars; median shift at most 0.18 arcsec (epoch 1 to 3); largest single star 0.31 arcsec
- D2: 2 stars; median shift at most 0.17 arcsec (epoch 1 to 2); largest single star 0.29 arcsec
- D3: no isolated Gaia star was clean enough to measure in every frame
- D4: no isolated Gaia star was clean enough to measure in every frame
- D5: no isolated Gaia star was clean enough to measure in every frame
- D6: no isolated Gaia star was clean enough to measure in every frame

What the pipeline's marker follows: the motion passed in the request (from the name search).

Sum of every exposure of every epoch, and difference frames:

| Det | Sum | Exposures | Saturated px | At the predicted place (MJy/sr; in sigma) | Marker minus predicted (E, N arcsec) | Marker S/N | Difference frames |
|---|---|---|---|---|---|---|---|
| D1 | on the sky | 92 | 0 | 1213; 4642 | +0.2, -0.3 | 19 | 2 |
| D1 | following the target | 92 | 0 | 1213; 4647 | +0.2, -0.3 | 19 |  |
| D1 | following the target, nothing rejected (diagnostic, not served) | 92 | | 1235; 4011 | | | |
| D2 | on the sky | 92 | 77 | 2127; 3447 | -1.2, -0.0 | 28 | 2 |
| D2 | following the target | 92 | 77 | 2127; 3448 | -1.2, -0.0 | 27 |  |
| D2 | following the target, nothing rejected (diagnostic, not served) | 92 | | no data (saturated) | | | |
| D3 | on the sky | 91 | 78 | 1945; 2521 | +0.7, -1.0 | 10 | 2 |
| D3 | following the target | 91 | 78 | 1945; 2521 | +0.7, -1.0 | 10 |  |
| D3 | following the target, nothing rejected (diagnostic, not served) | 91 | | no data (saturated) | | | |
| D4 | on the sky | 88 | 162 | 2964; 4414 | +0.1, +0.0 | 57 | 2 |
| D4 | following the target | 88 | 163 | 2018; 3262 | -0.0, -0.1 | 64 |  |
| D4 | following the target, nothing rejected (diagnostic, not served) | 88 | | no data (saturated) | | | |
| D5 | on the sky | 93 | 59 | 5930; 7691 | -0.3, -0.1 | 40 | 2 |
| D5 | following the target | 93 | 59 | 5762; 7514 | -0.3, -0.2 | 40 |  |
| D5 | following the target, nothing rejected (diagnostic, not served) | 93 | | no data (saturated) | | | |
| D6 | on the sky | 91 | 26 | 7518; 12649 | -0.1, -0.5 | 52 | 2 |
| D6 | following the target | 91 | 26 | 7518; 12649 | -0.1, -0.5 | 52 |  |
| D6 | following the target, nothing rejected (diagnostic, not served) | 91 | | no data (saturated) | | | |

Brightness measurements (`/api/lightcurve`, with the name-search motion): 548 exposures. The last column compares the last epoch with each earlier one inside the same wavelength bin (median ratio; smallest to largest; number of bins).

| Det | Exposures | Gave a flux | Saturated | Flagged or no data | Value compared | Last epoch over an earlier one |
|---|---|---|---|---|---|---|
| D1 | 83 | 0 | 83 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D2 | 76 | 0 | 76 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D3 | 88 | 0 | 88 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D4 | 81 | 0 | 81 | 0 | none | core saturated and the wing value is not trusted in this detector |
| D5 | 78 | 0 | 78 | 0 | wing (relative, not a flux) | epoch 3/1: x0.61; 0.45 to 0.77; 13<br>epoch 3/2: x0.79; 0.70 to 1.09; 15 |
| D6 | 90 | 0 | 90 | 0 | wing (relative, not a flux) | epoch 3/1: x0.51; 0.36 to 0.60; 8<br>epoch 3/2: x0.65; 0.38 to 0.74; 16 |

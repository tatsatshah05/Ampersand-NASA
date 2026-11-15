# Sources: every piece of data the project uses, and where each claim comes from

Written 2026-11-15 for the NASA Space Apps 2026 submission and pitch. Part 1 backs up the three candidates
(A, B and C) claim by claim. Parts 2 to 5 cover everything else the app reads, the published values we compare
against, the software, and the acknowledgement sentences to copy into anything published.

Nothing about the candidates has been reported anywhere. They are candidates: found in no catalogue or report we
checked, and confirmed by nobody. The referee's ruling, `docs/sweep/vetting/ruling.json`, is the authority on
every number about them; this file says where its data came from.

## Part 1. The three candidates

### 1.1 The images

Every brightness, position and "not there in 2025" result about A, B and C was measured on NASA SPHEREx
**Level 2 spectral images** (calibrated single exposures, 0.75 to 5.0 micrometres) from two releases:

| Release | IRSA collection | DOI | Used for |
|---|---|---|---|
| SPHEREx Data Release 1 (DR1), spectral images | `spherex_dr1` | [10.26131/IRSA678](https://doi.org/10.26131/IRSA678) | every visit up to spring 2026 |
| SPHEREx Quick Release 3 (QR3), spectral images | `spherex_qr3` | [10.26131/IRSA662](https://doi.org/10.26131/IRSA662) | the July to September 2026 visit |

- Both releases are served by the NASA/IPAC Infrared Science Archive (IRSA). IRSA's overview pages give these
  DOIs: DR1 at https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html and QR3 at
  https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html (read 2026-11-15). IRSA says the DR1 and QR3
  spectral images are meant to be used together.
- Images were found with IRSA's SIA2 service (https://irsa.ipac.caltech.edu/SIA). Only a small patch of each
  was read: either through IRSA's cutout service or as byte ranges of the same files in IRSA's public copy on
  Amazon Web Services (bucket `nasa-irsa-spherex`, AWS Open Data Registry). Both give the same pixels
  (`scripts/check_s3.py`).
- Pipeline version: the file names carry `l2b-v27-2026-229`, the SPHEREx pipeline that made them (Akeson et
  al. 2026).

**Every exposure behind each candidate is listed** in its own file. Each row has the exposure ID, detector,
release, DOI, date (UTC), the wavelength at the candidate, the measurement and a direct IRSA download link:

| Candidate | File | Exposures | DR1 / QR3 | First to last exposure |
|---|---|---|---|---|
| A, Sagittarius | [`docs/sources/candidate_A_exposures.csv`](sources/candidate_A_exposures.csv) | 327 | 216 / 111 | 2025-08-24 to 2026-09-22 |
| B, Scorpius | [`docs/sources/candidate_B_exposures.csv`](sources/candidate_B_exposures.csv) | 370 | 230 / 140 | 2025-08-02 to 2026-08-25 |
| C, Norma | [`docs/sources/candidate_C_exposures.csv`](sources/candidate_C_exposures.csv) | 425 | 256 / 169 | 2025-07-30 to 2026-09-12 |

The visits in those lists:

| Candidate | Not there | Bright | Later |
|---|---|---|---|
| A | 2025-08-24 to 2025-09-10 | 2026-03-20 to 2026-04-01 | 2026-08-25 to 2026-09-22 (still bright, fading) |
| B | 2025-08-02 to 2025-09-15 | 2026-02-26 to 2026-03-16 | 2026-08-08 to 2026-08-25 (brighter) |
| C | 2025-07-30 to 2025-08-19 | 2026-02-19 to 2026-03-03 | 2026-04-09 to 04-10 (2 exposures); 2026-07-28 to 2026-09-12 (faded, lines persist) |

The measurements in the CSV files are from `backend/sweep.py` (its `describe` step, a fit with the neighbouring
stars modelled), made on 2026-11-15 at 07:16 UTC and saved in `docs/sweep/vetting/rerun.json`. The ruling's
numbers come from four independent reviewers' own code on the same exposures (`docs/sweep/vetting/reviews_*.json`).
The two agree: positions within 0.16 to 0.21 arcsec, absent in 2025 for all three (`docs/sweep.md`, "What the
code does now").

The whole-plane sweep that first found them (472.6 square degrees, 1,162,894 sources compared, 6,023 changes,
109 seen in every image, 14 survivors, 3 candidates) used detector 6 of the same releases, read whole from the
AWS copy. Its tallies are in `docs/sweep/summary.json` and `docs/sweep.md`, "The tallies, every stage".

### 1.2 Each claim and what it rests on

| Claim | Data | Where the evidence is |
|---|---|---|
| Positions: A 270.80408 -23.46818, B 253.18038 -44.67697, C 241.70906 -52.20564 (J2000, about 0.3 arcsec) | SPHEREx exposures above (fits in 60, 97 and 53 exposures of detectors 3 to 6) | `ruling.json`; `rerun.json` |
| Not detected in 2025 | SPHEREx first-visit exposures, fitted with the neighbouring stars modelled; the neighbours themselves are in 2MASS, AllWISE and CatWISE2020 | `ruling.json`; `docs/sweep.md`, each candidate's brightness table |
| Brightness and rise in 2026 (A more than 100 times, B at least 250, C at least 30) | SPHEREx 2026 exposures, same fits | `ruling.json`; `docs/sweep/candidate_*_lightcurve.png` |
| Nothing at the place in older surveys | NEOWISE single exposures (2010 or 2014 to 2024), Spitzer GLIMPSE I and II, Deep GLIMPSE, APOGLIMPSE and MIPSGAL, VVV / VIRAC2, 2MASS | `docs/sweep.md`, the "brightest it can have been there" tables; `docs/sweep/vetting/*/archives/` |
| No catalogued star or variable at the place | Gaia DR3, SIMBAD, AAVSO VSX, CatWISE2020, AllWISE, 2MASS, GLIMPSE, GLIMPSE II (the eight services in `backend/sweep.py`, `SERVICES`) | `rerun.json`, `catalogue_answers` and `nearest` |
| Not a known asteroid or comet | JPL Small-Body Identification API | `docs/sweep.md`, "Is it real?" |
| The steady neighbours | A: 2MASS 18031245-2327467 (AllWISE W2 6.49 = 437 mJy), 20 arcsec. B: 2MASS 16524412-4440318 (40 mJy), 10 arcsec. C: a Herschel Hi-GAL cold clump (HIGALBM G330.4120-00.0823) at 3.5 to 3.75 arcsec, a Gaia DR3 star of type RS (5933349095879173504) at 11.95 arcsec and a VVV contact binary at 15.46 arcsec | `docs/sweep.md`; `searches-for-earlier-reports.md` |
| Not reported by anyone, as far as we could find | More than 30 catalogues and alert lists per candidate, each tested on a known object (Part 2) | `docs/sweep/searches-for-earlier-reports.md` (every search, its time, its control and its answer) |

What may be said about them, word for word, is in `ruling.json` (`what_can_be_said`) and
`frontend/src/finds.ts`. Never "discovery" or "new" without the qualifier.

### 1.3 Surveys that showed nothing at the places, with references

| Survey | What it measured | Reference |
|---|---|---|
| NEOWISE-Reactivation single exposures (IRSA table `neowiser_p1bs_psd`) | 3.4 and 4.6 micrometres, about twice a year, 2013 to 2024 | Mainzer et al. 2011, 2014 |
| WISE and AllWISE (`allwise_p3as_psd`) | 3.4 to 22 micrometres, 2010 | Wright et al. 2010; Cutri et al. 2013 |
| CatWISE2020 (`catwise_2020`) | 3.4 and 4.6 micrometres, 2010 to 2018 | Marocco et al. 2021 |
| 2MASS All-Sky Point Source Catalog (`fp_psc`) | 1.2 to 2.2 micrometres, 1997 to 2001 | Skrutskie et al. 2006 |
| Spitzer GLIMPSE I and II (`glimpse_s07`, `glimpse2_v2cat`) | 3.6 to 8 micrometres, 2004 to 2006 | Benjamin et al. 2003; Churchwell et al. 2009 |
| Spitzer Deep GLIMPSE and APOGLIMPSE | 3.6 and 4.5 micrometres, 2012 to 2018 | Whitney et al. 2011; Benjamin et al. 2016 (as cited in IRSA's data descriptions) |
| Spitzer MIPSGAL | 24 micrometres, 2005 to 2006 | Carey et al. 2009 |
| VVV / VIRAC2 (VizieR II/387) | 2.2 micrometres, many epochs 2010 to 2019 | Minniti et al. 2010; Smith et al. 2025 |
| Herschel Hi-GAL compact sources | 70 to 500 micrometres (cold dust) | Molinari et al. 2010; Elia et al. 2017 |
| Gaia DR3 | positions and brightness of visible stars, data to 2017 | Gaia Collaboration, Prusti et al. 2016; Vallenari et al. 2023 |

## Part 2. Where we looked for an earlier report

Full record, with every search's time (UTC), control and result: `docs/sweep/searches-for-earlier-reports.md`.
A search counts only if it found a known object first (its control). These held 2025-26 events, so only they could
carry a report of these brightenings:

| Source | Address | Reference |
|---|---|---|
| Transient Name Server (IAU) | https://www.wis-tns.org | |
| AAVSO Variable Star Index (VSX), live and VizieR's copy of 2026-10-18 (B/vsx) | https://www.aavso.org/vsx/index.php | Watson, Henden and Price 2006 |
| The Astronomer's Telegram: titles, and full text through the site's own search form | https://www.astronomerstelegram.org | Rutledge 1998 |
| CBAT: CBET titles and the unconfirmed-transient list (TOCP) | http://www.cbat.eps.harvard.edu/unconf/tocp.html | |
| Koji Mukai's lists of Galactic novae and of Fermi-LAT novae (NASA GSFC) | https://asd.gsfc.nasa.gov/Koji.Mukai/novae/novae.html | |
| ASAS-SN transients page | https://www.astronomy.ohio-state.edu/asassn/transients.html | Shappee et al. 2014; Kochanek et al. 2017 |
| ZTF alert brokers ALeRCE, ANTARES and Fink (A only; B and C are too far south) | https://api.alerce.online, https://api.antares.noirlab.edu, https://api.fink-portal.org | Bellm et al. 2019; Förster et al. 2021; Matheson et al. 2021; Möller et al. 2021 |
| vsnet-alert archive | http://ooruri.kusastro.kyoto-u.ac.jp/mailarchive/vsnet-alert/msglist | |
| MAXI flash reports and nova alerts | http://maxi.riken.jp/alert/novae/index.html | Matsuoka et al. 2009 |
| Swift/BAT Hard X-ray Transient Monitor (C) | https://swift.gsfc.nasa.gov/results/transients/ | Krimm et al. 2013 |
| British Astronomical Association VSS circulars; AAVSO forum and campaigns | https://britastro.org/vss, https://www.aavso.org/apps/campaigns | |
| Papers on SPHEREx and VVV transients | | Karambelkar et al. 2026 (arXiv:2602.07129); Li, Wang and Lin 2026 (A&A 710, A83; arXiv:2604.19551); Li and Wang 2024; Lucas et al. 2024 (MNRAS 528, 1789); Guo et al. 2024 (MNRAS 528, 1769) |

Older catalogues, which show only that no known variable or earlier eruption sat at the places (most through
VizieR's CfA mirror):

| Catalogue | VizieR | Reference |
|---|---|---|
| General Catalogue of Variable Stars 5.1 and NSV | B/gcvs | Samus et al. 2017 |
| Gaia DR3 variability and science alerts | I/358 | Eyer et al. 2023; Hodgkin et al. 2021 |
| ASAS-SN variable stars | II/366 | Jayasinghe et al. 2018 and later papers |
| SPICY (Spitzer young stars) | J/ApJS/254/33 | Kuhn et al. 2021 |
| VIVACE (VVV variables) | J/MNRAS/509/2566 | Molnar et al. 2022 |
| VVV high-amplitude and eruptive variables | J/MNRAS/465/3011, 465/3039, 472/2990 | Contreras Peña et al. 2017a, 2017b; Lucas et al. 2017 |
| Nova catalogues | J/ApJ/834/196, J/MNRAS/517/6150, J/ApJ/788/164, J/A+A/554/A123, J/ApJ/912/19 | Shafter 2017; Schaefer 2022; Pagnotta and Schaefer 2014; Saito et al. 2013; De et al. 2021 |
| Cataclysmic variables | B/cb, V/123A | Ritter and Kolb 2003; Downes et al. 2001 |
| OGLE-IV transients; eROSITA Galactic X-ray transients | J/AcA/64/197; J/MNRAS/544/885 | |
| SIMBAD (CfA mirror; the CDS original was down, so these did not pass their controls and are not counted) | | Wenger et al. 2000 |

Not yet searched, so the public sentence keeps its last clause: a person reading the Astronomer's Telegrams in
full, NASA ADS, SIMBAD at CDS, and the CBETs themselves. The checklist is section (d) of
`docs/sweep/searches-for-earlier-reports.md`.

## Part 3. Every outside source the app reads

From the code (`backend/`, `frontend/src/`), checked 2026-11-15:

| Source | Used for | Address in the code | Reference |
|---|---|---|---|
| SPHEREx DR1 and QR3 spectral images | every picture, brightness and spectrum | `backend/spherex.py` (IRSA SIA2 and cutouts), `backend/s3fetch.py` (AWS copy) | DOIs above; Bock et al. 2026; Akeson et al. 2026 |
| SPHEREx deep-field collections (`spherex_dr1_deep`, `spherex_qr3_deep`) | transit tests only | `backend/transits.py` | Bock et al. 2026 |
| Gaia DR3 | target motion, field stars, known neighbours | ESA TAP (`gea.esac.esa.int`); VizieR CfA copy of I/355; ARI Heidelberg mirror; IRSA `gaia_dr3_source` | Vallenari et al. 2023 |
| SIMBAD | name lookup, What is it? | CfA mirror (`simbad.harvard.edu`), then CDS | Wenger et al. 2000 |
| IRSA Gator: 2MASS, AllWISE, CatWISE2020, NEOWISE-R, GLIMPSE, GLIMPSE II | catalogue checks in the searches and sweep | `irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query` | Part 1.3 |
| AAVSO VSX | known-variable check | `vsx.aavso.org`, then `www.aavso.org/vsx` | Watson et al. 2006 |
| JPL Small-Body Identification API and Horizons | asteroid and comet labels; Eris's position | `ssd-api.jpl.nasa.gov/sb_ident.api`, `ssd.jpl.nasa.gov/api/horizons.api` | Giorgini et al. 1996 |
| HiPS sky images: AllWISE colour, 2MASS colour, DSS2 colour | the sky-context panel | IRSA and ESA HiPS mirrors | Fernique et al. 2015; survey references above; DSS (STScI) |
| Aladin Lite | the sky-context panel | CDS | Boch and Fernique 2014 |
| CIE 1931 colour-matching functions (CVRL, UCL copy) | colour of the object card's drawing (labelled as a drawing) | `frontend/src/portrait.ts` | CIE 1931 |
| 2MASS through VizieR's CfA mirror (II/246) | flux-scale check only | `scripts/check_flux_scale.py` | Skrutskie et al. 2006 |
| AAVSO International Database | outside check of R Draconis and RW Aurigae | `docs/verification.md` | AAVSO |

The training mode and the planted object in the distant-world search are simulations and use no outside data
beyond the real frames they are drawn on.

## Part 4. Published values the pitch and the app compare against

| Value | Where it is shown | Source |
|---|---|---|
| Barnard's Star motion and parallax | slide 5; the viewer | Gaia DR3 4472832130942575872 (Vallenari et al. 2023) |
| WISE 0855's motion and parallax | slide 5 | Kirkpatrick et al. 2021, through SIMBAD |
| Eris's position | slide 5 | JPL Horizons (Giorgini et al. 1996) |
| WASP-62 b transit depth, 1.23 per cent | slide 5 | Kokori et al. 2023 (ExoClock); other published depths 1.13 to 1.47 per cent, listed in `docs/transits.md` (Hellier et al. 2012 and others) |
| The two known novae, V7994 Sgr and V0691 Ser | slide 5 | AAVSO VSX |
| NEOWISE surveyed the sky about twice a year, 2014 to August 2024 | slide 2 | Mainzer et al. 2014; NASA/JPL |
| SPHEREx: whole sky every six months, 102 colours, 0.75 to 5 micrometres | slides 2 and 3 | Bock et al. 2026 |
| WiseView and Backyard Worlds | slide 3 | Caselden et al. 2018; Kuchner et al. 2017 |
| R Draconis and RW Aurigae variability | the brightness tool | AAVSO International Database |

## Part 5. Software

Astropy (Astropy Collaboration 2013, 2018, 2022), NumPy (Harris et al. 2020), SciPy (Virtanen et al. 2020),
reproject (https://reproject.readthedocs.io), Pillow, requests, FastAPI, React and Vite, Aladin Lite (Boch and
Fernique 2014).

## Acknowledgements to copy

SPHEREx (wording read from IRSA's SPHEREx pages on 2026-11-15, where IRSA asks for it in any published material):

> This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch
> of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the
> California Institute of Technology, and is funded by the National Aeronautics and Space Administration.

IRSA (https://irsa.ipac.caltech.edu/ack.html; check the wording there before publishing):

> This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National
> Aeronautics and Space Administration and operated by the California Institute of Technology.

Gaia:

> This work has made use of data from the European Space Agency (ESA) mission Gaia
> (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC,
> https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national
> institutions, in particular the institutions participating in the Gaia Multilateral Agreement.

2MASS:

> This publication makes use of data products from the Two Micron All Sky Survey, which is a joint project of the
> University of Massachusetts and the Infrared Processing and Analysis Center/California Institute of Technology,
> funded by the National Aeronautics and Space Administration and the National Science Foundation.

WISE and NEOWISE:

> This publication makes use of data products from the Wide-field Infrared Survey Explorer, which is a joint
> project of the University of California, Los Angeles, and the Jet Propulsion Laboratory/California Institute of
> Technology, funded by the National Aeronautics and Space Administration. This publication also makes use of data
> products from NEOWISE, which is a project of the Jet Propulsion Laboratory/California Institute of Technology,
> funded by the Planetary Science Division of the National Aeronautics and Space Administration.

Spitzer:

> This work is based in part on observations made with the Spitzer Space Telescope, which was operated by the Jet
> Propulsion Laboratory, California Institute of Technology under a contract with NASA.

SIMBAD and VizieR:

> This research has made use of the SIMBAD database and the VizieR catalogue access tool, operated at CDS,
> Strasbourg, France.

AAVSO:

> We acknowledge with thanks the variable star observations from the AAVSO International Database contributed by
> observers worldwide and used in this research.

## References

SPHEREx

- Bock, J. J., et al. 2026, ApJ, 999, 139, "The SPHEREx Satellite Mission". doi:10.3847/1538-4357/ae2be2; arXiv:2511.02985
- Akeson, R., et al. 2026, ApJS, 285, 67, "The SPHEREx Image and Spectrophotometry Processing Pipeline". arXiv:2511.15823
- SPHEREx Team 2026, SPHEREx DR1 Spectral Images, IPAC. doi:10.26131/IRSA678
- SPHEREx Team 2026, SPHEREx Quick Release 3 Spectral Images, IPAC. doi:10.26131/IRSA662

Surveys and catalogues

- Benjamin, R. A., et al. 2003, PASP, 115, 953 (GLIMPSE). doi:10.1086/376696
- Carey, S. J., et al. 2009, PASP, 121, 76 (MIPSGAL). doi:10.1086/596581
- Churchwell, E., et al. 2009, PASP, 121, 213 (GLIMPSE). doi:10.1086/597811
- Cutri, R. M., et al. 2013, Explanatory Supplement to the AllWISE Data Release Products, IPAC
- Elia, D., et al. 2017, MNRAS, 471, 100 (Hi-GAL compact sources). doi:10.1093/mnras/stx1357
- Eyer, L., et al. 2023, A&A, 674, A13 (Gaia DR3 variability)
- Gaia Collaboration, Prusti, T., et al. 2016, A&A, 595, A1. doi:10.1051/0004-6361/201629272
- Gaia Collaboration, Vallenari, A., et al. 2023, A&A, 674, A1 (Gaia DR3). doi:10.1051/0004-6361/202243940
- Hodgkin, S. T., et al. 2021, A&A, 652, A76 (Gaia science alerts)
- Jayasinghe, T., et al. 2018, MNRAS, 477, 3145 (ASAS-SN variable stars)
- Kuhn, M. A., et al. 2021, ApJS, 254, 33 (SPICY)
- Mainzer, A., et al. 2011, ApJ, 731, 53 (NEOWISE). doi:10.1088/0004-637X/731/1/53
- Mainzer, A., et al. 2014, ApJ, 792, 30 (NEOWISE-Reactivation). doi:10.1088/0004-637X/792/1/30
- Marocco, F., et al. 2021, ApJS, 253, 8 (CatWISE2020). doi:10.3847/1538-4365/abd805
- Minniti, D., et al. 2010, New Astronomy, 15, 433 (VVV). doi:10.1016/j.newast.2009.12.002
- Molinari, S., et al. 2010, PASP, 122, 314 (Hi-GAL). doi:10.1086/651314
- Molnar, T. A., et al. 2022, MNRAS, 509, 2566 (VIVACE)
- Samus, N. N., et al. 2017, Astronomy Reports, 61, 80 (GCVS). doi:10.1134/S1063772917010085
- Skrutskie, M. F., et al. 2006, AJ, 131, 1163 (2MASS). doi:10.1086/498708
- Smith, L. C., et al. 2025, MNRAS, 536, 3707 (VIRAC2). doi:10.1093/mnras/stae2797
- Watson, C. L., Henden, A. A., and Price, A. 2006, SASS, 25, 47 (AAVSO VSX)
- Wenger, M., et al. 2000, A&AS, 143, 9 (SIMBAD). doi:10.1051/aas:2000332
- Ochsenbein, F., Bauer, P., and Marcout, J. 2000, A&AS, 143, 23 (VizieR). doi:10.1051/aas:2000169
- Wright, E. L., et al. 2010, AJ, 140, 1868 (WISE). doi:10.1088/0004-6256/140/6/1868
- Deep GLIMPSE (Whitney et al. 2011) and APOGLIMPSE (Benjamin et al. 2016): cited as IRSA's data descriptions
  cite them; full details at https://irsa.ipac.caltech.edu/data/SPITZER/GLIMPSE/

Alert services and transient papers

- Bellm, E. C., et al. 2019, PASP, 131, 018002 (ZTF)
- Förster, F., et al. 2021, AJ, 161, 242 (ALeRCE)
- Karambelkar, V., et al. 2026, arXiv:2602.07129, "SPHEREx as a frontier for infrared transients"
- Kochanek, C. S., et al. 2017, PASP, 129, 104502 (ASAS-SN)
- Krimm, H. A., et al. 2013, ApJS, 209, 14 (Swift/BAT transient monitor)
- Matheson, T., et al. 2021, AJ, 161, 107 (ANTARES)
- Matsuoka, M., et al. 2009, PASJ, 61, 999 (MAXI)
- Möller, A., et al. 2021, MNRAS, 501, 3272 (Fink)
- Rutledge, R. E. 1998, PASP, 110, 754 (The Astronomer's Telegram)
- Shappee, B. J., et al. 2014, ApJ, 788, 48 (ASAS-SN)
- The nova, variable-star and VVV catalogues of Part 2 are cited there by their VizieR identifiers.

Comparison values and inspiration

- Caselden, D., et al. 2018, ascl:1806.004, "WiseView: Visualizing motion and variability of faint WISE sources"
- Giorgini, J. D., et al. 1996, BAAS, 28, 1158 (JPL Horizons)
- Hellier, C., et al. 2012, MNRAS, 426, 739 (WASP-62 b)
- Kirkpatrick, J. D., et al. 2021, ApJS, 253, 7 (WISE 0855 motion and parallax)
- Kokori, A., et al. 2023, ApJS, 265, 4 (ExoClock; WASP-62 b ephemeris and depth)
- Kuchner, M. J., et al. 2017, ApJL, 841, L19 (Backyard Worlds: Planet 9)

Software

- Astropy Collaboration 2013, A&A, 558, A33; 2018, AJ, 156, 123; 2022, ApJ, 935, 167
- Boch, T., and Fernique, P. 2014, ASP Conf. Ser., 485, 277 (Aladin Lite)
- Fernique, P., et al. 2015, A&A, 578, A114 (HiPS)
- Harris, C. R., et al. 2020, Nature, 585, 357 (NumPy). doi:10.1038/s41586-020-2649-2
- Virtanen, P., et al. 2020, Nature Methods, 17, 261 (SciPy). doi:10.1038/s41592-019-0686-2

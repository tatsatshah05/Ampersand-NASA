# The vetting of the sweep's three candidates (2026-11-15): the evidence

The sweep (`docs/sweep.md`) was left with three sources it could not explain, A, B and C. Each was attacked by
four reviewers who worked independently, each with one question and their own code, and a referee read all
twelve reports and ruled. All three remain **candidates**: real sources that we found in no catalogue or report we
checked, which nobody has confirmed. Nothing has been reported anywhere.

This folder keeps what a scientist needs to check the rulings: the ruling and the twelve reviews, and from the
reviewers' working folders their measurement tables, their scripts and the pictures that carry the argument. It is
a selection, not everything (384 of the reviewers' and referee's files, 6.95 MB, out of about 3,200): raw downloads, cutouts and large intermediate files
were left out.

**Changes made when copying.** Every script was renamed from `.py` to `.py.txt` so that the project's linters
skip them; their contents are unchanged. In text files, the temporary folder the reviewers worked in was
rewritten to this folder (`docs/sweep/vetting/`), other temporary paths to `<scratchpad>/` and the project folder
to `<repository>/`; nothing else was changed. A script therefore still refers to files that were not copied
(downloads, cutouts); the cutouts are in the project's cache, `backend/cache/sweep/cutouts/`, which is not in git.
Where the ruling says `vet2/`, read this folder.

## Start here

| File | What it is | Made by |
|---|---|---|
| `ruling.json` | The referee's ruling: for each candidate the corrected position, how much it brightened, whether it was reported, what it probably is, the one sentence a public page may show (`allowed_sentence`), what must not be said (`must_not_say`), what would confirm it, what a person must do, open items and key numbers; then `disagreements` (where the sweep and the reviewers differed and who was right), `method_faults` (what was wrong with the sweep's method) and `overall`. **The authority.** | referee |
| `reviews_A.json`, `reviews_B.json`, `reviews_C.json` | The twelve reviews, four per candidate, keyed by lens: `pixels`, `archives`, `reports`, `ordinary`. Each has the verdict, findings, key numbers, searches with their controls, what could not be checked, and the files. Where a review and the ruling differ, the ruling wins (for example the reports lenses measured A at the sweep's blended position; the referee did not use those values). | the four reviewers per candidate |
| `candidates.json` | A short machine-readable digest of the ruling for the app and `docs/sweep/summary.json`: positions, allowed sentences, the brightness per visit with ranges, rises, spectra, readings. `first_run_position_withdrawn` is kept only so code can find the first run's cache; never show it. | written from the ruling, 2026-11-15 |
| `rerun.json` | The fixed code (`backend/sweep.py describe`) run again on the three candidates' cached cutouts: position, every exposure fitted with the neighbours modelled, the faint-state test, the catalogues at the new position, the emission-line flag, and the comparison with the ruling. Made by `scripts/sweep_plane.py --describe`. | the fixed sweep code, 2026-11-15 07:16 UTC |
| `recheck_reports.json` | The wider search for earlier reports, made after the ruling: three searchers' reports (`searches`, every search with its time, control and result) and a referee's `verdict` (`per_candidate` with `what_can_be_said`, `overall`, and `checklist_for_a_person`). Temporary paths are rewritten as above. Read in plain words in `docs/sweep/searches-for-earlier-reports.md`. | three searchers and a referee, 2026-11-15 07:01-07:37 UTC |
| `atel_by_hand/RESULT.md`, `atel_by_hand/searches.json` | The Astronomer's Telegram check made after that, through the site's own search form, and the form's log of its six searches. | an automated reader, at the team lead's request, 2026-11-15 |

## The four lenses

- **pixels**: is it a real point of light at a fixed place, and is it measured correctly? Own code on the cached
  SPHEREx cutouts of all six detectors (not the project's `photometry.py` or `sweep.py`).
- **archives**: what was at the place before 2025 (catalogues, images and upper limits from 1998 to 2024)?
- **reports**: has anyone already reported or catalogued it? Every search with a control object.
- **ordinary**: ordinary explanations (asteroid, known variable, reflection, detector fault) and what it probably is.

## Pictures that carry the argument

| Picture | Shows | Lens |
|---|---|---|
| `A/pixels/stamps_D6_D4_D2.png` | A in each visit, detectors 6, 4 and 2: absent in 2025, bright in 2026 | A pixels |
| `A/pixels/stamps_native_single.png` | single exposures at native pixels | A pixels |
| `A/pixels/spectrum.png` | A's spectrum per visit | A pixels |
| `A/reports/candidateA_D6_epochs_neighbour.png` | the neighbouring star 20 arcsec away whose light made the sweep's 2025 "detection" | A reports |
| `A/ordinary/out/zoom_D5D6.png`, `A/ordinary/out/sed_A_by_visit.png` | zoomed cutouts by visit; the spectrum by visit with fits | A ordinary |
| `A/archives/png/prior_images.png`, `prior_zoom.png` | cutouts of the place from older surveys, before 2025 | A archives |
| `A/archives/png/neowise_2019-08-31_visit.png`, `neowise_frames_check.png` | the odd 2019 NEOWISE row, checked frame by frame | A archives |
| `B/pixels/pictures/zoom_visits_marked.png`, `stamps_visits_marked.png` | B in each visit, marked | B pixels |
| `B/pixels/pictures/strip_D6_exposures.png` | every detector 6 exposure | B pixels |
| `B/pixels/pictures/spectrum_by_visit.png`, `lightcurve_forced.png` | spectrum and light curve from forced fits | B pixels |
| `B/ordinary/out/B_spectra_by_epoch.png`, `B_positions.png` | spectra by visit; the measured positions | B ordinary |
| `B/archives/img/pre2025_irsa.png`, `spitzer_zoom_X.png`, `neowise_vs_spherex_northup.png`, `spherex_epochs_markers.png` | the place before 2025 in older surveys, NEOWISE beside SPHEREx, and SPHEREx by visit | B archives |
| `B/reports/B_position_check.png` | the position check against nearby catalogued stars | B reports |
| `C/pixels/stamps.png` | C in each visit, detectors 6, 4, 2 and 3, one grey scale per row | C pixels |
| `C/pixels/strip_D6.png`, `strip_D6_faint_visits.png` | every February-April detector 6 exposure; July-September 2026 and July-August 2025 by wavelength | C pixels |
| `C/pixels/spectrum.png`, `spectrum2.png` | spectra with the emission lines | C pixels |
| `C/pixels/wide.png` | 22 arcmin around the bright Mira V345 Nor per visit (the reflection test) | C pixels |
| `C/ordinary/C_spectrum_by_visit.png`, `stamps_lines.png` | the spectrum by visit; stamps in line and continuum channels | C ordinary |
| `C/archives/img/spitzer_pre2025_25as.png`, `spitzer_zoom_14as.png`, `unwise_pre2025.png`, `context_90as.png`, `decaps2_zoom7as.png` | the place before 2025 in Spitzer and WISE, the surroundings, and the faint optical source 0.9 arcsec away | C archives |

## Tables and logs, by candidate and lens

**A**

- pixels: `results_table.tsv` (per-visit summary), `spectrum_table.tsv` (every exposure: wavelength, flux, error,
  saturation and OVERFLOW at A; the source of the report draft's first reading), `fit2.json` (crowded-field fits with
  the neighbour modelled), `noise.json` (the blank-sky test, 30 empty places).
- ordinary: `out/forced.csv`, `forced_summary.txt`, `fit1_D56.csv`, `fit2_D56.csv`, `fit2_D56.txt` (forced and
  position fits), `wingtest_summary.txt` (the same circle at control points around the neighbour), `sedfit.txt`,
  `lines.txt` (colour temperature and the possible Brackett-alpha excess), `detpos.txt`, `vizloop*.txt` (catalogue
  loops), `downloads/jpl/` (JPL small-body answers and the Vesta control).
- archives: `tables/evidence_summary.csv` (what each survey says), `tables/forced_phot.json`,
  `tables/spherex_positions.json`, `tables/spherex_fixed_at_P.json`, `tables/wing_test.json`,
  `tables/neowise_forced_P_visits.json`, `neowise_visits.txt`, `consolidated_8as.txt`, `query_log.txt`.
- reports: `notes/` (each search's output: `cone_basic.out` TNS, VSX and SIMBAD; `brokers.out` ZTF brokers;
  `gaia_alerts.out`; `asassn.out`; `cbat.out`; `mukai.out`; `microlensing.out` OGLE and KMTNet; `vsx_1deg.out`;
  `vizier_*.out`; `atel_titles_2025jun_2026.tsv` and `atel_title_hits.txt`; `arxiv_search_html*.out`;
  `separations.out`; `requests.log`, every request made).

**B**

- pixels: `out/per_exposure.csv` (every exposure), `out/forced_table.json`, `out/centroids.json`,
  `out/adopted_positions.json`, `out/adopted_bright.json`, `out/catalogue_offsets.json`, `out/wcscheck.json` (the
  exposure whose coordinates are 17 arcsec off), `out/sed_fits.json`, `out/sed_fits_floor10.txt`,
  `out/shape_summary.json`, `out/ghost_rows.json`.
- ordinary: `out/astro2.json`, `out/field_calib.json`, `out/spectra_points.json` (the per-exposure spectrum used
  for the 4.25 micrometre dip), `out/sedfit.json`, `out/bright_stars.txt`, `out/viz_*.txt` and
  `out/vizier_all_60.txt` (young-star, maser, nebula and X-ray catalogues with controls), `out/sbident.log`.
- archives: `evidence_table.csv`, `centroid_summary.txt`, `twosrc_epochs.txt` and `twosrc_summary.txt` (the source
  and its neighbour fitted together, per visit), `astro_control.txt`, `irac_forced.txt` (Spitzer limits),
  `mipsgal_forced.txt`, `neowise_summary.txt`, `neowise_l1b_forced.txt`, `gator_near_X.txt`, `viz_batch1.txt`,
  `viz_batch2.txt`.
- reports: `searches_B.tsv` (every search, address, control and result).

**C**

- pixels: `forced.json` (forced fits with 28 neighbours modelled, every exposure; the report draft's first clean
  reading), `position.json`, `position_corrected.json`, `spectrum2.json`, `ghost_places.json`,
  `ghost_test3.json`, `mira.json` (the reflection test), `measure.log`, `fieldstars.log`.
- ordinary: `own_phot.jsonl` (every exposure), `analyse_phot.txt`, `by_wavelength.txt`, `line_ew.txt` and
  `line_controls.txt` (line strengths and their controls), `flare_continuum_feb2026.txt`, `sed_fit.txt`,
  `rates_lum.txt`, `positions.txt`, `aug2026_positions.txt`, `psf_width.txt`, `jpl_check.txt`, `jpl_control.txt`,
  `bright_stars.txt`, `sweep_points.txt`, `vizier_*.txt`, `refs.json`.
- archives: `data/archival_limits.csv` and `data/out_limits.txt` (every survey's limit), `data/out_distances.txt`,
  `data/neowise_visits.csv`, `data/out_neowise_visits.txt`, `data/out_neowise_2022_pixels.txt`,
  `data/out_spx_centroid.txt`, `data/spx_centroids.csv`, `data/out_spx_d3_ks.txt`, `data/out_decaps_zsource.txt`,
  `data/out_virac2_12as.txt`, `data/out_controls_gator.txt`, `data/out_controls_viz.txt`, `data/out_orphans.txt`,
  `data/query_log.txt`.
- reports: `search_log.tsv` and `fetch_log.tsv` (every search and fetch), `lists_xmatch.txt` (nova and transient
  lists), `atel_rss_scan.tsv` and `atel_rss_analysis.txt` (847 telegrams), `tns_1deg.txt`, `tns_AT2026epw.txt`,
  `vsx_1deg_summary.txt`, `vizier_all_*.txt` (with the two control novae), `simbad_cone.txt`,
  `simbad_controls_byname.txt`, `simbad_freshness.txt`, `spicy_cone.txt`, `fink_lsst.txt`, `arxiv_search.txt`,
  `li_wang_2024_check.txt`, `paper_*_positions.txt`, `richweb_novae_xmatch.txt`.

**referee**: `coords.py.txt` (adopted positions, offsets, Sun separations, flux conversions), `dates.py.txt` (visit
dates), `b_co2_check.py.txt` and `b_co2_check.out` (the 4.25 micrometre dip in B), `simbad/` (the CDS retry and the
control look-ups).

**Scripts**: every reviewer's scripts are in its lens folder as `*.py.txt` (for example
`A/pixels/measure.py.txt`, `B/reports/scripts/tns.sh` is not a Python file and was not copied).

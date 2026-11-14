# SPHEREx sky-change viewer (NASA Space Apps 2026, "Planet X and SPHEREx")

## What this is

A hackathon entry, built over one weekend. Submission closes Sunday 15 November 2026 at
night, local time (Edmonton). Working software on real data matters more than polish or
architecture. When a choice is between "correct and plain" and "clever and unfinished",
take the first.

The challenge, in NASA's words: create a public-facing web tool to display images of the
sky from the SPHEREx mission, making it easy for anyone to quickly see how they change
over time. Users enter the coordinates of a patch of sky (Right Ascension and
declination); the tool displays a series of images of that patch like a little video,
making it easy to spot moving objects.

Users are members of the public and citizen scientists, not astronomers. The closest
existing tool is WiseView from the Backyard Worlds project, which does this for WISE
data. Judges are NASA subject matter experts and will likely compare against it.

## The five test targets (this is the acceptance test)

The challenge says to test on these. Every feature should be checked against them.

| Target | Why it is there | What a good result looks like |
|---|---|---|
| Barnard's Star | Fastest-moving star, about 10.4 arcsec/year | Star visibly steps across frames; measured shift matches Gaia |
| Epsilon Indi B | Brown dwarf pair near a bright star | Faint companion visible and moving with the primary |
| WISE 0855 (RA 08h55m10.831s, Dec -07d14m42.53s) | Very cold, fast-moving brown dwarf, about 8 arcsec/year | Detected only after stacking the longest-wavelength detector |
| RW Aurigae | Variable star | Brightness chart shows change over time |
| R Draconis | Variable star (long period) | Brightness chart shows change over time |

Two traps here:

- Catalogue coordinates are for epoch J2000. Barnard's Star has moved about 4.5
  arcminutes since then. Propagate positions to the observation date using Gaia proper
  motion before centring a cutout, or the star will be off-frame at small fields of view.
- Motions between SPHEREx epochs are only one to three native pixels. A plain blink at
  native resolution barely shows them, so the display needs upsampling, a difference
  mode, and a per-frame centroid marker.

## What SPHEREx data is like (read before touching the pipeline)

- Pixel scale is about 6.15 arcsec. Each detector image is 2040 x 2040 pixels, roughly
  3.5 degrees across. There are six detectors (bands 1 to 6) covering 0.75 to 5.0 microns.
- Each image is NOT a single colour. A linear variable filter sits over each detector,
  so wavelength changes across the image. The same star lands on a different wavelength
  in every exposure. Consequences:
  - Blinking two arbitrary exposures shows colour differences, not time differences.
  - Frames for the video are built by stacking all exposures from ONE detector within
    ONE epoch. That averages over the detector's wavelength range and also raises
    signal-to-noise (the challenge statement suggests exactly this).
  - Brightness comparisons over time (variable stars) are only valid between
    measurements at nearly the same wavelength.
- The sky is re-observed roughly every six months, in clusters of exposures. Regions
  near the ecliptic poles are observed far more often. Work out the real cadence from
  the observation times in the query results rather than assuming it.
- Each file is a multi-extension FITS. Confirmed extensions: IMAGE (MJy/sr), FLAGS,
  VARIANCE, ZODI (zodiacal light model to subtract), EPSF (a table, not PSF), WCS-WAVE
  (wavelength lookup table). Details in "Verified facts".
- FLAGS is a bitmask, and most set bits do NOT mean a bad pixel. Bit 21 (SOURCE) is set
  on every pixel that holds a known source, which is nearly all of a crowded field.
  Never mask on `flags != 0`; use the bit lists in `backend/pipeline.py`.
- Bright stars saturate. Barnard's Star (K about 4.5 mag) has blank (NaN) core pixels in
  almost every exposure of detectors 1 to 4, and is clean only in detectors 5 and 6.

## Where the data comes from

All public, no key or account.

- Archive: IRSA at Caltech/IPAC. Mission page: https://irsa.ipac.caltech.edu/Missions/spherex.html
- Find images covering a position: IRSA SIA2 service at https://irsa.ipac.caltech.edu/SIA,
  collections `spherex_dr1` and `spherex_qr3` (`spherex_qr2` no longer exists). The
  backend calls it with plain HTTP and its own retries. TAP is at https://irsa.ipac.caltech.edu/TAP
- Fetch only a patch: append `?center=<ra>,<dec>&size=<degrees>` to the image URL. Full
  files are about 65 MB, so always use cutouts. Syntax:
  https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
- Same files on AWS, no credentials needed: bucket `nasa-irsa-spherex`, keys under
  `dr1/level2/` and `qr3/level2/` (each SIA row gives its key in `cloud_access`). Not
  used so far.
- Flag bits and recommended masks: Table 16 and Sect. 3 of the Explanatory Supplement,
  https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
- Worked notebooks to copy from: https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts
  and the other SPHEREx notebooks on that site.
- User guide: https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access
- Gaia positions and proper motions: Gaia's TAP service over plain HTTP. Name lookup:
  SIMBAD's TAP service (see "Verified facts").
- Known asteroids and comets (later, optional): JPL small-body identification API.

The SIA query, column names, cutout syntax and FITS layout were confirmed against the
live service on 2026-11-14 (see "Verified facts"). The Gaia TAP call and SIMBAD name
lookup are confirmed too. The JPL small-body API and the AWS route have not been run
yet: verify each the first time you use it and record what works.

Be a polite client of IRSA: cap concurrent requests (about 6), set timeouts, retry with
backoff, and cache every download on disk. Retries are not optional: IRSA's proxy
answers about one request in three with an immediate 502.

## Architecture

- `backend/`: Python, FastAPI. Libraries: astropy, reproject, scipy, numpy, Pillow,
  requests (see `backend/requirements.txt`; astroquery, pyvo and photutils are not used).
  Does all data access and image processing. Disk cache under `backend/cache/`:
  `cutouts/`, `queries/`, `frames/` (keyed by ra, dec, fov, detector, mode and options)
  and `photometry/` (keyed by ra, dec, detector, motion and code version).
- `frontend/`: Vite + React + TypeScript. Plays the frames, draws overlays and charts.
  Aladin Lite v3 for a context panel with Gaia and WISE layers.
- `scripts/`: one-off exploration and the cache warm-up script for the five targets.

Endpoints (adjust if something better emerges, and keep this list current):

- `GET /api/resolve?name=` BUILT. Object name to coordinates at the fixed date 2026.0
  (`ra`, `dec`, `epoch`), with `pmra`, `pmdec` (mas/yr), `parallax` (mas) when known,
  `source` ("Gaia DR3" or "SIMBAD"), `catalogue` (the position and epoch the motion
  starts from), `j2000`, `moved_since_2000_arcsec` and `notes`. 404 if SIMBAD does not
  know the name, 502 if SIMBAD is down. Same logic without a server:
  `backend.astrometry.resolve_name(name)`. Check: `scripts/check_resolve.py`.
- `GET /api/frames?ra=&dec=&fov=&detector=&mode=` BUILT for `mode=normal`, `difference`
  and `sum` (anything else answers 400). Defaults: fov 0.1 degrees, detector 5. Returns
  `size_px`, `pixel_arcsec`, `stretch`, `target`, `failures` and `frames`. Each frame has
  `epoch`, `date_start`, `date_end`, `date_mean`, `mjd_mean`, `image` (PNG path under
  `/frames/`), `n_exposures`, `wavelength_um` [min, max], `flagged_fraction`,
  `saturated_pixels`, `rejected_readings`, `centroid` and `predicted` (each with ra, dec,
  and x, y in PNG pixels from the top-left). In the PNG, north is up and east is left;
  white-with-no-detail pixels are saturated and transparent pixels have no data.
  - Optional `pmra=&pmdec=&parallax=` (mas/yr, mas, exactly as `/api/resolve` returns
    them; `pm_epoch` defaults to 2026.0): the object at (ra, dec) with that motion becomes
    `target`, so `predicted` works for objects Gaia does not list. Without them `target`
    is the Gaia star within 15 arcsec of the centre, or null. `target.origin` says which
    ("request" or "gaia_nearest").
  - `mode=difference`: each epoch minus a reference. `reference=first` (default)
    subtracts the first epoch and returns one frame per later epoch, each with
    `reference_epoch`; the first epoch's own details are in `reference_frame`.
    `reference=mean` subtracts the stack of all epochs and returns one frame per epoch
    (`reference_epoch` null). `stretch.kind` is "asinh-symmetric": mid-grey (128) is no
    change, white brighter, black fainter, one scale for all frames; transparent means
    the pixel is missing from the epoch or the reference. `centroid` and `predicted` are
    still those of the epoch's ordinary image. One epoch only: `frames` is empty and
    `message` says why.
  - `mode=sum`: one frame from every exposure of every epoch (`epoch` null,
    `epochs_combined` lists them). `registration` is "sky" by default. `track=target`
    shifts each exposure by the target's motion first (`registration` "target_motion",
    and a `note` saying stars are smeared and coordinates hold for the target only);
    it answers 400 if no motion is known.
- `GET /api/lightcurve?ra=&dec=` BUILT. Brightness of the object at (ra, dec) in every
  exposure of all six detectors, grouped into `bins` (SPHEREx's 102 wavelength channels,
  17 per detector). Each bin has `wavelength_um` [min, max], `detector`, counts, and
  `points` sorted by time. A point has `mjd`, `date`, `epoch` (same numbering as
  `/api/frames`), `wavelength_um`, `bandwidth_um`, `status`, `flux_mjy`, `flux_err_mjy`,
  `flags`, `relative_flux` (flux over the bin's median), and the wing fields below.
  `status` is "ok", "saturated", "flagged", "no_data", "no_sky" or "off_image"; only
  "ok" has a flux. Only points in the same bin are comparable in time. Optional
  `detector=` (one detector), and `pmra=&pmdec=&parallax=` as for `/api/frames`: the
  object is followed with that motion, else with that of the Gaia star within 15 arcsec.
  `method` in the response explains the measurement in plain words.
  - For saturated stars: `wing_mjy`, `wing_err_mjy`, `wing_status`, `wing_ring_px`,
    `wing_trusted`, `relative_wing`. This is a relative brightness from unsaturated
    pixels in a ring around the star, NOT a flux. Chart it only where `wing_trusted` is
    true (detectors 5 and 6); `relative_wing` is null elsewhere.
  - The first request for a position downloads every exposure of all six detectors
    (several minutes); after that it is served from `backend/cache/photometry/`.
- `GET /api/spectrum?ra=&dec=&epoch=` BUILT. The same per-exposure points sorted by
  wavelength, for one epoch (`epoch=1`, 2, ...) or all (omit it). `epochs` lists the
  epochs with their dates; a wrong epoch answers 400. Same optional parameters.

The frontend reads `?ra=&dec=&fov=` from the page URL so a view can be linked and embedded.

## Processing steps for /api/frames

1. Propagate the target position to the survey epoch if Gaia has a proper motion for it.
2. Query for all images covering the position.
3. Download cutouts concurrently.
4. Per cutout: drop pixels whose raw value is more than 10 sigma below zero (see
   "Unflagged negative pixels" in Verified facts), subtract ZODI, then subtract the
   sigma-clipped median that is left (it
   differs per exposure because each one is at a different wavelength). Mask defect and
   cosmic-ray bits, but keep cosmic-ray-flagged pixels where BLOOM is also set: next to
   a saturated star those flags mean charge spill, and masking them erases the star.
   Read the wavelength at the target.
5. Reproject every cutout onto one shared north-up grid centred on the request,
   oversampled to about 2 arcsec per pixel.
6. Group by epoch (a gap of more than 30 days starts a new one; computed over all
   detectors so epoch numbers agree between detectors) and detector. Drop single
   readings far from the per-pixel median (the flags miss some glitches), then take a
   weighted mean with ONE weight per exposure, the inverse of its median variance.
   Per-pixel inverse-variance weights would down-weight the exposures in which a source
   is brightest, because VARIANCE includes source photon noise.
7. Apply ONE brightness stretch per detector across all epochs (asinh, limits from the
   combined pixel distribution; the top of the scale is the brightest pixel so bright
   stars keep their shape). Per-frame auto-scaling would make brightness changes
   look fake or hide real ones.
8. Measure the centroid of the source nearest the target in each frame (round Gaussian
   fitted to valid pixels only, so a saturated star is located from its wings).
9. Write PNGs and return the metadata.

Difference mode subtracts the stacked images of step 6 pixel by pixel, with no flux
matching. Field stars do not cancel exactly: each epoch samples a star at a different
set of wavelengths and sub-pixel positions, which leaves a faint speckle at each one
(3 to 16 per cent of the star's peak, measured on seven field stars near Barnard's
Star). Sum mode is step 6 applied to all epochs at once.

## Photometry for /api/lightcurve and /api/spectrum (`backend/photometry.py`)

Measured on the native cutouts, one value per exposure, at the object's expected
position on that date. Sum of IMAGE minus ZODI in a circle of radius 2.5 native pixels,
minus a clipped-median sky from a ring 14 to 20 pixels out, times the pixel solid angle
(mJy). No aperture correction. A value is given only if no pixel in the circle is on the
Explanatory Supplement's photometry flag list. The cache key includes
`photometry.VERSION`: raise it when the measurement changes.

## Build order

Finish each step on real data before starting the next.

1. Backend proof: frames for Barnard's Star saved as PNGs, looked at by eye.
2. Frontend player: coordinate or name search, play/pause, speed, frame scrubber, URL parameters.
3. Detector selector and field-of-view selector.
4. Difference and sum modes.
5. Brightness chart (RW Aurigae, R Draconis).
6. Gaia overlay with proper-motion arrows, and measured versus predicted shift.
7. Spectrum on click.
8. Flags toggle and per-frame metadata panel.
9. Stretch goals, only after 1 to 8 work on all five targets: labels for known asteroids
   and comets; a "planted Planet X" training mode that injects a synthetic moving source.
10. Deploy, warm the cache for the five targets, record the demo.

## How to check your work

- Look at the images. After any pipeline change, regenerate the Barnard's Star frames
  and open the PNGs. A blank, striped or saturated frame is a bug even if the code ran.
- Barnard's Star is the ground truth: its measured shift between epochs should match
  Gaia proper motion plus parallax to within about a pixel. If it does not, alignment
  or epoch handling is wrong.
- Field stars must stay fixed between frames. If they jitter, reprojection is wrong.
- If a target shows nothing (likely for WISE 0855 at short wavelengths), say so in the
  interface and report it. Never fabricate, interpolate or substitute placeholder data,
  and never present simulated sources as real. The planted Planet X mode must be
  labelled as a simulation on screen.

## Conventions

- Keep it simple: no database, no auth, no job queue. Files on disk are the cache.
- Units and coordinates: degrees, ICRS, internally. Accept sexagesimal input in the UI.
- Credit data on the page: NASA/JPL-Caltech SPHEREx and NASA/IPAC IRSA.
- Commit after each working step with a plain message.
- When something in this file turns out to be wrong, fix the file.

## Verified facts

Confirmed against the live archive on 2026-11-14 with `scripts/explore_barnard.py`,
`scripts/download_barnard.py` and `scripts/check_barnard.py`. Re-run them to re-check.

Finding images (SIA2)
- `GET https://irsa.ipac.caltech.edu/SIA?COLLECTION=<name>&POS=circle <ra> <dec> 0.01`
  returns a VOTable. Parse with `astropy.io.votable.parse_single_table(...).to_table(
  use_names_over_ids=True)`; without that flag the columns are named col_0, col_1, ...
- SPHEREx collections on the service: `spherex_dr1` (2025-08 to 2026-05 at Barnard's
  Star), `spherex_qr3` (2026-08 onward), `spherex_dr1_deep`, `spherex_qr3_deep` (deep
  fields only, empty here) and `spherex_dr1_cube` (level-3 HiPS cubes). No `spherex_qr2`.
- Columns used: `access_url`, `energy_bandpassname` ("SPHEREx-D1" to "SPHEREx-D6"),
  `t_min`/`t_max` (MJD), `t_exptime` (113.6 s), `obs_id` (e.g. `2025W34_2B_0030_2`),
  `obs_collection`, `em_min`/`em_max` (metres), `access_estsize` (kB), `cloud_access`.
- A query takes 0.5 to 1.5 s. `pyvo.dal.SIA2Service` also works but fetches
  `/SIA/capabilities` first, which doubles the chance of hitting a 502.
- Detector ranges from `em_min`/`em_max`: D1 0.75-1.12, D2 1.10-1.65, D3 1.63-2.43,
  D4 2.40-3.85, D5 3.81-4.43, D6 4.41-5.01 microns.

Reliability
- IRSA's proxy returned HTTP 502 on about 1 request in 3 (SIA, TAP and cutouts alike),
  failing within 0.3 s and in bursts. With retries, 364 of 364 cutouts succeeded.

Cutouts
- `<access_url>?center=<ra>,<dec>&size=<degrees>` (plain degrees, no unit suffix).
  size=0.1 gives 58 x 59 pixels; size=0.15 gives 88 x 88. Near a detector edge the
  cutout comes back smaller rather than failing.
- A cutout is about 4.1 MB whatever its size, because the EPSF table (3.9 MB) is always
  included. One download takes 2.3 to 3.4 s. All 364 for Barnard's Star, six at a time:
  247 s (0.68 s each). The backend caches a slimmed copy (about 250 kB at size=0.15;
  91 MB for all 364) without EPSF.
- Extensions: PRIMARY (empty), IMAGE float32 MJy/sr, FLAGS int32, VARIANCE float32
  (MJy/sr)^2, ZODI float32 MJy/sr, EPSF (table: 451 rows, 11 columns), WCS-WAVE
  (table: 1 row, columns X, Y, VALUES).
- IMAGE header: `DETECTOR` (int 1-6), `OBSID`, `EXPIDN`, `DATE-OBS`/`MJD-OBS` (start),
  `DATE-AVG`/`MJD-AVG` (midpoint, used as the exposure time), `DATE-END`/`MJD-END`,
  `XPOSURE` (113.58 s), `TIMESYS` UTC, `PSF_FWHM` (about 7.4 arcsec). `DATE` is the
  processing date, not the observation.
- Sky WCS is `RA---TAN-SIP` (3rd order), ICRS, 6.15 arcsec per pixel; astropy's
  `WCS(header)` handles it and the star lands within half a pixel of the cutout centre.
- Wavelength: `w = WCS(header, fobj=hdul, key="W"); w.sip = None;
  wave, bandwidth = w.wcs_pix2world(x, y, 0)` in microns (0-based cutout pixels). At
  Barnard's Star in three D3 exposures: 1.873, 2.257 and 1.851 microns, R about 40.
  Wavelength varies by only about 0.02 microns across a 0.1 degree cutout.
- Flag bit names are NOT in the header. They are in Table 16 of the Explanatory
  Supplement (v2.1, 2026-11-10) and copied into `backend/pipeline.py`.
- After ZODI subtraction a sky level of about 0.16 MJy/sr remains in this field.

Cadence and counts at Barnard's Star
- 364 exposures (58 to 62 per detector) from 2025-08-15 to 2026-09-22, in three epochs:
  2025-08-15 to 10-01 (118 exposures), 2026-03-11 to 05-05 (122), 2026-08-16 to 09-22
  (124). Gaps between epochs are about five months. One detector gets 17 to 25
  exposures per epoch, usually within one or two weeks.

Gaia
- `https://gea.esac.esa.int/tap-server/tap/sync` with `REQUEST=doQuery&LANG=ADQL&
  FORMAT=votable&QUERY=...` on `gaiadr3.gaia_source` answers in about 3.5 s.
- Barnard's Star is Gaia DR3 4472832130942575872: pm (-801.55, +10362.39) mas/yr,
  parallax 546.98 mas. Position at 2026.0: RA 269.446267, Dec +4.768222 (4.50 arcmin
  from J2000).

Step 1 result (detector 5, fov 0.1 degrees, 2 arcsec grid)
- Three frames from 18, 19 and 25 exposures. Measured shift of the star against Gaia
  proper motion plus parallax: epoch 1 to 2 (-0.93, +5.90) vs (+0.59, +5.63) arcsec east,
  north; 1 to 3 (-2.21, +10.16) vs (-0.77, +10.25); 2 to 3 (-1.29, +4.26) vs
  (-1.37, +4.62). Largest disagreement 1.5 arcsec, a quarter of a native pixel, all of
  it an eastward offset of the epoch 1 centroid whose cause is not yet known.
- 13 isolated Gaia field stars move by a median of 0.11 to 0.22 arcsec between frames.
- Building the frames from cached cutouts takes about 10 s; a repeat request is served
  from `backend/cache/frames/` in milliseconds.
- After a pipeline change that alters pictures or numbers, raise `pipeline.VERSION` (and
  `photometry.VERSION` for the photometry). Both are part of the cache keys, so results
  from older code are never served again. Deleting `backend/cache/frames/` then only
  frees disk space. A process that was already running keeps the old code and the old
  keys: restart the server and re-run the warm-up script after a version change.

Name lookup (SIMBAD), confirmed 2026-11-14 with `scripts/check_resolve.py`
- SIMBAD TAP: `GET <mirror>/simbad/sim-tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=json&
  QUERY=...` answers in about 0.3 s with `{"metadata": [...], "data": [[...], ...]}`.
- On 2026-11-14 the Strasbourg original (`simbad.cds.unistra.fr`) answered every request
  with HTTP 404 "Page unavailable"; the CfA mirror (`simbad.harvard.edu`) worked. The
  backend tries CfA first, then Strasbourg. The Sesame resolver at CDS timed out or took
  5 s the same day; its CfA copy (`vizier.cfa.harvard.edu/viz-bin/nph-sesame`) worked but
  is not used.
- Name to object: `SELECT ... FROM basic AS b JOIN ident AS i ON i.oidref = b.oid WHERE
  i.id = '<name>'`. SIMBAD normalises the name itself: "Barnard's Star", "Epsilon Indi B"
  (stored as `* eps Ind B`), "RW Aurigae" (`V* RW Aur`) and "R Draconis" (`V* R Dra`) all
  match as typed. "WISE 0855-0714" and "WISE 0855" do not: the stored names are
  `WISE J085510.83-071442.5` and `WISEA J085510.74-071442.5`. The backend handles the
  first with `i.id LIKE 'WISE% J0855%-0714%'` (1.6 s, one object) and the second with a
  small alias table. "barnards star" without the apostrophe also needs the alias table.
- `basic` columns used: `oid`, `main_id`, `ra`, `dec` (degrees, ICRS, epoch J2000),
  `pmra`, `pmdec` (mas/yr), `plx_value` (mas), `otype`, `coo_bibcode`, `pm_bibcode`.
  The Gaia identifier, when there is one: `SELECT id FROM ident WHERE oidref = <oid>
  AND id LIKE 'Gaia DR3 %'`.
- SIMBAD has a Gaia DR3 identifier for Barnard's Star (4472832130942575872), Epsilon
  Indi B (6412596012146801152, G = 18.0) and R Draconis (1648328016354496384). It has
  none for RW Aurigae (a close pair; SIMBAD's motion is from Hipparcos) or WISE 0855.
- WISE 0855 in SIMBAD: J2000 position 133.818908, -7.247048, pm (-8123.7, +673.2)
  mas/yr, parallax 439 mas, all from Kirkpatrick et al. 2021. That J2000 position is 85
  arcsec east of the WISE name (which is where it was in 2010), as the motion requires,
  so SIMBAD's position really is for epoch 2000 and 26 years of motion are applied.
- Positions at 2026.0 from `resolve_name`: Barnard's Star 269.446267, +4.768222; Epsilon
  Indi B 331.096653, -56.800663; WISE 0855 133.759765, -7.242182; RW Aurigae 76.956587,
  +30.401291; R Draconis 248.167233, +66.755024.
- Barnard's Star only lands on 269.446267, +4.768222 (the centre the cached cutouts were
  fetched for) when Gaia's radial velocity (-110.5 km/s) is included in the motion.
  Straight-line proper motion gives Dec +4.768204, 0.06 arcsec south, which is a
  different cache key. `astrometry.propagate` does it the rigorous way.
- Gaia by identifier: `... FROM gaiadr3.gaia_source WHERE source_id = <id>`, 1.5 to 2.5 s.

Difference and sum modes (Barnard's Star, detector 5, fov 0.1; `scripts/check_modes.py`)
- Difference against epoch 1: two frames, the star a white patch (north) against a black
  one (south) spanning the full grey range, 0.00 to 1.00; everything else in the frame
  stays between 0.34 and 0.67, the faint speckles left by field stars.
- Sum of all 62 exposures, sky-registered: the star is stretched north-south (fitted
  FWHM 13.5 arcsec). Following the star's motion: FWHM 11.0 arcsec, the same as in a
  single epoch, and the field stars become short north-south streaks.

Flags and saturation (Explanatory Supplement v2.1, 2026-11-10, read on 2026-11-14)
- Sect. 3.3 "Flag usage" gives two lists. For photometry, mask SUR_ERROR, NONFUNC,
  MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, BLOOM, SNOWBALL, HALO, SATELLITE_HALO. For
  the background, mask those plus OVERFLOW, OUTLIER, SOURCE, TRANSIENT.
- OVERFLOW (bit 1) is NOT saturation. Table 16: "Overflow threshold reached during SUR.
  This threshold is set at approximately half the level of full-well saturation." The
  pixel's value then comes from the reads before the threshold and is valid; the
  mission's own photometry keeps such pixels. OVERFLOW with SUR_ERROR means overflow in
  the first 5 seconds (no usable value). BLOOM is charge spilled from a saturated
  neighbour. `photometry.saturated_pixels` encodes this.
- In the data: OVERFLOW appears on 1 to 4 core pixels of RW Aurigae once the peak passes
  about 100 MJy/sr, with finite values. Barnard's Star has OVERFLOW, SUR_ERROR and BLOOM
  on its core in nearly every exposure of ALL six detectors, including 5 and 6 where the
  values are finite and the display looks clean: for photometry it is saturated
  everywhere (4 of 354 exposures give a flux).
- The Supplement adds 3 per cent of the flux in quadrature to its catalogue errors
  (Sect. 3.3, Note 1); `flux_err_mjy` does the same.
- A blank circle of radius 2.5 pixels has a photometry-flagged pixel in about 15 per cent
  of exposures (cosmic rays, dead pixels; 77 of 480 in D1 and 78 of 487 in D5 near
  Barnard's Star), so about that share of measurements is "flagged" for any star.

Photometry checks (`scripts/check_photometry.py`, `scripts/check_flux_scale.py`)
- Flux scale: three isolated field stars (one near RW Aurigae, two near Barnard's Star,
  28 to 140 mJy) against 2MASS: SPHEREx / 2MASS = 0.92 to 0.96 in J, 1.00 to 1.04 in H,
  0.96 to 1.03 in Ks. Only three stars passed the isolation test.
- 2MASS came from VizieR's CfA mirror (`https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?
  -source=II/246/out&-c=<ra> <dec>&-c.rs=<arcsec>&-out=...`, under 1 s; once it returned
  no rows for a query that had worked minutes earlier). IRSA TAP on `fp_psc` timed out
  at 60 s three times and answered 502 once on 2026-11-14.
- RW Aurigae (326 exposures with a wavelength, 3 epochs): 131 fluxes, 167 saturated, 28
  flagged. Fluxes exist mostly in D1 (42), D2 (19), D5 (29), D6 (30); D3 and D4 are
  nearly all saturated. The spectrum rises from about 0.1-0.25 Jy at 0.75 microns to
  1-3 Jy at 4-5 microns. Between 2025-09 and 2026-09 it brightened about 2.5 times at
  0.75-0.84 microns and faded to about half at 3.9-5 microns (48 bins have 2+ fluxes;
  brightest/faintest within a bin: median 1.41, largest 2.86).
- R Draconis (496 exposures with a wavelength, 3 epochs of 2 to 3 months): saturated in
  every exposure of every detector; there is no flux at all. Flagged pixels reach 5 to
  8 native pixels from the star.
- Wing values (ring around a saturated star) were tested on same-bin pairs: Barnard's
  Star, which does not vary (all pairs), and R Draconis (pairs within 4 days, only 3 or
  4 per detector). Median larger/smaller ratio, Barnard then R Dra: D5 1.02-1.05 and
  1.04; D6 1.05-1.06 and 1.01-1.02; D4 1.03-1.08 and 1.20; D1 1.08 and 1.16-1.22; D2
  1.14-1.25 and 1.88; D3 1.19-1.32 and 1.69. Hence `wing_trusted` only in D5 and D6.
  Why detectors 1 to 3 misbehave is not known.
- With trusted wing values only, brightest/faintest within a bin: Barnard's Star median
  1.07 (largest 1.37), RW Aurigae 1.72 (2.52), R Draconis 1.87 (3.17). R Draconis fades
  through June 2025, is lower and rising from November 2025 to January 2026, and is
  lowest in May to June 2026. That fits its 245-day period but has not been compared
  with ground-based (AAVSO) data.
- RW Aurigae has exposures with both a flux and a wing value. For same-bin pairs from
  different epochs in D5 and D6 (21 pairs, flux changing by 0.54 to 0.83) the wing
  changed by the same factor to within 4 per cent typically (one pair was off by a
  factor 1.7). In D1 to D4 (44 pairs) the two disagreed by 19 per cent typically and
  up to a factor 2.3.
- Counts: RW Aurigae has 336 exposures (56 per detector), R Draconis 548 (89 to 93 per
  detector; it is 9 degrees from the north ecliptic pole). Measuring all exposures of a
  target from cached cutouts takes about 10 s.

Unflagged negative pixels (found 2026-11-14)
- Every target has pixels whose raw IMAGE value is more than 10 sigma below zero and
  that carry no defect flag (only SOURCE): 45 to 108 pixels per target over 258 to 548
  cutouts, mostly detectors 4 to 6, values from -0.1 to -2112 MJy/sr. `stack()` rejects
  them when an epoch has 5 or more exposures. WISE 0855 has an epoch of 3 exposures in
  detector 6 (2025-05-05), where one reading of -2000 MJy/sr left a black patch and set
  the difference scale to +/-579 MJy/sr. `pipeline.impossible_pixels` now masks them
  before stacking and photometry treats them as empty. Barnard's Star numbers did not
  change.

WISE 0855 in detector 6 (fov 0.1, motion from `/api/resolve`; `scripts/check_modes.py`)
- 45 exposures in three epochs (3, 21 and 21). A faint source sits at the predicted
  place in every epoch: measured minus predicted (-0.7, +0.5), (-1.2, +0.5) and
  (-0.6, +0.9) arcsec east, north; fitted S/N 5, 19 and 27. Epoch 2 to 3 it moved
  (-3.7, +0.9) arcsec against a predicted (-4.4, +0.5).
- Sum of all 45: S/N 24, FWHM 11.7 arcsec sky-registered; S/N 32, FWHM 10.9 arcsec
  following the motion.
- Difference against epoch 1 shows a white spot at the epoch 3 position; the dark half
  of the pair is lost in the noise of the 3-exposure reference. Other detectors were
  not examined here.

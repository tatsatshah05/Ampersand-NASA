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
- `frontend/`: the React app (Vite + TypeScript, Swara's PR #19). Tatsat chose it as
  the frontend on 2026-11-14. It has a basic player, the Gaia overlay (predicted
  against measured position) and a frame details panel. `npm run dev` serves it on
  port 5173 and passes `/api` and `/frames` to the backend on port 8000. `npm run build`
  writes `frontend/dist`, which the backend serves at `/` when it exists.
- The React app now has all of it: search by name or coordinates, the player, a
  zoomable image with motion markers, the selectors, the Gaia overlay and field stars
  (`/api/stars`), frame details, the flags layer (`flags_image`), the spectrum panel, the
  brightness-over-time panel, and an Aladin Lite sky-context panel that is loaded only
  when asked for (its servers in Strasbourg were down on 2026-11-14).
- `frontend/public/viewer.html`: the earlier single-file viewer (plain HTML +
  JavaScript, no build step, started by Anu for issue #8), kept at `/viewer.html`. It
  has nothing the app lacks any more. Both show only what the API returns: no sample or
  simulated data.
- `scripts/`: one-off exploration and the cache warm-up script for the five targets.

Endpoints (adjust if something better emerges, and keep this list current):

- `GET /api/resolve?name=` BUILT. Object name to coordinates at the fixed date 2026.0
  (`ra`, `dec`, `epoch`), with `pmra`, `pmdec` (mas/yr), `parallax` (mas) when known,
  `source` ("Gaia DR3" or "SIMBAD"), `catalogue` (the position and epoch the motion
  starts from), `j2000`, `moved_since_2000_arcsec` (null when no motion is known) and
  `notes`. `name` is SIMBAD's own identifier ("NAME Barnard's star", "M  31");
  `display_name` is the same without the catalogue prefix and doubled spaces. 404 if
  SIMBAD does not know the name, 502 if SIMBAD is down. Same logic without a server:
  `backend.astrometry.resolve_name(name)`. Check: `scripts/check_resolve.py`.
  - The name is cleaned before the lookup (`astrometry.clean_name`): curly quotes to
    straight ones, every dash and minus sign to a hyphen, accents dropped, Greek letters
    to SIMBAD's abbreviations (ε to eps), invisible characters and repeated spaces
    removed. The cache is keyed on the cleaned name, and `query` returns it. A name that
    still has characters outside plain ASCII is answered 404 without asking SIMBAD.
- `GET /api/frames?ra=&dec=&fov=&detector=&mode=` BUILT for `mode=normal`, `difference`
  and `sum` (anything else answers 400). Defaults: fov 0.1 degrees, detector 5. Returns
  `size_px`, `pixel_arcsec`, `stretch`, `target`, `failures` and `frames`. Each frame has
  `epoch`, `date_start`, `date_end`, `date_mean`, `mjd_mean`, `image` (PNG path under
  `/frames/`), `flags_image` (normal and sum modes: overlay PNG, blue = no data,
  red = saturated, transparent elsewhere), `n_exposures`, `wavelength_um` [min, max]
  or null, `flagged_fraction`,
  `saturated_pixels`, `rejected_readings`, `centroid` and `predicted` (each with ra, dec,
  and x, y in PNG pixels from the top-left). In the PNG, north is up and east is left;
  white-with-no-detail pixels are saturated and transparent pixels have no data.
  - Two saturation counts, which mean different things (`saturation_note` in the
    response says the same). `saturated_pixels`: picture pixels with no value in any
    exposure because the detector overflowed there; these are the white ones.
    `photometry_saturated_exposures`: how many of the frame's `n_exposures` have a
    saturated pixel inside the circle in which `/api/lightcurve` measures the target
    (the centre of the picture if there is no target), by the photometry rule, which also
    counts overflow within the first seconds, charge spilled from a neighbour and
    uncorrectable pixels. Those pixels usually still hold a value, so a frame can look
    fine, report 0 `saturated_pixels`, and have every exposure unusable for brightness.
  - `centroid` is the target, measured, or null. When the view has a `target`
    (`centroid_is` "target"), it is there only if the target is detected at `predicted`
    (`detection_sigma` 3 or more, or `detection` "saturated", see below) and a source
    shaped like a star (width 6 to 36 arcsec), fitted starting within 6 arcsec of
    `predicted`, lies no further from it than 3 arcsec, or a quarter of its own width if
    that is more (a saturated star is located from its wings). Otherwise `centroid` is
    null, `centroid_reason` says why in plain words, and `nearest_source` holds what was
    found instead when that was another object (the same fields as `centroid`, plus its
    own `offset_arcsec`, `detection_sigma` and `detection`; the last two are null when
    it was not measured on its own). `centroid_offset_arcsec` is centroid minus
    predicted: `east`, `north`, `total`. With no target at all (`centroid_is`
    "brightest_near_centre") `centroid` is the brightest source within 14 arcsec of the
    centre, as before, and the offset is null. `centroid_note` states which of the two
    applies.
  - `detection_sigma` (per frame): how strongly the target is detected, in multiples of
    the noise, measured the same way at the target and at the frame's empty places. The
    brightness of a star image of fixed width centred exactly on `predicted` is fitted
    together with a constant sky and with every Gaia star within 25 arcsec held at its
    catalogue place (so a neighbour's light is not taken for the target's); the same fit
    is made on a 12 arcsec grid of empty places (at least 18 arcsec from any Gaia star and
    from the target); `detection_sigma` is the target's value minus their median, over
    their scatter (1.4826 x median absolute deviation, after setting aside places more
    than 3 times that out, which hold sources no catalogue here lists), scaled up when a
    close neighbour shares the light. `detection`: "clear" (5 or more), "marginal" (3 to
    5), "none" (below 3), "saturated" (the detector overflowed at the place: certainly
    detected, no number), "unknown" (too few empty places or pixels to say, which can
    happen in fields of view under about 0.05 degrees; the decision then falls back to the
    fit's own S/N of 4).
    `detection_measure` has the parts: `flux_mjy` (the fitted brightness, a rough flux),
    `noise_mjy`, `blank_median_mjy`, `n_blank_places`, `n_blank_set_aside`,
    `n_blank_as_strong` (empty places that reach the same value), `n_neighbours_fitted`,
    `star_fwhm_arcsec`, `status` and `at` ("predicted", or "centroid" when there is no
    target). `detection_note` in the response says the same. Without a target it is
    measured where the centroid was found, which favours it a little.
  - `centroid.err_arcsec` is the position uncertainty and `centroid.err_arcsec_fit` the
    fit's own. They are equal unless `centroid.saturated_core` is true: a pixel within one
    star width of the fitted centre is saturated or bloom-flagged (the photometry rule)
    in at least one exposure, or has no value because the detector overflowed. Those
    pixels stay in the picture and in the fit (so the star is drawn), and the fit follows
    them: `err_arcsec` is then 1 arcsec in detectors 5 and 6 and 2 arcsec in detectors 1
    to 4, what the independent check found for Barnard's Star whichever pixels were used
    (the fit's own figure was 0.03 to 0.11). `error_note` in the response says the same.
    `nearest_source` carries the same three fields.
  - `blend` (per frame): the Gaia stars (G < 17) within one native pixel (6.15 arcsec) of
    `predicted` on the frame's date, nearest first, each with `source_id`, `gmag`,
    `distance_arcsec`, `east_arcsec`, `north_arcsec`, and `flux_mjy` and `light_share`
    from the same fixed-position fit as `detection_sigma` (rough; null where the target
    is saturated or the star is under 1.5 arcsec away). Empty when there is none, or no
    target. `centroid.blended` is true when the list is not empty (null with no target):
    the marker then measures a blob of both and is pulled toward the star. Nothing is
    subtracted. `blend_note` in the response says the same. A target that is a Gaia star
    is left out of its own list by identifier, so a close companion still shows.
  - `centroid.snr` is kept for compatibility, but it is the fitted height over the
    scatter left around the fit, NOT a detection strength: started on empty sky that fit
    returns 5 or more at 3 of 78 places in one WISE 0855 frame and at about 20 of 78 in
    two others (`docs/verification.md`). Show `detection_sigma` instead.
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
- `GET /api/stars?ra=&dec=&fov=&detector=` BUILT. Gaia DR3 stars in the frames of a view,
  for the catalogue overlay. Takes every parameter `/api/frames` takes (`mode`,
  `reference`, `track`, `pmra`, `pmdec`, `parallax`, `pm_epoch`) plus `limit`, and describes
  exactly the frames that request returns: `frames` (each with `epoch`, `mjd_mean`,
  `date_mean`, in the same order), `size_px`, `pixel_arcsec` and `stars`, brightest first.
  A star has `source_id`, `gmag`, `pmra`, `pmdec`, `parallax` (mas/yr and mas; null when
  Gaia has no motion for it), `is_target` and `positions`: one `{ra, dec, x, y}` per
  frame, for that frame's mean date with the star's own proper motion and parallax
  applied, x and y in PNG pixels exactly as for `centroid`. `target_source_id` names the
  star that is the view's target, if one is (by identifier, or, when the target came
  from the request's motion, the star that stays within 1.5 arcsec of `predicted`).
  - Keeping it small: only stars brighter than G = 17 that are inside the picture on at
    least one frame's date; at most `limit` of them (default 300, largest 2000), brightest
    first, except that stars faster than 100 mas/yr are always kept. `n_in_field`,
    `n_returned` and `truncated` say what was cut. Numbers are rounded (0.001 pixel,
    1e-7 degree). About 0.3 kB per star with three frames.
  - It has no cache of its own. It is worked out in milliseconds from two things that
    are on disk once `/api/frames` has run for the view: the frames metadata and the Gaia
    search around the centre. It calls `build_frames` with the same parameters, so it
    never fetches a cutout that `/api/frames` would not. If the Gaia search is not on
    disk (the view was only ever requested with a motion) it is made once, with 3 tries;
    if Gaia does not answer, `gaia_error` is set and `stars` is empty.
  - Check: `scripts/check_stars.py [name] [detector] [fov]`.
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
  - `stars_in_circle`: the Gaia stars (G < 17) whose place falls inside the measuring
    circle (`radius_arcsec`, 15.4) around the object: `by_epoch` (per visit, at its
    middle date: `epoch`, `date`, `stars` with `source_id`, `gmag`, `distance_arcsec`,
    `east_arcsec`, `north_arcsec`) and `stars` (over the whole run: `nearest_arcsec`,
    `farthest_arcsec`, `epochs`). Their light is in every flux measured there; nothing is
    subtracted. `known` is false (and the lists empty) when Gaia did not answer; the
    result is then not cached. Same in `/api/spectrum`.
  - For saturated stars: `wing_mjy`, `wing_err_mjy`, `wing_status`, `wing_ring_px`,
    `wing_trusted`, `relative_wing`. This is a relative brightness from unsaturated
    pixels in a ring around the star, NOT a flux. Chart it only where `wing_trusted` is
    true (detectors 5 and 6); `relative_wing` is null elsewhere.
  - The first request for a position downloads every exposure of all six detectors
    (several minutes); after that it is served from `backend/cache/photometry/`.
- `GET /api/spectrum?ra=&dec=&epoch=` BUILT. The same per-exposure points sorted by
  wavelength, for one epoch (`epoch=1`, 2, ...) or all (omit it). `epochs` lists the
  epochs with their dates; a wrong epoch answers 400. Same optional parameters.

The page reads `?ra=&dec=&fov=&det=&mode=` from its address so a view can be linked, and
passes `pmra`, `pmdec`, `parallax` through to `/api/frames` when they are in the address.

Results are cached only when complete. If any cutout failed to download, or Gaia did not
answer, the response still comes back (with `failures` or `gaia_error` set) but is not
written to the cache, so the next request tries again. All cache files are written to a
temporary name and renamed, because the server and the warm-up script can build the
same entry at the same time.

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
   detectors so epoch numbers agree between detectors) and detector. Take a weighted
   mean with ONE weight per exposure, the inverse of its median variance. Per-pixel
   inverse-variance weights would down-weight the exposures in which a source is
   brightest, because VARIANCE includes source photon noise.
   - Glitches (the flags miss some): with 5 or more exposures, at each pixel the highest
     of at least three readings is dropped if it is far above the SECOND highest, and
     the lowest if it is far below the second lowest. Far means 6 times that exposure's
     noise plus the brightest value within 4 grid pixels in the second-highest image.
     It is dropped only as part of a small patch: the connected patch in which that
     exposure is the extreme by half that margin must be 85 grid pixels or less (what a
     2 x 2 block of native pixels spreads over), and then the whole patch goes.
   - Never go back to "drop what disagrees with the median". Each exposure is at its
     own wavelength, so a source with a steep spectrum is bright in a minority of them
     and such a rule throws its light away (see "Stacking and glitches").
   - `pipeline.Stacker` takes the exposures one at a time and keeps only running sums
     and the two highest and two lowest readings per pixel, so memory does not grow
     with the number of exposures. Builds run one at a time (a lock in `build_frames`).
7. Apply ONE brightness stretch per detector across all epochs (asinh, limits from the
   combined pixel distribution; the top of the scale is the brightest pixel so bright
   stars keep their shape). Per-frame auto-scaling would make brightness changes
   look fake or hide real ones.
8. Measure the target in each frame. First how strongly it is detected at the predicted
   place (`detection_sigma`: a fixed-position fit with the known Gaia neighbours,
   compared with the same fit at the frame's empty places). Then where it is: a round
   Gaussian fitted to valid pixels only (so a saturated star is located from its wings),
   started at the brightest pixel within 6 arcsec of the predicted place. It counts as
   the target only if it is detected (3 times the noise or more) and within 3 arcsec of
   the prediction (see `centroid` under Endpoints); otherwise there is no centroid, and
   the reason is given. Only a view with no target at all falls back to the brightest
   source near the centre. Gaia is asked for the view's stars even when the request gives
   a motion (3 short tries then): they are the known neighbours.
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

Stacking and glitches (`pipeline.Stacker`, `scripts/check_stack.py`, 2026-11-14)
- The first rule dropped every reading more than 6 sigma (plus local brightness) from
  the per-pixel median. It threw away real light. Epsilon Indi B in detector 1 is 17
  times brighter at 1.08 microns than at 0.85 (6.65 against 0.39 MJy/sr in visit 2), so
  the median sat near the faint end and the bright readings were dropped. Brightness at
  the target (3 x 3 grid pixels minus the frame median, MJy/sr), old rule / present rule
  / nothing dropped: detector 1 visit 2, 0.235 / 1.222 / 1.222; visit 3, 0.813 / 1.879 /
  1.879; all visits following the target, 0.51 (from `docs/results.md`) / 1.527 / 1.527;
  detector 2 visit 3 (7 exposures), 4.84 / 7.707 / 7.707. The old rule also took 0.6 per
  cent off the core of Barnard's Star in visit 3 of detector 5.
- Real glitches are small: in Barnard's Star detector 5, WISE 0855 detector 6 and
  Epsilon Indi B detector 2 (visits 1 to 3) every patch that qualified was under 40 grid
  pixels. Large
  patches are whole exposures with a different background. Epsilon Indi B, detector 1,
  visit 3: `2026W16_2A_0434_1`, `2026W16_2A_0434_2` and `2026W18_2A_0819_1` differ from
  the other 17 by -1.0 to +0.9 MJy/sr over a third to two thirds of the frame (stray
  light from Epsilon Indi A 6.7 arcmin away; no flag marks it). Dropping pieces of them
  left visible steps, which is why a patch must be small to be dropped. They stay in the
  mean with their low weight and add a smooth gradient.
- The rule alone removes the dark spots it was first written for: with
  `impossible_pixels` switched off, Barnard's Star detector 5 visit 3 has a darkest
  pixel of -3.9 sigma with nothing dropped and -0.8 with the rule. WISE 0855 detector 6
  visit 3: -11.4 against -3.6; the target's brightness, the fit's own S/N (5.0, 18.6,
  27.4; not a detection strength, see `detection_sigma`) and position are the same as
  under the old rule.
- Barnard's Star detector 5 against the old rule: the same shifts (`check_barnard.py`),
  and 38 to 139 of the 32400 pixels of each frame differ, none by more than 2 grey levels.
- Known cost: something that two exposures show at overlapping places counts as seen
  twice and stays. WISE 0855 detector 6 visit 3 has two such places, at PNG pixels
  (102, 8) and (76, 168): a compact blob of 7 to 18 MJy/sr in one exposure and another
  8 arcsec away in an exposure 8 to 13 days later (not a moving object, cause unknown).
  The parts that overlap stay and the cores are dropped, leaving two small ring-shaped
  marks that the old rule removed completely.
- A source seen in only one exposure of a visit is still dropped, as before. Visits
  with fewer than 5 exposures still get no glitch removal at all.
- Memory, largest cached view (Epsilon Indi B, detector 5, fov 0.3, 86 exposures, 540 x
  540 grid), peak of a fresh process, old / new: normal 835 / 290 MB, sum 1154 / 261 MB,
  difference against the mean 1735 / 321 MB. Importing the backend alone is 123 MB.
  Barnard's Star fov 0.2 sum: 556 / 196 MB. The streaming stack gives the same image as
  the same rule applied to all exposures held at once, to 4e-16 MJy/sr. A 0.5 degree
  field (900 x 900) needs about 50 MB per stack being built, whatever the exposure count.

Gaia field stars (`/api/stars`, `scripts/check_stars.py`, 2026-11-14)
- Stars brighter than G = 17 inside the picture: Barnard's Star 64 at fov 0.1 and 280 at
  fov 0.2; WISE 0855 15 at fov 0.1; Epsilon Indi B 103 at fov 0.3. The answer is 20 kB for
  64 stars and three frames, 96 kB for 280, and a repeat request takes 2 to 5 ms.
- The listed places agree with the pictures: for isolated stars fitted in each frame, the
  median distance from the catalogue place is 0.15 to 0.37 arcsec (Barnard's Star 8 to 9
  stars per frame at fov 0.1 and 42 to 46 at fov 0.2; Epsilon Indi B 36 to 46 at fov 0.3;
  WISE 0855 detector 6, 4 to 5 stars, 0.16 to 0.53).
- Epsilon Indi B itself (G = 18.0) is fainter than the G = 17 search limit, so it is not
  in the list; it is drawn from `target` and `predicted` when the motion is passed.
  Epsilon Indi A (G = 4.3, 4.7 arcsec/yr) is listed when the field is wide enough.
- Gaia's synchronous TAP returned all 4288 stars (G < 17) within 0.435 degrees of
  Barnard's Star, the search a 0.5 degree field makes, in 3.9 s with QUERY_STATUS OK: no
  2000-row cut.

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
- The CfA mirror answers HTTP 400 to any name with a character outside plain ASCII
  ("Barnard’s Star" with a curly apostrophe, "ε Indi B", "Bételgeuse", a true minus
  sign). With Strasbourg down that used to come back as 502 "service down". Now the
  name is cleaned first and all four resolve; "eps Indi B", "alf Ori", "mu Cep" and
  "mu. Cep" each match one object. A 400 from a mirror is reported as "not found"
  (404); with every mirror unreachable an uncached name still answers 502.
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
- The frames' `photometry_saturated_exposures` agrees with the lightcurve's own count.
  RW Aurigae, every frame reporting 0 `saturated_pixels`: detector 2, 7/18, 8/19 and
  13/19 exposures in the three visits against 7, 8 and 13 "saturated" in
  `/api/lightcurve`; detector 3, 14/19, 16/18, 16/18 against 14, 16, 16; detector 5,
  17/18, 6/19, 0/19 against 17, 5, 0. Over all detectors 171 against 167 (the frames
  also count the 10 exposures that have no wavelength and so no lightcurve point).
  Barnard's Star 354 against 350 of 354; WISE 0855 0 against 0.

Unflagged negative pixels (found 2026-11-14)
- Every target has pixels whose raw IMAGE value is more than 10 sigma below zero and
  that carry no defect flag (only SOURCE): 45 to 108 pixels per target over 258 to 548
  cutouts, mostly detectors 4 to 6, values from -0.1 to -2112 MJy/sr. `stack()` rejects
  them when an epoch has 5 or more exposures. WISE 0855 has an epoch of 3 exposures in
  detector 6 (2025-05-05), where one reading of -2000 MJy/sr left a black patch and set
  the difference scale to +/-579 MJy/sr. `pipeline.impossible_pixels` now masks them
  before stacking and photometry treats them as empty. Barnard's Star numbers did not
  change.

WISE 0855 (fov 0.1, motion from `/api/resolve`; checked independently in
`docs/verification.md`, section 1, on single exposures with separate code)
- What is established: SPHEREx detects WISE 0855 in detectors 5 and 6 only (3.8 to 5.0
  microns), at about 0.5 mJy at 4.4 to 5 microns, and nothing certain below 3.8 microns
  (16 bins from 0.75 to 3.8 microns each within 0.02 mJy of zero). With the neighbouring
  star's light removed it is within 0.4 arcsec of the prediction in every visit and moves
  8.4 +/- 0.4 arcsec west in a year (0.986 years from visit 1 to 3) against 8.0 predicted.
  The place it left is empty a year later.
- A Gaia star (DR3 5756956644387831296, G = 16.3, nearly static, about a third as
  bright as WISE 0855 at 4.6 microns) lies 11.4, 8.1 and 4.3 arcsec from WISE 0855 in
  visits 1, 2 and 3. In visit 3 the two are one blob in 6-arcsec pixels and the star
  supplies about a quarter of the detector 6 light (22 to 25 per cent; 42 per cent in
  detector 5).
- Detector 6, visit 1 has only 3 exposures (all at 4.86 to 5.0 microns) and the source is
  marginal there (3.7 times the noise in the independent check). Detector 5 has 8
  exposures in that visit and shows it at 13.
- `detection_sigma` of the frames (motion passed): detector 6 visits 1 to 3: 3.4
  ("marginal"), 14.6, 11.2; detector 5: 10.9, 12.5, 8.8; detectors 1 to 4: -1.3 to 2.9,
  all "none". The independent check gave 3.7, 17.5, 14.2 and 12.9, 17.3, 12.5. The
  frames' fitted brightness in detector 6 is 0.29, 0.48, 0.48 mJy (check: 0.28, 0.47,
  0.46). Without the star fitted as a neighbour, detectors 1 to 4 showed up to 60 times
  the noise at the predicted place, all of it the star.
- Sum of all 45 detector 6 exposures: `detection_sigma` 15.3 lined up on the sky, 18.9
  following the motion (detector 5 following it: 18.2).
- The markers sit 0.8 to 1.3 arcsec from the prediction, pulled toward the star (the
  fit takes in its light); the position with the star removed is within 0.4 arcsec. The
  older figures "S/N 5, 19 and 27" and "within 1.3 arcsec" were the fit's own S/N (not
  a detection strength) and, in visit 3, partly the star: do not quote them.
- Difference against epoch 1 (detector 6) shows a white spot at the epoch 3 position;
  the dark half of the pair is lost in the noise of the 3-exposure reference.
- Without `pmra`/`pmdec`, `/api/frames` at this position picks that Gaia star as
  `target` (it is within 15 arcsec of the centre). The frontend must pass the motion
  from `/api/resolve` for objects Gaia does not list.

The marker is the target or nothing (`centroid`, checked 2026-11-14 on 41 views)
- Before, `centroid` was whatever was brightest within 14 arcsec of the predicted place.
  At WISE 0855 in detector 1, with the motion passed, that was the Gaia star of the
  section above (fit S/N 41, 59 and 48) at 11.4, 8.6 and 4.4 arcsec from the prediction.
  Now those three frames have `centroid` null, and that star in `nearest_source`.
- WISE 0855 detector 6 with the motion keeps its three markers (0.8, 1.3 and 1.1 arcsec
  from the prediction; `detection_sigma` 3.4 "marginal", 14.6, 11.2). Without the motion
  the target is the Gaia star, what is measured is the brown dwarf 10.5, 6.8 and 3.3
  arcsec from it, and all three frames now say so with a null `centroid`.
- Every other marker of the 41 views is where it was: Barnard's Star in all six
  detectors (0.1 to 1.5 arcsec from the prediction), Epsilon Indi B detector 5 (0.5 to
  0.8), RW Aurigae detectors 1, 3, 5 (0.1 to 1.5) and R Draconis detectors 1, 3, 5 (0.3
  to 2.9). The `check_barnard.py` shifts are unchanged.
- Why the limits are what they are: the largest offset of a real target is R Draconis in
  detector 3 (2.9 arcsec; it is saturated and fitted from its wings, 19 to 30 arcsec
  wide), the smallest offset of a wrong object is 3.3 arcsec with a width of 10. Hence
  3 arcsec, or a quarter of the fitted width if that is more. The margin is thin.
- `astrometry.offset_arcsec` now takes the short way round in right ascension, so two
  points either side of RA 0h are no longer 360 degrees apart.

Detection strength (`detection_sigma`, pipeline.VERSION 8, checked 2026-11-14 on 60 views:
five targets, six detectors, with and without the motion, fov 0.1)
- Why: the fit's own `snr` is not a detection strength (it is 5 or more at many empty
  places), yet it decided whether a marker was drawn. Now `detection_sigma` decides.
- Every marker of the 60 views is where it was under version 6 (same frames, same
  centroid or none); the pictures are byte for byte the same; the `check_barnard.py`
  shifts are unchanged. 115 frames are "clear", 54 "saturated", 1 "marginal" (WISE 0855
  detector 6, visit 1) and 13 "none" (WISE 0855 detectors 1 to 4 with the motion, and
  the Gaia star at WISE 0855's place in detector 6, visit 1, when the motion is left out).
- A first version used a plain circle of 6 arcsec radius minus a local sky. It gave the
  right answer in detectors 5 and 6 of WISE 0855 but 3.7 to 60 times the noise in
  detectors 1 to 4, all of it the G = 16.3 star 4 to 11 arcsec away. Fitting known Gaia
  neighbours at their catalogue places brought those to -1.3 to 2.9.
- Width of a star in a stacked frame, measured on isolated field stars (Barnard's Star
  and WISE 0855 fields, three visits each): 9.0 arcsec in detectors 1 to 3, 9.9 in 4,
  10.0 in 5, 10.3 in 6, spread 0.1 to 0.7 within a frame. These fixed widths are used.
- Empty places per frame at fov 0.1: 355 to 650 kept, 5 to 245 set aside as holding a
  source no catalogue here lists (most at R Draconis, 166 to 245; why was not examined).
  In WISE 0855 detector 2 visit 2, 61 of 656 empty places reach the 2.9 of
  the target position: `n_blank_as_strong` says how unusual a value is in that frame.
- Limits: only Gaia stars brighter than G = 17 are known neighbours. An object Gaia does
  not list (WISE 0855 itself, seen from the Gaia star's place without the motion) is not
  separated, and adds its light. The fixed star width does not fit a saturated star or
  the smeared stars of a target-following sum; there `detection_sigma` is only a
  yes-or-no, and saturated places count as detected.

Saturated stars: position uncertainty (`centroid.saturated_core`, pipeline.VERSION 9,
same 60 views)
- Barnard's Star sits 1.45 arcsec east of Gaia in visit 1 of detector 5 because its
  saturated and bloom-flagged core pixels still hold numbers and stay in the fit (on
  purpose: they draw the star). The independent check found that blanking them is no
  better (unsaturated light alone: up to 1.85 arcsec off in detector 2), so they stay,
  and the uncertainty says what is known instead.
- Flagged: every frame of Barnard's Star and R Draconis in all six detectors; RW
  Aurigae in 15 of its 18 frames (not detector 5 visit 3, where 0 of 19 exposures are
  saturated, nor detector 1 visit 2 and detector 6 visit 2). Not flagged: any frame of Epsilon
  Indi B or WISE 0855. A first version also counted flagged pixels that are masked out
  of the picture (single dead or persistent pixels marked OVERFLOW and SUR_ERROR) and
  wrongly flagged Epsilon Indi B detectors 5 and 6; only pixels that keep their value
  count now.
- Barnard's Star detector 5: `err_arcsec` 1.0 in all three visits (fit's own 0.037,
  0.026, 0.029); detectors 1 to 4: 2.0 (fit's own 0.04 to 0.11). Every offset from Gaia
  in those frames (0.12 to 1.45 arcsec) is within it. Markers, pictures and the
  `check_barnard.py` shifts are unchanged.

Blended neighbours and stars in the measuring circle (`blend`, `stars_in_circle`;
pipeline.VERSION 10, photometry.VERSION 7; same 60 views)
- Frames with a `blend`: 42 of the 60 views' frames. WISE 0855 visit 3 (motion passed)
  in every detector: the G = 16.31 star 4.2 to 4.4 arcsec away. Its share of the fitted
  light: 0.25 in detector 6 (0.165 mJy; independent check 22 to 25 per cent, 0.15 +/-
  0.03 mJy) and 0.41 in detector 5 (check: 42 per cent); 0.95 to 1.0 in detectors 1 to 4,
  where WISE 0855 is not detected. Every RW Aurigae frame: Gaia 156430822114424576
  (G = 12.18), its companion, 1.5 to 1.7 arcsec away: one blob, too close to share out
  (a first version gave fitted fluxes from -206 to +1131 mJy there, hence the 90 per
  cent overlap limit). None at Barnard's Star, Epsilon Indi B or R Draconis.
- Markers, pictures and the `check_barnard.py` shifts are unchanged.
- `stars_in_circle` (15.4 arcsec): WISE 0855 with the motion lists the G = 16.31 star at
  11.35, 8.23 and 4.26 arcsec in visits 1 to 3; RW Aurigae lists its companion at 1.6
  arcsec in every visit; Barnard's Star, R Draconis and Epsilon Indi B list none (G < 17
  only). Photometry statuses are unchanged (RW Aurigae 131 ok, 167 saturated, 28 flagged).

Reading cutouts straight from S3 (confirmed 2026-11-14, `scripts/check_s3.py` repeats it)
- `backend/s3fetch.py` reads only the image rows a cutout needs from the public bucket,
  `https://nasa-irsa-spherex.s3.amazonaws.com/<key>` (the key is the IRSA URL after
  `/ibe/data/spherex/`), with plain HTTPS `Range` requests and no account. One range per
  request: a request naming two ranges is answered with the whole 65 MB file.
- The file it writes is byte for byte the slim cutout made from IRSA's cutout service:
  144 sampled exposures (34 clipped by a detector edge) and, in a full run, all 364 for
  Barnard's Star, with 0 differing pixels, header lines or bytes.
- Speed from this machine: one detector at 0.15 degrees (62 cutouts) in 7.9 s, all six
  detectors (364) in 42 s, one detector at 0.5 degrees in 21 s, no retries. Through IRSA
  the same 364 took 247 s. A view that is not cached now answers in about 15 s (was 52 s).
- `spherex.fetch_cutout` tries S3 first and falls back to IRSA for that cutout on any
  failure. `SPHEREX_USE_S3=0` turns S3 off. The tests run with it off.
- FLAGS is tile-compressed in the full files (one tile per image row), so its size
  differs from file to file and every later extension starts at a different byte: the
  headers are read, never assumed.

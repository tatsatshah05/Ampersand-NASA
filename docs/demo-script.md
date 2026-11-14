# Demo video: shot-by-shot outline

For issue #16. Target length: about two and a half minutes. Record from the deployed
site, not a laptop server, so what the judges see matches what they can open.

**How to read this.** Lines marked **[CONFIRMED]** rest on something measured and
written down, in `CLAUDE.md` "Verified facts" or in `docs/results.md` (results of
2026-11-14). Lines marked **[TO CONFIRM]** depend on something that did not exist, or
that nobody had seen, when this was written. Before recording, check each one against
the live site; if it does not hold, use the fallback given, never the hopeful line.

Nothing in the video may be simulated, substituted or retouched. If a target shows
nothing, say so on camera: that is the result.

## What exists (2026-11-14) and what the script assumes

The data side is built and was checked on all five targets. The page a visitor sees
was still being changed when this was written, so every control named in the shots
below must be checked on the final page before recording.

| Piece | State |
|---|---|
| Frames for every target: normal, difference and sum, all six detectors | **[CONFIRMED]** built and looked at (`docs/results.md`) |
| Name to position, moved to where the object is now | **[CONFIRMED]** built (`/api/resolve`) |
| Brightness measurements over time, and brightness against wavelength | **[CONFIRMED]** built (`/api/lightcurve`, `/api/spectrum`); charts made from them are in `docs/results/` |
| The viewer: play, pause, step, blink first and last, trail, zoom, and menus for detector, field of view and mode | A viewer with these controls existed on 2026-11-14 (it was loaded and screenshotted for three views, but nobody clicked through it for this script). **[TO CONFIRM]** they are all on the page you record from, and work. |
| Name search box on the page | **[TO CONFIRM]** Fallback: open each target with the values in the table below, prepared beforehand. |
| Brightness chart on the page | **[TO CONFIRM]** Fallback: show the chart images in `docs/results/` and say they were made from the same measurements. |
| Spectrum on click | **[TO CONFIRM]** Fallback: as for the chart. |
| Measured-versus-Gaia numbers on screen | Seen on the site's front page for Barnard's Star on 2026-11-14: "measured shift 10.2 north, 2.2 west. Gaia predicts 10.3 north, 0.8 west. They differ by 1.4 arcsec, which is 0.23 of a SPHEREx pixel." **[TO CONFIRM]** it still reads so when you record. |
| Public address | **[TO CONFIRM]** nothing was deployed when this was written. |

## Before recording

- [ ] Site is deployed and `python scripts/warm_cache.py --check` passes on the server.
- [ ] Each target below has been opened once on the recording machine.
- [ ] Field of view stays at 0.1 degrees. Only that size is warmed; any other size
      downloads for about a minute per detector, live.
- [ ] Browser zoom 100%, window about 1280 x 720, no bookmarks bar, notifications off.
- [ ] Re-read `docs/results.md`: it says what each target really shows, and lists
      frames to avoid (a few have artefacts).
- [ ] Every **[TO CONFIRM]** line has been checked and either kept or replaced.

## The five targets: values to open them with

These are what the name search (`/api/resolve`) returned on 2026-11-14: the position
moved to 2026.0, and the motion. Pass the motion along with the position: without it
the marker can follow the wrong object (it does at WISE 0855). **[TO CONFIRM]** how
the final page takes these (a search box, or values in the page address).

| Target | RA (deg) | Dec (deg) | pmra (mas/yr) | pmdec (mas/yr) | parallax (mas) |
|---|---|---|---|---|---|
| Barnard's Star | 269.446267 | +4.768222 | -801.5509783684709 | 10362.394206546573 | 546.975939730948 |
| Epsilon Indi B | 331.096653 | -56.800663 | 3981.97666296105 | -2466.8318147663504 | 270.6580324694526 |
| WISE 0855-0714 | 133.759765 | -7.242182 | -8123.7 | 673.2 | 439.0 |
| RW Aurigae | 76.956587 | +30.401291 | 7.23 | -20.33 | 15.42 |
| R Draconis | 248.167233 | +66.755024 | -20.642811719160797 | 6.148818852711324 | 1.2509180143740992 |

## Shots

### 1. The question (0:00 to 0:20)

- **On screen:** the site, before anything is typed. Optionally a still of the SPHEREx
  spacecraft from NASA's image library, with credit.
- **Say:** "NASA's SPHEREx telescope maps the whole sky in infrared light, and then
  maps it again about six months later. Anything that moved or changed between maps
  is interesting: a nearby star, a failed star, maybe a world nobody has found yet.
  The data is public, but it is not easy to look at. We built a way for anyone to
  watch a patch of sky change."
- **Basis:** the six-month revisit is **[CONFIRMED]** at all five test targets: three
  or four visits each between April 2025 and October 2026, about five to six months apart.

### 2. Barnard's Star moves (0:20 to 1:00)

- **On screen:** Barnard's Star, detector 5 (3.8 to 4.4 microns). Let the three frames
  loop. Pause; step through them with the marker and trail on; blink between the first
  and last frame.
  Then switch Mode to Difference: the star shows as a white patch beside a black one.
- **Say:** "This is Barnard's Star, the fastest-moving star in the sky. Each frame is
  one SPHEREx visit: about twenty exposures, stacked. Watch the star step north while
  everything around it stays put."
- **Say:** "We measured that step and compared it with the Gaia star catalogue. They
  agree to within a quarter of one SPHEREx pixel."
- **Say, on the difference view:** "Subtract the first visit from a later one and
  everything that stayed still cancels. What is left is the thing that moved."
- **Basis:** **[CONFIRMED]** three frames in every detector (17 to 25 exposures each);
  measured positions within 1.5 arcseconds of the catalogue's proper motion plus
  parallax in all six detectors; ordinary stars in the frame move by a median of 0.4
  arcseconds or less. Difference frames show the white-north, black-south pair.
- **Worth one sentence:** "The star's catalogue position is from the year 2000. It has
  moved four and a half arcminutes since, so the tool first works out where it is
  now." **[CONFIRMED]**
- **Avoid:** detectors 1 to 4 for this star in close-up: its core is saturated there
  (drawn as a flat white patch). Detectors 5 and 6 are clean.

### 3. A star that changes brightness: RW Aurigae (1:00 to 1:30)

- **On screen:** RW Aurigae in Difference mode. Show detector 1 or 2 (the star is
  white: brighter than at the first visit), then detector 6 (the star is black:
  fainter). Then the brightness chart.
- **Say:** "Some things do not move; they change. This young star, RW Aurigae, got
  brighter in near-infrared light and fainter at longer wavelengths between September
  2025 and September 2026. One subtraction shows it. Nothing else in the frame changed."
- **Basis:** **[CONFIRMED]** in the difference frames (detectors 1 and 2 white, 5 and 6
  black, the other stars only faint speckle) and in the per-exposure measurements:
  within the same wavelength bins the flux rose by a median factor of about 1.6 in
  detector 1 (0.75 to 1.1 microns) and fell to about 0.5 to 0.6 of its earlier value
  in detectors 5 and 6 (3.8 to 5 microns). Chart: `docs/results/rw_aur_brightness.png`.
- **[TO CONFIRM]** the chart is on the page. Fallback: show the image from `docs/results/`.
- **Care needed:** SPHEREx sees a star at a different wavelength in every exposure, so
  only measurements at nearly the same wavelength can be compared. The chart does
  that; two ordinary frames side by side do not prove a brightness change.
- **Do not use R Draconis for this shot.** **[CONFIRMED]** it is so bright that its
  core is saturated in every exposure of every detector; there is no flux to chart,
  only a relative brightness from the star's outer halo in detectors 5 and 6 (which
  fell to about 0.5 to 0.6 between mid-2025 and mid-2026). It can be mentioned as a
  limit: "very bright stars overload the detector."

### 4. The hardest target: WISE 0855 (1:30 to 2:05)

- **On screen:** WISE 0855, detector 6, Normal mode with marker on; step through the
  three frames. Then detector 2 for contrast (the object is not there). Then detector 6
  in Sum mode.
- **Say:** "This is a very cold brown dwarf, and it moves almost as fast as Barnard's
  Star. In ordinary near-infrared light it is invisible." (switch to detector 2 and
  back) "At the longest wavelengths SPHEREx measures, there it is, and it moves west
  from one visit to the next, where the catalogue says it should."
- **Wording:** "very cold" and "about 8 arcseconds a year" are from the project brief.
  Anything stronger ("the coldest known") must be checked against a NASA page first.
- **Basis:** **[CONFIRMED]** a faint source at the predicted place in detectors 5 and 6
  in each visit's stacked frame (weakest in the first visit, which has only 3 to 8
  exposures), nothing at that place in detectors 1 to 4 at the first visit, and a
  westward shift of about 8 arcseconds in a year.
- **Say this too, it is part of the honest result:** "By 2026 it has drifted to within
  four arcseconds of an ordinary background star, closer than SPHEREx can separate.
  The star is the one you see at short wavelengths; it fades at long wavelengths just
  as the brown dwarf appears."
- **Correction to the plan:** the challenge text and the plan expected this object to
  appear "only after summing". **[CONFIRMED]** it is already visible in the per-visit
  frames of detectors 5 and 6; the summed frame (following the target) shows it more
  clearly. Do not say "only after summing".
- **Check before recording this shot.** On 2026-11-14 the site's front page, opened
  on WISE 0855 without the motion values, compared the object with a neighbouring
  catalogue star and read "They differ by 7.8 arcsec, which is 1.27 of a SPHEREx
  pixel", as if something were wrong. The measured 7.8 arcsec west is the result; the
  comparison is with the wrong star. Record this shot only from a view that was given
  the motion values, and check what the text under the frame says.
- **Trap to mention if it comes up:** this object has moved 212 arcseconds since 2000.
  **[CONFIRMED]** a search on its catalogue coordinates looks at the wrong spot, and a
  coordinates-only request (without the motion values) makes the marker follow the
  background star instead. Use the values in the table above.

### 5. What SPHEREx adds (2:05 to 2:20)

- **On screen:** the spectrum of Epsilon Indi B, or of WISE 0855 (brightness against
  wavelength).
- **Say:** "The existing tool for this kind of search, WiseView, uses the WISE
  telescope's infrared bands. SPHEREx measures about a hundred colours. This is the
  light of a brown dwarf, colour by colour: bright peaks with deep gaps between them."
  Or, on WISE 0855: "For this cold brown dwarf you can see the light switch on beyond
  four microns."
- **Basis:** **[CONFIRMED]** Epsilon Indi B: 298 measurements trace its brightness from
  0.75 to 5 microns, the same curve at all four visits, with deep dips near 1.4 and
  1.8 to 1.9 microns (`docs/results/eps_indi_b_brightness.png`). It is the clearer
  picture of the two. WISE 0855: about 0.2 mJy between 3 and 3.9 microns, rising to
  0.5 to 1 mJy between 4.1 and 4.8 microns (`docs/results/wise0855_brightness.png`;
  short of 4 microns the light is the background star's).
- **Do not explain the gaps** ("water", "methane") unless someone has checked that
  against a published source. This project measured the gaps, not their cause.
- **[TO CONFIRM]** the page shows a spectrum. If it does not, show the image from
  `docs/results/` and say so, or cut this shot.
- **Check the wording** before recording: "about a hundred colours" against NASA's
  SPHEREx page, and how many bands WiseView uses against the WiseView page. Neither
  figure was checked by this project.

### 6. Close (2:20 to 2:30)

- **On screen:** the site address, the team name, and the credits line.
- **Say:** "Type any coordinates and watch that patch of sky. Built by Team Ampersand
  for NASA Space Apps 2026."
- **Credits on screen (must be legible):** Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC
  Infrared Science Archive (IRSA); ESA Gaia DR3. Name lookup: SIMBAD (CDS, Strasbourg).

## Optional extra shot: Epsilon Indi B

**[CONFIRMED]** the brown dwarf pair (seen as one point) is visible in all six
detectors and moves south-east by about 6.3 arcseconds between spring 2025 and autumn
2026, on the catalogue track. Its bright primary star is 6.7 arcminutes away, outside
the default 0.1 degree frame, so "moving with the primary" needs a wider field of view
(see `docs/results.md` for what the wide view showed). Not needed for a 2.5 minute video.

## Things not to say

- Not "real time" or "live": SPHEREx data arrives in releases, and each visit is months apart.
- Not "discovers Planet X": the tool makes moving objects easier to spot; it has not found anything new.
- Not "every frame is one photo": each frame is a stack of the exposures from one visit.
- Not "only after summing" for WISE 0855 (see shot 4).
- Not a brightness claim from two ordinary frames; use the difference view or the chart.

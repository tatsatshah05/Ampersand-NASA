# Project page text

For issue #16: text to paste into the NASA Space Apps project page. First written
2026-11-14 and updated the same day against the running page and the repository's
records. Check the submission form for length limits before pasting; a short and a long
version are given (the short one is about 100 words, counted below).

**Read before pasting.** Everything stated as fact below is in `CLAUDE.md` "Verified
facts", `docs/results.md`, `docs/verification.md` or `docs/search.md`, or was seen on the
running page on 2026-11-14. Two things must still be supplied by a person and are marked
**[TO CONFIRM]**: the public web address (nothing is deployed) and the answer about AI
tools. Do not paste a marked sentence as it stands.

Words used: a **visit** is one pass of SPHEREx over a patch of sky; a **detector** is one
of SPHEREx's six infrared cameras.

---

## Project name

SPHEREx sky-change viewer (Team Ampersand)

## One-line summary

Watch NASA SPHEREx images of any patch of sky play like a short video, so anything that
moved or changed brightness stands out.

## Short description (about 100 words)

NASA's SPHEREx telescope maps the whole sky in infrared light and comes back to each
patch about every six months. Things that move or change between visits are worth a
look: nearby stars, cold "failed stars" called brown dwarfs, perhaps a distant world.
Type a star's name or a position and our web tool fetches the real SPHEREx images from
NASA's public archive, stacks each visit into one frame and plays them in a loop. On
Barnard's Star, the fastest-moving star in the sky, it visibly steps across the frames
by the amount the Gaia star catalogue predicts. A blind search and a practice mode
come with it.

## Full description

### The problem

SPHEREx is a NASA space telescope that maps the whole sky in infrared light and repeats
the map about every six months. Comparing one map with the next can reveal objects that
move: stars close to the Sun, brown dwarfs, and possibly distant members of our own solar
system that nobody has seen yet. The images are public, but they are stored as a very
large number of separate exposures in a format built for professional astronomers. There
was no simple way for a curious person to ask "what changed here?"

### What we built

A web page that shows SPHEREx images of one patch of sky, one visit after another, like a
flip-book. North is up, the frames are lined up with each other, and a marker shows where
the object at the centre was measured in each frame.

- **Search.** Type a star's name (it is looked up and moved to where the star is now) or
  a position. Buttons jump to the five targets named in the challenge.
- **Player.** Play, pause, step, blink between the first and last frame, change the
  speed, zoom and drag. Choose which of SPHEREx's six detectors (six ranges of infrared
  colour) to look through, and the size of the patch.
- **Three views.**
  - **Normal:** one frame per visit.
  - **Difference:** a later visit minus the first. Everything that stayed the same cancels
    to grey; something that moved leaves a white patch next to a black one, and something
    that brightened or faded leaves a single white or black patch.
  - **Sum:** every exposure added together, for objects too faint to see in one visit. The
    exposures can be shifted to follow a moving object before adding.
- **Gaia overlay.** Marks where the Gaia star catalogue says the object should be, and
  prints the measured shift next to the predicted one.
- **Spectrum.** Click any spot, or press "Spectrum of the target", to see brightness
  against colour, one dot per exposure, with the numbers to download.
- **Brightness chart.** "Brightness over time" compares measurements only at the same
  colour, and says in words whether the object got brighter, fainter, or whether there
  is too little to say.
- **Honest labels.** The page says how strong each detection is (in times the background
  scatter, and "marginal" when it is weak), warns when a star is so bright that its
  centre is overexposed, when a neighbouring star is blended in, and when a very bright
  star nearby can leave ghost rings. A Flags switch colours pixels with no data and
  pixels too bright to measure.
- **Sky context.** The same patch in other surveys (WISE, 2MASS, optical), from the Aladin
  sky atlas. It relies on outside servers, which were down for part of 2026-11-14; when
  they are, the panel says so and the rest of the page works.
- **Blind search.** A button, "Search this patch for anything that moved or changed", looks
  at every source in the patch without being told what to look for, and lists what moved
  or changed, with a number for how strong it is, and whether the star catalogues already
  know it. Details below.
- **Practice mode.** "Practise: find a planted object" adds ONE made-up moving object to
  real frames and asks the visitor to find it. It is a simulation, used only for
  practice: the screen carries a banner that cannot be closed and the word SIMULATION is
  drawn in every picture. It never reaches the real views. Apart from it, nothing shown
  is simulated or filled in.

Behind the page, for every request, the tool:

1. Works out where the object is **now**. Star catalogues list positions for the year
   2000, and fast stars have moved since: Barnard's Star by four and a half arcminutes.
   The tool moves the position forward using the star's measured motion.
2. Asks NASA's archive which SPHEREx exposures cover that spot and reads just the small
   patch needed from each one (about 35 to 100 exposures per detector), directly from
   NASA's public copy of the archive on Amazon S3, with the archive's own cutout service
   as the fallback.
3. Cleans each exposure: removes the glow of dust in our solar system using the model
   supplied with the data, and discards pixels the mission has flagged as damaged or hit
   by a cosmic ray.
4. Stacks all the exposures from one visit into a single, deeper frame. This matters for
   SPHEREx in particular: each exposure sees a star in a slightly different colour of
   infrared light, so two single exposures cannot be compared fairly, but two stacks can.
5. Uses the same brightness scale for every frame, so that a change in brightness on
   screen is a change in the data and not a display trick.

### What we found on the five test targets

Measured on real SPHEREx data, then measured again with separate code and compared with
outside catalogues and ground-based observers (`docs/verification.md`).

- **Barnard's Star** (fastest-moving star). Three visits, August 2025 to September 2026.
  The star moves north by about 10 arcseconds over the year. In detector 5 the measured
  shift (10.2 north, 2.2 west) agrees with the Gaia catalogue's prediction (10.3 north,
  0.8 west) to within 1.4 arcseconds, 0.23 of one SPHEREx pixel; in all 18 frames
  (three visits, six detectors) the measured position is within 1.5 arcseconds of the
  prediction. Ordinary stars in the same frames stay still (a median shift under 0.4
  arcseconds). The star overloads the detectors, so its position is only good to about
  1 arcsecond.
- **Epsilon Indi B** (a pair of brown dwarfs, seen as one point). Visible in all six
  detectors (faint in the shortest) and moving south-east along the catalogue track,
  6.3 arcseconds between April 2025 and October 2026. In a wider view the bright star it
  accompanies, Epsilon Indi A, leaves the same white-and-black mark in the difference
  image, in the same direction.
- **WISE 0855-0714** (a very cold, fast-moving brown dwarf). Seen only in the two
  longest-wavelength detectors (3.8 to 5.0 microns). In detector 6 it is a marginal
  detection in the first visit (3.4 times the background scatter, from only three
  exposures), then clear in the second and third (14.6 and 11.2 times). It moves 8.4
  arcseconds west in a year, as the catalogue says it should (8.0). By the third visit an
  unrelated star 4 arcseconds away supplies about a quarter of the light at 4.4 to 5
  microns, and SPHEREx cannot separate them.
- **RW Aurigae** (a young variable star). Between September 2025 and September 2026 it
  became about 1.7 times brighter at the shortest wavelengths and about half as bright at
  3.9 to 5 microns. The difference view shows this directly, and observers on the ground
  (AAVSO) recorded the same brightening, about 1.7 times in one filter. They also show
  that our September 2025 exposures fell in a dip lasting a few days. The fading at 3.9 to
  5 microns has no ground-based check. RW Aurigae is a close pair that SPHEREx measures as
  one.
- **R Draconis** (a bright long-period variable star). It is so bright that it overloads
  the detectors in every exposure, so its brightness cannot be measured. We measure the
  relative brightness of the star's outer light in the two longest-wavelength detectors. It
  rises and falls by a factor of about 2 to 3 over the three visits, in step with the
  246-day cycle that ground-based observers record; the same measure on Barnard's Star,
  which does not vary, stays flat to about 5 per cent.

We report what the data shows, including where it falls short.

### The blind search, and what it found

The search is given a patch of sky and nothing else. It finds every source that stands out
in the images, measures whether each moved in a straight line or changed brightness
between visits (comparing only the same colour each time), then tries to kill every
candidate with tests for the artefacts we found in SPHEREx data: reflections of bright
stars, overlapping glitches, saturated stars, blended neighbours. What survives is looked
up in five catalogues (Gaia DR3, SIMBAD, AAVSO's variable star index, CatWISE2020 and
AllWISE). Every detection is compared with the same measurement at hundreds of empty
places in the same picture, so the strength it reports is a measured one.

- Given only the five field centres, it found Barnard's Star, WISE 0855 and Epsilon Indi B
  moving at their catalogued speeds, and RW Aurigae changing, each labelled as already
  known. In 30 searches it reported 5 objects, all of them the targets, and no false
  alarm. It threw out a convincing-looking 7-sigma "mover" that turned out to be a
  reflection of Epsilon Indi A, and other blends and patches of nebula. Five objects in
  30 searches is a small sample: the false-alarm rate is below about 1 in 230 sources (95
  per cent confidence), not zero.
- We then pointed it at four young star clusters. Most of what it flagged there are young
  stars already listed as variable (17). Two candidates passed every test we have and are
  not listed as variable in the catalogues we asked; nine more changes could be neither
  confirmed nor ruled out.
- **The strongest candidate** is a young star buried in the Serpens South cloud (RA
  277.50547, Dec -2.06198) that became about five times brighter at 2.4 to 5 microns
  between September 2025 and March 2026 and stayed bright through September 2026. We
  checked it against another telescope. NASA's NEOWISE mission measured the same spot
  twice a year from 2014 to 2024, and its public archive shows this star swinging by a
  factor of 7 to 9. NEOWISE's last look, in March 2024, caught it at its faintest, at the
  level SPHEREx found in September 2025. So the search, knowing nothing, picked out a star
  that really is strongly variable, and SPHEREx watched it climb back out of a dip. It is
  not a new kind of event, and specialists who study young stars have very likely seen it
  vary. What we can say is that none of the variable-star lists we asked has it as
  variable, and that SPHEREx's pixels cannot tell which star of a tight group is the one
  changing. It is a candidate, not a finding. (Chart: `docs/search/serpsouth_neowise_spherex.png`.)

### Limits, stated plainly

- SPHEREx pixels are large (about 6 arcseconds). Motions between visits are only one to
  three pixels, even for the fastest stars, and two objects closer than that blur into one.
- So far there are only three or four visits to each of our test targets, so the "videos"
  are three or four frames long.
- The first time anyone asks for a new position, the tool has to read the image patches
  from NASA's archive: about 15 seconds when NASA's public copy answers, about a minute
  through the archive's own service. After that the position is kept and loads instantly.
  A new blind search takes 20 to 50 seconds once the images are on disk, about three
  minutes otherwise.
- Very bright stars overload the detectors (they saturate). The tool marks those pixels
  rather than hiding them, and does not report a brightness it cannot measure.
- A visit with very few exposures (fewer than about five) can give a patchy or noisy
  frame. One example: WISE 0855 in detector 6, visit 1, has three exposures and is marginal.
- The search cannot find objects that are too faint, move too slowly (about 1.2 to 2
  arcseconds a year is the least it can see with three visits), move faster than about
  16 arcseconds a year, or change by less than about 10 per cent. Objects inside bright
  nebulae and crowded fields give changes seen in one detector that cannot be told from
  artefacts, so only changes seen the same way in two or more detectors are quoted there.
- The faults our own testing found, and what is still open, are listed in
  `docs/results.md` and `docs/verification.md` in the code repository (some have been
  fixed since; see `CLAUDE.md`).
- The sky-context panel depends on outside servers that were unavailable at times on
  2026-11-14.

### How we compare with existing tools

WiseView, from the Backyard Worlds project, does this for NASA's older WISE telescope and
was our model. SPHEREx adds finer colour information: every point on the sky is measured
in 102 colours across the infrared from 0.75 to 5 microns.

### How we built it

- Backend: Python with FastAPI, astropy, reproject, numpy and scipy.
- Frontend: React and TypeScript, built with Vite; Aladin Lite for the sky-context panel.
- No accounts, no database, no API keys. All data comes from public archives at the time
  of the request and is kept on disk afterwards.
- Code: https://github.com/tatsatshah05/Ampersand-NASA
- Public web address: **[TO CONFIRM: nothing is deployed yet; add the address here once it
  is. Open it and check the five targets before pasting.]**

### Use of AI tools

**[TO CONFIRM by the team: answer the form's question accurately, in the team's own words,
about which AI tools were used and for what. This must be true and complete; do not paste
anything here that nobody has checked.]**

## Data and credits

- **SPHEREx images:** NASA/JPL-Caltech SPHEREx.
- **Archive and image cutout service:** NASA/IPAC Infrared Science Archive (IRSA); images
  also read from NASA's public Amazon S3 copy of the archive.
- **Star positions and motions:** ESA Gaia DR3 (European Space Agency, Gaia mission,
  processed by the Gaia Data Processing and Analysis Consortium).
- **Name lookup and object types:** the SIMBAD database, operated at CDS, Strasbourg, France.
- **Catalogues for the blind search:** Gaia DR3, SIMBAD, AAVSO's International Variable Star
  Index, CatWISE2020 and AllWISE (NASA/IPAC IRSA).
- **Brightness check on the Serpens South star:** NEOWISE single-exposure measurements
  (NASA/IPAC IRSA).
- **Ground-based brightness records for RW Aurigae and R Draconis:** AAVSO observers.
- **Sky context:** Aladin Lite (CDS, Strasbourg).
- **Inspiration:** WiseView and the Backyard Worlds: Planet 9 citizen science project.
- **Challenge:** NASA Space Apps 2026, "Planet X and SPHEREx".

Suggested credit line for the page footer and the video:

> Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive (IRSA); ESA Gaia DR3.

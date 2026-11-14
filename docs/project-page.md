# Project page text

For issue #16: text to paste into the NASA Space Apps project page. Written
2026-11-14. Check the submission form for length limits before pasting; a short and a
long version are given.

**Read before pasting.** Everything stated as fact below is in `CLAUDE.md` "Verified
facts" or in `docs/results.md` (results of 2026-11-14). Sentences marked
**[TO CONFIRM]** describe something that did not exist, or that nobody had seen, when
this was written. Check each against the live site, then either remove the marker or
remove the sentence. Do not paste a marked sentence as it stands.

---

## Project name

SPHEREx sky-change viewer (Team Ampersand)

## One-line summary

Watch NASA SPHEREx images of any patch of sky play like a short video, so anything
that moved or changed brightness stands out.

## Short description (about 100 words)

NASA's SPHEREx telescope photographs the entire sky in infrared light about every six
months. Things that move or change between those maps are worth a look: nearby stars,
cold "failed stars" called brown dwarfs, perhaps an undiscovered distant world. Our
web tool lets anyone look. Give it a position; it fetches the real SPHEREx images of
that spot from NASA's public archive, combines the exposures from each visit into one
clean frame, lines the frames up, and plays them in a loop. On Barnard's Star, the
fastest-moving star in the sky, the star visibly steps across the frames by the
amount the Gaia star catalogue predicts.

## Full description

### The problem

SPHEREx is a NASA space telescope that maps the whole sky in infrared light, and
repeats the map about every six months. Comparing one map with the next can reveal
objects that move: stars close to the Sun, brown dwarfs, and possibly distant members
of our own solar system that nobody has seen yet. The images are public, but they are
stored as a very large number of separate exposures in a format built for
professional astronomers. There was no simple way for a curious person to ask "what
changed here?"

### What we built

A web page that shows SPHEREx images of one patch of sky, one visit after another,
like a flip-book. North is up, the frames are lined up with each other, and a marker
shows where the object at the centre was measured in each frame. You can choose which
of SPHEREx's six detectors (six ranges of infrared colour) to look through.
**[TO CONFIRM against the final page]** You can pause, step, blink between the first
and last frame, and zoom.

Three ways to look:

- **Normal:** one frame per visit.
- **Difference:** a later visit minus the first. Everything that stayed the same
  cancels to grey; something that moved leaves a white patch next to a black one, and
  something that brightened or faded leaves a single white or black patch.
- **Sum:** every exposure added together, for objects too faint to see in one visit.
  The exposures can be shifted to follow a moving object before adding.

**[TO CONFIRM]** A search box where you type a star's name. (The part that turns a
name into a position, moved to where the object is now, is built and tested.)

Behind the page, for every request, the tool:

1. Works out where the object is **now**. Star catalogues list positions for the year
   2000, and fast stars have moved since: Barnard's Star by four and a half
   arcminutes. The tool moves the position forward using the star's measured motion.
2. Asks NASA's archive for every SPHEREx exposure covering that spot and downloads
   just the small patch needed from each one (about 35 to 100 exposures per detector).
3. Cleans each exposure: removes the glow of dust in our solar system using the model
   supplied with the data, and discards pixels the mission has flagged as damaged or
   hit by a cosmic ray.
4. Stacks all the exposures from one visit into a single, deeper frame. This matters
   for SPHEREx in particular: each exposure sees a star in a slightly different colour
   of infrared light, so two single exposures cannot be compared fairly, but two
   stacks can.
5. Uses the same brightness scale for every frame, so that a change in brightness on
   screen is a change in the data and not a display trick.

### What we found on the five test targets

- **Barnard's Star** (fastest-moving star). Three frames, from visits in August 2025,
  March 2026 and August 2026. The star steps north by about five arcseconds per
  visit. Our measured positions agree with the Gaia catalogue's prediction to within
  1.5 arcseconds, a quarter of one SPHEREx pixel, in all six detectors, while ordinary
  stars in the same frames stay still to within about 0.4 arcseconds.
- **Epsilon Indi B** (a pair of brown dwarfs, seen as one point). Visible in all six
  detectors and moving south-east along the catalogue track, about 6.3 arcseconds
  between spring 2025 and autumn 2026. In a wider view the bright star it accompanies,
  Epsilon Indi A, leaves the same white-and-black mark in the difference image, in the
  same direction.
- **WISE 0855-0714** (a very cold, fast-moving brown dwarf). Invisible at the shorter
  wavelengths, but a faint source appears at the predicted position in the two
  longest-wavelength detectors, and moves about 8 arcseconds west in a year, as the
  catalogue says it should. In 2026 it passes within 4 arcseconds of an unrelated
  background star, which SPHEREx cannot separate from it; the tool's measurements
  there are of the two together.
- **RW Aurigae** (a young variable star). Between September 2025 and September 2026 it
  became brighter at the shortest wavelengths (by a factor of about 1.6 between 0.75
  and 1.1 microns) and fainter at the longest (to about half between 4.4 and 5
  microns). The difference view shows this directly.
- **R Draconis** (a bright long-period variable star). It is so bright that it
  overloads the detectors in every exposure, so its brightness cannot be measured
  properly. The light in its outer halo, which is not overloaded, fell to between a
  half and two thirds of its earlier level between mid-2025 and mid-2026, at 3.8 to 5
  microns.

We report what the data shows, including where it falls short. Nothing shown is
simulated or filled in.

### Features still to confirm before submission

- **[TO CONFIRM]** A brightness chart over time on the page. (The measurements behind
  it are built and were used for the RW Aurigae and R Draconis results above.)
- **[TO CONFIRM]** A spectrum (brightness against colour) for any object you click.
  (The measurement is built.)
- **[TO CONFIRM]** The public web address of the deployed site.

### How it compares with existing tools

WiseView, from the Backyard Worlds project, does this for NASA's older WISE
telescope and was our model. SPHEREx adds finer colour information: every point on
the sky is measured across the infrared from 0.75 to 5 microns.

### Limits, stated plainly

- SPHEREx pixels are large (about 6 arcseconds). Motions between visits are only one
  to three pixels, even for the fastest stars, and two objects closer than that blur
  into one.
- So far there are only three or four visits to each of our test targets, so the
  "videos" are three or four frames long.
- The first time anyone asks for a new position, the tool has to download the image
  patches from NASA's archive, which takes about a minute per detector. After that
  the position is kept and loads instantly.
- Very bright stars overload the detectors (they saturate). The tool marks those
  pixels rather than hiding them, and does not report a brightness it cannot measure.
- A visit with very few exposures (fewer than about five) can give a patchy frame.
- Our own testing found faults we have not yet fixed; they are listed in
  `docs/results.md` in the code repository.

### How we built it

- Backend: Python with FastAPI, astropy, reproject, numpy and scipy.
- Frontend: a web page that plays the frames the backend builds.
  **[TO CONFIRM by the team: name the tools used.]**
- No accounts, no database, no API keys. All data comes from public archives at the
  time of the request and is kept on disk afterwards.
- Code: https://github.com/tatsatshah05/Ampersand-NASA

### Use of AI tools

**[TO CONFIRM by the team: answer the form's question accurately.]** For the record:
AI coding assistants (Anthropic's Claude) were used to write and check parts of the
code, to run the tests on the five targets and to draft documentation, including this
text. All images and measurements shown come from real SPHEREx data; no data, image
or result was generated by AI.

## Data and credits

- **SPHEREx images:** NASA/JPL-Caltech SPHEREx.
- **Archive and image cutout service:** NASA/IPAC Infrared Science Archive (IRSA).
- **Star positions and motions:** ESA Gaia DR3 (European Space Agency, Gaia mission,
  processed by the Gaia Data Processing and Analysis Consortium).
- **Name lookup:** the SIMBAD database, operated at CDS, Strasbourg, France.
- **Inspiration:** WiseView and the Backyard Worlds: Planet 9 citizen science project.
- **Challenge:** NASA Space Apps 2026, "Planet X and SPHEREx".

Suggested credit line for the page footer and the video:

> Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive (IRSA); ESA Gaia DR3.

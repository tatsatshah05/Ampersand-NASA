# Project page text

Text to paste into the NASA Space Apps project page (issue #16). Rewritten on 2026-11-15 against the running
page (built from `Dev` at commit `0221046`) and the project's records, then corrected after an independent
review of this text. On the evening of 2026-11-15 the answers were set out again in the order of the form's
eight fields ("The form, field by field", next): paste from there. The longer text after it is kept for anyone
who wants more detail than the form needs. The form's length limits are not known to us: check them when pasting.

**Read before pasting.** Every number and claim below is in the code, in a results file or in a write-up in the
repository; the write-up is named where it matters. Three things need a person and are marked **[TO FILL IN]**
or **[TO CONFIRM]**: the link to the demo (the slides are not uploaded anywhere public yet), and two sentences
of the answer about AI tools, which the team must agree are complete and true. Do not paste a marked sentence as
it stands. The public web address is filled in: the site was deployed on 2026-11-15.

Rules this text keeps, and any edit must keep: the three sweep sources are **candidates**, "found in no
catalogue or report we checked" and "not confirmed"; their three sentences are the referee's, word for word
(`docs/sweep/vetting/ruling.json`); nothing has been reported anywhere; never "discovery", "first" or "new
planet".

Words used: a **visit** is one pass of SPHEREx over a patch of sky (each visit is many photos, added up into one
picture). A **detector** is one of SPHEREx's six infrared cameras.

---

# The form, field by field

Each paragraph below is one line in this file, so that it pastes without broken lines. The headings in capitals
inside field 5 are plain text, in case the form does not read Markdown.

## 1. Project Name

SPHEREx sky-change viewer

## 2. High-Level Project Summary

For ten years NASA's NEOWISE telescope looked at the whole sky in infrared light about twice a year, so it could see what changed. It stopped in August 2024. NASA's SPHEREx telescope now photographs the whole sky in infrared light again and again. Our web tool lets anyone type a star's name or a position and watch the real SPHEREx pictures of that patch of sky play like a short film, as the challenge asks, and it searches the pictures for things that moved or changed. Every result is written twice: in plain words for anyone, and with the numbers for scientists.

We tested it on the challenge's five targets. It measures Barnard's Star moving 10.4 arcseconds between August 2025 and August 2026; the Gaia catalogue predicts 10.3. Our first sweep of the Milky Way's plane found two known novae by itself, and three infrared sources that SPHEREx could not detect in its pictures of July to September 2025 and saw much brighter in 2026. We found these three in no catalogue or report we checked. They are candidates: nobody has confirmed them.

## 3. Link to Project Demo

**[TO FILL IN]** The form asks for a 7-slide presentation or a video of 30 seconds or less, at a public link that needs no sign-in. The 7-slide deck exists (`docs/pitch/`, two versions of 7 slides each) and is not uploaded anywhere public yet. Upload the final one (Google Drive with "Anyone with the link", or this repository) and paste its link here. If AI wrote the slides' text or voiced a video, say so on the last slide or in the video's description: the form asks for that.

## 4. Link to Final Project

https://spherex-sky-change-viewer.onrender.com

(The code, if the form has room for a second link: https://github.com/tatsatshah05/Ampersand-NASA)

## 5. Detailed Project Description

WHAT IT DOES

SPHEREx sky-change viewer is a public website: https://spherex-sky-change-viewer.onrender.com. Type a star's name or a position (right ascension and declination), and it shows NASA SPHEREx's real infrared pictures of that patch of sky, one picture per visit, played like a short film. A visit is one pass of SPHEREx over the patch; SPHEREx comes back about every six months. Anything that moved or changed between visits stands out. The site opens on a source that appeared between two visits, blinking between the picture without it and the picture with it.

It has ten features, which stay in view on every screen:

- Watch: play, pause, step, blink and zoom. Beside the picture, one sentence says what happened and one table lists every visit. For a moving star it gives the measured shift and what the Gaia catalogue predicts.
- Brightness and Colours: how bright the object was at each visit, and in each colour of infrared light that SPHEREx sees (102 colours, from 0.75 to 5 micrometres).
- Find changes: a search of the patch for anything that moved or changed. Every find is checked against five star catalogues and against the faults we found in SPHEREx data.
- Far-off planet: a search for a distant world such as Planet X, by the jump it would make between visits.
- Asteroids: the known asteroids and comets that NASA/JPL predicts in the patch.
- What is it?: what the catalogues know about any star you press.
- Practise: real pictures with one made-up moving object, marked SIMULATION, to learn what a mover looks like.
- Observe anomalies: everything our searches saw change, for people to look at and vote on. Type any place to have it searched and kept under watch.
- Three tools: three more ways to look for hidden worlds, each tested on a world that astronomers already know.

Every result is written twice: Beginner, in plain words, and Expert, with the numbers. A "Demo mode" button gives a guided tour of the whole site.

HOW IT WORKS

1. It finds where the star is today. Stars move: Barnard's Star has moved 4.5 arcminutes since 2000. Positions and motions come from ESA's Gaia catalogue and the SIMBAD database.
2. It asks NASA's archive (IRSA) for every SPHEREx photo of that place, and fetches only the small patch it needs, never the whole 65 MB file.
3. It cleans each photo (it removes the glow of dust in the Solar System and the pixels marked as bad) and lines it up with north at the top.
4. It adds up each visit's photos from one detector into one deeper picture. This matters: in a single SPHEREx photo the colour of light changes across the image, so two single photos differ in colour, not only in time. Adding up a visit removes that, and shows fainter objects.
5. It draws every visit on one brightness scale, so a change on screen is a change in the data.
6. It measures the object: where it is, how strongly it is detected, and how that compares with the catalogue.

WHAT WE TESTED AND FOUND

The challenge's five targets, on real SPHEREx data:

- Barnard's Star moved 10.4 arcseconds between August 2025 and August 2026. Gaia predicts 10.3.
- Epsilon Indi B shows in all six detectors and moves 6.3 arcseconds between April 2025 and October 2026, on the catalogue's track.
- WISE 0855 shows only at the longest wavelengths, 3.8 to 5.0 micrometres, once each visit's photos are added up. Our independent check measures it moving 8.4 arcseconds west in a year (give or take 0.4); the catalogue predicts 8.0.
- RW Aurigae became about 1.6 times as bright at 0.75 to 1.1 micrometres between September 2025 and September 2026, and about half as bright at 3.9 to 5 micrometres. Ground observers (AAVSO) saw it brighten 1.7 times.
- R Draconis overexposes every photo, so the tool gives no brightness for it. The light in a ring just around the star rises and falls by 2 to 3 times, in step with the 246-day cycle that AAVSO observers record. That is a relative measure, not a brightness.

Planet X. Our search found no candidate in any patch it searched. To test it we planted made-up objects in real pictures: it found 177 of the 205 that were bright enough. Our limits are not deeper than earlier searches, so this does not rule Planet X in or out.

A sweep of the Milky Way's plane. We compared 1,162,894 sources over 472.6 square degrees between three SPHEREx visits. The sweep was not told where anything was. It found two known novae by itself, and it was left with three sources that it could not explain. Four independent AI reviewers attacked each one, each with its own code on the real data, and a referee ruled on what may be said. These are the three sentences, word for word:

- Candidate A, an infrared source in Sagittarius, was too faint to detect in SPHEREx images from late August and early September 2025 and was more than 100 times brighter by late March 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.
- Candidate B, an infrared source in Scorpius, was too faint to detect in SPHEREx images from August and September 2025, had appeared by late February 2026 and was at least 250 times brighter by August 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.
- Candidate C, an infrared source in Norma, was too faint to detect in SPHEREx images from July and August 2025, was at least 30 times brighter in late February and early March 2026 and had faded again by August 2026; its light hints at a nova hidden behind the Milky Way's dust, but it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.

We checked more than 30 public catalogues and alert lists for each one and found no earlier report. A person must still finish those searches, and an astronomer must check the numbers, so we have reported them to no one yet. Nothing in this project is called a discovery.

BENEFITS

- Anyone can watch the infrared sky change in real NASA data, with no download, no account and no code.
- It says plainly what it cannot do. It marks overexposed pixels, says when an object is not seen, labels every simulation, and calls an unexplained source a candidate.
- Citizen scientists get a list of unexplained changes to look at, and can put any patch of sky under watch: the tool searches it again when NASA's archive has more pictures of it.
- Scientists get the numbers, files to download, and a web address for every view.

WHAT WE HOPE TO ACHIEVE

NASA's NEOWISE telescope watched the infrared sky change for ten years, and stopped in August 2024. SPHEREx can carry that on. We hope people use this tool on SPHEREx as they used WiseView on the WISE pictures, and that astronomers check the three candidates. SPHEREx's next visits, about February to April 2027, will show how each one has changed.

TOOLS

Backend: Python, FastAPI, Astropy, reproject, NumPy, SciPy, Pillow, requests. Website: TypeScript, React, Vite, Aladin Lite. Checks: pytest, Vitest and browser checks with Playwright, about 1,400 automated tests, many of them on real SPHEREx pictures. Hosting: Docker on Render, one small server (1 CPU, 2 GB). No special hardware: we worked on laptops. AI: Anthropic's Claude, working in Claude Code, wrote most of the code and drafted our write-ups under our direction, and AI reviewers checked the main claims; the README says so. Code and every write-up: https://github.com/tatsatshah05/Ampersand-NASA

## 6. Use of Super Intelligence (SI)

Yes.

The tool: Anthropic's Claude, a large language model, working as a coding agent in Claude Code. **[TO CONFIRM: add any other AI tool that a teammate used, and what for.]**

How we used it:

- Code. AI agents wrote most of the code: the Python backend, the React website and the automated tests. The team set the goal and the rules (real data only; an unexplained source is a candidate, never a discovery), chose what to build and in what order, looked at the results on real data, and decided what to keep.
- Words. AI drafted the write-ups in the repository, the words on the website and the text of this project page. The team checked them.
- Checking. Before we kept a scientific claim, separate AI sessions, each with its own code, measured it again from the real data and tried to find an ordinary explanation. This covered the three candidates (four reviewers each, then a referee who ruled on what may be said), the three methods on the "Three tools" screen, and four of the five test targets. Claims were withdrawn or corrected as a result. Two examples: the sweep's first description of its three candidates was withdrawn, because the reviewers showed that its 2025 brightness values for two of them were the light of neighbouring stars; and "RW Aurigae became 2.5 times brighter" was corrected, because it compared a dip of a few days with a normal state.
- Searching. AI agents searched public catalogues and alert lists for earlier reports of the three candidates. They sent nothing to anyone.
- Ideas. The way we answer the challenge follows the challenge statement: add up each visit's pictures, play the visits as a short film, and test on the five targets. **[TO CONFIRM by the team, and correct if it is not how it went:]** The team asked for searches that could find something not yet catalogued. AI agents proposed and built the methods for that (the sweep of the Milky Way's plane, and the three methods on the "Three tools" screen), and the team decided what to keep and what to show.

What is not AI-generated:

- No picture, video or sound in the tool was made by an AI image, video or audio model. Every picture of the sky is real SPHEREx data. The drawing in "What is it?" is drawn by our code from the catalogues' numbers and is labelled "Illustration drawn from measurements. Not a photograph." The made-up object of the practice round is added by our code and is marked SIMULATION in every picture.
- We generated no NASA logo, flag or mission identifier.

Where the project says so: the repository's README has a section "Use of AI", the web page's metadata names it, and the Detailed Project Description says it under TOOLS and where the AI reviewers are mentioned. **[TO CONFIRM: say the same for the slides or the video if AI wrote or voiced any of it.]**

## 7. NASA Data

NASA's SPHEREx mission is the heart of the project. Every picture the tool shows comes from it.

- SPHEREx Level 2 spectral images (NASA/JPL-Caltech), Data Release 1 (doi:10.26131/IRSA678) and Quick Release 3 (doi:10.26131/IRSA662): every picture, brightness and spectrum in the tool. For one test we also used SPHEREx's deep-field images.
- NASA/IPAC Infrared Science Archive (IRSA): its image search (SIA2) lists every SPHEREx photo of a place, and its cutout service sends only the patch we need.
- NASA's public copy of the SPHEREx archive on Amazon Web Services (bucket nasa-irsa-spherex, AWS Open Data): the same files, read a few rows at a time, about six times faster.
- The SPHEREx Explanatory Supplement, the IRSA SPHEREx tutorials (notebooks) and the SPHEREx archive user guide: how to read the files, which marked pixels to leave out, and how to measure brightness.
- Catalogues at IRSA, to check every change we find: NEOWISE single exposures (a second opinion on brightness changes, 2014 to 2024), AllWISE, CatWISE2020, 2MASS and Spitzer GLIMPSE.
- NASA/JPL Solar System Dynamics: the Small-Body Identification API (the known asteroids and comets in a patch) and Horizons (the place of the dwarf planet Eris).
- WiseView and Backyard Worlds: Planet 9, the NASA-funded citizen science project that the challenge names: the model for our viewer.
- For the search for earlier reports of our three candidates: NASA's Astrophysics Data System (a first search only), and the nova lists and the Swift/BAT transient monitor at NASA's Goddard Space Flight Center.
- The SPHEREx All Sky Map 2025 (NASA/JPL-Caltech; SPHEREx at Caltech), as the background of our slides.

## 8. Space Agency Partner Data and Other References

SPACE AGENCY PARTNER DATA

- ESA (European Space Agency), Gaia Data Release 3: the position, motion and distance of the stars. It tells the tool where a star is today, it marks the known stars on each picture, and it is the prediction we compare our measurements with (Barnard's Star: 10.4 arcseconds measured, 10.3 predicted). Read from ESA's Gaia Archive, and from copies at Harvard (VizieR) and IRSA when ESA's server did not answer.
- ESA, Herschel Hi-GAL catalogue of cold dust clumps: used when checking Candidate C.
- JAXA and RIKEN, MAXI nova alerts and flash reports: searched for earlier reports of our candidates.

OTHER DATA

- SIMBAD and VizieR (CDS, Strasbourg; mirrors at Harvard): names, object types and catalogues.
- AAVSO: the International Variable Star Index, and observers' brightness records of RW Aurigae and R Draconis.
- Aladin Lite and HiPS sky images (CDS): the same patch in AllWISE, 2MASS and DSS2.
- VVV / VIRAC2, the Transient Name Server, The Astronomer's Telegram, CBAT, ASAS-SN, and the ZTF alert brokers ALeRCE, ANTARES and Fink: searched for earlier reports of the candidates.

PAPERS

- SPHEREx and its data: Bock et al. 2026; Akeson et al. 2026.
- Gaia DR3: Gaia Collaboration, Vallenari et al. 2023.
- WISE 0855's motion: Kirkpatrick et al. 2021.
- WiseView: Caselden et al. 2018. Backyard Worlds: Kuchner et al. 2017.
- SPHEREx and objects that change: Karambelkar et al. 2026 (arXiv:2602.07129); Astronomer's Telegrams 17601 and 18127 (nova V572 Velorum).
- Finding a distant body's distance from a short arc, and adding up pictures along a path: Bernstein and Khushalani 2000; Rice and Laughlin 2020.
- WASP-62 b: Hellier et al. 2012; Kokori et al. 2023.
- The full list, with every catalogue and every search: docs/sources.md in our repository.

SOFTWARE

Python, FastAPI, Uvicorn, Astropy, NumPy, SciPy, reproject, Pillow, requests; TypeScript, React, Vite, Vitest, oxlint, Aladin Lite; pytest, ruff, mypy, Playwright; Docker, Render, GitHub. AI: Anthropic's Claude, in Claude Code.

ACKNOWLEDGEMENTS

This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.

This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National Aeronautics and Space Administration and operated by the California Institute of Technology.

This work has made use of data from the European Space Agency (ESA) mission Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC, https://www.cosmos.esa.int/web/gaia/dpac/consortium).

---

# Longer text

More detail than the form needs, kept for the team and for anyone who asks.

## Project name

SPHEREx sky-change viewer (Team Ampersand)

## One-line summary

A public web tool that searches NASA SPHEREx's repeat infrared pictures of the sky for change, and shows anyone
the before and the after.

## Short description (about 130 words)

For ten years NASA's NEOWISE telescope looked at the whole sky in infrared light about twice a year, so it could
see what changed. It stopped in August 2024. NASA's SPHEREx telescope now photographs the whole sky in infrared
light again and again. Our web tool shows anyone the real SPHEREx pictures of any patch of sky, like a short
film, and searches them for things that moved or changed. It measures Barnard's Star moving 10.4 arcseconds in a
year; the Gaia catalogue predicts 10.3. Our first sweep of the Milky Way's plane found two known novae by itself,
and three infrared sources that SPHEREx could not detect in its pictures of July to September 2025 and saw much
brighter in 2026. We found these three in no catalogue or report we checked. They are candidates: nobody has
confirmed them.

## Full description

### What it is, and what sets it apart

From 2014 to August 2024, NASA's NEOWISE telescope looked at the whole sky in infrared light about twice a year.
Dust in the Milky Way blocks visible light, so a star that erupts behind the dust can be missed by ordinary
telescopes; in infrared light it can still be seen. NEOWISE has stopped. NASA's SPHEREx telescope now
photographs the whole sky in infrared light about every six months, in 102 colours from 0.75 to 5 micrometres.

What sets our tool apart: it searches SPHEREx's repeat pictures for change without being told where to look,
and it shows anyone the before and the after. Others have used SPHEREx to study objects that change: Karambelkar
and colleagues (2026) measured SPHEREx spectra of eight transients that NEOWISE had found (novae and outbursts
of young stars), and other astronomers reported SPHEREx observations of the nova V572 Velorum (Astronomer's
Telegrams 17601 and 18127). When we searched arXiv on 15 November 2026 (SPHEREx with transient, outburst, nova
and variability), that was the only paper about SPHEREx and transients that we found
(`docs/sweep/vetting/B/reports/searches_B.tsv`, `docs/novae.md`).

Our tool does three things with SPHEREx's pictures:

1. It **shows** them. Type a star's name or a position, and the real pictures of that patch play one visit after
   another, like a short film. Anything that moved or changed stands out.
2. It **searches** them for change, without being told what to look for, and checks every change it finds
   against star catalogues and against the faults we found in SPHEREx data.
3. It **explains** every result in plain words, at two levels: Beginner, for anyone, and Expert, for
   scientists. A switch at the bottom right of every screen changes between them.

The tool opens on a source that appeared between two SPHEREx visits, blinking between the picture without it
and the picture with it.

### The three candidates from our sweep of the Milky Way's plane

We ran the project's sweep over 472.6 square degrees of the Milky Way's plane, the part around the centre of
our Galaxy (63 patches; 1,162,894 sources compared between three SPHEREx visits: about July to September
2025, February to April 2026, and July to September 2026). The sweep was not told where anything was. It found
two known novae, V7994 Sagittarii and V0691 Serpentis, by itself. It was left with three sources that it could not
explain. Four independent reviewers attacked each one, and a referee ruled. The referee allowed one sentence
about each for a public page. Here they are, word for word:

> Candidate A, an infrared source in Sagittarius, was too faint to detect in SPHEREx images from late August and
> early September 2025 and was more than 100 times brighter by late March 2026; it is a candidate that we found
> in no catalogue or report we checked, and nobody has confirmed it yet.

> Candidate B, an infrared source in Scorpius, was too faint to detect in SPHEREx images from August and
> September 2025, had appeared by late February 2026 and was at least 250 times brighter by August 2026; it is a
> candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.

> Candidate C, an infrared source in Norma, was too faint to detect in SPHEREx images from July and August 2025,
> was at least 30 times brighter in late February and early March 2026 and had faded again by August 2026; its
> light hints at a nova hidden behind the Milky Way's dust, but it is a candidate that we found in no catalogue
> or report we checked, and nobody has confirmed it yet.

What "candidate" means here: a real source, seen in many photos and in more than one detector, at one fixed
place on the sky, that we found in no catalogue or report we checked. Nobody has confirmed any of the three.
Nobody knows yet what any of them is.

**Searches for earlier reports.** In two rounds of searches, one for the ruling and a wider one after it, we
checked more than 30 public catalogues and alert lists for each candidate. We counted a search only if it also
found a known object that it should find, which shows that it worked. A keyword search of the Astronomer's
Telegrams followed. None found an earlier report at any of the three places. Some sources have not been
searched in full: no person has read the telegrams in full yet, NASA's Astrophysics Data System has had only a
first search, and the SIMBAD database at CDS was down. So this does not prove that no one else has seen them.
Every search, with its date and its test object, is in `docs/sweep/searches-for-earlier-reports.md`.

**Nothing has been reported yet.** We have sent no report to anyone. A person must first finish the checklist in
that file, and a professional astronomer must check the numbers. Draft texts are ready, and not sent.

**What would confirm them.** A spectrum from a larger telescope, in near-infrared light. It would show broad
lines of hydrogen and helium for a nova, or narrow lines and carbon monoxide for a young star. All three are
close to the Sun in our sky now, so this becomes practical from about mid-January (C), late January (B) and
mid-February 2027 (A). SPHEREx's next visits, about February to April 2027, will show how each one changes. For
C, an X-ray observation would also help.

All the evidence, and what the sweep's first description of the three got wrong, is in `docs/sweep.md` and
`docs/sweep/vetting/`.

### How it answers the challenge

The challenge asks for a public web tool that shows SPHEREx pictures of a patch of sky over time, so that anyone
can see what moves or changes. It names five test targets, and Planet X.

**The five test targets** (measured on real SPHEREx data, `docs/results.md`; WISE 0855, RW Aurigae, R Draconis
and Barnard's Star checked again with separate code, `docs/verification.md`):

- **Barnard's Star**, the fastest-moving star. Three visits, August 2025 to August 2026. The page says: "It moved
  10.4 arcseconds north between August 2025 and August 2026. Gaia's star map predicted 10.3 arcseconds:
  they agree." In detector 5 the measured and predicted places differ by 1.4 arcseconds, under a quarter of one
  SPHEREx pixel. The star's centre is overexposed, so its place is good to about 1 arcsecond.
- **Epsilon Indi B**, a pair of brown dwarfs seen as one point. It shows in all six detectors and moves 6.3
  arcseconds to the south-east between April 2025 and October 2026, on the catalogue's track (detector 5: 5.0
  east and 3.8 south measured; 5.1 east and 3.7 south predicted). Its bright partner star, Epsilon Indi A, is
  6.7 arcminutes away; in a wider view it is seen to move the same way (not measured; `docs/results.md`).
- **WISE 0855-0714**, a very cold brown dwarf. It shows only at the longest wavelengths, 3.8 to 5.0 micrometres
  (detectors 5 and 6), in each visit's added-up picture. In detector 6 it stands 3.4 times the background
  scatter in the first visit (only three photos: marginal), then 14.6 and 11.2 times. The independent check, with
  a neighbouring star removed, measures it moving 8.4 arcseconds west in a year (give or take 0.4), where the
  catalogue predicts 8.0. By the third visit that ordinary star, 4 arcseconds away, gives about a quarter of the
  light at 4.4 to 5 micrometres, and SPHEREx cannot separate the two.
- **RW Aurigae**, a young variable star. Between September 2025 and September 2026 it became about 1.6 times as
  bright at 0.75 to 1.1 micrometres in SPHEREx's pictures, as the page shows, and about half as bright at 3.9 to
  5 micrometres. Ground observers (AAVSO) saw it brighten 1.7 times from one September to the next. Our September
  2025 photos fell in a dip that lasted a few days, so at 0.75 to 0.84 micrometres alone the factor is 2.0 to 2.6.
  The fading at 3.9 to 5 micrometres has no outside check. RW Aurigae is a close pair that SPHEREx measures as one.
- **R Draconis**, a bright long-period variable star. It overexposes the detectors in every photo, so no
  brightness can be given. Over three visits, the light in a ring just around the star, in detectors 5 and 6,
  rises and falls by a factor of about 2 to 3, in step with the 246-day cycle that AAVSO observers record and a
  few weeks behind it. The same measure on Barnard's Star, which does not vary, stays flat to about 5 per cent.
  It is a relative measure, not a brightness.

**Planet X.** A planet far beyond Neptune does not creep across the picture. It jumps between visits, because
SPHEREx sees it from opposite sides of the Earth's path round the Sun, and the size of the jump gives its
distance. The tool's **Far-off planet** search (Expert: **Planet X search**) looks for exactly that jump
(`docs/distant.md`):

- What was searched: patches of sky that people chose, up to 0.5 degrees across, in detectors 5 and 6. Not the
  whole sky.
- What it found: no candidate in any patch searched, and nothing when the same search is run with the Earth's
  motion reversed (a test of chance links).
- How we know it works: made-up objects planted in real pictures were found 177 times out of the 205 that were
  bright enough in three visits, with the distance right to about a per cent.
- The honest limit: around WISE 0855, an object brighter than about 0.2 millijanskys, between 1,000 and 30,000
  times the Earth-Sun distance, would have been found if it lay in the part of the picture the search can use:
  a fifth of it at 1,000 times that distance, about two thirds at 30,000. That is not deeper than earlier
  searches of WISE data. It is no new limit on Planet Nine, and it does not rule Planet X in or out.

A second method, **Follow the bend**, measures the distance of a far-off world from one visit. It found the
dwarf planet Eris in a patch centred on Eris (see "Three tools, three known worlds"). It cannot test Planet
Nine: such a planet is expected to look several times fainter than the faintest thing it can see.

### What a visitor can do

A list of the features stays in view on every screen (down the left edge of a wide window, along the top of a
narrow one), in this order. Each item has a Beginner name and an Expert name. A "Demo mode" button at the top
right starts a guided tour of 24 steps. The **Beginner | Expert** switch sits at the bottom right. In Beginner every tool is written in
plain words; Expert adds the numbers, the detector and the settings.

1. **Watch** (Expert: **Viewer**). The real pictures of the patch, one per visit, played like a short film:
   Play, Pause, step, "Blink before and after" (or "Blink first and last"), speed, zoom and drag. North is up.
   A row of buttons opens Candidate A, B and C, the five test targets, a young star in Serpens South and two
   novae of 2025; the search box takes a name or a position. Beside the picture, one sentence describes the
   whole run and one table lists every visit. These words hold still while the pictures play. For a moving star
   the side column gives the measured shift and the catalogue's prediction. Expert adds the detector (D1 to
   D6), the field of view (0.05 to 0.5 degrees), three modes (Normal, Difference, Sum), motion markers,
   predicted positions, pixels, flags, and two folds, Catalogue notes and Visit details.
2. **Brightness** (Expert: **Light curve**). How bright the object was in each visit, compared only in the
   same colour of infrared light, with a plain verdict (brighter, fainter, or too few to say).
3. **Colours** (Expert: **Spectrum**). How bright the object is in each colour that SPHEREx sees, one dot per
   photo, with the numbers to download.
4. **Find changes** (Expert: **Blind search**). A search of the patch for anything that moved or changed
   between visits. Every change is measured against hundreds of empty places in the same picture, tested for
   known faults, and checked against five catalogues.
5. **Far-off planet** (Expert: **Planet X search**). The search for a distant world, described above. Expert
   can also try it on a planted object, marked as a simulation.
6. **Asteroids** (Expert: **Small bodies**). The known asteroids and comets that NASA/JPL predicts in the patch,
   and what each photo shows at that place.
7. **What is it?** (Expert: **Object card**). What the Gaia DR3 and SIMBAD catalogues know about the object at
   the centre, and a drawing of it made from the catalogues' numbers: the colour of a glowing body at Gaia's
   temperature for it, and its size to scale with the Sun. The drawing is labelled "Illustration drawn from
   measurements. Not a photograph." The same patch in older surveys (WISE, 2MASS, DSS) is shown below it.
   While What is it? is open, pressing any star in the picture asks the catalogues about that star, and its
   card offers "Look at this one", which makes it the star the page follows.
8. **Practise** (Expert: **Training**). Real SPHEREx pictures with one made-up moving object added, to learn
   what a mover looks like. A banner that cannot be closed and the word SIMULATION in every picture say that
   it is practice. The same made-up object is used in one other place a visitor can open: the planted run of
   the Planet X search, in Expert, which is also marked as a simulation. To test that search we also planted
   made-up objects in real pictures and counted how many it found (the 177 of 205 above). Everything else is
   real data: SPHEREx's pictures, and the catalogues and older surveys they are compared with.
9. **Observe anomalies** (Expert: **Anomalies**). Everything our searches saw change, for people to look at.
   It first says what SPHEREx is and what an anomaly is. Then comes a group headed "Not reported anywhere we
   could find": Candidates A, B and C, each with two real SPHEREx pictures ("Not seen" and "At its brightest";
   Expert: "Last visit not detected" and "Brightest visit"), a line saying which star nearby (for C, the crowd
   around it) is not the candidate, its allowed sentence, what it probably is, the sentence about the search
   for earlier reports ("Has anyone reported it?"; Expert: "Search for earlier reports"), its status ("Not
   confirmed. Not yet reported to astronomers.") and a link "Watch it appear". Expert puts the position, brightness, rise and dates right
   under the pictures. Above the candidates, "Pick a patch of sky": type a star's name or coordinates and press "Watch this patch" to have
   that patch searched and kept under watch (it is searched again when NASA's archive has new pictures of it), or
   choose from the menu: everywhere, the Milky Way's plane, or each searched patch by its
   constellation, each with how many were found, and a "Show everywhere" button once a region is chosen.
   Below that, the chosen region's groups. From the patch searches ("Found by searching small patches", or
   "Found by searching this patch"): "Not listed as changing", "Already known" and "Set aside as false
   alarms" (Expert: "Needs eyes", "Already known", "Set aside as artefacts"), with votes. From the sweep of
   the plane, its 14 survivors in four groups: "Candidates", "Known novae", "Known stars that change" and "Set
   aside after a closer look" (Expert: "Candidates", "Known eruptions (novae)", "Catalogued stars that varied",
   "Set aside after a closer look"). A vote is an opinion, not a confirmation, and it never changes the
   machine's order. Scientists can download the whole list as a CSV file.
10. **Three tools** (Expert: **Methods**). Three ways to learn about hidden worlds, each tested on a world that
    astronomers already know, on a screen of its own (below).

### Three tools, three known worlds

Each method was built on SPHEREx data and then attacked by independent reviewers. Each was tested on a known
world, so its answer can be checked. We do not know of these ideas having been used on real SPHEREx data
before (we searched published papers, preprints and telegrams); the ideas themselves are old and have been used
with other telescopes. The screen states each verdict at the top.

- **Follow the bend** (`docs/reflex.md`). It adds up all the photos of one 15-day visit along paths that
  include the curve the Earth's motion puts in the path of a distant body. Verdict on the screen: "Found its
  test world. Distance only rough." In a patch centred on the dwarf planet Eris it found Eris about 1 to 2
  arcseconds from where JPL puts it. The bend in its path gives a distance of about 110 to 120 times the
  Earth-Sun distance, where JPL gives 95.5; the honest range is roughly 90 to 145, and at 95 per cent confidence
  the range has no upper end. This is a known-answer test on one known world: the patch was centred on Eris, and the method's
  settings were chosen after an earlier look had found it.
- **Line up the dips** (`docs/transits.md`). SPHEREx photographs some stars thousands of times; this method
  lines up one star's readings (484 usable ones for WASP-62) on a known planet's published timetable. Verdict on the screen: "Showed one known planet's dip. Mixed on a second." For the hot
  Jupiter WASP-62 b, in one detector, the star dims by about 1.1 to 1.2 per cent at the right times, against a
  published 1.2; none of 598 wrong timetables gave a dip as deep. It is a re-measurement of a known planet in
  one detector, not a blind test: the method was developed on the same readings. A second known planet, WASP-100
  b, showed the dip in that detector and not in another.
- **Off-centre in red** (`docs/colourwalk.md`). It asks whether a faint red partner pulls its star's image
  centre sideways in redder light. Verdict on the screen: "Not proven yet". On the one known partner tried,
  VHS 1256 b, the centre moved about 0.18 arcseconds toward the partner, but that is only about 2 times our
  usual error once the instrument's own offsets are counted; our rule, set before the test, asks for 4. The
  method was developed on this star, it failed two of its seven pre-set checks and its null test, and it has
  found nothing.

### What we do not claim

- **No discovery and no new planet.** Nothing in this project is called a discovery, a first, or a new planet.
- **The three sweep sources are candidates.** We found them in no catalogue or report we checked. Nobody has
  confirmed them, and what they are is not known. We have reported them to no one yet.
- **Planet X and Planet Nine.** We did not find them, and we do not rule them out. Our limits are not deeper
  than earlier searches.
- **The three methods** were tested on worlds that were already known. None of them has found anything new.
- **The candidates of the blind searches** in other patches (for example a young star in Serpens South that came
  back from a deep dip) are not listed as variable in the catalogues we asked, and specialists very likely know
  them (`docs/search.md`).
- **Nova V572 Velorum**: the dust we measured in it was already reported by others (ATel 18127). Our measurement
  is an independent one (`docs/novae.md`).
- **The practice object** is made up, and so is the object of the Planet X search's planted run. Both are
  marked as a simulation everywhere they appear.

### Limits, stated plainly

- SPHEREx pixels are 6.15 arcseconds across. Two objects closer than that blur into one, and even the fastest
  stars move only one to three pixels between visits.
- Most patches have only three or four visits so far, so each "film" is three or four pictures long.
- Very bright stars overexpose the detectors. The tool marks those pixels and does not give a brightness it
  cannot measure.
- The sweep of the Milky Way looked only for sources brighter than 30 millijanskys at 4.4 to 5.0 micrometres
  that changed by at least ten times, in one detector and three visits. It covered 472.6 square degrees, not the
  whole plane (`docs/sweep.md`, "Limits").
- The searches cover only the patches someone has searched. They are not a survey of the sky.
- The first time anyone asks for a new position, the tool reads the pictures from NASA's archive: about 15
  seconds when NASA's public copy on Amazon answers, about a minute otherwise. After that the position loads at
  once. A new search of a patch takes from under a minute to a few minutes.
- Some outside services (the SIMBAD database, the Aladin sky atlas, Gaia's own server) were down for hours on
  14 and 15 November 2026. When one is down, the page says so and the rest still works.
- The faults our own tests found, and what is still open, are in `docs/results.md`, `docs/verification.md` and
  each write-up's "Limits".

### How we compare with existing tools

WiseView, from the Backyard Worlds project, shows the older WISE pictures in the same way, and was our model.
SPHEREx adds colour: every point of the sky is measured in 102 colours from 0.75 to 5 micrometres. Our tool adds
a search for change, checks against catalogues, and plain words for every result.

### How we built it

- Backend: Python, FastAPI, astropy, reproject, numpy, scipy. It fetches only the small part of each picture it
  needs, from NASA's public copy of the archive on Amazon S3, with the archive's own cutout service at IRSA as
  the fallback, and keeps everything it fetches on disk.
- Each visit's photos are added up into one deeper picture, on one brightness scale for every visit, so a
  change on screen is a change in the data.
- Frontend: React and TypeScript, built with Vite; Aladin Lite for the older surveys.
- No accounts and no API keys. The only stored list is the vote list, one file on the server.
- Checks: Python and TypeScript tests that use real SPHEREx pictures and no network, and browser checks that
  guard the page (`scripts/checks/`): the words hold still while the pictures play, and the bar and the switch
  work at both levels.
- Code: https://github.com/tatsatshah05/Ampersand-NASA
- Public web address: https://spherex-sky-change-viewer.onrender.com (deployed on 2026-11-15 on Render; always on).

### Use of AI tools

**[TO CONFIRM by the team: the paragraph below is what the project's records show. Check that it is complete
and in the team's own words before pasting.]**

AI agents (Anthropic's Claude, working in Claude Code) wrote most of the code and drafted the write-ups, under
the team's direction. The main scientific claims were attacked by independent AI reviewers before we kept them:
the sweep's three candidates (four reviewers each, then a referee who ruled on what may be said), the three
methods, and four of the five test targets (`docs/verification.md`). Separate AI sessions, each with its own
code, re-measured those results from the real data, searched the catalogues and the literature, and tried to
find an ordinary explanation. The write-ups of the other results (Epsilon Indi B, the Planet X search, the blind
searches, the novae) record no separate review. Claims were withdrawn or corrected as a result. Two examples:

- **The sweep's first description of its three candidates was withdrawn.** The reviewers showed that its 2025
  brightness values for A and B were the light of neighbouring steady stars, that two of its positions were 3
  arcseconds off, that its named "counterparts" were other stars, and that C's bright readings fell on emission
  lines (`docs/sweep.md`, "What the sweep's first write-up got wrong").
- **RW Aurigae's change was corrected.** An earlier figure, "2.5 times brighter", compared a dip of a few days
  with a normal state. From one September to the next, ground observers (AAVSO) found about 1.7 times
  (`docs/verification.md`, section 2).

The rule for the whole project: real data only, nothing simulated except the clearly marked made-up object of
the practice round and of the Planet X search's planted run, and anything unexplained is a candidate, never a
discovery.

## Data and credits

- **SPHEREx images:** NASA/JPL-Caltech SPHEREx.
- **Archive and cutout service:** NASA/IPAC Infrared Science Archive (IRSA); images also read from NASA's public
  Amazon S3 copy of the archive.
- **Star positions and motions:** ESA Gaia DR3 (European Space Agency, Gaia mission, processed by the Gaia Data
  Processing and Analysis Consortium).
- **Names and object types:** the SIMBAD database, operated at CDS, Strasbourg, France.
- **Catalogues for the searches:** Gaia DR3, SIMBAD, AAVSO's International Variable Star Index, CatWISE2020,
  AllWISE, 2MASS and Spitzer GLIMPSE (NASA/IPAC IRSA).
- **Second opinion on brightness changes:** NEOWISE single-exposure measurements (NASA/IPAC IRSA).
- **Known asteroids and comets, and Eris's place:** NASA/JPL Solar System Dynamics (Small-Body Identification API
  and Horizons).
- **Ground-based brightness records for RW Aurigae and R Draconis:** AAVSO observers.
- **Older surveys around a patch:** Aladin Lite (CDS, Strasbourg).
- **Inspiration:** WiseView and the Backyard Worlds: Planet 9 citizen science project.
- **Challenge:** NASA Space Apps 2026, "Planet X and SPHEREx".

Suggested credit line for the page footer and the video:

> Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive (IRSA); ESA Gaia DR3.

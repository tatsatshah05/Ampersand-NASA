# Form copy sheet

Every answer for the Space Apps project form, each in its own box. On GitHub, point at a box and press the copy button at its right end, then paste into the form. Made by `scripts/make_form_copy_sheet.py` from [project-page.md](project-page.md): change that file and run the script, not this one. The same sheet as one page with a button on every value: [form-copy-sheet.html](form-copy-sheet.html) (download it and open it in a browser).

## Text answers

### Project Name

```text
SPHEREx sky-change viewer
```

The site's top bar says Ampersand. Change this name if you want the two to match.

### Summary (1,129 of 1,500 characters, 200 words)

```text
Our sweep of NASA SPHEREx's pictures of the Milky Way turned up three infrared sources that we found in no catalogue or report we checked. SPHEREx could not detect them in mid-2025, and saw them more than 100, at least 250 and at least 30 times brighter in 2026. They are candidates: nobody has confirmed them. The same sweep also found two known novae.

The tool that found them is a public website. Type a star's name or a position, and SPHEREx's real infrared pictures of that patch play like a short film. It also searches them for anything that moved or changed, and writes every result twice: in plain words, and with the numbers for scientists. On the challenge's five targets, it measures Barnard's Star moving 10.4 arcseconds in a year; the Gaia catalogue predicts 10.3.

For Planet X, it looks for the jump a planet far beyond Neptune makes between visits. It found no candidate in 14 patches of sky. Of the made-up objects we planted in real pictures that were bright enough, it found 177 of 205.

NASA's NEOWISE stopped watching the infrared sky change in 2024. With this tool, anyone can watch SPHEREx carry that on.
```

### Project Demo (link)

**Not ready.** Upload the 7-slide deck, or a video of 30 seconds or less, to a public link that needs no sign-in. Then paste that link in the form.

### Project (link)

```text
https://spherex-sky-change-viewer.onrender.com
```

The box takes one link. Keep the website here: the GitHub link goes in Project Details and in the second link list.

### GitHub link

```text
https://github.com/tatsatshah05/Ampersand-NASA
```

Already inside Project Details and the first row of Partner & Other Data. Here for anywhere else you want it.

### Project Details (12,716 characters, 2,258 words)

```text
WHAT IT DOES

SPHEREx sky-change viewer is a public website: https://spherex-sky-change-viewer.onrender.com. Its code and every write-up are public too: https://github.com/tatsatshah05/Ampersand-NASA. Type a star's name or a position (right ascension and declination), and it shows NASA SPHEREx's real infrared pictures of that patch of sky, one picture per visit, played like a short film. A visit is one pass of SPHEREx over the patch; SPHEREx comes back about every six months. Anything that moved or changed between visits stands out. The site opens on a source that appeared between two visits, blinking between the picture without it and the picture with it. That source is one of three that our own sweep turned up and that we found in no catalogue or report we checked. They are candidates, and nobody has confirmed them (see WHAT WE TESTED AND FOUND).

It has ten features, which stay in view on every screen:

- Watch: play, pause, step, blink and zoom. Beside the picture, one sentence says what happened and one table lists every visit. For a moving star it gives the measured shift and what the Gaia catalogue predicts.
- Brightness and Colours: how bright the object was at each visit, and in each colour of infrared light that SPHEREx sees (102 colours, from 0.75 to 5 micrometres).
- Find changes: a search of the patch for anything that moved or changed. Every find is checked against five star catalogues and against the faults we found in SPHEREx data.
- Far-off planet: the Planet X search. A world far beyond Neptune jumps between visits. The search looks for that jump in the patch, and says how bright a world at each distance would have had to be for it to show.
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

Planet X. A planet far beyond Neptune does not creep across the picture. It jumps between visits, because SPHEREx sees it from opposite sides of the Earth's path round the Sun. A world 500 times as far from the Sun as the Earth, where the proposed Planet Nine would be, jumps about 14 arcminutes, nearly half the Moon's width. The size of the jump gives the distance. Our Far-off planet search (Planet X search in Expert) looks for sources that come and go between visits, and links those that one body at one distance explains.

- On the real sky: no candidate in any of the 14 patches searched so far, and nothing when the same search is run with the Earth's motion reversed (a test of chance matches).
- On made-up objects planted in real pictures: it found 177 of the 205 that were bright enough in three visits, with the distance right to about one per cent. In all 539 planted runs it linked nothing except the planted object.
- The honest limit: around WISE 0855, an object brighter than about 0.2 millijanskys at 4 to 5 micrometres, between 1,000 and 30,000 times the Earth-Sun distance, would have been found if it lay in the part of the picture the search can use (a fifth of it at 1,000 times that distance, about two thirds at 30,000). Searches of ten years of WISE pictures go deeper (Luhman 2014; Meisner et al. 2017, 2018). So this is no new limit on Planet Nine, and it does not rule Planet X in or out.
- What it adds: anyone can point the search at a patch, it uses a second telescope and new years (2025 and 2026), and it says plainly what it would have seen. Every new SPHEREx visit adds one more place to check, which makes a chance match less likely.
- Two more things made for Planet X: Practise, where anyone learns to spot a made-up far-off world in real pictures (marked SIMULATION), and Follow the bend on the Three tools screen, which found the dwarf planet Eris in the pictures of one visit, in a patch centred on Eris. That is a test on a known world. It cannot test Planet Nine, which is expected to look several times fainter than the faintest thing that method can see.

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

NASA's NEOWISE telescope watched the infrared sky change for ten years, and stopped in August 2024. SPHEREx can carry that on. We hope people use this tool on SPHEREx as they used WiseView on the WISE pictures, and that astronomers check the three candidates. SPHEREx's next visits, about February to April 2027, will show how each one has changed. Each new visit also makes the Planet X search stronger, and anyone can run it on a patch nobody has searched.

HOW IT IS CREATIVE

- It turns a viewer into a searcher. The pictures that play as a film are also searched: for anything that moved or changed, for the jump of a far-off planet, and, across the Milky Way's plane, for sources that appeared between visits.
- It tests itself on known answers before it claims anything: the five targets, two known novae that the sweep found without being told where they were, made-up objects planted in real pictures, the dwarf planet Eris, and the planet WASP-62 b passing in front of its star.
- It writes every result twice, for a beginner and for a scientist. The words hold still while the pictures play, so the eye stays on the sky.
- It keeps watching. Any patch a visitor chooses is searched again when NASA's archive has new pictures of it.
- A practice round teaches what a moving object looks like, on a made-up one marked SIMULATION.

WHAT WE CONSIDERED

- Honesty before excitement. Real data only. An unexplained source is a candidate, never a discovery. Every simulation and every drawing is labelled. Where the tool cannot measure (an overexposed star, an object that is not seen), it says so.
- How SPHEREx data really behaves. Each photo holds many colours, bright stars overexpose, most marked pixels are not bad pixels, and the faint reflections of very bright stars move between visits and can pass for changes.
- Stars that have moved since their catalogue date, and motions of only one to three pixels between visits. Hence the enlarged picture, the blink between before and after, and the marker at the measured place.
- People who are not astronomers: plain words, no jargon in Beginner, and a guided tour.
- NASA's archive: the tool fetches only small patches, a few at a time, and keeps what it fetched.
- Time: one weekend. Each feature had to work on the five targets before the next was started.

TOOLS

Backend: Python, FastAPI, Astropy, reproject, NumPy, SciPy, Pillow, requests. Website: TypeScript, React, Vite, Aladin Lite. Checks: pytest, Vitest and browser checks with Playwright, about 1,400 automated tests, many of them on real SPHEREx pictures. Hosting: Docker on Render, one small server (1 CPU, 2 GB). No special hardware: we worked on laptops. AI: Anthropic's Claude, in Claude Code (see USE OF AI). Code and every write-up: https://github.com/tatsatshah05/Ampersand-NASA

USE OF AI

We say plainly where AI was used. Anthropic's Claude, a large language model working as a coding agent in Claude Code, wrote most of the code and the tests, and drafted the write-ups, the words on the site and this text. We set the goal and the rules, chose what to build, looked at the results on real data, and decided what to keep. Before we kept a scientific claim, separate AI sessions measured it again with their own code and tried to find an ordinary explanation; claims were withdrawn or corrected as a result. AI agents also proposed and built the methods of the extra searches that we asked for (the sweep of the Milky Way's plane, and the three methods on the Three tools screen). No picture, video or sound was made by AI: every picture of the sky is real SPHEREx data, the one drawing is labelled as a drawing, and the made-up practice object is marked SIMULATION. The repository's README and the site's metadata say the same.

DATA CREDITS

SPHEREx images: NASA/JPL-Caltech, served by the NASA/IPAC Infrared Science Archive (IRSA). Star positions and motions: ESA Gaia DR3. Names: SIMBAD (CDS, Strasbourg). Every other source is in the two lists of links below.
```

**Confirm one sentence before pasting.** In USE OF AI: "AI agents also proposed and built the methods of the extra searches that we asked for". Correct it if that is not how it went.

### Use of Super Intelligence (SI)

**Options to tick, nothing to paste.** Tick every option that covers writing code, writing or editing text, and analysing data or research. Tick slides or presentations if AI wrote the deck's words. Do not tick images, video or audio unless the deck or the video has any. Do not tick "I did not use SI".

## NASA Data (22 rows)

Each row is one "Add New Link": the first box is Link Text, the second is Link Url.

**1.**

```text
SPHEREx Level 2 spectral images, Data Release 1 (NASA/JPL-Caltech, IRSA)
```

```text
https://doi.org/10.26131/IRSA678
```

**2.**

```text
SPHEREx Level 2 spectral images, Quick Release 3 (NASA/JPL-Caltech, IRSA)
```

```text
https://doi.org/10.26131/IRSA662
```

**3.**

```text
SPHEREx at the NASA/IPAC Infrared Science Archive (IRSA)
```

```text
https://irsa.ipac.caltech.edu/Missions/spherex.html
```

**4.**

```text
IRSA image search (SIA2)
```

```text
https://irsa.ipac.caltech.edu/docs/program_interface/api_images.html
```

**5.**

```text
SPHEREx cutout service (IRSA)
```

```text
https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
```

**6.**

```text
SPHEREx data on Amazon Web Services (IRSA cloud data access)
```

```text
https://irsa.ipac.caltech.edu/cloud_access/
```

**7.**

```text
SPHEREx Explanatory Supplement
```

```text
https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
```

**8.**

```text
IRSA SPHEREx tutorials (notebooks)
```

```text
https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts
```

**9.**

```text
SPHEREx archive user guide
```

```text
https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access
```

**10.**

```text
NEOWISE, AllWISE and CatWISE2020 at IRSA
```

```text
https://irsa.ipac.caltech.edu/Missions/wise.html
```

**11.**

```text
2MASS at IRSA
```

```text
https://irsa.ipac.caltech.edu/Missions/2mass.html
```

**12.**

```text
Spitzer GLIMPSE at IRSA
```

```text
https://irsa.ipac.caltech.edu/data/SPITZER/GLIMPSE/
```

**13.**

```text
IRSA catalogue search (Gator)
```

```text
https://irsa.ipac.caltech.edu/applications/Gator/
```

**14.**

```text
JPL Small-Body Identification API
```

```text
https://ssd-api.jpl.nasa.gov/doc/sb_ident.html
```

**15.**

```text
JPL Horizons
```

```text
https://ssd.jpl.nasa.gov/horizons/
```

**16.**

```text
WiseView
```

```text
http://byw.tools/wiseview
```

**17.**

```text
Backyard Worlds: Planet 9
```

```text
https://www.zooniverse.org/projects/marckuchner/backyard-worlds-planet-9
```

**18.**

```text
SPHEREx All Sky Map 2025 (background of our slides)
```

```text
https://www.astropix.org/image/spherex/spherex20251218a
```

**19.**

```text
Swift/BAT transient monitor (NASA Goddard)
```

```text
https://swift.gsfc.nasa.gov/results/transients/
```

**20.**

```text
Koji Mukai's list of recent novae (NASA Goddard)
```

```text
https://asd.gsfc.nasa.gov/Koji.Mukai/novae/novae.html
```

**21.** Our automated check does not open this site. Open it once yourself to confirm it.

```text
NASA Astrophysics Data System
```

```text
https://ui.adsabs.harvard.edu
```

**22.**

```text
NASA's SPHEREx mission page
```

```text
https://science.nasa.gov/mission/spherex/
```

## Space Agency Partner & Other Data (36 rows)

Each row is one "Add New Link": the first box is Link Text, the second is Link Url.

**1.**

```text
Our code, tests and write-ups (GitHub)
```

```text
https://github.com/tatsatshah05/Ampersand-NASA
```

**2.**

```text
ESA Gaia Data Release 3
```

```text
https://www.cosmos.esa.int/web/gaia/dr3
```

**3.**

```text
ESA Herschel (Hi-GAL catalogue of cold dust clumps)
```

```text
https://www.cosmos.esa.int/web/herschel
```

**4.**

```text
JAXA and RIKEN MAXI nova alerts
```

```text
http://maxi.riken.jp/alert/novae/index.html
```

**5.** The Harvard mirror: the Strasbourg original was down on 15 November.

```text
SIMBAD (CDS, Strasbourg; Harvard mirror)
```

```text
https://simbad.harvard.edu/simbad/
```

**6.**

```text
VizieR catalogue service (CDS, Strasbourg)
```

```text
https://vizier.cds.unistra.fr/
```

**7.** This site refused our automated check. Open it once yourself to confirm.

```text
AAVSO International Variable Star Index (VSX)
```

```text
https://www.aavso.org/vsx/index.php
```

**8.**

```text
Aladin Lite (CDS, Strasbourg)
```

```text
https://aladin.cds.unistra.fr/AladinLite/
```

**9.**

```text
Digitized Sky Survey (STScI)
```

```text
https://archive.stsci.edu/cgi-bin/dss_form
```

**10.**

```text
VVV survey (VIRAC2 catalogue)
```

```text
https://vvvsurvey.org/
```

**11.**

```text
Transient Name Server
```

```text
https://www.wis-tns.org
```

**12.** Our automated check does not open this site. Open it once yourself to confirm it.

```text
The Astronomer's Telegram
```

```text
https://www.astronomerstelegram.org
```

**13.**

```text
CBAT Transient Objects Confirmation Page
```

```text
http://www.cbat.eps.harvard.edu/unconf/tocp.html
```

**14.**

```text
ASAS-SN transients
```

```text
https://www.astronomy.ohio-state.edu/asassn/transients.html
```

**15.**

```text
ALeRCE alert broker
```

```text
https://alerce.science/
```

**16.**

```text
ANTARES alert broker
```

```text
https://antares.noirlab.edu/
```

**17.**

```text
Fink alert broker
```

```text
https://fink-broker.org/
```

**18.**

```text
Paper: The SPHEREx Satellite Mission (Bock et al. 2026)
```

```text
https://arxiv.org/abs/2511.02985
```

**19.**

```text
Paper: The SPHEREx Image and Spectrophotometry Processing Pipeline (Akeson et al. 2026)
```

```text
https://arxiv.org/abs/2511.15823
```

**20.**

```text
Paper: SPHEREx as a frontier for infrared transients (Karambelkar et al. 2026)
```

```text
https://arxiv.org/abs/2602.07129
```

**21.**

```text
CIE colour-matching functions (CVRL)
```

```text
http://www.cvrl.org/
```

**22.**

```text
Astropy
```

```text
https://www.astropy.org/
```

**23.**

```text
NumPy
```

```text
https://numpy.org/
```

**24.**

```text
SciPy
```

```text
https://scipy.org/
```

**25.**

```text
reproject
```

```text
https://reproject.readthedocs.io
```

**26.**

```text
Pillow
```

```text
https://python-pillow.org/
```

**27.**

```text
Requests
```

```text
https://requests.readthedocs.io/
```

**28.**

```text
FastAPI
```

```text
https://fastapi.tiangolo.com/
```

**29.**

```text
React
```

```text
https://react.dev/
```

**30.**

```text
Vite
```

```text
https://vite.dev/
```

**31.**

```text
pytest
```

```text
https://docs.pytest.org/
```

**32.**

```text
Vitest
```

```text
https://vitest.dev/
```

**33.**

```text
Playwright
```

```text
https://playwright.dev/
```

**34.**

```text
Docker
```

```text
https://www.docker.com/
```

**35.**

```text
Render (hosting)
```

```text
https://render.com/
```

**36.**

```text
Claude Code, Anthropic (AI coding agent)
```

```text
https://claude.com/product/claude-code
```

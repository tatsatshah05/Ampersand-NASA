# Project page text

Text to paste into the NASA Space Apps project page (issue #16). Rewritten on 2026-11-15 against the running
page (built from `Dev` at commit `500e7fd`) and the project's records. Check the submission form for length
limits before pasting: a short and a long version are given.

**Read before pasting.** Every number and claim below is in the code, in a results file or in a write-up in the
repository; the write-up is named where it matters. Three things must be supplied or checked by a person and
are marked **[TO CONFIRM]**: the public web address (nothing is deployed yet), the name of the ninth item of the
bar (it is being renamed while this is written; see "What a visitor can do"), and the answer about AI tools,
which the team must agree is complete. Do not paste a marked sentence as it stands.

Rules this text keeps, and any edit must keep: the three sweep sources are **candidates**, "found in no
catalogue or report we checked" and "not confirmed"; their three sentences are the referee's, word for word
(`docs/sweep/vetting/ruling.json`); nothing has been reported anywhere; never "discovery", "first" or "new
planet".

Words used: a **visit** is one pass of SPHEREx over a patch of sky (each visit is many photos, added up into one
picture). A **detector** is one of SPHEREx's six infrared cameras.

---

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
and three infrared sources that were too faint to detect in 2025 and much brighter in 2026. We found these three
in no catalogue or report we checked. They are candidates: nobody has confirmed them.

## Full description

### What it is, and what sets it apart

From 2014 to August 2024, NASA's NEOWISE telescope looked at the whole sky in infrared light about twice a year.
Dust in the Milky Way blocks visible light, so a star that erupts behind the dust can be missed by ordinary
telescopes; in infrared light it can still be seen. NEOWISE has stopped. NASA's SPHEREx telescope now
photographs the whole sky in infrared light about every six months, in 102 colours from 0.75 to 5 micrometres.

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
our Galaxy (63 patches; 1,162,894 sources compared between three SPHEREx visits: August to September 2025,
February to April 2026, August to September 2026). The sweep was not told where anything was. It found two known
novae, V7994 Sagittarii and V0691 Serpentis, by itself. It was left with three sources that it could not
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
What each one is, is not known.

**Searches for earlier reports.** After the ruling we searched more than 30 public catalogues and alert lists
for each candidate. Each search was first tested on a known object, to show that it worked. A keyword search
of the Astronomer's Telegrams followed. None found an earlier report at any of the three places. Some sources
have not been searched in full: no person has read the telegrams in full yet, NASA's Astrophysics Data System
has had only a first search, and the SIMBAD database at CDS was down. So this does not prove that no one else
has seen them. Every search, with its date and its test object, is in `docs/sweep/searches-for-earlier-reports.md`.

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
  10.4 arcseconds north between August 2025 and August 2026. Its catalogue motion predicted 10.3 arcseconds:
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
- **RW Aurigae**, a young variable star. Between September 2025 and September 2026 it became about 1.7 times
  brighter at the shortest wavelengths, as observers on the ground (AAVSO) also recorded, and about half as
  bright at 3.9 to 5 micrometres. Our September 2025 photos fell in a dip that lasted a few days. The fading at
  3.9 to 5 micrometres has no outside check. RW Aurigae is a close pair that SPHEREx measures as one.
- **R Draconis**, a bright long-period variable star. It overexposes the detectors in every photo, so no
  brightness can be given. The light in a ring just around the star, in detectors 5 and 6, rises and falls in
  step with the 246-day cycle that AAVSO observers record. The same measure on Barnard's Star, which does not
  vary, stays flat to about 5 per cent. It is a relative measure, not a brightness.

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
- The honest limit: around WISE 0855, anything brighter than about 0.2 millijanskys between 1,000 and 30,000
  times the Earth-Sun distance would have been found. That is not deeper than earlier searches of WISE data. It
  is no new limit on Planet Nine, and it does not rule Planet X in or out.

A second method, **Follow the bend**, measures the distance of a far-off world from one visit. It found the
dwarf planet Eris in a patch centred on Eris (see "Three tools, three known worlds"). It cannot test Planet
Nine: such a planet is expected to look several times fainter than the faintest thing it can see.

### What a visitor can do

A bar across the top of every screen lists every feature, in this order. Each item has a Beginner name and an
Expert name. The **Beginner | Expert** switch sits at the bottom right. In Beginner every tool is written in
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
8. **Practise** (Expert: **Training**). Real SPHEREx pictures with one made-up moving object added, to learn
   what a mover looks like. A banner that cannot be closed and the word SIMULATION in every picture say that
   it is practice. It is the only simulated thing in the project.
9. **Observe anomalies** (Expert: **Anomalies**) **[TO CONFIRM: being built while this is written; check the
   name in the bar before pasting. Until it is merged the item reads "Vote" (Expert: "Watchlist").]** The list
   of what the searches found, for people to look at and vote on. It starts with a group headed "Not reported
   anywhere we could find": Candidates A, B and C, each with two real pictures, its allowed sentence, the
   result of the search for earlier reports, its status, and a link "Watch it appear". Then "Choose a region"
   (everywhere, the Milky Way sweep, or each searched patch), and the groups of the blind searches: those that
   need eyes, those already known, and those set aside as artefacts, with votes. A vote is an opinion, not a
   confirmation, and it never changes the machine's order. Scientists can download the whole list as a CSV file.
10. **Three tools** (Expert: **Methods**). Three ways to learn about hidden worlds, each tested on a world that
    astronomers already know, on a screen of its own (below).

### Three tools, three known worlds

Each method was built on SPHEREx data and then attacked by independent reviewers. Each was tested on a known
world, so its answer can be checked. As far as we could find, nobody has used these ideas on SPHEREx data
before; similar ideas have been used with other telescopes. The screen states each verdict at the top.

- **Follow the bend** (`docs/reflex.md`). It adds up all the photos of one 15-day visit along paths that
  include the curve the Earth's motion puts in the path of a distant body. Verdict on the screen: "Found its
  test world. Distance only rough." In a patch centred on the dwarf planet Eris it found Eris about 1 to 2
  arcseconds from where JPL puts it. The bend in its path gives a distance of about 110 to 120 times the
  Earth-Sun distance, where JPL gives 95.5; the honest range is roughly 90 to 145, with no far end at 95 per
  cent. This is a known-answer test on one known world: the patch was centred on Eris, and the method's
  settings were chosen after an earlier look had found it.
- **Line up the dips** (`docs/transits.md`). It folds thousands of readings of one star on a known planet's
  published timetable. Verdict on the screen: "Showed one known planet's dip. Mixed on a second." For the hot
  Jupiter WASP-62 b, in one detector, the star dims by about 1.1 to 1.2 per cent at the right times, against a
  published 1.2; none of 598 wrong timetables gave a dip as deep. It is a re-measurement of a known planet in
  one detector, not a blind test: the method was developed on the same readings. A second known planet, WASP-100
  b, showed the dip in that detector and not in another.
- **Off-centre in red** (`docs/colourwalk.md`). It asks whether a faint red partner pulls its star's image
  centre sideways in redder light. Verdict on the screen: "Not proven yet". On the one known partner tried,
  VHS 1256 b, the centre moved about 0.18 arcseconds toward the partner, but that is only about 2 times our
  usual error once the instrument's own offsets are counted; our rule, set before the test, asks for 4. The
  method was developed on this star, and two of its own checks failed. It has found nothing.

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
- **The practice object** is made up. It is marked as a simulation everywhere it appears.

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
- Public web address: **[TO CONFIRM: nothing is deployed yet; add the address once it is. Open it and check the
  five targets and the three candidates before pasting.]**

### Use of AI tools

**[TO CONFIRM by the team: the paragraph below is what the project's records show. Check that it is complete
and in the team's own words before pasting.]**

AI agents (Anthropic's Claude, working in Claude Code) wrote most of the code and drafted the write-ups, under
the team's direction. Every scientific claim was attacked by independent AI reviewers before we kept it: separate
AI sessions, each with its own code, re-measured the result from the real data, searched the catalogues and the
literature, and tried to find an ordinary explanation. For the sweep's candidates a referee then ruled on what may
be said. Claims were withdrawn or corrected as a result. Two examples:

- **The sweep's first description of its three candidates was withdrawn.** The reviewers showed that its 2025
  brightness values for A and B were the light of neighbouring steady stars, that two of its positions were 3
  arcseconds off, that its named "counterparts" were other stars, and that C's bright readings fell on emission
  lines (`docs/sweep.md`, "What the sweep's first write-up got wrong").
- **RW Aurigae's change was corrected.** An earlier figure, "2.5 times brighter", compared a dip of a few days
  with a normal state. Year on year it is about 1.7 times, as ground observers also found
  (`docs/verification.md`, section 2).

The rule for the whole project: real data only, nothing simulated except the clearly marked practice object, and
anything unexplained is a candidate, never a discovery.

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

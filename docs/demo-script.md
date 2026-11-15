# Demo video: shot-by-shot outline

For issue #16. Written for the teammate who records the video; no astronomy is needed. Target length: about three
and a half minutes. Check the submission form for a length limit; if it is shorter, cut shot 4 (practice) first,
then shot 7 (What is it?).

Record from the deployed site, not a laptop server, so that what the judges see matches what they can open.
**The public web address is not known yet** (nothing is deployed); it is written `<SITE>` below. **[TO CONFIRM]**
Replace `<SITE>` with the real address and run "Before recording" on it.

Rebuilt on 2026-11-15. Every control name below was read off the running page (built from `Dev` at commit
`500e7fd`) in a headless browser at 1440 x 900 and 1280 x 720, in Beginner and in Expert, except shot 5, which
is **written from the design** of a screen still being built (see shot 5). Nobody has played the video in real
time on the deployed site or tried a phone. Nothing is simulated, except the practice round in shot 4, which says
so on screen. If something shows nothing, say so on camera: that is the result.

How the page is laid out (the names are the page's own):

- **The bar** across the top lists every feature. In Beginner: Watch, Brightness, Colours, Find changes, Far-off
  planet, Asteroids, What is it?, Practise, Observe anomalies, Three tools. In Expert: Viewer, Light curve,
  Spectrum, Blind search, Planet X search, Small bodies, Object card, Training, Anomalies, Methods. (Until the
  Observe anomalies screen is merged, its place reads Vote, in Expert Watchlist.)
- **The switch** "Beginner | Expert" is at the bottom right of every screen.
- **The row of buttons** under the search box: Candidate A, Candidate B, Candidate C, Barnard's Star, Epsilon Indi
  B, WISE 0855, RW Aurigae, R Draconis, Young star in Serpens South, Nova V462 Lupi, Nova V572 Velorum.
- **The side column** beside the picture: one sentence about the whole run of visits and one table of all
  visits. These words do not change while the pictures play; only the mark of the visit on screen moves.

Words: a **visit** is one pass of SPHEREx over a patch of sky; a **detector** is one of its six infrared cameras.

## Before recording

- [ ] The site is deployed and every step of `docs/deploy.md`, "After deploying: warm-up", is done:
      `python scripts/export_lab.py --check` passed in the checkout before the build, and
      `python scripts/warm_cache.py --check` passes on the server.
- [ ] The bar's ninth item reads **Observe anomalies** in Beginner. If it reads **Vote**, the new screen is not
      merged: record shot 5 on the Vote screen (see the note in shot 5) or cut it.
- [ ] Open every address below once on the recording machine. A position the server has never been asked for
      can take up to a minute the first time; after that it is instant.
- [ ] The practice round: open its address (shot 4) once, so the round is built before recording. The same
      `train=1` gives the same made-up object every time, so you can rehearse it.
- [ ] Browser zoom 100%, window 1280 x 720 or 1440 x 900, no bookmarks bar, notifications off.
- [ ] The operating system's "reduce motion" setting is off. With it on, a candidate's view opens still on its
      "before" picture instead of blinking.
- [ ] Start every shot from its address, which says `ui=beginner` or `ui=expert`: the page otherwise remembers
      the last level chosen in that browser.
- [ ] Do not scroll to the older-survey pictures at the bottom of What is it? on camera (see "If an outside
      service is down").
- [ ] Re-read "Things not to say" at the end.

## The addresses

`<SITE>` then the text. The name buttons look the name up and move the position to where the star is now; if the
name service is down, these addresses do the same without it.

| Shot | What | Address |
|---|---|---|
| 1 | Candidate B (the page's own opening) | `/?ui=beginner` |
| 2 | Barnard's Star | `/?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&pmra=-801.5509783684709&pmdec=10362.394206546573&parallax=546.975939730948&name=Barnard%27s+star&ui=beginner` |
| 3 | RW Aurigae, Brightness open | `/?ra=76.956587&dec=30.401291&fov=0.1&det=5&mode=normal&pmra=7.23&pmdec=-20.33&parallax=15.42&name=RW+Aur&ui=beginner&tool=brightness` |
| 4 | Practice round | `/?train=1&level=easy&ui=beginner` |
| 5 | Observe anomalies | `/?watchlist=1&ui=beginner` |
| 5 | Candidate A (what "Watch it appear" opens) | `/?ra=270.80408&dec=-23.46818&fov=0.1&det=6&mode=normal&pmra=0&pmdec=0&name=Candidate+A&ui=beginner` |
| 6 | Three tools | `/?tools=1&ui=beginner` |
| 7 | What is it? on Barnard's Star | `/?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&pmra=-801.5509783684709&pmdec=10362.394206546573&parallax=546.975939730948&name=Barnard%27s+star&ui=beginner&tool=context` |

## Shots

### 1. A source appears (0:00 to 0:25)

- **Open:** `<SITE>/?ui=beginner`. The page opens on **Candidate B**, blinking by itself between two pictures
  marked "Before · Aug 2025" and "After · Mar 2026". The button **Blink before and after** is pressed. The side
  column reads "Candidate B", then "Not seen in August 2025. Clearly there by March 2026.", a table (Visit 1 Aug
  2025 not seen; Visit 2 Mar 2026 seen clearly; Visit 3 Aug 2026 seen clearly, brighter), and the candidate's
  sentence. Keep the sentence in the picture.
- **Say:** "For ten years NASA's NEOWISE telescope looked at the whole sky in infrared light, twice a year. It
  stopped in August 2024. NASA's SPHEREx telescope now photographs the whole infrared sky, again and again. Our
  tool searches those pictures for change, and shows anyone the before and the after. This is a source in
  Scorpius. In August 2025 SPHEREx could not detect it. By March 2026 it was clearly there. We found it in no
  catalogue or report we checked. It is a candidate: nobody has confirmed it yet."
- **Do not say:** discovery, new (without "that we found in no catalogue or report we checked"), first,
  confirmed, "a young star's outburst" as fact, any 2025 brightness for it, or that it has been reported.
  Do not read out the "times the background scatter" numbers as brightness.
- **Basis:** `frontend/src/finds.ts` (the sentence, word for word), `docs/sweep.md`.

### 2. The page's own steps: a star that moves (0:25 to 0:55)

- **Show:** the three numbered steps under the table: "1 Pick any star", "2 Press Play or Blink", "3 Read what
  changed". Then press **Barnard's Star** in the row of buttons (or open its address). It opens paused: press
  **Play**. Let the three visits play; then press **Blink first and last**.
- **On screen, the side column reads:** "It moved 10.4 arcseconds north between August 2025 and August 2026. Its
  catalogue motion predicted 10.3 arcseconds: they agree." and "Seen clearly in all 3 visits." Keep it in the
  picture while the visits play: the words do not change, only the mark of the visit on screen moves.
- **Say:** "This is Barnard's Star, the fastest-moving star in the sky. Each picture is one SPHEREx visit: about
  twenty photos, added up. Watch it step north while the stars around it stay still. The page measured 10.4
  arcseconds in a year. The Gaia star catalogue predicts 10.3. They agree."
- **If time allows:** "Its catalogue position is from the year 2000. It has moved four and a half arcminutes
  since, so the tool first works out where it is now."
- **Do not say:** that every picture is one photo; that it is "real time" or "live".
- **Basis:** the running page; `docs/verification.md`, section 4; `CLAUDE.md`, "Verified facts".

### 3. The bar and the switch: one tool at two levels (0:55 to 1:25)

- **Show:** press **RW Aurigae** in the row, then **Brightness** in the bar (or open the shot-3 address). The
  panel "Brightness over time" opens under the picture. In Beginner it reads: "It changed between September 2025
  and September 2026. In SPHEREx's shortest infrared colours it became about 1.6 times as bright. In SPHEREx's
  longest infrared colours the light just around it became about half as bright." and "Another star is so close
  that its light is mixed into these numbers."
- **Then press Expert** on the switch at the bottom right. The bar now reads Viewer, Light curve, Spectrum ...
  and the same panel shows "brighter in D1 (+64%, visit 1 to visit 3)", "The star's outer light also shows a
  change: fainter in D5 (−48%), fainter in D6 (−44%)", and a table per detector. Then press **Beginner** again.
- **Say:** "Every tool is in this bar. Each has two levels. In Beginner it speaks plainly: this young star became
  about one and a half times as bright in the shortest infrared colours, and about half as bright in the longest.
  One press, and Expert shows the scientist's view: each detector, each wavelength compared only with itself,
  and the numbers to download. Observers on the ground saw the same brightening."
- **Do not say:** "2.5 times" (that compared a dip of a few days with a normal state); that the long-wavelength
  fading is checked by anyone else (it has no outside check); "flux" for the outer light (it is a relative
  measure).
- **Basis:** the running page; `docs/verification.md`, section 2.

### 4. Practice: can you spot a mover? (1:25 to 1:45)

- **Show:** press **Practise** in the bar, or open `<SITE>/?train=1&level=easy&ui=beginner`. The screen
  "Practice: find a made-up object" opens with a banner that reads "SIMULATION. One made-up moving object has been
  added to these real SPHEREx images. It is not a real detection, and nothing here is a discovery." The word
  SIMULATION is drawn in the corner of every picture. Keep both in the frame. In the **Frames** menu choose
  **Difference frames**, press **Play**, click where you think the object is, then press **Show me**.
- **Say:** "To learn what a mover looks like, there is a practice round. It adds one made-up object to real
  SPHEREx pictures, and it says so in a banner that cannot be closed. This is the only made-up thing in the
  whole tool."
- **Do not say:** that the practice object is real, or a detection.
- **Basis:** `CLAUDE.md`, "Training mode"; the running page.

### 5. Observe anomalies (1:45 to 2:15)

**Written from the design.** This screen was being built while this outline was written (branch
`agent/anomalies-final` did not exist yet). Check every name below on the deployed page before recording.

- **Show:** press **Observe anomalies** in the bar (`<SITE>/?watchlist=1&ui=beginner`). The first group is headed
  "Not reported anywhere we could find": Candidates A, B and C, each with two real pictures, its sentence, the
  sentence about the search for earlier reports, and a status line. Press **Watch it appear** on Candidate A:
  its view opens, blinking between "Before" and "After". Go back, then show **Choose a region** (everywhere, the
  Milky Way's plane sweep, each searched patch by constellation, with counts). Scroll to the groups below (those
  that need eyes, those already known, and those set aside as an artefact) and to the vote buttons **Looks
  real**, **Looks like an artefact** and **Not sure**.
- **Say:** "Our sweep compared 472.6 square degrees of the Milky Way's plane between SPHEREx's visits. It found
  two known novae by itself, and three sources we could not explain. Four independent reviewers attacked each
  one. We searched more than thirty catalogues and alert lists for earlier reports, and found none. They are
  candidates: nobody has confirmed them, and we have not reported them yet. Everything else our searches found
  is here too, for anyone to look at and vote on. A vote is an opinion, not a confirmation."
- **Do not say:** discovery, new, first, confirmed; that nobody else has seen them (some sources are not yet
  searched in full); "a nova" as fact; "nothing in SIMBAD, so nobody has reported it"; that a vote
  confirms anything; that anything has been sent or reported.
- **If the screen still reads Vote:** the first group and Choose a region are not there. Open Candidate A from
  the row of buttons instead of Watch it appear, and on the Vote screen show only the three groups ("In no
  catalogue", "Already known", "Set aside as false alarms") and the vote buttons.
- **Basis:** `docs/sweep.md`, `docs/sweep/searches-for-earlier-reports.md`, `docs/watchlist.md`.

### 6. Three tools: Eris appears (2:15 to 2:50)

- **Show:** press **Three tools** in the bar (`<SITE>/?tools=1&ui=beginner`). The screen "Three tools, three
  known worlds" opens; the box under the title reads "Nothing on this screen is a new planet." Tool 1, **Follow
  the bend**, shows "Found its test world. Distance only rough." and "Our tool: about 111", "NASA: 95.6". Scroll
  to **Try it: make Eris appear**. Choose **One picture** (caption: "One picture. Eris is in here, but too faint
  to see."), then **All, as taken** (the light smears out), then press **Slide and stack** (caption: "Each
  picture slid to follow Eris, then added. Now Eris piles up into one sharp dot."). Press **Show where NASA says
  Eris is**. If time allows, move the **How far away?** slider under **Try it: find the distance** and watch the
  dot sharpen and blur.
- **Say:** "Three tools, each tested on a world astronomers already know, so you can check the answer. The first
  adds up 57 SPHEREx photos of one patch taken over 15 days. Added as they are, the dwarf planet Eris is too faint
  to see. Slid along the path that the Earth's own motion bends, and added, it piles up into one dot, where NASA
  says Eris is. The size of the bend gives a rough distance: about 111 times the Earth's distance from the Sun,
  where NASA gives about 96. The patch was centred on Eris, so this is a test on a known answer, not a search of
  the sky." Then, scrolling past the other two: "The second, Off-centre in red, is not proven yet. The third,
  Line up the dips, showed a known planet's dip, and was mixed on a second."
- **Do not say:** discovery, first, new planet; "finds Planet X", "a Planet Nine test" or "a Planet Nine search";
  "without being told where Eris is"; that the distance is precise, or "105 AU"; "6.8 sigma" (the straight path is
  rejected at about 7 sigma with all photos and about 4 sigma with the first day left out); "a spectrum from 0.75
  to 5 micrometres"; "covers 50 to 400 AU". For tool 3: not "blind", not that SPHEREx can find transiting planets,
  not that the TESS candidate TOI-4055.01 is a planet. For tool 2: not "candidate", not that a shift is a
  companion, not that it works blind.
- **Basis:** `docs/reflex.md`, `docs/transits.md` and `docs/colourwalk.md` ("Words for the demo" and their "do not
  say" lists); `frontend/src/toolsWording.ts`.

### 7. What is it? (2:50 to 3:10)

- **Show:** press **Watch** in the bar, press **Barnard's Star**, then **What is it?** in the bar (or open the
  shot-7 address). The card reads "SIMBAD lists it as an M dwarf: a small, cool star (astronomers call these red
  dwarfs)." Beside it, a drawing of the star next to the Sun, marked "Illustration drawn from measurements. Not a
  photograph." and "DRAWING, NOT A PHOTO", and "How far: 5.96 light-years (Gaia)."
- **Say:** "What is it? says what the star catalogues know about any object, in plain words, and draws it from
  their numbers: the colour of a body at its measured temperature, and its size next to the Sun. It is a drawing,
  and the page says so."
- **Do not say:** that the drawing is a photograph, or that SPHEREx measured these numbers (they are Gaia's and
  SIMBAD's).
- **Basis:** the running page; `frontend/src/identify.ts`.

### 8. Close: what is and is not claimed (3:10 to 3:30)

- **On screen:** the site address, the team name and the credits line.
- **Say:** "Everything here is real SPHEREx data, except the practice round, which says so. We claim no discovery
  and no new planet. The three sources are candidates that we found in no catalogue or report we checked; a
  bigger telescope's spectrum and SPHEREx's next visits will tell what they are. Type any star or position, and
  watch that patch of sky change. Built by Team Ampersand for NASA Space Apps 2026."
- **Credits on screen (must be legible):** Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared Science Archive
  (IRSA); ESA Gaia DR3. Names: SIMBAD (CDS, Strasbourg). Brightness checks: NEOWISE (NASA/IPAC IRSA) and AAVSO
  observers.

## Optional extra shots

- **Far-off planet (the Planet X search).** On WISE 0855 press **Far-off planet** (Expert: **Planet X search**).
  Its first run on a patch takes a few minutes; run it before recording. Say, from `docs/distant.md`: a distant
  world jumps between visits because we look from opposite sides of the Earth's path; this search looks for that
  jump; on the real sky it finds nothing here, and it says how bright an object would have had to be. In Expert,
  **Try it on a planted object (simulation)** shows it finding a made-up object, marked as a simulation. Do not
  say that a planet was found, that this rules Planet Nine in or out, or that the limit is deeper than WISE's.
- **Find changes on WISE 0855.** Beginner reads "It tested 188 points of light in this patch. 1 thing moved, and
  nothing changed brightness. It is already known in star catalogues." Expert (Blind search) reads "Moved 7.3
  arcseconds a year (give or take 0.7), heading west". Run it once before recording.
- **Candidate C.** Its table has four visits, one of them "picture spoiled here" (April 2026). Do not say that C
  had gone by August 2026: its emission lines were still there.

## If an outside service is down

| What depends on it | What you will see | What to do |
|---|---|---|
| Name lookup (SIMBAD), used by the search box and the name buttons of the five targets | A message under the search box | Open the addresses in the table above. The three candidates' buttons need no lookup |
| What is it? (Gaia DR3 and SIMBAD) | The card names the catalogue that did not answer | Open it on Barnard's Star once before recording; or cut shot 7 |
| The older-survey pictures at the bottom of What is it? (Aladin Lite, CDS) | An empty box, or "Gaia stars could not be loaded from VizieR right now." | Do not scroll to them. No shot needs them |
| The SPHEREx archive, for a position not yet downloaded | A long wait, or "The frames could not be loaded" | Use only positions opened before (see "Before recording"). Positions on the server's disk need no outside service |
| The catalogues the searches check | The panel says which catalogues answered | Run each search before recording; a finished search is kept |
| Three tools, Observe anomalies, the practice round | Nothing: they read files on the server | If a picture is missing there, the server's warm-up was not finished (`docs/deploy.md`) |

If something fails on the day, show the saved pictures in `docs/sweep/vetting/` (for example
`docs/sweep/vetting/B/pixels/pictures/zoom_visits_marked.png`), `docs/results/` and `docs/search/`, and say that
they are saved outputs of the same data.

## Things not to say

About the three candidates (the referee's lists, `docs/sweep/vetting/ruling.json`):

- Not "discovery", "confirmed", "first ever seen". Not "new" without "that we found in no catalogue or report we
  checked". Not that nobody else has seen them.
- Not that anything has been reported, sent or filed: nothing has.
- Not "nothing in SIMBAD, so nobody has reported it". Not "ZTF or Rubin saw nothing" as evidence (they cannot see
  B's field).
- Not "a nova" or "a young star's outburst" as fact. Not "hydrogen emission detected" for A, "ice detected" for B,
  or "[Mg IV] detected" for C.
- Not any 2025 brightness for A or B, and none of the first write-up's withdrawn statements
  (`docs/sweep.md`, "What the sweep's first write-up got wrong"): their 2025 values were the light of
  neighbouring stars.
- Not "a thousand times its old brightness" for B, and not "a pre-existing red star erupted".
- Not that C had gone, or nearly gone, by August 2026; not "178 and 300 mJy" for C; not "a flare lasting half a
  year" (its start is not known).
- Not an exact spring-2026 brightness for A without saying the readings were saturated.

About the three methods (each write-up's "do not say" list): not discovery, first or new planet; not "blind";
not "finds Planet X" or "tests Planet Nine"; not "without being told where Eris is"; not that SPHEREx can find
transiting planets; not that TOI-4055.01 is a planet; not that the colour walk is proven or found a companion.

About the rest:

- Not "real time" or "live": SPHEREx data come in releases, and visits are months apart.
- Not "every picture is one photo": each is the photos of one visit, added up.
- Not "discovers Planet X", and not that the Planet X search sets a new limit on Planet Nine.
- Not "S/N 5, 19, 27", "within 1.3 arcseconds" or "only after summing" for WISE 0855.
- Not "2.5 times" for RW Aurigae, and not "flux" or "brightness in physical units" for R Draconis.
- Not "new" or "erupted" about the Serpens South star: it came back from a dip.
- Not that the practice object is real. Keep its banner in view.

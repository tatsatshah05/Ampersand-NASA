# Demo video: shot-by-shot outline

For issue #16. Written for the teammate who records the video; no astronomy needed. Target
length: about three and a half minutes. Check the submission form for a video length
limit; if it is shorter, cut shot 7 (practice) first, then shot 1.

Record from the deployed site, not a laptop server, so what the judges see matches what
they can open. **The public web address is not known yet** (nothing is deployed); it is
written `<SITE>` below. **[TO CONFIRM]** Replace `<SITE>` with the real address and run
the "Before recording" checklist on it.

The page opens in **Beginner** (just the picture and what moved). The switch "Beginner | Expert" is at the top, under the title: press **Expert** before shot 2, or open the addresses below, which carry `ui=expert`. The page remembers the choice in that browser.

Words: a **visit** is one pass of SPHEREx over a patch of sky; a **detector** is one of the
six infrared cameras (D1 to D6, short to long wavelength).

Everything below was checked on 2026-11-14 on the running page (a local server built from
`Dev` after the search panel was merged), by loading it in a headless browser, reading what it
printed and looking at screenshots. Nobody played the video-style loop in real time or tried a phone. Nothing was simulated, substituted
or retouched, except the practice mode in shot 7, which says so on screen. If a target shows
nothing, say so on camera: that is the result.

## Before recording

- [ ] Site is deployed and `python scripts/warm_cache.py --check` passes on the server.
- [ ] Open every address in the shot list once on the recording machine. The first time a
      new position loads it can take up to a minute; after that it is instant.
- [ ] **Run the blind search once on each patch you will use** (WISE 0855 in shot 5, Serpens
      South in shot 6): press "Search this patch for anything that moved or changed". The
      first run takes 20 to 50 seconds when the images are already on the server, about three
      minutes when they are not. The answer is then kept, and a repeat is instant. The warm-up
      script does not do this for you.
- [ ] Field of view stays at 0.1 degrees. Only that size is prepared; any other size
      downloads for about a minute per detector, live.
- [ ] Browser zoom 100%, window about 1280 x 720 (the search panel is below the picture:
      scroll to it), no bookmarks bar, notifications off.
- [ ] Do not open the "Sky context" panel on camera (see "If an outside service is down").
- [ ] Re-read `docs/results.md` and `docs/verification.md`: they say what each target really
      shows and which frames to avoid.

## The targets, and the addresses that open them

On the page, the five challenge targets and the Serpens South star are buttons under the
search box. Each button looks the name up (SIMBAD) and moves the position to where the
object is now, and puts the object's motion in the address. If the name service is down,
paste one of these addresses instead (`<SITE>` then the text). The motion matters: without it
the marker can follow the wrong object at WISE 0855.

| Target | Address |
|---|---|
| Barnard's Star | `/?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal&pmra=-801.5509783684709&pmdec=10362.394206546573&parallax=546.975939730948&name=Barnard%27s+Star&ui=expert` |
| Epsilon Indi B | `/?ra=331.096653&dec=-56.800663&fov=0.1&det=5&mode=normal&pmra=3981.97666296105&pmdec=-2466.8318147663504&parallax=270.6580324694526&name=eps+Ind+B&ui=expert` |
| WISE 0855-0714 | `/?ra=133.759765&dec=-7.242182&fov=0.1&det=6&mode=normal&pmra=-8123.7&pmdec=673.2&parallax=439&name=WISEA+J085510.74-071442.5&ui=expert` |
| RW Aurigae | `/?ra=76.956587&dec=30.401291&fov=0.1&det=5&mode=normal&pmra=7.23&pmdec=-20.33&parallax=15.42&name=RW+Aur&ui=expert` |
| R Draconis | `/?ra=248.167233&dec=66.755024&fov=0.1&det=5&mode=normal&pmra=-20.642811719160797&pmdec=6.148818852711324&parallax=1.2509180143740992&ui=expert` (not seen on the page; assembled from the values in `docs/results.md`) |
| Serpens South young star | `/?ra=277.50547&dec=-2.06198&fov=0.1&det=6&mode=normal&name=Young+star+in+Serpens+South&ui=expert` |

## Shots

### 1. The question (0:00 to 0:15)

- **On screen:** `<SITE>/`, before anything is clicked (it opens on Barnard's Star, in Beginner: a good first picture).
- **Say:** "NASA's SPHEREx telescope maps the whole sky in infrared light, and then maps it
  again about six months later. Anything that moved or changed between maps is interesting:
  a nearby star, a failed star, maybe a world nobody has found yet. The data is public, but
  it is not easy to look at. We built a way for anyone to watch a patch of sky change."
- **Basis:** the six-month revisit is in `docs/results.md`: three or four visits per target
  between April 2025 and October 2026.

### 2. Barnard's Star moves (0:15 to 0:50)

- **Press:** the button "Barnard's Star" (or open its address above). Detector D5
  (3.81 to 4.43 microns) is selected.
- **Do:** let the three frames play in a loop. Press "Pause", then the "next frame" arrow
  (or the right arrow key) to step through the visits with "Motion markers" and "Gaia overlay"
  on. Tick "Blink first and last".
  Then open the "Mode" menu and choose "Difference (what changed)": the star is a white patch
  beside a black one.
- **On screen, at the last visit, the page itself reads:** "Since frame 1: measured shift
  10.2″ north, 2.2″ west. Gaia predicts 10.3″ north, 0.8″ west. They differ by 1.4″, which is
  0.23 of a SPHEREx pixel." Keep that text in the picture.
- **Say:** "This is Barnard's Star, the fastest-moving star in the sky. Each frame is one
  SPHEREx visit: about twenty exposures, stacked. Watch the star step north while everything
  around it stays put. We measured that step, and the Gaia star catalogue predicts it:
  measured 10.2 arcseconds north, predicted 10.3. They agree to within a quarter of one SPHEREx
  pixel."
- **Say, on the difference view:** "Subtract the first visit from a later one and everything
  that stayed still cancels. What is left is the thing that moved."
- **Worth one sentence:** "The star's catalogue position is from the year 2000. It has moved
  four and a half arcminutes since, so the tool first works out where it is now."
- **Say, if time allows (honest):** the page also says "The core is overexposed, so the
  position is good to about 1″". The star overloads the detector, so one arcsecond is as
  well as it can be placed.
- **Basis:** `docs/results.md` (Barnard's Star: marker within 1.5 arcseconds of the catalogue
  in all 18 frames), `docs/verification.md` section 4.
- **Avoid:** detectors D1 to D4 for this star in close-up: its core is saturated there (a flat
  white patch). D5 and D6 are clean.

### 3. A star that changes brightness: RW Aurigae (0:50 to 1:20)

- **Press:** the button "RW Aurigae" (opens in D5). Press "Brightness over time". A panel
  opens with one small chart per detector. Point at the D1 chart (0.75 to 1.12 microns): the
  dots climb from the first visit to the third. The text at the top of the panel reads
  "brighter in D1 (+64%, visit 1 to visit 3)". Then press "Outer light": the D5 and D6 charts
  fall, and the text reads "fainter in D5 (−48%), fainter in D6 (−44%)".
  Optional, before the chart: choose Mode "Difference (what changed)" and D1 (white star) then
  D6 (black star).
- **Say:** "Some things do not move; they change. This young star, RW Aurigae, became about
  1.7 times brighter at the shortest wavelengths and about half as bright at 3.9 to 5 microns
  between September 2025 and September 2026. Observers on the ground recorded the same
  brightening. The fading at the long wavelengths we can only see from SPHEREx. The chart
  compares measurements only at the same colour, because each exposure sees the star at a
  different colour."
- **Careful:** the page's own figure is "+64%" for detector 1 (the middle of 13 colour
  bins). "About 1.7 times" is the year-on-year figure that ground observers also found
  (`docs/verification.md` section 2). Do not say "2.5 times": that compares a dip of a few
  days with a normal state. Point at the chart rather than reading numbers aloud.
- **Say it is relative:** the long-wavelength fading is the star's "outer light" (the star's
  centre is overexposed there), a relative brightness, not a brightness in physical units.
- **Mention if asked:** RW Aurigae is a close pair that SPHEREx measures as one; the page says
  so in the box at the top of the panel.
- **Do not use R Draconis for this shot.** It is so bright that its core is saturated in every
  exposure of every detector; only a relative brightness of its outer light exists, in
  detectors D5 and D6. It can be mentioned as a limit: "very bright stars overload the
  detector."

### 4. The hardest target: WISE 0855 (1:20 to 1:50)

- **Press:** the button "WISE 0855" (opens in D6, 4.41 to 5.01 microns, with its motion in the
  address). Pause, then step to visit 1. The page reads "Marginal detection, 3.4 times the
  background scatter: treat with care", and the marker is drawn dashed. Step to visit 2: "Detected
  clearly, 15 times the background scatter". Keep the text in the picture.
  Then open the Detector menu and choose D2: nothing is there. Back to D6 and Mode "Sum (one
  deeper frame)".
- **Say:** "This is a very cold brown dwarf, and it moves almost as fast as Barnard's Star. In
  ordinary near-infrared light it is invisible. At the longest wavelengths SPHEREx measures,
  it is there, and it moves west from one visit to the next, where the catalogue says it
  should. The first visit is marginal: only three exposures, 3.4 times the background scatter.
  After that it is clear: 14.6 and 11.2 times."
- **Say this too, it is part of the honest result:** "By the third visit it has drifted to
  within four arcseconds of an ordinary background star, closer than SPHEREx can separate. The
  star supplies about a quarter of the light at the longest wavelengths."
- **Basis:** `docs/verification.md` section 1. The detection strengths 3.4, 14.6 and 11.2 are the
  page's; the separate check found 3.7, 17.5 and 14.2.
- **Do not say** "S/N 5, 19, 27", "within 1.3 arcseconds" or "only after summing": the first two
  are not detection strengths (see `docs/verification.md`), and it is already visible in each
  visit's frame in D5 and D6; the summed frame just shows it more clearly.
- **Wording:** "very cold" and "about 8 arcseconds a year" are from the project brief. Anything
  stronger ("the coldest known") must be checked against a NASA page first.
- **Trap:** this object has moved 212 arcseconds since 2000, so a search on its catalogue
  coordinates looks at the wrong spot, and without the motion values in the address the marker
  can follow the background star. Open it with the button or the address in the table above.
  Check the text under the frame at visit 3 before recording: it should name the neighbouring
  star.

### 5. The search finds the known objects by itself (1:50 to 2:20)

- **Press:** with WISE 0855 still open, scroll to the buttons under the picture and press
  "Search this patch for anything that moved or changed". The panel "Anything that moved or
  changed in this patch" opens below the picture (scroll down). Reading from a search made
  beforehand, it says: "188 sources tested in 19 seconds: 1 object moved or changed, 0 set aside
  as artefacts", then one card: "Moved 7.3 arcseconds a year (give or take 0.7), heading west",
  "Already known: WISEA J085510.74-071442.5, whose catalogued motion matches the measured one",
  "Verdict: clean". A numbered ring marks it on the picture.
- **Say:** "We also built a blind search. You give it a patch of sky and it looks at every source
  for anything that moves or changes brightness between visits, without being told what is
  there. Given only the field centres, it found Barnard's Star, the brown dwarfs WISE 0855 and
  Epsilon Indi B moving at their catalogued speeds, and RW Aurigae changing: brighter in the far
  red and about half as bright at 4 to 5 microns."
- **Say:** "It tries hard to fool itself first. Every detection is compared with the same
  measurement at hundreds of empty places in the same picture, and every candidate is tested
  against the artefacts we found in SPHEREx data: reflections of bright stars, overlapping
  glitches, saturated stars, blends. In ordinary star fields it reported only real, known
  objects, and it threw out convincing-looking movers that turned out to be a reflection,
  blends and patches of nebula."
- **If asked about numbers:** on the five challenge fields, 30 searches, 5 objects reported, all of
  them the targets, no false alarm found by eye; that is a small sample (`docs/search.md`).
- **Optional picture:** `docs/search/rejected_ghost_epsindib_D6.png`, the ring that looked like a
  7-sigma mover and was rejected.
- **Fallback if the search is slow or fails:** show `docs/search/recovery_wise0855_D5.png` and
  `docs/search/recovery_barnard_D5.png` (the saved output of the same search) and say they are
  its saved output.

### 6. A candidate nobody lists: Serpens South (2:20 to 3:10)

- **Press:** the button "Young star in Serpens South" (under "Or look at what our own search
  flagged (a candidate)"). D6 opens. The page warns that a very bright star is near (Gaia
  magnitude 5.1, 6.8 arcminutes away, outside the picture): leave it on screen, it is part of
  the honest picture. Press "Brightness over time": D3 to D6 are marked "brighter" across the four visits.
  Then press "Search this patch for anything that moved or changed" (a previously run search
  answers at once; 4 objects appear). Scroll to card 1: "Changed brightness between 3 Sep 2025
  and 30 Aug 2026: brighter, 4.5 times as bright as before", marked "Candidate", with the text "A
  candidate, not a finding: the catalogues that answered do not list it as a variable". Do not
  dwell on cards 3 and 4: they are marked "Caution", seen in one detector only, and not claimed
  (`docs/search.md`).
- **Cut to the picture:** `docs/search/serpsouth_neowise_spherex.png` (open the file full
  screen; it is NEOWISE 2014 to 2024 in grey dots and SPHEREx in coloured squares, 4.6 microns on
  top).
- **Say, on the page (word for word, `docs/search.md` "Words for the demo"):** "Then we pointed it
  at four young star clusters. Most of what it flagged there are young stars already listed as
  variable. Two are not listed as variable in Gaia, AAVSO's variable star index or AllWISE, and
  passed every test we have. The strongest is a young star buried in the Serpens South cloud that
  became about five times brighter at 2.4 to 5 microns between September 2025 and March 2026 and
  stayed bright through September 2026."
- **Say, on the chart (word for word, except the last words of the second sentence, see below):**
  "We then checked it against another telescope. NASA's NEOWISE mission measured the same spot
  twice a year from 2014 to 2024, and its public archive shows this star swinging by a factor of
  nine. NEOWISE's last look, in March 2024, caught it at its faintest in ten years, at exactly the
  level SPHEREx found in September 2025. So our search, knowing nothing, picked out a star that
  really is strongly variable, and SPHEREx watched it climb back out of a deep dip, in 102 colours
  at once. It is not a new kind of event, and specialists who study young stars have very likely
  seen it vary. What we can say is that none of the variable-star lists we asked has it, and that
  SPHEREx's pixels cannot tell which star of a tight group is the one changing."
  (`docs/search.md` says "its deepest dip on record"; the record is NEOWISE's ten years, so this
  script says "a deep dip" here. The NEOWISE table gives the factor as 9 at 4.6 microns and 7 at
  3.4 microns.)
- **Say "not listed as variable in Gaia DR3, AAVSO VSX or AllWISE"; never "new", "discovered" or
  "erupted".** Say "it came back from a dip". Say "candidate" and say what would confirm it: an
  infrared image from 2026 at a sharper scale than SPHEREx's, and the next SPHEREx visits.
- **Do not say** the search "discovered" it, and do not quote the search's "times the noise" as
  "signal to noise".

### 7. Practice: can you spot a mover? (3:10 to 3:30)

- **Press:** go to `<SITE>/`, then the button "Practise: find a planted object". A banner across
  the top reads "SIMULATION. Simulation: one made-up moving object has been added to these real
  SPHEREx images. It is not a real detection, and nothing here is a discovery." and the word
  SIMULATION is drawn in the corner of the picture. Keep both in the frame throughout. Pick
  "Difference frames" in the "Frames" menu, then press "Show me": rings joined by a line show where
  the made-up object was in each visit.
- **Say:** "To let anyone try this, there is a practice mode. It adds one made-up moving object to
  real SPHEREx pictures, and says so in a banner that cannot be closed. Find the dot that is in a
  different place in each frame. This is a simulation for practice, not a detection."
- **Basis:** `CLAUDE.md` "Training mode": the only simulated thing in the project; it has its own
  endpoint and never reaches the real views.

### 8. Close (3:30 to 3:40)

- **On screen:** the site address, the team name, and the credits line.
- **Say:** "Type a star's name or a position and watch that patch of sky. Built by Team Ampersand
  for NASA Space Apps 2026."
- **Credits on screen (must be legible):** Data: NASA/JPL-Caltech SPHEREx; NASA/IPAC Infrared
  Science Archive (IRSA); ESA Gaia DR3. Name lookup: SIMBAD (CDS, Strasbourg). Brightness check:
  NEOWISE (NASA/IPAC IRSA).

## If an outside service is down

The page depends on a few services outside our control. On 2026-11-14 some of them were down.

| What depends on it | What you will see | What to do |
|---|---|---|
| Sky context panel (Aladin Lite; Gaia stars from VizieR) | On the page tested: "Gaia stars could not be loaded from VizieR right now." The panel can also stay empty | Do not open it in the video. It is not needed for any shot |
| Name lookup (SIMBAD), used by the search box and the target buttons | A red message under the search box | Paste the addresses from the table above instead |
| The SPHEREx archive, for a position not yet downloaded | A long wait, or "The frames could not be loaded" with "Try again" | Use only positions opened beforehand (see "Before recording"). The cache on the server's disk needs no outside service |
| The catalogues the blind search checks (five) | The panel says which catalogues answered, and what it could not check | Run it beforehand; a finished search is kept |

If something fails on the day, show the saved pictures in `docs/results/` and `docs/search/`
and say they are saved outputs of the same code.

## Optional extra shots

- **Epsilon Indi B (a pair of brown dwarfs).** Press "Epsilon Indi B": it is visible in all six
  detectors and moves south-east about 6.3 arcseconds between April 2025 and October 2026, on the
  catalogue track. The page reads "No Gaia star near the centre" only if opened without the motion:
  use the button. Its bright primary star is 6.7 arcminutes away, outside the default frame, so
  "moving with the primary" needs a wider field of view (`docs/results.md`).
- **What SPHEREx adds: the spectrum.** On Epsilon Indi B press "Spectrum of the target" (or click
  on the object). Say: "The existing tool for this kind of search, WiseView, uses the WISE
  telescope's infrared bands. SPHEREx measures 102 colours from 0.75 to 5 microns. This is the
  light of a brown dwarf, colour by colour: bright peaks with deep gaps between them." Basis: 298
  measurements trace its brightness from 0.75 to 5 microns, the same curve at all four visits
  (`docs/results/eps_indi_b_brightness.png`). Do not explain the gaps ("water", "methane") unless
  someone has checked that against a published source. Check the WiseView wording against the
  WiseView page; this project did not check it.

## Things not to say

- Not "real time" or "live": SPHEREx data arrives in releases, and each visit is months apart.
- Not "discovers Planet X" or "discovered": the tool makes moving objects easier to spot; it has
  not found anything new. The Serpens South star is a candidate, not listed as variable in the
  catalogues we asked, and very likely known to specialists.
- Not "new" or "erupted" about the Serpens South star: it came back from a dip.
- Not "every frame is one photo": each frame is a stack of the exposures from one visit.
- Not "only after summing" for WISE 0855.
- Not "S/N 5, 19, 27" or "within 1.3 arcseconds" for WISE 0855.
- Not "2.5 times" for RW Aurigae, and not "flux" or "brightness in physical units" for R Draconis
  (relative brightness from the star's outer light).
- Not a brightness claim from two ordinary frames; use the difference view or the chart.
- Not that the practice object is real. It is a simulation, and the banner stays in view.

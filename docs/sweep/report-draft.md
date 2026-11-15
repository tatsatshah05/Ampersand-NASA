# NOT SENT. A PERSON MUST DO PART ONE FIRST.

Nothing in this file has been sent, filed or posted anywhere. No account was made and no form was filled.
This is a draft for a team member with no astronomy training. It is built from the vetting ruling of
2026-11-15 (`docs/sweep/vetting/ruling.json`); where this file and the ruling differ, the ruling wins. Part one
is the checklist of the wider search for earlier reports made after the ruling, kept in
`docs/sweep/searches-for-earlier-reports.md`. The candidates are explained in plain words in `docs/sweep.md`.

**Order:** do every check in part one for all three candidates, and write down the answers. Only if they all
come back empty, and the team agrees, and a professional astronomer (for example a mentor) has checked the
corrected numbers, may anyone use part two. If any check finds a report at or near a candidate's place, follow
"If any check finds a report" at the end of the checklist: stop, save the page, and tell the team the same day.

Use only these positions (J2000). The sweep's first positions were wrong and must not be used.

| Candidate | RA, Dec (degrees) | RA, Dec (hours and degrees) | Constellation |
|---|---|---|---|
| A | 270.80408, -23.46818 | 18:03:12.98, -23:28:05.4 | Sagittarius |
| B | 253.18038, -44.67697 | 16:52:43.29, -44:40:37.1 | Scorpius |
| C | 241.70906, -52.20564 | 16:06:50.17, -52:12:20.3 | Norma |

---

## Part one: the checks only a person can make

Part one is the checklist in `docs/sweep/searches-for-earlier-reports.md`, section (d). It is the wider search's
checklist for a person (2026-11-15), word for word, with a space after each check for the date, the UTC time,
what was typed and what came back. It is kept in that one place, so that there is never a second, different
list: work through it there, and write every answer there.

Its six steps, in short (the checklist itself has the addresses, the controls and the boxes that say what counts
as the same place):

1. The Astronomer's Telegram, full text, with V7994 (ATel 17419) as the control.
2. NASA ADS, with `bibstem:ATel abs:V7994` as the control.
3. SIMBAD at CDS, once it shows the 2025 nova V7994 Sgr.
4. On the day of publishing: the Transient Name Server (control AT 2025nlr) and CBAT's list of unconfirmed
   transients, again.
5. Optional: AAVSO's campaigns.
6. Optional, low priority: the Lucas et al. 2024 table.

What has already been done towards these steps, and by whom, is written in the checklist (by 2026-11-15 a
person had run only the NASA ADS control and one search for Sagittarius). The same section ends with the three
boxes to tick before anything is filed: the checks done, the team agreed, and a professional astronomer's check.

---

## What a report must not say

These are the ruling's lists ("must_not_say"), for every report, page, slide and post.

**For all three:**

- Not "discovery", "confirmed" or "first ever seen". Not "new", unless followed by "that we found in no
  catalogue or report we checked".
- Not the sweep's first positions.
- Not "nothing in SIMBAD" as proof that nobody has reported it.

**A:**

- Not "a nova" or "a dust-forming nova" as fact.
- Not that A appeared in 2025, not the first write-up's rise factor, and not any 2025 brightness for A: the
  sweep's 2025 numbers and tile images were the light of the star 2MASS 18031245-2327467, 20 arcsec away
  (the withdrawn claims are listed in docs/sweep.md, "What the sweep's first write-up got wrong").
- Not the sweep's D3 and D4 values as A's light.
- Not the first write-up's brightness for the nearest AllWISE source (it is 3.7 mJy, ten times more).
- Not "GLIMPSE does not cover this place" (GLIMPSE II does).
- Not an exact spring-2026 brightness without saying the readings are saturated (neither the sweep's single
  value nor its whole-image limits, which cannot be checked again).
- Not "it rose 1.8 times in three days" or "hydrogen emission detected" as established.

**B:**

- Not that B was there and rising in 2025, nor any 2025 brightness for B: the sweep's 2025 numbers and tile images
  were the star 2MASS 16524412-4440318, 10 arcsec away.
- Not the first write-up's ratio between the visits.
- Not "a thousand times its old brightness" measured against the CatWISE / GLIMPSE / 2MASS / Gaia star 3.5-4.9
  arcsec away, and not "a pre-existing red star erupted": that star is not the source.
- Not the sweep's D3 values as B's light.
- Not "a young star's outburst" or "ice detected" as fact.
- Not "ZTF/Rubin saw nothing" as evidence: they cannot see this field.

**C:**

- Not "a nova" or "[Mg IV] detected" as fact.
- Not "a flare on a young star embedded in a dust clump", or "on a faint star", as the reading: the GLIMPSE
  [4.5] 13.80 star is 6 arcsec from the source and is not it.
- Not the sweep's offsets to the GLIMPSE star and the clump (from the true place they are 6.0-6.2 and
  3.6-3.75 arcsec).
- Not the sweep's two bright tile readings as C's brightness: they fell on emission lines; the continuum was
  about 85-110 mJy.
- Not that C had gone, or nearly gone, by August 2026: emission lines are still detected.
- Not the sweep's faint values as C's own light.
- Not "a flare lasting half a year" as measured: the start is unknown, between 2025-08-19 and 2026-02-19.

---

## Part two: the texts, ready to paste only after part one comes back empty

The searches named in each draft below ("We found no report or catalogue entry ... in ...") are those of the
first round, made for the ruling. Before anything is sent, add the wider search's and the person's own checks
from `docs/sweep/searches-for-earlier-reports.md`, as they stand on that day.

How brightness is given: as an AB magnitude, **AB = 8.90 - 2.5 log10(flux in Jy)**, always with its
wavelength. Bigger AB numbers are fainter.

**Transient Name Server.** A report needs a TNS account and a reporting group, and it is public and
permanent. The form's own field names are used below in quotes; the form calls the first detection the
"Discovery date", which is the form's word, not ours. If SPHEREx is not in the instrument list, choose
"Other" and name it in the remarks.

**Astronomer's Telegram.** ATel accepts telegrams only from authors it has registered, so a professional
astronomer must post or co-author it. The title must say "candidate" or "transient", never "discovery".

**The data acknowledgement**, required by IRSA for any published use of SPHEREx data (wording read from IRSA's
SPHEREx page, `https://irsa.ipac.caltech.edu/Missions/spherex.html`, on 2026-11-15):

> This publication makes use of data products from the Spectro-Photometer for the History of the Universe,
> Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory
> and the California Institute of Technology, and is funded by the National Aeronautics and Space
> Administration.

It is usual to add a line crediting the NASA/IPAC Infrared Science Archive (IRSA); take its exact wording from
IRSA's website on the day.

### Candidate A

**Transient Name Server report (draft)**

- "RA": 18:03:12.98 (270.80408). "Dec": -23:28:05.4 (-23.46818). J2000, uncertainty 0.5 arcsec.
- Galactic: l 6.712, b -0.635.
- "Discovery date": 2026-03-20 04:30 UT, the first SPHEREx exposure of 2026 (2026W12_2A_0127_1).
- "Discovery mag": 6.5 +/- 1.3 mJy at 1.10 micrometres = AB 14.37 +/- 0.22 (a fit with the neighbouring star
  modelled; the 3.77 micrometre reading in the same exposure is saturated at the position). At 4.4-5.0
  micrometres the source was 2.4-2.9 Jy (AB 7.7-7.9) during 2026-03-20 to 2026-04-01, from partly saturated
  readings.
- "Last non-detection": 2025-09-10 09:53 UT, below about 14 mJy at 4.4-5.0 micrometres (AB fainter than 13.5).
- "Instrument": SPHEREx (or "Other"). Data: SPHEREx level-2 spectral images from NASA/IPAC IRSA.
- "Host": none.
- "Remarks": In the Galactic plane. Very red. Not detected by NEOWISE in 21 visits from 2014-03 to 2024-03
  (W2 about 4 mJy or less each), by Spitzer GLIMPSE II at [4.5] (under 2.1 mJy, 2005-2006) or by VVV at Ks
  (0.57 mJy or less within 3.2 arcsec, 2010-2019). A steady star, 2MASS 18031245-2327467, lies 20 arcsec away
  and was fitted separately. Nature unknown. Candidate; not confirmed.

**Astronomer's Telegram (draft)**

Title: A bright, very red infrared transient candidate in Sagittarius in SPHEREx images

Authors: [to be filled by the registered professional who posts it, with the team's agreement]

> We report an infrared transient candidate in public SPHEREx level-2 images from NASA/IPAC IRSA, at RA
> 18:03:12.98, Dec -23:28:05.4 (J2000; 270.80408, -23.46818; uncertainty 0.3-0.5 arcsec; l 6.712, b -0.635).
> It was not detected in SPHEREx images of 2025 August 24 to September 10 (below about 10-14 mJy at 4.4-5.0
> micrometres in fits with the nearby star modelled). It was about 2.4-2.9 Jy at 4.4-5.0 micrometres on 2026
> March 20 to April 1 (partly saturated), 0.67-0.80 Jy on 2026 August 25 to September 2, and about 0.4-0.6 Jy
> on 2026 September 22. Fluxes come from point-source fits in which the steady star 2MASS 18031245-2327467, 20
> arcsec away, was fitted separately.
>
> Archival limits at the position: NEOWISE W2 about 4 mJy or less in each of 21 visits (2014-2024), Spitzer
> [4.5] under 2.1 mJy (2005-06), VVV Ks 0.57 mJy or less (2010-2019). The source is point-like, holds one
> position to 0.12 arcsec per exposure, is seen in paired detectors at the same moments, was absent in 2025
> under the same pointing geometry, and does not move; JPL lists no known Solar System body within 54 arcsec.
> We found no report or catalogue entry at this position in the Transient Name Server, AAVSO VSX, ASAS-SN,
> CBAT, Koji Mukai's nova lists, the ZTF brokers ALeRCE, ANTARES and Fink, and ATel titles and keyword
> searches, each checked with a control object that was found; nor in OGLE, KMTNet or six papers, which had
> no control.
>
> The spectrum from 0.75 to 5 micrometres is a smooth, very red continuum, about 880 K in spring and 780-800 K
> in August 2026 without correction for reddening. A possible Brackett-alpha excess at 4.05 micrometres is seen
> in both 2026 visits at 3.5-4.4 sigma; this is tentative. Its nature is unknown: a heavily obscured classical
> nova that formed dust is the most likely reading and a stellar merger the next, but neither is established.
> The Sun was 0.7 degrees from the position on 2025 December 22, so the onset was probably not observable. We
> encourage near-infrared spectroscopy (the source was about K 11 in August 2026; it becomes practical again
> from about mid-February 2027).
>
> [The data acknowledgement above.]

### Candidate B

**Transient Name Server report (draft)**

- "RA": 16:52:43.29 (253.18038). "Dec": -44:40:37.1 (-44.67697). J2000, uncertainty 0.5 arcsec.
- Galactic: l 341.089, b -0.416.
- "Discovery date": 2026-02-26 14:18 UT.
- "Discovery mag": 49.7 +/- 7.3 mJy at 2.42 micrometres = AB 12.16 +/- 0.16.
- "Last non-detection": 2025-09-15 22:09 UT, below 4 mJy at 4.4-5.0 micrometres (AB fainter than 14.9).
- "Instrument": SPHEREx (or "Other"). Data: SPHEREx level-2 spectral images from NASA/IPAC IRSA.
- "Host": none.
- "Remarks": In a star-forming region of the Galactic plane. Not detected by Spitzer at [4.5] (under 0.73 mJy
  in 2004 and under 0.67 mJy in 2012) or by NEOWISE (W2 1.4 mJy or less on 2024-03-09). A steady star, 2MASS
  16524412-4440318, lies 10 arcsec away and was fitted separately. Candidate; not confirmed. Do not use
  exposure 2026W10_1A_0572_4 (detector 5) without correcting its sky coordinates, which the archive has 17
  arcsec off.

**Astronomer's Telegram (draft)**

Title: An infrared transient candidate in a star-forming region in Scorpius in SPHEREx images

Authors: [to be filled by the registered professional who posts it, with the team's agreement]

> We report an infrared transient candidate in public SPHEREx level-2 images from NASA/IPAC IRSA, at RA
> 16:52:43.29, Dec -44:40:37.1 (J2000; 253.18038, -44.67697; uncertainty 0.3 arcsec; l 341.089, b -0.416). It
> was not detected in SPHEREx images of 2025 August 2 to September 15 (3-sigma limit 2.5-4.0 mJy at 4.4-5.0
> micrometres). It was about 0.39-0.42 Jy at 4.4-5.0 micrometres in 2026 March (8-16 March), rising about
> 10 per cent a day, and about 1.0-1.1 Jy on 2026 August 8-25. It was first seen on 2026 February 26 at 49.7
> +/- 7.3 mJy at 2.42 micrometres. Fluxes come from point-source fits in which the steady star 2MASS
> 16524412-4440318, 10 arcsec away, was fitted separately.
>
> Archival limits at the position: Spitzer [4.5] under 0.7 mJy (2004, 2012), NEOWISE W2 1.4 mJy or less
> (2024 March 9). The source is point-like, holds one position to 0.25 arcsec over 93 bright exposures, is
> seen in paired detectors at the same instant and was absent in 2025 under the same pointing geometry; JPL
> lists no known Solar System body near it. We found no report or catalogue entry at the position in the
> Transient Name Server, CBAT, AAVSO VSX and about 40 VizieR catalogues of variables, young stars, masers,
> nebulae and X-ray sources, each checked with a control object that was found; nor in Koji Mukai's nova list,
> ASAS-SN, VizieR's all-catalogue search (no variable, young-star, transient or X-ray entry) or the titles of
> 1,217 ATels, which had no control. ZTF and Rubin cannot see this field.
>
> The August 2026 spectrum is that of warm dust, 567-575 K without correction for reddening. Possible
> features, all tentative: a water-ice dip near 3 micrometres (March), a 20-30 per cent dip at 4.25
> micrometres in three exposures that may be carbon dioxide ice, and possible hydrogen Paschen-alpha and
> Brackett-alpha emission in March in single channels. The position lies in the star-forming complex around
> the young-star group G341.1-0.3, so an outburst of an embedded young star is the most likely reading; a nova
> behind heavy dust and a stellar merger are not excluded. None of this is established. We encourage
> near-infrared spectroscopy at resolving power 2,000 or more (the source was about K 10 in 2026; it becomes
> practical again from about late January 2027) and a 3-5 micrometre spectrum.
>
> [The data acknowledgement above.]

### Candidate C

**Transient Name Server report (draft)**

- "RA": 16:06:50.17 (241.70906). "Dec": -52:12:20.3 (-52.20564). J2000, uncertainty 0.5 arcsec.
- Galactic: l 330.413, b -0.082.
- "Discovery date": 2026-02-19, about 02:55 UT. The first reading, about 54 mJy at 2.53 micrometres, lies near
  the detector edge and is not clean.
- "Discovery mag": use a clean reading. The first clean one in the pixels reviewer's forced fit
  (`docs/sweep/vetting/C/pixels/forced.json`) is 2026-02-22 14:06 UT, exposure 2026W08_2A_0578_1 (detector 4),
  101.7 +/- 1.9 mJy at 3.603 micrometres = AB 11.38 +/- 0.04 (with the 3 per cent calibration term). Give its
  own date and wavelength in the remarks.
- "Last non-detection": 2025-08-19 22:57 UT, below about 3 mJy at 4-5 micrometres (AB fainter than about 15.2).
- "Instrument": SPHEREx (or "Other"). Data: SPHEREx level-2 spectral images from NASA/IPAC IRSA.
- "Host": none.
- "Remarks": In the Galactic plane. Hydrogen emission lines suggest a reddened nova; this is not established.
  Not detected by Spitzer GLIMPSE at [4.5] (under 0.19-0.40 mJy), NEOWISE (under 5 mJy) or VVV (Ks about 0.12
  mJy or less). Candidate; not confirmed.

**Astronomer's Telegram (draft)**

Title: An infrared transient candidate with hydrogen emission lines in Norma in SPHEREx images

Authors: [to be filled by the registered professional who posts it, with the team's agreement]

> We report an infrared transient candidate in public SPHEREx level-2 images from NASA/IPAC IRSA, at RA
> 16:06:50.17, Dec -52:12:20.3 (J2000; 241.70906, -52.20564; uncertainty 0.3-0.5 arcsec; l 330.413, b -0.082).
> Its continuum at 4-5 micrometres was about 0 in 2025 July 30 to August 19 (below about 3 mJy, forced fits
> with 28 neighbouring stars modelled), about 85-110 mJy in 2026 February 19 to March 3, about a third of that
> on 2026 April 9-10, and about 3-5 mJy in 2026 July 28 to September 12, while emission lines are still
> detected. It faded by 0.66-0.78 magnitudes a month at 2-5 micrometres.
>
> In February-March 2026 the spectrum shows strong hydrogen lines (peak channel against the local continuum):
> Paschen-alpha 200-250 against 19-29 mJy, Brackett-alpha 438-519 against 93-103 mJy, Pfund-beta or
> Humphreys-epsilon 311-392 against 88-102 mJy, Brackett-beta 204-205 against 55-68 mJy, Brackett-gamma 71
> against 39 mJy, and also Paschen-beta and Pfund-gamma. In July-September 2026 a line at 4.488-4.492
> micrometres, absent in February, reads 46.6-58.6 mJy against a 2-4 mJy continuum; it is possibly [Mg IV]
> 4.487 micrometres. These identifications are tentative. The continuum's colour temperature in
> February-March was 1,125-1,160 K without correction for reddening.
>
> The source is point-like and holds one position to 0.14-0.22 arcsec. It is not a ghost of the bright Mira
> V345 Nor 7.7 arcmin away: at the predicted ghost positions we measure -0.9 to -0.3 mJy where at least 60 mJy
> would be expected. Archival limits at the position: Spitzer GLIMPSE [4.5] under 0.19-0.40 mJy, NEOWISE under
> 5 mJy (2010-2024), VVV Ks about 0.12 mJy or less (2010-2019). A cold Hi-GAL clump lies 3.6-3.75 arcsec away.
> We found no report at the position in the Transient Name Server, AAVSO VSX, or the titles and opening lines
> of 847 ATels, and no variable or transient entry in VizieR, each checked with a control object that was
> found; nor in CBAT, Koji Mukai's nova list, ASAS-SN or three relevant papers, which had no control.
>
> The emission lines and the fast fade suggest a classical nova hidden behind Galactic dust; an embedded
> young-star outburst is not excluded, given the nearby clump. Neither is established. We encourage
> near-infrared spectroscopy at resolving power 1,000 or more as soon as practical (from about mid-January
> 2027), and a Swift X-ray observation.
>
> [The data acknowledgement above.]

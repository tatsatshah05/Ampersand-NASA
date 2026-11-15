# Earth-reflex stacking: a distant world from one SPHEREx visit

Code: `backend/reflex.py` (entry `reflex_search`), check `scripts/check_reflex.py`, pictures `scripts/plot_reflex.py`,
tests `tests/test_reflex.py`, numbers `docs/reflex/results.json`. Probe scripts the module was rebuilt from:
`docs/reflex/probe/` (text copies, not run).

## The idea in three sentences
A body 50 to a few hundred AU away barely moves on its own, but the Earth moves 2 AU sideways over a few months and
speeds up and slows down even within one 10 to 17 day SPHEREx visit, so the body's path on the sky is bent by a few
to tens of arcseconds, and a straight line cannot imitate that bend. We add up all the exposures of one visit along
every possible bent path (after taking the fixed stars away using the other visits), and the path that gives the
brightest point also tells the distance. Nothing but the pictures is used: the ephemeris of a known body is looked up
only afterwards, to check the answer.

## The proof: Eris, found blind
Eris (a dwarf planet, 95.5 AU from SPHEREx in July 2025). Visit 2025-07-10 to 07-25 (57 usable D1-D3 exposures over
15.35 days). The search was given only a field centre and 0.13 degrees (0.0169 square degrees) around it.

| What | Required | Got |
|---|---|---|
| Strongest track vs JPL Horizons (observer SPHEREx) at the middle of the visit | within 4 arcsec | 1.37 arcsec |
| Signal-to-noise | at least 12 | 14.3 (coarse search 14.7) |
| Any other source in the field | below 8 | next highest 6.8; reversed-Earth best away from Eris 6.4 |
| Distance, 2 sigma interval contains JPL's 95.51 AU, best within 20% | yes | 105 AU, 1 sigma 91 to 111, 2 sigma 83 to 154 |
| Infinite distance rejected | delta S^2 at least 25 | 46 (about 6.8 sigma) |
| Drift within 0.5 arcsec/day of JPL's apparent linear drift (3.91, -3.61) | yes | (4.12, -3.37) |

Run `python scripts/check_reflex.py eris`: it exits with code 1 if any line fails. Picture: `docs/reflex/eris_profile.png`
(S/N against 1/distance; the left half is the Earth's motion reversed, which no real body follows).
The probe scripts reported S/N 16.4 and delta S^2 61 with the same method; the rebuilt module gives 14.3 and 46 (a
different noise calibration region and a drift box now centred on the reflex rate). The rebuilt numbers are the ones
to quote.

Spectrum from the same exposures (matched-filter flux along the blind track): D1 0.105, D2 0.067, D3 0.048 mJy, each
significant (S/N 11, 8, 6.5). It falls toward longer wavelength, as expected for an icy body with methane. The earlier
aperture photometry at JPL's places gave 0.187 / 0.096 / 0.057 mJy: the Gaussian matched filter is 15 to 45 per cent
lower in this field and its flux scale is not calibrated here, so quote the shape, not the absolute values. D4 to D6 were
not searched.

## What was searched
D1-D3, a 0.13 degree square, distances 50 AU outwards (1/d from -0.02 to +0.02 per AU, step 0.0015; about 1000 AU
and beyond cannot be told from "far"), drift box centred on the Earth's reflex rate for each 1/d with a radius of
1.5 times a circular orbit's speed plus 1 arcsec/day (24,439 trials for Eris's field). The choices were written in the
module docstring before the known answer was scored.

## Controls and how each came out
- Earth's motion reversed (1/d < 0): best 6.4 in the Eris field away from Eris. Passed.
- Straight-line-only (1/d = 0): 12.6 vs 14.3 at the best distance (delta S^2 46). Passed.
- Other visits at the place: Eris not there (-0.002 and -0.004 mJy, errors 0.004). Passed.
- Faint end, Sedna (visit 2025-08-18 to 09-04, V about 20.8): not found blind. Forced along JPL's track: combined S/N
  7.5 (D1 3.9, D2 5.0, D3 3.1) with this module, below the threshold of 8 and, with 24,000 trials to look through, not
  findable blind. The probe's number was about 5; the module is a little more sensitive, not less. Passed as a limit.
- Fixed stars that do not subtract cleanly give strong false peaks: 10.2 in the Sedna field and 22 and 21 in a second
  field (190.0, +5.0). All were removed by the "still there in another visit" test (the same place is 0.07 to 0.34 mJy in
  the other visits). The raw S/N threshold of 8 is therefore NOT a clean decision line by itself: the other-visit test
  does the work. Any new candidate must pass it.
- Field centre moved 2 arcmin east and 1.5 north (so the result is not "we looked where it was"): Eris is still the
  strongest source, 2.0 arcsec from JPL, S/N 15.6 (D1 13.4, D2 9.8, D3 7.0), drift (3.85, -3.44), delta S^2 vs infinity 55.
  But the distance comes out 118 AU, 23% above JPL's 95.5; its 1 sigma interval (105 to 118) does NOT contain the truth, its
  2 sigma interval (91 to 143) does. Two further lines fail the acceptance test: a reversed-Earth peak of 8.4 at the
  edge of the field (48, -216 arcsec from the centre, edge of a 234 arcsec half-width) is above the threshold. So: the
  detection and the place are robust to the field centre; the distance carries a systematic of 10 to 25% high, which
  the quoted 1 sigma interval does not cover. Quote the 2 sigma interval and "about 100 to 120 AU for a body that JPL
  puts at 95.5", never a precise distance.
- Shuffled exposure times in blank fields: see `results.json` key `blank_fields` if present; the runs were slow on a
  heavily loaded machine and may be incomplete. Not done: a threshold from a proper blank-field distribution (three
  to five fields), Makemake (the old box did not cover it; the new reflex-centred box is untested on it).

## Where the literature stands (searched 2026-11-14)
Searched: "SPHEREx trans-Neptunian / Kuiper belt", "SPHEREx Planet Nine shift-and-stack", "SPHEREx Eris Makemake Sedna
Haumea", "SPHEREx solar system moving targets pipeline". Found: SPHEREx spectra of known asteroids and a projection of
Centaur spectra, nothing on a blind moving-object search. The technique itself is old: Bernstein et al. 2004, Rice and
Laughlin 2020 (TESS), the ACT Planet 9 stack, heliostack (HST), ZTF digital tracking, KBMOD. What we found no sign of:
it applied to SPHEREx, or a 0.75-2.4 micrometre spectrum of the detected body from the same exposures. That is "we do
not know of this having been done with SPHEREx data", not "never done".

## Limits
- One visit reaches about V 19 for a grey body (stacked mean flux limit 0.03 mJy in D1-D3). That is about 2 magnitudes
  shallower than Pan-STARRS (V 21.5), than the TESS shift-stack and than Planet Nine's predicted brightness. This does
  not test Planet Nine or Planet X.
- A limit is quoted with its area: 0.0169 square degrees per field. "No Earth-size body within about 200 AU" would need
  an albedo and colour assumption (0.3 to 0.5, grey) and holds only in that area; it is not computed here.
- Tested positive on one object (Eris), one field, low ecliptic latitude, sparse sky. Not tested in crowded or Galactic-plane
  fields, where fixed-sky subtraction leaves residuals.
- Distance needs a visit of at least 8 days; shorter ones give a detection only. Leverage goes as duration squared.
  The 1 sigma interval is too narrow (it missed the truth when the field was shifted); quote the 2 sigma interval
  (83 to 154 AU for Eris at the original centre, 91 to 143 AU shifted).
- Peaks at the very edge of the field (within about 20 arcsec) are the weakest part of the search; the 8.4
  reversed-Earth peak of the shifted run is one. The module does not yet drop them.
- When the exposure list for a patch spans more than one real visit (field 190, +5: 43 days), the "visit" is two
  merged observations and the distance leverage is meaningless. The default picks the longest group; check
  `visit.duration_days`.
- JPL's small-body identification (`sb_ident`) did not list Eris at all in its own field (a 0.12 degree
  search at the middle of the visit returned an empty list), so "no known body nearby" from it is weak for distant bodies. Check the Minor Planet Center too.
- Bodies nearer than 50 AU are not searched.

## What would confirm a candidate
A second visit: the fit from one visit predicts where the body is in the next (Eris jumps about 1.2 degrees), and a
body at 100 AU should be at that place, with a consistent distance. Then CatWISE and optical archives at that place.

## Words for the demo
Say: "Without being told where Eris is, one 15-day SPHEREx visit finds it 1.4 arcsec from where JPL says it is (2.0 with
the field shifted), and the bend in its path puts it at about 105 to 118 AU (JPL: 95.5; 2 sigma 83 to 154). A body infinitely far away is ruled out
at about 6.8 sigma. We do not know of this having been done with SPHEREx data."
Do not say: discovery, first, new planet, Planet Nine search or test, "finds Planet X", that it beats WISE or Pan-STARRS,
that the distance is precise, or that it works anywhere in the sky (one field has passed).

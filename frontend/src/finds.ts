// The three candidates our blind sweep of the Milky Way's plane found (docs/sweep.md), as the
// referee ruled on them after four independent reviews each (docs/sweep/vetting/ruling.json). Every
// word and number here is the ruling's or the review it rests on: positions are the reviewers'
// corrected ones (never the sweep's), and `allowed` is the one sentence the referee allows a public
// page to show about each, copied verbatim. They are candidates: found in no catalogue or report we
// checked, and confirmed by nobody. Nothing has been reported anywhere.
//
// docs/sweep.md quotes every sentence below word for word, in "What the app shows about each
// candidate" (finds.test.ts checks it), so the page and the write-up cannot drift apart.
import { skyOffsetArcsec } from './api'
import type { SearchTarget } from './components/SearchBar'

export interface Find {
  key: 'A' | 'B' | 'C'
  /** The name on the page and on its button. */
  name: string
  constellation: string
  /** Degrees, ICRS: the mean of the reviewers' fits (each within 0.16 arcsec of it). */
  ra: number
  dec: number
  /** The detector whose pictures show it best (see the comment on each). */
  det: number
  /** The referee's allowed sentence, verbatim. */
  allowed: string
  /** What it probably is, hedged, with the evidence for that. Expert, and the "About this change" popover. */
  probably: string
  /** Its brightness in each visit from the reviewers' fits with the neighbours modelled, with their ranges. */
  brightness: string
  /** The steady star (or crowd) near it in the picture, so that nobody takes it for the candidate. */
  neighbour: string
  /** Where SPHEREx's last picture without it and first picture with it were taken, over all six detectors. */
  dates: string
  /** What was searched, which searches had a control object, and what a person must still search. */
  checked: string
  /** Why it is held at one place (in place of a motion, which nobody gave it). */
  place: string
  /**
   * For the brightness, spectrum and search tools, which measure in a fixed circle with no
   * neighbour modelled: what that circle holds at this place when the candidate is faint.
   */
  circle: string
  /**
   * The dates (UT, ISO, [from, to)) when the circle's light at this place is not the candidate's:
   * before it appeared, and for C again once its continuum had faded below its neighbours' light.
   */
  quiet: readonly (readonly [string, string])[]
  /** Visits of its own detector whose picture is spoiled at this place, and why (C only). */
  spoiled?: { visits: readonly number[]; note: string }
  /** The last SPHEREx exposure in which it was not seen, and the first in which it was (UT). */
  lastNotSeen: string
  firstSeen: string
  /** Where the evidence is written up. */
  evidence: string
  /**
   * The one sentence a public page may show about the second, wider search for earlier reports of it
   * (2026-11-15: more than 30 catalogues and alert lists, each tested on a known object), word for word:
   * that search's `what_can_be_said` for this candidate (docs/sweep.md quotes it).
   */
  reportSearch: string
  /** Where it stands, said as it is. One edit here changes it on every page, the day a person files a report. */
  status: string
}

/** Where all three stand today: nobody has confirmed them, and nothing has been sent to anyone. */
export const NOT_REPORTED = 'Not confirmed. Not yet reported to astronomers.'

export const FINDS: readonly Find[] = [
  {
    key: 'A',
    name: 'Candidate A',
    constellation: 'Sagittarius',
    ra: 270.80408,
    dec: -23.46818,
    // At 4.4 to 5.0 micrometres it went from about 0 to 2.4 to 2.9 Jy (partly saturated), and the
    // 437 mJy star 20 arcsec away stays steady; the referee's numbers are for this detector, and
    // the page's own measure sees it most strongly here (521 times the scatter in spring 2026,
    // against 273 in detector 5).
    det: 6,
    allowed:
      'Candidate A, an infrared source in Sagittarius, was too faint to detect in SPHEREx images from late August and early September 2025 and was more than 100 times brighter by late March 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.',
    probably:
      'Probably a dusty eruption of unknown kind, perhaps a nova hidden behind dust: its light is a smooth, very red glow. Not established.',
    brightness:
      "At 4.4–5.0 micrometres, in the reviewers' fits with the neighbouring star modelled: not detected on 24 August–10 September 2025 (below about 10–14 mJy), 2,419–2,926 mJy on 20 March–1 April 2026 (partly saturated) and 670–803 mJy on 25 August–2 September 2026.",
    neighbour:
      'The bright star about 20 arcseconds to the north-north-west, seen in every visit, is a steady neighbour, 2MASS 18031245-2327467 (437 mJy at 4.6 micrometres), not Candidate A.',
    dates:
      "Over all six detectors, SPHEREx's last picture without it was taken on 10 September 2025, and its first picture with it on 20 March 2026.",
    checked:
      "Searched on 15 November 2026, each with a control object that was found: the Transient Name Server, AAVSO VSX, ASAS-SN, CBAT, Koji Mukai's nova lists, the ZTF brokers and 942 Astronomer's Telegram titles. Also searched: six papers, OGLE and KMTNet. Not yet searched: the telegrams' full text, NASA ADS and SIMBAD, which was down that day.",
    place:
      'Held at its corrected place: no catalogue gives it a motion, and its spring and August 2026 positions agree to 0.4 arcseconds.',
    circle:
      "At Candidate A's place, in 2025 this measuring circle (15.4 arcseconds in radius) held only light from the steady star 2MASS 18031245-2327467, 20 arcseconds away; Candidate A itself was not detected. Those exposures are left out here, so nothing below is a 2025 brightness of Candidate A.",
    quiet: [['0000-01-01', '2026-03-20']],
    lastNotSeen: '2025-09-10 09:53',
    firstSeen: '2026-03-20 04:30',
    evidence: 'docs/sweep.md',
    reportSearch:
      "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate A's position in Sagittarius; some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it.",
    status: NOT_REPORTED,
  },
  {
    key: 'B',
    name: 'Candidate B',
    constellation: 'Scorpius',
    ra: 253.18038,
    dec: -44.67697,
    // About 0 in 2025, about 400 mJy in March and 1,000 to 1,090 mJy in August 2026 at 4.4 to 5.0
    // micrometres; the 40 mJy star 10 arcsec away stays steady. The page's own measure: 282 and
    // 619 times the scatter here, against 107 and 310 in detector 5.
    det: 6,
    allowed:
      'Candidate B, an infrared source in Scorpius, was too faint to detect in SPHEREx images from August and September 2025, had appeared by late February 2026 and was at least 250 times brighter by August 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.',
    probably:
      'Probably an outburst of a young star still inside its birth cloud: it lies in a star-forming complex, in a known group of young stars. Not established.',
    brightness:
      "At 4.4–5.0 micrometres, in the reviewers' fits with the neighbouring star modelled: not detected on 2 August–15 September 2025 (3-sigma limit 2.5–4.0 mJy), 393–424 mJy in March 2026 (8–16 March, rising about 10% a day) and 1,006–1,089 mJy on 8–25 August 2026.",
    neighbour:
      'The faint star 10 arcseconds to the north-east, seen in every visit, is a steady neighbour, 2MASS 16524412-4440318 (40 mJy at 4.6 micrometres), not Candidate B.',
    dates:
      "Over all six detectors, SPHEREx's last picture without it was taken on 15 September 2025, and its first picture with it on 26 February 2026, in detector 4 (2.42 micrometres).",
    checked:
      "Searched on 15 November 2026, each with a control object that was found: the Transient Name Server, CBAT, AAVSO VSX and about 40 catalogues of variable stars, young stars, masers, nebulae and X-ray sources. Also searched: Koji Mukai's nova list, ASAS-SN, VizieR, 1,217 Astronomer's Telegram titles and two papers. Not yet searched: the telegrams' full text, NASA ADS and SIMBAD, which was down that day.",
    place:
      'Held at its corrected place: no catalogue gives it a motion, and its March and August 2026 positions agree to 0.3 arcseconds.',
    circle:
      "At Candidate B's place, in 2025 this measuring circle (15.4 arcseconds in radius) held only light from the steady star 2MASS 16524412-4440318, 10 arcseconds away; Candidate B itself was not detected. Those exposures are left out here, so nothing below is a 2025 brightness of Candidate B.",
    quiet: [['0000-01-01', '2026-02-26']],
    lastNotSeen: '2025-09-15 22:09',
    firstSeen: '2026-02-26 14:18',
    evidence: 'docs/sweep.md',
    reportSearch:
      "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate B's position in Scorpius; some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it.",
    status: NOT_REPORTED,
  },
  {
    key: 'C',
    name: 'Candidate C',
    constellation: 'Norma',
    ra: 241.70906,
    dec: -52.20564,
    // Detector 6, where the reviewers' forced fit reads -0.5, 109.6 and 4.6 mJy in its three main
    // visits: the page's own measure then reads "not seen", "clear" (129 mJy) and "marginal" in
    // August 2026, which agrees with the ruling (still faintly there, its emission lines persist).
    // Detector 5 called August 2026 "not seen" (2.6 mJy in the reviewers' fit), which read as C having
    // gone, which the ruling forbids. Detector 6 also has visit 3, two April
    // 2026 exposures partly spoiled by cosmic-ray hits: the page says so (`spoiled`).
    det: 6,
    allowed:
      "Candidate C, an infrared source in Norma, was too faint to detect in SPHEREx images from July and August 2025, was at least 30 times brighter in late February and early March 2026 and had faded again by August 2026; its light hints at a nova hidden behind the Milky Way's dust, but it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.",
    probably:
      'Probably a nova hidden behind dust: in February and March 2026 its light was dominated by very strong hydrogen emission lines (Brackett-alpha 438–519 mJy against a continuum of 93–103 mJy). Not established.',
    brightness:
      "Its continuum at 4–5 micrometres, in the reviewers' fits with 28 neighbours modelled: about 0 on 30 July–19 August 2025 (not detected), about 85–110 mJy on 19 February–3 March 2026, about a third of that on 9–10 April 2026 and about 3–5 mJy in July–September 2026, while its emission lines persist.",
    neighbour:
      'The field is crowded: the stars around it are other stars, not Candidate C; the nearest catalogued ones, 1.9 and 2.2 arcseconds away, are faint and steady.',
    dates:
      "Over all six detectors, SPHEREx's last picture without it was taken on 19 August 2025, and its first picture with it on 19 February 2026, in detector 4 (2.53 micrometres).",
    checked:
      "Searched on 15 November 2026, each with a control object that was found: the Transient Name Server, AAVSO VSX, VizieR and the titles and opening lines of 847 Astronomer's Telegrams. Also searched: CBAT, Koji Mukai's nova list, ASAS-SN and three papers. Not yet searched: the telegrams' full text, NASA ADS, X-ray records and SIMBAD, which was down that day.",
    place:
      'Held at its corrected place: no catalogue gives it a motion, and its exposures bright in emission lines in August 2026 put it at the same place as in February.',
    circle:
      "At Candidate C's place, in 2025 and again from July 2026 this measuring circle (15.4 arcseconds in radius) held more light from neighbouring stars than from Candidate C, whose continuum was about 0 in 2025 and about 3–5 mJy in July–September 2026. Those exposures are left out here.",
    quiet: [
      ['0000-01-01', '2026-02-19'],
      ['2026-07-01', '9999-12-31'],
    ],
    spoiled: {
      visits: [3],
      note: 'Visit 3 (April 2026) is two exposures partly spoiled by cosmic-ray hits, so the page cannot say how clearly it is seen; the reviewers measured about a third of its February brightness then.',
    },
    lastNotSeen: '2025-08-19 22:57',
    firstSeen: '2026-02-19 02:55',
    evidence: 'docs/sweep.md',
    reportSearch:
      "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate C's position in Norma (two ordinary variable stars catalogued before 2025 lie 12 and 15 arcseconds away and are different stars); some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it.",
    status: NOT_REPORTED,
  },
]

/** Said after a candidate's `circle` note in the tools: where the right numbers are. */
export const FIND_EVIDENCE =
  "The values left are this circle's light, its neighbours' included; the reviewers' fits, with the neighbours modelled, are in the project's write-up, docs/sweep.md."

/**
 * Where a candidate's button takes the page: its corrected position, held still (a motion of
 * zero), so that /api/frames measures it at that one place in every visit. Without a motion it
 * measures the brightest spot near the centre, which in 2025 was a neighbouring star for all three.
 */
export function findTarget(find: Find): SearchTarget {
  return { ra: find.ra, dec: find.dec, name: find.name, pmra: 0, pmdec: 0, parallax: null, det: find.det }
}

/** How close a position must be to a candidate's to be that candidate, in arcseconds. */
export const FIND_RADIUS_ARCSEC = 5

/** How far a candidate's light reaches into another place's 15.4-arcsecond measuring circle, with room to spare. */
export const FIND_REACH_ARCSEC = 25

/** How far (ra, dec) is from a candidate, in arcseconds. */
export function arcsecFrom(find: Find, ra: number, dec: number): number {
  const { east, north } = skyOffsetArcsec(find, { ra, dec })
  return Math.hypot(east, north)
}

/** The candidate within 5 arcseconds of (ra, dec), or null. */
export function findAt(ra: number, dec: number): Find | null {
  if (!Number.isFinite(ra) || !Number.isFinite(dec)) return null
  return FINDS.find((find) => arcsecFrom(find, ra, dec) <= FIND_RADIUS_ARCSEC) ?? null
}

/** The candidate whose light reaches a measuring circle at (ra, dec) (within 25 arcseconds), and how far it is. */
export function findNear(ra: number, dec: number): { find: Find; arcsec: number } | null {
  if (!Number.isFinite(ra) || !Number.isFinite(dec)) return null
  for (const find of FINDS) {
    const arcsec = arcsecFrom(find, ra, dec)
    if (arcsec <= FIND_REACH_ARCSEC) return { find, arcsec }
  }
  return null
}

/** Whether a selection is one of our candidates held still at its place, as its button asks for it. */
export function isHeldFind(s: { ra: number; dec: number; pmra: number | null; pmdec: number | null }): boolean {
  return findAt(s.ra, s.dec) !== null && s.pmra === 0 && s.pmdec === 0
}

/** Whether an exposure taken at `date` (ISO, UT) is in one of the candidate's quiet windows. */
export function inQuiet(find: Find, date: string): boolean {
  return find.quiet.some(([from, to]) => date >= from && date < to)
}

/**
 * The sentence for a tool measuring at (ra, dec) near a candidate but not at it: the candidate's
 * light reaches this circle, so a change here may be the candidate's, not this place's.
 */
export function nearFindSentence(find: Find, arcsec: number): string {
  return `${find.name}, ${Math.round(arcsec)} arcseconds from here, appeared between 2025 and 2026 and its light reaches this measuring circle, so a change here may be ${find.name}'s light, not this place's.`
}

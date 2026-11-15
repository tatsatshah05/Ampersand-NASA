// The three candidates our blind sweep of the Milky Way's plane found (docs/sweep.md), as the
// referee ruled on them after four independent reviews each. Every word and number here is the
// ruling's: positions are the reviewers' corrected ones (never the sweep's), and `allowed` is
// the one sentence the referee allows a public page to show, copied verbatim. They are
// candidates: found in no catalogue or report we checked, and confirmed by nobody. Nothing has
// been reported anywhere.
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
  /** What it probably is, hedged, with the one strongest piece of evidence for that. */
  probably: string
  /** The last SPHEREx exposure in which it was not seen, and the first in which it was (UT). */
  lastNotSeen: string
  firstSeen: string
  /** Where the evidence is written up. */
  evidence: string
}

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
      'Probably a dusty eruption of unknown kind, perhaps a nova hidden behind dust: its light is a smooth, very red glow.',
    lastNotSeen: '2025-09-10 09:53',
    firstSeen: '2026-03-20 04:30',
    evidence: 'docs/sweep.md',
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
      'Probably an outburst of a young star still inside its birth cloud: it lies in a star-forming complex, in a known group of young stars.',
    lastNotSeen: '2025-09-15 22:09',
    firstSeen: '2026-02-26 14:18',
    evidence: 'docs/sweep.md',
  },
  {
    key: 'C',
    name: 'Candidate C',
    constellation: 'Norma',
    ra: 241.70906,
    dec: -52.20564,
    // At 4 to 5 micrometres its continuum went from about 0 to about 85 to 110 mJy and back to
    // about 3 to 5 mJy; detectors 5 and 6 see it alike (forced fits 112.9 and 109.6 mJy at its
    // brightest), but detector 6 also has a visit of two April 2026 exposures spoiled by
    // cosmic-ray "snowballs" right beside it, so detector 5's three clean visits show it best.
    det: 5,
    allowed:
      "Candidate C, an infrared source in Norma, was too faint to detect in SPHEREx images from July and August 2025, was at least 30 times brighter in late February and early March 2026 and had faded again by August 2026; its light hints at a nova hidden behind the Milky Way's dust, but it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.",
    probably:
      'Probably a nova hidden behind dust: in February and March 2026 its light was dominated by very strong hydrogen emission lines.',
    lastNotSeen: '2025-08-19 22:57',
    firstSeen: '2026-02-19 02:55',
    evidence: 'docs/sweep.md',
  },
]

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

/** The candidate within 5 arcseconds of (ra, dec), or null. */
export function findAt(ra: number, dec: number): Find | null {
  if (!Number.isFinite(ra) || !Number.isFinite(dec)) return null
  for (const find of FINDS) {
    const { east, north } = skyOffsetArcsec(find, { ra, dec })
    if (Math.hypot(east, north) <= FIND_RADIUS_ARCSEC) return find
  }
  return null
}

// The three candidates as data: the referee's corrected positions and allowed sentences, and the
// words a public page must never use about them.
import { describe, expect, it } from 'vitest'
import { FINDS, findAt } from './finds'

const byKey = Object.fromEntries(FINDS.map((f) => [f.key, f]))

describe('the three candidates', () => {
  it('are A, B and C, named as candidates, at the corrected positions (never the sweep’s)', () => {
    expect(FINDS.map((f) => [f.key, f.name, f.constellation, f.ra, f.dec])).toEqual([
      ['A', 'Candidate A', 'Sagittarius', 270.80408, -23.46818],
      ['B', 'Candidate B', 'Scorpius', 253.18038, -44.67697],
      ['C', 'Candidate C', 'Norma', 241.70906, -52.20564],
    ])
    // The sweep's positions for A and C were 3 arcsec off: they are not the candidates' places any more.
    expect(byKey.A.ra).not.toBe(270.80362)
    expect(byKey.C.dec).not.toBe(-52.20484)
  })

  it('carry the referee’s allowed sentence word for word', () => {
    expect(byKey.A.allowed).toBe(
      'Candidate A, an infrared source in Sagittarius, was too faint to detect in SPHEREx images from late August and early September 2025 and was more than 100 times brighter by late March 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.',
    )
    expect(byKey.B.allowed).toBe(
      'Candidate B, an infrared source in Scorpius, was too faint to detect in SPHEREx images from August and September 2025, had appeared by late February 2026 and was at least 250 times brighter by August 2026; it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.',
    )
    expect(byKey.C.allowed).toBe(
      "Candidate C, an infrared source in Norma, was too faint to detect in SPHEREx images from July and August 2025, was at least 30 times brighter in late February and early March 2026 and had faded again by August 2026; its light hints at a nova hidden behind the Milky Way's dust, but it is a candidate that we found in no catalogue or report we checked, and nobody has confirmed it yet.",
    )
  })

  it('never use the words the ruling forbids', () => {
    for (const f of FINDS) {
      const all = [f.name, f.allowed, f.probably].join(' ')
      expect(all).not.toMatch(/discover|confirmed it\b(?! yet)|first ever|ninefold|9 times|appears in 2025|ratio 35|rises steadily/i)
      // "new" only ever with the qualifier, and these sentences do not use it at all.
      expect(all).not.toMatch(/\bnew\b/i)
      // What it is, only ever hedged.
      expect(f.probably).toMatch(/^Probably /)
      expect(f.probably).not.toMatch(/\b(is|was) a (nova|young star)\b/i)
    }
  })

  it('say when each was last not seen and first seen, and where the evidence is', () => {
    expect(FINDS.map((f) => [f.lastNotSeen.slice(0, 10), f.firstSeen.slice(0, 10)])).toEqual([
      ['2025-09-10', '2026-03-20'],
      ['2025-09-15', '2026-02-26'],
      ['2025-08-19', '2026-02-19'],
    ])
    for (const f of FINDS) expect(f.evidence).toBe('docs/sweep.md')
  })
})

describe('findAt', () => {
  it('finds a candidate at its own place and within 5 arcseconds of it', () => {
    expect(findAt(253.18038, -44.67697)?.key).toBe('B')
    // 4.0 arcsec north of C, and 4.0 arcsec east of A (on the sky, so the RA step is divided by cos dec).
    expect(findAt(241.70906, -52.20564 + 4 / 3600)?.key).toBe('C')
    expect(findAt(270.80408 + 4 / 3600 / Math.cos((23.46818 * Math.PI) / 180), -23.46818)?.key).toBe('A')
  })
  it('finds nothing further than 5 arcseconds away, or elsewhere in the sky', () => {
    expect(findAt(253.18038, -44.67697 + 6 / 3600)).toBeNull()
    // The sweep's own position for A was 3.0 arcsec off: still A. Barnard's Star is nothing.
    expect(findAt(270.80362, -23.46745)?.key).toBe('A')
    expect(findAt(269.446267, 4.768222)).toBeNull()
    expect(findAt(Number.NaN, 0)).toBeNull()
  })
})

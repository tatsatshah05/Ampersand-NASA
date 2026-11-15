// The three candidates as data: the referee's corrected positions and allowed sentences, and the
// words a public page must never use about them.
import { describe, expect, it } from 'vitest'
import { CANDIDATE_LINE, FIND_EVIDENCE, FINDS, findAt, findNear, isHeldFind } from './finds'
import { MAYBE_PLAIN, NEIGHBOUR_PLAIN } from './findsInfo'
import lcB from './fixtures/lightcurve/find_b_d6.json'
import searchB from './fixtures/search/find_b.json'
import { guardLightcurve, leftOut, NEIGHBOURS_LIGHT, summarise, type LightcurveResponse } from './lightcurve'
import { isCandidate, markFinds, verdictSentence, type SearchStatus } from './search'
import { guardSpectrum, type SpectrumResponse } from './spectrum'
import { TIMES_SCATTER_NOTE } from './wording'

const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
// The sweep's first positions, withdrawn: read from the vetting folder, the only place they are kept.
const vetted = JSON.parse(readFileSync(new URL('../../docs/sweep/vetting/candidates.json', import.meta.url), 'utf8')) as {
  candidates: { label: string; first_run_position_withdrawn: [number, number] }[]
}
const withdrawn = Object.fromEntries(vetted.candidates.map((c) => [c.label, c.first_run_position_withdrawn]))
const byKey = Object.fromEntries(FINDS.map((f) => [f.key, f]))

describe('the three candidates', () => {
  it('are A, B and C, named as candidates, at the corrected positions (never the sweep’s)', () => {
    expect(FINDS.map((f) => [f.key, f.name, f.constellation, f.ra, f.dec])).toEqual([
      ['A', 'Candidate A', 'Sagittarius', 270.80408, -23.46818],
      ['B', 'Candidate B', 'Scorpius', 253.18038, -44.67697],
      ['C', 'Candidate C', 'Norma', 241.70906, -52.20564],
    ])
    // The sweep's positions for A and C were 3 arcsec off: they are not the candidates' places any more.
    for (const f of FINDS) expect([f.ra, f.dec]).not.toEqual(withdrawn[f.key])
    expect(byKey.A.ra).not.toBe(withdrawn.A[0])
    expect(byKey.C.dec).not.toBe(withdrawn.C[1])
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
    expect(findAt(withdrawn.A[0], withdrawn.A[1])?.key).toBe('A')
    expect(findAt(269.446267, 4.768222)).toBeNull()
    expect(findAt(Number.NaN, 0)).toBeNull()
  })
})

// ---- every other sentence about them, and the tools that measure them ------------------------

/** The write-up, with its quotation marks and line breaks undone, so a sentence can be found whole. */
const flat = (s: string) => s.replace(/\n>\s?/g, ' ').replace(/\s+/g, ' ')
const writeUp = flat(readFileSync(new URL('../../docs/sweep.md', import.meta.url), 'utf8'))

/** Every sentence the page can show about one candidate (finds.ts and findsInfo.ts). */
const sentencesOf = (f: (typeof FINDS)[number]) => [
  f.allowed,
  f.probably,
  f.brightness,
  f.neighbour,
  f.dates,
  f.checked,
  f.place,
  f.circle,
  ...(f.spoiled ? [f.spoiled.note] : []),
  NEIGHBOUR_PLAIN[f.key],
  MAYBE_PLAIN[f.key],
]

describe('every sentence about them', () => {
  it('is quoted word for word in docs/sweep.md, so the page and the write-up cannot drift apart', () => {
    for (const f of FINDS) for (const s of sentencesOf(f)) expect(writeUp, s).toContain(flat(s))
    for (const s of [FIND_EVIDENCE, TIMES_SCATTER_NOTE, CANDIDATE_LINE]) expect(writeUp, s).toContain(s)
  })

  it('Beginner’s one line under the table claims nothing the allowed sentences do not', () => {
    expect(CANDIDATE_LINE).toBe('A candidate: we found it in no catalogue or report we checked, and nobody has confirmed it yet.')
    expect(CANDIDATE_LINE).not.toMatch(/discover|first ever|\bnew\b|nova|young star|counterpart|\bconfirmed\b(?! it yet)/i)
    for (const f of FINDS) expect(f.allowed).toMatch(/candidate/i)
  })

  it('breaks none of the ruling’s "must not say"', () => {
    for (const f of FINDS) {
      const all = sentencesOf(f).join(' ')
      expect(all).not.toMatch(/discover|first ever|ninefold|9 times|appears in 2025|ratio 35|rises steadily|back to nearly nothing|counterpart/i)
      expect(all).not.toMatch(/\bnew\b/i)
      expect(all).not.toMatch(/\b(is|was) a (nova|young star)\b/i)
      expect(all).not.toMatch(/\bconfirmed\b(?! it yet| by nobody)/i)
      // The sweep's withdrawn positions.
      for (const [ra, dec] of Object.values(withdrawn)) expect(all).not.toMatch(new RegExp(`${String(ra).replace('.', '\\.')}|${String(Math.abs(dec)).replace('.', '\\.')}`))
    }
  })

  it('gives no 2025 brightness: only "not detected", with the reviewers’ limit', () => {
    expect(byKey.A.brightness).toContain('not detected on 24 August–10 September 2025 (below about 10–14 mJy)')
    expect(byKey.B.brightness).toContain('not detected on 2 August–15 September 2025 (3-sigma limit 2.5–4.0 mJy)')
    expect(byKey.C.brightness).toContain('about 0 on 30 July–19 August 2025 (not detected)')
  })
})

describe('the places near them', () => {
  it('findNear: a candidate whose light reaches a measuring circle within 25 arcsec', () => {
    // The steady star 10 arcsec north-east of B, where the patch search found a "change".
    expect(findNear(253.18377, -44.675508)?.find.key).toBe('B')
    expect(findNear(253.18377, -44.675508)?.arcsec).toBeCloseTo(10.1, 1) // the ruling: 10.0-10.2 arcsec
    expect(findNear(269.446267, 4.768222)).toBeNull()
  })
  it('isHeldFind: a candidate at its place with no motion, as its button asks', () => {
    expect(isHeldFind({ ra: 253.18038, dec: -44.67697, pmra: 0, pmdec: 0 })).toBe(true)
    expect(isHeldFind({ ra: 253.18038, dec: -44.67697, pmra: null, pmdec: null })).toBe(false)
    expect(isHeldFind({ ra: 269.446267, dec: 4.768222, pmra: 0, pmdec: 0 })).toBe(false)
  })
})

describe('the tools at a candidate (the server’s real answers at B)', () => {
  const lc = lcB as unknown as LightcurveResponse
  it('the brightness tool leaves out the 2025 exposures, whose circle held the neighbour’s light, and says why', () => {
    // Unguarded, visit 1 has values: the light of the star 2MASS 16524412-4440318, 10 arcsec away.
    expect(lc.bins!.some((b) => b.points.some((p) => p.epoch === 1 && p.flux_mjy != null))).toBe(true)
    expect(summarise(lc, 'flux').map((s) => [s.firstEpoch, s.lastEpoch])).toEqual([[1, 3]])
    const guarded = guardLightcurve(lc, lc)
    expect(guarded.bins!.every((b) => b.points.every((p) => p.date >= '2026-02-26' || (p.status === NEIGHBOURS_LIGHT && p.flux_mjy == null)))).toBe(true)
    expect(guarded.message).toContain(byKey.B.circle)
    // What is left compares March with August 2026: brighter, as the ruling says (about 2.5 times).
    expect(summarise(guarded, 'flux').map((s) => [s.firstEpoch, s.lastEpoch, s.verdict])).toEqual([[2, 3, 'brighter']])
    expect(leftOut(guarded, 'flux').reasons[NEIGHBOURS_LIGHT]).toBeGreaterThan(0)
  })
  it('the spectrum tool does the same, and a place near a candidate is only told so', () => {
    const point = (epoch: number, date: string, flux: number) => ({
      obs_id: String(epoch),
      detector: 6,
      epoch,
      mjd: 0,
      date,
      status: 'ok',
      wavelength_um: 4.6,
      bandwidth_um: 0.04,
      flux_mjy: flux,
      flux_err_mjy: 1,
    })
    const two: SpectrumResponse = {
      ra: 253.18038,
      dec: -44.67697,
      n_exposures: 2,
      status_counts: { ok: 2 },
      points: [point(1, '2025-08-17T04:08:13', 23), point(2, '2026-03-13T00:00:00', 400)],
    }
    const guarded = guardSpectrum(two, two)
    expect(guarded.points!.map((p) => [p.status, p.flux_mjy])).toEqual([
      [NEIGHBOURS_LIGHT, null],
      ['ok', 400],
    ])
    expect(guarded.message).toBe(`${byKey.B.circle} ${FIND_EVIDENCE} 1 of 2 exposures gave a clean measurement.`)
    const near = guardSpectrum({ ra: 253.18377, dec: -44.675508 }, { ...two, ra: 253.18377, dec: -44.675508 })
    expect(near.points).toEqual(two.points)
    expect(near.message).toMatch(/^Candidate B, 10 arcseconds from here, appeared between 2025 and 2026/)
  })
  it('the patch search marks the steady star 10 arcsec from B as B’s light, never as a candidate of its own', () => {
    const marked = markFinds(searchB as unknown as SearchStatus)
    const star = marked.result!.objects.find((o) => o.id === '03')!
    expect(star.near_find?.name).toBe('Candidate B')
    expect(star.near_find?.at).toBe(false)
    expect(star.verdict).toBe('caution')
    expect(isCandidate(star)).toBe(false)
    // In the Viewer's Find changes tool: short sentences, the distance computed, and no card to point to.
    expect(verdictSentence(star)).toBe("Candidate B is 10 arcseconds from here. Its light reaches this spot's measurement. So this change is most likely Candidate B's light.")
    expect(verdictSentence(star, true)).toBe(`${verdictSentence(star)} Its card is at the top of this page.`)
    // The others in the patch are left as they were.
    expect(marked.result!.objects.filter((o) => o.near_find)).toHaveLength(1)
  })
})

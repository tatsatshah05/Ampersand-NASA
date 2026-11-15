import { describe, expect, it } from 'vitest'
import { readAddress } from './address'
import {
  asObject,
  asRejected,
  exampleSentence,
  INTRO,
  isWatchlistAddress,
  neowiseHeadline,
  neowiseSentence,
  ORDER_SENTENCE,
  PLAIN_INTRO,
  PLAIN_TABS,
  tallySentence,
  viewerAddress,
  type Neowise,
  type WatchRow,
} from './watchlist'

const base = { id: 'x', kind: 'changer', ra: 277.505473, dec: -2.061979, rank_in_group: 1, best_detector: 6, first_seen: '', last_seen: '', patches: [], votes: { real: 0, artefact: 0, unsure: 0, total: 0 }, my_vote: null, notes: [], flags: [] } as const

describe('the page says candidate and opinion, never discovery', () => {
  it('uses the right words', () => {
    expect(INTRO).toMatch(/candidate/)
    expect(INTRO).toMatch(/opinion/)
    expect(INTRO).toMatch(/not a confirmation/)
    expect(ORDER_SENTENCE).toMatch(/votes never change it/)
    for (const text of [INTRO, ORDER_SENTENCE]) expect(text).not.toMatch(/discover(ed|y)|new object|sigma|S\/N/i)
  })
})

describe('NEOWISE wording', () => {
  const ok = (reading: 'changed' | 'steady' | 'cannot_say'): Neowise => ({ state: 'ok', reading, n_visits: 21, sentence: 'one sentence.', w1: null, w2: null })
  it('names the three readings', () => {
    expect(neowiseHeadline(ok('changed'))).toBe('NEOWISE also saw this spot change')
    expect(neowiseHeadline(ok('steady'))).toBe('NEOWISE saw it steady')
    expect(neowiseHeadline(ok('cannot_say'))).toBe('NEOWISE cannot say')
  })
  it('shows the backend sentence when there is one, and says plainly when there is not', () => {
    expect(neowiseSentence(ok('changed'))).toBe('one sentence.')
    expect(neowiseSentence({ state: 'waiting' })).toMatch(/Asking NEOWISE/)
    expect(neowiseSentence({ state: 'error', message: 'down' })).toMatch(/could not be asked/)
  })
})

describe('votes', () => {
  it('counts them as opinions', () => {
    expect(tallySentence({ real: 0, artefact: 0, unsure: 0, total: 0 })).toBe('No votes yet.')
    expect(tallySentence({ real: 2, artefact: 0, unsure: 1, total: 3 })).toBe('3 volunteers have voted: 2 real, 0 artefact, 1 unsure. These are opinions, not confirmations.')
    expect(tallySentence({ real: 1, artefact: 0, unsure: 0, total: 1 })).toMatch(/^1 volunteer has voted/)
  })
  it('labels examples', () => {
    expect(exampleSentence('eyes')).toBeNull()
    expect(exampleSentence('known')).toMatch(/Example/)
    expect(exampleSentence('artefact')).toMatch(/Example/)
  })
})

describe('the link to the viewer', () => {
  it('centres the normal view on the candidate in its best detector, and reads back', () => {
    const address = viewerAddress({ ra: 277.505473, dec: -2.061979, best_detector: 6 })
    const { selection } = readAddress(address)
    expect(selection).toMatchObject({ ra: 277.505473, dec: -2.061979, det: 6, mode: 'normal', fov: 0.1, name: null })
    expect(address).not.toMatch(/watchlist/)
  })
  it('does not invent a detector', () => {
    expect(readAddress(viewerAddress({ ra: 1, dec: 1, best_detector: null })).selection.det).toBe(5)
  })
  it('recognises the screen address', () => {
    expect(isWatchlistAddress('?watchlist=1')).toBe(true)
    expect(isWatchlistAddress('?ra=1&dec=2')).toBe(false)
  })
})

describe('rows as the search shapes', () => {
  it('a set-aside row is a rejected entry and not an object', () => {
    const row = { ...base, group: 'artefact', kind: 'mover', sigma: 7, detector: 6, reasons: ['not point-like'] } as unknown as WatchRow
    expect(asObject(row)).toBeNull()
    expect(asRejected(row)).toMatchObject({ detector: 6, sigma: 7, reasons: ['not point-like'] })
  })
  it('an object row is not a rejected entry', () => {
    const row = { ...base, group: 'eyes', verdict: 'clean', catalogue_status: {}, evidence: {} } as unknown as WatchRow
    expect(asObject(row)).not.toBeNull()
    expect(asRejected(row)).toBeNull()
  })
})

describe("Beginner's opening of the voting screen", () => {
  it('says why the screen is there and what a vote is, in plain words, and never "discovery"', () => {
    const all = [...PLAIN_INTRO, ...Object.values(PLAIN_TABS).flatMap((t) => [t.label, t.explain])].join(' ')
    expect(all).toMatch(/None is confirmed/)
    expect(all).toMatch(/does not change the list/)
    expect(all).toMatch(/only a candidate/)
    expect(all).not.toMatch(/discover|new object|new planet|sigma|S\/N|artefact|noise|CSV|gamed/i)
    const texts = [...PLAIN_INTRO, ...Object.values(PLAIN_TABS).map((t) => t.explain)]
    for (const s of texts.flatMap((x) => x.split(/(?<=[.!?])\s+/))) expect(s.split(/\s+/).length, s).toBeLessThanOrEqual(20)
  })
})

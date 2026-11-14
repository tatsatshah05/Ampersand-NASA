// The wording of search mode, checked against real responses of GET /api/search (trimmed, in
// src/fixtures/search). Expected values come from the definitions and from docs/search.md.
import { describe, expect, it } from 'vitest'
import barnard from './fixtures/search/barnard.json'
import epsindib from './fixtures/search/epsindib.json'
import rwaur from './fixtures/search/rwaur.json'
import serpsouth from './fixtures/search/serpsouth.json'
import wise from './fixtures/search/wise0855.json'
import * as S from './search'

const result = (f: unknown) => (f as { result: S.SearchResult }).result
const first = (f: unknown) => result(f).objects[0]
const status = (over: Partial<S.SearchStatus>): S.SearchStatus => ({
  status: 'running',
  seconds: 0,
  detector_now: null,
  detectors_done: 0,
  detectors_total: 6,
  searches_ahead: 0,
  ...over,
})

describe('progress', () => {
  it('says which detector and how long', () => {
    expect(S.progressSentence(status({ detector_now: 3, detectors_done: 2, seconds: 40.2 }))).toBe(
      'Searching detector 3: 2 of 6 done, 40 seconds so far.',
    )
  })
  it('says it is waiting when queued', () => {
    expect(S.progressSentence(status({ status: 'queued' }))).toBe('Waiting for another search to finish.')
    expect(S.progressSentence(status({ status: 'queued', searches_ahead: 2 }))).toContain('2 other searches')
  })
  it('says the catalogues are being checked once every detector is done', () => {
    expect(S.progressSentence(status({ detectors_done: 6, seconds: 31 }))).toBe('Checking the catalogues, 31 seconds so far.')
  })
})

describe('polling', () => {
  it('asks again until the search is done, and hands back the result', async () => {
    const answers = [status({ status: 'queued' }), status({ detector_now: 1 }), { ...status({}), status: 'done' as const }]
    const seen: string[] = []
    let calls = 0
    const last = await S.runSearch(
      { ra: 1, dec: 2, fov: 0.1 },
      { delayMs: 1, fetchStatus: () => Promise.resolve(answers[calls++]), onStatus: (s) => seen.push(s.status) },
    )
    expect(last.status).toBe('done')
    expect(calls).toBe(3)
    expect(seen).toEqual(['queued', 'running', 'done'])
  })
  it('stops at a failure and keeps the message', async () => {
    const last = await S.runSearch(
      { ra: 1, dec: 2, fov: 0.1 },
      { delayMs: 1, fetchStatus: () => Promise.resolve({ ...status({}), status: 'failed', error: 'IRSA did not respond' }) },
    )
    expect(last).toMatchObject({ status: 'failed', error: 'IRSA did not respond' })
  })
  it('builds the address with all six detectors by default', () => {
    expect(S.searchUrl({ ra: 277.51, dec: -2.05, fov: 0.2 })).toBe('/api/search?ra=277.51&dec=-2.05&fov=0.2&detectors=123456')
  })
})

describe('what happened', () => {
  it('Barnard\'s Star: speed and direction (Gaia: 10.4 arcsec/yr, almost due north)', () => {
    expect(S.headline(first(barnard))).toBe('Moved 10.3 arcseconds a year (give or take 1.5), heading north (bearing 348°).')
  })
  it('WISE 0855: heading west, 7.3 arcsec/yr in detector 5 as in docs/search.md', () => {
    expect(S.headline(first(wise))).toBe('Moved 7.3 arcseconds a year (give or take 0.7), heading west (bearing 283°).')
  })
  it('Epsilon Indi B: south-east', () => {
    expect(S.headline(first(epsindib))).toContain('heading south-east')
  })
  it('RW Aurigae: how much, and between which dates, from the response', () => {
    expect(S.headline(first(rwaur))).toBe('Changed brightness between 9 Sep 2025 and 13 Sep 2026: fainter, 0.52 times as bright as before.')
  })
  it('Serpens South: brighter, with the ratio the response gives', () => {
    expect(S.headline(first(serpsouth))).toBe('Changed brightness between 3 Sep 2025 and 30 Aug 2026: brighter, 4.5 times as bright as before.')
  })
  it('compass points', () => {
    expect([0, 44, 90, 180, 270, 315, 359.9, -90].map(S.compass)).toEqual([
      'north',
      'north-east',
      'east',
      'south',
      'west',
      'north-west',
      'north',
      'west',
    ])
  })
  it('does not invent dates or a ratio the response lacks', () => {
    const o = first(rwaur)
    const noDates = { ...o.evidence, visits: undefined }
    expect(S.changeSentence(noDates)).toBe('Changed brightness: fainter, 0.52 times as bright as before.')
    const noRatio = { ...o.evidence, change: { ...o.evidence.change!, ratio: null } }
    expect(S.changeSentence(noRatio)).toBe('Changed brightness between 9 Sep 2025 and 13 Sep 2026.')
    expect(S.changeSentence({ ...o.evidence, change: null })).toBe('Changed brightness.')
  })
  it('dates in words; anything else is left as it came', () => {
    expect(S.dateWords('2026-03-04')).toBe('4 Mar 2026')
    expect(S.dateWords('March')).toBe('March')
  })
})

describe('how strong', () => {
  it('uses "times the noise", never sigma or S/N', () => {
    const text = S.strengthSentence(first(barnard))
    expect(text).toBe(
      'Strongest: 6.1 times the noise in detector 5; 8.2 times the noise with the detectors put together. Reached 5 times the noise or more in detectors 5 and 6.',
    )
    expect(text).not.toMatch(/sigma|S\/N|signal/i)
  })
  it('says so when it took the detectors together to reach 5', () => {
    const o = result(serpsouth).objects.find((x) => x.id === '08')!
    expect(S.strengthSentence(o)).toContain('Reached 5 times the noise only when detectors are put together.')
  })
  it('lists the detectors in words', () => {
    expect(S.listWords([])).toBe('')
    expect(S.listWords([1])).toBe('1')
    expect(S.listWords([1, 5, 6])).toBe('1, 5 and 6')
  })
})

describe('what the catalogues say', () => {
  it('a known mover is named', () => {
    expect(S.catalogueSentence(first(barnard))).toBe(
      'Already known: Gaia DR3 4472832130942575872, whose catalogued motion matches the measured one.',
    )
    expect(S.candidateSentence(first(barnard))).toBeNull()
  })
  it('WISE 0855 is known from SIMBAD, not Gaia', () => {
    expect(S.catalogueSentence(first(wise))).toContain('WISEA J085510.74-071442.5')
  })
  it('a known variable is named', () => {
    expect(S.catalogueSentence(first(rwaur))).toBe('Already known as a variable star: V* RW Aur B.')
  })
  it('says which catalogues answered, and which did not', () => {
    const c = first(barnard).catalogue_status
    expect(S.answeredSentence(c)).toBe('Catalogues that answered: Gaia DR3, SIMBAD, AAVSO VSX, CatWISE2020 and AllWISE.')
    const partly: S.CatalogueStatus = { ...c, answered: ['Gaia DR3'], did_not_answer: { SIMBAD: 'timed out', 'AAVSO VSX': 'timed out' } }
    expect(S.answeredSentence(partly)).toBe('Catalogues that answered: Gaia DR3. Did not answer: SIMBAD and AAVSO VSX.')
    expect(S.answeredSentence({ ...partly, answered: [] })).toContain('No catalogue answered.')
  })
  it('a catalogue that did not answer is named in the verdict on a candidate', () => {
    const o = result(serpsouth).objects[0]
    const failed = { ...o, catalogue_status: { ...o.catalogue_status, did_not_answer: { 'AAVSO VSX': 'timed out' } } }
    expect(S.catalogueSentence(failed)).toContain('Not checked in AAVSO VSX, which did not answer.')
  })
  it('an object catalogued but not listed as variable is a candidate with what would confirm it', () => {
    const o = first(serpsouth)
    expect(S.isCandidate(o)).toBe(true)
    expect(S.catalogueSentence(o)).toBe(
      'MSX6C G028.6477+03.8174 is catalogued here, but it is not listed as a variable in the catalogues that answered.',
    )
    const text = S.candidateSentence(o)!
    expect(text).toContain('A candidate, not a finding')
    expect(text).toContain('would confirm it')
    expect(text).not.toMatch(/discover|new object|new variable/i)
  })
  it('only the four unexplained categories are candidates', () => {
    expect(result(serpsouth).objects.map((o) => S.isCandidate(o))).toEqual([true, false, false, true, false, true, true, true, true])
    expect(S.isCandidate(first(rwaur))).toBe(false)
  })
  it('a category the page does not know falls back to the backend\'s own words', () => {
    const o = first(barnard)
    const odd = { ...o, catalogue_status: { ...o.catalogue_status, category: 'something_new', meaning: 'the backend says this' } }
    expect(S.catalogueSentence(odd)).toBe('the backend says this')
    expect(S.isCandidate(odd)).toBe(false)
  })
})

describe('flags and verdicts', () => {
  const NAMES = ['saturated', 'halo', 'blended', 'wide', 'edge', 'few_exposures', 'two_visits', 'follows_roll', 'one_roll_only', 'uncalibrated']
  it('every flag backend/search.py can produce has its own plain sentence', () => {
    for (const f of NAMES) {
      const text = S.flagSentence(f)
      expect(text, f).not.toContain('Flag from the search') // that is the fallback for an unknown flag
      expect(text.length, f).toBeGreaterThan(30)
    }
    expect(new Set(NAMES.map(S.flagSentence)).size).toBe(NAMES.length)
  })
  it('an unknown flag is shown by its own name, not hidden', () => {
    expect(S.flagSentence('mystery_flag')).toBe('Flag from the search: mystery_flag.')
  })
  it('Barnard\'s Star is caution because it is saturated', () => {
    const o = first(barnard)
    expect(o.verdict).toBe('caution')
    expect(o.flags).toEqual(['saturated'])
    expect(S.verdictSentence(o)).toContain('flags a person should look at')
    expect(S.flagSentence('saturated')).toContain('1 to 2 arcseconds')
  })
  it('a clean object says nothing asks for caution', () => {
    expect(S.verdictSentence(first(wise))).toBe('Passed every artefact test the search has, and none of its caution flags was raised.')
  })
})

describe('single-detector candidates', () => {
  it('warns when only one detector reached 5 times the noise', () => {
    const o = result(serpsouth).objects.find((x) => x.id === '07')!
    expect(o.detectors_at_5_sigma).toEqual([2])
    expect(S.oneDetectorSentence(o)).toContain('Only one detector reached 5 times the noise on its own.')
  })
  it('says nothing for a candidate that several detectors agree on, or for a known object', () => {
    expect(S.oneDetectorSentence(first(serpsouth))).toBeNull()
    expect(S.oneDetectorSentence(first(rwaur))).toBeNull()
  })
})

describe('limits', () => {
  it('splits the backend\'s limits into sentences, in plain words, without the pointer to a file', () => {
    const lines = S.limitsSentences(result(rwaur).limits)
    expect(lines.length).toBeGreaterThanOrEqual(6)
    expect(lines[0]).toMatch(/^Finds only what stands 5 times above the noise/)
    expect(lines.join(' ')).not.toMatch(/sigma|docs\/search/)
    expect(lines.join(' ')).toContain('at least 10 per cent')
  })
})

describe('the whole search', () => {
  it('counts in one line', () => {
    const s = result(epsindib).summary
    expect(S.summarySentence(s)).toBe('161 sources tested in 38 seconds: 1 object moved or changed, 1 set aside as an artefact.')
  })
  it('the rejected artefact is described as rejected, with its reasons from the response', () => {
    const r = result(epsindib).rejected
    expect(r).toHaveLength(1)
    expect(S.rejectedHeadline(r[0])).toBe(
      'Looked like a mover in detector 6, 7 times the noise, at RA 331.07339°, Dec -56.76704°.',
    )
    expect(r[0].reasons[0]).toContain('reflection')
  })
  it('an empty result is a result, with the counts', () => {
    const s: S.SearchSummary = { ...result(rwaur).summary, n_objects: 0, n_rejected: 0, sources_tested: 197, seconds: 29 }
    expect(S.emptySentence(s)).toBe(
      'Nothing in this patch moved or changed enough to pass the tests. 197 sources tested in 29 seconds: 0 objects moved or changed, 0 set aside as artefacts.',
    )
  })
  it('knows when SPHEREx has no pictures here', () => {
    const s = result(rwaur).summary
    expect(S.noData(s)).toBe(false)
    expect(S.noData({ ...s, exposures: { '1': 0, '2': 0 } })).toBe(true)
    expect(S.noData({ ...s, exposures: {} })).toBe(false)
  })
  it('reports catalogues that failed', () => {
    const s = result(rwaur).summary
    expect(S.catalogueFailureSentence(s)).toBeNull()
    expect(S.catalogueFailureSentence({ ...s, catalogues_failed: { SIMBAD: 'down' } })).toContain('SIMBAD')
  })
  it('passes the backend\'s per-detector messages on', () => {
    const s = { ...result(rwaur).summary, messages: { '3': 'Only one visit so far: nothing can be compared yet.' } }
    expect(S.messagesOf(s)).toEqual(['Detector 3: Only one visit so far: nothing can be compared yet.'])
  })
})

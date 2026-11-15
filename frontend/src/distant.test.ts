// The wording of the distant-world search, checked against three real answers of GET /api/distant
// (src/fixtures/distant): a real search that found nothing, and two simulations.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { readAddress } from './address'
import * as D from './distant'
import real from './fixtures/distant/wise0855_real.json'
import found from './fixtures/distant/wise0855_planted_found.json'
import missed from './fixtures/distant/wise0855_planted_missed.json'

const result = (f: unknown) => (f as { result: D.DistantResult }).result
const status = (over: Partial<D.DistantStatus>): D.DistantStatus => ({
  status: 'running',
  simulation: false,
  ra: 1,
  dec: 2,
  fov: 0.2,
  detectors: [5, 6],
  seconds: 0,
  detector_now: null,
  detectors_done: 0,
  detectors_total: 2,
  ...over,
})
const candidate = result(found).candidates[0]

afterEach(() => vi.unstubAllGlobals())

describe('the address', () => {
  it('asks for detectors 5 and 6 unless told otherwise, and adds the plant only for a simulation', () => {
    expect(D.distantUrl({ ra: 1, dec: 2, fov: 0.2 })).toBe('/api/distant?ra=1&dec=2&fov=0.2&detectors=56')
    expect(D.distantUrl({ ra: 1, dec: 2, fov: 0.2, plant: 'hard', seed: 4 })).toBe(
      '/api/distant?ra=1&dec=2&fov=0.2&detectors=56&plant=hard&seed=4&plant_detector=5',
    )
  })
  it('the patch is at least 0.2 and at most 0.5 degrees', () => {
    expect([0.05, 0.1, 0.3, 0.9].map(D.searchFov)).toEqual([0.2, 0.2, 0.3, 0.5])
  })
})

describe('fetching', () => {
  it('reads the answer, and turns a 400 into its own words', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve({ ok: true, json: () => Promise.resolve(found) }))
    expect((await D.fetchDistantStatus({ ra: 1, dec: 2, fov: 0.2 })).result?.candidates).toHaveLength(1)
    vi.stubGlobal('fetch', () => Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({ detail: 'fov is too wide' }) }))
    await expect(D.fetchDistantStatus({ ra: 1, dec: 2, fov: 9 })).rejects.toThrow('fov is too wide')
    vi.stubGlobal('fetch', () => Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error('no')) }))
    await expect(D.fetchDistantStatus({ ra: 1, dec: 2, fov: 1 })).rejects.toThrow('does not offer')
  })
})

describe('polling', () => {
  it('asks again until the search is done, and hands back the result', async () => {
    const answers = [status({ status: 'queued' }), status({ detector_now: 5 }), { ...status({}), status: 'done' as const, result: result(real) }]
    let calls = 0
    const seen: string[] = []
    const last = await D.runDistant({ ra: 1, dec: 2, fov: 0.2 }, { delayMs: 1, fetchStatus: () => Promise.resolve(answers[calls++]), onStatus: (s) => seen.push(s.status) })
    expect(seen).toEqual(['queued', 'running', 'done'])
    expect(last.result?.status).toBe('nothing_found')
  })
  it('stops when the visitor stops it', async () => {
    const ctrl = new AbortController()
    const run = D.runDistant({ ra: 1, dec: 2, fov: 0.2 }, { signal: ctrl.signal, delayMs: 5, fetchStatus: () => Promise.resolve(status({})) })
    ctrl.abort()
    await expect(run).rejects.toThrow('stopped')
  })
})

describe('progress', () => {
  it('says which detector and how many are done', () => {
    expect(D.progressSentence(status({ detector_now: 6, detectors_done: 1, seconds: 12.4 }))).toBe('Searching detector 6: 1 of 2 done, 12 seconds so far.')
    expect(D.progressSentence(status({ status: 'queued' }))).toContain('Waiting')
    expect(D.progressSentence(status({ detectors_done: 2, seconds: 61 }))).toBe('Checking the catalogue, 61 seconds so far.')
  })
  it('warns that a new patch takes minutes', () => {
    expect(D.FIRST_TIME_NOTE).toContain('a few minutes')
    expect(D.FIRST_TIME_NOTE).toContain("NASA's archive")
  })
  it('says what patch it searches and why detectors 5 and 6', () => {
    const s = D.patchSentence(0.2)
    expect(s).toContain('0.2 degrees across in detectors 5 and 6')
    expect(s).toContain('3.8 to 5 micrometres')
  })
})

describe('the limit', () => {
  const rows = result(real).limit
  it('one row as a sentence, with the smear only when it is 6 arcseconds or more', () => {
    // With the densest-days pass the real answer has no badly smeared row any more, so one is made from a real row.
    const near = { ...rows[0], smear_arcsec: 20.5 }
    const sentence = D.limitSentence(near)
    expect(sentence).toContain(`At ${D.whole(near.distance_au)} times the Earth-Sun distance an object would jump ${D.whole(near.jump_arcsec)} arcseconds between visits.`)
    expect(sentence).toContain(`It would have been found if brighter than ${D.mjy(near.faintest_mjy)} mJy, in ${Math.round(near.share_of_picture * 100)}% of the picture.`)
    expect(sentence).toContain(`smears about ${D.whole(near.smear_arcsec)} arcseconds within a single visit, which is why the limit is weaker`)
    const far = rows.find((r) => r.smear_arcsec < 6)!
    expect(D.limitSentence(far)).not.toContain('smears')
  })
  it('names the pass in words, and the note about near objects', () => {
    expect(D.passWords('all')).toBe('all exposures of each visit')
    expect(D.passWords('densest_days')).toBe('the densest few days of each visit')
    expect(D.passWords(undefined)).toBeNull()
    expect(D.PASS_NOTE).toBe('A near object moves while a visit lasts, so for near distances the search also uses only the densest few days of each visit.')
  })
  it('does not round a share to a whole when it carries more', () => {
    expect(D.limitSentence({ distance_au: 5, jump_arcsec: 1, share_of_picture: 0.594, faintest_mjy: 0.45, smear_arcsec: 5.9 })).toContain('0.45 mJy, in 59%')
  })
})

describe('candidates', () => {
  it('headline with the range', () => {
    expect(D.candidateHeadline(candidate)).toBe('Candidate: about 2,558 times the Earth-Sun distance (between 2,534 and 2,583)')
  })
  it('an open upper end reads "or more"', () => {
    expect(D.candidateHeadline({ ...candidate, distance_range_au: [2534, null] })).toBe('Candidate: about 2,558 times the Earth-Sun distance (2,534 or more)')
  })
  it('says whether the other detector sees it', () => {
    expect(D.supportSentence(candidate)).toEqual(['Detector 6 does not see it. A real object should show in the neighbouring detector.'])
    expect(D.supportSentence({ ...candidate, support: [{ detector: 6, visits: [], seen: true }] })).toEqual(['Detector 6 also sees it.'])
  })
})

describe('chance, counts, catalogue', () => {
  it('chance with no links and with some', () => {
    expect(D.chanceSentence(result(real).chance)).toBe(
      "The same search with the Earth's motion reversed, which nothing real can follow, found nothing either: chance made no links in this picture.",
    )
    expect(D.chanceSentence({ links_with_earth_reversed: 1, note: '' })).toContain('made 1 link by chance')
    expect(D.chanceSentence({ links_with_earth_reversed: 3, note: '' })).toContain('made 3 links by chance in this picture, so a link here could be chance')
  })
  it('one sentence per entry with its counts, whatever the number of entries', () => {
    const entries = result(real).per_detector
    const sentences = D.perDetectorSentences(result(real))
    expect(sentences).toHaveLength(entries.length)
    entries.forEach((d, i) => {
      expect(sentences[i]).toContain(`Detector ${d.detector}`)
      expect(sentences[i]).toContain(`${D.whole(d.come_and_go)} sources come and go`.replace(/^1 sources/, '1 source'))
      expect(sentences[i]).toContain(`${D.whole(d.set_aside_catalogued)} set aside because a catalogued infrared source sits there`)
    })
  })
  it('names the pass when the entry carries one, and could not be searched otherwise', () => {
    const base = result(real).per_detector[0]
    expect(D.perDetectorSentence({ ...base, exposures: 'densest_days' })).toMatch(/^Detector \d, densest few days of each visit: /)
    expect(D.perDetectorSentence({ ...base, exposures: 'all' })).toMatch(/^Detector \d, all exposures of each visit: /)
    expect(D.perDetectorSentence({ ...base, can_search: false })).toContain('could not be searched')
  })
  it('the catalogue answered, or not', () => {
    expect(D.catalogueSentence(result(real).catalogue)).toContain(`${D.whole(result(real).catalogue.sources_in_field)} catalogued infrared sources`)
    const down = D.catalogueSentence({ name: 'CatWISE2020', asked: true, answered: false, sources_in_field: 0, error: 'timed out' })
    expect(down).toContain('did not answer (timed out)')
    expect(down).toContain('known infrared sources could not be ruled out')
  })
})

describe('simulation', () => {
  it('found: the planted distance next to what the search says', () => {
    expect(D.simulationSentence(result(found))).toBe('Planted at 2,559 times the Earth-Sun distance; the search says 2,558 times the Earth-Sun distance (between 2,534 and 2,583).')
    expect(D.plantedSentence(result(found).planted!)).toContain('easy level, seed 1, in detector 5, 2,559 times')
  })
  it('missed: the backend explains', () => {
    expect(D.simulationSentence(result(missed))).toBe(result(missed).answer)
    expect(result(missed).answer).toContain('did not find the planted object')
  })
})

describe('the link that follows a candidate', () => {
  it('picks the smallest field that holds 1.4 times the jump', () => {
    expect([100, 250, 400, 600, 2000].map(D.followFov)).toEqual([0.1, 0.1, 0.2, 0.5, 0.5])
  })
  it('opens the viewer at the follow numbers, in Expert, in the candidate detector', () => {
    const s = readAddress(D.followAddress(candidate)!).selection
    expect(s).toMatchObject({ ra: candidate.follow.ra, dec: candidate.follow.dec, pmra: 8943.5, pmdec: -5255.5, parallax: 80621.6, det: 5, ui: 'expert', fov: 0.1 })
  })
})

describe('the link from a simulation to the practice screen', () => {
  it('opens the same patch, detector, level and seed, and exists only for a simulation', () => {
    const sim = (found as unknown as D.DistantStatus).result!
    const address = D.practiceAddress(sim)!
    const p = new URLSearchParams(address)
    expect(p.get('train')).toBe(String(sim.planted!.seed))
    expect(p.get('level') ?? 'easy').toBe(sim.planted!.level)
    expect(Number(p.get('ra'))).toBeCloseTo(sim.ra, 5)
    expect(Number(p.get('dec'))).toBeCloseTo(sim.dec, 5)
    expect(Number(p.get('fov'))).toBe(sim.fov)
    expect(Number(p.get('det') ?? 5)).toBe(sim.planted!.detector)
    expect(p.get('name')).toBeNull() // not the default selection's name
    expect(D.practiceAddress((real as unknown as D.DistantStatus).result!)).toBeNull()
  })
})

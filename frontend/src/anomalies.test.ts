// The Observe anomalies screen's own logic and words (anomalies.ts), on real data: the frames the
// Viewer gets for the three candidates (fixtures/frames/find_*_d6.json), the sweep as exported
// (public/anomalies/sweep.json) and the watchlist's regions as the backend gives them.
import { describe, expect, it } from 'vitest'
import { LANDING, toFramesQuery } from './address'
import {
  ALL_THREE_LINK,
  allowedLineOf,
  cardPair,
  EVERYWHERE,
  findAddress,
  findFramesUrl,
  FINDS_HEADING,
  longDate,
  NAMED_PLACES,
  namedPlaceAt,
  optionText,
  patchName,
  patchRegionParam,
  PICTURES_NOTE,
  PLANE,
  regionAbout,
  regionOptions,
  SCREEN_TITLE,
  showsPatches,
  showsSweep,
  survivorAddress,
  survivorLines,
  survivorName,
  survivorPlace,
  sweepRowOf,
  WHAT_IS_AN_ANOMALY,
  type SweepData,
} from './anomalies'
import { framesUrl, type Frame, type FramesReady } from './api'
import { FINDS, NOT_REPORTED } from './finds'
import framesA from './fixtures/frames/find_a_d6.json'
import framesB from './fixtures/frames/find_b_d6.json'
import framesC from './fixtures/frames/find_c_d6.json'
import { markNearFind, type PatchRegions, type WatchRow } from './watchlist'

const fsModule = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fsModule)) as { readFileSync: (p: URL, encoding: string) => string }
const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8')
const sweep = JSON.parse(read('../public/anomalies/sweep.json')) as SweepData
const byKey = Object.fromEntries(FINDS.map((f) => [f.key, f]))

/** Words a newcomer must not meet in Beginner outside a closed fold (the features check's list). */
const BANNED = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy|aperture|photometry|ephemeris|S\/N)\b|σ/
const sentences = (text: string) => text.split(/(?<=[.!?])\s+/).filter(Boolean)
const words = (sentence: string) => sentence.split(/\s+/).filter(Boolean).length

// The regions as /api/watchlist/regions answered on the test copy of the database (tests/data/watchlist/small.sqlite3).
const REGIONS: PatchRegions = {
  regions: [
    { key: '167.400000_-77.000000_0.2000', ra: 167.4, dec: -77, fov: 0.2, area_sq_deg: 0.04, constellation: 'Chamaeleon', last_searched: '2026-11-15T01:09:01Z', count: 4, counts: { eyes: 0, known: 1, artefact: 3 } },
    { key: '269.446267_4.768222_0.1000', ra: 269.446267, dec: 4.768222, fov: 0.1, area_sq_deg: 0.01, constellation: 'Ophiuchus', last_searched: '2026-11-15T09:18:17Z', count: 1, counts: { eyes: 0, known: 1, artefact: 0 } },
    { key: '253.180380_-44.676970_0.1000', ra: 253.18038, dec: -44.67697, fov: 0.1, area_sq_deg: 0.01, constellation: 'Scorpius', last_searched: '2026-11-15T10:11:15Z', count: 7, counts: { eyes: 2, known: 3, artefact: 2 } },
  ],
  total: 12,
  counts: { eyes: 2, known: 5, artefact: 5 },
  patches_searched: 3,
  first_searched: '2026-11-15T01:09:01Z',
  last_searched: '2026-11-15T10:11:15Z',
}

describe('the screen’s first words', () => {
  it('is called Observe anomalies and says what an anomaly is, plainly, in three sentences', () => {
    expect(SCREEN_TITLE).toBe('Observe anomalies')
    expect(WHAT_IS_AN_ANOMALY).toHaveLength(3)
    for (const line of WHAT_IS_AN_ANOMALY) {
      expect(sentences(line)).toHaveLength(1)
      expect(words(line), line).toBeLessThanOrEqual(20)
      expect(line).not.toMatch(BANNED)
    }
    const all = WHAT_IS_AN_ANOMALY.join(' ')
    expect(all).toMatch(/moved, got brighter or fainter, appeared or vanished/)
    expect(all).toMatch(/known objects or measuring problems/)
    expect(all).toMatch(/candidates, not discoveries/)
  })

  it('heads the candidates with what can be shown, never "never seen before"', () => {
    expect(FINDS_HEADING).toBe('Not reported anywhere we could find')
    expect(FINDS_HEADING).not.toMatch(/never seen|new|discover/i)
  })
})

describe('a candidate’s two pictures', () => {
  const frames = (d: unknown) => (d as FramesReady).frames
  it('are the last visit it was not seen in and the visit it was brightest in, from the Viewer’s own frames', () => {
    // A: not seen Aug 2025, 1,925 mJy fitted Mar 2026 (brightest), 631 Aug 2026.
    expect(cardPair(frames(framesA))).toEqual({ before: 0, brightest: 1 })
    // B: brightest in August 2026 (926 against 377 in March), so the pair is 2025 and August 2026.
    expect(cardPair(frames(framesB))).toEqual({ before: 0, brightest: 2 })
    // C: brightest Feb-Mar 2026; the spoiled April visit ("unknown") and the faint August one ("marginal") are not chosen.
    expect(cardPair(frames(framesC))).toEqual({ before: 0, brightest: 1 })
  })

  it('are never two pictures that would not show the change', () => {
    const f = frames(framesB)
    expect(cardPair([f[1], f[2]])).toBeNull() // seen in both: no "not seen" before
    expect(cardPair([f[0]])).toBeNull()
    expect(cardPair([])).toBeNull()
    // A saturated place is brighter than any number.
    const saturated: Frame = { ...f[1], detection: 'saturated', detection_measure: null }
    expect(cardPair([f[0], saturated, f[2]])).toEqual({ before: 0, brightest: 1 })
  })

  it('come from the same request the Viewer makes, and the card opens the Viewer there at the level in use', () => {
    const b = byKey.B
    expect(findFramesUrl(b)).toBe(framesUrl(toFramesQuery(LANDING)))
    expect(findAddress(b, 'beginner')).toBe('?ra=253.18038&dec=-44.67697&fov=0.1&det=6&mode=normal&pmra=0&pmdec=0&name=Candidate+B&ui=beginner')
    expect(findAddress(byKey.A, 'expert')).toBe('?ra=270.80408&dec=-23.46818&fov=0.1&det=6&mode=normal&pmra=0&pmdec=0&name=Candidate+A&ui=expert')
  })

  it('are explained plainly in Beginner', () => {
    for (const s of sentences(PICTURES_NOTE.beginner)) expect(words(s)).toBeLessThanOrEqual(20)
    expect(PICTURES_NOTE.beginner).not.toMatch(BANNED)
  })
})

describe('the candidates’ words', () => {
  it('carry the search for earlier reports word for word, and a status that says nothing was reported', () => {
    for (const f of FINDS) {
      expect(f.reportSearch).toMatch(new RegExp(`^We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at ${f.name}'s position in ${f.constellation}[;( ]`))
      expect(f.reportSearch).toMatch(/so this does not prove that no one else has seen it\.$/)
      expect(f.status).toBe('Not confirmed. Not yet reported to astronomers.')
    }
    expect(NOT_REPORTED).toBe('Not confirmed. Not yet reported to astronomers.')
  })

  it('are quoted word for word in docs/sweep.md', () => {
    const writeUp = read('../../docs/sweep.md').replace(/\s+/g, ' ')
    for (const f of FINDS) expect(writeUp, f.reportSearch).toContain(f.reportSearch)
    expect(writeUp).toContain(NOT_REPORTED)
  })

  it('agree with the exported sweep data', () => {
    for (const f of FINDS) {
      const row = sweepRowOf(sweep, f)
      expect(row?.allowed_sentence).toBe(f.allowed)
      expect([row?.ra, row?.dec, row?.constellation]).toEqual([f.ra, f.dec, f.constellation])
      expect(row?.last_non_detection?.slice(0, 16)).toBe(f.lastNotSeen)
    }
    expect(sweepRowOf(null, byKey.A)).toBeNull()
  })
})

describe('the sweep’s survivors', () => {
  it('are named by what they are known as, placed, and linked to the Viewer', () => {
    const names = sweep.survivors.map(survivorName)
    expect(names.slice(0, 5)).toEqual(['Candidate A', 'Candidate B', 'Candidate C', 'V7994 Sagittarii (nova, 2025)', 'V0691 Serpentis (nova)'])
    expect(names.slice(5, 11).every((n) => n.startsWith('WISEA J'))).toBe(true)
    expect(names.slice(11)).toEqual(['A spot in Scorpius', 'A spot in Sagittarius', 'A spot in Sagittarius'])
    const nova = sweep.survivors[3]
    expect(survivorPlace(nova, 'beginner')).toBe('Sagittarius · RA 270.96968°, Dec −31.45726°')
    expect(survivorPlace(nova, 'expert')).toBe('Sagittarius · RA 270.96968°, Dec −31.45726° · tile l000.0_b-2.5')
    expect(survivorAddress(nova, 'beginner')).toBe('?ra=270.96968&dec=-31.45726&fov=0.1&det=6&mode=normal&ui=beginner')
    expect(survivorAddress(sweep.survivors[1], 'expert')).toBe(findAddress(byKey.B, 'expert'))
  })

  it('say in Beginner what each is, plainly, and in Expert the catalogue rows and numbers', () => {
    for (const s of sweep.survivors) {
      for (const line of survivorLines(s, 'beginner')) {
        expect(line).not.toMatch(BANNED)
        for (const t of sentences(line)) expect(words(t), t).toBeLessThanOrEqual(20)
      }
    }
    expect(survivorLines(sweep.survivors[5], 'expert')[0]).toMatch(/^Known variable \(catalogued and already bright\): WISEA J\S+ \(AllWISE\) W2 [\d.]+ mag = \d+ mJy, already bright\.$/)
    expect(survivorLines(sweep.survivors[3], 'expert')).toContain('Brightness at 4.4–5.0 micrometres: 1,289 mJy (proof tile), 1,612 mJy (sweep tile).')
    expect(survivorLines(sweep.survivors[13], 'expert')[0]).toMatch(/^Set aside: the catalogued planetary nebula PN M 1-40/)
    // A candidate's words are on its card, never repeated or reworded here.
    expect(survivorLines(sweep.survivors[0], 'expert')).toEqual(['Its card is at the top of this page.'])
  })

  it('never call anything a discovery or new', () => {
    const all = sweep.survivors.flatMap((s) => [survivorName(s), ...survivorLines(s, 'beginner'), ...survivorLines(s, 'expert')]).join(' ')
    expect(all).not.toMatch(/discover|never seen|\bnew\b/i)
    // "confirmed" only as the write-up says it of a spot set aside: "not confirmed".
    expect(all.replace(/not confirmed/g, '')).not.toMatch(/confirmed/i)
    expect(all).not.toMatch(/\.\./)
  })
})

describe('regions', () => {
  it('lists everywhere, the plane and every searched patch, each with the count its groups hold', () => {
    const options = regionOptions(REGIONS, sweep)
    expect(options.map((o) => [o.key, o.label, o.count])).toEqual([
      [EVERYWHERE, 'Everywhere', 12 + 14],
      [PLANE, "The Milky Way's plane (472.6 square degrees swept)", 14],
      ['167.400000_-77.000000_0.2000', 'Chamaeleon, RA 167.40°, Dec −77.00°', 4],
      ['269.446267_4.768222_0.1000', "Ophiuchus: Barnard's Star", 1],
      ['253.180380_-44.676970_0.1000', 'Scorpius: Candidate B', 7],
    ])
    expect(optionText(options[1])).toBe("The Milky Way's plane (472.6 square degrees swept) · 14 found")
    // Before anything has loaded there is still a choice, the default.
    expect(regionOptions(null, null)).toEqual([{ key: EVERYWHERE, label: 'Everywhere', count: 0 }])
  })

  it('says how large the chosen region is and when it was searched', () => {
    expect(regionAbout(PLANE, REGIONS, sweep, 'beginner')).toEqual([
      "472.6 square degrees of the Milky Way's plane, swept on 14 November 2026.",
      'Its pictures from three visits were compared: August to September 2025, February to April 2026, August to September 2026.',
      '14 anomalies passed every automatic check.',
    ])
    expect(regionAbout(PLANE, REGIONS, sweep, 'expert')[3]).toBe('63 tiles and 1,162,894 sources compared at 4.4–5.0 micrometres (detector 6).')
    expect(regionAbout(EVERYWHERE, REGIONS, sweep, 'beginner')).toEqual([
      "Every place searched so far: 3 small patches of sky and 472.6 square degrees of the Milky Way's plane.",
      'The patches were searched on 15 November 2026, and the plane was swept on 14 November 2026.',
      '26 anomalies in all: 12 in the patches and 14 in the sweep.',
    ])
    expect(regionAbout('253.180380_-44.676970_0.1000', REGIONS, sweep, 'beginner')).toEqual([
      'A patch 0.1 degrees across, last searched on 15 November 2026.',
      '7 anomalies found here.',
    ])
    expect(regionAbout('269.446267_4.768222_0.1000', REGIONS, sweep, 'expert')).toEqual([
      'A patch 0.1° across (0.01 square degrees), centred on RA 269.44627°, Dec +4.76822°; last searched 2026-11-15 09:18 UTC.',
      '1 anomaly found here.',
    ])
    expect(regionAbout('nowhere', REGIONS, sweep, 'beginner')).toEqual([])
    for (const key of [PLANE, EVERYWHERE, '253.180380_-44.676970_0.1000']) {
      for (const line of regionAbout(key, REGIONS, sweep, 'beginner')) {
        expect(line).not.toMatch(BANNED)
        for (const s of sentences(line)) expect(words(s), s).toBeLessThanOrEqual(20)
      }
    }
  })

  it('says a span of days when the patches were searched on more than one', () => {
    const two = { ...REGIONS, first_searched: '2026-11-14T20:00:00Z' }
    expect(regionAbout(EVERYWHERE, two, sweep, 'beginner')[1]).toBe('The patches were searched from 14 to 15 November 2026, and the plane was swept on 14 November 2026.')
  })

  it('decides which groups show and which part of the list is asked for', () => {
    expect([showsPatches(EVERYWHERE), showsSweep(EVERYWHERE)]).toEqual([true, true])
    expect([showsPatches(PLANE), showsSweep(PLANE)]).toEqual([false, true])
    expect([showsPatches('a_b_c'), showsSweep('a_b_c')]).toEqual([true, false])
    expect([patchRegionParam(EVERYWHERE), patchRegionParam(PLANE), patchRegionParam('a_b_c')]).toEqual([null, null, 'a_b_c'])
  })

  it('names a patch after the built-in target it is centred on', () => {
    expect(namedPlaceAt(253.18038, -44.67697)).toBe('Candidate B')
    expect(namedPlaceAt(76.956587, 30.401291)).toBe('RW Aurigae')
    expect(namedPlaceAt(277.50547, -2.06198)).toBe('Young star in Serpens South')
    expect(namedPlaceAt(277.51, -2.05)).toBeNull() // 0.2-degree patch near it, not centred on it
    expect(patchName({ ra: 52.265, dec: 31.31, constellation: 'Perseus' })).toBe('Perseus, RA 52.27°, Dec +31.31°')
    // The own looks are where the Viewer's row of buttons puts them.
    const searchBar = read('./components/SearchBar.tsx')
    for (const p of NAMED_PLACES.slice(-3)) {
      expect(searchBar).toContain(`name: '${p.name}'`)
      expect(searchBar).toContain(`ra: ${p.ra},`)
      expect(searchBar).toContain(`dec: ${p.dec},`)
    }
  })

  it('writes dates in words', () => {
    expect(longDate('2026-11-15T10:11:15Z')).toBe('15 November 2026')
    expect(longDate('2026-11-04')).toBe('4 November 2026')
    expect(longDate('soon')).toBe('soon')
  })
})

describe('the way in from the Viewer', () => {
  it('follows only the allowed sentence of the candidate on screen', () => {
    expect(ALL_THREE_LINK).toEqual({ beginner: 'See all three in Observe anomalies', expert: 'All three in Anomalies' })
    expect(allowedLineOf(byKey.B.allowed, 253.18038, -44.67697)?.key).toBe('B')
    expect(allowedLineOf(byKey.A.allowed, 253.18038, -44.67697)).toBeNull()
    expect(allowedLineOf(byKey.B.brightness, 253.18038, -44.67697)).toBeNull()
    expect(allowedLineOf(byKey.B.allowed, 269.446267, 4.768222)).toBeNull()
  })
})

describe('a patch search’s change next to a candidate', () => {
  const row = (over: Partial<WatchRow>): WatchRow => ({
    id: 'x', group: 'eyes', kind: 'changer', ra: 0, dec: 0, rank_in_group: 1, best_detector: 6, first_seen: '', last_seen: '',
    patches: [], votes: { real: 0, artefact: 0, unsure: 0, total: 0 }, my_vote: null, notes: [], flags: [], verdict: 'clean', ...over,
  })
  it('gets the patch search’s own caution: near B, the steady star 10 arcsec away holds B’s light', () => {
    const marked = markNearFind(row({ ra: 253.1838, dec: -44.6755 }))
    expect(marked.verdict).toBe('caution')
    expect(marked.near_find?.name).toBe('Candidate B')
    expect(marked.near_find?.at).toBe(false)
    expect(marked.near_find?.arcsec).toBeCloseTo(10.2, 0)
  })
  it('leaves everything else as the server sent it', () => {
    const far = row({ ra: 52.265, dec: 31.31 })
    expect(markNearFind(far)).toBe(far)
    const mover = row({ kind: 'mover', ra: 253.1807, dec: -44.6769 })
    expect(markNearFind(mover)).toBe(mover)
    const setAside = row({ group: 'artefact', ra: 253.1807, dec: -44.6769 })
    expect(markNearFind(setAside)).toBe(setAside)
  })
})

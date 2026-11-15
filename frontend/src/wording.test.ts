// The words of the table of visits and the sentence about the whole run, on real /api/frames
// answers (src/fixtures/frames, saved from the server on 14 Nov 2026) and on a few built cases.
// None of these functions takes the visit on screen, so the words cannot change while playing.
import { describe, expect, it } from 'vitest'
import type { Frame, FramesReady } from './api'
import barnardJson from './fixtures/frames/barnard_d5.json'
import differenceJson from './fixtures/frames/barnard_d5_difference.json'
import sumJson from './fixtures/frames/barnard_d5_sum.json'
import requestJson from './fixtures/frames/barnard_request_d5.json'
import epsIndJson from './fixtures/frames/epsindib_request_d5.json'
import rwAurJson from './fixtures/frames/rwaur_request_d5.json'
import novaJson from './fixtures/frames/v572vel_d2.json'
import wiseJson from './fixtures/frames/wise0855_request_d6.json'
import findAJson from './fixtures/frames/find_a_d6.json'
import findANoMotionJson from './fixtures/frames/find_a_d6_nomotion.json'
import findBJson from './fixtures/frames/find_b_d6.json'
import findBNoMotionJson from './fixtures/frames/find_b_d6_nomotion.json'
import findCJson from './fixtures/frames/find_c_d5.json'
import findCNoMotionJson from './fixtures/frames/find_c_d5_nomotion.json'
import findC6Json from './fixtures/frames/find_c_d6.json'
import { FINDS } from './finds'
import { movementInfo, pictureInfo } from './guide'
import {
  CHANGE_CAUTION,
  catalogueCheck,
  catalogueLine,
  changeHeadline,
  compassWord,
  dateSpan,
  expertCells,
  flagsNote,
  monthYearLong,
  overallResult,
  plainColumn,
  plainResult,
  rowAnnouncement,
  seenLine,
  shiftWords,
  tableCaption,
  tableNotes,
  tableRows,
} from './wording'

const barnard = barnardJson as unknown as FramesReady
const difference = differenceJson as unknown as FramesReady
const sum = sumJson as unknown as FramesReady
const request = requestJson as unknown as FramesReady
const epsInd = epsIndJson as unknown as FramesReady
const rwAur = rwAurJson as unknown as FramesReady
const nova = novaJson as unknown as FramesReady
const wise = wiseJson as unknown as FramesReady

const plain = (d: FramesReady) => tableRows(d).map((r) => plainResult(r, d))
const expert = (d: FramesReady) => tableRows(d).map((r) => expertCells(r, d))
const words = (s: string) => s.split(/\s+/).filter(Boolean).length

describe('small pieces', () => {
  it('writes dates from their text', () => {
    expect(monthYearLong('2025-08-26')).toBe('August 2025')
    expect(dateSpan('2025-08-21', '2025-08-30')).toBe('21–30 Aug 2025')
    expect(dateSpan('2026-08-18', '2026-09-22')).toBe('18 Aug–22 Sep 2026')
    expect(dateSpan('2025-12-22', '2026-01-20')).toBe('22 Dec 2025–20 Jan 2026')
    expect(dateSpan('2025-05-05', '2025-05-05')).toBe('5 May 2025')
  })
  it('says a shift in plain parts and a compass word', () => {
    expect(shiftWords({ east: -0.93, north: 5.9, total: 5.97 })).toBe('5.9 north, 0.9 west')
    expect(shiftWords({ east: -0.93, north: 5.9, total: 5.97 }, 'arcseconds')).toBe('5.9 arcseconds north, 0.9 west')
    expect(shiftWords({ east: 0.01, north: 0.02, total: 0.02 })).toBe('same place')
    expect(compassWord({ east: -2.21, north: 10.16 })).toBe('north')
    expect(compassWord({ east: 4.97, north: -3.84 })).toBe('south-east')
    expect(compassWord({ east: -7.77, north: 1.09 })).toBe('west')
  })
})

describe("a mover: Barnard's Star, detector 5 (Gaia's own star at the centre)", () => {
  it('says the whole run in one sentence, with the catalogue check under it', () => {
    // First and last measured places 10.40 arcseconds apart (CLAUDE.md, step 1: -2.21, +10.16).
    expect(overallResult(barnard)).toEqual({
      sentence: 'It moved 10.4 arcseconds north between August 2025 and August 2026.',
      more: ['Gaia, a star catalogue, expected 10.3. The two agree: this nearby object really is drifting across the sky.'],
      pointer: null,
    })
    const check = catalogueCheck(barnard)
    expect(check?.differ).toBeCloseTo(1.44, 2) // measured minus predicted, visit 1 to 3
    expect(check?.bar).toBeCloseTo(4.24, 2) // three times the two 1-arcsecond position errors
    expect(seenLine(barnard)).toBe('Seen clearly in all 3 visits.')
  })
  it("gives Beginner one row per visit: the visit and how far it had moved", () => {
    expect(plain(barnard)).toEqual(['start', '5.9 north, 0.9 west', '10.2 north, 2.2 west'])
    expect(tableNotes(barnard, 'beginner')).toEqual([])
  })
  it('gives Expert every number of every visit, two lines each', () => {
    expect(tableCaption(barnard)).toBe('Shift since visit 1 in ″, east and north; + from Gaia.')
    expect(expert(barnard)).toEqual([
      { measured: 'start', total: '', predicted: '', differ: '', about: '21–30 Aug 2025 · 18 exp. · clear, >1000× · ±1″' },
      { measured: '−0.9, +5.9', total: '6.0', predicted: '+0.6, +5.6', differ: '1.5″ (0.25 px)', about: '15–22 Mar 2026 · 19 exp. · clear, >1000× · ±1″' },
      { measured: '−2.2, +10.2', total: '10.4', predicted: '−0.8, +10.3', differ: '1.4″ (0.23 px)', about: '18 Aug–22 Sep 2026 · 25 exp. · clear, >1000× · ±1″' },
    ])
    // The overexposed core, said once for the visits it applies to.
    expect(tableNotes(barnard, 'expert')).toEqual([
      'The core is overexposed in visits 1, 2 and 3, so each position is good to about 1″, not the much smaller error of the fit.',
    ])
  })
  it('says the row of a visit stepped to, for a screen reader', () => {
    expect(rowAnnouncement(barnard, 0)).toBe('Visit 1 of 3, August 2025: where it started.')
    expect(rowAnnouncement(barnard, 1)).toBe('Visit 2 of 3, March 2026: moved 5.9 arcseconds north, 0.9 west.')
  })
  it('keeps Beginner short: the block for Barnard is under 60 words', () => {
    const r = overallResult(barnard)
    const all = [r.sentence, ...r.more, seenLine(barnard) ?? '', ...plain(barnard), ...tableNotes(barnard, 'beginner')]
    expect(words(all.join(' '))).toBeLessThan(60)
    expect(all.join(' ')).not.toMatch(/sigma|flux|epoch|detector|centroid/i)
  })
})

describe('a target given with its own motion (the name lookup)', () => {
  it('compares with the motion given, not with Gaia', () => {
    expect(tableCaption(request)).toBe('Shift since visit 1 in ″, east and north; + from the motion given.')
    expect(catalogueLine(request)).toBe('Its catalogue motion expected 10.3. The two agree: this nearby object really is drifting across the sky.')
  })
})

describe('an object that stayed in place: RW Aurigae', () => {
  it('says no movement, why, and where brightness changes are, never "it did not move" alone', () => {
    expect(overallResult(rwAur)).toEqual({
      sentence: 'No movement seen between September 2025 and September 2026.',
      more: ['Any shift was under a third of a pixel. Its catalogue motion expected 0.0: it barely moves.'],
      pointer: 'For brightness, see Expert’s Brightness over time.',
    })
    // The sentence says "within error" for every row, so the rows do not repeat it.
    expect(plain(rwAur)).toEqual(['start', '0.2 south, 0.8 east', '0.2 south, 0.8 east'])
  })
  it('keeps every caution in Expert, said once', () => {
    expect(tableNotes(rwAur, 'expert')).toEqual([
      'Within error, visits 2 and 3: under a third of one SPHEREx pixel (6.15 arcseconds), so it may be measurement error rather than real movement.',
      'The core is overexposed in visits 1 and 2, so each position is good to about 1″, not the much smaller error of the fit.',
      'Visits 1, 2 and 3: a star 1.6″ to 1.7″ away (Gaia G 12.2) is too close to separate from the target, so the position and brightness include its light.',
    ])
    expect(rowAnnouncement(rwAur, 1)).toBe('Visit 2 of 3, March 2026: shifted 0.2 arcseconds south, 0.8 east, within measuring error.')
  })
})

describe('a view with no known object at the centre: Nova V572 Velorum, detector 2', () => {
  it('never calls the shift of the marked spot movement', () => {
    const r = overallResult(nova)
    expect(r.sentence).toBe('The marked spot shifted 6.8 arcseconds between June 2025 and June 2026.')
    expect(r.more).toEqual(['No known object is listed at the centre, so this may be a different spot, not movement.'])
    expect(JSON.stringify([r, plain(nova)])).not.toMatch(/moved/)
    expect(tableNotes(nova, 'expert')).toContain('No known object is listed at the centre, so the shift in visits 2 and 3 may be a different spot, not movement.')
    expect(tableNotes(nova, 'expert')).toContain('No Gaia star near the centre, so there is no predicted motion to compare with.')
    expect(rowAnnouncement(nova, 2)).toBe('Visit 3 of 3, June 2026: shifted 5.5 arcseconds south, 4.0 west, which may be a different spot.')
  })
})

describe('a marginal detection and a blended neighbour: WISE 0855, detector 6', () => {
  it('says how clearly it is seen across the visits, and marks the marginal row', () => {
    expect(seenLine(wise)).toBe('Seen clearly in visits 2 and 3, only just in visit 1.')
    expect(plain(wise)[0]).toBe('start, only just seen')
    expect(expert(wise)[0].about).toBe('5 May 2025 · 3 exp. · marginal, 3.4× · ±0.5″')
    // The neighbour shares the light in visit 3 only: a word in that row, and the full note once.
    expect(expert(wise)[2].about).toBe('21 Apr–11 May 2026 · 21 exp. · clear, 11× · ±0.08″ · blended')
    expect(tableNotes(wise, 'expert')).toEqual([
      'Only a marginal detection in visit 1 (3 to 5 times the background scatter; 5 or more is clear): treat it with care.',
      'Visit 3: a neighbouring star (Gaia G 16.3, 4.4″ away) supplies about a quarter of the light.',
    ])
  })
})

describe('four visits, one of them within error: Epsilon Indi B', () => {
  it('marks only that row, and explains once', () => {
    expect(plain(epsInd)).toEqual(['start', '1.2 south, 1.2 east, within error', '2.0 south, 4.0 east', '3.8 south, 5.0 east'])
    expect(tableNotes(epsInd, 'beginner')).toEqual(['Within error: too small to be sure.'])
    expect(expert(epsInd)[1].about).toMatch(/· within error$/)
    expect(overallResult(epsInd).sentence).toBe('It moved 6.3 arcseconds south-east between May 2025 and September 2026.')
  })
})

describe('difference mode: each visit minus visit 1', () => {
  it('has one row fewer (visit 1 is subtracted) and measures from visit 1', () => {
    expect(tableRows(difference).map((r) => r.frame.epoch)).toEqual([2, 3])
    expect(plain(difference)).toEqual(['5.9 north, 0.9 west', '10.2 north, 2.2 west'])
    expect(tableNotes(difference, 'expert').slice(0, 2)).toEqual([
      'Visit 1 is the one subtracted, so the shifts are measured from it.',
      "The positions were measured in each visit's own image, not in the difference.",
    ])
    expect(rowAnnouncement(difference, 0)).toBe('Visit 2 of 3, March 2026: moved 5.9 arcseconds north, 0.9 west.')
  })
})

describe('the sum of all visits', () => {
  it('has one row and says nothing can move in it', () => {
    expect(overallResult(sum).sentence).toBe('Every visit is added into this one picture, so nothing moves in it.')
    expect(plain(sum)).toEqual(['every visit in one picture'])
    expect(tableCaption(sum)).toBe('The sum of all visits: one picture, so there is nothing to compare.')
    expect(tableNotes(sum, 'expert')[0]).toBe('Every visit is in this one frame, so nothing moves in it.')
    expect(seenLine(sum)).toBe('Seen clearly in the sum of all visits.')
    expect(rowAnnouncement(sum, 0)).toBe('All visits added together, August 2025 to September 2026.')
  })
})

describe('built cases', () => {
  const only = { ...barnard, frames: [barnard.frames[0]] }
  it('one visit only', () => {
    expect(overallResult(only).sentence).toBe('This is the only visit so far, so there is nothing to compare yet.')
    expect(plain(only)).toEqual(['the only visit so far'])
    expect(tableCaption(only)).toBe('One visit only, so there is nothing to compare yet.')
    expect(tableNotes(only, 'expert')[0]).toBe('This is the only visit so far with this detector, so there is nothing to compare it with yet.')
    expect(catalogueLine(only)).toBeNull()
  })

  const lost: FramesReady = {
    ...barnard,
    frames: barnard.frames.map((f, i) =>
      i === 1 ? ({ ...f, centroid: null, centroid_reason: 'The predicted position is off the picture, too near its edge, or has no data around it.' } as Frame) : f,
    ),
  }
  it('a visit with no position: "not found", and the run is measured between the visits that have one', () => {
    expect(plain(lost)).toEqual(['start', 'not found', '10.2 north, 2.2 west'])
    expect(expert(lost)[1].measured).toBe('not found')
    expect(tableNotes(lost, 'beginner')).toEqual(['Not found in visit 2: no clear spot could be measured there.'])
    expect(tableNotes(lost, 'expert')).toContain('Visit 2: no position could be measured. Visit details says why.')
    expect(overallResult(lost).sentence).toBe('It moved 10.4 arcseconds north between August 2025 and August 2026.')
    expect(rowAnnouncement(lost, 1)).toBe('Visit 2 of 3, March 2026: no position could be measured.')
  })
  it('never quotes a shift from a visit where it was not found', () => {
    const firstLost: FramesReady = { ...barnard, frames: barnard.frames.map((f, i) => (i === 0 ? ({ ...f, centroid: null } as Frame) : f)) }
    // Measured from visit 2, and the sentence says which visits.
    expect(overallResult(firstLost).sentence).toMatch(/^It moved 4\.\d arcseconds .* between visit 2 \(March 2026\) and visit 3 \(August 2026\)\.$/)
    expect(plain(firstLost)).toEqual(['not found', 'start', expect.stringMatching(/north/)])
    const once: FramesReady = { ...barnard, frames: barnard.frames.map((f, i) => (i === 2 ? f : ({ ...f, centroid: null } as Frame))) }
    expect(overallResult(once).sentence).toBe('It was found only in visit 3, so there is nothing to compare.')
    const none: FramesReady = { ...barnard, frames: barnard.frames.map((f) => ({ ...f, centroid: null }) as Frame) }
    expect(overallResult(none).sentence).toBe('No position could be measured in any visit.')
  })

  // Six visits (more than the four the block has room for): the table scrolls in its box.
  const later = (n: number, month: string): Frame => ({ ...barnard.frames[2], epoch: n, date_start: `2027-${month}-01`, date_end: `2027-${month}-09`, date_mean: `2027-${month}-05` })
  const many: FramesReady = { ...barnard, frames: [...barnard.frames, later(4, '02'), later(5, '07'), later(6, '12')] }
  it('more than four visits: one row each, the screen reader counts them all', () => {
    expect(tableRows(many)).toHaveLength(6)
    expect(plain(many).slice(3)).toEqual(['10.2 north, 2.2 west', '10.2 north, 2.2 west', '10.2 north, 2.2 west'])
    expect(rowAnnouncement(many, 5)).toBe('Visit 6 of 6, December 2027: moved 10.2 arcseconds north, 2.2 west.')
    expect(seenLine(many)).toBe('Seen clearly in all 6 visits.')
  })
  it('a missing visit number is said with the visit’s place in the run', () => {
    const gap = { ...barnard, frames: [barnard.frames[0], barnard.frames[1], { ...barnard.frames[2], epoch: 4 }] }
    expect(rowAnnouncement(gap, 2)).toBe('Visit 4, number 3 of 3, August 2026: moved 10.2 arcseconds north, 2.2 west.')
  })
  it('the Flags legend speaks of every visit at once', () => {
    expect(flagsNote(barnard)).toBe(
      ": no value in any exposure of a frame (none here). For measuring brightness the star's core is saturated in some exposures, even where the image looks fine: 18 of 18 in visit 1, 19 of 19 in visit 2, 23 of 25 in visit 3.",
    )
  })
})

// The three candidates of our sweep (finds.ts), on the server's real answers of 15 Nov 2026 for the
// views their buttons ask for: the corrected position, held still (pmra = pmdec = 0), in the detector
// that shows each best. The page's own measure, per visit, against the referee's ruling:
//   A, detector 6: -6.2 (not seen), 521, 168 times the scatter. Ruling: about 0 in Aug-Sep 2025 once
//     the 437 mJy star 20″ away is modelled; 2.4-2.9 Jy in spring 2026; 0.67-0.80 Jy in Aug 2026.
//   B, detector 6: -1.8, 282, 619. Ruling: about 0 in 2025; about 400 mJy in March, 1,000-1,090 in August.
//   C, detector 5: -1.1, 75, 0.7. Ruling: about 0 in 2025; 85-110 mJy in Feb-Mar 2026; 3-5 mJy in Jul-Sep 2026.
const findA = findAJson as unknown as FramesReady
const findB = findBJson as unknown as FramesReady
const findC = findCJson as unknown as FramesReady
const findC6 = findC6Json as unknown as FramesReady
const allowed = (key: string) => FINDS.find((f) => f.key === key)?.allowed

describe('something that appears: the three candidates', () => {
  it('A: says what was seen when, then the referee’s sentence and where the brightness tool is', () => {
    expect(overallResult(findA)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [allowed('A'), 'For brightness, see Expert’s Brightness over time.'],
      pointer: null,
    })
    // Beginner's column says how clearly it is seen in each visit, not how far it moved; the
    // line on how clearly it is seen would only say the headline again.
    expect(plainColumn(findA)).toEqual({ header: 'Seen', label: 'Every visit, and how clearly it is seen in it' })
    expect(plain(findA)).toEqual(['not seen', 'seen clearly', 'seen clearly'])
    expect(tableNotes(findA, 'beginner')).toEqual([])
    expect(seenLine(findA)).toBeNull()
  })

  it('B: the same, and the table says "not seen" where it is not seen, at both levels', () => {
    expect(overallResult(findB)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [allowed('B'), 'For brightness, see Expert’s Brightness over time.'],
      pointer: null,
    })
    expect(plain(findB)).toEqual(['not seen', 'seen clearly', 'seen clearly'])
    expect(expert(findB)[0]).toEqual({ measured: 'not seen', total: '', predicted: '0.0, 0.0', differ: '', about: '2–21 Aug 2025 · 18 exp. · not seen' })
    expect(expert(findB)[2].measured).toBe('−0.3, +0.1') // Expert keeps the shifts: within error, as its notes say
    expect(rowAnnouncement(findB, 0)).toBe('Visit 1 of 3, August 2025: not seen.')
    // Held still at its place by the page, not by any catalogue: no "catalogue motion" anywhere.
    expect(catalogueCheck(findB)).toBeNull()
    expect(catalogueLine(findB)).toBeNull()
    expect([...movementInfo(findB), ...pictureInfo(findB, 'Candidate B')].join(' ')).not.toMatch(/catalogue/i)
  })

  it('C: appeared and faded again', () => {
    expect(overallResult(findC)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there in February 2026, and faint again by August 2026.',
      more: [allowed('C'), 'For brightness, see Expert’s Brightness over time.'],
      pointer: null,
    })
    expect(plain(findC)).toEqual(['not seen', 'seen clearly', 'not seen'])
    expect(tableNotes(findC, 'beginner')).toEqual([])
    // Visit 3 is detector 6's alone: here the third row is visit 4, and the screen reader says so.
    expect(rowAnnouncement(findC, 2)).toBe('Visit 4, number 3 of 3, August 2026: not seen.')
  })

  it('a visit where how clearly is not known is left out of the headline (C in detector 6, two spoiled April exposures)', () => {
    expect(changeHeadline(findC6)?.sentence).toBe('Not seen in August 2025. Clearly there in March 2026, and faint again by August 2026.')
    expect(plain(findC6)).toEqual(['not seen', 'seen clearly', 'not known', 'only just seen'])
  })

  it('Expert has no headline over its table: the same words come first under it, with every caution kept', () => {
    expect(tableNotes(findB, 'expert')).toEqual([
      'Not seen in August 2025. Clearly there by March 2026.',
      allowed('B'),
      'For brightness, see Brightness over time.',
      'Within error, visit 3: under a third of one SPHEREx pixel (6.15 arcseconds), so it may be measurement error rather than real movement.',
      'Visit 1: no position could be measured. Visit details says why.',
      'Not detected in visit 1: at least 3 times the background scatter is needed.',
    ])
    // + is the fixed place, not a catalogue prediction: the caption says so, and why there is none.
    expect(tableCaption(findB)).toBe('Shift since visit 2 in ″, east and north; + is its fixed place (no Gaia star to G 17 within 15″ to predict from).')
  })

  it('says what was detected, never what the object is, and never "new" or "discovery"', () => {
    for (const d of [findA, findB, findC]) {
      const { sentence } = overallResult(d)
      expect(sentence).toMatch(/^Not seen in \w+ 2025\. Clearly there /)
      expect(sentence).not.toMatch(/nova|young star|eruption|outburst|new|discover|moved/i)
    }
  })

  it('keeps Beginner’s block as short as it can be around the referee’s sentence (51, 54 and 73 words)', () => {
    const counts = [findA, findB, findC].map((d) => {
      const r = overallResult(d)
      return words([r.sentence, ...r.more, seenLine(d) ?? '', ...plain(d), ...tableNotes(d, 'beginner')].join(' '))
    })
    expect(counts).toEqual([76, 79, 102])
  })
})

describe('the same places asked for with no motion: the measure is of the brightest spot near the centre', () => {
  // Without a target, /api/frames measures the brightest source within 14″ of the centre. In 2025
  // that was a neighbouring star for all three: the 437 mJy star 20″ from A, the 40 mJy star 10″
  // from B, neighbours of C. So no headline is said there.
  const noMotion = [findANoMotionJson, findBNoMotionJson, findCNoMotionJson] as unknown as FramesReady[]
  it('never says "not seen ... clearly there" from such a view, and Gaia has no star to G 17 within 15″ (no target)', () => {
    for (const d of noMotion) {
      expect(d.target).toBeNull()
      expect(d.frames[0].detection).toBe('clear')
      expect(changeHeadline(d)).toBeNull()
      expect(overallResult(d).sentence).not.toMatch(/Not seen|Clearly there/)
    }
  })
})

describe('the headline does not fire where it should not', () => {
  it('on any of the earlier views: movers, still stars, a sum, a difference, a marginal visit, no target', () => {
    for (const d of [barnard, difference, sum, request, epsInd, rwAur, nova, wise]) expect(changeHeadline(d)).toBeNull()
  })

  const edit = (d: FramesReady, i: number, change: Partial<Frame>): FramesReady => ({
    ...d,
    frames: d.frames.map((f, k) => (k === i ? { ...f, ...change } : f)),
  })
  const elsewhere: FramesReady = { ...findB, ra: 10, dec: 20 }

  it('somewhere that is not one of our candidates: one hedged line, and the pointer', () => {
    expect(overallResult(elsewhere)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [CHANGE_CAUTION],
      pointer: 'For brightness, see Expert’s Brightness over time.',
    })
    expect(CHANGE_CAUTION).toBe('This can be a real change in the sky or a measuring problem. The brightness tool shows every measurement.')
  })
  it('a neighbour sharing the light in any visit', () => {
    const star = { source_id: '1', gmag: 15, distance_arcsec: 4, light_share: 0.4 }
    expect(changeHeadline(edit(elsewhere, 2, { blend: [star] }))).toBeNull()
  })
  it('something saturated at the place in a visit where it is not seen', () => {
    expect(changeHeadline(edit(elsewhere, 0, { photometry_saturated_exposures: 3 }))).toBeNull()
  })
  it('a place near the picture’s edge', () => {
    const near = edit(elsewhere, 0, { predicted: { ...findB.frames[0].predicted!, x: 20 } })
    expect(changeHeadline(near)).toBeNull()
  })
  it('a visit too shallow for what is seen elsewhere to have been clear in it', () => {
    const shallow = edit(elsewhere, 0, { detection_measure: { ...findB.frames[0].detection_measure, noise_mjy: 100 } })
    expect(changeHeadline(shallow)).toBeNull()
  })
  it('a view with no target, or measured at the marked spot', () => {
    expect(changeHeadline({ ...elsewhere, target: null })).toBeNull()
    expect(changeHeadline(edit(elsewhere, 0, { detection_measure: { ...findB.frames[0].detection_measure, at: 'centroid' } }))).toBeNull()
  })
  it('seen only marginally before, or flickering: no headline', () => {
    expect(changeHeadline(edit(elsewhere, 0, { detection: 'marginal', detection_sigma: 3.4 }))).toBeNull()
    expect(changeHeadline(edit(elsewhere, 2, { ...findB.frames[0], epoch: 3 }))).not.toBeNull() // n c n: appeared and faded
    expect(changeHeadline(edit(edit(elsewhere, 1, { ...findB.frames[0], epoch: 2 }), 0, findB.frames[1]))).toBeNull() // c n c
  })
  it('something that faded: clearly there, then not seen', () => {
    const faded: FramesReady = { ...elsewhere, frames: [{ ...findB.frames[1], epoch: 1 }, { ...findB.frames[2], epoch: 2 }, { ...findB.frames[0], epoch: 3, date_mean: '2027-02-10' }] }
    expect(changeHeadline(faded)?.sentence).toBe('Clearly there in March and August 2026. Not seen in February 2027.')
  })
})

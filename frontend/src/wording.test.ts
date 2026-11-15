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
// Saved by the truth review (15 Nov 2026): a typed position with no known object, R Draconis in
// detector 1, V462 Lupi in detector 3, WISE 0855 in detector 1.
import noMatchJson from './fixtures/frames/nomatch241_d6.json'
import rdraD1Json from './fixtures/frames/rdra_d1.json'
import v462D3Json from './fixtures/frames/v462lup_d3.json'
import wiseD1Json from './fixtures/frames/wise0855_d1.json'
import findAJson from './fixtures/frames/find_a_d6.json'
import findANoMotionJson from './fixtures/frames/find_a_d6_nomotion.json'
import findBJson from './fixtures/frames/find_b_d6.json'
import findBNoMotionJson from './fixtures/frames/find_b_d6_nomotion.json'
import findCJson from './fixtures/frames/find_c_d5.json'
import findCNoMotionJson from './fixtures/frames/find_c_d5_nomotion.json'
import findC6Json from './fixtures/frames/find_c_d6.json'
import { CANDIDATE_LINE, FINDS } from './finds'
import { infoFor, INFO_NAMES, movementInfo, pictureInfo } from './guide'
import {
  BRIGHTNESS_LINE,
  CHANGE_CAUTION,
  TIMES_SCATTER_NOTE,
  beforeAfter,
  brightnessMayBeTheChange,
  catalogueCheck,
  catalogueLine,
  changeHeadline,
  compassWord,
  expertVerdict,
  markMotionFrom,
  dateSpan,
  expertCells,
  expertResult,
  flagsNote,
  isDrifting,
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
const noMatch = noMatchJson as unknown as FramesReady
const rdraD1 = rdraD1Json as unknown as FramesReady
const v462D3 = v462D3Json as unknown as FramesReady
const wiseD1 = wiseD1Json as unknown as FramesReady

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
      more: ["Gaia's star map predicted 10.3 arcseconds: they agree."],
      pointer: null,
    })
    // What that means is in the movement line's "i" (guide.ts), so the column stays short.
    expect(isDrifting(barnard)).toBe(true)
    expect(brightnessMayBeTheChange(barnard)).toBe(false)
    const check = catalogueCheck(barnard)
    expect(check?.differ).toBeCloseTo(1.44, 2) // measured minus predicted, visit 1 to 3
    expect(check?.bar).toBeCloseTo(4.24, 2) // three times the two 1-arcsecond position errors
    expect(seenLine(barnard)).toBe('Seen clearly in all 3 visits.')
  })
  it("gives Beginner one row per visit: the visit and how far it had moved, in arcseconds", () => {
    // The totals of Expert's rows (6.0 and 10.4); the way it went is in the sentence over the table.
    expect(plain(barnard)).toEqual(['start', '6.0', '10.4'])
    expect(tableNotes(barnard, 'beginner')).toEqual([])
  })
  it('gives Expert every number of every visit, two lines each', () => {
    // "px" says whose pixel: SPHEREx's own, not the 2″ squares the picture is drawn on.
    expect(tableCaption(barnard)).toBe('Shift since visit 1 in ″, east and north; + from Gaia. px: SPHEREx pixels of 6.15″.')
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
  it("gives Expert the run against Gaia in one line, in a scientist's units", () => {
    // East -2.21, north +10.16: PA 348 (the blind search's own bearing); Gaia's -0.8, +10.3: PA 356.
    // The two 1-arcsecond position errors in quadrature: 1.4; the residual 1.44 is 1.0 sigma of it.
    expect(expertVerdict(barnard)).toBe('Visit 1 → 3 (1.0 yr): measured 10.4 ± 1.4″ at PA 348°; Gaia DR3 predicts 10.3″ at PA 356°; residual 1.4″ (1.0σ): consistent.')
    expect(expertVerdict(nova)).toBeNull() // nothing predicted
    expect(expertVerdict(sum)).toBeNull()
    // RW Aurigae barely moves: no position angle for a shift under a third of a pixel.
    expect(expertVerdict(rwAur)).toMatch(/^Visit 1 → 3 \(1\.0 yr\): measured 0\.9 ± [\d.]+″; the given motion predicts 0\.0″; residual [\d.]+″ \([\d.]+σ\): consistent\.$/)
  })
  it('says the row of a visit stepped to, for a screen reader', () => {
    expect(rowAnnouncement(barnard, 0)).toBe('Visit 1 of 3, August 2025: where it started.')
    // The total first, as the table shows it (6.0), then its parts.
    expect(rowAnnouncement(barnard, 1)).toBe('Visit 2 of 3, March 2026: moved 6.0 arcseconds (5.9 north, 0.9 west).')
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
    expect(tableCaption(request)).toBe('Shift since visit 1 in ″, east and north; + from the motion given. px: SPHEREx pixels of 6.15″.')
    expect(catalogueLine(request)).toBe('Its catalogue motion predicted 10.3 arcseconds: they agree.')
  })
  it('says Gaia DR3 predicts when the motion given is the one the name lookup took from Gaia DR3 (src=gaia)', () => {
    const t = request.target!
    const gaia = markMotionFrom(request, 'gaia', t.pmra, t.pmdec)
    expect(tableCaption(gaia)).toBe('Shift since visit 1 in ″, east and north; + from Gaia. px: SPHEREx pixels of 6.15″.')
    expect(expertVerdict(gaia)).toMatch(/; Gaia DR3 predicts 10\.3″/)
    expect(expertVerdict(request)).toMatch(/; the given motion predicts 10\.3″/)
    // Only for that very motion, and never for a view the server already matched to a Gaia star.
    expect(markMotionFrom(request, 'gaia', 0, 0)).toBe(request)
    expect(markMotionFrom(request, null, t.pmra, t.pmdec)).toBe(request)
    expect(markMotionFrom(barnard, 'gaia', null, null)).toBe(barnard)
  })
})

describe('an object that stayed in place: RW Aurigae', () => {
  it('says no movement and why, never "it did not move" alone; brightness may be the change', () => {
    // The catalogue's agreement ("it barely moves") is in the movement line's "i"; the column
    // points to the Brightness tool instead, since what changed may be its brightness.
    expect(overallResult(rwAur)).toEqual({
      sentence: 'No movement seen between September 2025 and September 2026.',
      more: [`Any shift was under a third of a pixel. ${BRIGHTNESS_LINE}`],
      pointer: null,
    })
    expect(catalogueLine(rwAur)).toBe('Its catalogue motion predicted almost no shift: it barely moves.')
    // The movement line's "i" then points to the Brightness tool in the bar (guide.ts).
    expect(brightnessMayBeTheChange(rwAur)).toBe(true)
    expect(isDrifting(rwAur)).toBe(false)
    // The sentence says "within error" for every row, so the rows do not repeat it.
    expect(plain(rwAur)).toEqual(['start', '0.8', '0.9'])
  })
  it('keeps every caution in Expert, said once', () => {
    expect(tableNotes(rwAur, 'expert')).toEqual([
      'Within error, visits 2 and 3: under a third of one SPHEREx pixel (6.15 arcseconds), so it may be measurement error rather than real movement.',
      'The core is overexposed in visits 1 and 2, so each position is good to about 1″, not the much smaller error of the fit.',
      'Visits 1, 2 and 3: a star 1.6″ to 1.7″ away (Gaia G 12.2) is too close to separate from the target, so the position and brightness include its light.',
    ])
    expect(rowAnnouncement(rwAur, 1)).toBe('Visit 2 of 3, March 2026: shifted 0.8 arcseconds (0.2 south, 0.8 east), within measuring error.')
  })
})

describe('a view with no known object at the centre: Nova V572 Velorum, detector 2', () => {
  it('never calls the shift of the marked spot movement', () => {
    const r = overallResult(nova)
    expect(r.sentence).toBe('The marked spot shifted 6.8 arcseconds between June 2025 and June 2026.')
    expect(r.more).toEqual([`No known object is listed at the centre, so this may be a different spot, not movement. ${BRIGHTNESS_LINE}`])
    expect(JSON.stringify([r, plain(nova)])).not.toMatch(/moved/)
    expect(tableNotes(nova, 'expert')).toContain('No known object is listed at the centre, so the shift in visits 2 and 3 may be a different spot, not movement.')
    expect(tableNotes(nova, 'expert')).toContain('No Gaia star near the centre, so there is no predicted motion to compare with.')
    expect(rowAnnouncement(nova, 2)).toBe('Visit 3 of 3, June 2026: shifted 6.8 arcseconds (5.5 south, 4.0 west), which may be a different spot.')
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
    expect(plain(epsInd)).toEqual(['start', '1.7, within error', '4.4', '6.3'])
    expect(tableNotes(epsInd, 'beginner')).toEqual(['Within error: too small to be sure.'])
    expect(expert(epsInd)[1].about).toMatch(/· within error$/)
    expect(overallResult(epsInd).sentence).toBe('It moved 6.3 arcseconds south-east between May 2025 and September 2026.')
  })
})

describe('difference mode: each visit minus visit 1', () => {
  it('has one row fewer (visit 1 is subtracted) and measures from visit 1', () => {
    expect(tableRows(difference).map((r) => r.frame.epoch)).toEqual([2, 3])
    expect(plain(difference)).toEqual(['6.0', '10.4'])
    expect(tableNotes(difference, 'expert').slice(0, 2)).toEqual([
      'Visit 1 is the one subtracted, so the shifts are measured from it.',
      "The positions were measured in each visit's own image, not in the difference.",
    ])
    expect(rowAnnouncement(difference, 0)).toBe('Visit 2 of 3, March 2026: moved 6.0 arcseconds (5.9 north, 0.9 west).')
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

describe('saved views the truth review found (15 Nov 2026)', () => {
  it('no known object at the centre, a middle visit far off and the last one back: never "came back", always "may be a different spot"', () => {
    // 241.70906, -52.20564, detector 6: visits 2 and 3 landed on other spots up to 23.8 arcseconds away.
    const r = overallResult(noMatch)
    expect(r.sentence).toBe('The marked spot shifted by up to 23.8 arcseconds between August 2025 and August 2026.')
    expect(r.more[0]).toMatch(/^No known object is listed at the centre, so this may be a different spot, not movement\./)
    expect(JSON.stringify(r)).not.toMatch(/came back|moved/)
  })
  it('R Draconis in detector 1: a middle visit over a third of a pixel is "within the measuring error", not "under a third of a pixel"', () => {
    const r = overallResult(rdraD1)
    expect(r.sentence).toBe('No movement seen between July 2025 and July 2026.')
    expect(r.more[0]).toBe(`Any shift was within the measuring error. ${BRIGHTNESS_LINE}`)
    expect(plain(rdraD1)).toContain('2.4')
  })
  it('V462 Lupi in detector 3: no known object and a 2.2-arcsecond shift, so "may be a different spot" stays', () => {
    const r = overallResult(v462D3)
    expect(r.sentence).toMatch(/^The marked spot shifted by up to 2\.2 arcseconds /)
    expect(r.more[0]).toMatch(/^No known object is listed at the centre, so this may be a different spot, not movement\./)
  })
  it('WISE 0855 in detector 1: not seen in any visit, said without "all"', () => {
    expect(seenLine(wiseD1)).toBe('Not seen in any of the 3 visits.')
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
    expect(plain(lost)).toEqual(['start', 'not found', '10.4'])
    expect(expert(lost)[1].measured).toBe('not found')
    // Why, from the backend's own reason (here: off the picture).
    expect(tableNotes(lost, 'beginner')).toEqual(['Not found in visit 2: that place is at the edge of the picture, or has no data.'])
    expect(tableNotes(lost, 'expert')).toContain('Visit 2: no position could be measured. Visit details says why.')
    expect(overallResult(lost).sentence).toBe('It moved 10.4 arcseconds north between August 2025 and August 2026.')
    expect(rowAnnouncement(lost, 1)).toBe('Visit 2 of 3, March 2026: no position could be measured.')
  })
  it('never quotes a shift from a visit where it was not found', () => {
    const firstLost: FramesReady = { ...barnard, frames: barnard.frames.map((f, i) => (i === 0 ? ({ ...f, centroid: null } as Frame) : f)) }
    // Measured from visit 2, and the sentence says which visits.
    expect(overallResult(firstLost).sentence).toMatch(/^It moved 4\.\d arcseconds .* between visit 2 \(March 2026\) and visit 3 \(August 2026\)\.$/)
    expect(plain(firstLost)).toEqual(['not found', 'start', expect.stringMatching(/^4\.\d$/)])
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
    expect(plain(many).slice(3)).toEqual(['10.4', '10.4', '10.4'])
    expect(rowAnnouncement(many, 5)).toBe('Visit 6 of 6, December 2027: moved 10.4 arcseconds (10.2 north, 2.2 west).')
    expect(seenLine(many)).toBe('Seen clearly in all 6 visits.')
  })
  it('a missing visit number is said with the visit’s place in the run', () => {
    const gap = { ...barnard, frames: [barnard.frames[0], barnard.frames[1], { ...barnard.frames[2], epoch: 4 }] }
    expect(rowAnnouncement(gap, 2)).toBe('Visit 4, number 3 of 3, August 2026: moved 10.4 arcseconds (10.2 north, 2.2 west).')
  })
  it('a difference view whose subtracted visit has no position says which visit the shifts start from', () => {
    const blind = { ...difference, reference_frame: { ...difference.reference_frame, centroid: null } } as FramesReady
    const notes = tableNotes(blind, 'expert')
    expect(notes).not.toContain('Visit 1 is the one subtracted, so the shifts are measured from it.')
    expect(notes[0]).toBe('Visit 1 is the one subtracted. It has no measured position, so the shifts are measured from visit 2.')
  })
  it('a large expected shift that agrees only because the error is large is not "it barely moves"', () => {
    // Barnard's frames with both positions only good to 1.2 arcseconds and the shift cut to 2.5:
    // within error of a 2.5-arcsecond prediction, which is more than a third of a pixel.
    const scale = 2.5 / 10.4
    type Place = { ra: number; dec: number }
    const s0 = barnard.frames[0].centroid as Place
    const p0 = barnard.frames[0].predicted as Place
    const toward = <T extends Place>(at: T, from: Place): T => ({ ...at, ra: from.ra + (at.ra - from.ra) * scale, dec: from.dec + (at.dec - from.dec) * scale })
    const shrunk: FramesReady = {
      ...barnard,
      frames: barnard.frames.map((f, i) =>
        !f.centroid || i === 0
          ? f
          : ({ ...f, centroid: { ...toward(f.centroid, s0), err_arcsec: 1.2 }, predicted: f.predicted ? toward(f.predicted, p0) : f.predicted } as Frame),
      ),
    }
    const line = catalogueLine(shrunk) ?? ''
    expect(line).not.toMatch(/barely moves/)
    expect(line).toMatch(/^Gaia's star map predicted 2\.\d arcseconds/)
  })
  it('the Flags legend speaks of every visit at once', () => {
    expect(flagsNote(barnard)).toBe(
      ": no value in any exposure of a frame (none here). For measuring brightness the star's core is saturated in some exposures, even where the image looks fine: 18 of 18 in visit 1, 19 of 19 in visit 2, 23 of 25 in visit 3.",
    )
  })
})

// The three candidates of our sweep (finds.ts), on the server's real answers of 15 Nov 2026 for the
// views their buttons ask for: the corrected position, held still (pmra = pmdec = 0), in detector 6.
// The page's own measure, per visit, against the referee's ruling:
//   A: -6.2 (not seen), 521, 168 times the scatter (fitted 1,925 and 631 mJy). Ruling: about 0 in
//     Aug-Sep 2025 once the 437 mJy star 20″ away is modelled; 2.4-2.9 Jy in spring 2026; 0.67-0.80 Jy in Aug 2026.
//   B: -2.6, 282, 619 (377 and 926 mJy). Ruling: about 0 in 2025; about 400 mJy in March, 1,000-1,090 in August.
//   C: -1.4, 92 (129 mJy), unknown (two April exposures partly spoiled), 3.3 (marginal). Ruling: about
//     0 in 2025; 85-110 mJy in Feb-Mar 2026; a third of that in April; 3-5 mJy in Jul-Sep 2026, lines persisting.
//   C in detector 5 reads "not seen" in August 2026 (0.7 times the scatter), which reads as "back to
//   nearly nothing", a phrase the ruling forbids: the page shows C in detector 6.
const findA = findAJson as unknown as FramesReady
const findB = findBJson as unknown as FramesReady
const findC5 = findCJson as unknown as FramesReady
const findC = findC6Json as unknown as FramesReady
const find = (key: string) => FINDS.find((f) => f.key === key)!
const allowed = (key: string) => find(key).allowed

describe('something that appears: the three candidates', () => {
  it('A: the headline, then the table, then the referee’s sentence under it; no pointer to the brightness tool', () => {
    expect(overallResult(findA)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [],
      after: [CANDIDATE_LINE],
      pointer: null,
    })
    // Beginner's column says how clearly it is seen in each visit, and how it changed from the last
    // visit it was clearly seen in, by the page's own measure (1,925 then 631 mJy: fainter).
    expect(plainColumn(findA)).toEqual({ header: 'Seen', label: 'Every visit, and how clearly it is seen in it' })
    expect(plain(findA)).toEqual(['not seen', 'seen clearly', 'seen clearly, fainter'])
    expect(tableNotes(findA, 'beginner')).toEqual([])
    expect(seenLine(findA)).toBeNull()
  })

  it('B: brighter in August than in March, and "not seen" where it is not seen, at both levels', () => {
    expect(overallResult(findB)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [],
      after: [CANDIDATE_LINE],
      pointer: null,
    })
    expect(plain(findB)).toEqual(['not seen', 'seen clearly', 'seen clearly, brighter'])
    // Nothing is predicted for a candidate held at its place, so there is nothing to differ from.
    expect(expert(findB)[0]).toEqual({ measured: 'not seen', total: '', predicted: '', differ: '', about: '2–21 Aug 2025 · 18 exp. · not seen' })
    expect(expert(findB)[2].measured).toBe('−0.3, +0.1') // Expert keeps the shifts: within error, as its notes say
    // The reviewers' 0.3 arcsec, not the fit's 0.03: the shift of 0.3″ is then plainly within error.
    expect(expert(findB)[1].about).toBe('8–16 Mar 2026 · 19 exp. · clear, 282× · ±0.3″')
    expect(rowAnnouncement(findB, 0)).toBe('Visit 1 of 3, August 2025: not seen.')
    expect(rowAnnouncement(findB, 2)).toBe('Visit 3 of 3, August 2026: seen clearly, brighter.')
    // Held still at its place by the page, not by any catalogue: no "catalogue motion" anywhere.
    expect(catalogueCheck(findB)).toBeNull()
    expect(catalogueLine(findB)).toBeNull()
    expect([...movementInfo(findB), ...pictureInfo(findB, 'Candidate B')].join(' ')).not.toMatch(/catalogue/i)
  })

  it('C, in detector 6: appeared and faded again, still only just seen in August 2026; the spoiled April visit is said so', () => {
    expect(overallResult(findC)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there in March 2026, and faint again by August 2026.',
      more: [],
      after: [CANDIDATE_LINE],
      pointer: null,
    })
    expect(plain(findC)).toEqual(['not seen', 'seen clearly', 'picture spoiled here', 'only just seen'])
    expect(tableNotes(findC, 'beginner')).toEqual([])
    expect(rowAnnouncement(findC, 2)).toBe('Visit 3 of 4, April 2026: picture spoiled here.')
    // In detector 5, August 2026 reads "not seen": the reason the page shows detector 6.
    expect(plain(findC5)).toEqual(['not seen', 'seen clearly', 'not seen'])
  })

  it('Blink and the labels on the picture compare the visit without it and the first one with it', () => {
    expect(beforeAfter(findA)).toEqual({ before: 0, after: 1 })
    expect(beforeAfter(findB)).toEqual({ before: 0, after: 1 })
    expect(beforeAfter(findC)).toEqual({ before: 0, after: 1 }) // never visit 1 and visit 4, both without it
    for (const d of [barnard, difference, sum, request, epsInd, rwAur, nova, wise]) expect(beforeAfter(d)).toBeNull()
  })

  it('Expert: the headline, the referee’s sentence and the reviewers’ brightness over the table; the candidate’s notes first under it, then every caution', () => {
    expect(expertResult(findB)).toEqual({
      sentence: 'Not seen in August 2025. Clearly there by March 2026.',
      more: [allowed('B'), find('B').brightness],
      pointer: null,
    })
    expect(tableNotes(findB, 'expert')).toEqual([
      TIMES_SCATTER_NOTE,
      find('B').neighbour,
      `This picture is detector 6 (4.4–5.0 micrometres). ${find('B').dates}`,
      find('B').probably,
      find('B').checked,
      'Within error, visit 3: under a third of one SPHEREx pixel (6.15 arcseconds), so it may be measurement error rather than real movement.',
      'Visit 1: no position could be measured. Visit details says why.',
      'Not detected in visit 1: at least 3 times the background scatter is needed.',
    ])
    expect(tableNotes(findC, 'expert')).toContain(find('C').spoiled!.note)
    // + is the corrected place, not a catalogue prediction: the caption says so.
    expect(tableCaption(findB)).toBe('Shift since visit 2 in ″, east and north; + marks its corrected place, where it is held (no catalogue gives it a motion).')
    // Anywhere else, Expert has no sentence over its table.
    expect(expertResult(barnard)).toBeNull()
  })

  it('never points a candidate to the brightness tool, whose 2025 circle held a neighbour’s light', () => {
    for (const d of [findA, findB, findC]) {
      const r = overallResult(d)
      const e = expertResult(d)!
      expect([r.sentence, ...r.more, ...(r.after ?? []), r.pointer ?? '', e.sentence, ...e.more, ...tableNotes(d, 'expert')].join(' ')).not.toMatch(
        /Brightness over time|brightness tool/,
      )
    }
  })

  it('says what was detected, never what the object is, and never "new" or "discovery"', () => {
    for (const d of [findA, findB, findC]) {
      const { sentence } = overallResult(d)
      expect(sentence).toMatch(/^Not seen in \w+ 2025\. Clearly there /)
      expect(sentence).not.toMatch(/nova|young star|eruption|outburst|new|discover|moved/i)
    }
  })

  it('keeps Beginner’s words few: one short line under the table instead of the referee’s sentence (35, 35 and 44 words)', () => {
    const counts = [findA, findB, findC].map((d) => {
      const r = overallResult(d)
      return words([r.sentence, ...r.more, ...(r.after ?? []), seenLine(d) ?? '', ...plain(d), ...tableNotes(d, 'beginner')].join(' '))
    })
    expect(counts).toEqual([35, 35, 44])
  })
  it('Beginner’s line under a candidate’s table has an "i" that quotes the referee’s allowed sentence word for word', () => {
    for (const [d, key] of [[findA, 'A'], [findB, 'B'], [findC, 'C'], [findC5, 'C']] as const) {
      expect(overallResult(d).after).toEqual([CANDIDATE_LINE])
      expect(infoFor('candidate', d)).toEqual([allowed(key)])
      // Expert keeps the whole sentence on the page.
      expect(expertResult(d)?.more[0]).toBe(allowed(key))
    }
    expect(INFO_NAMES.candidate).toBe('About this candidate')
    // Nowhere else is there anything behind it.
    expect(infoFor('candidate', barnard)).toEqual([])
    expect(infoFor('candidate', null)).toEqual([])
    expect(CANDIDATE_LINE).toBe('A candidate: we found it in no catalogue or report we checked, and nobody has confirmed it yet.')
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
      // CHANGE_CAUTION already names the brightness tool, so no line of its own points there.
      more: [CHANGE_CAUTION],
      pointer: null,
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

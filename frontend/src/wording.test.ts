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
import {
  BRIGHTNESS_LINE,
  brightnessMayBeTheChange,
  catalogueCheck,
  catalogueLine,
  compassWord,
  expertVerdict,
  dateSpan,
  expertCells,
  flagsNote,
  isDrifting,
  monthYearLong,
  overallResult,
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
      more: ["Gaia's star map predicted 10.3 arcseconds: the two agree."],
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
    expect(catalogueLine(request)).toBe('Its catalogue motion predicted 10.3 arcseconds: the two agree.')
  })
})

describe('an object that stayed in place: RW Aurigae', () => {
  it('says no movement and why, never "it did not move" alone; brightness may be the change', () => {
    // The catalogue's agreement ("it barely moves") is in the movement line's "i"; the column
    // points to the Brightness tool instead, since what changed may be its brightness.
    expect(overallResult(rwAur)).toEqual({
      sentence: 'No movement seen between September 2025 and September 2026.',
      more: [`Any shift was under a third of a pixel. ${BRIGHTNESS_LINE}`],
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

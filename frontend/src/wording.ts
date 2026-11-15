// Plain-language sentences built from an /api/frames response. Every number in them
// comes from the response.
//
// "The words hold still": while the visits play, no word on the page may change. So the
// side column does not describe "the visit on screen"; it shows one table of every visit
// (visitRows), one sentence about the whole run (overallResult) and notes said once
// (tableNotes). Only the mark of the row on screen moves.
import { NATIVE_PIXEL_ARCSEC, type Frame, type FramesReady, type Target } from './api'
import { blendNotes, coreNotes, detectionNotes, detectionShort, isMarginal, listVisits } from './detection'
import { measuredRows, SMALL_SHIFT_ARCSEC, shiftBetween, shiftFromStart, startCentroid, visitRows, type Shift, type VisitFrame, type VisitRow } from './motion'

export { listVisits }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** When the exposures of a frame were taken and how many there are. */
function whenAndHowMany(frame: Frame): string {
  const when = frame.date_start === frame.date_end ? frame.date_start : `${frame.date_start} to ${frame.date_end}`
  return `${when}, ${plural(frame.n_exposures, 'exposure', 'exposures')}`
}

/**
 * What a frame is, by visit number and dates rather than by its place in the list: a
 * detector can miss a visit, and "frame 1 of 2" beside "visit 2" would confuse.
 */
export function frameLabel(frame: Frame, data: FramesReady): string {
  if (data.mode === 'sum') {
    const visits = frame.epochs_combined
    const which = visits?.length ? listVisits(visits) : 'every visit'
    return `${which.charAt(0).toUpperCase()}${which.slice(1)} added together: ${whenAndHowMany(frame)}`
  }
  if (data.mode === 'difference') {
    const minus = frame.reference_epoch != null ? `visit ${frame.reference_epoch}` : 'the average of all visits'
    return `Visit ${frame.epoch} minus ${minus}: ${whenAndHowMany(frame)}`
  }
  return `Visit ${frame.epoch}: ${whenAndHowMany(frame)}`
}

/** A short name for a frame, for the marks under the scrubber. */
export function frameTick(frame: Frame, data: FramesReady): string {
  if (data.mode === 'sum') return 'all'
  return String(frame.epoch)
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2025-06-19" as "Jun 2025". Read from the text, so the time zone cannot shift the month. */
export function monthYear(iso: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(iso)
  const month = m ? MONTHS[Number(m[2]) - 1] : undefined
  return m && month ? `${month} ${m[1]}` : iso
}

/**
 * A frame's caption in the strip of visits: "Visit 2" over "Jun 2025" (the month of its
 * middle date; the full dates are in its label), or for a sum, "All visits" over the
 * years it spans.
 */
export function visitCaption(frame: Frame, data: FramesReady): { name: string; when: string } {
  if (data.mode === 'sum') {
    const a = frame.date_start.slice(0, 4)
    const b = frame.date_end.slice(0, 4)
    return { name: 'All visits', when: a === b ? a : `${a} to ${b}` }
  }
  return { name: `Visit ${frame.epoch}`, when: monthYear(frame.date_mean) }
}

/** How far the marked object in this frame is from where it started, in words. */
export function motionSentence(frame: Frame, data: FramesReady): string {
  if (!frame.centroid) return 'No position could be measured in this frame.'
  if (data.frames.length === 1 && !data.reference_frame) {
    return data.mode === 'sum'
      ? 'Every visit is in this one frame, so nothing moves in it.'
      : 'This is the only visit so far with this detector, so there is nothing to compare it with yet.'
  }
  if (frame.centroid === startCentroid(data)) return 'This is where it started. Later frames are measured against it.'
  const shift = shiftFromStart(data, frame)
  if (!shift) return 'No position could be measured in this frame.'
  if (shift.total < 0.05) return 'Measured in the same place as at the start.'
  const parts: string[] = []
  if (Math.abs(shift.north) >= 0.05) parts.push(`${Math.abs(shift.north).toFixed(1)} ${shift.north > 0 ? 'north' : 'south'}`)
  if (Math.abs(shift.east) >= 0.05) parts.push(`${Math.abs(shift.east).toFixed(1)} ${shift.east > 0 ? 'east' : 'west'}`)
  const moved = `Moved ${shift.total.toFixed(1)} ${shift.total.toFixed(1) === '1.0' ? 'arcsecond' : 'arcseconds'} from where it started: ${parts.join(', ')}.`
  if (shift.total >= SMALL_SHIFT_ARCSEC) return moved
  return `${moved} That is under a third of one SPHEREx pixel (${NATIVE_PIXEL_ARCSEC} arcseconds), so it may be measurement error rather than real movement.`
}

/** One line on how to read the frames in the mode they were made in. */
export function modeSentence(data: FramesReady): string {
  if (data.mode === 'difference') {
    const minus = data.reference === 'mean' ? 'the average of all visits' : `visit ${data.reference_frame?.epoch ?? data.frames[0]?.reference_epoch ?? 1}`
    return `Difference: each frame is one visit minus ${minus}. Grey is no change, white is brighter, black is fainter.`
  }
  if (data.mode === 'sum') {
    if (data.registration === 'target_motion') {
      return "Sum, following the target: every exposure is shifted along the target's known motion and then added, so the target is sharp and the stars around it are smeared."
    }
    return 'Sum: every exposure from every visit added into one deeper frame. Nothing moves in it, and anything that moved between visits is smeared.'
  }
  return 'Normal: one frame for each visit SPHEREx has made to this patch of sky. Play them to see what moved or changed.'
}

/**
 * A note for frames with saturated pixels; null when there are none. It points to the
 * long-wavelength detectors without promising anything: Barnard's Star is clean in
 * detectors 5 and 6, but R Draconis saturates in every detector.
 */
export function saturationSentence(data: FramesReady): string | null {
  const n = data.frames.length
  const k = data.frames.filter((f) => f.saturated_pixels > 0).length
  if (k === 0) return null
  const which = n === 1 ? 'This frame has' : k === n ? `All ${n} frames have` : `${k} of the ${n} frames ${k === 1 ? 'has' : 'have'}`
  const advice =
    data.detector <= 4
      ? 'The long-wavelength detectors, 5 and 6, are often better, but not always.'
      : `This is one of the two long-wavelength detectors, which are often better than the rest, but not always. Detector ${data.detector === 5 ? 6 : 5} may be no cleaner.`
  return `${which} saturated pixels: a bright core is overexposed in detector ${data.detector} and shows as a flat white patch. ${advice}`
}

/** A note for frames built without some exposures; null when every download worked. */
export function failuresSentence(data: FramesReady): string | null {
  const n = data.failures?.length ?? 0
  if (n === 0) return null
  return `${plural(n, 'exposure', 'exposures')} could not be downloaded from NASA's archive, so these frames are built from fewer exposures than exist.`
}

// ---- the table of every visit, and the words about the whole run ----------------------------
//
// Nothing below takes "the visit on screen". Each function describes every visit, or the run
// from the first measured visit to the last, so its words are the same whichever visit is
// shown. Built on visitRows (motion.ts): shifts from the first visit with a position.

const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2025-08-26" as "August 2025", read from the text. */
export function monthYearLong(iso: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(iso)
  const month = m ? MONTHS_LONG[Number(m[2]) - 1] : undefined
  return m && month ? `${month} ${m[1]}` : iso
}

/** "21–30 Aug 2025", "18 Aug–22 Sep 2026", "22 Dec 2025–20 Jan 2026", "5 May 2025". */
export function dateSpan(start: string, end: string): string {
  const read = (iso: string) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
    const month = m ? MONTHS[Number(m[2]) - 1] : undefined
    return m && month ? { y: m[1], m: month, d: String(Number(m[3])) } : null
  }
  const a = read(start)
  const b = read(end)
  if (!a || !b) return start === end ? start : `${start} to ${end}`
  if (start.slice(0, 10) === end.slice(0, 10)) return `${a.d} ${a.m} ${a.y}`
  if (a.y === b.y && a.m === b.m) return `${a.d}–${b.d} ${a.m} ${a.y}`
  if (a.y === b.y) return `${a.d} ${a.m}–${b.d} ${b.m} ${a.y}`
  return `${a.d} ${a.m} ${a.y}–${b.d} ${b.m} ${b.y}`
}

/** The table's rows: the frames the player shows. A difference view's subtracted visit is what the shifts start from, not a row. */
export const tableRows = (data: FramesReady): VisitRow[] => visitRows(data).filter((r) => r.index !== null)

/** Every visit there is, the subtracted one of a difference view included. */
const allVisits = (data: FramesReady): VisitFrame[] => visitRows(data).map((r) => r.frame)

const isSum = (data: FramesReady) => data.mode === 'sum'
/** One visit in all, with nothing subtracted: nothing to compare with. */
const isAlone = (data: FramesReady) => data.frames.length === 1 && !data.reference_frame && !isSum(data)

/** "5.9 north, 0.9 west" (north or south first; a part under 0.05 arcseconds is left out). `unit` goes after the first number. */
export function shiftWords(shift: Shift, unit = ''): string {
  if (shift.total < 0.05) return 'same place'
  const parts: string[] = []
  if (Math.abs(shift.north) >= 0.05) parts.push([Math.abs(shift.north).toFixed(1), shift.north > 0 ? 'north' : 'south'])
  if (Math.abs(shift.east) >= 0.05) parts.push([Math.abs(shift.east).toFixed(1), shift.east > 0 ? 'east' : 'west'])
  return parts.map(([n, way], i) => (i === 0 && unit ? `${n} ${unit} ${way}` : `${n} ${way}`)).join(', ')
}

/** The way it went, as one of eight compass words. */
export function compassWord(shift: Pick<Shift, 'east' | 'north'>): string {
  const ways = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west']
  const angle = (Math.atan2(shift.east, shift.north) * 180) / Math.PI // 0 north, 90 east
  return ways[(Math.round(angle / 45) + 8) % 8]
}

/** "Visit 2"; "All visits" for a sum. The same name as the visit's thumbnail. */
export const rowName = (frame: Pick<Frame, 'epoch'>, data: FramesReady): string => (isSum(data) || frame.epoch === null ? 'All visits' : `Visit ${frame.epoch}`)

/** "Mar 2026"; for a sum, the years it spans. The same as the thumbnail's caption. */
export function rowMonth(frame: VisitFrame, data: FramesReady): string {
  if (isSum(data)) {
    const a = frame.date_start.slice(0, 4)
    const b = frame.date_end.slice(0, 4)
    return a === b ? a : `${a} to ${b}`
  }
  return monthYear(frame.date_mean)
}

/**
 * Beginner's cell: what happened to it in this visit, in plain words. "start", "5.9 north,
 * 0.9 west", "1.2 south, 1.2 east, within error", "not found"; "only just seen" is added
 * for a marginal detection.
 */
export function plainResult(row: VisitRow, data: FramesReady): string {
  let words: string
  if (isSum(data)) words = 'every visit in one picture'
  else if (isAlone(data)) words = 'the only visit so far'
  else if (row.start) words = 'start'
  else if (!row.frame.centroid || !row.shift) words = 'not found'
  else words = `${shiftWords(row.shift)}${row.withinError ? ', within error' : ''}`
  return isMarginal(row.frame) ? `${words}, only just seen` : words
}

const signed = (n: number) => (Math.abs(n) < 0.05 ? '0.0' : `${n > 0 ? '+' : '−'}${Math.abs(n).toFixed(1)}`)
const pair = (p: { east: number; north: number }) => `${signed(p.east)}, ${signed(p.north)}`
/** A position error: two decimals under 0.1 arcseconds, else one; a whole number as it is. */
const errWords = (err: number) => (Number.isInteger(err) ? String(err) : err < 0.1 ? err.toFixed(2) : err.toFixed(1))

export interface ExpertCells {
  /** Measured shift since the start, east and north, or "start" / "not found". */
  measured: string
  /** Its total, arcseconds. */
  total: string
  /** The predicted shift since the start's date, east and north; "—" when nothing is predicted. */
  predicted: string
  /** How far measured and predicted differ, in arcseconds and SPHEREx pixels. */
  differ: string
  /** The second line: dates, exposures, how clearly it is seen, the position's error, and short warnings. */
  about: string
}

/** Expert's row: every number for one visit. */
export function expertCells(row: VisitRow, data: FramesReady): ExpertCells {
  const f = row.frame
  const c = f.centroid
  let measured = ''
  if (isSum(data)) measured = 'one picture'
  else if (isAlone(data)) measured = 'only visit'
  else if (row.start) measured = 'start'
  else if (!c || !row.shift) measured = 'not found'
  else measured = pair(row.shift)
  const about = [
    dateSpan(f.date_start, f.date_end),
    plural(f.n_exposures, 'exposure', 'exposures'),
    detectionShort(f),
    c?.err_arcsec != null ? `position ±${errWords(c.err_arcsec)}″` : null,
    c?.saturated_core ? 'core overexposed' : null,
    (f.blend?.length ?? 0) > 0 ? 'blended' : null,
    row.withinError ? 'within error' : null,
  ].filter((w): w is string => !!w)
  return {
    measured,
    total: row.shift ? row.shift.total.toFixed(1) : '',
    predicted: row.predicted ? pair(row.predicted) : row.start || isSum(data) || isAlone(data) ? '' : '—',
    differ: row.differ != null ? `${row.differ.toFixed(1)}″ (${(row.differ / NATIVE_PIXEL_ARCSEC).toFixed(2)} px)` : '',
    about: about.join(' · '),
  }
}

/** Whose prediction the table compares with: "Gaia", "the motion given", or null when there is none. */
export function predictedBy(target: Target | null): string | null {
  if (!target || target.pmra == null || target.pmdec == null) return null
  return target.source_id ? 'Gaia' : 'the motion given'
}

/** The visit the shifts are measured from, or null when no visit has a position. */
const startEpoch = (data: FramesReady): number | null => visitRows(data).find((r) => r.start)?.frame.epoch ?? null

/** What Expert's table holds, in one line over it. */
export function tableCaption(data: FramesReady): string {
  if (isSum(data)) return 'The sum of all visits: one picture, so there is nothing to compare.'
  if (isAlone(data)) return 'One visit only, so there is nothing to compare yet.'
  const from = startEpoch(data)
  if (from === null) return 'Every visit. No position could be measured in any of them.'
  const by = predictedBy(data.target)
  const pred = by ? `, ○ measured and + as ${by} predicts` : ', ○ measured'
  return `Shift since visit ${from} in arcseconds (″), east and north${pred}.`
}

/** Why there is no prediction to compare with; null when there is one. GaiaReadout's words. */
export function noPredictionSentence(data: FramesReady): string | null {
  const t = data.target
  if (!t) {
    return data.gaia_error
      ? `Gaia catalogue did not answer (${data.gaia_error}), so there is no prediction to compare with.`
      : 'No Gaia star near the centre, so there is no predicted motion to compare with.'
  }
  if (t.pmra == null || t.pmdec == null) {
    return `Gaia DR3 ${t.source_id} is near the centre, but Gaia lists no motion for it, so there is no predicted motion to compare with.`
  }
  return null
}

const epochsOf = (rows: VisitRow[]) => rows.flatMap((r) => (r.frame.epoch === null ? [] : [r.frame.epoch]))
const capital = (s: string) => `${s.charAt(0).toUpperCase()}${s.slice(1)}`

/** The rows with a shift under a third of a pixel, and those with no position, among the rows that are not the start. */
function warnings(data: FramesReady) {
  if (isSum(data) || isAlone(data)) return { withinError: [], notFound: [] }
  const rows = tableRows(data)
  return {
    withinError: epochsOf(rows.filter((r) => r.withinError)),
    notFound: epochsOf(rows.filter((r) => !r.start && !r.frame.centroid)),
  }
}

/**
 * The notes under the table, each said once for the visits it applies to. Expert gets every
 * caution the per-visit sentences used to carry; Beginner the few it needs.
 */
export function tableNotes(data: FramesReady, level: 'beginner' | 'expert'): string[] {
  const { withinError, notFound } = warnings(data)
  const notes: string[] = []
  if (level === 'beginner') {
    if (withinError.length && overallKind(data) === 'moved') {
      notes.push(`Within error: under a third of a pixel, so it may be a measuring error.`)
    }
    if (notFound.length) notes.push(`Not found in ${listVisits(notFound)}: no clear spot could be measured there.`)
    return notes
  }
  if (isSum(data)) notes.push('Every visit is in this one frame, so nothing moves in it.')
  if (isAlone(data)) notes.push('This is the only visit so far with this detector, so there is nothing to compare it with yet.')
  if (data.mode === 'difference') {
    const ref = data.reference_frame?.epoch
    if (ref != null) notes.push(`Visit ${ref} is the one subtracted, so the shifts are measured from it.`)
    notes.push("The positions were measured in each visit's own image, not in the difference.")
  }
  if (withinError.length) {
    notes.push(
      `Within error, ${listVisits(withinError)}: under a third of one SPHEREx pixel (${NATIVE_PIXEL_ARCSEC} arcseconds), so it may be measurement error rather than real movement.`,
    )
  }
  if (notFound.length) notes.push(`${capital(listVisits(notFound))}: no position could be measured. Visit details says why.`)
  const visits = allVisits(data)
  notes.push(...detectionNotes(visits), ...coreNotes(visits), ...blendNotes(visits))
  const none = noPredictionSentence(data)
  if (none && !isSum(data) && !isAlone(data)) notes.push(none)
  return notes
}

type OverallKind = 'sum' | 'alone' | 'none found' | 'found once' | 'moved' | 'came back' | 'still'

function overallKind(data: FramesReady): OverallKind {
  if (isSum(data)) return 'sum'
  if (isAlone(data)) return 'alone'
  const measured = measuredRows(visitRows(data))
  if (measured.length === 0) return 'none found'
  if (measured.length === 1) return 'found once'
  const first = measured[0].frame.centroid
  const last = measured[measured.length - 1].frame.centroid
  if (first && last && shiftBetween(first, last).total >= SMALL_SHIFT_ARCSEC) return 'moved'
  return measured.some((r) => !r.withinError && r.shift) ? 'came back' : 'still'
}

const BRIGHTNESS_ELSEWHERE = 'Some objects change in brightness instead. Expert’s Brightness over time shows that.'

/**
 * Beginner's sentence about the whole run, from the first visit with a position to the last,
 * and the lines that go with it. Never names a shift from or to a visit where it was not
 * found. The sentence is the same whichever visit is on screen.
 */
export function overallResult(data: FramesReady): { sentence: string; more: string[] } {
  const kind = overallKind(data)
  if (kind === 'sum') return { sentence: 'Every visit is added into this one picture, so nothing moves in it.', more: [] }
  if (kind === 'alone') return { sentence: 'This is the only visit so far, so there is nothing to compare yet.', more: [] }
  const rows = visitRows(data)
  const measured = measuredRows(rows)
  if (kind === 'none found') return { sentence: 'No position could be measured in any visit.', more: [] }
  if (kind === 'found once') {
    return { sentence: `It was found only in visit ${measured[0].frame.epoch}, so there is nothing to compare.`, more: [] }
  }
  const a = measured[0].frame
  const b = measured[measured.length - 1].frame
  // The first and last visits with a position: by month when they are the first and last of all, else by number too.
  const ends = a === rows[0].frame && b === rows[rows.length - 1].frame
  const when = ends
    ? `between ${monthYearLong(a.date_mean)} and ${monthYearLong(b.date_mean)}`
    : `between visit ${a.epoch} (${monthYearLong(a.date_mean)}) and visit ${b.epoch} (${monthYearLong(b.date_mean)})`
  const overall = shiftBetween(a.centroid!, b.centroid!) // both measured: measuredRows
  if (kind === 'moved') return { sentence: `It moved ${overall.total.toFixed(1)} arcseconds ${compassWord(overall)} ${when}.`, more: [] }
  if (kind === 'came back') {
    const most = Math.max(...measured.map((r) => r.shift?.total ?? 0))
    return {
      sentence: `Its place changed by up to ${most.toFixed(1)} arcseconds ${when}, then came back.`,
      more: ['The first and last places differ by under a third of a pixel.', BRIGHTNESS_ELSEWHERE],
    }
  }
  return {
    sentence: `No movement seen ${when}.`,
    more: ['Any shift was under a third of a pixel, so it may be a measuring error.', BRIGHTNESS_ELSEWHERE],
  }
}

/**
 * Beginner's line on how clearly it is seen across the visits: "Seen clearly in all 3
 * visits.", "Seen clearly in visits 2 and 3, only just in visit 1." Null when the response
 * does not say.
 */
export function seenLine(data: FramesReady): string | null {
  const visits = allVisits(data)
  if (!visits.some((f) => f.detection)) return null
  const n = visits.length
  const which = (es: number[]) => (isSum(data) ? 'the sum of all visits' : n === 1 ? 'its one visit' : es.length === n ? `all ${n} visits` : listVisits(es))
  const where = (d: string) => visits.filter((f) => f.detection === d).map((f) => f.epoch ?? 0)
  const seen: string[] = []
  const clear = where('clear')
  const marginal = where('marginal')
  const saturated = where('saturated')
  if (clear.length) seen.push(`clearly in ${which(clear)}`)
  if (marginal.length) seen.push(`only just in ${which(marginal)}`)
  if (saturated.length) seen.push(`so brightly in ${which(saturated)} that the sensor overflowed`)
  const lines = seen.length ? [`Seen ${seen.join(', ')}.`] : []
  const none = where('none')
  const unknown = where('unknown')
  if (none.length) lines.push(`Not seen in ${which(none)}.`)
  if (unknown.length) lines.push(`How clearly is not known for ${which(unknown)}.`)
  return lines.join(' ')
}

/**
 * What a screen reader says when the visitor steps to a visit or chooses one: its row in
 * one sentence. "Visit 2 of 3, March 2026: moved 5.9 arcseconds north, 0.9 west."
 */
export function rowAnnouncement(data: FramesReady, index: number): string {
  const row = tableRows(data).find((r) => r.index === index)
  if (!row) return ''
  const f = row.frame
  if (isSum(data)) return `All visits added together, ${monthYearLong(f.date_start)} to ${monthYearLong(f.date_end)}.`
  // Visit numbers are counted over all six detectors, so one can be missing here: then the
  // visit's place in the run is said as well.
  const all = allVisits(data)
  const k = all.indexOf(f) + 1
  const head = f.epoch === k ? `${rowName(f, data)} of ${all.length}, ${monthYearLong(f.date_mean)}` : `${rowName(f, data)}, number ${k} of ${all.length}, ${monthYearLong(f.date_mean)}`
  if (isAlone(data)) return `${head}: the only visit so far.`
  if (row.start) return `${head}: where it started.`
  if (!row.shift) return `${head}: no position could be measured.`
  if (row.shift.total < 0.05) return `${head}: in the same place as at the start.`
  return `${head}: moved ${shiftWords(row.shift, 'arcseconds')}${row.withinError ? ', within measuring error' : ''}.`
}

/**
 * The Flags legend's words after its two keys, for every visit at once: whether any picture
 * pixel is saturated, and in how many exposures of each visit the core is saturated for
 * measuring brightness.
 */
export function flagsNote(data: FramesReady): string {
  const frames = data.frames
  const none = frames.every((f) => f.saturated_pixels === 0) ? ' (none here)' : ''
  const lost = frames.filter((f) => (f.photometry_saturated_exposures ?? 0) > 0)
  const each = lost.map((f) => `${f.photometry_saturated_exposures} of ${f.n_exposures} in ${f.epoch === null ? 'the sum' : `visit ${f.epoch}`}`)
  const photometry = lost.length
    ? `. For measuring brightness the star's core is saturated in some exposures, even where the image looks fine: ${each.join(', ')}.`
    : ''
  return `: no value in any exposure of a frame${none}${photometry}`
}

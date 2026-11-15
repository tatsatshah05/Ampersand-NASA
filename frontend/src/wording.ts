// Plain-language sentences built from an /api/frames response. Every number in them
// comes from the response.
import { NATIVE_PIXEL_ARCSEC, type Frame, type FramesReady } from './api'
import { SMALL_SHIFT_ARCSEC, realShiftBar, shiftFromStart, startCentroid } from './motion'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** "visit 2", "visits 1 and 3", "visits 1, 2 and 3". */
export function listVisits(epochs: number[]): string {
  if (epochs.length === 0) return 'no visits'
  if (epochs.length === 1) return `visit ${epochs[0]}`
  return `visits ${epochs.slice(0, -1).join(', ')} and ${epochs[epochs.length - 1]}`
}

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
  const start = startCentroid(data)
  const bar = start ? realShiftBar(start, frame.centroid) : SMALL_SHIFT_ARCSEC
  if (shift.total >= SMALL_SHIFT_ARCSEC && !data.target && shift.total < bar) {
    return `${moved} No known object is listed at the centre, so this may be a different spot, not movement.`
  }
  if (shift.total >= bar) return moved
  if (shift.total >= SMALL_SHIFT_ARCSEC) return `${moved} That is within the position error, so it may not be real movement.`
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

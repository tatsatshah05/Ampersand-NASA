// Plain-language words about what was and was not detected, built from the fields the
// backend gives for honesty: `detection`, the saturated-core position error, `blend`,
// `measured` and `stars_in_circle`. Every number comes from the response. Every field is
// optional, so an older cached response gives null (nothing to say) rather than an error.
//
// The page shows one table of every visit, so these words describe all the visits at once:
// a short word for each visit's row, and notes said once for the visits they apply to.
// Nothing here depends on which visit is on screen.
import type { BlendStar, Frame } from './api'
import type { Measured, StarsInCircle } from './spectrum'

/** "visit 2", "visits 1 and 3", "visits 1, 2 and 3". */
export function listVisits(epochs: number[]): string {
  if (epochs.length === 0) return 'no visits'
  if (epochs.length === 1) return `visit ${epochs[0]}`
  return `visits ${epochs.slice(0, -1).join(', ')} and ${epochs[epochs.length - 1]}`
}

const capital = (s: string) => `${s.charAt(0).toUpperCase()}${s.slice(1)}`

/** A number of times the background scatter: one decimal under 10, whole above. */
export const times = (n: number) => (n < 10 ? n.toFixed(1) : n >= 1000 ? 'over 1000' : String(Math.round(n)))

/** The fields of a visit these words read. */
type Seen = Pick<Frame, 'epoch' | 'detection' | 'detection_sigma' | 'centroid' | 'blend'>

/**
 * How strongly the target is detected in one visit, in a few words for its row:
 * "clear, 15×", "marginal, 3.4×", "not seen, 2.1×", "saturated", "unknown". The number is
 * times the background scatter. Null when the response does not say.
 */
export function detectionShort(frame: Seen): string | null {
  const sigma = frame.detection_sigma
  switch (frame.detection) {
    case 'clear':
      return sigma != null ? `clear, ${times(sigma)}×` : 'clear'
    case 'marginal':
      return sigma != null ? `marginal, ${times(sigma)}×` : 'marginal'
    case 'none':
      // Below 1 (or negative) the measured value is just noise: say that, not "-0.8×".
      return sigma != null && sigma >= 1 ? `not seen, ${times(sigma)}×` : 'not seen'
    case 'saturated':
      return 'saturated'
    case 'unknown':
      return 'unknown'
    default:
      return null
  }
}

/**
 * The full sentence on how strongly the target is detected in one visit; null when the
 * response does not say. Shown once per visit in Visit details, never as "the visit on screen".
 */
export function detectionSentence(frame: Pick<Frame, 'detection' | 'detection_sigma'>): string | null {
  const sigma = frame.detection_sigma
  switch (frame.detection) {
    case 'clear':
      return sigma != null ? `Detected clearly, ${times(sigma)} times the background scatter` : 'Detected clearly'
    case 'marginal':
      return sigma != null
        ? `Marginal detection, ${times(sigma)} times the background scatter: treat with care`
        : 'Marginal detection: treat with care'
    case 'none':
      if (sigma == null) return 'Not detected in this frame'
      // Below 1 (or negative) the measured value is just noise: say that, not "-0.8 times".
      return sigma < 1
        ? 'Not detected in this frame (nothing above the background scatter; at least 3 times it is needed)'
        : `Not detected in this frame (${times(sigma)} times the background scatter; at least 3 is needed)`
    case 'saturated':
      return 'Too bright to measure here (saturated)'
    case 'unknown':
      return 'How strongly it is detected could not be worked out for this frame'
    default:
      return null
  }
}

/** True when the target is detected, but only marginally: its marker is drawn dashed. */
export const isMarginal = (frame: Pick<Frame, 'detection'>): boolean => frame.detection === 'marginal'

const arcsec = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1))

/**
 * How good one visit's marked position is, said only where the fit's own error would
 * mislead: a saturated core. Null otherwise. (Visit details; the table says it once, coreNotes.)
 */
export function positionSentence(frame: Pick<Frame, 'centroid'>): string | null {
  const c = frame.centroid
  if (!c?.saturated_core || c.err_arcsec == null) return null
  return `The core is overexposed, so the position is good to about ${arcsec(c.err_arcsec)}″, not the much smaller error of the fit.`
}

const shareWordsCapital = (share: number) => capital(shareWords(share))

function neighbour(s: BlendStar): string {
  return `Gaia G ${s.gmag.toFixed(1)}, ${s.distance_arcsec.toFixed(1)}″ away`
}

/** One sentence per neighbouring star that shares the light in one visit; empty when none. (Visit details.) */
export function blendSentences(frame: Pick<Frame, 'blend'>): string[] {
  return (frame.blend ?? []).map((s) => {
    if (s.light_share == null) {
      return `A star ${s.distance_arcsec.toFixed(1)}″ away (Gaia G ${s.gmag.toFixed(1)}) is too close to separate from the target, so the position and brightness here include its light.`
    }
    if (s.light_share < 0.05) {
      return `A neighbouring star (${neighbour(s)}) supplies under 5 per cent of the light here.`
    }
    if (s.light_share >= 0.95) return `Nearly all of the light here comes from a neighbouring star (${neighbour(s)}).`
    return `${shareWordsCapital(s.light_share)} of the light here comes from a neighbouring star (${neighbour(s)}).`
  })
}

/** The visit numbers of the frames that pass `test`, in order (a sum, with no number, is left out). */
const epochsWhere = <F extends Pick<Frame, 'epoch'>>(frames: F[], test: (f: F) => boolean): number[] =>
  frames.filter((f) => f.epoch !== null && test(f)).map((f) => f.epoch as number)

/**
 * How good the marked positions are, said only where the fit's own error would mislead: a
 * saturated core. One note for the visits that share an error ("about 1″"). Empty otherwise.
 */
export function coreNotes(frames: Seen[]): string[] {
  const byError = new Map<number, number[]>()
  for (const f of frames) {
    const c = f.centroid
    if (!c?.saturated_core || c.err_arcsec == null || f.epoch === null) continue
    byError.set(c.err_arcsec, [...(byError.get(c.err_arcsec) ?? []), f.epoch])
  }
  return [...byError].map(([err, epochs]) => {
    const each = epochs.length === 1 ? 'the position is' : 'each position is'
    return `The core is overexposed in ${listVisits(epochs)}, so ${each} good to about ${arcsec(err)}″, not the much smaller error of the fit.`
  })
}

/** "About a quarter", "About 40 per cent" */
function shareWords(share: number): string {
  const friendly: [number, string][] = [
    [1 / 4, 'about a quarter'],
    [1 / 3, 'about a third'],
    [1 / 2, 'about half'],
    [2 / 3, 'about two thirds'],
    [3 / 4, 'about three quarters'],
  ]
  for (const [value, words] of friendly) if (Math.abs(share - value) <= 0.04) return words
  if (share < 0.05) return 'under 5 per cent'
  if (share >= 0.95) return 'nearly all'
  return `about ${Math.round(share * 100)} per cent`
}

/** "1.7″", or "1.6″ to 1.7″" when the distance differs from visit to visit. */
function distances(stars: BlendStar[]): string {
  const ds = stars.map((s) => s.distance_arcsec.toFixed(1))
  const lo = Math.min(...stars.map((s) => s.distance_arcsec)).toFixed(1)
  const hi = Math.max(...stars.map((s) => s.distance_arcsec)).toFixed(1)
  return new Set(ds).size === 1 ? `${ds[0]}″` : `${lo}″ to ${hi}″`
}

/**
 * One note per neighbouring star that shares the target's light, naming the visits it
 * does it in and how much of the light is its own. Empty when there is none.
 */
export function blendNotes(frames: Seen[]): string[] {
  const byStar = new Map<string, { epochs: number[]; seen: BlendStar[] }>()
  for (const f of frames) {
    if (f.epoch === null) continue
    for (const s of f.blend ?? []) {
      const was = byStar.get(s.source_id) ?? { epochs: [], seen: [] }
      byStar.set(s.source_id, { epochs: [...was.epochs, f.epoch], seen: [...was.seen, s] })
    }
  }
  return [...byStar.values()].map(({ epochs, seen }) => {
    const g = seen[0].gmag.toFixed(1)
    const where = capital(listVisits(epochs))
    if (seen.every((s) => s.light_share == null)) {
      return `${where}: a star ${distances(seen)} away (Gaia G ${g}) is too close to separate from the target, so the position and brightness include its light.`
    }
    // Each visit's share in words; the visits with the same words are said together.
    const groups = new Map<string, number[]>()
    seen.forEach((s, i) => {
      const words = s.light_share == null ? 'an unknown part' : shareWords(s.light_share)
      groups.set(words, [...(groups.get(words) ?? []), epochs[i]])
    })
    const share =
      groups.size === 1
        ? `${[...groups.keys()][0]} of the light`
        : `${[...groups].map(([words, es]) => `${words} in ${listVisits(es)}`).join(', ')} of the light`
    return `${where}: a neighbouring star (Gaia G ${g}, ${distances(seen)} away) supplies ${share}.`
  })
}

/**
 * The visits where the target is seen only marginally, or not at all, or where how strongly
 * could not be worked out: one note each, with what the numbers mean. Empty when there are none.
 */
export function detectionNotes(frames: Seen[]): string[] {
  const notes: string[] = []
  const marginal = epochsWhere(frames, isMarginal)
  if (marginal.length) {
    notes.push(
      `Only a marginal detection in ${listVisits(marginal)} (3 to 5 times the background scatter; 5 or more is clear): treat ${marginal.length === 1 ? 'it' : 'them'} with care.`,
    )
  }
  const none = epochsWhere(frames, (f) => f.detection === 'none')
  if (none.length) notes.push(`Not detected in ${listVisits(none)}: at least 3 times the background scatter is needed.`)
  const unknown = epochsWhere(frames, (f) => f.detection === 'unknown')
  if (unknown.length) {
    notes.push(`How strongly it is detected could not be worked out in ${listVisits(unknown)}: too few empty places to compare with.`)
  }
  return notes
}

/**
 * Why no position was measured in this frame, in the backend's own words, and what the fit
 * found instead (`nearest_source`). Null when there is a position.
 */
export function notFoundSentence(frame: Frame): string | null {
  if (frame.centroid) return null
  const parts = ['No position could be measured in this frame.']
  const why = frame.centroid_reason?.trim()
  if (why) parts.push(/[.!?]$/.test(why) ? why : `${why}.`)
  const other = frame.nearest_source
  if (other) {
    const far = other.offset_arcsec?.total
    // The backend's reason already gives the distance when that is why it was not taken.
    if (far != null && !why?.includes('from the predicted position')) {
      parts.push(`The nearest source found is ${far.toFixed(1)}″ from the predicted position.`)
    }
    const how = other.detection ? detectionSentence({ ...frame, detection: other.detection, detection_sigma: other.detection_sigma }) : null
    if (how) parts.push(`That source: ${how.charAt(0).toLowerCase()}${how.slice(1)}.`)
  }
  return parts.join(' ')
}

/** What the measurement follows, in the backend's own words; null when it does not say. */
export function measuredSentence(measured: Measured | undefined): string | null {
  return measured?.description?.trim() || null
}

/**
 * Which Gaia stars are inside the measuring circle and that their light is included.
 * Null when there are none; a different line when Gaia did not answer.
 */
export function circleStarsSentence(circle: StarsInCircle | undefined): string | null {
  if (!circle) return null
  if (circle.known === false) {
    return 'Gaia did not answer, so it is not known whether other stars are inside the measuring circle. Their light would be included.'
  }
  const stars = circle.stars ?? []
  if (stars.length === 0) return null
  const radius = circle.radius_arcsec != null ? ` (radius ${circle.radius_arcsec.toFixed(1)}″)` : ''
  const each = stars.map((s) => {
    const where =
      s.nearest_arcsec === s.farthest_arcsec
        ? `${s.nearest_arcsec.toFixed(1)}″ from the object`
        : `${s.nearest_arcsec.toFixed(1)}″ to ${s.farthest_arcsec.toFixed(1)}″ from the object, depending on the visit`
    return `Gaia G ${s.gmag.toFixed(1)}, ${where} (${listVisits(s.epochs)})`
  })
  const light = stars.length === 1 ? "Its light is included in these numbers and nothing is subtracted, so they add the star's light to the object's." : "Their light is included in these numbers and nothing is subtracted, so they add those stars' light to the object's."
  return `Inside the measuring circle${radius}: ${each.join('; ')}. ${light} Stars Gaia does not list, or lists fainter than G 17, are not counted.`
}

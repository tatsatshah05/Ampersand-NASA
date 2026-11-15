// Every word of Beginner's guide and of its small "i" popovers, in one place. Each popover
// is a pure function of what is on screen (the /api/frames answer, the visit shown), so
// every number in it is computed from that data or is a fact verified in CLAUDE.md.
//
// Rules for the words: reading age about 11, sentences of 20 words or fewer, everyday words,
// a science word only with its meaning beside it. Never "sigma", "flux", "epoch", "detector"
// or "centroid" here, and never "discovery" or "new planet" (guide.test.ts checks all of it).
import { NATIVE_PIXEL_ARCSEC, type Frame, type FramesReady } from './api'
import { times } from './detection'
import { SMALL_SHIFT_ARCSEC, shiftFromStart, startCentroid } from './motion'
import { monthYear } from './wording'

// ---- the step guide ------------------------------------------------------------------------

/** What the visitor has actually done so far. */
export interface Progress {
  /** Chose a star (a target button or the search). */
  chose: boolean
  /** Pressed Play, Blink, an arrow or a visit picture. */
  flipped: boolean
  /** Reached the last visit, or opened an explanation. */
  read: boolean
}

export const NO_PROGRESS: Progress = { chose: false, flipped: false, read: false }

export type StepState = 'done' | 'now' | 'later'

export interface Step {
  n: 1 | 2 | 3
  label: string
  state: StepState
}

const STEP_LABELS = ['Choose a star above', 'Flip through the visits', 'Read what changed'] as const

/** The three steps. Done ones are those the visitor did; "now" is the first one not done. */
export function guideSteps(progress: Progress): Step[] {
  const done = [progress.chose, progress.flipped, progress.read]
  const now = done.indexOf(false)
  return STEP_LABELS.map((label, i) => ({
    n: (i + 1) as 1 | 2 | 3,
    label,
    state: done[i] ? 'done' : i === now ? 'now' : 'later',
  }))
}

/** What a step's number says to a screen reader (the number is all that shows). */
export const stepName = (step: Step): string =>
  `Step ${step.n}, ${step.state === 'done' ? 'done' : step.state === 'now' ? 'you are here' : 'still to do'}`

export const GO_FURTHER = 'Then go further: practise finding a planted object, help check what the search found, or try Expert.'

// ---- the small "i" buttons -----------------------------------------------------------------

export const INFO_NAMES = {
  picture: 'About this picture',
  visits: 'About the visit pictures',
  player: 'About Play and Blink',
  movement: 'About the movement line',
  detection: 'About the detection line',
  bright: 'About the bright-star warning',
  level: 'About Beginner and Expert',
} as const

export type InfoKey = keyof typeof INFO_NAMES

/** The id of the picture's description: the stage points to it for screen readers. */
export const PICTURE_INFO_ID = 'stage-help'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2025-08-15" as "15 Aug 2025", read from the text so no time zone can shift the day. */
export function dayMonthYear(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const month = m ? MONTHS[Number(m[2]) - 1] : undefined
  return m && month ? `${Number(m[3])} ${month} ${m[1]}` : iso
}

/** "21, 20 and 18". */
const listNumbers = (ns: number[]): string => (ns.length < 2 ? ns.join('') : `${ns.slice(0, -1).join(', ')} and ${ns[ns.length - 1]}`)

/** Every picture of the view, the subtracted visit of a difference view included. */
const allFrames = (data: FramesReady): Pick<Frame, 'date_start' | 'date_end' | 'n_exposures'>[] =>
  data.reference_frame ? [data.reference_frame, ...data.frames] : data.frames

/** The picture: what the app did to make it, then how to move around in it. */
export function pictureInfo(data: FramesReady | null, frame: Frame | null): string[] {
  const story = [
    'These are real photos from NASA’s SPHEREx space telescope.',
    'It sees infrared, a kind of light our eyes cannot see.',
    'We asked NASA’s archive which SPHEREx exposures cover this spot. An exposure is one photo.',
    'We read just this patch of each one from NASA’s public copy of the files.',
    'We cleaned them, lined them up on the sky, and averaged the exposures of each visit into one picture.',
    'A visit is one time SPHEREx came back to this spot.',
  ]
  if (data) {
    const frames = allFrames(data)
    const exposures = frames.reduce((sum, f) => sum + f.n_exposures, 0)
    const first = frames.map((f) => f.date_start).sort()[0]
    const last = frames.map((f) => f.date_end).sort().reverse()[0]
    story.push(
      `In all, ${plural(exposures, 'exposure', 'exposures')} went into ${plural(frames.length, 'visit picture', 'visit pictures')}, taken between ${dayMonthYear(first)} and ${dayMonthYear(last)}.`,
    )
    if (frame && data.mode === 'normal') story.push(`The one on screen uses ${frame.n_exposures}.`)
  }
  return [
    story.join(' '),
    'Scroll or pinch to zoom, and drag to move. North is up and east is left. A flat white patch is too bright to measure. The space bar plays and pauses, and the arrow keys step.',
  ]
}

/** The strip of small pictures under the player. */
export function visitsInfo(data: FramesReady | null): string[] {
  const first = 'Each small picture is one visit: one time SPHEREx came back to look at this spot.'
  if (!data) return [first, 'Press one to show it in the big picture.']
  const frames = data.frames
  if (frames.length < 2) return [first, 'There is only one visit so far, so there is nothing to compare it with yet.']
  const a = monthYear(frames[0].date_mean)
  const b = monthYear(frames[frames.length - 1].date_mean)
  const counts = frames.length <= 6 ? ` They hold ${listNumbers(frames.map((f) => f.n_exposures))} exposures.` : ''
  return [first, `Here there are ${frames.length} visits, from ${a} to ${b}.${counts}`, 'Press one to show it in the big picture.']
}

/** Play and Blink. */
export function playerInfo(data: FramesReady | null): string[] {
  const play = 'Play shows the visits one after another, like a short film. Most stars stay put, so a mover seems to jump.'
  if (!data || data.frames.length < 2) return [play, 'With only one visit, there is nothing to flip between yet.']
  const a = data.frames[0].epoch
  const b = data.frames[data.frames.length - 1].epoch
  const which = a !== null && b !== null ? `visit ${a} and visit ${b}` : 'the first visit and the last one'
  return [play, `Blink flips between ${which}. That shows a small shift best.`]
}

const pixels = (arcsec: number) => (arcsec / NATIVE_PIXEL_ARCSEC).toFixed(2)

/** The sentence about how far the marked object moved. */
export function movementInfo(frame: Frame | null, data: FramesReady | null): string[] {
  const how =
    'We find the middle of the bright spot in each visit. Then we measure how far it is from where it was in the first visit.'
  const unit = `An arcsecond is a tiny angle: 3600 of them make one degree. One SPHEREx pixel is ${NATIVE_PIXEL_ARCSEC} arcseconds wide.`
  if (!frame || !data) return [how, unit]
  if (!frame.centroid) return [how, 'In this visit no clear spot could be measured, so no movement is shown.']
  if (frame.centroid === startCentroid(data)) return [how, 'This visit is the starting point, so it has nothing to be measured against.']
  const shift = shiftFromStart(data, frame)
  if (!shift) return [how, unit]
  const here = `Here it moved ${shift.total.toFixed(1)} arcseconds, which is ${pixels(shift.total)} of a pixel.`
  const care =
    shift.total < SMALL_SHIFT_ARCSEC
      ? 'That is under a third of a pixel, so it may be a measuring error and not real movement.'
      : 'That is more than a third of a pixel, so it is less likely to be just a measuring error.'
  return [how, `${unit} ${here} ${care}`]
}

/** The sentence about how clearly the object is seen. */
export function detectionInfo(frame: Frame | null): string[] {
  const how =
    'Empty sky is never perfectly smooth: it flickers a little. We call that the background scatter. We compare the object’s brightness with it.'
  const scale = 'At least 5 times the scatter counts as clear. From 3 to 5 is marginal, so take care. Under 3 counts as not seen.'
  if (!frame) return [how, scale]
  const sigma = frame.detection_sigma
  switch (frame.detection) {
    case 'clear':
    case 'marginal':
      return [how, sigma != null ? `Here it is ${times(sigma)} times the scatter. ${scale}` : scale]
    case 'none':
      return [how, sigma != null && sigma >= 1 ? `Here it is only ${times(sigma)} times the scatter. ${scale}` : `Here it is not above the scatter. ${scale}`]
    case 'saturated':
      return [how, 'Here the star is so bright that the sensor overflowed at its place. It is certainly there, but no number can be given.']
    case 'unknown':
      return [how, 'Here there were too few empty places nearby to compare with, so we cannot say how clearly it is seen.']
    default:
      return [how, scale]
  }
}

/** The warning about very bright stars near the patch. */
export function brightStarInfo(bright: { gmag: number }[] | null | undefined): string[] {
  const near =
    bright && bright.length > 0
      ? `Gaia, a star catalogue, gives ${bright.length === 1 ? 'it' : 'the brightest'} a brightness of ${Math.min(...bright.map((b) => b.gmag)).toFixed(1)}. A smaller number means brighter.`
      : 'Gaia is a star catalogue, and it lists this star as very bright.'
  return [
    `A very bright star is near this patch. ${near}`,
    'Light can bounce around inside the telescope and leave rings and streaks. They land in a different place in each visit, so they can look like movement.',
  ]
}

/** The Beginner | Expert switch. */
export function levelInfo(): string[] {
  return [
    'Beginner shows the picture and what moved. Expert adds more ways to look. Your choice is remembered on this device.',
    'In Expert you get other infrared colours, a picture of what changed, and one sum of all visits. It also has brightness charts, a patch search, asteroid labels and a search for a distant world (Planet X).',
  ]
}

/** All popover texts for what is on screen, by key. */
export function infoFor(key: InfoKey, data: FramesReady | null, frame: Frame | null, bright?: { gmag: number }[] | null): string[] {
  switch (key) {
    case 'picture':
      return pictureInfo(data, frame)
    case 'visits':
      return visitsInfo(data)
    case 'player':
      return playerInfo(data)
    case 'movement':
      return movementInfo(frame, data)
    case 'detection':
      return detectionInfo(frame)
    case 'bright':
      return brightStarInfo(bright)
    case 'level':
      return levelInfo()
  }
}

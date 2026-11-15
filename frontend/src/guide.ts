// Every word of Beginner's guide and of its small "i" popovers, in one place. Each popover
// is a pure function of the /api/frames answer, so every number in it is computed from that
// data or is a fact verified in CLAUDE.md. None takes the visit on screen: an open popover
// must not change while the visits play behind it, so each describes every visit, or the
// whole run from the first visit with a position to the last.
//
// Rules for the words: reading age about 11, sentences of 20 words or fewer, everyday words,
// a science word only with its meaning beside it. Never "sigma", "flux", "epoch", "detector"
// or "centroid" here, and never "discovery" or "new planet" (guide.test.ts checks all of it).
import { NATIVE_PIXEL_ARCSEC, type Frame, type FramesReady } from './api'
import { times } from './detection'
import { findChangeInfo, findPictureInfo, findPlayerInfo } from './findsInfo'
import { measuredRows, realShiftBar, shiftBetween, visitRows } from './motion'
import { catalogueCheck, listVisits, monthYear, monthYearLong } from './wording'

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

const STEP_LABELS = ['Press a star above', 'Press Blink or a visit', 'Read what changed'] as const
/** Step 2 for someone whose system asks for less motion: the pictures start still. */
const STILL_STEP_2 = 'Press Play to flip the visits'

/** The three steps. Done ones are those the visitor did; "now" is the first one not done. */
export function guideSteps(progress: Progress, still = false): Step[] {
  const done = [progress.chose, progress.flipped, progress.read]
  const now = done.indexOf(false)
  return STEP_LABELS.map((was, i) => ({
    n: (i + 1) as 1 | 2 | 3,
    label: i === 1 && still ? STILL_STEP_2 : was,
    state: done[i] ? 'done' : i === now ? 'now' : 'later',
  }))
}

/** What a step's number says to a screen reader (the number is all that shows). */
export const stepName = (step: Step): string =>
  `Step ${step.n}, ${step.state === 'done' ? 'done' : step.state === 'now' ? 'you are here' : 'still to do'}`

export const GO_FURTHER = 'Then go further: Practise, Vote, or Expert.'

// ---- the small "i" buttons -----------------------------------------------------------------

export const INFO_NAMES = {
  picture: 'About this picture',
  visits: 'About the visit pictures',
  player: 'About Play and Blink',
  movement: 'About the movement line',
  detection: 'About the detection line',
  bright: 'About the bright-star warning',
  level: 'About Beginner and Expert',
  steps: 'About these steps',
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
const listNumbers = (ns: (number | string)[]): string => (ns.length < 2 ? ns.join('') : `${ns.slice(0, -1).join(', ')} and ${ns[ns.length - 1]}`)

/** Every picture of the view, the subtracted visit of a difference view included. */
const allFrames = (data: FramesReady): Pick<Frame, 'date_start' | 'date_end' | 'n_exposures'>[] =>
  data.reference_frame ? [data.reference_frame, ...data.frames] : data.frames

/** The three steps and what "go further" means. */
export function stepsInfo(): string[] {
  return [
    'This page shows how one patch of sky changed between SPHEREx’s visits. The first three buttons are candidates our own search found: nobody has confirmed them yet. The next five are well-known objects, used as tests.',
    'Practise adds a made-up moving object to real photos, and you try to find it. Vote lists what our computer search found, and you say if it looks real. None of those finds is confirmed.',
    'Expert adds more tools for a closer look.',
  ]
}

/** The picture: what the app did to make it, then how to read the marks and move around. */
export function pictureInfo(data: FramesReady | null, name?: string | null): string[] {
  const story = [
    'These are real photos from NASA’s SPHEREx space telescope. It sees infrared, light our eyes cannot see, so we show it in grey.',
    'We asked NASA’s archive which SPHEREx exposures cover this spot. An exposure is one photo.',
    'We read just this patch, in one infrared colour, from NASA’s public copy.',
    'We cleaned them, lined them up on the sky, and averaged each visit’s exposures into one picture.',
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
  }
  // Said for every visit at once, so the words stay the same whichever visit is on screen.
  const visits = data ? visitRows(data).filter((r) => r.index !== null).map((r) => r.frame) : []
  const missing = visits.filter((f) => !f.centroid).map((f) => f.epoch ?? 0)
  const faint = visits.some((f) => f.centroid && f.detection === 'marginal')
  const ring = `The amber ring circles ${name ? name : 'the one we measured'} in the visit on screen. Dots and a line join its places in each visit.${faint ? ' A dashed ring means it is only faintly seen in that visit.' : ''}`
  const marks =
    data && missing.length === visits.length
      ? 'No ring is drawn, because nothing could be measured where the object should be.'
      : missing.length
        ? `${ring} In ${listVisits(missing)} no ring is drawn, because nothing could be measured where the object should be.`
        : ring
  return [
    story.join(' '),
    `${marks} Scroll or pinch to zoom, and drag to move. North is up and east is left. A flat white patch is too bright to measure.`,
  ]
}

/** The strip of small pictures under the player. */
export function visitsInfo(data: FramesReady | null): string[] {
  const first = 'Each small picture is one visit: one time SPHEREx came back to look at this spot.'
  if (!data) return [first, 'Press one to show it in the big picture.']
  const frames = data.frames
  if (frames.length < 2) return [first, 'There is only one visit so far, so there is nothing to compare it with yet.']
  const all = allFrames(data)
  const a = monthYear(all.map((f) => f.date_start).sort()[0])
  const b = monthYear(all.map((f) => f.date_end).sort().reverse()[0])
  const counts = frames.length <= 6 ? ` They hold ${listNumbers(frames.map((f) => f.n_exposures))} exposures.` : ''
  return [
    first,
    `Here there are ${frames.length} visits, between ${a} and ${b}.${counts} SPHEREx comes back to a spot about every six months.`,
    'Press one to show it in the big picture.',
  ]
}

/** Play and Blink. */
export function playerInfo(data: FramesReady | null): string[] {
  const play =
    'Play shows the visits one after another, like a short film. Most stars are so far away that they seem fixed. A nearby star or an asteroid shifts a little each visit.'
  if (!data || data.frames.length < 2) return [play, 'With only one visit, there is nothing to flip between yet.']
  const a = data.frames[0].epoch
  const b = data.frames[data.frames.length - 1].epoch
  const which = a !== null && b !== null ? `visit ${a} and visit ${b}` : 'the first visit and the last one'
  return [play, `If nothing moved, the pictures look the same apart from a little grain. Blink flips between ${which}, which shows a small shift best.`]
}

/** Pixels: one decimal, and "pixels" from one up. */
const pixelsOf = (arcsec: number) => {
  const p = arcsec / NATIVE_PIXEL_ARCSEC
  return p >= 0.95 ? `about ${p.toFixed(1)} pixels` : `${p.toFixed(2)} of a pixel`
}

/** The sentence about how far the marked object moved: the whole run, first visit with a spot to the last. */
export function movementInfo(data: FramesReady | null): string[] {
  const how =
    'We find the middle of the bright spot in each visit. Then we measure how far it is from where it was first measured.'
  const unit = `An arcsecond is a tiny angle on the sky: the full Moon is about 1,900 wide. A pixel is one tiny square of the picture, ${NATIVE_PIXEL_ARCSEC} arcseconds across.`
  if (!data) return [how, unit]
  if (data.mode === 'sum') return [how, `${unit} Here every visit is added into one picture, so nothing can move in it.`]
  const rows = visitRows(data)
  // The visits with no position, said once: something bright too far away, or no clear spot at all.
  const lost = rows.filter((r) => !r.frame.centroid)
  const bright = (d: string | null | undefined) => d === 'clear' || d === 'marginal' || d === 'saturated'
  const tooFar = lost.filter((r) => bright(r.frame.detection)).map((r) => r.frame.epoch ?? 0)
  const noSpot = lost.filter((r) => !bright(r.frame.detection)).map((r) => r.frame.epoch ?? 0)
  const gaps = [
    tooFar.length ? `In ${listVisits(tooFar)} something bright is there, but too far from where this object should be.` : '',
    noSpot.length ? `In ${listVisits(noSpot)} no clear spot could be measured.` : '',
  ]
    .filter(Boolean)
    .map((g) => ` ${g}`)
    .join('')
  const measured = measuredRows(rows)
  if (measured.length < 2) return [how, `${unit}${gaps} Fewer than two visits have a clear spot here, so no movement can be measured.`]
  const a = measured[0].frame
  const b = measured[measured.length - 1].frame
  const from = a.centroid! // measuredRows: both have a position
  const to = b.centroid!
  const shift = shiftBetween(from, to)
  const when = `Its first and last places are from ${monthYearLong(a.date_mean)} and ${monthYearLong(b.date_mean)}.`
  if (!data.target) {
    return [
      how,
      `${unit} ${when} The marked spot is ${shift.total.toFixed(1)} arcseconds from where it was first marked. No known object is listed at the centre, so it may be a different spot, not something moving.${gaps}`,
    ]
  }
  const here =
    shift.total < 0.05 ? 'Here it is in the same place as at the start.' : `Here it moved ${shift.total.toFixed(1)} arcseconds, ${pixelsOf(shift.total)}.`
  const care =
    shift.total >= realShiftBar(from, to)
      ? 'That is more than the measuring error, so it is less likely to be just a mistake.'
      : 'That is within the measuring error, so it may not be real movement. Even still stars seem to wobble by about 1.5 arcseconds.'
  const check = catalogueCheck(data)
  const catalogue = check
    ? ` Its catalogue motion says it should have moved ${check.expected.toFixed(1)} arcseconds by then.${
        check.agree ? ' That fits what we measured.' : ' That is not what we measured, so take care.'
      }`
    : ''
  return [how, `${unit} ${when} ${here} ${care}${catalogue}${gaps}`]
}

/** The line about how clearly the object is seen, in every visit at once. */
export function detectionInfo(data: FramesReady | null): string[] {
  const how =
    'Empty sky is never perfectly smooth: it looks a little grainy. We call that grain the background scatter. We measure it in empty places of the same picture.'
  const scale = 'At least 5 times the scatter counts as clear. From 3 to 5 it may be real or may be chance. Under 3 counts as not seen.'
  if (!data) return [how, scale]
  const visits = visitRows(data).map((r) => r.frame)
  const epochs = (fs: typeof visits) => fs.map((f) => f.epoch ?? 0)
  const lines: string[] = []
  // The visits with a number, said together; the same number in every visit is said once.
  const counted = visits.filter((f) => f.detection_sigma != null && (f.detection === 'clear' || f.detection === 'marginal' || f.detection === 'none'))
  if (counted.length) {
    const values = counted.map((f) => ((f.detection_sigma as number) < 1 ? 'under 1' : times(f.detection_sigma as number)))
    if (data.mode === 'sum') lines.push(`In the sum of all visits the object is ${values[0]} times the scatter.`)
    else if (new Set(values).size === 1 && counted.length === visits.length) lines.push(`In every visit the object is ${values[0]} times the scatter.`)
    else if (counted.length <= 4) lines.push(`In ${listVisits(epochs(counted))} the object is ${listNumbers(values)} times the scatter.`)
    else {
      const sigmas = counted.map((f) => f.detection_sigma as number)
      const say = (s: number) => (s < 1 ? 'under 1' : times(s))
      lines.push(`Across ${counted.length} visits the object is ${say(Math.min(...sigmas))} to ${say(Math.max(...sigmas))} times the scatter.`)
    }
  }
  const saturated = visits.filter((f) => f.detection === 'saturated')
  if (saturated.length) {
    const where = data.mode === 'sum' ? 'In the sum of all visits' : saturated.length === visits.length ? 'In every visit' : `In ${listVisits(epochs(saturated))}`
    lines.push(`${where} the star is so bright that the sensor overflowed at its place. It is certainly there, but no number can be given.`)
  }
  const unknown = visits.filter((f) => f.detection === 'unknown')
  if (unknown.length) lines.push(`For ${data.mode === 'sum' ? 'the sum' : listVisits(epochs(unknown))} there were too few empty places nearby to compare with.`)
  return [how, [...lines, scale].join(' ')]
}

export interface BrightStar {
  gmag: number
  distance_arcmin?: number
  inside_picture?: boolean
}

const brightest = (bright: BrightStar[] | null | undefined): BrightStar | null =>
  bright && bright.length > 0 ? bright.reduce((a, b) => (b.gmag < a.gmag ? b : a)) : null

/** The short warning Beginner shows on the page; the popover says the rest. */
export function brightLine(bright: BrightStar[] | null | undefined): string {
  return `${brightWhere(brightest(bright))} Its rings can look like movement.`
}

function brightWhere(top: BrightStar | null): string {
  return !top
    ? 'A very bright star is near this patch.'
    : top.distance_arcmin !== undefined && top.distance_arcmin < 0.1
      ? 'The star in the middle of this picture is very bright.'
      : top.inside_picture
        ? 'A very bright star is in this picture.'
        : top.inside_picture === false
          ? 'A very bright star is just outside this picture.'
          : 'A very bright star is near this patch.'
}

/** The warning about very bright stars near the patch. */
export function brightStarInfo(bright: BrightStar[] | null | undefined): string[] {
  const top = brightest(bright)
  const where = brightWhere(top)
  const number = top
    ? `Gaia, a star catalogue, gives ${bright && bright.length > 1 ? 'the brightest' : 'it'} a brightness of ${top.gmag.toFixed(1)}. A smaller number means brighter.`
    : 'Gaia is a star catalogue, and it lists this star as very bright.'
  return [
    `${where} ${number}`,
    'Light can bounce around inside the telescope and leave rings and patches of glow. They land in a different place in each visit, so they can look like movement. They are not changes in the sky.',
  ]
}

/** The Beginner | Expert switch. */
export function levelInfo(): string[] {
  return [
    'Beginner shows the picture and what moved. Expert adds more ways to look. Your choice is remembered on this device.',
    'Expert adds other infrared colours, a picture of what changed, and one sum of all visits. It adds brightness charts, a patch search, and a list of known asteroids and comets. It also has a search for a far-off planet some people think may exist.',
  ]
}

/** All popover texts for the view on screen, by key. None depends on which visit is shown. */
export function infoFor(key: InfoKey, data: FramesReady | null, bright?: BrightStar[] | null, name?: string | null): string[] {
  switch (key) {
    // One of our sweep's candidates (findsInfo.ts) is about something that appeared, not something that moved.
    case 'picture':
      return findPictureInfo(data, pictureInfo(data, name))
    case 'visits':
      return visitsInfo(data)
    case 'player':
      return findPlayerInfo(data) ?? playerInfo(data)
    case 'movement':
      return findChangeInfo(data) ?? movementInfo(data)
    case 'detection':
      return detectionInfo(data)
    case 'bright':
      return brightStarInfo(bright)
    case 'level':
      return levelInfo()
    case 'steps':
      return stepsInfo()
  }
}

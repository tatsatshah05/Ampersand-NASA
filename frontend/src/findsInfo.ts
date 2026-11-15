// Beginner's "i" popovers for one of our sweep's candidates (finds.ts), which the page holds at one
// place: the story is something that appeared, not something that moved, so three popovers say
// that instead (guide.ts's infoFor asks here first). The same rules as guide.ts: reading age about
// 11, sentences of 20 words or fewer, no "sigma", "flux", "epoch", "detector" or "centroid", never
// "discovery". Every fact is the page's own measure or the referee's ruling (finds.ts).
import type { FramesReady } from './api'
import type { Find } from './finds'
import { beforeAfter, changeHeadline, findShown, listVisits, monthYearLong } from './wording'

/** Each candidate's neighbour, for a reader of the picture (north is up and east is left). */
export const NEIGHBOUR_PLAIN: Record<Find['key'], string> = {
  A: 'The bright star just above it is a steady neighbour, there in every visit. It is not Candidate A.',
  B: 'The faint star just up and to the left is a steady neighbour, there in every visit. It is not Candidate B.',
  C: 'The stars around it are other stars, not Candidate C.',
}

/** What the evidence hints it may be, in plain words. Nobody has confirmed any of it. */
export const MAYBE_PLAIN: Record<Find['key'], string> = {
  A: 'What it is, nobody knows yet. Its light is a smooth, very red glow, like warm dust.',
  B: 'What it is, nobody knows yet. It lies among young stars, so it may be a young star flaring up.',
  C: 'Its light hints at a nova: most of it came from glowing hydrogen gas. A nova is a blast on the surface of a small, burnt-out star.',
}

/** "visit 1, in August 2025" */
const visitWhen = (data: FramesReady, i: number) => `visit ${data.frames[i].epoch}, in ${monthYearLong(data.frames[i].date_mean)}`

/** About Play and Blink: Blink flips between the picture without it and the first one with it. */
export function findPlayerInfo(data: FramesReady | null): string[] | null {
  const find = data && findShown(data)
  const pair = data && beforeAfter(data)
  if (!data || !find || !pair) return null
  return [
    'Play shows the visits one after another, like a short film.',
    `Blink before and after flips between ${visitWhen(data, pair.before)}, and ${visitWhen(data, pair.after)}. In the first, nothing is seen at ${find.name}'s place. In the second, it is clearly there.`,
  ]
}

/** About the line over the table: what changed, how we tell, and what it may be. */
export function findChangeInfo(data: FramesReady | null): string[] | null {
  const find = data && findShown(data)
  const change = data && changeHeadline(data)
  if (!data || !find || !change) return null
  const seen = data.frames.filter((f) => f.detection === 'clear' || f.detection === 'saturated').map((f) => f.epoch ?? 0)
  return [
    `We measure ${find.name}'s place in each visit. We compare it with the grain of the empty sky around it.`,
    'Under 3 times that grain counts as not seen. At least 5 times counts as clear.',
    `In ${listVisits(change.notSeen)} it was not seen. In ${listVisits(seen)} it was clearly there. It stays in one place, so it is not something moving past.`,
    MAYBE_PLAIN[find.key],
    'Nobody has confirmed it yet. People must still make some checks. A bigger telescope must look at its light.',
  ]
}

/** About this picture: the story (guide.ts's first paragraph) and, for a candidate, its own marks. */
export function findPictureInfo(data: FramesReady | null, base: string[]): string[] {
  const find = data && findShown(data)
  if (!data || !find) return base
  const marks = `The white cross marks ${find.name}'s place in every visit. The amber ring circles it where it is clearly seen. ${NEIGHBOUR_PLAIN[find.key]}`
  return [base[0], `${marks} Scroll or pinch to zoom, and drag to move. North is up and east is left. A flat white patch is too bright to measure.`]
}

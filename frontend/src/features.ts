// Every feature of the app, once, in the order of the bar at the top of every screen
// (components/FeatureBar.tsx): what each is called at each level, and one sentence on what it
// is, for its tooltip and for screen readers. Beginner's words follow the guide's rules
// (guide.ts): plain, short, and never "discovery" or "new planet".
//
// Three kinds: Watch is the picture itself; a tool opens as a panel under the picture of the
// Viewer (address: tool=<key>); a screen is a page of its own.
import type { UiLevel } from './address'

/** The tools that open as panels under the picture, each in a div.tool-slot with id "tool-<key>". */
export type ToolKey = 'brightness' | 'spectrum' | 'search' | 'distant' | 'smallbodies' | 'context'
/** The screens of their own: practice (?train=), the watchlist (?watchlist=1), the methods (?tools=1). */
export type ScreenKey = 'practise' | 'vote' | 'tools'
export type FeatureKey = 'watch' | ToolKey | ScreenKey

export interface Feature {
  key: FeatureKey
  kind: 'home' | 'tool' | 'screen'
  /** What the bar shows, at each level. */
  label: Record<UiLevel, string>
  /** One sentence: what it is. The item's title, never its name. */
  about: Record<UiLevel, string>
}

export const FEATURES: readonly Feature[] = [
  {
    key: 'watch',
    kind: 'home',
    label: { beginner: 'Watch', expert: 'Viewer' },
    about: {
      beginner: 'The real pictures of this patch of sky, one for each visit, played like a short film.',
      expert: 'The SPHEREx frames of this field, one per visit, with the player, the overlays and the table of measured shifts.',
    },
  },
  {
    key: 'brightness',
    kind: 'tool',
    label: { beginner: 'Brightness', expert: 'Light curve' },
    about: {
      beginner: 'How bright the object looked at each visit, compared only in the same colour of infrared light.',
      expert: "Light curve: the target's brightness in every SPHEREx exposure over time, compared only within one wavelength bin.",
    },
  },
  {
    key: 'spectrum',
    kind: 'tool',
    label: { beginner: 'Colours', expert: 'Spectrum' },
    about: {
      beginner: 'How bright the object is in each colour of infrared light that SPHEREx sees.',
      expert: 'Spectrum: one brightness measurement per exposure of the target, set out by wavelength from 0.75 to 5.0 micrometres.',
    },
  },
  {
    key: 'search',
    kind: 'tool',
    label: { beginner: 'Find changes', expert: 'Blind search' },
    about: {
      beginner: 'A computer search of this patch for anything that moved or changed brightness between visits.',
      expert: 'Blind search: everything in the field that moved or changed brightness between visits, each checked against the catalogues.',
    },
  },
  {
    key: 'distant',
    kind: 'tool',
    label: { beginner: 'Far-off planet', expert: 'Planet X search' },
    about: {
      beginner: 'A search of this patch for a far-off planet that some people think may exist.',
      expert: 'Planet X search: looks for a body hundreds to tens of thousands of times as far from the Sun as the Earth, by its parallax jump between visits.',
    },
  },
  {
    key: 'smallbodies',
    kind: 'tool',
    label: { beginner: 'Asteroids', expert: 'Small bodies' },
    about: {
      beginner: 'Known asteroids and comets that crossed this patch, from lists kept by NASA.',
      expert: 'Small bodies: known asteroids and comets that JPL predicts in this field, with the SPHEREx exposure each one crossed.',
    },
  },
  {
    key: 'context',
    kind: 'tool',
    label: { beginner: 'Other telescopes', expert: 'Sky context' },
    about: {
      beginner: 'The same patch of sky as other telescopes saw it.',
      expert: 'Sky context: the same field in WISE, 2MASS and DSS images, with Gaia DR3 stars, from the Aladin sky atlas.',
    },
  },
  {
    key: 'practise',
    kind: 'screen',
    label: { beginner: 'Practise', expert: 'Training' },
    about: {
      beginner: 'Practise finding a made-up moving object added to real pictures.',
      expert: 'Training: real SPHEREx frames with one simulated moving source added, to practise spotting movers.',
    },
  },
  {
    key: 'vote',
    kind: 'screen',
    label: { beginner: 'Vote', expert: 'Watchlist' },
    about: {
      beginner: 'Look at what our computer search found and vote on whether it looks real.',
      expert: 'Watchlist: what the blind searches found, for vetting by eye and voting, with the whole list as a CSV file.',
    },
  },
  {
    key: 'tools',
    kind: 'screen',
    label: { beginner: 'Three tools', expert: 'Methods' },
    about: {
      beginner: 'Three ways scientists look for planets, explained on a page of their own.',
      expert: 'Methods: three planet-finding methods, on a screen of their own.',
    },
  },
]

/** The six tools, in the bar's order. */
export const TOOL_KEYS: readonly ToolKey[] = FEATURES.filter((f) => f.kind === 'tool').map((f) => f.key as ToolKey)

export const isToolKey = (key: string): key is ToolKey => (TOOL_KEYS as readonly string[]).includes(key)

/** The feature by its key. */
export function feature(key: FeatureKey): Feature {
  const found = FEATURES.find((f) => f.key === key)
  if (!found) throw new Error(`No feature called ${key}`)
  return found
}

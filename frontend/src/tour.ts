// The guided tour (demo mode): what each step says and rings, and the plain functions that move
// between them. components/Tour.tsx is only the shell that draws it. Every view a step opens is one
// that is built beforehand (docs/demo-script.md): the three candidates, the target buttons and the
// tools' answers for them. No step asks the server to search or download anything new.
//
// The words follow the page's rules: plain, no "sigma", "flux", "epoch", "detector", "centroid" or
// "mJy"; nothing is called a discovery; anything said about Candidate A, B or C is finds.ts's own
// sentence (CANDIDATE_LINE); the practice screen says its object is made up.
import { DEFAULT_SELECTION, addressOf, readAddress, toolFrom, withTool, withUi, TOOLS_ADDRESS, type Selection, type UiLevel } from './address'
import { findAddress } from './anomalies'
import { CANDIDATE_LINE, FINDS } from './finds'
import { feature, type FeatureKey, type ToolKey } from './features'
import { isToolsAddress } from './tools'
import { WATCHLIST_ADDRESS, isWatchlistAddress } from './watchlist'

export const STORAGE_KEY = 'spherex-tour-step'

export interface Where {
  search: string
}

export interface Step {
  id: string
  title: string
  /** What this is and what it shows, as two to four short points: one sentence to a line (pointsOf). */
  what: string
  /** What to press: a bar item (named at the level in use), a visible name, or null for a step that only shows something. */
  press: { feature: FeatureKey } | string | null
  /** CSS selector of the element to ring. */
  target: string
  /** When several elements match `target`, the one whose text is exactly this. */
  targetText?: string
  /** The address this step needs (a query string), at the level in use. */
  url: (level: UiLevel) => string
  /** True when the page is already where the step needs it. */
  at: (where: Where, level: UiLevel) => boolean
  /** A bar item the tour presses once on arrival when its tool is not open yet. */
  opens?: ToolKey
}

// ---------- the places ----------

const BARNARD: Selection = {
  ...DEFAULT_SELECTION,
  name: "Barnard's Star",
  pmra: -801.5509783684709,
  pmdec: 10362.394206546573,
  parallax: 546.975939730948,
  motionFrom: 'gaia',
}
const RW_AUR: Selection = {
  ...DEFAULT_SELECTION,
  ra: 76.956587,
  dec: 30.401291,
  name: 'RW Aur',
  pmra: 7.23,
  pmdec: -20.33,
  parallax: 15.42,
}
const WISE_0855: Selection = {
  ...DEFAULT_SELECTION,
  ra: 133.759765,
  dec: -7.242182,
  name: 'WISE 0855',
  pmra: -8123.7,
  pmdec: 673.2,
  parallax: 439,
  det: 6,
}

const isScreen = (search: string) => isWatchlistAddress(search) || isToolsAddress(search) || readAddress(search).selection.train !== null
const onViewer = (w: Where) => !isScreen(w.search)
/** The viewer, looking at the place of `s` (a tenth of a degree is far wider than any move the page makes). */
const onViewerAt = (s: Selection) => (w: Where) => {
  if (!onViewer(w)) return false
  const at = readAddress(w.search).selection
  return Math.abs(at.ra - s.ra) < 0.01 && Math.abs(at.dec - s.dec) < 0.01
}

const viewerUrl = (s: Selection, tool: ToolKey | null) => (level: UiLevel) => withUi(withTool(addressOf({ ...s, ui: level }), tool), level)

// The page's own opening view (no position in the address): Candidate B.
const landingUrl = (level: UiLevel) => withUi('?', level)
const atLanding = (w: Where) => onViewer(w) && !new URLSearchParams(w.search).has('ra') && !new URLSearchParams(w.search).has('dec')
const atLandingOrB = (w: Where) => atLanding(w) || onViewerAt(readAddress(landingUrl('beginner')).selection)(w)

const trainUrl = (level: UiLevel) => withUi('?train=1&level=easy', level)
const atTrain = (w: Where) => readAddress(w.search).selection.train !== null
const watchlistUrl = (level: UiLevel) => withUi(WATCHLIST_ADDRESS, level)
const toolsUrl = (level: UiLevel) => withUi(TOOLS_ADDRESS, level)

const bar = (key: FeatureKey) => `nav[aria-label="Features"] [data-feature="${key}"]`

/** A step about a bar item that opens a tool of the viewer: on the star's own view, tool open. */
function toolStep(key: ToolKey, s: Selection, id: string, title: string, what: string): Step {
  return {
    id,
    title,
    what,
    press: { feature: key },
    target: bar(key),
    url: viewerUrl(s, key),
    at: onViewerAt(s),
    opens: key,
  }
}

export const STEPS: readonly Step[] = [
  {
    id: 'opening',
    title: 'A source appears',
    what: `This is Candidate B, in the constellation Scorpius.\nThe picture blinks between SPHEREx's visits in August 2025 and March 2026.\n${CANDIDATE_LINE}`,
    press: null,
    target: '.plate-col',
    url: landingUrl,
    at: atLandingOrB,
  },
  {
    id: 'sentence',
    title: 'The words beside the picture',
    what: `One sentence sums up the whole run.\nThe table has one row for every visit.\nThe words stay still while the pictures play.`,
    press: null,
    target: 'aside.inspector',
    url: landingUrl,
    at: atLandingOrB,
  },
  {
    id: 'player',
    title: 'The player',
    what: `Play, pause and step through the visits here.\nBlink flips between the before picture and the after picture.\nBlinking is the easiest way to see a change.`,
    press: null,
    target: '.transport',
    url: landingUrl,
    at: atLandingOrB,
  },
  {
    id: 'visits',
    title: 'The visits',
    what: `Each button is one visit of SPHEREx to this patch of sky.\nA visit is about twenty photos added up.\nPress one to see that visit alone.`,
    press: null,
    target: '.visit-strip',
    url: landingUrl,
    at: atLandingOrB,
  },
  {
    id: 'level',
    title: 'Beginner and Expert',
    what: `Beginner uses plain words.\nExpert shows every setting, number and table.\nPress Expert to look, then Beginner to come back.`,
    press: null,
    target: '.level-switch',
    url: landingUrl,
    at: (w) => onViewer(w),
  },
  {
    id: 'search',
    title: 'Search the sky',
    what: `Type a star's name to look at its patch of sky.\nOr type a position: right ascension, then declination.\nA place nobody has opened before takes about a minute, so the tour does not type one.`,
    press: null,
    target: 'form.searchbar',
    url: landingUrl,
    at: (w) => onViewer(w),
  },
  {
    id: 'targets',
    title: 'Ready-made places',
    what: `One press opens a place we prepared.\nFirst the three sources we found, then the five test targets from NASA's challenge.\nThen three more places where something changed.`,
    press: null,
    target: '.target-list',
    url: landingUrl,
    at: (w) => onViewer(w),
  },
  {
    id: 'barnard-button',
    title: 'A star that moves',
    what: `Barnard's Star is the fastest-moving star in the sky.\nPress its button to open it.`,
    press: "Barnard's Star",
    target: '.target-group button.target',
    targetText: "Barnard's Star",
    url: landingUrl,
    at: (w) => onViewer(w),
  },
  {
    id: 'barnard-moves',
    title: 'Watch it step north',
    what: `Press Play to run the three visits.\nThe star steps north.\nThe stars around it stay still.`,
    press: 'Play',
    target: '.transport .play-button',
    url: viewerUrl(BARNARD, null),
    at: onViewerAt(BARNARD),
  },
  {
    id: 'barnard-gaia',
    title: 'Measured against a catalogue',
    what: `The page measured the star moving 10.4 arcseconds north in a year.\nGaia's star map predicted 10.3.\nThe two agree.`,
    press: null,
    target: 'aside.inspector',
    url: viewerUrl(BARNARD, null),
    at: onViewerAt(BARNARD),
  },
  {
    id: 'watch',
    title: 'Watch',
    what: `The real pictures of a patch of sky, one for each visit.\nThey play like a short film.\nThis is where every star starts.`,
    press: { feature: 'watch' },
    target: bar('watch'),
    url: viewerUrl(BARNARD, null),
    at: onViewerAt(BARNARD),
  },
  toolStep(
    'brightness',
    RW_AUR,
    'brightness',
    'Brightness',
    `How bright RW Aurigae, a young star, looked at each visit.\nEach dot is one photo.\nEach colour of infrared light is compared only with itself.`,
  ),
  toolStep(
    'spectrum',
    RW_AUR,
    'spectrum',
    'Colours',
    `How bright RW Aurigae is in each colour of infrared light.\nSPHEREx sees colours from 0.75 to 5 micrometres.`,
  ),
  toolStep(
    'search',
    WISE_0855,
    'find-changes',
    'Find changes',
    `A computer search of this patch.\nIt looks for anything that moved or changed brightness between visits.\nIn WISE 0855’s patch it finds the one thing that moved, and says it is already known.`,
  ),
  toolStep(
    'distant',
    WISE_0855,
    'far-off-planet',
    'Far-off planet',
    `A search for a far-off planet.\nSuch a world would jump between visits, because SPHEREx looks from opposite sides of the Earth’s path.\nOn the real sky it finds nothing here, and says how bright an object would have had to be.`,
  ),
  toolStep(
    'smallbodies',
    BARNARD,
    'asteroids',
    'Asteroids',
    `Known asteroids and comets that crossed this patch.\nThe lists are kept by NASA.\nIf none crossed, it says so.`,
  ),
  toolStep(
    'context',
    BARNARD,
    'what-is-it',
    'What is it?',
    `What the star catalogues know about an object, in plain words.\nThe drawing is made from the catalogues' numbers.\nThe page says the drawing is not a photograph.`,
  ),
  {
    id: 'practise',
    title: 'Practise',
    what: `A practice round: one made-up moving object is added to real pictures.\nYou try to find it.\nIt is a SIMULATION, and the page says so on every picture.`,
    press: { feature: 'practise' },
    target: bar('practise'),
    url: trainUrl,
    at: atTrain,
  },
  {
    id: 'watchlist',
    title: 'Observe anomalies',
    what: `Everything our searches saw change in the pictures, sorted by the part of the sky.\nThree candidates come first.\n${CANDIDATE_LINE}`,
    press: { feature: 'vote' },
    target: bar('vote'),
    url: watchlistUrl,
    at: (w) => isWatchlistAddress(w.search),
  },
  {
    id: 'pick-patch',
    title: 'Pick a patch of sky',
    what: `Choose a patch that is already searched from this menu.\nThe field above it searches a patch nobody has searched yet.\nThat takes minutes, so the tour leaves it alone.`,
    press: 'The menu under Pick a patch of sky',
    target: '#region-choice',
    url: watchlistUrl,
    at: (w) => isWatchlistAddress(w.search),
  },
  {
    id: 'watch-it-appear',
    title: 'Watch it appear',
    what: `Each candidate has a card with a before picture and an after picture.\nThe link on the card opens that candidate's own view.\n${CANDIDATE_LINE}`,
    press: 'Watch it appear',
    target: '.anomaly-watch',
    url: watchlistUrl,
    at: (w) => isWatchlistAddress(w.search),
  },
  {
    // Where "Watch it appear" leads. Pressing that link on any of the three cards moves the tour here
    // (linkLeadsOn); Next opens the first card's view.
    id: 'candidate-view',
    title: 'The candidate’s own view',
    what: `This is the candidate’s own view.\nIt blinks between the visit before it was seen and the first visit where it is clearly seen.\n${CANDIDATE_LINE}`,
    press: null,
    target: '.plate-col',
    url: (level) => withUi(findAddress(FINDS[0], level), level),
    at: (w) => onViewer(w) && FINDS.some((f) => { const at = readAddress(w.search).selection; return Math.abs(at.ra - f.ra) < 0.01 && Math.abs(at.dec - f.dec) < 0.01 }),
  },
  {
    id: 'three-tools',
    title: 'Three tools',
    what: `Three ways scientists look for planets.\nEach is tested on a world astronomers already know, so the answer can be checked.\nNo planet is claimed.`,
    press: { feature: 'tools' },
    target: bar('tools'),
    url: toolsUrl,
    at: (w) => isToolsAddress(w.search),
  },
  {
    id: 'credits',
    title: 'Where the pictures come from',
    what: `The pictures are NASA/JPL-Caltech SPHEREx, from NASA/IPAC IRSA.\nStar positions are from ESA Gaia, and names from SIMBAD.\nEverything shown is real data, except what is marked as made up.`,
    press: null,
    target: 'footer.credits',
    url: landingUrl,
    at: (w) => onViewer(w),
  },
]

/** The visible name of what to press at this level, or null when the step only shows something. */
export function pressName(step: Step, level: UiLevel): string | null {
  if (step.press === null) return null
  return typeof step.press === 'string' ? step.press : feature(step.press.feature).label[level]
}

/** True when the tool this step opens is not the one the address names. */
export const needsOpening = (step: Step, search: string): boolean => step.opens !== undefined && toolFrom(search) !== step.opens

// ---------- moving ----------

/** The step after `i`, stopping at the last. */
export const nextStep = (i: number, length: number): number => Math.min(i + 1, length - 1)
/** The step before `i`, stopping at the first. */
export const prevStep = (i: number): number => Math.max(i - 1, 0)

// ---------- the address ----------

/** `?demo=<n>` as an index (n counts from 1), or null when there is none or it is not a step. */
export function parseDemo(search: string, length = STEPS.length): number | null {
  const raw = new URLSearchParams(search).get('demo')
  if (raw === null || !/^\d+$/.test(raw)) return null
  const n = Number(raw)
  if (n < 1) return null
  return Math.min(n, length) - 1
}

/** The query string without `demo` ("" when nothing else is left). */
export function withoutDemo(search: string): string {
  const p = new URLSearchParams(search)
  p.delete('demo')
  const rest = p.toString()
  return rest ? `?${rest}` : ''
}

/** The address of a navigation the tour makes itself: the step's query, carrying the step (`demo=<i + 1>`). */
export function hrefOf(path: string, query: string, index: number): string {
  const p = new URLSearchParams(query)
  p.set('demo', String(index + 1))
  return `${path}?${p}`
}

// ---------- storage ----------

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}
type StoreSource = StorageLike | (() => StorageLike | null) | null

/** The tab's own storage, or null when the browser will not give it. */
export function sessionStore(): StorageLike | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

// When storage throws, the step is kept here (and in `demo=<n>` on the tour's own navigations).
let inMemory: number | null = null

function open(source: StoreSource): StorageLike | null {
  try {
    return typeof source === 'function' ? source() : source
  } catch {
    return null
  }
}

/** The stored step, or null when there is none. */
export function readStep(source: StoreSource = sessionStore): number | null {
  const store = open(source)
  if (store) {
    try {
      const raw = store.getItem(STORAGE_KEY)
      if (raw === null) return null
      return /^\d+$/.test(raw) ? Number(raw) : null
    } catch {
      // fall through to memory
    }
  }
  return inMemory
}

export function saveStep(i: number, source: StoreSource = sessionStore): void {
  inMemory = i
  try {
    open(source)?.setItem(STORAGE_KEY, String(i))
  } catch {
    // The step is in memory, and in the address on the tour's own navigations.
  }
}

export function clearStep(source: StoreSource = sessionStore): void {
  inMemory = null
  try {
    open(source)?.removeItem(STORAGE_KEY)
  } catch {
    // Nothing more to do.
  }
}

// ---------- where the card goes ----------

export type CardPlace = 'top' | 'bottom' | 'left' | 'right'

/**
 * The card must not hide what it is about. Under a target in the top half of the window, over one in the
 * bottom half. A target too tall for either (the picture, the column of words) gets the card beside it, in a
 * window wide enough to have a side: right of a target on the left, left of one on the right.
 */
export function cardPlace(
  box: { top: number; left: number; width: number; height: number } | null,
  win: { width: number; height: number },
): CardPlace {
  if (box === null) return 'bottom'
  if (win.width >= 1000 && box.height > win.height * 0.55) return box.left + box.width / 2 < win.width / 2 ? 'right' : 'left'
  return box.top + box.height / 2 < win.height / 2 ? 'bottom' : 'top'
}

// ---------- a ringed link ----------

/**
 * A press on a ringed link loads the link's page. When that page is where the next step is (the candidate's
 * view after "Watch it appear"), the tour goes on to that step, so that the page the presenter asked for is
 * the page that stays. Any other link leaves the step as it is, and the step brings its own page back.
 */
export function linkLeadsOn(i: number, href: string, level: UiLevel): boolean {
  const next = STEPS[i + 1]
  if (!next) return false
  try {
    return next.at({ search: new URL(href).search }, level)
  } catch {
    return false
  }
}

// ---------- the way in ----------

/** The button in the top bar of every screen (TourStart.tsx), by the name the presenter asked for. */
export const DEMO_BUTTON = 'Demo mode'
export const DEMO_BUTTON_ABOUT = 'A guided walk through every feature: it shows what to press and what each thing does.'
/** What that button sends to the window; Tour.tsx starts the tour when it hears it. */
export const TOUR_START_EVENT = 'spherex-tour-start'

// ---------- said in points ----------

/** A step's points, in the order to say them: the lines its text was written in, and nothing cleverer. */
export const pointsOf = (step: Pick<Step, 'what'>): string[] => step.what.split('\n')

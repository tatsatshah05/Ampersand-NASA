// Issue #6: one box for "where in the sky?", and the row of target buttons.
//
// Text that reads as coordinates is turned into a position here (coords.ts). Anything
// else is looked up as a name by the backend (resolve.ts), so a named object's position
// and motion are always the catalogue's, moved to 2026: the only sky positions in this
// file are the fixed ones of OWN_LOOKS. Either way the result goes to `onSelect`, and a
// line under the box says what was found. The box sits in the page's top bar and the
// buttons in the row under it; useSkySearch holds what both share.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { FINDS, findAt, findTarget, type Find } from '../finds'
import { releaseFocusAfterPointer } from '../focus'
import {
  COORD_EXAMPLES,
  formatDecDeg,
  formatDecDms,
  formatRaDeg,
  formatRaHms,
  looksLikeCoords,
  parseCoords,
} from '../coords'
import {
  hasUnusableCharacters,
  nameForLookup,
  plainName,
  resolveName,
  ResolveError,
  type ResolvedName,
} from '../resolve'
import './SearchBar.css'

/** What a search hands to the app: where to look and, when known, how the object there moves. */
export interface SearchTarget {
  /** Degrees, ICRS. For a name: where the object is in 2026. For coordinates: exactly as typed. */
  ra: number
  dec: number
  /** The catalogue's name for the object ("Barnard's star"). Absent after a coordinate search. */
  name?: string
  /**
   * Proper motion (milliarcseconds per year) and parallax (milliarcseconds) exactly as
   * /api/resolve returned them, ready to pass to /api/frames; null where the catalogue
   * has none. All three are absent after a coordinate search: the motion is not known.
   */
  pmra?: number | null
  pmdec?: number | null
  parallax?: number | null
  /** A detector (1 to 6) to switch to, for an object that only shows up in one. */
  det?: number
}

interface Preset {
  name: string
  /** Why it is worth a look, shown as a tooltip. */
  about: string
  det?: number
  /** Other spellings of the same name that get the same detector suggestion when typed. */
  also?: string[]
}

// The five targets the challenge says to test on. Names only: the position and motion
// are looked up when the button is pressed.
const PRESETS: readonly Preset[] = [
  { name: "Barnard's Star", about: 'The fastest-moving star in the sky' },
  { name: 'Epsilon Indi B', about: 'A pair of brown dwarfs beside a bright star' },
  {
    name: 'WISE 0855',
    about: 'A very cold brown dwarf that only the longest infrared colour can see',
    det: 6,
    also: ['WISE 0855-0714'],
  },
  { name: 'RW Aurigae', about: 'A star whose brightness changes' },
  { name: 'R Draconis', about: 'A star whose brightness rises and falls over about eight months' },
]

// Not challenge targets: objects this project looked at with its own tools (docs/search.md,
// docs/novae.md). Fixed positions, the ones scripts/warm_cache.py prepares.
interface OwnLook {
  /** The target's name on the page, and its button's accessible name. */
  name: string
  /** A shorter text for the button, when the name is too long for the row; `name` is still what it is called. */
  label?: string
  about: string
  ra: number
  dec: number
  det: number
}

const OWN_LOOKS: readonly OwnLook[] = [
  {
    name: 'Young star in Serpens South',
    label: 'Serpens South',
    about:
      'Flagged by our blind search: about five times brighter in 2026 than in 2025. Not listed as variable in the ' +
      'catalogues we asked. A candidate, not a discovery.',
    ra: 277.50547,
    dec: -2.06198,
    det: 6,
  },
  {
    name: 'Nova V462 Lupi',
    label: 'V462 Lupi',
    about:
      'A star that erupted in June 2025, after SPHEREx began. Open "Spectrum of the target" to see its glowing gas ' +
      'and the warm glow at long wavelengths, and "Brightness over time" to see it fade. Position from AAVSO.',
    ra: 227.01362,
    dec: -40.14308,
    det: 6,
  },
  {
    name: 'Nova V572 Velorum',
    label: 'V572 Velorum',
    about:
      'A star that erupted in June 2025 during one of SPHEREx\'s visits: faint before, too bright to measure after. ' +
      'Position from AAVSO.',
    ra: 156.30783,
    dec: -53.522,
    det: 2,
  },
]

/** The backend's limit on the length of a name. */
const MAX_NAME_LENGTH = 80

const sameName = (a: string, b: string) => a.toLowerCase() === b.toLowerCase()

function presetNamed(query: string): Preset | undefined {
  return PRESETS.find((p) => sameName(p.name, query) || p.also?.some((other) => sameName(other, query)))
}

function Example({ children }: { children: string }) {
  return <code className="searchbar-example">{children}</code>
}

// What to try next, shown after the sentence that says what went wrong. Each one is
// worded so that no comma or full stop has to sit against an example.
const FIX = {
  empty: (
    <>
      For example <Example>Barnard's Star</Example> or <Example>{COORD_EXAMPLES[0]}</Example>
    </>
  ),
  coords: (
    <>
      Examples that work: <Example>{COORD_EXAMPLES[0]}</Example> or <Example>{COORD_EXAMPLES[1]}</Example>
    </>
  ),
  name: (
    <>
      Check the spelling: <Example>Barnard's Star</Example> is a name that works. Or give coordinates such as{' '}
      <Example>{COORD_EXAMPLES[0]}</Example>
    </>
  ),
  later: (
    <>
      Try again in a minute, or give coordinates instead, such as <Example>{COORD_EXAMPLES[0]}</Example>
    </>
  ),
  connection: <>Check your connection and try again.</>,
  either: (
    <>
      Try a name such as <Example>Barnard's Star</Example> or coordinates such as{' '}
      <Example>{COORD_EXAMPLES[0]}</Example>
    </>
  ),
} as const

type Status =
  | { kind: 'idle' }
  | { kind: 'working'; text: string }
  | { kind: 'found'; text: string }
  | { kind: 'error'; text: string; fix: ReactNode }

function failure(e: unknown): Status {
  if (!(e instanceof ResolveError)) return { kind: 'error', text: 'The name lookup failed.', fix: FIX.either }
  const fix =
    e.kind === 'not_found'
      ? FIX.name
      : e.kind === 'service_down'
        ? FIX.later
        : e.kind === 'unreachable'
          ? FIX.connection
          : FIX.either
  return { kind: 'error', text: e.message, fix }
}

/** "It has moved 270 arcsec since 2000." or, with no known motion, a sentence saying so. */
function motionText(found: ResolvedName): string {
  if (found.pmra === null || found.pmdec === null) return ' No motion is known for it.'
  const moved = found.moved_since_2000_arcsec
  if (moved === null) return ''
  const amount = moved >= 10 ? moved.toFixed(0) : moved >= 0.05 ? moved.toFixed(1) : 'less than 0.1'
  return ` It has moved ${amount} arcsec since 2000.`
}

function foundText(found: ResolvedName): string {
  const where = `RA ${formatRaDeg(found.ra)}°, Dec ${formatDecDeg(found.dec)}°`
  const source = found.source ? ` Source: ${found.source}.` : ''
  return `Found ${plainName(found.name)} at ${where}.${motionText(found)}${source}`
}

/** Called with what a search found, and the target button's name when it came from one (or a typed name that is one). */
export type OnSelect = (target: SearchTarget, picked?: string) => void

/** The search's state, shared by the box in the top bar and the row of target buttons. */
export interface SearchState {
  text: string
  status: Status
  edit: (text: string) => void
  submit: () => void
  pickPreset: (preset: Preset) => void
  pickLook: (look: OwnLook) => void
  pickFind: (find: Find) => void
}

/**
 * Holds the search and hands it to `children`, which put the box (SearchField) and the
 * target buttons (TargetButtons) where they belong on the page.
 */
export function SkySearch({ onSelect, children }: { onSelect: OnSelect; children: (search: SearchState) => ReactNode }) {
  return <>{children(useSkySearch(onSelect))}</>
}

function useSkySearch(onSelect: OnSelect): SearchState {
  const [text, setText] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  // The newest search wins. `latest` counts searches, so an answer that arrives after a
  // newer search began is dropped. `pending` is the lookup still on its way: kept so it
  // can be stopped, and so that asking for the same name again just keeps waiting.
  const latest = useRef(0)
  const pending = useRef<{ name: string; stop: AbortController } | null>(null)
  // A name lookup finishes later, by which time the parent may have passed a new callback.
  const onSelectNow = useRef(onSelect)
  useEffect(() => {
    onSelectNow.current = onSelect
  }, [onSelect])
  useEffect(
    () => () => {
      latest.current += 1
      pending.current?.stop.abort()
    },
    [],
  )

  /** Start a search: whatever was still being looked up no longer counts. */
  function begin(): number {
    pending.current?.stop.abort()
    pending.current = null
    latest.current += 1
    return latest.current
  }

  async function lookUp(name: string, mine: number, preset: Preset | undefined) {
    const stop = new AbortController()
    pending.current = { name, stop }
    setStatus({ kind: 'working', text: `Looking up ${name}…` })
    let found: ResolvedName
    try {
      found = await resolveName(name, stop.signal)
    } catch (e) {
      if (mine === latest.current) {
        pending.current = null
        setStatus(failure(e))
      }
      return
    }
    if (mine !== latest.current) return
    pending.current = null
    setStatus({ kind: 'found', text: foundText(found) })
    const target: SearchTarget = {
      ra: found.ra,
      dec: found.dec,
      name: plainName(found.name),
      pmra: found.pmra,
      pmdec: found.pmdec,
      parallax: found.parallax,
    }
    if (preset?.det !== undefined) target.det = preset.det
    onSelectNow.current(target, preset?.name)
  }

  function search(typed: string, preset?: Preset) {
    const query = typed.replace(/\s+/g, ' ').trim()
    // As a name: curly apostrophes, long dashes, Greek letters and accents made plain.
    const name = nameForLookup(query)
    // Enter pressed again while this very name is being looked up: keep waiting for the
    // answer that is on its way instead of asking the name service a second time.
    if (pending.current?.name === name) return
    const mine = begin()
    if (!/[\p{L}\p{N}]/u.test(query)) {
      setStatus({ kind: 'error', text: 'Type a name or coordinates first.', fix: FIX.empty })
      return
    }
    if (looksLikeCoords(query)) {
      const position = parseCoords(query)
      if (!position.ok) {
        setStatus({ kind: 'error', text: position.reason, fix: FIX.coords })
        return
      }
      const { ra, dec } = position
      // Both forms, so a person can see how their numbers were taken (hours or degrees).
      const sexagesimal = `${formatRaHms(ra)} ${formatDecDms(dec)}`
      setStatus({
        kind: 'found',
        text: `Coordinates read as RA ${formatRaDeg(ra)}°, Dec ${formatDecDeg(dec)}° (${sexagesimal}).`,
      })
      // One of our candidates' places (within 5 arcsec): shown as its button shows it, held at its
      // corrected place. With no motion the page would measure the brightest spot near the centre,
      // which in 2025 was a neighbouring star, and say it was "seen clearly in all 3 visits".
      const find = findAt(ra, dec)
      if (find) {
        setStatus({ kind: 'found', text: `Coordinates read as RA ${formatRaDeg(ra)}°, Dec ${formatDecDeg(dec)}° (${sexagesimal}): that is ${find.name}'s place.` })
        onSelectNow.current(findTarget(find), find.name)
        return
      }
      onSelectNow.current({ ra, dec }) // no motion: nothing is known about what is at a typed position
      return
    }
    // A candidate's name ("Candidate B", "candidate b") is its button.
    const named = FINDS.find((f) => sameName(f.name, query))
    if (named) {
      setStatus({ kind: 'idle' })
      onSelectNow.current(findTarget(named), named.name)
      return
    }
    if (name.length > MAX_NAME_LENGTH) {
      setStatus({
        kind: 'error',
        text: `That name is too long to look up (${MAX_NAME_LENGTH} characters at most).`,
        fix: FIX.either,
      })
      return
    }
    if (hasUnusableCharacters(name)) {
      setStatus({
        kind: 'error',
        text: 'Names are looked up in plain letters and digits, and this one has other characters.',
        fix: FIX.either,
      })
      return
    }
    void lookUp(name, mine, preset ?? presetNamed(name))
  }

  return {
    text,
    status,
    edit: (next) => {
      setText(next)
      if (status.kind === 'error') setStatus({ kind: 'idle' }) // the message was about the old text
    },
    submit: () => search(text),
    pickPreset: (preset) => {
      setText(preset.name)
      search(preset.name, preset)
    },
    pickLook: (look) => {
      begin()
      setText(look.name)
      setStatus({ kind: 'idle' })
      onSelectNow.current({ ra: look.ra, dec: look.dec, name: look.name, det: look.det }, look.name)
    },
    pickFind: (find) => {
      begin()
      setText(find.name)
      setStatus({ kind: 'idle' })
      onSelectNow.current(findTarget(find), find.name)
    },
  }
}

/** The target button for a target shown under `name` (the catalogue's or the button's), if one is. */
function targetNamed(name: string | null): string | null {
  if (!name) return null
  return (
    FINDS.find((find) => sameName(find.name, name))?.name ??
    presetNamed(name)?.name ??
    OWN_LOOKS.find((look) => sameName(look.name, name))?.name ??
    null
  )
}

/**
 * The search box. What it found or what went wrong shows in a small box under it while
 * it is in use, laid over the page so nothing moves; screen readers hear the same from
 * two live regions that are always there.
 */
export function SearchField({ search }: { search: SearchState }) {
  const id = useId()
  const { text, status } = search
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  // Shown whatever has the focus: a lookup on its way, and a message about what went wrong.
  const showAlways = status.kind === 'working' || status.kind === 'error'

  return (
    <form
      className="searchbar"
      role="search"
      aria-label="Search the sky"
      noValidate
      onSubmit={(e) => {
        e.preventDefault() // Enter in the box, or the Search button
        search.submit()
      }}
    >
      <div className="searchbar-row">
        <input
          id={`${id}-input`}
          className="searchbar-input"
          type="search"
          value={text}
          onChange={(e) => search.edit(e.target.value)}
          aria-label="Search by name or coordinates"
          placeholder="Search a star or coordinates"
          maxLength={200}
          autoComplete="off"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          aria-invalid={status.kind === 'error' || undefined}
          aria-describedby={status.kind === 'error' ? errorId : status.kind === 'idle' ? hintId : undefined}
        />
        <button className="searchbar-submit" type="submit" aria-label="Search" title="Search">
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M10.4 10.4L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="searchbar-pop" data-show={showAlways || undefined}>
        {status.kind === 'idle' ? (
          <p id={hintId} className="searchbar-hint">
            Type a name such as <Example>Barnard's Star</Example> or a position, RA then Dec, such as{' '}
            <Example>{COORD_EXAMPLES[0]}</Example> or <Example>{COORD_EXAMPLES[1]}</Example>
          </p>
        ) : (
          <p aria-hidden="true" className={status.kind === 'error' ? 'searchbar-error' : 'searchbar-status'} data-busy={status.kind === 'working' || undefined}>
            {status.text}
            {status.kind === 'error' && <span className="searchbar-fix"> {status.fix}</span>}
          </p>
        )}
      </div>

      {/* Both always present, so screen readers announce what appears in them. */}
      <div className="sr-only">
        <p role="status">{(status.kind === 'working' || status.kind === 'found') && status.text}</p>
        <p id={errorId} role="alert">
          {status.kind === 'error' && (
            <>
              {status.text} {status.fix}
            </>
          )}
        </p>
      </div>
    </form>
  )
}

/**
 * The three candidates our own search found (finds.ts), then the challenge's five test targets,
 * then what this project turned the tool on itself. A candidate's button carries the referee's
 * one allowed sentence as its description.
 * The button whose target is on screen is marked: `picked` is the button that was pressed
 * for it, when one was; otherwise the one named `shown` (the name the target is shown under).
 */
export function TargetButtons({ search, picked, shown }: { search: SearchState; picked: string | null; shown: string | null }) {
  const current = picked ?? targetNamed(shown)
  const button = (name: string, about: string, label: string, onClick: () => void) => (
    <button
      key={name}
      className="target"
      type="button"
      title={about}
      aria-label={label === name ? undefined : name}
      aria-current={current === name ? 'true' : undefined}
      onClick={(e) => {
        onClick()
        releaseFocusAfterPointer(e.currentTarget)
      }}
    >
      {label}
    </button>
  )
  return (
    <div className="target-list">
      <div className="target-group" role="group" aria-label="Candidates our search found">
        {FINDS.map((find) => button(find.name, find.allowed, find.name, () => search.pickFind(find)))}
      </div>
      <span className="target-divider" aria-hidden="true" />
      <div className="target-group" role="group" aria-label="The challenge's test targets">
        {PRESETS.map((preset) => button(preset.name, preset.about, preset.name, () => search.pickPreset(preset)))}
      </div>
      <span className="target-divider" aria-hidden="true" />
      <div className="target-group" role="group" aria-label="What we turned this tool on ourselves">
        {OWN_LOOKS.map((look) => button(look.name, look.about, look.label ?? look.name, () => search.pickLook(look)))}
      </div>
    </div>
  )
}

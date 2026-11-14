// Issue #6: one box for "where in the sky?".
//
// Text that reads as coordinates is turned into a position here (coords.ts). Anything
// else is looked up as a name by the backend (resolve.ts), so a named object's position
// and motion are always the catalogue's, moved to 2026: there are no sky positions in
// this file. Either way the result goes to `onSelect`, and one line under the box says
// what was found.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
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
    about: 'A very cold brown dwarf that only the longest-wavelength detector (6) can see',
    det: 6,
    also: ['WISE 0855-0714'],
  },
  { name: 'RW Aurigae', about: 'A star whose brightness changes' },
  { name: 'R Draconis', about: 'A star whose brightness rises and falls over about eight months' },
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

export function SearchBar({ onSelect }: { onSelect: (target: SearchTarget) => void }) {
  const id = useId()
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
    onSelectNow.current(target)
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
      onSelect({ ra, dec }) // no motion: nothing is known about what is at a typed position
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

  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const presetsId = `${id}-presets`

  return (
    <form
      className="searchbar"
      role="search"
      aria-label="Search the sky"
      noValidate
      onSubmit={(e) => {
        e.preventDefault() // Enter in the box, or the Search button
        search(text)
      }}
    >
      <label className="searchbar-label" htmlFor={`${id}-input`}>
        Search by name or coordinates
      </label>
      <div className="searchbar-row">
        <input
          id={`${id}-input`}
          className="searchbar-input"
          type="search"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            if (status.kind === 'error') setStatus({ kind: 'idle' }) // the message was about the old text
          }}
          placeholder={`Barnard's Star, or ${COORD_EXAMPLES[0]}`}
          maxLength={200}
          autoComplete="off"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          aria-invalid={status.kind === 'error' || undefined}
          aria-describedby={status.kind === 'error' ? errorId : status.kind === 'idle' ? hintId : undefined}
        />
        <button className="searchbar-submit" type="submit">
          Search
        </button>
      </div>

      <div className="searchbar-feedback">
        {status.kind === 'idle' && (
          <p id={hintId} className="searchbar-hint">
            Type a name such as <Example>Barnard's Star</Example> or a position, RA then Dec, such as{' '}
            <Example>{COORD_EXAMPLES[0]}</Example> or <Example>{COORD_EXAMPLES[1]}</Example>
          </p>
        )}
        {/* Both always present, so screen readers announce what appears in them. */}
        <p className="searchbar-status" role="status" data-busy={status.kind === 'working' || undefined}>
          {(status.kind === 'working' || status.kind === 'found') && status.text}
        </p>
        <p id={errorId} className="searchbar-error" role="alert">
          {status.kind === 'error' && (
            <>
              {status.text} <span className="searchbar-fix">{status.fix}</span>
            </>
          )}
        </p>
      </div>

      <div className="searchbar-presets" role="group" aria-labelledby={presetsId}>
        <span id={presetsId} className="searchbar-presets-label">
          Or pick one of the challenge's test targets:
        </span>
        {PRESETS.map((preset) => (
          <button
            key={preset.name}
            className="searchbar-preset"
            type="button"
            title={preset.about}
            onClick={() => {
              setText(preset.name)
              search(preset.name, preset)
            }}
          >
            {preset.name}
          </button>
        ))}
      </div>
    </form>
  )
}

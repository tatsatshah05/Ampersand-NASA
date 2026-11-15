// "Pick a patch of sky" on Observe anomalies: a field for a name or coordinates and "Watch this patch" (the
// screen searches that patch and keeps looking at it), then the menu of what is already watched: everywhere (the default), the sweep of the Milky Way's plane,
// and every patch a blind search has covered, named by its constellation (and by the built-in target
// it is centred on, if any), each with how many anomalies were found there. Whenever the choice is not
// Everywhere, a plain "Show everywhere" button follows the menu. Under it, first the chosen region's
// name ("Showing: ...", so the live region says the name first when the choice changes), then how
// large it is, when it was searched and how many it holds. The groups below follow the choice.
import { useState } from 'react'
import type { UiLevel } from '../address'
import {
  CHOOSE_WATCHED,
  EVERYWHERE,
  FIELD_LABEL,
  FIELD_PLACEHOLDER,
  PICK_HEADING,
  PICK_INTRO,
  WATCH_BUTTON,
  optionText,
  REGION_ID,
  regionAbout,
  regionName,
  SHOW_EVERYWHERE,
  showingLine,
  type RegionOption,
  type SweepData,
} from '../anomalies'
import type { PatchRegions } from '../watchlist'
import './RegionPicker.css'

interface Props {
  level: UiLevel
  value: string
  options: RegionOption[]
  patches: PatchRegions | null
  sweep: SweepData | null
  /** Why the list of patches could not be had, if it could not. */
  problem: string | null
  onChange: (key: string) => void
  /** A typed name or coordinates to watch (the form's submit). */
  onWatch?: (typed: string) => void
  /** Sentences about the patch being watched, in the order to show them (progress, notes, the watch lines). */
  lines?: readonly string[]
  /** A problem with the typed place or the search, shown as an alert. */
  error?: string | null
}

export function RegionPicker({ level, value, options, patches, sweep, problem, onChange, onWatch, lines = [], error = null }: Props) {
  const [typed, setTyped] = useState('')
  const about = [showingLine(regionName(value, options)), ...regionAbout(value, patches, sweep, level)]
  // The menu always holds the chosen value, even before the list it comes from has arrived (a region
  // read from the address): then by its name alone, with no count.
  const known = options.some((o) => o.key === value)
  return (
    <section className="region-picker" id={REGION_ID} aria-labelledby="region-title">
      <h2 id="region-title" className="region-title">
        {PICK_HEADING}
      </h2>
      <p className="region-intro">{PICK_INTRO[level]}</p>
      <form
        className="watch-form"
        onSubmit={(e) => {
          e.preventDefault()
          onWatch?.(typed)
        }}
      >
        <label htmlFor="watch-place">{FIELD_LABEL}</label>
        <div className="watch-row">
          <input
            id="watch-place"
            type="text"
            className="watch-input"
            value={typed}
            placeholder={FIELD_PLACEHOLDER}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setTyped(e.target.value)}
          />
          <button type="submit" className="primary watch-button">
            {WATCH_BUTTON}
          </button>
        </div>
      </form>
      <div className="watch-status" aria-live="polite">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
      </div>
      <p className="region-choose">
        <label htmlFor="region-choice">{CHOOSE_WATCHED}</label>
      </p>
      <div className="region-row">
        <select id="region-choice" className="region-select" value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {optionText(o)}
            </option>
          ))}
          {!known && <option value={value}>{regionName(value, options)}</option>}
        </select>
        {value !== EVERYWHERE && (
          <button type="button" className="region-everywhere" onClick={() => onChange(EVERYWHERE)}>
            {SHOW_EVERYWHERE}
          </button>
        )}
      </div>
      {problem && (
        <p role="alert" className="notice">
          The list of searched patches could not be loaded: {problem}
        </p>
      )}
      <div className="region-about" aria-live="polite">
        {about.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </section>
  )
}

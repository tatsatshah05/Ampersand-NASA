// "Choose a region" on Observe anomalies: everywhere (the default), the sweep of the Milky Way's plane,
// and every patch a blind search has covered, named by its constellation (and by the built-in target
// it is centred on, if any), each with how many anomalies were found there. Whenever the choice is not
// Everywhere, a plain "Show everywhere" button follows the menu. Under it, first the chosen region's
// name ("Showing: ...", so the live region says the name first when the choice changes), then how
// large it is, when it was searched and how many it holds. The groups below follow the choice.
import type { UiLevel } from '../address'
import {
  EVERYWHERE,
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
}

export function RegionPicker({ level, value, options, patches, sweep, problem, onChange }: Props) {
  const about = [showingLine(regionName(value, options)), ...regionAbout(value, patches, sweep, level)]
  // The menu always holds the chosen value, even before the list it comes from has arrived (a region
  // read from the address): then by its name alone, with no count.
  const known = options.some((o) => o.key === value)
  return (
    <section className="region-picker" id={REGION_ID} aria-labelledby="region-title">
      <h2 id="region-title" className="region-title">
        <label htmlFor="region-choice">Choose a region</label>
      </h2>
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

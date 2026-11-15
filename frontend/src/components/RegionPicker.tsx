// "Choose a region" on Observe anomalies: everywhere (the default), the sweep of the Milky Way's plane,
// and every patch a blind search has covered, named by its constellation (and by the built-in target
// it is centred on, if any), each with how many anomalies were found there. Under it, how large the
// chosen region is, when it was searched and how many it holds. The groups below follow the choice.
import type { UiLevel } from '../address'
import { optionText, regionAbout, type RegionOption, type SweepData } from '../anomalies'
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
  const about = regionAbout(value, patches, sweep, level)
  return (
    <section className="region-picker" aria-labelledby="region-title">
      <h2 id="region-title" className="region-title">
        <label htmlFor="region-choice">Choose a region</label>
      </h2>
      <select id="region-choice" className="region-select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {optionText(o)}
          </option>
        ))}
      </select>
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

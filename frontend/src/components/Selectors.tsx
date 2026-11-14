// Issue #7: which detector, how wide a patch of sky, and which kind of picture.
// The menus and their wording follow Anu's selectors (detecter_mode_selector.jsx and
// public/viewer.html); difference and sum add one more choice each.
import type { ChangeEvent } from 'react'
import { DETECTORS, FOV_PRESETS, DEFAULT_SELECTION, type Selection } from '../address'
import type { Mode, Reference, Track } from '../api'
import { releaseFocusAfterPointer } from '../focus'

const MODE_LABELS: [Mode, string][] = [
  ['normal', 'Normal (one picture per visit)'],
  ['difference', 'Difference (what changed)'],
  ['sum', 'Sum (one deeper picture)'],
]

interface Props {
  selection: Selection
  /** Whether the target's motion is known, so that a sum can follow it. */
  motionKnown: boolean
  onChange: (change: Partial<Selection>) => void
}

export function Selectors({ selection, motionKnown, onChange }: Props) {
  // Keep a field of view that came from the address even if it is not one of the presets.
  const fovs = FOV_PRESETS.includes(selection.fov) ? FOV_PRESETS : [...FOV_PRESETS, selection.fov].sort((a, b) => a - b)

  const pick = (change: (value: string) => Partial<Selection>) => (e: ChangeEvent<HTMLSelectElement>) => {
    onChange(change(e.target.value))
    releaseFocusAfterPointer(e.currentTarget) // so the space bar and arrow keys go back to the player
  }

  return (
    <div className="selectors" role="group" aria-label="What to show">
      <label className="field">
        Detector
        <select value={selection.det} onChange={pick((v) => ({ det: Number(v) }))}>
          {DETECTORS.map((d) => (
            <option key={d.number} value={d.number}>
              D{d.number}: {d.from.toFixed(2)} to {d.to.toFixed(2)} µm
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Field of view
        <select value={selection.fov} onChange={pick((v) => ({ fov: Number(v) }))}>
          {fovs.map((f) => (
            <option key={f} value={f}>
              {f}°{f === DEFAULT_SELECTION.fov ? ' (default)' : ''}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Mode
        <select value={selection.mode} onChange={pick((v) => ({ mode: v as Mode }))}>
          {MODE_LABELS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {selection.mode === 'difference' && (
        <label className="field">
          Against
          <select value={selection.reference} onChange={pick((v) => ({ reference: v as Reference }))}>
            <option value="first">the first visit</option>
            <option value="mean">the average of all visits</option>
          </select>
        </label>
      )}
      {selection.mode === 'sum' && (
        <label className="field">
          Lined up on
          <select value={selection.track} onChange={pick((v) => ({ track: v as Track }))}>
            <option value="sky">the sky (stars stay sharp)</option>
            {/* Offered when a motion is known; kept in the menu if a link already chose it. */}
            <option value="target" disabled={!motionKnown && selection.track !== 'target'}>
              {motionKnown || selection.track === 'target' ? "the target's motion (the target stays sharp)" : "the target's motion (not known here)"}
            </option>
          </select>
        </label>
      )}
    </div>
  )
}

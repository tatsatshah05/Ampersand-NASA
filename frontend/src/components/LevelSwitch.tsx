// The Beginner / Expert switch, and the plain paragraph Beginner shows about the picture.
import type { UiLevel } from '../address'
import { releaseFocusAfterPointer } from '../focus'

export const EXPERT_ADDS =
  'Expert adds the six detectors, difference and sum views, overlays, spectra, brightness charts, the search of a patch and asteroid labels.'

const SIDES: { level: UiLevel; label: string }[] = [
  { level: 'beginner', label: 'Beginner' },
  { level: 'expert', label: 'Expert' },
]

export function LevelSwitch({ level, onChange }: { level: UiLevel; onChange: (level: UiLevel) => void }) {
  return (
    <div className="level-switch">
      <div className="level-buttons" role="group" aria-label="How much to show">
        {SIDES.map((side) => (
          <button
            key={side.level}
            type="button"
            className="toggle"
            aria-pressed={level === side.level}
            onClick={(e) => {
              if (level !== side.level) onChange(side.level)
              releaseFocusAfterPointer(e.currentTarget)
            }}
          >
            {side.label}
          </button>
        ))}
      </div>
      <p className="hint">
        {level === 'beginner'
          ? `Beginner: the picture and what moved. ${EXPERT_ADDS}`
          : 'Expert: every control. Beginner: just the picture and what moved.'}
      </p>
    </div>
  )
}

export function BeginnerGuide() {
  return (
    <section className="panel" aria-label="What am I looking at?">
      <h2>What am I looking at?</h2>
      <p>
        These are real pictures from NASA's SPHEREx space telescope. Each one is from a different visit to this patch of
        sky, a few months apart. Stars stay put, so something that shifts or changes brightness from one picture to the
        next is what to look for. White is brighter. Press Play, or "Blink first and last", to flip between the pictures.
      </p>
    </section>
  )
}

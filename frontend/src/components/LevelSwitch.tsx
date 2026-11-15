// The Beginner / Expert switch, and the few plain sentences Beginner shows about the picture.
import type { UiLevel } from '../address'
import { releaseFocusAfterPointer } from '../focus'

export const EXPERT_ADDS =
  'Expert adds the six detectors, difference and sum views, overlays, spectra, brightness charts, the search of a patch, asteroid labels and the search for a distant world (Planet X).'

const SIDES: { level: UiLevel; label: string; about: string }[] = [
  { level: 'beginner', label: 'Beginner', about: 'The picture and what moved.' },
  { level: 'expert', label: 'Expert', about: EXPERT_ADDS },
]

/** Two joined buttons; the level on screen is the pressed one. Each says what it shows as a tooltip. */
export function LevelSwitch({ level, onChange }: { level: UiLevel; onChange: (level: UiLevel) => void }) {
  return (
    <div className="level-switch" role="group" aria-label="How much to show">
      {SIDES.map((side) => (
        <button
          key={side.level}
          type="button"
          className="segment"
          aria-pressed={level === side.level}
          title={side.about}
          onClick={(e) => {
            if (level !== side.level) onChange(side.level)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          {side.label}
        </button>
      ))}
    </div>
  )
}

export function BeginnerGuide() {
  return (
    <section className="guide" aria-labelledby="guide-title">
      <h2 id="guide-title">What am I looking at?</h2>
      <p>
        Real infrared pictures of this patch of sky from NASA's SPHEREx telescope, months apart. Stars stay put, so
        anything that moves or changes brightness is worth a look. Press Play or Blink to compare.
      </p>
    </section>
  )
}

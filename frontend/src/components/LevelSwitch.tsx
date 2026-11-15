// The Beginner / Expert switch, and the few plain sentences Beginner shows about the picture.
import type { UiLevel } from '../address'
import { releaseFocusAfterPointer } from '../focus'
import { GO_FURTHER, guideSteps, stepName, type Progress } from '../guide'

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

/**
 * Beginner's guide: three steps and a line on where to go next. The step the visitor is on
 * is marked by the hairline and the text colour only, inside badges of one fixed size, so
 * nothing moves when a step is done. It is a list, not a set of buttons: it never gets in the way.
 */
export function StepGuide({ progress, still = false }: { progress: Progress; still?: boolean }) {
  return (
    <section className="guide" aria-label="Where to start">
      <ol className="guide-steps">
        {guideSteps(progress, still).map((step) => (
          <li key={step.n} data-state={step.state} aria-current={step.state === 'now' ? 'step' : undefined}>
            <span className="guide-n" role="img" aria-label={stepName(step)}>
              {step.n}
            </span>
            {step.label}
          </li>
        ))}
      </ol>
      <p className="guide-further">{GO_FURTHER}</p>
    </section>
  )
}

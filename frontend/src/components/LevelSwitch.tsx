// The Beginner / Expert switch (shown in LevelDock, at the bottom right of every screen), and
// Beginner's step guide.
import type { ReactNode } from 'react'
import type { UiLevel } from '../address'
import { releaseFocusAfterPointer } from '../focus'
import { GO_FURTHER, guideSteps, stepName, type Progress } from '../guide'

export const EXPERT_ADDS =
  'Every tool written for scientists, with all the numbers, plus the six detectors, the difference and sum views and the overlays.'

const SIDES: { level: UiLevel; label: string; about: string }[] = [
  { level: 'beginner', label: 'Beginner', about: 'Every tool, written in plain words.' },
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
export function StepGuide({ progress, still = false, info }: { progress: Progress; still?: boolean; info?: ReactNode }) {
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
      <p className="guide-further">
        {GO_FURTHER}
        {info}
      </p>
    </section>
  )
}

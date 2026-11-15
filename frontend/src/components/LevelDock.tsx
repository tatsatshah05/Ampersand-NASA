// The Beginner | Expert switch and, in Beginner, its "i", in a small dock fixed at the bottom
// right corner of the window on every screen. The level belongs to the app, not to a screen:
// each screen keeps it in its address and on this device (address.ts), and every link between
// screens carries it. Each screen leaves room at its foot so the dock covers nothing.
import type { UiLevel } from '../address'
import { INFO_NAMES, levelInfo } from '../guide'
import { InfoButton } from './InfoButton'
import { LevelSwitch } from './LevelSwitch'
import './LevelDock.css'

interface Props {
  level: UiLevel
  onChange: (level: UiLevel) => void
  /** Called when the "i" is opened (the Viewer pauses the visits and counts it as reading). */
  onInfoOpen?: () => void
}

export function LevelDock({ level, onChange, onInfoOpen }: Props) {
  return (
    // The "i" goes before the switch, so the switch itself sits in the corner.
    <div className="level-dock">
      {level === 'beginner' && <InfoButton name={INFO_NAMES.level} text={levelInfo()} onOpen={onInfoOpen} />}
      <LevelSwitch level={level} onChange={onChange} />
    </div>
  )
}

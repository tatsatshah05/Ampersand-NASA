// Over the picture of one of our sweep's candidates (finds.ts): "Before · Aug 2025" and
// "After · Mar 2026", the visit where nothing is seen at its place and the first where it clearly
// is (wording.ts, beforeAfter). Both labels are always there and only the mark of the one on
// screen moves, so no word changes while the pictures flip (the rule of the side column too).
// The table and the screen-reader line already say which visit is which, so it is hidden from
// screen readers.
import type { FramesReady } from '../api'
import { beforeAfter, monthYear } from '../wording'

export function BeforeAfter({ data, current }: { data: FramesReady; current: number }) {
  const pair = beforeAfter(data)
  if (!pair) return null
  const when = (i: number) => monthYear(data.frames[i].date_mean)
  return (
    <div className="before-after" aria-hidden="true">
      <span className={current === pair.before ? 'on' : undefined}>
        Before<span className="before-after-when"> · {when(pair.before)}</span>
      </span>
      <span className={current === pair.after ? 'on' : undefined}>
        After<span className="before-after-when"> · {when(pair.after)}</span>
      </span>
    </div>
  )
}

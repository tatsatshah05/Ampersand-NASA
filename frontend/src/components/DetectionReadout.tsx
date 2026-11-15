// How strongly the target is detected in the frame on screen, how good its position is,
// and which neighbouring stars share its light. All from the /api/frames response; a
// response without these fields (an older cached one) shows nothing.
import type { Frame } from '../api'
import { blendSentences, detectionSentence, positionSentence } from '../detection'

/** `detectionOnly` leaves out the position and neighbouring-star lines (Beginner shows just how clearly it is seen). */
export function DetectionReadout({ frame, detectionOnly = false }: { frame: Frame; detectionOnly?: boolean }) {
  const detection = detectionSentence(frame)
  const lines = (detectionOnly ? [] : [positionSentence(frame), ...blendSentences(frame)]).filter((l): l is string => l !== null)
  if (!detection && lines.length === 0) return null
  return (
    <div className="detection-readout">
      {detection && <p className={`detection detection-${frame.detection}`}>{`${detection}.`}</p>}
      {lines.map((l) => (
        <p key={l} className="detection-extra">
          {l}
        </p>
      ))}
    </div>
  )
}

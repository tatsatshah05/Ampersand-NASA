// The picture shown while a view loads: the app in miniature. A star steps across three
// places, as a moving star does from one SPHEREx visit to the next, and the ring that marks
// "measured here" in the real pictures follows it, leaving a faint mark where it has been.
// It is a drawing, never data: it sits in the loading box only, and it is hidden from screen
// readers (the box's words say what is happening). With "reduce motion" it is a still picture
// of the same thing: the star at its last place, the two earlier places marked.
import './LoadingStar.css'

// Faint stars of the field, which stay put: x, y, radius.
const FIELD: ReadonlyArray<readonly [number, number, number]> = [
  [18, 24, 1.1],
  [30, 62, 0.7],
  [44, 100, 0.9],
  [72, 18, 1.3],
  [94, 96, 0.8],
  [120, 28, 0.7],
  [132, 104, 1.2],
  [152, 12, 0.9],
  [186, 76, 1.1],
  [198, 30, 0.8],
  [206, 102, 1.3],
]

// A four-pointed sparkle, 9 units from centre to tip.
const SPARKLE = 'M0 -9C1.2 -2.6 2.6 -1.2 9 0C2.6 1.2 1.2 2.6 0 9C-1.2 2.6 -2.6 1.2 -9 0C-2.6 -1.2 -1.2 -2.6 0 -9Z'

export function LoadingStar() {
  return (
    <svg className="loading-star" viewBox="0 0 220 120" aria-hidden="true" focusable="false">
      <g className="ls-field">
        {FIELD.map(([x, y, r]) => (
          <circle key={`${x},${y}`} cx={x} cy={y} r={r} />
        ))}
      </g>
      {/* Where it has been: the path so far and a small mark at each earlier place. */}
      <path className="ls-trail ls-trail-1" d="M58 84L110 62" />
      <path className="ls-trail ls-trail-2" d="M110 62L162 40" />
      <circle className="ls-ghost ls-ghost-1" cx="58" cy="84" r="3" />
      <circle className="ls-ghost ls-ghost-2" cx="110" cy="62" r="3" />
      {/* The star and the ring that follows it. */}
      <g className="ls-hero">
        <circle className="ls-glow" r="13" />
        <g className="ls-ring">
          <circle r="15" />
          <path d="M0 -15V-21M15 0H21M0 15V21M-15 0H-21" />
        </g>
        <path className="ls-sparkle" d={SPARKLE} />
      </g>
    </svg>
  )
}

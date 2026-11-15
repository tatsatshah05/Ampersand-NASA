// The sweep of the Milky Way's plane on Observe anomalies: its 14 survivors (public/anomalies/sweep.json,
// exported from docs/sweep/ by scripts/export_anomalies.py) in four groups: the three candidates (whose
// cards are at the top of the screen), the two known novae, the six known variable stars and the three
// set aside after a closer look. Each with what it is known as and its place (Beginner: what it is and its
// constellation only), and a link to the Viewer.
import type { UiLevel } from '../address'
import {
  findOf,
  survivorAddress,
  survivorLines,
  survivorName,
  survivorPlace,
  SWEEP_GROUPS,
  SWEEP_HEADING,
  WATCH_LINK,
  type SweepData,
} from '../anomalies'
import './SweepGroups.css'

interface Props {
  level: UiLevel
  sweep: SweepData | null
  problem: string | null
}

export function SweepGroups({ level, sweep, problem }: Props) {
  return (
    <section className="sweep-groups" aria-labelledby="sweep-groups-title">
      <h2 id="sweep-groups-title" className="sweep-groups-title">
        {SWEEP_HEADING[level]}
      </h2>
      {problem && (
        <p role="alert" className="notice">
          {problem}
        </p>
      )}
      {!sweep && !problem && <p role="status">Loading the sweep’s list…</p>}
      {sweep &&
        SWEEP_GROUPS.map((group) => {
          const items = sweep.survivors.filter((s) => s.kind === group.kind)
          const titleId = `sweep-${group.kind}`
          return (
            <section key={group.kind} className="sweep-group" aria-labelledby={titleId}>
              <h3 id={titleId} className="sweep-group-title">
                {group.label[level]} <span className="sweep-count">({items.length})</span>
              </h3>
              <ol className="sweep-items">
                {items.map((s) => {
                  const find = findOf(s)
                  const place = survivorPlace(s, level)
                  return (
                    <li key={`${s.ra},${s.dec}`} className={`sweep-item sweep-${s.kind}`}>
                      <p className="sweep-name">{survivorName(s, level)}</p>
                      {place && <p className="sweep-place">{place}</p>}
                      {survivorLines(s, level).map((line) => (
                        <p key={line} className="sweep-line">
                          {line}
                        </p>
                      ))}
                      <p className="sweep-links">
                        {find && <a href={`#find-${find.key}`}>See its card</a>}
                        <a href={survivorAddress(s, level)}>{find ? WATCH_LINK : 'Look at it in the viewer'}</a>
                      </p>
                    </li>
                  )
                })}
              </ol>
            </section>
          )
        })}
    </section>
  )
}

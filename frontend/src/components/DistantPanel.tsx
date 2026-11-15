// Distant-world search: looks in a patch for an object hundreds to tens of thousands of times
// as far from the Sun as the Earth is. Such an object jumps between SPHEREx visits because the
// Earth has moved to the other side of the Sun, and the size of the jump gives its distance.
// Everything shown is what GET /api/distant returned, in the words of src/distant.ts. The
// usual answer is a limit, not a find. A planted practice object is a SIMULATION, kept in its
// own state and never shown without its banner.
import { useEffect, useState } from 'react'
import { releaseFocusAfterPointer } from '../focus'
import {
  candidateHeadline,
  catalogueSentence,
  chanceSentence,
  followAddress,
  practiceAddress,
  SHARE_NOTE,
  limitSentence,
  mjy,
  patchSentence,
  perDetectorSentences,
  plantedSentence,
  PASS_NOTE,
  passWords,
  PLANT_LEVELS,
  positionDate,
  progressSentence,
  runDistant,
  searchFov,
  simulationSentence,
  supportSentence,
  FIRST_TIME_NOTE,
  whole,
  type Candidate,
  type DistantQuery,
  type DistantResult,
  type DistantStatus,
  type PlantLevel,
} from '../distant'
import { limitsSentences } from '../search'
import { skyToPixel, type Grid } from '../projection'
import type { UiLevel } from '../address'
import { DISTANT_FAILED, DISTANT_INTRO, DISTANT_TITLE, DISTANT_WAITING, distantResult } from '../plain'
import { PlainWords, ScienceFold } from './ScienceFold'
import './SearchPanel.css'
import './DistantPanel.css'
import './Scroll.css'

type Phase =
  | { state: 'running'; status: DistantStatus | null }
  | { state: 'done'; result: DistantResult }
  | { state: 'failed'; message: string }

/** The practice run being shown: its own level and seed, and its own answer. */
interface Sim {
  level: PlantLevel
  seed: number
  /** Counts retries of the same level and seed. */
  attempt: number
  phase: Phase
}

interface Props {
  query: { ra: number; dec: number; fov: number }
  onClose: () => void
  /** The candidates to mark on the picture (real or simulated), or an empty list. */
  onCandidates?: (candidates: Candidate[], simulation: boolean) => void
  /** Centre the viewer on a sky position. */
  onLook?: (ra: number, dec: number) => void
  /** How it is written: Expert as it always was, Beginner in plain words with the rest in one closed fold. */
  level?: UiLevel
}

/** Mount with a fresh `key` for each patch: the search starts when it appears. */
export function DistantPanel(props: Props) {
  return <Panel {...props} />
}

const DETECTORS = '56'

/** Run one search, reporting each answer to `set`. Returns the function that stops it. */
function start(q: DistantQuery, set: (p: Phase) => void): () => void {
  const ctrl = new AbortController()
  runDistant(q, { signal: ctrl.signal, onStatus: (status) => set({ state: 'running', status }) })
    .then((last) => {
      if (ctrl.signal.aborted) return
      if (last.status === 'done' && last.result) set({ state: 'done', result: last.result })
      else set({ state: 'failed', message: last.error ?? 'The search stopped without saying why.' })
    })
    .catch((e: unknown) => {
      if (!ctrl.signal.aborted) set({ state: 'failed', message: e instanceof Error ? e.message : String(e) })
    })
  return () => ctrl.abort()
}

const SIM_FALLBACK = 'One made-up moving object has been added to these real SPHEREx images. It is not a real detection, and nothing here is a discovery.'

/** Always on screen with a simulation answer: no way to close it. */
export function SimBanner({ notice }: { notice?: string }) {
  return (
    <div className="sim-banner distant-sim" role="note" aria-label="This is a simulation">
      <strong>SIMULATION.</strong> {notice ?? SIM_FALLBACK}
    </div>
  )
}

function Panel({ query, onClose, onCandidates, onLook, level: uiLevel = 'expert' }: Props) {
  const { ra, dec } = query
  const fov = searchFov(query.fov)
  // The real answer and the practice answer are kept apart, so one is never shown as the other.
  const [real, setReal] = useState<Phase>({ state: 'running', status: null })
  const [attempt, setAttempt] = useState(0)
  const [level, setLevel] = useState<PlantLevel>('easy')
  const [sim, setSim] = useState<Sim | null>(null)
  const simLevel = sim?.level
  const simSeed = sim?.seed
  const simAttempt = sim?.attempt

  useEffect(
    () => start({ ra, dec, fov, detectors: DETECTORS }, setReal),
    [ra, dec, fov, attempt],
  )

  useEffect(() => {
    if (!simLevel || simSeed === undefined) return
    return start({ ra, dec, fov, detectors: DETECTORS, plant: simLevel, seed: simSeed, plant_detector: 5 }, (phase) =>
      setSim((s) => (s && s.level === simLevel && s.seed === simSeed ? { ...s, phase } : s)),
    )
  }, [ra, dec, fov, simLevel, simSeed, simAttempt])

  // What is marked on the picture follows what is on screen.
  const shown = sim ? sim.phase : real
  const marked = shown.state === 'done' ? shown.result.candidates : null
  const simulated = sim !== null
  useEffect(() => {
    onCandidates?.(marked ?? [], simulated)
    return () => onCandidates?.([], false)
  }, [marked, simulated, onCandidates])

  const retry = () => {
    if (sim) setSim({ ...sim, phase: { state: 'running', status: null }, attempt: sim.attempt + 1 })
    else {
      setReal({ state: 'running', status: null })
      setAttempt(attempt + 1)
    }
  }
  const plant = (seed: number) => setSim({ level, seed, attempt: 0, phase: { state: 'running', status: null } })

  const plain = uiLevel === 'beginner'
  const head = (title: string) => (
    <div className="search-head">
      <h2>{title}</h2>
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  )
  // Everything Expert shows under its title. Beginner keeps it in its fold, with the progress
  // said in one sentence that does not change (no clock, no moving bar).
  const body = (
    <>
      <p className="hint">
        Patch: RA {ra.toFixed(4)}°, Dec {dec >= 0 ? '+' : '-'}
        {Math.abs(dec).toFixed(4)}°. {patchSentence(fov)}
      </p>

      {shown.state === 'running' &&
        (plain ? (
          <p role="status">{DISTANT_WAITING}</p>
        ) : (
          <div role="status" className="search-progress">
            <p>{shown.status ? progressSentence(shown.status) : 'Starting the search…'}</p>
            <p className="hint">{FIRST_TIME_NOTE}</p>
          </div>
        ))}

      {shown.state === 'failed' && (
        <div role="alert" className="search-failed">
          <p>The search could not finish: {shown.message}</p>
          <button type="button" onClick={retry}>
            Try again
          </button>
        </div>
      )}

      {shown.state === 'done' && <Answer result={shown.result} onLook={onLook} />}

      <div className="distant-practice">
        <label>
          Level{' '}
          <select value={level} onChange={(e) => setLevel(e.target.value as PlantLevel)}>
            {PLANT_LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={(e) => {
            plant(sim ? sim.seed : 1)
            releaseFocusAfterPointer(e.currentTarget)
          }}
        >
          Try it on a planted object (simulation)
        </button>
        {sim && (
          <>
            <button type="button" onClick={() => plant(sim.seed + 1)}>
              Plant another
            </button>
            <button type="button" onClick={() => setSim(null)}>
              Back to the real search
            </button>
          </>
        )}
      </div>
    </>
  )

  if (plain) {
    // The plain words are about the real search only; a practice run lives in the fold, with its banner.
    return (
      <section className="panel search distant plain-panel" aria-label="Search for a distant world">
        {head(DISTANT_TITLE)}
        <p className="plain-intro">{DISTANT_INTRO}</p>
        {real.state === 'running' && (
          <p role="status" className="plain-intro">
            {DISTANT_WAITING}
          </p>
        )}
        {real.state === 'failed' && (
          <div role="alert" className="search-failed">
            <p>
              {DISTANT_FAILED} {real.message}
            </p>
            <button
              type="button"
              onClick={() => {
                setReal({ state: 'running', status: null })
                setAttempt(attempt + 1)
              }}
            >
              Try again
            </button>
          </div>
        )}
        {real.state === 'done' && <PlainWords lines={distantResult(real.result, query.fov)} />}
        {sim && <SimBanner />}
        {real.state !== 'running' && <ScienceFold>{body}</ScienceFold>}
      </section>
    )
  }
  return (
    <section className="panel search distant" aria-label="Search for a distant world">
      {sim && shown.state !== 'done' && <SimBanner />}
      {head('Search for a distant world (Planet X)')}
      {body}
    </section>
  )
}

/** The answer to one search. A simulation answer always carries its banner and the planted truth. */
export function Answer({ result, onLook }: { result: DistantResult; onLook?: (ra: number, dec: number) => void }) {
  const failures = result.failures
  return (
    <>
      {result.simulation && <SimBanner notice={result.notice} />}
      <p className="search-summary distant-answer">{result.answer}</p>

      {result.simulation && result.planted && (
        <div className="distant-truth">
          <p>
            <strong>The truth.</strong> {plantedSentence(result.planted)}
          </p>
          <p>
            <strong>What the search said.</strong> {simulationSentence(result)}
          </p>
          <p>
            <a href={practiceAddress(result) ?? undefined} target="_blank" rel="noopener noreferrer">
              See this planted object on the practice screen
            </a>{' '}
            and try to spot it yourself. It is not in the real pictures above.
          </p>
        </div>
      )}

      {result.candidates.length > 0 && (
        <ol className="search-list distant-list">
          {result.candidates.map((c, i) => (
            <CandidateCard key={`${c.detector}-${c.distance_au}-${i}`} candidate={c} number={i + 1} simulation={result.simulation} onLook={onLook} />
          ))}
        </ol>
      )}

      {result.limit.length > 0 && (
        <>
          <h3>How faint an object could be and still have been found</h3>
          <div className="table-scroll">
          <table className="distant-table">
            <thead>
              <tr>
                <th>Distance (times the Earth-Sun distance)</th>
                <th>Jump between visits (arcseconds)</th>
                <th>Faintest it could be (mJy)</th>
                <th>Share of the picture</th>
                <th>Exposures used</th>
              </tr>
            </thead>
            <tbody>
              {result.limit.map((r) => (
                <tr key={r.distance_au} title={limitSentence(r)}>
                  <td>{whole(r.distance_au)}</td>
                  <td>{whole(r.jump_arcsec)}</td>
                  <td>{mjy(r.faintest_mjy)}</td>
                  <td>{Math.round(r.share_of_picture * 100)}%</td>
                  <td>{passWords(r.exposures) ?? 'all exposures of each visit'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <p className="hint">
            The best detector and the better of the two passes are used at each distance. {PASS_NOTE} {SHARE_NOTE} Hover a row, or open the notes below, for it as a sentence.
          </p>
        </>
      )}

      <p>{chanceSentence(result.chance)}</p>
      <ul className="distant-counts">
        {perDetectorSentences(result).map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      <p>{catalogueSentence(result.catalogue)}</p>

      {failures.length > 0 && (
        <div className="notice" role="alert">
          <p>Some parts of the search failed, so the answer above may be incomplete:</p>
          <ul>
            {failures.map((f) => {
              const text = typeof f === 'string' ? f : JSON.stringify(f)
              return <li key={text}>{text}</li>
            })}
          </ul>
        </div>
      )}

      <details className="search-limits">
        <summary>What this search cannot find, and how it works</summary>
        <ul>
          {limitsSentences(result.limits).map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
        <p>{result.method}</p>
        <ul>
          {result.limit.map((r) => (
            <li key={r.distance_au}>{limitSentence(r)}</li>
          ))}
        </ul>
      </details>
      <p className="hint">Credit: {result.credit}</p>
    </>
  )
}

function CandidateCard({
  candidate: c,
  number,
  simulation,
  onLook,
}: {
  candidate: Candidate
  number: number
  simulation: boolean
  onLook?: (ra: number, dec: number) => void
}) {
  const href = followAddress(c)
  const first = c.positions[0]
  return (
    <li className={`search-card candidate ${simulation ? 'simulated' : ''}`}>
      <div className="search-card-head">
        <span className="search-badge" aria-label={`Candidate ${number}`}>
          {number}
        </span>
        <div>
          <p className="search-kind">
            {simulation ? 'SIMULATION' : 'Candidate'} · detector {c.detector}
            <span className={`search-verdict ${c.verdict}`}>{c.verdict === 'clean' ? 'Clean' : 'Caution'}</span>
            {simulation && c.is_planted_object !== undefined && (
              <span className="search-verdict">{c.is_planted_object ? 'The planted object' : 'Not the planted object'}</span>
            )}
          </p>
          <p className="search-headline">{candidateHeadline(c)}</p>
        </div>
      </div>
      {passWords(c.exposures) && <p className="hint">Found using {passWords(c.exposures)}.</p>}
      <p>
        It jumps about {whole(c.jump_arcsec)} arcseconds between visits and drifts about {c.drift_arcsec_per_year.toFixed(1)} arcseconds a
        year.
      </p>
      <div className="table-scroll">
      <table className="distant-table">
        <thead>
          <tr>
            <th>Visit</th>
            <th>Date</th>
            <th>RA (°)</th>
            <th>Dec (°)</th>
            <th>Times the noise</th>
            <th>mJy</th>
          </tr>
        </thead>
        <tbody>
          {c.positions.map((p) => (
            <tr key={p.epoch}>
              <td>{p.epoch}</td>
              <td>{positionDate(p)}</td>
              <td>{p.ra.toFixed(5)}</td>
              <td>{p.dec.toFixed(5)}</td>
              <td>{p.times_noise.toFixed(1)}</td>
              <td>{mjy(p.flux_mjy)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {c.cautions.length > 0 && (
        <ul className="search-flags">
          {c.cautions.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
      {supportSentence(c).map((t) => (
        <p key={t} className="hint">
          {t}
        </p>
      ))}
      {simulation ? (
        <p className="search-candidate">This is the search's answer for a planted practice object. It is not a real candidate.</p>
      ) : (
        <p className="search-candidate">A candidate, not a finding: nothing here has been confirmed by another telescope.</p>
      )}
      {/* The buttons below open the real pictures, which do not hold a planted object: not offered in a simulation. */}
      <div className="distant-actions">
        {onLook && first && !simulation && (
          <button
            type="button"
            onClick={(e) => {
              onLook(first.ra, first.dec)
              releaseFocusAfterPointer(e.currentTarget)
            }}
          >
            Look at the first position
          </button>
        )}
        {href && !simulation && (
          <a href={href} target="_blank" rel="noopener noreferrer">
            Open a view that follows it
          </a>
        )}
      </div>
    </li>
  )
}

/**
 * A ring at each visit's position of every candidate, joined by a thin line in date order.
 * Positions come from ra and dec through the VIEW's grid, since the searched patch can be wider
 * than the view; those outside the picture are skipped. The ring of the visit on screen is bolder.
 */
export function DistantMarkers({
  candidates,
  grid,
  scale,
  epoch,
  simulation = false,
}: {
  candidates: Candidate[]
  grid: Grid
  scale: number
  epoch: number | null
  simulation?: boolean
}) {
  const r = 14 / scale // screen pixels to picture pixels: marks keep their size at every zoom
  const inside = (p: { x: number; y: number }) => p.x >= 0 && p.y >= 0 && p.x <= grid.sizePx && p.y <= grid.sizePx
  return (
    <svg
      className={`overlay distant-markers ${simulation ? 'simulated' : ''}`}
      viewBox={`0 0 ${grid.sizePx} ${grid.sizePx}`}
      role="img"
      aria-label={simulation ? 'SIMULATION: where the search put each candidate' : 'Where the search put each candidate'}
    >
      {candidates.map((c, i) => {
        const dots = [...c.positions]
          .sort((a, b) => a.epoch - b.epoch)
          .map((p) => ({ epoch: p.epoch, ...skyToPixel(p.ra, p.dec, grid) }))
          .filter(inside)
        return (
          <g key={`${c.detector}-${c.distance_au}-${i}`}>
            <title>{`${simulation ? 'SIMULATION ' : ''}${candidateHeadline(c)}`}</title>
            {dots.length > 1 && (
              <polyline points={dots.map((d) => `${d.x},${d.y}`).join(' ')} className="distant-line" vectorEffect="non-scaling-stroke" />
            )}
            {dots.map((d) => (
              <circle
                key={d.epoch}
                cx={d.x}
                cy={d.y}
                r={d.epoch === epoch ? r * 1.5 : r}
                className={`distant-ring ${d.epoch === epoch ? 'now' : ''}`}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {simulation && dots[0] && (
              <text x={dots[0].x + r} y={dots[0].y - r} fontSize={13 / scale} className="distant-label" vectorEffect="non-scaling-stroke">
                SIMULATION
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

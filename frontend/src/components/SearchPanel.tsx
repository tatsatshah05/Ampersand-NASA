// Search mode: one press lists everything in the patch that moved or changed brightness
// between SPHEREx visits, and says for each whether the catalogues already know it.
// Everything shown is what GET /api/search returned, in the words of src/search.ts.
// Anything no catalogue lists is a candidate and is never called a discovery.
import { useEffect, useState } from 'react'
import { releaseFocusAfterPointer } from '../focus'
import { skyToPixel, type Grid } from '../projection'
import {
  answeredSentence,
  candidateSentence,
  catalogueFailureSentence,
  catalogueSentence,
  changeDetail,
  emptySentence,
  flagSentence,
  headline,
  isCandidate,
  kindLabel,
  messagesOf,
  noData,
  progressSentence,
  rejectedHeadline,
  runSearch,
  strengthSentence,
  summarySentence,
  verdictSentence,
  type SearchObject,
  type SearchQuery,
  type SearchResult,
  type SearchStatus,
} from '../search'
import './SearchPanel.css'

type Phase =
  | { state: 'running'; status: SearchStatus | null }
  | { state: 'done'; result: SearchResult }
  | { state: 'failed'; message: string }

interface Props {
  query: SearchQuery
  onClose: () => void
  /** Centre the viewer on a sky position. */
  onLook: (ra: number, dec: number) => void
  /** The objects to mark on the picture, or an empty list when there are none. */
  onObjects: (objects: SearchObject[]) => void
}

/** Mount with a fresh `key` for each patch: the search starts when it appears. */
export function SearchPanel(props: Props) {
  return <Panel {...props} />
}

function Panel({ query, onClose, onLook, onObjects }: Props) {
  const [phase, setPhase] = useState<Phase>({ state: 'running', status: null })
  const [attempt, setAttempt] = useState(0)
  const { ra, dec, fov, detectors } = query

  useEffect(() => {
    const ctrl = new AbortController()
    runSearch({ ra, dec, fov, detectors }, { signal: ctrl.signal, onStatus: (status) => setPhase({ state: 'running', status }) })
      .then((last) => {
        if (last.status === 'done' && last.result) {
          setPhase({ state: 'done', result: last.result })
          onObjects(last.result.objects)
        } else {
          setPhase({ state: 'failed', message: last.error ?? 'The search stopped without saying why.' })
        }
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setPhase({ state: 'failed', message: e instanceof Error ? e.message : String(e) })
      })
    return () => {
      ctrl.abort()
      onObjects([])
    }
  }, [ra, dec, fov, detectors, attempt, onObjects])

  return (
    <section className="panel search" aria-label="Search for things that moved or changed">
      <div className="search-head">
        <h2>Anything that moved or changed in this patch</h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="hint">
        Patch: RA {ra.toFixed(4)}°, Dec {dec >= 0 ? '+' : '-'}
        {Math.abs(dec).toFixed(4)}°, {fov}° across, all six detectors. The search is not told what to look for. Every strength
        below is measured against the same measurement at hundreds of empty places in the same picture.
      </p>

      {phase.state === 'running' && (
        <div role="status" className="search-progress">
          <p>{phase.status ? progressSentence(phase.status) : 'Starting the search…'}</p>
          <div className="progress" aria-hidden="true">
            <span />
          </div>
          <p className="hint">A patch whose images are already here takes 20 to 50 seconds; otherwise several minutes.</p>
        </div>
      )}

      {phase.state === 'failed' && (
        <div role="alert" className="search-failed">
          <p>The search could not finish: {phase.message}</p>
          <button
            type="button"
            onClick={() => {
              setPhase({ state: 'running', status: null })
              setAttempt(attempt + 1)
            }}
          >
            Try again
          </button>
        </div>
      )}

      {phase.state === 'done' && <Done result={phase.result} onLook={onLook} />}
    </section>
  )
}

function Done({ result, onLook }: { result: SearchResult; onLook: (ra: number, dec: number) => void }) {
  const s = result.summary
  const notes = messagesOf(s)
  const failed = catalogueFailureSentence(s)

  if (noData(s)) {
    return (
      <div className="search-empty">
        <p>SPHEREx has no usable pictures of this patch, so nothing could be searched.</p>
        {notes.map((n) => (
          <p key={n} className="hint">
            {n}
          </p>
        ))}
      </div>
    )
  }

  return (
    <>
      <p className="search-summary">{result.objects.length ? summarySentence(s) : emptySentence(s)}</p>
      {s.n_below_threshold > 0 && (
        <p className="hint">{s.n_below_threshold} more fell short of 5 times the noise and are not listed.</p>
      )}
      {notes.map((n) => (
        <p key={n} className="notice">
          {n}
        </p>
      ))}
      <p className="search-catalogues">
        {s.catalogues_answered.length ? `Catalogues that answered: ${s.catalogues_answered.join(', ')}.` : 'No catalogue answered.'}{' '}
        {failed}
      </p>

      {result.objects.length > 0 && (
        <ol className="search-list">
          {result.objects.map((o, i) => (
            <Card key={o.id} object={o} number={i + 1} onLook={onLook} />
          ))}
        </ol>
      )}

      {result.rejected.length > 0 && (
        <details className="search-rejected">
          <summary>Looked like a find, but is an artefact ({result.rejected.length})</summary>
          <p className="hint">
            These reached 5 times the noise but have the signature of something other than a real moving or changing
            object. They are shown only so that you can see what was thrown out.
          </p>
          <ul>
            {result.rejected.map((r) => (
              <li key={`${r.detector}-${r.id}`}>
                <p>
                  <strong>Rejected.</strong> {rejectedHeadline(r)}
                </p>
                <ul>
                  {r.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      )}

      <details className="search-limits">
        <summary>What this search cannot find</summary>
        <p>{result.limits}</p>
      </details>
    </>
  )
}

function Card({ object: o, number, onLook }: { object: SearchObject; number: number; onLook: (ra: number, dec: number) => void }) {
  const candidate = candidateSentence(o)
  const detail = o.evidence.kind === 'changer' ? changeDetail(o.evidence) : null
  return (
    <li className={`search-card ${isCandidate(o) ? 'candidate' : ''}`}>
      <div className="search-card-head">
        <span className="search-badge" aria-label={`Object ${number}`}>
          {number}
        </span>
        <div>
          <p className="search-kind">
            {kindLabel(o.kind)}
            <span className={`search-verdict ${o.verdict}`}>{o.verdict === 'clean' ? 'Clean' : 'Caution'}</span>
            {isCandidate(o) && <span className="search-verdict candidate-tag">Candidate</span>}
          </p>
          <p className="search-headline">{headline(o)}</p>
        </div>
      </div>
      <p>{strengthSentence(o)}</p>
      {detail && <p className="hint">{detail}</p>}
      <p>
        <strong>Catalogues.</strong> {catalogueSentence(o)}
      </p>
      <p className="hint">{answeredSentence(o.catalogue_status)}</p>
      {candidate && <p className="search-candidate">{candidate}</p>}
      <p>
        <strong>{o.verdict === 'clean' ? 'Verdict: clean.' : 'Verdict: caution.'}</strong> {verdictSentence(o)}
      </p>
      {o.flags.length > 0 && (
        <ul className="search-flags">
          {o.flags.map((f) => (
            <li key={f}>{flagSentence(f)}</li>
          ))}
        </ul>
      )}
      <p className="hint">
        Place: RA {o.ra.toFixed(5)}°, Dec {o.dec >= 0 ? '+' : '-'}
        {Math.abs(o.dec).toFixed(5)}°
      </p>
      <button
        type="button"
        onClick={(e) => {
          onLook(o.ra, o.dec)
          releaseFocusAfterPointer(e.currentTarget)
        }}
      >
        Look at this one
      </button>
    </li>
  )
}

/** A numbered ring on the picture for each object the search found. Drawn in picture pixels. */
export function SearchMarkers({ objects, grid, scale }: { objects: SearchObject[]; grid: Grid; scale: number }) {
  const r = 11 / scale // screen pixels to picture pixels: marks keep their size at every zoom
  return (
    <svg className="overlay search-markers" viewBox={`0 0 ${grid.sizePx} ${grid.sizePx}`} role="img" aria-label="Objects found by the search">
      {objects.map((o, i) => {
        const p = skyToPixel(o.ra, o.dec, grid)
        if (p.x < 0 || p.y < 0 || p.x > grid.sizePx || p.y > grid.sizePx) return null
        return (
          <g key={o.id}>
            <title>{`${i + 1}: ${headline(o)}`}</title>
            <circle cx={p.x} cy={p.y} r={r} className="search-ring" vectorEffect="non-scaling-stroke" />
            <text x={p.x + r * 1.15} y={p.y - r * 1.15} fontSize={13 / scale} className="search-number">
              {i + 1}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

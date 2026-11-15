// Known asteroids and comets that crossed the patch, from NASA/JPL's small-body services,
// each with the single SPHEREx exposure it was predicted in. Loaded only when the panel is
// opened: the first lookup of a patch takes minutes because JPL's identification service
// answers slowly. Positions are predictions; the sentence under each picture is what the
// exposure itself shows there.
import { useEffect, useRef, useState } from 'react'
import { bodyVerdict, fetchSmallBodies, groupByBody, whenInWords, type SmallBodiesQuery, type SmallBodiesResponse, type SmallBodyCrossing, plainSummary } from '../smallbodies'
import './SpectrumPanel.css'
import './SmallBodiesPanel.css'

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'done'; data: SmallBodiesResponse }

interface Props {
  query: SmallBodiesQuery
  onClose: () => void
  level?: import('../address').UiLevel
}

export function SmallBodiesPanel({ query, onClose }: Props) {
  // A different view gets a fresh panel: remounting resets what is loaded.
  const key = `${query.ra},${query.dec},${query.fov},${query.detector}`
  return <Panel key={key} query={query} onClose={onClose} />
}

function Panel({ query, onClose }: Props) {
  // App builds `query` anew on every render: depend on its numbers, or every render would ask again.
  const { ra, dec, fov, detector } = query
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const section = useRef<HTMLElement>(null)

  useEffect(() => {
    section.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [load.state])

  useEffect(() => {
    const ctrl = new AbortController()
    // Started on the next tick, so the discarded first mount of React's development mode
    // never sends a request.
    const timer = window.setTimeout(() => {
      fetchSmallBodies({ ra, dec, fov, detector }, ctrl.signal)
        .then((data) => setLoad({ state: 'done', data }))
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [ra, dec, fov, detector])

  const data = load.state === 'done' ? load.data : null
  const groups = data ? groupByBody(data.bodies) : []

  return (
    <section className="panel smallbodies" aria-label="Known asteroids and comets" ref={section}>
      <div className="spectrum-head">
        <h2>Known asteroids and comets that crossed this patch</h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      {load.state === 'loading' && (
        <p className="spectrum-what">
          Asking NASA/JPL which known bodies were here, and measuring this patch in each exposure they were predicted in.
          The first time for a patch this takes a few minutes; after that it is instant.
        </p>
      )}
      {load.state === 'error' && <p className="status error">Could not look up asteroids and comets: {load.message}</p>}
      {data?.message && <p className="spectrum-what">{data.message}</p>}
      {data && !data.message && groups.length === 0 && data.problems.length === 0 && (
        <p className="smallbodies-none">No known asteroid or comet was in this patch during any SPHEREx exposure.</p>
      )}
      {data && groups.length > 0 && (
        <p className="spectrum-what">
          {groups.length === 1 ? '1 known body was' : `${groups.length} known bodies were`} predicted inside this patch during{' '}
          {data.bodies.length === 1 ? '1 exposure' : `${data.bodies.length} exposures`} of detector {query.detector}. Each position is a
          prediction; what the exposure itself shows there is measured separately.
        </p>
      )}
      {data && data.problems.length > 0 && (
        <p className="status error">
          This list may be incomplete: NASA/JPL did not answer for {data.problems.length === 1 ? 'one request' : `${data.problems.length} requests`}.
          Reload the panel to try again.
        </p>
      )}
      {groups.map((group) => (
        <Body key={group[0]?.name} group={group} />
      ))}
      {data && (
        <p className="hint">
          {data.limits} {data.observer_note} Small-body data: {data.credit}.
        </p>
      )}
    </section>
  )
}

function Body({ group }: { group: SmallBodyCrossing[] }) {
  const first = group[0]
  if (!first) return null
  const mags = group.map((c) => c.vmag).filter((v): v is number => v != null)
  return (
    <article className="smallbody">
      <h3>
        {first.name}
        <span className="smallbody-kind">
          {first.kind === 'comet' ? 'comet' : 'asteroid'}
          {first.designation ? `, ${first.designation}` : ''}
        </span>
      </h3>
      <p>
        Predicted to be about magnitude {mags.length ? Math.min(...mags).toFixed(1) : 'unknown'}, moving about{' '}
        {Math.round(first.rate_arcsec_per_hour)} arcseconds per hour across the sky. {bodyVerdict(group)}
      </p>
      <div className="smallbody-exposures">
        {group.map((c) => (
          <Exposure key={c.id} crossing={c} />
        ))}
      </div>
    </article>
  )
}

function Exposure({ crossing: c }: { crossing: SmallBodyCrossing }) {
  return (
    <figure className="smallbody-exposure">
      {c.picture ? (
        <div className="smallbody-picture">
          <img src={c.picture} alt={`${c.name} in one SPHEREx exposure, centred on its predicted position`} />
          <svg viewBox="0 0 100 100" aria-hidden="true">
            {/* four ticks round the predicted place, leaving the place itself clear */}
            <path d="M50 22V34M50 66V78M22 50H34M66 50H78" />
          </svg>
        </div>
      ) : (
        <div className="smallbody-picture smallbody-nopicture">No picture</div>
      )}
      <figcaption>
        <b>{whenInWords(c.exposure.time)}</b>
        <br />
        Visit {c.exposure.visit ?? '?'}, detector {c.exposure.detector}, {c.exposure.wavelength_um[0].toFixed(2)} to{' '}
        {c.exposure.wavelength_um[1].toFixed(2)} µm
        <br />
        Predicted magnitude {c.vmag == null ? 'unknown' : c.vmag.toFixed(1)}
        <br />
        <span className={`smallbody-verdict ${c.verdict ?? ''}`}>{plainSummary(c.summary)}</span>
      </figcaption>
    </figure>
  )
}

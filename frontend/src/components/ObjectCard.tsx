// "What is it?": what the catalogues know about the thing at a place, in plain words, with a
// picture drawn only from measured numbers (portrait.ts). Self-contained: give it a place
// and a level; it asks /api/identify once for that place and never changes by itself.
//
//   <ObjectCard ra={269.446267} dec={4.768222} name="Barnard's Star" level="beginner"
//               onLook={(t) => recentre(t)} />
import { useEffect, useId, useState } from 'react'
import type { UiLevel } from '../address'
import {
  ILLUSTRATION_LABEL,
  NOTHING_HERE,
  beginnerFacts,
  blurSentences,
  cardTitle,
  catalogueName,
  discLabel,
  distanceForScale,
  distanceScaleCaption,
  expertRows,
  fetchIdentify,
  identifyUrl,
  kindSentence,
  lookTarget,
  notKnownLine,
  num,
  partOfSentence,
  pictureNotes,
  servicesLine,
  unreachableSentence,
  type IdentifyResult,
  type LookTarget,
} from '../identify'
import { NEAREST_STAR_LY, blackbodyRgb255, distanceScale, glowsVisibly, hex, nearestLabelSide, portraitLayout, type Body } from '../portrait'
import './ObjectCard.css'

export interface ObjectCardProps {
  /** where the object is on the SPHEREx pictures (degrees, positions for 2026.0 as the page uses) */
  ra: number
  dec: number
  /** the name the page already has for exactly this place, if any */
  name?: string
  level: UiLevel
  /** when given, a "Look at this one" button that hands back the object's place and motion */
  onLook?: (target: LookTarget) => void
}

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'done'; result: IdentifyResult }

export function ObjectCard(props: ObjectCardProps) {
  // A new place is a new card: its state starts again from "loading".
  return <Lookup key={`${props.ra},${props.dec}`} {...props} />
}

function Lookup({ ra, dec, name, level, onLook }: ObjectCardProps) {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    // Started on the next tick, so React's discarded first mount in development sends nothing.
    const timer = window.setTimeout(() => {
      fetchIdentify(identifyUrl(ra, dec), ctrl.signal)
        .then((result) => setLoad({ state: 'done', result }))
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [ra, dec])
  return <ObjectCardView load={load} name={name} level={level} onLook={onLook} />
}

/** The card for a given state of the lookup: no effects, so it can be rendered in tests. */
export function ObjectCardView({ load, name, level, onLook }: { load: Load; name?: string; level: UiLevel; onLook?: (t: LookTarget) => void }) {
  if (load.state === 'loading') {
    return (
      <section className="oc" aria-busy="true" aria-label="What is it?">
        <p className="oc-eyebrow">What is it?</p>
        {name ? <h2 className="oc-title">{name}</h2> : null}
        <p className="oc-status">Looking this place up in Gaia and SIMBAD…</p>
      </section>
    )
  }
  if (load.state === 'error') {
    return (
      <section className="oc" aria-label="What is it?">
        <p className="oc-eyebrow">What is it?</p>
        {name ? <h2 className="oc-title">{name}</h2> : null}
        <p className="oc-notice" role="alert">
          The lookup could not be done. {load.message}
        </p>
      </section>
    )
  }
  return <Card result={load.result} name={name} level={level} onLook={onLook} />
}

export function Card({ result: r, name, level, onLook }: { result: IdentifyResult; name?: string; level: UiLevel; onLook?: (t: LookTarget) => void }) {
  const title = cardTitle(r, name)
  const aka = catalogueName(r, name)
  const unreachable = unreachableSentence(r)
  const found = r.gaia != null || r.simbad != null
  return (
    <section className="oc" aria-label={`What is it? ${title}`}>
      <p className="oc-eyebrow">What is it?</p>
      <h2 className="oc-title">{title}</h2>
      {aka ? <p className="oc-aka">In SIMBAD: {aka}</p> : null}
      {level === 'expert' && found ? <Identifiers result={r} /> : null}
      {unreachable ? (
        <p className="oc-notice" role="status">
          {unreachable}
        </p>
      ) : null}
      {found ? <Found result={r} name={name} level={level} /> : <NothingFound result={r} level={level} />}
      {onLook ? (
        <button type="button" className="oc-look" onClick={() => onLook(lookTarget(r, name))}>
          Look at this one
        </button>
      ) : null}
      <p className="oc-credit">Catalogues: {r.credit}.</p>
    </section>
  )
}

function Identifiers({ result: r }: { result: IdentifyResult }) {
  return (
    <dl className="oc-ids">
      {r.gaia ? (
        <div>
          <dt>Gaia</dt>
          <dd>
            <code>{r.gaia.name}</code>, {num(r.gaia.separation_arcsec, 2)} arcsec from the place asked
          </dd>
        </div>
      ) : null}
      {r.simbad ? (
        <div>
          <dt>SIMBAD</dt>
          <dd>
            <code>{r.simbad.main_id}</code>, {num(r.simbad.separation_arcsec, 2)} arcsec
          </dd>
        </div>
      ) : null}
      {r.match ? (
        <div>
          <dt>Match</dt>
          <dd>{r.match.text}</dd>
        </div>
      ) : null}
    </dl>
  )
}

function Found({ result: r, name, level }: { result: IdentifyResult; name?: string; level: UiLevel }) {
  const kind = kindSentence(r)
  const partOf = partOfSentence(r)
  const blur = blurSentences(r)
  return (
    <>
      {kind ? <p className="oc-kind">{kind}</p> : null}
      {partOf ? <p className="oc-line">{partOf}</p> : null}
      {blur.map((b) => (
        <p key={b} className="oc-line oc-blur">
          {b}
        </p>
      ))}
      <Picture result={r} name={name} />
      {level === 'beginner' ? <Beginner result={r} /> : <Expert result={r} />}
    </>
  )
}

function Beginner({ result: r }: { result: IdentifyResult }) {
  const facts = beginnerFacts(r)
  return (
    <>
      {facts.length ? (
        <ul className="oc-facts">
          {facts.map((f) => (
            <li key={f.text}>
              {f.text} <span className="oc-src">{f.source}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="oc-unknown">{notKnownLine(r)}</p>
    </>
  )
}

function Expert({ result: r }: { result: IdentifyResult }) {
  const rows = expertRows(r)
  return (
    <>
      <div className="oc-table-wrap">
        <table className="oc-table oc-values">
          <colgroup>
            <col className="oc-w-quantity" />
            <col className="oc-w-value" />
            <col className="oc-w-error" />
            <col className="oc-w-source" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Quantity</th>
              <th scope="col">Value</th>
              <th scope="col">Error or range</th>
              <th scope="col">Catalogue and column</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.quantity + row.column}>
                <th scope="row">{row.quantity}</th>
                <td className="oc-num">
                  {row.value}
                  {row.unit ? ` ${row.unit}` : ''}
                </td>
                <td className="oc-num">{row.uncertainty}</td>
                <td>
                  {row.catalogue}
                  <span className="oc-col">
                    <Breakable text={row.column} />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Neighbours result={r} level="expert" />
      <p className="oc-unknown">{notKnownLine(r)}</p>
      <ul className="oc-notes">
        {r.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
        <li>{servicesLine(r)}.</li>
      </ul>
    </>
  )
}

function Neighbours({ result: r, level }: { result: IdentifyResult; level: UiLevel }) {
  const list = r.neighbours
  const radius = num(r.query.neighbour_radius_arcsec)
  if (!list.length) {
    const asked = r.services.gaia.answered && r.services.simbad.answered
    return <p className="oc-line">{asked ? `No other catalogued source within ${radius} arcseconds.` : ''}</p>
  }
  if (level === 'beginner') {
    return (
      <>
        <h3 className="oc-h3">Catalogued sources within {radius} arcseconds</h3>
        <ul className="oc-near">
          {list.map((n) => (
            <li key={n.name}>
              {num(n.separation_arcsec, 1)} arcseconds away: {n.simbad_name ?? n.name}
              {n.same_pixel ? ' (inside the same SPHEREx pixel)' : ''} <span className="oc-src">{n.catalogue === 'SIMBAD' ? 'SIMBAD' : 'Gaia'}</span>
            </li>
          ))}
        </ul>
      </>
    )
  }
  return (
    <>
      <h3 className="oc-h3">Other catalogued sources within {radius} arcsec</h3>
      <div className="oc-table-wrap">
        <table className="oc-table oc-nb">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Distance (arcsec)</th>
              <th scope="col">G (mag)</th>
              <th scope="col">BP-RP (mag)</th>
              <th scope="col">Same pixel</th>
            </tr>
          </thead>
          <tbody>
            {list.map((n) => (
              <tr key={n.name}>
                <th scope="row">
                  <code>{n.name}</code>
                  {n.simbad_name && n.simbad_name !== n.name ? <span className="oc-col">SIMBAD: {n.simbad_name}</span> : null}
                  {n.simbad_type ? <span className="oc-col">{n.simbad_type.label}</span> : null}
                </th>
                <td className="oc-num" data-label="Distance (arcsec)">{num(n.separation_arcsec, 2)}</td>
                <td className="oc-num" data-label="G">{n.g_mag != null ? num(n.g_mag, 2) : ''}</td>
                <td className="oc-num" data-label="BP-RP">{n.bp_rp != null ? num(n.bp_rp, 2) : ''}</td>
                <td data-label="Same pixel:">{n.same_pixel ? 'yes' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function NothingFound({ result: r, level }: { result: IdentifyResult; level: UiLevel }) {
  if (r.nothing_catalogued == null) {
    return <p className="oc-kind">It could not be checked whether anything is listed here, because {r.unreachable.join(' and ')} did not answer.</p>
  }
  const n = r.nearest_catalogued
  const pixel = n && n.separation_arcsec <= r.query.pixel_arcsec ? ', inside the same SPHEREx pixel' : ''
  return (
    <>
      <p className="oc-kind">{NOTHING_HERE}</p>
      <p className="oc-line">
        {n
          ? `The nearest catalogued thing is ${n.simbad_name ?? n.name}, ${num(n.separation_arcsec, 1)} arcseconds away${pixel}.`
          : `Nothing is listed within ${num(r.searched_arcsec)} arcseconds.`}
      </p>
      <Neighbours result={r} level={level} />
    </>
  )
}

// ------------------------------------------------------------------ the picture

// Space is black: the picture is drawn on a black field of its own. Every colour inside it
// is computed from a measured temperature (portrait.ts); the only other colours are the
// white of the label and grey for outlines, ticks and words.
const PLATE_WHITE = '#ffffff'
const PLATE_GREY = '#a1a1a6'
const PLATE_DARK = '#141416'
const NEAREST_TEXT = `Nearest star, ${NEAREST_STAR_LY}`

/** A catalogue column name that may break after its dots and semicolons, never inside a word. */
function Breakable({ text }: { text: string }) {
  const parts = text.split(/(?<=[.;,])/)
  return (
    <>
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 ? <wbr /> : null}
        </span>
      ))}
    </>
  )
}

function Picture({ result: r, name }: { result: IdentifyResult; name?: string }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const t = r.portrait.temperature
  const rad = r.portrait.radius
  const layout = portraitLayout({
    temperatureK: t && typeof t.value === 'number' ? t.value : null,
    radiusRsun: rad && typeof rad.value === 'number' ? rad.value : null,
    label: discLabel(r, name),
  })
  const dist = distanceForScale(r)
  const scale = dist ? distanceScale(dist.ly, dist.low, dist.high) : null
  if (layout.kind === 'none' && !scale) return null
  const notes = pictureNotes(r)
  if (layout.kind === 'none') notes.unshift('No disc: neither its temperature nor its size is in the catalogues we asked.')
  const objectColour = t && typeof t.value === 'number' && glowsVisibly(t.value) ? hex(blackbodyRgb255(t.value)) : PLATE_WHITE
  const source = r.derived.from === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  return (
    <figure className="oc-plate">
      <p className="oc-plate-label">{ILLUSTRATION_LABEL}</p>
      {layout.kind !== 'none' ? (
        <svg className="oc-discs" viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label={describe(layout.bodies)}>
          <defs>
            {layout.bodies
              .filter((b) => b.fill === 'glow')
              .map((b) => (
                <radialGradient key={b.key} id={`${uid}-${b.key}`} cx="50%" cy="50%" r="50%">
                  {b.stops.map((s) => (
                    <stop key={s.offset} offset={s.offset} stopColor={s.color} />
                  ))}
                </radialGradient>
              ))}
          </defs>
          {layout.bodies.map((b) => (
            <g key={b.key}>
              <Disc body={b} gradient={`url(#${uid}-${b.key})`} />
              <text x={b.cx} y={layout.labelY} textAnchor="middle" fill={PLATE_WHITE} fontSize="14">
                {b.label}
              </text>
            </g>
          ))}
        </svg>
      ) : null}
      {scale && dist ? (
        <svg className="oc-scale" viewBox={`0 0 ${scale.width} ${scale.height}`} role="img" aria-label={distanceScaleCaption(dist, source)}>
          <line x1={scale.x0} y1={44} x2={scale.x1} y2={44} stroke={PLATE_GREY} strokeWidth={1.5} />
          {scale.ticks.map((tk, i) => (
            <g key={tk.label}>
              <line x1={tk.x} y1={40} x2={tk.x} y2={48} stroke={PLATE_GREY} strokeWidth={1} />
              <text
                x={tk.x}
                y={64}
                fontSize="12"
                fill={PLATE_GREY}
                textAnchor={i === 0 ? 'start' : 'middle'}
              >
                {i === 0 ? 'Sun' : tk.label}
              </text>
            </g>
          ))}
          <text x={scale.x1 + 8} y={80} fontSize="12" fill={PLATE_GREY} textAnchor="end">
            light-years
          </text>
          <line x1={scale.nearest.x} y1={30} x2={scale.nearest.x} y2={44} stroke={PLATE_WHITE} strokeWidth={1} />
          {nearestLabelSide(scale, NEAREST_TEXT.length * 6.6) === 'right' ? (
            <text x={scale.nearest.x + 3} y={33} fontSize="12" fill={PLATE_GREY} textAnchor="start">
              {NEAREST_TEXT}
            </text>
          ) : (
            <text x={scale.nearest.x - 3} y={33} fontSize="12" fill={PLATE_GREY} textAnchor="end">
              {NEAREST_TEXT}
            </text>
          )}
          {scale.object.xLow != null && scale.object.xHigh != null ? (
            <line x1={scale.object.xLow} y1={44} x2={scale.object.xHigh} y2={44} stroke={objectColour} strokeWidth={4} strokeOpacity={0.55} />
          ) : null}
          <circle cx={scale.object.x} cy={44} r={4.5} fill={objectColour} />
          <text x={clampLabel(scale.object.x, discLabel(r, name), scale.x0, scale.x1)} y={16} fontSize="13" fill={PLATE_WHITE} textAnchor="middle">
            {discLabel(r, name)}
          </text>
          <line x1={scale.object.x} y1={20} x2={scale.object.x} y2={38} stroke={PLATE_WHITE} strokeWidth={1} />
        </svg>
      ) : null}
      <figcaption>
        <ul>
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          {dist ? <li>{distanceScaleCaption(dist, source)}</li> : null}
        </ul>
      </figcaption>
    </figure>
  )
}

function Disc({ body: b, gradient }: { body: Body; gradient: string }) {
  if (b.fill === 'glow') return <circle cx={b.cx} cy={b.cy} r={b.r} fill={gradient} />
  if (b.fill === 'dark') return <circle cx={b.cx} cy={b.cy} r={b.r} fill={PLATE_DARK} stroke={PLATE_GREY} strokeWidth={1.2} />
  return <circle cx={b.cx} cy={b.cy} r={b.r} fill="none" stroke={PLATE_GREY} strokeWidth={b.dot ? 1.5 : 1.2} />
}

/** Keep a centred label inside the line's ends. */
function clampLabel(x: number, label: string, x0: number, x1: number): number {
  const half = (label.length * 6.8) / 2
  return Math.min(Math.max(x, x0 + half - 12), x1 - half + 12)
}

function describe(bodies: Body[]): string {
  return bodies
    .map((b) => (b.radiusRsun != null ? `${b.label}, ${num(b.radiusRsun, 3)} solar radii` : `${b.label}, size not measured`))
    .join('; ')
}

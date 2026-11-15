// "What is it?": what the catalogues know about the thing at a place, in plain words, with a
// picture drawn only from measured numbers (portrait.ts). Self-contained: give it a place
// and a level; it asks /api/identify once for that place and never changes by itself (a
// visitor may press "Try again" after a failure).
//
//   <ObjectCard ra={269.446267} dec={4.768222} epoch={2026.0} name="Barnard's Star" level="beginner"
//               onLook={(t) => recentre(t)} />
import { Fragment, useEffect, useId, useState } from 'react'
import type { UiLevel } from '../address'
import {
  ILLUSTRATION_LABEL,
  NOTHING_HERE,
  PLATE_TAG,
  beginnerFacts,
  blurSentences,
  cardTitle,
  catalogueName,
  colourDrawn,
  disagreements,
  discLabel,
  distanceForScale,
  distanceScaleCaption,
  expertGroups,
  fetchIdentify,
  identifyUrl,
  kindSentence,
  lookTarget,
  notKnownLine,
  nothingFoundLines,
  num,
  partOfSentence,
  pictureDescription,
  pictureNotes,
  readableName,
  searchLine,
  servicesLine,
  sourcesKey,
  systemLine,
  temperatureForPicture,
  unreachableSentence,
  type IdentifyResult,
  type LookTarget,
} from '../identify'
import {
  DISC_LABEL_SIZE,
  SCALE_CHAR,
  SCALE_TEXT_SIZE,
  TAG_SIZE,
  blackbodyRgb255,
  distanceScale,
  glowsVisibly,
  hex,
  nearestLabelSide,
  portraitLayout,
  type Body,
} from '../portrait'
import './ObjectCard.css'

export interface ObjectCardProps {
  /** where the object is on the SPHEREx picture (degrees) */
  ra: number
  dec: number
  /**
   * the date of the picture the place was read from, as a decimal (Julian) year. Stars move:
   * Barnard's Star is 7 arcsec from its 2026.0 place on a September 2026 picture. Leave it out
   * for a position from /api/resolve, which is for 2026.0.
   */
  epoch?: number
  /** the name the page already has for exactly this place, if any */
  name?: string
  level: UiLevel
  /** when given, a "Look at this one" button that hands back the object's place (at 2026.0) and motion */
  onLook?: (target: LookTarget) => void
}

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'done'; result: IdentifyResult }

export function ObjectCard(props: ObjectCardProps) {
  // A new place (or picture date) is a new card: its state starts again from "loading".
  return <Lookup key={`${props.ra},${props.dec},${props.epoch ?? ''}`} {...props} />
}

function Lookup({ ra, dec, epoch, name, level, onLook }: ObjectCardProps) {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const ctrl = new AbortController()
    // Started on the next tick, so React's discarded first mount in development sends nothing.
    const timer = window.setTimeout(() => {
      fetchIdentify(identifyUrl(ra, dec, undefined, epoch), ctrl.signal)
        .then((result) => setLoad({ state: 'done', result }))
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [ra, dec, epoch, attempt])
  const retry = () => {
    setLoad({ state: 'loading' })
    setAttempt((n) => n + 1)
  }
  return <ObjectCardView load={load} name={name} level={level} onLook={onLook} onRetry={retry} />
}

/** The card for a given state of the lookup: no effects, so it can be rendered in tests. */
export function ObjectCardView({
  load,
  name,
  level,
  onLook,
  onRetry,
}: {
  load: Load
  name?: string
  level: UiLevel
  onLook?: (t: LookTarget) => void
  onRetry?: () => void
}) {
  if (load.state === 'loading') {
    return (
      <section className="oc oc-loading" aria-busy="true" aria-label="What is it?">
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
        <div className="oc-notice" role="alert">
          <p>The lookup could not be done. {load.message}</p>
          {onRetry ? <RetryButton onRetry={onRetry} /> : null}
        </div>
      </section>
    )
  }
  return <Card result={load.result} name={name} level={level} onLook={onLook} onRetry={onRetry} />
}

function RetryButton({ onRetry }: { onRetry: () => void }) {
  return (
    <button type="button" className="oc-retry" onClick={onRetry}>
      Try again
    </button>
  )
}

export function Card({
  result: r,
  name,
  level,
  onLook,
  onRetry,
}: {
  result: IdentifyResult
  name?: string
  level: UiLevel
  onLook?: (t: LookTarget) => void
  onRetry?: () => void
}) {
  const title = cardTitle(r, name)
  const aka = catalogueName(r, name)
  const system = systemLine(r, name)
  const unreachable = unreachableSentence(r)
  const found = r.gaia != null || r.simbad != null
  return (
    <section className="oc" aria-label={`What is it? ${title}`}>
      <p className="oc-eyebrow">What is it?</p>
      <h2 className="oc-title">{title}</h2>
      {aka ? <p className="oc-aka">In SIMBAD: {aka}</p> : null}
      {system ? <p className="oc-aka">{system}</p> : null}
      {level === 'expert' ? <Identifiers result={r} /> : null}
      {unreachable ? (
        <div className="oc-notice" role="status">
          <p>{unreachable}</p>
          {onRetry ? <RetryButton onRetry={onRetry} /> : null}
        </div>
      ) : null}
      {found ? <Found result={r} name={name} level={level} /> : <NothingFound result={r} level={level} />}
      {onLook ? (
        <button type="button" className="oc-look" onClick={() => onLook(lookTarget(r, name))}>
          {found ? 'Look at this one' : 'Look at this place'}
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
      {r.choice ? (
        <div>
          <dt>Chosen</dt>
          <dd>{r.choice.text}</dd>
        </div>
      ) : null}
      {r.match ? (
        <div>
          <dt>Match</dt>
          <dd>{r.match.text}</dd>
        </div>
      ) : null}
      <div>
        <dt>Search</dt>
        <dd>{searchLine(r)}</dd>
      </div>
    </dl>
  )
}

function Found({ result: r, name, level }: { result: IdentifyResult; name?: string; level: UiLevel }) {
  const kind = kindSentence(r)
  const partOf = partOfSentence(r, name)
  const blur = blurSentences(r, level)
  return (
    <>
      {kind ? <p className="oc-kind">{kind}</p> : null}
      {partOf ? <p className="oc-line">{partOf}</p> : null}
      {blur.length ? (
        <div className="oc-blur">
          {blur.map((b) => (
            <p key={b} className="oc-line">
              {b}
            </p>
          ))}
        </div>
      ) : null}
      <Picture result={r} name={name} level={level} />
      {level === 'beginner' ? <Beginner result={r} /> : <Expert result={r} />}
    </>
  )
}

function Beginner({ result: r }: { result: IdentifyResult }) {
  const facts = beginnerFacts(r)
  const key = sourcesKey(r)
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
      {key.length ? <p className="oc-key">{key.join(' ')}</p> : null}
    </>
  )
}

/** A value or a range that may break between its parts but never inside a number. */
function Unbroken({ text }: { text: string }) {
  const parts = text.split(' to ')
  return (
    <>
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 ? ' to ' : null}
          <span className="oc-nw">{p}</span>
        </Fragment>
      ))}
    </>
  )
}

function Expert({ result: r }: { result: IdentifyResult }) {
  const groups = expertGroups(r)
  const notes = [...disagreements(r), ...r.notes, `${servicesLine(r)}.`]
  return (
    <>
      <div className="oc-table-wrap">
        <table className="oc-table oc-values">
          <colgroup>
            <col className="oc-w-quantity" />
            <col className="oc-w-value" />
            <col className="oc-w-error" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Quantity</th>
              <th scope="col">Value</th>
              <th scope="col">Error or range</th>
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.title}>
              <tr className="oc-group">
                <th scope="colgroup" colSpan={3}>
                  {g.title}
                </th>
              </tr>
              {g.rows.map((row) => (
                <Fragment key={row.quantity + row.source}>
                  <tr className="oc-row">
                    <th scope="row">{row.quantity}</th>
                    <td className="oc-num">
                      <span className="oc-nw">
                        {row.value}
                        {row.unit ? ` ${row.unit}` : ''}
                      </span>
                    </td>
                    <td className="oc-num">
                      <Unbroken text={row.uncertainty} />
                    </td>
                  </tr>
                  <tr className="oc-srcrow">
                    <td colSpan={3}>
                      <span className="oc-col">
                        <Breakable text={row.source} />
                      </span>
                      {row.notes.map((n) => (
                        <span key={n} className="oc-flag">
                          {n}
                        </span>
                      ))}
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          ))}
        </table>
      </div>
      <Neighbours result={r} level="expert" />
      <p className="oc-unknown">{notKnownLine(r)}</p>
      <ul className="oc-notes">
        {notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </>
  )
}

function Neighbours({ result: r, level }: { result: IdentifyResult; level: UiLevel }) {
  const list = r.neighbours
  const radius = num(r.query.neighbour_radius_arcsec)
  if (!list.length) {
    const asked = r.services.gaia.answered && r.services.simbad.answered
    return asked ? <p className="oc-line">No other catalogued source within {radius} arcseconds.</p> : null
  }
  if (level === 'beginner') {
    return (
      <>
        <h3 className="oc-h3">Catalogued sources within {radius} arcseconds</h3>
        <ul className="oc-near">
          {list.map((n) => (
            <li key={n.name}>
              {num(n.separation_arcsec, 1)} arcseconds away: {readableName(n.display_name)}
              {n.same_pixel ? ' (inside the same SPHEREx pixel)' : ''}
              {n.possibly_spurious ? ' (may not be real)' : ''} <span className="oc-src">{n.catalogue === 'SIMBAD' ? 'SIMBAD' : 'Gaia'}</span>
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
                  {n.possibly_spurious ? (
                    <span className="oc-col">
                      possibly not real: {n.astrometric_params_solved === 3 ? '2-parameter solution, ' : ''}
                      {n.visibility_periods_used != null ? `${n.visibility_periods_used} visibility periods, ` : ''}beside a source 8 or more mag brighter
                    </span>
                  ) : null}
                </th>
                <td className="oc-num" data-label="Distance (arcsec)">
                  {num(n.separation_arcsec, 2)}
                </td>
                <td className="oc-num" data-label="G">
                  {n.g_mag != null ? num(n.g_mag, 2) : ''}
                </td>
                <td className="oc-num" data-label="BP-RP">
                  {n.bp_rp != null ? num(n.bp_rp, 2) : ''}
                </td>
                <td data-label="Same pixel">{n.same_pixel ? 'yes' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function NothingFound({ result: r, level }: { result: IdentifyResult; level: UiLevel }) {
  const key = level === 'beginner' ? sourcesKey(r) : []
  return (
    <>
      {r.nothing_catalogued === true ? <p className="oc-kind">{NOTHING_HERE}</p> : null}
      {nothingFoundLines(r).map((l, i) => (
        <p key={l} className={i === 0 && r.nothing_catalogued !== true ? 'oc-kind' : 'oc-line'}>
          {l}
        </p>
      ))}
      <Neighbours result={r} level={level} />
      {key.length ? <p className="oc-key">{key.join(' ')}</p> : null}
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
// Its distance, 4.25 light-years, is in the caption under the picture.
const NEAREST_TEXT = 'Nearest star'
const TAG_SPACE = 24

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

function Picture({ result: r, name, level }: { result: IdentifyResult; name?: string; level: UiLevel }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const tPicture = temperatureForPicture(r)
  const rad = r.portrait.radius
  const label = discLabel(r, name)
  const layout = portraitLayout({
    temperatureK: tPicture,
    radiusRsun: rad && typeof rad.value === 'number' ? rad.value : null,
    label,
  })
  const dist = distanceForScale(r)
  const scale = dist ? distanceScale(dist.ly, dist.low, dist.high) : null
  if (layout.kind === 'none' && !scale) return null
  const notes = pictureNotes(r, level, layout)
  if (layout.kind === 'none') {
    // With the colour withheld, the colour note comes first and this one follows it.
    if (colourDrawn(r) === 'withheld') notes.push('So no disc is drawn: its size is not measured either.')
    else notes.unshift('No disc: neither its temperature nor its size is in the catalogues we asked.')
  }
  const objectColour = tPicture != null && glowsVisibly(tPicture) ? hex(blackbodyRgb255(tPicture)) : PLATE_WHITE
  const source = r.derived.from === 'SIMBAD' ? 'SIMBAD' : 'Gaia'
  const caption = dist ? distanceScaleCaption(r, dist, source) : null
  const discs = layout.kind !== 'none'
  const discsHeight = layout.height + TAG_SPACE
  const scaleHeight = (scale?.height ?? 0) + (discs ? 0 : TAG_SPACE)
  return (
    <figure className="oc-plate" aria-labelledby={`${uid}-label`}>
      <p className="oc-plate-label" id={`${uid}-label`}>
        {ILLUSTRATION_LABEL}
      </p>
      {discs ? (
        <svg className="oc-discs" viewBox={`0 0 ${layout.width} ${discsHeight}`} role="img" aria-label={pictureDescription(r, layout)}>
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
              <text x={b.cx} y={layout.labelY} textAnchor="middle" fill={PLATE_WHITE} fontSize={DISC_LABEL_SIZE}>
                {b.label}
              </text>
            </g>
          ))}
          <PlateTag x={layout.width / 2} y={discsHeight - 6} />
        </svg>
      ) : null}
      {scale && dist ? (
        <svg className="oc-scale" viewBox={`0 0 ${scale.width} ${scaleHeight}`} aria-hidden="true">
          <line x1={scale.x0} y1={44} x2={scale.x1} y2={44} stroke={PLATE_GREY} strokeWidth={1.5} />
          {scale.ticks.map((tk, i) => (
            <g key={tk.label}>
              <line x1={tk.x} y1={40} x2={tk.x} y2={48} stroke={PLATE_GREY} strokeWidth={1} />
              <text x={tk.x} y={66} fontSize={SCALE_TEXT_SIZE} fill={PLATE_GREY} textAnchor={i === 0 ? 'start' : 'middle'}>
                {i === 0 ? 'Sun' : tk.label}
              </text>
            </g>
          ))}
          <text x={scale.width - 4} y={86} fontSize={SCALE_TEXT_SIZE} fill={PLATE_GREY} textAnchor="end">
            light-years
          </text>
          <line x1={scale.nearest.x} y1={28} x2={scale.nearest.x} y2={44} stroke={PLATE_WHITE} strokeWidth={1} />
          {nearestLabelSide(scale, NEAREST_TEXT.length * SCALE_CHAR) === 'right' ? (
            <text x={scale.nearest.x + 3} y={34} fontSize={SCALE_TEXT_SIZE} fill={PLATE_GREY} textAnchor="start">
              {NEAREST_TEXT}
            </text>
          ) : (
            <text x={scale.nearest.x - 3} y={34} fontSize={SCALE_TEXT_SIZE} fill={PLATE_GREY} textAnchor="end">
              {NEAREST_TEXT}
            </text>
          )}
          {scale.object.xLow != null && scale.object.xHigh != null ? (
            <line x1={scale.object.xLow} y1={44} x2={scale.object.xHigh} y2={44} stroke={objectColour} strokeWidth={4} strokeOpacity={0.55} />
          ) : null}
          <circle cx={scale.object.x} cy={44} r={4.5} fill={objectColour} />
          <text x={clampLabel(scale.object.x, label, scale.x0, scale.width - 4)} y={15} fontSize={SCALE_TEXT_SIZE} fill={PLATE_WHITE} textAnchor="middle">
            {label}
          </text>
          <line x1={scale.object.x} y1={19} x2={scale.object.x} y2={38} stroke={PLATE_WHITE} strokeWidth={1} />
          {discs ? null : <PlateTag x={scale.width / 2} y={scaleHeight - 4} />}
        </svg>
      ) : null}
      <figcaption>
        <ul>
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          {caption ? <li>{caption}</li> : null}
        </ul>
      </figcaption>
    </figure>
  )
}

/** A second, small "drawing, not a photo" mark inside the picture itself, under what is drawn. */
function PlateTag({ x, y }: { x: number; y: number }) {
  return (
    <text x={x} y={y} textAnchor="middle" fill={PLATE_GREY} fontSize={TAG_SIZE} letterSpacing="0.08em">
      {PLATE_TAG}
    </text>
  )
}

function Disc({ body: b, gradient }: { body: Body; gradient: string }) {
  if (b.fill === 'glow') return <circle cx={b.cx} cy={b.cy} r={b.r} fill={gradient} />
  if (b.fill === 'dark') return <circle cx={b.cx} cy={b.cy} r={b.r} fill={PLATE_DARK} stroke={PLATE_GREY} strokeWidth={1.2} />
  return <circle cx={b.cx} cy={b.cy} r={b.r} fill="none" stroke={PLATE_GREY} strokeWidth={b.dot ? 1.5 : 1.2} />
}

/** Keep a centred label inside the picture's ends. */
function clampLabel(x: number, label: string, x0: number, x1: number): number {
  const half = (label.length * SCALE_CHAR) / 2
  return Math.min(Math.max(x, x0 + half - 12), x1 - half)
}

// Issue #11: the spectrum of the target, or of a spot picked on the image.
// Every SPHEREx exposure sees the sky through a different colour of infrared light, so
// one brightness measurement per exposure, set out by wavelength, is a spectrum.
// It shows only what GET /api/spectrum returns: an exposure with no clean measurement
// is a tick on a rail above the chart, never a value.
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { fetchSpectrum, type SpectrumPoint, type SpectrumRequest, type SpectrumResponse } from '../spectrum'
import type { UiLevel } from '../address'
import { circleStarsSentence, measuredSentence } from '../detection'
import {
  SPECTRUM_AXIS_X,
  SPECTRUM_AXIS_Y,
  SPECTRUM_ERROR,
  SPECTRUM_INTRO,
  SPECTRUM_LOADING,
  SPECTRUM_RAILS,
  SPECTRUM_SPOT_ASK,
  SPECTRUM_SPOT_BUTTON,
  SPECTRUM_SPOT_TITLE,
  SPECTRUM_TITLE,
  measureCautions,
  spectrumEmpty,
  spectrumResult,
  spectrumTip,
  spectrumTipValue,
  spectrumVisit,
} from '../plain'
import { PlainWords, ScienceFold } from './ScienceFold'
import './SpectrumPanel.css'

// Visits 1 to 3 get a colour each (checked to stay distinguishable with colour-blindness
// on the panel background; a fourth colour does not pass, so later visits share a grey).
const VISIT_COLOURS = ['#3987e5', '#d95926', '#199e70']
const LATER_COLOUR = 'var(--chart-later)'
const SATURATED_COLOUR = 'var(--chart-saturated)'
const NO_VALUE_COLOUR = '#77776f'
const visitColour = (epoch: number) => VISIT_COLOURS[epoch - 1] ?? LATER_COLOUR

// Chart geometry in SVG units. The wavelength axis is fixed, so every object is drawn
// on the same scale: SPHEREx covers 0.75 to 5.0 micrometres.
const W = 760
const H = 360
const M = { l: 66, r: 14, t: 50, b: 44 }
const PW = W - M.l - M.r
const PH = H - M.t - M.b
const X0 = 0.7
const X1 = 5.05
const xOf = (wavelength: number) => M.l + ((wavelength - X0) / (X1 - X0)) * PW

type Located = SpectrumPoint & { wavelength_um: number }
type Measured = Located & { flux_mjy: number }

interface Mark {
  x: number
  y: number
  point: Located
  /** A measurement, a measurement beyond the top or bottom of the chart, or a rail tick. */
  shape: 'dot' | 'above' | 'below' | 'tick'
  colour: string
  errTop?: number
  errBottom?: number
}

interface Chart {
  bands: { x: number; width: number; label: string; shaded: boolean }[]
  ticks: { y: number; text: string; zero: boolean }[]
  rails: { name: string; y: number }[]
  marks: Mark[]
  offChart: number
  empty: string | null
}

function niceStep(raw: number) {
  const p = Math.pow(10, Math.floor(Math.log10(raw)))
  const f = raw / p
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p
}

/** A brightness to about three figures. */
function fmtValue(v: number) {
  const a = Math.abs(v)
  return v.toFixed(a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3)
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function layout(data: SpectrumResponse, hidden: ReadonlySet<number>): Chart {
  const pts = (data.points ?? []).filter((p): p is Located => p.wavelength_um !== null && !hidden.has(p.epoch))
  const ok = pts.filter((p): p is Measured => p.status === 'ok' && p.flux_mjy !== null)

  // Vertical range. One wild reading must not flatten everything else, so the axis stops
  // a little above the 98th percentile and readings beyond it are drawn as arrowheads at
  // the edge (their values are in the hover text and the CSV).
  let lo = 0
  let hi = 1
  if (ok.length) {
    const v = ok.map((p) => p.flux_mjy).sort((a, b) => a - b)
    const top = Math.max(...ok.map((p) => p.flux_mjy + (p.flux_err_mjy ?? 0)))
    const p98 = v[Math.floor(0.98 * (v.length - 1))]
    hi = v.length >= 20 && p98 > 0 && top > 3 * p98 ? 1.3 * p98 : top
    if (!(hi > 0)) hi = Math.abs(v[0]) || 1
    const bottom = Math.min(...ok.map((p) => p.flux_mjy - (p.flux_err_mjy ?? 0)))
    lo = Math.min(0, Math.max(bottom, -0.35 * hi))
  }
  const step = niceStep((hi - lo) / 5)
  const yTop = hi + 0.04 * (hi - lo)
  const yOf = (v: number) => M.t + PH - ((v - lo) / (yTop - lo)) * PH
  const decimals = Math.max(0, -Math.floor(Math.log10(step)))
  const tickText = (v: number) =>
    hi >= 10000 ? `${(v / 1000).toFixed(step >= 1000 ? 0 : 1)}K` : v.toFixed(decimals)

  const ticks: Chart['ticks'] = []
  for (let t = Math.ceil(lo / step) * step; t <= yTop + 1e-9; t += step) {
    const zero = Math.abs(t) < step / 1e6
    ticks.push({ y: yOf(t), text: tickText(zero ? 0 : t), zero })
  }

  // Which detector saw which wavelengths, as faint stripes with names. Neighbouring
  // detectors overlap a little, so each stripe ends halfway through the overlap.
  const ranges = Object.entries(data.detector_ranges_um ?? {})
    .map(([det, r]) => ({ det, from: r[0], to: r[1] }))
    .sort((a, b) => a.from - b.from)
  const bands = ranges.map((r, i) => {
    const left = i ? (ranges[i - 1].to + r.from) / 2 : r.from
    const right = i < ranges.length - 1 ? (r.to + ranges[i + 1].from) / 2 : r.to
    return { x: xOf(left), width: xOf(right) - xOf(left), label: `D${r.det}`, shaded: i % 2 === 0 }
  })

  const marks: Mark[] = []
  const rails: Chart['rails'] = []
  const rail = (name: string, y: number, colour: string, rows: Located[]) => {
    if (!rows.length) return
    rails.push({ name, y })
    for (const p of rows) marks.push({ x: xOf(p.wavelength_um), y, point: p, shape: 'tick', colour })
  }
  rail('saturated', 26, SATURATED_COLOUR, pts.filter((p) => p.status === 'saturated'))
  rail('no value', 40, NO_VALUE_COLOUR, pts.filter((p) => p.status !== 'ok' && p.status !== 'saturated'))

  let offChart = 0
  for (const p of ok) {
    const x = xOf(p.wavelength_um)
    const colour = visitColour(p.epoch)
    const err = p.flux_err_mjy ?? 0
    if (p.flux_mjy > yTop || p.flux_mjy < lo) {
      offChart += 1
      const above = p.flux_mjy > yTop
      marks.push({ x, y: above ? M.t + 5 : M.t + PH - 5, point: p, shape: above ? 'above' : 'below', colour })
    } else {
      marks.push({
        x,
        y: yOf(p.flux_mjy),
        point: p,
        shape: 'dot',
        colour,
        errTop: yOf(Math.min(p.flux_mjy + err, yTop)),
        errBottom: yOf(Math.max(p.flux_mjy - err, lo)),
      })
    }
  }

  let empty: string | null = null
  if (!ok.length) {
    const epochs = data.epochs ?? []
    if (epochs.length && epochs.every((e) => hidden.has(e.epoch))) empty = 'No visit is switched on.'
    else if (pts.length && pts.every((p) => p.status === 'saturated'))
      empty = 'Too bright: every exposure is saturated here, so there is no value to plot.'
    else if (pts.length) empty = 'No exposure gave a clean measurement here.'
    else empty = 'SPHEREx has no exposure of this spot.'
  }
  return { bands, ticks, rails, marks, offChart, empty }
}

/** What was measured, in words, from what the backend says it followed. */
function describeTarget(request: SpectrumRequest, data: SpectrumResponse) {
  const place = `RA ${request.ra.toFixed(5)}°, Dec ${request.dec.toFixed(5)}°`
  // The backend says what it measured; the guesses below are for an older response without that.
  const measured = measuredSentence(data.measured)
  if (measured) return `${measured} (${place})`
  const t = data.target
  if (t?.origin === 'request') return `The target of this view (${place} in 2026), followed with its known motion.`
  if (t?.source_id) return `Gaia DR3 ${t.source_id}, the catalogued star at ${place}, followed with its Gaia motion.`
  return `The spot at ${place}. No catalogued star with a known motion is there, so the same place is measured in every exposure.`
}

function summary(data: SpectrumResponse) {
  const counts = data.status_counts ?? {}
  const n = data.n_exposures ?? 0
  const ok = counts.ok ?? 0
  const saturated = counts.saturated ?? 0
  const rest = n - ok - saturated
  let text = data.message ?? `${ok} of ${plural(n, 'exposure', 'exposures')} gave a clean measurement.`
  if (saturated) text += ` ${saturated} are saturated: the object is too bright there for SPHEREx to give a value.`
  if (rest > 0) text += ` ${rest} are flagged or incomplete.`
  if (data.failures?.length)
    text += ` ${plural(data.failures.length, 'exposure', 'exposures')} could not be downloaded and are missing.`
  return text
}

/** Every exposure, with or without a value, as the backend returned it. */
function downloadCsv(request: SpectrumRequest, data: SpectrumResponse) {
  const cols = ['date', 'mjd', 'epoch', 'detector', 'wavelength_um', 'bandwidth_um', 'status', 'flux_mjy', 'flux_err_mjy', 'obs_id'] as const
  const rows = (data.points ?? []).map((p) => cols.map((c) => p[c] ?? '').join(','))
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([`${cols.join(',')}\n${rows.join('\n')}\n`], { type: 'text/csv' }))
  a.download = `spherex_spectrum_${request.ra.toFixed(5)}_${request.dec.toFixed(5)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

function hoverText(p: Located) {
  if (p.status === 'ok' && p.flux_mjy !== null) return `${fmtValue(p.flux_mjy)} ± ${fmtValue(p.flux_err_mjy ?? 0)} mJy`
  if (p.status === 'saturated') return 'Saturated: no value'
  return `No value (${p.status.replace('_', ' ')})`
}

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'done'; data: SpectrumResponse }

interface Props {
  request: SpectrumRequest
  onClose: () => void
  /** How it is written: Expert as it always was, Beginner in plain words with the rest in one closed fold. */
  level?: UiLevel
}

export function SpectrumPanel({ request, onClose, level = 'expert' }: Props) {
  // A different request gets a fresh panel: remounting resets what is loaded and shown.
  const key = `${request.kind},${request.ra},${request.dec},${JSON.stringify(request.motion ?? null)}`
  return <Panel key={key} request={request} onClose={onClose} level={level} />
}

function Panel({ request, onClose, level }: Props & { level: UiLevel }) {
  // The target is measured at the centre of the view, whose exposures the backend
  // already holds. Any other spot is new to it (a few hundred downloads from NASA's
  // archive), so that is asked about first.
  const [confirmed, setConfirmed] = useState(request.kind === 'target')
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [hidden, setHidden] = useState<ReadonlySet<number>>(new Set())
  const [hover, setHover] = useState<Mark | null>(null)
  const section = useRef<HTMLElement>(null)

  // Bring the panel into view when it opens, and again when the chart arrives and makes
  // it taller.
  useEffect(() => {
    section.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [load.state])

  useEffect(() => {
    if (!confirmed) return
    const ctrl = new AbortController()
    // Started on the next tick: in development React mounts every component twice, and
    // this way the first, discarded mount never sends a request to the archive.
    const timer = window.setTimeout(() => {
      fetchSpectrum(request, ctrl.signal)
        .then((data) => setLoad({ state: 'done', data }))
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [confirmed, request])

  const data = load.state === 'done' ? load.data : null
  const chart = useMemo(() => (data ? layout(data, hidden) : null), [data, hidden])
  const place = `RA ${request.ra.toFixed(5)}°, Dec ${request.dec.toFixed(5)}°`

  function toggleVisit(epoch: number) {
    const next = new Set(hidden)
    if (next.has(epoch)) next.delete(epoch)
    else next.add(epoch)
    setHidden(next)
    setHover(null)
  }

  const head = (title: string) => (
    <div className="spectrum-head">
      <h2>{title}</h2>
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  )
  // Everything under the title, as Expert has always shown it. Beginner keeps it in its fold.
  const body = (
    <>
      <p className="spectrum-what">{data ? describeTarget(request, data) : place}</p>
      {data && circleStarsSentence(data.stars_in_circle) && (
        <p className="spectrum-what stars-in-circle">{circleStarsSentence(data.stars_in_circle)}</p>
      )}

      {!confirmed && (
        <>
          <p className="spectrum-what">
            This spot has to be fetched from NASA's archive in every SPHEREx exposure (a few hundred downloads), which
            takes a few minutes the first time. The target of the view is quick: use "Spectrum of the target".
          </p>
          <button type="button" onClick={() => setConfirmed(true)}>
            Measure this spot
          </button>
        </>
      )}
      {confirmed && load.state === 'loading' && (
        <p className="spectrum-what">
          {request.kind === 'target'
            ? 'Measuring the target in every exposure… a few seconds if it has been viewed before, a few minutes if not.'
            : 'Measuring this spot in every exposure… a new spot takes a few minutes.'}
        </p>
      )}
      {load.state === 'error' && <p className="status error">Could not get the spectrum: {load.message}</p>}

      {data && chart && (
        <>
          <p className="spectrum-what">{summary(data)}</p>
          {/* One button per visit: the legend, and the way to compare visits. */}
          <div className="spectrum-visits">
            {(data.epochs ?? []).map((e) => (
              <button type="button" key={e.epoch} aria-pressed={!hidden.has(e.epoch)} onClick={() => toggleVisit(e.epoch)}>
                <i style={{ background: visitColour(e.epoch) }} />
                Visit {e.epoch}: {e.date_start} to {e.date_end}
              </button>
            ))}
          </div>

          <SpectrumChart chart={chart} hover={hover} onHover={setHover} />

          <div className="spectrum-foot">
            <p>
              Each dot is one SPHEREx exposure. Every exposure sees the sky through a different colour of infrared
              light, so together they show how bright the object is at each wavelength: its spectrum. The brightness is
              added up inside a circle 15″ in radius, so anything else inside that circle is included.
            </p>
            {chart.offChart > 0 && (
              <p>
                {plural(chart.offChart, 'reading is', 'readings are')} beyond the edge of the chart and drawn as{' '}
                {chart.offChart === 1 ? 'an arrowhead' : 'arrowheads'}; hover for the value. A single reading far from
                its neighbours is usually a glitch in that exposure, not the object.
              </p>
            )}
            <button type="button" onClick={() => downloadCsv(request, data)}>
              Download these numbers (CSV)
            </button>
            <details>
              <summary>How this is measured</summary>
              <p>{[data.method?.flux, data.method?.error, data.method?.rejection].filter(Boolean).join(' ')}</p>
            </details>
          </div>
        </>
      )}
    </>
  )

  if (level === 'beginner') {
    return (
      <section className="panel spectrum plain-panel" aria-label="Spectrum" ref={section}>
        {head(confirmed ? SPECTRUM_TITLE : SPECTRUM_SPOT_TITLE)}
        <p className="plain-intro">{SPECTRUM_INTRO}</p>
        {!confirmed && (
          <>
            <p className="plain-intro">{SPECTRUM_SPOT_ASK}</p>
            <button type="button" onClick={() => setConfirmed(true)}>
              {SPECTRUM_SPOT_BUTTON}
            </button>
          </>
        )}
        {confirmed && load.state === 'loading' && <p className="plain-intro">{SPECTRUM_LOADING}</p>}
        {load.state === 'error' && (
          <p className="status error">
            {SPECTRUM_ERROR} {load.message}
          </p>
        )}
        {data && <PlainSpectrum data={data} />}
        {data && <ScienceFold>{body}</ScienceFold>}
      </section>
    )
  }
  return (
    <section className="panel spectrum" aria-label="Spectrum" ref={section}>
      {head(confirmed ? 'Spectrum: brightness at each wavelength' : 'Measure the spectrum of this spot?')}
      {body}
    </section>
  )
}

/**
 * The chart: one mark per exposure, set out by wavelength. Expert's words name the detectors,
 * the unit and the statuses; Beginner's (`plain`, with the chart's own message in `empty`) say
 * "infrared colour", "too bright" and "not measured" instead.
 */
function SpectrumChart({ chart, hover, onHover, plain = false, empty }: { chart: Chart; hover: Mark | null; onHover: (m: Mark | null) => void; plain?: boolean; empty?: string | null }) {
  function onMove(e: PointerEvent<SVGSVGElement>) {
    // The nearest mark to the pointer, so a small dot does not have to be hit exactly.
    const box = e.currentTarget.getBoundingClientRect()
    const k = W / box.width
    const mx = (e.clientX - box.left) * k
    const my = (e.clientY - box.top) * k
    let best: Mark | null = null
    let bestDistance = 24
    for (const m of chart.marks) {
      const d = Math.hypot(m.x - mx, m.y - my)
      if (d < bestDistance) {
        bestDistance = d
        best = m
      }
    }
    onHover(best)
  }
  const message = plain ? empty : chart.empty
  return (
    <div className="spectrum-plot">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={plain ? 'How bright it is in each infrared colour, one dot per photo' : 'Brightness against wavelength, one point per SPHEREx exposure'}
        onPointerMove={onMove}
        onPointerLeave={() => onHover(null)}
      >
        {/* An invisible sheet over the whole chart, so the pointer is followed between the marks too. */}
        <rect width={W} height={H} fill="transparent" />
        {chart.bands.map((b) => (
          <g key={b.label}>
            {b.shaded && <rect x={b.x} y={M.t} width={b.width} height={PH} fill="var(--chart-band)" />}
            {!plain && (
              <text x={b.x + b.width / 2} y={13} textAnchor="middle">
                {b.label}
              </text>
            )}
          </g>
        ))}
        {chart.ticks.map((t) => (
          <g key={t.text}>
            <line x1={M.l} x2={W - M.r} y1={t.y} y2={t.y} className={t.zero ? 'spectrum-axis' : 'spectrum-grid'} />
            <text x={M.l - 8} y={t.y + 4} textAnchor="end">
              {t.text}
            </text>
          </g>
        ))}
        {[1, 2, 3, 4, 5].map((w) => (
          <g key={w}>
            <line x1={xOf(w)} x2={xOf(w)} y1={M.t + PH} y2={M.t + PH + 5} className="spectrum-axis" />
            <text x={xOf(w)} y={M.t + PH + 19} textAnchor="middle">
              {w}
            </text>
          </g>
        ))}
        <text x={M.l + PW / 2} y={H - 6} textAnchor="middle">
          {plain ? SPECTRUM_AXIS_X : 'Wavelength (micrometres)'}
        </text>
        <text x={14} y={M.t + PH / 2} textAnchor="middle" transform={`rotate(-90 14 ${M.t + PH / 2})`}>
          {plain ? SPECTRUM_AXIS_Y : 'Brightness (mJy)'}
        </text>
        {chart.rails.map((r) => (
          <text key={r.name} x={M.l - 8} y={r.y + 4} textAnchor="end" className="spectrum-rail">
            {plain ? (SPECTRUM_RAILS[r.name] ?? r.name) : r.name}
          </text>
        ))}

        {/* Error bars first, then the marks on top of them. */}
        {chart.marks.map((m) =>
          m.shape === 'dot' ? (
            <line key={`e${m.point.obs_id}-${m.point.detector}`} x1={m.x} x2={m.x} y1={m.errTop} y2={m.errBottom} stroke={m.colour} strokeOpacity={0.5} />
          ) : null,
        )}
        {chart.marks.map((m) => {
          const key = `${m.point.obs_id}-${m.point.detector}`
          if (m.shape === 'tick')
            return <line key={key} x1={m.x} x2={m.x} y1={m.y - 4} y2={m.y + 4} stroke={m.colour} strokeWidth={1.5} />
          if (m.shape === 'dot') return <circle key={key} cx={m.x} cy={m.y} r={3.5} fill={m.colour} className="spectrum-mark" />
          const s = m.shape === 'above' ? -1 : 1 // an arrowhead pointing off the chart
          return (
            <path
              key={key}
              d={`M${m.x} ${m.y + 5 * s} L${m.x - 4.5} ${m.y - 3 * s} L${m.x + 4.5} ${m.y - 3 * s} Z`}
              fill={m.colour}
              className="spectrum-mark"
            />
          )
        })}
        {hover && <circle cx={hover.x} cy={hover.y} r={7} className="spectrum-ring" />}
        {message && (
          <text x={M.l + PW / 2} y={M.t + PH / 2} textAnchor="middle" className="spectrum-empty">
            {message}
          </text>
        )}
      </svg>
      {hover && (
        <div
          className="spectrum-tip"
          style={{
            left: `${(hover.x / W) * 100}%`,
            top: `${(hover.y / H) * 100}%`,
            transform: `translate(${hover.x > W * 0.6 ? 'calc(-100% - 14px)' : '14px'}, ${hover.y < 100 ? '12px' : 'calc(-100% - 8px)'})`,
          }}
        >
          <b>{plain ? spectrumTipValue(hover.point.status, hover.point.flux_mjy) : hoverText(hover.point)}</b>
          <div>
            {plain ? spectrumTip(hover.point.wavelength_um) : `${hover.point.wavelength_um.toFixed(3)} µm, detector ${hover.point.detector}`}
          </div>
          <div>
            <i style={{ background: visitColour(hover.point.epoch) }} />
            Visit {hover.point.epoch}, {hover.point.date.slice(0, 10)}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Beginner's part of the panel, for an answer that has arrived: what the tool states about this
 * object (plain.ts), the cautions, the visits as the chart's legend, and the chart in plain
 * words. Exported for the tests.
 */
export function PlainSpectrum({ data }: { data: SpectrumResponse }) {
  const [hidden, setHidden] = useState<ReadonlySet<number>>(new Set())
  const [hover, setHover] = useState<Mark | null>(null)
  const chart = useMemo(() => layout(data, hidden), [data, hidden])
  const epochs = data.epochs ?? []
  const allHidden = epochs.length > 0 && epochs.every((e) => hidden.has(e.epoch))
  function toggleVisit(epoch: number) {
    const next = new Set(hidden)
    if (next.has(epoch)) next.delete(epoch)
    else next.add(epoch)
    setHidden(next)
    setHover(null)
  }
  return (
    <>
      <PlainWords lines={spectrumResult(data)} cautions={measureCautions(data)} />
      <div className="spectrum-visits">
        {epochs.map((e) => (
          <button type="button" key={e.epoch} aria-pressed={!hidden.has(e.epoch)} onClick={() => toggleVisit(e.epoch)}>
            <i style={{ background: visitColour(e.epoch) }} />
            {spectrumVisit(e.epoch, e.date_start, e.date_end)}
          </button>
        ))}
      </div>
      <SpectrumChart chart={chart} hover={hover} onHover={setHover} plain empty={chart.empty ? spectrumEmpty(data, allHidden) : null} />
    </>
  )
}

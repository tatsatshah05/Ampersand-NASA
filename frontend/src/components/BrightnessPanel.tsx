// Issue #9: brightness of the target over time, for spotting variable stars.
// Every SPHEREx exposure sees a star at a different wavelength, so points are only
// comparable in time inside one wavelength bin. The chart is one small panel per
// detector on shared scales; in each, a thin line joins the points of one bin (never two
// bins), and dots are coloured by visit with the same colours as the spectrum panel.
// It shows only what GET /api/lightcurve returns; a point without a value is counted
// and explained, never drawn.
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import {
  AGREEMENT,
  CHANGE_THRESHOLD,
  MIN_BINS,
  countValues,
  defaultMeasure,
  fetchLightcurve,
  leftOut,
  relError,
  usableBins,
  relValue,
  summarise,
  type DetectorSummary,
  type LightcurveBin,
  type LightcurvePoint,
  type LightcurveResponse,
  type Measure,
} from '../lightcurve'
import type { SpectrumRequest } from '../spectrum'
import type { UiLevel } from '../address'
import { circleStarsSentence, measuredSentence } from '../detection'
import {
  BRIGHTNESS_ERROR,
  BRIGHTNESS_INTRO,
  BRIGHTNESS_LOADING,
  BRIGHTNESS_TITLE,
  bandCaption,
  brightnessAxis,
  brightnessResult,
  brightnessTip,
  measureCautions,
  plainMeasure,
} from '../plain'
import { PlainWords, ScienceFold } from './ScienceFold'
import './SpectrumPanel.css'
import './BrightnessPanel.css'

// Same visit colours as the spectrum panel (validated together on the panel background).
const VISIT_COLOURS = ['#3987e5', '#d95926', '#199e70']
const LATER_COLOUR = '#9a9a94'
const visitColour = (epoch: number) => VISIT_COLOURS[epoch - 1] ?? LATER_COLOUR

// One small chart, in SVG units.
const W = 360
const H = 210
const M = { l: 44, r: 10, t: 12, b: 28 }
const PW = W - M.l - M.r
const PH = H - M.t - M.b

const MEASURE_LABEL: Record<Measure, string> = {
  flux: 'Brightness relative to usual (1 = usual)',
  wing: "Relative brightness from the star's outer light (1 = usual)",
}

const REASON_TEXT: Record<string, string> = {
  saturated: 'saturated (too bright to measure)',
  flagged: 'a flagged pixel on the star',
  no_data: 'an empty pixel on the star',
  no_sky: 'not enough clean sky around it',
  off_image: 'too close to the edge of the detector',
  untrusted_detector: 'in detectors 1 to 4, where the outer-light measure does not repeat well enough',
  no_wing: 'no outer-light measurement',
  not_saturated: 'in a detector the star does not overload, where its outer light is too faint to mean anything',
  no_value: 'measured, but with nothing else in its wavelength bin to compare with',
  no_wavelength: 'no wavelength could be read',
}

const reasonText = (r: string) => REASON_TEXT[r] ?? r.replace(/^wing_/, 'outer light: ').replace(/_/g, ' ')
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
const pct = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(v !== 0 && Math.abs(v) < 0.1 ? 1 : 0)}%`
const mjdToDate = (mjd: number) => new Date((mjd - 40587) * 86400000)

interface Dot {
  x: number
  y: number
  point: LightcurvePoint
  bin: LightcurveBin
  value: number
  err: number | null
  shape: 'dot' | 'above' | 'below'
  /** Ends of the one-sigma error bar, in SVG units (dots only). */
  errTop?: number
  errBottom?: number
}

interface SmallChart {
  detector: number
  range: [number, number] | null
  dots: Dot[]
  lines: { bin: number; d: string }[]
}

interface Layout {
  charts: SmallChart[]
  yTicks: { y: number; text: string; one: boolean }[]
  xTicks: { x: number; text: string }[]
  offChart: number
  emptyDetectors: number[]
}

function niceStep(raw: number) {
  const p = Math.pow(10, Math.floor(Math.log10(raw)))
  const f = raw / p
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p
}

function layout(data: LightcurveResponse, m: Measure, hiddenDetectors: ReadonlySet<number>): Layout {
  const bins = usableBins(data, m)
  const valued = bins.flatMap((b) =>
    b.points.flatMap((p) => {
      const v = relValue(p, m)
      return v === null ? [] : [{ p, b, v, e: relError(p, b, m) }]   // an unknown error stays unknown
    }),
  )

  // Shared time axis, a little wider than the data.
  const mjds = bins.flatMap((b) => b.points.map((p) => p.mjd))
  const t0 = mjds.length ? Math.min(...mjds) : 0
  const t1 = mjds.length ? Math.max(...mjds) : 1
  const pad = Math.max((t1 - t0) * 0.04, 5)
  const x0 = t0 - pad
  const x1 = t1 + pad
  const xOf = (mjd: number) => M.l + ((mjd - x0) / (x1 - x0)) * PW

  // Shared brightness axis, always including 1 (usual). A few wild readings must not
  // flatten the rest: past the 1st and 99th percentiles the axis stops and those readings
  // are arrowheads at the edge (their values are in the hover text and the CSV).
  let lo = 0.8
  let hi = 1.2
  if (valued.length) {
    const v = valued.map((d) => d.v).sort((a, b) => a - b)
    const q = (f: number) => v[Math.floor(f * (v.length - 1))]
    lo = Math.min(1, v.length >= 20 ? q(0.01) : v[0])
    hi = Math.max(1, v.length >= 20 ? q(0.99) : v[v.length - 1])
    const span = Math.max(hi - lo, 0.1)
    lo -= 0.08 * span
    hi += 0.08 * span
  }
  const yOf = (v: number) => M.t + PH - ((v - lo) / (hi - lo)) * PH
  const step = niceStep((hi - lo) / 4)
  const decimals = Math.max(0, -Math.floor(Math.log10(step)))
  const yTicks: Layout['yTicks'] = []
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) {
    yTicks.push({ y: yOf(t), text: t.toFixed(decimals), one: Math.abs(t - 1) < step / 1e6 })
  }
  if (!yTicks.some((t) => t.one)) yTicks.push({ y: yOf(1), text: '1', one: true })

  // Month ticks: every third month, or every month when the data span is short.
  const xTicks: Layout['xTicks'] = []
  const every = x1 - x0 > 200 ? 3 : 1
  const d = mjdToDate(x0)
  const cur = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))
  while (cur.getUTCMonth() % every) cur.setUTCMonth(cur.getUTCMonth() + 1)
  for (; cur.getTime() / 86400000 + 40587 <= x1; cur.setUTCMonth(cur.getUTCMonth() + every)) {
    const mjd = cur.getTime() / 86400000 + 40587
    xTicks.push({ x: xOf(mjd), text: cur.toLocaleString('en', { month: 'short', year: '2-digit', timeZone: 'UTC' }) })
  }

  const ranges = data.detector_ranges_um ?? {}
  const detectors = [...new Set(bins.map((b) => b.detector))].sort((a, b) => a - b)
  const charts: SmallChart[] = []
  const emptyDetectors: number[] = []
  let offChart = 0
  for (const det of detectors) {
    const own = valued.filter((d) => d.b.detector === det)
    if (!own.length) {
      emptyDetectors.push(det)
      continue
    }
    if (hiddenDetectors.has(det)) continue
    const dots: Dot[] = own.map(({ p, b, v, e }) => {
      const x = xOf(p.mjd)
      if (v > hi || v < lo) {
        offChart += 1
        const above = v > hi
        return { x, y: above ? M.t + 5 : M.t + PH - 5, point: p, bin: b, value: v, err: e, shape: above ? 'above' : 'below' }
      }
      return {
        x,
        y: yOf(v),
        point: p,
        bin: b,
        value: v,
        err: e,
        shape: 'dot',
        errTop: e === null ? undefined : yOf(Math.min(v + e, hi)),
        errBottom: e === null ? undefined : yOf(Math.max(v - e, lo)),
      }
    })
    // One line per bin, through that bin's points in time order (the backend sorts them).
    const lines = bins
      .filter((b) => b.detector === det)
      .map((b) => {
        const pts = b.points
          .map((p) => relValue(p, m))
          .map((v, i) => (v === null ? null : [xOf(b.points[i].mjd), yOf(Math.min(Math.max(v, lo), hi))]))
          .filter((xy): xy is number[] => xy !== null)
        return { bin: b.bin, d: pts.length > 1 ? `M${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L')}` : '' }
      })
      .filter((l) => l.d)
    charts.push({ detector: det, range: ranges[String(det)] ?? null, dots, lines })
  }
  return { charts, yTicks, xTicks, offChart, emptyDetectors }
}

function describeTarget(request: SpectrumRequest, data: LightcurveResponse) {
  const place = `RA ${request.ra.toFixed(5)}°, Dec ${request.dec.toFixed(5)}°`
  // The backend says what it measured; the guesses below are for an older response without that.
  const measured = measuredSentence(data.measured)
  if (measured) return `${measured} (${place})`
  const t = data.target
  if (t?.origin === 'request') return `The target of this view (${place} in 2026), followed with its known motion.`
  if (t?.source_id) return `Gaia DR3 ${t.source_id}, the catalogued star at ${place}, followed with its Gaia motion.`
  return `The spot at ${place}. No catalogued star with a known motion is there, so the same place is measured in every exposure.`
}

function verdictSentence(summary: DetectorSummary[], m: Measure) {
  if (!summary.length) return 'There are not enough measurements in two different visits to compare.'
  const changed = summary.filter((s) => s.verdict === 'brighter' || s.verdict === 'fainter')
  const what = m === 'flux' ? 'brightness' : 'outer light'
  if (!changed.length) {
    return `SPHEREx does not show a clear change in ${what} between visits: no detector with at least ${MIN_BINS} wavelength bins changed by ${CHANGE_THRESHOLD * 100}% or more with most of its bins agreeing.`
  }
  // Each detector has its own first and last visit with values, so each is named with its own.
  const parts = changed.map((s) => `${s.verdict} in D${s.detector} (${pct(s.medianChange)}, visit ${s.firstEpoch} to visit ${s.lastEpoch})`)
  return `SPHEREx shows the ${what} changing between visits: ${parts.join(', ')}.`
}

function downloadCsv(request: SpectrumRequest, data: LightcurveResponse) {
  const cols = ['date', 'mjd', 'epoch', 'detector', 'bin', 'bin_from_um', 'bin_to_um', 'wavelength_um', 'status', 'flux_mjy', 'flux_err_mjy', 'relative_flux', 'wing_status', 'wing_mjy', 'wing_err_mjy', 'relative_wing', 'obs_id'] as const
  const rows = (data.bins ?? []).flatMap((b) =>
    b.points.map((p) => {
      const row: Partial<Record<(typeof cols)[number], unknown>> = {
        ...p,
        bin: b.bin,
        bin_from_um: b.wavelength_um[0],
        bin_to_um: b.wavelength_um[1],
      }
      return cols.map((c) => row[c] ?? '').join(',')
    }),
  )
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([`${cols.join(',')}\n${rows.join('\n')}\n`], { type: 'text/csv' }))
  a.download = `spherex_brightness_${request.ra.toFixed(5)}_${request.dec.toFixed(5)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'done'; data: LightcurveResponse }

interface Props {
  request: SpectrumRequest
  onClose: () => void
  /** How it is written: Expert as it always was, Beginner in plain words with the rest in one closed fold. */
  level?: UiLevel
}

export function BrightnessPanel({ request, onClose, level = 'expert' }: Props) {
  // A different request gets a fresh panel: remounting resets what is loaded and shown.
  const key = `${request.ra},${request.dec},${JSON.stringify(request.motion ?? null)}`
  return <Panel key={key} request={request} onClose={onClose} level={level} />
}

function Panel({ request, onClose, level }: Props & { level: UiLevel }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [measureChoice, setMeasureChoice] = useState<Measure | null>(null)
  const [hidden, setHidden] = useState<ReadonlySet<number>>(new Set())
  const [hover, setHover] = useState<{ detector: number; dot: Dot } | null>(null)
  const section = useRef<HTMLElement>(null)

  useEffect(() => {
    section.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [load.state])

  useEffect(() => {
    const ctrl = new AbortController()
    // Started on the next tick, so the discarded first mount of React's development mode
    // never sends a request.
    const timer = window.setTimeout(() => {
      fetchLightcurve(request, ctrl.signal)
        .then((data) => setLoad({ state: 'done', data }))
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setLoad({ state: 'error', message: e instanceof Error ? e.message : String(e) })
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [request])

  const data = load.state === 'done' ? load.data : null
  const measure: Measure = measureChoice ?? (data ? defaultMeasure(data) : 'flux')
  const chart = useMemo(() => (data ? layout(data, measure, hidden) : null), [data, measure, hidden])
  const summary = useMemo(() => (data ? summarise(data, measure) : []), [data, measure])
  const other: Measure = measure === 'flux' ? 'wing' : 'flux'
  const otherChanged = useMemo(
    () => (data ? summarise(data, other).filter((s) => s.verdict === 'brighter' || s.verdict === 'fainter') : []),
    [data, other],
  )
  const missing = useMemo(() => (data ? leftOut(data, measure) : null), [data, measure])
  const counts = data ? { flux: countValues(data, 'flux'), wing: countValues(data, 'wing') } : null

  function toggleDetector(det: number) {
    const next = new Set(hidden)
    if (next.has(det)) next.delete(det)
    else next.add(det)
    setHidden(next)
    setHover(null)
  }

  const visits = data
    ? [...new Map((data.bins ?? []).flatMap((b) => b.points.map((p) => [p.epoch, p.date] as const))).keys()].sort((a, b) => a - b)
    : []
  const allDetectors = data ? [...new Set((data.bins ?? []).map((b) => b.detector))].sort((a, b) => a - b) : []

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
      <p className="spectrum-what">{data ? describeTarget(request, data) : `RA ${request.ra.toFixed(5)}°, Dec ${request.dec.toFixed(5)}°`}</p>
      {data && circleStarsSentence(data.stars_in_circle) && (
        <p className="spectrum-what stars-in-circle">{circleStarsSentence(data.stars_in_circle)}</p>
      )}
      {load.state === 'loading' && (
        <p className="spectrum-what">
          Measuring the target in every exposure of all six detectors… a few seconds if it has been viewed before,
          several minutes if not.
        </p>
      )}
      {load.state === 'error' && <p className="status error">Could not get the brightness over time: {load.message}</p>}
      {data?.message && <p className="spectrum-what">{data.message}</p>}

      {data && chart && counts && missing && (
        <>
          <p className="brightness-verdict">{verdictSentence(summary, measure)}</p>
          {counts.flux > 0 && counts.wing > 0 && otherChanged.length > 0 && (
            <p className="spectrum-what">
              {other === 'wing' ? "The star's outer light" : 'The measured brightness'} also shows a change:{' '}
              {otherChanged.map((s) => `${s.verdict} in D${s.detector} (${pct(s.medianChange)})`).join(', ')}. Switch
              below to see it.
            </p>
          )}

          {counts.flux > 0 && counts.wing > 0 && (
            <div className="brightness-measure" role="radiogroup" aria-label="What to plot">
              {(['flux', 'wing'] as const).map((m) => (
                <button type="button" key={m} role="radio" aria-checked={measure === m} onClick={() => setMeasureChoice(m)}>
                  {m === 'flux' ? `Measured brightness (${counts.flux} points)` : `Outer light (${counts.wing} points)`}
                </button>
              ))}
            </div>
          )}
          {measure === 'wing' && (
            <p className="spectrum-what">
              This star is too bright for SPHEREx to measure directly{counts.flux === 0 ? ' in any exposure' : ''}, so
              this shows the light in a ring around it instead. That is a relative brightness, not a flux: it only
              says whether the star got brighter or fainter, compared with itself in the same wavelength bin.
            </p>
          )}

          <div className="spectrum-visits">
            {visits.map((ep) => (
              <span key={ep} className="brightness-visit">
                <i style={{ background: visitColour(ep) }} />
                Visit {ep}
              </span>
            ))}
            {allDetectors.map((det) =>
              chart.emptyDetectors.includes(det) ? null : (
                <button type="button" key={det} aria-pressed={!hidden.has(det)} onClick={() => toggleDetector(det)}>
                  D{det}
                </button>
              ),
            )}
          </div>

          <p className="brightness-axis">{MEASURE_LABEL[measure]}</p>
          <SmallCharts chart={chart} measure={measure} hover={hover} onHover={setHover} />

          {summary.length > 0 && (
            <table className="brightness-table">
              <caption>
                Change from first to last visit, per detector. Each wavelength bin is compared with itself; the table
                gives the middle (median) bin.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Detector</th>
                  <th scope="col">Visits</th>
                  <th scope="col">Bins compared</th>
                  <th scope="col">Median change</th>
                  <th scope="col">Brighter / fainter bins</th>
                  <th scope="col">Reading</th>
                </tr>
              </thead>
              <tbody>
                {summary.map((s) => (
                  <tr key={s.detector}>
                    <th scope="row">D{s.detector}</th>
                    <td>
                      {s.firstEpoch} → {s.lastEpoch}
                    </td>
                    <td>{s.nBins}</td>
                    <td>{pct(s.medianChange)}</td>
                    <td>
                      {s.nBrighter} / {s.nFainter}
                    </td>
                    <td>{s.verdict}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="spectrum-foot">
            <p>
              Each dot is one SPHEREx exposure. Every exposure sees the star at a different wavelength, so the dots are
              grouped into narrow wavelength bins and each bin is scaled to its own usual level (1 on the axis). A thin
              line joins the dots of one bin; hover a dot to see its bin. "Brighter" or "fainter" is only called when the
              median change is at least {CHANGE_THRESHOLD * 100}%, at least {AGREEMENT * 100}% of the bins agree, and at
              least {MIN_BINS} bins could be compared.
            </p>
            <p>
              {countValues(data, measure)} of {plural(data.n_exposures ?? 0, 'exposure', 'exposures')} are plotted
              {missing.total > 0 && (
                <>
                  ; {missing.total} {missing.total === 1 ? 'was' : 'were'} left out:{' '}
                  {Object.entries(missing.reasons)
                    .sort((a, b) => b[1] - a[1])
                    .map(([r, n]) => `${n} ${reasonText(r)}`)
                    .join(', ')}
                </>
              )}
              .
              {chart.emptyDetectors.length > 0 &&
                ` No usable values in ${chart.emptyDetectors.map((d) => `D${d}`).join(', ')}.`}
              {chart.offChart > 0 &&
                ` ${plural(chart.offChart, 'reading is', 'readings are')} beyond the edge of the charts, drawn as arrowheads; hover for the value.`}
              {data.failures?.length
                ? ` ${plural(data.failures.length, 'exposure', 'exposures')} could not be downloaded and are missing.`
                : ''}
            </p>
            <button type="button" onClick={() => downloadCsv(request, data)}>
              Download these numbers (CSV)
            </button>
            <details>
              <summary>How this is measured</summary>
              <p>
                {[data.method?.flux, data.method?.error, data.method?.rejection, measure === 'wing' ? data.method?.wing : null]
                  .filter(Boolean)
                  .join(' ')}
              </p>
            </details>
          </div>
        </>
      )}
    </>
  )

  if (level === 'beginner') {
    return (
      <section className="panel brightness plain-panel" aria-label="Brightness over time" ref={section}>
        {head(BRIGHTNESS_TITLE)}
        <p className="plain-intro">{BRIGHTNESS_INTRO}</p>
        {load.state === 'loading' && <p className="plain-intro">{BRIGHTNESS_LOADING}</p>}
        {load.state === 'error' && (
          <p className="status error">
            {BRIGHTNESS_ERROR} {load.message}
          </p>
        )}
        {data && <PlainBrightness data={data} />}
        {data && <ScienceFold>{body}</ScienceFold>}
      </section>
    )
  }
  return (
    <section className="panel brightness" aria-label="Brightness over time" ref={section}>
      {head('Brightness over time')}
      {body}
    </section>
  )
}

type Hover = { detector: number; dot: Dot } | null

/**
 * The small charts, one per detector, on shared scales. Expert's captions and hover text name
 * the detector and the wavelength bin; Beginner's (plain) name the band of infrared colours and
 * say the value as "times its usual brightness".
 */
function SmallCharts({ chart, measure, hover, onHover, plain = false }: { chart: Layout; measure: Measure; hover: Hover; onHover: (h: Hover) => void; plain?: boolean }) {
  function onMove(det: number, dots: Dot[], e: PointerEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    const k = W / box.width
    const mx = (e.clientX - box.left) * k
    const my = (e.clientY - box.top) * k
    let best: Dot | null = null
    let bestDistance = 20
    for (const d of dots) {
      const dist = Math.hypot(d.x - mx, d.y - my)
      if (dist < bestDistance) {
        bestDistance = dist
        best = d
      }
    }
    onHover(best ? { detector: det, dot: best } : null)
  }
  const axis = plain ? brightnessAxis(measure) : MEASURE_LABEL[measure]
  return (
    <div className="brightness-grid">
      {chart.charts.map((c) => (
        <figure key={c.detector} className="brightness-chart">
          <figcaption>
            {plain ? (
              bandCaption(c.detector)
            ) : (
              <>
                <b>D{c.detector}</b>
                {c.range && ` · ${c.range[0].toFixed(2)}–${c.range[1].toFixed(2)} µm`}
              </>
            )}
          </figcaption>
          <div className="spectrum-plot">
            <svg
              viewBox={`0 0 ${W} ${H}`}
              role="img"
              aria-label={plain ? `${bandCaption(c.detector)}: ${axis}, by date` : `Detector ${c.detector}: ${MEASURE_LABEL[measure]} against date`}
              onPointerMove={(e) => onMove(c.detector, c.dots, e)}
              onPointerLeave={() => onHover(null)}
            >
              <rect width={W} height={H} fill="transparent" />
              {chart.yTicks.map((t) => (
                <g key={t.text}>
                  <line x1={M.l} x2={W - M.r} y1={t.y} y2={t.y} className={t.one ? 'spectrum-axis' : 'spectrum-grid'} />
                  <text x={M.l - 6} y={t.y + 4} textAnchor="end">
                    {t.text}
                  </text>
                </g>
              ))}
              {chart.xTicks.map((t) => (
                <g key={t.text}>
                  <line x1={t.x} x2={t.x} y1={M.t + PH} y2={M.t + PH + 4} className="spectrum-axis" />
                  <text x={t.x} y={H - 8} textAnchor={t.x > W - 16 ? 'end' : 'middle'}>
                    {t.text}
                  </text>
                </g>
              ))}
              {c.lines.map((l) => (
                <path
                  key={l.bin}
                  d={l.d}
                  fill="none"
                  className={hover?.detector === c.detector && hover.dot.bin.bin === l.bin ? 'brightness-line on' : 'brightness-line'}
                />
              ))}
              {/* Error bars first, then the dots on top of them. */}
              {c.dots.map((d) =>
                d.shape === 'dot' && d.errTop !== undefined ? (
                  <line
                    key={`e${d.point.obs_id}-${d.bin.bin}`}
                    x1={d.x}
                    x2={d.x}
                    y1={d.errTop}
                    y2={d.errBottom}
                    stroke={visitColour(d.point.epoch)}
                    strokeOpacity={0.45}
                  />
                ) : null,
              )}
              {c.dots.map((d) => {
                const k = `${d.point.obs_id}-${d.bin.bin}`
                const colour = visitColour(d.point.epoch)
                if (d.shape === 'dot') return <circle key={k} cx={d.x} cy={d.y} r={3} fill={colour} className="spectrum-mark" />
                const s = d.shape === 'above' ? -1 : 1
                return (
                  <path
                    key={k}
                    d={`M${d.x} ${d.y + 5 * s} L${d.x - 4} ${d.y - 3 * s} L${d.x + 4} ${d.y - 3 * s} Z`}
                    fill={colour}
                    className="spectrum-mark"
                  />
                )
              })}
              {hover?.detector === c.detector && <circle cx={hover.dot.x} cy={hover.dot.y} r={6} className="spectrum-ring" />}
            </svg>
            {hover?.detector === c.detector && (
              <div
                className="spectrum-tip"
                style={{
                  left: `${(hover.dot.x / W) * 100}%`,
                  top: `${(hover.dot.y / H) * 100}%`,
                  transform: `translate(${hover.dot.x > W * 0.55 ? 'calc(-100% - 12px)' : '12px'}, ${hover.dot.y < 70 ? '10px' : 'calc(-100% - 8px)'})`,
                }}
              >
                {plain ? (
                  <b>{brightnessTip(hover.dot.value, hover.dot.err)}</b>
                ) : (
                  <>
                    <b>
                      {hover.dot.value.toFixed(3)}
                      {hover.dot.err !== null && ` ± ${hover.dot.err.toFixed(3)}`} × usual
                    </b>
                    <div>
                      Bin {hover.dot.bin.wavelength_um[0].toFixed(3)}–{hover.dot.bin.wavelength_um[1].toFixed(3)} µm
                    </div>
                  </>
                )}
                <div>
                  <i style={{ background: visitColour(hover.dot.point.epoch) }} />
                  Visit {hover.dot.point.epoch}, {hover.dot.point.date.slice(0, 10)}
                </div>
              </div>
            )}
          </div>
        </figure>
      ))}
    </div>
  )
}

/**
 * Beginner's part of the panel, for an answer that has arrived: the sentences about this object
 * (plain.ts, from the tool's own same-colour comparison), the cautions, and the chart of the
 * measure those sentences are about, in plain words. Exported for the tests.
 */
export function PlainBrightness({ data }: { data: LightcurveResponse }) {
  const [hover, setHover] = useState<Hover>(null)
  const measure = plainMeasure(data)
  const chart = useMemo(() => layout(data, measure, new Set()), [data, measure])
  const visits = [...new Set((data.bins ?? []).flatMap((b) => b.points.map((p) => p.epoch)))].sort((a, b) => a - b)
  return (
    <>
      <PlainWords lines={brightnessResult(data)} cautions={measureCautions(data)} />
      {chart.charts.length > 0 && (
        <>
          <div className="spectrum-visits">
            {visits.map((ep) => (
              <span key={ep} className="brightness-visit">
                <i style={{ background: visitColour(ep) }} />
                Visit {ep}
              </span>
            ))}
          </div>
          <p className="brightness-axis">{brightnessAxis(measure)}</p>
          <SmallCharts chart={chart} measure={measure} hover={hover} onHover={setHover} plain />
        </>
      )}
    </>
  )
}

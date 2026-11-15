// Issue #12, part 3: Aladin Lite v3 context view centred on the search position, with
// WISE / 2MASS / optical sky images, Gaia DR3 stars, and a box showing the SPHEREx field.
// Aladin's terms ask that its logo and link stay visible at the bottom right of the view.
import { useEffect, useRef, useState } from 'react'
import type { Aladin, Layer } from 'aladin-lite'
import type { UiLevel } from '../address'
import { CONTEXT_CREDIT, CONTEXT_FAILED, CONTEXT_INTRO, CONTEXT_NO_IMAGE, CONTEXT_PICK, CONTEXT_TITLE, SURVEY_WORDS, contextResult } from '../plain'
import { PlainWords, ScienceFold } from './ScienceFold'

// Each survey is a full HiPS address on a mirror, tried in order, so Aladin never has to look a
// survey id up at the Strasbourg servers (which were down on 14 November). Each address answered
// <address>/properties and served a tile with open CORS on 14 November.
const SURVEYS = [
  {
    id: 'wise',
    label: 'WISE infrared (closest to SPHEREx)',
    mirrors: [
      'https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1',
      'https://skies.esac.esa.int/AllWISEColor',
    ],
  },
  {
    id: '2mass',
    label: '2MASS near-infrared',
    mirrors: ['https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color', 'https://skies.esac.esa.int/2MASSColor'],
  },
  {
    id: 'dss',
    label: 'DSS optical',
    mirrors: ['https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color', 'https://skies.esac.esa.int/DSSColor'],
  },
] as const

/** The first mirror that answers, or null. Asks all at once and takes the first good answer. */
async function firstMirror(mirrors: readonly string[]): Promise<string | null> {
  const ask = async (base: string) => {
    const r = await fetch(`${base}/properties`, {
      signal: AbortSignal.timeout(8000),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return base
  }
  try {
    return await Promise.any(mirrors.map(ask))
  } catch {
    return null
  }
}

const NO_IMAGE = 'The sky image could not be loaded right now.'

// The view is this many SPHEREx fields wide, so the orange box sits in its surroundings.
const VIEW_FIELDS = 3
// A survey sets its own starting zoom when it finishes loading, some time after it is asked for,
// so the width is set again at these moments (milliseconds) after every change.
const WIDTH_AGAIN_MS = [0, 700, 2000, 4500]

/** Set the view's width now and again while the survey settles. Returns how to cancel. */
function holdWidth(aladin: Aladin, fov: number): () => void {
  const timers = WIDTH_AGAIN_MS.map((ms) => window.setTimeout(() => aladin.setFoV(fov * VIEW_FIELDS), ms))
  return () => timers.forEach((t) => window.clearTimeout(t))
}

const GAIA_DR3 = 'I/355/gaiadr3' // Gaia DR3 main catalogue on VizieR

interface Props {
  ra: number
  dec: number
  fov: number // SPHEREx field of view in degrees
  /** How it is written: Expert as it always was, Beginner in plain words with the rest in one closed fold. */
  level?: UiLevel
  /** When given, a Close button beside the title (as the other tool panels have). */
  onClose?: () => void
}

type AladinModule = typeof import('aladin-lite').default

export function ContextView({ ra, dec, fov, level = 'expert', onClose }: Props) {
  const plain = level === 'beginner'
  const divRef = useRef<HTMLDivElement>(null)
  const [viewer, setViewer] = useState<{
    A: AladinModule
    aladin: Aladin
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [survey, setSurvey] = useState<string>(SURVEYS[0].id)
  const [imageFailed, setImageFailed] = useState(false)
  // Beginner starts with the bare sky picture; the catalogue's marks are one switch away in the fold.
  const [showGaia, setShowGaia] = useState(!plain)
  // Which position the Gaia stars were last loaded for, and whether that worked.
  const [gaiaLoad, setGaiaLoad] = useState<{ key: string; ok: boolean } | null>(null)
  const posKey = `${ra},${dec},${fov}`
  const gaiaNote =
    gaiaLoad?.key !== posKey
      ? 'Loading Gaia stars…'
      : gaiaLoad.ok
        ? ''
        : 'Gaia stars could not be loaded from VizieR right now.'
  const gaiaRef = useRef<Layer | null>(null)
  const boxRef = useRef<Layer | null>(null)
  const fovRef = useRef(fov) // the newest field size, for the survey switch
  const start = useRef({ ra, dec, fov }) // only the first position; later changes go through gotoRaDec

  // Create the viewer once. The library is large, so it is loaded only when this panel mounts.
  useEffect(() => {
    let cancelled = false
    const div = divRef.current
    let made: Aladin | null = null
    // Aladin reports a survey it cannot load as an unhandled rejection; turn that into a sentence.
    const onRejection = (e: PromiseRejectionEvent) => {
      const msg = String((e.reason as Error | undefined)?.message ?? e.reason)
      // Aladin also pings a usage logger at Strasbourg on start; when that host is down its fetch
      // rejects with no handler. Nothing is lost by it, so it is not left as an uncaught error.
      if (/Failed to fetch/i.test(msg)) e.preventDefault()
      if (!/HiPS|CDS ID|survey/i.test(msg)) return
      e.preventDefault()
      if (!cancelled) setImageFailed(true)
    }
    window.addEventListener('unhandledrejection', onRejection)
    Promise.all([import('aladin-lite'), firstMirror(SURVEYS[0].mirrors)])
      .then(async ([{ default: A }, mirror]) => {
        await A.init
        if (cancelled || !div) return
        const s = start.current
        // Without a working mirror the first address is still given, so Aladin does not fall back to
        // its default survey id (a lookup at Strasbourg); the image then simply does not appear.
        if (!mirror) setImageFailed(true)
        const aladin = A.aladin(div, {
          target: `${s.ra} ${s.dec}`,
          fov: s.fov * VIEW_FIELDS,
          survey: mirror ?? SURVEYS[0].mirrors[0],
          cooFrame: 'ICRSd',
          showReticle: true,
          showZoomControl: true,
          showLayersControl: false,
          showCooGridControl: false,
          showSimbadPointerControl: false,
          showFullscreenControl: false,
          showShareControl: false,
          showSettingsControl: false,
          showFrame: false,
          showProjectionControl: false,
          showCooLocation: false,
          showContextMenu: false,
        })
        made = aladin
        setViewer({ A, aladin })
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(`The sky atlas could not start (${String(e)}).`)
      })
    return () => {
      cancelled = true
      window.removeEventListener('unhandledrejection', onRejection)
      // Aladin Lite has no destroy call. Take its layers off and empty the div, which is as far as
      // the library allows. React StrictMode mounts twice in development.
      try {
        const a = made as (Aladin & { removeLayers?: () => void }) | null
        a?.removeLayers?.()
      } catch {
        // already gone
      }
      made = null
      if (div) div.innerHTML = ''
    }
  }, [])

  // Follow the search position: re-centre, redraw the SPHEREx field box, reload Gaia stars.
  useEffect(() => {
    if (!viewer) return
    const { A, aladin } = viewer
    let stale = false
    fovRef.current = fov
    aladin.gotoRaDec(ra, dec)
    const letGo = holdWidth(aladin, fov)

    if (boxRef.current) aladin.removeLayer(boxRef.current)
    const half = fov / 2
    const dra = half / Math.max(Math.cos((dec * Math.PI) / 180), 0.01)
    const box = A.graphicOverlay({
      name: 'SPHEREx field',
      color: '#ff8a3d',
      lineWidth: 2,
    })
    aladin.addOverlay(box)
    box.add(
      A.polygon([
        [ra - dra, dec - half],
        [ra + dra, dec - half],
        [ra + dra, dec + half],
        [ra - dra, dec + half],
      ]),
    )
    boxRef.current = box

    if (gaiaRef.current) {
      aladin.removeLayer(gaiaRef.current)
      gaiaRef.current = null
    }
    const key = `${ra},${dec},${fov}`
    // The view is a square VIEW_FIELDS fields wide, so its corners are 0.71 of that from the centre.
    try {
      A.catalogFromVizieR(
        GAIA_DR3,
        `${ra} ${dec}`,
        fov * VIEW_FIELDS * 0.72,
        {
          name: 'Gaia DR3',
          color: '#38d6e8',
          sourceSize: 10,
          limit: 2000,
          onClick: 'showTable',
        },
        (cat) => {
          if (stale) return
          aladin.addCatalog(cat)
          gaiaRef.current = cat
          setGaiaLoad({ key, ok: true })
        },
        () => {
          if (!stale) setGaiaLoad({ key, ok: false })
        },
      )
    } catch {
      void Promise.resolve().then(() => {
        if (!stale) setGaiaLoad({ key, ok: false })
      })
    }
    return () => {
      stale = true
      letGo()
    }
  }, [viewer, ra, dec, fov])

  useEffect(() => {
    if (!viewer) return
    let stale = false
    let letGo = () => {}
    const chosen = SURVEYS.find((s) => s.id === survey) ?? SURVEYS[0]
    void firstMirror(chosen.mirrors).then((mirror) => {
      if (stale) return
      setImageFailed(!mirror)
      if (!mirror) return
      viewer.aladin.setBaseImageLayer(mirror)
      letGo = holdWidth(viewer.aladin, fovRef.current)
    })
    return () => {
      stale = true
      letGo()
    }
  }, [viewer, survey])

  useEffect(() => {
    const cat = gaiaRef.current
    if (cat) {
      if (showGaia) cat.show()
      else cat.hide()
    }
  }, [showGaia, gaiaNote])

  const title = plain ? CONTEXT_TITLE : 'Sky context'
  const surveyPicker = (
    <label>
      {plain ? CONTEXT_PICK : 'Sky image'}{' '}
      <select value={survey} onChange={(e) => setSurvey(e.target.value)}>
        {SURVEYS.map((s) => (
          <option key={s.id} value={s.id}>
            {plain ? (SURVEY_WORDS[s.id]?.label ?? s.label) : s.label}
          </option>
        ))}
      </select>
    </label>
  )
  const gaiaSwitch = (
    <label>
      <input type="checkbox" checked={showGaia} onChange={(e) => setShowGaia(e.target.checked)} />{' '}
      <span className="key gaia">Gaia DR3 stars</span>
    </label>
  )
  const credit = <p className="hint">Sky atlas: Aladin Lite (CDS, Strasbourg). Star catalogue: ESA Gaia DR3 via VizieR.</p>

  // The sky atlas keeps its place among the section's children at both levels, so a change of
  // level never takes its element away from it.
  return (
    <section className={plain ? 'panel context plain-panel' : 'panel context'} aria-label="Sky context">
      {onClose ? (
        <div className="spectrum-head">
          <h2>{title}</h2>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      ) : (
        <h2>{title}</h2>
      )}
      {plain ? (
        <>
          <p className="plain-intro">{CONTEXT_INTRO}</p>
          <PlainWords lines={contextResult(survey, fov)} />
        </>
      ) : (
        <p className="hint">
          Other surveys around the same spot. The <span className="key measured">orange box</span> is the SPHEREx field
          shown on the left.
        </p>
      )}
      {error ? <p className="status error">{plain ? CONTEXT_FAILED : error}</p> : <div ref={divRef} className="aladin" />}
      {plain ? (
        <>
          <div className="plain-pick">{surveyPicker}</div>
          {imageFailed && <p className="hint">{CONTEXT_NO_IMAGE}</p>}
          <p className="hint">{CONTEXT_CREDIT}</p>
          <ScienceFold>
            {error && <p className="status error">{error}</p>}
            <div className="context-controls">{gaiaSwitch}</div>
            {gaiaNote && <p className="hint">{gaiaNote}</p>}
            {credit}
          </ScienceFold>
        </>
      ) : (
        <>
          <div className="context-controls">
            {surveyPicker}
            {gaiaSwitch}
          </div>
          {imageFailed && <p className="hint">{NO_IMAGE}</p>}
          {gaiaNote && <p className="hint">{gaiaNote}</p>}
          {credit}
        </>
      )}
    </section>
  )
}

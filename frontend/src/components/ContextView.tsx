// Issue #12, part 3: Aladin Lite v3 context view centred on the search position, with
// WISE / 2MASS / optical sky images, Gaia DR3 stars, and a box showing the SPHEREx field.
// Aladin's terms ask that its logo and link stay visible at the bottom right of the view.
import { useEffect, useRef, useState } from 'react'
import type { Aladin, Layer } from 'aladin-lite'

const SURVEYS = [
  { id: 'CDS/P/allWISE/color', label: 'WISE infrared (closest to SPHEREx)' },
  { id: 'CDS/P/2MASS/color', label: '2MASS near-infrared' },
  { id: 'CDS/P/DSS2/color', label: 'DSS optical' },
] as const

const GAIA_DR3 = 'I/355/gaiadr3' // Gaia DR3 main catalogue on VizieR

interface Props {
  ra: number
  dec: number
  fov: number // SPHEREx field of view in degrees
}

type AladinModule = typeof import('aladin-lite').default

export function ContextView({ ra, dec, fov }: Props) {
  const divRef = useRef<HTMLDivElement>(null)
  const [viewer, setViewer] = useState<{ A: AladinModule; aladin: Aladin } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [survey, setSurvey] = useState<string>(SURVEYS[0].id)
  const [showGaia, setShowGaia] = useState(true)
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
  const start = useRef({ ra, dec, fov }) // only the first position; later changes go through gotoRaDec

  // Create the viewer once. The library is large, so it is loaded only when this panel mounts.
  useEffect(() => {
    let cancelled = false
    const div = divRef.current
    import('aladin-lite')
      .then(async ({ default: A }) => {
        await A.init
        if (cancelled || !div) return
        const s = start.current
        const aladin = A.aladin(div, {
          target: `${s.ra} ${s.dec}`,
          fov: s.fov * 5,
          survey: SURVEYS[0].id,
          cooFrame: 'ICRSd',
          showReticle: true,
          showLayersControl: true,
          showCooGridControl: true,
          showSimbadPointerControl: true,
          showShareControl: false,
          showContextMenu: true,
        })
        setViewer({ A, aladin })
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(`The sky atlas could not start (${String(e)}).`)
      })
    return () => {
      cancelled = true
      if (div) div.innerHTML = '' // React StrictMode mounts twice in development
    }
  }, [])

  // Follow the search position: re-centre, redraw the SPHEREx field box, reload Gaia stars.
  useEffect(() => {
    if (!viewer) return
    const { A, aladin } = viewer
    let stale = false
    aladin.gotoRaDec(ra, dec)
    aladin.setFoV(fov * 5)

    if (boxRef.current) aladin.removeLayer(boxRef.current)
    const half = fov / 2
    const dra = half / Math.max(Math.cos((dec * Math.PI) / 180), 0.01)
    const box = A.graphicOverlay({ name: 'SPHEREx field', color: '#ff8a3d', lineWidth: 2 })
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
    A.catalogFromVizieR(
      GAIA_DR3,
      `${ra} ${dec}`,
      fov * 2,
      { name: 'Gaia DR3', color: '#38d6e8', sourceSize: 10, limit: 2000, onClick: 'showTable' },
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
    return () => {
      stale = true
    }
  }, [viewer, ra, dec, fov])

  useEffect(() => {
    viewer?.aladin.setBaseImageLayer(survey)
  }, [viewer, survey])

  useEffect(() => {
    const cat = gaiaRef.current
    if (cat) {
      if (showGaia) cat.show()
      else cat.hide()
    }
  }, [showGaia, gaiaNote])

  return (
    <section className="panel context" aria-label="Sky context">
      <h2>Sky context</h2>
      <p className="hint">
        Other surveys around the same spot. The <span className="key measured">orange box</span> is the SPHEREx field
        shown on the left.
      </p>
      {error ? (
        <p className="status error">{error}</p>
      ) : (
        <div ref={divRef} className="aladin" />
      )}
      <div className="context-controls">
        <label>
          Sky image{' '}
          <select value={survey} onChange={(e) => setSurvey(e.target.value)}>
            {SURVEYS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={showGaia} onChange={(e) => setShowGaia(e.target.checked)} />{' '}
          <span className="key gaia">Gaia DR3 stars</span>
        </label>
      </div>
      {gaiaNote && <p className="hint">{gaiaNote}</p>}
      <p className="hint">Sky atlas: Aladin Lite (CDS, Strasbourg). Star catalogue: ESA Gaia DR3 via VizieR.</p>
    </section>
  )
}

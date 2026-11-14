// Practice mode: real SPHEREx frames with ONE made-up moving object added by the
// backend (GET /api/training, backend/training.py). Everything here is a simulation and
// the screen says so; nothing from this module is ever shown in the ordinary view.
import { useEffect, useState } from 'react'
import { addressOf, DEFAULT_SELECTION, FOV_MAX, type Level, type Selection } from './address'
import { skyOffsetArcsec } from './api'

/** Where the made-up object is in one visit. x and y are picture pixels from the top-left. */
export interface PlantedSpot {
  epoch: number
  ra: number
  dec: number
  x: number
  y: number
}

export interface TrainingFrame {
  epoch: number
  date_start: string
  date_end: string
  date_mean: string
  mjd_mean: number
  n_exposures: number
  wavelength_um: [number, number] | null
  image: string
  planted: PlantedSpot
  planted_in_reference?: PlantedSpot
}

export interface TrainingResponse {
  simulation: true
  notice: string
  key: string
  ra: number
  dec: number
  fov: number
  detector: number
  mode: 'normal' | 'difference'
  level: Level
  seed: number
  size_px: number
  pixel_arcsec: number
  frames: TrainingFrame[]
  failures: string[]
  found_within_arcsec: number
  planted: {
    distance_au: number
    swing_arcsec: number
    drift_arcsec_per_year: number
    peak_over_noise: number
    positions: PlantedSpot[]
    explanation: string
  }
  credit?: string
}

/** Shown while nothing has come back yet (and if the answer fails): the same words as the backend's notice. */
export const FALLBACK_NOTICE =
  'Simulation: one made-up moving object has been added to these real SPHEREx images. It is not a real detection, and nothing here is a discovery.'

export const FOV_MIN_TRAINING = 0.05

/** The request for a practice round of the selection on screen. */
export function trainingUrl(s: Selection): string {
  const fov = Math.min(Math.max(s.fov, FOV_MIN_TRAINING), FOV_MAX)
  const mode = s.mode === 'difference' ? 'difference' : 'normal'
  const q = new URLSearchParams({
    ra: String(s.ra),
    dec: String(s.dec),
    fov: String(fov),
    detector: String(s.det),
    mode,
    level: s.level,
    seed: String(s.train ?? 0),
  })
  return `/api/training?${q}`
}

/** The page address of a practice round at the selection's position. */
export function trainingAddress(s: Selection, seed: number, level: Level = 'easy'): string {
  return addressOf({
    ...s,
    // The practice screen has only the ordinary and difference frames, and a field it can build.
    mode: s.mode === 'difference' ? 'difference' : 'normal',
    fov: Math.min(Math.max(s.fov, FOV_MIN_TRAINING), FOV_MAX),
    pmra: null,
    pmdec: null,
    parallax: null,
    train: seed,
    level,
  })
}

/** The address of the ordinary view of the same position. */
export function realSkyAddress(s: Selection): string {
  return addressOf({ ...s, train: null, level: DEFAULT_SELECTION.level })
}

/** A fresh seed for a new round. */
export const newSeed = (): number => Math.floor(Math.random() * 1_000_000)

/** How far a click is from the made-up object, in arcseconds, and whether that counts as finding it. */
export function judgeClick(
  click: { ra: number; dec: number },
  planted: { ra: number; dec: number },
  foundWithinArcsec: number,
): { found: boolean; distanceArcsec: number } {
  const { east, north } = skyOffsetArcsec(planted, click)
  const distanceArcsec = Math.hypot(east, north)
  return { found: distanceArcsec <= foundWithinArcsec, distanceArcsec }
}

/** Which quarter of the picture a point is in (x, y from the top-left). */
export function quarterOf(x: number, y: number, sizePx: number): 'upper left' | 'upper right' | 'lower left' | 'lower right' {
  const side = x < sizePx / 2 ? 'left' : 'right'
  const height = y < sizePx / 2 ? 'upper' : 'lower'
  return `${height} ${side}`
}

/** The hint, once there have been three misses. */
export function hintSentence(first: PlantedSpot, sizePx: number): string {
  return `Hint: in the first frame shown (visit ${first.epoch}) the made-up object is in the ${quarterOf(first.x, first.y, sizePx)} quarter of the picture.`
}

export const MISSES_BEFORE_HINT = 3

/** "35 arcseconds", with no false precision. */
export function arcsecondsText(arcsec: number): string {
  const rounded = arcsec < 10 ? Math.round(arcsec * 10) / 10 : Math.round(arcsec)
  return `${rounded} ${rounded === 1 ? 'arcsecond' : 'arcseconds'}`
}

export function triesText(tries: number): string {
  return tries === 1 ? 'on your first try' : `in ${tries} tries`
}

// ---- loading ------------------------------------------------------------------------------

export type TrainingLoad =
  | { state: 'loading' }
  | { state: 'ready'; data: TrainingResponse }
  | { state: 'error'; message: string }

/** The backend's plain reason for a refusal, or a sentence of our own. */
function explain(status: number, body: unknown): string {
  const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : undefined
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail) && detail.length) return 'The server did not accept this request for a practice round.'
  if (status >= 500) return `The server ran into a problem while making the practice round (error ${status}). Try again.`
  return `The server answered with error ${status}.`
}

export async function fetchTraining(url: string, signal?: AbortSignal): Promise<TrainingResponse> {
  let r: Response
  try {
    r = await fetch(url, { signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new Error('The server could not be reached. Check your connection and that the server is running, then try again.', { cause: e })
  }
  let body: unknown
  try {
    body = await r.json()
  } catch (e) {
    if (signal?.aborted) throw e
    body = undefined
  }
  if (!r.ok) throw new Error(explain(r.status, body))
  const b = body as Partial<TrainingResponse> | undefined
  if (!b || b.simulation !== true || !Array.isArray(b.frames) || !b.planted) {
    throw new Error('The server answered, but not with a practice round. It may be the wrong server, or still starting up.')
  }
  return b as TrainingResponse
}

/** The practice round at `url`, ready only once every picture can be shown. `attempt` asks again. */
export function useTraining(url: string, attempt: number): TrainingLoad {
  const key = `${attempt} ${url}`
  const [settled, setSettled] = useState<{ key: string; load: Exclude<TrainingLoad, { state: 'loading' }> } | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    const settle = (load: Exclude<TrainingLoad, { state: 'loading' }>) => {
      if (!ctrl.signal.aborted) setSettled({ key, load })
    }
    const timer = window.setTimeout(() => {
      fetchTraining(url, ctrl.signal)
        .then(async (body) => {
          try {
            await Promise.all(
              body.frames.map((f) => {
                const image = new Image()
                image.src = f.image
                return image.decode()
              }),
            )
          } catch {
            settle({ state: 'error', message: 'The practice round was made, but one of its pictures could not be loaded. Try again.' })
            return
          }
          settle({ state: 'ready', data: body })
        })
        .catch((e: unknown) => settle({ state: 'error', message: e instanceof Error ? e.message : String(e) }))
    }, 0)
    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [key, url])

  return settled?.key === key ? settled.load : { state: 'loading' }
}

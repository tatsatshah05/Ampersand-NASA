// The physics of the "What is it?" picture: pure functions, no drawing.
//
// Everything the picture shows is computed here from a measured number, and nothing else:
//   colour   from the object's temperature (a blackbody seen by the eye),
//   size     from its radius, to scale with the Sun (and Jupiter and the Earth for small things),
//   edge     a standard limb-darkening approximation, the same for every star,
//   distance a scale line in light-years, with the nearest star for comparison.
// No spots, no granulation, no corona, no flares, no planets are drawn: no catalogue we ask
// measures them. When a number is missing the matching part of the picture is left out.

// ------------------------------------------------------------------ reference values

/** Nominal solar effective temperature, IAU 2015 Resolution B3 (K). */
export const SUN_TEFF_K = 5772
/** Nominal solar radius, IAU 2015 Resolution B3 (km). */
export const SUN_RADIUS_KM = 695_700
/** Nominal equatorial radius of Jupiter, IAU 2015 Resolution B3 (km). */
export const JUPITER_RADIUS_KM = 71_492
/** Nominal equatorial radius of the Earth, IAU 2015 Resolution B3 (km). */
export const EARTH_RADIUS_KM = 6_378.1
/** Jupiter and the Earth are drawn too when the object is smaller than this many solar radii. */
export const SMALL_RADIUS_RSUN = 0.2
/**
 * The nearest star, Proxima Centauri, in light-years: Gaia DR3 parallax 768.07 mas, so
 * 1000 / 768.07 = 1.302 pc = 4.246 light-years.
 */
export const NEAREST_STAR_LY = 4.25
/**
 * Below this temperature an object gives off no light the eye can see: a hot body starts
 * to glow a dull red near 798 K, the Draper point (J. W. Draper, 1847). Above it the glow
 * is visible but faint (a blackbody at 1,000 K puts about one part in 100,000 of its light
 * between 380 and 780 nm). Below it the object is drawn dark, with an outline, and the card
 * says it is too cool to glow in light our eyes can see.
 */
export const GLOW_MIN_K = 800
/**
 * Limb darkening: the linear law I(mu) / I(centre) = 1 - u (1 - mu), with mu the cosine of
 * the angle between the line of sight and the surface normal (mu = sqrt(1 - (r/R)^2) at a
 * fraction r/R of the way out). u = 0.6 is the classic value for the Sun in visible light.
 * One law and one coefficient for every star: a standard approximation, and said so.
 */
export const LIMB_U = 0.6

// ------------------------------------------------------------------ colour of a blackbody

/**
 * CIE 1931 2-degree standard observer colour-matching functions x-bar, y-bar, z-bar, every
 * 5 nm from 360 to 830 nm (row i is 360 + 5 i nm). Source: the Colour & Vision Research
 * Laboratory (UCL) copy of the CIE table, http://www.cvrl.org/database/data/cmfs/ciexyz31.csv
 * (downloaded 2026-11-15), given to 6 significant figures.
 */
export const CIE_1931_2DEG_5NM: readonly (readonly [number, number, number])[] = [
  [0.0001299, 3.917e-6, 0.0006061], [0.0002321, 6.965e-6, 0.001086], [0.0004149, 1.239e-5, 0.001946],
  [0.0007416, 2.202e-5, 0.003486], [0.001368, 3.9e-5, 0.00645], [0.002236, 6.4e-5, 0.01055],
  [0.004243, 0.00012, 0.02005], [0.00765, 0.000217, 0.03621], [0.01431, 0.000396, 0.06785],
  [0.02319, 0.00064, 0.1102], [0.04351, 0.00121, 0.2074], [0.07763, 0.00218, 0.3713], [0.13438, 0.004, 0.6456],
  [0.21477, 0.0073, 1.03905], [0.2839, 0.0116, 1.3856], [0.3285, 0.01684, 1.62296], [0.34828, 0.023, 1.74706],
  [0.34806, 0.0298, 1.7826], [0.3362, 0.038, 1.77211], [0.3187, 0.048, 1.7441], [0.2908, 0.06, 1.6692],
  [0.2511, 0.0739, 1.5281], [0.19536, 0.09098, 1.28764], [0.1421, 0.1126, 1.0419], [0.09564, 0.13902, 0.81295],
  [0.05795, 0.1693, 0.6162], [0.03201, 0.20802, 0.46518], [0.0147, 0.2586, 0.3533], [0.0049, 0.323, 0.272],
  [0.0024, 0.4073, 0.2123], [0.0093, 0.503, 0.1582], [0.0291, 0.6082, 0.1117], [0.06327, 0.71, 0.07825],
  [0.1096, 0.7932, 0.05725], [0.1655, 0.862, 0.04216], [0.22575, 0.91485, 0.02984], [0.2904, 0.954, 0.0203],
  [0.3597, 0.9803, 0.0134], [0.43345, 0.99495, 0.00875], [0.51205, 1, 0.00575], [0.5945, 0.995, 0.0039],
  [0.6784, 0.9786, 0.00275], [0.7621, 0.952, 0.0021], [0.8425, 0.9154, 0.0018], [0.9163, 0.87, 0.00165],
  [0.9786, 0.8163, 0.0014], [1.0263, 0.757, 0.0011], [1.0567, 0.6949, 0.001], [1.0622, 0.631, 0.0008],
  [1.0456, 0.5668, 0.0006], [1.0026, 0.503, 0.00034], [0.9384, 0.4412, 0.00024], [0.85445, 0.381, 0.00019],
  [0.7514, 0.321, 0.0001], [0.6424, 0.265, 5e-5], [0.5419, 0.217, 3e-5], [0.4479, 0.175, 2e-5],
  [0.3608, 0.1382, 1e-5], [0.2835, 0.107, 0], [0.2187, 0.0816, 0], [0.1649, 0.061, 0], [0.1212, 0.04458, 0],
  [0.0874, 0.032, 0], [0.0636, 0.0232, 0], [0.04677, 0.017, 0], [0.0329, 0.01192, 0], [0.0227, 0.00821, 0],
  [0.01584, 0.005723, 0], [0.0113592, 0.004102, 0], [0.00811092, 0.002929, 0], [0.00579035, 0.002091, 0],
  [0.00410946, 0.001484, 0], [0.00289933, 0.001047, 0], [0.00204919, 0.00074, 0], [0.00143997, 0.00052, 0],
  [0.000999949, 0.0003611, 0], [0.000690079, 0.0002492, 0], [0.000476021, 0.0001719, 0], [0.000332301, 0.00012, 0],
  [0.000234826, 8.48e-5, 0], [0.000166151, 6e-5, 0], [0.000117413, 4.24e-5, 0], [8.30753e-5, 3e-5, 0],
  [5.87065e-5, 2.12e-5, 0], [4.15099e-5, 1.499e-5, 0], [2.93533e-5, 1.06e-5, 0], [2.06738e-5, 7.4657e-6, 0],
  [1.45598e-5, 5.2578e-6, 0], [1.0254e-5, 3.7029e-6, 0], [7.22146e-6, 2.6078e-6, 0],
  [5.08587e-6, 1.8366e-6, 0], [3.58165e-6, 1.2934e-6, 0], [2.52253e-6, 9.1093e-7, 0],
  [1.77651e-6, 6.4153e-7, 0], [1.25114e-6, 4.5181e-7, 0],
]
const CMF_START_NM = 360
const CMF_STEP_NM = 5

/** Second radiation constant hc/k in m K (CODATA 2018, exact from the defined h, c and k). */
const C2_M_K = 0.014387768775039337

/** Planck's law, B_lambda(T) up to a constant factor (2 h c^2), which the scaling below removes. */
export function planckRelative(wavelengthM: number, temperatureK: number): number {
  return 1 / wavelengthM ** 5 / Math.expm1(C2_M_K / (wavelengthM * temperatureK))
}

/** CIE XYZ of a blackbody (arbitrary scale): the Planck spectrum weighted by the colour-matching functions. */
export function blackbodyXyz(temperatureK: number): [number, number, number] {
  let x = 0
  let y = 0
  let z = 0
  CIE_1931_2DEG_5NM.forEach(([xb, yb, zb], i) => {
    const b = planckRelative((CMF_START_NM + CMF_STEP_NM * i) * 1e-9, temperatureK)
    x += xb * b
    y += yb * b
    z += zb * b
  })
  return [x, y, z]
}

/** XYZ to linear sRGB: the matrix of IEC 61966-2-1 (sRGB, D65 white). */
export const XYZ_TO_LINEAR_SRGB: readonly (readonly [number, number, number])[] = [
  [3.2406, -1.5372, -0.4986],
  [-0.9689, 1.8758, 0.0415],
  [0.0557, -0.204, 1.057],
]

export function linearSrgb([x, y, z]: readonly [number, number, number]): [number, number, number] {
  const m = XYZ_TO_LINEAR_SRGB
  return [0, 1, 2].map((i) => m[i][0] * x + m[i][1] * y + m[i][2] * z) as [number, number, number]
}

/** The sRGB transfer function (IEC 61966-2-1): linear light 0..1 to the encoded value 0..1. */
export function gammaEncode(v: number): number {
  const c = Math.min(Math.max(v, 0), 1)
  return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055
}

export type Rgb = [number, number, number]

/**
 * The colour of a blackbody's surface as the eye would see it, in linear sRGB with the
 * brightest channel 1. Below about 1,900 K the colour lies outside what a screen can show
 * (blue comes out negative); the smallest amount of white that brings every channel to
 * zero or above is added, which moves the colour straight toward white and keeps its
 * dominant wavelength. (Below about 880 K green goes negative too, and the line to white
 * enters the screen's range on its red-to-blue edge, so 800 K comes out (255, 0, 40).)
 * Brightness is not shown: every colour is scaled to full.
 */
export function blackbodyLinear(temperatureK: number): Rgb {
  const rgb = linearSrgb(blackbodyXyz(temperatureK))
  const lift = Math.min(0, ...rgb)
  const shifted = rgb.map((c) => c - lift)
  const top = Math.max(...shifted)
  return shifted.map((c) => c / top) as Rgb
}

/** The same colour gamma-encoded, 0..255 per channel. */
export function blackbodyRgb255(temperatureK: number): Rgb {
  return blackbodyLinear(temperatureK).map((c) => Math.round(gammaEncode(c) * 255)) as Rgb
}

export function hex([r, g, b]: Rgb): string {
  return `#${[r, g, b].map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')}`
}

/** Hue in degrees (0 red, 30 orange, 60 yellow, 240 blue) of an 0..255 colour, for tests and words. */
export function hueDegrees([r, g, b]: Rgb): number {
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  if (max === min) return 0
  const d = max - min
  let h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  h *= 60
  return h < 0 ? h + 360 : h
}

/** Does it glow in light our eyes can see? */
export function glowsVisibly(temperatureK: number): boolean {
  return temperatureK >= GLOW_MIN_K
}

/**
 * The colour in a word or two, by temperature, matched to what blackbodyRgb255 gives:
 * 900 K (255, 9, 0) red, 1,200 K (255, 79, 0) red-orange, 3,100 K (255, 187, 116) orange, 4,500 K (255, 222, 188)
 * pale orange, 5,772 K (255, 241, 234) white with a warm tint, 7,000 K (244, 242, 255)
 * white, 10,000 K (205, 217, 255) blue-white, 20,000 K (171, 193, 255) pale blue
 * (portrait.test.ts checks each).
 */
export function colourWord(temperatureK: number): string | null {
  if (!glowsVisibly(temperatureK)) return null
  if (temperatureK < 1000) return 'red'
  if (temperatureK < 1600) return 'red-orange'
  if (temperatureK < 3700) return 'orange'
  if (temperatureK < 5200) return 'pale orange'
  if (temperatureK < 6300) return 'white with a warm tint'
  if (temperatureK < 7500) return 'white'
  if (temperatureK < 15000) return 'blue-white'
  return 'pale blue'
}

// ------------------------------------------------------------------ the disc

/** Limb darkening, linear law: brightness at mu relative to the centre of the disc. */
export function limbIntensity(mu: number, u: number = LIMB_U): number {
  return 1 - u * (1 - Math.min(Math.max(mu, 0), 1))
}

export interface Stop {
  /** fraction of the way from the centre to the edge, 0..1 */
  offset: number
  color: string
}

/**
 * Gradient stops for a glowing disc: the blackbody colour times the limb-darkening
 * intensity, in linear light, then gamma-encoded. Many stops, so the straight
 * interpolation between them (in encoded values) follows the curve closely.
 */
export function discStops(temperatureK: number, n = 16): Stop[] {
  const lin = blackbodyLinear(temperatureK)
  const stops: Stop[] = []
  for (let i = 0; i <= n; i++) {
    // denser towards the edge, where mu changes fastest
    const r = Math.sin(((i / n) * Math.PI) / 2)
    const k = limbIntensity(Math.sqrt(Math.max(0, 1 - r * r)))
    stops.push({ offset: r, color: hex(lin.map((c) => gammaEncode(c * k) * 255) as Rgb) })
  }
  return stops
}

export type Fill = 'glow' | 'dark' | 'outline'

export interface Body {
  key: 'object' | 'sun' | 'jupiter' | 'earth'
  label: string
  cx: number
  cy: number
  /** radius drawn, in picture units */
  r: number
  /** radius to scale, in picture units (may be below what can be seen; then r is the smallest dot) */
  rToScale: number
  /** in solar radii, or null when not measured */
  radiusRsun: number | null
  fill: Fill
  stops: Stop[]
  /** smaller than can be drawn: shown as the smallest dot */
  dot: boolean
}

export interface PortraitInput {
  temperatureK: number | null
  radiusRsun: number | null
  /** a short name for the object, under its disc */
  label: string
}

export interface Portrait {
  width: number
  height: number
  bodies: Body[]
  /** 'none' when neither a temperature nor a radius is known: nothing is drawn */
  kind: 'colour-and-size' | 'colour-only' | 'size-only' | 'none'
  labelY: number
}

export const PICTURE_WIDTH = 400
/**
 * Type sizes in picture units. The picture is drawn 400 units wide and shown at most 400 px
 * wide (ObjectCard.css); on a 390 px phone it is about 300 px wide, so 16 units still render
 * at 12 px and 17 units at about 12.8 px.
 */
export const DISC_LABEL_SIZE = 17
export const SCALE_TEXT_SIZE = 17
export const TAG_SIZE = 16
/** Width of one character of a label at DISC_LABEL_SIZE, roughly (system sans, 0.55 em). */
export const LABEL_CHAR = 9.35
/** Width of one character at SCALE_TEXT_SIZE, roughly. */
export const SCALE_CHAR = 9.4
const MAX_R = 64 // the largest disc's radius
const TOP = 18
const GAP = 20
const MIN_DOT = 0.75 // the smallest radius drawn; a body drawn this size is flagged `dot`
const NOMINAL_R = 46 // a disc whose size is not measured: its size means nothing

/**
 * Lay out the picture. With a radius: the object and the Sun to scale (and Jupiter and the
 * Earth when the object is under a fifth of the Sun's radius), side by side, centres on one
 * line, largest first. With a temperature only: the object's disc alone, at a size that
 * means nothing. With neither: nothing.
 */
export function portraitLayout(input: PortraitInput): Portrait {
  const { temperatureK, radiusRsun } = input
  const hasT = temperatureK != null && Number.isFinite(temperatureK) && temperatureK > 0
  const hasR = radiusRsun != null && Number.isFinite(radiusRsun) && radiusRsun > 0
  const labelY = TOP + 2 * MAX_R + 22
  const height = labelY + 12
  if (!hasT && !hasR) return { width: PICTURE_WIDTH, height: 0, bodies: [], kind: 'none', labelY: 0 }

  const objectFill: Fill = !hasT ? 'outline' : glowsVisibly(temperatureK) ? 'glow' : 'dark'
  const objectStops = hasT && objectFill === 'glow' ? discStops(temperatureK) : []
  const cy = TOP + MAX_R

  if (!hasR) {
    const body: Body = {
      key: 'object',
      label: input.label,
      cx: PICTURE_WIDTH / 2,
      cy,
      r: NOMINAL_R,
      rToScale: NOMINAL_R,
      radiusRsun: null,
      fill: objectFill,
      stops: objectStops,
      dot: false,
    }
    return { width: PICTURE_WIDTH, height, bodies: [body], kind: 'colour-only', labelY }
  }

  const sizes: { key: Body['key']; label: string; rsun: number; fill: Fill; stops: Stop[] }[] = [
    { key: 'object', label: input.label, rsun: radiusRsun, fill: objectFill, stops: objectStops },
    { key: 'sun', label: 'Sun', rsun: 1, fill: 'glow', stops: discStops(SUN_TEFF_K) },
  ]
  if (radiusRsun < SMALL_RADIUS_RSUN) {
    sizes.push({ key: 'jupiter', label: 'Jupiter', rsun: JUPITER_RADIUS_KM / SUN_RADIUS_KM, fill: 'outline', stops: [] })
    sizes.push({ key: 'earth', label: 'Earth', rsun: EARTH_RADIUS_KM / SUN_RADIUS_KM, fill: 'outline', stops: [] })
  }
  const scale = MAX_R / Math.max(...sizes.map((s) => s.rsun)) // picture units per solar radius
  sizes.sort((a, b) => b.rsun - a.rsun)
  const slots = sizes.map((s) => {
    const rToScale = s.rsun * scale
    return { ...s, rToScale, width: Math.max(2 * rToScale, s.label.length * LABEL_CHAR) }
  })
  const total = slots.reduce((sum, s) => sum + s.width, 0) + GAP * (slots.length - 1)
  // Four bodies with a long label can need more than 400 units: then the picture is wider
  // (and is shown a little smaller), never cut off.
  const width = Math.max(PICTURE_WIDTH, Math.ceil(total + 16))
  let x = (width - total) / 2
  const bodies: Body[] = slots.map((s) => {
    const cx = x + s.width / 2
    x += s.width + GAP
    const dot = s.rToScale < MIN_DOT
    return {
      key: s.key,
      label: s.label,
      cx,
      cy,
      r: dot ? MIN_DOT : s.rToScale,
      rToScale: s.rToScale,
      radiusRsun: s.rsun,
      fill: s.fill,
      stops: s.stops,
      dot,
    }
  })
  return { width, height, bodies, kind: hasT ? 'colour-and-size' : 'size-only', labelY }
}

// ------------------------------------------------------------------ the distance line

export interface Tick {
  x: number
  label: string
}

export interface DistanceScale {
  width: number
  height: number
  x0: number
  x1: number
  maxLy: number
  ticks: Tick[]
  object: { x: number; xLow: number | null; xHigh: number | null }
  nearest: { x: number }
}

/**
 * Which side of its marker the nearest-star label goes: to the right unless the object's
 * marker (and the line down to it) would fall inside the label, then to the left if there
 * is room. `textWidth` is the label's width in picture units.
 */
export function nearestLabelSide(s: DistanceScale, textWidth: number): 'right' | 'left' {
  const gap = 6
  const clearRight = s.object.x < s.nearest.x - gap || s.object.x > s.nearest.x + 3 + textWidth + gap
  if (clearRight) return 'right'
  return s.nearest.x - 3 - textWidth >= 0 ? 'left' : 'right'
}

/** A round number at or above v: 1, 2 or 5 times a power of ten. */
export function niceCeil(v: number): number {
  const p = 10 ** Math.floor(Math.log10(v))
  for (const m of [1, 2, 5, 10]) if (m * p >= v) return m * p
  return 10 * p
}

/**
 * A straight scale line in light-years from the Sun to a little past the object (or its
 * upper bound), with the nearest star marked. Returns null without a distance.
 */
export function distanceScale(ly: number | null, low: number | null = null, high: number | null = null): DistanceScale | null {
  if (ly == null || !Number.isFinite(ly) || ly <= 0) return null
  const width = PICTURE_WIDTH
  const x0 = 24
  // room on the right for the last tick's label ("100,000" at SCALE_TEXT_SIZE, 66 units), centred on its tick
  const x1 = width - 34
  const far = Math.max(high ?? ly, ly, NEAREST_STAR_LY)
  const step = niceCeil(far / 4)
  const maxLy = Math.ceil((far * 1.08) / step) * step
  const at = (v: number) => x0 + ((x1 - x0) * v) / maxLy
  const ticks: Tick[] = []
  for (let v = 0; v <= maxLy + 1e-9; v += step) ticks.push({ x: at(v), label: v.toLocaleString('en-US') })
  return {
    width,
    height: 94,
    x0,
    x1,
    maxLy,
    ticks,
    object: { x: at(ly), xLow: low != null && low > 0 ? at(low) : null, xHigh: high != null ? at(Math.min(high, maxLy)) : null },
    nearest: { x: at(NEAREST_STAR_LY) },
  }
}

// The physics of the "What is it?" picture against known values.
//
// References:
//  - CIE illuminant A is a Planckian radiator at 2856 K with chromaticity x = 0.44757,
//    y = 0.40745 (CIE 15:2004); an equal-energy spectrum is at x = y = 1/3.
//  - Mitchell Charity, "Blackbody color datafile" (bbr_color.txt, version 2001-Jun-22,
//    http://www.vendian.org/mncharity/dir3/blackbody/), its "2deg" rows: sRGB, brightest
//    channel 1, gamma-encoded. His CMFs carry the Judd-Vos correction, so his colours differ
//    from the plain CIE 1931 ones by a few levels; the tolerance below is 5 of 255.
//  - An independent computation in Python (numpy, the full-precision CVRL table, the same
//    steps) gave the exact values listed in `python`.
import { describe, expect, it } from 'vitest'
import {
  CIE_1931_2DEG_5NM,
  EARTH_RADIUS_KM,
  GLOW_MIN_K,
  JUPITER_RADIUS_KM,
  NEAREST_STAR_LY,
  SUN_RADIUS_KM,
  SUN_TEFF_K,
  blackbodyLinear,
  blackbodyRgb255,
  blackbodyXyz,
  colourWord,
  discStops,
  distanceScale,
  gammaEncode,
  glowsVisibly,
  hex,
  hueDegrees,
  limbIntensity,
  linearSrgb,
  niceCeil,
  portraitLayout,
  type Rgb,
} from './portrait'

const chromaticity = ([x, y, z]: [number, number, number]) => [x / (x + y + z), y / (x + y + z)]

describe('the colour-matching table', () => {
  it('has 95 rows from 360 to 830 nm with y-bar = 1 at 555 nm', () => {
    expect(CIE_1931_2DEG_5NM).toHaveLength(95)
    expect(CIE_1931_2DEG_5NM[(555 - 360) / 5][1]).toBe(1)
    expect(Math.max(...CIE_1931_2DEG_5NM.map((r) => r[1]))).toBe(1)
  })
  it('puts an equal-energy spectrum at x = y = 1/3', () => {
    const sum = CIE_1931_2DEG_5NM.reduce(([a, b, c], [x, y, z]) => [a + x, b + y, c + z], [0, 0, 0])
    const [x, y] = chromaticity(sum as [number, number, number])
    expect(x).toBeCloseTo(1 / 3, 4)
    expect(y).toBeCloseTo(1 / 3, 4)
  })
  it('puts a 2856 K blackbody on CIE illuminant A', () => {
    const [x, y] = chromaticity(blackbodyXyz(2856))
    expect(Math.abs(x - 0.44757)).toBeLessThan(3e-4)
    expect(Math.abs(y - 0.40745)).toBeLessThan(3e-4)
  })
  it('the sRGB matrix maps the D65 white to equal channels', () => {
    const [r, g, b] = linearSrgb([0.95047, 1, 1.08883])
    for (const c of [r, g, b]) expect(c).toBeCloseTo(1, 3)
  })
})

describe('blackbody colours', () => {
  const charity: Record<number, Rgb> = {
    2500: [255, 166, 69],
    3000: [255, 185, 105],
    3200: [255, 192, 118],
    4000: [255, 213, 161],
    5000: [255, 231, 204],
    5800: [255, 241, 231],
    6500: [255, 249, 251],
    8000: [229, 233, 255],
    10000: [207, 218, 255],
    20000: [173, 193, 255],
  }
  it.each(Object.entries(charity))('%s K is within 5 levels of Charity\'s table', (t, ref) => {
    const got = blackbodyRgb255(Number(t))
    got.forEach((c, i) => expect(Math.abs(c - ref[i])).toBeLessThanOrEqual(5))
  })
  const python: Record<number, Rgb> = {
    1000: [255, 46, 0],
    1200: [255, 79, 0],
    3100: [255, 187, 116],
    3200: [255, 190, 122],
    4500: [255, 222, 188],
    5772: [255, 241, 234],
    7000: [244, 242, 255],
    10000: [205, 217, 255],
    20000: [171, 193, 255],
  }
  it.each(Object.entries(python))('%s K matches the independent computation to one level', (t, ref) => {
    blackbodyRgb255(Number(t)).forEach((c, i) => expect(Math.abs(c - ref[i])).toBeLessThanOrEqual(1))
  })
  it('the Sun (5,772 K) is near white with a slight warm tint', () => {
    const [r, g, b] = blackbodyRgb255(SUN_TEFF_K)
    expect(r).toBe(255)
    expect(g).toBeGreaterThanOrEqual(b)
    expect(b).toBeGreaterThanOrEqual(225)
    expect(r - b).toBeLessThanOrEqual(30)
    expect(hueDegrees([r, g, b])).toBeGreaterThan(5)
    expect(hueDegrees([r, g, b])).toBeLessThan(40)
    expect(colourWord(SUN_TEFF_K)).toBe('white with a warm tint')
  })
  it('3,200 K is orange: red full, green about three quarters, blue under half', () => {
    const [r, g, b] = blackbodyRgb255(3200)
    expect(r).toBe(255)
    expect(g).toBeGreaterThan(180)
    expect(g).toBeLessThan(200)
    expect(b).toBeLessThan(128)
    expect(hueDegrees([r, g, b])).toBeGreaterThan(25)
    expect(hueDegrees([r, g, b])).toBeLessThan(35)
    expect(colourWord(3200)).toBe('orange')
  })
  it('10,000 K is blue-white', () => {
    const [r, g, b] = blackbodyRgb255(10000)
    expect(b).toBe(255)
    expect(r).toBeLessThan(g)
    expect(r).toBeGreaterThan(190)
    expect(colourWord(10000)).toBe('blue-white')
  })
  it('scales the brightest channel to 1 and never goes negative', () => {
    for (const t of [800, 1000, 1500, 2000, 3000, 6000, 12000, 40000]) {
      const lin = blackbodyLinear(t)
      expect(Math.max(...lin)).toBeCloseTo(1, 12)
      expect(Math.min(...lin)).toBeGreaterThanOrEqual(0)
    }
  })
  it('below 1,000 K it does not glow visibly, and has no colour word', () => {
    expect(GLOW_MIN_K).toBe(1000)
    expect(glowsVisibly(999)).toBe(false)
    expect(glowsVisibly(1000)).toBe(true)
    expect(colourWord(285)).toBeNull()
  })
  it('gamma-encodes with the sRGB curve', () => {
    expect(gammaEncode(0)).toBe(0)
    expect(gammaEncode(1)).toBeCloseTo(1, 12)
    expect(gammaEncode(0.0031308)).toBeCloseTo(0.04045, 5)
    expect(gammaEncode(0.5)).toBeCloseTo(0.735357, 5)
    expect(hex([255, 187, 116])).toBe('#ffbb74')
  })
})

describe('the disc', () => {
  it('darkens toward the edge by the linear law with u = 0.6', () => {
    expect(limbIntensity(1)).toBe(1)
    expect(limbIntensity(0)).toBeCloseTo(0.4, 12)
    expect(limbIntensity(0.5)).toBeCloseTo(0.7, 12)
  })
  it('its stops start at the full colour and end at 0.4 of it in linear light', () => {
    const stops = discStops(3100)
    expect(stops[0]).toEqual({ offset: 0, color: hex(blackbodyRgb255(3100)) })
    expect(stops.at(-1)?.offset).toBeCloseTo(1, 12)
    const edge = hex(blackbodyLinear(3100).map((c) => Math.round(gammaEncode(c * 0.4) * 255)) as Rgb)
    expect(stops.at(-1)?.color).toBe(edge)
    for (let i = 1; i < stops.length; i++) expect(stops[i].offset).toBeGreaterThan(stops[i - 1].offset)
  })
})

describe('sizes to scale', () => {
  const ratio = (p: ReturnType<typeof portraitLayout>, a: string, b: string) => {
    const find = (k: string) => p.bodies.find((x) => x.key === k)!
    return find(a).rToScale / find(b).rToScale
  }
  it("Barnard's Star (0.2022 solar radii, just over a fifth) beside the Sun, to scale", () => {
    const p = portraitLayout({ temperatureK: 3100, radiusRsun: 0.2022, label: "Barnard's star" })
    expect(p.kind).toBe('colour-and-size')
    expect(p.bodies.map((b) => b.key)).toEqual(['sun', 'object'])
    expect(ratio(p, 'object', 'sun')).toBeCloseTo(0.2022, 10)
    expect(p.bodies.find((b) => b.key === 'object')!.fill).toBe('glow')
  })
  it('under a fifth of the Sun: Jupiter and the Earth too, all to scale', () => {
    const p = portraitLayout({ temperatureK: 2600, radiusRsun: 0.12, label: 'A small star' })
    expect(p.bodies.map((b) => b.key)).toEqual(['sun', 'object', 'jupiter', 'earth'])
    expect(ratio(p, 'object', 'sun')).toBeCloseTo(0.12, 10)
    expect(ratio(p, 'jupiter', 'sun')).toBeCloseTo(JUPITER_RADIUS_KM / SUN_RADIUS_KM, 10)
    expect(ratio(p, 'earth', 'sun')).toBeCloseTo(EARTH_RADIUS_KM / SUN_RADIUS_KM, 10)
    expect(JUPITER_RADIUS_KM / SUN_RADIUS_KM).toBeCloseTo(0.10276, 5)
    const earth = p.bodies.find((b) => b.key === 'earth')!
    expect(earth.dot).toBe(true) // 0.6 picture units to scale: drawn as the smallest dot
    expect(p.bodies.find((b) => b.key === 'jupiter')!.fill).toBe('outline') // no colour: planets are not drawn hot
  })
  it('discs and labels never overlap, and stay inside the picture', () => {
    for (const r of [0.01, 0.09, 0.2022, 0.5, 1, 1.158, 3, 40, 300]) {
      const p = portraitLayout({ temperatureK: 4800, radiusRsun: r, label: 'An object name' })
      for (const b of p.bodies) {
        const half = Math.max(b.r, (b.label.length * 7.1) / 2)
        expect(b.cx - half).toBeGreaterThanOrEqual(0)
        expect(b.cx + half).toBeLessThanOrEqual(p.width)
        expect(b.cy + b.r).toBeLessThan(p.labelY - 8)
      }
      for (let i = 1; i < p.bodies.length; i++) {
        const a = p.bodies[i - 1]
        const b = p.bodies[i]
        expect(b.cx - a.cx).toBeGreaterThanOrEqual(a.r + b.r)
        expect(b.cx - a.cx).toBeGreaterThanOrEqual((a.label.length + b.label.length) * 3.55)
      }
    }
  })
  it('a giant fills the disc and the Sun becomes a dot', () => {
    const p = portraitLayout({ temperatureK: 3000, radiusRsun: 200, label: 'Giant' })
    expect(p.bodies[0].key).toBe('object')
    expect(p.bodies[1].dot).toBe(true)
    expect(ratio(p, 'sun', 'object')).toBeCloseTo(1 / 200, 10)
    expect(p.bodies.some((b) => b.key === 'jupiter')).toBe(false)
  })
  it('no radius: one disc whose size means nothing, and no Sun', () => {
    const p = portraitLayout({ temperatureK: 1417, radiusRsun: null, label: 'eps Ind B' })
    expect(p.kind).toBe('colour-only')
    expect(p.bodies.map((b) => b.key)).toEqual(['object'])
    expect(p.bodies[0].radiusRsun).toBeNull()
  })
  it('no temperature: an outline to scale beside a glowing Sun', () => {
    const p = portraitLayout({ temperatureK: null, radiusRsun: 1.5, label: 'X' })
    expect(p.kind).toBe('size-only')
    expect(p.bodies.find((b) => b.key === 'object')!.fill).toBe('outline')
    expect(p.bodies.find((b) => b.key === 'object')!.stops).toEqual([])
    expect(p.bodies.find((b) => b.key === 'sun')!.fill).toBe('glow')
  })
  it('too cool to glow: a dark disc', () => {
    const p = portraitLayout({ temperatureK: 285, radiusRsun: null, label: 'Y dwarf' })
    expect(p.bodies[0].fill).toBe('dark')
    expect(p.bodies[0].stops).toEqual([])
  })
  it('neither: nothing at all', () => {
    expect(portraitLayout({ temperatureK: null, radiusRsun: null, label: 'R Dra' })).toEqual({
      width: 400,
      height: 0,
      bodies: [],
      kind: 'none',
      labelY: 0,
    })
  })
})

describe('the distance line', () => {
  it('needs a distance', () => {
    expect(distanceScale(null)).toBeNull()
    expect(distanceScale(-1)).toBeNull()
  })
  it("Barnard's Star at 5.96 light-years, the nearest star at 4.25", () => {
    const s = distanceScale(5.963)!
    expect(s.maxLy).toBeGreaterThan(5.963)
    expect(s.ticks[0]).toEqual({ x: s.x0, label: '0' })
    const frac = (x: number) => (x - s.x0) / (s.x1 - s.x0)
    expect(frac(s.object.x) * s.maxLy).toBeCloseTo(5.963, 9)
    expect(frac(s.nearest.x) * s.maxLy).toBeCloseTo(NEAREST_STAR_LY, 9)
    expect(s.ticks.at(-1)!.x).toBeLessThanOrEqual(s.x1 + 1e-9)
  })
  it('R Draconis at 2,607 light-years with its range', () => {
    const s = distanceScale(2607, 2472, 2742)!
    expect(s.object.xLow).toBeLessThan(s.object.x)
    expect(s.object.xHigh).toBeGreaterThan(s.object.x)
    expect(s.maxLy).toBeGreaterThanOrEqual(2742)
    expect(s.nearest.x - s.x0).toBeLessThan(1)
  })
  it('rounds the end of the line to 1, 2 or 5 times a power of ten', () => {
    expect([0.3, 1, 1.5, 3, 7, 40, 999].map(niceCeil)).toEqual([0.5, 1, 2, 5, 10, 50, 1000])
  })
})

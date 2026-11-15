import { describe, expect, it } from 'vitest'
import { addressOf, DEFAULT_SELECTION, readAddress } from './address'
import { arcsecondsText, hintSentence, judgeClick, quarterOf, realMoverNote, realSkyAddress, trainingAddress, trainingUrl, triesText } from './training'

describe('click distance', () => {
  const planted = { ra: 100, dec: 10 }
  it('counts a click on the object as found, at distance zero', () => {
    const r = judgeClick(planted, planted, 12)
    expect(r.found).toBe(true)
    expect(r.distanceArcsec).toBe(0)
  })
  it('measures a north offset in arcseconds', () => {
    const r = judgeClick({ ra: 100, dec: 10 + 20 / 3600 }, planted, 12)
    expect(r.distanceArcsec).toBeCloseTo(20, 6)
    expect(r.found).toBe(false)
  })
  it('allows for declination when measuring along right ascension', () => {
    const dec = 60
    const r = judgeClick({ ra: 100 + 20 / 3600 / Math.cos((dec * Math.PI) / 180), dec }, { ra: 100, dec }, 12)
    expect(r.distanceArcsec).toBeCloseTo(20, 4)
  })
  it('works across right ascension 0', () => {
    const r = judgeClick({ ra: 0.001, dec: 0 }, { ra: 359.999, dec: 0 }, 12)
    expect(r.distanceArcsec).toBeCloseTo(7.2, 3)
    expect(r.found).toBe(true)
  })
  it('counts exactly the limit as found', () => {
    expect(judgeClick({ ra: 100, dec: 10 + 12 / 3600 }, planted, 12 + 1e-9).found).toBe(true)
  })
})

describe('hint and wording', () => {
  it('names the quarter of the picture', () => {
    expect(quarterOf(10, 10, 100)).toBe('upper left')
    expect(quarterOf(90, 10, 100)).toBe('upper right')
    expect(quarterOf(10, 90, 100)).toBe('lower left')
    expect(quarterOf(90, 90, 100)).toBe('lower right')
  })
  it('gives a hint that says where, without coordinates', () => {
    const text = hintSentence({ epoch: 2, ra: 1, dec: 1, x: 80, y: 20 }, 100)
    expect(text).toContain('upper right')
    expect(text).toContain('visit 2')
  })
  it('rounds distances without false precision', () => {
    expect(arcsecondsText(37.4)).toBe('37 arcseconds')
    expect(arcsecondsText(4.26)).toBe('4.3 arcseconds')
    expect(arcsecondsText(1)).toBe('1 arcsecond')
  })
  it('counts tries', () => {
    expect(triesText(1)).toBe('on your first try')
    expect(triesText(4)).toBe('in 4 tries')
  })
})

describe('the practice address', () => {
  it('round-trips train and level', () => {
    const query = addressOf({ ...DEFAULT_SELECTION, train: 7, level: 'hard' })
    const { selection, notes } = readAddress(query)
    expect(selection.train).toBe(7)
    expect(selection.level).toBe('hard')
    expect(notes).toEqual([])
  })
  it('leaves train and level out of the ordinary view', () => {
    const query = addressOf(DEFAULT_SELECTION)
    expect(query).not.toContain('train')
    expect(query).not.toContain('level')
    expect(readAddress(query).selection.train).toBeNull()
  })
  it('reads a short address, as in ?train=7&level=easy', () => {
    const { selection } = readAddress('?train=7&level=easy')
    expect(selection.train).toBe(7)
    expect(selection.ra).toBe(DEFAULT_SELECTION.ra)
  })
  it('says so for a seed or level that cannot be used', () => {
    const bad = readAddress('?train=abc')
    expect(bad.selection.train).toBeNull()
    expect(bad.notes).toHaveLength(1)
    const level = readAddress('?train=3&level=brutal')
    expect(level.selection.train).toBe(3)
    expect(level.selection.level).toBe('easy')
    expect(level.notes).toHaveLength(1)
    expect(readAddress('?train=-1').selection.train).toBeNull()
    expect(readAddress('?train=1.5').selection.train).toBeNull()
  })
  it('builds a round at the position on screen, with no sum mode and no motion', () => {
    const query = trainingAddress({ ...DEFAULT_SELECTION, mode: 'sum', pmra: 1, pmdec: 2, parallax: 3, fov: 0.02 }, 12)
    const { selection } = readAddress(query)
    expect(selection.train).toBe(12)
    expect(selection.mode).toBe('normal')
    expect(selection.pmra).toBeNull()
    expect(selection.fov).toBe(0.05) // 0.05 degrees is the least a practice round takes
  })
  it('goes back to the ordinary view of the same position', () => {
    const query = realSkyAddress({ ...DEFAULT_SELECTION, ra: 76.956587, dec: 30.401291, det: 2, train: 3 })
    const { selection } = readAddress(query)
    expect(selection.train).toBeNull()
    expect(selection.ra).toBe(76.956587)
    expect(selection.det).toBe(2)
    expect(query).not.toContain('train')
  })
  it('asks the backend with the round the address names', () => {
    const url = trainingUrl({ ...DEFAULT_SELECTION, train: 7, level: 'medium', mode: 'difference' })
    expect(url).toContain('/api/training?')
    expect(url).toContain('seed=7')
    expect(url).toContain('level=medium')
    expect(url).toContain('mode=difference')
    expect(url).toContain('detector=5')
  })
})

describe('a practice patch centred on a real moving object', () => {
  it("names Barnard's Star in the default round, and says it is not the made-up object", () => {
    expect(realMoverNote(DEFAULT_SELECTION.ra, DEFAULT_SELECTION.dec)).toBe(
      "This patch holds Barnard's Star, a real star that moves fast: the bright one in the middle. It is not the made-up object.",
    )
  })
  it('says nothing for a patch with none of them', () => {
    expect(realMoverNote(253.18038, -44.67697)).toBeNull()
    expect(realMoverNote(269.446267, 4.768222 + 0.05)).toBeNull()
  })
})

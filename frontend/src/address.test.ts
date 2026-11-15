import { afterEach, describe, expect, it, vi } from 'vitest'
import { addressOf, chooseUiLevel, DEFAULT_SELECTION, readAddress, readStoredLevel, storeLevel } from './address'
import { realSkyAddress, trainingAddress } from './training'

describe('ui in the page address', () => {
  it('round-trips expert, and leaves Beginner out of the address', () => {
    const expert = { ...DEFAULT_SELECTION, ui: 'expert' as const }
    expect(addressOf(expert)).toContain('ui=expert')
    expect(readAddress(addressOf(expert)).selection.ui).toBe('expert')
    expect(addressOf(DEFAULT_SELECTION)).not.toContain('ui=')
    expect(readAddress(addressOf(DEFAULT_SELECTION)).selection.ui).toBe('beginner')
  })

  it('a Beginner address with the sum or difference view shows the normal view, as its words describe', () => {
    const read = readAddress('?ra=133.759765&dec=-7.242182&det=6&mode=sum&ui=beginner')
    expect(read.selection.ui).toBe('beginner')
    expect(read.selection.mode).toBe('normal')
    expect(readAddress('?mode=sum&ui=expert').selection.mode).toBe('sum')
  })
  it('a Beginner address that looks like an expert one says ui=beginner, and reads back as Beginner', () => {
    const wise = { ...DEFAULT_SELECTION, det: 6 }
    expect(addressOf(wise)).toContain('ui=beginner')
    expect(readAddress(addressOf(wise)).selection.ui).toBe('beginner')
  })

  it('keeps other parameters and does not duplicate ui', () => {
    const next = addressOf({ ...DEFAULT_SELECTION, ui: 'expert' }, '?ui=expert&x=1')
    expect(next.match(/ui=/g)).toHaveLength(1)
    expect(next).toContain('x=1')
  })

  it('the practice screen and its way back keep ui=expert', () => {
    const expert = { ...DEFAULT_SELECTION, ui: 'expert' as const }
    const train = trainingAddress(expert, 7)
    expect(readAddress(train).selection.ui).toBe('expert')
    expect(realSkyAddress(readAddress(train).selection)).toContain('ui=expert')
  })
})

describe('which level an address opens in', () => {
  it('the address wins over what was stored', () => {
    expect(chooseUiLevel('?ui=expert', 'beginner')).toBe('expert')
    expect(chooseUiLevel('?ui=beginner&mode=difference', 'expert')).toBe('beginner')
  })
  it('a first visit with nothing stored is Beginner', () => {
    expect(chooseUiLevel('', null)).toBe('beginner')
    expect(chooseUiLevel('?ra=269.446267&dec=4.768222&fov=0.1&det=5&mode=normal', null)).toBe('beginner')
  })
  it('uses the stored choice when the address does not say', () => {
    expect(chooseUiLevel('', 'expert')).toBe('expert')
    expect(chooseUiLevel('', 'beginner')).toBe('beginner')
    expect(chooseUiLevel('', 'nonsense')).toBe('beginner')
  })
  it('an address with an expert-only setting and no ui opens in Expert', () => {
    expect(chooseUiLevel('?ra=133.759765&dec=-7.242182&det=6&mode=difference', null)).toBe('expert')
    expect(chooseUiLevel('?mode=sum', null)).toBe('expert')
    expect(chooseUiLevel('?det=2', null)).toBe('expert')
    expect(chooseUiLevel('?detector=2', null)).toBe('expert')
    expect(chooseUiLevel('?fov=0.2', 'beginner')).toBe('expert')
  })
  it('settings that are the defaults, or unusable, do not make it Expert', () => {
    expect(chooseUiLevel('?det=5&fov=0.1&mode=normal', null)).toBe('beginner')
    expect(chooseUiLevel('?det=9&fov=7&mode=weird', null)).toBe('beginner')
  })
  it('readAddress uses the stored value', () => {
    expect(readAddress('', 'expert').selection.ui).toBe('expert')
    expect(readAddress('').selection.ui).toBe('beginner')
  })
})

describe('remembering the choice', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('stores and reads it back', () => {
    const data = new Map<string, string>()
    vi.stubGlobal('window', {
      localStorage: { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) },
    })
    expect(readStoredLevel()).toBeNull()
    storeLevel('expert')
    expect(readStoredLevel()).toBe('expert')
  })
  it('works when storage is not available', () => {
    vi.stubGlobal('window', {
      get localStorage(): never {
        throw new Error('blocked')
      },
    })
    expect(readStoredLevel()).toBeNull()
    expect(() => storeLevel('expert')).not.toThrow()
  })
})

describe('the parallax of a far-off body', () => {
  it('keeps a parallax of 687,549 mas (a body 300 times the Earth-Sun distance away) and drops an absurd one', () => {
    const kept = readAddress('?ra=10&dec=5&pmra=100&pmdec=200&parallax=687549').selection
    expect(kept.parallax).toBe(687549)
    const dropped = readAddress('?ra=10&dec=5&pmra=100&pmdec=200&parallax=5000000').selection
    expect(dropped.parallax).toBeNull()
  })
})

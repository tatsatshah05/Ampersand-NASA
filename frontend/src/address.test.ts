import { afterEach, describe, expect, it, vi } from 'vitest'
import { addressOf, chooseUiLevel, DEFAULT_SELECTION, LANDING, readAddress, readStoredLevel, storeLevel, toolFrom, withTarget, withTool, withUi, writeTool } from './address'
import { TOOL_KEYS } from './features'
import { realSkyAddress, trainingAddress } from './training'

describe('the tool open under the picture (tool=<key>)', () => {
  it('reads each of the six tools, and nothing else', () => {
    for (const key of TOOL_KEYS) expect(toolFrom(`?ra=10&dec=5&tool=${key}`)).toBe(key)
    expect(toolFrom('?ra=10&dec=5')).toBeNull()
    expect(toolFrom('?tool=watch')).toBeNull()
    expect(toolFrom('?tool=Spectrum')).toBeNull()
    expect(toolFrom('?tool=')).toBeNull()
  })

  it('ignores an unknown tool with a note, as for the other parameters, and keeps the rest of the address', () => {
    const read = readAddress('?ra=10&dec=5&tool=telescope')
    expect(read.notes).toEqual([
      'The address asks to open a tool called "telescope". The tools are brightness, spectrum, search, distant, smallbodies, context, so none is opened.',
    ])
    expect(read.selection.ra).toBe(10)
    expect(readAddress('?ra=10&dec=5&tool=spectrum').notes).toEqual([])
    expect(readAddress('?ra=10&dec=5').notes).toEqual([])
  })

  it('sets the tool on screen in the address, and drops it for Watch, leaving every other parameter', () => {
    expect(withTool('?ra=10&dec=5&ui=expert', 'distant')).toBe('?ra=10&dec=5&ui=expert&tool=distant')
    expect(withTool('?ra=10&dec=5&tool=distant&ui=expert', 'context')).toBe('?ra=10&dec=5&tool=context&ui=expert')
    expect(withTool('?ra=10&dec=5&tool=distant', null)).toBe('?ra=10&dec=5')
    expect(withTool('', 'spectrum')).toBe('?tool=spectrum')
  })

  it('stays in the address when the view changes (addressOf keeps it), and is not carried to a practice round', () => {
    const next = addressOf({ ...DEFAULT_SELECTION, ra: 20 }, '?ra=10&dec=5&tool=brightness')
    expect(toolFrom(next)).toBe('brightness')
    expect(next.match(/tool=/g)).toHaveLength(1)
    expect(toolFrom(trainingAddress(DEFAULT_SELECTION, 7))).toBeNull()
  })

  afterEach(() => vi.unstubAllGlobals())
  it('is written in place (replaceState), and only when it changes', () => {
    const calls: string[] = []
    const page = {
      location: { search: '?ra=10&dec=5' },
      history: {
        replaceState: (_: unknown, __: string, url: string) => {
          calls.push(url)
          page.location.search = url
        },
      },
    }
    vi.stubGlobal('window', page)
    writeTool('search')
    writeTool('search')
    writeTool(null)
    writeTool(null)
    expect(calls).toEqual(['?ra=10&dec=5&tool=search', '?ra=10&dec=5'])
  })
})

describe('the level carried by the links between screens', () => {
  it('says the level outright, in place of any the address had', () => {
    expect(withUi('?watchlist=1', 'beginner')).toBe('?watchlist=1&ui=beginner')
    expect(withUi('?watchlist=1&ui=beginner', 'expert')).toBe('?watchlist=1&ui=expert')
    expect(withUi('', 'expert')).toBe('?ui=expert')
    expect(readAddress(withUi(trainingAddress(DEFAULT_SELECTION, 7), 'beginner'), 'expert').selection.ui).toBe('beginner')
    expect(readAddress(withUi(trainingAddress(DEFAULT_SELECTION, 7), 'expert'), 'beginner').selection.ui).toBe('expert')
  })
})

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

describe('what the page opens on', () => {
  it('an address with no position opens on Candidate B, held still at its corrected place, in detector 6', () => {
    const { selection, notes } = readAddress('')
    expect(selection).toEqual(LANDING)
    expect([selection.name, selection.ra, selection.dec, selection.pmra, selection.pmdec, selection.det]).toEqual(['Candidate B', 253.18038, -44.67697, 0, 0, 6])
    expect(notes).toEqual([])
    expect(readAddress('?ui=expert').selection.name).toBe('Candidate B')
    // Its address reads back as the same view, in Beginner.
    expect(readAddress(addressOf(LANDING)).selection).toEqual(LANDING)
  })
  it('Barnard’s Star stays the example: an unusable position, and a practice round with none, still show it', () => {
    expect(readAddress('?ra=abc&dec=5').selection.name).toBe("Barnard's Star")
    expect(readAddress('?train=7&level=easy').selection.ra).toBe(DEFAULT_SELECTION.ra)
    expect(DEFAULT_SELECTION.det).toBe(5)
  })
  it('leaving a candidate in its own detector, a star that suggests none goes back to detector 5', () => {
    const barnard = { ra: 269.446267, dec: 4.768222, name: "Barnard's Star" }
    expect(withTarget(LANDING, barnard, 6)?.det).toBe(5)
    // A detector the visitor chose for themselves on the candidate is kept.
    expect(withTarget({ ...LANDING, det: 3 }, barnard, 3)?.det).toBe(3)
    // Anywhere else the usual detector applies, as before.
    expect(withTarget(DEFAULT_SELECTION, barnard, 6)?.det).toBe(6)
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

// Beginner's "i" popovers for the three candidates, on the server's real answers for their buttons'
// views: about something that appeared, in plain words, by guide.ts's rules.
import { describe, expect, it } from 'vitest'
import type { FramesReady } from './api'
import findAJson from './fixtures/frames/find_a_d6.json'
import findBJson from './fixtures/frames/find_b_d6.json'
import findCJson from './fixtures/frames/find_c_d6.json'
import barnardJson from './fixtures/frames/barnard_d5.json'
import { infoFor, pictureInfo, playerInfo } from './guide'

const [findA, findB, findC, barnard] = [findAJson, findBJson, findCJson, barnardJson] as unknown as FramesReady[]
const words = (s: string) => s.split(/\s+/).filter(Boolean).length
const sentences = (text: string[]) => text.join(' ').split(/(?<=[.!?])\s+/)

describe('the candidates’ popovers', () => {
  it('follow guide.ts’s rules: sentences of 20 words or fewer, no science words, never "discovery"', () => {
    for (const d of [findA, findB, findC]) {
      for (const key of ['picture', 'player', 'movement'] as const) {
        const text = infoFor(key, d, null, 'Candidate B')
        for (const s of sentences(text)) expect(words(s), s).toBeLessThanOrEqual(20)
        expect(text.join(' ')).not.toMatch(/sigma|flux|epoch|detector|centroid|discover|new planet|\bnew\b|confirmed it\b(?! yet)/i)
      }
    }
  })

  it('Play and Blink: Blink flips between the visit without it and the first one with it', () => {
    expect(infoFor('player', findB, null, null)).toEqual([
      'Play shows the visits one after another, like a short film.',
      "Blink before and after flips between visit 1, in August 2025, and visit 2, in March 2026. In the first, nothing is seen at Candidate B's place. In the second, it is clearly there.",
    ])
    // C: never visit 1 and visit 4, both without it.
    expect(infoFor('player', findC, null, null)[1]).toMatch(/^Blink before and after flips between visit 1, in August 2025, and visit 2, in March 2026\./)
    expect(infoFor('player', barnard, null, null)).toEqual(playerInfo(barnard))
  })

  it('the headline’s popover says what changed and how we tell, with what it may be, hedged', () => {
    const c = infoFor('movement', findC, null, null)
    expect(c).toContain('In visit 1 it was not seen. In visit 2 it was clearly there. It stays in one place, so it is not something moving past.')
    expect(c.join(' ')).toContain('Its light hints at a nova')
    expect(c[c.length - 1]).toBe('Nobody has confirmed it yet. People must still make some checks. A bigger telescope must look at its light.')
    expect(infoFor('movement', findA, null, null).join(' ')).toContain('In visit 1 it was not seen. In visits 2 and 3 it was clearly there.')
  })

  it('the picture: the white cross marks its place in every visit, and the neighbour is named as not the candidate', () => {
    const [story, marks] = infoFor('picture', findB, null, 'Candidate B')
    expect(story).toBe(pictureInfo(findB, 'Candidate B')[0])
    expect(marks).toMatch(/^The white cross marks Candidate B's place in every visit\. The amber ring circles it where it is clearly seen\. The faint star just up and to the left is a steady neighbour/)
    expect(marks).not.toMatch(/Dots and a line/)
    expect(infoFor('picture', barnard, null, "Barnard's Star")).toEqual(pictureInfo(barnard, "Barnard's Star"))
  })
})

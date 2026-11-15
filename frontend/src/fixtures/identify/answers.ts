// The /api/identify answers for the test places, saved from the real catalogues by
// scripts/check_identify.py --save (tests/test_identify.py checks they are what the backend returns).
import type { IdentifyResult } from '../../identify'
import barnard from './barnard.json'
import candidate from './candidate.json'
import epsindib from './epsindib.json'
import faint from './faint.json'
import rdra from './rdra.json'
import rwaur from './rwaur.json'
import wise0855 from './wise0855.json'

const as = (j: unknown) => j as IdentifyResult

export const ANSWERS: Record<string, IdentifyResult> = {
  barnard: as(barnard),
  epsindib: as(epsindib),
  wise0855: as(wise0855),
  rwaur: as(rwaur),
  rdra: as(rdra),
  faint: as(faint),
  candidate: as(candidate),
}

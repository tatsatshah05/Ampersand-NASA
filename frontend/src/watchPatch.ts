// Watching a patch on Observe anomalies, without the screen: turn what a visitor typed into a patch, search
// it (runSearch polls /api/search), and open a patch that is already being watched (asking /api/watch,
// and searching again only when it says the archive has new pictures). The screen shows what these return.
// Nothing here starts a search except searchThisPatch, and openWatched when /api/watch says new_pictures.
import type { UiLevel } from './address'
import {
  AGAIN_LINE,
  fetchWatch,
  LOOKUP_FAILED,
  NAME_HAS_OTHER_CHARACTERS,
  nameTooLong,
  NOTHING_FOUND,
  patchKey,
  SEARCH_FAILED,
  TYPE_FIRST,
  watchProgress,
  WATCH_DETECTORS,
  WATCH_FOV,
  type WatchInfo,
} from './anomalies'
import { looksLikeCoords, parseCoords } from './coords'
import { FINDS, findTarget } from './finds'
import { hasUnusableCharacters, nameForLookup, resolveName, ResolveError } from './resolve'
import { runSearch, type SearchStatus } from './search'
import { fetchRegions, type PatchRegions } from './watchlist'

export interface Patch {
  ra: number
  dec: number
  fov: number
  key: string
}

const MAX_NAME_LENGTH = 80
const round6 = (x: number) => Math.round(x * 1e6) / 1e6

/** The patch centred on a position, to the 6 decimals the key has. */
export function patchAt(ra: number, dec: number, fov: number = WATCH_FOV): Patch {
  const r = round6(ra)
  const d = round6(dec)
  return { ra: r, dec: d, fov, key: patchKey(r, d, fov) }
}

export type Found = { ok: true; ra: number; dec: number; patch: Patch } | { ok: false; text: string }

/** Typed text as a patch: coordinates are read, anything else is looked up as a name (as the search box does). */
export async function findPatch(typed: string, signal?: AbortSignal): Promise<Found> {
  const query = typed.replace(/\s+/g, ' ').trim()
  if (!/[\p{L}\p{N}]/u.test(query)) return { ok: false, text: TYPE_FIRST }
  if (looksLikeCoords(query)) {
    const position = parseCoords(query)
    if (!position.ok) return { ok: false, text: position.reason }
    const patch = patchAt(position.ra, position.dec)
    return { ok: true, ra: patch.ra, dec: patch.dec, patch }
  }
  // One of our candidates, by name: its own corrected place.
  const find = FINDS.find((f) => f.name.toLowerCase() === query.toLowerCase())
  if (find) {
    const t = findTarget(find)
    const patch = patchAt(t.ra, t.dec)
    return { ok: true, ra: patch.ra, dec: patch.dec, patch }
  }
  const name = nameForLookup(query)
  if (name.length > MAX_NAME_LENGTH) return { ok: false, text: nameTooLong(MAX_NAME_LENGTH) }
  if (hasUnusableCharacters(name)) return { ok: false, text: NAME_HAS_OTHER_CHARACTERS }
  try {
    const found = await resolveName(name, signal)
    const patch = patchAt(found.ra, found.dec)
    return { ok: true, ra: patch.ra, dec: patch.dec, patch }
  } catch (e) {
    if (signal?.aborted) throw e
    return { ok: false, text: e instanceof ResolveError ? e.message : LOOKUP_FAILED }
  }
}

/** Run the search of a patch to its end (null when it was stopped). */
async function search(patch: Patch, level: UiLevel, signal: AbortSignal, onProgress: (line: string) => void): Promise<SearchStatus> {
  return runSearch(
    { ra: patch.ra, dec: patch.dec, fov: patch.fov, detectors: WATCH_DETECTORS },
    { signal, onStatus: (s) => (s.status === 'queued' || s.status === 'running') && onProgress(watchProgress(s, level)) },
  )
}

/** The regions list and /api/watch, each null when it did not answer (a failure of either must not break the screen). */
async function reload(patch: Patch, signal: AbortSignal): Promise<{ regions: PatchRegions | null; watch: WatchInfo | null }> {
  const [regions, watch] = await Promise.all([
    fetchRegions(signal).catch(() => null),
    fetchWatch(patch.ra, patch.dec, patch.fov, signal).catch(() => null),
  ])
  if (signal.aborted) throw new DOMException('stopped', 'AbortError')
  return { regions, watch }
}

export type SearchOutcome =
  | { kind: 'failed'; error: string }
  | { kind: 'done'; key: string; regions: PatchRegions | null; watch: WatchInfo | null; chosen: boolean; nothing: string | null }

/** Search the patch, then reload the list of searched patches: if it holds the patch, it is chosen; if not, nothing was found. */
export async function searchThisPatch(patch: Patch, level: UiLevel, signal: AbortSignal, onProgress: (line: string) => void): Promise<SearchOutcome> {
  const status = await search(patch, level, signal, onProgress)
  if (status.status === 'failed') return { kind: 'failed', error: status.error || SEARCH_FAILED }
  const { regions, watch } = await reload(patch, signal)
  // The patch is in the list once it has been searched; with a count of 0, or not at all, nothing was found.
  const entry = regions?.regions.find((r) => r.key === patch.key)
  return { kind: 'done', key: patch.key, regions, watch, chosen: !!entry, nothing: entry && entry.count > 0 ? null : NOTHING_FOUND }
}

export interface OpenOutcome {
  watch: WatchInfo | null
  /** The list of patches, reloaded: only when the patch was searched again. */
  regions: PatchRegions | null
  searchedAgain: boolean
  error: string | null
}

/**
 * Open a patch that is already being watched: ask /api/watch. Only when it says the archive has new
 * pictures, search the patch again (`onNote` says so) and reload the list and /api/watch.
 */
export async function openWatched(
  patch: Patch,
  level: UiLevel,
  signal: AbortSignal,
  onProgress: (line: string) => void,
  onNote: (line: string) => void,
): Promise<OpenOutcome> {
  const first = await fetchWatch(patch.ra, patch.dec, patch.fov, signal).catch(() => null)
  if (signal.aborted) throw new DOMException('stopped', 'AbortError')
  if (!first?.new_pictures) return { watch: first, regions: null, searchedAgain: false, error: null }
  onNote(AGAIN_LINE)
  const status = await search(patch, level, signal, onProgress)
  if (status.status === 'failed') return { watch: first, regions: null, searchedAgain: true, error: status.error || SEARCH_FAILED }
  const { regions, watch } = await reload(patch, signal)
  return { watch: watch ?? first, regions, searchedAgain: true, error: null }
}

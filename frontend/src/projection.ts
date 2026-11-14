// Between the picture and the sky. A frame is a tangent-plane picture centred on the
// requested position, north up and east left, with square pixels (see make_grid in
// backend/pipeline.py). Picture positions here are in image pixels from the top-left
// where pixel i spans i to i+1, so the centre of the picture is at sizePx / 2.

const RAD = Math.PI / 180

export interface Grid {
  /** Sky position of the middle of the picture, in degrees. */
  ra: number
  dec: number
  /** The picture is sizePx by sizePx. */
  sizePx: number
  /** Arcseconds per picture pixel, as the API reports it. */
  pixelArcsec: number
}

/** Sky position (degrees) of a point in the picture. */
export function pixelToSky(x: number, y: number, grid: Grid): { ra: number; dec: number } {
  const perPixel = (grid.pixelArcsec / 3600) * RAD
  const xi = -(x - grid.sizePx / 2) * perPixel // east is left
  const eta = -(y - grid.sizePx / 2) * perPixel // north is up
  const dec0 = grid.dec * RAD
  const den = Math.cos(dec0) - eta * Math.sin(dec0)
  const dra = Math.atan2(xi, den)
  const dec = Math.atan(((Math.sin(dec0) + eta * Math.cos(dec0)) * Math.cos(dra)) / den)
  return { ra: (((grid.ra + dra / RAD) % 360) + 360) % 360, dec: dec / RAD }
}

/** Point in the picture of a sky position (degrees). */
export function skyToPixel(ra: number, dec: number, grid: Grid): { x: number; y: number } {
  const perPixel = (grid.pixelArcsec / 3600) * RAD
  const dec0 = grid.dec * RAD
  const d = dec * RAD
  const dra = (ra - grid.ra) * RAD
  const cosC = Math.sin(dec0) * Math.sin(d) + Math.cos(dec0) * Math.cos(d) * Math.cos(dra)
  const xi = (Math.cos(d) * Math.sin(dra)) / cosC
  const eta = (Math.cos(dec0) * Math.sin(d) - Math.sin(dec0) * Math.cos(d) * Math.cos(dra)) / cosC
  return { x: grid.sizePx / 2 - xi / perPixel, y: grid.sizePx / 2 - eta / perPixel }
}

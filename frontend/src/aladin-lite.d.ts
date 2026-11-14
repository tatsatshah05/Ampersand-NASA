// Minimal types for the parts of aladin-lite 3.9.2-beta that ContextView uses. The package
// ships no types; these names and argument orders were checked against node_modules/aladin-lite/dist/aladin.js.
declare module 'aladin-lite' {
  export interface AladinOptions {
    target?: string
    fov?: number
    survey?: string
    cooFrame?: string
    showReticle?: boolean
    showLayersControl?: boolean
    showCooGridControl?: boolean
    showSimbadPointerControl?: boolean
    showFullscreenControl?: boolean
    showShareControl?: boolean
    showZoomControl?: boolean
    showSettingsControl?: boolean
    showFrame?: boolean
    showProjectionControl?: boolean
    showCooLocation?: boolean
    showContextMenu?: boolean
  }

  export interface Layer {
    show(): void
    hide(): void
  }

  export interface GraphicOverlay extends Layer {
    add(shape: unknown): void
  }

  export interface Aladin {
    gotoRaDec(ra: number, dec: number): void
    setFoV(fovDeg: number): void
    setBaseImageLayer(surveyId: string): void
    addCatalog(catalog: Layer): void
    addOverlay(overlay: Layer): void
    removeLayer(layer: Layer): void
  }

  export interface CatalogOptions {
    name?: string
    color?: string
    sourceSize?: number
    limit?: number
    onClick?: 'showTable' | 'showPopup'
  }

  interface AladinStatic {
    init: Promise<void>
    aladin(element: string | HTMLElement, options?: AladinOptions): Aladin
    catalogFromVizieR(
      catalogId: string,
      target: string,
      radiusDeg: number,
      options: CatalogOptions,
      onSuccess?: (catalog: Layer) => void,
      onError?: (error: unknown) => void,
    ): void
    graphicOverlay(options?: { color?: string; lineWidth?: number; name?: string }): GraphicOverlay
    polygon(corners: [number, number][], options?: { color?: string; lineWidth?: number }): unknown
  }

  const A: AladinStatic
  export default A
}

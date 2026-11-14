# SPHEREx time-lapse viewer (frontend)

A React page that shows SPHEREx infrared images of a small patch of sky over time. It asks the Python backend in `../backend` for the frames, finds the target star in each, and draws where Gaia says the star should be next to where it was measured.

## Run it

The backend serves the built page at `/`, so build first, then start the backend from the repository root:

```
cd frontend
npm ci
npm run build
cd ..
uvicorn backend.app:app --port 8000
```

Open http://localhost:8000. For work on the page itself, `npm run dev` starts Vite with hot reload; it passes `/api` and `/frames` to a backend running on port 8000 (see `vite.config.ts`).

## Checks

```
npm run lint        # oxlint
npm run typecheck   # tsc
npm test            # vitest
npm run build       # type check and production build into dist/
```

## Where things are

- `src/App.tsx`: the page; holds the search, the chosen frames and the layout.
- `src/api.ts`, `src/stars.ts`: types and fetches for the backend's `/api/frames` and `/api/stars`.
- `src/components/`: one file per panel. `Stage` (zoomable image), `PlayerControls`, `GaiaOverlay` (arrow, predicted marks and readout), `FieldStars`, `FrameDetails`, `SpectrumPanel`, `BrightnessPanel`, `MotionLayer`, `ContextView` (Aladin Lite sky atlas, opt-in), `SearchBar`, `Selectors`, `StatusCard`.
- `src/*.ts`: helpers such as coordinate parsing (`coords.ts`), projection, zoom, spectrum and light-curve calculations. Tests sit next to them as `*.test.ts(x)`.
- `public/viewer.html`: the earlier single-file viewer, served at `/viewer.html`.

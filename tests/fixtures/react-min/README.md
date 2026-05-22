# `react-min` — ASTRA acquisition-pipeline test fixture

A minimal Vite + React 19 + TypeScript app, built with sourcemaps, whose
`dist/` output is committed to the repo so the acquisition-pipeline
integration test can run without `npm` or network access.

The pipeline integration test serves `dist/` via a local `http.server`,
runs the harvester to discover JS + sourcemaps, then runs the
sourcemap-exploder to reconstruct the original `.tsx` sources. The test
verifies that the grep marker below survives the full round-trip.

## Grep marker

```
ASTRA_FIXTURE_MARKER
```

with the string value `"react-min"`. Defined in `src/App.tsx`. After
build it lands in `dist/assets/index-*.js.map` inside `sourcesContent[]`.

## Layout

```
tests/fixtures/react-min/
  index.html          # entry HTML, references /src/main.tsx
  vite.config.ts      # build.sourcemap=true, react/react-dom externalized
  tsconfig.json
  package.json
  .gitignore          # ignores node_modules/, .vite/, *.log
  src/
    main.tsx          # createRoot bootstrap
    App.tsx           # the marker lives here
  dist/               # COMMITTED — built artifact for tests
    index.html
    assets/index-*.js
    assets/index-*.js.map
```

## Why React is externalized

The fixture exists for static analysis (harvesting + sourcemap
reconstruction), not runtime execution. Bundling React + ReactDOM blew
`dist/` past 1 MB, which violates the < 200 KB constraint for fixtures.

`vite.config.ts` marks `react`, `react-dom`, `react-dom/client`, and
`react/jsx-runtime` as external and rewrites their import paths to
`https://esm.sh/react@19[...]`. The harvester sees real `<script
type=module>` and real ESM `import` statements pointing at external
URLs — exactly the shape it needs to discover dynamic JS in the wild.

If a future test wants a runtime-executable fixture, build a separate
fixture; do not unwind this one.

## Rebuilding `dist/` from scratch

```bash
cd tests/fixtures/react-min
rm -rf node_modules dist package-lock.json
npm install --no-audit --no-fund
npm run build
```

Then commit the regenerated `dist/`.

## Versions used (last build)

| Tool                 | Version |
|----------------------|---------|
| Node.js              | v25.9.0 |
| npm                  | 11.12.1 |
| Vite                 | 6.4.2   |
| React                | 19.2.6  |
| ReactDOM             | 19.2.6  |
| @vitejs/plugin-react | 4.7.0   |
| TypeScript           | 5.9.3   |

The npm `^` ranges in `package.json` mean a fresh install on a future
machine may pick newer patches. That is fine — the integration test
only depends on the build emitting:

1. At least one `.js` file under `dist/assets/` with a sibling `.js.map`.
2. A `//# sourceMappingURL=...` pragma at the end of that `.js`.
3. The marker string `"react-min"` (defined alongside
   `ASTRA_FIXTURE_MARKER` in `src/App.tsx`) present inside
   `sourcesContent[]` of the emitted `.map`.

If any of those break after a rebuild, the fixture is wrong, not the test.

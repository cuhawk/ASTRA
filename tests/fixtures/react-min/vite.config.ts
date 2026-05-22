import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Minimal config for the ASTRA acquisition-pipeline test fixture.
// Sourcemaps MUST be enabled so the harvester + sourcemap-exploder
// can reconstruct the original .tsx sources from dist/.
//
// React/ReactDOM are externalized via importmap so dist/ stays
// under the 200 KB cap. The fixture is for static analysis (harvesting
// + sourcemap reconstruction), not runtime execution — the bundle still
// has a real Vite + React + TSX build chain producing realistic .js.map
// with sourcesContent[] including our App.tsx marker.
export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: true,
    minify: "esbuild",
    target: "es2020",
    rollupOptions: {
      external: ["react", "react-dom", "react-dom/client", "react/jsx-runtime"],
      output: {
        manualChunks: undefined,
        paths: {
          react: "https://esm.sh/react@19",
          "react-dom": "https://esm.sh/react-dom@19",
          "react-dom/client": "https://esm.sh/react-dom@19/client",
          "react/jsx-runtime": "https://esm.sh/react@19/jsx-runtime",
        },
      },
    },
  },
});

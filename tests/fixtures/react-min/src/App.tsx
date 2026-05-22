import { useState } from "react";

// Grep marker for the ASTRA acquisition-pipeline integration test.
// The test verifies this string survives the round-trip:
//   src/App.tsx -> Vite build -> dist/*.js.map (sourcesContent) -> harvester -> exploder
export const ASTRA_FIXTURE_MARKER = "react-min";

export function App() {
  const [count, setCount] = useState(0);
  return (
    <main>
      <h1>ASTRA fixture: {ASTRA_FIXTURE_MARKER}</h1>
      <button onClick={() => setCount((c) => c + 1)}>count: {count}</button>
    </main>
  );
}

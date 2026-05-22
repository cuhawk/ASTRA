# ASTRA

**BloodHound for JavaScript web apps.**

Drop a URL or a `.zip` of JS. ASTRA reconstructs the source, builds a callgraph with taint tags, records which functions are live in which user-facing features, and serves the result as an interactive graph you can query in cypher or natural language.

---

## Why

Real-world web apps ship as obfuscated, multi-chunk, sourcemap-stripped bundles. Off-the-shelf SAST tools (CodeQL, Semgrep, Snyk Code) are engineered for source repositories the analyst owns — that is rarely the bug-hunter's input. Dynamic-only tools (Burp DOM Invader, DOMLogger++) observe the running page but cannot prioritize *which* of the 8,000 functions in a webpack chunk to instrument. LLM-only "audit my repo" prototypes hallucinate without ground truth.

ASTRA is the missing middle: a callgraph-grounded, framework-aware static prior over JS bundles, fused with runtime coverage from a real Chrome session, queried through a BloodHound-style graph UI.

---

## What you get

- **Acquisition** — paste a URL or upload a zip. ASTRA fetches every `<script src>`, dynamic `import()`, inline blob, and `.map` file.
- **Sourcemap reconstruction** — restores the original source tree from public sourcemaps.
- **AST + callgraph** — framework-aware, with async edges (`Promise.then`, `addEventListener`, `postMessage`, `setTimeout`, RxJS, service workers).
- **Taint analysis** — source → sink chains with closure-expanded tags and hop-decayed confidence.
- **Feature-level coverage** — drive the site through scripted feature runs; ASTRA labels each function with which features actually execute it. Dead code falls out for free.
- **Interactive graph** — cytoscape.js explorer with code panel, taint chain viewer, and feature labels.
- **Query** — write cypher directly, pick a canned query template, or describe what you want in English.

---

## Tiers

| Tier  | LLM key source                | Quota                |
|-------|-------------------------------|----------------------|
| Free  | ASTRA's Gemini key            | 100 queries / user   |
| Pro   | Your Anthropic API key        | Unlimited (you pay)  |

**Free** uses Gemini Flash + `text-embedding-004` for NL → cypher, chain triage, and semantic search.

**Pro** unlocks the Sonnet → Opus advisor cascade for deeper chain audits. Opus fires only when Sonnet returns uncertain — your key is never burned for free-tier work.

---

## What ASTRA is not

- **Not a SCA tool.** No SBOM, no CVE-to-symbol reachability, no dependency-vuln scanning.
- **Not self-host.** ASTRA is delivered as a hosted SaaS. No desktop app, no local install.
- **Not multi-language.** JavaScript / TypeScript only at MVP. Python and Go are deferred.
- **Not an LLM-first analyzer.** The LLM never builds the graph; it triages and translates queries.

---

## Status

Pre-MVP. Repository is being bootstrapped. See `CLAUDE.md` for the design contract and `memory.md` for operating notes.

A substantial portion of the analysis core is vendored from a private reference workspace (`tlxkull`). See `VENDORED.md` (when created) for upstream provenance.

---

## License

TBD.

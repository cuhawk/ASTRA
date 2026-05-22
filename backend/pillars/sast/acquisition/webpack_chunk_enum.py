# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: bin/webpack_chunk_enum.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-23
# license:       proprietary — see upstream repo
# modifications: JS snippet only; CLI scaffold + delta tracking dropped

"""Webpack lazy-chunk URL enumeration.

The harvester's Playwright `page.goto(..., networkidle)` only sees chunks the
bundle eagerly loads on the initial route. Lazy route splits and gated dynamic
imports remain invisible. This module injects a JS snippet that walks the live
page's webpack runtime — both `window.__webpack_require__` (older bundles) and
the `webpackChunk_N_E` push-array hijack (Next.js App Router IIFE closure) —
and asks `__webpack_require__.u(id)` for every chunk URL the bundle declares.
"""
from __future__ import annotations

import json

from pydantic import BaseModel

# JS that walks every known way to reach the webpack chunk URL function.
# Returns a JSON-stringified array of {id, url} plus diagnostic info.
JS_SNIPPET = r"""
(() => {
  function safe(fn, fallback) { try { return fn(); } catch (e) { return fallback; } }

  // Strategy 1: window.__webpack_require__ direct (older webpack builds)
  let wpr = window.__webpack_require__ || null;

  // Strategy 2: Hijack a freshly-resolved push call to capture __webpack_require__
  // (Next.js App Router gates it inside an IIFE closure)
  if (!wpr) {
    const chunks = window.webpackChunk_N_E || window.webpackChunk || null;
    if (chunks && typeof chunks.push === 'function') {
      try {
        chunks.push([
          ['__tlx_probe_' + Date.now()],
          {},
          (req) => { window.__tlx_wpr = req; }
        ]);
        wpr = window.__tlx_wpr || null;
      } catch (e) {}
    }
  }

  // Strategy 3: scan loaded scripts for require.u inline expressions
  // (only used as a fallback hint, not enumeration)

  const diag = {
    wpr_present: !!wpr,
    wpr_u_present: !!(wpr && wpr.u),
    wpr_p: wpr && wpr.p ? wpr.p : null,
    chunk_array_length: safe(() => (window.webpackChunk_N_E || window.webpackChunk || []).length, 0),
  };

  if (!wpr || !wpr.u) {
    return JSON.stringify({ diag, urls: [], error: 'webpack_require_u_unreachable' });
  }

  // Iterate IDs. Webpack typically uses 4-5 digit numeric IDs but a contiguous
  // range search is wasteful. Instead: walk known IDs from the chunk array's
  // already-pushed modules + brute the 0..20000 range and dedupe.
  const seen = new Set();
  const results = [];

  // Seed from already-pushed module IDs (these are usually valid chunk IDs too)
  const seedIds = [];
  safe(() => {
    const arr = window.webpackChunk_N_E || window.webpackChunk || [];
    for (const tuple of arr) {
      if (Array.isArray(tuple[0])) {
        for (const id of tuple[0]) seedIds.push(id);
      }
      if (tuple[1] && typeof tuple[1] === 'object') {
        for (const k of Object.keys(tuple[1])) {
          const n = Number(k);
          if (Number.isFinite(n)) seedIds.push(n);
        }
      }
    }
  });

  // Brute 0..20000 — webpack URLs return undefined or throw for unknown IDs;
  // we keep only resolutions that look like a real chunk URL.
  for (let i = 0; i < 20000; i++) {
    if (i >= 20000) break;
    let u;
    try { u = wpr.u(i); } catch (e) { continue; }
    if (!u || typeof u !== 'string') continue;
    if (!/\.js/.test(u)) continue;
    if (seen.has(u)) continue;
    seen.add(u);
    results.push({ id: i, url: u });
  }
  // Also iterate the seed set in case it has larger IDs
  for (const i of seedIds) {
    let u;
    try { u = wpr.u(i); } catch (e) { continue; }
    if (!u || typeof u !== 'string') continue;
    if (seen.has(u)) continue;
    seen.add(u);
    results.push({ id: i, url: u });
  }

  // Build full URLs by prefixing with wpr.p when present and the chunk URL is
  // relative.
  const base = (wpr.p || '').replace(/\/?$/, '/');
  const full = results.map(r => ({
    id: r.id,
    url: /^https?:\/\//.test(r.url) ? r.url : (base + r.url)
  }));

  return JSON.stringify({ diag, urls: full });
})()
"""


class WebpackChunkEnumResult(BaseModel):
    diag: dict
    urls: list[str]  # full absolute URLs, already joined with wpr.p when present
    error: str | None = None


async def enumerate_webpack_chunks(page) -> WebpackChunkEnumResult:
    """Run the webpack chunk-enumeration JS snippet against a live Playwright page.

    Returns a `WebpackChunkEnumResult` with the discovered chunk URLs and a
    diagnostic dict (TLX shape: `wpr_present`, `wpr_u_present`, `wpr_p`,
    `chunk_array_length`).

    Failure modes — page has no webpack runtime, CSP blocks evaluate, the
    snippet throws — are caught here. The caller gets an empty result with a
    populated `error` and `diag`, never an exception.
    """
    try:
        raw = await page.evaluate(JS_SNIPPET)
    except Exception as exc:
        return WebpackChunkEnumResult(
            diag={"error": "evaluation_failed", "exception_type": type(exc).__name__},
            urls=[],
            error="evaluation_failed",
        )

    if not isinstance(raw, str):
        return WebpackChunkEnumResult(
            diag={"error": "non_string_return", "got_type": type(raw).__name__},
            urls=[],
            error="non_string_return",
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return WebpackChunkEnumResult(
            diag={"error": "bad_json"},
            urls=[],
            error="bad_json",
        )

    diag = parsed.get("diag", {}) or {}
    err = parsed.get("error")
    raw_urls = parsed.get("urls") or []
    urls: list[str] = []
    for entry in raw_urls:
        if isinstance(entry, dict):
            u = entry.get("url")
            if isinstance(u, str) and u:
                urls.append(u)
        elif isinstance(entry, str) and entry:
            urls.append(entry)

    return WebpackChunkEnumResult(diag=diag, urls=urls, error=err)


__all__ = ["JS_SNIPPET", "WebpackChunkEnumResult", "enumerate_webpack_chunks"]

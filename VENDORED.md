# Vendored Code Provenance

This file tracks every component copied or `git subtree`-imported from an upstream repository. Per `CLAUDE.md` §2 and §6, every vendored file must record its upstream SHA, license, and import date.

## Source repositories

| Short name | Upstream URL                          | License (as of import) |
|------------|---------------------------------------|------------------------|
| tlxkull    | https://github.com/cuhawk/tlxkull     | (record on first import) |

## Vendored components

> Append one row per vendored component. Do not delete rows — historical provenance is the point. When a component is re-vendored at a newer SHA, append a new row rather than editing the old one.

| ASTRA path                        | Upstream path                       | Upstream SHA | Imported on (UTC) | Method      | Notes |
|-----------------------------------|-------------------------------------|--------------|-------------------|-------------|-------|
| _(none yet — Session 1 fills this)_ |                                   |              |                   |             |       |

## Per-file header convention

Every vendored file MUST start with this header block (adjust comment syntax per language):

```
# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: tlx/modules/<module>/<file>
# upstream-sha:  <full 40-char SHA>
# imported-on:   YYYY-MM-DD
# license:       <SPDX id or "see LICENSE in upstream repo">
# modifications: <"none" or short description; update on every edit>
```

## Import method

- **Preferred:** `git subtree add --prefix=<astra/path> <tlxkull-url> <sha> --squash`.
- **Fallback (small, isolated files):** copy + header block.
- Either way, the row in the table above is mandatory.

## When to re-vendor

Re-vendor a component when:
1. Upstream fixes a bug we depend on.
2. Upstream gains a feature we want.
3. Our local modifications have drifted far enough that diffing against upstream is painful.

Never silently re-vendor. Always append a new row.

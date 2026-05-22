# Session 8: Frontend shell (Next.js MVP)

Branch: `feat/frontend-shell`
Goal: Functional Next.js 15 frontend that talks to the existing backend — auth, runs CRUD, features CRUD, URL paste. No graph canvas (cytoscape) yet — deferred to a follow-up session.

## Decisions (locked 2026-05-22)

- **Scope:** functional MVP only. No graph canvas. No shadcn install. Plain Tailwind v4. Dark theme.
- **Stack:** Next.js 15 App Router, React 19, TypeScript strict, Tailwind v4.
- **Auth UX:** "Sign in with GitHub" button → href `${API_BASE}/auth/github/login`. Backend handles callback and 302s back to `settings.base_url` which is set to the frontend URL.
- **API:** thin fetch wrapper in `lib/api.ts`. Cookies flow via `credentials: "include"`.
- **CORS:** backend allows `localhost:3000` + `127.0.0.1:3000` origins.
- **Local-only for now:** Session 10 deploy deferred per user. Local dev runbook in README.

## Pages

- `/` — landing. If unauth: "Sign in with GitHub" + product blurb. If auth: redirect to `/runs`.
- `/runs` — list user's runs. Each row links to `/runs/{id}`. "New run" button → `/runs/new`.
- `/runs/new` — URL paste form. POST → redirect to `/runs/{id}`.
- `/runs/[id]` — show run status (pending/acquiring/analyzing/done/failed), metrics (files / functions / edges), and a table of Function nodes once status === "done". Polls /runs/{id} every 2s while pending/in-progress. Link to `/runs/[id]/features`.
- `/runs/[id]/features` — list features for run; create form; link to record (record runs server-side via existing POST .../record — UI just shows status). Function-execution table per feature.

## Backend deltas

- `backend/main.py` — add CORSMiddleware allowing the frontend dev origin.
- `backend/config.py` — `frontend_origin: str = "http://127.0.0.1:3000"`. Adjust `base_url` default to frontend.
- `.env.example` — note `ASTRA_FRONTEND_ORIGIN`.

## Layout

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.js          (or tailwindcss/postcss for v4)
├── tailwind.config.ts         (only if needed; v4 prefers config-less)
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           (/)
│   │   ├── globals.css
│   │   ├── runs/
│   │   │   ├── page.tsx       (/runs)
│   │   │   ├── new/page.tsx   (/runs/new)
│   │   │   └── [id]/
│   │   │       ├── page.tsx   (/runs/[id])
│   │   │       └── features/page.tsx (/runs/[id]/features)
│   │   └── api-health/page.tsx  (dev-only: shows /healthz response)
│   ├── lib/
│   │   ├── api.ts             fetch wrapper
│   │   ├── types.ts           pydantic-mirrored TS types
│   │   └── env.ts             NEXT_PUBLIC_API_BASE
│   └── components/
│       ├── Button.tsx
│       ├── Card.tsx
│       └── StatusBadge.tsx
```

## Tasks

1. **[SEQUENTIAL]** Backend CORS + frontend_origin config. Main agent.
2. **[SEQUENTIAL]** Scaffold Next.js 15 in `frontend/` via `npm create next-app@latest` (non-interactive flags). Subagent.
3. **[PARALLEL after 2]** Wire pages + API client + components. Subagent.
4. **[SEQUENTIAL]** `just dev-frontend` recipe runs `npm --prefix frontend run dev`. Update justfile.
5. **[SEQUENTIAL]** README runbook: how to start backend + Redis + frontend together locally with a populated `.env`.
6. **[SEQUENTIAL]** Commit + squash-merge.

## Verification

- [ ] `just test` still passes (backend tests untouched).
- [ ] `npm --prefix frontend run build` succeeds with zero TS errors.
- [ ] Manual smoke: `just dev-backend` + `just dev-frontend` + visiting `/` renders the landing and "Sign in with GitHub" links to the backend.
- [ ] CORS preflight on `/auth/me` from `http://127.0.0.1:3000` succeeds.

## Out of scope

- Cytoscape graph canvas (next session).
- shadcn components.
- E2E tests (Playwright against the dev server). Defer.
- Visual design polish.
- Mobile responsive.

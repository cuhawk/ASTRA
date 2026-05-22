# ASTRA task runner. Recipes are stubs in Session 0; each session fills in its targets.

# Default: list available recipes
default:
    @just --list

# Backend FastAPI dev server (wired in Session 4)
dev-backend:
    @echo "[stub] dev-backend — wire FastAPI + uvicorn in Session 4 (auth-and-quota)"

# Frontend Next.js dev server (wired in Session 8)
dev-frontend:
    @echo "[stub] dev-frontend — wire Next.js in Session 8 (frontend-shell)"

# Worker process for analysis jobs (wired in Session 6)
dev-worker:
    @echo "[stub] dev-worker — wire RQ/Dramatiq + Redis in Session 6 (callgraph-and-taint-api)"

# Run all backend tests
test:
    .venv/bin/python -m pytest -v

# Deploy to production host (wired in Session 10)
deploy:
    @echo "[stub] deploy — wire Fly.io or Railway pipeline in Session 10 (deploy)"

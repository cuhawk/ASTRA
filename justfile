# ASTRA task runner. Recipes are stubs in Session 0; each session fills in its targets.

# Default: list available recipes
default:
    @just --list

# Backend FastAPI dev server. Requires local Redis + .env populated (see .env.example).
dev-backend:
    .venv/bin/uvicorn backend.main:create_app --factory --reload --host 127.0.0.1 --port 8000

# Frontend Next.js dev server
dev-frontend:
    npm --prefix frontend run dev

# Worker process for analysis jobs (wired in Session 6)
dev-worker:
    @echo "[stub] dev-worker — wire RQ/Dramatiq + Redis in Session 6 (callgraph-and-taint-api)"

# Run all backend tests
test:
    .venv/bin/python -m pytest -v

# Deploy to production host (wired in Session 10)
deploy:
    @echo "[stub] deploy — wire Fly.io or Railway pipeline in Session 10 (deploy)"

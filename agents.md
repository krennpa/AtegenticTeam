# Umamimatch Agent Context

This file states the current repository state so coding agents can collaborate cleanly during the hackathon prep.

## 1) Core Working Rules

- OS/terminal: Windows + PowerShell.
- Python: use project virtual env (`.venv`) and run backend with `uvicorn app.main:app --reload --port 8000`.
- Frontend: Next.js app, run with `npm run dev`.
- Backend stack: FastAPI + SQLModel + LangChain/LangGraph.
- Frontend stack: Next.js App Router + TypeScript + Tailwind + Shadcn UI conventions.

## 2) Current Product/Code Status (2026-04-17)

### Branding

- Project naming target is **Umamimatch**.
- Use Umamimatch naming for UI copy, app titles, config defaults, and docs.

### Backend

- Entry point: `backend/app/main.py`.
- Startup creates DB tables via `create_db_and_tables()`.
- Mounted routers:
  - `/auth`
  - `/profiles`
  - `/restaurants`
  - `/teams`
  - `/decision`
  - `/api` (team restaurant cache endpoints)
  - `/notifications`

### AI / Agent Runtime

- Decision runtime is LangGraph `create_react_agent` based.
- Tools currently used:
  - `retrieve_team_needs`
  - `retrieve_restaurant_menus`
- LLM setup is now factory-driven with provider selection:
  - `LLM_PROVIDER=openai` (default)
  - `LLM_PROVIDER=vertexai` (supported fallback)
- Keep this phase minimal: clean architecture seams now, deeper agentic redesign later.

### Scraping

- Current scraper keeps crawl4ai + simple HTTP fallback.
- Strategy/orchestrator seam is the preferred extension point.
- Do not add heavy new extraction features during cleanup passes unless explicitly requested.

## 3) Database Reality

- Default app config now points to `sqlite:///./umamimatch.db`.
- Existing repo may still contain older `dynalunch.db` files.
- When debugging, always verify which DB file runtime is actually using.

## 4) Collaboration Protocol (Colleague + Codex)

### Working style for pairing

1. Keep PRs/sessions small and focused (branding, provider wiring, scraping seams, etc.).
2. Preserve API contracts unless both frontend and backend updates are done together.
3. Prefer cleanup/refactor-lite over feature expansion in prep phases.

### Codex vibe-coding challenge mode

1. Start with a clear objective and a small acceptance checklist.
2. Make minimal coherent edits; avoid broad rewrites.
3. Keep handoff notes tight:
   - what changed
   - what intentionally did not change
   - what is next for deeper agentic work

## 5) Known Risks to Watch

- Frontend stale endpoint call remains possible:
  - `frontend/app/teams/[id]/decision/page.tsx` calls `POST /restaurants/{id}/rescrape?force=true`
  - Backend may not expose this endpoint.
- Duplicate auth route folders exist:
  - `frontend/app/(auth)/...`
  - `frontend/app/auth/...`
  - Keep behavior consistent when touching auth pages.

## 6) API Reality (Do Not Drift)

- Primary decision flow:
  1. `POST /decision/ingest-restaurants`
  2. `POST /decision/agent-decision`
  3. `GET /decision/history`
- Team cache management:
  - `GET /api/teams/{team_id}/restaurants`
  - `PUT /api/teams/{team_id}/restaurants/{restaurant_id}/cache`
  - `DELETE /api/teams/{team_id}/restaurants/{restaurant_id}`

## 7) Agent Editing Guidance

- Keep backend/frontend contracts synchronized.
- Treat `team_restaurants` as source of truth for cache policy.
- Avoid introducing alternate decision modes during prep cleanup.
- Keep architecture cleaner now; save major redesign for explicitly scoped follow-up tasks.

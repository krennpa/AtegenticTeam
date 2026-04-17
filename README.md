# Dynalunch – Lunch Decision Web App

A minimal end-to-end prototype to make group lunch decisions easier.

- Backend: FastAPI (Python), SQLite (local), LangChain + LangGraph (decision flow), crawl4ai + Playwright (web scraping)
- Frontend: Next.js (App Router, TypeScript), TailwindCSS, simple forms, JWT in headers + localStorage

## Screenshots

### Landing Page
![Landing Page](docs/landing-page.png)

### Dashboard
![Dashboard](docs/dashboard.png)

## Quick Start (Docker - Recommended)

**Prerequisites:** Docker Desktop or Docker Engine with Docker Compose

```bash
# 1. Clone and configure
cp .env.example .env

# 2. Build and run
docker-compose up --build

# 3. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

See [DOCKER.md](./DOCKER.md) for detailed Docker deployment guide.

## Local Development (Windows)

**Prerequisites:**
- Python 3.10+ (recommend 3.12)
- Node.js 18+ and npm
- Windows PowerShell

**Note:** Web scraping with Playwright has known issues on Windows. Docker deployment (Linux containers) is recommended for full functionality.

## Backend – Local Run

1) Create and activate a virtual environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies

```powershell
pip install -r requirements.txt
```

3) (Optional) Configure environment

Create a `.env` in `backend/` if you want to override defaults:

```env
# backend/.env
SECRET_KEY=change-me
DATABASE_URL=sqlite:///./dynalunch.db
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

4) Start the API

```powershell
uvicorn app.main:app --reload --port 8000
```

- Health check: http://localhost:8000/health
- OpenAPI docs: http://localhost:8000/docs

Database will be created automatically (SQLite file in `backend/` working dir).

## Frontend – Local Run

1) Install dependencies

```powershell
cd ../frontend
npm install
```

2) Configure API base URL (if different)

By default the app uses `http://localhost:8000`. To override, set:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"
```

3) Start the dev server

```powershell
npm run dev
```

Visit http://localhost:3000

## Basic Flow (MVP)

1) Signup and Login

- Use the UI at `/auth/signup` or `/auth/login`.
- JWT is stored in localStorage and sent via Authorization header.

2) Profile

- Go to `/profile` to view/update your profile (budget, allergies, diet, etc.).

3) Decision

- Go to `/decision` and paste menu URLs (one per line). Example:
  - https://www.enjoyhenry.com/menuplan-bdo/
- Click "Run Decision": the backend will create restaurant entries, scrape menus, and compute a ranking.

Note: Some sites render menus dynamically. If scraping returns no items, we’ll add a site-specific adapter or a Playwright fallback in the next iteration.

## API Overview (MVP)

- `POST /auth/signup` – returns `{ user, token }`
- `POST /auth/login` – returns `{ user, token }`
- `GET /profiles/me` – current user profile
- `PUT /profiles/me` – update profile
- `POST /restaurants` – add a restaurant `{ url, displayName? }`
- `GET /restaurants` – list restaurants
- `GET /restaurants/{id}` – get restaurant
- `GET /restaurants/{id}/menu` – list menu items
- `POST /restaurants/{id}/rescrape` – fetch & parse menu
- `POST /decision` – run decision flow across participants and restaurants

## Architecture Notes

- Backend organized in `app/` by feature: `api/`, `core/`, `db/`, `scraping/`, `decision/`.
- Scraping is modular. Default adapter uses `requests + BeautifulSoup`. You can add site-specific adapters or Playwright support in `app/scraping/adapters/`.
- Decision flow uses a minimal LangGraph pipeline with heuristic scoring. LLM tiebreakers can be added later.

## Next Steps

- Add dynamic-site support (Playwright) and/or site-specific adapter for enjoyhenry.com.
- Add participant selection UI to support groups (beyond "me only").
- Add restaurant management UI (add/list/select), background re-scrape.
- Improve heuristics and add optional LLM tiebreaker in LangGraph.
- Migrate DB to Postgres and add Docker + GCP deployment.

## Dev Tips

- Run FastAPI in `backend/` so SQLite path resolves correctly.
- If CORS errors occur, update `CORS_ORIGINS` in `backend/.env`.
- If the decision result is empty, check `/restaurants/{id}/menu` to verify that scraping found items.

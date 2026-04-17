import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.session import create_db_and_tables
from .api.routers.auth import router as auth_router
from .api.routers.profiles import router as profiles_router
from .api.routers.restaurants import router as restaurants_router
from .api.routers.teams import router as teams_router
from .api.routers.decision import router as decision_router
from .api.routers.team_restaurants import router as team_restaurants_router
from .api.routers.notifications import router as notifications_router

# Fix for Windows asyncio + Playwright subprocess issues
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="Umamimatch API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Routers
app.include_router(auth_router, prefix="/auth", tags=["auth"]) 
app.include_router(profiles_router, prefix="/profiles", tags=["profiles"]) 
app.include_router(restaurants_router, prefix="/restaurants", tags=["restaurants"]) 
app.include_router(teams_router, prefix="/teams", tags=["teams"]) 
app.include_router(decision_router, prefix="/decision", tags=["decision"])
app.include_router(team_restaurants_router, prefix="/api", tags=["team-restaurants"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"]) 

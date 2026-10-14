
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.models
from app.api.auth import router as auth_router
from app.api.game import router as game_router
from app.api.players import router as players_router
from app.api.results import router as results_router
from app.api.rooms import router as rooms_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.core.limiter import limiter


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "A real-time multiplayer drawing and guessing game "
        "built with FastAPI and WebSockets."
    ),
    version="1.0.0",
    debug=settings.DEBUG,
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms_router, prefix=settings.API_V1_PREFIX)
app.include_router(players_router, prefix=settings.API_V1_PREFIX)
app.include_router(game_router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket_router)
app.include_router(results_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {
        "message": "Real-Time Drawing Game API",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
    }

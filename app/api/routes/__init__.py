"""API routes module."""
from app.api.routes.programs import router as programs_router
from app.api.routes.days import router as days_router
from app.api.routes.logs import router as logs_router
from app.api.routes.settings import router as settings_router
from app.api.routes.circuits import router as circuits_router
from app.api.routes.activities import router as activities_router
from app.api.routes.favorites import router as favorites_router
from app.api.routes.movement_preferences import router as movement_preferences_router

__all__ = [
    "programs_router",
    "days_router",
    "logs_router",
    "settings_router",
    "circuits_router",
    "activities_router",
    "favorites_router",
    "movement_preferences_router",
]

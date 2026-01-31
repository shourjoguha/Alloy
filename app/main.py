"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: Cleanup resources
    from app.llm import cleanup_llm_provider
    await cleanup_llm_provider()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="AI-enabled workout coach that creates adaptive strength/fitness programs",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "app": settings.app_name}
    
    # LLM health check
    @app.get("/health/llm")
    async def llm_health_check():
        """Check LLM provider availability."""
        from app.llm import get_llm_provider
        
        provider = get_llm_provider()
        is_healthy = await provider.health_check()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "provider": settings.llm_provider,
            "model": settings.ollama_model,
        }
    
    # Import and include routers
    from app.api.routes import (
        programs_router,
        days_router,
        logs_router,
        settings_router,
        circuits_router,
        activities_router,
        favorites_router,
        movement_preferences_router,
    )
    from app.api.routes import auth as auth_router
    from app.api.routes import onboarding as onboarding_router

    app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
    app.include_router(programs_router, prefix="/programs", tags=["Programs"])
    app.include_router(days_router, prefix="/days", tags=["Daily Planning"])
    app.include_router(logs_router, prefix="/logs", tags=["Logging"])
    app.include_router(settings_router, prefix="/settings", tags=["Settings"])
    app.include_router(circuits_router, prefix="/circuits", tags=["Circuits"])
    app.include_router(activities_router, prefix="/activities", tags=["Activities"])
    app.include_router(favorites_router, prefix="/favorites", tags=["Favorites"])
    app.include_router(movement_preferences_router, prefix="/movement-preferences", tags=["Movement Preferences"])
    app.include_router(onboarding_router.router, prefix="/onboarding", tags=["Onboarding"])
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        import traceback
        import logging
        logging.error(f"Unhandled exception: {exc}", exc_info=True)
        logging.error(f"Traceback: {traceback.format_exc()}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)}
        )
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

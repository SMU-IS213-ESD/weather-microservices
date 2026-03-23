"""
FastAPI application factory for the Weather Service.

Startup order:
  1. Load environment variables from .env (development only).
  2. Create the FastAPI app with metadata for auto-generated docs.
  3. Register global exception handlers.
  4. Mount the /weather router.

The service exposes interactive docs at:
  - Swagger UI  →  /docs
  - ReDoc       →  /redoc
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from app.middleware.error_handler import register_error_handlers
from app.routes.weather import router

# Load .env in local development; harmless no-op in Docker/production.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

app = FastAPI(
    title="Weather Service",
    description=(
        "Drone-flight weather assessment microservice. "
        "Wraps the OpenWeather API with safety thresholds and Redis caching."
    ),
    version="1.0.0",
)

register_error_handlers(app)

app.include_router(router, prefix="/weather", tags=["weather"])


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict:
    """Return a simple liveness probe response."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8006"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

"""
Global exception handlers registered on the FastAPI application.

Converts domain exceptions and unexpected errors into consistent JSON
error responses so that every error the service returns has the same
shape:

    {
        "error": "<error type>",
        "detail": "<human-readable message>"
    }
"""

import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.weather_service import OpenWeatherError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """
    Attach all exception handlers to *app*.

    :param app: The FastAPI application instance.
    """

    @app.exception_handler(OpenWeatherError)
    async def handle_openweather_error(
        request: Request, exc: OpenWeatherError
    ) -> JSONResponse:
        """
        Map OpenWeather API errors to appropriate HTTP status codes.

        - 401 Unauthorized  → 502 (bad API key configured upstream)
        - 404 Not Found     → 422 (invalid coordinates)
        - 429 Too Many Reqs → 503 (rate-limited)
        - everything else   → 502
        """
        logger.error("OpenWeather API error: status=%s detail=%s", exc.status_code, exc.detail)

        status_map = {401: 502, 404: 422, 429: 503}
        http_status = status_map.get(exc.status_code, 502)

        return JSONResponse(
            status_code=http_status,
            content={"error": "upstream_api_error", "detail": exc.detail},
        )

    @app.exception_handler(httpx.RequestError)
    async def handle_request_error(
        request: Request, exc: httpx.RequestError
    ) -> JSONResponse:
        """Handle network-level failures when contacting OpenWeather."""
        logger.error("Network error contacting OpenWeather: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "upstream_unavailable",
                "detail": "Could not reach the OpenWeather API. Please try again later.",
            },
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        """Handle configuration errors such as a missing API key."""
        logger.error("Configuration error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "configuration_error", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def handle_generic_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler — logs the full traceback and returns a safe 500."""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected error occurred.",
            },
        )

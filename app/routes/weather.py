"""
Weather API route definitions.

All routes are mounted under the ``/weather`` prefix by ``app/main.py``.
Query-parameter validation (type coercion, range checks) is handled by
FastAPI / Pydantic automatically.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.controllers import weather_controller
from app.models.weather_models import WeatherCheckResponse, WeatherCurrentResponse

router = APIRouter()


@router.get(
    "/check",
    response_model=WeatherCheckResponse,
    summary="Drone flight safety check",
    description=(
        "Fetches current weather for the given coordinates and evaluates whether "
        "conditions are safe for drone flight. Results are cached for 5 minutes."
    ),
)
async def check_weather(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
) -> WeatherCheckResponse:
    """
    Return a safety assessment for drone flight at *(lat, lon)*.

    :param lat: Latitude, validated to the range [-90, 90].
    :param lon: Longitude, validated to the range [-180, 180].
    :returns: :class:`~app.models.weather_models.WeatherCheckResponse` with
              ``safe``, ``reasons``, raw weather data, and provenance.
    """
    return await weather_controller.get_weather_check(lat, lon)


@router.get(
    "/current",
    response_model=WeatherCurrentResponse,
    summary="Raw current weather",
    description=(
        "Returns the current weather reading for the given coordinates without "
        "any safety evaluation. Results are cached for 5 minutes."
    ),
)
async def current_weather(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
) -> WeatherCurrentResponse:
    """
    Return raw weather data for *(lat, lon)* with no safety logic applied.

    :param lat: Latitude, validated to the range [-90, 90].
    :param lon: Longitude, validated to the range [-180, 180].
    :returns: :class:`~app.models.weather_models.WeatherCurrentResponse`
              with structured weather fields and provenance.
    """
    return await weather_controller.get_weather_current(lat, lon)

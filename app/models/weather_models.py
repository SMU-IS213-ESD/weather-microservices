"""
Pydantic models for request validation and API response serialisation.

All public response shapes are defined here so that both controllers and
tests have a single source of truth for field names and types.
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class WeatherData(BaseModel):
    """Normalised weather reading extracted from an OpenWeather API response."""

    temperature: float = Field(..., description="Air temperature in degrees Celsius")
    windSpeed: float = Field(..., description="Wind speed in metres per second")
    visibility: int = Field(..., description="Visibility in metres (max 10 000)")
    condition: str = Field(..., description="OpenWeather main condition label, e.g. 'Clear'")
    description: str = Field(..., description="OpenWeather verbose description, e.g. 'clear sky'")


class WeatherCheckResponse(BaseModel):
    """
    Response body for ``GET /weather/check``.

    Includes the full drone safety assessment alongside the raw weather data.
    """

    lat: float = Field(..., description="Latitude of the queried coordinate")
    lon: float = Field(..., description="Longitude of the queried coordinate")
    safe: bool = Field(..., description="True when all safety thresholds are met")
    reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable explanation for each violated threshold; empty when safe",
    )
    weather: WeatherData
    source: Literal["cache", "api"] = Field(
        ..., description="Whether the result came from Redis cache or a live API call"
    )
    checkedAt: str = Field(..., description="ISO 8601 UTC timestamp of when the data was fetched")


class WeatherCurrentResponse(BaseModel):
    """
    Response body for ``GET /weather/current``.

    Returns raw weather data only — no safety evaluation.
    """

    lat: float = Field(..., description="Latitude of the queried coordinate")
    lon: float = Field(..., description="Longitude of the queried coordinate")
    weather: WeatherData
    source: Literal["cache", "api"] = Field(
        ..., description="Whether the result came from Redis cache or a live API call"
    )
    fetchedAt: str = Field(..., description="ISO 8601 UTC timestamp of when the data was fetched")

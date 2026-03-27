"""
Thin wrapper around the OpenWeather Current Weather API (v2.5).

Responsibilities:
  - Build the authenticated request URL.
  - Parse the raw JSON response into a typed WeatherData model.
  - Translate HTTP / network errors into domain-specific exceptions.

This module intentionally has no caching logic; caching is handled by
the controller layer so this service stays easy to unit-test.
"""

import os
import httpx

from app.config.constants import OPENWEATHER_BASE_URL, DEFAULT_VISIBILITY_M
from app.models.weather_models import WeatherData


class OpenWeatherError(Exception):
    """
    Raised when the OpenWeather API returns a non-2xx HTTP response.

    Attributes:
        status_code: The HTTP status code returned by the API.
        detail:      The raw response body, useful for upstream error messages.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenWeather API error {status_code}: {detail}")


def _parse_response(raw: dict) -> WeatherData:
    """
    Extract and normalise fields from a raw OpenWeather JSON response.

    The ``visibility`` field is optional in the OpenWeather response
    (omitted when visibility exceeds 10 000 m), so a safe default is
    applied when it is absent.

    :param raw: Parsed JSON dict from the ``/data/2.5/weather`` endpoint.
    :returns:   A populated :class:`~app.models.weather_models.WeatherData`.
    :raises KeyError: If expected top-level keys are missing from *raw*.
    """
    weather_entry = raw["weather"][0]
    return WeatherData(
        temperature=raw["main"]["temp"],
        windSpeed=raw["wind"]["speed"],
        visibility=raw.get("visibility", DEFAULT_VISIBILITY_M),
        condition=weather_entry["main"],
        description=weather_entry["description"],
    )


async def fetch_current_weather(lat: float, lon: float) -> WeatherData:
    """
    Fetch current weather conditions for the given coordinates.

    Makes a single GET request to the OpenWeather ``/weather`` endpoint
    with ``units=metric`` so that temperature is in °C and wind speed
    is in m/s.

    :param lat: Latitude in decimal degrees.
    :param lon: Longitude in decimal degrees.
    :returns:   Parsed :class:`~app.models.weather_models.WeatherData`.
    :raises ValueError:          If ``OPENWEATHER_API_KEY`` is not set.
    :raises OpenWeatherError:    On non-2xx responses from the API.
    :raises httpx.RequestError:  On network-level failures (timeout, DNS, etc.).
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY environment variable is not set")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{OPENWEATHER_BASE_URL}/weather", params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OpenWeatherError(
                exc.response.status_code, exc.response.text
            ) from exc

    return _parse_response(response.json())

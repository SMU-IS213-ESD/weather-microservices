"""
Weather controllers — orchestrate the cache, weather service, and safety evaluation.

Each public function maps 1-to-1 to a route handler and is deliberately kept
free of HTTP concerns (no Request/Response objects) so it can be called and
tested in isolation.

Cache strategy
--------------
Both endpoints share the same Redis key (keyed by rounded lat/lon).  The
cached payload stores the raw WeatherData plus the original fetch timestamp.
Safety evaluation is cheap (pure comparisons) so it is always re-run on
cache hits rather than storing its result separately.
"""

import logging
from datetime import datetime, timezone

from app.models.weather_models import WeatherCheckResponse, WeatherCurrentResponse, WeatherData
from app.services import cache_service, safety_service, weather_service

logger = logging.getLogger(__name__)


async def get_weather_check(lat: float, lon: float) -> WeatherCheckResponse:
    """
    Return a drone flight safety assessment for the given coordinates.

    Flow:
      1. Check Redis for a cached weather entry.
      2. On a cache miss, fetch live data from OpenWeather and store it.
      3. Run safety evaluation against the (cached or fresh) weather data.
      4. Return a :class:`~app.models.weather_models.WeatherCheckResponse`.

    :param lat: Latitude in decimal degrees.
    :param lon: Longitude in decimal degrees.
    :returns: Full safety assessment including raw weather and reasoning.
    :raises app.services.weather_service.OpenWeatherError: On API errors.
    :raises httpx.RequestError: On network failures when the cache is cold.
    """
    cache_key = cache_service.build_cache_key(lat, lon)
    cached = await cache_service.get_cached(cache_key)

    if cached:
        logger.debug("Cache HIT  key=%s", cache_key)
        weather = WeatherData(**cached["weather"])
        safe, reasons = safety_service.evaluate_safety(weather)
        return WeatherCheckResponse(
            lat=lat,
            lon=lon,
            safe=safe,
            reasons=reasons,
            weather=weather,
            source="cache",
            checkedAt=cached["fetchedAt"],
        )

    logger.debug("Cache MISS key=%s — fetching from OpenWeather", cache_key)
    weather = await weather_service.fetch_current_weather(lat, lon)
    fetched_at = datetime.now(timezone.utc).isoformat()

    # Persist raw weather data for reuse by both endpoints.
    await cache_service.set_cached(
        cache_key,
        {"weather": weather.model_dump(), "fetchedAt": fetched_at},
    )

    safe, reasons = safety_service.evaluate_safety(weather)
    return WeatherCheckResponse(
        lat=lat,
        lon=lon,
        safe=safe,
        reasons=reasons,
        weather=weather,
        source="api",
        checkedAt=fetched_at,
    )


async def get_weather_current(lat: float, lon: float) -> WeatherCurrentResponse:
    """
    Return raw current weather data for the given coordinates.

    No safety evaluation is performed.  If a cached entry exists from a
    prior ``/check`` call for the same location it is reused, avoiding a
    redundant OpenWeather request.

    :param lat: Latitude in decimal degrees.
    :param lon: Longitude in decimal degrees.
    :returns: Raw weather data with cache/api provenance indicator.
    :raises app.services.weather_service.OpenWeatherError: On API errors.
    :raises httpx.RequestError: On network failures when the cache is cold.
    """
    cache_key = cache_service.build_cache_key(lat, lon)
    cached = await cache_service.get_cached(cache_key)

    if cached:
        logger.debug("Cache HIT  key=%s", cache_key)
        return WeatherCurrentResponse(
            lat=lat,
            lon=lon,
            weather=WeatherData(**cached["weather"]),
            source="cache",
            fetchedAt=cached["fetchedAt"],
        )

    logger.debug("Cache MISS key=%s — fetching from OpenWeather", cache_key)
    weather = await weather_service.fetch_current_weather(lat, lon)
    fetched_at = datetime.now(timezone.utc).isoformat()

    await cache_service.set_cached(
        cache_key,
        {"weather": weather.model_dump(), "fetchedAt": fetched_at},
    )

    return WeatherCurrentResponse(
        lat=lat,
        lon=lon,
        weather=weather,
        source="api",
        fetchedAt=fetched_at,
    )

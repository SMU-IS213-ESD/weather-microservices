"""
Unit tests for the Weather Service.

The OpenWeather HTTP call and Redis client are both mocked — no external
services are contacted during the test run.

Test coverage:
  - GET /weather/check    safe conditions
  - GET /weather/check    every unsafe condition (wind / visibility / temp / condition / description)
  - GET /weather/check    multiple simultaneous violations
  - GET /weather/current  happy path
  - GET /weather/check    cache hit returns source='cache'
  - GET /weather/check    OpenWeather API error propagation
  - GET /weather/check    network error propagation
  - GET /weather/check    missing API key
  - safety_service        unit-tested directly
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.weather_models import WeatherData
from app.services.safety_service import evaluate_safety
from app.services.weather_service import OpenWeatherError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_weather(**overrides) -> WeatherData:
    """Return a WeatherData that is safe by default; override individual fields."""
    defaults = {
        "temperature": 25.0,
        "windSpeed": 5.0,
        "visibility": 5000,
        "condition": "Clear",
        "description": "clear sky",
    }
    return WeatherData(**{**defaults, **overrides})


# Reusable async mock for fetch_current_weather (safe conditions by default)
def mock_fetch(weather: WeatherData = None):
    """Return a coroutine mock that resolves to *weather*."""
    if weather is None:
        weather = make_weather()
    m = AsyncMock(return_value=weather)
    return m


# Reusable async mock for Redis cache (always a miss by default)
def no_cache():
    get = AsyncMock(return_value=None)
    set_ = AsyncMock()
    return get, set_


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /weather/check — happy path (safe)
# ---------------------------------------------------------------------------

class TestWeatherCheckSafe:
    def test_returns_safe_true(self, client):
        weather = make_weather()
        get_cache, set_cache = no_cache()

        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch(weather)),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 200
        data = resp.json()
        assert data["safe"] is True
        assert data["reasons"] == []
        assert data["source"] == "api"
        assert data["weather"]["temperature"] == 25.0
        assert data["weather"]["windSpeed"] == 5.0
        assert data["weather"]["visibility"] == 5000
        assert data["weather"]["condition"] == "Clear"

    def test_response_shape_matches_spec(self, client):
        get_cache, set_cache = no_cache()

        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch()),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        data = resp.json()
        # All required top-level keys must be present
        for key in ("lat", "lon", "safe", "reasons", "weather", "source", "checkedAt"):
            assert key in data, f"Missing key: {key}"
        # Weather sub-object keys
        for key in ("temperature", "windSpeed", "visibility", "condition", "description"):
            assert key in data["weather"], f"Missing weather key: {key}"


# ---------------------------------------------------------------------------
# GET /weather/check — unsafe conditions
# ---------------------------------------------------------------------------

class TestWeatherCheckUnsafe:
    def _check(self, client, weather: WeatherData):
        get_cache, set_cache = no_cache()
        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch(weather)),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")
        assert resp.status_code == 200
        return resp.json()

    def test_high_wind_speed(self, client):
        data = self._check(client, make_weather(windSpeed=11.0))
        assert data["safe"] is False
        assert any("wind" in r.lower() for r in data["reasons"])

    def test_low_visibility(self, client):
        data = self._check(client, make_weather(visibility=500))
        assert data["safe"] is False
        assert any("visibility" in r.lower() for r in data["reasons"])

    def test_temperature_too_low(self, client):
        data = self._check(client, make_weather(temperature=-1.0))
        assert data["safe"] is False
        assert any("temperature" in r.lower() for r in data["reasons"])

    def test_temperature_too_high(self, client):
        data = self._check(client, make_weather(temperature=46.0))
        assert data["safe"] is False
        assert any("temperature" in r.lower() for r in data["reasons"])

    def test_thunderstorm_condition(self, client):
        data = self._check(client, make_weather(condition="Thunderstorm", description="thunderstorm with rain"))
        assert data["safe"] is False
        assert any("thunderstorm" in r.lower() for r in data["reasons"])

    def test_snow_condition(self, client):
        data = self._check(client, make_weather(condition="Snow", description="light snow"))
        assert data["safe"] is False
        assert any("snow" in r.lower() for r in data["reasons"])

    def test_heavy_rain_description(self, client):
        data = self._check(client, make_weather(condition="Rain", description="heavy rain"))
        assert data["safe"] is False
        assert any("heavy rain" in r.lower() or "unsafe" in r.lower() for r in data["reasons"])

    def test_multiple_violations_all_reported(self, client):
        """When several thresholds are breached, every reason must be present."""
        data = self._check(
            client,
            make_weather(windSpeed=15.0, visibility=200, temperature=-5.0),
        )
        assert data["safe"] is False
        assert len(data["reasons"]) >= 3


# ---------------------------------------------------------------------------
# GET /weather/current
# ---------------------------------------------------------------------------

class TestWeatherCurrent:
    def test_returns_weather_data(self, client):
        weather = make_weather()
        get_cache, set_cache = no_cache()

        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch(weather)),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/current?lat=1.3&lon=103.8")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "api"
        assert "safe" not in data          # no safety fields on this endpoint
        assert "reasons" not in data
        assert data["weather"]["condition"] == "Clear"

    def test_response_has_fetchedAt(self, client):
        get_cache, set_cache = no_cache()

        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch()),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/current?lat=1.3&lon=103.8")

        assert "fetchedAt" in resp.json()


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def test_cache_hit_returns_source_cache(self, client):
        weather = make_weather()
        from datetime import datetime, timezone

        cached_payload = {
            "weather": weather.model_dump(),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        }
        get_cache = AsyncMock(return_value=cached_payload)
        set_cache = AsyncMock()

        with (
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 200
        assert resp.json()["source"] == "cache"
        # set_cached must NOT be called on a hit
        set_cache.assert_not_called()

    def test_cache_miss_calls_api_and_stores_result(self, client):
        get_cache, set_cache = no_cache()

        with (
            patch("app.controllers.weather_controller.weather_service.fetch_current_weather", mock_fetch()) as mock_api,
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
            patch("app.controllers.weather_controller.cache_service.set_cached", set_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.json()["source"] == "api"
        mock_api.assert_awaited_once()
        set_cache.assert_awaited_once()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_openweather_401_returns_502(self, client):
        get_cache, _ = no_cache()

        with (
            patch(
                "app.controllers.weather_controller.weather_service.fetch_current_weather",
                AsyncMock(side_effect=OpenWeatherError(401, "Invalid API key")),
            ),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 502
        assert resp.json()["error"] == "upstream_api_error"

    def test_openweather_429_returns_503(self, client):
        get_cache, _ = no_cache()

        with (
            patch(
                "app.controllers.weather_controller.weather_service.fetch_current_weather",
                AsyncMock(side_effect=OpenWeatherError(429, "Too many requests")),
            ),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 503

    def test_network_error_returns_503(self, client):
        import httpx

        get_cache, _ = no_cache()

        with (
            patch(
                "app.controllers.weather_controller.weather_service.fetch_current_weather",
                AsyncMock(side_effect=httpx.ConnectError("unreachable")),
            ),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 503
        assert resp.json()["error"] == "upstream_unavailable"

    def test_missing_api_key_returns_500(self, client):
        get_cache, _ = no_cache()

        with (
            patch(
                "app.controllers.weather_controller.weather_service.fetch_current_weather",
                AsyncMock(side_effect=ValueError("OPENWEATHER_API_KEY environment variable is not set")),
            ),
            patch("app.controllers.weather_controller.cache_service.get_cached", get_cache),
        ):
            resp = client.get("/weather/check?lat=1.3&lon=103.8")

        assert resp.status_code == 500
        assert resp.json()["error"] == "configuration_error"

    def test_invalid_lat_returns_422(self, client):
        resp = client.get("/weather/check?lat=999&lon=103.8")
        assert resp.status_code == 422

    def test_missing_query_params_returns_422(self, client):
        resp = client.get("/weather/check")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# safety_service — direct unit tests (no HTTP layer)
# ---------------------------------------------------------------------------

class TestSafetyService:
    def test_all_safe(self):
        safe, reasons = evaluate_safety(make_weather())
        assert safe is True
        assert reasons == []

    def test_boundary_wind_speed_at_limit_is_safe(self):
        safe, _ = evaluate_safety(make_weather(windSpeed=10.0))
        assert safe is True

    def test_boundary_wind_speed_above_limit_is_unsafe(self):
        safe, _ = evaluate_safety(make_weather(windSpeed=10.1))
        assert safe is False

    def test_boundary_visibility_at_limit_is_safe(self):
        safe, _ = evaluate_safety(make_weather(visibility=1000))
        assert safe is True

    def test_boundary_visibility_below_limit_is_unsafe(self):
        safe, _ = evaluate_safety(make_weather(visibility=999))
        assert safe is False

    def test_boundary_temp_at_min_is_safe(self):
        safe, _ = evaluate_safety(make_weather(temperature=0.0))
        assert safe is True

    def test_boundary_temp_below_min_is_unsafe(self):
        safe, _ = evaluate_safety(make_weather(temperature=-0.1))
        assert safe is False

    def test_boundary_temp_at_max_is_safe(self):
        safe, _ = evaluate_safety(make_weather(temperature=45.0))
        assert safe is True

    def test_boundary_temp_above_max_is_unsafe(self):
        safe, _ = evaluate_safety(make_weather(temperature=45.1))
        assert safe is False

    def test_tornado_description_is_unsafe(self):
        safe, reasons = evaluate_safety(make_weather(condition="Tornado", description="tornado"))
        assert safe is False

    def test_squall_description_is_unsafe(self):
        safe, reasons = evaluate_safety(make_weather(description="squall"))
        assert safe is False

    def test_drizzle_is_safe(self):
        """Light rain that doesn't match any unsafe keyword should be safe."""
        safe, _ = evaluate_safety(make_weather(condition="Drizzle", description="light intensity drizzle"))
        assert safe is True

"""
Safety thresholds and global configuration constants.

All drone-flight limits are defined here as named constants so they
can be adjusted in one place without hunting through business logic.
"""

# ---------------------------------------------------------------------------
# Drone flight safety thresholds
# ---------------------------------------------------------------------------

MAX_WIND_SPEED_MS: float = 10.0
"""Wind speed ceiling in metres per second. Above this value flight is unsafe."""

MIN_VISIBILITY_M: int = 1_000
"""Minimum acceptable visibility in metres. Below this value flight is unsafe."""

MIN_TEMP_C: float = 0.0
"""Minimum safe operating temperature in degrees Celsius."""

MAX_TEMP_C: float = 45.0
"""Maximum safe operating temperature in degrees Celsius."""

UNSAFE_CONDITION_MAINS: frozenset[str] = frozenset({"Thunderstorm", "Snow"})
"""
OpenWeather 'main' condition labels that unconditionally ground drones.
Checked against the ``weather[0].main`` field of the API response.
"""

UNSAFE_DESCRIPTION_KEYWORDS: tuple[str, ...] = (
    "heavy rain",
    "heavy intensity rain",
    "very heavy rain",
    "extreme rain",
    "freezing rain",
    "storm",
    "tornado",
    "squall",
    "blizzard",
)
"""
Sub-strings matched against the lower-cased OpenWeather description.
Any match flags the condition as unsafe even when 'main' is not in
UNSAFE_CONDITION_MAINS (e.g. heavy rain sits under main='Rain').
"""

# ---------------------------------------------------------------------------
# Redis cache settings
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS: int = 300
"""How long a cached weather entry lives in Redis (5 minutes)."""

CACHE_KEY_PREFIX: str = "weather"
"""Namespace prefix for all Redis cache keys managed by this service."""

COORD_PRECISION: int = 2
"""
Decimal places used when rounding lat/lon before building a cache key.
Rounding to 2 d.p. groups requests within ~1.1 km of each other.
"""

# ---------------------------------------------------------------------------
# OpenWeather API
# ---------------------------------------------------------------------------

OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
"""Base URL for the OpenWeather Current Weather v2.5 API."""

DEFAULT_VISIBILITY_M: int = 10_000
"""
Fallback visibility in metres when OpenWeather omits the field.
The API caps reported visibility at 10 000 m, so this is a safe default.
"""

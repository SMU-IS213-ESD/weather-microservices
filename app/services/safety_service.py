"""
Drone flight safety evaluation logic.

Each threshold is checked independently so that every violated condition
is returned to the caller — not just the first one encountered.  This
gives operators a complete picture of why a flight is grounded.
"""

from app.config.constants import (
    MAX_WIND_SPEED_MS,
    MIN_VISIBILITY_M,
    MIN_TEMP_C,
    MAX_TEMP_C,
    UNSAFE_CONDITION_MAINS,
    UNSAFE_DESCRIPTION_KEYWORDS,
)
from app.models.weather_models import WeatherData


def evaluate_safety(weather: WeatherData) -> tuple[bool, list[str]]:
    """
    Determine whether current weather conditions permit safe drone flight.

    Checks (in order):
      1. Wind speed against :data:`MAX_WIND_SPEED_MS`
      2. Visibility against :data:`MIN_VISIBILITY_M`
      3. Temperature lower-bound :data:`MIN_TEMP_C`
      4. Temperature upper-bound :data:`MAX_TEMP_C`
      5. OpenWeather ``main`` label against :data:`UNSAFE_CONDITION_MAINS`
      6. OpenWeather ``description`` against :data:`UNSAFE_DESCRIPTION_KEYWORDS`

    :param weather: Normalised reading from the weather service.
    :returns: A ``(safe, reasons)`` tuple where *reasons* contains one
              human-readable string per violated threshold and *safe* is
              ``True`` only when *reasons* is empty.
    """
    reasons: list[str] = []

    # --- Wind speed ---
    if weather.windSpeed > MAX_WIND_SPEED_MS:
        reasons.append(
            f"Wind speed {weather.windSpeed} m/s exceeds the {MAX_WIND_SPEED_MS} m/s limit"
        )

    # --- Visibility ---
    if weather.visibility < MIN_VISIBILITY_M:
        reasons.append(
            f"Visibility {weather.visibility} m is below the {MIN_VISIBILITY_M} m minimum"
        )

    # --- Temperature lower bound ---
    if weather.temperature < MIN_TEMP_C:
        reasons.append(
            f"Temperature {weather.temperature}°C is below the {MIN_TEMP_C}°C minimum"
        )

    # --- Temperature upper bound ---
    if weather.temperature > MAX_TEMP_C:
        reasons.append(
            f"Temperature {weather.temperature}°C exceeds the {MAX_TEMP_C}°C maximum"
        )

    # --- Weather condition (main label takes priority over description) ---
    if weather.condition in UNSAFE_CONDITION_MAINS:
        reasons.append(
            f"Weather condition '{weather.condition}' is not safe for drone flight"
        )
    else:
        description_lower = weather.description.lower()
        matched_keyword = next(
            (kw for kw in UNSAFE_DESCRIPTION_KEYWORDS if kw in description_lower),
            None,
        )
        if matched_keyword:
            reasons.append(
                f"Weather description indicates unsafe conditions: '{weather.description}'"
            )

    return len(reasons) == 0, reasons

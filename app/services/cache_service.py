"""
Redis-backed cache for weather API responses.

Keys are namespaced under ``weather:<lat>:<lon>`` where coordinates are
rounded to :data:`~app.config.constants.COORD_PRECISION` decimal places,
grouping requests within ~1.1 km of each other into a single cache entry.

Redis failures are caught and logged rather than re-raised so that a
Redis outage never blocks the primary request path — the service simply
falls back to live API calls.
"""

import json
import logging
import os

import redis.asyncio as aioredis

from app.config.constants import CACHE_TTL_SECONDS, CACHE_KEY_PREFIX, COORD_PRECISION

logger = logging.getLogger(__name__)

# Module-level singleton initialised lazily on first use.
_redis_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    """
    Return the shared Redis client, creating it on first call.

    Connection settings are read from ``REDIS_HOST`` / ``REDIS_PORT``
    environment variables with sensible defaults for local development.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
    return _redis_client


def build_cache_key(lat: float, lon: float) -> str:
    """
    Build a Redis key for the given coordinate pair.

    :param lat: Latitude in decimal degrees.
    :param lon: Longitude in decimal degrees.
    :returns: A string key, e.g. ``"weather:1.30:103.80"``.
    """
    lat_r = round(lat, COORD_PRECISION)
    lon_r = round(lon, COORD_PRECISION)
    return f"{CACHE_KEY_PREFIX}:{lat_r}:{lon_r}"


async def get_cached(key: str) -> dict | None:
    """
    Retrieve a cached entry by key.

    :param key: Redis key produced by :func:`build_cache_key`.
    :returns: Deserialised dict on a cache hit, ``None`` on a miss or
              when Redis is unreachable.
    """
    try:
        raw = await _get_client().get(key)
        if raw:
            return json.loads(raw)
        return None
    except Exception as exc:
        logger.warning("Redis GET failed — continuing without cache: %s", exc)
        return None


async def set_cached(key: str, value: dict, ttl: int = CACHE_TTL_SECONDS) -> None:
    """
    Persist *value* under *key* with an expiry of *ttl* seconds.

    :param key:   Redis key produced by :func:`build_cache_key`.
    :param value: Dict to JSON-serialise and store.
    :param ttl:   Time-to-live in seconds (default: ``CACHE_TTL_SECONDS``).
    """
    try:
        await _get_client().setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("Redis SET failed — response will not be cached: %s", exc)

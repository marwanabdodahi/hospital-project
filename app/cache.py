import json

import redis

from app.logger import logger

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def get_cache(key):
    """Return the cached value, or None if it is missing or Redis is unavailable."""
    try:
        data = r.get(key)
        return json.loads(data) if data else None
    except (redis.RedisError, ValueError) as e:
        logger.warning("Cache read failed for %s: %s", key, e)
        return None


def set_cache(key, value, seconds=60):
    try:
        r.set(key, json.dumps(value, default=str), ex=seconds)
    except (redis.RedisError, TypeError) as e:
        logger.warning("Cache write failed for %s: %s", key, e)


def delete_cache(*keys):
    try:
        r.delete(*keys)
    except redis.RedisError as e:
        logger.warning("Cache delete failed for %s: %s", keys, e)


def cached(key, build):
    """Return the cached value for key, otherwise build it, store it and return it."""
    value = get_cache(key)
    if value is None:
        value = build()
        set_cache(key, value)
    return value

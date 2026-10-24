# Cliente Upstash REST compartido por cache y rate limit
from upstash_redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


def obtener_upstash() -> Redis | None:
    """Devuelve el cliente Upstash, o None si faltan URL/token."""
    global _redis

    if not settings.upstash_redis_rest_url or not settings.upstash_redis_rest_token:
        return None

    if _redis is None:
        _redis = Redis(
            url=settings.upstash_redis_rest_url.rstrip("/"),
            token=settings.upstash_redis_rest_token,
            rest_retries=0,
            allow_telemetry=False,
        )

    return _redis


async def cerrar_upstash() -> None:
    global _redis

    if _redis is not None:
        await _redis.close()
        _redis = None

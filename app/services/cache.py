# Cache de recetas: memoria o Upstash REST, con fallback
import asyncio
import logging
from collections import OrderedDict
from hashlib import sha256
from time import monotonic
from typing import Protocol

import httpx
from pydantic import ValidationError
from upstash_redis.errors import UpstashError

from app.core.config import settings
from app.core.upstash import obtener_upstash
from app.schemas.interpret import RespuestaInterpretacion

logger = logging.getLogger(__name__)

PREFIJO_CACHE = f"{settings.app_namespace}:{settings.app_env}:cache:recipe:"


def normalizar_prompt(prompt: str) -> str:
    """Normaliza para que mayúsculas y espacios no rompan el cache."""
    return " ".join(prompt.strip().lower().split())


def clave_prompt(prompt: str) -> str:
    """Devuelve un hash: el prompt crudo no se guarda."""
    return sha256(normalizar_prompt(prompt).encode("utf-8")).hexdigest()


class CacheBackend(Protocol):
    async def obtener(self, clave: str) -> RespuestaInterpretacion | None: ...

    async def guardar(self, clave: str, receta: RespuestaInterpretacion) -> None: ...

    async def limpiar(self) -> None: ...


class CacheTTL[T]:
    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._datos: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def obtener(self, clave: str) -> T | None:
        entrada = self._datos.get(clave)

        if entrada is None:
            return None

        expira, valor = entrada

        if monotonic() >= expira:
            self._datos.pop(clave, None)
            return None

        self._datos.move_to_end(clave)

        return valor

    def guardar(self, clave: str, valor: T) -> None:
        self._datos[clave] = (monotonic() + self._ttl, valor)
        self._datos.move_to_end(clave)

        while len(self._datos) > self._max:
            self._datos.popitem(last=False)

    def limpiar(self) -> None:
        self._datos.clear()


class MemoryCache:
    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        self._cache: CacheTTL[RespuestaInterpretacion] = CacheTTL(
            ttl_seconds,
            max_entries,
        )

    async def obtener(self, clave: str) -> RespuestaInterpretacion | None:
        return self._cache.obtener(clave)

    async def guardar(self, clave: str, receta: RespuestaInterpretacion) -> None:
        self._cache.guardar(clave, receta)

    async def limpiar(self) -> None:
        self._cache.limpiar()


class UpstashCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds

    async def obtener(self, clave: str) -> RespuestaInterpretacion | None:
        redis = obtener_upstash()

        if redis is None:
            raise UpstashError("Upstash no configurado")

        completa = f"{PREFIJO_CACHE}{clave}"
        raw = await asyncio.wait_for(
            redis.get(completa),
            timeout=settings.upstash_timeout_seconds,
        )

        if raw is None:
            return None

        try:
            return RespuestaInterpretacion.model_validate_json(raw)
        except ValidationError:
            await asyncio.wait_for(
                redis.delete(completa),
                timeout=settings.upstash_timeout_seconds,
            )
            return None

    async def guardar(self, clave: str, receta: RespuestaInterpretacion) -> None:
        redis = obtener_upstash()

        if redis is None:
            raise UpstashError("Upstash no configurado")

        await asyncio.wait_for(
            redis.set(
                f"{PREFIJO_CACHE}{clave}",
                receta.model_dump_json(),
                ex=self._ttl,
            ),
            timeout=settings.upstash_timeout_seconds,
        )

    async def limpiar(self) -> None:
        redis = obtener_upstash()

        if redis is None:
            return

        claves = await asyncio.wait_for(
            redis.keys(f"{PREFIJO_CACHE}*"),
            timeout=settings.upstash_timeout_seconds,
        )

        if claves:
            await asyncio.wait_for(
                redis.delete(*claves),
                timeout=settings.upstash_timeout_seconds,
            )


class CacheConFallback:
    def __init__(self, primario: CacheBackend, respaldo: CacheBackend) -> None:
        self._primario = primario
        self._respaldo = respaldo

    async def obtener(self, clave: str) -> RespuestaInterpretacion | None:
        try:
            return await self._primario.obtener(clave)
        except (UpstashError, httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            logger.warning("Upstash cache falló al leer: %s", exc)
            return await self._respaldo.obtener(clave)

    async def guardar(self, clave: str, receta: RespuestaInterpretacion) -> None:
        try:
            await self._primario.guardar(clave, receta)
        except (UpstashError, httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            logger.warning("Upstash cache falló al guardar: %s", exc)
            await self._respaldo.guardar(clave, receta)

    async def limpiar(self) -> None:
        try:
            await self._primario.limpiar()
        except (UpstashError, httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            logger.warning("Upstash cache falló al limpiar: %s", exc)

        await self._respaldo.limpiar()


def _crear_cache() -> CacheBackend:
    memoria = MemoryCache(settings.cache_ttl_seconds, settings.cache_max_entries)

    if settings.cache_backend == "upstash":
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            return CacheConFallback(
                UpstashCache(settings.cache_ttl_seconds),
                memoria,
            )

        logger.warning("CACHE_BACKEND=upstash sin URL/token; usando memoria")

    return memoria


cache_recetas: CacheBackend = _crear_cache()


async def obtener_receta(prompt: str) -> RespuestaInterpretacion | None:
    if not settings.cache_enabled:
        return None

    return await cache_recetas.obtener(clave_prompt(prompt))


async def guardar_receta(prompt: str, receta: RespuestaInterpretacion) -> None:
    if not settings.cache_enabled:
        return

    await cache_recetas.guardar(clave_prompt(prompt), receta)


async def limpiar_cache() -> None:
    await cache_recetas.limpiar()

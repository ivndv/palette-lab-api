# Rate limit: Upstash Redis con @upstash/ratelimit (SDK Python) y fallback en memoria
import asyncio
import logging
from collections import deque
from math import ceil
from time import monotonic, time

import httpx
from fastapi import HTTPException, Request
from upstash_ratelimit import Response
from upstash_ratelimit.asyncio import Ratelimit, SlidingWindow
from upstash_redis.errors import UpstashError

from app.core.config import settings
from app.core.upstash import obtener_upstash

logger = logging.getLogger(__name__)

_aviso_fallback = False


class Limitador:
    def __init__(self) -> None:
        self._eventos: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def verificar(self, clave: str) -> None:
        ahora = monotonic()

        async with self._lock:
            # 1. Limpia eventos de más de 24 horas
            eventos = self._eventos.setdefault(clave, deque())

            while eventos and ahora - eventos[0] >= 86_400:
                eventos.popleft()

            # 2. Comprueba la ventana de un minuto
            recientes = [instante for instante in eventos if ahora - instante < 60]

            if settings.rate_limit_per_min > 0 and len(recientes) >= settings.rate_limit_per_min:
                espera = max(1, int(60 - (ahora - recientes[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Demasiadas peticiones. Inténtalo más tarde.",
                    headers={"Retry-After": str(espera)},
                )

            # 3. Comprueba la ventana diaria
            if settings.rate_limit_per_day > 0 and len(eventos) >= settings.rate_limit_per_day:
                espera = max(1, int(86_400 - (ahora - eventos[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Límite diario alcanzado.",
                    headers={"Retry-After": str(espera)},
                )

            eventos.append(ahora)

    def reiniciar(self) -> None:
        self._eventos.clear()


limitador = Limitador()


def _prefijo() -> str:
    return f"{settings.app_namespace}:{settings.app_env}:rl"


def _crear_limitadores(redis) -> tuple[Ratelimit, Ratelimit, Ratelimit]:
    prefijo = _prefijo()

    return (
        Ratelimit(
            redis=redis,
            limiter=SlidingWindow(settings.rate_limit_per_min, 1, "m"),
            prefix=f"{prefijo}:minuto",
        ),
        Ratelimit(
            redis=redis,
            limiter=SlidingWindow(settings.rate_limit_per_day, 1, "d"),
            prefix=f"{prefijo}:dia",
        ),
        Ratelimit(
            redis=redis,
            limiter=SlidingWindow(settings.rate_limit_global_per_day, 1, "d"),
            prefix=f"{prefijo}:global",
        ),
    )


def _rechazar(mensaje: str, respuesta: Response) -> None:
    espera = max(1, int(ceil(respuesta.reset - time())))
    raise HTTPException(
        status_code=429,
        detail=mensaje,
        headers={"Retry-After": str(espera)},
    )


async def _consumir(limitador_actual: Ratelimit, identificador: str) -> Response:
    return await asyncio.wait_for(
        limitador_actual.limit(identificador),
        timeout=settings.upstash_timeout_seconds,
    )


async def _limitar_upstash(clave: str) -> None:
    redis = obtener_upstash()

    if redis is None:
        raise UpstashError("Upstash no configurado")

    minuto, dia, global_dia = _crear_limitadores(redis)

    respuesta_minuto = await _consumir(minuto, clave)
    if not respuesta_minuto.allowed:
        _rechazar("Demasiadas peticiones. Inténtalo más tarde.", respuesta_minuto)

    respuesta_dia = await _consumir(dia, clave)
    if not respuesta_dia.allowed:
        _rechazar("Límite diario alcanzado.", respuesta_dia)

    respuesta_global = await _consumir(global_dia, "global")
    if not respuesta_global.allowed:
        _rechazar(
            "El servicio alcanzó su límite diario. Inténtalo de nuevo mañana.",
            respuesta_global,
        )


def obtener_cliente(request: Request) -> str:
    """Usa la IP que reenvía el BFF; si no, la conexión directa."""
    return request.headers.get("x-client-ip") or (
        request.client.host if request.client else "desconocido"
    )


async def limitar_peticiones(request: Request) -> None:
    global _aviso_fallback

    clave = obtener_cliente(request)

    if (
        settings.rate_limit_backend == "upstash"
        and settings.upstash_redis_rest_url
        and settings.upstash_redis_rest_token
    ):
        try:
            await _limitar_upstash(clave)
            return
        except HTTPException:
            raise
        except (UpstashError, httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            if not _aviso_fallback:
                logger.warning("Upstash rate limit falló; usando memoria: %s", exc)
                _aviso_fallback = True

    await limitador.verificar(clave)

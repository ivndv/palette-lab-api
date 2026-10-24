import asyncio
from time import time

import pytest
from fastapi import HTTPException
from upstash_ratelimit import Response

from app import rate_limit
from app.core.config import settings


class FakeLimitador:
    def __init__(self, allowed: bool = True, reset: float | None = None) -> None:
        self.allowed = allowed
        self.reset = reset if reset is not None else time() + 60
        self.llamadas: list[str] = []

    async def limit(self, identificador: str) -> Response:
        self.llamadas.append(identificador)
        return Response(
            allowed=self.allowed,
            limit=10,
            remaining=0 if not self.allowed else 9,
            reset=self.reset,
        )


def _preparar(monkeypatch, minuto: FakeLimitador, dia: FakeLimitador, global_: FakeLimitador):
    monkeypatch.setattr(rate_limit, "obtener_upstash", lambda: object())
    monkeypatch.setattr(
        rate_limit,
        "_crear_limitadores",
        lambda _redis: (minuto, dia, global_),
    )


def test_upstash_rate_limit_permite(monkeypatch) -> None:
    minuto = FakeLimitador()
    dia = FakeLimitador()
    global_ = FakeLimitador()
    _preparar(monkeypatch, minuto, dia, global_)

    asyncio.run(rate_limit._limitar_upstash("1.2.3.4"))

    assert minuto.llamadas == ["1.2.3.4"]
    assert dia.llamadas == ["1.2.3.4"]
    assert global_.llamadas == ["global"]


def test_upstash_rate_limit_bloquea_por_minuto(monkeypatch) -> None:
    minuto = FakeLimitador(allowed=False, reset=time() + 60)
    dia = FakeLimitador()
    global_ = FakeLimitador()
    _preparar(monkeypatch, minuto, dia, global_)
    monkeypatch.setattr(settings, "rate_limit_per_min", 1)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(rate_limit._limitar_upstash("1.2.3.4"))

    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
    assert dia.llamadas == []
    assert global_.llamadas == []


def test_upstash_rate_limit_bloquea_por_dia(monkeypatch) -> None:
    minuto = FakeLimitador()
    dia = FakeLimitador(allowed=False, reset=time() + 3600)
    global_ = FakeLimitador()
    _preparar(monkeypatch, minuto, dia, global_)
    monkeypatch.setattr(settings, "rate_limit_per_day", 1)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(rate_limit._limitar_upstash("1.2.3.4"))

    assert exc.value.status_code == 429
    assert global_.llamadas == []

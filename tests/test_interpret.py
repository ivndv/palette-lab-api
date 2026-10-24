import asyncio

from httpx import Request, Response
from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.core.config import settings
from app.rate_limit import limitador
from app.routers import interpret as router_interpret
from app.schemas.interpret import RespuestaInterpretacion
from app.services import ia
from app.services.cache import cache_recetas


def _receta() -> RespuestaInterpretacion:
    return RespuestaInterpretacion(
        base="#B45309",
        mode="analogous",
        tone="muted",
        label="café cálido",
    )


def _error_rate_limit() -> RateLimitError:
    request = Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = Response(429, request=request)
    return RateLimitError("Límite de Groq", response=response, body=None)


def test_interpret_ok(client, monkeypatch) -> None:
    async def receta_falsa(prompt: str) -> RespuestaInterpretacion:
        return _receta()

    monkeypatch.setattr(router_interpret, "interpretar_palette", receta_falsa)

    res = client.post("/interpret", json={"prompt": "café artesanal"})

    assert res.status_code == 200
    assert res.json() == {
        "base": "#b45309",
        "mode": "analogous",
        "tone": "muted",
        "label": "café cálido",
    }


def test_interpret_prompt_vacio(client) -> None:
    res = client.post("/interpret", json={"prompt": ""})

    assert res.status_code == 422


def test_interpret_prompt_largo(client) -> None:
    res = client.post("/interpret", json={"prompt": "x" * 241})

    assert res.status_code == 400


def test_interpret_prompt_en_blanco(client) -> None:
    res = client.post("/interpret", json={"prompt": "   "})

    assert res.status_code == 400


def test_interpret_error_de_ia(client, monkeypatch) -> None:
    async def explota(prompt: str) -> RespuestaInterpretacion:
        raise RuntimeError("boom")

    monkeypatch.setattr(router_interpret, "interpretar_palette", explota)

    res = client.post("/interpret", json={"prompt": "café"})

    assert res.status_code == 502


def test_interpret_receta_invalida(client, monkeypatch) -> None:
    async def invalida(prompt: str) -> RespuestaInterpretacion:
        raise ValueError("La IA no devolvió una receta válida.")

    monkeypatch.setattr(router_interpret, "interpretar_palette", invalida)

    res = client.post("/interpret", json={"prompt": "café"})

    assert res.status_code == 502


def test_interpret_error_rate_limit(client, monkeypatch) -> None:
    async def falla(prompt: str) -> RespuestaInterpretacion:
        raise _error_rate_limit()

    monkeypatch.setattr(router_interpret, "interpretar_palette", falla)

    res = client.post("/interpret", json={"prompt": "café"})

    assert res.status_code == 429


def test_interpret_error_timeout(client, monkeypatch) -> None:
    async def falla(prompt: str) -> RespuestaInterpretacion:
        request = Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        raise APITimeoutError(request=request)

    monkeypatch.setattr(router_interpret, "interpretar_palette", falla)

    res = client.post("/interpret", json={"prompt": "café"})

    assert res.status_code == 504


def test_interpret_error_conexion(client, monkeypatch) -> None:
    async def falla(prompt: str) -> RespuestaInterpretacion:
        request = Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        raise APIConnectionError(request=request)

    monkeypatch.setattr(router_interpret, "interpretar_palette", falla)

    res = client.post("/interpret", json={"prompt": "café"})

    assert res.status_code == 503


def test_cache_evita_repetir_la_ia(monkeypatch) -> None:
    asyncio.run(cache_recetas.limpiar())
    monkeypatch.setattr(settings, "mock_ai", True)
    llamadas = [0]

    def receta_falsa(prompt: str) -> RespuestaInterpretacion:
        llamadas[0] += 1
        return _receta()

    monkeypatch.setattr(ia, "_receta_mock", receta_falsa)

    first = asyncio.run(ia.interpretar_palette("café artesanal"))
    second = asyncio.run(ia.interpretar_palette("  CAFÉ   artesanal "))

    assert first == second
    assert llamadas[0] == 1


def test_interpret_rate_limit(client, monkeypatch) -> None:
    async def receta_falsa(prompt: str) -> RespuestaInterpretacion:
        return _receta()

    monkeypatch.setattr(router_interpret, "interpretar_palette", receta_falsa)
    monkeypatch.setattr(settings, "rate_limit_per_min", 1)
    limitador.reiniciar()

    first = client.post("/interpret", json={"prompt": "café"})
    second = client.post("/interpret", json={"prompt": "café"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"].isdigit()

import asyncio

from app.schemas.interpret import RespuestaInterpretacion
from app.services import cache as cache_mod
from app.services.cache import (
    CacheTTL,
    UpstashCache,
    clave_prompt,
    normalizar_prompt,
)


class FakeUpstash:
    def __init__(self) -> None:
        self.datos: dict[str, str] = {}

    async def get(self, clave: str) -> str | None:
        return self.datos.get(clave)

    async def set(self, clave: str, valor: str, ex: int | None = None) -> bool:
        self.datos[clave] = valor
        return True

    async def keys(self, patron: str) -> list[str]:
        return list(self.datos)

    async def delete(self, *claves: str) -> int:
        borradas = 0

        for clave in claves:
            if clave in self.datos:
                del self.datos[clave]
                borradas += 1

        return borradas


def test_normalizar_prompt() -> None:
    assert normalizar_prompt("  Café   ARTESANAL ") == "café artesanal"


def test_clave_prompt_es_estable_y_normaliza() -> None:
    assert clave_prompt("  Café   Artesanal ") == clave_prompt("café artesanal")
    assert clave_prompt("café") != clave_prompt("playa")


def test_cache_ttl_expira(monkeypatch) -> None:
    reloj = [100.0]
    monkeypatch.setattr(cache_mod, "monotonic", lambda: reloj[0])

    cache: CacheTTL[int] = CacheTTL(ttl_seconds=10, max_entries=2)
    cache.guardar("a", 1)

    assert cache.obtener("a") == 1

    reloj[0] = 111
    assert cache.obtener("a") is None


def test_cache_ttl_respeta_el_maximo_y_lru(monkeypatch) -> None:
    reloj = [100.0]
    monkeypatch.setattr(cache_mod, "monotonic", lambda: reloj[0])

    cache: CacheTTL[int] = CacheTTL(ttl_seconds=100, max_entries=2)
    cache.guardar("a", 1)
    cache.guardar("b", 2)

    # "a" pasa a ser el más reciente
    assert cache.obtener("a") == 1

    cache.guardar("c", 3)

    assert cache.obtener("a") == 1
    assert cache.obtener("b") is None
    assert cache.obtener("c") == 3


def test_cache_limpiar() -> None:
    cache: CacheTTL[int] = CacheTTL(ttl_seconds=100, max_entries=2)
    cache.guardar("a", 1)

    cache.limpiar()

    assert cache.obtener("a") is None


def test_upstash_cache_guarda_y_lee(monkeypatch) -> None:
    fake = FakeUpstash()
    monkeypatch.setattr(cache_mod, "obtener_upstash", lambda: fake)
    cache = UpstashCache(ttl_seconds=60)
    receta = RespuestaInterpretacion(
        base="#b45309",
        mode="analogous",
        tone="muted",
        label="café cálido",
    )

    asyncio.run(cache.guardar("clave", receta))

    assert asyncio.run(cache.obtener("clave")) == receta


def test_upstash_cache_borra_json_corrupto(monkeypatch) -> None:
    fake = FakeUpstash()
    monkeypatch.setattr(cache_mod, "obtener_upstash", lambda: fake)
    cache = UpstashCache(ttl_seconds=60)

    asyncio.run(fake.set(f"{cache_mod.PREFIJO_CACHE}clave", "{no-es-json"))

    assert asyncio.run(cache.obtener("clave")) is None
    assert asyncio.run(fake.get(f"{cache_mod.PREFIJO_CACHE}clave")) is None

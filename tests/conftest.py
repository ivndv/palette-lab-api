# Fixtures compartidas: aíslan los tests de la configuración local (.env)
import asyncio
import os

import pytest
from fastapi.testclient import TestClient

# Fuerza memoria en tests aunque el .env local tenga Upstash
os.environ["CACHE_BACKEND"] = "memory"
os.environ["RATE_LIMIT_BACKEND"] = "memory"
os.environ["UPSTASH_REDIS_REST_URL"] = ""
os.environ["UPSTASH_REDIS_REST_TOKEN"] = ""

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.rate_limit import limitador  # noqa: E402
from app.services.cache import cache_recetas  # noqa: E402


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    """Sin API key y con límites altos en cada test."""
    monkeypatch.setattr(settings, "palette_lab_api_key", "")
    monkeypatch.setattr(settings, "rate_limit_per_min", 1000)
    monkeypatch.setattr(settings, "rate_limit_per_day", 1000)
    monkeypatch.setattr(settings, "cache_enabled", True)
    limitador.reiniciar()
    asyncio.run(cache_recetas.limpiar())


@pytest.fixture
def client():
    return TestClient(app)

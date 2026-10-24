import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.upstash import cerrar_upstash, obtener_upstash
from app.routers import health, interpret

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = obtener_upstash()

    if redis is not None:
        try:
            await asyncio.wait_for(
                redis.ping(),
                timeout=settings.upstash_timeout_seconds,
            )
            logger.info("Upstash conectado")
        except Exception as exc:
            logger.warning("Upstash no disponible: %s", exc)

    yield

    await cerrar_upstash()


app = FastAPI(title="palette-lab-api", version="0.1.0", lifespan=lifespan)

# CORS: solo los orígenes de confianza.
# El front llama desde el BFF de Cloudflare Pages, así que esto es defensivo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origen.strip() for origen in settings.allowed_origins.split(",") if origen.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "X-Client-IP"],
)

app.include_router(health.router)
app.include_router(interpret.router)

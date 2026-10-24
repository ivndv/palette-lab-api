import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, APITimeoutError, BadRequestError, RateLimitError
from pydantic import ValidationError

from app.core.config import settings
from app.dependencies.security import verificar_api_key
from app.rate_limit import limitar_peticiones
from app.schemas.interpret import PeticionInterpretacion, RespuestaInterpretacion
from app.services.ia import interpretar_palette

logger = logging.getLogger(__name__)

router = APIRouter(tags=["paletas"])


@router.post(
    "/interpret",
    dependencies=[Depends(verificar_api_key), Depends(limitar_peticiones)],
)
async def interpret(peticion: PeticionInterpretacion) -> RespuestaInterpretacion:
    """Interpreta una descripción y devuelve base, armonía y tono."""
    # 1. Normaliza y rechaza descripciones vacías o enormes sin gastar cuota
    prompt = peticion.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail="La descripción no puede estar vacía.")

    if len(prompt) > settings.max_prompt_length:
        raise HTTPException(status_code=400, detail="La descripción es demasiado larga.")

    # 2. Pide la receta a la IA y traduce sus fallos a HTTP
    try:
        return await interpretar_palette(prompt)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail="La IA alcanzó su límite. Inténtalo más tarde.",
        ) from exc
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="La IA tardó demasiado en responder.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo conectar con la IA.",
        ) from exc
    except BadRequestError as exc:
        logger.error("Groq rechazó la petición: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="La IA rechazó la petición.",
        ) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="La IA devolvió una receta inválida.",
        ) from exc
    except Exception as exc:
        logger.exception("Fallo inesperado al interpretar la paleta")
        raise HTTPException(
            status_code=502,
            detail="La IA no respondió correctamente.",
        ) from exc

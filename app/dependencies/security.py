# Seguridad: X-API-Key (secreto compartido)
import secrets

from fastapi import Header, HTTPException

from app.core.config import settings


def verificar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Comprueba el secreto compartido del header X-API-Key."""
    # Sin secreto configurado no se exige (solo desarrollo local)
    if not settings.palette_lab_api_key:
        return

    # compare_digest evita timing attacks (comparar con == filtra información)
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.palette_lab_api_key):
        raise HTTPException(status_code=401, detail="API key inválida.")

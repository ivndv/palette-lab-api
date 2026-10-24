# Configuración del servicio (variables de entorno)
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Clave de la IA (secreta: solo vive aquí)
    groq_api_key: str = ""

    # Secreto compartido con Cloudflare Pages (header X-API-Key).
    # Si está vacío NO se exige (solo para desarrollo local).
    palette_lab_api_key: str = ""

    # Proveedor de IA (compatible con el SDK de OpenAI)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"
    # Menor que el timeout del BFF para que el 504 llegue antes
    groq_timeout_seconds: float = 8.0
    # gpt-oss razona antes de responder: necesita margen de tokens
    groq_max_tokens: int = 1500
    groq_reasoning_effort: str = "low"

    # Límites
    max_prompt_length: int = 240
    rate_limit_per_min: int = 10
    rate_limit_per_day: int = 100

    # Solo desarrollo: evita llamar a Groq y devuelve una receta fija
    mock_ai: bool = False

    # Cache de respuestas por prompt normalizado
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86_400
    cache_max_entries: int = 500

    # Upstash Redis (REST) para cache y rate limit
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    upstash_timeout_seconds: float = 1.5
    app_namespace: str = "palette"
    app_env: Literal["local", "staging", "production"] = "local"
    cache_backend: Literal["memory", "upstash"] = "memory"
    rate_limit_backend: Literal["memory", "upstash"] = "memory"
    rate_limit_global_per_day: int = 800

    # CORS: orígenes permitidos (separados por coma)
    allowed_origins: str = "http://localhost:5173"


settings = Settings()

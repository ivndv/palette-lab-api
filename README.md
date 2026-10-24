# Palette Lab API

Microservicio de interpretación de paletas con IA para **Palette Lab**.

Recibe una descripción en lenguaje natural y devuelve una receta válida:

```json
{
  "base": "#b45309",
  "mode": "analogous",
  "tone": "muted",
  "label": "café cálido"
}
```

La IA **no genera la paleta completa**. Solo elige el color base, la armonía y el tono; el motor determinista de Palette Lab genera los cinco colores.

## Stack

- FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings
- Groq vía SDK de OpenAI
- Docker
- pytest + ruff

## Endpoints

- `GET /health` → `{"status":"ok"}`
- `POST /interpret` → receta de paleta
  - Header `X-API-Key` si `PALETTE_LAB_API_KEY` está configurado
  - Body: `{"prompt":"café artesanal"}`
  - Errores: `400`, `401`, `429`, `502`, `503`, `504`

## Desarrollo local

```bash
make install
cp .env.example .env
# Opción A: rellena GROQ_API_KEY en .env
make dev

# Opción B: sin Groq, con recetas mock
MOCK_AI=true make dev
```

Swagger: `http://localhost:8010/docs`

## Tests

```bash
make test
```

Los tests mockean la IA: nunca gastan cuota de Groq.

## Docker

```bash
make docker-build
make docker-run
```

El contenedor escucha en `8000`; con `make docker-run` queda publicado en `8010` para no chocar con `codebook-api`. Expone `GET /health` para el healthcheck.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `GROQ_API_KEY` | Clave de Groq. Solo vive en este servicio. |
| `PALETTE_LAB_API_KEY` | Secreto compartido con el BFF. Si está vacío, no se exige. |
| `RATE_LIMIT_PER_MIN` | Peticiones por minuto. Default `10`. |
| `RATE_LIMIT_PER_DAY` | Peticiones por día. Default `100`. |
| `ALLOWED_ORIGINS` | Orígenes CORS separados por coma. |
| `MOCK_AI` | Solo local: devuelve recetas fijas sin llamar a Groq. |
| `CACHE_ENABLED` | Activa el cache de respuestas. Default `true`. |
| `CACHE_TTL_SECONDS` | Vida del cache. Default `86400` (24 h). |
| `CACHE_MAX_ENTRIES` | Máximo de prompts cacheados en memoria. Default `500`. |
| `UPSTASH_REDIS_REST_URL` | URL REST de Upstash. |
| `UPSTASH_REDIS_REST_TOKEN` | Token REST de Upstash. |
| `UPSTASH_TIMEOUT_SECONDS` | Timeout de Upstash. Default `1.5`. |
| `APP_NAMESPACE` | Prefijo de llaves. Default `palette`. |
| `APP_ENV` | `local`, `staging` o `production`. |
| `CACHE_BACKEND` | `memory` o `upstash`. Default `memory`. |
| `RATE_LIMIT_BACKEND` | `memory` o `upstash`. Default `memory`. |
| `RATE_LIMIT_GLOBAL_PER_DAY` | Límite global diario. Default `800`. |

## Cache y rate limit

Las respuestas exitosas se cachean por hash del prompt normalizado:

- Mismo prompt → misma receta, sin llamar a Groq.
- TTL de 24 horas.
- En memoria o Upstash REST.
- Si Upstash falla, se usa memoria como fallback.
- Upstash también guarda los contadores del rate limit.

El rate limit usa el SDK oficial `upstash-ratelimit` con ventanas deslizantes:

- 10 por minuto.
- 100 por día por IP.
- 800 por día global.

Prefijos:

```text
palette:<env>:rl:minuto:<ip>
palette:<env>:rl:dia:<ip>
palette:<env>:rl:global
palette:<env>:cache:recipe:<sha256>
```

Para producción con Upstash:

```env
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...
APP_NAMESPACE=palette
APP_ENV=production
CACHE_BACKEND=upstash
RATE_LIMIT_BACKEND=upstash
```

El system prompt está en inglés y acepta descripciones en español o inglés. La etiqueta se devuelve en español.

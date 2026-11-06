# AGENTS.md — Palette Lab API (`palette-lab-api`)

## 1. Visión general

**palette-lab-api** es un microservicio en **Python (FastAPI)** que convierte una descripción en lenguaje natural en una **receta de paleta**: color base, armonía, tono y etiqueta.

- **Propósito:** aislar la clave de IA y la llamada al modelo del BFF de Palette Lab.
- **Consumidor único:** `functions/api/interpret.ts` (Cloudflare Pages), vía `POST /interpret`.
- **La IA no genera la paleta completa:** solo elige base, armonía y tono. Los cinco colores los deriva el motor determinista del frontend.
- **Documentación de arquitectura:** [`docs/diseno-y-arquitectura.md`](docs/diseno-y-arquitectura.md).
- **Repositorio:** `palette-lab-api` · **Front:** `palette-lab`.

## 2. Antes de tocar código

- **Documentación de arquitectura:** lee `docs/diseno-y-arquitectura.md` antes de cambios estructurales.
- **Referencias:** [FastAPI](https://fastapi.tiangolo.com/), [Groq (compatible con el SDK de OpenAI)](https://console.groq.com/docs/openai) y [`upstash-ratelimit`](https://github.com/upstash/ratelimit-py).

**CodeGraph** (índice de símbolos del repo): usa `codegraph_explore` (`query`, `maxFiles`, `projectPath`) antes de un grep masivo o de leer varios archivos; devuelve fuente verbatim, rutas de llamada e impacto.

- `codegraph sync /home/ivan/software-dev/palette-lab-api` tras editar, pull o cambiar de rama (incremental, uso normal).
- `codegraph index /home/ivan/software-dev/palette-lab-api` solo al crear el índice, tras `codegraph upgrade` o si `status` avisa `built by vX` (rebuild completo).
- `codegraph status /home/ivan/software-dev/palette-lab-api` para comprobar el estado.

## 3. Stack tecnológico

| Capa | Tecnología | Detalle |
| :--- | :--- | :--- |
| **Framework** | **FastAPI** | ASGI, async, OpenAPI automático |
| **Servidor** | **Uvicorn** | `--host 0.0.0.0 --port $PORT` |
| **IA** | **Groq** vía SDK `openai` | `AsyncOpenAI` + JSON estricto |
| **Modelo** | `openai/gpt-oss-20b` | `reasoning_effort: low`, `max_tokens: 1500` |
| **Config** | **pydantic-settings** | `.env` tipado |
| **Cache** | **Memoria** o **Upstash REST** | TTL 24 h, 500 entradas |
| **Rate limit** | **`upstash-ratelimit`** | ventanas deslizantes + fallback en memoria |
| **Tests** | **pytest** | 23 pruebas, IA mockeada |
| **Lint/formato** | **ruff** | `line-length 100` |
| **Deploy** | **Docker / Dokploy** | puerto 8000 |
| **Python** | 3.13 | `pyproject.toml` |

## 4. Estructura del código

```plaintext
palette-lab-api/
├── app/
│   ├── main.py                  → app, CORS, lifespan de Upstash, routers
│   ├── rate_limit.py            → limitador por minuto, por día y global
│   ├── core/
│   │   ├── config.py            → settings (pydantic-settings)
│   │   └── upstash.py           → cliente Upstash perezoso y cierre limpio
│   ├── routers/
│   │   ├── health.py            → GET /health
│   │   └── interpret.py         → POST /interpret
│   ├── schemas/interpret.py     → Modo, Tono, Peticion, Respuesta
│   ├── services/
│   │   ├── ia.py                → prompt, cliente Groq, mock, cache
│   │   └── cache.py             → cache por hash de prompt
│   └── dependencies/security.py → X-API-Key
├── tests/                       → 23 pruebas (IA mockeada, Upstash simulado)
├── docs/                        → documentación de arquitectura
├── Makefile                     → install / dev / test / lint / docker
├── requirements.txt · requirements-dev.txt
├── pyproject.toml               → ruff + pytest
└── Dockerfile
```

## 5. Arquitectura y flujo de datos

### 5.1 Flujo de una interpretación

1. El BFF envía `POST /interpret` con la descripción del usuario y la cabecera `X-API-Key`.
2. `dependencies/security.py` valida la clave compartida.
3. `rate_limit.py` aplica los límites por minuto, por día y global.
4. `services/cache.py` busca una receta por el hash del prompt normalizado.
5. Si no hay cache, `services/ia.py` llama a Groq con JSON estricto y el prompt de sistema.
6. La respuesta se valida con Pydantic y solo entonces sale como receta (`base`, `mode`, `tone`, `label`).

### 5.2 Cache y rate limit

- El cache usa **hash del prompt normalizado**: mismo texto → misma receta sin llamar a Groq.
- Si Upstash falla, se degrada a memoria (con un único warning).
- Los prefijos de llaves son contrato operativo: `palette:<env>:rl:*` y `palette:<env>:cache:recipe:*`.
- `MOCK_AI=true` **solo** en local y en tests; nunca en producción.

## 6. Variables de entorno

Todas viven en `.env` (ignorado por Git); los nombres válidos están en `.env.example`.

| Grupo | Variables |
| :--- | :--- |
| **Groq** | `GROQ_API_KEY` |
| **Secreto del BFF** | `PALETTE_LAB_API_KEY` |
| **Límites** | `RATE_LIMIT_PER_MIN`, `RATE_LIMIT_PER_DAY`, `RATE_LIMIT_GLOBAL_PER_DAY` |
| **Desarrollo** | `MOCK_AI` |
| **Cache** | `CACHE_ENABLED`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ENTRIES`, `CACHE_BACKEND` |
| **Upstash** | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `UPSTASH_TIMEOUT_SECONDS`, `APP_NAMESPACE`, `APP_ENV`, `RATE_LIMIT_BACKEND` |
| **CORS** | `ALLOWED_ORIGINS` (defensivo: el BFF llama desde el servidor) |

## 7. Comandos

```bash
# Crea .venv e instala dependencias de desarrollo
make install

# Servidor con recarga automática (puerto 8010)
make dev

# Ejecuta los tests con cobertura
make test

# Revisa lint y formato (ruff)
make lint

# Formatea el código
make format

# Abre Swagger en el navegador
make docs

# Construye la imagen Docker local
make docker-build

# Corre la imagen local con el .env
make docker-run
```

Swagger: `http://localhost:8010/docs`.

## 8. Convenciones y reglas críticas

### 8.1 Ejecución de checks

- **Prohibido ejecutar tests o linter de forma reactiva tras cada pequeño cambio.** Acumula los cambios y corre `make lint` y `make test` **una sola vez al final**.

### 8.2 Estilo de código y comentarios

- **Lenguaje:** código, comentarios y documentación en **español**.
- **Comentarios:** `#` de **una sola línea**, en español, **sin punto final**.
- **Pasos numerados:** `# 1. …`, `# 2. …` en la lógica secuencial.
- **Tipado estricto:** anotaciones en todas las funciones; prohibido `Any` sin justificar.

### 8.3 Reglas de negocio

- **La IA solo devuelve la receta**, nunca los cinco colores.
- **La etiqueta va en español** y con máximo 60 caracteres.
- **`base` siempre en minúsculas** (`#rrggbb`); el schema lo normaliza.
- **`mode` y `tone` son enums cerrados**; no añadir valores sin actualizar el frontend (`palette-lab/src/lib/ai.ts`).
- **La respuesta se valida con Pydantic** antes de salir; nunca se reenvía el JSON crudo del modelo.
- **El prompt del sistema ignora instrucciones de cambio de rol o esquema** (defensa contra prompt injection).

## 9. Flujo de Git y despliegue

- **Prohibido** hacer commits o push sin la aprobación explícita del usuario.
- El desarrollo va en `develop`; el merge a `main` solo se hace tras aprobación.
- Mensajes de commit con *Conventional Commits*, en minúsculas y español (`feat: …`, `fix: …`, `chore: …`).
- El despliegue es con **Docker / Dokploy**, escuchando en el puerto 8000.

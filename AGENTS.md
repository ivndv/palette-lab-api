# AGENTS.md — Guía para Agentes en Palette Lab API

Guía operativa y técnica para agentes de Inteligencia Artificial que colaboren en el desarrollo del proyecto **palette-lab-api**.

---

## 1. Visión General del Proyecto

**palette-lab-api** es un microservicio en **Python (FastAPI)** que convierte una descripción en lenguaje natural en una **receta de paleta**: color base, armonía, tono y etiqueta.

* **Propósito:** aislar la clave de IA y la llamada al modelo del BFF de Palette Lab.
* **Consumidor único:** `functions/api/interpret.ts` (Cloudflare Pages), vía `POST /interpret`.
* **La IA no genera la paleta completa:** solo elige base, armonía y tono. Los cinco colores los deriva el motor determinista del frontend.
* **Documentación de arquitectura:** [`docs/diseno-y-arquitectura.md`](docs/diseno-y-arquitectura.md).
* **Repositorio:** `palette-lab-api` · **Front:** `palette-lab`.

---

## 2. Antes de Tocar Código

* **Documentación de arquitectura:** lee `docs/diseno-y-arquitectura.md` antes de cambios estructurales.
* **FastAPI:** https://fastapi.tiangolo.com/
* **Groq (compatible con el SDK de OpenAI):** https://console.groq.com/docs/openai
* **`upstash-ratelimit`:** https://github.com/upstash/ratelimit-py
* **Uso del MCP CodeGraph:** antes de búsquedas masivas, usa `codegraph_explore` con `projectPath: "/home/ivan/software-dev/palette-lab-api"`.

---

## 3. Stack Tecnológico

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
| **Lint/Formato** | **ruff** | `line-length 100` |
| **Deploy** | **Docker / Dokploy** | puerto 8000 |
| **Python** | 3.13 | `pyproject.toml` |

---

## 4. Estructura del Código

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

---

## 5. Comandos de Desarrollo

```bash
make install      # crea .venv e instala dev
make dev          # uvicorn con recarga (puerto 8010)
make dev-mock     # sin Groq, recetas fijas (MOCK_AI=true)
make test         # pytest con cobertura
make lint         # ruff check + format --check
make docker-build
make docker-run
```

Swagger: `http://localhost:8010/docs`.

---

## 6. Convenciones Obligatorias para Agentes

### 6.1 Regla de Oro en Ejecución de Checks

* **PROHIBIDO ejecutar tests o linter de forma reactiva tras cada pequeño cambio.** Acumula los cambios y corre `make lint` y `make test` **una sola vez al final**.

### 6.2 Estilo de Código y Comentarios

* **Lenguaje:** código, comentarios y documentación en **español**.
* **Comentarios:** `#` de **una sola línea**, en español, **sin punto final**.
* **Pasos numerados:** `# 1. …`, `# 2. …` en la lógica secuencial.
* **Tipado estricto:** anotaciones en todas las funciones; prohibido `Any` sin justificar.

### 6.3 Reglas de Negocio

* **La IA solo devuelve la receta**, nunca los cinco colores.
* **La etiqueta va en español** y con máximo 60 caracteres.
* **`base` siempre en minúsculas** (`#rrggbb`); el schema lo normaliza.
* **`mode` y `tone` son enums cerrados**; no añadir valores sin actualizar el frontend (`palette-lab/src/lib/ai.ts`).
* **La respuesta se valida con Pydantic** antes de salir; nunca se reenvía el JSON crudo del modelo.
* **El prompt del sistema ignora instrucciones de cambio de rol o esquema** (defensa contra prompt injection).

### 6.4 Cache y rate limit

* El cache usa **hash del prompt normalizado**: mismo texto → misma receta sin llamar a Groq.
* Si Upstash falla, se degrada a memoria (con un único warning).
* Los prefijos de llaves son contrato operativo: `palette:<env>:rl:*` y `palette:<env>:cache:recipe:*`.
* `MOCK_AI=true` **solo** en local y en tests; nunca en producción.

### 6.5 Flujo de Git

* **PROHIBIDO hacer commits o push sin la aprobación explícita del usuario.**
* **Flujo de ramas:** desarrollo en `develop`; merge a `main` solo tras aprobación.
* **Mensajes de commit:** *Conventional Commits* en minúsculas y español (`feat: …`, `fix: …`, `chore: …`).

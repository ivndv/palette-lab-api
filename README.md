# Palette Lab API

## Descripción

Microservicio de interpretación de paletas con IA para **Palette Lab**. Recibe una descripción en lenguaje natural y devuelve una receta de color válida —base, armonía, tono y etiqueta— que el frontend convierte en una paleta de cinco colores.

Existe para aislar la clave de Groq del navegador y del BFF: la credencial de IA nunca sale de este servicio. La IA **no genera la paleta completa**; solo elige la receta, y el motor determinista de Palette Lab deriva los cinco colores.

## Características

- **Interpretación en lenguaje natural**: acepta descripciones en español o inglés y devuelve siempre una receta JSON válida.
- **Contrato cerrado**: armonías y tonos son enumerados fijos; el frontend nunca recibe un valor desconocido.
- **Salida validada**: la respuesta del modelo pasa por Pydantic antes de salir, sin reenviar JSON crudo.
- **Cache por prompt**: el mismo texto devuelve la misma receta sin gastar cuota de Groq.
- **Rate limiting en tres niveles**: por minuto, por día y global diario.
- **Degradación limpia**: si Upstash no responde, cache y límites caen a memoria.
- **Autenticación simple**: secreto compartido en el header `X-API-Key`.
- **Salud ultraligera**: `/health` no toca base de datos ni IA.
- **Errores explícitos**: cada fallo del proveedor se traduce a un código HTTP concreto.
- **Tests sin cuota**: la IA va mockeada en pytest.

## Secciones

1. **Salud** (`GET /health`): responde `{"status":"ok"}` sin dependencias externas.
2. **Interpretación** (`POST /interpret`): recibe un prompt y devuelve la receta de paleta.
3. **Documentación automática** (`/docs`): Swagger generado por FastAPI.

### Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/health` | `{ "status": "ok" }` |
| `POST` | `/interpret` | Recibe `{ "prompt": "..." }` y devuelve la receta |

### Códigos de error

| Código | Causa |
|---|---|
| `400` | Prompt vacío o mayor a `MAX_PROMPT_LENGTH` (240) |
| `401` | `X-API-Key` ausente o incorrecta |
| `429` | Límite propio superado o cuota de Groq agotada |
| `502` | Groq rechazó la petición o la receta no valida |
| `503` | No se pudo conectar con Groq |
| `504` | Groq tardó más que `GROQ_TIMEOUT_SECONDS` |

## Uso

El consumidor único es el BFF de Palette Lab (`functions/api/interpret.ts`), que llama desde el servidor:

```bash
curl -X POST http://localhost:8010/interpret \
  -H "X-API-Key: tu_secreto" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "atardecer en la playa"}'
```

```json
{
  "base": "#b45309",
  "mode": "analogous",
  "tone": "muted",
  "label": "atardecer cálido"
}
```

- **`base`**: color HEX en minúsculas.
- **`mode`**: `analogous`, `complementary`, `triadic`, `monochrome` o `random`.
- **`tone`**: `balanced`, `pastel`, `vivid`, `muted`, `dark` o `light`.
- **`label`**: descripción corta en español, máximo 60 caracteres.

Si `PALETTE_LAB_API_KEY` está vacío, el header no se exige. Eso es solo para desarrollo local: en producción debe estar configurado.

## Tecnologías Utilizadas

- **Framework**: FastAPI + Uvicorn
- **Configuración**: Pydantic v2 + pydantic-settings
- **IA**: Groq vía SDK de OpenAI, modelo `openai/gpt-oss-20b`
- **Cache y límites**: Upstash Redis (`upstash-ratelimit`) con fallback en memoria
- **Validación**: Pydantic antes de cada respuesta
- **Testing**: pytest, IA mockeada
- **Lint & Formato**: ruff
- **Herramientas**: Python 3.13, uv, Docker
- **Infra & CI/CD**: Docker, Dokploy, GitHub Actions

## Despliegue

El servicio se encuentra desplegado en **Dokploy** y se publica a través de Cloudflare Tunnel. Puedes consultarlo directamente aquí: [api-palettelab.fluxdv.icu](https://api-palettelab.fluxdv.icu/)

## Licencia

Licencia de Uso Personal:

Este software es propiedad de **Ivan Cruz**. Se permite el uso de este software solo para fines personales y no comerciales. No se permite la distribución, modificación ni uso comercial de este software sin el consentimiento expreso de **Ivan Cruz**.

Cualquier uso no autorizado puede resultar en acciones legales.

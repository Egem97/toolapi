# TOOL_API

API REST en FastAPI para **transformar, cargar y proporcionar datos**. El primer caso de uso es la subida de archivos Excel a carpetas compartidas en OneDrive vía Microsoft Graph.

> **Idiomas**: código y mensajes de error en **inglés**, documentación (este archivo, README, comentarios de alto nivel) en **español**.

---

## 1. Stack

| Capa | Tecnología | Versión objetivo |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Framework | FastAPI | ^0.115 |
| Servidor ASGI | Uvicorn (workers) + Gunicorn en prod | latest |
| Validación / settings | Pydantic v2 + `pydantic-settings` | ^2.9 |
| ORM | SQLAlchemy 2.0 async | ^2.0 |
| Migraciones | Alembic | ^1.13 |
| BD | PostgreSQL | 16 |
| Cache / rate limit | Redis + `slowapi` | latest |
| Auth | JWT (HS256) con `python-jose[cryptography]` + `passlib[bcrypt]` (sistema-a-sistema, sin SSO) | — |
| OneDrive / Graph | `msal` (Client Credentials) + `httpx` | ^1.32 / ^0.27 |
| Datos | `pandas`, `polars`, `openpyxl`, `fastexcel` | latest estables |
| HTTP cliente | `httpx` async | ^0.27 |
| Logs | `structlog` | latest |
| Métricas | `prometheus-fastapi-instrumentator` | latest |
| Tests | `pytest`, `pytest-asyncio`, `httpx.AsyncClient` | latest |
| Calidad | `ruff`, `mypy`, `pre-commit` | latest |
| Gestión deps | **uv** (Astral) | latest |
| Contenedor | Docker + docker-compose | — |

**Concurrencia**: 4 workers Uvicorn (Gunicorn `-k uvicorn.workers.UvicornWorker -w 4`) cubren con holgura 15+ usuarios concurrentes y ~1000 req/día.

---

## 2. Estructura del proyecto

```
TOOL_API/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Entrada FastAPI
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings, .env)
│   │   ├── security.py            # JWT: encode/decode, dependencias
│   │   ├── logging.py             # structlog
│   │   └── exceptions.py          # Excepciones de dominio + handlers
│   ├── api/
│   │   └── v1/
│   │       ├── router.py          # Agrega todos los routers v1
│   │       └── endpoints/
│   │           ├── auth.py        # (reservado, sin endpoints activos)
│   │           ├── health.py      # GET /v1/health
│   │           └── onedrive.py    # POST /v1/onedrive/upload
│   ├── schemas/                   # Pydantic models (request/response)
│   │   ├── auth.py
│   │   └── onedrive.py
│   ├── services/                  # Lógica de negocio
│   │   └── onedrive_service.py    # MSAL + Graph upload
│   ├── db/
│   │   ├── session.py             # AsyncEngine + sessionmaker
│   │   └── base.py                # Declarative base
│   └── models/                    # SQLAlchemy ORM models
├── tests/
│   ├── conftest.py
│   └── api/v1/test_onedrive.py
├── alembic/
├── .env.example
├── .gitignore
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md
```

---

## 3. Convenciones

- **Versionado**: todo bajo `/v1/...`. Romper compatibilidad ⇒ `/v2/...`.
- **Zona horaria**: `America/Lima` (GMT-5). Almacenar en BD como **UTC**, convertir en respuesta.
- **Identificadores**: snake_case en JSON (`drive_id`, `folder_id`, `name_file`).
- **Errores**: respuesta uniforme `{"error": {"code": "...", "message": "...", "details": {...}}}`. Mensajes en inglés.
- **Async first**: handlers `async def`. Para librerías sync (pandas, msal) usar `run_in_threadpool`.
- **Auth**: todos los endpoints (excepto `/health`) requieren `Authorization: Bearer <jwt>`. Los tokens son estáticos y de larga duración, generados con `scripts/generate_token.py`. No existe endpoint de login.
- **Logs**: estructurados en JSON, incluir `request_id`.
- **Comentarios en código**: solo cuando el *por qué* no sea obvio. No describir el *qué*.

---

## 4. Variables de entorno (`.env`)

```env
# App
APP_NAME=TOOL_API
APP_ENV=development          # development | staging | production
DEBUG=true
TIMEZONE=America/Lima

# API
API_V1_PREFIX=/v1
CORS_ORIGINS=["http://localhost:3000"]

# Seguridad / JWT
JWT_SECRET=change-me-32-bytes-min
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Cliente sistema-a-sistema (para emitir JWT)
SYSTEM_CLIENT_ID=tool-api-client
SYSTEM_CLIENT_ID=tool-api-client

# Base de datos
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tool_api

# Redis (opcional para rate limit / cache)
REDIS_URL=redis://localhost:6379/0

# Microsoft Graph (Client Credentials - app-only)
MS_TENANT_ID=
MS_CLIENT_ID=
MS_CLIENT_SECRET=
MS_GRAPH_SCOPE=https://graph.microsoft.com/.default
```

---

## 5. Endpoint inicial: subir Excel a OneDrive

`POST /v1/onedrive/upload` — `multipart/form-data`

| Campo | Tipo | Descripción |
|---|---|---|
| `drive_id` | string (form) | ID del drive de OneDrive destino |
| `folder_id` | string (form) | ID de la carpeta destino |
| `name_file` | string (form) | Nombre del archivo (con extensión `.xlsx` o `.xls`) |
| `file` | file (form) | Archivo Excel |

**Reglas**:
- Validar extensión y MIME: solo `.xlsx` (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) y `.xls` (`application/vnd.ms-excel`).
- Subida directa por **PUT** a Graph (`/drives/{drive_id}/items/{folder_id}:/{name_file}:/content`).
- Si existe archivo con mismo nombre ⇒ **replace** (default de Graph en este endpoint).
- Auth Graph: **MSAL Client Credentials** (`MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`).

**Respuesta 201**:
```json
{
  "id": "01ABC...",
  "name": "ventas.xlsx",
  "web_url": "https://...sharepoint.com/...",
  "size": 123456,
  "created_at": "2026-04-13T10:30:00-05:00"
}
```

**Auth requerida**: Bearer JWT estático generado con `scripts/generate_token.py`.

---

## 6. Comandos

### Setup local
```bash
uv sync                         # instala dependencias
cp .env.example .env            # configurar variables
uv run alembic upgrade head     # migraciones (cuando existan)
```

### Desarrollo
```bash
uv run uvicorn app.main:app --reload --port 5555
```

### Producción
```bash
uv run gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:5555
```

### Tests / calidad
```bash
uv run pytest -v
uv run ruff check .
uv run ruff format .
uv run mypy app
```

### Docker
```bash
docker compose up --build
```

---

## 7. Seguridad (checklist)

- [x] JWT con expiración corta (60 min default).
- [x] Secretos solo en `.env` (nunca commitear).
- [x] CORS restringido por entorno.
- [x] Rate limit por IP (`slowapi`): 60 req/min por defecto.
- [x] Validación estricta con Pydantic.
- [x] HTTPS obligatorio en producción (Nginx/Caddy delante).
- [x] Cabeceras seguras (`X-Content-Type-Options`, `X-Frame-Options`, etc.).
- [x] Logs sin secretos ni PII.
- [x] Tokens MSAL cacheados en memoria (renovar al expirar).

---

## 8. Roadmap

1. **v0.1** — Endpoint OneDrive upload + auth JWT + health.
2. **v0.2** — Endpoints de transformación de Excel (lectura, validación, normalización).
3. **v0.3** — Endpoints de consulta de datos desde PostgreSQL.
4. **v0.4** — Tareas en background con Celery/RQ si se necesitan procesos largos.

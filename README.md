# TOOL_API

API REST construida con FastAPI para **transformar, cargar y proporcionar datos**. El primer caso de uso implementado es la subida de archivos Excel a OneDrive mediante Microsoft Graph.

## Prerrequisitos

- Python 3.12
- pip (incluido con Python)
- Docker y Docker Compose v2 (`docker compose`)
- Una aplicacion registrada en Azure AD con permisos app-only de Microsoft Graph (`Files.ReadWrite.All` o `Sites.ReadWrite.All`)

## Instalacion local

```bash
cp .env.example .env
# editar .env con los valores reales

python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# o: .venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Ejecucion en desarrollo

```bash
uvicorn app.main:app --reload --port 5555
```

Documentacion interactiva: http://localhost:5555/docs

## Ejecucion con Docker

```bash
docker compose up --build
```

Servicios incluidos:

- `api` (FastAPI en el puerto 5555)
- `db` (PostgreSQL 16 en el puerto 5432)
- `redis` (Redis 7 en el puerto 6379)

## Calidad y tests

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Variables de entorno

Ver `.env.example` para la lista completa. Variables principales:

| Variable | Descripcion |
|---|---|
| `JWT_SECRET` | Clave secreta para firmar JWT (minimo 32 bytes) |
| `SYSTEM_CLIENT_ID` | Identificador del sistema (sub del JWT, default `tool-api-client`) |
| `MS_TENANT_ID` / `MS_CLIENT_ID` / `MS_CLIENT_SECRET` | App registration de Azure AD |
| `DATABASE_URL` | URL de PostgreSQL (driver asyncpg) |
| `REDIS_URL` | URL de Redis para rate limiting |
| `CORS_ORIGINS` | Lista JSON de origenes permitidos |

## Autenticacion

El API usa **tokens JWT estáticos**. Se generan una sola vez y se entregan al consumidor.

**Generar token:**

```bash
python scripts/generate_token.py
# opciones:
python scripts/generate_token.py --subject mi-sistema --days 180
```

El token resultante se usa en todas las llamadas:

```
Authorization: Bearer eyJ...
```

No existe endpoint de login — la aplicacion no expone credenciales al exterior.

## Endpoints

### `GET /v1/health`

Check de salud. No requiere autenticacion.

### `POST /v1/onedrive/upload`

Sube un archivo Excel a una carpeta de OneDrive. Requiere Bearer JWT.

```bash
curl -X POST http://localhost:5555/v1/onedrive/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "drive_id=b!xxxx" \
  -F "folder_id=01ABC..." \
  -F "name_file=ventas.xlsx" \
  -F "file=@./ventas.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

Respuesta 201:

```json
{
  "id": "01ABC...",
  "name": "ventas.xlsx",
  "web_url": "https://...sharepoint.com/...",
  "size": 123456,
  "created_at": "2026-04-13T10:30:00-05:00"
}
```

Reglas de validacion:

- Solo extensiones `.xlsx` y `.xls`.
- El `Content-Type` del archivo debe coincidir con la extension.
- Si existe un archivo con el mismo nombre, Graph realiza reemplazo automatico (`conflictBehavior=replace`).

## Formato de errores

Todas las respuestas de error siguen el mismo esquema:

```json
{
  "error": {
    "code": "CODE_IN_SNAKE_OR_UPPER",
    "message": "Human readable message",
    "details": { }
  }
}
```

## Observabilidad

- Metricas Prometheus en `/metrics`.
- Logs JSON estructurados con `structlog`.
- Rate limit por IP (`slowapi`) configurable via `RATE_LIMIT_DEFAULT`.

## Despliegue en VPS (Ubuntu)

### Primera vez

```bash
# En el VPS:
git clone https://github.com/TU_USUARIO/TOOL_API.git
cd TOOL_API
cp .env.example .env
nano .env          # rellenar JWT_SECRET, MS_*, POSTGRES_*, etc.
bash deploy.sh
```

### Actualizar tras un push

```bash
# En el VPS:
cd TOOL_API
bash deploy.sh
```

El script hace: `git pull` → `docker compose up --build -d` → limpia imágenes viejas → muestra estado y URL.

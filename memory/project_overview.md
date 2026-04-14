---
name: TOOL_API project overview
description: FastAPI project for data transformation/loading/serving; first endpoint uploads Excel files to OneDrive via Microsoft Graph
type: project
---

TOOL_API es un FastAPI en `c:\Users\EdwardoEnriquez\Documents\TOOL_API` para transformar, cargar y proveer datos. Stack confirmado: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, PostgreSQL 16, Redis (cache/rate limit), JWT sistema-a-sistema, MSAL (client credentials) para Microsoft Graph, uv para deps, Docker.

**Why:** Usuario necesita API seguro para 15+ usuarios concurrentes y ~1000 req/día. Consumo solo sistema-a-sistema (no SSO). Despliegue en Linux Ubuntu. Zona horaria America/Lima (GMT-5). Idiomas: código y mensajes en inglés, docs en español.

**How to apply:**
- Mantener versionado `/v1/...` desde el inicio.
- Primer endpoint: `POST /v1/onedrive/upload` (multipart con drive_id, folder_id, name_file, file). Solo .xlsx/.xls. Replace si existe. MSAL Client Credentials.
- Archivos no superan ~500 MB pero típicamente son tablas de 20k filas x 20 cols (uso de polars/pandas).
- Ver CLAUDE.md para estructura, env vars y comandos.

# Endpoint Kissflow — Descarga de adjuntos

Recupera los adjuntos de un item (instancia) de un proceso Kissflow y los
devuelve codificados en **base64**. Maneja N archivos en un solo campo.

---

## Resumen

| | |
|---|---|
| **Método / Ruta** | `POST /v1/kissflow/attachments` |
| **Auth** | `Authorization: Bearer <jwt>` (token estático, ver abajo) |
| **Content-Type** | `application/json` |
| **Respuesta OK** | `200 OK` |

---

## Configuración previa (`.env`)

El endpoint lee credenciales, cuenta y subdominio del entorno. Asegúrate de
tener estas variables definidas:

```env
KISSFLOW_SUBDOMAIN=alzaperu
KISSFLOW_ACCOUNT_ID=<account_id>
KISSFLOW_ACCESS_KEY_ID=<access_key_id>
KISSFLOW_ACCESS_KEY_SECRET=<access_key_secret>
```

Si falta alguna, el endpoint responde `500 KISSFLOW_CONFIG_MISSING`.

---

## Request

### Cuerpo (JSON)

| Campo | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `process_id` | string | sí | — | ID del proceso (`_flow_id` del item). |
| `instance_id` | string | sí | — | `_id` del item enviado (NO el `_root_process_instance`). |
| `activity_instance_id` | string | sí | — | `_id` del paso donde se subió el archivo (en `_previous_context` / `_current_context`). NO es el `_activity_id` de definición. |
| `field_id` | string | no | `"Files"` | Nombre del campo de tipo Attachment. |

> Los identificadores se validan con el patrón `^[A-Za-z0-9!_\-]{1,200}$`.
> Un valor inválido devuelve `422 VALIDATION_ERROR`.

### Ejemplo

```json
{
  "process_id": "PRUEBAS_CPRODUCE_UPLOAD_FILES",
  "instance_id": "PkDaST4_kSys",
  "activity_instance_id": "PkDaST4aDoKK",
  "field_id": "Files"
}
```

---

## Response

### `200 OK`

```json
{
  "count": 1,
  "attachments": [
    {
      "name": "documento_prueba.pdf",
      "base64": "JVBERi0xLjQKJ..."
    }
  ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `count` | int | Cantidad de adjuntos devueltos. |
| `attachments` | array | Lista de adjuntos. Vacía si el campo no tiene archivos válidos. |
| `attachments[].name` | string | Nombre del archivo. |
| `attachments[].base64` | string | Contenido del archivo en base64 (ASCII). |

---

## Errores

Todos los errores siguen el formato uniforme de la API:

```json
{ "error": { "code": "...", "message": "...", "details": { } } }
```

| HTTP | `code` | Causa |
|---|---|---|
| 401 | `UNAUTHORIZED` / `INVALID_TOKEN` | Falta el Bearer token o es inválido/expirado. |
| 409 | `KISSFLOW_ITEM_DRAFT` | El item está en estado `Draft`: Kissflow no expone sus adjuntos vía API. Envía el item y reintenta. |
| 422 | `VALIDATION_ERROR` | Algún identificador no cumple el patrón permitido. |
| 500 | `KISSFLOW_CONFIG_MISSING` | Faltan variables `KISSFLOW_*` en el entorno. |
| 502 | `KISSFLOW_REQUEST_FAILED` | Kissflow respondió con error (401/403/404, etc.). El campo `details.upstream_status` trae el código original. |

---

## Ejemplos de uso

### cURL

```bash
curl -X POST "http://localhost:5555/v1/kissflow/attachments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "process_id": "PRUEBAS_CPRODUCE_UPLOAD_FILES",
    "instance_id": "PkDaST4_kSys",
    "activity_instance_id": "PkDaST4aDoKK",
    "field_id": "Files"
  }'
```

### Python (`httpx`)

```python
import base64
import httpx

resp = httpx.post(
    "http://localhost:5555/v1/kissflow/attachments",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "process_id": "PRUEBAS_CPRODUCE_UPLOAD_FILES",
        "instance_id": "PkDaST4_kSys",
        "activity_instance_id": "PkDaST4aDoKK",
        "field_id": "Files",
    },
    timeout=120,
)
resp.raise_for_status()
data = resp.json()

print(f"Adjuntos: {data['count']}")
for att in data["attachments"]:
    with open(att["name"], "wb") as fh:
        fh.write(base64.b64decode(att["base64"]))
    print(f"  guardado: {att['name']}")
```

### JavaScript (`fetch`)

```js
const resp = await fetch("http://localhost:5555/v1/kissflow/attachments", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    process_id: "PRUEBAS_CPRODUCE_UPLOAD_FILES",
    instance_id: "PkDaST4_kSys",
    activity_instance_id: "PkDaST4aDoKK",
    field_id: "Files",
  }),
});

if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
const data = await resp.json();
console.log(`Adjuntos: ${data.count}`);
```

---

## Generar el token (JWT)

Los endpoints (excepto `/health`) requieren un Bearer JWT estático:

```bash
uv run python scripts/generate_token.py
```

Copia el token resultante y úsalo en el header `Authorization: Bearer <token>`.

---

## Notas

- Los archivos viajan en base64 dentro del JSON, lo que incrementa ~33 % el
  tamaño respecto al binario. Para adjuntos muy grandes considera tiempos de
  espera del cliente más altos.
- El endpoint descarga **todos** los adjuntos del campo en una sola llamada;
  cada archivo implica un request adicional a Kissflow.

"""Recuperación de adjuntos de un proceso Kissflow como [{name, base64}].

Credenciales, cuenta y subdominio se leen de la configuración (`.env`); el
endpoint solo aporta los identificadores del item.
"""

import base64
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import status

from app.core.config import settings
from app.core.exceptions import APIError
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUEST_TIMEOUT_SECONDS = 60.0
MAX_REDIRECTS = 5


class KissflowService:
    def _base_url(self) -> str:
        if not (
            settings.KISSFLOW_SUBDOMAIN
            and settings.KISSFLOW_ACCOUNT_ID
            and settings.KISSFLOW_ACCESS_KEY_ID
            and settings.KISSFLOW_ACCESS_KEY_SECRET
        ):
            raise APIError(
                code="KISSFLOW_CONFIG_MISSING",
                message="Kissflow credentials are not configured",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return f"https://{settings.KISSFLOW_SUBDOMAIN}.kissflow.com"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "X-Access-Key-Id": settings.KISSFLOW_ACCESS_KEY_ID,
            "X-Access-Key-Secret": settings.KISSFLOW_ACCESS_KEY_SECRET,
        }

    async def _get_instance(
        self,
        client: httpx.AsyncClient,
        process_id: str,
        instance_id: str,
        activity_instance_id: str,
    ) -> dict[str, Any]:
        # La ruta con activity_instance_id es la que devuelve los campos del
        # formulario; sin ella Kissflow solo regresa metadatos de sistema.
        url = (
            f"{self._base_url()}/process/2/{settings.KISSFLOW_ACCOUNT_ID}/{process_id}"
            f"/{instance_id}/{activity_instance_id}"
        )
        headers = {"Accept": "application/json", **self._auth_headers()}
        response = await client.get(url, headers=headers)
        self._raise_for_upstream(response, "fetch_instance")
        return response.json()

    async def _download_attachment_bytes(
        self,
        client: httpx.AsyncClient,
        process_id: str,
        instance_id: str,
        activity_instance_id: str,
        field_id: str,
        att_id: str,
    ) -> bytes:
        url = (
            f"{self._base_url()}/process/2/{settings.KISSFLOW_ACCOUNT_ID}/{process_id}"
            f"/{instance_id}/{activity_instance_id}/{field_id}/attachment/{att_id}"
        )
        headers = {"Accept": "application/octet-stream", **self._auth_headers()}
        response = await client.get(url, headers=headers)
        # Kissflow responde 302 hacia una URL firmada de almacenamiento. Se siguen
        # los redirects manualmente conservando las credenciales solo mientras se
        # permanezca en el host de Kissflow; nunca se reenvían a un host externo.
        for _ in range(MAX_REDIRECTS):
            if not response.is_redirect:
                break
            location = response.headers.get("location")
            if not location:
                break
            redirect_url = httpx.URL(urljoin(str(response.url), location))
            same_host = redirect_url.host == response.url.host
            response = await client.get(
                redirect_url, headers=headers if same_host else {}
            )
        self._raise_for_upstream(response, "download_attachment")
        return response.content

    def _raise_for_upstream(self, response: httpx.Response, op: str) -> None:
        if response.is_success:
            return
        logger.error(
            "kissflow_request_failed",
            operation=op,
            status_code=response.status_code,
        )
        raise APIError(
            code="KISSFLOW_REQUEST_FAILED",
            message="Kissflow request failed",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"upstream_status": response.status_code},
        )

    async def get_attachments_base64(
        self,
        process_id: str,
        instance_id: str,
        activity_instance_id: str,
        field_id: str = "Files",
    ) -> list[dict[str, str]]:
        """Devuelve los adjuntos del item como ``[{"name", "base64"}, ...]``.

        Itera sobre cada adjunto del campo ``field_id``, descarga el binario y
        lo codifica en base64. Lista vacía si el campo no trae adjuntos válidos.
        """
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            instance = await self._get_instance(
                client, process_id, instance_id, activity_instance_id
            )

            if instance.get("_status") == "Draft":
                raise APIError(
                    code="KISSFLOW_ITEM_DRAFT",
                    message=(
                        "Item is in 'Draft' status: Kissflow does not expose its "
                        "attachments via API. Submit the item and retry."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                    details={"instance_id": instance_id},
                )

            attachments = _extract_attachments(instance.get(field_id))

            result: list[dict[str, str]] = []
            for i, att in enumerate(attachments, 1):
                att_id = _attachment_id(att)
                if not att_id:
                    continue
                name = _attachment_name(att, f"adjunto_{i}")
                content = await self._download_attachment_bytes(
                    client,
                    process_id,
                    instance_id,
                    activity_instance_id,
                    field_id,
                    att_id,
                )
                result.append(
                    {
                        "name": name,
                        "base64": base64.b64encode(content).decode("ascii"),
                    }
                )
            return result


def _extract_attachments(field_value: Any) -> list[dict[str, Any]]:
    if isinstance(field_value, dict):
        return [field_value]
    if isinstance(field_value, list):
        return [a for a in field_value if isinstance(a, dict)]
    return []


def _attachment_id(att: dict[str, Any]) -> str | None:
    for key in ("_id", "id", "Id", "AttachmentId"):
        if att.get(key):
            return str(att[key])
    return None


def _attachment_name(att: dict[str, Any], fallback: str) -> str:
    for key in ("Name", "name", "FileName", "_name"):
        if att.get(key):
            return str(att[key])
    return fallback


_service_singleton: KissflowService | None = None


def get_kissflow_service() -> KissflowService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = KissflowService()
    return _service_singleton

import asyncio
import io
import json
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd
from fastapi import status
from fastapi.concurrency import run_in_threadpool
from msal import ConfidentialClientApplication

from app.core.config import settings
from app.core.exceptions import APIError
from app.core.logging import get_logger
from app.core.timezone import to_local

logger = get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
UPLOAD_TIMEOUT_SECONDS = 60.0
DOWNLOAD_TIMEOUT_SECONDS = 60.0


@dataclass
class OneDriveUploadResult:
    id: str
    name: str
    web_url: str
    size: int
    created_at: str


@dataclass
class OneDriveDownloadResult:
    id: str
    name: str
    size: int
    content_type: str
    content: bytes


@dataclass
class OneDriveDataResult:
    name: str
    row_count: int
    columns: list[str]
    data: list[dict[str, Any]]


class OneDriveService:
    def __init__(self) -> None:
        self._msal_app: ConfidentialClientApplication | None = None
        # Token se cachea en memoria para evitar ida y vuelta a AAD en cada request.
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def _get_msal_app(self) -> ConfidentialClientApplication:
        if self._msal_app is None:
            if not (settings.MS_TENANT_ID and settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET):
                raise APIError(
                    code="GRAPH_CONFIG_MISSING",
                    message="Microsoft Graph credentials are not configured",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            self._msal_app = ConfidentialClientApplication(
                client_id=settings.MS_CLIENT_ID,
                client_credential=settings.MS_CLIENT_SECRET,
                authority=f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}",
            )
        return self._msal_app

    async def _get_access_token(self) -> str:
        async with self._lock:
            if self._cached_token and time.time() < self._token_expires_at - 60:
                return self._cached_token

            app = self._get_msal_app()
            result: dict[str, Any] = await run_in_threadpool(
                app.acquire_token_for_client, scopes=[settings.MS_GRAPH_SCOPE]
            )
            if "access_token" not in result:
                logger.error(
                    "graph_auth_failed",
                    error_code=result.get("error"),
                )
                raise APIError(
                    code="GRAPH_AUTH_FAILED",
                    message="Failed to acquire Microsoft Graph token",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    details={},
                )
            self._cached_token = result["access_token"]
            self._token_expires_at = time.time() + int(result.get("expires_in", 3600))
            return self._cached_token

    async def upload_excel(
        self,
        drive_id: str,
        folder_id: str,
        name_file: str,
        file_bytes: bytes,
        content_type: str,
    ) -> OneDriveUploadResult:
        token = await self._get_access_token()
        safe_name = urllib.parse.quote(name_file, safe="")
        url = (
            f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}:/{safe_name}:/content"
            "?@microsoft.graph.conflictBehavior=replace"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        }

        async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT_SECONDS) as client:
            response = await client.put(url, headers=headers, content=file_bytes)

        if response.status_code not in (200, 201):
            graph_error_code: str | None = None
            try:
                payload = response.json()
                graph_error_code = (payload.get("error") or {}).get("code")
            except ValueError:
                graph_error_code = None
            logger.error(
                "graph_upload_failed",
                status_code=response.status_code,
                error_code=graph_error_code,
            )
            raise APIError(
                code="GRAPH_UPLOAD_FAILED",
                message="Microsoft Graph upload failed",
                status_code=status.HTTP_502_BAD_GATEWAY,
                details={},
            )

        data = response.json()
        created_raw = data.get("createdDateTime") or data.get("lastModifiedDateTime")
        created_at = _format_created_at(created_raw)

        return OneDriveUploadResult(
            id=data["id"],
            name=data["name"],
            web_url=data.get("webUrl", ""),
            size=int(data.get("size", len(file_bytes))),
            created_at=created_at,
        )

    async def download_file(
        self,
        drive_id: str,
        folder_id: str,
        name_file: str,
    ) -> OneDriveDownloadResult:
        token = await self._get_access_token()
        safe_name = urllib.parse.quote(name_file, safe="")
        base_url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}:/{safe_name}"
        headers = {"Authorization": f"Bearer {token}"}

        # Graph responde el contenido con un 302 a un enlace pre-autenticado en otro
        # host; httpx elimina la cabecera Authorization en redirecciones cross-origin.
        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            meta_response = await client.get(base_url, headers=headers)
            if meta_response.status_code == 404:
                raise APIError(
                    code="GRAPH_FILE_NOT_FOUND",
                    message="File not found in OneDrive",
                    status_code=status.HTTP_404_NOT_FOUND,
                    details={},
                )
            if meta_response.status_code != 200:
                self._raise_download_error(meta_response)

            metadata = meta_response.json()
            content_response = await client.get(f"{base_url}:/content", headers=headers)
            if content_response.status_code != 200:
                self._raise_download_error(content_response)

        content = content_response.content
        graph_file = metadata.get("file") or {}
        content_type = graph_file.get("mimeType") or "application/octet-stream"

        return OneDriveDownloadResult(
            id=metadata["id"],
            name=metadata["name"],
            size=int(metadata.get("size", len(content))),
            content_type=content_type,
            content=content,
        )

    async def download_as_json(
        self,
        drive_id: str,
        folder_id: str,
        name_file: str,
    ) -> OneDriveDataResult:
        downloaded = await self.download_file(drive_id, folder_id, name_file)
        columns, records = await run_in_threadpool(_excel_to_records, downloaded.content)
        return OneDriveDataResult(
            name=downloaded.name,
            row_count=len(records),
            columns=columns,
            data=records,
        )

    def _raise_download_error(self, response: httpx.Response) -> None:
        graph_error_code: str | None = None
        try:
            payload = response.json()
            graph_error_code = (payload.get("error") or {}).get("code")
        except ValueError:
            graph_error_code = None
        logger.error(
            "graph_download_failed",
            status_code=response.status_code,
            error_code=graph_error_code,
        )
        raise APIError(
            code="GRAPH_DOWNLOAD_FAILED",
            message="Microsoft Graph download failed",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={},
        )


def _excel_to_records(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:  # openpyxl/xlrd lanzan varios tipos de error
        logger.error("excel_parse_failed", error=str(exc))
        raise APIError(
            code="EXCEL_PARSE_FAILED",
            message="Failed to parse Excel file",
            status_code=422,
            details={},
        ) from exc

    # to_json normaliza tipos de numpy a nativos y convierte NaN/NaT en null.
    records: list[dict[str, Any]] = json.loads(df.to_json(orient="records", date_format="iso"))
    return [str(col) for col in df.columns], records


def _format_created_at(raw: str | None) -> str:
    from datetime import datetime, timezone

    if not raw:
        dt = datetime.now(tz=timezone.utc)
    else:
        normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            dt = datetime.now(tz=timezone.utc)
    return to_local(dt).isoformat(timespec="seconds")


_service_singleton: OneDriveService | None = None


def get_onedrive_service() -> OneDriveService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = OneDriveService()
    return _service_singleton

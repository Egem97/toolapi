import asyncio
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx
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


@dataclass
class OneDriveUploadResult:
    id: str
    name: str
    web_url: str
    size: int
    created_at: str


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

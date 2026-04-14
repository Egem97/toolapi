from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.onedrive_service import OneDriveUploadResult

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/onedrive/upload")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_invalid_extension(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/onedrive/upload",
        headers=auth_headers,
        data={"drive_id": "d", "folder_id": "f", "name_file": "bad.txt"},
        files={"file": ("bad.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILENAME"


@pytest.mark.asyncio
async def test_upload_invalid_content_type(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/onedrive/upload",
        headers=auth_headers,
        data={"drive_id": "d", "folder_id": "f", "name_file": "ok.xlsx"},
        files={"file": ("ok.xlsx", b"data", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CONTENT_TYPE"


@pytest.mark.asyncio
async def test_upload_success(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    fake_result = OneDriveUploadResult(
        id="01ABC",
        name="ventas.xlsx",
        web_url="https://sharepoint.example.com/ventas.xlsx",
        size=123456,
        created_at="2026-04-13T10:30:00-05:00",
    )

    with patch(
        "app.api.v1.endpoints.onedrive.OneDriveService.upload_excel",
        new=AsyncMock(return_value=fake_result),
    ):
        response = await client.post(
            "/v1/onedrive/upload",
            headers=auth_headers,
            data={
                "drive_id": "drive-1",
                "folder_id": "folder-1",
                "name_file": "ventas.xlsx",
            },
            files={"file": ("ventas.xlsx", b"PK\x03\x04fake-xlsx-bytes", XLSX_CT)},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "01ABC"
    assert body["name"] == "ventas.xlsx"
    assert body["size"] == 123456
    assert body["created_at"].endswith("-05:00")


@pytest.mark.asyncio
async def test_upload_empty_file(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/onedrive/upload",
        headers=auth_headers,
        data={"drive_id": "d", "folder_id": "f", "name_file": "ok.xlsx"},
        files={"file": ("ok.xlsx", b"", XLSX_CT)},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_FILE"

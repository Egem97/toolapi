from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from pathlib import Path

from app.services.onedrive_service import (
    OneDriveDownloadResult,
    OneDriveUploadResult,
)

_FIXTURE_XLSX = Path(__file__).resolve().parent.parent / "bd_dni_supabase.xlsx"

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
async def test_upload_csv_success(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    fake_result = OneDriveUploadResult(
        id="01CSV",
        name="ventas.csv",
        web_url="https://sharepoint.example.com/ventas.csv",
        size=42,
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
                "name_file": "ventas.csv",
            },
            files={"file": ("ventas.csv", b"a,b,c\n1,2,3\n", "text/csv")},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "ventas.csv"


@pytest.mark.asyncio
async def test_upload_csv_alternate_content_type(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    fake_result = OneDriveUploadResult(
        id="01CSV",
        name="ventas.csv",
        web_url="https://sharepoint.example.com/ventas.csv",
        size=42,
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
                "name_file": "ventas.csv",
            },
            files={"file": ("ventas.csv", b"a,b,c\n1,2,3\n", "application/vnd.ms-excel")},
        )

    assert response.status_code == 201


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


@pytest.mark.asyncio
async def test_download_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/onedrive/download")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_invalid_filename(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/onedrive/download",
        headers=auth_headers,
        data={"drive_id": "d", "folder_id": "f", "name_file": "bad.txt"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILENAME"


@pytest.mark.asyncio
async def test_download_success(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    fake_result = OneDriveDownloadResult(
        id="01ABC",
        name="ventas.xlsx",
        size=14,
        content_type=XLSX_CT,
        content=b"PK\x03\x04fake-xl",
    )

    with patch(
        "app.api.v1.endpoints.onedrive.OneDriveService.download_file",
        new=AsyncMock(return_value=fake_result),
    ):
        response = await client.post(
            "/v1/onedrive/download",
            headers=auth_headers,
            data={
                "drive_id": "drive-1",
                "folder_id": "folder-1",
                "name_file": "ventas.xlsx",
            },
        )

    assert response.status_code == 200
    assert response.content == b"PK\x03\x04fake-xl"
    assert response.headers["content-type"] == XLSX_CT
    assert "ventas.xlsx" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_not_found(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    from app.core.exceptions import APIError

    error = APIError(
        code="GRAPH_FILE_NOT_FOUND",
        message="File not found in OneDrive",
        status_code=404,
        details={},
    )

    with patch(
        "app.api.v1.endpoints.onedrive.OneDriveService.download_file",
        new=AsyncMock(side_effect=error),
    ):
        response = await client.post(
            "/v1/onedrive/download",
            headers=auth_headers,
            data={
                "drive_id": "drive-1",
                "folder_id": "folder-1",
                "name_file": "ausente.xlsx",
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GRAPH_FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_data_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/onedrive/data")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_data_rejects_non_excel(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/onedrive/data",
        headers=auth_headers,
        data={"drive_id": "d", "folder_id": "f", "name_file": "datos.csv"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_EXTENSION"


@pytest.mark.asyncio
async def test_data_success(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    downloaded = OneDriveDownloadResult(
        id="01ABC",
        name="bd_dni_supabase.xlsx",
        size=_FIXTURE_XLSX.stat().st_size,
        content_type=XLSX_CT,
        content=_FIXTURE_XLSX.read_bytes(),
    )

    with patch(
        "app.api.v1.endpoints.onedrive.OneDriveService.download_file",
        new=AsyncMock(return_value=downloaded),
    ):
        response = await client.post(
            "/v1/onedrive/data",
            headers=auth_headers,
            data={
                "drive_id": "drive-1",
                "folder_id": "folder-1",
                "name_file": "bd_dni_supabase.xlsx",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "bd_dni_supabase.xlsx"
    assert body["row_count"] == 2100
    assert body["columns"][:2] == ["item", "dni"]
    assert len(body["data"]) == 2100
    first = body["data"][0]
    assert first["item"] == 1
    assert first["dni"] == 43864680
    # NaN del Excel debe transformarse a null en JSON.
    assert first["estado"] is None


@pytest.mark.asyncio
async def test_data_parse_failure(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    downloaded = OneDriveDownloadResult(
        id="01BAD",
        name="corrupto.xlsx",
        size=5,
        content_type=XLSX_CT,
        content=b"not-an-excel",
    )

    with patch(
        "app.api.v1.endpoints.onedrive.OneDriveService.download_file",
        new=AsyncMock(return_value=downloaded),
    ):
        response = await client.post(
            "/v1/onedrive/data",
            headers=auth_headers,
            data={
                "drive_id": "drive-1",
                "folder_id": "folder-1",
                "name_file": "corrupto.xlsx",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXCEL_PARSE_FAILED"

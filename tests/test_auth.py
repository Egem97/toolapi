import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, decode_token
from app.core.exceptions import APIError


def test_valid_token_decodes() -> None:
    token = create_access_token(subject="tool-api-client")
    payload = decode_token(token)
    assert payload["sub"] == "tool-api-client"
    assert payload["iss"] == "TOOL_API"


def test_invalid_token_raises() -> None:
    with pytest.raises(APIError) as exc_info:
        decode_token("invalid.token.here")
    assert exc_info.value.code == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client: AsyncClient) -> None:
    response = await client.post("/v1/onedrive/upload")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_token(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/onedrive/upload",
        headers={"Authorization": "Bearer bad.token.value"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"

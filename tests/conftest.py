import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("SYSTEM_CLIENT_ID", "tool-api-client")
os.environ.setdefault("MS_TENANT_ID", "tenant")
os.environ.setdefault("MS_CLIENT_ID", "client")
os.environ.setdefault("MS_CLIENT_SECRET", "secret")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token(subject="tool-api-client")
    return {"Authorization": f"Bearer {token}"}

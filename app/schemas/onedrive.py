from typing import Any

from pydantic import BaseModel


class OneDriveUploadResponse(BaseModel):
    id: str
    name: str
    web_url: str
    size: int
    created_at: str


class OneDriveDataResponse(BaseModel):
    name: str
    row_count: int
    columns: list[str]
    data: list[dict[str, Any]]

from pydantic import BaseModel


class OneDriveUploadResponse(BaseModel):
    id: str
    name: str
    web_url: str
    size: int
    created_at: str

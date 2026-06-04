from pydantic import BaseModel, Field

_ID_PATTERN = r"^[A-Za-z0-9!_\-]{1,200}$"


class KissflowAttachmentsRequest(BaseModel):
    process_id: str = Field(..., pattern=_ID_PATTERN)
    instance_id: str = Field(..., pattern=_ID_PATTERN)
    activity_instance_id: str = Field(..., pattern=_ID_PATTERN)
    field_id: str = Field(default="Files", pattern=_ID_PATTERN)


class KissflowAttachment(BaseModel):
    name: str
    base64: str


class KissflowAttachmentsResponse(BaseModel):
    count: int
    attachments: list[KissflowAttachment]

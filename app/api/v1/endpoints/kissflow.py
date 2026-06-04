from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.security import get_current_client
from app.schemas.kissflow import (
    KissflowAttachment,
    KissflowAttachmentsRequest,
    KissflowAttachmentsResponse,
)
from app.services.kissflow_service import KissflowService, get_kissflow_service

router = APIRouter()


@router.post(
    "/attachments",
    response_model=KissflowAttachmentsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_attachments(
    payload: KissflowAttachmentsRequest,
    _: Annotated[str, Depends(get_current_client)],
    service: Annotated[KissflowService, Depends(get_kissflow_service)],
) -> KissflowAttachmentsResponse:
    items = await service.get_attachments_base64(
        process_id=payload.process_id,
        instance_id=payload.instance_id,
        activity_instance_id=payload.activity_instance_id,
        field_id=payload.field_id,
    )
    attachments = [KissflowAttachment(name=i["name"], base64=i["base64"]) for i in items]
    return KissflowAttachmentsResponse(count=len(attachments), attachments=attachments)

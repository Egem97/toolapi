from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.security import get_current_client
from app.schemas.kissflow import KissflowAttachment, KissflowAttachmentsRequest
from app.services.kissflow_service import KissflowService, get_kissflow_service

router = APIRouter()


@router.post(
    "/attachments",
    response_model=list[KissflowAttachment],
    status_code=status.HTTP_200_OK,
)
async def get_attachments(
    payload: KissflowAttachmentsRequest,
    _: Annotated[str, Depends(get_current_client)],
    service: Annotated[KissflowService, Depends(get_kissflow_service)],
) -> list[KissflowAttachment]:
    items = await service.get_attachments_base64(
        process_id=payload.process_id,
        instance_id=payload.instance_id,
        activity_instance_id=payload.activity_instance_id,
        field_id=payload.field_id,
    )
    return [KissflowAttachment(name=i["name"], base64=i["base64"]) for i in items]

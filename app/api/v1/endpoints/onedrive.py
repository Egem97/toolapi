import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.core.exceptions import APIError
from app.core.security import get_current_client
from app.schemas.onedrive import OneDriveUploadResponse
from app.services.onedrive_service import OneDriveService, get_onedrive_service

router = APIRouter()

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pdf": "application/pdf",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024  # 1 MB

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\- .]{1,120}\.(xlsx|xls|pdf)$", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9!_\-]{1,200}$")

_MAGIC_BYTES: dict[str, bytes] = {
    ".xlsx": b"PK\x03\x04",
    ".xls": b"\xD0\xCF\x11\xE0",
    ".pdf": b"%PDF",
}


def _validate_file(name_file: str, content_type: str | None) -> str:
    if not _FILENAME_RE.match(name_file):
        raise APIError(
            code="INVALID_FILENAME",
            message="File name contains invalid characters or extension",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"name_file": name_file},
        )
    lower = name_file.lower()
    matched_ext: str | None = None
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            matched_ext = ext
            break
    if matched_ext is None:
        raise APIError(
            code="INVALID_FILE_EXTENSION",
            message="Only .xlsx and .xls files are allowed",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"name_file": name_file},
        )
    expected = ALLOWED_EXTENSIONS[matched_ext]
    if content_type != expected:
        raise APIError(
            code="INVALID_CONTENT_TYPE",
            message="File content type does not match extension",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"expected": expected, "received": content_type or ""},
        )
    return expected


def _validate_identifier(value: str, field: str) -> None:
    if not _IDENTIFIER_RE.match(value):
        raise APIError(
            code="INVALID_IDENTIFIER",
            message="Identifier contains invalid characters",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": field},
        )


def _matched_ext(name_file: str) -> str:
    lower = name_file.lower()
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return ""


@router.post(
    "/upload",
    response_model=OneDriveUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_excel(
    request: Request,
    drive_id: Annotated[str, Form(min_length=1)],
    folder_id: Annotated[str, Form(min_length=1)],
    name_file: Annotated[str, Form(min_length=1)],
    file: Annotated[UploadFile, File(...)],
    _: Annotated[str, Depends(get_current_client)],
    service: Annotated[OneDriveService, Depends(get_onedrive_service)],
) -> OneDriveUploadResponse:
    _validate_identifier(drive_id, "drive_id")
    _validate_identifier(folder_id, "folder_id")
    content_type = _validate_file(name_file, file.content_type)

    # Pre-check via Content-Length header.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_FILE_SIZE_BYTES:
                raise APIError(
                    code="FILE_TOO_LARGE",
                    message="File exceeds maximum allowed size",
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    details={"max_bytes": MAX_FILE_SIZE_BYTES},
                )
        except ValueError:
            pass

    # Chunked read with size enforcement.
    buffer = bytearray()
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_FILE_SIZE_BYTES:
            raise APIError(
                code="FILE_TOO_LARGE",
                message="File exceeds maximum allowed size",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                details={"max_bytes": MAX_FILE_SIZE_BYTES},
            )

    if not buffer:
        raise APIError(
            code="EMPTY_FILE",
            message="Uploaded file is empty",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ext = _matched_ext(name_file)
    magic = _MAGIC_BYTES.get(ext)
    if magic is not None and not bytes(buffer[: len(magic)]).startswith(magic):
        raise APIError(
            code="INVALID_FILE_CONTENT",
            message="File content does not match declared extension",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"extension": ext},
        )

    file_bytes = bytes(buffer)

    result = await service.upload_excel(
        drive_id=drive_id,
        folder_id=folder_id,
        name_file=name_file,
        file_bytes=file_bytes,
        content_type=content_type,
    )

    return OneDriveUploadResponse(
        id=result.id,
        name=result.name,
        web_url=result.web_url,
        size=result.size,
        created_at=result.created_at,
    )

from fastapi import APIRouter

from app.core.timezone import local_now_iso

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": local_now_iso()}

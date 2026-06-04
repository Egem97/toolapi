from fastapi import APIRouter

from app.api.v1.endpoints import health, kissflow, onedrive

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(onedrive.router, prefix="/onedrive", tags=["onedrive"])
api_router.include_router(kissflow.router, prefix="/kissflow", tags=["kissflow"])

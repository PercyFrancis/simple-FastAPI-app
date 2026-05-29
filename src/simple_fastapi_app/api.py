from fastapi import APIRouter

from simple_fastapi_app.item.views import router as item_router


api_router = APIRouter()

@api_router.get("/health/")
def get_health():
    return {"status": "ok"}


api_router.include_router(item_router, prefix="/items", tags=["items"])
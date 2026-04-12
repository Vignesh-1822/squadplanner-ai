"""GET /admin/serpapi-usage — operational metrics."""

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/serpapi-usage")
async def serpapi_usage():
    """Return SerpAPI call counts / quotas (wire to real metrics later)."""
    return {"configured": bool(settings.serpapi_api_key), "calls_today": 0}

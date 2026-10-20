"""Operational admin routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.middleware.authz import require_admin
from config import settings
from db.client import get_collection

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/serpapi-usage")
async def get_serpapi_usage(current_user: dict = Depends(require_admin)):
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = get_collection("api_usage")
    doc = await usage.find_one({"type": "serpapi_usage", "month": current_month})
    calls_used = int(doc["calls_used"]) if doc else 0
    hard_limit = settings.serpapi_monthly_hard_limit
    return {
        "month": current_month,
        "calls_used": calls_used,
        "hard_limit": hard_limit,
        "remaining": hard_limit - calls_used,
    }

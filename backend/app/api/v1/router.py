"""API v1 Router registry."""

from fastapi import APIRouter

from app.api.v1.ai_content import router as ai_content_router
from app.api.v1.assignments import router as assignments_router
from app.api.v1.audit import router as audit_router
from app.api.v1.categories import router as categories_router
from app.api.v1.health import router as health_router
from app.api.v1.media import router as media_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.research import router as research_router
from app.api.v1.sources import router as sources_router
from app.api.v1.stories import router as stories_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.trends import router as trends_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(assignments_router)
api_v1_router.include_router(stories_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(trends_router)
api_v1_router.include_router(opportunities_router)
api_v1_router.include_router(research_router)
api_v1_router.include_router(ai_content_router)
api_v1_router.include_router(media_router)
